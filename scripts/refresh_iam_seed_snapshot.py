"""Refresh the checked-in IAM seed snapshot from the configured database.

This command only reads roles, features, and role-feature permissions from the
configured database. It rewrites the local source snapshot; it never writes to
the database.
"""

from __future__ import annotations

import asyncio
import base64
import gzip
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.db.session import close_database, session_factory
from app.modules.iam.models import Feature, Role, RoleFeaturePermission

SNAPSHOT_PATH = Path(__file__).resolve().parents[1] / "app/modules/iam/seed_data.py"


def _serialize(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _role_row(role: Role) -> dict[str, Any]:
    return {"id": role.id, "entity_id": role.entity_id, "code": role.code, "name": role.name, "description": role.description, "is_system": bool(role.is_system), "is_active": bool(role.is_active), "is_deleted": bool(role.is_deleted), "created_at": _serialize(role.created_at)}


def _feature_row(feature: Feature) -> dict[str, Any]:
    return {"id": feature.id, "code": feature.code, "name": feature.name, "description": feature.description, "parent_id": feature.parent_id, "icon": feature.icon, "url": feature.route, "order_index": feature.order_index, "is_system": bool(feature.is_system), "is_active": bool(feature.is_active), "is_deleted": bool(feature.is_deleted), "created_at": _serialize(feature.created_at)}


def _permission_row(permission: RoleFeaturePermission) -> dict[str, Any]:
    return {"id": permission.id, "role_id": permission.role_id, "feature_id": permission.feature_id, "can_create": bool(permission.can_create), "can_view": bool(permission.can_view), "can_update": bool(permission.can_update), "can_delete": bool(permission.can_delete), "is_deleted": bool(permission.is_deleted), "sidebar_order": permission.sidebar_order, "created_at": _serialize(permission.created_at)}


def _encoded_snapshot(payload: dict[str, list[dict[str, Any]]]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded = base64.b85encode(gzip.compress(raw)).decode("ascii")
    chunks = [encoded[index : index + 100] for index in range(0, len(encoded), 100)]
    return "_COMPRESSED_SNAPSHOT = (\n" + "\n".join(f"    {json.dumps(chunk)}" for chunk in chunks) + "\n)"


def _write_snapshot(payload: dict[str, list[dict[str, Any]]]) -> None:
    source = SNAPSHOT_PATH.read_text()
    replacement = _encoded_snapshot(payload)
    updated, count = re.subn(r"^_COMPRESSED_SNAPSHOT = \(\n.*?^\)\n\n\n@lru_cache", replacement + "\n\n\n@lru_cache", source, flags=re.MULTILINE | re.DOTALL)
    if count != 1:
        raise RuntimeError("Could not locate the IAM snapshot payload in seed_data.py")
    SNAPSHOT_PATH.write_text(updated)


async def main() -> None:
    try:
        async with session_factory() as session:
            roles = list((await session.scalars(select(Role).order_by(Role.code))).all())
            features = list((await session.scalars(select(Feature).order_by(Feature.order_index, Feature.name, Feature.id))).all())
            permissions = list((await session.scalars(select(RoleFeaturePermission).order_by(RoleFeaturePermission.role_id, RoleFeaturePermission.feature_id))).all())
        payload = {"roles": [_role_row(role) for role in roles], "features": [_feature_row(feature) for feature in features], "permissions": [_permission_row(permission) for permission in permissions]}
        _write_snapshot(payload)
        print(f"Refreshed IAM seed snapshot: {len(roles)} roles, {len(features)} features, and {len(permissions)} permissions.")
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
