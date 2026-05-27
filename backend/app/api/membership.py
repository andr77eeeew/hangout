from fastapi import APIRouter, Depends, status
from pymongo.asynchronous.collection import AsyncCollection
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.mongo import get_activities_collection, get_membership_collection
from app.core.storage import get_s3_public_sign_client
from app.models.user import User, UserRole
from app.schemas.common import ErrorResponse
from app.schemas.membership import (
    MembershipListResponse,
    MembershipResponse,
)
from app.services.membership import MembershipService

router = APIRouter(prefix="/activities", tags=["👥 Membership"])
membership_service = MembershipService()


@router.post(
    "/{activity_id}/join",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
    summary="🤝 Join an activity",
    description="""
    Request to join an activity.

    * **Open** activities → auto-approved, `current_members` incremented.
    * **Closed** activities → status `pending`, waiting for creator approval.
    """,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Cannot join own activity / Activity is not active / Activity is full",
        },
        401: {
            "model": ErrorResponse,
            "description": "Token is invalid (Unauthorized)",
        },
        409: {
            "model": ErrorResponse,
            "description": "Already applied to this activity",
        },
    },
)
async def join_activity(
    activity_id: str,
    current_user: User = Depends(get_current_user),
    activities_col: AsyncCollection = Depends(get_activities_collection),
    membership_col: AsyncCollection = Depends(get_membership_collection),
):
    return await membership_service.join_activity(
        user_id=current_user.id,
        activity_id=activity_id,
        activities_col=activities_col,
        membership_col=membership_col,
    )


@router.post(
    "/{activity_id}/leave",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="🚪 Leave an activity",
    description="""
    Leave an activity you are currently a member of.

    *🚨 The creator cannot leave their own activity.*
    """,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Creator cannot leave own activity / Invalid activity id",
        },
        404: {
            "model": ErrorResponse,
            "description": "Activity or active membership not found",
        },
    },
)
async def leave_activity(
    activity_id: str,
    current_user: User = Depends(get_current_user),
    activities_col: AsyncCollection = Depends(get_activities_collection),
    membership_col: AsyncCollection = Depends(get_membership_collection),
):
    await membership_service.leave_activity(
        user_id=current_user.id,
        activity_id=activity_id,
        activities_col=activities_col,
        membership_col=membership_col,
    )


@router.get(
    "/{activity_id}/members",
    response_model=MembershipListResponse,
    status_code=status.HTTP_200_OK,
    summary="📋 List activity members",
    description="""
    Returns the list of members for an activity.

    * **Regular users** see only `approved` members.
    * **Creator / Moderator** see `approved` + `pending` members.
    """,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Invalid activity id",
        },
        404: {
            "model": ErrorResponse,
            "description": "Activity not found",
        },
    },
)
async def list_members(
    activity_id: str,
    current_user: User = Depends(get_current_user),
    activities_col: AsyncCollection = Depends(get_activities_collection),
    membership_col: AsyncCollection = Depends(get_membership_collection),
    db: AsyncSession = Depends(get_db),
    s3_public_sign=Depends(get_s3_public_sign_client),
):
    return await membership_service.list_members(
        activity_id=activity_id,
        current_user_id=current_user.id,
        is_moderator=current_user.user_role == UserRole.moderator,
        activities_col=activities_col,
        membership_col=membership_col,
        db=db,
        s3_public_sign=s3_public_sign,
    )


@router.get(
    "/{activity_id}/members/me",
    response_model=MembershipResponse | None,
    status_code=status.HTTP_200_OK,
    summary="🔍 Get my membership status",
    description="""
    Returns the current user's membership for a specific activity,
    or `null` if the user has no membership record.
    """,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Invalid activity id",
        },
    },
)
async def get_my_membership(
    activity_id: str,
    current_user: User = Depends(get_current_user),
    membership_col: AsyncCollection = Depends(get_membership_collection),
):
    return await membership_service.get_my_membership(
        user_id=current_user.id,
        activity_id=activity_id,
        membership_col=membership_col,
    )


@router.post(
    "/{activity_id}/members/{membership_id}/approve",
    response_model=MembershipResponse,
    status_code=status.HTTP_200_OK,
    summary="✅ Approve a pending member",
    description="""
    Approve a pending membership request.

    *🚨 Only the activity creator or a moderator can approve members.*
    """,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Only pending memberships can be approved / Activity is full",
        },
        403: {
            "model": ErrorResponse,
            "description": "Only the activity creator can manage members",
        },
        404: {
            "model": ErrorResponse,
            "description": "Membership or activity not found",
        },
    },
)
async def approve_member(
    activity_id: str,
    membership_id: str,
    current_user: User = Depends(get_current_user),
    activities_col: AsyncCollection = Depends(get_activities_collection),
    membership_col: AsyncCollection = Depends(get_membership_collection),
):
    return await membership_service.approve_member(
        user_id=current_user.id,
        is_moderator=current_user.user_role == UserRole.moderator,
        membership_id=membership_id,
        activities_col=activities_col,
        membership_col=membership_col,
    )


@router.post(
    "/{activity_id}/members/{membership_id}/reject",
    response_model=MembershipResponse,
    status_code=status.HTTP_200_OK,
    summary="❌ Reject a pending member",
    description="""
    Reject a pending membership request.

    *🚨 Only the activity creator or a moderator can reject members.*
    """,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Only pending memberships can be rejected",
        },
        403: {
            "model": ErrorResponse,
            "description": "Only the activity creator can manage members",
        },
        404: {
            "model": ErrorResponse,
            "description": "Membership or activity not found",
        },
    },
)
async def reject_member(
    activity_id: str,
    membership_id: str,
    current_user: User = Depends(get_current_user),
    activities_col: AsyncCollection = Depends(get_activities_collection),
    membership_col: AsyncCollection = Depends(get_membership_collection),
):
    return await membership_service.reject_member(
        user_id=current_user.id,
        is_moderator=current_user.user_role == UserRole.moderator,
        membership_id=membership_id,
        activities_col=activities_col,
        membership_col=membership_col,
    )


@router.post(
    "/{activity_id}/members/{membership_id}/kick",
    response_model=MembershipResponse,
    status_code=status.HTTP_200_OK,
    summary="🦵 Kick an approved member",
    description="""
    Kick an approved member from the activity.

    *🚨 Only the activity creator or a moderator can kick members.*
    *Cannot kick yourself.*
    """,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Only approved members can be kicked / Cannot kick yourself",
        },
        403: {
            "model": ErrorResponse,
            "description": "Only the activity creator can manage members",
        },
        404: {
            "model": ErrorResponse,
            "description": "Membership or activity not found",
        },
    },
)
async def kick_member(
    activity_id: str,
    membership_id: str,
    current_user: User = Depends(get_current_user),
    activities_col: AsyncCollection = Depends(get_activities_collection),
    membership_col: AsyncCollection = Depends(get_membership_collection),
):
    return await membership_service.kick_member(
        user_id=current_user.id,
        is_moderator=current_user.user_role == UserRole.moderator,
        membership_id=membership_id,
        activities_col=activities_col,
        membership_col=membership_col,
    )
