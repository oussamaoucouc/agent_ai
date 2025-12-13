"""
Reusable streaming TTS generator for all TTS direct endpoints.
This replaces the complex sentence_buffer approach with simple, reliable sequential generation.
"""

import json
import logging
import asyncio
import re
from fastapi.concurrency import run_in_threadpool
from AI_Agents_Workflows.tts_chunker import split_for_tts
from tts_utils import text_to_speech
from utils import clean_model_output, ensure_response_content


async def stream_tts_response(
    text_stream_generator,
    user_id: str,
    session_id: str,
    apply_voice_callback=None,
    tool_log_regex=None
):
    """
    Generic streaming TTS handler that works for any agent.
    
    Args:
        text_stream_generator: Async generator that yields text chunks
        user_id: User ID for session management
        session_id: Session ID for voice settings
        apply_voice_callback: Optional callback to apply per-session voice
        tool_log_regex: Optional regex to clean tool execution logs
        
    Yields:
        SSE events with text chunks and audio chunks
    """
    full_response = ""
    if tool_log_regex is None:
        tool_log_regex = re.compile(r"[\w_]+\([^)]*\)\s*completed\s+in\s+[\d.]+s\.?", re.IGNORECASE)
    
    try:
        # Apply per-session voice if callback provided
        if apply_voice_callback:
            apply_voice_callback(user_id, session_id)
        
        # Step 1: Stream full text response to UI first
        logging.info(f"TTS Stream: Starting text streaming for session {session_id}")
        
        async for chunk in text_stream_generator:
            if chunk:
                # Clean chunk and add to full response
                cleaned_chunk = tool_log_regex.sub("\n", chunk)
                full_response += chunk
                
                # Stream cleaned text to UI immediately
                if cleaned_chunk.strip():
                    yield f"data: {json.dumps({'content': cleaned_chunk})}\n\n"
                    await asyncio.sleep(0.01)
        
        # Step 2: Clean and split full response into TTS chunks
        cleaned_response = clean_model_output(full_response)
        cleaned_response = ensure_response_content(cleaned_response)
        
        chunks = split_for_tts(cleaned_response)
        logging.info(f"TTS Stream: Split response into {len(chunks)} chunks")
        
        # Step 3: Generate TTS sequentially for each chunk
        sent_count = 0
        skipped_count = 0
        
        for idx, chunk_text in enumerate(chunks):
            try:
                logging.info(f"TTS Stream: Generating audio for chunk {idx+1}/{len(chunks)}")
                
                # Generate TTS with timeout
                audio_path, viseme_data = await asyncio.wait_for(
                    run_in_threadpool(text_to_speech, chunk_text),
                    timeout=30.0
                )
                
                if audio_path:
                    import os
                    audio_filename = os.path.basename(audio_path)
                    
                    # Send audio chunk immediately
                    yield f"data: {json.dumps({
                        'type': 'audio_chunk',
                        'sentence_index': idx,
                        'audio_filename': audio_filename,
                        'visemes': viseme_data,
                        'sentence_text': chunk_text
                    })}\n\n"
                    
                    sent_count += 1
                    logging.info(f"TTS Stream: Sent audio chunk {idx}")
                else:
                    logging.warning(f"TTS Stream: No audio generated for chunk {idx}")
                    skipped_count += 1
                    
            except asyncio.TimeoutError:
                logging.error(f"TTS Stream: Timeout generating audio for chunk {idx} (30s exceeded)")
                skipped_count += 1
            except Exception as e:
                logging.error(f"TTS Stream: Error generating audio for chunk {idx}: {str(e)}")
                skipped_count += 1
        
        logging.info(f"TTS Stream: Done. Sent: {sent_count}, Skipped: {skipped_count}")
        
        # Step 4: Send completion signal
        yield f"data: {json.dumps({
            'done': True,
            'full_response': cleaned_response,
            'total_audio_chunks': sent_count
        })}\n\n"

    except asyncio.CancelledError:
        logging.warning("TTS Stream: Cancelled by user")
        raise
    except Exception as e:
        logging.error(f"TTS Stream: Error in streaming: {str(e)}", exc_info=True)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
