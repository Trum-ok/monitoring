from app.api.deps import get_telegram_notifier
from app.tg_bot.bot import TelegramBot
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter()


@router.get("/health")
async def health(
    request: Request,
    notifier: TelegramBot = Depends(get_telegram_notifier),
) -> JSONResponse:
    checks: dict[str, str] = {}

    try:
        async with request.app.state.database.session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    worker_alive = notifier.worker_task is not None and not notifier.worker_task.done()
    checks["telegram_worker"] = "ok" if worker_alive else "error"

    healthy = all(value == "ok" for value in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "degraded", **checks},
    )
