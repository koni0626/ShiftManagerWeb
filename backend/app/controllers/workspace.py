from fastapi import APIRouter, Body
from app import schemas as s
from app.controllers.dependencies import DB, Current
from app.services.workspace_service import WorkspaceService
from app.services.visit_service import VisitService
from app.services.request_service import RequestService
from app.services.availability_service import AvailabilityService

router = APIRouter(prefix="/scopes/{scope_id}", tags=["workspace"])


@router.get("/workspace")
def workspace(scope_id: str, db: DB, actor: Current):
    return WorkspaceService(db, actor, scope_id).snapshot()


@router.post("/visits")
def visit(scope_id: str, data: s.VisitInput, db: DB, actor: Current):
    return VisitService(db, actor, scope_id).save_visit(data)


@router.patch("/visits/{id}")
def edit_visit(scope_id: str, id: str, data: s.VisitInput, db: DB, actor: Current):
    return VisitService(db, actor, scope_id).save_visit(data, id)


@router.patch("/visits/{id}/position")
def position(scope_id: str, id: str, data: s.Position, db: DB, actor: Current):
    return VisitService(db, actor, scope_id).position(id, data)


@router.post("/visits/{id}/{action}")
def transition(
    scope_id: str, id: str, action: str, data: s.Version, db: DB, actor: Current
):
    return VisitService(db, actor, scope_id).transition(
        id, action, data.expected_version
    )


@router.patch("/clients/{id}/coordinates")
def coordinates(scope_id: str, id: str, data: s.Coordinates, db: DB, actor: Current):
    return WorkspaceService(db, actor, scope_id).coordinates(id, data)


@router.post("/clients/{id}/geocode")
def geocode(scope_id: str, id: str, data: s.Version, db: DB, actor: Current):
    return WorkspaceService(db, actor, scope_id).geocode(id, data)


@router.post("/members")
def member(scope_id: str, data: s.MemberInput, db: DB, actor: Current):
    return WorkspaceService(db, actor, scope_id).member(data)


@router.post("/staff/{id}/setup-token")
def setup_token(scope_id: str, id: str, db: DB, actor: Current):
    return WorkspaceService(db, actor, scope_id).account(id)


@router.patch("/staff/{id}/account")
def account(scope_id: str, id: str, data: s.MemberStatus, db: DB, actor: Current):
    return WorkspaceService(db, actor, scope_id).account(id, data.active)


@router.post("/staff/{id}/pay-terms")
def pay(scope_id: str, id: str, data: s.PayInput, db: DB, actor: Current):
    return WorkspaceService(db, actor, scope_id).pay(id, data)


@router.post("/request-windows")
def window(scope_id: str, data: s.WindowInput, db: DB, actor: Current):
    return RequestService(db, actor, scope_id).window(data)


@router.post("/request-submissions/{id}/return")
def return_submission(
    scope_id: str, id: str, data: s.ReturnInput, db: DB, actor: Current
):
    return RequestService(db, actor, scope_id).return_submission(id, data)


@router.put("/staff/{id}/requests/{month}")
def proxy_request(
    scope_id: str, id: str, month: str, data: s.RequestInput, db: DB, actor: Current
):
    return AvailabilityService(db, actor, scope_id, id).requests(month, data=data)


@router.post("/staff/{id}/requests/{month}/{action}")
def proxy_request_action(
    scope_id: str,
    id: str,
    month: str,
    action: str,
    data: s.Version,
    db: DB,
    actor: Current,
):
    return AvailabilityService(db, actor, scope_id, id).requests(
        month, action=action, expected=data.expected_version
    )


@router.post("/owner-profile")
def create_owner_profile(scope_id: str, data: s.StaffInput, db: DB, actor: Current):
    return WorkspaceService(db, actor, scope_id).save(
        "staff", data.model_dump(), bind_owner=True
    )


@router.post("/owner-profile/link")
def link_owner_profile(scope_id: str, data: s.OwnerProfileLink, db: DB, actor: Current):
    return WorkspaceService(db, actor, scope_id).link_owner_profile(data)


@router.post("/{resource}")
def create(
    scope_id: str, resource: str, db: DB, actor: Current, data: dict = Body(...)
):
    return WorkspaceService(db, actor, scope_id).save(resource, data)


@router.patch("/{resource}/{id}")
def edit(
    scope_id: str,
    resource: str,
    id: str,
    db: DB,
    actor: Current,
    data: dict = Body(...),
):
    return WorkspaceService(db, actor, scope_id).save(resource, data, id)
