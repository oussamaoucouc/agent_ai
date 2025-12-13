"""
Simple text chunking for TTS - splits on paragraph boundaries for reliable streaming.
Optimized for conversational AI and avatar lip sync.
"""

import re
import logging
from typing import List


def split_for_tts(text: str, max_chunk_size: int = 500, min_chunk_size: int = 10) -> List[str]:
    """
    Split text into TTS-friendly chunks based on paragraph boundaries.
    
    This is a simpler, more reliable approach than sentence buffering:
    - Splits on double newlines (paragraph boundaries)
    - Further splits large paragraphs at sentence boundaries
    - Each chunk is 10-500 characters (optimal for voice synthesis)
    
    Args:
        text: Full text to split
        max_chunk_size: Maximum characters per chunk (default 500)
        min_chunk_size: Minimum characters per chunk (default 10)
        
    Returns:
        List of text chunks ready for TTS generation
    """
    if not text or not text.strip():
        return []
    
    # Split on double newlines (paragraph boundaries)
    paragraphs = re.split(r'\n\n+', text.strip())
    
    chunks = []
    for para in paragraphs:
        para = para.strip()
        if not para or len(para) < min_chunk_size:
            continue
            
        if len(para) <= max_chunk_size:
            # Paragraph is small enough, use as-is
            chunks.append(para)
        else:
            # Large paragraph - split at sentence boundaries
            # Match sentence endings: . ! ? followed by space or newline
            sentences = re.split(r'([.!?]+(?:\s+|\n))', para)
            
            current_chunk = ""
            for i in range(0, len(sentences), 2):
                sentence = sentences[i]
                # Add punctuation if it exists
                if i + 1 < len(sentences):
                    sentence += sentences[i + 1]
                
                # Check if adding this sentence would exceed max size
                if current_chunk and len(current_chunk + sentence) > max_chunk_size:
                    # Save current chunk and start new one
                    if len(current_chunk.strip()) >= min_chunk_size:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence
                else:
                    current_chunk += sentence
            
            # Don't forget the last chunk
            if current_chunk and len(current_chunk.strip()) >= min_chunk_size:
                chunks.append(current_chunk.strip())
    
    logging.info(f"TTS Chunking: Split {len(text)} chars into {len(chunks)} chunks")
    return chunks
