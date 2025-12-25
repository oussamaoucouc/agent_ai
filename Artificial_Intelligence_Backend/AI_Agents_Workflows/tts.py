"""
Text-to-Speech functionality using Kokoro TTS (ONNX), with integrated viseme generation.
Running in-process for maximum performance.
"""
import os
import sys
import json
import re
import hashlib
import time
import shutil
import subprocess
import soundfile as sf
from pathlib import Path
from kokoro_onnx import Kokoro
from .config import TTS_CACHE_DIR, TTS_CACHE_KEEP_RECENT, TTS_CACHE_MAX_AGE_HOURS, RHUBARB_PATH, get_current_voice

# Correctly locate the models directory relative to this file
# This assumes the structure: Artificial_Intelligence_Backend/models/kokoro
curr_dir = Path(__file__).parent  # AI_Agents_Workflows
backend_dir = curr_dir.parent      # Artificial_Intelligence_Backend
MODEL_DIR = backend_dir / "models" / "kokoro"
MODEL_PATH = MODEL_DIR / "kokoro-v0_19.onnx"
VOICES_PATH = MODEL_DIR / "voices.json"

class KokoroTTS:
    _instance = None
    _model = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if not MODEL_PATH.exists() or not VOICES_PATH.exists():
            print(f"Kokoro model not found at {MODEL_PATH}. Running setup...", file=sys.stderr)
            # Attempt to run setup if missing (fallback)
            try:
                # Try absolute import first (works if /app is in sys.path)
                import setup_tts
                setup_tts.setup_tts()
            except ImportError:
                # Fallback: add parent to path
                try:
                    sys.path.insert(0, str(Path(__file__).parent.parent))
                    import setup_tts
                    setup_tts.setup_tts()
                except Exception as e:
                    print(f"Failed to auto-setup Kokoro: {e}", file=sys.stderr)
                    raise RuntimeError("Kokoro TTS model files missing. Please run setup_tts.py manually.")
            except Exception as e:
                print(f"Failed to auto-setup Kokoro: {e}", file=sys.stderr)
                raise RuntimeError("Kokoro TTS model files missing. Please run setup_tts.py.")
        
        print(f"Loading Kokoro ONNX model from {MODEL_PATH}...", file=sys.stderr)
        self._model = Kokoro(str(MODEL_PATH), str(VOICES_PATH))
        print("Kokoro ONNX model loaded.", file=sys.stderr)

    def generate(self, text, voice="af_sky"):
        """
        Generate audio from text.
        Returns:
            audio (numpy array): raw float32 audio
            sample_rate (int): sample rate (usually 24000)
        """
        if not self._model:
            raise RuntimeError("Kokoro model not initialized")
        
        # Ensure we're using a valid voice ID
        # For simplicity, we pass the voice string directly. kokoro-onnx handles validation or throws.
        # Fallback to af_sky if something goes wrong is handled by the caller or try/except block.
        return self._model.create(text, voice=voice, speed=1.0, lang="en-us")

# --- Helper functions --- #

def get_text_hash(text):
    """Generate a hash for the text to use as a cache key."""
    return hashlib.md5(text.encode()).hexdigest()

def clean_text_for_tts(text):
    """Clean and prepare text for TTS processing."""
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'[*_~`#]', '', text)
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r' +', ' ', text)
    return text

def generate_visemes(audio_path, text):
    """
    Generates viseme data for a given audio file and text using Rhubarb Lip Sync.
    The viseme data is saved to a JSON file with the same name as the audio file.
    """
    if not os.path.exists(RHUBARB_PATH):
        print(f"Rhubarb executable not found at {RHUBARB_PATH}", file=sys.stderr)
        return None

    viseme_output_path = Path(audio_path).with_suffix('.json')

    # Rhubarb requires the dialog text in a file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as temp_dialog_file:
        temp_dialog_file.write(text)
        dialog_file_path = temp_dialog_file.name

    # Ensure the executable has permission to run
    try:
        current_mode = os.stat(RHUBARB_PATH).st_mode
        os.chmod(RHUBARB_PATH, current_mode | 0o111)
    except Exception as e:
        print(f"Warning: Could not set execute permission on {RHUBARB_PATH}: {e}", file=sys.stderr)

    try:
        command = [
            str(RHUBARB_PATH),
            '-f', 'json',
            '--dialogFile', dialog_file_path,
            '-o', str(viseme_output_path),
            str(audio_path)
        ]
        
        # Run Rhubarb
        subprocess.run(command, check=True, capture_output=True, text=True)
        
        if viseme_output_path.exists():
            with open(viseme_output_path, 'r') as f:
                return json.load(f)
        return None

    except subprocess.CalledProcessError as e:
        print(f"Error running Rhubarb: {e}\nStderr: {e.stderr}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"An unexpected error occurred in generate_visemes: {e}", file=sys.stderr)
        return None
    finally:
        if os.path.exists(dialog_file_path):
            os.remove(dialog_file_path)

# --- Cache Cleanup --- #

def cleanup_tts_cache():
    """Remove old or excess cached TTS files."""
    try:
        cache_dir = Path(TTS_CACHE_DIR)
        if not cache_dir.exists():
            return

        # Group by stem
        items = {}
        for p in cache_dir.glob('*'):
            if p.suffix not in {'.wav', '.json'}:
                continue
            items.setdefault(p.stem, []).append(p)

        # Sort items by newest mtime
        sorted_items = sorted(
            items.items(),
            key=lambda kv: max(f.stat().st_mtime for f in kv[1]),
            reverse=True
        )

        now = time.time()
        max_age_secs = TTS_CACHE_MAX_AGE_HOURS * 3600

        # Delete items beyond keep-recent threshold
        for stem, paths in sorted_items[TTS_CACHE_KEEP_RECENT:]:
            for p in paths:
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass

        # Delete items older than max age
        for stem, paths in sorted_items[:TTS_CACHE_KEEP_RECENT]:
            try:
                newest_mtime = max(f.stat().st_mtime for f in paths)
                if now - newest_mtime > max_age_secs:
                    for p in paths:
                        try:
                            p.unlink(missing_ok=True)
                        except Exception:
                            pass
            except Exception:
                continue

    except Exception:
        pass

# --- Main Public Function --- #

def text_to_speech(text):
    """
    Convert text to speech using Kokoro ONNX (in-process).
    
    Returns:
        tuple: (path_to_audio_file, viseme_data_dict) or (None, None)
    """
    cleaned_text = clean_text_for_tts(text)
    if not cleaned_text:
        return None, None
    
    try:
        voice = get_current_voice()
    except Exception:
        voice = "af_sky"

    # Cache key
    text_hash = get_text_hash(f"{voice}|{cleaned_text}")
    cache_audio_path = os.path.join(TTS_CACHE_DIR, f"{text_hash}.wav")
    cache_viseme_path = os.path.join(TTS_CACHE_DIR, f"{text_hash}.json")
    
    # Check cache
    if os.path.exists(cache_audio_path) and os.path.exists(cache_viseme_path):
         try:
            if os.path.getsize(cache_audio_path) > 1000:
                print(f"Using cached TTS: {cleaned_text[:30]}...", file=sys.stderr)
                # Touch files to update mtime
                Path(cache_audio_path).touch()
                with open(cache_viseme_path, 'r') as f:
                    viseme_data = json.load(f)
                return cache_audio_path, viseme_data
         except Exception:
             pass

    # Generate
    print(f"Generating TTS (Kokoro ONNX): {cleaned_text[:30]}...", file=sys.stderr)
    try:
        tts = KokoroTTS.get_instance()
        audio, sample_rate = tts.generate(cleaned_text, voice=voice)
        
        # Save audio
        sf.write(cache_audio_path, audio, sample_rate)
        
        # Generate visemes
        viseme_data = generate_visemes(cache_audio_path, cleaned_text)
        
        # Cleanup
        cleanup_tts_cache()
        
        return cache_audio_path, viseme_data
        
    except Exception as e:
        print(f"TTS Generation Error: {e}", file=sys.stderr)
        return None, None
