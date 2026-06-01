from fastapi import APIRouter, Depends, Query, status
from pymongo.asynchronous.collection import AsyncCollection
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.mongo import get_reports_collection
from app.core.redis_client import get_redis
from app.models.user import User
from app.schemas.report import (
    ReportCreate,
    ReportDismiss,
    ReportListResponse,
    ReportResolve,
    ReportResponse,
    ReportStatus,
)
from app.services.report import ReportService

router = APIRouter(prefix="/reports", tags=["🛡️ Moderation & Reports"])


@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a report",
)
async def create_report(
    payload: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    reports_collection: AsyncCollection = Depends(get_reports_collection),
) -> ReportResponse:
    return await ReportService.create_report(
        reporter=current_user,
        payload=payload,
        db=db,
        reports_collection=reports_collection,
    )


@router.get(
    "",
    response_model=ReportListResponse,
    status_code=status.HTTP_200_OK,
    summary="List reports",
)
async def list_reports(
    status: ReportStatus | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    reports_collection: AsyncCollection = Depends(get_reports_collection),
) -> ReportListResponse:
    return await ReportService.list_reports(
        moderator=current_user,
        status=status,
        cursor=cursor,
        limit=limit,
        reports_collection=reports_collection,
    )


@router.post(
    "/{report_id}/take",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Take a report for review",
)
async def take_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    reports_collection: AsyncCollection = Depends(get_reports_collection),
) -> ReportResponse:
    return await ReportService.take_report(
        report_id=report_id,
        moderator=current_user,
        reports_collection=reports_collection,
    )


@router.post(
    "/{report_id}/resolve",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve a report",
)
async def resolve_report(
    report_id: str,
    payload: ReportResolve,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    reports_collection: AsyncCollection = Depends(get_reports_collection),
) -> ReportResponse:
    return await ReportService.resolve_report(
        report_id=report_id,
        moderator=current_user,
        payload=payload,
        db=db,
        redis=redis,
        reports_collection=reports_collection,
    )


@router.post(
    "/{report_id}/dismiss",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Dismiss a report",
)
async def dismiss_report(
    report_id: str,
    payload: ReportDismiss,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    reports_collection: AsyncCollection = Depends(get_reports_collection),
) -> ReportResponse:
    return await ReportService.dismiss_report(
        report_id=report_id,
        moderator=current_user,
        payload=payload,
        db=db,
        reports_collection=reports_collection,
    )


@router.get(
    "/user/{user_id}",
    response_model=ReportListResponse,
    status_code=status.HTTP_200_OK,
    summary="View report history for a user",
)
async def get_user_reports(
    user_id: int,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    reports_collection: AsyncCollection = Depends(get_reports_collection),
) -> ReportListResponse:
    return await ReportService.get_user_reports(
        user_id=user_id,
        moderator=current_user,
        cursor=cursor,
        limit=limit,
        db=db,
        reports_collection=reports_collection,
    )
