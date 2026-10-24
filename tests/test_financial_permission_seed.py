"""Focused checks for the Super Admin financial report permission seed."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.iam.models import RoleFeaturePermission
from app.seed import (
    SUPER_ADMIN_FINANCIAL_REPORTS,
    grant_super_admin_financial_report_permissions,
)


@pytest.mark.asyncio
async def test_grant_is_idempotent_and_only_uses_existing_features() -> None:
    session = MagicMock()
    session.flush = AsyncMock()
    role = SimpleNamespace(id="super-admin-role")
    features = [
        SimpleNamespace(id=f"feature-{index}")
        for index in range(len(SUPER_ADMIN_FINANCIAL_REPORTS))
    ]
    existing_one = SimpleNamespace()
    existing_two = SimpleNamespace()
    session.scalar = AsyncMock(
        side_effect=[
            role,
            features[0],
            None,
            features[1],
            existing_one,
            features[2],
            None,
            features[3],
            existing_two,
            features[4],
            None,
        ]
    )

    counts = await grant_super_admin_financial_report_permissions(session)

    assert counts == {
        "features_found": 5,
        "permissions_created": 3,
        "permissions_updated": 2,
    }
    added = [call.args[0] for call in session.add.call_args_list]
    assert len(added) == 3
    assert all(isinstance(permission, RoleFeaturePermission) for permission in added)
    assert {permission.feature_id for permission in added} == {
        features[0].id,
        features[2].id,
        features[4].id,
    }
    for permission in [*added, existing_one, existing_two]:
        assert permission.can_view is True
        assert permission.can_create is True
        assert permission.can_update is True
        assert permission.can_delete is False
        assert permission.is_deleted is False
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_grant_fails_instead_of_creating_a_missing_feature() -> None:
    session = MagicMock()
    session.flush = AsyncMock()
    session.scalar = AsyncMock(
        side_effect=[SimpleNamespace(id="super-admin-role"), None]
    )

    with pytest.raises(RuntimeError, match="missing from the catalogue"):
        await grant_super_admin_financial_report_permissions(session)

    session.add.assert_not_called()
    session.flush.assert_not_awaited()
