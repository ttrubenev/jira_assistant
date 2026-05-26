from __future__ import annotations

from dataclasses import dataclass
import re

from .domain import IssueDraft


@dataclass(frozen=True)
class ParsedMessage:
    summary: str
    description: str
    epic_query: str | None
    assignee_query: str | None
    sprint_query: str | None
    estimate: float | None

    def to_draft(self) -> IssueDraft:
        return IssueDraft(
            summary=self.summary,
            description=self.description,
            epic_query=self.epic_query,
            assignee_query=self.assignee_query,
            sprint_query=self.sprint_query,
            estimate=self.estimate,
        )


@dataclass(frozen=True)
class ParsedIssueUpdate:
    issue_key: str | None
    issue_query: str | None
    estimate: float


FIELD_PATTERNS = {
    "epic_query": re.compile(
        r"(?:^|\n|\s)(?:эпик|эпике|epic)\s*:?\s*(?P<value>[^\n,;]+)",
        re.IGNORECASE,
    ),
    "assignee_query": re.compile(
        r"(?:^|\n|\s)(?:на|исполнитель|ответственный|assignee)\s*:?\s*(?P<value>[^\n,;]+)",
        re.IGNORECASE,
    ),
    "sprint_query": re.compile(
        r"(?:^|\n|\s)(?:спринт|спринте|sprint)\s*:?\s*(?P<value>[^\n,;]+)",
        re.IGNORECASE,
    ),
}

DESCRIPTION_PATTERN = re.compile(
    r"(?P<prefix>^|\n|[\s,;.!?])"
    r"(?:с\s+описани(?:ем|е)|описание|дискрипше?н|description|desc)"
    r"\s*:?\s*(?P<value>.+)$",
    re.IGNORECASE | re.DOTALL,
)
ESTIMATE_PATTERN = re.compile(
    r"(?P<prefix>^|\n|[\s,;])"
    r"(?:с\s+|со\s+)?"
    r"(?:estimate|est|оценк(?:а|ой|у|е|и)?|стори\s*поинт(?:ы|ов)?|story\s*points?|sp)"
    r"\s*:?\s*(?P<value>\d+(?:[.,]\d+)?)\b",
    re.IGNORECASE,
)
UPDATE_TRAILING_ESTIMATE_PATTERN = re.compile(
    r"(?P<prefix>^|\s)(?:на|в)\s*(?P<value>\d+(?:[.,]\d+)?)\b\s*$",
    re.IGNORECASE,
)

ISSUE_KEY_PATTERN = re.compile(r"\b(?P<key>[A-ZА-Я]+-\d+)\b", re.IGNORECASE)
UPDATE_COMMAND_PATTERN = re.compile(
    r"^\s*(?:измени|изменить|обнови|обновить|поставь|поставить|поменяй|поменять|установи|установить)\b",
    re.IGNORECASE,
)
UPDATE_FILLER_PATTERN = re.compile(
    r"\b(?:story\s*points?|стори\s*поинт(?:ы|ов)?|estimate|est|оценк(?:а|ой|у|е|и)?|sp|в|у|для|задач[аеуи]?)\b",
    re.IGNORECASE,
)

CREATE_PREFIX = re.compile(
    r"^\s*(?:создай|создать|заведи|завести|добавь|добавить)\s+(?:задач[ауи]?|таск[ауи]?|тикет)?\s*:?\s*",
    re.IGNORECASE,
)
BATCH_CREATE_PREFIX = re.compile(
    r"^\s*(?:создай|создать|заведи|завести|добавь|добавить)\s+(?:задачи|таски|тикеты)\s*:?\s*",
    re.IGNORECASE,
)
BATCH_ITEM_MARKER = re.compile(
    r"(?:(?<=^)|(?<=[.!?])\s+)(?:задач[ауи]?|таск[ауи]?|тикет)\s+",
    re.IGNORECASE,
)
BATCH_CONJUNCTION_MARKER = re.compile(
    r"\s+и\s+(?:задачу|задача|таску|таска|тикет)\s+",
    re.IGNORECASE,
)


def parse_issue_message(text: str) -> ParsedMessage:
    cleaned = normalize_whitespace(text)
    description, cleaned_without_description = extract_description(cleaned)
    estimate, cleaned_without_estimate = extract_estimate(cleaned_without_description)
    fields: dict[str, str | None] = {}
    summary_source = cleaned_without_estimate

    for field_name, pattern in FIELD_PATTERNS.items():
        match = pattern.search(cleaned_without_estimate)
        value = match.group("value").strip(" .") if match else None
        fields[field_name] = value or None
        if match:
            summary_source = summary_source.replace(match.group(0), " ")

    summary = extract_summary(summary_source)
    return ParsedMessage(
        summary=summary,
        description=description,
        epic_query=fields["epic_query"],
        assignee_query=fields["assignee_query"],
        sprint_query=fields["sprint_query"],
        estimate=estimate,
    )


def looks_like_issue_command(text: str) -> bool:
    cleaned = normalize_whitespace(text)
    return bool(
        CREATE_PREFIX.match(cleaned)
        or BATCH_CREATE_PREFIX.match(cleaned)
        or UPDATE_COMMAND_PATTERN.match(cleaned)
    )


def extract_description(text: str) -> tuple[str, str]:
    match = DESCRIPTION_PATTERN.search(text)
    if match is None:
        return "", text

    description = normalize_whitespace(match.group("value")).strip(" .")
    if description:
        description = ensure_sentence_punctuation(description)

    cleaned = normalize_whitespace(f"{text[: match.start()]}{match.group('prefix')}")
    return description, cleaned


def parse_issue_batch(text: str) -> tuple[ParsedMessage, ...]:
    cleaned = normalize_whitespace(text)
    match = BATCH_CREATE_PREFIX.match(cleaned)
    if match is not None:
        raw_items = split_batch_items(cleaned[match.end() :])
    else:
        generic_match = CREATE_PREFIX.match(cleaned)
        if generic_match is None:
            return ()
        raw_items = split_batch_items(cleaned[generic_match.end() :])

    if len(raw_items) < 2:
        return ()

    return tuple(parse_issue_message(f"Создай задачу: {item}") for item in raw_items)


def split_batch_items(text: str) -> tuple[str, ...]:
    body = normalize_whitespace(text).strip(" .")
    if not body:
        return ()

    markers = list(BATCH_ITEM_MARKER.finditer(body))
    if not markers:
        return split_batch_items_by_conjunction(body)

    return split_by_markers(body, markers)


def split_batch_items_by_conjunction(text: str) -> tuple[str, ...]:
    body = normalize_whitespace(text).strip(" .")
    markers = list(BATCH_CONJUNCTION_MARKER.finditer(body))
    if not markers:
        return ()

    return split_by_markers(body, markers)


def split_by_markers(body: str, markers: list[re.Match[str]]) -> tuple[str, ...]:
    items: list[str] = []
    first_item = body[: markers[0].start()].strip(" .")
    if first_item:
        items.append(first_item)

    for index, marker in enumerate(markers):
        start = marker.end()
        end = markers[index + 1].start() if index + 1 < len(markers) else len(body)
        item = body[start:end].strip(" .")
        if item:
            items.append(item)

    return tuple(items)


def parse_issue_update(text: str) -> ParsedIssueUpdate | None:
    cleaned = normalize_whitespace(text)
    key_match = ISSUE_KEY_PATTERN.search(cleaned)
    estimate, cleaned_without_estimate = extract_update_estimate(cleaned)
    if key_match is None or estimate is None:
        if estimate is None or UPDATE_COMMAND_PATTERN.search(cleaned) is None:
            return None

        issue_query = extract_issue_update_query(cleaned_without_estimate)
        if not issue_query:
            return None

        return ParsedIssueUpdate(
            issue_key=None,
            issue_query=issue_query,
            estimate=estimate,
        )

    return ParsedIssueUpdate(
        issue_key=key_match.group("key").upper(),
        issue_query=None,
        estimate=estimate,
    )


def extract_issue_update_query(text: str) -> str | None:
    without_command = UPDATE_COMMAND_PATTERN.sub("", text).strip(" .,:;")
    without_fillers = UPDATE_FILLER_PATTERN.sub(" ", without_command)
    query = normalize_whitespace(without_fillers).strip(" .,:;")
    if not query:
        return None
    return query


def extract_update_estimate(text: str) -> tuple[float | None, str]:
    estimate, cleaned_without_estimate = extract_estimate(text)
    if estimate is not None:
        return estimate, cleaned_without_estimate

    match = UPDATE_TRAILING_ESTIMATE_PATTERN.search(text)
    if match is None:
        return None, text

    value = float(match.group("value").replace(",", "."))

    def replace(match: re.Match[str]) -> str:
        return match.group("prefix")

    return value, normalize_whitespace(UPDATE_TRAILING_ESTIMATE_PATTERN.sub(replace, text, count=1))


def normalize_whitespace(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.strip().splitlines()]
    return "\n".join(line for line in lines if line)


def extract_summary(text: str) -> str:
    without_prefix = CREATE_PREFIX.sub("", normalize_whitespace(text)).strip(" .")
    first_sentence = re.split(r"(?<=[.!?])\s+", without_prefix, maxsplit=1)[0].strip(" .")
    if not first_sentence:
        return "Новая задача из Telegram"
    return truncate(first_sentence, limit=120)


def extract_estimate(text: str) -> tuple[float | None, str]:
    match = ESTIMATE_PATTERN.search(text)
    if match is None:
        return None, text

    value = float(match.group("value").replace(",", "."))

    def replace(match: re.Match[str]) -> str:
        return match.group("prefix")

    return value, normalize_whitespace(ESTIMATE_PATTERN.sub(replace, text, count=1))


def truncate(text: str, *, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def ensure_sentence_punctuation(text: str) -> str:
    if text.endswith((".", "!", "?")):
        return text
    return f"{text}."
