from fastapi import APIRouter
from app import schemas as s
from app.controllers.dependencies import DB, Current
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview")
def overview(db: DB, actor: Current):
    return AdminService(db, actor).overview()


@router.post("/companies")
def company(data: s.CompanyInput, db: DB, actor: Current):
    return AdminService(db, actor).company(data)


@router.post("/owners")
def owner(data: s.OwnerInput, db: DB, actor: Current):
    return AdminService(db, actor).owner(data)
