"""Business rules and authorization for service-request workflows."""

import re
import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.auth.models import Account
from app.modules.service_requests.constants import (
    ADMIN_ROLE_CODES,
    ASSOCIATION_VIEW_ROLE_CODES,
    RESIDENT_ONLY_ROLE_CODES,
    STATUS_MANAGER_ROLE_CODES,
    ServiceRequestStatus,
)
from app.modules.service_requests.messages import ServiceRequestMessage
from app.modules.service_requests.models import ServiceRequest, ServiceRequestThreadMessage
from app.modules.service_requests.repository import ServiceRequestRepository
from app.modules.service_requests.schemas import (
    ServiceRequestCreateRequest,
    ServiceRequestMappingRequest,
    ServiceRequestMessageRequest,
)


@dataclass(frozen=True)
class ServiceRequestMessageEvent:
    """Committed message data and its server-authorized WebSocket recipients."""

    request_id: str
    message: dict
    recipient_account_ids: set[str]


class ServiceRequestService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = ServiceRequestRepository(session)

    @staticmethod
    def role_code(account: Account) -> RoleCode:
        if account.role is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, ServiceRequestMessage.FORBIDDEN)
        try:
            return RoleCode(account.role.code)
        except ValueError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, ServiceRequestMessage.FORBIDDEN) from exc

    async def list(self, account: Account, association_id: str | None = None) -> list[dict]:
        role_code = self.role_code(account)
        if role_code in RESIDENT_ONLY_ROLE_CODES:
            return await self.repository.list_for_resident(account.id, account.user_id)
        if role_code not in ASSOCIATION_VIEW_ROLE_CODES:
            return await self.repository.list_for_resident(account.id, account.user_id)

        allowed_ids = await self._allowed_association_ids(account, role_code)
        if association_id:
            if role_code != RoleCode.SUPER_ADMIN and association_id not in allowed_ids:
                raise HTTPException(status.HTTP_403_FORBIDDEN, ServiceRequestMessage.FORBIDDEN)
            return await self.repository.list_for_associations(
                [association_id],
                include_unassigned=role_code in ADMIN_ROLE_CODES,
            )

        if role_code == RoleCode.SUPER_ADMIN:
            return await self.repository.list_all()
        return await self.repository.list_for_associations(
            allowed_ids,
            include_unassigned=role_code in ADMIN_ROLE_CODES,
        )

    async def detail(self, request_id: str, account: Account) -> dict:
        request = await self._authorized_request(request_id, account)
        detail = await self.repository.get_detail(request.id)
        if detail is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, ServiceRequestMessage.NOT_FOUND)
        return detail

    async def create(self, payload: ServiceRequestCreateRequest, account: Account) -> str:
        role_code = self.role_code(account)
        is_admin = role_code in ADMIN_ROLE_CODES
        if payload.user_id and not is_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, ServiceRequestMessage.FORBIDDEN)

        resident_identifier = payload.user_id if is_admin and payload.user_id else account.id
        resident = await self.repository.resident_context(resident_identifier)
        if not resident or not resident.get("association_id"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, ServiceRequestMessage.USER_NOT_MAPPED)

        if is_admin:
            await self._require_admin_association(account, resident["association_id"])
            if payload.association_id and payload.association_id != resident["association_id"]:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    ServiceRequestMessage.INVALID_ASSOCIATION,
                )

        display_id = await self._display_id(resident)
        request = ServiceRequest(
            id=str(uuid.uuid4()),
            user_id=resident["request_user_id"],
            association_id=resident["association_id"],
            unit_id=resident["unit_id"],
            sr_display_id=display_id,
            service_type=payload.service_type,
            sub_category=payload.sub_category,
            custom_title=payload.custom_title,
            description=payload.description,
            image_url=payload.image_url,
            incoming_call_no=payload.incoming_call_no,
            status=(
                ServiceRequestStatus.IN_PROGRESS
                if payload.user_id and is_admin
                else ServiceRequestStatus.NEW
            ),
            is_deleted=False,
        )
        self.repository.add(request)
        await self.repository.session.flush()

        if payload.user_id and is_admin:
            await self.repository.add_notification(
                resident.get("account_id"),
                f"Service Request Created: {display_id}",
                f"An admin created a new {payload.service_type} request on your behalf.",
                request.id,
            )
        else:
            await self.repository.notify_association_admins(
                resident["association_id"],
                f"New Service Request: {display_id}",
                f"{resident.get('name') or 'A resident'} created a new {payload.service_type} "
                f"request for Unit {resident.get('unit_number') or 'N/A'}.",
                request.id,
            )
        return request.id

    async def update_status(
        self,
        request_id: str,
        new_status: ServiceRequestStatus,
        account: Account,
    ) -> None:
        role_code = self.role_code(account)
        if role_code not in STATUS_MANAGER_ROLE_CODES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, ServiceRequestMessage.FORBIDDEN)
        request = await self._authorized_request(request_id, account)
        request.status = new_status.value
        await self.repository.session.flush()
        if role_code in ADMIN_ROLE_CODES:
            resident = (
                await self.repository.resident_context(request.user_id)
                if request.user_id
                else None
            )
            await self.repository.add_notification(
                resident.get("account_id") if resident else None,
                f"Service Request Updated: {request.sr_display_id or request.id}",
                f"Your service request status was updated to '{new_status.value}'.",
                request.id,
            )

    async def map(
        self,
        request_id: str,
        payload: ServiceRequestMappingRequest,
        account: Account,
    ) -> None:
        role_code = self.role_code(account)
        if role_code not in ADMIN_ROLE_CODES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, ServiceRequestMessage.FORBIDDEN)
        request = await self.repository.get(request_id)
        if request is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, ServiceRequestMessage.NOT_FOUND)
        await self._require_admin_association(account, payload.association_id)
        if not await self.repository.unit_belongs_to_association(
            payload.unit_id,
            payload.association_id,
        ):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, ServiceRequestMessage.INVALID_UNIT)
        if not await self.repository.resident_belongs_to_unit(payload.user_id, payload.unit_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, ServiceRequestMessage.INVALID_RESIDENT)
        resident = await self.repository.resident_context(payload.user_id)
        if resident is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, ServiceRequestMessage.INVALID_RESIDENT)
        request.association_id = payload.association_id
        request.unit_id = payload.unit_id
        request.user_id = resident["request_user_id"]
        await self.repository.session.flush()
        await self.repository.add_notification(
            resident.get("account_id"),
            f"Service Request Assigned: {request.sr_display_id or request.id}",
            "A community administrator assigned a service request to your unit.",
            request.id,
        )

    async def delete(self, request_id: str, account: Account) -> None:
        role_code = self.role_code(account)
        if role_code not in ADMIN_ROLE_CODES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, ServiceRequestMessage.FORBIDDEN)
        request = await self._authorized_request(request_id, account)
        request.is_deleted = True

    async def messages(self, request_id: str, account: Account) -> list[dict]:
        await self._authorized_request(request_id, account)
        return await self.repository.messages(request_id)

    async def send_message(
        self,
        request_id: str,
        payload: ServiceRequestMessageRequest,
        account: Account,
    ) -> ServiceRequestMessageEvent:
        request = await self._authorized_request(request_id, account)
        message = ServiceRequestThreadMessage(
            id=str(uuid.uuid4()),
            service_request_id=request.id,
            sender_id=account.id,
            message=payload.message,
            attachment_url=payload.attachment_url,
        )
        self.repository.add_message(message)
        await self.repository.session.flush()

        resident = (
            await self.repository.resident_context(request.user_id)
            if request.user_id
            else None
        )
        resident_account_id = resident.get("account_id") if resident else None
        title = f"New Message: {request.sr_display_id or request.id}"
        if resident_account_id == account.id:
            if request.association_id:
                await self.repository.notify_association_admins(
                    request.association_id,
                    title,
                    "A resident sent a new message on their service request.",
                    request.id,
                )
        else:
            await self.repository.add_notification(
                resident_account_id,
                title,
                "A community administrator sent a new message on your service request.",
                request.id,
            )
        message_event = await self.repository.message_event(message.id)
        if message_event is None:
            raise RuntimeError("Persisted service-request message could not be loaded")
        return ServiceRequestMessageEvent(
            request_id=request.id,
            message=message_event,
            recipient_account_ids=await self.repository.participant_account_ids(request),
        )

    async def blocks(self, association_id: str, account: Account) -> list[dict]:
        resolved_id = await self._resolve_association_id(association_id, account)
        await self._require_association_access(account, resolved_id)
        return await self.repository.blocks(resolved_id)

    async def units(self, association_id: str, account: Account) -> list[dict]:
        await self._require_admin_association(account, association_id)
        return await self.repository.units(association_id)

    async def block_units(self, block_id: str, account: Account) -> list[dict]:
        association_id = await self.repository.block_association_id(block_id)
        if not association_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Block not found")
        await self._require_admin_association(account, association_id)
        return await self.repository.block_units(block_id)

    async def residents(self, unit_id: str, account: Account) -> list[dict]:
        association_id = await self.repository.unit_association_id(unit_id)
        if not association_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unit not found")
        await self._require_admin_association(account, association_id)
        return await self.repository.residents(unit_id)

    async def _authorized_request(self, request_id: str, account: Account) -> ServiceRequest:
        request = await self.repository.get(request_id)
        if request is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, ServiceRequestMessage.NOT_FOUND)
        role_code = self.role_code(account)
        if role_code in RESIDENT_ONLY_ROLE_CODES:
            if not await self._resident_can_access(request, account):
                raise HTTPException(status.HTTP_403_FORBIDDEN, ServiceRequestMessage.FORBIDDEN)
            return request
        if role_code not in ASSOCIATION_VIEW_ROLE_CODES:
            if not await self._resident_can_access(request, account):
                raise HTTPException(status.HTTP_403_FORBIDDEN, ServiceRequestMessage.FORBIDDEN)
            return request
        if role_code == RoleCode.SUPER_ADMIN:
            return request
        allowed_ids = await self._allowed_association_ids(account, role_code)
        if request.association_id is None and role_code in ADMIN_ROLE_CODES:
            return request
        if request.association_id not in allowed_ids:
            raise HTTPException(status.HTTP_403_FORBIDDEN, ServiceRequestMessage.FORBIDDEN)
        return request

    async def _resident_can_access(self, request: ServiceRequest, account: Account) -> bool:
        if request.user_id in {account.id, account.user_id}:
            return True
        resident_context = await self.repository.resident_unit_context(account.id, account.user_id)
        return bool(
            resident_context
            and request.unit_id == resident_context.get("unit_id")
            and request.association_id == resident_context.get("association_id")
        )

    async def _allowed_association_ids(self, account: Account, role_code: RoleCode) -> list[str]:
        if role_code == RoleCode.SUPER_ADMIN:
            return []
        if role_code in ADMIN_ROLE_CODES:
            return await self.repository.admin_association_ids(account.id)
        association_id = await self.repository.member_association_id(account)
        return [association_id] if association_id else []

    async def _require_admin_association(self, account: Account, association_id: str) -> None:
        role_code = self.role_code(account)
        if role_code not in ADMIN_ROLE_CODES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, ServiceRequestMessage.FORBIDDEN)
        if role_code == RoleCode.SUPER_ADMIN:
            return
        allowed_ids = await self.repository.admin_association_ids(account.id)
        if association_id not in allowed_ids:
            raise HTTPException(status.HTTP_403_FORBIDDEN, ServiceRequestMessage.FORBIDDEN)

    async def _require_association_access(self, account: Account, association_id: str) -> None:
        role_code = self.role_code(account)
        if role_code == RoleCode.SUPER_ADMIN:
            return
        if role_code in ADMIN_ROLE_CODES:
            allowed_ids = await self.repository.admin_association_ids(account.id)
        else:
            member_association_id = await self.repository.member_association_id(account)
            allowed_ids = [member_association_id] if member_association_id else []
        if association_id not in allowed_ids:
            raise HTTPException(status.HTTP_403_FORBIDDEN, ServiceRequestMessage.FORBIDDEN)

    async def _resolve_association_id(self, association_id: str, account: Account) -> str:
        if association_id != "me":
            return association_id
        resolved_id = await self.repository.member_association_id(account)
        if not resolved_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, ServiceRequestMessage.USER_NOT_MAPPED)
        return resolved_id

    async def _display_id(self, resident: dict) -> str:
        association_name = resident.get("association_name") or ""
        initials = "".join(word[0].upper() for word in association_name.split() if word) or "XX"
        block_name = self._display_segment(resident.get("block_name"), "NA")
        unit_number = self._display_segment(resident.get("unit_number"), "NA")
        sequence = await self.repository.next_display_sequence(resident.get("unit_id"))
        return f"SR-{initials}-{block_name}-{unit_number}#{sequence}"

    @staticmethod
    def _display_segment(value: object, fallback: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_-]", "-", str(value or fallback).strip())
        return cleaned or fallback
