"""Order service managing checkout, DB price revalidation, and idempotency."""
import hashlib, json
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import Cart, ChatSession, MenuItem, Order, OrderIdempotency, OrderItem
from app.schemas.order_schema import OrderItemResponse, OrderResponse
from app.services import cart_service

class OrderError(Exception): """Base order error."""
class OrderSessionNotFoundError(OrderError): """Session not found."""
class OrderSessionClosedError(OrderError): """Order already placed for session."""
class EmptyCartError(OrderError): """Cart is empty."""
class ItemUnavailableError(OrderError): """Item unavailable at placement."""
class IdempotencyConflictError(OrderError): """Key reused with different payload."""
class StaleCartError(OrderError):
    """Raised when cart version differs from client confirmation."""
    def __init__(self, current_cart):
        self.current_cart = current_cart
        super().__init__("Stale cart version.")


def _hash_request(data: dict) -> str:
    # Produce consistent SHA256 digest of normalized request fields
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()

def _format_order(order: Order) -> OrderResponse:
    # Snapshot past items and line amounts accurately
    items = [OrderItemResponse(
        menu_item_id=i.menu_item_id, 
        item_name=i.item_name, 
        unit_price=i.unit_price,
        quantity=i.quantity, 
        line_total=i.line_total, 
        special_request=i.special_request

    ) for i in order.items]
    
    return OrderResponse(
        order_id=order.id, 
        status=order.status, 
        order_type=order.order_type,
        table_number=order.table_number, 
        contact=order.contact, 
        total=order.total_amount, 
        items=items
    )


def create_order(db: Session, session_id: UUID, order_type: str, cart_version: int,
                 table_number: str | None, contact: str | None, idempotency_key: str) -> OrderResponse:
    
    # 1. Validate session existence
    if not db.scalar(select(ChatSession.id).where(ChatSession.id == session_id)):
        raise OrderSessionNotFoundError(f"Session {session_id} not found.")

    req_data = {
                "session_id": str(session_id), 
                "order_type": order_type, 
                "table": table_number, 
                "contact": contact
            }
    req_hash = _hash_request(req_data)

    # 2. Check idempotency record
    existing_rec = db.scalar(select(OrderIdempotency).where(
        OrderIdempotency.session_id == session_id, 
        OrderIdempotency.idempotency_key == idempotency_key
    ))
    if existing_rec:
        if existing_rec.request_hash == req_hash: 
            return _format_order(existing_rec.order)

        raise IdempotencyConflictError("Idempotency key reused with different request payload.")

    # 3. Reject if session already placed an order
    if db.scalar(select(Order.id)
        .where(Order.session_id == session_id).limit(1)):
            raise OrderSessionClosedError("Order already placed for this session.")

    # 4. Validate cart lines and concurrency version
    cart = db.get(Cart, session_id)
    lines_data = cart.state.get("lines", []) if cart else []

    if not lines_data: 
        raise EmptyCartError("Cannot place order with an empty cart.")

    if not cart or cart.version != cart_version:
        raise StaleCartError(cart_service.get_cart(db, session_id))

    # 5. Re-check item availability and recalculate totals strictly from DB
    item_ids = [l["item_id"] for l in lines_data]
    menu_items = {
            m.id: m 
            for m in db.scalars(select(MenuItem)
            .where(MenuItem.id.in_(item_ids))).all()
        }
    order_items_to_create, total_amount = [], Decimal("0.00")

    for l in lines_data:
        m = menu_items.get(l["item_id"])
        if not m or m.deleted_at or not m.is_available:
            name = m.name if m else f"Item {l['item_id']}"
            raise ItemUnavailableError(f"Menu item '{name}' is no longer available.")
        unit_price = Decimal(str(m.price))
        line_tot = unit_price * l["quantity"]
        total_amount += line_tot
        order_items_to_create.append(OrderItem(
            menu_item_id=m.id, 
            item_name=m.name, 
            unit_price=unit_price,
            quantity=l["quantity"], 
            special_request=l.get("special_request"), 
            line_total=line_tot
        ))

    # 6. Atomically persist order, items, idempotency key and clear cart
    order = Order(
        session_id=session_id, 
        order_type=order_type, 
        table_number=table_number,
        contact=contact, 
        status="placed", 
        total_amount=total_amount, 
        items=order_items_to_create
    )
    db.add(order)
    db.flush()
    db.add(OrderIdempotency(session_id=session_id, 
                            idempotency_key=idempotency_key, 
                            request_hash=req_hash, 
                            order_id=order.id)
                        )
    cart.state, cart.version = {"lines": []}, cart.version + 1
    db.commit()
    db.refresh(order)
    return _format_order(order)
