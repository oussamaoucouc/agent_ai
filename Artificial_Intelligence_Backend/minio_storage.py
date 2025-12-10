"""
MinIO Object Storage wrapper for RAG document management.

This module provides a clean interface to MinIO S3-compatible object storage,
handling document uploads, downloads, presigned URLs, and bucket management.
"""

import os
import tempfile
import hashlib
import logging
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from datetime import datetime,timedelta

from minio import Minio
from minio.error import S3Error
from urllib3.exceptions import MaxRetryError

logger = logging.getLogger(__name__)


# MinIO Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
MINIO_SECURE = os.getenv("MINIO_SECURE", "False").lower() == "true"


def get_minio_client() -> Minio:
    """
    Initialize and return MinIO client.
    
    Returns:
        Minio: Configured MinIO client instance
        
    Raises:
        Exception: If connection to MinIO fails
    """
    try:
        client = Minio(
            endpoint=MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
        # Test connection
        client.list_buckets()
        logger.info(f"Successfully connected to MinIO at {MINIO_ENDPOINT}")
        return client
    except MaxRetryError:
        logger.error(f"Failed to connect to MinIO at {MINIO_ENDPOINT}. Is the container running?")
        raise Exception(f"MinIO connection failed. Check if MinIO container is running at {MINIO_ENDPOINT}")
    except Exception as e:
        logger.error(f"MinIO connection error: {e}")
        raise


def get_user_bucket_name(user_id: str) -> str:
    """Generate bucket name for user."""
    # Bucket names must be lowercase, alphanumeric + hyphens
    return f"user-{user_id.lower().replace('_', '-')}"


def ensure_bucket_exists(client: Minio, bucket_name: str) -> None:
    """
    Create bucket if it doesn't exist.
    
    Args:
        client: MinIO client instance
        bucket_name: Name of bucket to create
    """
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            logger.info(f"Created bucket: {bucket_name}")
        else:
            logger.debug(f"Bucket already exists: {bucket_name}")
    except S3Error as e:
        logger.error(f"Error ensuring bucket exists: {e}")
        raise


def upload_document(
    user_id: str,
    file_path: str,
    filename: str,
    file_type: str,
    metadata: Optional[Dict[str, str]] = None
) -> Tuple[str, str, str]:
    """
    Upload document to MinIO.
    
    Args:
        user_id: User ID who owns the document
        file_path: Local path to file to upload
        filename: Filename to use in MinIO
        file_type: Type of file (pdf, docx, txt, csv)
        metadata: Optional additional metadata
        
    Returns:
        Tuple of (bucket_name, object_key, etag)
        
    Raises:
        FileNotFoundError: If file_path doesn't exist
        Exception: If upload fails
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    client = get_minio_client()
    bucket_name = get_user_bucket_name(user_id)
    ensure_bucket_exists(client, bucket_name)
    
    # Object key: {file_type}/{filename}
    object_key = f"{file_type}/{filename}"
    
    # Prepare metadata
    file_metadata = {
        "file_type": file_type,
        "upload_date": datetime.utcnow().isoformat(),
        "user_id": user_id
    }
    if metadata:
        file_metadata.update(metadata)
    
    # Determine content type
    content_type = _get_content_type(filename)
    
    try:
        # Upload file
        result = client.fput_object(
            bucket_name=bucket_name,
            object_name=object_key,
            file_path=file_path,
            content_type=content_type,
            metadata=file_metadata
        )
        
        etag = result.etag
        logger.info(f"Uploaded {filename} to {bucket_name}/{object_key} (etag: {etag})")
        return bucket_name, object_key, etag
        
    except S3Error as e:
        logger.error(f"Failed to upload {filename}: {e}")
        raise Exception(f"Upload failed: {str(e)}")


def get_presigned_download_url(
    user_id: str,
    filename: str,
    file_type: str,
    expiry: int = 3600
) -> str:
    """
    Generate presigned URL for direct download from MinIO.
    
    Args:
        user_id: User ID who owns the document
        filename: Filename in MinIO
        file_type: Type of file (pdf, docx, txt, csv)
        expiry: URL expiry time in seconds (default: 1 hour)
        
    Returns:
        Presigned URL string
        
    Raises:
        Exception: If URL generation fails
    """
    client = get_minio_client()
    bucket_name = get_user_bucket_name(user_id)
    object_key = f"{file_type}/{filename}"
    
    try:
        url = client.presigned_get_object(
            bucket_name=bucket_name,
            object_name=object_key,
            expires=timedelta(seconds=expiry)
        )
        logger.debug(f"Generated presigned URL for {bucket_name}/{object_key}")
        return url
    except S3Error as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        raise Exception(f"Failed to generate download URL: {str(e)}")


def download_to_temp(user_id: str, filename: str, file_type: str) -> str:
    """
    Download document from MinIO to temporary file (for RAG processing).
    Uses original filename to preserve it in RAG vector DB.
    
    Args:
        user_id: User ID who owns the document
        filename: Filename in MinIO
        file_type: Type of file (pdf, docx, txt, csv)
        
    Returns:
        Path to temporary file with original filename
        
    Raises:
        Exception: If download fails
        
    Note:
        Creates files in user-specific temp directory to preserve original names.
    """
    client = get_minio_client()
    bucket_name = get_user_bucket_name(user_id)
    object_key = f"{file_type}/{filename}"
    
    try:
        # Create user-specific temp directory
        temp_dir = tempfile.gettempdir()
        user_temp_dir = os.path.join(temp_dir, f"rag_{user_id}")
        os.makedirs(user_temp_dir, exist_ok=True)
        
        # Use original filename in temp directory to preserve name in RAG DB
        temp_path = os.path.join(user_temp_dir, filename)
        
        # Download object to temp file
        client.fget_object(
            bucket_name=bucket_name,
            object_name=object_key,
            file_path=temp_path
        )
        
        logger.debug(f"Downloaded {bucket_name}/{object_key} to {temp_path}")
        return temp_path
        
    except S3Error as e:
        logger.error(f"Failed to download {filename}: {e}")
        # Clean up temp file if created
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        raise Exception(f"Download failed: {str(e)}")


def delete_document(user_id: str, filename: str, file_type: str) -> bool:
    """
    Delete document from MinIO.
    
    Args:
        user_id: User ID who owns the document
        filename: Filename in MinIO
        file_type: Type of file (pdf, docx, txt, csv)
        
    Returns:
        True if deleted successfully
        
    Raises:
        Exception: If deletion fails
    """
    client = get_minio_client()
    bucket_name = get_user_bucket_name(user_id)
    object_key = f"{file_type}/{filename}"
    
    try:
        client.remove_object(bucket_name=bucket_name, object_name=object_key)
        logger.info(f"Deleted {bucket_name}/{object_key}")
        return True
    except S3Error as e:
        # If object doesn't exist, consider it a success
        if "NoSuchKey" in str(e):
            logger.warning(f"Object not found (already deleted?): {bucket_name}/{object_key}")
            return True
        logger.error(f"Failed to delete {filename}: {e}")
        raise Exception(f"Deletion failed: {str(e)}")


def list_user_documents(user_id: str, file_type: Optional[str] = None) -> List[Dict[str, str]]:
    """
    List all documents for a user.
    
    Args:
        user_id: User ID
        file_type: Optional filter by file type (pdf, docx, txt, csv)
        
    Returns:
        List of document info dicts with keys: object_key, filename, file_type, size, etag
    """
    client = get_minio_client()
    bucket_name = get_user_bucket_name(user_id)
    
    try:
        # Check if bucket exists
        if not client.bucket_exists(bucket_name):
            logger.debug(f"Bucket {bucket_name} doesn't exist, returning empty list")
            return []
        
        # List objects
        prefix = f"{file_type}/" if file_type else ""
        objects = client.list_objects(bucket_name, prefix=prefix, recursive=True)
        
        documents = []
        for obj in objects:
            doc_file_type, filename = obj.object_name.split('/', 1)
            documents.append({
                "object_key": obj.object_name,
                "filename": filename,
                "file_type": doc_file_type,
                "size": obj.size,
                "etag": obj.etag
            })
        
        logger.debug(f"Listed {len(documents)} documents for user {user_id}")
        return documents
        
    except S3Error as e:
        logger.error(f"Failed to list documents: {e}")
        return []


def document_exists(user_id: str, filename: str, file_type: str) -> bool:
    """
    Check if document exists in MinIO.
    
    Args:
        user_id: User ID who owns the document
        filename: Filename in MinIO
        file_type: Type of file (pdf, docx, txt, csv)
        
    Returns:
        True if document exists
    """
    client = get_minio_client()
    bucket_name = get_user_bucket_name(user_id)
    object_key = f"{file_type}/{filename}"
    
    try:
        client.stat_object(bucket_name=bucket_name, object_name=object_key)
        return True
    except S3Error:
        return False


def delete_user_bucket(user_id: str) -> bool:
    """
    Delete all documents and bucket for a user.
   
    Args:
        user_id: User ID
        
    Returns:
        True if deleted successfully
    """
    client = get_minio_client()
    bucket_name = get_user_bucket_name(user_id)
    
    try:
        if not client.bucket_exists(bucket_name):
            logger.debug(f"Bucket {bucket_name} doesn't exist, nothing to delete")
            return True
        
        # Delete all objects in bucket
        objects = client.list_objects(bucket_name, recursive=True)
        for obj in objects:
            client.remove_object(bucket_name, obj.object_name)
            logger.debug(f"Deleted object: {obj.object_name}")
        
        # Delete bucket
        client.remove_bucket(bucket_name)
        logger.info(f"Deleted bucket: {bucket_name}")
        return True
        
    except S3Error as e:
        logger.error(f"Failed to delete user bucket: {e}")
        raise Exception(f"Failed to delete user data: {str(e)}")


def _get_content_type(filename: str) -> str:
    """Determine content type from filename extension."""
    ext = Path(filename).suffix.lower()
    content_types = {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.doc': 'application/msword',
        '.txt': 'text/plain',
        '.md': 'text/markdown',
        '.csv': 'text/csv'
    }
    return content_types.get(ext, 'application/octet-stream')


# Utility function for calculating SHA256 hash
def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA256 hash of file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(8192), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()
