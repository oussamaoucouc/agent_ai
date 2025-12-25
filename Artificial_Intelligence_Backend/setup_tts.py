import os
import requests
import json
from pathlib import Path

# Configuration for Kokoro v1.0
MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

BASE_DIR = Path(__file__).parent
MODEL_DIR = BASE_DIR / "models" / "kokoro"

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
    
    # English
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
    "zm_yunjian", "zm_yunxia", "zm_yunxi", "zm_yunyang"
]

def setup_tts():
    """Download Kokoro ONNX model and voices if they don't exist."""
    print(f"Setting up Kokoro TTS v1.0 in {MODEL_DIR}...")
    
    # Create directory
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    
    # Define paths
    model_path = MODEL_DIR / "kokoro-v1.0.onnx"
    voices_bin_path = MODEL_DIR / "voices-v1.0.bin"
    voices_json_path = MODEL_DIR / "voices.json"
    
    # Remove old v0.19 files if they exist to avoid confusion
    old_model = MODEL_DIR / "kokoro-v0_19.onnx"
    if old_model.exists():
        print("Removing old v0.19 model...")
        old_model.unlink()

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

    # Download Voices Binary
    if not voices_bin_path.exists():
        print(f"Downloading voices binary from {VOICES_URL}...")
        try:
            response = requests.get(VOICES_URL, stream=True)
            response.raise_for_status()
            with open(voices_bin_path, "wb") as f:
                f.write(response.content)
            print("Voices binary downloaded successfully.")
        except Exception as e:
            print(f"Failed to download voices binary: {e}")
            raise
    else:
        print("Voices binary file already exists.")
        
    # Generate voices.json (Dictionary of keys for frontend)
    # The actual values don't matter for the frontend as long as keys are correct.
    # We'll just map key -> key or simple metadata if needed.
    # But to be safe, we'll make it a dict where key is the voice ID.
    print("Generating voices.json for frontend...")
    voices_data = {v: {"name": v} for v in VOICE_LIST}
    
    with open(voices_json_path, "w") as f:
        json.dump(voices_data, f, indent=2)
    print(f"voices.json generated with {len(VOICE_LIST)} voices.")

    print("Kokoro TTS v1.0 setup complete.")

if __name__ == "__main__":
    setup_tts()
