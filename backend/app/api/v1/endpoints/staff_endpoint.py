"""Staff endpoints for order tracking, menu availability, and review management."""
from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api.v1.router import staff_router as router
from app.database.connection import get_db
from app.schemas.order_schema import OrderResponse
from app.schemas.staff_schema import (
    ItemAvailabilityUpdate,
    MenuItemReviewUpdate,
    MenuItemStaffResponse,
    OrderStatusUpdate,
)
from app.services import staff_service

def _handle_staff_error(e: Exception) -> None:
    # Map domain exceptions to standard HTTP error codes
    if isinstance(e, (staff_service.OrderNotFoundError, staff_service.MenuItemNotFoundError)):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, staff_service.InvalidStatusTransitionError):
        raise HTTPException(status_code=409, detail=str(e))
    raise HTTPException(status_code=500, detail="Internal staff error.")

@router.get("/orders", response_model=list[OrderResponse])
def get_orders(
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[OrderResponse]:
    """List incoming orders newest first with optional status filter."""
    return staff_service.list_orders(db, status=status, limit=limit, offset=offset)


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_single_order(order_id: int, db: Session = Depends(get_db)) -> OrderResponse:
    """Retrieve details for a single order."""
    try:
        return staff_service.get_order(db, order_id)
    except Exception as e:
        _handle_staff_error(e)


@router.patch("/orders/{order_id}", response_model=OrderResponse)
def update_status(order_id: int, payload: OrderStatusUpdate, db: Session = Depends(get_db)) -> OrderResponse:
    """Update order lifecycle status according to allowed transitions."""
    try:
        return staff_service.update_order_status(db, order_id, payload.status)
    except Exception as e:
        _handle_staff_error(e)



@router.get("/menu", response_model=list[MenuItemStaffResponse])
def get_menu_items(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[MenuItemStaffResponse]:
    """List menu items with current availability."""
    return staff_service.list_menu_items(db, limit=limit, offset=offset)

@router.get("/menu/review", response_model=list[MenuItemStaffResponse])
def get_items_for_review(db: Session = Depends(get_db)) -> list[MenuItemStaffResponse]:
    """List items with unreviewed inferred fields."""
    return staff_service.list_review_items(db)


@router.patch("/menu/{item_id}/availability", response_model=MenuItemStaffResponse)
def toggle_availability(item_id: int, payload: ItemAvailabilityUpdate, db: Session = Depends(get_db)) -> MenuItemStaffResponse:
    """Toggle availability without re-embedding."""
    try:
        return staff_service.toggle_item_availability(db, item_id, payload.is_available)
    except Exception as e:
        _handle_staff_error(e)

@router.patch("/menu/{item_id}", response_model=MenuItemStaffResponse)
def review_menu_item(item_id: int, payload: MenuItemReviewUpdate, db: Session = Depends(get_db)) -> MenuItemStaffResponse:
    """Correct inferred fields and clear needs_review flag."""
    try:
        res, _ = staff_service.review_menu_item(db, item_id, payload.model_dump(exclude_unset=True))
        return res
    except Exception as e:
        _handle_staff_error(e)
