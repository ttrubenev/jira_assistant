# Alfa Jira Telegram Bot

Telegram-бот для создания задач в Jira из текстовых сообщений.

## Что умеет MVP

- Принимает обычный текст в Telegram.
- Достает из сообщения описание задачи, примерный эпик, исполнителя и спринт.
- Опционально нормализует свободные формулировки через AI-агента.
- Ищет похожие эпики, пользователей и спринты в Jira.
- Предлагает варианты, если точного совпадения нет.
- Создает задачу только после явного подтверждения.
- Хранит секреты только в переменных окружения.
- Поддерживает старую Jira через REST API `/rest/api/2`.

## Быстрый старт

Если нужно поднять бота коллеге с нуля, используйте короткую инструкцию:
[docs/MINIMAL_SETUP_FOR_COLLEAGUES.md](docs/MINIMAL_SETUP_FOR_COLLEAGUES.md).

Подробная версия лежит здесь:
[docs/SETUP_FOR_COLLEAGUES.md](docs/SETUP_FOR_COLLEAGUES.md).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Создайте `.env` из `.env.example`, заполните личные токены и Jira-настройки, подключите VPN, затем запустите:

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

Если эпик, спринт или исполнитель не указаны, бот использует значения по умолчанию из `.env`.

Если бот найдет несколько похожих эпиков, исполнителей или спринтов, он покажет нумерованный список. Ответьте номером варианта.

## Настройки Jira

Старые Jira часто отличаются набором custom fields. Важные переменные:

- `JIRA_BASE_URL=https://jira.company.local`
- `JIRA_PROJECT_KEY` — ключ проекта, например `ABC`.
- `JIRA_BOARD_ID` — id Jira-доски.
- `JIRA_DEFAULT_EPIC_KEY` — ключ эпика по умолчанию.
- `JIRA_DEFAULT_EPIC_NAME` — название эпика по умолчанию.
- `JIRA_DEFAULT_SPRINT_QUERY` — общий префикс или название спринта.
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
JIRA_BASE_URL=https://jira.company.local
JIRA_USERNAME=your-login
JIRA_API_TOKEN=your-password-or-token
JIRA_PROJECT_KEY=ABC
JIRA_BOARD_ID=123
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

## AI-агент

По умолчанию AI-агент выключен, и бот работает детерминированным парсером. Чтобы бот понимал более свободные формулировки, включите:

```bash
AI_AGENT_ENABLED=true
OPENAI_API_KEY=sk-...
OPENAI_INTENT_MODEL=gpt-5.5
```

Агент не создает задачи напрямую. Он только переписывает сообщение в понятную боту команду, например:

```text
закинь тест формы на Иванова на два поинта
```

в:

```text
Создай задачу: тест формы. На Иванова. Estimate 2
```

Создание задач и изменение Story Points по-прежнему проходят через существующий сценарий с подтверждением или выбором похожей задачи.

## Проверки

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
