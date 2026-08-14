"""
Global exception handlers for the FastAPI application.

Intercepts raw database and application exceptions and returns
clean, structured JSON error responses instead of generic 500 errors.
"""

import logging  # Built-in logging library to record warning and error statements
from fastapi import FastAPI, Request, status  # FastAPI types and standard HTTP status code mapping
from fastapi.responses import JSONResponse  # Response class used to return structured JSON payloads for errors
from sqlalchemy.exc import IntegrityError, DataError, OperationalError, ProgrammingError  # Database exceptions thrown by SQLAlchemy

logger = logging.getLogger("auto_shop.exceptions")


def _extract_integrity_detail(exc: IntegrityError) -> dict:
    """
    Parse a SQLAlchemy IntegrityError into a user-friendly message.

    SQLAlchemy's IntegrityError contains database constraint details.
    We inspect the underlying PostgreSQL driver message (`exc.orig`)
    and format it nicely for our API clients.
    """
    orig = str(exc.orig) if exc.orig else str(exc)

    # 1. Unique constraint violation (e.g. duplicate username/email)
    if "unique" in orig.lower() or "duplicate key" in orig.lower():
        return {
            "error": "duplicate_resource",
            "message": "A record with this value already exists. Please use a unique value.",
            "detail": orig.split("DETAIL:")[-1].strip() if "DETAIL:" in orig else None
        }

    # 2. Foreign key constraint violation (e.g. referencing a non-existent vehicle ID)
    if "foreign key" in orig.lower() or "violates foreign key" in orig.lower():
        return {
            "error": "foreign_key_violation",
            "message": "The referenced record does not exist or cannot be removed because other records depend on it.",
            "detail": orig.split("DETAIL:")[-1].strip() if "DETAIL:" in orig else None
        }

    # 3. Not-null constraint violation (e.g. leaving a required database field empty)
    if "not-null" in orig.lower() or "null value" in orig.lower():
        return {
            "error": "missing_required_field",
            "message": "A required field was left empty.",
            "detail": orig.split("DETAIL:")[-1].strip() if "DETAIL:" in orig else None
        }

    # 4. Check constraint violation (e.g. negative prices, invalid types)
    if "check" in orig.lower() or "violates check" in orig.lower():
        return {
            "error": "validation_failed",
            "message": "A value did not pass a database validation check.",
            "detail": orig.split("DETAIL:")[-1].strip() if "DETAIL:" in orig else None
        }

    # 5. Generic database integrity error fallback
    return {
        "error": "integrity_error",
        "message": "The request could not be completed due to a data constraint.",
        "detail": None
    }


def register_exception_handlers(app: FastAPI) -> None:
    """
    Attach global exception handlers to the FastAPI application instance.
    Whenever these exceptions are raised in route handlers, they are intercepted here.
    """

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        # Log constraint violations as warnings (client side mistakes usually)
        logger.warning("IntegrityError on %s %s: %s", request.method, request.url.path, exc.orig)
        body = _extract_integrity_detail(exc)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=body
        )

    @app.exception_handler(DataError)
    async def data_error_handler(request: Request, exc: DataError) -> JSONResponse:
        # Triggers when data type/format mismatch occurs (e.g., passing invalid UUID format)
        logger.warning("DataError on %s %s: %s", request.method, request.url.path, exc.orig)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "invalid_data",
                "message": "The submitted data has an invalid type or format for the target field.",
                "detail": str(exc.orig) if exc.orig else None
            }
        )

    @app.exception_handler(OperationalError)
    async def operational_error_handler(request: Request, exc: OperationalError) -> JSONResponse:
        # Triggers when database goes offline or fails connection
        logger.error("OperationalError on %s %s: %s", request.method, request.url.path, exc.orig)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "database_unavailable",
                "message": "The database is temporarily unavailable. Please try again shortly."
            }
        )

    @app.exception_handler(ProgrammingError)
    async def programming_error_handler(request: Request, exc: ProgrammingError) -> JSONResponse:
        # Triggers due to SQL syntax error or missing table schemas
        logger.error("ProgrammingError on %s %s: %s", request.method, request.url.path, exc.orig)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "An internal server error occurred. The team has been notified."
            }
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        # Triggers when validating values inside models or logic checks
        logger.warning("ValueError on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "bad_request",
                "message": str(exc)
            }
        )

    from app.exceptions import NotFoundError

    @app.exception_handler(NotFoundError)
    async def not_found_error_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        logger.warning("NotFoundError on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "not_found",
                "message": str(exc)
            }
        )


    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Catch-all for any other unanticipated error (returns 500)
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "An unexpected error occurred. The team has been notified."
            }
        )
