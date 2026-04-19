from pathlib import Path
from uuid import uuid4

from app.core.config import settings


def save_upload(content: bytes, original_filename: str) -> str:
    suffix = Path(original_filename).suffix.lower()
    storage_dir = Path(settings.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}{suffix}"
    path = storage_dir / filename
    path.write_bytes(content)
    return str(path)
