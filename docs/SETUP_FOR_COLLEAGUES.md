# Как поднять личного Telegram-бота для Jira

Эта инструкция для коллег, которые не программируют каждый день и хотят поднять себе такого же личного бота.

Бот умеет:
- создавать задачи в Jira из Telegram-сообщений;
- создавать несколько задач одним сообщением;
- заполнять Epic, Sprint, Assignee, Story Points и Description;
- менять Story Points у уже созданной задачи;
- работать в фоне на Mac, даже если Terminal, Codex или Claude Code закрыты.

## 0. Что понадобится

- MacBook.
- Доступ к Jira через VPN.
- Telegram.
- Папка с этим проектом `Alfa`.
- Codex или Claude Code, если хотите, чтобы агент помогал выполнять шаги.
- 20-40 минут на первую настройку.

Важно:
- Не отправляйте токены, пароли и содержимое `.env` в чат с людьми.
- Если используете Codex или Claude Code, лучше вставлять секреты руками в файл `.env`, а не писать их в диалог.
- Если в компании нельзя отправлять рабочие данные во внешние AI-сервисы, не включайте `OPENAI_API_KEY` и `AI_AGENT_ENABLED=true`.

## 1. Получите папку проекта

Если проект лежит в Git:

```bash
cd ~/Documents
git clone <ссылка-на-репозиторий> Alfa
cd Alfa
```

Если проект передали архивом:

1. Распакуйте архив.
2. Положите папку, например, сюда:

```text
/Users/<ваш-пользователь>/Documents/Alfa
```

3. Откройте Terminal и перейдите в папку:

```bash
cd ~/Documents/Alfa
```

Проверьте, что вы в правильной папке:

```bash
ls
```

Должны быть видны файлы и папки:

```text
README.md
pyproject.toml
scripts
src
tests
```

## 2. Подготовьте Python-окружение

Если хотите, чтобы Codex или Claude Code помогали вам выполнять шаги:

Для Codex:

1. Откройте Codex.
2. Выберите папку проекта `Alfa`.
3. Вставьте prompt из раздела 17 этой инструкции.

Для Claude Code:

1. Откройте Terminal.
2. Перейдите в папку проекта:

```bash
cd ~/Documents/Alfa
```

3. Запустите Claude Code:

```bash
claude
```

4. Вставьте prompt из раздела 17 этой инструкции.

Если Codex или Claude Code не используете, просто выполняйте команды ниже руками в Terminal.

В Terminal в папке проекта выполните:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Если команда `python3` не найдена, установите Command Line Tools:

```bash
xcode-select --install
```

После установки повторите команды выше.

## 3. Создайте `.env`

В папке проекта выполните:

```bash
cp .env.example .env
```

Откройте `.env` обычным редактором:

```bash
open -a TextEdit .env
```

Если установлен VS Code:

```bash
code .env
```

В этот файл нужно вставить ваши личные значения.

## 4. Создайте Telegram-бота

1. Откройте Telegram.
2. Найдите `@BotFather`.
3. Отправьте команду:

```text
/newbot
```

4. Укажите имя, например:

```text
My Jira Assistant
```

5. Укажите username, он должен заканчиваться на `bot`, например:

```text
my_jira_assistant_bot
```

6. BotFather выдаст токен вида:

```text
1234567890:AA...
```

7. Вставьте его в `.env`:

```env
TELEGRAM_BOT_TOKEN=1234567890:AA...
```

## 5. Заполните базовые настройки Jira

Откройте Jira через VPN.

### JIRA_BASE_URL

Возьмите адрес Jira до `/browse/...`.

Пример:

```env
JIRA_BASE_URL=https://jira.company.local
```

Если задача открывается по ссылке:

```text
https://jira.company.local/browse/ABC-123
```

то `JIRA_BASE_URL` будет:

```env
JIRA_BASE_URL=https://jira.company.local
```

### JIRA_PROJECT_KEY

Это первые буквы в ключе задачи.

Пример:

```text
ABC-123
```

Значит:

```env
JIRA_PROJECT_KEY=ABC
```

### JIRA_USERNAME

Ваш логин в Jira.

Пример:

```env
JIRA_USERNAME=ivanov
```

### JIRA_API_TOKEN

Зависит от вашей Jira:

- если в Jira есть Personal Access Token, создайте его в профиле Jira;
- если Jira старая и токенов нет, может использоваться пароль от Jira;
- если не знаете, спросите коллегу или Jira-админа, какой способ авторизации разрешен.

Вставьте значение:

```env
JIRA_API_TOKEN=ваш-токен-или-пароль
```

### JIRA_AUTH_MODE

Если используете Personal Access Token:

```env
JIRA_AUTH_MODE=bearer
```

Если используете логин + пароль:

```env
JIRA_AUTH_MODE=basic
```

## 6. Заполните project/board/custom fields

Для своего проекта заполните значения из Jira.

Проверьте, что в `.env` есть:

```env
JIRA_PROJECT_KEY=ABC
JIRA_BOARD_ID=123
JIRA_EPIC_LINK_FIELD=customfield_TODO
JIRA_EPIC_NAME_FIELD=customfield_TODO
JIRA_SPRINT_FIELD=customfield_TODO
JIRA_TASK_TYPE_FIELD=customfield_TODO
JIRA_DEFAULT_TASK_TYPE=
JIRA_ESTIMATE_FIELD=customfield_TODO
```

Если у вас другой проект:

1. Заполните минимум:

```env
JIRA_BASE_URL=...
JIRA_USERNAME=...
JIRA_API_TOKEN=...
JIRA_AUTH_MODE=...
JIRA_PROJECT_KEY=...
```

2. Подключите VPN.
3. Выполните:

```bash
./scripts/check_setup.sh
```

Скрипт покажет:
- удалось ли войти в Jira;
- найден ли проект;
- возможные поля Epic/Sprint;
- доски;
- активные и будущие спринты.

Если не знаете, какой `customfield_*` выбрать, попросите Codex или Claude Code:

```text
Посмотри вывод ./scripts/check_setup.sh и помоги заполнить customfield_* в .env для Epic Link, Epic Name, Sprint, Story Points и Тип задачи.
Секреты из .env не выводи.
```

## 7. Заполните значения по умолчанию

Если в сообщении не указан эпик, спринт или исполнитель, бот подставит дефолты.

### Дефолтный эпик

Откройте нужный эпик в Jira.

Если ссылка:

```text
https://jira.company.local/browse/ABC-456
```

то:

```env
JIRA_DEFAULT_EPIC_KEY=ABC-456
```

Название эпика скопируйте из Jira:

```env
JIRA_DEFAULT_EPIC_NAME="Название эпика"
```

### Дефолтный спринт

Если спринты называются так:

```text
[ABC:TEAM] 18.05-29.05
[ABC:TEAM] 01.06-12.06
```

то достаточно указать общий префикс:

```env
JIRA_DEFAULT_SPRINT_QUERY="[ABC:TEAM]"
```

Бот сам выберет активный спринт.

### Дефолтный исполнитель

Если задачи по умолчанию нужно ставить на вас или конкретного коллегу, заполните:

```env
JIRA_DEFAULT_ASSIGNEE_KEY=user_key
JIRA_DEFAULT_ASSIGNEE_NAME=Фамилия Имя Отчество
JIRA_DEFAULT_ASSIGNEE_EMAIL=user@company.ru
```

Чтобы найти пользователя через Jira:

```bash
PYTHONPATH=src .venv/bin/python scripts/check_user_search.py "Фамилия Имя"
```

Пример:

```bash
PYTHONPATH=src .venv/bin/python scripts/check_user_search.py "Иванов"
```

Скрипт выведет похожих пользователей. Возьмите `key`, ФИО и email.

## 8. Проверьте настройки

Подключите VPN.

Выполните:

```bash
./scripts/check_setup.sh
```

Если видите:

```text
Jira auth: OK
```

значит Jira-логин работает.

Частые ошибки:

- `HTTP 401` — неверный логин/токен/пароль или выбран не тот `JIRA_AUTH_MODE`.
- `Cannot reach Jira` — не подключен VPN, неверный `JIRA_BASE_URL` или проблема с сертификатом.
- `No boards found` — проверьте `JIRA_PROJECT_KEY` или права на доску.

Если корпоративный сертификат не доверяется локально, оставьте:

```env
JIRA_VERIFY_TLS=false
```

## 9. Запустите бота как постоянный сервис

Выполните:

```bash
./scripts/install_service.sh
```

Проверьте статус:

```bash
./scripts/status_bot.sh | grep -E 'state =|pid ='
```

Нормальный результат:

```text
state = running
pid = 12345
```

Теперь бот будет работать в фоне на Mac даже после закрытия Terminal, Codex или Claude Code.

Ограничение: бот работает только пока Mac включен, не спит, есть интернет и есть доступ к Jira/VPN. Если Mac выключен или ушел в сон, бот не сможет получать сообщения и создавать задачи.

## 10. Проверьте в Telegram

Откройте своего бота в Telegram и отправьте:

```text
/start
```

Потом попробуйте:

```text
Заведи тикет [design] тест с оценкой 5 с описанием Проверить создание задачи.
```

Бот должен показать подтверждение. Нажмите `Нет`, если это тест.

## 11. Примеры сообщений

Создать одну задачу:

```text
Заведи тикет Title с оценкой 5 на Иванова с описанием Description
```

```text
Создай задачу: Title. Эпик Epic Name. Спринт Sprint Name. Estimate 2
```

Создать несколько задач:

```text
Заведи задачи Title1 с оценкой 2. задачу Title2 с оценкой 5. задачу Title3 с оценкой 0.2
```

Изменить Story Points:

```text
Измени в задаче Title оценку на 0.5
```

```text
Измени ABC-123 Estimate 3
```

```text
Измени оценку Title на 0.1
```

Заполнить Description:

```text
Заведи тикет Title с описанием Создать окно подтверждения. Ссылка www.b.com.
```

Также работают маркеры:

```text
Описание ...
Дискрипшен ...
Дискрипшн ...
description ...
desc ...
```

## 12. Команды бота

```text
/start — стартовое сообщение
/cancel — отменить текущий сценарий
/help — показать помощь
```

## 13. Как остановить бота

```bash
./scripts/stop_bot.sh
```

## 14. Как перезапустить после изменения `.env`

Если поменяли токен, Jira-настройки или OpenAI-настройки:

```bash
./scripts/install_service.sh
```

## 15. Где смотреть ошибки

```bash
tail -n 100 ~/.alfa-jira-bot/logs/bot.err.log
```

Обычные логи:

```bash
tail -n 100 ~/.alfa-jira-bot/logs/bot.out.log
```

Не отправляйте логи наружу, если там могут быть внутренние ссылки, ФИО или рабочие данные.

## 16. AI-агент

По умолчанию AI-агент можно оставить выключенным:

```env
AI_AGENT_ENABLED=false
OPENAI_API_KEY=
```

Если вам разрешено использовать OpenAI для рабочих данных, можно включить:

```env
AI_AGENT_ENABLED=true
OPENAI_API_KEY=sk-...
OPENAI_INTENT_MODEL=gpt-5.5
```

## 17. Готовый prompt для Codex или Claude Code

Скопируйте этот текст в Codex или Claude Code, открыв папку проекта `Alfa`:

```text
Помоги мне поднять личного Telegram-бота для создания задач в Jira.

Работай в этой папке проекта. Следуй docs/SETUP_FOR_COLLEAGUES.md.

Важно:
- не выводи в чат содержимое .env, токены, пароли и API keys;
- если нужно вставить секрет, скажи мне открыть .env локально через TextEdit или VS Code;
- проверь, что создано Python-окружение .venv;
- помоги заполнить .env по шагам;
- после заполнения .env запусти ./scripts/check_setup.sh;
- если check_setup.sh падает, объясни ошибку простыми словами и скажи, что поправить;
- когда проверка пройдет, запусти ./scripts/install_service.sh;
- проверь статус командой ./scripts/status_bot.sh | grep -E 'state =|pid =';
- в конце дай короткий список тестовых сообщений для Telegram.
```

## 18. Чеклист готовности

- [ ] VPN подключен.
- [ ] `.env` создан из `.env.example`.
- [ ] `TELEGRAM_BOT_TOKEN` заполнен.
- [ ] `JIRA_BASE_URL` заполнен.
- [ ] `JIRA_USERNAME` заполнен.
- [ ] `JIRA_API_TOKEN` заполнен.
- [ ] `JIRA_AUTH_MODE` выбран правильно.
- [ ] `JIRA_PROJECT_KEY` заполнен.
- [ ] `JIRA_BOARD_ID` заполнен.
- [ ] `customfield_*` заполнены.
- [ ] `./scripts/check_setup.sh` проходит без ошибок.
- [ ] `./scripts/install_service.sh` выполнен.
- [ ] `./scripts/status_bot.sh` показывает `state = running`.
- [ ] Бот отвечает в Telegram на `/start`.
