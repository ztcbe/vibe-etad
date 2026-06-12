"""Admin service — user/report listing, stats."""
import uuid
from datetime import date

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models.user import User
from db.models.profile import UserProfile
from db.models.matching import Match
from db.models.moderation import Report
from common.enums import UserStatus, MatchStatus, ReportStatus


async def list_users(db: AsyncSession, page: int = 1, page_size: int = 20, status: str | None = None) -> dict:
    """Get paginated user list with profile info."""
    stmt = select(User, UserProfile).join(UserProfile, UserProfile.user_id == User.id, isouter=True)
    if status:
        stmt = stmt.where(User.status == status)

    # Count
    count_stmt = select(func.count()).select_from(User)
    if status:
        count_stmt = count_stmt.where(User.status == status)
    total = (await db.execute(count_stmt)).scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
    stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for user, profile in rows:
        items.append({
            "id": user.id,
            "username": user.username,
            "display_name": profile.display_name if profile else None,
            "role": user.role.value,
            "status": user.status.value,
            "date_of_birth": user.date_of_birth,
            "completeness_score": profile.completeness_score if profile else 0,
            "created_at": user.created_at,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def list_reports(db: AsyncSession, page: int = 1, page_size: int = 20, status: str | None = None) -> dict:
    """Get paginated report list."""
    stmt = select(Report)
    if status:
        stmt = stmt.where(Report.status == status)

    count_stmt = select(func.count()).select_from(Report)
    if status:
        count_stmt = count_stmt.where(Report.status == status)
    total = (await db.execute(count_stmt)).scalar() or 0

    offset = (page - 1) * page_size
    stmt = stmt.order_by(Report.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    reports = result.scalars().all()

    items = []
    for r in reports:
        reporter = await db.get(User, r.reporter_user_id)
        reported = await db.get(User, r.reported_user_id)
        reporter_name = None
        reported_name = None
        if reporter:
            rp = (await db.execute(select(UserProfile).where(UserProfile.user_id == reporter.id))).scalar_one_or_none()
            reporter_name = rp.display_name if rp else None
        if reported:
            de = (await db.execute(select(UserProfile).where(UserProfile.user_id == reported.id))).scalar_one_or_none()
            reported_name = de.display_name if de else None

        items.append({
            "id": r.id,
            "reporter_user_id": r.reporter_user_id,
            "reporter_name": reporter_name,
            "reported_user_id": r.reported_user_id,
            "reported_name": reported_name,
            "category": r.category.value,
            "description": r.description,
            "status": r.status.value,
            "created_at": r.created_at,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_stats(db: AsyncSession) -> dict:
    """Get dashboard statistics."""
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    active_users = (await db.execute(
        select(func.count()).select_from(User).where(User.status == UserStatus.ACTIVE)
    )).scalar() or 0
    total_matches = (await db.execute(
        select(func.count()).select_from(Match).where(Match.status == MatchStatus.ACTIVE)
    )).scalar() or 0
    open_reports = (await db.execute(
        select(func.count()).select_from(Report).where(Report.status == ReportStatus.OPEN)
    )).scalar() or 0

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_matches": total_matches,
        "open_reports": open_reports,
    }
