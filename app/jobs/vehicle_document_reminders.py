"""Create one in-app notification for each vehicle document due for renewal."""

from dataclasses import dataclass
from datetime import date
from typing import Literal
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.service import create_notification


DocumentType = Literal["insurance", "puc"]
DELIVERY_TABLE = "vehicle_document_reminder_deliveries"


@dataclass(frozen=True)
class DueVehicleDocument:
    vehicle_id: str
    account_id: str
    registration_number: str
    document_type: DocumentType
    reminder_date: date

    @property
    def label(self) -> str:
        return "Insurance policy" if self.document_type == "insurance" else "PUC certificate"


async def send_due_vehicle_document_reminders(
    session: AsyncSession,
    *,
    reminder_date: date,
) -> int:
    """Create due reminders once, even if the scheduled job is retried.

    The unique delivery record is inserted before the notification. Because this
    function runs within the caller's transaction, a failed notification rolls
    back the reservation and remains eligible for the next run.
    """
    due_documents = await _due_documents(session, reminder_date)
    sent_count = 0

    for document in due_documents:
        delivery_id = str(uuid4())
        delivery_created = await _reserve_delivery(session, document, delivery_id)
        if not delivery_created:
            continue

        notification = await create_notification(
            session,
            document.account_id,
            title=f"{document.label} renewal reminder",
            message=(
                f"Your {document.label.lower()} for {document.registration_number} "
                "is due for renewal today."
            ),
            notification_type="vehicle_reminder",
            entity_type="vehicle",
            entity_id=document.vehicle_id,
            action_url="/profile",
            metadata={
                "vehicle_id": document.vehicle_id,
                "registration_number": document.registration_number,
                "document_type": document.document_type,
                "reminder_date": document.reminder_date.isoformat(),
            },
        )
        if notification is None:
            await session.execute(
                text(f"DELETE FROM {DELIVERY_TABLE} WHERE id = :delivery_id"),
                {"delivery_id": delivery_id},
            )
            continue

        await session.execute(
            text(
                f"UPDATE {DELIVERY_TABLE} SET notification_id = :notification_id "
                "WHERE id = :delivery_id"
            ),
            {"notification_id": notification["id"], "delivery_id": delivery_id},
        )
        sent_count += 1

    return sent_count


async def _due_documents(session: AsyncSession, reminder_date: date) -> list[DueVehicleDocument]:
    result = await session.execute(
        text(
            "SELECT v.id AS vehicle_id, ac.account_id, v.registration_number, "
            "'insurance' AS document_type, v.insurance_reminder_date AS reminder_date "
            "FROM vehicles v "
            "JOIN accounts ac ON ac.user_id = v.user_id AND ac.status = 'active' "
            "WHERE v.is_deleted = 0 "
            "AND NULLIF(TRIM(v.insurance_url), '') IS NOT NULL "
            "AND v.insurance_reminder_date = :reminder_date "
            "UNION ALL "
            "SELECT v.id AS vehicle_id, ac.account_id, v.registration_number, "
            "'puc' AS document_type, v.puc_reminder_date AS reminder_date "
            "FROM vehicles v "
            "JOIN accounts ac ON ac.user_id = v.user_id AND ac.status = 'active' "
            "WHERE v.is_deleted = 0 "
            "AND NULLIF(TRIM(v.puc_url), '') IS NOT NULL "
            "AND v.puc_reminder_date = :reminder_date"
        ),
        {"reminder_date": reminder_date},
    )
    return [
        DueVehicleDocument(
            vehicle_id=row["vehicle_id"],
            account_id=row["account_id"],
            registration_number=row["registration_number"],
            document_type=row["document_type"],
            reminder_date=row["reminder_date"],
        )
        for row in result.mappings().all()
    ]


async def _reserve_delivery(
    session: AsyncSession,
    document: DueVehicleDocument,
    delivery_id: str,
) -> bool:
    result = await session.execute(
        text(
            f"INSERT IGNORE INTO {DELIVERY_TABLE} "
            "(id, vehicle_id, account_id, document_type, reminder_date) "
            "VALUES (:id, :vehicle_id, :account_id, :document_type, :reminder_date)"
        ),
        {
            "id": delivery_id,
            "vehicle_id": document.vehicle_id,
            "account_id": document.account_id,
            "document_type": document.document_type,
            "reminder_date": document.reminder_date,
        },
    )
    return result.rowcount == 1
