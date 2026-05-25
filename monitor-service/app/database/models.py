from sqlalchemy import String, DateTime, Index, Integer, Text
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from app.database.db import Base


class Error(Base):
    __tablename__ = "errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signature_hash: Mapped[str] = mapped_column(String(255), index=True, unique=True)
    exc_type: Mapped[str] = mapped_column(String(255), index=True)
    message: Mapped[str] = mapped_column(Text)
    traceback_preview: Mapped[str] = mapped_column(Text)
    count: Mapped[int] = mapped_column(Integer, default=1)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_signature_hash", signature_hash),
        Index("idx_exc_type", exc_type),
    )
