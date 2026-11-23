"""Orders API endpoints for Cafe Chatbot."""
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.api.v1.router import order_router as router
from app.database.connection import get_db
from app.schemas.order_schema import OrderCreateRequest, OrderResponse
from app.services.order_service import create_order, StaleCartError, EmptyCartError, IdempotencyConflictError, OrderSessionClosedError, OrderSessionNotFoundError, ItemUnavailableError

def _handle_order_error(e: Exception) -> None:
    # Map domain exceptions to standard HTTP error responses
    if isinstance(e, StaleCartError):
        raise HTTPException(status_code=409, detail=e.current_cart.model_dump(mode="json"))
    if isinstance(e, (ItemUnavailableError, IdempotencyConflictError, OrderSessionClosedError)):
        raise HTTPException(status_code=409, detail=str(e))
    if isinstance(e, OrderSessionNotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, EmptyCartError):
        raise HTTPException(status_code=422, detail=str(e))
    raise HTTPException(status_code=500, detail="Internal order processing error.")


@router.post("", response_model=OrderResponse, status_code=201)
def place_order(
    payload: OrderCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> OrderResponse:
    """Confirm and place an order using explicit checkout and idempotency."""
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=422, detail="Idempotency-Key header is required.")

    try:
        return create_order(
            db=db,
            session_id=payload.session_id,
            order_type=payload.order_type,
            cart_version=payload.cart_version,
            table_number=payload.table_number,
            contact=payload.contact,
            idempotency_key=idempotency_key.strip(),
        )
    except Exception as e:
        _handle_order_error(e)
