import io
import re
import os
import hashlib
import secrets
from pathlib import Path
from typing import Optional, Tuple
from fastapi import HTTPException, Header, Security, status
from PIL import Image, UnidentifiedImageError
from .config import settings
from .logging import logger

# Set strict decompression bomb threshold on Pillow
Image.MAX_IMAGE_PIXELS = settings.max_image_pixels

# Magic Byte Signatures for allowed formats
MAGIC_SIGNATURES = {
    "image/jpeg": [
        b"\xff\xd8\xff\xe0",
        b"\xff\xd8\xff\xe1",
        b"\xff\xd8\xff\xe2",
        b"\xff\xd8\xff\xe3",
        b"\xff\xd8\xff\xe8",
        b"\xff\xd8\xff\xdb",
        b"\xff\xd8\xff\xee",
    ],
    "image/png": [
        b"\x89PNG\r\n\x1a\n"
    ],
    "image/webp": [
        b"RIFF"  # Followed by WEBP at offset 8
    ]
}

def detect_mime_from_bytes(data: bytes) -> Optional[str]:
    """Inspects the leading bytes of the raw payload to ascertain true MIME type."""
    if len(data) < 12:
        return None
    
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    
    return None

def sanitize_filename(filename: Optional[str]) -> str:
    """Strips directory traversal sequences (..) and special characters from user filenames."""
    if not filename:
        return "upload.bin"
    # Take basename only to defeat directory traversal
    base = os.path.basename(filename)
    # Remove all non-alphanumeric characters except dot, dash, underscore
    clean = re.sub(r'[^a-zA-Z0-9._-]', '', base)
    return clean or "upload.bin"

def validate_image_upload(raw_bytes: bytes, field_name: str = "document") -> Image.Image:
    """
    Validates file payload strictly against:
    1. Size boundary (rejects > max_upload_size_bytes)
    2. File signature / Magic bytes (rejects fake file extensions)
    3. Image decode validity (rejects truncated or malformed matrices)
    4. Image dimensions / decompression bomb protection (rejects extreme resolutions)
    """
    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded {field_name} is empty."
        )

    # 1. Size constraint
    if len(raw_bytes) > settings.max_upload_size_bytes:
        logger.warning(f"Upload rejected: {field_name} size ({len(raw_bytes)} bytes) exceeds limit.")
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded {field_name} exceeds maximum allowed size of {settings.max_upload_size_bytes // (1024 * 1024)}MB."
        )

    # 2. File Signature / Magic Bytes
    detected_mime = detect_mime_from_bytes(raw_bytes)
    if not detected_mime or detected_mime not in MAGIC_SIGNATURES:
        logger.warning(f"Upload rejected: {field_name} has invalid or unsupported magic bytes.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format for {field_name}. Only authentic JPEG, PNG, and WebP images are permitted."
        )

    # 3. Decode Validation & Dimension Check
    try:
        buffer = io.BytesIO(raw_bytes)
        img = Image.open(buffer)
        img.verify()
        
        buffer.seek(0)
        img = Image.open(buffer)
        
        width, height = img.size
        pixels = width * height
        if pixels > settings.max_image_pixels:
            logger.warning(f"Upload rejected: {field_name} dimensions ({width}x{height} = {pixels}px) exceed safe limit.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image dimensions ({width}x{height}) exceed maximum allowed limit of {settings.max_image_pixels} pixels."
            )
        
        img.load()
        return img
    except (UnidentifiedImageError, OSError, SyntaxError) as e:
        logger.warning(f"Upload rejected: {field_name} image decode failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Corrupted or invalid image data for {field_name}. Please upload an intact image."
        )

def mask_aadhaar_number(text: Optional[str]) -> Optional[str]:
    """Redacts the first 8 digits of a 12-digit Aadhaar number: XXXX-XXXX-1234."""
    if not text:
        return text
    pattern = re.compile(r'\b(\d{4})[\s-]?(\d{4})[\s-]?(\d{4})\b')
    return pattern.sub(r'XXXX-XXXX-\3', text)

def generate_session_token() -> Tuple[str, str]:
    """
    Generates a cryptographically secure random session token.
    Returns: (raw_token_for_client, sha256_hash_for_database)
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return raw_token, token_hash

def hash_token(raw_token: str) -> str:
    """Computes SHA-256 hash of a raw token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

def verify_officer_token(x_officer_key: Optional[str] = Header(None)) -> str:
    """Enforces authorization for officer review, audit logs, and case queries."""
    if not x_officer_key or x_officer_key != settings.officer_key:
        logger.warning("Unauthorized attempt to access protected officer endpoint.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Officer authorization token missing or invalid."
        )
    return x_officer_key
