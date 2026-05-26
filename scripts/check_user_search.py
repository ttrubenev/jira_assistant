from __future__ import annotations

import asyncio
import sys

from alfa_jira_bot.config import BotConfig
from alfa_jira_bot.jira import JiraClient


async def main() -> None:
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        raise SystemExit("Usage: PYTHONPATH=src .venv/bin/python scripts/check_user_search.py <name>")

    users = await JiraClient(BotConfig.from_env()).search_assignees(query)
    if not users:
        print("No users found")
        return

    for user in users[:10]:
        print(user.display_name)


if __name__ == "__main__":
    asyncio.run(main())
