from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CandidateKind(str, Enum):
    EPIC = "epic"
    ASSIGNEE = "assignee"
    SPRINT = "sprint"
    ISSUE = "issue"


class ConversationState(str, Enum):
    IDLE = "idle"
    RESOLVING_EPIC = "resolving_epic"
    RESOLVING_ASSIGNEE = "resolving_assignee"
    RESOLVING_SPRINT = "resolving_sprint"
    RESOLVING_ISSUE_UPDATE = "resolving_issue_update"
    CONFIRMING = "confirming"
    CONFIRMING_BATCH = "confirming_batch"


@dataclass(frozen=True)
class Candidate:
    id: str
    name: str
    kind: CandidateKind
    key: str | None = None
    email: str | None = None
    score: float = 0

    @property
    def display_name(self) -> str:
        details = [self.key, self.email]
        suffix = ", ".join(value for value in details if value)
        if suffix:
            return f"{self.name} ({suffix})"
        return self.name


@dataclass(frozen=True)
class IssueDraft:
    summary: str
    description: str
    epic_query: str | None
    assignee_query: str | None
    sprint_query: str | None
    estimate: float | None = None
    epic: Candidate | None = None
    assignee: Candidate | None = None
    sprint: Candidate | None = None

    def with_candidate(self, candidate: Candidate) -> "IssueDraft":
        if candidate.kind == CandidateKind.EPIC:
            return IssueDraft(
                summary=self.summary,
                description=self.description,
                epic_query=self.epic_query,
                assignee_query=self.assignee_query,
                sprint_query=self.sprint_query,
                estimate=self.estimate,
                epic=candidate,
                assignee=self.assignee,
                sprint=self.sprint,
            )
        if candidate.kind == CandidateKind.ASSIGNEE:
            return IssueDraft(
                summary=self.summary,
                description=self.description,
                epic_query=self.epic_query,
                assignee_query=self.assignee_query,
                sprint_query=self.sprint_query,
                estimate=self.estimate,
                epic=self.epic,
                assignee=candidate,
                sprint=self.sprint,
            )
        return IssueDraft(
            summary=self.summary,
            description=self.description,
            epic_query=self.epic_query,
            assignee_query=self.assignee_query,
            sprint_query=self.sprint_query,
            estimate=self.estimate,
            epic=self.epic,
            assignee=self.assignee,
            sprint=candidate,
        )

    @property
    def is_ready(self) -> bool:
        return self.epic is not None and self.assignee is not None and self.sprint is not None


@dataclass(frozen=True)
class CreatedIssue:
    key: str
    url: str


@dataclass(frozen=True)
class UpdatedIssue:
    key: str
    url: str
    message: str


@dataclass(frozen=True)
class PendingIssueUpdate:
    estimate: float


@dataclass
class ChatSession:
    state: ConversationState = ConversationState.IDLE
    draft: IssueDraft | None = None
    batch_drafts: tuple[IssueDraft, ...] = ()
    pending_update: PendingIssueUpdate | None = None
    candidates: tuple[Candidate, ...] = ()
