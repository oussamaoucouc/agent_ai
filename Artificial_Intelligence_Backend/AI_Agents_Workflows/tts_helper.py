"""
Helper script for Text-to-Speech functionality.
This script is called as a separate process.
"""
import sys
import os
import tempfile
import requests
import subprocess
from pathlib import Path
import soundfile as sf
import numpy as np

from config import KOKORO_TTS_URL, KOKORO_TTS_CONFIG, KOKORO_TTS_HEADERS, KOKORO_TTS_TIMEOUT, RHUBARB_PATH

# Override voice from environment if provided
VOICE_OVERRIDE = os.getenv("KOKORO_VOICE")
if VOICE_OVERRIDE:
    KOKORO_TTS_CONFIG["voice"] = VOICE_OVERRIDE



def generate_visemes(audio_path, text):
    """
    Generates viseme data for a given audio file and text using Rhubarb Lip Sync.
    The viseme data is saved to a JSON file with the same name as the audio file.
    """
    if not os.path.exists(RHUBARB_PATH):
        print(f"Rhubarb executable not found at {RHUBARB_PATH}", file=sys.stderr)
        return False

    # The output JSON file will have the same name as the audio file, but with a .json extension
    viseme_output_path = Path(audio_path).with_suffix('.json')

    # Rhubarb requires the dialog text in a file
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
            audio_path
        ]
        
        # Using subprocess.run to execute the command
        # Run Rhubarb and capture raw bytes to avoid Unicode decode issues
        result = subprocess.run(command, check=True, capture_output=True, text=False)
        # Best-effort decode for logs; Rhubarb may emit non-UTF8 bytes
        if result.stdout:
            try:
                print(result.stdout.decode('utf-8', errors='replace'), file=sys.stderr)
            except Exception:
                pass
        if result.stderr:
            try:
                print(result.stderr.decode('utf-8', errors='replace'), file=sys.stderr)
            except Exception:
                pass
        print(f"Successfully generated visemes: {viseme_output_path}", file=sys.stderr)
        return True

    except subprocess.CalledProcessError as e:
        print(f"Error running Rhubarb: {e}", file=sys.stderr)
        print(f"Stderr: {e.stderr}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"An unexpected error occurred in generate_visemes: {e}", file=sys.stderr)
        return False
    finally:
        # Clean up the temporary dialog file
        if 'dialog_file_path' in locals() and os.path.exists(dialog_file_path):
            os.remove(dialog_file_path)

def synthesize_speech_kokoro(text, output_path):
    """Synthesize speech using the Kokoro TTS container and generate visemes."""
    try:
        # Create payload using configuration from config.py
        payload = {
            **KOKORO_TTS_CONFIG,
            
            "input": text
        }

        print(f"Sending request to Kokoro TTS: {KOKORO_TTS_URL} with payload: {{'model': 'kokoro', 'input': '{text[:50]}...', 'response_format': 'wav'}}", file=sys.stderr)
        # Set timeout to 120 seconds
        response = requests.post(KOKORO_TTS_URL, json=payload, headers=KOKORO_TTS_HEADERS, stream=True, timeout=KOKORO_TTS_TIMEOUT)

        if response.status_code == 200:
            with open(output_path, 'wb') as f_out:
                for chunk in response.iter_content(chunk_size=8192):
                    f_out.write(chunk)
            print(f"Successfully saved Kokoro TTS audio to {output_path}", file=sys.stderr)

            # --- NEW: Convert audio to Rhubarb-compatible format before generating visemes ---
            try:
                data, samplerate = sf.read(output_path)
                # If stereo, convert to mono by averaging channels
                if data.ndim > 1 and data.shape[1] == 2:
                    data = np.mean(data, axis=1)
                # Write back as 16-bit PCM WAV
                sf.write(output_path, data, samplerate, subtype='PCM_16')
                print(f"Successfully converted {output_path} to 16-bit mono WAV.", file=sys.stderr)

                # --- Generate visemes after audio is converted ---
                print("Starting viseme generation...", file=sys.stderr)
                visemes_generated = generate_visemes(output_path, text)
                if not visemes_generated:
                    print("Warning: Viseme generation failed, but audio was created successfully.", file=sys.stderr)

            except Exception as e:
                print(f"Warning: Audio conversion failed: {e}. Viseme generation will be skipped.", file=sys.stderr)
            
            return True # Audio generation was successful in any case
        else:
            # Log the error response text for debugging
            error_text = response.text
            print(f"Error from Kokoro TTS: Status code {response.status_code}, Response: {error_text}", file=sys.stderr)
            return False
    except requests.exceptions.Timeout:
        print(f"Error: Request to Kokoro TTS timed out.", file=sys.stderr)
        return False
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Kokoro TTS at {KOKORO_TTS_URL}: {str(e)}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Unexpected error during Kokoro TTS synthesis: {str(e)}", file=sys.stderr)
        return False

def synthesize_speech(text, output_path):
    """Main synthesis function, always uses Kokoro."""
    print(f"Synthesizing speech using Kokoro TTS", file=sys.stderr)
    return synthesize_speech_kokoro(text, output_path)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python tts_helper.py <text> <output_path>", file=sys.stderr)
        sys.exit(1)
    
    text_to_synthesize = sys.argv[1]
    audio_output_path = sys.argv[2]
    
    if not synthesize_speech_kokoro(text_to_synthesize, audio_output_path):
        sys.exit(1)