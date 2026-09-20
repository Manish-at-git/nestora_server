"""Permission CRUD, summary, and matrix response contracts."""

from datetime import datetime

from pydantic import BaseModel, Field


class PermissionRequest(BaseModel):
    role_id: str
    feature_id: str
    can_create: bool = False
    can_view: bool = False
    can_update: bool = False
    can_delete: bool = False
    sidebar_order: int = Field(default=0, ge=0)


class PermissionResponse(PermissionRequest):
    id: str
    role_name: str | None = None
    feature_name: str | None = None
    created_at: datetime | None = None


class PermissionMutationResponse(BaseModel):
    ok: bool = True
    message: str = "Permissions updated successfully"


class RolePermissionSummary(BaseModel):
    id: str
    name: str
    code: str
    description: str | None = None
    entity_id: str | None = None
    entity_name: str | None = None
    is_active: bool
    created_at: datetime | None = None
    configured_features_count: int = 0
    accounts_count: int = 0
    total_features_count: int = 0


class MatrixPermissionItem(BaseModel):
    feature_id: str
    feature_name: str
    feature_code: str | None = None
    feature_description: str | None = None
    parent_id: str | None = None
    parent_name: str | None = None
    url: str | None = None
    order_index: int = 0
    icon: str | None = None
    can_create: bool = False
    can_view: bool = False
    can_update: bool = False
    can_delete: bool = False
    sidebar_order: int = 0


class MatrixRole(BaseModel):
    id: str
    name: str
    code: str
    description: str | None = None
    entity_id: str | None = None
    entity_name: str | None = None
    is_active: bool


class RolePermissionMatrixResponse(BaseModel):
    role: MatrixRole
    features: list[MatrixPermissionItem]


class BulkPermissionItem(BaseModel):
    feature_id: str
    can_create: bool = False
    can_view: bool = False
    can_update: bool = False
    can_delete: bool = False
    sidebar_order: int = Field(default=0, ge=0)


class BulkPermissionRequest(BaseModel):
    permissions: list[BulkPermissionItem]
