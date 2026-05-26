import unittest

from jira_assistant_bot.domain import Candidate, CandidateKind
from jira_assistant_bot.fuzzy import rank_candidates, score_text


class FuzzyTests(unittest.TestCase):
    def test_scores_exact_match_highest(self) -> None:
        self.assertEqual(score_text("Мобильный профиль", "мобильный профиль"), 1)

    def test_ranks_candidates_by_name_key_and_email(self) -> None:
        candidates = (
            Candidate(id="1", name="Платежи", kind=CandidateKind.EPIC, key="PAY-1"),
            Candidate(id="2", name="Мобильный профиль клиента", kind=CandidateKind.EPIC, key="MOB-2"),
        )

        ranked = rank_candidates("профиль", candidates)

        self.assertEqual(ranked[0].key, "MOB-2")


if __name__ == "__main__":
    unittest.main()
