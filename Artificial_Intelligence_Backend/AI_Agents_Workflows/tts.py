"""
Text-to-Speech functionality using Kokoro TTS, with integrated viseme generation.
"""
import os
import sys
import tempfile
import subprocess
import functools
import shutil
import json
import re
import hashlib
import time
from pathlib import Path

# Assuming config.py has this, otherwise define it
try:
    from .config import TTS_CACHE_DIR, TTS_CACHE_KEEP_RECENT, TTS_CACHE_MAX_AGE_HOURS
except ImportError:
    TTS_CACHE_DIR = Path(__file__).parent.parent / "cache" / "tts"
    TTS_CACHE_KEEP_RECENT = 50
    TTS_CACHE_MAX_AGE_HOURS = 24

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

# --- Initialization --- #

@functools.lru_cache(maxsize=1)
def initialize_tts():
    """Initialize the text-to-speech components."""
    tts_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_helper.py")
    os.makedirs(TTS_CACHE_DIR, exist_ok=True)
    return tts_script_path

# --- Cache Cleanup --- #

def cleanup_tts_cache():
    """Remove old or excess cached TTS files.

    - Keeps the most recent TTS_CACHE_KEEP_RECENT items (pairs of wav/json).
    - Removes any items older than TTS_CACHE_MAX_AGE_HOURS.
    - Deletes orphaned files that don't have a matching pair.
    """
    try:
        cache_dir = Path(TTS_CACHE_DIR)
        if not cache_dir.exists():
            return

        # Group by stem to treat wav/json as one item
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

        # Orphan cleanup: json without wav, wav without json
        for json_file in cache_dir.glob('*.json'):
            wav_file = json_file.with_suffix('.wav')
            if not wav_file.exists():
                try:
                    json_file.unlink(missing_ok=True)
                except Exception:
                    pass
        for wav_file in cache_dir.glob('*.wav'):
            json_file = wav_file.with_suffix('.json')
            if not json_file.exists():
                # Be conservative: only remove if older than max age
                try:
                    if now - wav_file.stat().st_mtime > max_age_secs:
                        wav_file.unlink(missing_ok=True)
                except Exception:
                    pass
    except Exception:
        # Never let cleanup errors affect TTS flow
        pass

# --- Core Subprocess Runner --- #

def run_tts_script(text, tts_script_path):
    """
    Runs the TTS helper script to generate speech and visemes.
    Returns paths to temporary audio and viseme files.
    """
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio_file:
        audio_file_path = temp_audio_file.name

    try:
        command = [sys.executable, tts_script_path, text, audio_file_path]
        # Pass selected voice to subprocess so tts_helper can use it
        try:
            from .config import get_current_voice
            current_voice = get_current_voice()
        except Exception:
            current_voice = "af_sky"
        env = os.environ.copy()
        env["KOKORO_VOICE"] = current_voice
        # Capture raw bytes to avoid UnicodeDecodeError from helper/Rhubarb outputs
        result = subprocess.run(command, check=True, capture_output=True, text=False, env=env)
        
        if result.stderr:
            try:
                print("TTS Helper STDERR:", result.stderr.decode('utf-8', errors='replace'), file=sys.stderr)
            except Exception:
                # If decoding fails, skip printing raw bytes
                pass

        viseme_file_path = Path(audio_file_path).with_suffix('.json')

        if not os.path.exists(audio_file_path) or os.path.getsize(audio_file_path) == 0:
            print(f"Error: Audio file was not created or is empty at {audio_file_path}", file=sys.stderr)
            return None, None

        if not os.path.exists(viseme_file_path):
            print(f"Warning: Viseme file not found at {viseme_file_path}", file=sys.stderr)
            return audio_file_path, None

        return audio_file_path, viseme_file_path

    except subprocess.CalledProcessError as e:
        print(f"Error running tts_helper.py: {e}\nStderr: {e.stderr}", file=sys.stderr)
        if os.path.exists(audio_file_path):
            os.remove(audio_file_path)
        return None, None

# --- Main Public Function --- #

def text_to_speech(text):
    """
    Convert text to speech, generate visemes, and handle caching.
    
    Returns:
        tuple: (path_to_audio_file, viseme_data_dict) or (None, None)
    """
    tts_script_path = initialize_tts()
    if not tts_script_path:
        raise Exception("TTS initialization failed.")

    cleaned_text = clean_text_for_tts(text)
    if not cleaned_text:
        print("Text is empty after cleaning, skipping TTS.", file=sys.stderr)
        return None, None
    
    # Include voice in cache key so voice changes reflect in audio
    try:
        from .config import get_current_voice
        current_voice = get_current_voice()
    except Exception:
        current_voice = "af_sky"
    text_hash = get_text_hash(f"{current_voice}|{cleaned_text}")
    cache_audio_path = os.path.join(TTS_CACHE_DIR, f"{text_hash}.wav")
    cache_viseme_path = os.path.join(TTS_CACHE_DIR, f"{text_hash}.json")
    
    # Check cache for both audio and visemes
    if os.path.exists(cache_audio_path) and os.path.exists(cache_viseme_path):
        print(f"Using cached TTS audio and visemes for text: {cleaned_text[:50]}...", file=sys.stderr)
        with open(cache_viseme_path, 'r') as f:
            viseme_data = json.load(f)
        return cache_audio_path, viseme_data
    
    # If not in cache, generate audio and visemes
    print(f"Generating new TTS audio and visemes for text: {cleaned_text[:50]}...", file=sys.stderr)
    temp_audio_path, temp_viseme_path = run_tts_script(cleaned_text, tts_script_path)
    
    if not temp_audio_path:
        return None, None
        
    # Move generated audio to cache and clean up temp file
    shutil.copy2(temp_audio_path, cache_audio_path)
    print(f"Cached TTS audio at {cache_audio_path}", file=sys.stderr)
    os.remove(temp_audio_path)
    
    viseme_data = None
    if temp_viseme_path:
        # Load viseme data from temp file
        with open(temp_viseme_path, 'r') as f:
            viseme_data = json.load(f)
        # Copy viseme data to cache and clean up temp file
        shutil.copy2(temp_viseme_path, cache_viseme_path)
        print(f"Cached visemes at {cache_viseme_path}", file=sys.stderr)
        os.remove(temp_viseme_path)
    
    # Opportunistic cache cleanup after generating output
    cleanup_tts_cache()

    return cache_audio_path, viseme_data