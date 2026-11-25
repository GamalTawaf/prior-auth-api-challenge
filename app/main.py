from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.telemetry import setup_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_telemetry(app)
    yield


app = FastAPI(title="Prior Authorization API", version="0.1.0", lifespan=lifespan)


@app.get("/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
