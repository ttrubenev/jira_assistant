from __future__ import annotations

from dataclasses import dataclass
import json

import httpx


class IntentInterpreter:
    async def interpret(self, text: str) -> str:
        raise NotImplementedError


class DisabledIntentInterpreter(IntentInterpreter):
    async def interpret(self, text: str) -> str:
        return text


@dataclass(frozen=True)
class OpenAIIntentInterpreter(IntentInterpreter):
    api_key: str
    model: str
    base_url: str = "https://api.openai.com"
    timeout: float = 30

    async def interpret(self, text: str) -> str:
        payload = {
            "model": self.model,
            "instructions": INTENT_INSTRUCTIONS,
            "input": text,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "jira_bot_intent",
                    "strict": True,
                    "schema": INTENT_SCHEMA,
                }
            },
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url.rstrip('/')}/v1/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()

        interpreted = parse_response_text(response.json())
        if not interpreted:
            return text

        data = json.loads(interpreted)
        canonical_text = str(data.get("canonical_text") or "").strip()
        if data.get("action") == "unknown" or not canonical_text:
            return text
        return canonical_text


def build_intent_interpreter(
    *,
    enabled: bool,
    api_key: str | None,
    model: str,
    base_url: str,
) -> IntentInterpreter:
    if not enabled or not api_key:
        return DisabledIntentInterpreter()
    return OpenAIIntentInterpreter(api_key=api_key, model=model, base_url=base_url)


def parse_response_text(payload: dict) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return output_text.strip()

    for output_item in payload.get("output", []):
        for content_item in output_item.get("content", []):
            text = content_item.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return ""


INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "action": {
            "type": "string",
            "enum": ["create_issue", "create_many_issues", "update_estimate", "unknown"],
        },
        "canonical_text": {
            "type": "string",
            "description": "A Russian command that the existing Jira Telegram bot parser can understand.",
        },
    },
    "required": ["action", "canonical_text"],
}


INTENT_INSTRUCTIONS = """
You normalize Russian Telegram messages for a Jira bot.

Return only JSON matching the schema.

The bot already understands these canonical commands:
- Create one issue: "Создай задачу: <summary>. Эпик <epic>. На <assignee>. Спринт <sprint>. Estimate <number>"
- Create many issues: "Создай задачи: <summary>. оценка <number>. задача <summary>. оценка <number>."
- Update story points by issue key: "Измени <KEY> Estimate <number>"
- Update story points by title: "Измени задачу <title> Estimate <number>"

Rules:
- Preserve user-provided names, Jira keys, epic names, sprint names, and estimates.
- If assignee, epic, or sprint are absent, omit that part. The bot has defaults.
- Use dot as decimal separator in estimates.
- For casual Russian words like "закинь", "создай", "заведи", infer create_issue.
- For "оцени", "поставь оценку", "стори поинты", infer update_estimate if the user refers to an existing task; infer create_issue if the user asks to create a task.
- If intent is unclear, return action "unknown" and canonical_text "".

Examples:
User: "закинь тест формы на Иванова на два поинта"
{"action":"create_issue","canonical_text":"Создай задачу: тест формы. На Иванова. Estimate 2"}

User: "поменяй тестовая форма на 0,5"
{"action":"update_estimate","canonical_text":"Измени задачу тестовая форма Estimate 0.5"}

User: "создай три задачи тест1 на 2 тест2 на 1 тест3 на 1"
{"action":"create_many_issues","canonical_text":"Создай задачи: тест1. оценка 2. задача тест2. оценка 1. задача тест3. оценка 1."}
""".strip()
