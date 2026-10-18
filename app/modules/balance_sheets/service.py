"""Authorization, validation, spreadsheet parsing, and Balance Sheet workflows."""

import re
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from fastapi import HTTPException, status
from openpyxl.workbook.workbook import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.balance_sheets.messages import BalanceSheetMessage
from app.modules.balance_sheets.models import BalanceSheet, BalanceSheetItem
from app.modules.balance_sheets.repository import BalanceSheetRepository
from app.modules.balance_sheets.schemas import (
    BalanceSheetItemRequest,
    BalanceSheetItemResponse,
    BalanceSheetRequest,
    BalanceSheetResponse,
    BalanceSheetSection,
    BalanceSheetTotals,
)

SECTION_ALIASES = {
    "current_asset": BalanceSheetSection.CURRENT_ASSET,
    "current_assets": BalanceSheetSection.CURRENT_ASSET,
    "non_current_asset": BalanceSheetSection.NON_CURRENT_ASSET,
    "non_current_assets": BalanceSheetSection.NON_CURRENT_ASSET,
    "current_liability": BalanceSheetSection.CURRENT_LIABILITY,
    "current_liabilities": BalanceSheetSection.CURRENT_LIABILITY,
    "non_current_liability": BalanceSheetSection.NON_CURRENT_LIABILITY,
    "non_current_liabilities": BalanceSheetSection.NON_CURRENT_LIABILITY,
    "equity": BalanceSheetSection.EQUITY,
}


class BalanceSheetService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = BalanceSheetRepository(session)

    async def check_association(self, account, association_id: str) -> None:
        if not await self.repository.association_exists(association_id):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                BalanceSheetMessage.ASSOCIATION_NOT_FOUND,
            )

        scoped = await self.repository.scoped_associations(
            account.id,
            account.role.code,
            account.user_id,
        )
        if scoped is not None and association_id not in scoped:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                BalanceSheetMessage.UNAUTHORIZED_ASSOCIATION,
            )

    @staticmethod
    def totals(items: list[BalanceSheetItemRequest | BalanceSheetItem]) -> BalanceSheetTotals:
        section_totals = {
            section: Decimal("0.00")
            for section in BalanceSheetSection
        }
        for item in items:
            section = BalanceSheetSection(item.section)
            section_totals[section] += Decimal(item.amount)

        current_assets = section_totals[BalanceSheetSection.CURRENT_ASSET]
        non_current_assets = section_totals[BalanceSheetSection.NON_CURRENT_ASSET]
        current_liabilities = section_totals[BalanceSheetSection.CURRENT_LIABILITY]
        non_current_liabilities = section_totals[BalanceSheetSection.NON_CURRENT_LIABILITY]
        equity = section_totals[BalanceSheetSection.EQUITY]
        assets = current_assets + non_current_assets
        liabilities = current_liabilities + non_current_liabilities
        liabilities_and_equity = liabilities + equity

        return BalanceSheetTotals(
            current_assets=current_assets,
            non_current_assets=non_current_assets,
            total_assets=assets,
            current_liabilities=current_liabilities,
            non_current_liabilities=non_current_liabilities,
            total_liabilities=liabilities,
            total_equity=equity,
            liabilities_and_equity=liabilities_and_equity,
            working_capital=current_assets - current_liabilities,
            current_ratio=(current_assets / current_liabilities).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
            if current_liabilities
            else None,
            debt_to_equity_ratio=(liabilities / equity).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
            if equity
            else None,
        )

    def validate_balanced(
        self,
        items: list[BalanceSheetItemRequest | BalanceSheetItem],
    ) -> None:
        totals = self.totals(items)
        if totals.total_assets != totals.liabilities_and_equity:
            difference = totals.total_assets - totals.liabilities_and_equity
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"{BalanceSheetMessage.UNBALANCED}. Difference: {difference:.2f}",
            )

    async def validate_chart_accounts(
        self,
        association_id: str,
        items: list[BalanceSheetItemRequest],
    ) -> None:
        account_ids = {
            item.chart_of_account_id
            for item in items
            if item.chart_of_account_id
        }
        accounts = await self.repository.association_accounts_by_id(
            association_id,
            account_ids,
        )
        missing = account_ids - set(accounts)
        if missing:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "One or more Chart of Accounts entries do not belong to this association",
            )

    @staticmethod
    def build_items(
        balance_sheet_id: str,
        requests: list[BalanceSheetItemRequest],
    ) -> list[BalanceSheetItem]:
        return [
            BalanceSheetItem(
                id=str(uuid.uuid4()),
                balance_sheet_id=balance_sheet_id,
                chart_of_account_id=item.chart_of_account_id,
                section=item.section.value,
                account_name=item.account_name.strip(),
                amount=item.amount,
                sort_order=index,
            )
            for index, item in enumerate(requests)
        ]

    async def create(self, account, payload: BalanceSheetRequest) -> BalanceSheet:
        await self.check_association(account, payload.association_id)
        if await self.repository.duplicate_date(
            payload.association_id,
            payload.as_on_date,
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                BalanceSheetMessage.DUPLICATE_DATE,
            )

        self.validate_balanced(payload.items)
        await self.validate_chart_accounts(payload.association_id, payload.items)
        balance_sheet_id = str(uuid.uuid4())
        balance_sheet = BalanceSheet(
            id=balance_sheet_id,
            association_id=payload.association_id,
            as_on_date=payload.as_on_date,
            health_status=payload.health_status,
            health_note=payload.health_note,
            created_by=account.id,
            updated_by=account.id,
            items=self.build_items(balance_sheet_id, payload.items),
        )
        self.repository.add(balance_sheet)
        await self.repository.session.flush()
        return balance_sheet

    async def update(
        self,
        account,
        balance_sheet_id: str,
        payload: BalanceSheetRequest,
    ) -> BalanceSheet:
        balance_sheet = await self.repository.get_by_id(balance_sheet_id)
        if not balance_sheet:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                BalanceSheetMessage.NOT_FOUND,
            )
        await self.check_association(account, balance_sheet.association_id)
        if payload.association_id != balance_sheet.association_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "A Balance Sheet cannot be moved to another association",
            )
        if await self.repository.duplicate_date(
            payload.association_id,
            payload.as_on_date,
            excluding_id=balance_sheet.id,
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                BalanceSheetMessage.DUPLICATE_DATE,
            )

        self.validate_balanced(payload.items)
        await self.validate_chart_accounts(payload.association_id, payload.items)
        balance_sheet.as_on_date = payload.as_on_date
        balance_sheet.health_status = payload.health_status
        balance_sheet.health_note = payload.health_note
        balance_sheet.updated_by = account.id
        await self.repository.replace_items(
            balance_sheet,
            self.build_items(balance_sheet.id, payload.items),
        )
        await self.repository.session.flush()
        return balance_sheet

    async def get(
        self,
        account,
        association_id: str,
        as_on_date: date | None,
    ) -> BalanceSheet | None:
        await self.check_association(account, association_id)
        return await self.repository.get_by_date(association_id, as_on_date)

    async def dates(self, account, association_id: str) -> list[date]:
        await self.check_association(account, association_id)
        return await self.repository.list_dates(association_id)

    async def serialize(self, balance_sheet: BalanceSheet) -> BalanceSheetResponse:
        account_ids = {
            item.chart_of_account_id
            for item in balance_sheet.items
            if item.chart_of_account_id
        }
        account_codes = await self.repository.item_account_codes(account_ids)
        current_totals = self.totals(balance_sheet.items)
        previous = await self.repository.previous_snapshot(
            balance_sheet.association_id,
            balance_sheet.as_on_date,
        )
        previous_totals = self.totals(previous.items) if previous else None

        def growth(current: Decimal, prior: Decimal | None) -> Decimal | None:
            if prior in (None, Decimal("0.00")):
                return None
            return ((current - prior) / abs(prior) * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        return BalanceSheetResponse(
            id=balance_sheet.id,
            association_id=balance_sheet.association_id,
            association_name=balance_sheet.association.name,
            as_on_date=balance_sheet.as_on_date,
            items=[
                BalanceSheetItemResponse(
                    id=item.id,
                    chart_of_account_id=item.chart_of_account_id,
                    account_code=account_codes.get(item.chart_of_account_id),
                    section=BalanceSheetSection(item.section),
                    account_name=item.account_name,
                    amount=item.amount,
                    sort_order=item.sort_order,
                )
                for item in balance_sheet.items
            ],
            totals=current_totals,
            assets_growth_pct=growth(
                current_totals.total_assets,
                previous_totals.total_assets if previous_totals else None,
            ),
            liabilities_growth_pct=growth(
                current_totals.total_liabilities,
                previous_totals.total_liabilities if previous_totals else None,
            ),
            equity_growth_pct=growth(
                current_totals.total_equity,
                previous_totals.total_equity if previous_totals else None,
            ),
            health_status=balance_sheet.health_status,
            health_note=balance_sheet.health_note,
            created_at=balance_sheet.created_at,
            updated_at=balance_sheet.updated_at,
        )

    async def parse_workbook(
        self,
        association_id: str,
        workbook: Workbook,
    ) -> tuple[list[BalanceSheetItemRequest], str | None, str | None]:
        sheet = workbook.active
        headers = {
            self.normalize_header(cell.value): index
            for index, cell in enumerate(sheet[1])
            if cell.value
        }
        required = {"section", "account_name", "amount"}
        missing = sorted(required - set(headers))
        if missing:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Missing required columns: {', '.join(missing)}",
            )

        parsed_rows: list[tuple[BalanceSheetSection, str, Decimal, str | None]] = []
        health_statuses: set[str] = set()
        health_notes: set[str] = set()
        errors: list[str] = []
        for row_number, row in enumerate(
            sheet.iter_rows(min_row=2, values_only=True),
            start=2,
        ):
            if not any(value not in (None, "") for value in row):
                continue

            section_value = self.cell_value(row, headers["section"])
            account_name = self.cell_value(row, headers["account_name"])
            amount_value = self.cell_value(row, headers["amount"])
            account_code = (
                self.cell_value(row, headers["account_code"])
                if "account_code" in headers
                else None
            )
            if "health_status" in headers:
                value = self.cell_value(row, headers["health_status"])
                if str(value or "").strip():
                    health_statuses.add(str(value).strip())
            if "financial_health_note" in headers:
                value = self.cell_value(row, headers["financial_health_note"])
                if str(value or "").strip():
                    health_notes.add(str(value).strip())
            section_key = self.normalize_header(section_value)
            section = SECTION_ALIASES.get(section_key)

            if not section:
                errors.append(f"Row {row_number}: invalid Section")
                continue
            if not str(account_name or "").strip():
                errors.append(f"Row {row_number}: Account Name is required")
                continue
            try:
                amount = Decimal(str(amount_value)).quantize(Decimal("0.01"))
                if not amount.is_finite():
                    raise InvalidOperation
            except (InvalidOperation, TypeError, ValueError):
                errors.append(f"Row {row_number}: Amount must be a valid number")
                continue

            parsed_rows.append(
                (
                    section,
                    str(account_name).strip(),
                    amount,
                    self.normalize_account_code(account_code),
                )
            )

        if errors:
            detail = "; ".join(errors[:10])
            if len(errors) > 10:
                detail += f"; and {len(errors) - 10} more errors"
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail)
        if not parsed_rows:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                BalanceSheetMessage.EMPTY_IMPORT,
            )
        if len(health_statuses) > 1 or len(health_notes) > 1:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Health Status and Financial Health Note must be the same on every populated row",
            )

        account_codes = {row[3] for row in parsed_rows if row[3]}
        accounts = await self.repository.association_accounts_by_code(
            association_id,
            account_codes,
        )
        unknown_codes = sorted(account_codes - set(accounts))
        if unknown_codes:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Unknown account codes for this association: "
                + ", ".join(unknown_codes[:10]),
            )

        return [
            BalanceSheetItemRequest(
                section=section,
                account_name=account_name,
                amount=amount,
                chart_of_account_id=accounts[account_code].id
                if account_code
                else None,
            )
            for section, account_name, amount, account_code in parsed_rows
        ], next(iter(health_statuses), None), next(iter(health_notes), None)

    @staticmethod
    def normalize_header(value: object) -> str:
        normalized = re.sub(
            r"[^a-z0-9]+",
            "_",
            str(value or "").strip().lower(),
        ).strip("_")
        return normalized.removesuffix("_optional")

    @staticmethod
    def normalize_account_code(value: object) -> str | None:
        if value in (None, ""):
            return None
        return str(value).strip().removesuffix(".0")

    @staticmethod
    def cell_value(row: tuple, index: int):
        return row[index] if index < len(row) else None

    async def import_workbook(
        self,
        account,
        association_id: str,
        as_on_date: date,
        workbook: Workbook,
    ) -> BalanceSheet:
        await self.check_association(account, association_id)
        items, health_status, health_note = await self.parse_workbook(
            association_id, workbook
        )
        return await self.create(
            account,
            BalanceSheetRequest(
                association_id=association_id,
                as_on_date=as_on_date,
                items=items,
                health_status=health_status,
                health_note=health_note,
            ),
        )
