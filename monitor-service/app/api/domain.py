"""Pydantic schemas for monitor service API payloads."""

from pydantic import BaseModel, Field


class ErrorIngestSchema(BaseModel):
    """Incoming error event payload accepted by ingest endpoint."""

    signature_hash: str = Field(..., min_length=1)
    signature_source: str | None = None
    exc_type: str = Field(..., min_length=1)
    message: str = Field(...)
    traceback_preview: str = Field(...)
