# Инструкция по установке: Monitor Service + SDK

Этот гайд для пользователя, который хочет:
1. Поднять `monitor-service` на сервере.
2. Подключить SDK в свой Python-проект.
3. Получать алерты об unhandled exceptions в Telegram.
4. Разбирать ошибки в веб-интерфейсе на `/ui`.

## 1. Что нужно заранее

На сервере:
1. Docker + Docker Compose.
2. Открытый порт `8000/tcp`.
3. Telegram Bot Token и Chat ID.

В вашем Python-проекте:
1. Python 3.13+ (требование `monitor-sdk`).
2. Доступ к URL monitor-service.

## 2. Куда положить файлы на сервере

Скопируйте репозиторий на сервер, например в:

```bash
/opt/error-monitoring
```

Ожидаемая структура:
- `/opt/error-monitoring/monitor-service`
- `/opt/error-monitoring/sdk`

## 3. Настройка monitor-service на сервере

```bash
cd /opt/error-monitoring/monitor-service/deploy
```

Создайте `.env`:

```env
MONITOR_TG_BOT_TOKEN=123456:your_bot_token
MONITOR_TG_CHAT_ID=123456789

MONITOR_DB_PATH=/app/data/monitor.db
MONITOR_THROTTLE_SECONDS=1.0
MONITOR_TG_RATE_LIMIT_PER_SEC=1.0
MONITOR_TG_MAX_RETRIES=3
MONITOR_TG_RETRY_BACKOFF_MAX_SEC=30
MONITOR_TG_PARSE_MODE=HTML
MONITOR_TG_QUEUE_MAXSIZE=1000
MONITOR_ALERT_COOLDOWN_MINUTES=30

MONITOR_EVENT_RETENTION_DAYS=30
MONITOR_MAX_EVENTS_PER_ERROR=500

MONITOR_WEB_USER=admin
MONITOR_WEB_PASSWORD=задайте_свой_пароль
MONITOR_WEB_PAGE_SIZE=25
MONITOR_WEB_EVENTS_LIMIT=50
```

Про веб-переменные:
1. `MONITOR_WEB_USER` и `MONITOR_WEB_PASSWORD` — логин и пароль HTTP Basic для `/ui`.
   Если хотя бы одна пустая, веб-интерфейс отдаёт `503` и внутрь никого не пускает.
2. `MONITOR_EVENT_RETENTION_DAYS` — сколько дней хранить отдельные вхождения (`0` — не чистить по возрасту).
3. `MONITOR_MAX_EVENTS_PER_ERROR` — сколько последних вхождений хранить на одну сигнатуру (`0` — без лимита).

Запуск:

```bash
docker compose --env-file .env up --build -d
```

Проверка:

```bash
docker compose ps
docker compose logs -f monitor-service
```

## 4. Что происходит при запуске

1. Выполняется `alembic upgrade head`.
2. Поднимается FastAPI на `0.0.0.0:8000`.
3. Поднимается Telegram worker с очередью.
4. Веб-интерфейс доступен на `http://<SERVER_IP_OR_DOMAIN>:8000/ui`.

## 5. Веб-интерфейс

Открывается по `/ui` (корень `/` редиректит туда же), логин и пароль — из
`MONITOR_WEB_USER` / `MONITOR_WEB_PASSWORD`.

Список ошибок (`/ui/errors`):
1. Сводка: групп ошибок, вхождений за период, сервисов, новых за сутки.
2. Фильтры: поиск по тексту/типу/сервису, статус, сервис, период (1 час … 30 дней, всё время).
3. Сортировка по числу вхождений, последнему или первому появлению; постраничный вывод.
4. В строке: статус, вхождения за период и всего, тип с сообщением, место падения из трейсбека,
   сервис, первое и последнее появление, быстрые действия «В работу» и «Решена».

Карточка ошибки (`/ui/errors/{id}`):
1. Полный трейсбек последнего вхождения с кнопкой «Скопировать».
2. Счётчики: всего, за сутки, за неделю; первое и последнее появление; время последнего
   Telegram-алерта; сигнатура.
3. Недавние появления — раскрывающийся список отдельных вхождений с их трейсбеками.
4. Смена статуса и удаление группы вместе со всеми её вхождениями.

Статусы: `Открыта` → `В работе` → `Решена`. Если по решённой сигнатуре приходит новое
вхождение, она автоматически возвращается в `Открыта`, и по ней сразу уходит Telegram-алерт
(в обход cooldown), так как это регресс.

Отдельные вхождения пишутся в таблицу `error_events` начиная с этого релиза: у групп, которые
существовали раньше, счётчик `count` сохранится, но история вхождений начнётся с нуля.

## 6. Как подключить SDK в ваш проект

### Вариант A (рекомендуется): установка из GitHub

```bash
uv add "monitor-sdk @ git+https://github.com/<ORG>/<REPO>.git#subdirectory=sdk"
```

Пин на релизный тег:

```bash
uv add "monitor-sdk @ git+https://github.com/<ORG>/<REPO>.git@sdk-v0.1.1#subdirectory=sdk"
```

### Вариант B: локальная установка

```bash
uv add /opt/error-monitoring/sdk
```

Если в вашем проекте нет uv, работают эквиваленты на pip:

```bash
pip install "git+https://github.com/<ORG>/<REPO>.git#subdirectory=sdk"
```

### Инициализация SDK в коде

```python
import monitor_sdk

monitor_sdk.init(
    dsn="http://<SERVER_IP_OR_DOMAIN>:8000",
    service_name="my-python-service",
)
```

Где:
1. `<SERVER_IP_OR_DOMAIN>` — адрес сервера monitor-service.
2. `service_name` — имя вашего приложения.

## 7. Минимальный пример приложения с SDK

```python
import monitor_sdk

monitor_sdk.init("http://203.0.113.10:8000", service_name="billing-api")


def crash():
    raise RuntimeError("payment flow failed")


if __name__ == "__main__":
    crash()
```

## 8. Как проверить API вручную

```bash
curl -X POST http://<SERVER_IP_OR_DOMAIN>:8000/api/errors \
  -H "Content-Type: application/json" \
  -d '{
    "signature_hash": "manual-test-signature",
    "exc_type": "RuntimeError",
    "message": "manual test",
    "traceback_preview": "Traceback (most recent call last): ..."
  }'
```

## 9. Как работает очередь и защита от 429

1. API делает upsert ошибки в SQLite.
2. Если ошибка новая или вышел cooldown, событие ставится в `asyncio.Queue`.
3. Один воркер отправляет сообщения последовательно.
4. Скорость отправки ограничивается `MONITOR_THROTTLE_SECONDS` и `MONITOR_TG_RATE_LIMIT_PER_SEC`.
5. Если Telegram вернул `429`, воркер использует `retry_after` и повторяет отправку.
6. `last_notified_at` обновляется только после успешной отправки.

## 10. Частые команды эксплуатации

```bash
cd /opt/error-monitoring/monitor-service/deploy
docker compose --env-file .env up --build -d
docker compose logs -f monitor-service
docker compose down
```

## 11. Локальная разработка

Проект использует [uv](https://docs.astral.sh/uv/). Зависимости описаны в `pyproject.toml`,
версии зафиксированы в `uv.lock` (`requirements.txt` больше не используется).

Репозиторий — uv workspace с двумя членами: `monitor-service` и `sdk`.

Установка uv:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Поднять окружение:

```bash
uv sync
```

Создаётся один общий `.venv` в корне репозитория. `monitor-service` и `sdk` входят
в dev-группу корневого проекта и ставятся в editable-режиме, поэтому `import app`,
`import main` и `import monitor_sdk` работают без правки `PYTHONPATH`.

Только прод-зависимости сервиса, без dev-инструментов и SDK (так собирается образ):

```bash
uv sync --no-dev --no-install-project --package monitor-service
```

Запуск сервиса локально:

```bash
cd monitor-service
uv run alembic upgrade head
uv run uvicorn main:app --reload
```

Переменные окружения читаются из `.env` или из окружения. Минимум для локального запуска
с веб-интерфейсом:

```bash
MONITOR_TG_BOT_TOKEN=000:fake MONITOR_TG_CHAT_ID=1 \
MONITOR_WEB_USER=admin MONITOR_WEB_PASSWORD=secret \
uv run uvicorn main:app --reload
```

Работа с зависимостями:

```bash
uv add --package monitor-service <пакет>
uv remove --package monitor-service <пакет>
uv add --dev <пакет>
uv lock --upgrade
```

## 12. Лицензия и релизы

- Лицензия проекта: `AGPL-3.0-or-later` (см. файл `LICENSE`).
- Политика версий и процесс релизов: `RELEASE.md`.
- Рекомендованный формат SDK-тегов: `sdk-vX.Y.Z`.
