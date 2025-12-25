import os
import requests
import json
from pathlib import Path

# Configuration
MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.json"

BASE_DIR = Path(__file__).parent
MODEL_DIR = BASE_DIR / "models" / "kokoro"

def setup_tts():
    """Download Kokoro ONNX model and voices if they don't exist."""
    print(f"Setting up Kokoro TTS in {MODEL_DIR}...")
    
    # Create directory
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    
    # Define paths
    model_path = MODEL_DIR / "kokoro-v0_19.onnx"
    voices_path = MODEL_DIR / "voices.json"
    
    # Download Model
    if not model_path.exists():
        print(f"Downloading model from {MODEL_URL}...")
        try:
            response = requests.get(MODEL_URL, stream=True)
            response.raise_for_status()
            with open(model_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print("Model downloaded successfully.")
        except Exception as e:
            print(f"Failed to download model: {e}")
            raise
    else:
        print("Model file already exists.")

    # Download Voices
    if not voices_path.exists():
        print(f"Downloading voices from {VOICES_URL}...")
        try:
            response = requests.get(VOICES_URL, stream=True)
            response.raise_for_status()
            with open(voices_path, "wb") as f:
                f.write(response.content)
            print("Voices downloaded successfully.")
        except Exception as e:
            print(f"Failed to download voices: {e}")
            raise
    else:
        print("Voices file already exists.")
        
    print("Kokoro TTS setup complete.")

if __name__ == "__main__":
    setup_tts()
