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
from pathlib import Path

# Assuming config.py has this, otherwise define it
try:
    from .config import TTS_CACHE_DIR
except ImportError:
    TTS_CACHE_DIR = Path(__file__).parent.parent / "cache" / "tts"

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
        result = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        
        if result.stderr:
            print("TTS Helper STDERR:", result.stderr, file=sys.stderr)

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
    
    text_hash = get_text_hash(cleaned_text)
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
            
    return cache_audio_path, viseme_data