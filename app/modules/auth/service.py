"""Authentication business rules, kept separate from HTTP routing and SQL query details."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
import uuid
import secrets

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import AccountStatus, RoleCode
from app.core.messages import Message
from app.core.security import (
    generate_secret,
    hash_password,
    hash_secret,
    session_expiry,
    utc_now,
    verify_password,
)
from app.modules.auth.models import Account, AuthSession, PasswordResetChallenge
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import (
    AccountResponse,
    CreateAccountRequest,
    CreateMemberAccountRequest,
    RolePermissionResponse,
    UpdateDetailsRequest,
)
from app.modules.employees.models import Employee
from app.modules.users.models import UserCode, UserDetail
from app.modules.iam.models import Role


@dataclass
class LoginResult:
    """Secrets are returned only to the router so it can set browser cookies after commit."""

    account: AccountResponse
    session_token: str
    csrf_token: str


@dataclass
class PasswordResetDelivery:
    """The router receives the raw reset token only long enough to pass it to the email notifier."""

    email: str
    token: str


class AuthService:
    """Use case layer for login, current-user loading, and logout."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.repository = AuthRepository(session)
        self.settings = settings

    async def login(self, email: str, password: str) -> LoginResult:
        """Validate active credentials and stage a revocable opaque session."""
        account = await self.repository.get_account_by_email(email.lower())
        if not account or not verify_password(password, account.password_hash):
            # Keep one message for either mismatch so attackers cannot discover valid emails.
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=Message.INVALID_CREDENTIALS)
        if account.status != AccountStatus.ACTIVE or not account.role or not account.role.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=Message.FORBIDDEN)

        session_token = generate_secret()
        csrf_token = generate_secret()
        self.repository.add_session(
            AuthSession(
                account_id=account.id,
                token_hash=hash_secret(session_token),
                csrf_token_hash=hash_secret(csrf_token),
                expires_at=session_expiry(self.settings),
                last_seen_at=utc_now(),
            )
        )
        return LoginResult(
            account=await self.to_account_response(account),
            session_token=session_token,
            csrf_token=csrf_token,
        )

    async def validate_access_code(self, code: str) -> dict:
        """Validate an onboarding code without consuming it."""
        if not re.fullmatch(r"[A-Z0-9\-!@#$%^&*]{4,20}", code):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid code format.")
        record = await self.repository.session.scalar(select(UserCode).where(UserCode.login_code == code))
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Invalid Code. Please try again.")
        if record.status != "active":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "This code is no longer active.")
        if record.expires_at:
            now = datetime.now(timezone.utc)
            expiry = record.expires_at
            if expiry.tzinfo is None:
                now = now.replace(tzinfo=None)
            if expiry < now:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "This code has expired.")
        linked = await self.repository.session.scalar(
            select(Account.id).join(UserDetail, UserDetail.user_id == Account.user_id).where(UserDetail.code_id == record.id)
        )
        return {"valid": True, "code_id": record.id, "already_registered": linked is not None}

    async def request_access_code(self, name: str, email: str, contact_number: str) -> None:
        """Record a public access request for administrator review."""
        pending = await self.repository.session.scalar(
            text("SELECT id FROM code_requests WHERE email = :email AND status = 'pending' LIMIT 1"),
            {"email": email.lower()},
        )
        if pending:
            raise HTTPException(status.HTTP_409_CONFLICT, "A request with this email is already pending.")
        await self.repository.session.execute(
            text(
                "INSERT INTO code_requests (id, name, email, contact_number, status) "
                "VALUES (:id, :name, :email, :contact_number, 'pending')"
            ),
            {"id": str(uuid.uuid4()), "name": name.strip(), "email": email.lower(), "contact_number": contact_number.strip()},
        )
        count = await self.repository.session.scalar(text("SELECT COUNT(id) FROM service_requests")) or 0
        await self.repository.session.execute(
            text(
                "INSERT INTO service_requests "
                "(id, user_id, association_id, unit_id, sr_display_id, service_type, custom_title, description, status) "
                "VALUES (:id, NULL, NULL, NULL, :display_id, 'Access Code Request', :title, :description, 'New')"
            ),
            {
                "id": str(uuid.uuid4()),
                "display_id": f"SR-PUB-#{int(count) + 1}",
                "title": f"Code Request: {name.strip()}",
                "description": f"Name: {name.strip()}\nEmail: {email.lower()}\nContact Number: {contact_number.strip()}",
            },
        )

    async def get_user_details_by_code(self, code: str) -> dict:
        """Load the onboarding profile associated with an access code."""
        result = await self.repository.session.execute(
            text(
                "SELECT u.user_id, u.code_id, u.name, u.email, u.contact_number, u.address, "
                "assoc.name AS association_name, assoc.address_line_1, assoc.address_line_2, "
                "assoc.city, assoc.state, assoc.pincode, b.name AS block_name, un.unit_number "
                "FROM user_details u JOIN user_codes uc ON uc.id = u.code_id "
                "LEFT JOIN units un ON u.unit_id = un.id "
                "LEFT JOIN blocks b ON un.block_id = b.id "
                "LEFT JOIN associations assoc ON b.association_id = assoc.id OR u.association_id = assoc.id "
                "WHERE uc.login_code = :code AND u.is_deleted = 0 LIMIT 1"
            ),
            {"code": code.strip().upper()},
        )
        row = result.mappings().first()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Details not found for this code.")
        data = dict(row)
        if not data.get("address"):
            parts = []
            if data.get("block_name") and data.get("unit_number"):
                parts.append(f"Block {data['block_name']} - Unit {data['unit_number']}")
            elif data.get("association_name"):
                parts.append(data["association_name"])
            for key in ("address_line_1", "address_line_2"):
                if data.get(key):
                    parts.append(data[key])
            location = ", ".join(filter(None, (data.get("city"), data.get("state"))))
            if location and data.get("pincode"):
                location += f" - {data['pincode']}"
            elif data.get("pincode"):
                location = str(data["pincode"])
            if location:
                parts.append(location)
            data["address"] = ", ".join(parts)
        return data

    async def create_member_account(self, payload: CreateMemberAccountRequest) -> LoginResult:
        """Create a resident account from an active onboarding code and start a session."""
        if payload.password != payload.confirm_password:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Passwords do not match.")
        code = await self.repository.session.scalar(
            select(UserCode).where(UserCode.login_code == payload.code, UserCode.status == "active")
        )
        if code is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Access code is invalid or inactive.")
        detail = await self.repository.session.scalar(
            select(UserDetail).where(UserDetail.code_id == code.id, UserDetail.is_deleted.is_(False))
        )
        if detail is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No member details linked to this code.")
        if await self.repository.get_account_by_email(str(payload.email).lower()):
            raise HTTPException(status.HTTP_409_CONFLICT, "An account already exists for this email.")
        role = await self.repository.session.scalar(
            select(Role).where(Role.id == detail.role_id, Role.is_active.is_(True), Role.is_deleted.is_(False))
        ) if detail.role_id else None
        if role is None:
            role = await self.repository.get_role_by_code(RoleCode.HOMEOWNER)
        if role is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Homeowner role is not configured.")
        account = Account(
            email=str(payload.email).lower(),
            password_hash=hash_password(payload.password),
            role_id=role.id,
            role=role,
            user_id=detail.user_id,
            status=AccountStatus.ACTIVE,
            password_changed_at=utc_now(),
        )
        self.repository.add_account(account)
        code.status = "used"
        await self.repository.session.flush()
        session_token = generate_secret()
        csrf_token = generate_secret()
        self.repository.add_session(AuthSession(
            account_id=account.id,
            token_hash=hash_secret(session_token),
            csrf_token_hash=hash_secret(csrf_token),
            expires_at=session_expiry(self.settings),
            last_seen_at=utc_now(),
        ))
        await self.repository.session.flush()
        return LoginResult(
            account=await self.to_account_response(account),
            session_token=session_token,
            csrf_token=csrf_token,
        )

    async def request_details_update(self, payload: UpdateDetailsRequest) -> None:
        """Store a resident correction request for administrator review."""
        code = await self.repository.session.scalar(select(UserCode).where(UserCode.login_code == payload.code.upper()))
        if code is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Invalid access code.")
        detail = await self.repository.session.scalar(select(UserDetail).where(UserDetail.code_id == code.id))
        if detail is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Details not found for this code.")
        await self.repository.session.execute(
            text(
                "INSERT INTO update_requests "
                "(id, code_id, requested_name, requested_address, requested_email, requested_contact, note, status) "
                "VALUES (:id, :code_id, :name, :address, :email, :contact, :note, 'open')"
            ),
            {
                "id": str(uuid.uuid4()), "code_id": code.id,
                "name": payload.requested_name, "address": payload.requested_address,
                "email": str(payload.requested_email) if payload.requested_email else None,
                "contact": payload.requested_contact, "note": payload.note,
            },
        )

    async def get_authenticated_session(self, raw_token: str | None) -> AuthSession:
        """Resolve a browser cookie to an active session, account, and role."""
        if not raw_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=Message.UNAUTHORIZED)
        auth_session = await self.repository.get_active_session(hash_secret(raw_token), utc_now())
        if not auth_session or not auth_session.account:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=Message.UNAUTHORIZED)
        account = auth_session.account
        if account.status != AccountStatus.ACTIVE or not account.role or not account.role.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=Message.FORBIDDEN)
        return auth_session

    async def logout(self, auth_session: AuthSession) -> None:
        """Revoke the current server-side session so copying a past cookie cannot restore access."""
        await self.repository.revoke_session(auth_session, utc_now())

    async def create_account(self, payload: CreateAccountRequest) -> AccountResponse:
        """Create an active account after the router has enforced privileged role and CSRF checks."""
        email = str(payload.email).lower()
        if await self.repository.get_account_by_email(email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=Message.BAD_REQUEST)
        role = await self.repository.get_role_by_code(payload.role_code)
        if role is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=Message.BAD_REQUEST)
        account = Account(
            email=email,
            password_hash=hash_password(payload.password),
            role_id=role.id,
            role=role,
            status=AccountStatus.ACTIVE,
            password_changed_at=utc_now(),
        )
        self.repository.add_account(account)
        await self.repository.session.flush()
        return await self.to_account_response(account)

    async def request_password_reset(self, email: str) -> PasswordResetDelivery | None:
        """Create one fresh challenge for an active account without disclosing account existence."""
        account = await self.repository.get_account_by_email(email.lower())
        if not account or account.status != AccountStatus.ACTIVE:
            return None
        now = utc_now()
        await self.repository.consume_active_reset_challenges_for_account(account.id, now)
        token = generate_secret()
        self.repository.add_password_reset_challenge(
            PasswordResetChallenge(
                account_id=account.id,
                token_hash=hash_secret(token),
                expires_at=now + timedelta(minutes=self.settings.password_reset_ttl_minutes),
            )
        )
        return PasswordResetDelivery(email=account.email, token=token)

    async def request_password_reset_otp(self, email: str) -> PasswordResetDelivery | None:
        """Create a six-digit challenge for the legacy-compatible OTP recovery flow."""
        account = await self.repository.get_account_by_email(email.lower())
        if not account or account.status != AccountStatus.ACTIVE:
            return None
        now = utc_now()
        await self.repository.consume_active_reset_challenges_for_account(account.id, now)
        otp = f"{secrets.randbelow(1_000_000):06d}"
        self.repository.add_password_reset_challenge(
            PasswordResetChallenge(
                account_id=account.id,
                token_hash=hash_secret(otp),
                expires_at=now + timedelta(minutes=self.settings.password_reset_ttl_minutes),
            )
        )
        return PasswordResetDelivery(email=account.email, token=otp)

    async def verify_password_reset_otp(self, email: str, otp: str) -> bool:
        """Verify an OTP only for the account that requested it."""
        account = await self.repository.get_account_by_email(email.lower())
        if not account:
            return False
        challenge = await self.repository.get_active_password_reset_challenge(hash_secret(otp), utc_now())
        return bool(challenge and challenge.account_id == account.id)

    async def reset_password_with_otp(self, email: str, otp: str, new_password: str) -> bool:
        """Consume an OTP, update the password, and revoke sessions atomically."""
        account = await self.repository.get_account_by_email(email.lower())
        if not account:
            return False
        challenge = await self.repository.get_active_password_reset_challenge(hash_secret(otp), utc_now())
        if challenge is None or challenge.account_id != account.id:
            return False
        now = utc_now()
        account.password_hash = hash_password(new_password)
        account.password_changed_at = now
        challenge.consumed_at = now
        await self.repository.consume_active_reset_challenges_for_account(account.id, now)
        await self.repository.revoke_all_sessions_for_account(account.id, now)
        await self.repository.session.flush()
        return True

    async def verify_password_reset_token(self, token: str) -> bool:
        """Check whether a reset token is unconsumed and unexpired without changing account state."""
        challenge = await self.repository.get_active_password_reset_challenge(hash_secret(token), utc_now())
        return challenge is not None

    async def reset_password(self, token: str, new_password: str) -> bool:
        """Atomically replace the password, consume reset links, and revoke every active session."""
        now = utc_now()
        challenge = await self.repository.get_active_password_reset_challenge(hash_secret(token), now)
        if challenge is None or challenge.account is None:
            return False
        challenge.account.password_hash = hash_password(new_password)
        challenge.account.password_changed_at = now
        challenge.consumed_at = now
        await self.repository.consume_active_reset_challenges_for_account(challenge.account_id, now)
        await self.repository.revoke_all_sessions_for_account(challenge.account_id, now)
        await self.repository.session.flush()
        return True

    async def to_account_response(self, account: Account) -> AccountResponse:
        """Translate an account and its database permission matrix into the client API shape."""
        if not account.role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=Message.FORBIDDEN)
        rows = await self.repository.get_role_permissions(account.role_id)
        name = await self._account_name(account)
        association_id = await self._account_association_id(account)
        return AccountResponse(
            account_id=account.id,
            email=account.email,
            name=name,
            role=account.role.name,
            role_code=account.role.code,
            association_id=association_id,
            role_permissions=[
                RolePermissionResponse(
                    feature_id=feature.id,
                    feature_name=feature.name,
                    feature_code=feature.code,
                    parent_id=feature.parent_id,
                    icon=feature.icon,
                    url=feature.route,
                    order_index=feature.order_index,
                    sidebar_order=permission.sidebar_order,
                    can_create=permission.can_create,
                    can_view=permission.can_view,
                    can_update=permission.can_update,
                    can_delete=permission.can_delete,
                )
                for permission, feature in rows
            ],
        )

    async def _account_association_id(self, account: Account) -> str | None:
        """Resolve a resident's association through the assigned unit and block."""
        if not account.user_id:
            return None
        return await self.repository.session.scalar(
            text(
                "SELECT COALESCE(ud.association_id, b.association_id) "
                "FROM user_details ud "
                "LEFT JOIN units u ON u.id = ud.unit_id "
                "LEFT JOIN blocks b ON b.id = u.block_id "
                "WHERE ud.user_id = :user_id AND ud.is_deleted = 0 LIMIT 1"
            ),
            {"user_id": account.user_id},
        )

    async def _account_name(self, account: Account) -> str | None:
        """Return the resident or employee display name associated with an account."""
        if account.user_id:
            name = await self.repository.session.scalar(
                select(UserDetail.name).where(
                    UserDetail.user_id == account.user_id,
                    UserDetail.is_deleted.is_(False),
                )
            )
            if name:
                return name
        if account.employee_id:
            return await self.repository.session.scalar(
                select(Employee.name).where(
                    Employee.employee_id == account.employee_id,
                    Employee.is_deleted.is_(False),
                )
            )
        return None
