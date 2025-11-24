"""
Media utilities for handling multimodal inputs (images, audio, video).
Provides file persistence, Agno media object creation, and cleanup functions.
"""
from agno.media import Image, Audio, Video
from pathlib import Path
from fastapi import UploadFile
from typing import List, Optional, Tuple, Dict
import os
import shutil
import aiofiles
from datetime import datetime
import mimetypes
import logging

logger = logging.getLogger(__name__)

# Base media directory - persisted across restarts
MEDIA_BASE_DIR = Path("/data/media")


def get_user_media_dir(user_id: str) -> Path:
    """Get base media directory for a user."""
    return MEDIA_BASE_DIR / str(user_id)


def get_session_media_dir(user_id: str, session_id: str) -> Path:
    """Get media directory for a specific session."""
    return get_user_media_dir(user_id) / str(session_id)


async def save_media_file(
    file: UploadFile,
    user_id: str,
    session_id: str,
    media_type: str  # 'image', 'audio', 'video'
) -> Dict[str, any]:
    """
    Save an uploaded media file to disk and return metadata.
    
    Args:
        file: The uploaded file
        user_id: User ID
        session_id: Session ID
        media_type: Type of media ('image', 'audio', 'video')
    
    Returns:
        dict with: filename, file_path, file_size, mime_type, url
    """
    # Create directory structure
    session_dir = get_session_media_dir(user_id, session_id)
    media_type_dir = session_dir / media_type
    media_type_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    original_name = file.filename or "unnamed"
    # Sanitize filename
    safe_original = "".join(c for c in original_name if c.isalnum() or c in "._- ")
    safe_name = f"{timestamp}_{safe_original}"
    file_path = media_type_dir / safe_name
    
    # Save file to disk
    try:
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
        logger.info(f"Saved {media_type} file: {file_path}")
    except Exception as e:
        logger.error(f"Error saving media file: {e}")
        raise
    
    # Get file metadata
    file_size = os.path.getsize(file_path)
    mime_type = mimetypes.guess_type(str(file_path))[0] or file.content_type or "application/octet-stream"
    
    # Generate URL for frontend access
    # Format: /media/{user_id}/{session_id}/{type}/{filename}
    url = f"/media/{user_id}/{session_id}/{media_type}/{safe_name}"
    
    return {
        "filename": safe_name,
        "file_path": str(file_path),
        "file_size": file_size,
        "mime_type": mime_type,
        "url": url
    }


async def save_and_process_media(
    user_id: str,
    session_id: str,
    images: List[UploadFile] = [],
    audio: List[UploadFile] = [],
    videos: List[UploadFile] = []
) -> Tuple[Optional[List[Image]], Optional[List[Audio]], Optional[List[Video]], Dict[str, List[str]]]:
    """
    Save media files to disk, store metadata in DB, and create Agno media objects.
    
    Args:
        user_id: User ID
        session_id: Session ID
        images: List of image files
        audio: List of audio files
        videos: List of video files
    
    Returns:
        Tuple of:
        - List of Agno Image objects (or None)
        - List of Agno Audio objects (or None)
        - List of Agno Video objects (or None)
        - Dict of media URLs for frontend {'images': [...], 'audio': [...], 'videos': [...]}
    """
    try:
        from sessions import SessionLocal
        from sqlalchemy import text
    except ImportError:
        logger.error("Failed to import database dependencies")
        raise
    
    agno_images = []
    agno_audio = []
    agno_videos = []
    media_urls = {'images': [], 'audio': [], 'videos': []}
    
    db = SessionLocal()
    
    try:
        # Process images
        for img_file in images:
            try:
                metadata = await save_media_file(img_file, user_id, session_id, 'image')
                
                # Store in database
                db.execute(text("""
                    INSERT INTO session_media (user_id, session_id, media_type, filename, file_path, file_size, mime_type)
                    VALUES (:user_id, :session_id, :media_type, :filename, :file_path, :file_size, :mime_type)
                """), {
                    'user_id': user_id,
                    'session_id': session_id,
                    'media_type': 'image',
                    'filename': metadata['filename'],
                    'file_path': metadata['file_path'],
                    'file_size': metadata['file_size'],
                    'mime_type': metadata['mime_type']
                })
                db.commit()
                
                # Create Agno Image object
                agno_images.append(Image(filepath=metadata['file_path']))
                media_urls['images'].append(metadata['url'])
                logger.info(f"Processed image: {metadata['filename']}")
            except Exception as e:
                logger.error(f"Error processing image file: {e}")
                db.rollback()
                # Continue with other files
        
        # Process audio
        for audio_file in audio:
            try:
                metadata = await save_media_file(audio_file, user_id, session_id, 'audio')
                
                # Store in database
                db.execute(text("""
                    INSERT INTO session_media (user_id, session_id, media_type, filename, file_path, file_size, mime_type)
                    VALUES (:user_id, :session_id, :media_type, :filename, :file_path, :file_size, :mime_type)
                """), {
                    'user_id': user_id,
                    'session_id': session_id,
                    'media_type': 'audio',
                    'filename': metadata['filename'],
                    'file_path': metadata['file_path'],
                    'file_size': metadata['file_size'],
                    'mime_type': metadata['mime_type']
                })
                db.commit()
                
                # Read audio file content for Agno
                with open(metadata['file_path'], 'rb') as f:
                    audio_content = f.read()
                
                # Determine format from extension
                file_ext = Path(metadata['filename']).suffix.lower().lstrip('.')
                agno_audio.append(Audio(content=audio_content, format=file_ext or 'wav'))
                media_urls['audio'].append(metadata['url'])
                logger.info(f"Processed audio: {metadata['filename']}")
            except Exception as e:
                logger.error(f"Error processing audio file: {e}")
                db.rollback()
        
        # Process videos
        for video_file in videos:
            try:
                metadata = await save_media_file(video_file, user_id, session_id, 'video')
                
                # Store in database
                db.execute(text("""
                    INSERT INTO session_media (user_id, session_id, media_type, filename, file_path, file_size, mime_type)
                    VALUES (:user_id, :session_id, :media_type, :filename, :file_path, :file_size, :mime_type)
                """), {
                    'user_id': user_id,
                    'session_id': session_id,
                    'media_type': 'video',
                    'filename': metadata['filename'],
                    'file_path': metadata['file_path'],
                    'file_size': metadata['file_size'],
                    'mime_type': metadata['mime_type']
                })
                db.commit()
                
                # Create Agno Video object
                agno_videos.append(Video(filepath=metadata['file_path']))
                media_urls['videos'].append(metadata['url'])
                logger.info(f"Processed video: {metadata['filename']}")
            except Exception as e:
                logger.error(f"Error processing video file: {e}")
                db.rollback()
        
    finally:
        db.close()
    
    return (
        agno_images if agno_images else None,
        agno_audio if agno_audio else None,
        agno_videos if agno_videos else None,
        media_urls
    )


async def cleanup_session_media(user_id: str, session_id: str) -> None:
    """
    Delete all media files for a specific session.
    Called when user deletes a session.
    
    Args:
        user_id: User ID
        session_id: Session ID
    """
    session_media_dir = get_session_media_dir(user_id, session_id)
    if session_media_dir.exists():
        try:
            shutil.rmtree(session_media_dir)
            logger.info(f"Deleted session media directory: {session_media_dir}")
        except Exception as e:
            logger.error(f"Error deleting session media directory: {e}")
            raise


async def cleanup_user_media(user_id: str) -> None:
    """
    Delete all media files for a user (all sessions).
    Called when admin deletes a user.
    
    Args:
        user_id: User ID
    """
    user_media_dir = get_user_media_dir(user_id)
    if user_media_dir.exists():
        try:
            shutil.rmtree(user_media_dir)
            logger.info(f"Deleted user media directory: {user_media_dir}")
        except Exception as e:
            logger.error(f"Error deleting user media directory: {e}")
            raise
