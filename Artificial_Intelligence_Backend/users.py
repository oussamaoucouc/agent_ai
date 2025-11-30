from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, constr
import json as _json
from sqlalchemy import create_engine, Column, String, DateTime, Integer, UniqueConstraint, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session as SASession
from datetime import datetime
import uuid
import hashlib
import hmac
import binascii
import secrets
import os

from AI_Agents_Workflows.config import DB_URL, get_user_pdf_dir, get_user_docx_dir, get_user_text_dir, get_user_csv_dir
import sessions as session_mod
from auth import issue_token, get_user_from_auth_header, issue_access_token, issue_refresh_token, verify_refresh_token, APP_ENV
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


class RefreshTokenDB(Base):
    __tablename__ = "refresh_tokens"
    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), index=True, nullable=False)
    jti = Column(String(64), unique=True, nullable=False)
    issued_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Integer, nullable=False, default=0)
    replaced_by = Column(String(64), nullable=True)


class DocumentMetadata(Base):
    __tablename__ = "document_metadata"
    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)  # Owner of the document
    filename = Column(String(256), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_type = Column(String(32), nullable=False)  # pdf, docx, etc.
    uploaded_by = Column(String(64), nullable=False)  # User ID of uploader (admin or user)
    is_admin_uploaded = Column(Integer, default=0)  # 0=False, 1=True
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def store_refresh(db: SASession, user_id: str, jti: str, expires_at: datetime):
    rt = RefreshTokenDB(id=str(uuid.uuid4()), user_id=user_id, jti=jti, issued_at=datetime.utcnow(), expires_at=expires_at, revoked=0, replaced_by=None)
    db.add(rt)
    db.commit()


def revoke_refresh(db: SASession, jti: str, replaced_by: str | None = None):
    rt = db.query(RefreshTokenDB).filter(RefreshTokenDB.jti == jti).first()
    if rt:
        rt.revoked = 1
        rt.replaced_by = replaced_by
        db.commit()


def is_refresh_valid(db: SASession, jti: str) -> bool:
    rt = db.query(RefreshTokenDB).filter(RefreshTokenDB.jti == jti).first()
    if not rt or rt.revoked:
        return False
    return rt.expires_at > datetime.utcnow()


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
    mcpWebTools: int
    mcpLocalTools: int
    createdAt: str


def _hash_password_sha256(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def _hash_password_secure(password: str, iterations: int = 200_000) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    return f"pbkdf2_sha256${iterations}${binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}"

def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        if stored_hash.startswith('pbkdf2_sha256$'):
            _, iter_str, salt_hex, hash_hex = stored_hash.split('$', 3)
            iterations = int(iter_str)
            salt = binascii.unhexlify(salt_hex.encode())
            expected = binascii.unhexlify(hash_hex.encode())
            dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
            return hmac.compare_digest(dk, expected)
        # Fallback for legacy SHA-256
        return _hash_password_sha256(password) == stored_hash
    except Exception as e:
        print(f"❌ _verify_password exception: {e}")
        import traceback
        traceback.print_exc()
        return False


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
            password_hash=_hash_password_secure(admin_password),
            role="admin",
            created_at=datetime.utcnow(),
        )
        db.add(u)
        db.commit()
        # Ensure document directory exists
        try:
            for f in (get_user_pdf_dir, get_user_docx_dir, get_user_text_dir, get_user_csv_dir):
                d = f(user_id)
                os.makedirs(d, exist_ok=True)
        except Exception:
            pass
        # Create default per-user settings on first user creation
        try:
            if not db.query(session_mod.SessionSettingsDB).filter(session_mod.SessionSettingsDB.user_id == user_id).first():
                from AI_Agents_Workflows.config import get_default_model_id, get_default_voice
                db.add(session_mod.SessionSettingsDB(
                    user_id=user_id,
                    voice=get_default_voice(),
                    model_id=get_default_model_id(),
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
            password_hash=_hash_password_secure(request.password),
            role=request.role if request.role in ("admin", "user") else "user",
            created_at=datetime.utcnow(),
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        # Ensure user has a document folder created
        try:
            for f in (get_user_pdf_dir, get_user_docx_dir, get_user_text_dir, get_user_csv_dir):
                d = f(user_id)
                os.makedirs(d, exist_ok=True)
        except Exception:
            pass
        # Initialize default per-user settings at creation
        try:
            if not db.query(session_mod.SessionSettingsDB).filter(session_mod.SessionSettingsDB.user_id == user_id).first():
                from AI_Agents_Workflows.config import get_default_model_id, get_default_voice
                db.add(session_mod.SessionSettingsDB(
                    user_id=user_id,
                    voice=get_default_voice(),
                    model_id=get_default_model_id(),
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
            u.password_hash = _hash_password_secure(request.password)
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
        # Explicitly delete messages first to be robust if FK cascade is missing
        try:
            session_ids = [s.id for s in db_sessions]
            if session_ids:
                db.query(session_mod.MessageDB).filter(session_mod.MessageDB.session_id.in_(session_ids)).delete(synchronize_session=False)
        except Exception:
            # Non-fatal: continue with session delete
            pass
        # Delete sessions (ORM will cascade to messages where supported)
        for s in db_sessions:
            db.delete(s)

        # Remove user-level session settings row(s)
        try:
            db.query(session_mod.SessionSettingsDB).filter(session_mod.SessionSettingsDB.user_id == user_id).delete(synchronize_session=False)
        except Exception:
            # Non-fatal: settings table may not exist in some deployments
            pass

        # Cleanup DocumentMetadata
        try:
            db.query(DocumentMetadata).filter(DocumentMetadata.user_id == user_id).delete(synchronize_session=False)
        except Exception:
            pass

        # Robust deletes: check table existence before deleting, and rollback on errors to avoid transaction abort
        def _delete_if_table_exists(table: str, column_expr: str = "meta_data->>'user_id'"):
            try:
                exists = db.execute(text("SELECT to_regclass(:tname)"), {"tname": table}).scalar()
                if exists:
                    db.execute(text(f"DELETE FROM {table} WHERE {column_expr} = :uid"), {"uid": user_id})
                    db.commit()
            except Exception:
                db.rollback()
        _delete_if_table_exists("agent_session", column_expr="user_id")
        _delete_if_table_exists("ragdocs")
        _delete_if_table_exists("pdf_documents")
        _delete_if_table_exists("docx_documents")
        _delete_if_table_exists("text_documents")
        _delete_if_table_exists("csv_documents")
        _delete_if_table_exists("combined_documents")

        import hashlib
        uid = f"u_{hashlib.sha1(user_id.encode('utf-8')).hexdigest()[:12]}"
        def _drop_table_if_exists(schema_table: str):
            try:
                exists = db.execute(text("SELECT to_regclass(:tname)"), {"tname": schema_table}).scalar()
                if exists:
                    db.execute(text(f"DROP TABLE IF EXISTS {schema_table}"))
                    db.commit()
            except Exception:
                db.rollback()
        for base in ["combined_documents", "pdf_documents", "docx_documents", "text_documents", "csv_documents"]:
            for schema in ["ai", "public"]:
                _drop_table_if_exists(f"{schema}.{base}_{uid}")

        db.delete(u)
        db.commit()
        # Optionally remove user document directory and per-user agent memory DB files
        try:
            import shutil
            for f in (get_user_pdf_dir, get_user_docx_dir, get_user_text_dir, get_user_csv_dir):
                user_dir = f(user_id)
                if os.path.isdir(user_dir):
                    try:
                        shutil.rmtree(user_dir)
                    except Exception:
                        try:
                            for root, dirs, files in os.walk(user_dir, topdown=False):
                                for name in files:
                                    fpath = os.path.join(root, name)
                                    try:
                                        os.remove(fpath)
                                    except Exception:
                                        pass
                                for name in dirs:
                                    dpath = os.path.join(root, name)
                                    try:
                                        os.rmdir(dpath)
                                    except Exception:
                                        pass
                            os.rmdir(user_dir)
                        except Exception:
                            pass
        except Exception:
            pass
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")


@router.post("/login", response_model=LoginResponse)
def user_login(request: LoginRequest, response: Response, db: SASession = Depends(get_db)):
    try:
        print(f"\n=== LOGIN ATTEMPT ===")
        print(f"Username received: '{request.username}'")
        print(f"Password received: '{request.password}'")
        
        u = db.query(UserDB).filter(UserDB.username == request.username).first()
        
        if not u:
            print(f"❌ User not found in database: '{request.username}'")
            # Show available users for debugging
            all_users = db.query(UserDB).all()
            print(f"Available users: {[user.username for user in all_users]}")
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        print(f"✓ User found: {u.username} (ID: {u.id})")
        print(f"  Password hash: {u.password_hash[:50]}...")
        
        password_valid = _verify_password(request.password, u.password_hash)
        print(f"  Password verification: {'✓ PASSED' if password_valid else '❌ FAILED'}")
        
        if not password_valid:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        print(f"✓ Login successful for user: {u.username}")
        
        access = issue_access_token(u.id, u.role)
        refresh = issue_refresh_token(u.id, u.role)
        try:
            payload = verify_refresh_token(refresh)
            exp = datetime.utcfromtimestamp(int(payload.get("exp", 0))) if payload else datetime.utcnow()
            store_refresh(db, u.id, payload.get("jti"), exp)  # type: ignore
        except Exception:
            pass
        secure_flag = True if (APP_ENV == "production") else False
        response.set_cookie(key="refresh_token", value=refresh, httponly=True, secure=secure_flag, samesite="lax", path="/")
        return LoginResponse(user_id=u.id, session_id="", username=u.username, role=u.role, token=access)
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Login error: {e}")
        import traceback
        traceback.print_exc()
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
            docs_count = 0
            try:
                for f in (get_user_pdf_dir, get_user_docx_dir, get_user_text_dir, get_user_csv_dir):
                    d = f(u.id)
                    if os.path.isdir(d):
                        docs_count += len([fpath for fpath in os.listdir(d) if os.path.isfile(os.path.join(d, fpath))])
            except Exception:
                pass
            # Count selected MCP tools from session settings
            tools_count = 0
            web_tools_count = 0
            local_tools_count = 0
            try:
                settings = db.query(session_mod.SessionSettingsDB).filter(session_mod.SessionSettingsDB.user_id == u.id).first()
                if settings and settings.mcp_tools_urls:
                    parsed = _json.loads(settings.mcp_tools_urls)
                    if isinstance(parsed, list):
                        web_tools_count = len([str(x).strip() for x in parsed if isinstance(x, str) and str(x).strip()])
                if settings and settings.mcp_stdio_commands:
                    parsed_stdio = _json.loads(settings.mcp_stdio_commands)
                    if isinstance(parsed_stdio, list):
                        local_tools_count = len([str(x).strip() for x in parsed_stdio if isinstance(x, str) and str(x).strip()])
                tools_count = web_tools_count + local_tools_count
            except Exception:
                tools_count = 0
                web_tools_count = 0
                local_tools_count = 0
            stats.append(UserStatsModel(
                id=u.id,
                username=u.username,
                role=u.role,
                sessions=sess_count,
                documents=docs_count,
                mcpTools=tools_count,
                mcpWebTools=web_tools_count,
                mcpLocalTools=local_tools_count,
                createdAt=u.created_at.isoformat()
            ))
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing user stats: {str(e)}")
