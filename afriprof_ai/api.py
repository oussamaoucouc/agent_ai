"""
API endpoints for the AI Teacher Assistant application (FastAPI app instance).
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, constr
from typing import Optional, Dict, Any
import json
import tempfile
import shutil
import os
import time
import datetime
from pydub import AudioSegment
from teacher_agent.rag_agent import run_rag_agent, initialize_knowledge_base
from teacher_agent.locks import get_user_kb_lock
from teacher_agent.ai_agent_assistant import run_assistant_agent
from teacher_agent.config import get_user_pdf_dir
from teacher_agent.mcp_agent import run_agent_async as run_mcp_agent
from teacher_agent.tts import text_to_speech
from teacher_agent.config import TTS_DELETE_AFTER_SERVE, TTS_DELETE_DELAY_SECONDS
from typing import Optional
from teacher_agent.stt import initialize_stt
import base64
import uuid
from fastapi.responses import FileResponse
from fastapi.concurrency import run_in_threadpool
import asyncio
from datetime import datetime
import sessions
import logging


# Sessions persistence moved to sessions.py


app = FastAPI(
    title="AI Teacher Assistant",
    description="An interactive educational assistant using RAG, speech recognition, and AI",
    version="1.0.0"
)

# CORS configuration
origins = [
    "http://localhost:3000",  # Adjust if your frontend runs on a different port
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include sessions router
app.include_router(sessions.router)

# Registry of active tasks per user/session for cancellation
active_tasks: Dict[str, asyncio.Task] = {}

# Helper: robustly clean model output to remove internal reasoning and tool traces
def clean_model_output(text: str) -> str:
    import re
    if not text:
        return ""

    # Remove <think> blocks (case-insensitive, multiline)
    text = re.sub(r'(?is)<think>.*?</think>', '', text)

    # Remove common chain-of-thought or tool traces enclosed in bracket tags
    labels = [
        'TOOL_CALLS', 'ANALYSIS', 'REASONING', 'INTERNAL', 'SYSTEM', 'DEBUG', 'SCRATCHPAD'
    ]
    for label in labels:
        # [LABEL] ... [/LABEL]
        text = re.sub(rf'(?is)\[{label}\].*?\[/{label}\]', '', text)
        # [LABEL] ... [LABEL] (duplicate marker style)
        text = re.sub(rf'(?is)\[{label}\].*?\[{label}\]', '', text)
        # [LABEL] ... end-of-line
        text = re.sub(rf'(?is)\[{label}\].*?(?=\n|$)', '', text)

    # Prefer explicit final-response markers if present
    m = re.search(r'(?is)(Final Response:|Final Answer:|Assistant Response:|User-facing response:)\s*(.*)', text)
    if m:
        text = m.group(2)
    else:
        m2 = re.search(r'(?is)(Response:|Answer:)\s*(.*)', text)
        if m2:
            text = m2.group(2)

    # Remove markdown code fences and language hints
    text = re.sub(r'```[a-zA-Z]*\s*', '', text)
    text = re.sub(r'```', '', text)

    # Strip list and step markers from each line
    lines = text.splitlines()
    lines = [re.sub(r'^\s*(?:[-*]\s+|\d+[.)]\s+|Step\s*\d+\s*:)', '', line) for line in lines]
    text = '\n'.join(lines)

    # Collapse excessive blank lines and trim
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    text = text.strip()

    # Fallback: choose a sensible paragraph if brackets remain or text is meta-heavy
    if not text or re.search(r'(?is)\[[A-Z][A-Z_]+\]', text):
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        candidates = [p for p in paragraphs if not re.search(r'(?is)\[[A-Z][A-Z_]+\]', p)]
        if candidates:
            # Prefer last sentence-like paragraph, else the longest
            selected = None
            for p in reversed(candidates):
                if re.search(r'[.!?]\s*$', p):
                    selected = p
                    break
            text = selected or max(candidates, key=len)
        else:
            # As last resort, remove any bracket tags and trim
            text = re.sub(r'(?is)\[[A-Z][A-Z_]+\]', '', text).strip()

    return text

# Session models, schemas, and endpoints moved to sessions.py

class LoginRequest(BaseModel):
    username: str

class QueryRequest(BaseModel):
    user_id: str
    session_id: str
    query: constr(strip_whitespace=True, min_length=1, max_length=2000)

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

class CancelRequest(BaseModel):
    user_id: str
    session_id: str

@app.post("/cancel")
async def cancel_endpoint(request: CancelRequest):
    key = f"{request.user_id}:{request.session_id}"
    task = active_tasks.pop(key, None)
    if task and not task.done():
        task.cancel()
        return {"status": "cancelled"}
    return {"status": "idle"}

@app.post("/login")
async def login(request: LoginRequest):
    # In a real application, you would verify the username and create a real session.
    # For now, we'll just generate a user_id and session_id.
    user_id = f"{request.username}_{str(uuid.uuid4())[:8]}"
    session_id = str(uuid.uuid4())
    return {"user_id": user_id, "session_id": session_id}

@app.post("/upload_document", response_model=Dict[str, str])
async def upload_document_endpoint(file: UploadFile = File(...), user_id: str = Form(...), session_id: str = Form(...)):
    try:
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension != ".pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")

        # Save the uploaded file to the per-user PDFs directory
        user_pdfs_dir = str(get_user_pdf_dir(user_id))
        os.makedirs(user_pdfs_dir, exist_ok=True)
        safe_name = os.path.basename(file.filename)
        file_path = os.path.join(user_pdfs_dir, safe_name)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        # Immediately upsert into KB so the newly added document is indexed
        lock = get_user_kb_lock(user_id)
        logging.info(f"Waiting for KB lock for user {user_id} (upload)")
        async with lock:
            logging.info(f"Entered KB lock for user {user_id} (upload)")
            kb = await initialize_knowledge_base(user_id)
            try:
                await kb.aload(recreate=False, upsert=True)
                logging.info(f"KB upsert load complete for user {user_id} (upload)")
            except Exception as e:
                # Fallback: first-time collection creation or backend hiccup
                msg = str(e).lower()
                if "not found" in msg or "does not exist" in msg or "no such" in msg:
                    logging.info(f"Upsert failed; recreating collection for user {user_id} (upload)")
                    await kb.aload(recreate=True, upsert=False)
                    logging.info(f"KB recreate load complete for user {user_id} (upload)")
                else:
                    raise
        return {"message": f"Successfully uploaded {safe_name}", "filename": safe_name, "path": file_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")

# List documents for a user (persisted on disk)
@app.get("/list_documents", response_model=Dict[str, Any])
async def list_documents(user_id: str):
    try:
        user_pdfs_dir = str(get_user_pdf_dir(user_id))
        os.makedirs(user_pdfs_dir, exist_ok=True)
        docs = []
        for name in os.listdir(user_pdfs_dir):
            if name.lower().endswith(".pdf"):
                docs.append({
                    "filename": name,
                    "path": os.path.join(user_pdfs_dir, name)
                })
        return {"documents": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")

# Delete a document for a user and sync KB
@app.delete("/delete_document", response_model=Dict[str, str])
async def delete_document(user_id: str, filename: str):
    try:
        user_pdfs_dir = str(get_user_pdf_dir(user_id))
        os.makedirs(user_pdfs_dir, exist_ok=True)
        safe_name = os.path.basename(filename)
        file_path = os.path.join(user_pdfs_dir, safe_name)
        if not os.path.isfile(file_path):
            raise HTTPException(status_code=404, detail="File not found")
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
        # Trigger KB sync (rebuild collection to reflect deletion)
        lock = get_user_kb_lock(user_id)
        logging.info(f"Waiting for KB lock for user {user_id} (delete)")
        async with lock:
            logging.info(f"Entered KB lock for user {user_id} (delete)")
            kb = await initialize_knowledge_base(user_id)
            await kb.aload(recreate=True, upsert=False)
            logging.info(f"KB recreate load complete for user {user_id} (delete)")
        return {"message": "Successfully deleted", "filename": safe_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")

#LLM QUERY
@app.post("/query", response_model=QueryResponse)
async def query_agent(request: QueryRequest):
    try:
        response = await run_rag_agent(request.query, request.user_id, request.session_id)
        return QueryResponse(
            user_id=request.user_id,
            session_id=request.session_id,
            response=response
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# MCP LLM QUERY
@app.post("/query_mcp", response_model=QueryResponse)
async def query_mcp(request: QueryRequest):
    try:
        response = await run_mcp_agent(request.query, request.user_id, request.session_id)
        return QueryResponse(
            user_id=request.user_id,
            session_id=request.session_id,
            response=response
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ASSISTANT LLM QUERY
@app.post("/query_assistant", response_model=QueryResponse)
async def query_assistant(request: QueryRequest):
    try:
        response = await run_assistant_agent(request.query, request.user_id, request.session_id)
        return QueryResponse(
            user_id=request.user_id,
            session_id=request.session_id,
            response=response
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ASSISTANT LLM QUERY not displayed Reasoning
@app.post("/query_assistant_direct", response_model=QueryResponse)
async def query_assistant_direct(request: QueryRequest):
    key = f"{request.user_id}:{request.session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        response = await run_assistant_agent(request.query, request.user_id, request.session_id)
        response = clean_model_output(response)

        return QueryResponse(
            user_id=request.user_id,
            session_id=request.session_id,
            response=response
        )
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Request cancelled")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        active_tasks.pop(key, None)

# MCP LLM QUERY not displayed Reasoning
@app.post("/query_mcp_direct", response_model=QueryResponse)
async def query_mcp_direct(request: QueryRequest):
    key = f"{request.user_id}:{request.session_id}"
    try:
        # Track the current handler task for cancellation as well
        current = asyncio.current_task()
        if current:
            active_tasks[key] = current
        # Run MCP agent as a cancellable task
        task = asyncio.create_task(run_mcp_agent(request.query, request.user_id, request.session_id))
        response = await task
        response = clean_model_output(response)
        return QueryResponse(
            user_id=request.user_id,
            session_id=request.session_id,
            response=response
        )
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Request cancelled")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        active_tasks.pop(key, None)

# MCP Speech-to-text then Query
@app.post("/stt_query_mcp", response_model=Dict[str, str])
async def stt_query_mcp_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...)
):
    try:
        # First transcribe the audio
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        # Get the transcribed text
        query_text = stt_result["text"]
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        # Process the query using the MCP agent
        response = await run_mcp_agent(query_text, user_id, session_id)

        return {
            "text": query_text,
            "response": response,
            "user_id": user_id,
            "session_id": session_id,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query: {str(e)}")

# ASSISTANT Speech-to-text then Query
@app.post("/stt_query_assistant", response_model=Dict[str, str])
async def stt_query_assistant_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...)
):
    try:
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        query_text = stt_result["text"]
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        response = await run_assistant_agent(query_text, user_id, session_id)

        return {
            "text": query_text,
            "response": response,
            "user_id": user_id,
            "session_id": session_id,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query: {str(e)}")

# ASSISTANT STT then Query, direct (filtered reasoning)
@app.post("/stt_query_assistant_direct", response_model=Dict[str, str])
async def stt_query_assistant_direct_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...)
):
    try:
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        query_text = stt_result["text"]
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        response = await run_assistant_agent(query_text, user_id, session_id)
        response = clean_model_output(response)

        return {
            "text": query_text,
            "response": response,
            "user_id": user_id,
            "session_id": session_id,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query: {str(e)}")

# MCP STT then Query, direct (filtered reasoning)
@app.post("/stt_query_mcp_direct", response_model=Dict[str, str])
async def stt_query_mcp_direct_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...)
):
    try:
        # First transcribe the audio
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        # Get the transcribed text
        query_text = stt_result["text"]
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        # Process the query using the MCP agent
        response = await run_mcp_agent(query_text, user_id, session_id)
        response = clean_model_output(response)

        return {
            "text": query_text,
            "response": response,
            "user_id": user_id,
            "session_id": session_id,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query: {str(e)}")

# MCP Query then TTS
@app.post("/query_mcp_tts")
async def query_mcp_tts_endpoint(request: QueryRequest):
    """
    Returns a JSON with the MCP text response, audio filename, and viseme data.
    """
    try:
        response_text = await run_mcp_agent(request.query, request.user_id, request.session_id)

        # Generate audio and visemes
        # Apply per-session voice before generating audio
        with sessions.SessionLocal() as db:
            sessions.apply_session_voice(db, request.user_id, request.session_id)
        audio_path, viseme_data = await run_in_threadpool(text_to_speech, response_text)

        audio_filename = None
        if audio_path:
            audio_filename = os.path.basename(audio_path)

        return {
            "user_id": request.user_id,
            "session_id": request.session_id,
            "response": response_text,
            "audio_filename": audio_filename,
            "visemes": viseme_data,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ASSISTANT Query then TTS
@app.post("/query_assistant_tts")
async def query_assistant_tts_endpoint(request: QueryRequest):
    """
    Returns a JSON with the assistant text response, audio filename, and viseme data.
    """
    try:
        response_text = await run_assistant_agent(request.query, request.user_id, request.session_id)

        with sessions.SessionLocal() as db:
            sessions.apply_session_voice(db, request.user_id, request.session_id)
        audio_path, viseme_data = await run_in_threadpool(text_to_speech, response_text)

        audio_filename = None
        if audio_path:
            audio_filename = os.path.basename(audio_path)

        return {
            "user_id": request.user_id,
            "session_id": request.session_id,
            "response": response_text,
            "audio_filename": audio_filename,
            "visemes": viseme_data,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ASSISTANT Query direct then TTS (filtered reasoning)
@app.post("/query_assistant_tts_direct")
async def query_assistant_tts_direct(request: QueryRequest):
    """
    Returns a JSON with the filtered assistant text response, audio filename, and viseme data.
    """
    key = f"{request.user_id}:{request.session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        response_text = await run_assistant_agent(request.query, request.user_id, request.session_id)
        response_text = clean_model_output(response_text)

        with sessions.SessionLocal() as db:
            sessions.apply_session_voice(db, request.user_id, request.session_id)
        audio_path, viseme_data = await run_in_threadpool(text_to_speech, response_text)
        
        audio_filename = None
        if audio_path:
            audio_filename = os.path.basename(audio_path)

        return {
            "user_id": request.user_id,
            "session_id": request.session_id,
            "response": response_text,
            "audio_filename": audio_filename,
            "visemes": viseme_data,
            "status": "success"
        }
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Request cancelled")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        active_tasks.pop(key, None)

# MCP Query direct then TTS (filtered reasoning)
@app.post("/query_mcp_tts_direct")
async def query_mcp_tts_direct(request: QueryRequest):
    """
    Returns a JSON with the filtered MCP text response, audio filename, and viseme data.
    """
    key = f"{request.user_id}:{request.session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        response_text = await run_mcp_agent(request.query, request.user_id, request.session_id)
        response_text = clean_model_output(response_text)

        # Generate audio and visemes
        # Apply per-session voice before generating audio
        with sessions.SessionLocal() as db:
            sessions.apply_session_voice(db, request.user_id, request.session_id)
        audio_path, viseme_data = await run_in_threadpool(text_to_speech, response_text)
        
        audio_filename = None
        if audio_path:
            audio_filename = os.path.basename(audio_path)

        return {
            "user_id": request.user_id,
            "session_id": request.session_id,
            "response": response_text,
            "audio_filename": audio_filename,
            "visemes": viseme_data,
            "status": "success"
        }
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Request cancelled")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        active_tasks.pop(key, None)

# MCP Full Agent: STT -> Query -> TTS
@app.post("/stt_query_mcp_tts", response_model=Dict[str, Any])
async def stt_query_mcp_tts_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...)
):
    """
    Combined STT, MCP query, and TTS endpoint that returns viseme data and audio filename.
    """
    try:
        # First transcribe the audio
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        # Get the transcribed text
        query_text = stt_result["text"]
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        # Process the query using the MCP agent
        response_text = await run_mcp_agent(query_text, user_id, session_id)

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
            "user_id": user_id,
            "session_id": session_id,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query with TTS: {str(e)}")

# ASSISTANT Full Agent: STT -> Query -> TTS
@app.post("/stt_query_assistant_tts", response_model=Dict[str, Any])
async def stt_query_assistant_tts_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...)
):
    """
    Combined STT, assistant query, and TTS endpoint that returns viseme data and audio filename.
    """
    try:
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        query_text = stt_result["text"]
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        response_text = await run_assistant_agent(query_text, user_id, session_id)

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
            "user_id": user_id,
            "session_id": session_id,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query with TTS: {str(e)}")

# ASSISTANT Full Agent direct: STT -> Query (filtered) -> TTS
@app.post("/stt_query_assistant_tts_direct", response_model=Dict[str, Any])
async def stt_query_assistant_tts_direct_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...)
):
    """
    Combined STT, filtered assistant query, and TTS endpoint that returns viseme data and audio filename.
    """
    key = f"{user_id}:{session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        query_text = stt_result["text"]
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        response_text = await run_assistant_agent(query_text, user_id, session_id)
        response_text = clean_model_output(response_text)

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
            "user_id": user_id,
            "session_id": session_id,
            "status": "success"
        }
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Request cancelled")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query with TTS: {str(e)}")
    finally:
        active_tasks.pop(key, None)
# MCP Full Agent direct: STT -> Query (filtered) -> TTS
@app.post("/stt_query_mcp_tts_direct", response_model=Dict[str, Any])
async def stt_query_mcp_tts_direct_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...)
):
    """
    Combined STT, filtered MCP query, and TTS endpoint that returns viseme data and audio filename.
    """
    key = f"{user_id}:{session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        # First transcribe the audio
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        # Get the transcribed text
        query_text = stt_result["text"]
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        # Process the query using the MCP agent with filtering
        response_text = await run_mcp_agent(query_text, user_id, session_id)
        response_text = clean_model_output(response_text)

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
            "user_id": user_id,
            "session_id": session_id,
            "status": "success"
        }
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Request cancelled")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query with TTS: {str(e)}")
    finally:
        active_tasks.pop(key, None)
#LLM QUERY not displayed Reasoning
@app.post("/query_direct", response_model=QueryResponse)
async def query_direct(request: QueryRequest):
    key = f"{request.user_id}:{request.session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        response = await run_rag_agent(request.query, request.user_id, request.session_id)
        # Clean model output to remove think/tool traces and formatting
        response = clean_model_output(response)

        return QueryResponse(
            user_id=request.user_id,
            session_id=request.session_id,
            response=response
        )
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Request cancelled")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        active_tasks.pop(key, None)

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
        file_extension = os.path.splitext(file.filename)[1].lower() if file.filename else ".wav"
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
                raise HTTPException(status_code=400, detail=f"Error converting audio format: {str(e)}")
        else:
            try:
                audio = AudioSegment.from_file(input_path)
                audio = audio.set_channels(1).set_frame_rate(16000)
                audio.export(input_path, format="wav")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Error processing WAV audio: {str(e)}")

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
    session_id: str = Form(...)
):
    """
    Combined STT and query endpoint that:
    1. Converts audio input to text
    2. Processes the query using the RAG agent
    3. Returns both the transcribed text and the query response
    """
    try:
        # First transcribe the audio
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        # Get the transcribed text
        query_text = stt_result["text"]
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        # Process the query using the RAG agent
        response = await run_rag_agent(query_text, user_id, session_id)

        return {
            "text": query_text,
            "response": response,
            "user_id": user_id,
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
    session_id: str = Form(...)
):
    """
    Combined STT and filtered query endpoint that:
    1. Converts audio input to text
    2. Processes the query using the RAG agent with filtering
    3. Returns both the transcribed text and the filtered query response
    """
    try:
        # First transcribe the audio
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        # Get the transcribed text
        query_text = stt_result["text"]
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        # Process the query using the RAG agent and clean output
        response = await run_rag_agent(query_text, user_id, session_id)
        response = clean_model_output(response)

        return {
            "text": query_text,
            "response": response,
            "user_id": user_id,
            "session_id": session_id,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query: {str(e)}")

#Query to speach to text 
@app.post("/query_tts")
async def query_tts_endpoint(request: QueryRequest):
    """
    Returns a JSON with the text response, audio filename, and viseme data.
    """
    try:
        response_text = await run_rag_agent(request.query, request.user_id, request.session_id)
        
        # Generate audio and visemes
        # Apply per-session voice before generating audio
        with sessions.SessionLocal() as db:
            sessions.apply_session_voice(db, request.user_id, request.session_id)
        audio_path, viseme_data = await run_in_threadpool(text_to_speech, response_text)

        audio_filename = None
        if audio_path:
            audio_filename = os.path.basename(audio_path)

        return {
            "user_id": request.user_id,
            "session_id": request.session_id,
            "response": response_text,
            "audio_filename": audio_filename,
            "visemes": viseme_data,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

#Query text to speach direct disabled Reasoning
@app.post("/query_tts_direct")
async def query_tts_direct(request: QueryRequest):
    """
    Returns a JSON with the filtered text response, audio filename, and viseme data.
    """
    key = f"{request.user_id}:{request.session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        response_text = await run_rag_agent(request.query, request.user_id, request.session_id)
        # Clean model output to remove think/tool traces and formatting
        response_text = clean_model_output(response_text)

        # Generate audio and visemes
        # Apply per-session voice before generating audio
        with sessions.SessionLocal() as db:
            sessions.apply_session_voice(db, request.user_id, request.session_id)
        audio_path, viseme_data = await run_in_threadpool(text_to_speech, response_text)
        
        audio_filename = None
        if audio_path:
            audio_filename = os.path.basename(audio_path)

        return {
            "user_id": request.user_id,
            "session_id": request.session_id,
            "response": response_text,
            "audio_filename": audio_filename,
            "visemes": viseme_data,
            "status": "success"
        }
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Request cancelled")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        active_tasks.pop(key, None)

# Full Agent
@app.post("/stt_query_tts", response_model=Dict[str, Any])
async def stt_query_tts_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...)
):
    """
    Combined STT, query, and TTS endpoint that returns viseme data and audio filename.
    """
    try:
        # First transcribe the audio
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        # Get the transcribed text
        query_text = stt_result["text"]
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        # Process the query using the RAG agent
        response_text = await run_rag_agent(query_text, user_id, session_id)

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
            "user_id": user_id,
            "session_id": session_id,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query with TTS: {str(e)}")

# Full Agent with reasoning not displayed
@app.post("/stt_query_tts_direct", response_model=Dict[str, Any])
async def stt_query_tts_direct_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...)
):
    """
    Combined STT, filtered query, and TTS endpoint that returns viseme data and audio filename.
    """
    key = f"{user_id}:{session_id}"
    active_tasks[key] = asyncio.current_task()
    try:
        # First transcribe the audio
        stt_result = await stt_endpoint(file, user_id, session_id)
        if stt_result["status"] != "success":
            return stt_result

        # Get the transcribed text
        query_text = stt_result["text"]
        if not query_text:
            return {"text": "", "user_id": user_id, "session_id": session_id, "status": "error", "message": "No speech detected"}

        # Process the query using the RAG agent
        response_text = await run_rag_agent(query_text, user_id, session_id)
        response_text = clean_model_output(response_text)

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
            "user_id": user_id,
            "session_id": session_id,
            "status": "success"
        }
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Request cancelled")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio query with TTS: {str(e)}")
    finally:
        active_tasks.pop(key, None)

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
        from teacher_agent.config import OLLAMA_BASE_URL, get_current_model_id
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
        from teacher_agent.config import set_model_id
        set_model_id(request.model)
        return {"success": True, "message": f"Model changed to {request.model}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error setting model: {str(e)}")

@app.post("/set_voice")
async def set_voice_endpoint(request: SetVoiceRequest):
    """Set the voice for TTS"""
    try:
        # Persist per-session voice and update runtime config
        from teacher_agent.config import set_voice
        set_voice(request.voice)
        # Also persist to the database as session-specific setting
        with sessions.SessionLocal() as db:
            settings = db.query(sessions.SessionSettingsDB).filter(
                sessions.SessionSettingsDB.session_id == request.session_id,
                sessions.SessionSettingsDB.user_id == request.user_id,
            ).first()
            now = datetime.utcnow()
            if settings:
                settings.voice = request.voice
                settings.updated_at = now
            else:
                db.add(sessions.SessionSettingsDB(session_id=request.session_id, user_id=request.user_id, voice=request.voice, updated_at=now))
            db.commit()
        return {"success": True, "message": f"Voice changed to {request.voice}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error setting voice: {str(e)}")

# Health and monitoring endpoints
@app.get("/")
async def root():
    """Root endpoint with basic info"""
    return {
        "message": "AI Teacher Assistant API",
        "status": "running",
        "timestamp": datetime.datetime.now().isoformat(),
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    try:
        # You can add more health checks here (database, services, etc.)
        return {
            "status": "healthy",
            "timestamp": datetime.datetime.now().isoformat(),
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
        "build_time": datetime.datetime.now().isoformat(),
        "environment": "production",
        "version": "1.0.0"
    }