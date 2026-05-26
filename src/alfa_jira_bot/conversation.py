from __future__ import annotations

from dataclasses import dataclass

from .domain import (
    Candidate,
    CandidateKind,
    ChatSession,
    ConversationState,
    CreatedIssue,
    IssueDraft,
    PendingIssueUpdate,
    UpdatedIssue,
)
from .fuzzy import rank_candidates
from .parser import parse_issue_batch, parse_issue_message, parse_issue_update
from .ports import JiraGateway


@dataclass(frozen=True)
class BotReply:
    text: str


@dataclass(frozen=True)
class ConversationDefaults:
    epic: Candidate | None = None
    assignee: Candidate | None = None
    sprint_query: str | None = None


class ConversationManager:
    def __init__(self, jira: JiraGateway, defaults: ConversationDefaults | None = None) -> None:
        self.jira = jira
        self.defaults = defaults or ConversationDefaults()
        self.sessions: dict[int, ChatSession] = {}

    def is_idle(self, chat_id: int) -> bool:
        session = self.sessions.get(chat_id)
        return session is None or session.state == ConversationState.IDLE

    async def handle_text(self, chat_id: int, text: str) -> list[BotReply]:
        normalized = text.strip()
        if is_cancel(normalized):
            self.sessions.pop(chat_id, None)
            return [BotReply("Ок, отменил создание задачи.")]

        session = self.sessions.setdefault(chat_id, ChatSession())

        if session.state == ConversationState.IDLE:
            update = parse_issue_update(normalized)
            if update is not None:
                if update.issue_key is not None:
                    updated = await self.jira.update_issue_estimate(update.issue_key, update.estimate)
                    return [BotReply(format_updated_issue(updated))]
                return await self._resolve_issue_update(chat_id, update.issue_query or "", update.estimate)

            batch = parse_issue_batch(normalized)
            if batch:
                return await self._prepare_batch(chat_id, tuple(parsed.to_draft() for parsed in batch))

            draft = parse_issue_message(normalized).to_draft()
            session.draft = draft
            return await self._resolve_next(chat_id)

        if session.state in {
            ConversationState.RESOLVING_EPIC,
            ConversationState.RESOLVING_ASSIGNEE,
            ConversationState.RESOLVING_SPRINT,
            ConversationState.RESOLVING_ISSUE_UPDATE,
        }:
            return await self._handle_candidate_answer(chat_id, normalized)

        if session.state == ConversationState.CONFIRMING:
            return await self._handle_confirmation(chat_id, normalized)

        if session.state == ConversationState.CONFIRMING_BATCH:
            return await self._handle_batch_confirmation(chat_id, normalized)

        return [BotReply("Не понял состояние диалога. Напишите задачу заново.")]

    async def _handle_candidate_answer(self, chat_id: int, text: str) -> list[BotReply]:
        session = self.sessions[chat_id]
        selected = candidate_by_answer(text, session.candidates)
        if selected is not None:
            if session.state == ConversationState.RESOLVING_ISSUE_UPDATE:
                pending_update = session.pending_update
                if pending_update is None:
                    self.sessions.pop(chat_id, None)
                    return [BotReply("Не нашел данные для обновления. Напишите команду заново.")]
                updated = await self.jira.update_issue_estimate(selected.key or selected.id, pending_update.estimate)
                self.sessions.pop(chat_id, None)
                return [BotReply(format_updated_issue(updated))]

            draft = session.draft
            if draft is None:
                self.sessions.pop(chat_id, None)
                return [BotReply("Черновик потерялся. Напишите задачу заново.")]

            session.draft = draft.with_candidate(selected)
            session.candidates = ()
            return await self._resolve_next(chat_id)

        kind = expected_kind(session.state)
        candidates = await self._search(kind, text)
        ranked = rank_candidates(text, candidates)
        if not ranked:
            return [BotReply(f"Не нашел похожих вариантов. Уточните: {kind_label(kind)}.")]

        session.candidates = ranked
        return [BotReply(format_candidates(f"Похоже, это один из вариантов. Выберите номер:", ranked))]

    async def _handle_confirmation(self, chat_id: int, text: str) -> list[BotReply]:
        session = self.sessions[chat_id]
        draft = session.draft
        if draft is None:
            self.sessions.pop(chat_id, None)
            return [BotReply("Черновик потерялся. Напишите задачу заново.")]

        if is_positive(text):
            created = await self.jira.create_issue(draft)
            self.sessions.pop(chat_id, None)
            return [BotReply(format_created_issue(created))]

        if is_negative(text):
            self.sessions.pop(chat_id, None)
            return [BotReply("Ок, отменил создание задачи.")]

        return [BotReply("Создать задачу? Ответьте «да» или «нет».")]

    async def _handle_batch_confirmation(self, chat_id: int, text: str) -> list[BotReply]:
        session = self.sessions[chat_id]
        drafts = session.batch_drafts
        if not drafts:
            self.sessions.pop(chat_id, None)
            return [BotReply("Черновики потерялись. Напишите задачи заново.")]

        if is_positive(text):
            created = [await self.jira.create_issue(draft) for draft in drafts]
            self.sessions.pop(chat_id, None)
            return [BotReply(format_created_batch(tuple(created)))]

        if is_negative(text):
            self.sessions.pop(chat_id, None)
            return [BotReply("Ок, отменил создание задач.")]

        return [BotReply(f"Создать {len(drafts)} задачи? Ответьте «да» или «нет».")]

    async def _resolve_next(self, chat_id: int) -> list[BotReply]:
        session = self.sessions[chat_id]
        draft = session.draft
        if draft is None:
            session.state = ConversationState.IDLE
            return [BotReply("Напишите задачу одним сообщением.")]

        for kind, query, state in [
            (CandidateKind.EPIC, draft.epic_query, ConversationState.RESOLVING_EPIC),
            (CandidateKind.ASSIGNEE, draft.assignee_query, ConversationState.RESOLVING_ASSIGNEE),
            (CandidateKind.SPRINT, draft.sprint_query, ConversationState.RESOLVING_SPRINT),
        ]:
            if current_candidate(draft, kind) is not None:
                continue
            default_candidate = self._default_candidate(kind)
            if not query and default_candidate is not None:
                session.draft = draft.with_candidate(default_candidate)
                return await self._resolve_next(chat_id)

            used_default_query = False
            if not query:
                query = self._default_query(kind)
                used_default_query = query is not None
                if not query:
                    session.state = state
                    return [BotReply(f"Укажите {kind_label(kind)}.")]

            candidates = await self._search(kind, query)
            ranked = rank_candidates(query, candidates)
            automatic_candidate = candidate_for_automatic_selection(
                kind,
                ranked,
                used_default_query=used_default_query,
            )
            if automatic_candidate is not None:
                session.draft = draft.with_candidate(automatic_candidate)
                return await self._resolve_next(chat_id)

            session.state = state
            session.candidates = ranked
            if ranked:
                return [BotReply(format_candidates(f"Выберите {kind_label(kind)}:", ranked))]
            return [BotReply(f"Не нашел {kind_label(kind)} по «{query}». Уточните запрос.")]

        session.state = ConversationState.CONFIRMING
        return [BotReply(format_confirmation(draft))]

    async def _prepare_batch(self, chat_id: int, drafts: tuple[IssueDraft, ...]) -> list[BotReply]:
        session = self.sessions[chat_id]
        resolved_drafts: list[IssueDraft] = []

        for index, draft in enumerate(drafts, start=1):
            resolved, error = await self._resolve_batch_draft(draft)
            if error is not None:
                self.sessions.pop(chat_id, None)
                return [BotReply(f"В задаче {index} «{draft.summary}» {error}")]
            resolved_drafts.append(resolved)

        session.state = ConversationState.CONFIRMING_BATCH
        session.batch_drafts = tuple(resolved_drafts)
        session.draft = None
        session.candidates = ()
        return [BotReply(format_batch_confirmation(session.batch_drafts))]

    async def _resolve_batch_draft(self, draft: IssueDraft) -> tuple[IssueDraft, str | None]:
        resolved = draft
        for kind, query in [
            (CandidateKind.EPIC, resolved.epic_query),
            (CandidateKind.ASSIGNEE, resolved.assignee_query),
            (CandidateKind.SPRINT, resolved.sprint_query),
        ]:
            if current_candidate(resolved, kind) is not None:
                continue

            default_candidate = self._default_candidate(kind)
            if not query and default_candidate is not None:
                resolved = resolved.with_candidate(default_candidate)
                continue

            used_default_query = False
            if not query:
                query = self._default_query(kind)
                used_default_query = query is not None

            if not query:
                return resolved, f"не указан {kind_label(kind)}."

            candidates = await self._search(kind, query)
            ranked = rank_candidates(query, candidates)
            automatic_candidate = candidate_for_automatic_selection(
                kind,
                ranked,
                used_default_query=used_default_query,
            )
            if automatic_candidate is None:
                label = kind_label(kind)
                if ranked:
                    return resolved, f"не смог уверенно выбрать {label}. Уточните запрос или создайте эту задачу отдельно."
                return resolved, f"не нашел {label} по «{query}». Уточните запрос или создайте эту задачу отдельно."

            resolved = resolved.with_candidate(automatic_candidate)

        return resolved, None

    async def _search(self, kind: CandidateKind, query: str) -> tuple[Candidate, ...]:
        if kind == CandidateKind.EPIC:
            return await self.jira.search_epics(query)
        if kind == CandidateKind.ASSIGNEE:
            return await self.jira.search_assignees(query)
        if kind == CandidateKind.ISSUE:
            return await self.jira.search_issues(query)
        return await self.jira.search_sprints(query)

    async def _resolve_issue_update(self, chat_id: int, query: str, estimate: float) -> list[BotReply]:
        session = self.sessions[chat_id]
        candidates = await self.jira.search_issues(query)
        ranked = rank_candidates(query, candidates, limit=10)
        automatic_candidate = candidate_for_automatic_selection(
            CandidateKind.ISSUE,
            ranked,
            used_default_query=False,
        )
        if automatic_candidate is not None:
            updated = await self.jira.update_issue_estimate(
                automatic_candidate.key or automatic_candidate.id,
                estimate,
            )
            return [BotReply(format_updated_issue(updated))]

        if not ranked:
            return [BotReply(f"Не нашел задачи по «{query}». Укажите точнее или пришлите ключ задачи.")]

        session.state = ConversationState.RESOLVING_ISSUE_UPDATE
        session.pending_update = PendingIssueUpdate(estimate=estimate)
        session.candidates = ranked
        return [BotReply(format_candidates("Нашел похожие задачи. Выберите номер:", ranked))]

    def _default_candidate(self, kind: CandidateKind) -> Candidate | None:
        if kind == CandidateKind.EPIC:
            return self.defaults.epic
        if kind == CandidateKind.ASSIGNEE:
            return self.defaults.assignee
        return None

    def _default_query(self, kind: CandidateKind) -> str | None:
        if kind == CandidateKind.SPRINT:
            return self.defaults.sprint_query
        return None


def current_candidate(draft: IssueDraft, kind: CandidateKind) -> Candidate | None:
    if kind == CandidateKind.EPIC:
        return draft.epic
    if kind == CandidateKind.ASSIGNEE:
        return draft.assignee
    return draft.sprint


def expected_kind(state: ConversationState) -> CandidateKind:
    if state == ConversationState.RESOLVING_EPIC:
        return CandidateKind.EPIC
    if state == ConversationState.RESOLVING_ASSIGNEE:
        return CandidateKind.ASSIGNEE
    if state == ConversationState.RESOLVING_ISSUE_UPDATE:
        return CandidateKind.ISSUE
    return CandidateKind.SPRINT


def candidate_by_answer(text: str, candidates: tuple[Candidate, ...]) -> Candidate | None:
    if text.isdigit():
        index = int(text) - 1
        if 0 <= index < len(candidates):
            return candidates[index]

    ranked = rank_candidates(text, candidates, limit=1)
    if ranked and ranked[0].score >= 0.85:
        return ranked[0]
    return None


def candidate_for_automatic_selection(
    kind: CandidateKind,
    candidates: tuple[Candidate, ...],
    *,
    used_default_query: bool,
) -> Candidate | None:
    if not candidates:
        return None

    if kind == CandidateKind.SPRINT and used_default_query:
        active_sprints = [candidate for candidate in candidates if is_active_sprint(candidate)]
        if len(active_sprints) == 1:
            return active_sprints[0]

    top_candidate = candidates[0]
    second_score = candidates[1].score if len(candidates) > 1 else 0
    if top_candidate.score >= 0.85 and top_candidate.score - second_score >= 0.15:
        return top_candidate

    return None


def is_active_sprint(candidate: Candidate) -> bool:
    return (candidate.key or "").casefold() == "active"


def kind_label(kind: CandidateKind) -> str:
    if kind == CandidateKind.EPIC:
        return "эпик"
    if kind == CandidateKind.ASSIGNEE:
        return "исполнителя"
    if kind == CandidateKind.ISSUE:
        return "задачу"
    return "спринт"


def format_candidates(title: str, candidates: tuple[Candidate, ...]) -> str:
    lines = [title]
    lines.extend(f"{index}. {candidate.display_name}" for index, candidate in enumerate(candidates, start=1))
    return "\n".join(lines)


def format_confirmation(draft: IssueDraft) -> str:
    lines = [
        "Проверьте задачу:",
        f"Название: {draft.summary}",
        f"Эпик: {draft.epic.display_name if draft.epic else 'не выбран'}",
        f"Исполнитель: {draft.assignee.display_name if draft.assignee else 'не выбран'}",
        f"Спринт: {draft.sprint.display_name if draft.sprint else 'не выбран'}",
        f"Estimate: {format_estimate(draft.estimate)}",
    ]
    if draft.description:
        lines.append(f"Description: {format_description(draft.description)}")
    lines.extend(["", "Создать задачу? Ответьте «да» или «нет»."])
    return "\n".join(lines)


def format_batch_confirmation(drafts: tuple[IssueDraft, ...]) -> str:
    lines = ["Проверьте задачи:"]
    for index, draft in enumerate(drafts, start=1):
        lines.append(
            f"{index}. {draft.summary} — Estimate: {format_estimate(draft.estimate)} — "
            f"Исполнитель: {draft.assignee.display_name if draft.assignee else 'не выбран'} — "
            f"Спринт: {draft.sprint.display_name if draft.sprint else 'не выбран'}"
        )
        if draft.description:
            lines.append(f"   Description: {format_description(draft.description)}")
    lines.extend(["", f"Создать {len(drafts)} задачи? Ответьте «да» или «нет»."])
    return "\n".join(lines)


def format_created_issue(issue: CreatedIssue) -> str:
    return f"Готово: {issue.key}\n{issue.url}"


def format_created_batch(issues: tuple[CreatedIssue, ...]) -> str:
    lines = [f"Готово, создал задач: {len(issues)}"]
    lines.extend(f"{index}. {issue.key} — {issue.url}" for index, issue in enumerate(issues, start=1))
    return "\n".join(lines)


def format_updated_issue(issue: UpdatedIssue) -> str:
    return f"Готово: {issue.message}\n{issue.url}"


def format_estimate(estimate: float | None) -> str:
    if estimate is None:
        return "не указан"
    numeric_estimate = float(estimate)
    if numeric_estimate.is_integer():
        return str(int(numeric_estimate))
    return str(numeric_estimate).rstrip("0").rstrip(".")


def format_description(description: str) -> str:
    return truncate_text(description, limit=500)


def truncate_text(text: str, *, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def is_cancel(text: str) -> bool:
    return text.casefold() in {"/cancel", "отмена", "отменить", "отмени", "стоп"}


def is_positive(text: str) -> bool:
    return text.casefold() in {"да", "ага", "ок", "создать", "yes", "y"}


def is_negative(text: str) -> bool:
    return text.casefold() in {"нет", "не", "no", "n", "отмена"}
