from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base


class ShipmentStatus(str, Enum):
    PENDING = "PENDING"
    REJECTED = "REJECTED"
    ASSIGNED = "ASSIGNED"
    PICKED_UP = "PICKED_UP"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    COMPLETED = "COMPLETED"


shipment_status_enum = ENUM(
    ShipmentStatus,
    name="shipment_status",
    create_type=False,
)


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(primary_key=True)
    tracking_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    courier_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    sender_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sender_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    origin_address: Mapped[str] = mapped_column(Text, nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(100), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    destination_address: Mapped[str] = mapped_column(Text, nullable=False)
    package_description: Mapped[str] = mapped_column(Text, nullable=False)
    weight_kg: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
        nullable=False,
    )
    status: Mapped[ShipmentStatus] = mapped_column(
        shipment_status_enum,
        index=True,
        nullable=False,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_image_url: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TrackingHistory(Base):
    __tablename__ = "tracking_histories"

    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(
        ForeignKey("shipments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[ShipmentStatus] = mapped_column(
        shipment_status_enum,
        nullable=False,
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )