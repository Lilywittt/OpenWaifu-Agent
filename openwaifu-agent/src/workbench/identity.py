from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from hashlib import sha1
from typing import Mapping

from io_utils import normalize_spaces

from .profile import WorkbenchProfile

_CF_EMAIL_HEADER = "cf-access-authenticated-user-email"
_CF_NAME_HEADER = "cf-access-authenticated-user-name"
_CLIENT_IP_HEADER_CANDIDATES = (
    "cf-connecting-ip",
    "true-client-ip",
    "x-real-ip",
)
_FORWARDED_IP_HEADER = "x-forwarded-for"
_CF_COUNTRY_HEADER = "cf-ipcountry"
_CF_REGION_HEADER = "cf-region"
_CF_CITY_HEADER = "cf-ipcity"
_CF_POSTAL_CODE_HEADER = "cf-postal-code"
_CF_TIMEZONE_HEADER = "cf-timezone"
_CF_RAY_HEADER = "cf-ray"
_HOST_HEADER = "host"
_USER_AGENT_HEADER = "user-agent"
_FORWARDED_PROTO_HEADER = "x-forwarded-proto"

_PRIVATE_DISPLAY_NAME = "\u79c1\u6709\u5de5\u4f5c\u53f0"
_ANONYMOUS_DISPLAY_NAME = "\u533f\u540d\u4f53\u9a8c\u8005"


@dataclass(frozen=True)
class WorkbenchRequestContext:
    client_ip: str = ""
    country: str = ""
    region: str = ""
    city: str = ""
    postal_code: str = ""
    timezone: str = ""
    cf_ray: str = ""
    host: str = ""
    user_agent: str = ""
    forwarded_proto: str = ""


@dataclass(frozen=True)
class WorkbenchViewer:
    owner_id: str
    display_name: str
    email: str
    authenticated: bool
    public: bool
    client_ip: str = ""


def _owner_from_text(value: str, *, prefix: str) -> str:
    normalized = normalize_spaces(value).casefold()
    if not normalized:
        normalized = "anonymous"
    digest = sha1(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _normalize_ip_candidate(value: str) -> str:
    text = normalize_spaces(value)
    if not text:
        return ""
    if text.startswith("[") and "]" in text:
        text = text[1 : text.index("]")]
    if text.count(":") == 1 and "." in text:
        host, _, port = text.partition(":")
        if port.isdigit():
            text = host
    try:
        return ipaddress.ip_address(text).compressed
    except ValueError:
        return ""


def _resolve_client_ip(headers: Mapping[str, str], *, client_address: str) -> str:
    for header_name in _CLIENT_IP_HEADER_CANDIDATES:
        client_ip = _normalize_ip_candidate(headers.get(header_name, ""))
        if client_ip:
            return client_ip
    forwarded = normalize_spaces(headers.get(_FORWARDED_IP_HEADER, ""))
    if forwarded:
        for part in forwarded.split(","):
            client_ip = _normalize_ip_candidate(part)
            if client_ip:
                return client_ip
    return _normalize_ip_candidate(client_address)


def resolve_workbench_request_context(
    *,
    headers: Mapping[str, str] | None = None,
    client_address: str = "",
) -> WorkbenchRequestContext:
    lowered_headers = {str(key).strip().lower(): str(value) for key, value in (headers or {}).items()}
    return WorkbenchRequestContext(
        client_ip=_resolve_client_ip(lowered_headers, client_address=client_address),
        country=normalize_spaces(lowered_headers.get(_CF_COUNTRY_HEADER, "")),
        region=normalize_spaces(lowered_headers.get(_CF_REGION_HEADER, "")),
        city=normalize_spaces(lowered_headers.get(_CF_CITY_HEADER, "")),
        postal_code=normalize_spaces(lowered_headers.get(_CF_POSTAL_CODE_HEADER, "")),
        timezone=normalize_spaces(lowered_headers.get(_CF_TIMEZONE_HEADER, "")),
        cf_ray=normalize_spaces(lowered_headers.get(_CF_RAY_HEADER, "")),
        host=normalize_spaces(lowered_headers.get(_HOST_HEADER, "")),
        user_agent=normalize_spaces(lowered_headers.get(_USER_AGENT_HEADER, "")),
        forwarded_proto=normalize_spaces(lowered_headers.get(_FORWARDED_PROTO_HEADER, "")),
    )


def resolve_workbench_viewer(
    profile: WorkbenchProfile,
    *,
    headers: Mapping[str, str] | None = None,
    client_address: str = "",
    request_context: WorkbenchRequestContext | None = None,
) -> WorkbenchViewer:
    lowered_headers = {str(key).strip().lower(): str(value) for key, value in (headers or {}).items()}
    context = request_context or resolve_workbench_request_context(
        headers=lowered_headers,
        client_address=client_address,
    )
    if not profile.public:
        return WorkbenchViewer(
            owner_id="private",
            display_name=_PRIVATE_DISPLAY_NAME,
            email="",
            authenticated=True,
            public=False,
            client_ip=context.client_ip,
        )

    email = normalize_spaces(lowered_headers.get(_CF_EMAIL_HEADER, ""))
    display_name = normalize_spaces(lowered_headers.get(_CF_NAME_HEADER, ""))
    if email:
        return WorkbenchViewer(
            owner_id=_owner_from_text(email, prefix="access"),
            display_name=display_name or email,
            email=email,
            authenticated=True,
            public=True,
            client_ip=context.client_ip,
        )

    client_text = context.client_ip or normalize_spaces(client_address) or "local"
    return WorkbenchViewer(
        owner_id=_owner_from_text(client_text, prefix="anonymous"),
        display_name=_ANONYMOUS_DISPLAY_NAME,
        email="",
        authenticated=False,
        public=True,
        client_ip=context.client_ip,
    )
