from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ResumeRead(BaseModel):
    id: int
    original_filename: str
    content_type: str
    status: str
    extracted_text: str | None
    analysis: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
