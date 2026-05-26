import unittest

from jira_assistant_bot.conversation import ConversationDefaults, ConversationManager
from jira_assistant_bot.domain import Candidate, CandidateKind, CreatedIssue, IssueDraft, UpdatedIssue
from jira_assistant_bot.telegram_app import (
    asks_for_confirmation,
    help_text,
    interpret_if_idle,
    is_cancelled_reply,
    is_completed_reply,
)


class FakeInterpreter:
    def __init__(self, interpreted_text: str) -> None:
        self.interpreted_text = interpreted_text
        self.calls: list[str] = []

    async def interpret(self, text: str) -> str:
        self.calls.append(text)
        return self.interpreted_text


class FailingInterpreter:
    async def interpret(self, text: str) -> str:
        raise RuntimeError("AI is unavailable")


class FakeJira:
    async def search_epics(self, query: str) -> tuple[Candidate, ...]:
        return ()

    async def search_assignees(self, query: str) -> tuple[Candidate, ...]:
        return ()

    async def search_sprints(self, query: str) -> tuple[Candidate, ...]:
        return (Candidate(id="42", name="[ABC:TEAM] 18.05-29.05", kind=CandidateKind.SPRINT, key="active"),)

    async def search_issues(self, query: str) -> tuple[Candidate, ...]:
        return ()

    async def create_issue(self, draft: IssueDraft) -> CreatedIssue:
        return CreatedIssue(key="ABC-123", url="https://jira.example.local/browse/ABC-123")

    async def update_issue_estimate(self, issue_key: str, estimate: float) -> UpdatedIssue:
        return UpdatedIssue(key=issue_key, url="", message="")


class TelegramAppTests(unittest.IsolatedAsyncioTestCase):
    def test_detects_confirmation_reply(self) -> None:
        self.assertTrue(asks_for_confirmation("Создать задачу? Ответьте «да» или «нет»."))
        self.assertFalse(asks_for_confirmation("Ок, отменил создание задачи."))

    def test_detects_cancelled_reply(self) -> None:
        self.assertTrue(is_cancelled_reply("Ок, отменил создание задачи."))
        self.assertFalse(is_cancelled_reply("Проверьте задачу:"))

    def test_detects_completed_reply(self) -> None:
        self.assertTrue(is_completed_reply("Готово: ABC-1"))
        self.assertTrue(is_completed_reply("Готово, создал задач: 2"))
        self.assertFalse(is_completed_reply("Проверьте задачу:"))

    def test_help_text_contains_examples_and_commands(self) -> None:
        text = help_text()

        self.assertIn("Что умеет бот", text)
        self.assertIn("Заведи тикет", text)
        self.assertIn("Заведи задачи", text)
        self.assertIn("Измени ABC-123", text)
        self.assertIn("/help", text)
        self.assertIn("/cancel", text)

    async def test_interprets_only_idle_conversations(self) -> None:
        manager = ConversationManager(
            FakeJira(),
            defaults=ConversationDefaults(
                epic=Candidate(id="ABC-456", key="ABC-456", name="Default Epic", kind=CandidateKind.EPIC),
                assignee=Candidate(id="user_key", key="user_key", name="Иванов Иван", kind=CandidateKind.ASSIGNEE),
                sprint_query="[ABC:TEAM]",
            ),
        )
        interpreter = FakeInterpreter("Создай задачу: тест. Estimate 1")

        text = await interpret_if_idle(manager, interpreter, 10, "закинь тест на один поинт")

        self.assertEqual(text, "Создай задачу: тест. Estimate 1")
        self.assertEqual(interpreter.calls, ["закинь тест на один поинт"])

        await manager.handle_text(10, text)
        confirmation_answer = await interpret_if_idle(manager, interpreter, 10, "да")

        self.assertEqual(confirmation_answer, "да")
        self.assertEqual(interpreter.calls, ["закинь тест на один поинт"])

    async def test_interpreter_failure_falls_back_to_original_text(self) -> None:
        manager = ConversationManager(FakeJira())

        text = await interpret_if_idle(manager, FailingInterpreter(), 10, "создай задачу тест")

        self.assertEqual(text, "создай задачу тест")


if __name__ == "__main__":
    unittest.main()
