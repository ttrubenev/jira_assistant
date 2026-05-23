from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .config import BotConfig
from .conversation import BotReply, ConversationDefaults, ConversationManager
from .domain import Candidate, CandidateKind
from .jira import JiraClient
from .transcriber import VoiceTranscriber, build_transcriber


def run() -> None:
    config = BotConfig.from_env()
    jira = JiraClient(config)
    conversation = ConversationManager(jira, defaults=build_conversation_defaults(config))
    transcriber = build_transcriber(config.voice_transcriber_command)

    app = Application.builder().token(config.telegram_bot_token).build()
    app.bot_data["conversation"] = conversation
    app.bot_data["transcriber"] = transcriber

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    app.run_polling()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(
        "Напишите задачу одним сообщением: описание, эпик, исполнитель, спринт. Для отмены: /cancel."
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    conversation = get_conversation(context)
    replies = await with_typing_indicator(
        context,
        update.effective_chat.id,
        safe_handle_text(conversation, update.effective_chat.id, "/cancel"),
    )
    for reply in replies:
        await update.message.reply_text(reply.text)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.message.text is None or update.effective_chat is None:
        return

    conversation = get_conversation(context)
    replies = await with_typing_indicator(
        context,
        update.effective_chat.id,
        safe_handle_text(conversation, update.effective_chat.id, update.message.text),
    )
    for reply in replies:
        await update.message.reply_text(reply.text)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.message.voice is None or update.effective_chat is None:
        return

    transcriber = get_transcriber(context)
    try:
        with TemporaryDirectory() as tmp_dir:
            voice_file = await update.message.voice.get_file()
            path = Path(tmp_dir) / "voice.oga"
            await voice_file.download_to_drive(custom_path=path)
            text = await transcriber.transcribe(path)
    except RuntimeError as error:
        await update.message.reply_text(f"Не смог распознать голос: {error}")
        return

    conversation = get_conversation(context)
    replies = await with_typing_indicator(
        context,
        update.effective_chat.id,
        safe_handle_text(conversation, update.effective_chat.id, text),
    )
    await update.message.reply_text(f"Распознал: {text}")
    for reply in replies:
        await update.message.reply_text(reply.text)


def get_conversation(context: ContextTypes.DEFAULT_TYPE) -> ConversationManager:
    return context.application.bot_data["conversation"]


def get_transcriber(context: ContextTypes.DEFAULT_TYPE) -> VoiceTranscriber:
    return context.application.bot_data["transcriber"]


async def safe_handle_text(conversation: ConversationManager, chat_id: int, text: str) -> list[BotReply]:
    try:
        return await conversation.handle_text(chat_id, text)
    except Exception as error:
        return [BotReply(format_integration_error(error))]


async def with_typing_indicator(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    operation,
) -> list[BotReply]:
    indicator_task = asyncio.create_task(send_typing_until_done(context, chat_id))
    try:
        return await operation
    finally:
        indicator_task.cancel()
        with suppress(asyncio.CancelledError):
            await indicator_task


async def send_typing_until_done(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    while True:
        with suppress(Exception):
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(4)


def format_integration_error(error: Exception) -> str:
    message = str(error).strip()
    if not message:
        return "Не смог выполнить запрос к Jira. Проверьте VPN и настройки интеграции."
    return f"Не смог выполнить запрос к Jira. Проверьте VPN и настройки интеграции.\nДеталь: {message}"


def build_conversation_defaults(config: BotConfig) -> ConversationDefaults:
    default_epic = None
    if config.jira_default_epic_key:
        default_epic = Candidate(
            id=config.jira_default_epic_key,
            key=config.jira_default_epic_key,
            name=config.jira_default_epic_name or config.jira_default_epic_key,
            kind=CandidateKind.EPIC,
        )

    default_assignee = None
    if config.jira_default_assignee_key:
        default_assignee = Candidate(
            id=config.jira_default_assignee_key,
            key=config.jira_default_assignee_key,
            name=config.jira_default_assignee_name or config.jira_default_assignee_key,
            email=config.jira_default_assignee_email,
            kind=CandidateKind.ASSIGNEE,
        )

    return ConversationDefaults(
        epic=default_epic,
        assignee=default_assignee,
        sprint_query=config.jira_default_sprint_query,
    )
