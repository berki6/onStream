import secrets
import string
from sqlalchemy.orm import Session
from src.infrastructure.db import models


def generate_upload_id(length: int = 8) -> str:
    """
    Generate a unique alphanumeric upload_id.

    Uses URL-safe characters, excludes ambiguous ones (0/O, 1/I/l).
    Length defaults to 8 characters (~2.8 trillion possible combinations).
    """
    # Use URL-safe characters, exclude ambiguous ones
    chars = string.ascii_letters + string.digits
    # Remove ambiguous characters: 0/O, 1/I/l
    safe_chars = "".join(c for c in chars if c not in "0O1Il")

    return "".join(secrets.choice(safe_chars) for _ in range(length))


def generate_unique_upload_id(db: Session, length: int = 8) -> str:
    """
    Generate a unique upload_id that doesn't exist in the database.

    Keeps generating until it finds one that's not in use.
    """
    while True:
        upload_id = generate_upload_id(length)
        # Check if this upload_id already exists
        existing = (
            db.query(models.Video).filter(models.Video.upload_id == upload_id).first()
        )
        if not existing:
            return upload_id
