"""Admin API endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from db.models.user import User
from app.dependencies import get_current_admin
from modules.admin import service
from modules.admin.schemas import AdminStatsResponse, AdminUserListResponse, AdminReportListResponse
from common.errors import standard_response

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
):
    result = await service.list_users(db, page, page_size, status)
    return standard_response(data=result)


@router.get("/reports")
async def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
):
    result = await service.list_reports(db, page, page_size, status)
    return standard_response(data=result)


@router.get("/stats")
async def get_stats(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
):
    result = await service.get_stats(db)
    return standard_response(data=AdminStatsResponse(**result))
