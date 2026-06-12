import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.media import MediaAsset
from db.models.profile import UserProfile
from modules.media.schemas import MediaUploadResponse
from common.errors import ValidationError, AppError
from common.enums import MediaPurpose

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png"}
MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5MB


async def upload(db: AsyncSession, user_id: uuid.UUID, file: UploadFile, purpose: str) -> MediaUploadResponse:
    # Validate purpose
    try:
        media_purpose = MediaPurpose(purpose)
    except ValueError:
        raise ValidationError(message=f"Invalid purpose: {purpose}. Must be 'avatar' or 'chat_attachment'")

    # Validate MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise ValidationError(message=f"Invalid file type: {file.content_type}. Only JPEG and PNG are allowed")

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise ValidationError(message="File too large. Maximum size is 5MB")

    # Save file
    ext = "jpg" if file.content_type == "image/jpeg" else "png"
    filename = f"{uuid.uuid4()}.{ext}"
    upload_dir = Path("./uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / filename
    file_path.write_bytes(content)

    # Create media_assets record
    media = MediaAsset(
        user_id=user_id,
        url=f"/media/{filename}",
        purpose=media_purpose,
        mime_type=file.content_type,
        size_bytes=len(content),
    )
    db.add(media)

    # If avatar, update user_profiles.avatar_url
    if media_purpose == MediaPurpose.AVATAR:
        result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
        profile = result.scalar_one_or_none()
        if profile:
            profile.avatar_url = media.url

    await db.commit()
    await db.refresh(media)

    return MediaUploadResponse(
        media_id=media.id,
        url=media.url,
        purpose=media.purpose.value,
    )
