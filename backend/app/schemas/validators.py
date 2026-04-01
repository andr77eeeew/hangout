import re
from typing import Annotated

from pydantic import AfterValidator, Field


def _validate_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not re.search(r"[A-Z]", value):
        raise ValueError("Password must contain at least one capital letter")
    if not re.search(r"\d", value):
        raise ValueError("Password must contain at least one number")
    return value


def _validate_username(value: str) -> str:
    if len(value) < 3:
        raise ValueError("Username must be at least 3 characters")
    if not re.match(r"[a-zA-Z0-9_]+$", value):
        raise ValueError("Username must be alphanumeric, digits, or underscore")
    return value


def _validate_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for raw in tags:
        tag = raw.strip().lstrip("#").casefold()
        if not tag:
            continue
        if tag not in seen:
            seen.add(tag)
            normalized.append(tag)

    if not normalized:
        raise ValueError("At least one tag is required")
    if len(normalized) > 5:
        raise ValueError("No more than 5 tags are allowed")
    return normalized


ValidPassword = Annotated[str, AfterValidator(_validate_password)]
ValidUsername = Annotated[str, AfterValidator(_validate_username)]
ValidTags = Annotated[list[str], AfterValidator(_validate_tags)]
