"""Booking, transfer, and gate admission rules for event passes."""

import json
import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.auth.models import Account
from app.modules.events.pass_repository import EventPassRepository
from app.modules.events.schemas import (
    EventPassBookingRequest, EventPassCheckInRequest, EventPassShareRequest,
)
from app.modules.events.service import EventService


def serialize(value: object) -> object:
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


class EventPassService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = EventPassRepository(session)
        self.events = EventService(session)

    async def book(self, event_id: str, payload: EventPassBookingRequest, account: Account) -> dict:
        event = await self.events._authorized_event(event_id, account)
        if not event.has_pass or event.status != "Published":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pass booking is not open for this event.")
        if event.registration_deadline and event.registration_deadline < datetime.now():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Registration deadline has passed.")
        # Lock the event before counting purchases, so concurrent bookings cannot exceed capacity.
        await self.repo.one("SELECT id FROM events WHERE id=:event_id FOR UPDATE", event_id=event_id)
        if event.max_capacity and await self.repo.booked_count(event_id) + payload.member_count > event.max_capacity:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not enough passes remain for this event.")
        limit = event.max_passes_per_user or 10
        if await self.repo.buyer_count(event_id, account.id) + payload.member_count > limit:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Maximum {limit} passes permitted per member.")

        price = Decimal(event.pass_price if event.pass_price is not None else event.fee_amount or 0)
        amount = (price * payload.member_count).quantize(Decimal("0.01"))
        if amount > 0 and payload.payment_method == "wallet":
            wallet = await self.repo.wallet(account.id)
            if not wallet or not wallet["security_pin"] or wallet["security_pin"] != payload.pin:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid wallet security PIN.")
            if Decimal(wallet["balance"]) < amount:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Insufficient wallet balance.")
            await self.repo.debit_wallet(wallet["id"], amount, event.title)
        elif amount > 0 and payload.payment_method == "upi":
            wallet = await self.repo.wallet(account.id)
            if not wallet:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "A Nestora Wallet is required to record this UPI payment.")
            await self.repo.record_upi_payment(wallet["id"], amount, event.title)

        buyer = await self.repo.buyer(account.id)
        pass_id = str(uuid.uuid4())
        pass_code = f"PASS-{uuid.uuid4().hex[:8].upper()}"
        await self.repo.insert_pass({
            "id": pass_id, "event_id": event_id, "account_id": account.id,
            "buyer_name": buyer["name"] if buyer else account.email,
            "buyer_mobile": buyer["mobile"] if buyer else None,
            "total_passes": payload.member_count, "remaining_passes": payload.member_count,
            "pass_code": pass_code,
            "qr_data": json.dumps({"pass_id": pass_id, "pass_code": pass_code, "event_id": event_id}),
            "amount_paid": amount, "payment_method": payload.payment_method if amount > 0 else "free",
            "payment_status": "Completed", "status": "Active",
            "shared_from_pass_id": None, "shared_to_mobile": None,
        })
        rsvp = await self.events.repository.rsvp(event_id, account.id)
        if rsvp:
            rsvp.status = "going"
            rsvp.is_deleted = False
        else:
            from app.modules.events.models import EventRSVP
            self.events.repository.add_rsvp(EventRSVP(
                id=str(uuid.uuid4()), event_id=event_id, account_id=account.id,
                status="going", is_deleted=False,
            ))
        await self.repo.session.flush()
        return {
            "pass_id": pass_id, "pass_code": pass_code,
            "pass_link": f"/event-pass/{pass_id}", "member_count": payload.member_count,
            "total_amount": float(amount), "message": "Pass generated successfully.",
        }

    async def my_passes(self, event_id: str, account: Account) -> list[dict]:
        await self.events._authorized_event(event_id, account)
        rows = await self.repo.my_passes(event_id, account.id)
        for row in rows:
            row["transfers"] = await self.repo.transfers(row["id"])
        return serialize(rows)

    async def detail(self, pass_id: str, account: Account | None) -> dict:
        row = await self.repo.pass_by_id(pass_id)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Pass not found.")
        event = await self.events.repository.get(row["event_id"])
        if not event:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found.")
        owner = bool(account and account.id == row["account_id"])
        if account and not owner:
            try:
                await self.events._manager_event(event.id, account)
                owner = True
            except HTTPException:
                pass
        public_pass = {key: row[key] for key in (
            "id", "event_id", "pass_code", "buyer_name", "total_passes", "remaining_passes",
            "checked_in_passes", "status", "created_at",
        )}
        public_pass["is_shared"] = bool(row["shared_from_pass_id"])
        if owner:
            public_pass.update({"buyer_mobile": row["buyer_mobile"], "amount_paid": row["amount_paid"]})
        association = await self.repo.one(
            "SELECT id,name,country FROM associations WHERE id=:id", id=event.association_id,
        ) if event.association_id else None
        return serialize({
            "pass": public_pass,
            "event": {"id": event.id, "title": event.title, "starts_at": event.starts_at,
                      "ends_at": event.ends_at, "location": event.location, "banner_url": event.banner_url,
                      "description": event.description},
            "association": association,
            "transfers": await self.repo.transfers(pass_id) if owner else [],
            "is_owner": owner,
        })

    async def share(self, pass_id: str, payload: EventPassShareRequest, account: Account) -> dict:
        row = await self.repo.pass_by_id(pass_id, lock=True)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Pass not found.")
        if row["account_id"] != account.id:
            await self.events._manager_event(row["event_id"], account)
        if row["shared_from_pass_id"]:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "A shared pass cannot be transferred again.")
        if row["status"] != "Active" or payload.count > row["remaining_passes"]:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not enough active passes remain to share.")
        mobile = "".join(c for c in payload.recipient_mobile if c.isdigit())
        if len(mobile) < 7:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Enter a valid mobile number.")
        recipient = await self.repo.recipient(mobile[-10:])
        recipient_id = recipient["account_id"] if recipient else row["account_id"]
        recipient_name = recipient["name"] if recipient else f"Member ({payload.recipient_mobile})"
        new_id = str(uuid.uuid4())
        new_code = f"PASS-{uuid.uuid4().hex[:8].upper()}"
        await self.repo.execute(
            "UPDATE event_passes SET remaining_passes=remaining_passes-:count,updated_at=NOW() WHERE id=:id",
            count=payload.count, id=pass_id,
        )
        await self.repo.insert_pass({
            "id": new_id, "event_id": row["event_id"], "account_id": recipient_id,
            "buyer_name": recipient_name, "buyer_mobile": payload.recipient_mobile,
            "total_passes": payload.count, "remaining_passes": payload.count,
            "pass_code": new_code,
            "qr_data": json.dumps({"pass_id": new_id, "pass_code": new_code, "event_id": row["event_id"]}),
            "amount_paid": Decimal("0"), "payment_method": "Transferred",
            "payment_status": "Completed", "status": "Active",
            "shared_from_pass_id": pass_id, "shared_to_mobile": payload.recipient_mobile,
        })
        sender = await self.repo.buyer(account.id)
        await self.repo.execute(
            "INSERT INTO event_pass_transfers "
            "(id,original_pass_id,new_pass_id,event_id,sender_account_id,sender_name,sender_mobile,"
            "recipient_mobile,recipient_name,count) VALUES "
            "(:id,:original,:new,:event_id,:sender,:sender_name,:sender_mobile,:mobile,:name,:count)",
            id=str(uuid.uuid4()), original=pass_id, new=new_id, event_id=row["event_id"],
            sender=account.id, sender_name=sender["name"] if sender else account.email,
            sender_mobile=sender["mobile"] if sender else None,
            mobile=payload.recipient_mobile, name=recipient_name, count=payload.count,
        )
        return {
            "new_pass_id": new_id, "new_pass_link": f"/event-pass/{new_id}",
            "remaining_passes": row["remaining_passes"] - payload.count,
            "shared_count": payload.count, "message": "Pass shared successfully.",
        }

    async def admin_list(self, event_id: str, account: Account) -> dict:
        event = await self.events._manager_event(event_id, account)
        rows = await self.repo.admin_passes(event_id)
        summary = {
            "total_passes_booked": sum(p["total_passes"] for p in rows if not p["shared_from_pass_id"]),
            "total_active_passes": sum(p["remaining_passes"] for p in rows),
            "total_checked_in": sum(p["checked_in_passes"] for p in rows),
            "total_pass_records": len(rows),
        }
        if getattr(getattr(account, "role", None), "code", None) == RoleCode.BOARD_MEMBER:
            summary["total_revenue"] = sum(Decimal(p["amount_paid"]) for p in rows)
        return serialize({"event": {"id": event.id, "title": event.title}, "passes": rows, "summary": summary})

    async def verify(self, event_id: str, query: str, account: Account) -> dict:
        await self.events._manager_event(event_id, account)
        raw = query.strip()
        if "/event-pass/" in raw:
            raw = raw.split("/event-pass/")[-1].split("?")[0].split("/")[0]
        elif raw.startswith("{"):
            try:
                raw = json.loads(raw).get("pass_id", raw)
            except ValueError:
                pass
        mobile = "".join(c for c in raw if c.isdigit())
        row = await self.repo.scan_match(event_id, raw, mobile[-10:] if len(mobile) >= 7 else None)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No matching event pass found.")
        if row["event_id"] != event_id:
            return {"ok": False, "wrong_event": True, "message": "This pass belongs to another event.",
                    "pass": {"id": row["id"], "pass_code": row["pass_code"]}}
        return serialize({
            "ok": True, "wrong_event": False, "pass": row,
            "checkins": await self.repo.checkins(row["id"]),
            "remaining_passes": row["remaining_passes"],
            "checked_in_passes": row["checked_in_passes"],
            "total_passes": row["total_passes"],
            "can_check_in": row["status"] == "Active" and row["remaining_passes"] > 0,
        })

    async def check_in(self, event_id: str, pass_id: str, payload: EventPassCheckInRequest, account: Account) -> dict:
        await self.events._manager_event(event_id, account)
        row = await self.repo.pass_by_id(pass_id, lock=True)
        if not row or row["event_id"] != event_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Pass not found for this event.")
        if row["status"] != "Active" or payload.admit_count > row["remaining_passes"]:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not enough active passes remain.")
        remaining = row["remaining_passes"] - payload.admit_count
        checked = row["checked_in_passes"] + payload.admit_count
        await self.repo.execute(
            "UPDATE event_passes SET remaining_passes=:remaining,checked_in_passes=:checked,"
            "last_checked_in_at=NOW(),last_checked_in_by=:checker,updated_at=NOW(),"
            "status=:status WHERE id=:id",
            remaining=remaining, checked=checked, checker=account.id,
            status="Checked In" if remaining == 0 else "Active", id=pass_id,
        )
        await self.repo.execute(
            "INSERT INTO event_pass_checkins "
            "(id,pass_id,event_id,admitted_count,checked_in_by,checked_in_by_name,notes) "
            "VALUES (:id,:pass_id,:event_id,:count,:checker,:name,:notes)",
            id=str(uuid.uuid4()), pass_id=pass_id, event_id=event_id,
            count=payload.admit_count, checker=account.id, name=account.email,
            notes=payload.notes,
        )
        return {"admitted_now": payload.admit_count, "remaining_passes": remaining,
                "checked_in_passes": checked, "message": "Check-in successful."}
