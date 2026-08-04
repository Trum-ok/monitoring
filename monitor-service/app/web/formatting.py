import re
from datetime import UTC, datetime, timedelta

FRAME_PATTERN = re.compile(r'File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<func>\S+)')

STATUS_LABELS = {
    "open": "Открыта",
    "acknowledged": "В работе",
    "resolved": "Решена",
}

WINDOWS: dict[str, tuple[str, timedelta | None]] = {
    "1h": ("1 час", timedelta(hours=1)),
    "6h": ("6 часов", timedelta(hours=6)),
    "1d": ("1 день", timedelta(days=1)),
    "7d": ("7 дней", timedelta(days=7)),
    "30d": ("30 дней", timedelta(days=30)),
    "all": ("Всё время", None),
}
DEFAULT_WINDOW = "7d"


def window_since(window: str) -> datetime | None:
    """Return the lower time bound for a named window, ``None`` for the unbounded one."""
    _, delta = WINDOWS.get(window, WINDOWS[DEFAULT_WINDOW])
    if delta is None:
        return None
    return datetime.now(UTC) - delta


def as_utc(value: datetime | None) -> datetime | None:
    """Attach UTC to naive datetimes coming from SQLite."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def format_dt(value: datetime | None) -> str:
    aware = as_utc(value)
    if aware is None:
        return "—"
    return aware.strftime("%d.%m.%Y %H:%M:%S UTC")


def _plural(number: int, one: str, few: str, many: str) -> str:
    if 11 <= number % 100 <= 14:
        return many
    remainder = number % 10
    if remainder == 1:
        return one
    if 2 <= remainder <= 4:
        return few
    return many


def humanize_ago(value: datetime | None) -> str:
    """Render a coarse relative timestamp such as ``5 минут назад``."""
    aware = as_utc(value)
    if aware is None:
        return "—"

    seconds = int((datetime.now(UTC) - aware).total_seconds())
    if seconds < 0:
        return "только что"
    if seconds < 60:
        return "только что"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} {_plural(minutes, 'минуту', 'минуты', 'минут')} назад"

    hours = minutes // 60
    if hours < 24:
        return f"{hours} {_plural(hours, 'час', 'часа', 'часов')} назад"

    days = hours // 24
    if days < 30:
        return f"{days} {_plural(days, 'день', 'дня', 'дней')} назад"

    months = days // 30
    if months < 12:
        return f"{months} {_plural(months, 'месяц', 'месяца', 'месяцев')} назад"

    years = days // 365
    return f"{years} {_plural(years, 'год', 'года', 'лет')} назад"


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def error_location(traceback_preview: str) -> str:
    """Return ``module.py:42 in func`` for the deepest frame of a traceback."""
    matches = FRAME_PATTERN.findall(traceback_preview or "")
    if not matches:
        return ""

    file_path, line, func = matches[-1]
    return f"{file_path}:{line} in {func}"


def first_line(text: str) -> str:
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""
