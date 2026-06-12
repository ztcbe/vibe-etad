from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from db.models.user import User
from app.dependencies import get_current_user
from modules.media.schemas import MediaUploadResponse
from modules.media import service
from common.errors import standard_response

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    purpose: str = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    result = await service.upload(db, user.id, file, purpose)
    return standard_response(data=result)
