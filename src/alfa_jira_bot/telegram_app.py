from __future__ import annotations

import asyncio
from contextlib import suppress

from telegram import BotCommand, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .agent import IntentInterpreter, build_intent_interpreter
from .config import BotConfig
from .conversation import BotReply, ConversationDefaults, ConversationManager, is_confirmation_reply
from .domain import Candidate, CandidateKind
from .jira import JiraClient

CANCEL_BUTTON_TEXT = "Отменить"
YES_BUTTON_TEXT = "Да"
NO_BUTTON_TEXT = "Нет"


def run() -> None:
    config = BotConfig.from_env()
    jira = JiraClient(config)
    conversation = ConversationManager(jira, defaults=build_conversation_defaults(config))
    intent_interpreter = build_intent_interpreter(
        enabled=config.ai_agent_enabled,
        api_key=config.openai_api_key,
        model=config.openai_intent_model,
        base_url=config.openai_base_url,
    )

    app = Application.builder().token(config.telegram_bot_token).build()
    app.bot_data["conversation"] = conversation
    app.bot_data["intent_interpreter"] = intent_interpreter

    app.post_init = setup_bot_commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(
        "Напишите задачу одним сообщением: описание, эпик, исполнитель, спринт.",
        reply_markup=main_menu_markup(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(help_text(), reply_markup=ReplyKeyboardRemove())


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    conversation = get_conversation(context)
    intent_interpreter = get_intent_interpreter(context)
    replies = await with_typing_indicator(
        context,
        update.effective_chat.id,
        safe_handle_text(conversation, intent_interpreter, update.effective_chat.id, "/cancel"),
    )
    for reply in replies:
        await reply_with_menu(update, reply)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.message.text is None or update.effective_chat is None:
        return

    conversation = get_conversation(context)
    intent_interpreter = get_intent_interpreter(context)
    replies = await with_typing_indicator(
        context,
        update.effective_chat.id,
        safe_handle_text(conversation, intent_interpreter, update.effective_chat.id, update.message.text),
    )
    for reply in replies:
        await reply_with_menu(update, reply)


def main_menu_markup() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(CANCEL_BUTTON_TEXT)]],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Напишите задачу",
    )


async def setup_bot_commands(app: Application) -> None:
    await app.bot.set_my_commands(
        [
            BotCommand("start", "начать работу"),
            BotCommand("cancel", "отменить текущий сценарий"),
            BotCommand("help", "что умеет этот бот"),
        ]
    )


def help_text() -> str:
    return "\n".join(
        [
            "Что умеет бот",
            "",
            "Я помогаю создавать и обновлять задачи в Jira.",
            "",
            "Можно:",
            "• создать одну или сразу несколько задач одним сообщением c указанием эпика, спринта, исполнителя, Story Points, описание задачи;",
            "• изменить Story Points у существующей задачи по названию или ключу;",
            "",
            "Если эпик, спринт или исполнитель не указаны, я подставляю значения по умолчанию, которые задавались при создании бота, или могу найти похожие варианты и предложу их.",
            "",
            "Пример создания одной задачи:",
            "• Заведи тикет Title с оценкой 5 на Иванова с описанием Description",
            "• Создай задачу: Title. Эпик Epic Name. Спринт Sprint Name. Estimate 2",
            "",
            "Пример создания сразу нескольких задач:",
            "• Заведи задачи Title1 с оценкой 2. задачу Title2 с оценкой 5. задачу Title3 с оценкой 0.2",
            "",
            "Примеры изменения оценки у заведённой задачи:",
            "• Измени в задаче Title оценку на 0.5",
            "• Измени ABC-123 Estimate 3",
            "• Измени оценку Title на 0.1",
            "",
            "Команды:",
            "• /start — стартовое сообщение",
            "• /cancel — отменить текущий сценарий",
            "• /help — показать помощь",
        ]
    )


def confirmation_menu_markup() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(YES_BUTTON_TEXT), KeyboardButton(NO_BUTTON_TEXT)]],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Подтвердите действие",
    )


async def reply_with_menu(update: Update, reply: BotReply) -> None:
    if update.message is None:
        return
    await update.message.reply_text(reply.text, reply_markup=reply_markup_for(reply))


def reply_markup_for(reply: BotReply) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    if is_cancelled_reply(reply.text) or is_completed_reply(reply.text):
        return ReplyKeyboardRemove()
    if asks_for_confirmation(reply.text):
        return confirmation_menu_markup()
    return main_menu_markup()


def asks_for_confirmation(text: str) -> bool:
    return "Ответьте «да» или «нет»" in text


def is_cancelled_reply(text: str) -> bool:
    return text.startswith("Ок, отменил")


def is_completed_reply(text: str) -> bool:
    return text.startswith("Готово")


def get_conversation(context: ContextTypes.DEFAULT_TYPE) -> ConversationManager:
    return context.application.bot_data["conversation"]


def get_intent_interpreter(context: ContextTypes.DEFAULT_TYPE) -> IntentInterpreter:
    return context.application.bot_data["intent_interpreter"]


async def safe_handle_text(
    conversation: ConversationManager,
    intent_interpreter: IntentInterpreter,
    chat_id: int,
    text: str,
) -> list[BotReply]:
    try:
        interpreted_text = await interpret_if_idle(conversation, intent_interpreter, chat_id, text)
        return await conversation.handle_text(chat_id, interpreted_text)
    except Exception as error:
        return [BotReply(format_integration_error(error))]


async def interpret_if_idle(
    conversation: ConversationManager,
    intent_interpreter: IntentInterpreter,
    chat_id: int,
    text: str,
) -> str:
    if not conversation.is_idle(chat_id):
        return text
    if is_confirmation_reply(text.strip()):
        return text
    with suppress(Exception):
        return await intent_interpreter.interpret(text)
    return text


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
