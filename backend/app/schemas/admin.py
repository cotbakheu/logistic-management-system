from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from db.models.shipment import ShipmentStatus


class ShipmentSummaryResponse(BaseModel):
    pending_orders: int = Field(ge=0)
    in_transit: int = Field(ge=0)
    delivered_today: int = Field(ge=0)
    rejected: int = Field(ge=0)


class SystemSettingsPayload(BaseModel):
    pending_alert_timeout_minutes: int = Field(gt=0)
    auto_complete_days: int = Field(gt=0)


class SystemSettingsResponse(SystemSettingsPayload):
    pass


class CourierCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=1, max_length=150)
    phone: str = Field(min_length=8, max_length=20)
    password: str = Field(min_length=8)


class CourierUpdatePayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, min_length=1, max_length=150)
    phone: str | None = Field(default=None, min_length=8, max_length=20)
    password: str | None = Field(default=None, min_length=8)
    is_active: bool | None = None


class CourierResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: str | None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CourierListResponse(BaseModel):
    items: list[CourierResponse]
    total: int
    page: int
    limit: int


class CourierOption(BaseModel):
    id: int
    name: str


class AssignShipmentPayload(BaseModel):
    courier_id: int = Field(gt=0)


class RejectShipmentPayload(BaseModel):
    rejection_reason: str = Field(min_length=1)


class AdminShipmentUser(BaseModel):
    id: int
    name: str


class AdminShipmentListItem(BaseModel):
    id: int
    tracking_number: str
    customer: AdminShipmentUser
    courier: AdminShipmentUser | None
    sender_name: str
    sender_phone: str
    origin_address: str
    recipient_name: str
    recipient_phone: str
    destination_address: str
    package_description: str
    weight_kg: Decimal
    status: ShipmentStatus
    rejection_reason: str | None
    proof_image_url: str | None
    delivered_at: datetime | None
    created_at: datetime
    updated_at: datetime
    is_overdue_pending: bool


class AdminShipmentListResponse(BaseModel):
    items: list[AdminShipmentListItem]
    total: int
    page: int
    limit: int
