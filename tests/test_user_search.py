import unittest

from jira_assistant_bot.user_search import assignee_search_queries, nominative_person_token, strip_html


class UserSearchTests(unittest.TestCase):
    def test_builds_queries_for_russian_name_forms(self) -> None:
        queries = assignee_search_queries("Иванова Ивана Александровича")

        self.assertIn("Иванова Ивана Александровича", queries)
        self.assertIn("Иванов Ивана Александровича", queries)
        self.assertIn("Ивана Иванов", queries)

    def test_converts_common_person_tokens_to_nominative(self) -> None:
        self.assertEqual(nominative_person_token("Иванова"), "Иванов")
        self.assertEqual(nominative_person_token("Александровича"), "Александрович")

    def test_strips_jira_picker_html(self) -> None:
        self.assertEqual(strip_html("<b>Иванов</b> Иван"), "Иванов Иван")


if __name__ == "__main__":
    unittest.main()
