from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .auth import JiraAuthSettings, auth_headers, httpx_auth
from .config import BotConfig
from .domain import Candidate, CandidateKind, CreatedIssue, IssueDraft, UpdatedIssue
from .fuzzy import rank_candidates
from .user_search import assignee_search_queries, strip_html, unique_candidates


@dataclass(frozen=True)
class JiraClient:
    config: BotConfig

    def _client(self) -> httpx.AsyncClient:
        auth_settings = JiraAuthSettings(
            mode=self.config.jira_auth_mode,
            username=self.config.jira_username,
            token=self.config.jira_api_token,
        )
        return httpx.AsyncClient(
            base_url=self.config.jira_base_url,
            auth=httpx_auth(auth_settings),
            headers=auth_headers(auth_settings),
            verify=self.config.jira_verify_tls,
            timeout=30,
        )

    async def search_epics(self, query: str) -> tuple[Candidate, ...]:
        jql = (
            f'project = "{self.config.jira_project_key}" '
            f'AND issuetype = Epic AND text ~ "{escape_jql(query)}" ORDER BY updated DESC'
        )
        params = {
            "jql": jql,
            "maxResults": "10",
            "fields": f"summary,{self.config.jira_epic_name_field}",
        }
        async with self._client() as client:
            response = await client.get("/rest/api/2/search", params=params)
            response.raise_for_status()
            issues = response.json().get("issues", [])

        return tuple(self._epic_candidate(issue) for issue in issues)

    async def search_assignees(self, query: str) -> tuple[Candidate, ...]:
        async with self._client() as client:
            users: list[dict[str, Any]] = []
            for search_query in assignee_search_queries(query):
                users.extend(await self._search_assignable_users(client, search_query))
                users.extend(await self._search_user_picker(client, search_query))
                users.extend(await self._search_group_user_picker(client, search_query))
                users.extend(await self._search_users(client, search_query))

        candidates = unique_candidates(self._user_candidate(user) for user in users)
        return rank_candidates(query, candidates, limit=10)

    async def _search_assignable_users(self, client: httpx.AsyncClient, query: str) -> list[dict[str, Any]]:
        response = await client.get(
            "/rest/api/2/user/assignable/search",
            params={
                "project": self.config.jira_project_key,
                "username": query,
                "query": query,
                "maxResults": "20",
            },
        )
        if response.status_code in {400, 404}:
            return []
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []

    async def _search_user_picker(self, client: httpx.AsyncClient, query: str) -> list[dict[str, Any]]:
        response = await client.get(
            "/rest/api/2/user/picker",
            params={"query": query, "maxResults": "20"},
        )
        if response.status_code in {400, 404}:
            return []
        response.raise_for_status()
        users = response.json().get("users", [])
        return users if isinstance(users, list) else []

    async def _search_group_user_picker(self, client: httpx.AsyncClient, query: str) -> list[dict[str, Any]]:
        response = await client.get(
            "/rest/api/2/groupuserpicker",
            params={"query": query, "maxResults": "20", "showAvatar": "false"},
        )
        if response.status_code in {400, 404}:
            return []
        response.raise_for_status()
        users = response.json().get("users", {})
        if isinstance(users, dict):
            nested_users = users.get("users", [])
            return nested_users if isinstance(nested_users, list) else []
        return users if isinstance(users, list) else []

    async def _search_users(self, client: httpx.AsyncClient, query: str) -> list[dict[str, Any]]:
        response = await client.get(
            "/rest/api/2/user/search",
            params={"username": query, "maxResults": "20"},
        )
        if response.status_code in {400, 404}:
            return []
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []

    async def search_sprints(self, query: str) -> tuple[Candidate, ...]:
        if self.config.jira_board_id is None:
            return ()

        params = {"state": "active,future", "maxResults": "50"}
        async with self._client() as client:
            response = await client.get(
                f"/rest/agile/1.0/board/{self.config.jira_board_id}/sprint",
                params=params,
            )
            if response.status_code == 404:
                return await self._search_greenhopper_sprints(client)
            response.raise_for_status()
            sprints = response.json().get("values", [])

        return tuple(
            Candidate(
                id=str(sprint.get("id", "")),
                name=str(sprint.get("name", "")),
                kind=CandidateKind.SPRINT,
                key=str(sprint.get("state", "")) or None,
            )
            for sprint in sprints
            if sprint.get("id") and sprint.get("name")
        )

    async def search_issues(self, query: str) -> tuple[Candidate, ...]:
        jql = (
            f'project = "{self.config.jira_project_key}" '
            f'AND summary ~ "{escape_jql(query)}" ORDER BY updated DESC'
        )
        async with self._client() as client:
            response = await client.get(
                "/rest/api/2/search",
                params={"jql": jql, "maxResults": "20", "fields": "summary"},
            )
            response.raise_for_status()
            issues = response.json().get("issues", [])

        candidates = tuple(
            Candidate(
                id=str(issue.get("key", "")),
                key=str(issue.get("key", "")),
                name=str((issue.get("fields") or {}).get("summary") or issue.get("key", "")),
                kind=CandidateKind.ISSUE,
            )
            for issue in issues
            if issue.get("key")
        )
        return rank_candidates(query, candidates, limit=10)

    async def _search_greenhopper_sprints(self, client: httpx.AsyncClient) -> tuple[Candidate, ...]:
        response = await client.get(
            f"/rest/greenhopper/1.0/sprintquery/{self.config.jira_board_id}",
            params={"includeHistoricSprints": "false", "includeFutureSprints": "true"},
        )
        response.raise_for_status()
        sprints = response.json().get("sprints", [])
        return tuple(
            Candidate(
                id=str(sprint.get("id", "")),
                name=str(sprint.get("name", "")),
                kind=CandidateKind.SPRINT,
                key=str(sprint.get("state", "")).lower() or None,
            )
            for sprint in sprints
            if sprint.get("id") and sprint.get("name")
        )

    async def create_issue(self, draft: IssueDraft) -> CreatedIssue:
        if draft.epic is None or draft.assignee is None or draft.sprint is None:
            raise ValueError("Issue draft must be fully resolved before creation")

        fields: dict[str, Any] = {
            "project": {"key": self.config.jira_project_key},
            "summary": draft.summary,
            "description": draft.description,
            "issuetype": {"name": self.config.jira_issue_type},
        }
        fields.update(self._default_create_fields())
        fields.update(self._estimate_fields(draft.estimate))

        async with self._client() as client:
            response = await client.post("/rest/api/2/issue", json={"fields": fields})
            raise_for_status(response, action="создание задачи")
            payload = response.json()
            key = str(payload["key"])

            await self._assign_issue(client, issue_key=key, assignee=draft.assignee)
            await self._add_issue_to_epic(client, issue_key=key, epic=draft.epic)
            await self._add_issue_to_sprint(client, issue_key=key, sprint=draft.sprint)

        return CreatedIssue(key=key, url=f"{self.config.jira_base_url}/browse/{key}")

    async def update_issue_estimate(self, issue_key: str, estimate: float) -> UpdatedIssue:
        async with self._client() as client:
            await self._set_estimate(client, issue_key=issue_key, estimate=estimate)

        return UpdatedIssue(
            key=issue_key,
            url=f"{self.config.jira_base_url}/browse/{issue_key}",
            message=f"Story Points обновлены: {format_estimate_value(estimate)}",
        )

    async def _assign_issue(self, client: httpx.AsyncClient, *, issue_key: str, assignee: Candidate) -> None:
        response = await client.put(
            f"/rest/api/2/issue/{issue_key}/assignee",
            json=self._assignee_payload(assignee),
        )
        raise_for_status(response, action=f"назначение исполнителя для {issue_key}")

    async def _add_issue_to_epic(self, client: httpx.AsyncClient, *, issue_key: str, epic: Candidate) -> None:
        response = await client.post(
            f"/rest/agile/1.0/epic/{epic.key or epic.id}/issue",
            json={"issues": [issue_key]},
        )
        if response.status_code == 404:
            response = await client.put(
                f"/rest/api/2/issue/{issue_key}",
                json={"fields": {self.config.jira_epic_link_field: epic.key or epic.id}},
            )
        raise_for_status(response, action=f"добавление {issue_key} в эпик")

    async def _add_issue_to_sprint(self, client: httpx.AsyncClient, *, issue_key: str, sprint: Candidate) -> None:
        response = await client.post(
            f"/rest/agile/1.0/sprint/{sprint.id}/issue",
            json={"issues": [issue_key]},
        )
        if response.status_code == 404 and self.config.jira_sprint_field:
            response = await client.put(
                f"/rest/api/2/issue/{issue_key}",
                json={"fields": {self.config.jira_sprint_field: int(sprint.id)}},
            )
        raise_for_status(response, action=f"добавление {issue_key} в спринт")

    async def _set_estimate(self, client: httpx.AsyncClient, *, issue_key: str, estimate: float) -> None:
        if not self.config.jira_estimate_field:
            raise RuntimeError("JIRA_ESTIMATE_FIELD не настроен")

        response = await client.put(
            f"/rest/api/2/issue/{issue_key}",
            json={"fields": self._estimate_fields(estimate)},
        )
        raise_for_status(response, action=f"обновление Story Points для {issue_key}")

    def _epic_candidate(self, issue: dict[str, Any]) -> Candidate:
        fields = issue.get("fields", {})
        epic_name = fields.get(self.config.jira_epic_name_field)
        summary = fields.get("summary")
        key = str(issue.get("key", ""))
        return Candidate(
            id=key,
            key=key,
            name=str(epic_name or summary or key),
            kind=CandidateKind.EPIC,
        )

    def _user_candidate(self, user: dict[str, Any]) -> Candidate:
        account_id = user.get("accountId")
        name = user.get("name") or user.get("key") or user.get("userName") or account_id
        display_name = user.get("displayName") or user.get("html") or name
        email = user.get("emailAddress")
        return Candidate(
            id=str(account_id or name),
            key=str(name) if name else None,
            name=strip_html(str(display_name)),
            email=str(email) if email else None,
            kind=CandidateKind.ASSIGNEE,
        )

    def _assignee_payload(self, assignee: Candidate) -> dict[str, str]:
        if assignee.key:
            return {"name": assignee.key}
        return {"name": assignee.id}

    def _default_create_fields(self) -> dict[str, Any]:
        if not self.config.jira_task_type_field or not self.config.jira_default_task_type:
            return {}
        return {
            self.config.jira_task_type_field: {
                "value": self.config.jira_default_task_type,
            }
        }

    def _estimate_fields(self, estimate: float | None) -> dict[str, Any]:
        if estimate is None or not self.config.jira_estimate_field:
            return {}
        return {
            self.config.jira_estimate_field: float(estimate),
        }


def escape_jql(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def format_estimate_value(value: float) -> str:
    numeric_value = float(value)
    if numeric_value.is_integer():
        return str(int(numeric_value))
    return str(numeric_value).rstrip("0").rstrip(".")


def raise_for_status(response: httpx.Response, *, action: str) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        details = format_jira_error(response)
        raise RuntimeError(f"Jira не приняла запрос: {action}. {details}") from error


def format_jira_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        text = " ".join(response.text.split())
        return f"HTTP {response.status_code}: {text[:700]}"

    messages: list[str] = []
    for message in payload.get("errorMessages", []):
        messages.append(str(message))

    errors = payload.get("errors", {})
    if isinstance(errors, dict):
        for field, message in errors.items():
            messages.append(f"{field}: {message}")

    if not messages:
        messages.append(str(payload))

    return f"HTTP {response.status_code}: {'; '.join(messages)}"
