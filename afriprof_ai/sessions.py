from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, constr
from typing import Optional
from sqlalchemy import create_engine, Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session as SASession
from datetime import datetime
from teacher_agent.config import DB_URL, get_current_voice, set_voice
import uuid

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
    # Use session_id as primary key to enforce one settings row per session
    session_id = Column(String(64), ForeignKey("app_sessions.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(String(256), index=True, nullable=False)
    voice = Column(String(128), nullable=False, default="af_sky")
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
    settings = db.query(SessionSettingsDB).filter(SessionSettingsDB.session_id == session_id, SessionSettingsDB.user_id == user_id).first()
    return settings.voice if settings and settings.voice else get_current_voice()


def apply_session_voice(db: SASession, user_id: str, session_id: str) -> str:
    voice = get_session_voice(db, user_id, session_id)
    try:
        set_voice(voice)
    except Exception:
        # If setting voice fails (unlikely), continue with current config
        pass
    return voice


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
async def list_sessions(user_id: str = Query(..., min_length=1), db: SASession = Depends(get_db)):
    try:
        sessions = db.query(SessionDB).filter(SessionDB.user_id == user_id).order_by(SessionDB.created_at.desc()).all()
        return [_db_to_session_model(s) for s in sessions]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching sessions: {str(e)}")


@router.post("", response_model=SessionModel)
async def create_session(request: CreateSessionRequest, db: SASession = Depends(get_db)):
    try:
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        name = f"Session - {datetime.now().isoformat()}"
        s = SessionDB(id=session_id, user_id=request.user_id, name=name, created_at=now)
        db.add(s)
        greet_msg = MessageDB(
            id=str(uuid.uuid4()),
            session_id=session_id,
            text="Hello! I am your AI Assistant. How can I help you today?",
            sender="assistant",
            created_at=now,
        )
        db.add(greet_msg)
        # Create default session settings
        default_voice = get_current_voice()
        settings = SessionSettingsDB(session_id=session_id, user_id=request.user_id, voice=default_voice, updated_at=now)
        db.add(settings)
        db.commit()
        db.refresh(s)
        db.refresh(greet_msg)
        db.refresh(settings)
        return _db_to_session_model(s)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating session: {str(e)}")


@router.put("/{session_id}/rename", response_model=SessionModel)
async def rename_session(session_id: str, request: RenameSessionRequest, db: SASession = Depends(get_db)):
    try:
        s = db.query(SessionDB).filter(SessionDB.id == session_id, SessionDB.user_id == request.user_id).first()
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
async def delete_session(session_id: str, request: DeleteSessionRequest, db: SASession = Depends(get_db)):
    try:
        s = db.query(SessionDB).filter(SessionDB.id == session_id, SessionDB.user_id == request.user_id).first()
        if not s:
            raise HTTPException(status_code=404, detail="Session not found")
        db.delete(s)
        db.commit()
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting session: {str(e)}")


@router.put("/{session_id}/messages", response_model=SessionModel)
async def save_session_messages(session_id: str, request: SaveMessagesRequest, db: SASession = Depends(get_db)):
    try:
        s = db.query(SessionDB).filter(SessionDB.id == session_id, SessionDB.user_id == request.user_id).first()
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