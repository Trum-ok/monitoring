import secrets

from app.utils.config import Settings
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

basic_scheme = HTTPBasic(auto_error=False)

UNAUTHORIZED_HEADERS = {"WWW-Authenticate": 'Basic realm="Monitoring"'}


def require_web_auth(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(basic_scheme),
) -> None:
    settings: Settings = request.app.state.settings

    if not settings.web_user or not settings.web_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Web UI is disabled: set MONITOR_WEB_USER and MONITOR_WEB_PASSWORD",
        )

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers=UNAUTHORIZED_HEADERS,
        )

    user_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"), settings.web_user.encode("utf-8")
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"), settings.web_password.encode("utf-8")
    )
    if not (user_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers=UNAUTHORIZED_HEADERS,
        )
