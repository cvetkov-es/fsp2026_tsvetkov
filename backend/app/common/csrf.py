from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.common.errors import problem

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


class CSRFMiddleware(BaseHTTPMiddleware):
    """Простая защита от CSRF: браузерный клиент всегда шлёт X-Requested-With: fsp."""

    async def dispatch(self, request: Request, call_next):
        if (
            request.method in UNSAFE
            and request.url.path.startswith("/api/v1")
            and request.headers.get("x-requested-with") != "fsp"
        ):
            return problem(403, "csrf", "Запрос отклонён защитой от CSRF")
        return await call_next(request)
