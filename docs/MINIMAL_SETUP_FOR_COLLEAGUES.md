# Минимальная инструкция для коллег

Цель: поднять личного Telegram-бота, который создает и обновляет задачи в Jira.

## 1. Скачать проект

Получите архив проекта от коллеги или скачайте его из GitHub.

Распакуйте архив в удобную папку, например:

```text
/Users/<ваш-пользователь>/Documents/Alfa
```

Откройте Terminal и перейдите в папку проекта:

```bash
cd ~/Documents/Alfa
```

Проверьте, что вы внутри проекта:

```bash
ls
```

Должны быть видны:

```text
README.md
pyproject.toml
scripts
src
```

## 2. Ввести prompt в Codex или Claude Code

Откройте проект в Codex или Claude Code и вставьте prompt:

```text
Помоги мне поднять личного Telegram-бота для создания задач в Jira.

Работай в текущей папке проекта.

Важно:
- не выводи в чат содержимое .env, токены, пароли и API keys;
- если нужно вставить секрет, попроси меня открыть .env локально;
- создай Python-окружение .venv, если его нет;
- помоги заполнить .env по шагам;
- объясняй простыми словами, что и откуда брать;
- после заполнения .env запусти ./scripts/check_setup.sh;
- если проверка упала, объясни ошибку и скажи, что исправить;
- когда проверка пройдет, запусти ./scripts/install_service.sh;
- проверь статус командой ./scripts/status_bot.sh | grep -E 'state =|pid =';
- в конце дай 3 тестовых сообщения для Telegram.
```

Если Codex или Claude Code не используете, выполните шаги ниже вручную.

## 3. Открыть и заполнить `.env`

Создайте `.env`:

```bash
cp .env.example .env
```

Откройте `.env` через Terminal в обычном редакторе:

```bash
open -a TextEdit .env
```

Если установлен VS Code:

```bash
code .env
```

Заполните значения.

### TELEGRAM_BOT_TOKEN

Где взять:

1. Откройте Telegram.
2. Найдите `@BotFather`.
3. Отправьте `/newbot`.
4. Задайте имя бота.
5. Задайте username, который заканчивается на `bot`.
6. BotFather выдаст token.

Куда вставить:

```env
TELEGRAM_BOT_TOKEN=сюда_вставить_токен_бота
```

### JIRA_BASE_URL

Где взять:

Откройте Jira и возьмите адрес до `/browse/...`.

Пример: если задача открывается так:

```text
https://jira.company.local/browse/ABC-123
```

то нужно вставить:

```env
JIRA_BASE_URL=https://jira.company.local
```

### JIRA_PROJECT_KEY

Где взять:

Это первые буквы в ключе задачи.

Пример:

```text
ABC-123
```

значит:

```env
JIRA_PROJECT_KEY=ABC
```

### JIRA_USERNAME

Ваш логин в Jira:

```env
JIRA_USERNAME=ваш_логин
```

### JIRA_API_TOKEN

Где взять:

- если Jira поддерживает Personal Access Token, создайте его в профиле Jira;
- если Jira старая, может использоваться пароль от Jira;
- если не знаете, спросите Jira-админа или коллегу.

Куда вставить:

```env
JIRA_API_TOKEN=ваш_токен_или_пароль
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

### JIRA_BOARD_ID

Где взять:

Откройте Jira-доску. В URL часто есть:

```text
rapidView=123
```

Тогда:

```env
JIRA_BOARD_ID=123
```

### customfield_*

Нужно заполнить:

```env
JIRA_EPIC_LINK_FIELD=customfield_...
JIRA_EPIC_NAME_FIELD=customfield_...
JIRA_SPRINT_FIELD=customfield_...
JIRA_TASK_TYPE_FIELD=customfield_...
JIRA_ESTIMATE_FIELD=customfield_...
```

Как найти:

1. Подключите VPN.
2. Заполните базовые Jira-настройки выше.
3. Выполните:

```bash
./scripts/check_setup.sh
```

Скрипт покажет возможные поля Epic/Sprint и доски.

Если не понятно, что выбрать, попросите Codex или Claude:

```text
Посмотри вывод ./scripts/check_setup.sh и помоги заполнить customfield_* в .env.
Секреты из .env не выводи.
```

### Значения по умолчанию

Если в сообщении не указать эпик, спринт или исполнителя, бот возьмет дефолты из `.env`.

Эпик:

```env
JIRA_DEFAULT_EPIC_KEY=ABC-123
JIRA_DEFAULT_EPIC_NAME=Название эпика
```

Спринт:

```env
JIRA_DEFAULT_SPRINT_QUERY=Общий префикс или название спринта
```

Исполнитель:

```env
JIRA_DEFAULT_ASSIGNEE_KEY=user_key
JIRA_DEFAULT_ASSIGNEE_NAME=Фамилия Имя Отчество
JIRA_DEFAULT_ASSIGNEE_EMAIL=user@company.ru
```

Найти пользователя:

```bash
PYTHONPATH=src .venv/bin/python scripts/check_user_search.py "Фамилия"
```

### Проверить и запустить

Подключите VPN и выполните:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
./scripts/check_setup.sh
./scripts/install_service.sh
./scripts/status_bot.sh | grep -E 'state =|pid ='
```

Если увидели:

```text
state = running
```

бот запущен.

Бот работает в фоне только пока Mac включен, не спит, есть интернет и доступ к Jira/VPN.

## 4. Примеры сообщений

Одна задача:

```text
Заведи тикет Title с оценкой 5 на Иванова с описанием Description
```

```text
Создай задачу: Title. Эпик Epic Name. Спринт Sprint Name. Estimate 2
```

Несколько задач:

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

Description:

```text
Заведи тикет Title с описанием Создать окно подтверждения. Ссылка www.example.com.
```

## 5. Доработки

Если хотите свои команды, просто общайтесь с Codex или Claude Code человеческим языком.

Примеры:

```text
Сделай так, чтобы бот понимал команду "поставь оценку задаче Title 3".
```

```text
Добавь в /help новый пример сообщения.
```

```text
Сделай кнопку подтверждения красивее и проверь тестами.
```

Любые доработки допускаются. После изменений просите агента:

```text
Прогони тесты, перезапусти сервис и коротко напиши, что изменилось.
```

## Как выложить на GitHub для коллег

Если хотите выложить проект в GitHub как отдельный репозиторий:

1. Создайте пустой репозиторий на GitHub.
2. В Terminal в папке проекта выполните:

```bash
git remote add origin https://github.com/<your-org>/<repo-name>.git
git push -u origin master
```

Если remote уже существует:

```bash
git remote set-url origin https://github.com/<your-org>/<repo-name>.git
git push -u origin master
```

Перед публикацией проверьте, что секреты не попали в git:

```bash
git status --short
git ls-files | grep -E '(^|/)\\.env($|\\.)' || true
```

В выводе не должно быть `.env`, `.env.save`, `.env.local` и других файлов с секретами.
