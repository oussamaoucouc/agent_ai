"""
Sentence-based buffering for streaming TTS to enable faster avatar response.

This module provides a buffer that accumulates streaming text chunks and extracts
complete sentences based on punctuation markers. Complete sentences are immediately
sent to TTS for audio generation, allowing the avatar to start speaking before
the full response is complete.
"""

import re
from typing import List, Tuple


class SentenceBuffer:
    """
    Buffer for extracting complete sentences from streaming text chunks.
    
    Key features:
    - Accumulates text chunks as they arrive from LLM streaming
    - Identifies sentence boundaries using punctuation marks
    - Extracts complete sentences while preserving incomplete text
    - Optimized for continuous audio playback without gaps
    """
    
    # Sentence-ending punctuation marks
    # Match punctuation followed by optional whitespace (for streaming scenarios)
    SENTENCE_ENDINGS = re.compile(r'([.!?;])(\s*)')
    
    # Minimum sentence length to avoid sending tiny fragments to TTS
    MIN_SENTENCE_LENGTH = 10
    
    def __init__(self):
        """Initialize an empty sentence buffer."""
        self.buffer = ""
        self.sentences_extracted = 0
    
    def add_chunk(self, chunk: str) -> List[str]:
        """
        Add a text chunk to the buffer and extract any complete sentences.
        
        Args:
            chunk: New text chunk from streaming response
            
        Returns:
            List of complete sentences ready for TTS generation.
            Empty list if no complete sentences were found.
        """
        if not chunk:
            return []
        
        # Add chunk to buffer
        self.buffer += chunk
        
        # Extract complete sentences
        sentences = self._extract_sentences()
        
        if sentences:
            self.sentences_extracted += len(sentences)
            import logging
            logging.info(f"SentenceBuffer: Extracted {len(sentences)} sentence(s). Total extracted: {self.sentences_extracted}. Remaining buffer: {len(self.buffer)} chars")
        
        return sentences
    
    def _extract_sentences(self) -> List[str]:
        """
        Extract complete sentences from the current buffer.
        
        For streaming scenarios, a sentence is considered complete when:
        1. It ends with punctuation (. ! ? ;)
        2. There's either:
           a) More content after the punctuation (confirming it's not mid-stream)
           b) Whitespace after the punctuation
        3. Meets minimum length requirement
        
        Returns:
            List of complete sentences. Buffer is updated to remove extracted sentences.
        """
        sentences = []
        
        # Find all sentence boundaries
        matches = list(self.SENTENCE_ENDINGS.finditer(self.buffer))
        
        if not matches:
            return sentences
        
        # Only extract sentences where we're SURE they're complete
        # A sentence is complete if there's content after it OR if it ends with space+punctuation
        complete_until = 0
        
        for i, match in enumerate(matches):
            punct_pos = match.end(1)  # Position after the punctuation mark
            space_pos = match.end(2)  # Position after optional whitespace
            
            # Check if there's more content after this punctuation
            has_content_after = space_pos < len(self.buffer)
            
            # Check if punctuation is followed by whitespace
            has_whitespace = match.group(2).strip() == '' and match.group(2) != ''
            
            # Extract this sentence if:
            # 1. There's content after it (next sentence started), OR
            # 2. It has whitespace after punctuation (space confirms end of sentence)
            if has_content_after or has_whitespace:
                # This sentence is complete
                if i < len(matches) - 1:
                    # Not the last match, so definitely complete
                    complete_until = space_pos
                elif has_content_after and not self.buffer[space_pos:].strip():
                    # Last match, but only whitespace after - don't extract yet
                    break
                elif has_whitespace:
                    # Last match with whitespace - safe to extract
                    complete_until = space_pos
        
        if complete_until == 0:
            return sentences
        
        # Extract complete portion
        complete_text = self.buffer[:complete_until].strip()
        self.buffer = self.buffer[complete_until:].strip()
        
        if not complete_text:
            return sentences
        
        # Split into individual sentences
        current_pos = 0
        for match in self.SENTENCE_ENDINGS.finditer(complete_text):
            sentence_end = match.end()
            sentence = complete_text[current_pos:sentence_end].strip()
            if sentence and len(sentence) >= self.MIN_SENTENCE_LENGTH:
                sentences.append(sentence)
            current_pos = sentence_end
        
        return sentences
    
    def flush(self) -> str:
        """
        Flush any remaining text in the buffer as a final sentence.
        
        This should be called when the stream is complete to ensure
        any incomplete sentence at the end is also sent to TTS.
        
        Returns:
            Remaining buffer content, or empty string if buffer is empty.
        """
        remaining = self.buffer.strip()
        self.buffer = ""
        
        # Return remaining text only if it's substantial enough
        if remaining and len(remaining) >= self.MIN_SENTENCE_LENGTH:
            return remaining
        return ""
    
    def reset(self):
        """Reset the buffer and counters."""
        self.buffer = ""
        self.sentences_extracted = 0
    
    @property
    def has_content(self) -> bool:
        """Check if buffer has any content."""
        return bool(self.buffer.strip())
    
    @property
    def buffer_length(self) -> int:
        """Get current buffer length."""
        return len(self.buffer)


def split_into_sentences_simple(text: str) -> List[str]:
    """
    Simple sentence splitter for non-streaming scenarios.
    
    Args:
        text: Complete text to split into sentences
        
    Returns:
        List of sentences
    """
    buffer = SentenceBuffer()
    buffer.add_chunk(text)
    sentences = []
    
    # Extract any complete sentences
    complete = buffer._extract_sentences()
    sentences.extend(complete)
    
    # Add final remaining text
    final = buffer.flush()
    if final:
        sentences.append(final)
    
    return sentences
