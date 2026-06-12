"""Admin module schemas."""
import uuid
from datetime import datetime, date
from pydantic import BaseModel


class AdminUserItem(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str | None
    role: str
    status: str
    date_of_birth: date
    completeness_score: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminUserListResponse(BaseModel):
    items: list[AdminUserItem]
    total: int
    page: int
    page_size: int


class AdminReportItem(BaseModel):
    id: uuid.UUID
    reporter_user_id: uuid.UUID
    reporter_name: str | None
    reported_user_id: uuid.UUID
    reported_name: str | None
    category: str
    description: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminReportListResponse(BaseModel):
    items: list[AdminReportItem]
    total: int
    page: int
    page_size: int


class AdminStatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_matches: int
    open_reports: int
