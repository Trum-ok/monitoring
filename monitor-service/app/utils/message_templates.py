from typing import Any


def build_error_alert_message(payload: dict[str, Any], max_traceback_chars: int = 1200) -> str:
    signature = str(payload.get("signature_hash", "unknown"))
    exc_type = str(payload.get("exc_type", "Exception"))
    message = str(payload.get("message", ""))
    count = int(payload.get("count", 1))
    traceback_preview = str(payload.get("traceback_preview", ""))[:max_traceback_chars]

    return (
        "<b>Error detected</b>\n"
        f"<b>Signature:</b> <code>{signature}</code>\n"
        f"<b>Type:</b> {exc_type}\n"
        f"<b>Count:</b> {count}\n"
        f"<b>Message:</b> {message}\n"
        f"<b>Traceback:</b>\n<code>{traceback_preview}</code>"
    )
