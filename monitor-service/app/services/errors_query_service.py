"""Read-only queries and management actions used by the web UI."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.database.db import Database
from app.database.models import Error, ErrorEvent, ErrorStatus
from sqlalchemy import delete, func, or_, select, update

SORT_LAST_SEEN = "last_seen"
SORT_FIRST_SEEN = "first_seen"
SORT_OCCURRENCES = "occurrences"
SORT_OPTIONS = (SORT_OCCURRENCES, SORT_LAST_SEEN, SORT_FIRST_SEEN)


@dataclass(slots=True)
class ErrorGroup:
    error: Error
    window_count: int


@dataclass(slots=True)
class Summary:
    groups: int
    occurrences: int
    services: int
    new_groups: int


@dataclass(slots=True)
class ErrorGroupPage:
    items: list[ErrorGroup]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // self.page_size))

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages


class ErrorsQueryService:
    def __init__(self, database: Database, page_size: int = 25):
        self.database = database
        self.page_size = page_size
        self.logger = logging.getLogger(__name__)

    async def list_groups(
        self,
        *,
        since: datetime | None = None,
        service_name: str | None = None,
        status: str | None = None,
        query: str | None = None,
        sort: str = SORT_LAST_SEEN,
        page: int = 1,
    ) -> ErrorGroupPage:
        """Return one page of aggregated error groups matching the filters."""
        page = max(1, page)
        window_count = func.count(ErrorEvent.id).label("window_count")

        join_condition = ErrorEvent.signature_hash == Error.signature_hash
        if since is not None:
            join_condition = join_condition & (ErrorEvent.occurred_at >= since)

        stmt = select(Error, window_count).outerjoin(ErrorEvent, join_condition)

        conditions = []
        if since is not None:
            conditions.append(Error.last_seen_at >= since)
        if service_name:
            conditions.append(Error.service_name == service_name)
        if status:
            conditions.append(Error.status == status)
        if query:
            pattern = f"%{query.strip()}%"
            conditions.append(
                or_(
                    Error.message.ilike(pattern),
                    Error.exc_type.ilike(pattern),
                    Error.traceback_preview.ilike(pattern),
                    Error.service_name.ilike(pattern),
                )
            )

        if conditions:
            stmt = stmt.where(*conditions)

        stmt = stmt.group_by(Error.id)

        if sort == SORT_OCCURRENCES:
            stmt = stmt.order_by(window_count.desc(), Error.last_seen_at.desc())
        elif sort == SORT_FIRST_SEEN:
            stmt = stmt.order_by(Error.first_seen_at.desc())
        else:
            stmt = stmt.order_by(Error.last_seen_at.desc())

        count_stmt = select(func.count()).select_from(Error)
        if conditions:
            count_stmt = count_stmt.where(*conditions)

        async with self.database.session() as session:
            total = await session.scalar(count_stmt) or 0
            result = await session.execute(
                stmt.limit(self.page_size).offset((page - 1) * self.page_size)
            )
            items = [ErrorGroup(error=row[0], window_count=row[1]) for row in result.all()]

        return ErrorGroupPage(items=items, total=total, page=page, page_size=self.page_size)

    async def get_group(self, error_id: int) -> Error | None:
        async with self.database.session() as session:
            return await session.get(Error, error_id)

    async def list_events(self, signature_hash: str, limit: int = 50) -> list[ErrorEvent]:
        """Return the most recent occurrences of one signature."""
        async with self.database.session() as session:
            result = await session.execute(
                select(ErrorEvent)
                .where(ErrorEvent.signature_hash == signature_hash)
                .order_by(ErrorEvent.occurred_at.desc(), ErrorEvent.id.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def count_events(self, signature_hash: str, since: datetime | None = None) -> int:
        stmt = (
            select(func.count())
            .select_from(ErrorEvent)
            .where(ErrorEvent.signature_hash == signature_hash)
        )
        if since is not None:
            stmt = stmt.where(ErrorEvent.occurred_at >= since)

        async with self.database.session() as session:
            return await session.scalar(stmt) or 0

    async def list_services(self) -> list[str]:
        async with self.database.session() as session:
            result = await session.execute(
                select(Error.service_name).distinct().order_by(Error.service_name)
            )
            return list(result.scalars().all())

    async def summary(self, since: datetime | None = None) -> Summary:
        """Return headline counters for the current filter window."""
        groups_stmt = select(func.count()).select_from(Error)
        services_stmt = select(func.count(func.distinct(Error.service_name)))
        occurrences_stmt = select(func.count()).select_from(ErrorEvent)
        if since is not None:
            groups_stmt = groups_stmt.where(Error.last_seen_at >= since)
            services_stmt = services_stmt.where(Error.last_seen_at >= since)
            occurrences_stmt = occurrences_stmt.where(ErrorEvent.occurred_at >= since)

        day_ago = datetime.now(UTC) - timedelta(days=1)
        new_groups_stmt = (
            select(func.count()).select_from(Error).where(Error.first_seen_at >= day_ago)
        )

        async with self.database.session() as session:
            return Summary(
                groups=await session.scalar(groups_stmt) or 0,
                occurrences=await session.scalar(occurrences_stmt) or 0,
                services=await session.scalar(services_stmt) or 0,
                new_groups=await session.scalar(new_groups_stmt) or 0,
            )

    async def set_status(self, error_id: int, status: str) -> bool:
        if status not in ErrorStatus.ALL:
            raise ValueError(f"Unknown status: {status}")

        async with self.database.session() as session:
            result = await session.execute(
                update(Error)
                .where(Error.id == error_id)
                .values(status=status, status_changed_at=datetime.now(UTC))
            )
            await session.commit()
            return result.rowcount > 0

    async def delete_group(self, error_id: int) -> bool:
        """Delete an error group together with all of its recorded occurrences."""
        async with self.database.session() as session:
            signature_hash = await session.scalar(
                select(Error.signature_hash).where(Error.id == error_id)
            )
            if signature_hash is None:
                return False

            await session.execute(
                delete(ErrorEvent).where(ErrorEvent.signature_hash == signature_hash)
            )
            await session.execute(delete(Error).where(Error.id == error_id))
            await session.commit()
            self.logger.info("Error group deleted id=%s signature=%s", error_id, signature_hash)
            return True
