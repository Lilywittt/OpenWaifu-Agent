from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from typing import Mapping

from io_utils import normalize_spaces
from .profile import WorkbenchProfile

_CF_EMAIL_HEADER = "cf-access-authenticated-user-email"
_CF_NAME_HEADER = "cf-access-authenticated-user-name"


@dataclass(frozen=True)
class WorkbenchViewer:
    owner_id: str
    display_name: str
    email: str
    authenticated: bool
    public: bool


def _owner_from_text(value: str, *, prefix: str) -> str:
    normalized = normalize_spaces(value).casefold()
    if not normalized:
        normalized = "anonymous"
    digest = sha1(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def resolve_workbench_viewer(
    profile: WorkbenchProfile,
    *,
    headers: Mapping[str, str] | None = None,
    client_address: str = "",
) -> WorkbenchViewer:
    if not profile.public:
        return WorkbenchViewer(
            owner_id="private",
            display_name="私有工作台",
            email="",
            authenticated=True,
            public=False,
        )

    lowered_headers = {str(key).strip().lower(): str(value) for key, value in (headers or {}).items()}
    email = normalize_spaces(lowered_headers.get(_CF_EMAIL_HEADER, ""))
    display_name = normalize_spaces(lowered_headers.get(_CF_NAME_HEADER, ""))
    if email:
        return WorkbenchViewer(
            owner_id=_owner_from_text(email, prefix="access"),
            display_name=display_name or email,
            email=email,
            authenticated=True,
            public=True,
        )

    client_text = normalize_spaces(client_address) or "local"
    return WorkbenchViewer(
        owner_id=_owner_from_text(client_text, prefix="anonymous"),
        display_name="匿名体验者",
        email="",
        authenticated=False,
        public=True,
    )
