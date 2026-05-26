from __future__ import annotations

from dataclasses import dataclass
import asyncio
import json
from pathlib import Path
import shlex

import httpx


class VoiceTranscriber:
    async def transcribe(self, path: Path) -> str:
        raise NotImplementedError


class DisabledTranscriber(VoiceTranscriber):
    async def transcribe(self, path: Path) -> str:
        raise RuntimeError("Voice transcription is not configured")


@dataclass(frozen=True)
class CommandTranscriber(VoiceTranscriber):
    command: str

    async def transcribe(self, path: Path) -> str:
        args = [*shlex.split(self.command), str(path)]
        if not args:
            raise RuntimeError("Voice transcription command is empty")

        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            error = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(error or "Voice transcription failed")

        text = stdout.decode("utf-8", errors="replace").strip()
        if not text:
            raise RuntimeError("Voice transcription returned empty text")
        return text


@dataclass(frozen=True)
class OpenAITranscriber(VoiceTranscriber):
    api_key: str
    model: str
    base_url: str = "https://api.openai.com"
    timeout: float = 60

    async def transcribe(self, path: Path) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            with path.open("rb") as audio_file:
                response = await client.post(
                    f"{self.base_url.rstrip('/')}/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data={
                        "model": self.model,
                        "response_format": "json",
                        "language": "ru",
                        "prompt": "Telegram voice message about Jira tasks, epics, sprints, assignees, and Story Points.",
                    },
                    files={"file": (path.name, audio_file, "audio/ogg")},
                )
                if response.status_code == 429:
                    raise RuntimeError("OpenAI временно ограничил запросы. Попробуйте позже или проверьте лимиты/баланс API.")
                if response.status_code in {401, 403}:
                    raise RuntimeError("OpenAI не принял API key или permissions. Проверьте ключ и доступ к audio transcriptions.")
                if response.status_code >= 400:
                    raise RuntimeError(f"OpenAI transcription вернул HTTP {response.status_code}: {extract_openai_error(response)}")

        text = parse_transcription_text(response.text)
        if not text:
            raise RuntimeError("Voice transcription returned empty text")
        return text


def build_transcriber(
    *,
    provider: str,
    command: str | None,
    openai_api_key: str | None,
    openai_base_url: str,
    openai_model: str,
) -> VoiceTranscriber:
    if provider == "openai" and openai_api_key:
        return OpenAITranscriber(
            api_key=openai_api_key,
            base_url=openai_base_url,
            model=openai_model,
        )
    if command:
        return CommandTranscriber(command=command)
    return DisabledTranscriber()


def parse_transcription_text(raw_response: str) -> str:
    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError:
        return raw_response.strip()
    return str(data.get("text") or "").strip()


def extract_openai_error(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text.strip()[:300]

    error = data.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str):
            return message[:300]
    return response.text.strip()[:300]
