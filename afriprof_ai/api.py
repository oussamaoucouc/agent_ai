"""
API endpoints for the AI Teacher Assistant application (FastAPI app instance).
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, constr
from typing import Optional, Dict, Any
import json
import tempfile
import shutil
import os
import datetime
from pydub import AudioSegment
from teacher_agent.rag_agent import run_rag_agent
from teacher_agent.mcp_agent import run_agent_async as run_mcp_agent
from teacher_agent.tts import text_to_speech
from teacher_agent.stt import initialize_stt
import base64
import uuid
from fastapi.responses import FileResponse
from fastapi.concurrency import run_in_threadpool


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

        # Save the uploaded file to the data/pdfs directory
        pdfs_dir = os.path.join(os.path.dirname(__file__), 'data', 'pdfs')
        os.makedirs(pdfs_dir, exist_ok=True)
        file_path = os.path.join(pdfs_dir, file.filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return {"message": f"Successfully uploaded {file.filename}", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")

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

# MCP LLM QUERY not displayed Reasoning
@app.post("/query_mcp_direct", response_model=QueryResponse)
async def query_mcp_direct(request: QueryRequest):
    try:
        response = await run_mcp_agent(request.query, request.user_id, request.session_id)
        marker = "</think>"
        marker_pos = response.find(marker)
        if marker_pos != -1:
            response = response[marker_pos + len(marker):]
        response = response.strip()

        return QueryResponse(
            user_id=request.user_id,
            session_id=request.session_id,
            response=response
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        # Filter out the thinking process, even if the opening tag is missing.
        marker = "</think>"
        marker_pos = response.find(marker)
        if marker_pos != -1:
            response = response[marker_pos + len(marker):]
        response = response.strip()

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

# MCP Query direct then TTS (filtered reasoning)
@app.post("/query_mcp_tts_direct")
async def query_mcp_tts_direct(request: QueryRequest):
    """
    Returns a JSON with the filtered MCP text response, audio filename, and viseme data.
    """
    try:
        response_text = await run_mcp_agent(request.query, request.user_id, request.session_id)
        # Filter out the thinking process, even if the opening tag is missing.
        marker = "</think>"
        marker_pos = response_text.find(marker)
        if marker_pos != -1:
            response_text = response_text[marker_pos + len(marker):]
        response_text = response_text.strip()

        # Generate audio and visemes
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
        # Filter out the thinking process, even if the opening tag is missing.
        marker = "</think>"
        marker_pos = response_text.find(marker)
        if marker_pos != -1:
            response_text = response_text[marker_pos + len(marker):]
        response_text = response_text.strip()

        # Generate audio and visemes
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
#LLM QUERY not displayed Reasoning
@app.post("/query_direct", response_model=QueryResponse)
async def query_direct(request: QueryRequest):
    try:
        response = await run_rag_agent(request.query, request.user_id, request.session_id)
        # Filter out the thinking process, even if the opening tag is missing.
        marker = "</think>"
        marker_pos = response.find(marker)
        if marker_pos != -1:
            response = response[marker_pos + len(marker):]
        response = response.strip()

        return QueryResponse(
            user_id=request.user_id,
            session_id=request.session_id,
            response=response
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        # 1. Generate audio and visemes. This now returns the cached audio path and viseme data.
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

        # Process the query using the RAG agent with filtering
        response = await run_rag_agent(query_text, user_id, session_id)
        # Filter out the thinking process, even if the opening tag is missing.
        marker = "</think>"
        marker_pos = response.find(marker)
        if marker_pos != -1:
            response = response[marker_pos + len(marker):]
        response = response.strip()

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
    try:
        response_text = await run_rag_agent(request.query, request.user_id, request.session_id)
        # Filter out the thinking process, even if the opening tag is missing.
        marker = "</think>"
        marker_pos = response_text.find(marker)
        if marker_pos != -1:
            response_text = response_text[marker_pos + len(marker):]
        response_text = response_text.strip()

        # Generate audio and visemes
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
        # Filter out the thinking process, even if the opening tag is missing.
        marker = "</think>"
        marker_pos = response_text.find(marker)
        if marker_pos != -1:
            response_text = response_text[marker_pos + len(marker):]
        response_text = response_text.strip()

        # Generate audio and visemes
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

#Downloading audio file
@app.get("/querytts_audio/{filename}")
def querytts_audio(filename: str):
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

    return FileResponse(file_path, media_type="audio/wav", filename=filename)


@app.post("/query_debug", response_model=QueryResponse)
async def query_agent_debug(request: QueryRequest):
    try:
        print(f"DEBUG: Starting query with: {request.query[:50]}...")
        print(f"DEBUG: User ID: {request.user_id}, Session ID: {request.session_id}")
        
        # Test Ollama connection first
        from teacher_agent.config import OLLAMA_BASE_URL, MODEL_ID
        import requests
        
        print(f"DEBUG: Testing Ollama connection to {OLLAMA_BASE_URL}")
        try:
            test_response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": MODEL_ID,
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