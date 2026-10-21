from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from core.config import settings
from db.models.shipment import Shipment, ShipmentStatus, TrackingHistory
from db.models.user import User, UserRole
from schemas.shipment import ShipmentCreatePayload


async def create_shipment_service(
    payload: ShipmentCreatePayload,
    current_user: User,
    session: AsyncSession,
) -> Shipment:
    sender_phone = current_user.phone.strip() if current_user.phone else ""
    origin_address = "USER_DEFAULT_ORIGIN_ADDRESS"

    if not sender_phone:
        raise ValueError("Authenticated user must have a phone number")
    if not origin_address:
        raise ValueError("Default origin address is not configured")

    business_date = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y%m%d")
    tracking_prefix = f"TRX-{business_date}-"

    # Serialize number allocation for the same business day.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:tracking_prefix))"),
        {"tracking_prefix": tracking_prefix},
    )
    last_number = await session.scalar(
        select(func.max(Shipment.tracking_number)).where(
            Shipment.tracking_number.like(f"{tracking_prefix}%")
        )
    )
    sequence = int(last_number.rsplit("-", 1)[1]) + 1 if last_number else 1
    tracking_number = f"{tracking_prefix}{sequence:04d}"

    shipment = Shipment(
        tracking_number=tracking_number,
        customer_id=current_user.id,
        sender_name=current_user.name,
        sender_phone=sender_phone,
        origin_address=origin_address,
        recipient_name=payload.recipient_name,
        recipient_phone=payload.recipient_phone,
        destination_address=payload.destination_address,
        package_description=payload.package_description,
        weight_kg=payload.weight_kg,
        status=ShipmentStatus.PENDING,
    )
    session.add(shipment)
    await session.flush()

    session.add(
        TrackingHistory(
            shipment_id=shipment.id,
            status=ShipmentStatus.PENDING,
            notes="Shipment created and awaiting assignment.",
            created_by=current_user.id,
        )
    )

    try:
        await session.commit()
        await session.refresh(shipment)
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError(
            "Could not create shipment due to a database constraint"
        ) from exc

    return shipment


async def get_customer_shipments_service(
    customer_id: int,
    session: AsyncSession,
    shipment_status: ShipmentStatus | None = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    filters = [Shipment.customer_id == customer_id]
    if shipment_status is not None:
        filters.append(Shipment.status == shipment_status)

    total = await session.scalar(
        select(func.count(Shipment.id)).where(*filters)
    )
    shipments = (
        await session.scalars(
            select(Shipment)
            .where(*filters)
            .order_by(Shipment.created_at.desc(), Shipment.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).all()

    return {
        "items": shipments,
        "total": total or 0,
        "page": page,
        "limit": limit,
    }


async def confirm_shipment_service(
    shipment_id: int,
    customer_id: int,
    session: AsyncSession,
) -> Shipment:
    shipment = await session.scalar(
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .with_for_update()
    )

    if shipment is None:
        raise LookupError("Shipment not found")

    if shipment.customer_id != customer_id:
        raise PermissionError("You do not own this shipment")

    if shipment.status != ShipmentStatus.DELIVERED:
        raise ValueError(
            "Only delivered shipments can be confirmed",
        )

    shipment.status = ShipmentStatus.COMPLETED
    session.add(
        TrackingHistory(
            shipment_id=shipment.id,
            status=ShipmentStatus.COMPLETED,
            notes="Shipment arrival confirmed by the customer.",
            created_by=customer_id,
        )
    )

    try:
        await session.commit()
        await session.refresh(shipment)
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError(
            "Could not confirm shipment due to a database constraint",
        ) from exc

    return shipment


async def get_shipment_tracking_service(
    tracking_number: str,
    session: AsyncSession,
) -> dict:
    shipment = await session.scalar(
        select(Shipment).where(Shipment.tracking_number == tracking_number)
    )

    if shipment is None:
        raise LookupError("Shipment not found")

    tracking_history = (
        await session.scalars(
            select(TrackingHistory)
            .where(TrackingHistory.shipment_id == shipment.id)
            .order_by(TrackingHistory.created_at.asc(), TrackingHistory.id.asc())
        )
    ).all()

    return {
        "tracking_number": shipment.tracking_number,
        "status": shipment.status,
        "sender_name": shipment.sender_name,
        "sender_phone": shipment.sender_phone,
        "origin_address": shipment.origin_address,
        "recipient_name": shipment.recipient_name,
        "recipient_phone": shipment.recipient_phone,
        "destination_address": shipment.destination_address,
        "package_description": shipment.package_description,
        "weight_kg": shipment.weight_kg,
        "rejection_reason": shipment.rejection_reason,
        "proof_image_url": shipment.proof_image_url,
        "delivered_at": shipment.delivered_at,
        "created_at": shipment.created_at,
        "updated_at": shipment.updated_at,
        "tracking_history": tracking_history,
    }


async def get_shipment_detail_service(
    shipment_id: int,
    current_user: User,
    session: AsyncSession,
) -> dict:
    customer = aliased(User)
    courier = aliased(User)
    shipment_row = await session.execute(
        select(Shipment, customer, courier)
        .join(customer, Shipment.customer_id == customer.id)
        .outerjoin(courier, Shipment.courier_id == courier.id)
        .where(Shipment.id == shipment_id)
    )
    result = shipment_row.one_or_none()

    if result is None:
        raise LookupError("Shipment not found")

    shipment, customer_user, courier_user = result
    if (
        current_user.role == UserRole.COURIER
        and shipment.courier_id != current_user.id
    ):
        raise PermissionError("You are not assigned to this shipment")

    tracking_history = (
        await session.scalars(
            select(TrackingHistory)
            .where(TrackingHistory.shipment_id == shipment.id)
            .order_by(TrackingHistory.created_at.asc(), TrackingHistory.id.asc())
        )
    ).all()

    return {
        "id": shipment.id,
        "tracking_number": shipment.tracking_number,
        "customer": {
            "id": customer_user.id,
            "name": customer_user.name,
        },
        "courier": (
            {
                "id": courier_user.id,
                "name": courier_user.name,
            }
            if courier_user is not None
            else None
        ),
        "sender_name": shipment.sender_name,
        "sender_phone": shipment.sender_phone,
        "origin_address": shipment.origin_address,
        "recipient_name": shipment.recipient_name,
        "recipient_phone": shipment.recipient_phone,
        "destination_address": shipment.destination_address,
        "package_description": shipment.package_description,
        "weight_kg": shipment.weight_kg,
        "status": shipment.status,
        "rejection_reason": shipment.rejection_reason,
        "proof_image_url": shipment.proof_image_url,
        "delivered_at": shipment.delivered_at,
        "created_at": shipment.created_at,
        "updated_at": shipment.updated_at,
        "tracking_history": tracking_history,
    }
