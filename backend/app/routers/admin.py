from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.deps import require_roles
from db.models.user import User, UserRole
from db.session import SessionDep
from db.models.shipment import ShipmentStatus
from schemas.admin import (
    AdminShipmentListResponse,
    AssignShipmentPayload,
    CourierOption,
    CourierCreatePayload,
    CourierListResponse,
    CourierResponse,
    CourierUpdatePayload,
    RejectShipmentPayload,
    SystemSettingsPayload,
    SystemSettingsResponse,
    ShipmentSummaryResponse,
)
from schemas.base import BaseResponse
from schemas.shipment import ShipmentCreateResponse
from services.admin import (
    create_courier_service,
    deactivate_courier_service,
    assign_shipment_service,
    get_admin_shipments_service,
    get_courier_options_service,
    get_couriers_service,
    get_shipment_summary_service,
    update_system_settings_service,
    update_courier_service,
    reject_shipment_service,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@router.get(
    "/dashboard/summary",
    response_model=BaseResponse[ShipmentSummaryResponse],
)
async def get_shipment_summary(
    session: SessionDep,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> BaseResponse[ShipmentSummaryResponse]:
    summary = await get_shipment_summary_service(session)

    return {
        "status": "success",
        "message": "Shipment summary retrieved successfully",
        "data": summary,
    }


@router.put(
    "/settings",
    response_model=BaseResponse[SystemSettingsResponse],
)
async def update_system_settings(
    payload: SystemSettingsPayload,
    session: SessionDep,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> BaseResponse[SystemSettingsResponse]:
    try:
        settings_data = await update_system_settings_service(payload, session)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(exc), "code": "INTERNAL_ERROR"},
        ) from exc

    return {
        "status": "success",
        "message": "System settings updated successfully",
        "data": settings_data,
    }


@router.post(
    "/couriers",
    response_model=BaseResponse[CourierResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_courier(
    payload: CourierCreatePayload,
    session: SessionDep,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> BaseResponse[CourierResponse]:
    try:
        courier = await create_courier_service(payload, session)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": str(exc), "code": "DUPLICATE"},
        ) from exc

    return {
        "status": "success",
        "message": "Courier created successfully",
        "data": courier,
    }


@router.get(
    "/couriers",
    response_model=BaseResponse[CourierListResponse],
)
async def get_couriers(
    session: SessionDep,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> BaseResponse[CourierListResponse]:
    couriers = await get_couriers_service(session, page, limit)

    return {
        "status": "success",
        "message": "Couriers retrieved successfully",
        "data": couriers,
    }


@router.get(
    "/couriers/options",
    response_model=BaseResponse[list[CourierOption]],
)
async def get_courier_options(
    session: SessionDep,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> BaseResponse[list[CourierOption]]:
    couriers = await get_courier_options_service(session)

    return {
        "status": "success",
        "message": "Courier options retrieved successfully",
        "data": couriers,
    }


@router.put(
    "/couriers/{courier_id}",
    response_model=BaseResponse[CourierResponse],
)
async def update_courier(
    courier_id: int,
    payload: CourierUpdatePayload,
    session: SessionDep,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> BaseResponse[CourierResponse]:
    try:
        courier = await update_courier_service(courier_id, payload, session)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(exc), "code": "NOT_FOUND"},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": str(exc), "code": "DUPLICATE"},
        ) from exc

    return {
        "status": "success",
        "message": "Courier updated successfully",
        "data": courier,
    }


@router.delete(
    "/couriers/{courier_id}",
    response_model=BaseResponse[CourierResponse],
)
async def deactivate_courier(
    courier_id: int,
    session: SessionDep,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> BaseResponse[CourierResponse]:
    try:
        courier = await deactivate_courier_service(courier_id, session)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(exc), "code": "NOT_FOUND"},
        ) from exc

    return {
        "status": "success",
        "message": "Courier deactivated successfully",
        "data": courier,
    }


@router.put(
    "/shipments/{shipment_id}/assign",
    response_model=BaseResponse[ShipmentCreateResponse],
)
async def assign_shipment(
    shipment_id: int,
    payload: AssignShipmentPayload,
    session: SessionDep,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> BaseResponse[ShipmentCreateResponse]:
    try:
        shipment = await assign_shipment_service(
            shipment_id=shipment_id,
            courier_id=payload.courier_id,
            admin_id=current_user.id,
            session=session,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(exc), "code": "NOT_FOUND"},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": str(exc), "code": "INVALID_STATUS_TRANSITION"},
        ) from exc

    return {
        "status": "success",
        "message": "Shipment assigned successfully",
        "data": shipment,
    }


@router.put(
    "/shipments/{shipment_id}/reject",
    response_model=BaseResponse[ShipmentCreateResponse],
)
async def reject_shipment(
    shipment_id: int,
    payload: RejectShipmentPayload,
    session: SessionDep,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> BaseResponse[ShipmentCreateResponse]:
    try:
        shipment = await reject_shipment_service(
            shipment_id=shipment_id,
            rejection_reason=payload.rejection_reason,
            admin_id=current_user.id,
            session=session,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(exc), "code": "NOT_FOUND"},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": str(exc), "code": "INVALID_STATUS_TRANSITION"},
        ) from exc

    return {
        "status": "success",
        "message": "Shipment rejected successfully",
        "data": shipment,
    }


@router.get(
    "/shipments",
    response_model=BaseResponse[AdminShipmentListResponse],
)
async def get_admin_shipments(
    session: SessionDep,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    shipment_status: ShipmentStatus | None = Query(default=None, alias="status"),
    courier_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    query: str | None = Query(default=None, alias="q", min_length=1),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> BaseResponse[AdminShipmentListResponse]:
    shipments = await get_admin_shipments_service(
        session=session,
        shipment_status=shipment_status,
        courier_id=courier_id,
        date_from=date_from,
        date_to=date_to,
        query=query,
        page=page,
        limit=limit,
    )

    return {
        "status": "success",
        "message": "Admin shipments retrieved successfully",
        "data": shipments,
    }
