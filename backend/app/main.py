from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from app.controllers import auth, admin, workspace, member
from app.core.config import settings
from app.core.errors import AppError
from app.db import engine


@asynccontextmanager
async def lifespan(app):
    with engine.connect() as connection:
        role = connection.execute(
            text(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
            )
        ).one()
        if role.rolsuper or role.rolbypassrls:
            raise RuntimeError(
                "The API must use a non-superuser PostgreSQL role without BYPASSRLS."
            )
        if not connection.scalar(text("SELECT to_regclass('public.users')")):
            raise RuntimeError("Run Alembic migrations before starting the API.")
    yield


app = FastAPI(title="訪問のアトリエ Web API", version="0.1.0", lifespan=lifespan)
for router in (auth.router, admin.router, workspace.router, member.router):
    app.include_router(router, prefix="/api/v1")


@app.middleware("http")
async def security(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if request.headers.get("origin") not in settings.allowed_origins.split(","):
            return JSONResponse(
                {"message": "許可されていない接続元です"}, status_code=403
            )
    response = await call_next(request)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.exception_handler(AppError)
async def app_error(request, error):
    return JSONResponse(
        {"message": error.message, "details": error.details}, status_code=error.status
    )


@app.exception_handler(IntegrityError)
async def integrity_error(request, error):
    return JSONResponse(
        {"message": "登録済みの情報との重複、または参照先の不整合があります"},
        status_code=409,
    )


@app.exception_handler(ValidationError)
@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    return JSONResponse(
        {
            "message": "入力内容を確認してください",
            "details": [
                {"field": ".".join(map(str, x["loc"])), "message": x["msg"]}
                for x in error.errors()
            ],
        },
        status_code=422,
    )


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/v1/config")
def config():
    return {"tile_url": settings.map_tile_url, "attribution": settings.map_attribution}
