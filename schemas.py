from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class PreuveCreate(BaseModel):
    signalement_id: int
    type: str  # "avant" ou "apres"
    photo_base64: str
    uploaded_by: Optional[int] = None  # si vous voulez lier à un utilisateur

class PreuveOut(BaseModel):
    id: int
    signalement_id: int
    type: str
    photo_base64: str
    created_at: datetime
    uploaded_by: Optional[int] = None

    class Config:
        from_attributes = True