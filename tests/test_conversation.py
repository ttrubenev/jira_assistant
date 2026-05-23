import unittest

from alfa_jira_bot.conversation import ConversationDefaults, ConversationManager
from alfa_jira_bot.domain import Candidate, CandidateKind, CreatedIssue, IssueDraft, UpdatedIssue


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
            Candidate(id="41", name="Alfa Mobile 24.6", kind=CandidateKind.SPRINT),
            Candidate(id="42", name="[DFA:STORM] 18.05-29.05", kind=CandidateKind.SPRINT, key="active"),
            Candidate(id="43", name="[DFA:STORM] 01.06-12.06", kind=CandidateKind.SPRINT, key="future"),
        )

    async def search_issues(self, query: str) -> tuple[Candidate, ...]:
        return (
            Candidate(id="DFA-1", key="DFA-1", name="Тестовая форма", kind=CandidateKind.ISSUE),
            Candidate(id="DFA-2", key="DFA-2", name="Тестовый экран", kind=CandidateKind.ISSUE),
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
            "Создай задачу: проверить историю. Эпик профиль, На Иванов, Спринт Alfa Mobile 24.6",
        )
        self.assertIn("Проверьте задачу", replies[0].text)

        replies = await manager.handle_text(10, "да")

        self.assertIn("ABC-123", replies[0].text)

    async def test_uses_default_epic_and_active_sprint(self) -> None:
        manager = ConversationManager(
            FakeJira(),
            defaults=ConversationDefaults(
                epic=Candidate(
                    id="DFA-33230",
                    key="DFA-33230",
                    name="[Q2-Q4_26ЦФА] Мелкие доработки 2026",
                    kind=CandidateKind.EPIC,
                ),
                sprint_query="[DFA:STORM]",
            ),
        )

        replies = await manager.handle_text(10, "Создай задачу: проверить анкету. На Иванов")

        self.assertIn("[Q2-Q4_26ЦФА] Мелкие доработки 2026", replies[0].text)
        self.assertIn("[DFA:STORM] 18.05-29.05", replies[0].text)

    async def test_uses_default_assignee(self) -> None:
        manager = ConversationManager(
            FakeJira(),
            defaults=ConversationDefaults(
                epic=Candidate(
                    id="DFA-33230",
                    key="DFA-33230",
                    name="[Q2-Q4_26ЦФА] Мелкие доработки 2026",
                    kind=CandidateKind.EPIC,
                ),
                assignee=Candidate(
                    id="U_M28HF",
                    key="U_M28HF",
                    name="Трубенёв Тимофей Александрович",
                    email="TTrubenev@alfabank.ru",
                    kind=CandidateKind.ASSIGNEE,
                ),
                sprint_query="[DFA:STORM]",
            ),
        )

        replies = await manager.handle_text(10, "Создай задачу: проверить анкету")

        self.assertIn("Трубенёв Тимофей Александрович", replies[0].text)
        self.assertIn("U_M28HF", replies[0].text)

    async def test_cancel_resets_session(self) -> None:
        manager = ConversationManager(FakeJira())

        await manager.handle_text(10, "Создай задачу: проверить историю")
        replies = await manager.handle_text(10, "/cancel")

        self.assertEqual(replies[0].text, "Ок, отменил создание задачи.")

    async def test_updates_existing_issue_estimate(self) -> None:
        manager = ConversationManager(FakeJira())

        replies = await manager.handle_text(10, "Измени DFA-12345 Estimate 5")

        self.assertIn("Story Points обновлены: 5", replies[0].text)
        self.assertIn("DFA-12345", replies[0].text)

    async def test_updates_issue_estimate_by_title_after_choice(self) -> None:
        manager = ConversationManager(FakeJira())

        replies = await manager.handle_text(10, "Измени задачу тест Estimate 5")
        self.assertIn("Нашел похожие задачи", replies[0].text)
        self.assertIn("DFA-1", replies[0].text)

        replies = await manager.handle_text(10, "1")
        self.assertIn("Story Points обновлены: 5", replies[0].text)
        self.assertIn("DFA-1", replies[0].text)

    async def test_creates_batch_with_defaults(self) -> None:
        jira = FakeJira()
        manager = ConversationManager(
            jira,
            defaults=ConversationDefaults(
                epic=Candidate(
                    id="DFA-33230",
                    key="DFA-33230",
                    name="[Q2-Q4_26ЦФА] Мелкие доработки 2026",
                    kind=CandidateKind.EPIC,
                ),
                assignee=Candidate(
                    id="U_M28HF",
                    key="U_M28HF",
                    name="Трубенёв Тимофей Александрович",
                    email="TTrubenev@alfabank.ru",
                    kind=CandidateKind.ASSIGNEE,
                ),
                sprint_query="[DFA:STORM]",
            ),
        )

        replies = await manager.handle_text(10, "Создай задачи: тест1. оценка 2. задача тест2. оценка 1.")
        self.assertIn("Проверьте задачи", replies[0].text)
        self.assertIn("тест1", replies[0].text)
        self.assertIn("тест2", replies[0].text)
        self.assertIn("Трубенёв Тимофей Александрович", replies[0].text)

        replies = await manager.handle_text(10, "да")

        self.assertEqual(len(jira.created), 2)
        self.assertIn("ABC-123", replies[0].text)
        self.assertIn("ABC-124", replies[0].text)


if __name__ == "__main__":
    unittest.main()
