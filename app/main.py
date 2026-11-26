from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.audit.router import router as audit_router
from app.intake.router import router as intake_router
from app.prior_auth.router import router as prior_auth_router
from app.shared.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationFailure,
    bad_request_handler,
    conflict_handler,
    forbidden_handler,
    not_found_handler,
    request_validation_handler,
    validation_failure_handler,
)
from app.shared.middleware import LimitRequestBodyMiddleware
from app.telemetry import setup_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_telemetry(app)
    yield


app = FastAPI(
    title="Prior Authorization API",
    version="0.1.0",
    lifespan=lifespan,
    description=(
        "Partner-facing prior authorization API. "
        "People: members (patients), provider offices (doctors' offices), "
        "reviewers (nurses or physicians), operations admins, auditors. "
        "JSON/API field names stay technical (`member_id`, role enums); "
        "office emails use plain language. Primary keys are named `uuid`. "
        "Errors use `error_code`, `field`, `message`, and optional `correlation_id`."
    ),
)

app.add_middleware(LimitRequestBodyMiddleware)
app.add_exception_handler(ValidationFailure, validation_failure_handler)
app.add_exception_handler(RequestValidationError, request_validation_handler)
app.add_exception_handler(BadRequestError, bad_request_handler)
app.add_exception_handler(ConflictError, conflict_handler)
app.add_exception_handler(NotFoundError, not_found_handler)
app.add_exception_handler(ForbiddenError, forbidden_handler)

app.include_router(prior_auth_router)
app.include_router(intake_router)
app.include_router(audit_router)


@app.get("/v1/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
