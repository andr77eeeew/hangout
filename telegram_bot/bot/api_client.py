import httpx
from datetime import datetime, timedelta
from bot.config import settings
from bot.schemas import (
    CreatorPreview,
    ActivitySummary,
    ActivityDetails,
    MemberPreview,
    MembershipSummary,
    TagSummary,
    ReportDetails,
    ReportPage,
    ActivityCreatePayload,
    ReportResolvePayload,
    ReportDismissPayload,
)


class APIError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message: str = message
        self.status_code: int | None = status_code
        self.detail: str | None = detail


class ValidationError(APIError):
    def __init__(
        self,
        message: str,
        detail: str | None = None,
        errors: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message, status_code=400, detail=detail)
        self.errors: dict[str, str] = errors or {}


class UnauthorizedError(APIError):
    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message, status_code=401, detail=detail)


class PermissionDeniedError(APIError):
    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message, status_code=403, detail=detail)


class NotFoundError(APIError):
    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message, status_code=404, detail=detail)


class ConflictError(APIError):
    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message, status_code=409, detail=detail)


def _handle_http_error(err: httpx.HTTPStatusError) -> None:
    status_code: int = err.response.status_code
    detail: str | None = None
    errors: dict[str, str] = {}
    try:
        data = err.response.json()
        if isinstance(data, dict):
            raw_detail = data.get("detail")
            if isinstance(raw_detail, list):
                for item in raw_detail:
                    if isinstance(item, dict):
                        loc: str = ".".join(str(x) for x in item.get("loc", []))
                        msg: str = item.get("msg", "Validation error")
                        errors[loc] = msg
                detail = "Validation failed"
            elif isinstance(raw_detail, str):
                detail = raw_detail
    except Exception:
        pass

    message: str = f"HTTP error {status_code}"
    if detail:
        message = detail

    if status_code == 400:
        raise ValidationError(message=message, detail=detail, errors=errors)
    elif status_code == 401:
        raise UnauthorizedError(message=message, detail=detail)
    elif status_code == 403:
        raise PermissionDeniedError(message=message, detail=detail)
    elif status_code == 404:
        raise NotFoundError(message=message, detail=detail)
    elif status_code == 409:
        raise ConflictError(message=message, detail=detail)
    else:
        raise APIError(message=message, status_code=status_code, detail=detail)


def _map_activity(
    data: dict[str, int | str | bool | list[str] | dict[str, int | str | None] | None],
) -> ActivitySummary:
    starts_at_val = data.get("date")
    if isinstance(starts_at_val, str):
        starts_at = datetime.fromisoformat(starts_at_val.replace("Z", "+00:00"))
    elif isinstance(starts_at_val, datetime):
        starts_at = starts_at_val
    else:
        starts_at = datetime.now()

    ends_at: datetime = starts_at + timedelta(hours=2)

    creator_data = data.get("creator")
    creator: CreatorPreview | None = None
    creator_id: int = 0
    if isinstance(creator_data, dict):
        creator = CreatorPreview(
            id=int(creator_data.get("id") or 0),
            username=str(creator_data.get("username") or ""),
            avatar_url=creator_data.get("avatar_url"),
        )
        creator_id = creator.id

    tags_list: list[str] = []
    raw_tags = data.get("tags")
    if isinstance(raw_tags, list):
        tags_list = [str(t) for t in raw_tags]

    return ActivitySummary(
        id=str(data.get("id") or data.get("_id") or ""),
        creator_id=creator_id,
        title=str(data.get("title") or ""),
        description=str(data.get("description") or ""),
        starts_at=starts_at,
        ends_at=ends_at,
        location=data.get("location"),
        online_link=data.get("online_link"),
        format=str(data.get("format") or "online"),
        category=str(data.get("category") or ""),
        tags=tags_list,
        current_members=int(data.get("current_members") or 1),
        max_members=int(data.get("max_members"))
        if data.get("max_members") is not None
        else None,
        creator=creator,
        status=str(data.get("status") or "active"),
    )


def _map_activity_details(
    data: dict[str, int | str | bool | list[str] | dict[str, int | str | None] | None],
) -> ActivityDetails:
    summary = _map_activity(data)
    return ActivityDetails(**summary.model_dump())


def _map_membership(
    data: dict[str, int | str | dict[str, int | str | None] | None],
) -> MembershipSummary:
    joined_at_val = data.get("joined_at")
    if isinstance(joined_at_val, str):
        joined_at = datetime.fromisoformat(joined_at_val.replace("Z", "+00:00"))
    elif isinstance(joined_at_val, datetime):
        joined_at = joined_at_val
    else:
        joined_at = datetime.now()

    user_preview_data = data.get("user_preview")
    user_preview: MemberPreview | None = None
    if isinstance(user_preview_data, dict):
        user_preview = MemberPreview(
            id=int(user_preview_data.get("id") or 0),
            username=str(user_preview_data.get("username") or ""),
            avatar_url=user_preview_data.get("avatar_url"),
        )

    return MembershipSummary(
        id=str(data.get("id") or data.get("_id") or ""),
        activity_id=str(data.get("activity_id") or ""),
        user_id=int(data.get("user_id") or 0),
        status=str(data.get("status") or "pending"),
        joined_at=joined_at,
        user_preview=user_preview,
    )


def _map_tag(data: dict[str, int | str]) -> TagSummary:
    name: str = str(data.get("name") or "")
    slug: str = name.lower().replace(" ", "-")
    return TagSummary(
        id=int(data.get("id") or 0),
        name=name,
        slug=slug,
    )


def _map_report(data: dict[str, int | str | None]) -> ReportDetails:
    def parse_dt(val: int | str | None) -> datetime | None:
        if not val:
            return None
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        return None

    created_at = parse_dt(data.get("created_at")) or datetime.now()
    updated_at = parse_dt(data.get("updated_at")) or datetime.now()

    return ReportDetails(
        id=str(data.get("id") or data.get("_id") or ""),
        reporter_id=int(data.get("reporter_id") or 0),
        reported_user_id=int(data.get("reported_user_id") or 0),
        activity_id=data.get("activity_id"),
        chat_message_id=data.get("chat_message_id"),
        reason=str(data.get("reason") or ""),
        status=str(data.get("status") or "open"),
        moderator_id=int(data.get("moderator_id"))
        if data.get("moderator_id") is not None
        else None,
        moderator_notes=data.get("moderator_notes"),
        resolution=data.get("resolution"),
        created_at=created_at,
        updated_at=updated_at,
        taken_at=parse_dt(data.get("taken_at")),
        resolved_at=parse_dt(data.get("resolved_at")),
    )


class APIClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url: str = base_url or settings.BACKEND_INTERNAL_URL
        self.api_key: str = api_key or settings.INTERNAL_API_KEY.get_secret_value()
        self.headers: dict[str, str] = {
            "X-Internal-Key": self.api_key,
            "Content-Type": "application/json",
        }

    # --- Existing Helper Methods ---

    async def generate_link_code(self, telegram_user_id: int) -> str:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.post(
                    "/internal/telegram/link-code",
                    json={"telegram_user_id": str(telegram_user_id)},
                )
                response.raise_for_status()
                data: dict[str, str] = response.json()
                return data["code"]
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def get_user_by_telegram_id(
        self, telegram_user_id: int
    ) -> dict[str, int | str | None] | None:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.get(
                    f"/internal/telegram/users/{telegram_user_id}"
                )
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                data: dict[str, int | str | None] = response.json()
                return data
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def get_notification_preferences(
        self, telegram_user_id: int
    ) -> dict[str, int | bool]:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.get(
                    f"/internal/telegram/users/{telegram_user_id}/notification-preferences"
                )
                response.raise_for_status()
                data: dict[str, int | bool] = response.json()
                return data
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def update_notification_preferences(
        self, telegram_user_id: int, patch: dict[str, bool | None]
    ) -> dict[str, int | bool]:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.patch(
                    f"/internal/telegram/users/{telegram_user_id}/notification-preferences",
                    json=patch,
                )
                response.raise_for_status()
                data: dict[str, int | bool] = response.json()
                return data
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def unlink(self, telegram_user_id: int) -> bool:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.delete(
                    f"/internal/telegram/users/{telegram_user_id}/link"
                )
                response.raise_for_status()
                return True
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    # --- 18 Stage 6C Sprint 2 Endpoint Methods ---

    async def get_user_created_activities(self, user_id: int) -> list[ActivitySummary]:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.get(f"/internal/users/{user_id}/activities")
                response.raise_for_status()
                data: list[
                    dict[
                        str,
                        int
                        | str
                        | bool
                        | list[str]
                        | dict[str, int | str | None]
                        | None,
                    ]
                ] = response.json()
                return [_map_activity(item) for item in data]
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def get_user_joined_activities(self, user_id: int) -> list[ActivitySummary]:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.get(f"/internal/users/{user_id}/memberships")
                response.raise_for_status()
                data: list[
                    dict[
                        str,
                        int
                        | str
                        | bool
                        | list[str]
                        | dict[str, int | str | None]
                        | None,
                    ]
                ] = response.json()
                return [_map_activity(item) for item in data]
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def get_internal_activity(self, activity_id: str) -> ActivityDetails:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.get(f"/internal/activities/{activity_id}")
                response.raise_for_status()
                data: dict[
                    str,
                    int | str | bool | list[str] | dict[str, int | str | None] | None,
                ] = response.json()
                return _map_activity_details(data)
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def create_activity_on_behalf(
        self, user_id: int, activity_data: ActivityCreatePayload
    ) -> ActivityDetails:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.post(
                    f"/internal/users/{user_id}/activities",
                    json=activity_data.model_dump(mode="json"),
                )
                response.raise_for_status()
                data: dict[
                    str,
                    int | str | bool | list[str] | dict[str, int | str | None] | None,
                ] = response.json()
                return _map_activity_details(data)
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def create_activity(
        self, user_id: int, payload: ActivityCreatePayload
    ) -> ActivityDetails:
        return await self.create_activity_on_behalf(
            user_id=user_id, activity_data=payload
        )

    async def join_activity_on_behalf(
        self, user_id: int, activity_id: str
    ) -> MembershipSummary:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.post(
                    f"/internal/users/{user_id}/activities/{activity_id}/join"
                )
                response.raise_for_status()
                data: dict[str, int | str | dict[str, int | str | None] | None] = (
                    response.json()
                )
                return _map_membership(data)
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def get_pending_members_on_behalf(
        self, user_id: int, activity_id: str
    ) -> list[MembershipSummary]:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.get(
                    f"/internal/users/{user_id}/activities/{activity_id}/pending-members"
                )
                response.raise_for_status()
                data: dict[
                    str,
                    int
                    | list[dict[str, int | str | dict[str, int | str | None] | None]],
                ] = response.json()
                items = data.get("items") or []
                return [_map_membership(item) for item in items]
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def approve_membership_on_behalf(
        self, user_id: int, membership_id: str
    ) -> MembershipSummary:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.post(
                    f"/internal/users/{user_id}/memberships/{membership_id}/approve"
                )
                response.raise_for_status()
                data: dict[str, int | str | dict[str, int | str | None] | None] = (
                    response.json()
                )
                return _map_membership(data)
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def reject_membership_on_behalf(
        self, user_id: int, membership_id: str
    ) -> MembershipSummary:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.post(
                    f"/internal/users/{user_id}/memberships/{membership_id}/reject"
                )
                response.raise_for_status()
                data: dict[str, int | str | dict[str, int | str | None] | None] = (
                    response.json()
                )
                return _map_membership(data)
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def kick_membership_on_behalf(
        self, user_id: int, membership_id: str
    ) -> MembershipSummary:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.post(
                    f"/internal/users/{user_id}/memberships/{membership_id}/kick"
                )
                response.raise_for_status()
                data: dict[str, int | str | dict[str, int | str | None] | None] = (
                    response.json()
                )
                return _map_membership(data)
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def join_activity(self, user_id: int, activity_id: str) -> MembershipSummary:
        return await self.join_activity_on_behalf(
            user_id=user_id, activity_id=activity_id
        )

    async def get_my_created_activities(self, user_id: int) -> list[ActivitySummary]:
        return await self.get_user_created_activities(user_id=user_id)

    async def get_pending_members(
        self, user_id: int, activity_id: str
    ) -> list[MembershipSummary]:
        return await self.get_pending_members_on_behalf(
            user_id=user_id, activity_id=activity_id
        )

    async def approve_member(
        self, user_id: int, membership_id: str
    ) -> MembershipSummary:
        return await self.approve_membership_on_behalf(
            user_id=user_id, membership_id=membership_id
        )

    async def reject_member(
        self, user_id: int, membership_id: str
    ) -> MembershipSummary:
        return await self.reject_membership_on_behalf(
            user_id=user_id, membership_id=membership_id
        )

    async def kick_member(self, user_id: int, membership_id: str) -> MembershipSummary:
        return await self.kick_membership_on_behalf(
            user_id=user_id, membership_id=membership_id
        )

    async def get_favorite_tags(self, user_id: int) -> list[TagSummary]:
        return await self.get_user_favorite_tags(user_id)

    async def get_user_favorite_tags(self, user_id: int) -> list[TagSummary]:

        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.get(f"/internal/users/{user_id}/tags/favorites")
                response.raise_for_status()
                data: list[dict[str, int | str]] = response.json()
                return [_map_tag(item) for item in data]
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def add_favorite_tag(
        self, user_id: int, tag_name: str
    ) -> dict[str, str | dict[str, str | int]]:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.post(
                    f"/internal/users/{user_id}/tags/{tag_name}/favorite"
                )
                response.raise_for_status()
                data: dict[str, str | dict[str, str | int]] = response.json()
                return data
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def remove_favorite_tag(
        self, user_id: int, tag_name: str
    ) -> dict[str, str | dict[str, str | int]]:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.delete(
                    f"/internal/users/{user_id}/tags/{tag_name}/favorite"
                )
                response.raise_for_status()
                data: dict[str, str | dict[str, str | int]] = response.json()
                return data
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def get_report_internal(
        self, report_id: str, moderator_id: int
    ) -> ReportDetails:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.get(
                    f"/internal/moderation/reports/{report_id}",
                    params={"moderator_id": moderator_id},
                )
                response.raise_for_status()
                data: dict[str, int | str | None] = response.json()
                return _map_report(data)
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def list_reports_internal(
        self,
        moderator_id: int,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> ReportPage:
        params: dict[str, str | int] = {"moderator_id": moderator_id, "limit": limit}
        if status:
            params["status"] = status
        if cursor:
            params["cursor"] = cursor

        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.get(
                    "/internal/moderation/reports",
                    params=params,
                )
                response.raise_for_status()
                data: dict[
                    str, int | str | bool | list[dict[str, int | str | None]]
                ] = response.json()
                raw_items = data.get("items") or []
                items = [_map_report(item) for item in raw_items]
                return ReportPage(
                    items=items,
                    total=data.get("total") if data.get("total") is not None else None,
                    next_cursor=str(data.get("next_cursor"))
                    if data.get("next_cursor") is not None
                    else None,
                    has_more=bool(data.get("has_more")),
                )
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def take_report_internal(
        self, report_id: str, moderator_id: int
    ) -> ReportDetails:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.post(
                    f"/internal/moderation/reports/{report_id}/take",
                    params={"moderator_id": moderator_id},
                )
                response.raise_for_status()
                data: dict[str, int | str | None] = response.json()
                return _map_report(data)
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def resolve_report_internal(
        self, report_id: str, payload: ReportResolvePayload, moderator_id: int
    ) -> ReportDetails:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.post(
                    f"/internal/moderation/reports/{report_id}/resolve",
                    params={"moderator_id": moderator_id},
                    json=payload.model_dump(mode="json"),
                )
                response.raise_for_status()
                data: dict[str, int | str | None] = response.json()
                return _map_report(data)
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def dismiss_report_internal(
        self, report_id: str, payload: ReportDismissPayload, moderator_id: int
    ) -> ReportDetails:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.post(
                    f"/internal/moderation/reports/{report_id}/dismiss",
                    params={"moderator_id": moderator_id},
                    json=payload.model_dump(mode="json"),
                )
                response.raise_for_status()
                data: dict[str, int | str | None] = response.json()
                return _map_report(data)
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def ban_user_internal(
        self, user_id: int, reason: str, moderator_id: int
    ) -> dict[str, int | str | bool | list[dict[str, int | str]] | None]:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.post(
                    f"/internal/moderation/users/{user_id}/ban",
                    params={"moderator_id": moderator_id},
                    json={"reason": reason},
                )
                response.raise_for_status()
                data: dict[
                    str, int | str | bool | list[dict[str, int | str]] | None
                ] = response.json()
                return data
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise

    async def unban_user_internal(
        self, user_id: int, reason: str, moderator_id: int
    ) -> dict[str, int | str | bool | list[dict[str, int | str]] | None]:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            try:
                response = await client.post(
                    f"/internal/moderation/users/{user_id}/unban",
                    params={"moderator_id": moderator_id},
                    json={"reason": reason},
                )
                response.raise_for_status()
                data: dict[
                    str, int | str | bool | list[dict[str, int | str]] | None
                ] = response.json()
                return data
            except httpx.HTTPStatusError as e:
                _handle_http_error(e)
                raise
