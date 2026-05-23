from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
from urllib.parse import urlparse

from dotenv import load_dotenv
import httpx

from .auth import JiraAuthSettings, auth_headers, httpx_auth, normalize_auth_mode
from .config import bool_env, optional_env, optional_int_env, required_env


@dataclass(frozen=True)
class DiscoveryConfig:
    jira_base_url: str
    jira_auth_mode: str
    jira_username: str
    jira_api_token: str
    jira_project_key: str | None
    jira_board_id: int | None
    jira_verify_tls: bool

    @classmethod
    def from_env(cls) -> "DiscoveryConfig":
        load_dotenv()

        base_url = required_env("JIRA_BASE_URL").rstrip("/")
        parsed_url = urlparse(base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("JIRA_BASE_URL must be an absolute http or https URL")

        return cls(
            jira_base_url=base_url,
            jira_auth_mode=normalize_auth_mode(os.getenv("JIRA_AUTH_MODE", "basic")),
            jira_username=required_env("JIRA_USERNAME"),
            jira_api_token=required_env("JIRA_API_TOKEN"),
            jira_project_key=optional_env("JIRA_PROJECT_KEY"),
            jira_board_id=optional_int_env("JIRA_BOARD_ID"),
            jira_verify_tls=bool_env("JIRA_VERIFY_TLS", default=True),
        )


async def run_discovery() -> None:
    config = DiscoveryConfig.from_env()
    auth_settings = JiraAuthSettings(
        mode=config.jira_auth_mode,
        username=config.jira_username,
        token=config.jira_api_token,
    )
    async with httpx.AsyncClient(
        base_url=config.jira_base_url,
        auth=httpx_auth(auth_settings),
        headers=auth_headers(auth_settings),
        verify=config.jira_verify_tls,
        timeout=30,
    ) as client:
        await print_current_user(client)
        await print_project_hint(client, config.jira_project_key)
        await print_fields(client)
        await print_boards(client, config.jira_project_key)
        await print_sprints(client, config.jira_board_id)


async def print_current_user(client: httpx.AsyncClient) -> None:
    response = await client.get("/rest/api/2/myself")
    response.raise_for_status()
    payload = response.json()
    display_name = payload.get("displayName") or payload.get("name") or "unknown"
    print(f"Jira auth: OK, user = {display_name}")


async def print_project_hint(client: httpx.AsyncClient, project_key: str | None) -> None:
    if not project_key:
        print("\nJIRA_PROJECT_KEY is not set. You can take it from issue keys, for example ABC in ABC-123.")
        return

    response = await client.get(f"/rest/api/2/project/{project_key}")
    if response.status_code == 404:
        print(f"\nProject {project_key}: not found")
        return

    response.raise_for_status()
    payload = response.json()
    print(f"\nProject: {payload.get('key')} - {payload.get('name')}")


async def print_fields(client: httpx.AsyncClient) -> None:
    response = await client.get("/rest/api/2/field")
    response.raise_for_status()
    fields = response.json()
    keywords = ("epic", "эпик", "sprint", "спринт")
    matches = [
        field
        for field in fields
        if any(keyword in str(field.get("name", "")).casefold() for keyword in keywords)
    ]

    print("\nPossible custom fields:")
    for field in matches:
        field_id = field.get("id")
        name = field.get("name")
        schema = field.get("schema") or {}
        custom = schema.get("custom") or ""
        print(f"- {field_id}: {name} ({custom})")

    if not matches:
        print("- No Epic/Sprint fields found by name. Ask Jira admin or inspect create metadata.")


async def print_boards(client: httpx.AsyncClient, project_key: str | None) -> None:
    params = {"maxResults": "50"}
    if project_key:
        params["projectKeyOrId"] = project_key

    response = await client.get("/rest/agile/1.0/board", params=params)
    if response.status_code == 404:
        print("\nBoards: /rest/agile/1.0 is unavailable in this Jira.")
        return

    response.raise_for_status()
    boards = response.json().get("values", [])
    print("\nBoards:")
    if not boards:
        print("- No boards found")
        return

    for board in boards:
        print(f"- {board.get('id')}: {board.get('name')} [{board.get('type')}]")


async def print_sprints(client: httpx.AsyncClient, board_id: int | None) -> None:
    if board_id is None:
        print("\nSprints: set JIRA_BOARD_ID first to check active/future sprints.")
        return

    response = await client.get(
        f"/rest/agile/1.0/board/{board_id}/sprint",
        params={"state": "active,future", "maxResults": "20"},
    )
    if response.status_code == 404:
        await print_greenhopper_sprints(client, board_id)
        return

    response.raise_for_status()
    print_sprint_list(response.json().get("values", []))


async def print_greenhopper_sprints(client: httpx.AsyncClient, board_id: int) -> None:
    response = await client.get(
        f"/rest/greenhopper/1.0/sprintquery/{board_id}",
        params={"includeHistoricSprints": "false", "includeFutureSprints": "true"},
    )
    if response.status_code == 404:
        print("\nSprints: neither Agile nor GreenHopper sprint endpoints are available.")
        return

    response.raise_for_status()
    print_sprint_list(response.json().get("sprints", []))


def print_sprint_list(sprints: list[dict[str, object]]) -> None:
    print("\nActive/future sprints:")
    if not sprints:
        print("- No active or future sprints found")
        return

    for sprint in sprints:
        print(f"- {sprint.get('id')}: {sprint.get('name')}")


def main() -> None:
    try:
        asyncio.run(run_discovery())
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        if status == 401:
            raise SystemExit(
                "Jira returned HTTP 401: credentials were rejected. "
                "Check JIRA_USERNAME/JIRA_API_TOKEN, or set JIRA_AUTH_MODE=bearer if you use a Personal Access Token."
            ) from error
        body = error.response.text[:500]
        raise SystemExit(f"Jira returned HTTP {status}: {body}") from error
    except httpx.RequestError as error:
        raise SystemExit(f"Cannot reach Jira. Check VPN, URL, TLS, and proxy settings. Detail: {error}") from error
    except ValueError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
