"""HTTP routes for cookie-session authentication using the common response envelope."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_codes import generate_access_code
from app.core.config import Settings
from app.core.constants import RoleCode
from app.core.dependencies import AuthContext, get_app_settings, get_auth_context, require_csrf, require_role
from app.core.messages import Message
from app.core.responses import ApiResponse, success_response
from app.core.security import clear_auth_cookies, set_auth_cookies
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.auth.notifier import PasswordResetNotifier
from app.modules.auth.schemas import (
    AccountResponse,
    CreateAccountRequest,
    LoginRequest,
    LoginResponseData,
    LogoutResponseData,
    PasswordResetConfirmRequest,
    PasswordResetConfirmResponse,
    LegacyPasswordResetRequest,
    PasswordResetOtpRequest,
    LegacyPasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetRequestResponse,
    PasswordResetVerifyRequest,
    PasswordResetVerifyResponse,
    AccessCodeRequest,
    AccessCodeRequestResponse,
    ValidateCodeRequest,
    ValidateCodeResponse,
    UserDetailsResponse,
    CreateMemberAccountRequest,
    UpdateDetailsRequest,
    CodeRequestResponse,
    IssueCodeRequest,
    UpdateRequestResponse,
    AccessCodeStatsResponse,
)
from app.modules.auth.service import AuthService
from app.modules.users.models import UserCode, UserDetail

logger = logging.getLogger("nestora.server.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])
public_router = APIRouter(tags=["Public Authentication"])
admin_code_router = APIRouter(prefix="/admin", tags=["Access Code Administration"])


@public_router.post("/login-code", response_model=ApiResponse[ValidateCodeResponse])
async def validate_login_code(
    payload: ValidateCodeRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    result = await AuthService(session, settings).validate_access_code(payload.code)
    return success_response(ValidateCodeResponse(**result), Message.SUCCESS)


@public_router.post("/request-code", response_model=ApiResponse[AccessCodeRequestResponse])
async def request_code(
    payload: AccessCodeRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    async with UnitOfWork(session):
        await AuthService(session, settings).request_access_code(
            payload.name, str(payload.email), payload.contact_number
        )
    return success_response(AccessCodeRequestResponse(), "Request submitted successfully")


@public_router.get("/user-details", response_model=ApiResponse[UserDetailsResponse])
async def get_user_details(
    code: str,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    details = await AuthService(session, settings).get_user_details_by_code(code)
    return success_response(UserDetailsResponse(**details), Message.SUCCESS)


@public_router.post("/create-account", response_model=ApiResponse[LoginResponseData])
async def create_member_account(
    payload: CreateMemberAccountRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> JSONResponse:
    async with UnitOfWork(session):
        result = await AuthService(session, settings).create_member_account(payload)
    response = JSONResponse(
        content=success_response(LoginResponseData(account=result.account), Message.CREATED),
        status_code=status.HTTP_201_CREATED,
    )
    set_auth_cookies(response, result.session_token, result.csrf_token, settings)
    return response


@public_router.post("/update-details-request", response_model=ApiResponse[AccessCodeRequestResponse])
async def update_details_request(
    payload: UpdateDetailsRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    async with UnitOfWork(session):
        await AuthService(session, settings).request_details_update(payload)
    return success_response(AccessCodeRequestResponse(), "Update request submitted successfully")


@admin_code_router.get(
    "/code-requests",
    response_model=ApiResponse[list[CodeRequestResponse]],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)
async def list_code_requests(session: AsyncSession = Depends(get_db_session)) -> dict:
    result = await session.execute(
        text("SELECT id, name, email, contact_number, status, issued_code, created_at FROM code_requests ORDER BY created_at DESC")
    )
    requests = []
    for row in result.mappings().all():
        item = dict(row)
        if item.get("created_at") is not None:
            item["created_at"] = item["created_at"].isoformat()
        requests.append(CodeRequestResponse(**item))
    return success_response(requests)


@admin_code_router.post(
    "/code-requests/approve",
    response_model=ApiResponse[CodeRequestResponse],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)
async def approve_code_request(
    payload: IssueCodeRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    request = (
        await session.execute(text("SELECT * FROM code_requests WHERE id = :id"), {"id": payload.request_id})
    ).mappings().first()
    if request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found.")
    if request["status"] != "pending":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Request already processed.")
    async with UnitOfWork(session):
        for _ in range(10):
            code_value = generate_access_code()
            if await session.scalar(select(UserCode.id).where(UserCode.login_code == code_value)) is None:
                break
        code = UserCode(id=str(uuid.uuid4()), login_code=code_value, status="active")
        session.add(code)
        await session.flush()
        session.add(UserDetail(
            user_id=str(uuid.uuid4()), code_id=code.id, name=request["name"], address="Address pending update",
            email=request["email"], contact_number=request["contact_number"], is_deleted=False,
        ))
        await session.execute(
            text("UPDATE code_requests SET status = 'approved', issued_code = :code WHERE id = :id"),
            {"code": code_value, "id": payload.request_id},
        )
    return success_response(CodeRequestResponse(
        id=request["id"], name=request["name"], email=request["email"],
        contact_number=request["contact_number"], status="approved", issued_code=code_value,
        created_at=request["created_at"].isoformat() if request["created_at"] else None,
    ), "Access code issued successfully")


@admin_code_router.post(
    "/code-requests/reject",
    response_model=ApiResponse[AccessCodeRequestResponse],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)
async def reject_code_request(
    payload: IssueCodeRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        result = await session.execute(
            text("UPDATE code_requests SET status = 'rejected' WHERE id = :id AND status = 'pending'"),
            {"id": payload.request_id},
        )
        if result.rowcount == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Request not found or already processed.")
    return success_response(AccessCodeRequestResponse(), "Access request rejected")


@admin_code_router.get(
    "/update-requests",
    response_model=ApiResponse[list[UpdateRequestResponse]],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)
async def list_update_requests(session: AsyncSession = Depends(get_db_session)) -> dict:
    result = await session.execute(
        text(
            "SELECT ur.id, ur.status, ur.requested_name, ur.requested_address, "
            "ur.requested_email, ur.requested_contact, ur.note, ur.created_at, "
            "uc.login_code FROM update_requests ur "
            "LEFT JOIN user_codes uc ON uc.id = ur.code_id "
            "ORDER BY ur.created_at DESC"
        )
    )
    requests = []
    for row in result.mappings().all():
        item = dict(row)
        if item.get("created_at") is not None:
            item["created_at"] = item["created_at"].isoformat()
        requests.append(UpdateRequestResponse(**item))
    return success_response(requests)


@admin_code_router.post(
    "/update-requests/{request_id}/resolve",
    response_model=ApiResponse[AccessCodeRequestResponse],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)
async def resolve_update_request(
    request_id: str,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        result = await session.execute(
            text("UPDATE update_requests SET status = 'resolved' WHERE id = :id"),
            {"id": request_id},
        )
        if result.rowcount == 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Update request not found.")
    return success_response(AccessCodeRequestResponse(), "Update request resolved")


@admin_code_router.get(
    "/stats",
    response_model=ApiResponse[AccessCodeStatsResponse],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)
async def access_code_stats(session: AsyncSession = Depends(get_db_session)) -> dict:
    queries = {
        "total_codes": "SELECT COUNT(*) FROM user_codes",
        "used_codes": "SELECT COUNT(*) FROM user_codes WHERE status = 'used'",
        "pending_requests": "SELECT COUNT(*) FROM code_requests WHERE status = 'pending'",
        "members": "SELECT COUNT(*) FROM accounts WHERE user_id IS NOT NULL",
        "open_update_requests": "SELECT COUNT(*) FROM update_requests WHERE status = 'open'",
    }
    values = {name: int(await session.scalar(text(query)) or 0) for name, query in queries.items()}
    return success_response(AccessCodeStatsResponse(**values))


@router.post("/login", response_model=ApiResponse[LoginResponseData], status_code=status.HTTP_200_OK)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> JSONResponse:
    """Create a server-side session and put its opaque bearer value only in an HttpOnly cookie."""
    async with UnitOfWork(session):
        result = await AuthService(session, settings).login(str(payload.email), payload.password)

    response = JSONResponse(
        status_code=status.HTTP_200_OK,
        content=success_response(LoginResponseData(account=result.account), Message.SUCCESS),
    )
    set_auth_cookies(response, result.session_token, result.csrf_token, settings)
    return response


@router.post("/logout", response_model=ApiResponse[LogoutResponseData])
async def logout(
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> Response:
    """Revoke this exact session, then clear its browser cookies."""
    async with UnitOfWork(session):
        await AuthService(session, settings).logout(context.session)

    response = JSONResponse(content=success_response(LogoutResponseData(), Message.SUCCESS))
    clear_auth_cookies(response, settings)
    return response


@router.get("/me", response_model=ApiResponse[AccountResponse])
async def me(
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    """Return the current account using the browser session cookie, never a JWT."""
    account = await AuthService(session, settings).to_account_response(context.account)
    return success_response(account, Message.SUCCESS)


@router.post("/accounts", response_model=ApiResponse[AccountResponse], status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: CreateAccountRequest,
    _: AuthContext = Depends(require_csrf),
    __: AuthContext = Depends(require_role(RoleCode.SUPER_ADMIN)),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    """Let a CSRF-protected super administrator provision an account with a known system role."""
    async with UnitOfWork(session):
        account = await AuthService(session, settings).create_account(payload)
    return success_response(account, Message.CREATED)


@router.post("/password-reset/request", response_model=ApiResponse[PasswordResetRequestResponse])
async def request_password_reset(
    payload: PasswordResetRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    """Create a reset challenge and email it when SMTP is configured without exposing account existence."""
    async with UnitOfWork(session):
        delivery = await AuthService(session, settings).request_password_reset(str(payload.email))
    email_result = None
    if delivery is not None:
        email_result = await PasswordResetNotifier(settings).send(
            delivery.email, delivery.token, delivery.user_name
        )
    else:
        logger.warning("[PASSWORD RESET EMAIL NOT ATTEMPTED] reason=account_not_found_or_inactive")
    response_data = PasswordResetRequestResponse()
    if settings.debug or settings.environment == "development":
        response_data = PasswordResetRequestResponse(
            email_sent=bool(email_result and email_result.get("ok")),
            email_provider=email_result.get("provider") if email_result else None,
            email_message_id=email_result.get("message_id") if email_result else None,
            email_error=email_result.get("error") if email_result and not email_result.get("ok") else None,
        )
    return success_response(response_data, Message.PASSWORD_RESET_REQUEST_ACCEPTED)


@public_router.post("/forgot-password", response_model=ApiResponse[PasswordResetRequestResponse])
async def request_password_reset_otp(
    payload: LegacyPasswordResetRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    """Compatibility endpoint for the existing email -> OTP recovery screen."""
    async with UnitOfWork(session):
        delivery = await AuthService(session, settings).request_password_reset_otp(str(payload.email))
    email_result = None
    if delivery is not None:
        email_result = await PasswordResetNotifier(settings).send_otp(
            delivery.email, delivery.token, delivery.user_name
        )
    else:
        logger.warning("[PASSWORD RESET EMAIL NOT ATTEMPTED] reason=account_not_found_or_inactive")
    response_data = PasswordResetRequestResponse()
    if settings.debug or settings.environment == "development":
        response_data = PasswordResetRequestResponse(
            email_sent=bool(email_result and email_result.get("ok")),
            email_provider=email_result.get("provider") if email_result else None,
            email_message_id=email_result.get("message_id") if email_result else None,
            email_error=email_result.get("error") if email_result and not email_result.get("ok") else None,
        )
    return success_response(response_data, Message.PASSWORD_RESET_REQUEST_ACCEPTED)


@public_router.post("/verify-otp", response_model=ApiResponse[PasswordResetVerifyResponse])
async def verify_password_reset_otp(
    payload: PasswordResetOtpRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    """Validate an OTP without consuming it so the next screen can set a password."""
    valid = await AuthService(session, settings).verify_password_reset_otp(str(payload.email), payload.otp)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=Message.BAD_REQUEST)
    return success_response(PasswordResetVerifyResponse(), Message.PASSWORD_RESET_TOKEN_VALID)


@public_router.post("/reset-password", response_model=ApiResponse[PasswordResetConfirmResponse])
async def reset_password_with_otp(
    payload: LegacyPasswordResetConfirmRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> Response:
    """Compatibility endpoint that consumes the OTP and revokes existing sessions."""
    async with UnitOfWork(session):
        updated = await AuthService(session, settings).reset_password_with_otp(
            str(payload.email), payload.otp, payload.new_password
        )
    if not updated:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=Message.BAD_REQUEST)
    response = JSONResponse(content=success_response(PasswordResetConfirmResponse(), Message.PASSWORD_UPDATED))
    clear_auth_cookies(response, settings)
    return response


@router.post("/password-reset/verify", response_model=ApiResponse[PasswordResetVerifyResponse])
async def verify_password_reset(
    payload: PasswordResetVerifyRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    """Allow the client to validate a reset link before showing the replacement-password form."""
    is_valid = await AuthService(session, settings).verify_password_reset_token(payload.token)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=Message.BAD_REQUEST)
    return success_response(PasswordResetVerifyResponse(), Message.PASSWORD_RESET_TOKEN_VALID)


@router.post("/password-reset/confirm", response_model=ApiResponse[PasswordResetConfirmResponse])
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> Response:
    """Consume a valid reset token, replace the password, revoke sessions, and clear local cookies."""
    async with UnitOfWork(session):
        password_updated = await AuthService(session, settings).reset_password(payload.token, payload.password)
    if not password_updated:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=Message.BAD_REQUEST)
    response = JSONResponse(
        content=success_response(PasswordResetConfirmResponse(), Message.PASSWORD_UPDATED)
    )
    clear_auth_cookies(response, settings)
    return response
