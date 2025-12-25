import os
import requests
import json
from pathlib import Path

# Configuration for Kokoro v1.0
MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

# Configuration for Piper Arabic TTS
PIPER_ARABIC_MODEL_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx"
PIPER_ARABIC_CONFIG_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx.json"

BASE_DIR = Path(__file__).parent
MODEL_DIR = BASE_DIR / "models" / "kokoro"
PIPER_MODEL_DIR = BASE_DIR / "models" / "piper"

# Full list of voices supported by Kokoro v1.0
# The frontend needs this list to populate the dropdown.
# The backend uses the binary file for actual generation.
VOICE_LIST = [
    # American Female
    "af", "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jadzia", 
    "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", 
    "af_sky", "af_v0bella", "af_v0irulan", "af_v0nicole", "af_v0", 
    "af_v0sarah", "af_v0sky",
    
    # American Male
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", 
    "am_onyx", "am_puck", "am_santa", "am_v0adam", "am_v0gurney", 
    "am_v0michael",
    
    # British Female
    "bf_alice", "bf_emma", "bf_lily", "bf_v0emma", "bf_v0isabella",
    
    # British Male
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis", "bm_v0george", 
    "bm_v0lewis",
    
    # Spanish
    "ef_dora", "em_alex", "em_santa",
    
    # French
    "ff_siwis",
    
    # Hindi
    "hf_alpha", "hf_beta", "hm_omega", "hm_psi",
    
    # Italian
    "if_sara", "im_nicola",
    
    # Japanese
    "jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo",
    
    # Brazilian Portuguese
    "pf_dora", "pm_alex", "pm_santa",
    
    # Chinese
    "zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi", 
    "zm_yunjian", "zm_yunxia", "zm_yunxi", "zm_yunyang",
    
    # Arabic (Piper TTS)
    "ar_kareem",
]

def setup_tts():
    """Download Kokoro ONNX model, Piper Arabic model, and voices if they don't exist."""
    print(f"Setting up Kokoro TTS v1.0 in {MODEL_DIR}...")
    
    # Create directories
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    PIPER_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    
    # Define paths
    model_path = MODEL_DIR / "kokoro-v1.0.onnx"
    voices_bin_path = MODEL_DIR / "voices-v1.0.bin"
    voices_json_path = MODEL_DIR / "voices.json"
    
    # Piper Arabic paths
    piper_arabic_model = PIPER_MODEL_DIR / "ar_JO-kareem-medium.onnx"
    piper_arabic_config = PIPER_MODEL_DIR / "ar_JO-kareem-medium.onnx.json"
    
    # Remove old v0.19 files if they exist to avoid confusion
    old_model = MODEL_DIR / "kokoro-v0_19.onnx"
    if old_model.exists():
        print("Removing old v0.19 model...")
        old_model.unlink()

    # Download Kokoro Model
    if not model_path.exists():
        print(f"Downloading Kokoro model from {MODEL_URL}...")
        try:
            response = requests.get(MODEL_URL, stream=True)
            response.raise_for_status()
            with open(model_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print("Kokoro model downloaded successfully.")
        except Exception as e:
            print(f"Failed to download Kokoro model: {e}")
            raise
    else:
        print("Kokoro model file already exists.")

    # Download Kokoro Voices Binary
    if not voices_bin_path.exists():
        print(f"Downloading Kokoro voices binary from {VOICES_URL}...")
        try:
            response = requests.get(VOICES_URL, stream=True)
            response.raise_for_status()
            with open(voices_bin_path, "wb") as f:
                f.write(response.content)
            print("Kokoro voices binary downloaded successfully.")
        except Exception as e:
            print(f"Failed to download Kokoro voices binary: {e}")
            raise
    else:
        print("Kokoro voices binary file already exists.")
    
    # Download Piper Arabic Model
    if not piper_arabic_model.exists():
        print(f"Downloading Piper Arabic model from {PIPER_ARABIC_MODEL_URL}...")
        try:
            response = requests.get(PIPER_ARABIC_MODEL_URL, stream=True)
            response.raise_for_status()
            with open(piper_arabic_model, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print("Piper Arabic model downloaded successfully.")
        except Exception as e:
            print(f"Failed to download Piper Arabic model: {e}")
            raise
    else:
        print("Piper Arabic model already exists.")
    
    # Download Piper Arabic Config
    if not piper_arabic_config.exists():
        print(f"Downloading Piper Arabic config from {PIPER_ARABIC_CONFIG_URL}...")
        try:
            response = requests.get(PIPER_ARABIC_CONFIG_URL)
            response.raise_for_status()
            with open(piper_arabic_config, "wb") as f:
                f.write(response.content)
            print("Piper Arabic config downloaded successfully.")
        except Exception as e:
            print(f"Failed to download Piper Arabic config: {e}")
            raise
    else:
        print("Piper Arabic config already exists.")
        
    # Generate voices.json (Dictionary of keys for frontend)
    print("Generating voices.json for frontend...")
    voices_data = {v: {"name": v} for v in VOICE_LIST}
    
    with open(voices_json_path, "w") as f:
        json.dump(voices_data, f, indent=2)
    print(f"voices.json generated with {len(VOICE_LIST)} voices.")

    print("TTS setup complete (Kokoro + Piper Arabic).")

if __name__ == "__main__":
    setup_tts()

