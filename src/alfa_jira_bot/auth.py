from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JiraAuthSettings:
    mode: str
    username: str
    token: str


def normalize_auth_mode(value: str) -> str:
    mode = value.strip().casefold()
    if mode in {"basic", "bearer"}:
        return mode
    raise ValueError("JIRA_AUTH_MODE must be basic or bearer")


def httpx_auth(settings: JiraAuthSettings) -> tuple[str, str] | None:
    if settings.mode == "basic":
        return settings.username, settings.token
    return None


def auth_headers(settings: JiraAuthSettings) -> dict[str, str]:
    if settings.mode == "bearer":
        return {"Authorization": f"Bearer {settings.token}"}
    return {}
