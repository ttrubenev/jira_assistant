from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlparse

from dotenv import load_dotenv

from .auth import normalize_auth_mode


@dataclass(frozen=True)
class BotConfig:
    telegram_bot_token: str
    jira_base_url: str
    jira_auth_mode: str
    jira_username: str
    jira_api_token: str
    jira_project_key: str
    jira_issue_type: str
    jira_epic_link_field: str
    jira_epic_name_field: str
    jira_sprint_field: str | None
    jira_task_type_field: str | None
    jira_default_task_type: str | None
    jira_estimate_field: str | None
    jira_board_id: int | None
    jira_default_epic_key: str | None
    jira_default_epic_name: str | None
    jira_default_sprint_query: str | None
    jira_default_assignee_key: str | None
    jira_default_assignee_name: str | None
    jira_default_assignee_email: str | None
    jira_verify_tls: bool
    voice_transcriber_command: str | None

    @classmethod
    def from_env(cls) -> "BotConfig":
        load_dotenv()

        base_url = required_env("JIRA_BASE_URL").rstrip("/")
        parsed_url = urlparse(base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("JIRA_BASE_URL must be an absolute http or https URL")

        return cls(
            telegram_bot_token=required_env("TELEGRAM_BOT_TOKEN"),
            jira_base_url=base_url,
            jira_auth_mode=normalize_auth_mode(os.getenv("JIRA_AUTH_MODE", "basic")),
            jira_username=required_env("JIRA_USERNAME"),
            jira_api_token=required_env("JIRA_API_TOKEN"),
            jira_project_key=required_env("JIRA_PROJECT_KEY"),
            jira_issue_type=os.getenv("JIRA_ISSUE_TYPE", "Task"),
            jira_epic_link_field=required_env("JIRA_EPIC_LINK_FIELD"),
            jira_epic_name_field=required_env("JIRA_EPIC_NAME_FIELD"),
            jira_sprint_field=optional_env("JIRA_SPRINT_FIELD"),
            jira_task_type_field=optional_env("JIRA_TASK_TYPE_FIELD"),
            jira_default_task_type=optional_env("JIRA_DEFAULT_TASK_TYPE"),
            jira_estimate_field=optional_env("JIRA_ESTIMATE_FIELD"),
            jira_board_id=optional_int_env("JIRA_BOARD_ID"),
            jira_default_epic_key=optional_env("JIRA_DEFAULT_EPIC_KEY"),
            jira_default_epic_name=optional_env("JIRA_DEFAULT_EPIC_NAME"),
            jira_default_sprint_query=optional_env("JIRA_DEFAULT_SPRINT_QUERY"),
            jira_default_assignee_key=optional_env("JIRA_DEFAULT_ASSIGNEE_KEY"),
            jira_default_assignee_name=optional_env("JIRA_DEFAULT_ASSIGNEE_NAME"),
            jira_default_assignee_email=optional_env("JIRA_DEFAULT_ASSIGNEE_EMAIL"),
            jira_verify_tls=bool_env("JIRA_VERIFY_TLS", default=True),
            voice_transcriber_command=optional_env("VOICE_TRANSCRIBER_COMMAND"),
        )


def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def optional_int_env(name: str) -> int | None:
    value = optional_env(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error


def bool_env(name: str, *, default: bool) -> bool:
    value = optional_env(name)
    if value is None:
        return default
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"{name} must be true or false")
