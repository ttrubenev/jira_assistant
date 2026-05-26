# Alfa Jira Telegram Bot

Telegram-бот для создания задач в Jira из текстовых сообщений, с подготовкой к голосовым сообщениям через локальный или корпоративный speech-to-text.

## Что умеет MVP

- Принимает обычный текст в Telegram.
- Достает из сообщения описание задачи, примерный эпик, исполнителя и спринт.
- Опционально нормализует свободные формулировки через AI-агента.
- Ищет похожие эпики, пользователей и спринты в Jira.
- Предлагает варианты, если точного совпадения нет.
- Создает задачу только после явного подтверждения.
- Хранит секреты только в переменных окружения.
- Поддерживает старую Jira через REST API `/rest/api/2`.
- Голосовой ввод подключается через локальную CLI-команду, чтобы не отправлять банковские данные во внешний STT.

## Быстрый старт

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

В этой рабочей папке `.env` уже создан с настройками DFA. Заполните в нем `TELEGRAM_BOT_TOKEN`, `JIRA_USERNAME`, `JIRA_API_TOKEN` и три `customfield_*`, подключите Endpoint Security VPN, затем запустите:

```bash
./scripts/install_service.sh
```

Команда установит бота как macOS LaunchAgent в `~/.alfa-jira-bot`. После этого он будет стартовать сам и перезапускаться после падений.

Остановить бота:

```bash
./scripts/stop_bot.sh
```

Проверить статус:

```bash
./scripts/status_bot.sh
```

## Как создать Telegram-бота

1. Откройте Telegram и найдите `@BotFather`.
2. Отправьте `/newbot`.
3. Укажите имя бота, например `Alfa Jira Assistant`.
4. Укажите username, который заканчивается на `bot`, например `alfa_jira_helper_bot`.
5. BotFather выдаст token. Вставьте его в `.env` как `TELEGRAM_BOT_TOKEN`.

Не отправляйте token в чат и не коммитьте `.env`.

## Пример сообщения

```text
Создай задачу: проверить отображение истории операций после перевыпуска карты.
На Иванова
```

Если эпик не указан, бот использует `DFA-33230`: `[Q2-Q4_26ЦФА] Мелкие доработки 2026`. Если спринт не указан, бот ищет активный спринт с префиксом `[DFA:STORM]`.

Если бот найдет несколько похожих эпиков, исполнителей или спринтов, он покажет нумерованный список. Ответьте номером варианта.

## Настройки Jira

Старые Jira часто отличаются набором custom fields. Важные переменные:

- `JIRA_BASE_URL=https://jira.moscow.alfaintra.net`
- `JIRA_PROJECT_KEY=DFA`
- `JIRA_BOARD_ID=28235`
- `JIRA_DEFAULT_EPIC_KEY=DFA-33230`
- `JIRA_DEFAULT_EPIC_NAME="[Q2-Q4_26ЦФА] Мелкие доработки 2026"`
- `JIRA_DEFAULT_SPRINT_QUERY="[DFA:STORM]"`
- `JIRA_EPIC_LINK_FIELD` — поле Epic Link для создаваемой задачи.
- `JIRA_EPIC_NAME_FIELD` — поле с названием Epic.
- `JIRA_SPRINT_FIELD` — поле Sprint.

Если задача создается, но не попадает в эпик или спринт, почти всегда причина в неверном `customfield_*`.

### Где взять значения

- `JIRA_BASE_URL` — откройте Jira через VPN и возьмите домен до `/browse/...`, например `https://jira.company.local`.
- `JIRA_PROJECT_KEY` — первые буквы в ключе задачи. Если задача выглядит как `MOB-12345`, project key будет `MOB`.
- `JIRA_BOARD_ID` — обычно виден в URL доски: `RapidBoard.jspa?rapidView=123`. Значение `123` и есть board id.
- `JIRA_EPIC_LINK_FIELD`, `JIRA_EPIC_NAME_FIELD`, `JIRA_SPRINT_FIELD` — проще всего получить через discovery-команду ниже.

После заполнения базовых значений в `.env`:

```env
JIRA_BASE_URL=https://jira.moscow.alfaintra.net
JIRA_USERNAME=your-login
JIRA_API_TOKEN=your-password-or-token
JIRA_PROJECT_KEY=DFA
JIRA_BOARD_ID=28235
```

Запустите:

```bash
PYTHONPATH=src .venv/bin/python -m alfa_jira_bot.discover
```

Или короче:

```bash
./scripts/check_setup.sh
```

Команда ничего не меняет в Jira. Она проверит авторизацию, покажет проект, возможные поля Epic/Sprint, boards и активные/будущие спринты.

Если discovery отвечает `HTTP 401`, Jira не приняла учетные данные. Проверьте `JIRA_USERNAME` и `JIRA_API_TOKEN`. Если используете Jira Personal Access Token, поставьте:

```env
JIRA_AUTH_MODE=bearer
```

Для обычного логина и пароля оставьте:

```env
JIRA_AUTH_MODE=basic
```

## Голосовые сообщения

По умолчанию голос отключен. Для корпоративного или локального speech-to-text укажите:

```bash
VOICE_TRANSCRIBER_PROVIDER=command
VOICE_TRANSCRIBER_COMMAND=/path/to/company-stt
```

Команда получит путь к скачанному `.oga` файлу первым аргументом и должна вернуть распознанный текст в stdout.

Команда может содержать аргументы, например:

```bash
VOICE_TRANSCRIBER_COMMAND="python /opt/company-stt/transcribe.py"
```

Также можно включить OpenAI transcription:

```bash
OPENAI_API_KEY=sk-...
VOICE_TRANSCRIBER_PROVIDER=openai
VOICE_TRANSCRIBER_MODEL=gpt-4o-mini-transcribe
```

Telegram voice будет скачан во временный файл, распознан и затем обработан как обычное текстовое сообщение.

## AI-агент

По умолчанию AI-агент выключен, и бот работает детерминированным парсером. Чтобы бот понимал более свободные формулировки, включите:

```bash
AI_AGENT_ENABLED=true
OPENAI_API_KEY=sk-...
OPENAI_INTENT_MODEL=gpt-5.5
```

Агент не создает задачи напрямую. Он только переписывает сообщение в понятную боту команду, например:

```text
закинь тест формы на Трубенёва на два поинта
```

в:

```text
Создай задачу: тест формы. На Трубенёва. Estimate 2
```

Создание задач и изменение Story Points по-прежнему проходят через существующий сценарий с подтверждением или выбором похожей задачи.

## Проверки

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
