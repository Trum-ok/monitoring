from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables.

    Attributes:
        tg_bot_token: Telegram Bot API token used for sending alert messages.
        tg_chat_id: Target Telegram chat identifier where alerts are delivered.
        db_path: Path to SQLite database file used for error storage.
        throttle_seconds: Minimal delay between Telegram messages in the notifier worker.
        tg_rate_limit_per_sec: Maximum Telegram send throughput.
        tg_max_retries: Maximum send retries for transient Telegram errors.
        tg_retry_backoff_max_sec: Upper bound for retry sleep duration.
        tg_parse_mode: Parse mode used in Telegram ``sendMessage`` requests.
        tg_queue_maxsize: Bounded in-memory queue size for pending alerts.
        tg_max_traceback_chars: Max traceback characters in Telegram alerts (capped at 2048).
        alert_cooldown_minutes: Cooldown window for re-sending alerts for the same signature.
        event_retention_days: Age limit for stored occurrences, ``0`` disables age-based cleanup.
        max_events_per_error: Occurrences kept per signature, ``0`` disables the limit.
        web_user: Username for HTTP Basic auth of the web UI, empty value disables the UI.
        web_password: Password for HTTP Basic auth of the web UI, empty value disables the UI.
        web_page_size: Number of error groups shown on one page of the web UI.
        web_events_limit: Number of recent occurrences shown on the error details page.
    """

    tg_bot_token: str
    tg_chat_id: str
    db_path: str = "./data/monitor.db"
    throttle_seconds: float = 1.0
    tg_rate_limit_per_sec: float = 1.0
    tg_max_retries: int = 3
    tg_retry_backoff_max_sec: float = 30.0
    tg_parse_mode: str = "HTML"
    tg_queue_maxsize: int = 1000
    tg_max_traceback_chars: int = Field(default=1200, ge=128, le=2048)
    alert_cooldown_minutes: int = 30
    event_retention_days: int = Field(default=30, ge=0)
    max_events_per_error: int = Field(default=500, ge=0)
    web_user: str = ""
    web_password: str = ""
    web_page_size: int = Field(default=25, ge=5, le=200)
    web_events_limit: int = Field(default=50, ge=5, le=500)

    model_config = SettingsConfigDict(env_prefix="MONITOR_", env_file=".env", extra="ignore")
