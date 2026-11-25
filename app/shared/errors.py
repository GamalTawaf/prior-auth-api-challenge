from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class FieldError(BaseModel):
    error_code: str
    field: str
    message: str


class ProblemBody(BaseModel):
    detail: str
    errors: list[FieldError] = Field(default_factory=list)
    correlation_id: str | None = None


class ValidationFailure(Exception):
    def __init__(
        self, correlation_id: str, errors: list[FieldError], detail: str = "Validation failed"
    ):
        self.correlation_id = correlation_id
        self.errors = errors
        self.detail = detail
        super().__init__(detail)


class ConflictError(Exception):
    def __init__(self, detail: str = "Conflict"):
        self.detail = detail
        super().__init__(detail)


class NotFoundError(Exception):
    def __init__(self, detail: str = "Not found"):
        self.detail = detail
        super().__init__(detail)


class ForbiddenError(Exception):
    def __init__(self, detail: str = "Forbidden"):
        self.detail = detail
        super().__init__(detail)


async def validation_failure_handler(_request: Request, exc: ValidationFailure) -> JSONResponse:
    body = ProblemBody(
        detail=exc.detail,
        errors=exc.errors,
        correlation_id=exc.correlation_id,
    )
    return JSONResponse(status_code=422, content=body.model_dump())


async def conflict_handler(_request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": exc.detail})


async def not_found_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.detail})


async def forbidden_handler(_request: Request, exc: ForbiddenError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": exc.detail})
