import logging

from fastapi import APIRouter, Depends
from app.api.domain import ErrorIngestSchema
from app.api.deps import get_errors_service, get_telegram_notifier
from app.services.errors_service import ErrorsService
from app.tg_bot.bot import TelegramBot

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

@router.post("/errors")
async def ingest_error(
    error: ErrorIngestSchema,
    errors_service: ErrorsService = Depends(get_errors_service),
    notifier: TelegramBot = Depends(get_telegram_notifier),
):
    logger.info(
        "Ingest request received signature=%s exc_type=%s",
        error.signature_hash,
        error.exc_type,
    )
    is_new_error, current_count, last_notified_at = await errors_service.upsert_error(error)
    should_notify = errors_service.should_notify(is_new_error, last_notified_at)
    logger.info(
        "Ingest processed signature=%s count=%s queued_for_notification=%s",
        error.signature_hash,
        current_count,
        should_notify,
    )

    if should_notify:
        await notifier.send_alert(
            {
                "signature_hash": error.signature_hash,
                "signature_source": error.signature_source or "unknown",
                "exc_type": error.exc_type,
                "message": error.message,
                "traceback_preview": error.traceback_preview,
                "count": current_count,
            }
        )

    return {
        "message": "Error ingested",
        "is_new_error": is_new_error,
        "current_count": current_count,
        "last_notified_at": last_notified_at,
        "queued_for_notification": should_notify,
    }
