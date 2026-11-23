"""Cart API endpoints for Cafe Chatbot."""
from uuid import UUID
from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api.v1.router import cart_router as router
from app.database.connection import get_db
from app.schemas.cart_schema import (
    CartItemAdd,
    CartItemRemove,
    CartItemUpdate,
    CartResponse,
)
from app.services import cart_service


def _handle_cart_error(e: Exception) -> None:
    # Map domain exceptions to API HTTP error responses
    if isinstance(e, cart_service.StaleCartVersionError):
        raise HTTPException(status_code=409, detail=e.current_cart.model_dump(mode="json"))
    if isinstance(e, cart_service.SessionNotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, cart_service.SessionClosedError):
        raise HTTPException(status_code=409, detail=str(e))
    if isinstance(e, cart_service.MenuItemError):
        status = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status, detail=str(e))
    raise HTTPException(status_code=500, detail="Internal cart error.")


@router.get("/{session_id}", response_model=CartResponse)
def get_cart(session_id: UUID, db: Session = Depends(get_db)) -> CartResponse:
    """Retrieve current session cart with calculated prices and version."""
    try:
        return cart_service.get_cart(db, session_id)
    except Exception as e:
        _handle_cart_error(e)


@router.post("/{session_id}/items", response_model=CartResponse, status_code=200)
@router.post("/{session_id}", response_model=CartResponse, status_code=200)
def add_item(session_id: UUID, payload: CartItemAdd, db: Session = Depends(get_db)) -> CartResponse:
    """Add an item or increment quantity in the cart."""
    try:
        return cart_service.add_item(
            db, session_id, payload.item_id, payload.quantity,
            payload.special_request, payload.expected_version
        )
    except Exception as e:
        _handle_cart_error(e)


@router.patch("/{session_id}", response_model=CartResponse)
def update_item(session_id: UUID, payload: CartItemUpdate, db: Session = Depends(get_db)) -> CartResponse:
    """Update item quantity or special request directly without LLM."""
    try:
        return cart_service.update_item(
            db, session_id, payload.item_id, payload.quantity,
            payload.special_request, payload.expected_version
        )
    except Exception as e:
        _handle_cart_error(e)


@router.delete("/{session_id}/items/{item_id}", response_model=CartResponse)
def remove_item(session_id: UUID, item_id: int, expected_version: int = Query(ge=1), db: Session = Depends(get_db)) -> CartResponse:
    """Remove a specific item line from the cart."""
    try:
        return cart_service.remove_item(db, session_id, item_id, expected_version)
    except Exception as e:
        _handle_cart_error(e)


@router.delete("/{session_id}", response_model=CartResponse)
def clear_or_remove_item(session_id: UUID, payload: CartItemRemove, db: Session = Depends(get_db)) -> CartResponse:
    """Alternative removal endpoint accepting JSON body with expected version."""
    try:
        return cart_service.remove_item(db, session_id, payload.item_id, payload.expected_version)
    except Exception as e:
        _handle_cart_error(e)
