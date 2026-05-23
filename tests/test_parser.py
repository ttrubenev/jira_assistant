import unittest

from alfa_jira_bot.parser import parse_issue_batch, parse_issue_message, parse_issue_update


class ParserTests(unittest.TestCase):
    def test_parses_issue_fields(self) -> None:
        parsed = parse_issue_message(
            """
            Создай задачу: проверить историю операций после перевыпуска карты.
            Эпик мобильный профиль клиента
            На Иванова
            Спринт Alfa Mobile 24.6
            Estimate 3
            """
        )

        self.assertEqual(parsed.summary, "проверить историю операций после перевыпуска карты")
        self.assertEqual(parsed.epic_query, "мобильный профиль клиента")
        self.assertEqual(parsed.assignee_query, "Иванова")
        self.assertEqual(parsed.sprint_query, "Alfa Mobile 24.6")
        self.assertEqual(parsed.estimate, 3)
        self.assertEqual(parsed.description, "")

    def test_parses_estimate_without_polluting_assignee(self) -> None:
        parsed = parse_issue_message("Создай задачу: [design] тест. На Трубенёва Тимофей Estimate 0,5")

        self.assertEqual(parsed.summary, "[design] тест")
        self.assertEqual(parsed.assignee_query, "Трубенёва Тимофей")
        self.assertEqual(parsed.estimate, 0.5)

    def test_parses_issue_update_estimate(self) -> None:
        parsed = parse_issue_update("Измени DFA-12345 story points 5")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.issue_key, "DFA-12345")
        self.assertIsNone(parsed.issue_query)
        self.assertEqual(parsed.estimate, 5)

    def test_parses_issue_update_by_title(self) -> None:
        parsed = parse_issue_update("Измени задачу тестовая задача Estimate 3")

        self.assertIsNotNone(parsed)
        self.assertIsNone(parsed.issue_key)
        self.assertEqual(parsed.issue_query, "тестовая")
        self.assertEqual(parsed.estimate, 3)

    def test_parses_issue_update_with_russian_trailing_estimate(self) -> None:
        cases = [
            "измени в задаче тест оценку на 0.1",
            "измени оценку в задаче тест на 0.1",
            "измени оценку тест на 0.1",
        ]

        for text in cases:
            with self.subTest(text=text):
                parsed = parse_issue_update(text)

                self.assertIsNotNone(parsed)
                self.assertIsNone(parsed.issue_key)
                self.assertEqual(parsed.issue_query, "тест")
                self.assertEqual(parsed.estimate, 0.1)

    def test_parses_issue_batch(self) -> None:
        parsed = parse_issue_batch(
            "Создай задачи: тест1. На трубенёва. оценка 2. задача тест2. оценка 1. задача тест3. оценка 1."
        )

        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0].summary, "тест1")
        self.assertEqual(parsed[0].assignee_query, "трубенёва")
        self.assertEqual(parsed[0].estimate, 2)
        self.assertEqual(parsed[1].summary, "тест2")
        self.assertEqual(parsed[1].estimate, 1)
        self.assertEqual(parsed[2].summary, "тест3")
        self.assertEqual(parsed[2].estimate, 1)


if __name__ == "__main__":
    unittest.main()
