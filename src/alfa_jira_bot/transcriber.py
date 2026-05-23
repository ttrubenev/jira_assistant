from __future__ import annotations

from dataclasses import dataclass
import asyncio
from pathlib import Path
import shlex


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


def build_transcriber(command: str | None) -> VoiceTranscriber:
    if command:
        return CommandTranscriber(command=command)
    return DisabledTranscriber()
