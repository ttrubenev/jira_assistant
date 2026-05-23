import unittest

from alfa_jira_bot.user_search import assignee_search_queries, nominative_person_token, strip_html


class UserSearchTests(unittest.TestCase):
    def test_builds_queries_for_russian_name_forms(self) -> None:
        queries = assignee_search_queries("Трубенёва Тимофей Александрович")

        self.assertIn("Трубенёва Тимофей Александрович", queries)
        self.assertIn("Трубенев Тимофей Александрович", queries)
        self.assertIn("Трубенёв Тимофей Александрович", queries)
        self.assertIn("Тимофей Трубенёв", queries)

    def test_converts_common_person_tokens_to_nominative(self) -> None:
        self.assertEqual(nominative_person_token("Иванова"), "Иванов")
        self.assertEqual(nominative_person_token("Трубенёва"), "Трубенёв")
        self.assertEqual(nominative_person_token("Александровича"), "Александрович")

    def test_strips_jira_picker_html(self) -> None:
        self.assertEqual(strip_html("<b>Трубенёв</b> Тимофей"), "Трубенёв Тимофей")


if __name__ == "__main__":
    unittest.main()
