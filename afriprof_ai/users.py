from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, constr
import json as _json
from sqlalchemy import create_engine, Column, String, DateTime, Integer, UniqueConstraint, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session as SASession
from datetime import datetime
import uuid
import hashlib
import os

from teacher_agent.config import DB_URL, get_user_pdf_dir
import sessions as session_mod
from fastapi import Request
from auth import issue_token, get_user_from_auth_header


# Local SQLAlchemy base separate from sessions.py to avoid circular import
Base = declarative_base()


class UserDB(Base):
    __tablename__ = "app_users"
    # Persisted identifier used across backend capabilities
    id = Column(String(64), primary_key=True)  # user_id
    username = Column(String(256), nullable=False, unique=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), nullable=False, default="user")  # 'admin' or 'user'
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint('username', name='uq_app_users_username'),
    )


engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Schemas ---
class UserCreateRequest(BaseModel):
    username: constr(strip_whitespace=True, min_length=1, max_length=256)
    password: constr(strip_whitespace=True, min_length=4, max_length=256)
    role: constr(strip_whitespace=True, min_length=4, max_length=10)  # 'admin' | 'user'


class UserUpdateRequest(BaseModel):
    password: constr(strip_whitespace=True, min_length=4, max_length=256) | None = None
    role: constr(strip_whitespace=True, min_length=4, max_length=10) | None = None


class UserModel(BaseModel):
    id: str
    username: str
    role: str
    createdAt: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    user_id: str
    session_id: str
    username: str
    role: str
    token: str | None = None


class UserStatsModel(BaseModel):
    id: str
    username: str
    role: str
    sessions: int
    documents: int
    mcpTools: int
    createdAt: str


def _hash_password(password: str) -> str:
    # Lightweight hash for demo purposes; replace with bcrypt/argon2 in production
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _db_to_user_model(u: UserDB) -> UserModel:
    return UserModel(id=u.id, username=u.username, role=u.role, createdAt=u.created_at.isoformat())


router = APIRouter(prefix="/users", tags=["users"])


def ensure_admin_seed():
    """Create a default admin user if one does not already exist.
    Credentials are controlled by environment variables:
    - APP_ADMIN_USERNAME (default: 'adi')
    - APP_ADMIN_PASSWORD (default: 'adi123')
    """
    admin_username = os.environ.get("APP_ADMIN_USERNAME", "adi").strip()
    admin_password = os.environ.get("APP_ADMIN_PASSWORD", "adi123").strip()
    if not admin_username or not admin_password:
        return
    db = SessionLocal()
    try:
        existing = db.query(UserDB).filter(UserDB.username == admin_username).first()
        if existing:
            return
        user_id = str(uuid.uuid4())
        u = UserDB(
            id=user_id,
            username=admin_username,
            password_hash=_hash_password(admin_password),
            role="admin",
            created_at=datetime.utcnow(),
        )
        db.add(u)
        db.commit()
        # Ensure document directory exists
        try:
            user_dir = get_user_pdf_dir(user_id)
            os.makedirs(user_dir, exist_ok=True)
        except Exception:
            pass
        # Create default per-user settings on first user creation
        try:
            if not db.query(session_mod.SessionSettingsDB).filter(session_mod.SessionSettingsDB.user_id == user_id).first():
                db.add(session_mod.SessionSettingsDB(
                    user_id=user_id,
                    voice="af_sky",
                    model_id="granite4:tiny-h",
                    updated_at=datetime.utcnow(),
                ))
                db.commit()
        except Exception:
            # Non-fatal: settings can be created later on first session
            pass
    finally:
        db.close()


@router.get("", response_model=list[UserModel])
def list_users(db: SASession = Depends(get_db)):
    try:
        users = db.query(UserDB).order_by(UserDB.created_at.desc()).all()
        return [_db_to_user_model(u) for u in users]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching users: {str(e)}")


@router.post("", response_model=UserModel)
def create_user(request: UserCreateRequest, http_request: Request, db: SASession = Depends(get_db)):
    try:
        # Admin-only
        payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
        if not payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = payload.get("uid")
        role = payload.get("role")
        u_admin = db.query(UserDB).filter(UserDB.id == uid).first()
        if not u_admin or role != "admin" or u_admin.role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        existing = db.query(UserDB).filter(UserDB.username == request.username).first()
        if existing:
            raise HTTPException(status_code=409, detail="Username already exists")
        user_id = str(uuid.uuid4())
        u = UserDB(
            id=user_id,
            username=request.username,
            password_hash=_hash_password(request.password),
            role=request.role if request.role in ("admin", "user") else "user",
            created_at=datetime.utcnow(),
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        # Ensure user has a document folder created
        try:
            user_dir = get_user_pdf_dir(user_id)
            os.makedirs(user_dir, exist_ok=True)
        except Exception:
            # Non-fatal
            pass
        # Initialize default per-user settings at creation
        try:
            if not db.query(session_mod.SessionSettingsDB).filter(session_mod.SessionSettingsDB.user_id == user_id).first():
                db.add(session_mod.SessionSettingsDB(
                    user_id=user_id,
                    voice="af_sky",
                    model_id="granite4:tiny-h",
                    updated_at=datetime.utcnow(),
                ))
                db.commit()
        except Exception:
            # Non-fatal: settings can be created later
            pass
        return _db_to_user_model(u)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")


@router.put("/{user_id}", response_model=UserModel)
def update_user(user_id: str, request: UserUpdateRequest, http_request: Request, db: SASession = Depends(get_db)):
    try:
        # Admin-only
        payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
        if not payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = payload.get("uid")
        role = payload.get("role")
        u_admin = db.query(UserDB).filter(UserDB.id == uid).first()
        if not u_admin or role != "admin" or u_admin.role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        u = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        if request.password:
            u.password_hash = _hash_password(request.password)
        if request.role:
            u.role = request.role if request.role in ("admin", "user") else u.role
        db.commit()
        db.refresh(u)
        return _db_to_user_model(u)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating user: {str(e)}")


@router.delete("/{user_id}")
def delete_user(user_id: str, http_request: Request, db: SASession = Depends(get_db)):
    try:
        # Admin-only
        payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
        if not payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = payload.get("uid")
        role = payload.get("role")
        u_admin = db.query(UserDB).filter(UserDB.id == uid).first()
        if not u_admin or role != "admin" or u_admin.role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        u = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")

        # Clean up sessions/messages/settings for the user
        # These tables are defined in sessions.py with no FK to users; remove manually
        db_sessions = db.query(session_mod.SessionDB).filter(session_mod.SessionDB.user_id == user_id).all()
        for s in db_sessions:
            # Messages and settings use cascade or direct deletes in sessions router
            db.delete(s)

        # Clean up AGNO PostgresStorage rows for this user's sessions
        try:
            db.execute(
                text("DELETE FROM agent_session WHERE user_id = :uid"),
                {"uid": user_id},
            )
        except Exception:
            # Non-fatal: agent_session may not exist in some deployments
            pass

        db.delete(u)
        db.commit()
        # Optionally remove user document directory
        try:
            user_dir = get_user_pdf_dir(user_id)
            if os.path.isdir(user_dir):
                # Leave files if you prefer; here we remove directory
                import shutil
                shutil.rmtree(user_dir, ignore_errors=True)
        except Exception:
            pass
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")


@router.post("/login", response_model=LoginResponse)
def user_login(request: LoginRequest, db: SASession = Depends(get_db)):
    try:
        u = db.query(UserDB).filter(UserDB.username == request.username).first()
        if not u or u.password_hash != _hash_password(request.password):
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # Do NOT auto-create a session on login.
        # Frontend will load sessions and create one only if needed.
        # For admins, this prevents inflating session counts when viewing the dashboard.
        token = issue_token(u.id, u.role)
        return LoginResponse(user_id=u.id, session_id="", username=u.username, role=u.role, token=token)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error during login: {str(e)}")


@router.get("/stats", response_model=list[UserStatsModel])
def user_stats(request: Request, db: SASession = Depends(get_db)):
    """
    Returns dashboard-ready statistics for each user:
    - total sessions per user
    - number of uploaded documents found in the user's PDF directory
    """
    try:
        # Admin-only
        payload = get_user_from_auth_header(request.headers.get("Authorization"))
        if not payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        admin_id = payload.get("uid")
        role = payload.get("role")
        u_admin = db.query(UserDB).filter(UserDB.id == admin_id).first()
        if not u_admin or role != "admin" or u_admin.role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        users = db.query(UserDB).order_by(UserDB.created_at.desc()).all()
        stats: list[UserStatsModel] = []
        # Build a per-user sessions count
        for u in users:
            sess_count = db.query(session_mod.SessionDB).filter(session_mod.SessionDB.user_id == u.id).count()
            # Count documents by scanning user PDF dir
            docs_count = 0
            try:
                user_dir = get_user_pdf_dir(u.id)
                if os.path.isdir(user_dir):
                    docs_count = len([f for f in os.listdir(user_dir) if os.path.isfile(os.path.join(user_dir, f))])
            except Exception:
                pass
            # Count selected MCP tools from session settings (JSON array of URLs)
            tools_count = 0
            try:
                settings = db.query(session_mod.SessionSettingsDB).filter(session_mod.SessionSettingsDB.user_id == u.id).first()
                if settings and settings.mcp_tools_urls:
                    parsed = _json.loads(settings.mcp_tools_urls)
                    if isinstance(parsed, list):
                        tools_count = len([str(x).strip() for x in parsed if isinstance(x, str) and str(x).strip()])
            except Exception:
                tools_count = 0
            stats.append(UserStatsModel(
                id=u.id,
                username=u.username,
                role=u.role,
                sessions=sess_count,
                documents=docs_count,
                mcpTools=tools_count,
                createdAt=u.created_at.isoformat()
            ))
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing user stats: {str(e)}")