from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None
    is_active: bool
    email_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}
