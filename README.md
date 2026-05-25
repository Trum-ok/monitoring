# Инструкция по установке: Monitor Service + SDK

Этот гайд для пользователя, который хочет:
1. Поднять `monitor-service` на сервере.
2. Подключить SDK в свой Python-проект.
3. Получать алерты об unhandled exceptions в Telegram.

## 1. Что нужно заранее

На сервере:
1. Docker + Docker Compose.
2. Открытый порт `8000/tcp`.
3. Telegram Bot Token и Chat ID.

В вашем Python-проекте:
1. Python 3.10+.
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
```

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

## 5. Как подключить SDK в ваш проект

### Вариант A (рекомендуется): установка из GitHub

```bash
pip install "git+https://github.com/<ORG>/<REPO>.git#subdirectory=sdk"
```

Пин на релизный тег:

```bash
pip install "git+https://github.com/<ORG>/<REPO>.git@sdk-v0.1.0#subdirectory=sdk"
```

### Вариант B: локальная установка

```bash
pip install /opt/error-monitoring/sdk
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

## 6. Минимальный пример приложения с SDK

```python
import monitor_sdk

monitor_sdk.init("http://203.0.113.10:8000", service_name="billing-api")


def crash():
    raise RuntimeError("payment flow failed")


if __name__ == "__main__":
    crash()
```

## 7. Как проверить API вручную

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

## 8. Как работает очередь и защита от 429

1. API делает upsert ошибки в SQLite.
2. Если ошибка новая или вышел cooldown, событие ставится в `asyncio.Queue`.
3. Один воркер отправляет сообщения последовательно.
4. Скорость отправки ограничивается `MONITOR_THROTTLE_SECONDS` и `MONITOR_TG_RATE_LIMIT_PER_SEC`.
5. Если Telegram вернул `429`, воркер использует `retry_after` и повторяет отправку.
6. `last_notified_at` обновляется только после успешной отправки.

## 9. Частые команды эксплуатации

```bash
cd /opt/error-monitoring/monitor-service/deploy
docker compose --env-file .env up --build -d
docker compose logs -f monitor-service
docker compose down
```

## 10. Лицензия и релизы

- Лицензия проекта: `AGPL-3.0-or-later` (см. файл `LICENSE`).
- Политика версий и процесс релизов: `RELEASE.md`.
- Рекомендованный формат SDK-тегов: `sdk-vX.Y.Z`.
