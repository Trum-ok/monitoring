from html import escape
from typing import Any


def build_error_alert_message(payload: dict[str, Any], max_traceback_chars: int = 1200) -> str:
    signature_hash = escape(str(payload.get("signature_hash", "unknown")))
    signature_source = escape(str(payload.get("signature_source", "unknown")))
    service_name = escape(str(payload.get("service_name", "unknown")))
    exc_type = escape(str(payload.get("exc_type", "Exception")))
    message = escape(str(payload.get("message", "")))
    count = int(payload.get("count", 1))
    traceback_preview = escape(str(payload.get("traceback_preview", ""))[:max_traceback_chars])

    return (
        "🚨 <b>Error detected</b>\n"
        f"<b>Service:</b> {service_name}\n"
        f"<b>Signature:</b> <code>{signature_source}</code>\n"
        f"<b>Hash:</b> <code>{signature_hash}</code>\n"
        f"<b>Type:</b> {exc_type}\n"
        f"<b>Count:</b> {count}\n"
        f"<b>Message:</b> {message}\n"
        f"<b>Traceback:</b>\n<pre>{traceback_preview}</pre>"
    )
