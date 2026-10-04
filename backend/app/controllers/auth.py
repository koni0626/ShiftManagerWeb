from dataclasses import asdict
from fastapi import APIRouter, Request, Response
from app import schemas as s
from app.core.config import settings
from app.controllers.dependencies import DB, Current
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(data: s.Login, request: Request, response: Response, db: DB):
    actor, token, csrf = AuthService(db).login(
        data.login_id, data.password, request.client.host
    )
    for key, value, hidden in (
        ("atelier_session", token, True),
        ("atelier_csrf", csrf, False),
    ):
        response.set_cookie(
            key,
            value,
            httponly=hidden,
            secure=settings.cookie_secure,
            samesite="strict",
            max_age=settings.session_hours * 3600,
            path="/",
        )
    return asdict(actor)


@router.get("/me")
def me(actor: Current):
    return asdict(actor)


@router.post("/logout")
def logout(request: Request, response: Response, db: DB, actor: Current):
    AuthService(db).logout(request.cookies.get("atelier_session"))
    response.delete_cookie("atelier_session")
    response.delete_cookie("atelier_csrf")
    return {"ok": True}


@router.post("/setup")
def setup(data: s.Setup, db: DB):
    AuthService(db).setup(data.token, data.password)
    return {"ok": True}


@router.post("/password")
def password(data: s.Password, db: DB, actor: Current):
    AuthService(db).password(actor, data.current_password, data.password)
    return {"ok": True}
