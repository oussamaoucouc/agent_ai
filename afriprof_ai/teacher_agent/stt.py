"""
Speech-to-Text functionality using VOSK.
"""
import json
import time
import pyaudio
import functools

from vosk import Model as VoskModel, KaldiRecognizer
import sys
from .config import VOSK_MODEL_PATH

@functools.lru_cache(maxsize=1)
def initialize_stt():
    """Initialize the speech-to-text components if not already initialized
    
    This function is cached using functools.lru_cache to avoid reloading
    the model on subsequent calls, significantly improving performance.
    """
    try:
        print("Loading speech recognition model. This may take a moment...")
        vosk_model = VoskModel(VOSK_MODEL_PATH)
        recognizer = KaldiRecognizer(vosk_model, 16000)
        return vosk_model, recognizer
    except Exception as e:
        raise RuntimeError(f"Error initializing STT: {e}")

def record_audio(recognizer):
    """Record audio and convert to text using VOSK"""
    p_audio = pyaudio.PyAudio()
    stream = p_audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=4096
    )
    
    stream.start_stream()
    text = ""
    start_time = time.time()
    try:
        while (time.time() - start_time) < 30:  # 30 second timeout
            data = stream.read(4096, exception_on_overflow=False)
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "")
                if text:
                    break
    except Exception as e:
        raise RuntimeError(f"Error during recording: {e}")
    finally:
        # Always ensure these cleanup steps happen
        stream.stop_stream()
        stream.close()
        p_audio.terminate()
        placeholder.empty()
    
    return text