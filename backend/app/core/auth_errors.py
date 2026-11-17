from collections.abc import Callable

from fastapi import HTTPException, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.core.rate_limit import RateLimitExceeded


class AuthSessionError(HTTPException):
    def __init__(self, message: str, code: str = "INVALID_SESSION"):
        super().__init__(401, detail=message, headers={"WWW-Authenticate": "Bearer"})
        self.code = code


class SensitiveAuthRoute(APIRoute):
    """Never echo credential input in validation errors or cache auth responses."""

    def get_route_handler(self) -> Callable:
        handler = super().get_route_handler()

        async def sanitized_handler(request: Request) -> Response:
            try:
                response = await handler(request)
            except RequestValidationError as exc:
                response = JSONResponse(status_code=422, content={"detail": [
                    {key: error[key] for key in ("type", "loc", "msg")}
                    for error in exc.errors()
                ]})
            except AuthSessionError as exc:
                response = JSONResponse(status_code=exc.status_code, headers=exc.headers, content={
                    "success": False,
                    "message": exc.detail,
                    "detail": exc.detail,
                    "error_code": exc.code,
                })
            except RateLimitExceeded:
                # Preserve the application's existing quota error contract.
                raise
            except HTTPException as exc:
                response = await http_exception_handler(request, exc)
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
            return response

        return sanitized_handler
