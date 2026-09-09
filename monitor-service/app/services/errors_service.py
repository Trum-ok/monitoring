import logging
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

from app.api.domain import ErrorIngestSchema
from app.database.db import Database
from app.database.models import Error, ErrorEvent, ErrorStatus
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession


class UpsertResult(NamedTuple):
    is_new_error: bool
    current_count: int
    last_notified_at: datetime | None
    was_reopened: bool


class ErrorsService:
    def __init__(
        self,
        database: Database,
        alert_cooldown_minutes: int,
        event_retention_days: int = 30,
        max_events_per_error: int = 500,
    ):
        self.database = database
        self.alert_cooldown_minutes = alert_cooldown_minutes
        self.event_retention_days = event_retention_days
        self.max_events_per_error = max_events_per_error
        self.logger = logging.getLogger(__name__)

    async def upsert_error(self, error: ErrorIngestSchema) -> UpsertResult:
        async with self.database.session() as session:
            self.logger.info(f"Upserting error: {error}")

            occurred_at = datetime.now(UTC)

            previous_status = await session.scalar(
                select(Error.status).where(Error.signature_hash == error.signature_hash)
            )
            was_reopened = previous_status == ErrorStatus.RESOLVED

            set_values = {
                "service_name": error.service_name,
                "exc_type": error.exc_type,
                "message": error.message,
                "traceback_preview": error.traceback_preview,
                "count": Error.count + 1,
                "last_seen_at": occurred_at,
            }
            if was_reopened:
                set_values["status"] = ErrorStatus.OPEN
                set_values["status_changed_at"] = occurred_at

            upsert_stmt = (
                insert(Error)
                .values(
                    signature_hash=error.signature_hash,
                    service_name=error.service_name,
                    exc_type=error.exc_type,
                    message=error.message,
                    traceback_preview=error.traceback_preview,
                    count=1,
                    status=ErrorStatus.OPEN,
                    first_seen_at=occurred_at,
                    last_seen_at=occurred_at,
                )
                .on_conflict_do_update(
                    index_elements=[Error.signature_hash],
                    set_=set_values,
                )
            )

            await session.execute(upsert_stmt)
            await session.execute(
                insert(ErrorEvent).values(
                    signature_hash=error.signature_hash,
                    service_name=error.service_name,
                    exc_type=error.exc_type,
                    message=error.message,
                    traceback_preview=error.traceback_preview,
                    occurred_at=occurred_at,
                )
            )
            await self._prune_events(session, error.signature_hash, occurred_at)
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
                "Error upserted signature=%s count=%s is_new=%s reopened=%s",
                error.signature_hash,
                current_count,
                is_new_error,
                was_reopened,
            )
            return UpsertResult(is_new_error, current_count, last_notified_at, was_reopened)

    async def _prune_events(
        self, session: AsyncSession, signature_hash: str, now: datetime
    ) -> None:
        """Drop occurrences of one signature that fall out of retention limits."""
        if self.event_retention_days > 0:
            cutoff = now - timedelta(days=self.event_retention_days)
            await session.execute(
                delete(ErrorEvent).where(
                    ErrorEvent.signature_hash == signature_hash,
                    ErrorEvent.occurred_at < cutoff,
                )
            )

        if self.max_events_per_error > 0:
            keep_ids = (
                select(ErrorEvent.id)
                .where(ErrorEvent.signature_hash == signature_hash)
                .order_by(ErrorEvent.occurred_at.desc(), ErrorEvent.id.desc())
                .limit(self.max_events_per_error)
            )
            await session.execute(
                delete(ErrorEvent).where(
                    ErrorEvent.signature_hash == signature_hash,
                    ErrorEvent.id.not_in(keep_ids),
                )
            )

    def should_notify(
        self,
        is_new_error: bool,
        last_notified_at: datetime | None,
        was_reopened: bool = False,
    ) -> bool:
        """Return notification decision using configured cooldown policy."""
        if is_new_error or was_reopened or last_notified_at is None:
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
