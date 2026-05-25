import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert

from app.database.models import Error
from app.api.domain import ErrorIngestSchema
import typing
if typing.TYPE_CHECKING:
    from app.application import Application


class ErrorsService:
    def __init__(self, app: "Application"):
        self.app = app
        self.logger = logging.getLogger(__name__)

    async def upsert_error(self, error: ErrorIngestSchema) -> tuple[bool, int, str | None]:
        async with self.app.database.session() as session:
            self.logger.info(f"Upserting error: {error}")

            upsert_stmt = (
                insert(Error)
                .values(
                    signature_hash=error.signature_hash,
                    exc_type=error.exc_type,
                    message=error.message,
                    traceback_preview=error.traceback_preview,
                    count=1,
                )
                .on_conflict_do_update(
                    index_elements=[Error.signature_hash],
                    set_={
                        "exc_type": error.exc_type,
                        "message": error.message,
                        "traceback_preview": error.traceback_preview,
                        "count": Error.count + 1,
                    },
                )
            )

            await session.execute(upsert_stmt)
            await session.commit()

            result = await session.execute(
                select(Error.count, Error.last_notified_at).where(
                    Error.signature_hash == error.signature_hash
                )
            )
            row = result.one()
            current_count, last_notified_at = row
            is_new_error = current_count == 1
            last_notified_at_iso = (
                last_notified_at.astimezone(timezone.utc).isoformat()
                if isinstance(last_notified_at, datetime)
                else None
            )

            self.logger.info(
                "Error upserted signature=%s count=%s is_new=%s",
                error.signature_hash,
                current_count,
                is_new_error,
            )
            return is_new_error, current_count, last_notified_at_iso

    def should_notify(self, is_new_error: bool, last_notified_at_iso: str | None) -> bool:
        """Return notification decision using configured cooldown policy."""
        if is_new_error:
            return True
        if not last_notified_at_iso:
            return True

        try:
            last_notified_at = datetime.fromisoformat(last_notified_at_iso)
        except ValueError:
            self.logger.warning("Invalid last_notified_at format: %s", last_notified_at_iso)
            return True

        if last_notified_at.tzinfo is None:
            last_notified_at = last_notified_at.replace(tzinfo=timezone.utc)

        cooldown = timedelta(minutes=self.app.settings.alert_cooldown_minutes)
        return datetime.now(timezone.utc) - last_notified_at >= cooldown

    async def mark_notified(self, signature_hash: str) -> None:
        """Persist current notification timestamp after successful alert send."""
        async with self.app.database.session() as session:
            stmt = (
                update(Error)
                .where(Error.signature_hash == signature_hash)
                .values(last_notified_at=datetime.now(timezone.utc))
            )
            await session.execute(stmt)
            await session.commit()
