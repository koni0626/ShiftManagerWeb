from fastapi import APIRouter
from app import schemas as s
from app.controllers.dependencies import DB, Current
from app.services.member_service import MemberService

router = APIRouter(prefix="/me", tags=["member"])


@router.get("/schedule")
def schedule(db: DB, actor: Current):
    return MemberService(db, actor).schedule()


@router.put("/requests/{month}")
def requests(month: str, data: s.RequestInput, db: DB, actor: Current):
    return MemberService(db, actor).requests(month, data=data)


@router.post("/requests/{month}/{action}")
def transition(month: str, action: str, data: s.Version, db: DB, actor: Current):
    return MemberService(db, actor).requests(
        month, action=action, expected=data.expected_version
    )


@router.post("/notices/{id}/read")
def read(id: str, db: DB, actor: Current):
    return MemberService(db, actor).read_notice(id)
