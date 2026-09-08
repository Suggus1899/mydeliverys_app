from typing import Any, cast

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.domain.errors import DomainError


class AppException(Exception):
    """Base application exception with standardized response."""

    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY,
        data: Any = None,
    ):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.data = data
        super().__init__(message)


def create_error_response(
    error_code: str,
    message: str,
    status_code: int,
    data: Any = None,
) -> JSONResponse:
    """Create standardized error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error_code": error_code,
            "message": message,
            "data": data,
        },
    )


def create_success_response(
    data: Any = None,
    message: str = "Operación completada con éxito.",
    status_code: int = status.HTTP_200_OK,
) -> JSONResponse:
    """Create standardized success response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "error_code": None,
            "message": message,
            "data": data,
        },
    )


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Handle DomainError from business logic."""
    return create_error_response(
        error_code=exc.code,
        message=exc.message,
        status_code=exc.status,
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle AppException."""
    return create_error_response(
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
        data=exc.data,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors."""
    errors = []
    for error in exc.errors():
        loc = " -> ".join(str(x) for x in error["loc"])
        errors.append(f"{loc}: {error['msg']}")

    return create_error_response(
        error_code="VALIDATION_ERROR",
        message="Datos de entrada inválidos.",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        data={"details": errors},
    )


async def pydantic_validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle Pydantic model validation errors."""
    return create_error_response(
        error_code="VALIDATION_ERROR",
        message="Datos de entrada inválidos.",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        data={"details": str(exc)},
    )


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Handle database integrity errors (unique constraints, etc.)."""
    error_msg = str(exc.orig) if exc.orig else "Error de integridad en la base de datos."

    # Detect common constraint violations
    if "unique constraint" in error_msg.lower() or "duplicate key" in error_msg.lower():
        if "phone_number" in error_msg:
            return create_error_response(
                error_code="PHONE_ALREADY_REGISTERED",
                message="Este número de teléfono ya está registrado.",
                status_code=status.HTTP_409_CONFLICT,
            )
        if "idempotency" in error_msg.lower():
            return create_error_response(
                error_code="IDEMPOTENCY_KEY_CONFLICT",
                message="Clave de idempotencia ya utilizada con contenido diferente.",
                status_code=status.HTTP_409_CONFLICT,
            )
        return create_error_response(
            error_code="DUPLICATE_ENTRY",
            message="Ya existe un registro con estos datos.",
            status_code=status.HTTP_409_CONFLICT,
        )

    if "foreign key" in error_msg.lower():
        return create_error_response(
            error_code="FOREIGN_KEY_VIOLATION",
            message="Referencia a recurso inexistente.",
            status_code=status.HTTP_409_CONFLICT,
        )

    return create_error_response(
        error_code="DATABASE_ERROR",
        message="Error en la base de datos. Intente nuevamente.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    # Log the exception here (in production, use proper logging)
    import traceback

    traceback.print_exc()

    return create_error_response(
        error_code="INTERNAL_SERVER_ERROR",
        message="Error interno del servidor. Por favor intente más tarde.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers."""
    # FastAPI accepts handlers specialized by exception type at runtime, while
    # its public type annotation only exposes the generic Exception signature.
    app.add_exception_handler(DomainError, cast(Any, domain_error_handler))
    app.add_exception_handler(AppException, cast(Any, app_exception_handler))
    app.add_exception_handler(RequestValidationError, cast(Any, validation_error_handler))
    app.add_exception_handler(ValidationError, cast(Any, pydantic_validation_error_handler))
    app.add_exception_handler(IntegrityError, cast(Any, integrity_error_handler))
    app.add_exception_handler(Exception, generic_exception_handler)
