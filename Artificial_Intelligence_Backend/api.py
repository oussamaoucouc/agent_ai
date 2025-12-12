"""
API endpoints for the AI Assistant application (FastAPI app instance).
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, constr
from typing import Optional, Dict, Any, List
import json
import tempfile
import shutil
import os
import time
import datetime
from pydub import AudioSegment
from AI_Agents_Workflows.rag_agent import run_rag_agent, initialize_knowledge_base
from AI_Agents_Workflows.locks import get_user_kb_lock
from AI_Agents_Workflows.ai_agent_assistant import run_assistant_agent
from AI_Agents_Workflows.config import get_user_pdf_dir, get_user_docx_dir, get_user_text_dir, get_user_csv_dir
from AI_Agents_Workflows.mcp_agent import run_agent_async as run_mcp_agent, reset_mcp_gateway_state
from AI_Agents_Workflows.tts import text_to_speech
from AI_Agents_Workflows.sentence_buffer import SentenceBuffer
from AI_Agents_Workflows.config import TTS_DELETE_AFTER_SERVE, TTS_DELETE_DELAY_SECONDS
from typing import Optional
from AI_Agents_Workflows.stt import initialize_stt
import base64
import uuid
from fastapi.responses import FileResponse
from fastapi.concurrency import run_in_threadpool
import asyncio
from datetime import datetime
import sessions
import users
import logging
from auth import get_user_from_auth_header
from auth import verify_refresh_token, issue_access_token, issue_refresh_token, APP_ENV
from users import SessionLocal as _UserSessionLocal, DocumentMetadata
from users import RefreshTokenDB, store_refresh, revoke_refresh, is_refresh_valid
from agno.media import Image, Audio, Video


# Sessions persistence moved to sessions.py


app = FastAPI(
    title="AI Teacher Assistant",
    description="An interactive educational assistant using RAG, speech recognition, and AI",
    version="1.0.0"
)

# CORS configuration
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static media directory for serving uploaded multimodal files
from fastapi.staticfiles import StaticFiles
from pathlib import Path

MEDIA_DIR = Path("/data/media")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


app.include_router(sessions.router)
# Include users router (admin/user management)
app.include_router(users.router)

# Seed default admin on startup
@app.on_event("startup")
def _seed_default_admin():
    try:
        users.ensure_admin_seed()
    except Exception as e:
        logging.warning(f"Admin seeding skipped/failed: {e}")

# Global regex for filtering tool execution logs
import re
tool_log_regex = re.compile(r"[\w_]+\([^)]*\)\s*completed\s+in\s+[\d.]+s\.?", re.IGNORECASE)

# Registry of active tasks per user/session for cancellation
active_tasks: Dict[str, asyncio.Task] = {}

# Helper: robustly clean model output to remove internal reasoning and tool traces
def clean_model_output(text: str) -> str:
    import re
    if not text:
        return ""

    # Remove AGNO tool execution logs like "search(query=...) completed in 1.9721s."
    text = re.sub(r"[\w_]+\([^)]*\)\s*completed\s+in\s+[\d.]+s\.?", "", text, flags=re.IGNORECASE)

    # Remove <think> blocks (case-insensitive, multiline) - these are reasoning traces
    text = re.sub(r'(?is)<think>.*?</think>', '', text)

    # Remove specific chain-of-thought markers ONLY if they're clearly delimited
    labels = [
        'TOOL_CALLS', 'INTERNAL', 'SYSTEM', 'DEBUG', 'SCRATCHPAD'
    ]
    for label in labels:
        # [LABEL] ... [/LABEL]
        text = re.sub(rf'(?is)\[{label}\].*?\[/{label}\]', '', text)

    # Remove common model artifact tokens (chat template markers)
    artifact_tokens = [
        r'<\|im_end\|>', r'<\|im_start\|>', r'<\|eot\|>', r'<eot>', 
        r'</s>', r'<end_of_role>', r'<end_of_turn>', r'end_of_turn'
    ]
    for token in artifact_tokens:
        text = re.sub(token, '', text, flags=re.IGNORECASE)

    # Remove markdown code fences ONLY if they wrap JSON/code blocks (not user content)
    # Only remove fences that start with specific language hints
    text = re.sub(r'```(?:json|python|javascript|bash)\s*(.*?)```', r'\1', text, flags=re.DOTALL)

    # Collapse excessive blank lines and trim
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    text = text.strip()

    return text

def ensure_response_content(text: str) -> str:
    """
    Ensure the model response is not empty.
    Returns a default message if the response is empty or whitespace only.
    """
    if not text or not text.strip():
        return "The model returned an empty response. Please try a different model or rephrase your query."
    return text

# Session models, schemas, and endpoints moved to sessions.py

class LoginRequest(BaseModel):
    username: str

class QueryRequest(BaseModel):
    user_id: str
    session_id: str
    query: constr(strip_whitespace=True, min_length=1, max_length=2000)
    images: Optional[List[str]] = None
    audio: Optional[List[str]] = None
    videos: Optional[List[str]] = None

class QueryResponse(BaseModel):
    user_id: str
    session_id: str
    response: str


class TTSRequest(BaseModel):
    user_id: str
    session_id: str
    text: constr(strip_whitespace=True, min_length=1, max_length=2000)


# --- Pydantic models for session persistence ---

class SetModelRequest(BaseModel):
    user_id: str
    session_id: str
    model: str

class SetVoiceRequest(BaseModel):
    user_id: str
    session_id: str
    voice: str

# Configuration models
class ConfigResponse(BaseModel):
    model: str
    voice: str
    ollama_base_url: str
    openai_base_url: Optional[str] = None
    openai_api_key_set: bool = False
    google_api_key_set: bool = False
    openrouter_api_key_set: bool = False
    agno_api_key_set: bool = False
    gemini_search_enabled: bool = False
    mcp_transport: str
    mcp_server_url: Optional[str] = None
    mcp_stdio_command: Optional[str] = None
    mcp_stdio_args: list[str] = []
    mcp_stdio_commands: list[str] = []
    mcp_stdio_tools: list[Dict[str, Any]] = []
    available_models_labeled: Optional[list[Dict[str, Any]]] = None
    available_models: list[str] = []
    available_voices_labeled: Optional[list[Dict[str, Any]]] = None
    available_voices: list[str] = []
    mcp_servers: list[Dict[str, Any]] = []

class ConfigUpdateRequest(BaseModel):
    user_id: str
    model: Optional[str] = None
    voice: Optional[str] = None
    ollama_base_url: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    agno_api_key: Optional[str] = None
    gemini_search_enabled: Optional[bool] = None
    mcp_transport: Optional[str] = None
    mcp_server_url: Optional[str] = None
    mcp_stdio_command: Optional[str] = None
    mcp_stdio_args: Optional[list[str]] = None
    mcp_stdio_commands: Optional[list[str]] = None
    mcp_stdio_tools: Optional[list[Dict[str, Any]]] = None
    available_models_labeled: Optional[list[Dict[str, Any]]] = None
    available_models: Optional[list[str]] = None
    available_voices_labeled: Optional[list[Dict[str, Any]]] = None
    available_voices: Optional[list[str]] = None
    mcp_servers: Optional[list[Dict[str, Any]]] = None

class ConfigPathResponse(BaseModel):
    config_state_path: str
    exists: bool

class CancelRequest(BaseModel):
    user_id: str
    session_id: str

class ModelCapabilitiesResponse(BaseModel):
    model_id: str
    supports_images: bool
    supports_audio: bool
    supports_videos: bool
    warning: Optional[str] = None

def check_model_multimodal_support(model_id: str) -> dict:
    """
    Check if a model supports multimodal inputs based on configuration.
    Returns dict with supports_images, supports_audio, supports_videos.
    """
    from AI_Agents_Workflows.config import get_model_multimodal_capabilities
    return get_model_multimodal_capabilities(model_id)

@app.post("/cancel")
async def cancel_endpoint(request: CancelRequest, http_request: Request):
    # Auth check
    token_payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
    if not token_payload:
        raise HTTPException(status_code=401, detail="Unauthorized")
    uid = token_payload.get("uid")
    
    # Ensure user can only cancel their own session
    if uid != request.user_id:
        raise HTTPException(status_code=403, detail="Cannot cancel another user's task")

    key = f"{request.user_id}:{request.session_id}"
    task = active_tasks.pop(key, None)
    if task and not task.done():
        task.cancel()
        return {"status": "cancelled"}
    return {"status": "idle"}

@app.get("/check_model_capabilities/{model_id}", response_model=ModelCapabilitiesResponse)
async def check_model_capabilities(model_id: str):
    """Check if a model supports multimodal inputs."""
    caps = check_model_multimodal_support(model_id)
    response = ModelCapabilitiesResponse(
        model_id=model_id,
        **caps
    )
    if not any([caps['supports_images'], caps['supports_audio'], caps['supports_videos']]):
        response.warning = f"The model '{model_id}' doesn't support multimodal inputs. Please select a model like GPT-4o, Claude 3, or Gemini."
    return response

@app.post("/query_assistant_multimodal")
async def query_assistant_multimodal(
    query: str = Form(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    images: list[UploadFile] = File(default=[]),
    audio: list[UploadFile] = File(default=[]),
    videos: list[UploadFile] = File(default=[]),
    http_request: Request = None
):
    """
    Assistant agent query with multimodal input support.
    Accepts images, audio, and video files along with text query.
    """
    key = f"{user_id}:{session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        # Auth check
        token_payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        
        # Get session's model and validate multimodal support
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
            session_model_id = s.model_id if s.model_id else "default"
        
        caps = check_model_multimodal_support(session_model_id)
        
        # Validate media types against model capabilities
        if images and not caps['supports_images']:
            raise HTTPException(
                status_code=400,
                detail=f"The selected model '{session_model_id}' doesn't support image inputs. Please switch to GPT-4o, Claude 3, or Gemini."
            )
        if audio and not caps['supports_audio']:
            raise HTTPException(
                status_code=400,
                detail=f"The selected model '{session_model_id}' doesn't support audio inputs. Please switch to GPT-4o-audio-preview."
            )
        if videos and not caps['supports_videos']:
            raise HTTPException(
                status_code=400,
                detail=f"The selected model '{session_model_id}' doesn't support video inputs. Please switch to Gemini 2.0 Flash."
            )
        
        # Save media files and get Agno media objects
        from AI_Agents_Workflows.media_utils import save_and_process_media
        
        agno_images, agno_audio, agno_videos, media_urls = await save_and_process_media(
            user_id=uid,
            session_id=session_id,
            images=images,
            audio=audio,
            videos=videos
        )
        
        # Run agent with multimodal inputs
        response_text = await run_assistant_agent(
            query=query,
            user_id=uid,
            session_id=session_id,
            images=agno_images,
            audio=agno_audio,
            videos=agno_videos
        )
        
        response_text = clean_model_output(response_text)
        response_text = ensure_response_content(response_text)
        
        return {
            "user_id": uid,
            "session_id": session_id,
            "response": response_text,
            "attached_images": media_urls.get('images', []),
            "attached_audio": media_urls.get('audio', []),
            "attached_videos": media_urls.get('videos', []),
            "status": "success"
        }
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Request cancelled")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in multimodal assistant query: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        active_tasks.pop(key, None)


async def login(request: LoginRequest):
    # In a real application, you would verify the username and create a real session.
    # For now, we'll just generate a user_id and session_id.
    user_id = f"{request.username}_{str(uuid.uuid4())[:8]}"
    session_id = str(uuid.uuid4())
    return {"user_id": user_id, "session_id": session_id}

@app.post("/upload_document", response_model=Dict[str, Any])
async def upload_document_endpoint(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    target_user_id: Optional[str] = Form(None)
):
    try:
        # Auth check
        token_payload = get_user_from_auth_header(request.headers.get("Authorization"))
        auth_user_id = token_payload.get("uid") if token_payload else None
        auth_role = token_payload.get("role") if token_payload else None

        effective_user_id = user_id
        is_admin_upload = False

        if target_user_id:
            if auth_role != "admin":
                raise HTTPException(status_code=403, detail="Admin privileges required to upload for another user")
            effective_user_id = target_user_id
            is_admin_upload = True

        file_extension = os.path.splitext(file.filename)[1].lower()
        allowed = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv"}
        if file_extension not in allowed:
            raise HTTPException(status_code=400, detail="Only pdf, docx, doc, txt, md, csv files are allowed")

        # Save the uploaded file to the per-user PDFs directory (using effective_user_id)
        if file_extension == ".pdf":
            target_dir = str(get_user_pdf_dir(effective_user_id))
            kind = "pdf"
        elif file_extension in {".doc", ".docx"}:
            target_dir = str(get_user_docx_dir(effective_user_id))
            kind = "docx"
        elif file_extension in {".txt", ".md"}:
            target_dir = str(get_user_text_dir(effective_user_id))
            kind = "text"
        else:
            target_dir = str(get_user_csv_dir(effective_user_id))
            kind = "csv"
        os.makedirs(target_dir, exist_ok=True)
        safe_name = os.path.basename(file.filename)
        file_path = os.path.join(target_dir, safe_name)

        # Write upload to a temporary file first
        tmp_name = f".tmp_{uuid.uuid4().hex}{file_extension}"
        tmp_path = os.path.join(target_dir, tmp_name)
        with open(tmp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        def _sha256(path: str) -> str:
            import hashlib
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()

        # If a file with the same name already exists, check for content duplicates
        if os.path.isfile(file_path):
            try:
                if _sha256(file_path) == _sha256(tmp_path):
                    # Exact duplicate: remove temp and skip KB upsert
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                    # Even if duplicate on disk, ensure metadata exists
                    try:
                        with _UserSessionLocal() as db:
                            exists = db.query(DocumentMetadata).filter(
                                DocumentMetadata.user_id == effective_user_id,
                                DocumentMetadata.filename == safe_name
                            ).first()
                            if not exists:
                                doc_meta = DocumentMetadata(
                                    id=str(uuid.uuid4()),
                                    user_id=effective_user_id,
                                    filename=safe_name,
                                    file_path=file_path,
                                    file_type=kind,
                                    uploaded_by=auth_user_id or user_id,
                                    is_admin_uploaded=1 if is_admin_upload else 0
                                )
                                db.add(doc_meta)
                                db.commit()
                    except Exception as e:
                        logging.error(f"Failed to ensure metadata for duplicate: {e}")

                    return {"message": "Already uploaded", "filename": safe_name, "path": file_path, "duplicate": True}
                else:
                    # Same name but different content: generate a unique filename to avoid overwrite
                    base, ext = os.path.splitext(safe_name)
                    counter = 2
                    new_name = f"{base} ({counter}){ext}"
                    new_path = os.path.join(target_dir, new_name)
                    while os.path.exists(new_path):
                        counter += 1
                        new_name = f"{base} ({counter}){ext}"
                        new_path = os.path.join(target_dir, new_name)
                    os.replace(tmp_path, new_path)
                    safe_name = new_name
                    file_path = new_path
            except Exception:
                # On any error during hashing, fall back to renaming to avoid overwrite
                base, ext = os.path.splitext(safe_name)
                counter = 2
                new_name = f"{base} ({counter}){ext}"
                new_path = os.path.join(target_dir, new_name)
                while os.path.exists(new_path):
                    counter += 1
                    new_name = f"{base} ({counter}){ext}"
                    new_path = os.path.join(target_dir, new_name)
                os.replace(tmp_path, new_path)
                safe_name = new_name
                file_path = new_path
        else:
            # No conflict: finalize temp file to target path
            os.replace(tmp_path, file_path)

        # Immediately upsert into KB so the newly added/updated document is indexed
        lock = get_user_kb_lock(effective_user_id)
        logging.info(f"Waiting for KB lock for user {effective_user_id} (upload)")
        async with lock:
            logging.info(f"Entered KB lock for user {effective_user_id} (upload)")
            kb = await initialize_knowledge_base(effective_user_id, only_path=file_path, only_kind=kind)
            try:
                await kb.aload(recreate=False, upsert=True)
                logging.info(f"KB upsert load complete for user {effective_user_id} (upload)")
            except Exception as e:
                # Fallback: first-time collection creation or backend hiccup
                msg = str(e).lower()
                if "not found" in msg or "does not exist" in msg or "no such" in msg:
                    logging.info(f"Upsert failed; recreating collection for user {effective_user_id} (upload)")
                    await kb.aload(recreate=True, upsert=False)
                    logging.info(f"KB recreate load complete for user {effective_user_id} (upload)")
                else:
                    raise

        # Save metadata
        try:
            with _UserSessionLocal() as db:
                doc_meta = DocumentMetadata(
                    id=str(uuid.uuid4()),
                    user_id=effective_user_id,
                    filename=safe_name,
                    file_path=file_path,
                    file_type=kind,
                    uploaded_by=auth_user_id or user_id,
                    is_admin_uploaded=1 if is_admin_upload else 0
                )
                db.add(doc_meta)
                db.commit()
        except Exception as e:
            logging.error(f"Failed to save document metadata: {e}")

        return {"message": f"Successfully uploaded {safe_name}", "filename": safe_name, "path": file_path, "kind": kind}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")

# List documents for a user (persisted on disk)
@app.get("/list_documents", response_model=Dict[str, Any])
async def list_documents(user_id: Optional[str] = None, request: Request = None, target_user_id: Optional[str] = None):
    try:
        # Prefer token user_id if Authorization present
        token_payload = get_user_from_auth_header(request.headers.get("Authorization")) if request else None
        auth_user_id = token_payload.get("uid") if token_payload else None
        auth_role = token_payload.get("role") if token_payload else None

        if not user_id and auth_user_id:
            user_id = auth_user_id
        
        effective_user_id = user_id
        if target_user_id:
            if auth_role != "admin":
                raise HTTPException(status_code=403, detail="Admin privileges required to view another user's documents")
            effective_user_id = target_user_id

        if not effective_user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
            
        dirs = [
            (str(get_user_pdf_dir(effective_user_id)), "pdf", {".pdf"}),
            (str(get_user_docx_dir(effective_user_id)), "docx", {".doc", ".docx"}),
            (str(get_user_text_dir(effective_user_id)), "text", {".txt", ".md"}),
            (str(get_user_csv_dir(effective_user_id)), "csv", {".csv"}),
        ]
        docs = []
        for d, kind, exts in dirs:
            os.makedirs(d, exist_ok=True)
            for name in os.listdir(d):
                if any(name.lower().endswith(ext) for ext in exts):
                    docs.append({"filename": name, "path": os.path.join(d, name), "kind": kind})
        
        # Merge with metadata
        try:
            with _UserSessionLocal() as db:
                metas = db.query(DocumentMetadata).filter(DocumentMetadata.user_id == effective_user_id).all()
                meta_map = {m.filename: m for m in metas}
                
                for doc in docs:
                    fname = doc["filename"]
                    if fname in meta_map:
                        doc["is_admin_uploaded"] = bool(meta_map[fname].is_admin_uploaded)
                        doc["uploaded_by"] = meta_map[fname].uploaded_by
                    else:
                        doc["is_admin_uploaded"] = False
        except Exception as e:
            logging.error(f"Error fetching document metadata: {e}")
            # Fallback to defaults
            for doc in docs:
                if "is_admin_uploaded" not in doc:
                    doc["is_admin_uploaded"] = False

        return {"documents": docs}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")

# Delete a document for a user and sync KB
@app.delete("/delete_document", response_model=Dict[str, str])
async def delete_document(user_id: Optional[str] = None, filename: str = "", kind: Optional[str] = None, request: Request = None):
    try:
        token_payload = get_user_from_auth_header(request.headers.get("Authorization")) if request else None
        auth_user_id = token_payload.get("uid") if token_payload else None
        auth_role = token_payload.get("role") if token_payload else None

        if not user_id and auth_user_id:
            user_id = auth_user_id
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        safe_name = os.path.basename(filename)

        # Permission check: prevent users from deleting admin-uploaded files
        try:
            with _UserSessionLocal() as db:
                meta = db.query(DocumentMetadata).filter(
                    DocumentMetadata.user_id == user_id,
                    DocumentMetadata.filename == safe_name
                ).first()
                if meta and meta.is_admin_uploaded and auth_role != "admin":
                    raise HTTPException(status_code=403, detail="Cannot delete admin-uploaded document")
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error checking document permission: {e}")

        candidates = []
        if kind == "pdf":
            d = str(get_user_pdf_dir(user_id))
            candidates.append(os.path.join(d, safe_name))
        elif kind == "docx":
            d = str(get_user_docx_dir(user_id))
            candidates.append(os.path.join(d, safe_name))
        elif kind == "text":
            d = str(get_user_text_dir(user_id))
            candidates.append(os.path.join(d, safe_name))
        elif kind == "csv":
            d = str(get_user_csv_dir(user_id))
            candidates.append(os.path.join(d, safe_name))
        else:
            for d in [str(get_user_pdf_dir(user_id)), str(get_user_docx_dir(user_id)), str(get_user_text_dir(user_id)), str(get_user_csv_dir(user_id))]:
                candidates.append(os.path.join(d, safe_name))
        file_path = next((p for p in candidates if os.path.isfile(p)), None)
        if not file_path:
            raise HTTPException(status_code=404, detail="File not found")
        def _sha256(path: str) -> str:
            import hashlib
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        try:
            file_sha256 = _sha256(file_path)
        except Exception:
            file_sha256 = ""
        # Robust deletion: retry a few times in case the file is briefly locked (Windows)
        last_err = None
        for attempt in range(5):
            try:
                os.remove(file_path)
                last_err = None
                break
            except PermissionError as e:
                last_err = e
                time.sleep(0.25)
            except Exception as e:
                last_err = e
                break
        if last_err is not None:
            raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(last_err)}")
        
        # Delete metadata record
        try:
            with _UserSessionLocal() as db:
                db.query(DocumentMetadata).filter(
                    DocumentMetadata.user_id == user_id,
                    DocumentMetadata.filename == safe_name
                ).delete()
                db.commit()
        except Exception as e:
            logging.error(f"Error deleting document metadata: {e}")

        lock = get_user_kb_lock(user_id)
        logging.info(f"Waiting for KB lock for user {user_id} (delete)")
        async with lock:
            logging.info(f"Entered KB lock for user {user_id} (delete)")
            from sqlalchemy import text
            from sessions import SessionLocal
            base_name = os.path.splitext(safe_name)[0]
            name_full = safe_name
            name_base = base_name
            params = {"uid": user_id, "sha": file_sha256, "name_full": name_full, "name_base": name_base}
            import hashlib
            uid = f"u_{hashlib.sha1(str(user_id).encode('utf-8')).hexdigest()[:12]}"
            tables_base = [f"combined_documents_{uid}"]
            if kind == "pdf":
                tables_base.append(f"pdf_documents_{uid}")
            elif kind == "docx":
                tables_base.append(f"docx_documents_{uid}")
            elif kind == "text":
                tables_base.append(f"text_documents_{uid}")
            elif kind == "csv":
                tables_base.append(f"csv_documents_{uid}")
            
            # Explicitly check schemas to ensure deletion works regardless of search_path
            schemas = ["rag", "ai"]

            with SessionLocal() as db:
                for base in tables_base:
                    for schema in schemas:
                        t = f"{schema}.{base}"
                        try:
                            exists = db.execute(text("SELECT to_regclass(:tname)"), {"tname": t}).scalar()
                            if exists:
                                db.execute(
                                    text(
                                        f"DELETE FROM {t} WHERE meta_data->>'user_id' = :uid AND ((meta_data->>'file_sha256' = :sha AND :sha <> '') OR name = :name_full OR name = :name_base)"
                                    ),
                                    params,
                                )
                                db.commit()
                        except Exception as e:
                            logging.error(f"Error deleting from {t}: {e}")
                            db.rollback()
        return {"message": "Successfully deleted", "filename": safe_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")

#LLM QUERY (with SSE Streaming)
@app.post("/query")
async def query_agent(request: QueryRequest, http_request: Request):
    key = f"{request.user_id}:{request.session_id}"
    active_tasks[key] = asyncio.current_task()
    
    # Auth check outside the generator
    token_payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
    if not token_payload:
        raise HTTPException(status_code=401, detail="Unauthorized")
    uid = token_payload.get("uid")
    
    with sessions.SessionLocal() as db:
        s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == request.session_id, sessions.SessionDB.user_id == uid).first()
        if not s:
            raise HTTPException(status_code=404, detail="Session not found")

    async def stream_response():
        full_response = ""
        try:
            # Get streaming generator from RAG agent
            stream_gen = await run_rag_agent(
                request.query, uid, request.session_id,
                stream=True
            )
            
            async for chunk in stream_gen:
                if chunk:
                    full_response += chunk
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
            
            # Send done event with complete response
            cleaned_response = ensure_response_content(full_response)
            yield f"data: {json.dumps({'done': True, 'full_response': cleaned_response})}\n\n"
            
        except asyncio.CancelledError:
            yield f"data: {json.dumps({'error': 'Request cancelled'})}\n\n"
        except Exception as e:
            logging.error(f"Error in RAG streaming: {type(e).__name__}: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            active_tasks.pop(key, None)
    
    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# MCP LLM QUERY (with SSE Streaming)
@app.post("/query_mcp")
async def query_mcp(request: QueryRequest, http_request: Request):
    key = f"{request.user_id}:{request.session_id}"
    active_tasks[key] = asyncio.current_task()
    
    # Auth check outside the generator
    token_payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
    if not token_payload:
        raise HTTPException(status_code=401, detail="Unauthorized")
    uid = token_payload.get("uid")
    
    with sessions.SessionLocal() as db:
        s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == request.session_id, sessions.SessionDB.user_id == uid).first()
        if not s:
            raise HTTPException(status_code=404, detail="Session not found")

    # Regex for filtering tool execution logs from streaming chunks
    import re
    tool_log_regex = re.compile(r"[\w_]+\([^)]*\)\s*completed\s+in\s+[\d.]+s\.?", re.IGNORECASE)

    async def stream_response():
        full_response = ""
        try:
            # Get streaming generator from MCP agent
            stream_gen = await run_mcp_agent(
                request.query, uid, request.session_id,
                stream=True
            )
            
            async for chunk in stream_gen:
                if chunk:
                    # Clean each chunk in real-time to prevent tool logs from appearing
                    # Replace with newline to ensure separation (prevents "TitleContent" merging)
                    cleaned_chunk = tool_log_regex.sub("\n", chunk)
                    full_response += chunk  # Keep original for final cleaning
                    # Only send non-empty cleaned chunks
                    if cleaned_chunk.strip():
                        yield f"data: {json.dumps({'content': cleaned_chunk})}\n\n"
            
            # Clean and send done event
            cleaned_response = clean_model_output(full_response)
            cleaned_response = ensure_response_content(cleaned_response)
            yield f"data: {json.dumps({'done': True, 'full_response': cleaned_response})}\n\n"
            
        except asyncio.CancelledError:
            yield f"data: {json.dumps({'error': 'Request cancelled'})}\n\n"
        except Exception as e:
            logging.error(f"Error in MCP streaming: {type(e).__name__}: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            active_tasks.pop(key, None)
    
    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/reset_mcp_gateway")
async def reset_mcp_gateway_endpoint(http_request: Request):
    """
    Reset the MCP Gateway state to force re-registration of servers.
    Call this after adding/removing MCP servers in Docker Desktop MCP Toolkit.
    """
    try:
        token_payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        reset_mcp_gateway_state()
        return {"status": "success", "message": "MCP Gateway state reset. Servers will be re-registered on next query."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ASSISTANT LLM QUERY (with SSE Streaming)
@app.post("/query_assistant")
async def query_assistant(request: QueryRequest, http_request: Request):
    key = f"{request.user_id}:{request.session_id}"
    active_tasks[key] = asyncio.current_task()
    
    # Auth check outside the generator
    token_payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
    if not token_payload:
        raise HTTPException(status_code=401, detail="Unauthorized")
    uid = token_payload.get("uid")
    
    with sessions.SessionLocal() as db:
        s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == request.session_id, sessions.SessionDB.user_id == uid).first()
        if not s:
            raise HTTPException(status_code=404, detail="Session not found")
    
    # Handle images
    images = []
    if request.images:
        for img_str in request.images:
            try:
                # Check if it's a data URI and strip header if present
                if "base64," in img_str:
                    header, encoded = img_str.split("base64,", 1)
                    # Guess extension from header
                    ext = ".png" # Default
                    if "image/jpeg" in header: ext = ".jpg"
                    elif "image/png" in header: ext = ".png"
                    elif "image/webp" in header: ext = ".webp"
                    elif "image/gif" in header: ext = ".gif"
                else:
                    encoded = img_str
                    ext = ".png"

                # Decode base64
                image_data = base64.b64decode(encoded)
                
                # Create temp file
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_img:
                    temp_img.write(image_data)
                    temp_path = temp_img.name
                
                # Add to images list using filepath
                images.append(Image(filepath=temp_path))
                logging.info(f"Processed image to temp file: {temp_path}")
            except Exception as e:
                logging.error(f"Failed to process image: {e}")

    # Handle audio
    audio_files = []
    if request.audio:
        for audio_str in request.audio:
            try:
                # Check if it's a data URI and strip header if present
                if "base64," in audio_str:
                    header, encoded = audio_str.split("base64,", 1)
                    # Guess extension from header
                    ext = ".mp3" # Default
                    if "audio/mpeg" in header: ext = ".mp3"
                    elif "audio/wav" in header: ext = ".wav"
                    elif "audio/ogg" in header: ext = ".ogg"
                    elif "audio/webm" in header: ext = ".webm"
                else:
                    encoded = audio_str
                    ext = ".mp3"

                # Decode base64
                audio_data = base64.b64decode(encoded)
                
                # Create temp file
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_audio:
                    temp_audio.write(audio_data)
                    temp_path = temp_audio.name
                
                # Add to audio list using filepath
                audio_files.append(Audio(filepath=temp_path))
                logging.info(f"Processed audio to temp file: {temp_path}")
            except Exception as e:
                logging.error(f"Failed to process audio: {e}")

    # Handle videos
    video_files = []
    if request.videos:
        for video_str in request.videos:
            try:
                # Check if it's a data URI and strip header if present
                if "base64," in video_str:
                    header, encoded = video_str.split("base64,", 1)
                    # Guess extension from header
                    ext = ".mp4" # Default
                    if "video/mp4" in header: ext = ".mp4"
                    elif "video/webm" in header: ext = ".webm"
                    elif "video/ogg" in header: ext = ".ogg"
                else:
                    encoded = video_str
                    ext = ".mp4"

                # Decode base64
                video_data = base64.b64decode(encoded)
                
                # Create temp file
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_video:
                    temp_video.write(video_data)
                    temp_path = temp_video.name
                
                # Add to videos list using filepath
                video_files.append(Video(filepath=temp_path))
                logging.info(f"Processed video to temp file: {temp_path}")
            except Exception as e:
                logging.error(f"Failed to process video: {e}")

    async def stream_response():
        full_response = ""
        try:
            # Get streaming generator from assistant agent
            stream_gen = await run_assistant_agent(
                request.query, uid, request.session_id,
                images=images if images else None,
                audio=audio_files if audio_files else None,
                videos=video_files if video_files else None,
                stream=True
            )
            
            async for chunk in stream_gen:
                if chunk:
                    full_response += chunk
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
            
            # Send done event with complete response
            cleaned_response = ensure_response_content(full_response)
            yield f"data: {json.dumps({'done': True, 'full_response': cleaned_response})}\n\n"
            
        except asyncio.CancelledError:
            yield f"data: {json.dumps({'error': 'Request cancelled'})}\n\n"
        except Exception as e:
            logging.error(f"Error in assistant streaming: {type(e).__name__}: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            active_tasks.pop(key, None)
    
    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ASSISTANT LLM QUERY not displayed Reasoning (with SSE Streaming)
@app.post("/query_assistant_direct")
async def query_assistant_direct(request: QueryRequest, http_request: Request):
    key = f"{request.user_id}:{request.session_id}"
    active_tasks[key] = asyncio.current_task()
    
    # Auth check outside the generator
    token_payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
    if not token_payload:
        raise HTTPException(status_code=401, detail="Unauthorized")
    uid = token_payload.get("uid")
    
    with sessions.SessionLocal() as db:
        s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == request.session_id, sessions.SessionDB.user_id == uid).first()
        if not s:
            raise HTTPException(status_code=404, detail="Session not found")
    
    # Handle images
    images = []
    if request.images:
        for img_str in request.images:
            try:
                # Check if it's a data URI and strip header if present
                if "base64," in img_str:
                    header, encoded = img_str.split("base64,", 1)
                    # Guess extension from header
                    ext = ".png" # Default
                    if "image/jpeg" in header: ext = ".jpg"
                    elif "image/png" in header: ext = ".png"
                    elif "image/webp" in header: ext = ".webp"
                    elif "image/gif" in header: ext = ".gif"
                else:
                    encoded = img_str
                    ext = ".png"

                # Decode base64
                image_data = base64.b64decode(encoded)
                
                # Create temp file
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_img:
                    temp_img.write(image_data)
                    temp_path = temp_img.name
                
                # Add to images list using filepath
                images.append(Image(filepath=temp_path))
                logging.info(f"Processed image to temp file: {temp_path}")
            except Exception as e:
                logging.error(f"Failed to process image: {e}")

    # Handle audio
    audio_files = []
    if request.audio:
        for audio_str in request.audio:
            try:
                # Check if it's a data URI and strip header if present
                if "base64," in audio_str:
                    header, encoded = audio_str.split("base64,", 1)
                    # Guess extension from header
                    ext = ".mp3" # Default
                    if "audio/mpeg" in header: ext = ".mp3"
                    elif "audio/wav" in header: ext = ".wav"
                    elif "audio/ogg" in header: ext = ".ogg"
                    elif "audio/webm" in header: ext = ".webm"
                else:
                    encoded = audio_str
                    ext = ".mp3"

                # Decode base64
                audio_data = base64.b64decode(encoded)
                
                # Create temp file
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_audio:
                    temp_audio.write(audio_data)
                    temp_path = temp_audio.name
                
                # Add to audio list using filepath
                audio_files.append(Audio(filepath=temp_path))
                logging.info(f"Processed audio to temp file: {temp_path}")
            except Exception as e:
                logging.error(f"Failed to process audio: {e}")

    # Handle videos
    video_files = []
    if request.videos:
        for video_str in request.videos:
            try:
                # Check if it's a data URI and strip header if present
                if "base64," in video_str:
                    header, encoded = video_str.split("base64,", 1)
                    # Guess extension from header
                    ext = ".mp4" # Default
                    if "video/mp4" in header: ext = ".mp4"
                    elif "video/webm" in header: ext = ".webm"
                    elif "video/ogg" in header: ext = ".ogg"
                else:
                    encoded = video_str
                    ext = ".mp4"

                # Decode base64
                video_data = base64.b64decode(encoded)
                
                # Create temp file
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_video:
                    temp_video.write(video_data)
                    temp_path = temp_video.name
                
                # Add to videos list using filepath
                video_files.append(Video(filepath=temp_path))
                logging.info(f"Processed video to temp file: {temp_path}")
            except Exception as e:
                logging.error(f"Failed to process video: {e}")

    async def stream_response():
        full_response = ""
        try:
            # Get streaming generator from assistant agent
            stream_gen = await run_assistant_agent(
                request.query, uid, request.session_id,
                images=images if images else None,
                audio=audio_files if audio_files else None,
                videos=video_files if video_files else None,
                stream=True
            )
            
            async for chunk in stream_gen:
                if chunk:
                    full_response += chunk
                    # SSE format: data: JSON\n\n
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
            
            # Clean the final response and send done event
            cleaned_response = clean_model_output(full_response)
            cleaned_response = ensure_response_content(cleaned_response)
            
            yield f"data: {json.dumps({'done': True, 'full_response': cleaned_response})}\n\n"
            
        except asyncio.CancelledError:
            yield f"data: {json.dumps({'error': 'Request cancelled'})}\n\n"
        except Exception as e:
            logging.error(f"Error in streaming: {type(e).__name__}: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            active_tasks.pop(key, None)
    
    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# MCP LLM QUERY not displayed Reasoning (with SSE Streaming)
@app.post("/query_mcp_direct")
async def query_mcp_direct(request: QueryRequest, http_request: Request):
    key = f"{request.user_id}:{request.session_id}"
    active_tasks[key] = asyncio.current_task()
    
    # Auth check outside the generator
    token_payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
    if not token_payload:
        raise HTTPException(status_code=401, detail="Unauthorized")
    uid = token_payload.get("uid")
    
    with sessions.SessionLocal() as db:
        s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == request.session_id, sessions.SessionDB.user_id == uid).first()
        if not s:
            raise HTTPException(status_code=404, detail="Session not found")

    # Regex for filtering tool execution logs from streaming chunks
    import re
    tool_log_regex = re.compile(r"[\w_]+\([^)]*\)\s*completed\s+in\s+[\d.]+s\.?", re.IGNORECASE)

    async def stream_response():
        full_response = ""
        try:
            # Get streaming generator from MCP agent
            stream_gen = await run_mcp_agent(
                request.query, uid, request.session_id,
                stream=True
            )
            
            async for chunk in stream_gen:
                if chunk:
                    # Clean each chunk in real-time to prevent tool logs from appearing
                    # Replace with newline to ensure separation (prevents "TitleContent" merging)
                    cleaned_chunk = tool_log_regex.sub("\n", chunk)
                    full_response += chunk  # Keep original for final cleaning
                    # Only send non-empty cleaned chunks
                    # SSE format: data: JSON\n\n
                    if cleaned_chunk.strip():
                        yield f"data: {json.dumps({'content': cleaned_chunk})}\n\n"
            
            # Clean the final response and send done event
            cleaned_response = clean_model_output(full_response)
            cleaned_response = ensure_response_content(cleaned_response)
            
            yield f"data: {json.dumps({'done': True, 'full_response': cleaned_response})}\n\n"
            
        except asyncio.CancelledError:
            yield f"data: {json.dumps({'error': 'Request cancelled'})}\n\n"
        except Exception as e:
            logging.error(f"Error in MCP streaming: {type(e).__name__}: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            active_tasks.pop(key, None)
    
    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# MCP Speech-to-text then Query
@app.post("/stt_query_mcp", response_model=Dict[str, str])
async def stt_query_mcp_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    request: Request = None,
):
    key = f"{user_id}:{session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        token_payload = get_user_from_auth_header(request.headers.get("Authorization") if request else None)
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
        # First transcribe the audio
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        # Get the transcribed text
        query_text = stt_result["text"]
        try:
            logging.info(f"STT transcript len={len(query_text)} user={user_id} session={session_id}")
        except Exception:
            pass
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        # Process the query using the MCP agent
        response = await run_mcp_agent(query_text, user_id, session_id)
        response = ensure_response_content(response)

        return {
            "text": query_text,
            "response": response,
            "user_id": user_id,
            "session_id": session_id,
            "status": "success"
        }
    except asyncio.CancelledError:
        logging.warning(f"Task cancelled: user={user_id} session={session_id}")
        return {
            "text": "",
            "response": "Request cancelled by user",
            "user_id": user_id,
            "session_id": session_id,
            "status": "cancelled"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query: {str(e)}")
    finally:
        active_tasks.pop(key, None)

# ASSISTANT Speech-to-text then Query
@app.post("/stt_query_assistant", response_model=Dict[str, str])
async def stt_query_assistant_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    request: Request = None,
):
    key = f"{user_id}:{session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        token_payload = get_user_from_auth_header(request.headers.get("Authorization") if request else None)
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        query_text = stt_result["text"]
        try:
            logging.info(f"STT transcript len={len(query_text)} user={user_id} session={session_id}")
        except Exception:
            pass
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        response = await run_assistant_agent(query_text, user_id, session_id)
        response = ensure_response_content(response)

        return {
            "text": query_text,
            "response": response,
            "user_id": user_id,
            "session_id": session_id,
            "status": "success"
        }
    except asyncio.CancelledError:
        logging.warning(f"Task cancelled: user={user_id} session={session_id}")
        return {
            "text": "",
            "response": "Request cancelled by user",
            "user_id": user_id,
            "session_id": session_id,
            "status": "cancelled"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query: {str(e)}")
    finally:
        active_tasks.pop(key, None)

# ASSISTANT STT then Query, direct (filtered reasoning)
@app.post("/stt_query_assistant_direct", response_model=Dict[str, str])
async def stt_query_assistant_direct_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    request: Request = None,
):
    key = f"{user_id}:{session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        token_payload = get_user_from_auth_header(request.headers.get("Authorization") if request else None)
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        query_text = stt_result["text"]
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        response = await run_assistant_agent(query_text, user_id, session_id)
        response = clean_model_output(response)
        response = ensure_response_content(response)

        return {
            "text": query_text,
            "response": response,
            "user_id": user_id,
            "session_id": session_id,
            "status": "success"
        }
    except asyncio.CancelledError:
        logging.warning(f"Task cancelled: user={user_id} session={session_id}")
        return {
            "text": "",
            "response": "Request cancelled by user",
            "user_id": user_id,
            "session_id": session_id,
            "status": "cancelled"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query: {str(e)}")
    finally:
        active_tasks.pop(key, None)

# MCP STT then Query, direct (filtered reasoning)
@app.post("/stt_query_mcp_direct", response_model=Dict[str, str])
async def stt_query_mcp_direct_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    request: Request = None,
):
    key = f"{user_id}:{session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        token_payload = get_user_from_auth_header(request.headers.get("Authorization") if request else None)
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
        # First transcribe the audio
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        # Get the transcribed text
        query_text = stt_result["text"]
        try:
            logging.info(f"STT transcript len={len(query_text)} user={user_id} session={session_id}")
        except Exception:
            pass
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        # Process the query using the MCP agent
        response = await run_mcp_agent(query_text, user_id, session_id)
        response = clean_model_output(response)
        response = ensure_response_content(response)

        return {
            "text": query_text,
            "response": response,
            "user_id": user_id,
            "session_id": session_id,
            "status": "success"
        }
    except asyncio.CancelledError:
        logging.warning(f"Task cancelled: user={user_id} session={session_id}")
        return {
            "text": "",
            "response": "Request cancelled by user",
            "user_id": user_id,
            "session_id": session_id,
            "status": "cancelled"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query: {str(e)}")
    finally:
        active_tasks.pop(key, None)

# MCP Query then TTS
@app.post("/query_mcp_tts")
async def query_mcp_tts_endpoint(request: QueryRequest, http_request: Request):
    """
    Returns a JSON with the MCP text response, audio filename, and viseme data.
    """
    key = f"{request.user_id}:{request.session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        token_payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == request.session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
        response_text = await run_mcp_agent(request.query, uid, request.session_id)
        response_text = clean_model_output(response_text)
        response_text = ensure_response_content(response_text)

        # Generate audio and visemes
        # Apply per-session voice before generating audio
        with sessions.SessionLocal() as db:
            sessions.apply_session_voice(db, request.user_id, request.session_id)
        audio_path, viseme_data = await run_in_threadpool(text_to_speech, response_text)

        audio_filename = None
        if audio_path:
            audio_filename = os.path.basename(audio_path)

        return {
            "user_id": uid,
            "session_id": request.session_id,
            "response": response_text,
            "audio_filename": audio_filename,
            "visemes": viseme_data,
            "status": "success"
        }
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Request cancelled")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        active_tasks.pop(key, None)

# ASSISTANT Query then TTS
@app.post("/query_assistant_tts")
async def query_assistant_tts_endpoint(request: QueryRequest, http_request: Request):
    """
    Returns a JSON with the assistant text response, audio filename, and viseme data.
    """
    key = f"{request.user_id}:{request.session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        token_payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == request.session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
        
        # Handle images
        images = []
        if request.images:
            for img_str in request.images:
                try:
                    # Check if it's a data URI and strip header if present
                    if "base64," in img_str:
                        header, encoded = img_str.split("base64,", 1)
                        # Guess extension from header
                        ext = ".png" # Default
                        if "image/jpeg" in header: ext = ".jpg"
                        elif "image/png" in header: ext = ".png"
                        elif "image/webp" in header: ext = ".webp"
                        elif "image/gif" in header: ext = ".gif"
                    else:
                        encoded = img_str
                        ext = ".png"

                    # Decode base64
                    image_data = base64.b64decode(encoded)
                    
                    # Create temp file
                    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_img:
                        temp_img.write(image_data)
                        temp_path = temp_img.name
                    
                    # Add to images list using filepath
                    images.append(Image(filepath=temp_path))
                    logging.info(f"Processed image to temp file: {temp_path}")
                except Exception as e:
                    logging.error(f"Failed to process image: {e}")

        # Handle audio
        audio_files = []
        if request.audio:
            for audio_str in request.audio:
                try:
                    # Check if it's a data URI and strip header if present
                    if "base64," in audio_str:
                        header, encoded = audio_str.split("base64,", 1)
                        # Guess extension from header
                        ext = ".mp3" # Default
                        if "audio/mpeg" in header: ext = ".mp3"
                        elif "audio/wav" in header: ext = ".wav"
                        elif "audio/ogg" in header: ext = ".ogg"
                        elif "audio/webm" in header: ext = ".webm"
                    else:
                        encoded = audio_str
                        ext = ".mp3"

                    # Decode base64
                    audio_data = base64.b64decode(encoded)
                    
                    # Create temp file
                    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_audio:
                        temp_audio.write(audio_data)
                        temp_path = temp_audio.name
                    
                    # Add to audio list using filepath
                    audio_files.append(Audio(filepath=temp_path))
                    logging.info(f"Processed audio to temp file: {temp_path}")
                except Exception as e:
                    logging.error(f"Failed to process audio: {e}")

        # Handle videos
        video_files = []
        if request.videos:
            for video_str in request.videos:
                try:
                    # Check if it's a data URI and strip header if present
                    if "base64," in video_str:
                        header, encoded = video_str.split("base64,", 1)
                        # Guess extension from header
                        ext = ".mp4" # Default
                        if "video/mp4" in header: ext = ".mp4"
                        elif "video/webm" in header: ext = ".webm"
                        elif "video/ogg" in header: ext = ".ogg"
                    else:
                        encoded = video_str
                        ext = ".mp4"

                    # Decode base64
                    video_data = base64.b64decode(encoded)
                    
                    # Create temp file
                    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_video:
                        temp_video.write(video_data)
                        temp_path = temp_video.name
                    
                    # Add to videos list using filepath
                    video_files.append(Video(filepath=temp_path))
                    logging.info(f"Processed video to temp file: {temp_path}")
                except Exception as e:
                    logging.error(f"Failed to process video: {e}")

        response_text = await run_assistant_agent(request.query, uid, request.session_id, images=images if images else None, audio=audio_files if audio_files else None, videos=video_files if video_files else None)
        response_text = ensure_response_content(response_text)

        with sessions.SessionLocal() as db:
            sessions.apply_session_voice(db, request.user_id, request.session_id)
        audio_path, viseme_data = await run_in_threadpool(text_to_speech, response_text)

        audio_filename = None
        if audio_path:
            audio_filename = os.path.basename(audio_path)

        return {
            "user_id": uid,
            "session_id": request.session_id,
            "response": response_text,
            "audio_filename": audio_filename,
            "visemes": viseme_data,
            "status": "success"
        }
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Request cancelled")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        active_tasks.pop(key, None)

# ASSISTANT Query direct then TTS (filtered reasoning)
@app.post("/query_assistant_tts_direct")
async def query_assistant_tts_direct(request: QueryRequest, http_request: Request):
    """
    Returns a SSE stream with text chunks, followed by audio filename and viseme data.
    """
    key = f"{request.user_id}:{request.session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        token_payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == request.session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
        
        # Handle images
        images = []
        if request.images:
            for img_str in request.images:
                try:
                    # Check if it's a data URI and strip header if present
                    if "base64," in img_str:
                        header, encoded = img_str.split("base64,", 1)
                        # Guess extension from header
                        ext = ".png" # Default
                        if "image/jpeg" in header: ext = ".jpg"
                        elif "image/png" in header: ext = ".png"
                        elif "image/webp" in header: ext = ".webp"
                        elif "image/gif" in header: ext = ".gif"
                    else:
                        encoded = img_str
                        ext = ".png"

                    # Decode base64
                    image_data = base64.b64decode(encoded)
                    
                    # Create temp file
                    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_img:
                        temp_img.write(image_data)
                        temp_path = temp_img.name
                    
                    # Add to images list using filepath
                    images.append(Image(filepath=temp_path))
                    logging.info(f"Processed image to temp file: {temp_path}")
                except Exception as e:
                    logging.error(f"Failed to process image: {e}")

        # Handle audio
        audio_files = []
        if request.audio:
            for audio_str in request.audio:
                try:
                    # Check if it's a data URI and strip header if present
                    if "base64," in audio_str:
                        header, encoded = audio_str.split("base64,", 1)
                        # Guess extension from header
                        ext = ".mp3" # Default
                        if "audio/mpeg" in header: ext = ".mp3"
                        elif "audio/wav" in header: ext = ".wav"
                        elif "audio/ogg" in header: ext = ".ogg"
                        elif "audio/webm" in header: ext = ".webm"
                    else:
                        encoded = audio_str
                        ext = ".mp3"

                    # Decode base64
                    audio_data = base64.b64decode(encoded)
                    
                    # Create temp file
                    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_audio:
                        temp_audio.write(audio_data)
                        temp_path = temp_audio.name
                    
                    # Add to audio list using filepath
                    audio_files.append(Audio(filepath=temp_path))
                    logging.info(f"Processed audio to temp file: {temp_path}")
                except Exception as e:
                    logging.error(f"Failed to process audio: {e}")

        # Handle videos
        video_files = []
        if request.videos:
            for video_str in request.videos:
                try:
                    # Check if it's a data URI and strip header if present
                    if "base64," in video_str:
                        header, encoded = video_str.split("base64,", 1)
                        # Guess extension from header
                        ext = ".mp4" # Default
                        if "video/mp4" in header: ext = ".mp4"
                        elif "video/webm" in header: ext = ".webm"
                        elif "video/ogg" in header: ext = ".ogg"
                    else:
                        encoded = video_str
                        ext = ".mp4"

                    # Decode base64
                    video_data = base64.b64decode(encoded)
                    
                    # Create temp file
                    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_video:
                        temp_video.write(video_data)
                        temp_path = temp_video.name
                    
                    # Add to videos list using filepath
                    video_files.append(Video(filepath=temp_path))
                    logging.info(f"Processed video to temp file: {temp_path}")
                except Exception as e:
                    logging.error(f"Failed to process video: {e}")

        async def stream_response():
            full_response = ""
            sentence_buffer = SentenceBuffer()
            sentence_index = 0
            collected_sentences = []  # Collect sentences for later TTS generation
            tts_tasks = []  # Track TTS generation tasks
            
            async def generate_tts_task(sentence: str, idx: int):
                """Generate TTS in background without blocking"""
                try:
                    audio_path, viseme_data = await run_in_threadpool(text_to_speech, sentence)
                    audio_filename = None
                    if audio_path:
                        size_bytes = os.path.getsize(audio_path)
                        logging.info(f"Generated TTS audio: {audio_path} ({size_bytes} bytes)")
                        if size_bytes < 1000:
                            logging.warning(f"Audio file seems too small ({size_bytes} bytes) for sentence: {sentence[:50]}...")
                        audio_filename = os.path.basename(audio_path)
                    return {'type': 'audio_chunk', 'sentence_index': idx, 'audio_filename': audio_filename, 'visemes': viseme_data, 'sentence_text': sentence}
                except Exception as e:
                    logging.error(f"Error generating TTS for sentence {idx}: {str(e)}")
                    return None
            
            try:
                # Apply per-session voice before generating audio (once at start)
                with sessions.SessionLocal() as db:
                    sessions.apply_session_voice(db, request.user_id, request.session_id)
                
                # 1. Stream text from Assistant agent
                stream_gen = await run_assistant_agent(
                    request.query, uid, request.session_id,
                    images=images if images else None,
                    audio=audio_files if audio_files else None,
                    videos=video_files if video_files else None,
                    stream=True
                )
                
                async for chunk in stream_gen:
                    if chunk:
                        # Clean each chunk in real-time
                        # Replace tool logs with newline
                        cleaned_chunk = tool_log_regex.sub("\n", chunk)
                        full_response += chunk
                        
                        # Send text chunk to UI for display
                        if cleaned_chunk.strip():
                            yield f"data: {json.dumps({'content': cleaned_chunk})}\n\n"
                            await asyncio.sleep(0.01)
                        
                        # Add chunk to sentence buffer
                        complete_sentences = sentence_buffer.add_chunk(cleaned_chunk)
                        
                        # Launch TTS generation in PARALLEL for each sentence
                        for sentence in complete_sentences:
                             if sentence.strip():
                                idx = len(collected_sentences)
                                collected_sentences.append(sentence)
                                task = asyncio.create_task(generate_tts_task(sentence, idx))
                                tts_tasks.append(task)
                
                # After text streaming, send audio as tasks complete (in order by sentence_index)
                logging.info(f"ASSISTANT TTS: Text streaming done. Processing {len(tts_tasks)} audio tasks")
                
                if len(tts_tasks) == 0:
                    logging.warning("ASSISTANT TTS: No audio tasks to process, skipping")
                    sentence_index = 0
                else:
                    completed_audio = {}
                    next_index_to_send = 0
                    total_tasks = len(tts_tasks)
                    tasks_completed = 0
                    
                    try:
                        logging.info(f"ASSISTANT TTS: Starting as_completed loop with {len(tts_tasks)} tasks")
                        for task in asyncio.as_completed(tts_tasks):
                            result = await task
                            tasks_completed += 1
                            logging.info(f"ASSISTANT TTS: Task {tasks_completed}/{total_tasks} done. Has result: {result is not None}")
                            
                            if result:
                                completed_audio[result['sentence_index']] = result
                                logging.info(f"ASSISTANT TTS: Buffered sentence {result['sentence_index']}")
                                
                            # Send buffered audio in order
                            while next_index_to_send in completed_audio:
                                logging.info(f"ASSISTANT TTS: Yielding chunk {next_index_to_send}")
                                yield f"data: {json.dumps(completed_audio[next_index_to_send])}\n\n"
                                await asyncio.sleep(0.05)  # Small delay to ensure SSE event is processed
                                del completed_audio[next_index_to_send]
                                next_index_to_send += 1
                            
                            # If all tasks done, send any remaining (skip failed gaps)
                            if tasks_completed == total_tasks:
                                logging.info(f"ASSISTANT TTS: Flushing remaining from index {next_index_to_send}")
                                while next_index_to_send < total_tasks:
                                    if next_index_to_send in completed_audio:
                                        logging.info(f"ASSISTANT TTS: Flushing chunk {next_index_to_send}")
                                        yield f"data: {json.dumps(completed_audio[next_index_to_send])}\n\n"
                                        del completed_audio[next_index_to_send]
                                    else:
                                        logging.warning(f"ASSISTANT TTS: Skipping missing index {next_index_to_send}")
                                    next_index_to_send += 1
                        
                        logging.info(f"ASSISTANT TTS: as_completed loop finished. Tasks completed: {tasks_completed}/{total_tasks}")
                        logging.info(f"ASSISTANT TTS: Done processing all {total_tasks} tasks")
                    except GeneratorExit:
                        logging.error(f"ASSISTANT TTS: GeneratorExit!!! Client closed stream. Tasks completed: {tasks_completed}/{total_tasks}")
                        raise
                    except asyncio.CancelledError:
                        logging.warning(f"ASSISTANT TTS: Cancelled by user. Tasks completed: {tasks_completed}/{total_tasks}")
                        return
                    except Exception as e:
                        logging.error(f"ASSISTANT TTS: Error in audio processing loop: {str(e)}", exc_info=True)
                    
                    sentence_index = len(collected_sentences)




                # 2. Handle any remaining incomplete sentence
                remaining_text = sentence_buffer.flush()
                if remaining_text and remaining_text.strip():
                    try:
                        audio_path, viseme_data = await run_in_threadpool(text_to_speech, remaining_text)
                        audio_filename = None
                        if audio_path:
                            audio_filename = os.path.basename(audio_path)
                        yield f"data: {json.dumps({'type': 'audio_chunk', 'sentence_index': sentence_index, 'audio_filename': audio_filename, 'visemes': viseme_data, 'sentence_text': remaining_text})}\n\n"
                        sentence_index += 1
                    except Exception as e:
                        logging.error(f"Error generating TTS for final sentence: {str(e)}")

                # 3. Clean full response for final event
                cleaned_response = clean_model_output(full_response)
                cleaned_response = ensure_response_content(cleaned_response)

                # 4. Send final done event
                yield f"data: {json.dumps({'done': True, 'full_response': cleaned_response, 'total_audio_chunks': sentence_index})}\n\n"

            except asyncio.CancelledError:
                logging.warning("Stream request cancelled by user")
                return
            except Exception as e:
                logging.error(f"Error in Assistant TTS streaming: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                active_tasks.pop(key, None)

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# MCP Query direct then TTS (filtered reasoning)
@app.post("/query_mcp_tts_direct")
async def query_mcp_tts_direct(request: QueryRequest, http_request: Request):
    """
    Returns a SSE stream with text chunks, followed by audio filename and viseme data.
    """
    key = f"{request.user_id}:{request.session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        token_payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == request.session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")

        async def stream_response():
            full_response = ""
            sentence_buffer = SentenceBuffer()
            sentence_index = 0
            collected_sentences = []  # Collect sentences for later TTS generation
            tts_tasks = []  # Track TTS generation tasks
            
            async def generate_tts_task(sentence: str, idx: int):
                """Generate TTS in background without blocking"""
                try:
                    audio_path, viseme_data = await run_in_threadpool(text_to_speech, sentence)
                    audio_filename = None
                    if audio_path:
                        audio_filename = os.path.basename(audio_path)
                    return {'type': 'audio_chunk', 'sentence_index': idx, 'audio_filename': audio_filename, 'visemes': viseme_data, 'sentence_text': sentence}
                except Exception as e:
                    logging.error(f"Error generating TTS for sentence {idx}: {str(e)}")
                    return None
            
            try:
                # Apply per-session voice before generating audio (once at start)
                with sessions.SessionLocal() as db:
                    sessions.apply_session_voice(db, request.user_id, request.session_id)
                
                # 1. Stream text from MCP agent
                stream_gen = await run_mcp_agent(
                    request.query, uid, request.session_id,
                    stream=True
                )
                
                async for chunk in stream_gen:
                    if chunk:
                        # Clean each chunk in real-time
                        # Replace tool logs with newline
                        cleaned_chunk = tool_log_regex.sub("\n", chunk)
                        full_response += chunk
                        
                        # Send text chunk to UI for display
                        if cleaned_chunk.strip():
                            yield f"data: {json.dumps({'content': cleaned_chunk})}\n\n"
                            await asyncio.sleep(0.01)
                        
                        complete_sentences = sentence_buffer.add_chunk(cleaned_chunk)
                        
                        # Launch TTS generation in PARALLEL for each sentence
                        for sentence in complete_sentences:
                            if sentence.strip():
                                idx = len(collected_sentences)
                                collected_sentences.append(sentence)
                                task = asyncio.create_task(generate_tts_task(sentence, idx))
                                tts_tasks.append(task)
                
                # After text streaming, send audio as tasks complete (in order by sentence_index)
                logging.info(f"MCP TTS: Text streaming done. Processing {len(tts_tasks)} audio tasks")
                
                if len(tts_tasks) == 0:
                    logging.warning("MCP TTS: No audio tasks to process, skipping")
                    sentence_index = 0
                else:
                    completed_audio = {}
                    next_index_to_send = 0
                    total_tasks = len(tts_tasks)
                    tasks_completed = 0
                    
                    try:
                        for task in asyncio.as_completed(tts_tasks):
                            result = await task
                            tasks_completed += 1
                            logging.info(f"MCP TTS: Task {tasks_completed}/{total_tasks} done. Has result: {result is not None}")
                            
                            if result:
                                completed_audio[result['sentence_index']] = result
                                logging.info(f"MCP TTS: Buffered sentence {result['sentence_index']}")
                                
                            # Send buffered audio in order
                            while next_index_to_send in completed_audio:
                                logging.info(f"MCP TTS: Yielding chunk {next_index_to_send}")
                                yield f"data: {json.dumps(completed_audio[next_index_to_send])}\n\n"
                                del completed_audio[next_index_to_send]
                                next_index_to_send += 1
                            
                            # If all tasks done, send any remaining (skip failed gaps)
                            if tasks_completed == total_tasks:
                                logging.info(f"MCP TTS: Flushing remaining from index {next_index_to_send}")
                                while next_index_to_send < total_tasks:
                                    if next_index_to_send in completed_audio:
                                        logging.info(f"MCP TTS: Flushing chunk {next_index_to_send}")
                                        yield f"data: {json.dumps(completed_audio[next_index_to_send])}\n\n"
                                        del completed_audio[next_index_to_send]
                                    next_index_to_send += 1
                        
                        logging.info(f"MCP TTS: Done processing all {total_tasks} tasks")
                    except Exception as e:
                        logging.error(f"MCP TTS: Error in audio processing loop: {str(e)}", exc_info=True)
                    
                    sentence_index = len(collected_sentences)




                # 3. Handle any remaining incomplete sentence
                remaining_text = sentence_buffer.flush()
                if remaining_text and remaining_text.strip():
                    try:
                        audio_path, viseme_data = await run_in_threadpool(text_to_speech, remaining_text)
                        audio_filename = None
                        if audio_path:
                            audio_filename = os.path.basename(audio_path)
                        yield f"data: {json.dumps({'type': 'audio_chunk', 'sentence_index': sentence_index, 'audio_filename': audio_filename, 'visemes': viseme_data, 'sentence_text': remaining_text})}\n\n"
                        sentence_index += 1
                    except Exception as e:
                        logging.error(f"Error generating TTS for final sentence: {str(e)}")

                # 3. Clean full response for final event
                cleaned_response = clean_model_output(full_response)
                cleaned_response = ensure_response_content(cleaned_response)

                # 4. Send final done event
                yield f"data: {json.dumps({'done': True, 'full_response': cleaned_response, 'total_audio_chunks': sentence_index})}\n\n"

            except asyncio.CancelledError:
                logging.warning("Stream request cancelled by user")
                return
            except Exception as e:
                logging.error(f"Error in MCP TTS streaming: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                active_tasks.pop(key, None)

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except asyncio.CancelledError:
        logging.warning("Request cancelled")
        return JSONResponse(status_code=499, content={"detail": "Request cancelled"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# MCP Full Agent: STT -> Query -> TTS
@app.post("/stt_query_mcp_tts", response_model=Dict[str, Any])
async def stt_query_mcp_tts_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    request: Request = None,
):
    """
    Combined STT, MCP query, and TTS endpoint that returns viseme data and audio filename.
    """
    try:
        token_payload = get_user_from_auth_header(request.headers.get("Authorization") if request else None)
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
        # First transcribe the audio
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        # Get the transcribed text
        query_text = stt_result["text"]
        try:
            logging.info(f"STT transcript len={len(query_text)} user={user_id} session={session_id}")
        except Exception:
            pass
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        # Process the query using the MCP agent
        response_text = await run_mcp_agent(query_text, uid, session_id)

        # Generate audio and visemes
        # Apply per-session voice before generating audio
        with sessions.SessionLocal() as db:
            sessions.apply_session_voice(db, user_id, session_id)
        audio_path, viseme_data = await run_in_threadpool(text_to_speech, response_text)
        
        audio_filename = None
        if audio_path:
            audio_filename = os.path.basename(audio_path)

        return {
            "text": query_text,
            "response": response_text,
            "audio_filename": audio_filename,
            "visemes": viseme_data,
            "user_id": uid,
            "session_id": session_id,
            "status": "success"
        }
    except asyncio.CancelledError:
        logging.warning("Request cancelled")
        return JSONResponse(status_code=499, content={"detail": "Request cancelled"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query with TTS: {str(e)}")

# ASSISTANT Full Agent: STT -> Query -> TTS
@app.post("/stt_query_assistant_tts", response_model=Dict[str, Any])
async def stt_query_assistant_tts_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    request: Request = None,
):
    """
    Combined STT, assistant query, and TTS endpoint that returns viseme data and audio filename.
    """
    try:
        token_payload = get_user_from_auth_header(request.headers.get("Authorization") if request else None)
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        query_text = stt_result["text"]
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        response_text = await run_assistant_agent(query_text, uid, session_id)

        with sessions.SessionLocal() as db:
            sessions.apply_session_voice(db, user_id, session_id)
        audio_path, viseme_data = await run_in_threadpool(text_to_speech, response_text)
        
        audio_filename = None
        if audio_path:
            audio_filename = os.path.basename(audio_path)

        return {
            "text": query_text,
            "response": response_text,
            "audio_filename": audio_filename,
            "visemes": viseme_data,
            "user_id": uid,
            "session_id": session_id,
            "status": "success"
        }
    except asyncio.CancelledError:
        logging.warning("Request cancelled")
        return JSONResponse(status_code=499, content={"detail": "Request cancelled"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query with TTS: {str(e)}")

# ASSISTANT Full Agent direct: STT -> Query (filtered) -> TTS
@app.post("/stt_query_assistant_tts_direct")
async def stt_query_assistant_tts_direct_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    request: Request = None,
):
    """
    Combined STT, filtered assistant query, and TTS endpoint that returns a SSE stream.
    """
    key = f"{user_id}:{session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        token_payload = get_user_from_auth_header(request.headers.get("Authorization") if request else None)
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
        
        # 1. Transcribe audio first
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        query_text = stt_result["text"]
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        async def stream_response():
            full_response = ""
            sentence_buffer = SentenceBuffer()
            sentence_index = 0
            
            try:
                # 1. Send transcription immediately
                yield f"data: {json.dumps({'type': 'transcription', 'text': query_text})}\n\n"
                
                # Apply per-session voice before generating audio (once at start)
                with sessions.SessionLocal() as db:
                    sessions.apply_session_voice(db, user_id, session_id)

                # 2. Stream text from Assistant agent
                stream_gen = await run_assistant_agent(query_text, uid, session_id, stream=True)
                
                async for chunk in stream_gen:
                    if chunk:
                        cleaned_chunk = tool_log_regex.sub("\n", chunk)
                        full_response += chunk
                        
                        # Send text chunk to UI for display
                        if cleaned_chunk.strip():
                            yield f"data: {json.dumps({'content': cleaned_chunk})}\n\n"
                            await asyncio.sleep(0.01)
                        
                        # Add chunk to sentence buffer
                        complete_sentences = sentence_buffer.add_chunk(cleaned_chunk)
                        
                        # Generate TTS immediately for each complete sentence
                        for sentence in complete_sentences:
                            if sentence.strip():
                                try:
                                    # Generate audio and visemes for this sentence
                                    audio_path, viseme_data = await run_in_threadpool(text_to_speech, sentence)
                                    
                                    audio_filename = None
                                    if audio_path:
                                        audio_filename = os.path.basename(audio_path)
                                    
                                    # Send audio chunk event immediately
                                    yield f"data: {json.dumps({'type': 'audio_chunk', 'sentence_index': sentence_index, 'audio_filename': audio_filename, 'visemes': viseme_data, 'sentence_text': sentence})}\n\n"
                                    sentence_index += 1
                                    
                                except Exception as e:
                                    logging.error(f"Error generating TTS for sentence {sentence_index}: {str(e)}")
                                    # Continue even if one sentence fails

                # 3. Handle any remaining incomplete sentence
                remaining_text = sentence_buffer.flush()
                if remaining_text and remaining_text.strip():
                    try:
                        audio_path, viseme_data = await run_in_threadpool(text_to_speech, remaining_text)
                        audio_filename = None
                        if audio_path:
                            audio_filename = os.path.basename(audio_path)
                        yield f"data: {json.dumps({'type': 'audio_chunk', 'sentence_index': sentence_index, 'audio_filename': audio_filename, 'visemes': viseme_data, 'sentence_text': remaining_text})}\n\n"
                        sentence_index += 1
                    except Exception as e:
                        logging.error(f"Error generating TTS for final sentence: {str(e)}")

                # 4. Clean full response
                cleaned_response = clean_model_output(full_response)
                # Ensure response content (e.g. if empty)
                cleaned_response = ensure_response_content(cleaned_response)

                # 5. Send done event
                yield f"data: {json.dumps({'done': True, 'text': query_text, 'full_response': cleaned_response, 'total_audio_chunks': sentence_index})}\n\n"

            except asyncio.CancelledError:
                logging.warning("Stream request cancelled by user")
                return
            except Exception as e:
                logging.error(f"Error in STT Assistant TTS streaming: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                active_tasks.pop(key, None)

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Request cancelled")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query with TTS: {str(e)}")
# MCP Full Agent direct: STT -> Query (filtered) -> TTS
@app.post("/stt_query_mcp_tts_direct")
async def stt_query_mcp_tts_direct_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    request: Request = None,
):
    """
    Combined STT, filtered MCP query, and TTS endpoint that returns a SSE stream.
    """
    key = f"{user_id}:{session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        token_payload = get_user_from_auth_header(request.headers.get("Authorization") if request else None)
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
        
        # 1. Transcribe audio first
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        query_text = stt_result["text"]
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        async def stream_response():
            full_response = ""
            sentence_buffer = SentenceBuffer()
            sentence_index = 0
            
            try:
                # 1. Send transcription immediately
                yield f"data: {json.dumps({'type': 'transcription', 'text': query_text})}\n\n"
                
                # Apply per-session voice before generating audio (once at start)
                with sessions.SessionLocal() as db:
                    sessions.apply_session_voice(db, user_id, session_id)

                # 2. Stream text from MCP agent
                stream_gen = await run_mcp_agent(query_text, uid, session_id, stream=True)
                
                async for chunk in stream_gen:
                    if chunk:
                        cleaned_chunk = tool_log_regex.sub("\n", chunk)
                        full_response += chunk
                        
                        # Send text chunk to UI for display
                        if cleaned_chunk.strip():
                            yield f"data: {json.dumps({'content': cleaned_chunk})}\n\n"
                            await asyncio.sleep(0.01)
                        
                        # Add chunk to sentence buffer
                        complete_sentences = sentence_buffer.add_chunk(cleaned_chunk)
                        
                        # Generate TTS immediately for each complete sentence
                        for sentence in complete_sentences:
                            if sentence.strip():
                                try:
                                    # Generate audio and visemes for this sentence
                                    audio_path, viseme_data = await run_in_threadpool(text_to_speech, sentence)
                                    
                                    audio_filename = None
                                    if audio_path:
                                        audio_filename = os.path.basename(audio_path)
                                    
                                    # Send audio chunk event immediately
                                    yield f"data: {json.dumps({'type': 'audio_chunk', 'sentence_index': sentence_index, 'audio_filename': audio_filename, 'visemes': viseme_data, 'sentence_text': sentence})}\n\n"
                                    sentence_index += 1
                                    
                                except Exception as e:
                                    logging.error(f"Error generating TTS for sentence {sentence_index}: {str(e)}")
                                    # Continue even if one sentence fails

                # 3. Handle any remaining incomplete sentence
                remaining_text = sentence_buffer.flush()
                if remaining_text and remaining_text.strip():
                    try:
                        audio_path, viseme_data = await run_in_threadpool(text_to_speech, remaining_text)
                        audio_filename = None
                        if audio_path:
                            audio_filename = os.path.basename(audio_path)
                        yield f"data: {json.dumps({'type': 'audio_chunk', 'sentence_index': sentence_index, 'audio_filename': audio_filename, 'visemes': viseme_data, 'sentence_text': remaining_text})}\n\n"
                        sentence_index += 1
                    except Exception as e:
                        logging.error(f"Error generating TTS for final sentence: {str(e)}")

                # 4. Clean full response
                cleaned_response = clean_model_output(full_response)
                cleaned_response = ensure_response_content(cleaned_response)

                # 5. Send done event
                yield f"data: {json.dumps({'done': True, 'text': query_text, 'full_response': cleaned_response, 'total_audio_chunks': sentence_index})}\n\n"

            except asyncio.CancelledError:
                logging.warning("Stream request cancelled by user")
                return
            except Exception as e:
                logging.error(f"Error in STT MCP TTS streaming: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                active_tasks.pop(key, None)

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except asyncio.CancelledError:
        logging.warning("Request cancelled")
        return JSONResponse(status_code=499, content={"detail": "Request cancelled"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query with TTS: {str(e)}")
#LLM QUERY not displayed Reasoning (with SSE Streaming)
@app.post("/query_direct")
async def query_direct(request: QueryRequest, http_request: Request):
    key = f"{request.user_id}:{request.session_id}"
    active_tasks[key] = asyncio.current_task()
    
    # Auth check outside the generator
    token_payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
    if not token_payload:
        raise HTTPException(status_code=401, detail="Unauthorized")
    uid = token_payload.get("uid")
    with sessions.SessionLocal() as db:
        s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == request.session_id, sessions.SessionDB.user_id == uid).first()
        if not s:
            raise HTTPException(status_code=404, detail="Session not found")

    async def stream_response():
        full_response = ""
        try:
            # Get streaming generator from RAG agent
            stream_gen = await run_rag_agent(
                request.query, uid, request.session_id,
                stream=True
            )
            
            async for chunk in stream_gen:
                if chunk:
                    # Clean each chunk in real-time to prevent tool logs from appearing
                    # Replace with newline to ensure separation
                    cleaned_chunk = tool_log_regex.sub("\n", chunk)
                    full_response += chunk
                    
                    if cleaned_chunk.strip():
                        yield f"data: {json.dumps({'content': cleaned_chunk})}\n\n"
            
            # Clean and send done event
            cleaned_response = clean_model_output(full_response)
            cleaned_response = ensure_response_content(cleaned_response)
            yield f"data: {json.dumps({'done': True, 'full_response': cleaned_response})}\n\n"
            
        except asyncio.CancelledError:
            logging.warning("RAG Stream request cancelled by user")
            # If client disconnected, we can just return.
            return
        except Exception as e:
            logging.error(f"Error in RAG streaming: {type(e).__name__}: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            active_tasks.pop(key, None)
    
    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


#Speach to text
@app.post("/stt", response_model=Dict[str, str])
async def stt_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...)
):
    """
    Speech-to-text endpoint that accepts various audio formats, converts to WAV PCM 16-bit mono 16kHz, and returns the transcription.
    """
    try:
        ct = getattr(file, "content_type", "") or ""
        ct_l = ct.lower()
        guessed_ext = ".wav"
        if "webm" in ct_l:
            guessed_ext = ".webm"
        elif "ogg" in ct_l:
            guessed_ext = ".ogg"
        elif "mp3" in ct_l or "mpeg" in ct_l:
            guessed_ext = ".mp3"
        elif "wav" in ct_l:
            guessed_ext = ".wav"

        name_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
        file_extension = name_ext or guessed_ext
        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
            temp_file.write(await file.read())
            input_path = temp_file.name

        if file_extension != ".wav":
            try:
                wav_path = input_path + ".wav"
                audio = AudioSegment.from_file(input_path)
                audio = audio.set_channels(1).set_frame_rate(16000)
                audio.export(wav_path, format="wav")
                os.unlink(input_path)
                input_path = wav_path
            except Exception as e:
                msg = str(e)
                if "ffmpeg" in msg.lower():
                    raise HTTPException(status_code=500, detail="FFmpeg is required to convert audio (install ffmpeg and ensure it's on PATH)")
                raise HTTPException(status_code=400, detail=f"Error converting audio format: {msg}")
        else:
            try:
                audio = AudioSegment.from_file(input_path)
                audio = audio.set_channels(1).set_frame_rate(16000)
                audio.export(input_path, format="wav")
            except Exception as e:
                msg = str(e)
                if "ffmpeg" in msg.lower():
                    raise HTTPException(status_code=500, detail="FFmpeg is required to process WAV audio (install ffmpeg and ensure it's on PATH)")
                raise HTTPException(status_code=400, detail=f"Error processing WAV audio: {msg}")

        wf = None
        try:
            vosk_model, recognizer = initialize_stt()
            import wave
            try:
                wf = wave.open(input_path, "rb")
                text = ""
                while True:
                    data = wf.readframes(4096)
                    if len(data) == 0:
                        break
                    if recognizer.AcceptWaveform(data):
                        result = recognizer.Result()
                        text = json.loads(result).get("text", "")
                if not text:
                    text = json.loads(recognizer.FinalResult()).get("text", "")
            finally:
                if wf is not None:
                    wf.close()
        except Exception as e:
            try:
                os.unlink(input_path)
            except Exception:
                pass
            raise HTTPException(status_code=500, detail=f"Error transcribing audio: {str(e)}")

        try:
            os.unlink(input_path)
        except Exception:
            pass

        if not text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}
        return {"text": text, "user_id": user_id, "session_id": session_id, "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error transcribing speech: {str(e)}")

#Text to Speach
@app.post("/tts")
def tts_endpoint(request: TTSRequest):
    try:
        # Apply per-session voice before generating audio
        with sessions.SessionLocal() as db:
            sessions.apply_session_voice(db, request.user_id, request.session_id)
        # Generate audio and visemes. This now returns the cached audio path and viseme data.
        audio_path, viseme_data = text_to_speech(request.text)

        if not audio_path:
            raise HTTPException(status_code=500, detail="TTS failed to generate audio file.")

        audio_filename = os.path.basename(audio_path)

        # 3. Return both the audio filename and viseme data in a JSON response.
        return {
            "audio_filename": audio_filename,
            "visemes": viseme_data
        }
    except Exception as e:
        # Log the exception for debugging
        print(f"Error in /tts endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


#Speach to text query
@app.post("/stt_query", response_model=Dict[str, str])
async def stt_query_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    request: Request = None,
):
    """
    Combined STT and query endpoint that:
    1. Converts audio input to text
    2. Processes the query using the RAG agent
    3. Returns both the transcribed text and the query response
    """
    try:
        token_payload = get_user_from_auth_header(request.headers.get("Authorization") if request else None)
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
        # First transcribe the audio
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        # Get the transcribed text
        query_text = stt_result["text"]
        try:
            logging.info(f"STT transcript len={len(query_text)} user={user_id} session={session_id}")
        except Exception:
            pass
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        # Process the query using the RAG agent
        response = await run_rag_agent(query_text, uid, session_id)

        return {
            "text": query_text,
            "response": response,
            "user_id": uid,
            "session_id": session_id,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query: {str(e)}")

#Speach to text query direct not displayed Reasoning
@app.post("/stt_query_direct", response_model=Dict[str, str])
async def stt_query_direct_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    request: Request = None,
):
    """
    Combined STT and filtered query endpoint that:
    1. Converts audio input to text
    2. Processes the query using the RAG agent with filtering
    3. Returns both the transcribed text and the filtered query response
    """
    try:
        token_payload = get_user_from_auth_header(request.headers.get("Authorization") if request else None)
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
        # First transcribe the audio
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        # Get the transcribed text
        query_text = stt_result["text"]
        try:
            logging.info(f"STT transcript len={len(query_text)} user={user_id} session={session_id}")
        except Exception:
            pass
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        # Process the query using the RAG agent and clean output
        response = await run_rag_agent(query_text, uid, session_id)
        response = clean_model_output(response)

        return {
            "text": query_text,
            "response": response,
            "user_id": uid,
            "session_id": session_id,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query: {str(e)}")

#Query to speach to text 
@app.post("/query_tts")
async def query_tts_endpoint(request: QueryRequest, http_request: Request):
    """
    Returns a JSON with the text response, audio filename, and viseme data.
    """
    try:
        token_payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == request.session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
        response_text = await run_rag_agent(request.query, uid, request.session_id)
        
        # Generate audio and visemes
        # Apply per-session voice before generating audio
        with sessions.SessionLocal() as db:
            sessions.apply_session_voice(db, request.user_id, request.session_id)
        audio_path, viseme_data = await run_in_threadpool(text_to_speech, response_text)

        audio_filename = None
        if audio_path:
            audio_filename = os.path.basename(audio_path)

        return {
            "user_id": uid,
            "session_id": request.session_id,
            "response": response_text,
            "audio_filename": audio_filename,
            "visemes": viseme_data,
            "status": "success"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

#Query text to speach direct disabled Reasoning
@app.post("/query_tts_direct")
async def query_tts_direct(request: QueryRequest, http_request: Request):
    """
    Returns a SSE stream with text chunks, followed by audio filename and viseme data.
    """
    key = f"{request.user_id}:{request.session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        token_payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == request.session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")

        async def stream_response():
            full_response = ""
            sentence_buffer = SentenceBuffer()
            sentence_index = 0
            collected_sentences = []  # Collect sentences for later TTS generation
            tts_tasks = []  # Track TTS generation tasks
            
            async def generate_tts_task(sentence: str, idx: int):
                """Generate TTS in background without blocking"""
                try:
                    audio_path, viseme_data = await run_in_threadpool(text_to_speech, sentence)
                    audio_filename = None
                    if audio_path:
                        audio_filename = os.path.basename(audio_path)
                    return {'type': 'audio_chunk', 'sentence_index': idx, 'audio_filename': audio_filename, 'visemes': viseme_data, 'sentence_text': sentence}
                except Exception as e:
                    logging.error(f"Error generating TTS for sentence {idx}: {str(e)}")
                    return None
            
            try:
                # Apply per-session voice before generating audio (once at start)
                with sessions.SessionLocal() as db:
                    sessions.apply_session_voice(db, request.user_id, request.session_id)
                
                # 1. Stream text from RAG agent
                stream_gen = await run_rag_agent(
                    request.query, uid, request.session_id,
                    stream=True
                )
                
                async for chunk in stream_gen:
                    if chunk:
                        # Clean each chunk in real-time to prevent tool logs from appearing
                        # Replace with newline to ensure separation
                        cleaned_chunk = tool_log_regex.sub("\n", chunk)
                        full_response += chunk
                        
                        # Send text chunk to UI for display
                        if cleaned_chunk.strip():
                            yield f"data: {json.dumps({'content': cleaned_chunk})}\n\n"
                            await asyncio.sleep(0.01)
                        
                        # Add chunk to sentence buffer
                        complete_sentences = sentence_buffer.add_chunk(cleaned_chunk)
                        
                        # Launch TTS generation in PARALLEL for each sentence
                        for sentence in complete_sentences:
                             if sentence.strip():
                                idx = len(collected_sentences)
                                collected_sentences.append(sentence)
                                task = asyncio.create_task(generate_tts_task(sentence, idx))
                                tts_tasks.append(task)
                        
                # After text streaming, send audio as tasks complete (in order by sentence_index)
                logging.info(f"RAG TTS: Text streaming done. Processing {len(tts_tasks)} audio tasks")
                
                if len(tts_tasks) == 0:
                    logging.warning("RAG TTS: No audio tasks to process, skipping")
                    sentence_index = 0
                else:
                    completed_audio = {}
                    next_index_to_send = 0
                    total_tasks = len(tts_tasks)
                    tasks_completed = 0
                    
                    try:
                        for task in asyncio.as_completed(tts_tasks):
                            result = await task
                            tasks_completed += 1
                            logging.info(f"RAG TTS: Task {tasks_completed}/{total_tasks} done. Has result: {result is not None}")
                            
                            if result:
                                completed_audio[result['sentence_index']] = result
                                logging.info(f"RAG TTS: Buffered sentence {result['sentence_index']}")
                                
                            # Send buffered audio in order
                            while next_index_to_send in completed_audio:
                                logging.info(f"RAG TTS: Yielding chunk {next_index_to_send}")
                                yield f"data: {json.dumps(completed_audio[next_index_to_send])}\n\n"
                                del completed_audio[next_index_to_send]
                                next_index_to_send += 1
                            
                            # If all tasks done, send any remaining (skip failed gaps)
                            if tasks_completed == total_tasks:
                                logging.info(f"RAG TTS: Flushing remaining from index {next_index_to_send}")
                                while next_index_to_send < total_tasks:
                                    if next_index_to_send in completed_audio:
                                        logging.info(f"RAG TTS: Flushing chunk {next_index_to_send}")
                                        yield f"data: {json.dumps(completed_audio[next_index_to_send])}\n\n"
                                        del completed_audio[next_index_to_send]
                                    next_index_to_send += 1
                        
                        logging.info(f"RAG TTS: Done processing all {total_tasks} tasks")
                    except Exception as e:
                        logging.error(f"RAG TTS: Error in audio processing loop: {str(e)}", exc_info=True)
                    
                    sentence_index = len(collected_sentences)


                
                # 2. Handle any remaining incomplete sentence
                remaining_text = sentence_buffer.flush()
                if remaining_text and remaining_text.strip():
                    try:
                        audio_path, viseme_data = await run_in_threadpool(text_to_speech, remaining_text)
                        audio_filename = None
                        if audio_path:
                            audio_filename = os.path.basename(audio_path)
                        yield f"data: {json.dumps({'type': 'audio_chunk', 'sentence_index': sentence_index, 'audio_filename': audio_filename, 'visemes': viseme_data, 'sentence_text': remaining_text})}\n\n"
                        sentence_index += 1
                    except Exception as e:
                        logging.error(f"Error generating TTS for final sentence: {str(e)}")

                # 3. Clean full response for final event
                cleaned_response = clean_model_output(full_response)
                cleaned_response = ensure_response_content(cleaned_response)

                # 4. Send final done event
                yield f"data: {json.dumps({'done': True, 'full_response': cleaned_response, 'total_audio_chunks': sentence_index})}\n\n"
                
            except asyncio.CancelledError:
                yield f"data: {json.dumps({'error': 'Request cancelled'})}\n\n"
            except Exception as e:
                logging.error(f"Error in TTS streaming: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                active_tasks.pop(key, None)

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Full Agent
@app.post("/stt_query_tts", response_model=Dict[str, Any])
async def stt_query_tts_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    request: Request = None,
):
    """
    Combined STT, query, and TTS endpoint that returns viseme data and audio filename.
    """
    try:
        token_payload = get_user_from_auth_header(request.headers.get("Authorization") if request else None)
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
        # First transcribe the audio
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        # Get the transcribed text
        query_text = stt_result["text"]
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        # Process the query using the RAG agent
        response_text = await run_rag_agent(query_text, uid, session_id)

        # Generate audio and visemes
        # Apply per-session voice before generating audio
        with sessions.SessionLocal() as db:
            sessions.apply_session_voice(db, user_id, session_id)
        audio_path, viseme_data = await run_in_threadpool(text_to_speech, response_text)
        
        audio_filename = None
        if audio_path:
            audio_filename = os.path.basename(audio_path)

        return {
            "text": query_text,
            "response": response_text,
            "audio_filename": audio_filename,
            "visemes": viseme_data,
            "user_id": uid,
            "session_id": session_id,
            "status": "success"
        }
    except asyncio.CancelledError:
        logging.warning("Request cancelled")
        return JSONResponse(status_code=499, content={"detail": "Request cancelled"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query with TTS: {str(e)}")

# Full Agent with reasoning not displayed
@app.post("/stt_query_tts_direct")
async def stt_query_tts_direct_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    request: Request = None,
):
    """
    Combined STT, filtered query, and TTS endpoint that returns a SSE stream.
    """
    key = f"{user_id}:{session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        token_payload = get_user_from_auth_header(request.headers.get("Authorization") if request else None)
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")
        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
        
        # 1. Transcribe audio first (blocking but necessary)
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        query_text = stt_result["text"]
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        async def stream_response():
            full_response = ""
            sentence_buffer = SentenceBuffer()
            sentence_index = 0
            
            try:
                # 1. Send transcription immediately
                yield f"data: {json.dumps({'type': 'transcription', 'text': query_text})}\n\n"
                
                # Apply per-session voice before generating audio (once at start)
                with sessions.SessionLocal() as db:
                    sessions.apply_session_voice(db, user_id, session_id)

                # 2. Stream text from RAG agent
                stream_gen = await run_rag_agent(query_text, uid, session_id, stream=True)
                
                async for chunk in stream_gen:
                    if chunk:
                        # Clean each chunk in real-time
                        # Replace tool logs with newline
                        cleaned_chunk = tool_log_regex.sub("\n", chunk)
                        full_response += chunk
                        
                        # Send text chunk to UI for display
                        if cleaned_chunk.strip():
                            yield f"data: {json.dumps({'content': cleaned_chunk})}\n\n"
                            await asyncio.sleep(0.01)
                        
                        # Add chunk to sentence buffer
                        complete_sentences = sentence_buffer.add_chunk(cleaned_chunk)
                        
                        # Generate TTS immediately for each complete sentence
                        for sentence in complete_sentences:
                            if sentence.strip():
                                try:
                                    # Generate audio and visemes for this sentence
                                    audio_path, viseme_data = await run_in_threadpool(text_to_speech, sentence)
                                    
                                    audio_filename = None
                                    if audio_path:
                                        audio_filename = os.path.basename(audio_path)
                                    
                                    # Send audio chunk event immediately
                                    yield f"data: {json.dumps({'type': 'audio_chunk', 'sentence_index': sentence_index, 'audio_filename': audio_filename, 'visemes': viseme_data, 'sentence_text': sentence})}\n\n"
                                    sentence_index += 1
                                    
                                except Exception as e:
                                    logging.error(f"Error generating TTS for sentence {sentence_index}: {str(e)}")
                                    # Continue even if one sentence fails

                # 3. Handle any remaining incomplete sentence
                remaining_text = sentence_buffer.flush()
                if remaining_text and remaining_text.strip():
                    try:
                        audio_path, viseme_data = await run_in_threadpool(text_to_speech, remaining_text)
                        audio_filename = None
                        if audio_path:
                            audio_filename = os.path.basename(audio_path)
                        yield f"data: {json.dumps({'type': 'audio_chunk', 'sentence_index': sentence_index, 'audio_filename': audio_filename, 'visemes': viseme_data, 'sentence_text': remaining_text})}\n\n"
                        sentence_index += 1
                    except Exception as e:
                        logging.error(f"Error generating TTS for final sentence: {str(e)}")

                # 4. Clean full response for final event
                cleaned_response = clean_model_output(full_response)

                # 5. Send final done event with audio data and original query text (for UI)
                yield f"data: {json.dumps({'done': True, 'text': query_text, 'full_response': cleaned_response, 'total_audio_chunks': sentence_index})}\n\n"

            except asyncio.CancelledError:
                logging.warning("RAG Stream request cancelled by user")
                return
            except Exception as e:
                logging.error(f"Error in STT TTS streaming: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                active_tasks.pop(key, None)

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except asyncio.CancelledError:
        logging.warning("Request cancelled")
        return JSONResponse(status_code=499, content={"detail": "Request cancelled"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query with TTS: {str(e)}")

#Downloading audio file
def _delete_tts_pair(file_path: str, delay_seconds: int = 2):
    """Background task to delete served WAV and its paired JSON (robust)."""
    try:
        import time, os

        def _safe_unlink(path: str, attempts: int = 8, initial_delay: float = 0.5) -> bool:
            delay = initial_delay
            for _ in range(attempts):
                try:
                    if os.path.exists(path):
                        os.remove(path)
                        return True
                    else:
                        return True
                except Exception:
                    time.sleep(delay)
                    delay = min(delay * 1.5, 5.0)
            return False

        # wait before attempting deletion (streaming + configured delay)
        time.sleep(max(0, delay_seconds))
        json_path = os.path.splitext(file_path)[0] + ".json"
        _safe_unlink(file_path)
        _safe_unlink(json_path)
    except Exception:
        pass

@app.get("/querytts_audio/{filename}")
def querytts_audio(filename: str, background_tasks: BackgroundTasks, delete: Optional[bool] = None, delay_seconds: Optional[int] = None):
    """
    Serves the generated TTS audio file for download/playback.
    """
    # Correctly locate the audio file in the project's tts_cache directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, 'tts_cache', filename)

    if not os.path.exists(file_path):
        # Fallback for older files that might be in the system temp dir, can be removed later
        file_path_temp = os.path.join(tempfile.gettempdir(), filename)
        if not os.path.exists(file_path_temp):
            raise HTTPException(status_code=404, detail=f"Audio file not found at {file_path} or {file_path_temp}.")
        file_path = file_path_temp

    # decide deletion based on query param or config default
    effective_delete = TTS_DELETE_AFTER_SERVE if delete is None else bool(delete)
    effective_delay = TTS_DELETE_DELAY_SECONDS if delay_seconds is None else int(delay_seconds)
    if effective_delete:
        # Schedule deletion in a daemon thread so server reloads don't wait on BackgroundTasks
        try:
            import threading
            threading.Thread(target=_delete_tts_pair, args=(file_path, effective_delay), daemon=True).start()
        except Exception:
            pass
    return FileResponse(file_path, media_type="audio/wav", filename=filename)


@app.post("/query_debug", response_model=QueryResponse)
async def query_agent_debug(request: QueryRequest):
    try:
        print(f"DEBUG: Starting query with: {request.query[:50]}...")
        print(f"DEBUG: User ID: {request.user_id}, Session ID: {request.session_id}")
        
        # Test Ollama connection first
        from AI_Agents_Workflows.config import OLLAMA_BASE_URL, get_current_model_id
        import requests
        
        print(f"DEBUG: Testing Ollama connection to {OLLAMA_BASE_URL}")
        try:
            test_response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": get_current_model_id(),
                    "prompt": "Hello",
                    "stream": False
                },
                timeout=30
            )
            print(f"DEBUG: Ollama test response status: {test_response.status_code}")
            if test_response.status_code == 200:
                print("DEBUG: Ollama connection successful")
            else:
                print(f"DEBUG: Ollama connection failed: {test_response.text}")
        except Exception as e:
            print(f"DEBUG: Ollama connection error: {e}")
        
        print("DEBUG: Calling run_rag_agent...")
        response = await run_rag_agent(request.query, request.user_id, request.session_id)
        print(f"DEBUG: RAG agent response length: {len(response) if response else 0}")
        
        return QueryResponse(
            user_id=request.user_id,
            session_id=request.session_id,
            response=response
        )
    except Exception as e:
        print(f"DEBUG: Exception occurred: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

# Configuration endpoints
@app.post("/set_model")
async def set_model_endpoint(request: SetModelRequest):
    """Set the model for the AI agents"""
    try:
        from AI_Agents_Workflows.config import set_model_id
        # Update runtime config immediately
        set_model_id(request.model)
        # Persist as a per-user setting (use latest record)
        with sessions.SessionLocal() as db:
            settings = (
                db.query(sessions.SessionSettingsDB)
                .filter(sessions.SessionSettingsDB.user_id == request.user_id)
                .order_by(sessions.SessionSettingsDB.updated_at.desc())
                .first()
            )
            now = datetime.utcnow()
            if settings:
                settings.model_id = request.model
                settings.updated_at = now
            else:
                # Ensure non-null voice default when creating a new settings row
                from AI_Agents_Workflows.config import get_current_voice
                db.add(sessions.SessionSettingsDB(user_id=request.user_id, voice=get_current_voice(), model_id=request.model, updated_at=now))
            db.commit()
        logging.info(f"Model change persisted (user-level): user={request.user_id}, model_id={request.model}")
        return {"success": True, "message": f"Model changed to {request.model}"}
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logging.error(f"Error setting model: {str(e)}\n{error_details}")
        raise HTTPException(status_code=500, detail=f"Error setting model: {str(e)}")

@app.post("/set_voice")
async def set_voice_endpoint(request: SetVoiceRequest):
    """Set the voice for TTS"""
    try:
        # Update runtime config immediately
        from AI_Agents_Workflows.config import set_voice
        set_voice(request.voice)
        # Persist as a per-user setting (use latest record)
        with sessions.SessionLocal() as db:
            settings = (
                db.query(sessions.SessionSettingsDB)
                .filter(sessions.SessionSettingsDB.user_id == request.user_id)
                .order_by(sessions.SessionSettingsDB.updated_at.desc())
                .first()
            )
            now = datetime.utcnow()
            if settings:
                settings.voice = request.voice
                settings.updated_at = now
            else:
                db.add(sessions.SessionSettingsDB(user_id=request.user_id, voice=request.voice, updated_at=now))
            db.commit()
        logging.info(f"Voice change persisted (user-level): user={request.user_id}, voice={request.voice}")
        return {"success": True, "message": f"Voice changed to {request.voice}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error setting voice: {str(e)}")

@app.get("/config", response_model=ConfigResponse)
async def get_config(user_id: Optional[str] = None, request: Request = None):
    """Return current runtime configuration (admin-only)."""
    try:
        # Verify admin via token if present
        token_payload = get_user_from_auth_header(request.headers.get("Authorization")) if request else None
        uid = user_id
        role = None
        with users.SessionLocal() as db:
            if token_payload:
                uid = token_payload.get("uid")
                role = token_payload.get("role")
            u = db.query(users.UserDB).filter(users.UserDB.id == uid).first()
            if not u or (u.role != "admin"):
                raise HTTPException(status_code=403, detail="Admin access required")
        from AI_Agents_Workflows.config import get_runtime_config
        cfg = get_runtime_config()
        return ConfigResponse(**cfg)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching config: {str(e)}")

@app.put("/config", response_model=ConfigResponse)
async def update_config(request: ConfigUpdateRequest, http_request: Request = None):
    """Update runtime configuration (admin-only)."""
    try:
        # Verify admin via token if present
        with users.SessionLocal() as db:
            uid = request.user_id
            token_payload = get_user_from_auth_header(http_request.headers.get("Authorization")) if http_request else None
            if token_payload:
                uid = token_payload.get("uid")
            u = db.query(users.UserDB).filter(users.UserDB.id == uid).first()
            if not u or u.role != "admin":
                raise HTTPException(status_code=403, detail="Admin access required")
        from AI_Agents_Workflows.config import update_runtime_config
        cfg = update_runtime_config({
            "model": request.model,
            "voice": request.voice,
            "ollama_base_url": request.ollama_base_url,
            "openai_api_key": request.openai_api_key,
            "google_api_key": request.google_api_key,
            "openrouter_api_key": request.openrouter_api_key,
            "agno_api_key": request.agno_api_key,
            "gemini_search_enabled": request.gemini_search_enabled,
            "mcp_transport": request.mcp_transport,
            "mcp_server_url": request.mcp_server_url,
            "mcp_stdio_command": request.mcp_stdio_command,
            "mcp_stdio_args": request.mcp_stdio_args,
            "mcp_stdio_commands": request.mcp_stdio_commands,
            "mcp_stdio_tools": request.mcp_stdio_tools,
            "available_models_labeled": request.available_models_labeled,
            "available_models": request.available_models,
            "available_voices_labeled": request.available_voices_labeled,
            "available_voices": request.available_voices,
            "mcp_servers": request.mcp_servers,
        })
        return ConfigResponse(**cfg)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating config: {str(e)}")

@app.get("/config_path", response_model=ConfigPathResponse)
async def get_config_path(user_id: Optional[str] = None, request: Request = None):
    """Return the absolute path to the persisted runtime config (admin-only)."""
    try:
        # Verify admin via token if present
        with users.SessionLocal() as db:
            uid = user_id
            token_payload = get_user_from_auth_header(request.headers.get("Authorization")) if request else None
            if token_payload:
                uid = token_payload.get("uid")
            u = db.query(users.UserDB).filter(users.UserDB.id == uid).first()
            if not u or u.role != "admin":
                raise HTTPException(status_code=403, detail="Admin access required")
        from AI_Agents_Workflows.config import CONFIG_STATE_PATH
        path_str = str(CONFIG_STATE_PATH.resolve())
        return ConfigPathResponse(config_state_path=path_str, exists=os.path.exists(CONFIG_STATE_PATH))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching config path: {str(e)}")

# Health and monitoring endpoints
@app.get("/")
async def root():
    """Root endpoint with basic info"""
    return {
        "message": "AI Teacher Assistant API",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "docs": "/docs"
    }

# Fallback to neutralize unwanted WebSocket requests hitting `/ws/config`.
# We do not support WebSocket-based config updates. Returning 410 clearly
# communicates that the endpoint is intentionally disabled and stops retry loops.
@app.get("/ws/config")
async def ws_config_fallback():
    return JSONResponse(
        status_code=410,
        content={
            "status": "disabled",
            "message": "WebSocket config updates are disabled; use HTTP /config",
        },
    )


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    try:
        # You can add more health checks here (database, services, etc.)
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "api": "running",
                "database": "connected",  # You can add actual DB check
                "ollama": "connected",    # You can add actual Ollama check
                "tts": "available"        # You can add actual TTS check
            }
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.get("/status")
async def deployment_status():
    """Deployment status endpoint"""
    return {
        "deployment": "completed",
        "build_time": datetime.now().isoformat(),
        "environment": "production",
        "version": "1.0.0"
    }
class ModelsCatalogResponse(BaseModel):
    models: list[str]

class VoicesCatalogResponse(BaseModel):
    voices: list[str]

class McpToolItem(BaseModel):
    label: str
    url: str

class McpToolsCatalogResponse(BaseModel):
    tools: list[McpToolItem]

class McpStdioItem(BaseModel):
    label: str
    command: str

class McpStdioToolsCatalogResponse(BaseModel):
    tools: list[McpStdioItem]

# Labeled catalogs for non-admin clients
class LabeledItem(BaseModel):
    label: str
    id: str
    provider: Optional[str] = None
    supports_images: bool = False
    supports_audio: bool = False
    supports_videos: bool = False

class ModelsCatalogLabeledResponse(BaseModel):
    items: list[LabeledItem]

class VoicesCatalogLabeledResponse(BaseModel):
    items: list[LabeledItem]

@app.get("/models", response_model=ModelsCatalogResponse)
async def get_models(user_id: Optional[str] = None, request: Request = None):
    """Return available models catalog to any authenticated user."""
    try:
        # Verify user via token if present (any role)
        with users.SessionLocal() as db:
            uid = user_id
            token_payload = get_user_from_auth_header(request.headers.get("Authorization")) if request else None
            if token_payload:
                uid = token_payload.get("uid")
            u = db.query(users.UserDB).filter(users.UserDB.id == uid).first()
            if not u:
                raise HTTPException(status_code=401, detail="Invalid user")
        from AI_Agents_Workflows.config import get_runtime_config
        cfg = get_runtime_config()
        return ModelsCatalogResponse(models=cfg.get("available_models", []))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching models: {str(e)}")

@app.get("/models_labeled", response_model=ModelsCatalogLabeledResponse)
async def get_models_labeled(user_id: Optional[str] = None, request: Request = None):
    try:
        with users.SessionLocal() as db:
            uid = user_id
            token_payload = get_user_from_auth_header(request.headers.get("Authorization")) if request else None
            if token_payload:
                uid = token_payload.get("uid")
            u = db.query(users.UserDB).filter(users.UserDB.id == uid).first()
            if not u:
                raise HTTPException(status_code=401, detail="Invalid user")
        from AI_Agents_Workflows.config import get_runtime_config
        cfg = get_runtime_config()
        labeled = cfg.get("available_models_labeled", []) or []
        items: list[LabeledItem] = []
        if labeled:
            for m in labeled:
                if isinstance(m, dict):
                    label = str(m.get("label", "Model"))
                    mid = str(m.get("id", ""))
                    provider = m.get("provider")
                    supports_images = bool(m.get("supports_images", False))
                    supports_audio = bool(m.get("supports_audio", False))
                    supports_videos = bool(m.get("supports_videos", False))
                    if mid.strip():
                        items.append(LabeledItem(
                            label=label, 
                            id=mid, 
                            provider=provider,
                            supports_images=supports_images,
                            supports_audio=supports_audio,
                            supports_videos=supports_videos
                        ))
        else:
            for mid in cfg.get("available_models", []) or []:
                ms = str(mid).strip()
                if ms:
                    items.append(LabeledItem(label=ms, id=ms))
        return ModelsCatalogLabeledResponse(items=items)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching labeled models: {str(e)}")

# Voices catalog for any authenticated user
@app.get("/voices", response_model=VoicesCatalogResponse)
async def get_voices(user_id: Optional[str] = None, request: Request = None):
    """Return available voices catalog to any authenticated user."""
    try:
        # Verify user via token if present (any role)
        with users.SessionLocal() as db:
            uid = user_id
            token_payload = get_user_from_auth_header(request.headers.get("Authorization")) if request else None
            if token_payload:
                uid = token_payload.get("uid")
            u = db.query(users.UserDB).filter(users.UserDB.id == uid).first()
            if not u:
                raise HTTPException(status_code=401, detail="Invalid user")
        from AI_Agents_Workflows.config import get_runtime_config
        cfg = get_runtime_config()
        return VoicesCatalogResponse(voices=cfg.get("available_voices", []))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching voices: {str(e)}")

@app.get("/voices_labeled", response_model=VoicesCatalogLabeledResponse)
async def get_voices_labeled(user_id: Optional[str] = None, request: Request = None):
    try:
        with users.SessionLocal() as db:
            uid = user_id
            token_payload = get_user_from_auth_header(request.headers.get("Authorization")) if request else None
            if token_payload:
                uid = token_payload.get("uid")
            u = db.query(users.UserDB).filter(users.UserDB.id == uid).first()
            if not u:
                raise HTTPException(status_code=401, detail="Invalid user")
        from AI_Agents_Workflows.config import get_runtime_config
        cfg = get_runtime_config()
        labeled = cfg.get("available_voices_labeled", []) or []
        items: list[LabeledItem] = []
        if labeled:
            for v in labeled:
                if isinstance(v, dict):
                    label = str(v.get("label", "Voice"))
                    vid = str(v.get("id", ""))
                    if vid.strip():
                        items.append(LabeledItem(label=label, id=vid))
        else:
            for vid in cfg.get("available_voices", []) or []:
                vs = str(vid).strip()
                if vs:
                    items.append(LabeledItem(label=vs, id=vs))
        return VoicesCatalogLabeledResponse(items=items)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching labeled voices: {str(e)}")

# MCP tools catalog for any authenticated user
@app.get("/mcp_tools", response_model=McpToolsCatalogResponse)
async def get_mcp_tools(user_id: Optional[str] = None, request: Request = None):
    """Return available MCP tools (label + url) configured by admin."""
    try:
        # Verify user via token if present (any role)
        with users.SessionLocal() as db:
            uid = user_id
            token_payload = get_user_from_auth_header(request.headers.get("Authorization")) if request else None
            if token_payload:
                uid = token_payload.get("uid")
            u = db.query(users.UserDB).filter(users.UserDB.id == uid).first()
            if not u:
                raise HTTPException(status_code=401, detail="Invalid user")
        from AI_Agents_Workflows.config import get_runtime_config
        cfg = get_runtime_config()
        servers = cfg.get("mcp_servers", []) or []
        items = []
        for s in servers:
            if isinstance(s, dict):
                label = str(s.get("label", "Server"))
                raw_url = str(s.get("url", ""))
                if raw_url.strip():
                    try:
                        # Sanitize: remove query string to avoid exposing secrets
                        base = raw_url.split("?")[0]
                        items.append(McpToolItem(label=label, url=base))
                    except Exception:
                        items.append(McpToolItem(label=label, url=""))
        return McpToolsCatalogResponse(tools=items)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching MCP tools: {str(e)}")

@app.get("/mcp_stdio_tools", response_model=McpStdioToolsCatalogResponse)
async def get_mcp_stdio_tools(user_id: Optional[str] = None, request: Request = None):
    """Return available stdio MCP commands configured by admin (any authenticated user)."""
    try:
        with users.SessionLocal() as db:
            uid = user_id
            token_payload = get_user_from_auth_header(request.headers.get("Authorization")) if request else None
            if token_payload:
                uid = token_payload.get("uid")
            u = db.query(users.UserDB).filter(users.UserDB.id == uid).first()
            if not u:
                raise HTTPException(status_code=401, detail="Invalid user")
        from AI_Agents_Workflows.config import get_runtime_config
        cfg = get_runtime_config()
        tools = cfg.get("mcp_stdio_tools", []) or []
        items: list[McpStdioItem] = []
        def _mask(cmd: str) -> str:
            try:
                import re
                s = str(cmd)
                patterns = [
                    r"(?i)(api_key=)([^&\s]+)",
                    r"(?i)(apikey=)([^&\s]+)",
                    r"(?i)(token=)([^&\s]+)",
                    r"(?i)(--api-key\s+)([^\s]+)",
                    r"(?i)(--token\s+)([^\s]+)",
                ]
                for p in patterns:
                    s = re.sub(p, lambda m: m.group(1) + "<redacted>", s)
                return s
            except Exception:
                return str(cmd)
        for t in tools:
            if isinstance(t, dict):
                label = str(t.get("label", "Command"))
                command = str(t.get("command", ""))
                if command.strip():
                    items.append(McpStdioItem(label=label, command=_mask(command)))
        # Backward compatibility: if no labeled tools, fall back to commands list
        if not items:
            cmds = cfg.get("mcp_stdio_commands", []) or []
            for i, c in enumerate(cmds, 1):
                cs = str(c).strip()
                if cs:
                    items.append(McpStdioItem(label=f"Command {i}", command=_mask(cs)))
        return McpStdioToolsCatalogResponse(tools=items)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching MCP stdio tools: {str(e)}")

class SetMcpToolsRequest(BaseModel):
    user_id: str
    session_id: str
    tool_labels: Optional[list[str]] = None
    tool_urls: Optional[list[str]] = None

class SetMcpStdioToolsRequest(BaseModel):
    user_id: str
    session_id: str
    commands: Optional[list[str]] = None

@app.post("/set_mcp_tools")
async def set_mcp_tools(request: SetMcpToolsRequest):
    """Persist per-user MCP tool selection. Accepts labels (preferred) or URLs."""
    try:
        # Resolve URLs from labels if provided
        urls: list[str] = []
        if request.tool_labels and len(request.tool_labels) > 0:
            from AI_Agents_Workflows.config import get_runtime_config
            cfg = get_runtime_config()
            servers = cfg.get("mcp_servers", []) or []
            label_to_url = {str(s.get("label", "")).lower().strip(): str(s.get("url", "")).strip() for s in servers if isinstance(s, dict)}
            for lbl in request.tool_labels:
                u = label_to_url.get(str(lbl).lower().strip())
                if u:
                    urls.append(u)
        elif request.tool_urls:
            urls = [str(u).strip() for u in request.tool_urls if str(u).strip()]

        # Store JSON array in session settings (user-level)
        import json as _json
        with sessions.SessionLocal() as db:
            settings = (
                db.query(sessions.SessionSettingsDB)
                .filter(sessions.SessionSettingsDB.user_id == request.user_id)
                .order_by(sessions.SessionSettingsDB.updated_at.desc())
                .first()
            )
            now = datetime.utcnow()
            urls_json = _json.dumps(urls or [])
            if settings:
                settings.mcp_tools_urls = urls_json
                settings.updated_at = now
            else:
                # Create with defaults for missing fields
                from AI_Agents_Workflows.config import get_current_voice, get_current_model_id
                db.add(sessions.SessionSettingsDB(user_id=request.user_id, voice=get_current_voice(), model_id=get_current_model_id(), mcp_tools_urls=urls_json, updated_at=now))
            db.commit()
        logging.info(f"MCP tools selection persisted: user={request.user_id}, urls={len(urls)}")
        return {"success": True, "count": len(urls)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error setting MCP tools: {str(e)}")

@app.post("/set_mcp_stdio_tools")
async def set_mcp_stdio_tools(request: SetMcpStdioToolsRequest):
    """Persist per-user stdio MCP command selection."""
    try:
        cmds: list[str] = []
        if request.commands:
            cmds = [str(c).strip() for c in request.commands if str(c).strip()]
        import json as _json
        with sessions.SessionLocal() as db:
            settings = (
                db.query(sessions.SessionSettingsDB)
                .filter(sessions.SessionSettingsDB.user_id == request.user_id)
                .order_by(sessions.SessionSettingsDB.updated_at.desc())
                .first()
            )
            now = datetime.utcnow()
            cmds_json = _json.dumps(cmds or [])
            if settings:
                settings.mcp_stdio_commands = cmds_json
                settings.updated_at = now
            else:
                from AI_Agents_Workflows.config import get_current_voice, get_current_model_id
                db.add(sessions.SessionSettingsDB(user_id=request.user_id, voice=get_current_voice(), model_id=get_current_model_id(), mcp_stdio_commands=cmds_json, updated_at=now))
            db.commit()
        logging.info(f"MCP stdio tools selection persisted: user={request.user_id}, cmds={len(cmds)}")
        return {"success": True, "count": len(cmds)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error setting MCP stdio tools: {str(e)}")

# Refresh endpoint
@app.post("/auth/refresh")
async def auth_refresh(request: Request):
    try:
        token = request.cookies.get("refresh_token")
        if not token:
            raise HTTPException(status_code=401, detail="Unauthorized")
        payload = verify_refresh_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = str(payload.get("uid"))
        role = str(payload.get("role"))
        jti = str(payload.get("jti"))
        from fastapi import Response
        response = Response()
        with _UserSessionLocal() as db:
            if not is_refresh_valid(db, jti):
                raise HTTPException(status_code=401, detail="Unauthorized")
            new_access = issue_access_token(uid, role)
            new_refresh = issue_refresh_token(uid, role)
            new_payload = verify_refresh_token(new_refresh)
            new_jti = str(new_payload.get("jti")) if new_payload else ""
            exp = datetime.datetime.utcfromtimestamp(int(new_payload.get("exp", 0))) if new_payload else datetime.datetime.utcnow()
            revoke_refresh(db, jti, replaced_by=new_jti)
            store_refresh(db, uid, new_jti, exp)
        secure_flag = True if (APP_ENV == "production") else False
        response.set_cookie(key="refresh_token", value=new_refresh, httponly=True, secure=secure_flag, samesite="lax", path="/")
        return {"access_token": new_access}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing token: {str(e)}")
