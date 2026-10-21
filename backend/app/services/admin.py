from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from core.security import hash_password
from db.models.shipment import Shipment, ShipmentStatus, TrackingHistory
from db.models.system_setting import SystemSetting
from db.models.user import User, UserRole
from schemas.admin import (
    CourierCreatePayload,
    CourierUpdatePayload,
    SystemSettingsPayload,
)


BUSINESS_TIMEZONE = ZoneInfo("Asia/Jakarta")
DEFAULT_PENDING_ALERT_TIMEOUT_MINUTES = 30


async def update_system_settings_service(
    payload: SystemSettingsPayload,
    session: AsyncSession,
) -> dict[str, int]:
    settings_to_save = {
        "pending_alert_timeout_minutes": (
            payload.pending_alert_timeout_minutes,
            "Durasi menit status PENDING sebelum ditandai terlambat",
        ),
        "auto_complete_days": (
            payload.auto_complete_days,
            "Durasi hari status DELIVERED sebelum otomatis menjadi COMPLETED",
        ),
    }

    for key, (value, description) in settings_to_save.items():
        setting = await session.get(SystemSetting, key)
        if setting is None:
            session.add(
                SystemSetting(
                    key=key,
                    value=str(value),
                    description=description,
                )
            )
        else:
            setting.value = str(value)
            setting.description = description

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError(
            "Could not save system settings due to a database constraint"
        ) from exc

    return {
        "pending_alert_timeout_minutes": payload.pending_alert_timeout_minutes,
        "auto_complete_days": payload.auto_complete_days,
    }


def _ensure_courier(user: User | None) -> User:
    if user is None:
        raise LookupError("Courier not found")
    if user.role != UserRole.COURIER:
        raise LookupError("Courier not found")
    return user


async def create_courier_service(
    payload: CourierCreatePayload,
    session: AsyncSession,
) -> User:
    existing_user = await session.scalar(
        select(User).where(
            (User.email == payload.email) | (User.name == payload.name)
        )
    )
    if existing_user:
        raise ValueError("Courier name or email already registered")

    courier = User(
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=UserRole.COURIER,
        is_active=True,
    )
    session.add(courier)

    try:
        await session.commit()
        await session.refresh(courier)
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError(
            "Could not create courier due to a database constraint"
        ) from exc

    return courier


async def get_couriers_service(
    session: AsyncSession,
    page: int = 1,
    limit: int = 20,
) -> dict:
    filters = [User.role == UserRole.COURIER]
    total = await session.scalar(
        select(func.count(User.id)).where(*filters)
    )
    couriers = (
        await session.scalars(
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc(), User.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).all()

    return {
        "items": couriers,
        "total": total or 0,
        "page": page,
        "limit": limit,
    }


async def get_courier_options_service(
    session: AsyncSession,
) -> list[dict[str, int | str]]:
    couriers = (
        await session.scalars(
            select(User)
            .where(
                User.role == UserRole.COURIER,
                User.is_active.is_(True),
            )
            .order_by(User.name.asc(), User.id.asc())
        )
    ).all()
    return [{"id": courier.id, "name": courier.name} for courier in couriers]


async def assign_shipment_service(
    shipment_id: int,
    courier_id: int,
    admin_id: int,
    session: AsyncSession,
) -> Shipment:
    shipment = await session.scalar(
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .with_for_update()
    )
    if shipment is None:
        raise LookupError("Shipment not found")

    courier = await session.scalar(
        select(User).where(
            User.id == courier_id,
            User.role == UserRole.COURIER,
            User.is_active.is_(True),
        )
    )
    if courier is None:
        raise LookupError("Active courier not found")
    if shipment.status != ShipmentStatus.PENDING:
        raise ValueError("Only pending shipments can be assigned")

    shipment.courier_id = courier.id
    shipment.status = ShipmentStatus.ASSIGNED
    session.add(
        TrackingHistory(
            shipment_id=shipment.id,
            status=ShipmentStatus.ASSIGNED,
            notes=f"Shipment assigned to courier {courier.name}.",
            created_by=admin_id,
        )
    )

    try:
        await session.commit()
        await session.refresh(shipment)
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError(
            "Could not assign shipment due to a database constraint"
        ) from exc

    return shipment


async def reject_shipment_service(
    shipment_id: int,
    rejection_reason: str,
    admin_id: int,
    session: AsyncSession,
) -> Shipment:
    shipment = await session.scalar(
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .with_for_update()
    )
    if shipment is None:
        raise LookupError("Shipment not found")
    if shipment.status != ShipmentStatus.PENDING:
        raise ValueError("Only pending shipments can be rejected")

    reason = rejection_reason.strip()
    if not reason:
        raise ValueError("Rejection reason must not be empty")

    shipment.status = ShipmentStatus.REJECTED
    shipment.rejection_reason = reason
    session.add(
        TrackingHistory(
            shipment_id=shipment.id,
            status=ShipmentStatus.REJECTED,
            notes=f"Shipment rejected: {reason}",
            created_by=admin_id,
        )
    )

    try:
        await session.commit()
        await session.refresh(shipment)
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError(
            "Could not reject shipment due to a database constraint"
        ) from exc

    return shipment


async def update_courier_service(
    courier_id: int,
    payload: CourierUpdatePayload,
    session: AsyncSession,
) -> User:
    courier = _ensure_courier(await session.get(User, courier_id))

    updates = payload.model_dump(exclude_unset=True)
    if "email" in updates or "name" in updates:
        duplicate_values = []
        if "email" in updates:
            duplicate_values.append(User.email == updates["email"])
        if "name" in updates:
            duplicate_values.append(User.name == updates["name"])
        duplicate = await session.scalar(
            select(User).where(
                User.id != courier_id,
                User.role == UserRole.COURIER,
                or_(*duplicate_values),
            )
        )
        if duplicate:
            raise ValueError("Courier name or email already registered")

    if "password" in updates:
        updates["password_hash"] = hash_password(updates.pop("password"))

    for field, value in updates.items():
        setattr(courier, field, value)

    try:
        await session.commit()
        await session.refresh(courier)
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError(
            "Could not update courier due to a database constraint"
        ) from exc

    return courier


async def deactivate_courier_service(
    courier_id: int,
    session: AsyncSession,
) -> User:
    courier = _ensure_courier(await session.get(User, courier_id))
    courier.is_active = False

    try:
        await session.commit()
        await session.refresh(courier)
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError(
            "Could not deactivate courier due to a database constraint"
        ) from exc

    return courier


async def get_shipment_summary_service(session: AsyncSession) -> dict[str, int]:
    business_today = datetime.now(BUSINESS_TIMEZONE).date()
    start_of_day = datetime.combine(
        business_today,
        time.min,
        tzinfo=BUSINESS_TIMEZONE,
    ).astimezone(timezone.utc)
    start_of_next_day = datetime.combine(
        business_today + timedelta(days=1),
        time.min,
        tzinfo=BUSINESS_TIMEZONE,
    ).astimezone(timezone.utc)

    summary = await session.execute(
        select(
            func.count()
            .filter(Shipment.status == ShipmentStatus.PENDING)
            .label("pending_orders"),
            func.count()
            .filter(Shipment.status == ShipmentStatus.IN_TRANSIT)
            .label("in_transit"),
            func.count()
            .filter(
                Shipment.delivered_at >= start_of_day,
                Shipment.delivered_at < start_of_next_day,
            )
            .label("delivered_today"),
            func.count()
            .filter(Shipment.status == ShipmentStatus.REJECTED)
            .label("rejected"),
        )
    )
    row = summary.one()

    return {
        "pending_orders": row.pending_orders,
        "in_transit": row.in_transit,
        "delivered_today": row.delivered_today,
        "rejected": row.rejected,
    }


async def get_admin_shipments_service(
    session: AsyncSession,
    shipment_status: ShipmentStatus | None = None,
    courier_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    query: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    filters = []

    if shipment_status is not None:
        filters.append(Shipment.status == shipment_status)
    if courier_id is not None:
        filters.append(Shipment.courier_id == courier_id)
    if date_from is not None:
        filters.append(
            Shipment.created_at
            >= datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        )
    if date_to is not None:
        filters.append(
            Shipment.created_at
            < datetime.combine(
                date_to + timedelta(days=1),
                time.min,
                tzinfo=timezone.utc,
            )
        )
    if query:
        search_pattern = f"%{query.strip()}%"
        filters.append(Shipment.tracking_number.ilike(search_pattern))

    total = await session.scalar(
        select(func.count(Shipment.id)).where(*filters)
    )
    setting_value = await session.scalar(
        select(SystemSetting.value).where(
            SystemSetting.key == "pending_alert_timeout_minutes"
        )
    )
    try:
        pending_alert_timeout_minutes = (
            int(setting_value)
            if setting_value is not None
            else DEFAULT_PENDING_ALERT_TIMEOUT_MINUTES
        )
    except ValueError as exc:
        raise ValueError(
            "Invalid pending alert timeout configuration"
        ) from exc

    now = datetime.now(timezone.utc)
    overdue_cutoff = now - timedelta(minutes=pending_alert_timeout_minutes)
    customer = aliased(User)
    courier = aliased(User)
    shipment_rows = (
        await session.execute(
            select(Shipment, customer, courier)
            .join(customer, Shipment.customer_id == customer.id)
            .outerjoin(courier, Shipment.courier_id == courier.id)
            .where(*filters)
            .order_by(
                case(
                    (Shipment.status == ShipmentStatus.PENDING, 0),
                    else_=1,
                ),
                Shipment.created_at.desc(),
                Shipment.id.desc(),
            )
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).all()

    items = [
        {
            "id": shipment.id,
            "tracking_number": shipment.tracking_number,
            "customer": {
                "id": customer.id,
                "name": customer.name,
            },
            "courier": (
                {
                    "id": courier.id,
                    "name": courier.name,
                }
                if courier is not None
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
            "is_overdue_pending": (
                shipment.status == ShipmentStatus.PENDING
                and shipment.created_at <= overdue_cutoff
            ),
        }
        for shipment, customer, courier in shipment_rows
    ]

    return {
        "items": items,
        "total": total or 0,
        "page": page,
        "limit": limit,
    }
