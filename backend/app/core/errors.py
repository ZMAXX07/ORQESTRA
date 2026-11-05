"""Consistent, safe error response handlers for FastAPI."""

import logging
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("orqestra.errors")


class ErrorDetail(BaseModel):
    """Detailed error object."""
    code: str
    message: str
    details: Optional[Any] = None


class ErrorResponse(BaseModel):
    """Safe, standard error response envelope."""
    error: ErrorDetail


def _cors_headers_for_request(request: Request) -> Dict[str, str]:
    """Ensure error responses propagate CORS headers so browsers receive meaningful errors."""
    origin = request.headers.get("origin")
    if not origin:
        return {}
    try:
        from backend.app.core.config import get_settings
        settings = get_settings()
        allowed = settings.CORS_ORIGINS
        if isinstance(allowed, str):
            allowed = [a.strip() for a in allowed.split(",")]
        if isinstance(allowed, list) and (origin in allowed or "*" in allowed):
            return {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
                "Vary": "Origin",
            }
    except Exception:
        pass
    return {}


def register_error_handlers(app: FastAPI) -> None:
    """Register custom exception handlers on FastAPI application."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        logger.warning(
            f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}"
        )
        if isinstance(exc.detail, dict):
            code = exc.detail.get("code", f"HTTP_{exc.status_code}")
            message = str(exc.detail.get("message", "An error occurred"))
            details = {k: v for k, v in exc.detail.items() if k not in ("code", "message")} or None
        else:
            code = f"HTTP_{exc.status_code}"
            message = str(exc.detail)
            details = None

        response_headers = _cors_headers_for_request(request)
        if exc.headers:
            response_headers.update(exc.headers)

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "details": details,
                }
            },
            headers=response_headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Simplify validation error representations to prevent exposing internal structure
        errors: List[Dict[str, Any]] = []
        for err in exc.errors():
            loc = " -> ".join([str(item) for item in err.get("loc", []) if item != "body"])
            errors.append({
                "field": loc or "body",
                "message": err.get("msg", "Validation error"),
                "type": err.get("type", "value_error"),
            })

        logger.info(f"Validation failure on {request.method} {request.url.path}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "The request payload failed validation.",
                    "details": errors,
                }
            },
            headers=_cors_headers_for_request(request),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log the full exception internally, but return a safe generic message to client
        logger.error(
            f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected internal server error occurred. Please try again later.",
                    "details": None,
                }
            },
            headers=_cors_headers_for_request(request),
        )
