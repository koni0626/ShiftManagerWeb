from typing import Annotated
from fastapi import Depends, Request
from sqlalchemy.orm import Session
from app.db import get_db
from app.policies import Actor
from app.services.auth_service import AuthService

DB = Annotated[Session, Depends(get_db)]


def authenticate(request: Request, db: DB):
    return AuthService(db).authenticate(
        request.cookies.get("atelier_session"),
        request.headers.get("x-csrf-token"),
        request.method not in ("GET", "HEAD", "OPTIONS"),
    )


Current = Annotated[Actor, Depends(authenticate)]
