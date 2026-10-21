from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from db.models.shipment import ShipmentStatus


class ShipmentCreatePayload(BaseModel):
    recipient_name: str = Field(min_length=1, max_length=100)
    recipient_phone: str = Field(min_length=8, max_length=20)
    destination_address: str = Field(min_length=1)
    package_description: str = Field(min_length=1)
    weight_kg: Decimal = Field(gt=0, le=9999.99)

    @field_validator(
        "recipient_name",
        "recipient_phone",
        "destination_address",
        "package_description",
    )
    @classmethod
    def trim_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field must not be empty")
        return value

    @field_validator("recipient_phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if not value.lstrip("+").isdigit():
            raise ValueError("Phone must contain only digits and may start with +")
        return value


class ShipmentCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tracking_number: str
    status: ShipmentStatus
    created_at: datetime


class ShipmentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tracking_number: str
    status: ShipmentStatus
    recipient_name: str
    destination_address: str
    package_description: str
    weight_kg: Decimal
    created_at: datetime
    updated_at: datetime


class ShipmentListResponse(BaseModel):
    items: list[ShipmentListItem]
    total: int
    page: int
    limit: int


class ShipmentUserResponse(BaseModel):
    id: int
    name: str


class TrackingHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: ShipmentStatus
    notes: str
    created_at: datetime


class ShipmentDetailResponse(BaseModel):
    id: int
    tracking_number: str
    customer: ShipmentUserResponse
    courier: ShipmentUserResponse | None
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
    tracking_history: list[TrackingHistoryResponse]


class ShipmentTrackingResponse(BaseModel):
    tracking_number: str
    status: ShipmentStatus
    sender_name: str
    sender_phone: str
    origin_address: str
    recipient_name: str
    recipient_phone: str
    destination_address: str
    package_description: str
    weight_kg: Decimal
    rejection_reason: str | None
    proof_image_url: str | None
    delivered_at: datetime | None
    created_at: datetime
    updated_at: datetime
    tracking_history: list[TrackingHistoryResponse]
