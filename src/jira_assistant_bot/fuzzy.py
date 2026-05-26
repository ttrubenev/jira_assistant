from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Iterable

from .domain import Candidate


def normalize_text(value: str) -> str:
    lowered = value.casefold().replace("ё", "е")
    return " ".join(re.findall(r"[a-zа-я0-9]+", lowered))


def score_text(query: str, value: str) -> float:
    normalized_query = normalize_text(query)
    normalized_value = normalize_text(value)
    if not normalized_query or not normalized_value:
        return 0

    if normalized_query == normalized_value:
        return 1
    if normalized_query in normalized_value:
        return 0.92

    query_tokens = set(normalized_query.split())
    value_tokens = set(normalized_value.split())
    token_score = len(query_tokens & value_tokens) / max(len(query_tokens), 1)
    ratio = SequenceMatcher(None, normalized_query, normalized_value).ratio()
    return max(token_score * 0.9, ratio)


def rank_candidates(query: str, candidates: Iterable[Candidate], *, limit: int = 5) -> tuple[Candidate, ...]:
    ranked = [
        Candidate(
            id=candidate.id,
            name=candidate.name,
            kind=candidate.kind,
            key=candidate.key,
            email=candidate.email,
            score=score_text(query, searchable_text(candidate)),
        )
        for candidate in candidates
    ]
    ranked.sort(key=lambda candidate: candidate.score, reverse=True)
    return tuple(candidate for candidate in ranked[:limit] if candidate.score > 0.25)


def searchable_text(candidate: Candidate) -> str:
    return " ".join(value for value in [candidate.name, candidate.key, candidate.email] if value)
