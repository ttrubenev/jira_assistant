import unittest

from jira_assistant_bot.agent import DisabledIntentInterpreter, parse_response_text


class AgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_interpreter_returns_original_text(self) -> None:
        interpreter = DisabledIntentInterpreter()

        text = await interpreter.interpret("закинь тест формы на два поинта")

        self.assertEqual(text, "закинь тест формы на два поинта")

    def test_parses_raw_responses_output_text(self) -> None:
        text = parse_response_text({"output_text": '{"action":"unknown","canonical_text":""}'})

        self.assertEqual(text, '{"action":"unknown","canonical_text":""}')

    def test_parses_raw_responses_output_items(self) -> None:
        text = parse_response_text(
            {
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"action":"create_issue","canonical_text":"Создай задачу: тест"}',
                            }
                        ]
                    }
                ]
            }
        )

        self.assertEqual(text, '{"action":"create_issue","canonical_text":"Создай задачу: тест"}')


if __name__ == "__main__":
    unittest.main()
