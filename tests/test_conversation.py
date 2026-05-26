import unittest

from jira_assistant_bot.conversation import ConversationDefaults, ConversationManager
from jira_assistant_bot.domain import Candidate, CandidateKind, CreatedIssue, IssueDraft, UpdatedIssue


class FakeJira:
    def __init__(self) -> None:
        self.created: list[IssueDraft] = []

    async def search_epics(self, query: str) -> tuple[Candidate, ...]:
        return (
            Candidate(id="EPIC-1", key="EPIC-1", name="Мобильный профиль клиента", kind=CandidateKind.EPIC),
            Candidate(id="EPIC-2", key="EPIC-2", name="Платежи", kind=CandidateKind.EPIC),
        )

    async def search_assignees(self, query: str) -> tuple[Candidate, ...]:
        return (
            Candidate(
                id="ivanov",
                key="ivanov",
                name="Иванов Иван",
                email="ivanov@example.local",
                kind=CandidateKind.ASSIGNEE,
            ),
        )

    async def search_sprints(self, query: str) -> tuple[Candidate, ...]:
        return (
            Candidate(id="41", name="Product Team 24.6", kind=CandidateKind.SPRINT),
            Candidate(id="42", name="[ABC:TEAM] 18.05-29.05", kind=CandidateKind.SPRINT, key="active"),
            Candidate(id="43", name="[ABC:TEAM] 01.06-12.06", kind=CandidateKind.SPRINT, key="future"),
        )

    async def search_issues(self, query: str) -> tuple[Candidate, ...]:
        return (
            Candidate(id="ABC-1", key="ABC-1", name="Тестовая форма", kind=CandidateKind.ISSUE),
            Candidate(id="ABC-2", key="ABC-2", name="Тестовый экран", kind=CandidateKind.ISSUE),
        )

    async def create_issue(self, draft: IssueDraft) -> CreatedIssue:
        self.created.append(draft)
        key = f"ABC-{122 + len(self.created)}"
        return CreatedIssue(key=key, url=f"https://jira.example.local/browse/{key}")

    async def update_issue_estimate(self, issue_key: str, estimate: float) -> UpdatedIssue:
        return UpdatedIssue(
            key=issue_key,
            url=f"https://jira.example.local/browse/{issue_key}",
            message=f"Story Points обновлены: {int(estimate)}",
        )


class ConversationTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_flow_with_confirmation(self) -> None:
        manager = ConversationManager(FakeJira())

        replies = await manager.handle_text(
            10,
            "Создай задачу: проверить историю. Эпик профиль, На Иванов, Спринт Product Team 24.6",
        )
        self.assertIn("Проверьте задачу", replies[0].text)

        replies = await manager.handle_text(10, "да")

        self.assertIn("ABC-123", replies[0].text)

    async def test_uses_default_epic_and_active_sprint(self) -> None:
        manager = ConversationManager(
            FakeJira(),
            defaults=ConversationDefaults(
                epic=Candidate(
                    id="ABC-456",
                    key="ABC-456",
                    name="Default Epic",
                    kind=CandidateKind.EPIC,
                ),
                sprint_query="[ABC:TEAM]",
            ),
        )

        replies = await manager.handle_text(10, "Создай задачу: проверить анкету. На Иванов")

        self.assertIn("Default Epic", replies[0].text)
        self.assertIn("[ABC:TEAM] 18.05-29.05", replies[0].text)

    async def test_uses_default_assignee(self) -> None:
        manager = ConversationManager(
            FakeJira(),
            defaults=ConversationDefaults(
                epic=Candidate(
                    id="ABC-456",
                    key="ABC-456",
                    name="Default Epic",
                    kind=CandidateKind.EPIC,
                ),
                assignee=Candidate(
                    id="user_key",
                    key="user_key",
                    name="Иванов Иван Иванович",
                    email="ivanov@example.local",
                    kind=CandidateKind.ASSIGNEE,
                ),
                sprint_query="[ABC:TEAM]",
            ),
        )

        replies = await manager.handle_text(10, "Создай задачу: проверить анкету")

        self.assertIn("Иванов Иван Иванович", replies[0].text)
        self.assertIn("user_key", replies[0].text)

    async def test_confirmation_shows_description(self) -> None:
        manager = ConversationManager(
            FakeJira(),
            defaults=ConversationDefaults(
                epic=Candidate(
                    id="ABC-456",
                    key="ABC-456",
                    name="Default Epic",
                    kind=CandidateKind.EPIC,
                ),
                assignee=Candidate(
                    id="user_key",
                    key="user_key",
                    name="Иванов Иван Иванович",
                    email="ivanov@example.local",
                    kind=CandidateKind.ASSIGNEE,
                ),
                sprint_query="[ABC:TEAM]",
            ),
        )

        replies = await manager.handle_text(
            10,
            "Создай задачу: тест. Описание Создать окно подтверждения.",
        )

        self.assertIn("Description: Создать окно подтверждения.", replies[0].text)

    async def test_cancel_resets_session(self) -> None:
        manager = ConversationManager(FakeJira())

        await manager.handle_text(10, "Создай задачу: проверить историю")
        replies = await manager.handle_text(10, "/cancel")

        self.assertEqual(replies[0].text, "Ок, отменил создание задачи.")

    async def test_cancel_button_text_resets_session(self) -> None:
        manager = ConversationManager(FakeJira())

        await manager.handle_text(10, "Создай задачу: проверить историю")
        replies = await manager.handle_text(10, "Отменить")

        self.assertEqual(replies[0].text, "Ок, отменил создание задачи.")

    async def test_negative_confirmation_cancels_issue_creation(self) -> None:
        manager = ConversationManager(FakeJira())

        await manager.handle_text(
            10,
            "Создай задачу: проверить историю. Эпик профиль, На Иванов, Спринт Product Team 24.6",
        )
        replies = await manager.handle_text(10, "Нет")

        self.assertEqual(replies[0].text, "Ок, отменил создание задачи.")

    async def test_new_create_command_replaces_pending_confirmation(self) -> None:
        manager = ConversationManager(
            FakeJira(),
            defaults=ConversationDefaults(
                epic=Candidate(id="ABC-456", key="ABC-456", name="Default Epic", kind=CandidateKind.EPIC),
                assignee=Candidate(id="user_key", key="user_key", name="Иванов Иван", kind=CandidateKind.ASSIGNEE),
                sprint_query="[ABC:TEAM]",
            ),
        )

        await manager.handle_text(10, "Создай задачу: старая задача. оценка 1")
        replies = await manager.handle_text(
            10,
            "Заведи задачу Адресная заявка с оценкой 2 на Иванов с описание Создать дизайн.",
        )

        self.assertIn("Проверьте задачу", replies[0].text)
        self.assertIn("Название: Адресная заявка", replies[0].text)
        self.assertIn("Исполнитель: Иванов Иван", replies[0].text)
        self.assertIn("Estimate: 2", replies[0].text)
        self.assertIn("Description: Создать дизайн.", replies[0].text)

    async def test_invalid_confirmation_answer_repeats_full_confirmation(self) -> None:
        manager = ConversationManager(
            FakeJira(),
            defaults=ConversationDefaults(
                epic=Candidate(id="ABC-456", key="ABC-456", name="Default Epic", kind=CandidateKind.EPIC),
                assignee=Candidate(id="user_key", key="user_key", name="Иванов Иван", kind=CandidateKind.ASSIGNEE),
                sprint_query="[ABC:TEAM]",
            ),
        )

        await manager.handle_text(10, "Создай задачу: проверить историю. оценка 1")
        replies = await manager.handle_text(10, "не понял")

        self.assertIn("Проверьте задачу", replies[0].text)
        self.assertIn("Название: проверить историю", replies[0].text)

    async def test_updates_existing_issue_estimate(self) -> None:
        manager = ConversationManager(FakeJira())

        replies = await manager.handle_text(10, "Измени ABC-12345 Estimate 5")

        self.assertIn("Story Points обновлены: 5", replies[0].text)
        self.assertIn("ABC-12345", replies[0].text)

    async def test_updates_issue_estimate_by_title_after_choice(self) -> None:
        manager = ConversationManager(FakeJira())

        replies = await manager.handle_text(10, "Измени задачу тест Estimate 5")
        self.assertIn("Нашел похожие задачи", replies[0].text)
        self.assertIn("ABC-1", replies[0].text)

        replies = await manager.handle_text(10, "1")
        self.assertIn("Story Points обновлены: 5", replies[0].text)
        self.assertIn("ABC-1", replies[0].text)

    async def test_creates_batch_with_defaults(self) -> None:
        jira = FakeJira()
        manager = ConversationManager(
            jira,
            defaults=ConversationDefaults(
                epic=Candidate(
                    id="ABC-456",
                    key="ABC-456",
                    name="Default Epic",
                    kind=CandidateKind.EPIC,
                ),
                assignee=Candidate(
                    id="user_key",
                    key="user_key",
                    name="Иванов Иван Иванович",
                    email="ivanov@example.local",
                    kind=CandidateKind.ASSIGNEE,
                ),
                sprint_query="[ABC:TEAM]",
            ),
        )

        replies = await manager.handle_text(10, "Создай задачи: тест1. оценка 2. задача тест2. оценка 1.")
        self.assertIn("Проверьте задачи", replies[0].text)
        self.assertIn("тест1", replies[0].text)
        self.assertIn("тест2", replies[0].text)
        self.assertIn("Иванов Иван Иванович", replies[0].text)

        replies = await manager.handle_text(10, "да")

        self.assertEqual(len(jira.created), 2)
        self.assertIn("ABC-123", replies[0].text)
        self.assertIn("ABC-124", replies[0].text)

    async def test_batch_confirmation_shows_description(self) -> None:
        manager = ConversationManager(
            FakeJira(),
            defaults=ConversationDefaults(
                epic=Candidate(
                    id="ABC-456",
                    key="ABC-456",
                    name="Default Epic",
                    kind=CandidateKind.EPIC,
                ),
                assignee=Candidate(
                    id="user_key",
                    key="user_key",
                    name="Иванов Иван Иванович",
                    email="ivanov@example.local",
                    kind=CandidateKind.ASSIGNEE,
                ),
                sprint_query="[ABC:TEAM]",
            ),
        )

        replies = await manager.handle_text(
            10,
            "Создай задачи: тест1. Описание первое описание. задача тест2. оценка 1.",
        )

        self.assertIn("Description: первое описание.", replies[0].text)

    async def test_negative_batch_confirmation_cancels_issue_creation(self) -> None:
        jira = FakeJira()
        manager = ConversationManager(
            jira,
            defaults=ConversationDefaults(
                epic=Candidate(
                    id="ABC-456",
                    key="ABC-456",
                    name="Default Epic",
                    kind=CandidateKind.EPIC,
                ),
                assignee=Candidate(
                    id="user_key",
                    key="user_key",
                    name="Иванов Иван Иванович",
                    email="ivanov@example.local",
                    kind=CandidateKind.ASSIGNEE,
                ),
                sprint_query="[ABC:TEAM]",
            ),
        )

        await manager.handle_text(10, "Создай задачи: тест1. оценка 2. задача тест2. оценка 1.")
        replies = await manager.handle_text(10, "Нет")

        self.assertEqual(replies[0].text, "Ок, отменил создание задач.")
        self.assertEqual(jira.created, [])


if __name__ == "__main__":
    unittest.main()
