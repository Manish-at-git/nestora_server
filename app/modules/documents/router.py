"""Protected association, resident, and unit document routes."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import AuthContext, get_auth_context, require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.documents.schemas import (
    DocumentMutationResponse,
    DocumentRequest,
    DocumentResponse,
    DocumentUpdateRequest,
    UnitDocumentRequest,
    UnitDocumentResponse,
    UnitDocumentUpdateRequest,
)
from app.modules.documents.service import DocumentService


VIEW_ROLES = (
    RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT, RoleCode.BOARD_MEMBER,
    RoleCode.COMMITTEE_MEMBER, RoleCode.HOMEOWNER, RoleCode.TENANT,
)

router = APIRouter(tags=["Documents"])


@router.get("/board-documents", response_model=ApiResponse[list[DocumentResponse]], dependencies=[Depends(require_role(*VIEW_ROLES))])
@router.get("/resident-documents", response_model=ApiResponse[list[DocumentResponse]], dependencies=[Depends(require_role(*VIEW_ROLES))])
@router.get("/admin/documents", response_model=ApiResponse[list[DocumentResponse]], dependencies=[Depends(require_role(*VIEW_ROLES))])
async def list_documents(
    assoc_id: str | None = Query(None), context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await DocumentService(session).list(context.account, context.account.role.code, assoc_id)
    return success_response([DocumentResponse(**row) for row in rows])


@router.post("/board-documents", response_model=ApiResponse[DocumentMutationResponse], status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT, RoleCode.BOARD_MEMBER))])
@router.post("/admin/documents", response_model=ApiResponse[DocumentMutationResponse], status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT, RoleCode.BOARD_MEMBER))])
async def create_document(
    payload: DocumentRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        document_id = await DocumentService(session).create(context.account, context.account.role.code, payload)
    return success_response(DocumentMutationResponse(id=document_id))


@router.put("/board-documents/{document_id}", response_model=ApiResponse[DocumentMutationResponse], dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT, RoleCode.BOARD_MEMBER))])
@router.put("/admin/documents/{document_id}", response_model=ApiResponse[DocumentMutationResponse], dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT, RoleCode.BOARD_MEMBER))])
async def update_document(
    document_id: str, payload: DocumentUpdateRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await DocumentService(session).update(context.account, context.account.role.code, document_id, payload)
    return success_response(DocumentMutationResponse())


@router.delete("/board-documents/{document_id}", response_model=ApiResponse[DocumentMutationResponse], dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT, RoleCode.BOARD_MEMBER))])
@router.delete("/admin/documents/{document_id}", response_model=ApiResponse[DocumentMutationResponse], dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT, RoleCode.BOARD_MEMBER))])
async def delete_document(
    document_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await DocumentService(session).delete(context.account, context.account.role.code, document_id)
    return success_response(DocumentMutationResponse())


@router.get("/unit-documents", response_model=ApiResponse[list[UnitDocumentResponse]], dependencies=[Depends(require_role(*VIEW_ROLES))])
async def list_unit_documents(
    assoc_id: str | None = Query(None), context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await DocumentService(session).list_unit(context.account, context.account.role.code, assoc_id)
    return success_response([UnitDocumentResponse(**row) for row in rows])


@router.get("/admin/associations/{association_id}/all-units", dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT, RoleCode.BOARD_MEMBER))])
async def list_association_units(
    association_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return success_response(await DocumentService(session).list_units(context.account, context.account.role.code, association_id))


@router.post("/unit-documents", response_model=ApiResponse[DocumentMutationResponse], status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_role(*VIEW_ROLES))])
async def create_unit_document(
    payload: UnitDocumentRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        document_id = await DocumentService(session).create_unit(context.account, context.account.role.code, payload)
    return success_response(DocumentMutationResponse(id=document_id))


@router.put("/unit-documents/{document_id}", response_model=ApiResponse[DocumentMutationResponse], dependencies=[Depends(require_role(*VIEW_ROLES))])
async def update_unit_document(
    document_id: str, payload: UnitDocumentUpdateRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await DocumentService(session).update_unit(context.account, context.account.role.code, document_id, payload)
    return success_response(DocumentMutationResponse())


@router.delete("/unit-documents/{document_id}", response_model=ApiResponse[DocumentMutationResponse], dependencies=[Depends(require_role(*VIEW_ROLES))])
async def delete_unit_document(
    document_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await DocumentService(session).delete_unit(context.account, context.account.role.code, document_id)
    return success_response(DocumentMutationResponse())
