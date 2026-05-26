from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


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

    model_config = SettingsConfigDict(env_prefix="MONITOR_", env_file=".env", extra="ignore")
