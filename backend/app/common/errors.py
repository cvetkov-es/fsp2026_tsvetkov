from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM = "application/problem+json"
HTTP_CODES = {401: "unauthenticated", 403: "forbidden", 404: "not_found", 405: "method_not_allowed"}


class AppError(Exception):
    def __init__(self, status: int, code: str, title: str, detail: str | None = None):
        super().__init__(title)
        self.status, self.code, self.title, self.detail = status, code, title, detail


def problem(status: int, code: str, title: str, detail: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type=PROBLEM,
        content={
            "type": f"https://fsp-hiring.ru/errors/{code}",
            "title": title,
            "status": status,
            "detail": detail,
            "code": code,
        },
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return problem(exc.status, exc.code, exc.title, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        detail = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        return problem(422, "validation_error", "Некорректные данные запроса", detail)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = HTTP_CODES.get(exc.status_code, "http_error")
        return problem(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        return problem(500, "internal_error", "Ошибка на сервере. Попробуйте позже")
