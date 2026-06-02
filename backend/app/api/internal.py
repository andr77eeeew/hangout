from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.asynchronous.collection import AsyncCollection
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from botocore.client import BaseClient

from app.core.database import get_db
from app.core.internal_auth import verify_internal_api_key
from app.core.mongo import (
    get_activities_collection,
    get_membership_collection,
    get_reports_collection,
)
from app.core.redis_client import get_redis
from app.core.storage import get_s3_public_sign_client
from app.models.user import User, UserRole
from app.schemas.activity import ActivityCreate, ActivityResponse
from app.schemas.ban import BanUserRequest, UnbanUserRequest
from app.schemas.membership import (
    MemberPreview,
    MembershipListResponse,
    MembershipResponse,
)
from app.schemas.report import (
    ReportDismiss,
    ReportListResponse,
    ReportResolve,
    ReportResponse,
    ReportStatus,
)
from app.schemas.user import TagResponse, UserResponse
from app.services.activity import ActivityService
from app.services.ban import BanService
from app.services.membership import MembershipService
from app.services.report import ReportService
from app.services.tag import TagService

router = APIRouter(
    prefix="/internal",
    tags=["🤖 Internal API for Telegram Bot"],
    dependencies=[Depends(verify_internal_api_key)],
)

activity_service = ActivityService()
membership_service = MembershipService()


async def get_acting_user(user_id: int, db: AsyncSession) -> User:
    stmt = (
        select(User).options(selectinload(User.favorite_tags)).where(User.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or inactive",
        )
    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is banned",
        )
    return user


# --- Activities ---


@router.get(
    "/users/{user_id}/activities",
    response_model=list[ActivityResponse],
    status_code=status.HTTP_200_OK,
)
async def get_user_created_activities(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    collection: AsyncCollection = Depends(get_activities_collection),
    s3_public_sign: BaseClient = Depends(get_s3_public_sign_client),
) -> list[ActivityResponse]:
    await get_acting_user(user_id, db)
    docs = (
        await collection.find({"creator_id": user_id})
        .sort("_id", -1)
        .to_list(length=None)
    )
    items: list[ActivityResponse] = []
    for doc in docs:
        item = await activity_service._to_activity_response(doc, db, s3_public_sign)
        items.append(item)
    return items


@router.get(
    "/users/{user_id}/memberships",
    response_model=list[ActivityResponse],
    status_code=status.HTTP_200_OK,
)
async def get_user_joined_activities(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    membership_col: AsyncCollection = Depends(get_membership_collection),
    activities_col: AsyncCollection = Depends(get_activities_collection),
    s3_public_sign: BaseClient = Depends(get_s3_public_sign_client),
) -> list[ActivityResponse]:
    await get_acting_user(user_id, db)
    memberships = await membership_col.find(
        {"user_id": user_id, "status": "approved"}
    ).to_list(length=None)

    activity_ids = [m["activity_id"] for m in memberships]
    if not activity_ids:
        return []

    docs = (
        await activities_col.find({"_id": {"$in": activity_ids}})
        .sort("_id", -1)
        .to_list(length=None)
    )

    items: list[ActivityResponse] = []
    for doc in docs:
        item = await activity_service._to_activity_response(doc, db, s3_public_sign)
        items.append(item)
    return items


@router.get(
    "/activities/{activity_id}",
    response_model=ActivityResponse,
    status_code=status.HTTP_200_OK,
)
async def get_internal_activity(
    activity_id: str,
    db: AsyncSession = Depends(get_db),
    collection: AsyncCollection = Depends(get_activities_collection),
    s3_public_sign: BaseClient = Depends(get_s3_public_sign_client),
) -> ActivityResponse:
    return await activity_service.get_activity(
        activity_id=activity_id,
        collection=collection,
        db=db,
        s3_public_sign=s3_public_sign,
    )


@router.post(
    "/users/{user_id}/activities",
    response_model=ActivityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_activity_on_behalf(
    user_id: int,
    activity_data: ActivityCreate,
    db: AsyncSession = Depends(get_db),
    collection: AsyncCollection = Depends(get_activities_collection),
    membership_col: AsyncCollection = Depends(get_membership_collection),
    s3_public_sign: BaseClient = Depends(get_s3_public_sign_client),
) -> ActivityResponse:
    acting_user = await get_acting_user(user_id, db)
    return await activity_service.create_activity(
        activity_data=activity_data,
        creator_id=acting_user.id,
        collection=collection,
        membership_col=membership_col,
        db=db,
        s3_public_sign=s3_public_sign,
    )


# --- Membership ---


@router.post(
    "/users/{user_id}/activities/{activity_id}/join",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def join_activity_on_behalf(
    user_id: int,
    activity_id: str,
    db: AsyncSession = Depends(get_db),
    activities_col: AsyncCollection = Depends(get_activities_collection),
    membership_col: AsyncCollection = Depends(get_membership_collection),
) -> MembershipResponse:
    acting_user = await get_acting_user(user_id, db)
    return await membership_service.join_activity(
        user_id=acting_user.id,
        activity_id=activity_id,
        activities_col=activities_col,
        membership_col=membership_col,
    )


@router.get(
    "/users/{user_id}/activities/{activity_id}/pending-members",
    response_model=MembershipListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_pending_members_on_behalf(
    user_id: int,
    activity_id: str,
    db: AsyncSession = Depends(get_db),
    activities_col: AsyncCollection = Depends(get_activities_collection),
    membership_col: AsyncCollection = Depends(get_membership_collection),
    s3_public_sign: BaseClient = Depends(get_s3_public_sign_client),
) -> MembershipListResponse:
    acting_user = await get_acting_user(user_id, db)

    if not ObjectId.is_valid(activity_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid activity id",
        )

    activity = await activities_col.find_one({"_id": ObjectId(activity_id)})
    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )

    is_mod = acting_user.user_role == UserRole.moderator
    if activity["creator_id"] != acting_user.id and not is_mod:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the activity creator or a moderator can manage members",
        )

    cursor = membership_col.find(
        {
            "activity_id": ObjectId(activity_id),
            "status": "pending",
        }
    )
    memberships = await cursor.to_list(length=None)

    user_ids = {m["user_id"] for m in memberships}
    users_map = {}
    if user_ids:
        result = await db.execute(
            select(User).where(
                User.id.in_(user_ids),
                User.is_active.is_(True),
            )
        )
        users = result.scalars().all()
        users_map = {u.id: u for u in users}

    items: list[MembershipResponse] = []
    for m in memberships:
        u = users_map.get(m["user_id"])
        preview = None
        if u:
            from app.core.image_utils import build_image_url

            preview = MemberPreview(
                id=u.id,
                username=u.username,
                avatar_url=build_image_url(u.avatar, s3_public_sign)
                if u.avatar
                else None,
            )
        items.append(
            MembershipResponse(
                **m,
                user_preview=preview,
            )
        )
    return MembershipListResponse(items=items, total=len(items))


@router.post(
    "/users/{user_id}/memberships/{membership_id}/approve",
    response_model=MembershipResponse,
    status_code=status.HTTP_200_OK,
)
async def approve_membership_on_behalf(
    user_id: int,
    membership_id: str,
    db: AsyncSession = Depends(get_db),
    activities_col: AsyncCollection = Depends(get_activities_collection),
    membership_col: AsyncCollection = Depends(get_membership_collection),
) -> MembershipResponse:
    acting_user = await get_acting_user(user_id, db)
    return await membership_service.approve_member(
        user_id=acting_user.id,
        is_moderator=acting_user.user_role == UserRole.moderator,
        membership_id=membership_id,
        activities_col=activities_col,
        membership_col=membership_col,
    )


@router.post(
    "/users/{user_id}/memberships/{membership_id}/reject",
    response_model=MembershipResponse,
    status_code=status.HTTP_200_OK,
)
async def reject_membership_on_behalf(
    user_id: int,
    membership_id: str,
    db: AsyncSession = Depends(get_db),
    activities_col: AsyncCollection = Depends(get_activities_collection),
    membership_col: AsyncCollection = Depends(get_membership_collection),
) -> MembershipResponse:
    acting_user = await get_acting_user(user_id, db)
    return await membership_service.reject_member(
        user_id=acting_user.id,
        is_moderator=acting_user.user_role == UserRole.moderator,
        membership_id=membership_id,
        activities_col=activities_col,
        membership_col=membership_col,
    )


@router.post(
    "/users/{user_id}/memberships/{membership_id}/kick",
    response_model=MembershipResponse,
    status_code=status.HTTP_200_OK,
)
async def kick_membership_on_behalf(
    user_id: int,
    membership_id: str,
    db: AsyncSession = Depends(get_db),
    activities_col: AsyncCollection = Depends(get_activities_collection),
    membership_col: AsyncCollection = Depends(get_membership_collection),
) -> MembershipResponse:
    acting_user = await get_acting_user(user_id, db)
    return await membership_service.kick_member(
        user_id=acting_user.id,
        is_moderator=acting_user.user_role == UserRole.moderator,
        membership_id=membership_id,
        activities_col=activities_col,
        membership_col=membership_col,
    )


# --- Tags ---


@router.get(
    "/users/{user_id}/tags/favorites",
    response_model=list[TagResponse],
    status_code=status.HTTP_200_OK,
)
async def get_user_favorite_tags(
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[TagResponse]:
    acting_user = await get_acting_user(user_id, db)
    return [TagResponse.model_validate(tag) for tag in acting_user.favorite_tags]


@router.post(
    "/users/{user_id}/tags/{tag_name}/favorite",
    status_code=status.HTTP_200_OK,
)
async def add_favorite_tag(
    user_id: int,
    tag_name: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str | dict[str, str | int]]:
    acting_user = await get_acting_user(user_id, db)
    return await TagService.add_favorite_tag(
        tag_name=tag_name,
        db=db,
        current_user=acting_user,
    )


@router.delete(
    "/users/{user_id}/tags/{tag_name}/favorite",
    status_code=status.HTTP_200_OK,
)
async def remove_favorite_tag(
    user_id: int,
    tag_name: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str | dict[str, str | int]]:
    acting_user = await get_acting_user(user_id, db)
    return await TagService.remove_favorite_tag(
        tag_name=tag_name,
        db=db,
        current_user=acting_user,
    )


# --- Moderation ---


@router.get(
    "/moderation/reports",
    response_model=ReportListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_reports_internal(
    moderator_id: int,
    status: ReportStatus | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    reports_collection: AsyncCollection = Depends(get_reports_collection),
) -> ReportListResponse:
    acting_user = await get_acting_user(moderator_id, db)
    return await ReportService.list_reports(
        moderator=acting_user,
        status=status,
        cursor=cursor,
        limit=limit,
        reports_collection=reports_collection,
    )


@router.post(
    "/moderation/reports/{report_id}/take",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
)
async def take_report_internal(
    report_id: str,
    moderator_id: int,
    db: AsyncSession = Depends(get_db),
    reports_collection: AsyncCollection = Depends(get_reports_collection),
) -> ReportResponse:
    acting_user = await get_acting_user(moderator_id, db)
    return await ReportService.take_report(
        report_id=report_id,
        moderator=acting_user,
        reports_collection=reports_collection,
    )


@router.post(
    "/moderation/reports/{report_id}/resolve",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
)
async def resolve_report_internal(
    report_id: str,
    payload: ReportResolve,
    moderator_id: int,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    reports_collection: AsyncCollection = Depends(get_reports_collection),
) -> ReportResponse:
    acting_user = await get_acting_user(moderator_id, db)
    return await ReportService.resolve_report(
        report_id=report_id,
        moderator=acting_user,
        payload=payload,
        db=db,
        redis=redis,
        reports_collection=reports_collection,
    )


@router.post(
    "/moderation/reports/{report_id}/dismiss",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
)
async def dismiss_report_internal(
    report_id: str,
    payload: ReportDismiss,
    moderator_id: int,
    db: AsyncSession = Depends(get_db),
    reports_collection: AsyncCollection = Depends(get_reports_collection),
) -> ReportResponse:
    acting_user = await get_acting_user(moderator_id, db)
    return await ReportService.dismiss_report(
        report_id=report_id,
        moderator=acting_user,
        payload=payload,
        db=db,
        reports_collection=reports_collection,
    )


@router.post(
    "/moderation/users/{user_id}/ban",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
async def ban_user_internal(
    user_id: int,
    payload: BanUserRequest,
    moderator_id: int,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> UserResponse:
    acting_user = await get_acting_user(moderator_id, db)
    return await BanService.ban_user(
        user_id=user_id,
        moderator=acting_user,
        reason=payload.reason,
        db=db,
        redis=redis,
    )


@router.post(
    "/moderation/users/{user_id}/unban",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
async def unban_user_internal(
    user_id: int,
    payload: UnbanUserRequest,
    moderator_id: int,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    acting_user = await get_acting_user(moderator_id, db)
    return await BanService.unban_user(
        user_id=user_id,
        moderator=acting_user,
        reason=payload.reason,
        db=db,
    )


@router.get(
    "/moderation/reports/{report_id}",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
)
async def get_report_internal(
    report_id: str,
    moderator_id: int,
    db: AsyncSession = Depends(get_db),
    reports_collection: AsyncCollection = Depends(get_reports_collection),
) -> ReportResponse:
    acting_user = await get_acting_user(moderator_id, db)
    if acting_user.user_role != UserRole.moderator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    if not ObjectId.is_valid(report_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid report id",
        )
    report = await reports_collection.find_one({"_id": ObjectId(report_id)})
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
    return ReportResponse(**report)
