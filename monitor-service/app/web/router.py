"""Web UI routes rendered with Jinja2 templates."""

import logging
from pathlib import Path
from urllib.parse import urlsplit

from app.database.models import ErrorStatus
from app.services.errors_query_service import (
    SORT_LAST_SEEN,
    SORT_OPTIONS,
    ErrorsQueryService,
)
from app.web.auth import require_web_auth
from app.web.formatting import (
    DEFAULT_WINDOW,
    WINDOWS,
    error_location,
    first_line,
    format_dt,
    humanize_ago,
    status_label,
    window_since,
)
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
ERRORS_URL = "/ui/errors"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["format_dt"] = format_dt
templates.env.filters["humanize_ago"] = humanize_ago
templates.env.filters["status_label"] = status_label
templates.env.filters["error_location"] = error_location
templates.env.filters["first_line"] = first_line

router = APIRouter(
    prefix="/ui",
    include_in_schema=False,
    dependencies=[Depends(require_web_auth)],
)
logger = logging.getLogger(__name__)


def get_query_service(request: Request) -> ErrorsQueryService:
    return request.app.state.services.errors_query_service


def current_url(request: Request) -> str:
    """Return the current path with its query string, for round-trip redirects."""
    query = request.url.query
    return f"{request.url.path}?{query}" if query else request.url.path


def safe_back_url(back: str | None) -> str:
    """Allow redirects only to internal UI paths."""
    if not back:
        return ERRORS_URL

    parts = urlsplit(back)
    if parts.scheme or parts.netloc or not parts.path.startswith("/ui"):
        return ERRORS_URL

    return back


@router.get("")
async def index() -> RedirectResponse:
    return RedirectResponse(ERRORS_URL, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/errors")
async def errors_list(
    request: Request,
    window: str = Query(DEFAULT_WINDOW),
    service: str = Query(""),
    error_status: str = Query("", alias="status"),
    q: str = Query(""),
    sort: str = Query(SORT_LAST_SEEN),
    page: int = Query(1, ge=1),
    query_service: ErrorsQueryService = Depends(get_query_service),
):
    if window not in WINDOWS:
        window = DEFAULT_WINDOW
    if sort not in SORT_OPTIONS:
        sort = SORT_LAST_SEEN
    if error_status not in ErrorStatus.ALL:
        error_status = ""

    since = window_since(window)
    groups = await query_service.list_groups(
        since=since,
        service_name=service or None,
        status=error_status or None,
        query=q or None,
        sort=sort,
        page=page,
    )
    summary = await query_service.summary(since=since)
    services = await query_service.list_services()

    return templates.TemplateResponse(
        request,
        "errors_list.html",
        {
            "groups": groups,
            "summary": summary,
            "services": services,
            "windows": WINDOWS,
            "statuses": ErrorStatus.ALL,
            "filters": {
                "window": window,
                "service": service,
                "status": error_status,
                "q": q,
                "sort": sort,
            },
            "back_url": current_url(request),
        },
    )


@router.get("/errors/{error_id}")
async def error_detail(
    request: Request,
    error_id: int,
    back: str = Query(""),
    query_service: ErrorsQueryService = Depends(get_query_service),
):
    group = await query_service.get_group(error_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Error group not found")

    settings = request.app.state.settings
    events = await query_service.list_events(group.signature_hash, limit=settings.web_events_limit)
    stored_events = await query_service.count_events(group.signature_hash)
    day_count = await query_service.count_events(group.signature_hash, since=window_since("1d"))
    week_count = await query_service.count_events(group.signature_hash, since=window_since("7d"))

    return templates.TemplateResponse(
        request,
        "error_detail.html",
        {
            "error": group,
            "events": events,
            "stored_events": stored_events,
            "day_count": day_count,
            "week_count": week_count,
            "statuses": ErrorStatus.ALL,
            "back_url": safe_back_url(back),
            "detail_url": current_url(request),
        },
    )


@router.post("/errors/{error_id}/status/{new_status}")
async def change_status(
    error_id: int,
    new_status: str,
    back: str = Query(""),
    query_service: ErrorsQueryService = Depends(get_query_service),
) -> RedirectResponse:
    if new_status not in ErrorStatus.ALL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown status: {new_status}"
        )

    updated = await query_service.set_status(error_id, new_status)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Error group not found")

    logger.info("Status changed via web UI error_id=%s status=%s", error_id, new_status)
    return RedirectResponse(safe_back_url(back), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/errors/{error_id}/delete")
async def delete_group(
    error_id: int,
    back: str = Query(""),
    query_service: ErrorsQueryService = Depends(get_query_service),
) -> RedirectResponse:
    deleted = await query_service.delete_group(error_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Error group not found")

    logger.info("Error group deleted via web UI error_id=%s", error_id)
    return RedirectResponse(safe_back_url(back), status_code=status.HTTP_303_SEE_OTHER)
