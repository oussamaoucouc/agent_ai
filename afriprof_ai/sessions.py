from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, constr
from typing import Optional
from sqlalchemy import create_engine, Column, String, Text, DateTime, ForeignKey, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session as SASession
from datetime import datetime
from teacher_agent.config import DB_URL, get_current_voice, set_voice, get_runtime_config, get_default_voice
import uuid
import logging
from auth import get_user_from_auth_header

# SQLAlchemy base and engine
Base = declarative_base()


class SessionDB(Base):
    __tablename__ = "app_sessions"
    id = Column(String(64), primary_key=True)
    user_id = Column(String(256), index=True, nullable=False)
    name = Column(String(512), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    messages = relationship(
        "MessageDB",
        cascade="all, delete-orphan",
        back_populates="session",
        order_by="MessageDB.created_at",
    )


class SessionSettingsDB(Base):
    __tablename__ = "app_session_settings"
    # User-level settings: one row per user
    user_id = Column(String(256), primary_key=True)
    voice = Column(String(128), nullable=False, default="af_sky")
    model_id = Column(String(128), nullable=True)
    # JSON array of MCP tool URLs selected by the user (stored as text)
    mcp_tools_urls = Column(Text, nullable=True)
    # JSON array of stdio MCP commands selected by the user (stored as text)
    mcp_stdio_commands = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MessageDB(Base):
    __tablename__ = "app_messages"
    id = Column(String(64), primary_key=True)
    session_id = Column(String(64), ForeignKey("app_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    text = Column(Text, nullable=False)
    sender = Column(String(32), nullable=False)  # 'user' or 'assistant'
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    session = relationship("SessionDB", back_populates="messages")


engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

# Ensure schema aligns with user-level settings.
try:
    insp = inspect(engine)
    cols = [c.get('name') for c in insp.get_columns('app_session_settings')]
    # Add model_id if missing (older deployments)
    if 'model_id' not in cols:
        with engine.connect() as conn:
            conn.exec_driver_sql("ALTER TABLE app_session_settings ADD COLUMN model_id VARCHAR(128)")
            conn.commit()
            logging.info("Added model_id column to app_session_settings (runtime migration)")
    # Add mcp_tools_urls if missing
    if 'mcp_tools_urls' not in cols:
        with engine.connect() as conn:
            conn.exec_driver_sql("ALTER TABLE app_session_settings ADD COLUMN mcp_tools_urls TEXT")
            conn.commit()
            logging.info("Added mcp_tools_urls column to app_session_settings (runtime migration)")
    # Add mcp_stdio_commands if missing
    if 'mcp_stdio_commands' not in cols:
        with engine.connect() as conn:
            conn.exec_driver_sql("ALTER TABLE app_session_settings ADD COLUMN mcp_stdio_commands TEXT")
            conn.commit()
            logging.info("Added mcp_stdio_commands column to app_session_settings (runtime migration)")
    # Migrate away from session_id if present to user-level PK
    if 'session_id' in cols:
        with engine.connect() as conn:
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS app_session_settings_new (
                    user_id VARCHAR(256) PRIMARY KEY,
                    voice VARCHAR(128) NOT NULL,
                    model_id VARCHAR(128),
                    updated_at TIMESTAMP NOT NULL
                );
                """
            )
            conn.exec_driver_sql(
                """
                INSERT INTO app_session_settings_new (user_id, voice, model_id, updated_at)
                SELECT DISTINCT ON (user_id)
                    user_id,
                    COALESCE(voice, 'af_sky') AS voice,
                    model_id,
                    COALESCE(updated_at, CURRENT_TIMESTAMP) AS updated_at
                FROM app_session_settings
                ORDER BY user_id, updated_at DESC NULLS LAST;
                """
            )
            conn.exec_driver_sql("DROP TABLE app_session_settings")
            conn.exec_driver_sql("ALTER TABLE app_session_settings_new RENAME TO app_session_settings")
            conn.commit()
            logging.info("Migrated app_session_settings to user-level schema (dropped session_id).")
except Exception as e:
    logging.warning(f"Settings schema migration skipped or partially applied: {e}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Pydantic models
class MessageModel(BaseModel):
    id: str
    text: str
    sender: constr(strip_whitespace=True)
    createdAt: Optional[str] = None


class SessionModel(BaseModel):
    id: str
    name: str
    createdAt: str
    messages: list[MessageModel]


def _db_to_session_model(s: SessionDB) -> SessionModel:
    return SessionModel(
        id=s.id,
        name=s.name,
        createdAt=s.created_at.isoformat(),
        messages=[
            MessageModel(
                id=m.id,
                text=m.text,
                sender=m.sender,
                createdAt=m.created_at.isoformat(),
            )
            for m in s.messages
        ],
    )


def get_session_voice(db: SASession, user_id: str, session_id: str) -> str:
    settings = (
        db.query(SessionSettingsDB)
        .filter(SessionSettingsDB.user_id == user_id)
        .order_by(SessionSettingsDB.updated_at.desc())
        .first()
    )
    candidate = (settings.voice if settings and settings.voice else None) or get_default_voice()
    try:
        cfg = get_runtime_config()
        available = cfg.get("available_voices", []) or []
        if not candidate or candidate not in available:
            corrected = get_default_voice()
            if settings:
                from datetime import datetime as _dt
                settings.voice = corrected
                settings.updated_at = _dt.utcnow()
                db.commit()
            logging.info(
                f"Session voice resolve: user={user_id}, session={session_id} invalid or unset -> corrected to {corrected}"
            )
            return corrected
    except Exception:
        pass
    return candidate


def apply_session_voice(db: SASession, user_id: str, session_id: str) -> str:
    voice = get_session_voice(db, user_id, session_id)
    try:
        set_voice(voice)
        logging.info(f"Applied session voice: user={user_id}, session={session_id}, voice={voice}")
    except Exception:
        # If setting voice fails (unlikely), continue with current config
        logging.warning("Failed to apply session voice; continuing with current config.")
    return voice

# --- Per-session model helpers ---
from teacher_agent.config import get_current_model_id, set_model_id, get_runtime_config, get_default_model_id
import logging

def get_session_model_id(db: SASession, user_id: str, session_id: str) -> str:
    """Resolve model by user-level preference (latest), validated against available_models.
    Falls back to first available model.
    """
    settings = (
        db.query(SessionSettingsDB)
        .filter(SessionSettingsDB.user_id == user_id)
        .order_by(SessionSettingsDB.updated_at.desc())
        .first()
    )
    candidate = (settings.model_id if settings and settings.model_id else None) or get_default_model_id()
    try:
        cfg = get_runtime_config()
        available = cfg.get("available_models", []) or []
        if not candidate or candidate not in available:
            corrected = get_default_model_id()
            if settings:
                from datetime import datetime as _dt
                settings.model_id = corrected
                settings.updated_at = _dt.utcnow()
                db.commit()
            logging.info(
                f"Session model resolve: user={user_id}, session={session_id} invalid or unset -> corrected to {corrected}"
            )
            return corrected
    except Exception:
        pass
    logging.info(f"Session model resolve: user={user_id}, session={session_id}, model_id={candidate}")
    return candidate

def apply_session_model(db: SASession, user_id: str, session_id: str) -> str:
    """Apply the session-specific model to runtime config and return it."""
    model_id = get_session_model_id(db, user_id, session_id)
    try:
        set_model_id(model_id)
        logging.info(f"Applied session model: user={user_id}, session={session_id}, model_id={model_id}")
    except Exception as e:
        logging.warning(f"Failed to apply session model; continuing with current config. err={e}")
    return model_id

# --- MCP tools selection helpers ---
import json as _json
from teacher_agent.config import get_runtime_config as _get_runtime_config

def get_session_mcp_tools_urls(db: SASession, user_id: str, session_id: str) -> list[str]:
    """Resolve MCP tool URLs by user-level preference (JSON array in mcp_tools_urls).
    If the user has not selected any tools, return an empty list (no fallback).
    """
    settings = (
        db.query(SessionSettingsDB)
        .filter(SessionSettingsDB.user_id == user_id)
        .order_by(SessionSettingsDB.updated_at.desc())
        .first()
    )
    urls: list[str] = []
    if settings and settings.mcp_tools_urls:
        try:
            parsed = _json.loads(settings.mcp_tools_urls)
            if isinstance(parsed, list):
                urls = [str(u) for u in parsed if isinstance(u, str) and u.strip()]
        except Exception:
            urls = []
    # Do not fallback to global config; default to no tools selected
    return urls

def get_session_mcp_stdio_commands(db: SASession, user_id: str, session_id: str) -> list[str]:
    """Resolve stdio MCP commands by user-level preference (JSON array in mcp_stdio_commands).
    If the user has not selected any commands, return an empty list (no fallback).
    """
    settings = (
        db.query(SessionSettingsDB)
        .filter(SessionSettingsDB.user_id == user_id)
        .order_by(SessionSettingsDB.updated_at.desc())
        .first()
    )
    cmds: list[str] = []
    if settings and settings.mcp_stdio_commands:
        try:
            parsed = _json.loads(settings.mcp_stdio_commands)
            if isinstance(parsed, list):
                cmds = [str(c).strip() for c in parsed if isinstance(c, str) and str(c).strip()]
        except Exception:
            cmds = []
    return cmds


class CreateSessionRequest(BaseModel):
    user_id: str


class RenameSessionRequest(BaseModel):
    user_id: str
    name: constr(strip_whitespace=True, min_length=1, max_length=512)


class DeleteSessionRequest(BaseModel):
    user_id: str


class SaveMessagesRequest(BaseModel):
    user_id: str
    messages: list[MessageModel]


# Router definition
router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionModel])
async def list_sessions(user_id: str = Query(None), request: Request = None, db: SASession = Depends(get_db)):
    try:
        # Derive identity from bearer token if present
        token_payload = get_user_from_auth_header(request.headers.get("Authorization")) if request else None
        uid = user_id or (token_payload.get("uid") if token_payload else None)
        if not uid:
            raise HTTPException(status_code=401, detail="Unauthorized")
        sessions = db.query(SessionDB).filter(SessionDB.user_id == uid).order_by(SessionDB.created_at.desc()).all()
        return [_db_to_session_model(s) for s in sessions]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching sessions: {str(e)}")


@router.post("", response_model=SessionModel)
async def create_session(request: CreateSessionRequest, http_request: Request = None, db: SASession = Depends(get_db)):
    try:
        token_payload = get_user_from_auth_header(http_request.headers.get("Authorization")) if http_request else None
        uid = (token_payload.get("uid") if token_payload else request.user_id)
        if not uid:
            raise HTTPException(status_code=401, detail="Unauthorized")
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        name = f"Session - {datetime.now().isoformat()}"
        s = SessionDB(id=session_id, user_id=uid, name=name, created_at=now)
        db.add(s)
        greet_msg = MessageDB(
            id=str(uuid.uuid4()),
            session_id=session_id,
            text="Hello! I am your AI Assistant. How can I help you today?",
            sender="assistant",
            created_at=now,
        )
        db.add(greet_msg)
        # Ensure user-level settings exist once; do not duplicate per session
        if not db.query(SessionSettingsDB).filter(SessionSettingsDB.user_id == uid).first():
            default_voice = get_default_voice()
            from teacher_agent.config import get_default_model_id
            default_model = get_default_model_id()
            db.add(SessionSettingsDB(user_id=uid, voice=default_voice, model_id=default_model, updated_at=now))
        db.commit()
        db.refresh(s)
        db.refresh(greet_msg)
        try:
            resolved_model = get_session_model_id(db, uid, session_id)
            resolved_voice = get_session_voice(db, uid, session_id)
            logging.info(f"New session created: user={uid}, session={session_id}, model_id={resolved_model}, voice={resolved_voice}")
        except Exception:
            pass
        return _db_to_session_model(s)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating session: {str(e)}")


@router.put("/{session_id}/rename", response_model=SessionModel)
async def rename_session(session_id: str, request: RenameSessionRequest, http_request: Request = None, db: SASession = Depends(get_db)):
    try:
        token_payload = get_user_from_auth_header(http_request.headers.get("Authorization")) if http_request else None
        uid = (token_payload.get("uid") if token_payload else request.user_id)
        if not uid:
            raise HTTPException(status_code=401, detail="Unauthorized")
        s = db.query(SessionDB).filter(SessionDB.id == session_id, SessionDB.user_id == uid).first()
        if not s:
            raise HTTPException(status_code=404, detail="Session not found")
        s.name = request.name
        db.commit()
        db.refresh(s)
        return _db_to_session_model(s)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error renaming session: {str(e)}")


@router.delete("/{session_id}")
async def delete_session(session_id: str, request: DeleteSessionRequest, http_request: Request = None, db: SASession = Depends(get_db)):
    try:
        token_payload = get_user_from_auth_header(http_request.headers.get("Authorization")) if http_request else None
        uid = (token_payload.get("uid") if token_payload else request.user_id)
        if not uid:
            raise HTTPException(status_code=401, detail="Unauthorized")
        s = db.query(SessionDB).filter(SessionDB.id == session_id, SessionDB.user_id == uid).first()
        if not s:
            raise HTTPException(status_code=404, detail="Session not found")
        # Explicitly delete messages for this session to be robust across deployments
        # where the DB schema may not have ON DELETE CASCADE on the FK.
        try:
            db.query(MessageDB).filter(MessageDB.session_id == session_id).delete(synchronize_session=False)
        except Exception:
            # Non-fatal: if the table doesn't exist or delete fails, continue with session delete
            pass

        # Delete app session (ORM will cascade to app_messages where supported)
        db.delete(s)

        # Also clean up AGNO PostgresStorage rows in agent_session for this user/session.
        # Some agents use plain session_id, others use f"{user_id}_{session_id}".
        try:
            db.execute(
                text(
                    """
                    DELETE FROM agent_session
                    WHERE user_id = :uid AND (session_id = :sid OR session_id = :combined)
                    """
                ),
                {"uid": uid, "sid": session_id, "combined": f"{uid}_{session_id}"},
            )
        except Exception:
            # Non-fatal: agent_session may not exist in some deployments
            pass
        db.commit()
        # No agent SQLite memory DBs to clean up
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting session: {str(e)}")


# --- Session settings retrieval ---
class SessionSettingsResponse(BaseModel):
    model_id: str
    voice: str
    mcp_tools_urls: list[str] = []
    mcp_stdio_commands: list[str] = []


@router.get("/{session_id}/settings", response_model=SessionSettingsResponse)
async def get_session_settings(session_id: str, user_id: str = Query(None), request: Request = None, db: SASession = Depends(get_db)):
    """Return per-session settings (model and voice), falling back to global defaults if unset."""
    try:
        token_payload = get_user_from_auth_header(request.headers.get("Authorization")) if request else None
        uid = user_id or (token_payload.get("uid") if token_payload else None)
        if not uid:
            raise HTTPException(status_code=401, detail="Unauthorized")
        settings = db.query(SessionSettingsDB).filter(SessionSettingsDB.user_id == uid).first()

        # Resolve with fallbacks
        resolved_model = get_session_model_id(db, uid, session_id)
        resolved_voice = get_session_voice(db, uid, session_id)
        resolved_tools = get_session_mcp_tools_urls(db, uid, session_id)
        resolved_stdio = get_session_mcp_stdio_commands(db, uid, session_id)

        logging.info(
            f"Settings resolve: user={uid}, session={session_id}, "
            f"model_id={resolved_model}, voice={resolved_voice}, tools={len(resolved_tools)} URLs, exists={bool(settings)} (user-level)"
        )

        return SessionSettingsResponse(model_id=resolved_model, voice=resolved_voice, mcp_tools_urls=resolved_tools, mcp_stdio_commands=resolved_stdio)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching session settings: {str(e)}")


@router.put("/{session_id}/messages", response_model=SessionModel)
async def save_session_messages(session_id: str, request: SaveMessagesRequest, http_request: Request = None, db: SASession = Depends(get_db)):
    try:
        token_payload = get_user_from_auth_header(http_request.headers.get("Authorization")) if http_request else None
        uid = (token_payload.get("uid") if token_payload else request.user_id)
        if not uid:
            raise HTTPException(status_code=401, detail="Unauthorized")
        s = db.query(SessionDB).filter(SessionDB.id == session_id, SessionDB.user_id == uid).first()
        if not s:
            raise HTTPException(status_code=404, detail="Session not found")

        db.query(MessageDB).filter(MessageDB.session_id == session_id).delete()
        now = datetime.utcnow()
        for msg in request.messages:
            created_at = datetime.fromisoformat(msg.createdAt) if msg.createdAt else now
            db.add(
                MessageDB(
                    id=msg.id,
                    session_id=session_id,
                    text=msg.text,
                    sender=msg.sender,
                    created_at=created_at,
                )
            )
        db.commit()
        db.refresh(s)
        return _db_to_session_model(s)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error saving messages: {str(e)}")