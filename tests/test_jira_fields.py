import unittest

from alfa_jira_bot.config import BotConfig
from alfa_jira_bot.jira import JiraClient, format_estimate_value


class JiraFieldsTests(unittest.TestCase):
    def test_builds_default_task_type_select_field(self) -> None:
        config = BotConfig(
            telegram_bot_token="telegram",
            jira_base_url="https://jira.example.local",
            jira_auth_mode="bearer",
            jira_username="user",
            jira_api_token="token",
            jira_project_key="DFA",
            jira_issue_type="Task",
            jira_epic_link_field="customfield_10376",
            jira_epic_name_field="customfield_10377",
            jira_sprint_field="customfield_10375",
            jira_task_type_field="customfield_33794",
            jira_default_task_type="Задача развития",
            jira_estimate_field="customfield_10372",
            jira_board_id=28235,
            jira_default_epic_key="DFA-33230",
            jira_default_epic_name="[Q2-Q4_26ЦФА] Мелкие доработки 2026",
            jira_default_sprint_query="[DFA:STORM]",
            jira_default_assignee_key="U_M28HF",
            jira_default_assignee_name="Трубенёв Тимофей Александрович",
            jira_default_assignee_email="TTrubenev@alfabank.ru",
            jira_verify_tls=False,
            ai_agent_enabled=False,
            openai_api_key=None,
            openai_base_url="https://api.openai.com",
            openai_intent_model="gpt-5.5",
            voice_transcriber_provider="command",
            voice_transcriber_command=None,
            voice_transcriber_model="gpt-4o-mini-transcribe",
        )

        fields = JiraClient(config)._default_create_fields()

        self.assertEqual(fields["customfield_33794"], {"value": "Задача развития"})

    def test_builds_estimate_select_field(self) -> None:
        config = BotConfig(
            telegram_bot_token="telegram",
            jira_base_url="https://jira.example.local",
            jira_auth_mode="bearer",
            jira_username="user",
            jira_api_token="token",
            jira_project_key="DFA",
            jira_issue_type="Task",
            jira_epic_link_field="customfield_10376",
            jira_epic_name_field="customfield_10377",
            jira_sprint_field="customfield_10375",
            jira_task_type_field="customfield_33794",
            jira_default_task_type="Задача развития",
            jira_estimate_field="customfield_10372",
            jira_board_id=28235,
            jira_default_epic_key="DFA-33230",
            jira_default_epic_name="[Q2-Q4_26ЦФА] Мелкие доработки 2026",
            jira_default_sprint_query="[DFA:STORM]",
            jira_default_assignee_key="U_M28HF",
            jira_default_assignee_name="Трубенёв Тимофей Александрович",
            jira_default_assignee_email="TTrubenev@alfabank.ru",
            jira_verify_tls=False,
            ai_agent_enabled=False,
            openai_api_key=None,
            openai_base_url="https://api.openai.com",
            openai_intent_model="gpt-5.5",
            voice_transcriber_provider="command",
            voice_transcriber_command=None,
            voice_transcriber_model="gpt-4o-mini-transcribe",
        )

        fields = JiraClient(config)._estimate_fields(3)

        self.assertEqual(fields["customfield_10372"], 3.0)

    def test_formats_estimate_without_unnecessary_fraction(self) -> None:
        self.assertEqual(format_estimate_value(3), "3")
        self.assertEqual(format_estimate_value(0.5), "0.5")


if __name__ == "__main__":
    unittest.main()
