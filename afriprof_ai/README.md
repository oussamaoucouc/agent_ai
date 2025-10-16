# AI Teacher 🧑🏫  
*An interactive educational assistant using RAG, speech recognition, and AI*

---

## 📋 Overview  
This AI teacher leverages **Retrieval-Augmented Generation (RAG)**, speech-to-text (STT), text-to-speech (TTS), and large language models (LLM) to create a voice-enabled learning experience. It supports context-aware teaching through document-based knowledge augmentation.

---

## 🧩 Requirements  
Before starting, install these:
- [Python + `uv`](https://github.com/astral-sh/uv) (dependency manager)
- [Docker](https://www.docker.com/) (for TTS service)
- [Ollama](https://ollama.com/) (for LLM)
- [Vosk STT Models](https://alphacephei.com/vosk/models) (see below)
- [Docker](https://www.docker.com/) (for Postgres db)

---

## 🛠️ Setup Instructions  

### 1. Install Dependencies  
```bash
uv sync
```

### 2. Configure Speech-to-Text (STT)  
URL: [Vosk Model List](https://alphacephei.com/vosk/models)  
Download one of these models and put it in the path `../model/<your-chosen-model>`:
- Large vocabulary (accurate but resource-heavy):  
  `vosk-model-en-us-0.42-gigaspeech` (~3GB)
- Lightweight (good for weaker hardware):  
  `vosk-model-en-us-0.22` (~500MB)

Update `config.py`:  
```python
VOSK_MODEL_PATH = "../model/<your-chosen-model>"
```

### 3. Start Text-to-Speech (TTS)  

```bash
docker run -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-cpu:v0.2.2
```
For GPU
```bash
docker run --gpus all -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-gpu:v0.2.2
```


Change voice in `config.py` based on the following URL: https://doc.voxta.ai/docs/kokoro-tts/ :  
```python
KOKORO_TTS_CONFIG = {
    "model": "kokoro",
    "voice": "af_sky",  # Options: "af_sky" (male), "af_ryuusei" (female)
    "response_format": "wav"
}
```

### 4. Configure LLM (Ollama)  
1. Start Ollama and set context size:  
   ```bash
   ollama run qwen3:1.7b
   /set parameter num_ctx 32768
   /save qwen3:1.7bmax
   /bye
   ```
2. Update `config.py`:  
   ```python
   LLM_MODEL = "qwen3:1.7bmax"
   ```
3. Download Embedding Model:  
   ```bash
   ollama pull nomic-embed-text
   ```

### 5. Configure the postgresql
   ```bash
docker run -d -e POSTGRES_DB=ai -e POSTGRES_USER=ai -e POSTGRES_PASSWORD=ai -e PGDATA=/var/lib/postgresql/data/pgdata -v pgvolume:/var/lib/postgresql/data -p 5532:5432 --name pgvector ankane/pgvector
   ```

### 6. Add PDF Documents for Knowledge Base  
Place PDF files in `data/pdfs/` directory for RAG capabilities.

### 7. Initial Knowledge Base Setup 🧠  
Step 1. For the **first run only**, modify `rag_agent.py` to initialize the vector database:
Step 2. After the initial setup, revert to normal operation:
```python
# In rag_agent.py - AFTER INITIAL RUN 
await knowledge_base.aload(recreate=True, upsert=False) # First run
await knowledge_base.aload(recreate=False, upsert=True) #After collection creation keep the following config
```

---

## ▶️ Run the App  
```bash
uv run main.py
```

---

## 🧪 Configuration Reference  
All settings in `config.py`:  
| Setting            | Description                          | Example Value |
|--------------------|--------------------------------------|---------------|
| `VOSK_MODEL_PATH`  | Path to speech recognition model     | `../model/vosk-model-en-us-0.42-gigaspeech` |
| `KOKORO_TTS_CONFIG`| Voice & output format                | `{"voice": "af_sky", "response_format": "wav"}` |
| `LLM_MODEL`        | Active LLM model name                | `qwen3:1.7bmax` |

---

## ❓ Troubleshooting  
- **STT Errors**: Verify model path exists and is unzipped  
- **TTS Issues**: Check Docker container status with `docker ps`  
- **LLM Problems**: Ensure Ollama is running (`ollama list`)  
- **Context Limits**: Confirm model saved with `/save` after setting `num_ctx`
- **Knowledge Base**: If documents don't appear, verify PDFs in `data/pdfs/` and check `rag_agent.py` configuration
```

### Key Additions:
- 📁 **PDF Document Setup**: Step 5 clarifies where to place training materials
- 🧠 **Vector Database Initialization**: Added step 6 with explicit first-run instructions for `rag_agent.py`
- 🔄 **Two-phase Setup**: Clearly separates initial database creation from ongoing operation
- 🚨 **Warning**: Implicit reminder to revert settings after initial setup
- 📚 **Knowledge Base Troubleshooting**: Added a new troubleshooting item for document issues
