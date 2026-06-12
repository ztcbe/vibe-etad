import uuid
from datetime import datetime

from pydantic import BaseModel


class MediaUploadResponse(BaseModel):
    media_id: uuid.UUID
    url: str
    purpose: str

    model_config = {"from_attributes": True}
