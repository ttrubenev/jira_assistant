from __future__ import annotations

from typing import Protocol

from .domain import Candidate, CreatedIssue, IssueDraft, UpdatedIssue


class JiraGateway(Protocol):
    async def search_epics(self, query: str) -> tuple[Candidate, ...]:
        ...

    async def search_assignees(self, query: str) -> tuple[Candidate, ...]:
        ...

    async def search_sprints(self, query: str) -> tuple[Candidate, ...]:
        ...

    async def search_issues(self, query: str) -> tuple[Candidate, ...]:
        ...

    async def create_issue(self, draft: IssueDraft) -> CreatedIssue:
        ...

    async def update_issue_estimate(self, issue_key: str, estimate: float) -> UpdatedIssue:
        ...
