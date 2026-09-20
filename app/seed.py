"""Idempotent seed functions for Nestora's static IAM catalogue and bootstrap account."""

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import RoleCode
from app.core.security import hash_password, utc_now

# Encryption is paused for bank seed values for now; retain the helper import
# location in the commented call sites below for a later opt-in.
# from app.core.field_encryption import encrypt_field
from app.modules.associations.models import Association
from app.modules.amenities.models import Amenity, AmenityBooking
from app.modules.announcements.models import Announcement, AnnouncementComment, AnnouncementLike
from app.modules.events.models import Event, EventComment, EventLike, EventRSVP
from app.modules.polls.models import Poll, PollComment, PollLike, PollOption, PollVote
from app.modules.auth.models import Account
from app.modules.bank.models import BankAccount
from app.modules.board_tasks.models import BoardTask
from app.modules.board_members.models import BoardMember
from app.modules.committees.models import BoardCommitteeChatMessage, Committee, CommitteeMember
from app.modules.financials.models import FinancialReport
from app.modules.documents.models import Document, UnitDocument
from app.modules.chart_of_accounts.models import GlobalChartOfAccount, AssociationChartOfAccount
from app.modules.entities.models import Entity
from app.modules.employees.models import Employee
from app.modules.marketplace.models import MarketplaceCategory
from app.modules.visitor_management.models import Delivery, PreApprovedVisitor, Visitor, VisitorLog, VisitorVisit
from app.modules.wallet.models import Wallet, WalletTransaction
from app.modules.iam.models import Feature, Role, RoleFeaturePermission
from app.modules.meetings.models import Meeting
from app.modules.iam.seed_data import load_iam_seed_snapshot
from app.modules.service_requests.models import ServiceRequest
from app.modules.subscriptions.models import SubscriptionPlan
from app.modules.users.models import UserCode, UserDetail
from app.modules.vendors.models import Vendor

# These are development bootstrap defaults. Production deployments should
# override them with unique INITIAL_ADMIN_* values before the first seed run.
DEFAULT_SUPER_ADMIN_EMAIL = "superadmin@nestora.io"
DEFAULT_SUPER_ADMIN_PASSWORD = "Admin@nestora2026"
DEFAULT_SUPER_ADMIN_ID = "1b6c5d02-2851-4bef-834d-664b8518ca7e"
WELCOME_NOTIFICATION_ID = "5d8fd65f-25e1-4d57-932b-696b5db13e7d"


async def _seed_roles(session: AsyncSession, rows: list[dict]) -> None:
    """Insert copied roles using their original IDs and reject incompatible existing records."""
    for row in rows:
        entity_id = row.get("entity_id")
        if entity_id and await session.get(Entity, entity_id) is None:
            if bool(row.get("is_deleted", False)):
                # Historical deleted roles can reference entities that were
                # removed before the IAM snapshot was captured.
                continue
            raise RuntimeError(
                f"Role '{row['code']}' references missing entity ID {entity_id}; "
                "seed that entity before seeding roles."
            )

        role = await session.get(Role, row["id"])
        if role is not None:
            if role.code != row["code"]:
                raise RuntimeError(f"Role ID {row['id']} already belongs to '{role.code}', not '{row['code']}'")
            role.entity_id = row.get("entity_id")
            role.name = row["name"]
            role.description = row.get("description")
            role.is_system = bool(row.get("is_system", True))
            role.is_active = bool(row["is_active"])
            role.is_deleted = bool(row.get("is_deleted", False))
            continue

        code_owner = await session.scalar(select(Role).where(Role.code == row["code"]))
        if code_owner is not None:
            raise RuntimeError(
                f"Role code '{row['code']}' already uses ID {code_owner.id}; use a fresh database for this seed"
            )
        session.add(
            Role(
                id=row["id"],
                entity_id=row.get("entity_id"),
                code=row["code"],
                name=row["name"],
                description=row["description"],
                is_system=bool(row.get("is_system", True)),
                is_active=bool(row["is_active"]),
                is_deleted=bool(row.get("is_deleted", False)),
                created_at=row["created_at"],
            )
        )
    await session.flush()


async def _seed_features(session: AsyncSession, rows: list[dict]) -> None:
    """Insert copied features first, then restore their self-referencing parent links."""
    saved_features: dict[str, Feature] = {}
    for row in rows:
        feature = await session.get(Feature, row["id"])
        if feature is not None:
            if feature.code != row["code"]:
                raise RuntimeError(
                    f"Feature ID {row['id']} already belongs to '{feature.code}', not '{row['code']}'"
                )
            saved_features[row["id"]] = feature
            feature.name = row["name"]
            feature.description = row.get("description")
            feature.icon = row.get("icon")
            feature.route = row.get("url")
            feature.order_index = row["order_index"]
            feature.is_system = bool(row.get("is_system", True))
            feature.is_active = bool(row["is_active"])
            feature.is_deleted = bool(row.get("is_deleted", False))
            continue

        if row["code"] is not None:
            code_owner = await session.scalar(select(Feature).where(Feature.code == row["code"]))
            if code_owner is not None:
                raise RuntimeError(
                    f"Feature code '{row['code']}' already uses ID {code_owner.id}; use a fresh database for this seed"
                )
        feature = Feature(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            description=row["description"],
            parent_id=None,
            icon=row["icon"],
            route=row["url"],
            order_index=row["order_index"],
            is_system=bool(row.get("is_system", True)),
            is_active=bool(row["is_active"]),
            is_deleted=bool(row.get("is_deleted", False)),
            created_at=row["created_at"],
        )
        session.add(feature)
        saved_features[row["id"]] = feature
    await session.flush()

    for row in rows:
        saved_features[row["id"]].parent_id = row["parent_id"]
    await session.flush()


async def _seed_permissions(session: AsyncSession, rows: list[dict]) -> None:
    """Insert each copied CRUD and sidebar assignment using its original ID."""
    for row in rows:
        permission = await session.get(RoleFeaturePermission, row["id"])
        if permission is not None:
            if permission.role_id != row["role_id"] or permission.feature_id != row["feature_id"]:
                raise RuntimeError(f"Permission ID {row['id']} has incompatible role or feature references")
            permission.can_create = bool(row["can_create"])
            permission.can_view = bool(row["can_view"])
            permission.can_update = bool(row["can_update"])
            permission.can_delete = bool(row["can_delete"])
            permission.sidebar_order = row["sidebar_order"]
            permission.is_deleted = bool(row.get("is_deleted", False))
            continue

        assignment = await session.scalar(
            select(RoleFeaturePermission).where(
                RoleFeaturePermission.role_id == row["role_id"],
                RoleFeaturePermission.feature_id == row["feature_id"],
            )
        )
        if assignment is not None:
            raise RuntimeError(
                "A role-feature assignment already exists with a different ID; use a fresh database for this seed"
            )
        session.add(
            RoleFeaturePermission(
                id=row["id"],
                role_id=row["role_id"],
                feature_id=row["feature_id"],
                can_create=bool(row["can_create"]),
                can_view=bool(row["can_view"]),
                can_update=bool(row["can_update"]),
                can_delete=bool(row["can_delete"]),
                is_deleted=bool(row.get("is_deleted", False)),
                sidebar_order=row["sidebar_order"],
                created_at=row["created_at"],
            )
        )
    await session.flush()


async def _seed_subscription_plans(session: AsyncSession, rows: list[dict]) -> None:
    """Seed optional subscription plans without requiring them in the IAM snapshot."""
    for row in rows:
        plan = await session.get(SubscriptionPlan, row["id"])
        if plan is not None:
            plan.is_deleted = False
            continue
        session.add(
            SubscriptionPlan(
                id=row["id"],
                name=row["name"],
                code=row.get("code"),
                country=row.get("country", "IN"),
                description=row.get("description"),
                monthly_price=row.get("monthly_price"),
                yearly_price=row.get("yearly_price"),
                trial_days=row.get("trial_days", 0),
                is_active=bool(row.get("is_active", True)),
                is_deleted=False,
            )
        )
    await session.flush()


async def _seed_associations(session: AsyncSession, rows: list[dict]) -> None:
    """Restore optional association snapshot rows without requiring legacy data in the fixture."""
    for row in rows:
        association = await session.get(Association, row["id"])
        if association is not None:
            association.is_deleted = False
            continue
        session.add(
            Association(
                id=row["id"],
                name=row["name"],
                association_code=row.get("association_code"),
                entity_id=row.get("entity_id"),
                country=row.get("country"),
                is_active=bool(row.get("is_active", True)),
                is_deleted=False,
            )
        )
    await session.flush()


async def _seed_bank_accounts(session: AsyncSession, rows: list[dict]) -> None:
    """Restore optional bank fixtures while keeping rows soft-deletable."""
    for row in rows:
        account = await session.get(BankAccount, row["id"])
        if account is not None:
            account.is_deleted = False
            continue
        session.add(
            BankAccount(
                id=row.get("id", str(uuid.uuid4())),
                association_id=row["association_id"],
                account_name=row["account_name"],
                account_holder_name=row["account_holder_name"],
                bank_name=row["bank_name"],
                account_number=row["account_number"],
                # account_number=encrypt_field(row["account_number"]) or "",
                ifsc_code=row["ifsc_code"],
                branch_name=row.get("branch_name"),
                account_type=row.get("account_type", "Current"),
                currency=row.get("currency", "INR"),
                upi_id=row.get("upi_id"),
                qr_code_url=row.get("qr_code_url"),
                gateway_provider=row.get("gateway_provider"),
                merchant_id=row.get("merchant_id"),
                api_key=row.get("api_key"),
                api_secret=row.get("api_secret"),
                webhook_secret=row.get("webhook_secret"),
                # api_key=encrypt_field(row.get("api_key")),
                # api_secret=encrypt_field(row.get("api_secret")),
                # webhook_secret=encrypt_field(row.get("webhook_secret")),
                is_default=bool(row.get("is_default", False)),
                status=row.get("status", "Active"),
                created_by=row.get("created_by"),
                is_deleted=False,
            )
        )
    await session.flush()


async def _seed_financial_reports(session: AsyncSession, rows: list[dict]) -> None:
    """Restore optional report fixtures while keeping soft-deleted rows excluded."""
    for row in rows:
        report = await session.get(FinancialReport, row["id"])
        if report is not None:
            report.is_deleted = False
            continue
        session.add(
            FinancialReport(
                id=row["id"],
                association_id=row["association_id"],
                published_month=row["published_month"],
                report_type=row["report_type"],
                title=row["title"],
                file_url=row["file_url"],
                uploaded_by=row.get("uploaded_by"),
                is_deleted=False,
            )
        )
    await session.flush()


async def _seed_users(session: AsyncSession, rows: list[dict]) -> None:
    """Restore optional user fixtures and reactivate their soft-deleted profiles."""
    for row in rows:
        user = await session.get(UserDetail, row["user_id"])
        if user is not None:
            user.is_deleted = False
            continue
        code_id = row.get("code_id")
        if row.get("activation_code") and not code_id:
            code = UserCode(
                id=str(uuid.uuid4()),
                login_code=row["activation_code"],
                status="active",
            )
            session.add(code)
            await session.flush()
            code_id = code.id
        session.add(
            UserDetail(
                user_id=row["user_id"],
                code_id=code_id,
                name=row["name"],
                address=row.get("address", ""),
                email=row["email"],
                contact_number=row["contact_number"],
                first_name=row.get("first_name"),
                last_name=row.get("last_name"),
                role_id=row.get("role_id"),
                association_id=row.get("association_id"),
                unit_id=row.get("unit_id"),
                is_deleted=False,
            )
        )
    await session.flush()


async def _seed_vendors(session: AsyncSession, rows: list[dict]) -> None:
    """Restore optional vendor fixtures and reactivate soft-deleted records."""
    for row in rows:
        vendor = await session.get(Vendor, row["id"])
        if vendor is not None:
            vendor.is_deleted = False
            continue
        values = {key: value for key, value in row.items() if key in Vendor.__table__.columns}
        values.setdefault("service_type", "General")
        values["is_deleted"] = False
        session.add(Vendor(**values))
    await session.flush()


async def _seed_service_requests(session: AsyncSession, rows: list[dict]) -> None:
    """Restore optional service-request fixtures and reactivate soft-deleted tickets."""
    for row in rows:
        request = await session.get(ServiceRequest, row["id"])
        if request is not None:
            request.is_deleted = False
            continue
        values = {key: value for key, value in row.items() if key in ServiceRequest.__table__.columns}
        values["is_deleted"] = False
        session.add(ServiceRequest(**values))
    await session.flush()


async def _seed_board_tasks(session: AsyncSession, rows: list[dict]) -> None:
    """Restore optional board-task fixtures and reactivate soft-deleted tasks."""
    for row in rows:
        task = await session.get(BoardTask, row["id"])
        if task is not None:
            task.is_deleted = False
            continue
        values = {key: value for key, value in row.items() if key in BoardTask.__table__.columns}
        values["is_deleted"] = False
        session.add(BoardTask(**values))
    await session.flush()


async def _seed_meetings(session: AsyncSession, rows: list[dict]) -> None:
    """Restore optional meeting fixtures and reactivate soft-deleted meetings."""
    for row in rows:
        meeting = await session.get(Meeting, row["id"])
        if meeting is not None:
            meeting.is_deleted = False
            continue
        values = {key: value for key, value in row.items() if key in Meeting.__table__.columns}
        values["is_deleted"] = False
        session.add(Meeting(**values))
    await session.flush()


async def _seed_committees(session: AsyncSession, rows: list[dict]) -> None:
    """Restore optional committee fixtures and their active memberships."""
    for row in rows:
        committee = await session.get(Committee, row["id"])
        if committee is None:
            values = {key: value for key, value in row.items() if key in Committee.__table__.columns}
            values["is_deleted"] = False
            session.add(Committee(**values))
        else:
            committee.is_deleted = False
            for key in ("association_id", "name", "description", "start_date", "end_date"):
                if key in row:
                    setattr(committee, key, row[key])
        for member_row in row.get("members", []):
            member_id = member_row.get("id") or str(uuid.uuid4())
            member = await session.get(CommitteeMember, member_id)
            if member is None:
                values = {
                    "id": member_id,
                    "committee_id": row["id"],
                    "user_id": member_row["user_id"],
                    "role": member_row.get("role"),
                    "start_date": member_row.get("start_date"),
                    "end_date": member_row.get("end_date"),
                    "is_deleted": False,
                }
                session.add(CommitteeMember(**values))
            else:
                member.is_deleted = False
    await session.flush()


async def _seed_amenities(session: AsyncSession, rows: list[dict]) -> None:
    """Restore optional amenity fixtures and their reservations."""
    for row in rows:
        amenity = await session.get(Amenity, row["id"])
        if amenity is None:
            values = {key: value for key, value in row.items() if key in Amenity.__table__.columns}
            values["is_deleted"] = False
            session.add(Amenity(**values))
        else:
            amenity.is_deleted = False
            for key in ("association_id", "name", "charges", "status"):
                if key in row:
                    setattr(amenity, key, row[key])
        for booking_row in row.get("bookings", []):
            booking_id = booking_row.get("id") or str(uuid.uuid4())
            booking = await session.get(AmenityBooking, booking_id)
            if booking is None:
                values = {key: value for key, value in booking_row.items() if key in AmenityBooking.__table__.columns}
                values.update({"id": booking_id, "amenity_id": row["id"], "is_deleted": False})
                session.add(AmenityBooking(**values))
            else:
                booking.is_deleted = False
    await session.flush()


async def _seed_announcements(session: AsyncSession, rows: list[dict]) -> None:
    """Restore optional announcement fixtures and active engagement rows."""
    for row in rows:
        announcement = await session.get(Announcement, row["id"])
        if announcement is None:
            values = {key: value for key, value in row.items() if key in Announcement.__table__.columns}
            values["is_deleted"] = False
            session.add(Announcement(**values))
        else:
            announcement.is_deleted = False
            for key in (
                "association_id", "title", "body", "category", "pinned", "audience", "attachment_url"
            ):
                if key in row:
                    setattr(announcement, key, row[key])
        for like_row in row.get("likes", []):
            like_id = like_row.get("id") or str(uuid.uuid4())
            like = await session.get(AnnouncementLike, like_id)
            if like is None:
                values = {key: value for key, value in like_row.items() if key in AnnouncementLike.__table__.columns}
                values.update({"id": like_id, "announcement_id": row["id"], "is_deleted": False})
                session.add(AnnouncementLike(**values))
            else:
                like.is_deleted = False
        for comment_row in row.get("comments", []):
            comment_id = comment_row.get("id") or str(uuid.uuid4())
            comment = await session.get(AnnouncementComment, comment_id)
            if comment is None:
                values = {key: value for key, value in comment_row.items() if key in AnnouncementComment.__table__.columns}
                values.update({"id": comment_id, "announcement_id": row["id"], "is_deleted": False})
                session.add(AnnouncementComment(**values))
            else:
                comment.is_deleted = False
    await session.flush()


async def _seed_events(session: AsyncSession, rows: list[dict]) -> None:
    """Restore optional event fixtures and active RSVPs/engagement rows."""
    for row in rows:
        event = await session.get(Event, row["id"])
        if event is None:
            values = {key: value for key, value in row.items() if key in Event.__table__.columns}
            values["is_deleted"] = False
            session.add(Event(**values))
        else:
            event.is_deleted = False
            for key in Event.__table__.columns.keys():
                if key in row and key not in {"id", "created_at", "updated_at", "is_deleted"}:
                    setattr(event, key, row[key])
        for child_rows, model, fk in ((row.get("rsvps", []), EventRSVP, "event_id"), (row.get("likes", []), EventLike, "event_id"), (row.get("comments", []), EventComment, "event_id")):
            for child in child_rows:
                child_id = child.get("id") or str(uuid.uuid4())
                identity = child_id if model is not EventLike else {"event_id": row["id"], "account_id": child["account_id"]}
                existing = await session.get(model, identity)
                if existing is None:
                    values = {key: value for key, value in child.items() if key in model.__table__.columns}
                    if model is not EventLike:
                        values["id"] = child_id
                    values[fk] = row["id"]
                    values["is_deleted"] = False
                    session.add(model(**values))
                else:
                    existing.is_deleted = False
    await session.flush()


async def _seed_polls(session: AsyncSession, rows: list[dict]) -> None:
    """Restore optional poll fixtures and active options, votes, likes, and comments."""
    for row in rows:
        poll = await session.get(Poll, row["id"])
        if poll is None:
            values = {key: value for key, value in row.items() if key in Poll.__table__.columns}
            values["is_deleted"] = False
            session.add(Poll(**values))
        else:
            poll.is_deleted = False
            for key in Poll.__table__.columns.keys():
                if key in row and key not in {"id", "created_at", "updated_at", "is_deleted"}:
                    setattr(poll, key, row[key])
        for child_rows, model in ((row.get("options", []), PollOption), (row.get("votes", []), PollVote), (row.get("likes", []), PollLike), (row.get("comments", []), PollComment)):
            for child in child_rows:
                if model is PollLike:
                    identity = {"poll_id": row["id"], "account_id": child["account_id"]}
                    child_id = None
                elif model is PollVote:
                    identity = {"poll_id": row["id"], "option_id": child["option_id"], "account_id": child["account_id"]}
                    child_id = None
                else:
                    child_id = child.get("id") or str(uuid.uuid4())
                    identity = child_id
                existing = await session.get(model, identity)
                if existing is None:
                    values = {key: value for key, value in child.items() if key in model.__table__.columns}
                    if model is PollOption and "option_text" not in values and "text" in child:
                        values["option_text"] = child["text"]
                    if model is PollComment and "content" not in values and "comment" in child:
                        values["content"] = child["comment"]
                    if child_id:
                        values["id"] = child_id
                    values["poll_id"] = row["id"]
                    values["is_deleted"] = False
                    session.add(model(**values))
                else:
                    existing.is_deleted = False
    await session.flush()


async def _seed_board_members(session: AsyncSession, rows: list[dict]) -> None:
    """Restore optional board-member terms while keeping soft-deleted rows excluded."""
    for row in rows:
        membership = await session.get(BoardMember, row["id"])
        if membership is None:
            values = {key: value for key, value in row.items() if key in BoardMember.__table__.columns}
            values["is_deleted"] = False
            session.add(BoardMember(**values))
        else:
            membership.is_deleted = False
            for key in ("association_id", "account_id", "term_start_date", "term_end_date", "status", "created_by"):
                if key in row:
                    setattr(membership, key, row[key])
    await session.flush()


async def _seed_documents(session: AsyncSession, rows: list[dict]) -> None:
    """Restore document fixtures and clear their approved soft-delete flag."""
    for row in rows:
        document = await session.get(Document, row["id"])
        if document is not None:
            document.is_deleted = False
            continue
        values = {key: value for key, value in row.items() if key in {column.name for column in Document.__table__.columns}}
        values["is_deleted"] = False
        session.add(Document(**values))
    await session.flush()


async def _seed_unit_documents(session: AsyncSession, rows: list[dict]) -> None:
    """Restore unit-document fixtures and clear their approved soft-delete flag."""
    for row in rows:
        document = await session.get(UnitDocument, row["id"])
        if document is not None:
            document.is_deleted = False
            continue
        values = {key: value for key, value in row.items() if key in {column.name for column in UnitDocument.__table__.columns}}
        values["is_deleted"] = False
        session.add(UnitDocument(**values))
    await session.flush()


async def _seed_chart_of_accounts(session: AsyncSession, rows: list[dict]) -> None:
    """Restore global and association COA fixtures with soft-delete reset."""
    for row in rows:
        table = AssociationChartOfAccount if row.get("association_id") else GlobalChartOfAccount
        account = await session.get(table, row["id"])
        if account is not None:
            account.is_deleted = False
            continue
        values = {key: value for key, value in row.items() if key in {column.name for column in table.__table__.columns}}
        values["is_deleted"] = False
        session.add(table(**values))
    await session.flush()


async def _seed_marketplace_categories(session: AsyncSession, rows: list[dict]) -> None:
    """Seed the marketplace category catalogue and restore soft-deleted rows."""
    default_names = (
        "Furniture", "Electronics", "Vehicles", "Books", "Home Appliances", "Sports",
        "Baby Products", "Pet Supplies", "Fashion", "Home Decor", "Garden", "Others",
    )
    source = rows or [{"name": name} for name in default_names]
    for row in source:
        category = None
        if row.get("id"):
            category = await session.get(MarketplaceCategory, row["id"])
        if category is None:
            category = await session.scalar(select(MarketplaceCategory).where(MarketplaceCategory.name == row["name"]))
        if category is not None:
            category.is_deleted = False
            continue
        session.add(MarketplaceCategory(id=row.get("id", str(uuid.uuid4())), name=row["name"], is_deleted=False))
    await session.flush()


async def _seed_visitor_management(session: AsyncSession, snapshot: dict) -> None:
    """Restore optional visitor fixtures and always clear their approved soft-delete flags."""
    for model, key in (
        (Visitor, "visitors"),
        (VisitorVisit, "visitor_visits"),
        (PreApprovedVisitor, "pre_approved_visitors"),
        (VisitorLog, "visitor_logs"),
        (Delivery, "deliveries"),
    ):
        for row in snapshot.get(key, []):
            record = await session.get(model, row["id"])
            if record is not None:
                record.is_deleted = False
                continue
            columns = {column.name for column in model.__table__.columns}
            values = {name: value for name, value in row.items() if name in columns}
            values["is_deleted"] = False
            session.add(model(**values))
        await session.flush()


async def _seed_committee_chat(session: AsyncSession, rows: list[dict]) -> None:
    """Restore optional committee-chat fixtures while excluding soft-deleted rows."""
    for row in rows:
        message = await session.get(BoardCommitteeChatMessage, row["id"])
        if message is not None:
            message.is_deleted = False
            continue
        values = {key: value for key, value in row.items() if key in BoardCommitteeChatMessage.__table__.columns}
        values["is_deleted"] = False
        session.add(BoardCommitteeChatMessage(**values))
    await session.flush()


async def _seed_wallets(session: AsyncSession, snapshot: dict) -> None:
    """Restore optional wallet snapshots while explicitly clearing approved soft-delete flags."""
    for row in snapshot.get("wallets", []):
        wallet = await session.get(Wallet, row["id"])
        values = {key: row[key] for key in ("account_id", "balance", "reward_points", "security_pin", "status") if key in row}
        if wallet is None:
            session.add(Wallet(id=row["id"], is_deleted=False, **values))
        else:
            for key, value in values.items():
                setattr(wallet, key, value)
            wallet.is_deleted = False
    await session.flush()
    for row in snapshot.get("wallet_transactions", []):
        transaction = await session.get(WalletTransaction, row["id"])
        values = {key: row[key] for key in ("wallet_id", "type", "amount", "status", "reference_number", "description") if key in row}
        if transaction is None:
            session.add(WalletTransaction(id=row["id"], is_deleted=False, **values))
        else:
            for key, value in values.items():
                setattr(transaction, key, value)
            transaction.is_deleted = False
    await session.flush()


async def _seed_bootstrap_super_admin(session: AsyncSession, settings: Settings) -> Account:
    """Create the requested initial platform administrator unless it already exists."""
    super_admin = await session.scalar(
        select(Role).where(Role.code == RoleCode.SUPER_ADMIN, Role.is_deleted.is_(False))
    )
    if super_admin is None:
        raise RuntimeError(f"The {RoleCode.SUPER_ADMIN} role was not seeded")

    email = (settings.initial_admin_email or DEFAULT_SUPER_ADMIN_EMAIL).lower()
    password = settings.initial_admin_password or DEFAULT_SUPER_ADMIN_PASSWORD
    existing = await session.scalar(select(Account).where(Account.email == email))
    if existing:
        return existing
    account_values = {
        "email": email,
        "password_hash": hash_password(password),
        "role_id": super_admin.id,
        "password_changed_at": utc_now(),
    }
    if email == DEFAULT_SUPER_ADMIN_EMAIL:
        account_values["id"] = DEFAULT_SUPER_ADMIN_ID
    account = Account(**account_values)
    session.add(account)
    await session.flush()
    return account


async def _seed_welcome_notification(session: AsyncSession, account_id: str) -> None:
    """Seed one reusable welcome payload and the bootstrap account's inbox state."""
    await session.execute(
        text(
            "INSERT IGNORE INTO notifications (id, type, title, message, action_url, metadata) "
            "VALUES (:id, :type, :title, :message, :action_url, :metadata)"
        ),
        {
            "id": WELCOME_NOTIFICATION_ID,
            "type": "system",
            "title": "Welcome to Nestora",
            "message": "Your notification inbox is ready.",
            "action_url": "/dashboard",
            "metadata": '{\"seed\": true}',
        },
    )
    await session.execute(
        text(
            "INSERT IGNORE INTO notification_recipients "
            "(notification_id, account_id, delivered_at) "
            "VALUES (:notification_id, :account_id, CURRENT_TIMESTAMP)"
        ),
        {"notification_id": WELCOME_NOTIFICATION_ID, "account_id": account_id},
    )


async def seed_auth_data(session: AsyncSession, settings: Settings) -> None:
    """Seed the saved IAM snapshot and a superadmin account in the caller's transaction."""
    snapshot = load_iam_seed_snapshot()
    await _seed_roles(session, snapshot["roles"])
    await _seed_features(session, snapshot["features"])
    await _seed_permissions(session, snapshot["permissions"])
    await _seed_subscription_plans(session, snapshot.get("subscription_plans", []))
    await _seed_associations(session, snapshot.get("associations", []))
    await _seed_bank_accounts(session, snapshot.get("bank_accounts", []))
    await _seed_financial_reports(session, snapshot.get("financial_reports", []))
    await _seed_users(session, snapshot.get("users", []))
    await _seed_vendors(session, snapshot.get("vendors", []))
    await _seed_service_requests(session, snapshot.get("service_requests", []))
    await _seed_board_tasks(session, snapshot.get("board_tasks", []))
    await _seed_meetings(session, snapshot.get("meetings", []))
    await _seed_committees(session, snapshot.get("committees", []))
    await _seed_committee_chat(session, snapshot.get("committee_chat", []))
    await _seed_amenities(session, snapshot.get("amenities", []))
    await _seed_announcements(session, snapshot.get("announcements", []))
    await _seed_events(session, snapshot.get("events", []))
    await _seed_polls(session, snapshot.get("polls", []))
    await _seed_board_members(session, snapshot.get("board_members", []))
    await _seed_documents(session, snapshot.get("documents", []) + snapshot.get("board_documents", []))
    await _seed_unit_documents(session, snapshot.get("unit_documents", []))
    await _seed_chart_of_accounts(
        session,
        snapshot.get("chart_of_accounts", [])
        + snapshot.get("global_chart_of_accounts", [])
        + snapshot.get("association_chart_of_accounts", []),
    )
    await _seed_marketplace_categories(session, snapshot.get("marketplace_categories", []))
    await _seed_visitor_management(session, snapshot)
    await _seed_wallets(session, snapshot)
    bootstrap_admin = await _seed_bootstrap_super_admin(session, settings)
    await _seed_welcome_notification(session, bootstrap_admin.id)
