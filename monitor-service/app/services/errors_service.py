import logging
from datetime import UTC, datetime, timedelta

from app.api.domain import ErrorIngestSchema
from app.database.db import Database
from app.database.models import Error
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert


class ErrorsService:
    def __init__(self, database: Database, alert_cooldown_minutes: int):
        self.database = database
        self.alert_cooldown_minutes = alert_cooldown_minutes
        self.logger = logging.getLogger(__name__)

    async def upsert_error(self, error: ErrorIngestSchema) -> tuple[bool, int, datetime | None]:
        async with self.database.session() as session:
            self.logger.info(f"Upserting error: {error}")

            upsert_stmt = (
                insert(Error)
                .values(
                    signature_hash=error.signature_hash,
                    service_name=error.service_name,
                    exc_type=error.exc_type,
                    message=error.message,
                    traceback_preview=error.traceback_preview,
                    count=1,
                )
                .on_conflict_do_update(
                    index_elements=[Error.signature_hash],
                    set_={
                        "service_name": error.service_name,
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
            if last_notified_at is not None and last_notified_at.tzinfo is None:
                last_notified_at = last_notified_at.replace(tzinfo=UTC)

            self.logger.info(
                "Error upserted signature=%s count=%s is_new=%s",
                error.signature_hash,
                current_count,
                is_new_error,
            )
            return is_new_error, current_count, last_notified_at

    def should_notify(self, is_new_error: bool, last_notified_at: datetime | None) -> bool:
        """Return notification decision using configured cooldown policy."""
        if is_new_error or last_notified_at is None:
            return True

        cooldown = timedelta(minutes=self.alert_cooldown_minutes)
        return datetime.now(UTC) - last_notified_at >= cooldown

    async def mark_notified(self, signature_hash: str) -> None:
        """Persist current notification timestamp after successful alert send."""
        async with self.database.session() as session:
            stmt = (
                update(Error)
                .where(Error.signature_hash == signature_hash)
                .values(last_notified_at=datetime.now(UTC))
            )
            await session.execute(stmt)
            await session.commit()
