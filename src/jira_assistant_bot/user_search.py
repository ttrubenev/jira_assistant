from __future__ import annotations

import re
from typing import Iterable

from .domain import Candidate


def assignee_search_queries(query: str) -> tuple[str, ...]:
    normalized_query = " ".join(query.split())
    if not normalized_query:
        return ()

    no_yo_query = normalized_query.replace("ё", "е").replace("Ё", "Е")
    queries: list[str] = [normalized_query, no_yo_query]
    for token_set in [normalized_query.split(), no_yo_query.split()]:
        queries.extend(token_set)
        queries.extend(nominative_person_token(token) for token in token_set)
        if len(token_set) >= 2:
            queries.append(" ".join([nominative_person_token(token_set[0]), *token_set[1:]]))
            queries.append(" ".join([token_set[1], nominative_person_token(token_set[0])]))

    return tuple(unique_strings(query for query in queries if query))


def nominative_person_token(value: str) -> str:
    lowered = value.casefold().replace("ё", "е")
    if lowered.endswith(("ева", "ова")):
        return value[:-1]
    if lowered.endswith("ина"):
        return value[:-1]
    if lowered.endswith("ича"):
        return value[:-1]
    if lowered.endswith("а") and len(value) > 4:
        return value[:-1]
    return value


def unique_strings(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return tuple(result)


def unique_candidates(candidates: Iterable[Candidate]) -> tuple[Candidate, ...]:
    seen: set[str] = set()
    result: list[Candidate] = []
    for candidate in candidates:
        key = candidate.key or candidate.email or candidate.id
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return tuple(result)


def strip_html(value: str) -> str:
    return " ".join(part for part in re.sub(r"<[^>]+>", " ", value).split())
