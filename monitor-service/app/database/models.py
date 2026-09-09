from datetime import UTC, datetime

from app.database.db import Base
from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class ErrorStatus:
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"

    ALL = (OPEN, ACKNOWLEDGED, RESOLVED)


class Error(Base):
    __tablename__ = "errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signature_hash: Mapped[str] = mapped_column(String(255), index=True, unique=True)
    service_name: Mapped[str] = mapped_column(String(255), index=True)
    exc_type: Mapped[str] = mapped_column(String(255), index=True)
    message: Mapped[str] = mapped_column(Text)
    traceback_preview: Mapped[str] = mapped_column(Text)
    count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default=ErrorStatus.OPEN, index=True)
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, index=True, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        Index("idx_signature_hash", signature_hash),
        Index("idx_service_name", service_name),
        Index("idx_exc_type", exc_type),
        Index("idx_status", status),
        Index("idx_last_seen_at", last_seen_at),
    )


class ErrorEvent(Base):
    __tablename__ = "error_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signature_hash: Mapped[str] = mapped_column(String(255), index=True)
    service_name: Mapped[str] = mapped_column(String(255))
    exc_type: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    traceback_preview: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("idx_error_events_signature_occurred", signature_hash, occurred_at),
        Index("idx_error_events_occurred_at", occurred_at),
    )
