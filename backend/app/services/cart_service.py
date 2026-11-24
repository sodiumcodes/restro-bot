from decimal import Decimal
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database.models import Cart, ChatSession, MenuItem, Order
from app.services.session_service import SessionNotFoundError
from app.schemas.cart_schema import CartLineResponse, CartResponse

# Base exception for all cart-related errors.
class CartError(Exception):
    """Base cart error."""
    
class SessionClosedError(CartError):
    """Raised when an order has already been placed for the session."""

class MenuItemError(CartError):
    """Raised when a menu item is invalid, unavailable, or violates cart limits."""

class StaleCartVersionError(CartError):
    """Raised when the client's cart version does not match the latest DB version."""
    def __init__(self, current_cart: CartResponse):
        # Store the latest cart so the client can refresh its outdated state.
        self.current_cart = current_cart
        super().__init__("Stale cart version.")

def _validate_session(db: Session, session_id: UUID) -> None:
    """Verify that the session exists and has not already placed an order."""

    # Check whether the requested chat session exists.
    if not db.scalar(select(ChatSession.id).where(ChatSession.id == session_id)):
        raise SessionNotFoundError(f"Session {session_id} not found.")

    # A session cannot modify its cart after placing an order.
    if db.scalar(select(Order.id).where(Order.session_id == session_id).limit(1)):
        raise SessionClosedError("Order already placed for this session.")

def _build_response( session_id: UUID, version: int, lines_data: list[dict], db: Session )-> CartResponse:
    """Build the cart response using current menu item details and DB prices."""

    # Return an empty cart with a zero total when no items exist.
    if not lines_data:
        return CartResponse(
            session_id=session_id,
            version=version,
            lines=[],
            total=Decimal("0.00")
        )

    # Fetch all menu items in one query to avoid individual DB queries per item.
    item_ids = [l["item_id"] for l in lines_data]
    items = {
        m.id: m
        for m in db.scalars(
            select(MenuItem).where(MenuItem.id.in_(item_ids))
        ).all()
    }

    lines, total = [], Decimal("0.00")

    for l in lines_data:
        item = items.get(l["item_id"])

        # Exclude items that no longer exist, are deleted, or are unavailable.
        if not item or item.deleted_at or not item.is_available:
            continue

        # Calculate the line total using the current database price.
        line_tot = Decimal(str(item.price)) * l["quantity"]
        total += line_tot

        # Convert stored cart data into the response schema.
        lines.append(
            CartLineResponse(
                item_id=item.id,
                name=item.name,
                quantity=l["quantity"],
                unit_price=Decimal(str(item.price)),
                line_total=line_tot,
                special_request=l.get("special_request")
            )
        )

    # Return the cart with its calculated total and current version.
    return CartResponse(
        session_id=session_id,
        version=version,
        lines=lines,
        total=total
    )

def get_cart(db: Session, session_id: UUID) -> CartResponse:
    """Retrieve the cart, creating an empty one if it does not exist."""

    # Ensure the session is valid before accessing its cart.
    _validate_session(db, session_id)
    cart = db.get(Cart, session_id)

    # Initialize a new cart with version 1 when no cart exists.
    if not cart:
        cart = Cart(session_id=session_id, state={"lines": []}, version=1)
        db.add(cart)
        db.commit()

    # Build the response using the latest menu item details.
    return _build_response(
        session_id,
        cart.version,
        cart.state.get("lines", []),
        db
    )

def add_item(
    db: Session,
    session_id: UUID,
    item_id: int,
    quantity: int,
    special_request: str | None,
    expected_version: int
) -> CartResponse:
    """Add an item to the cart or increase its existing quantity."""

    # Verify that the requested menu item exists and is not soft-deleted.
    item = db.get(MenuItem, item_id)

    if not item or item.deleted_at:
        raise MenuItemError(f"Menu item {item_id} not found.")

    # Prevent unavailable menu items from being added to the cart.
    if not item.is_available:
        raise MenuItemError(f"Menu item '{item.name}' is currently unavailable.")

    # Validate the requested quantity against the configured cart limit.
    if quantity < 1 or quantity > settings.CART_MAX_QUANTITY:
        raise MenuItemError(
            f"Quantity must be between 1 and {settings.CART_MAX_QUANTITY}."
        )

    def mutate(lines: list[dict]) -> list[dict]:
        """Add a new cart line or update the quantity of an existing line."""

        for l in lines:
            if l["item_id"] == item_id:

                # Ensure the combined quantity does not exceed the cart limit.
                if l["quantity"] + quantity > settings.CART_MAX_QUANTITY:
                    raise MenuItemError(
                        f"Total exceeds limit {settings.CART_MAX_QUANTITY}."
                    )

                # Increase the existing item's quantity.
                l["quantity"] += quantity

                # Update the special request only when a new value is provided.
                if special_request is not None:
                    l["special_request"] = special_request

                return lines

        # Add a new entry when the item is not already present in the cart.
        lines.append({
            "item_id": item_id,
            "quantity": quantity,
            "special_request": special_request
        })

        return lines

    # Apply the mutation through the shared version-checking mechanism.
    return _mutate_cart(db, session_id, expected_version, mutate)

def update_item(
    db: Session,
    session_id: UUID,
    item_id: int,
    quantity: int | None,
    special_request: str | None,
    expected_version: int
) -> CartResponse:
    """Update an existing item's quantity or special request."""

    # Prevent quantities above the configured maximum.
    if quantity is not None and quantity > settings.CART_MAX_QUANTITY:
        raise MenuItemError(
            f"Quantity cannot exceed {settings.CART_MAX_QUANTITY}."
        )

    def mutate(lines: list[dict]) -> list[dict]:
        """Locate the target item and apply the requested updates."""

        # Find the cart line corresponding to the requested menu item.
        target = next(
            (l for l in lines if l["item_id"] == item_id),
            None
        )

        # An item must already exist in the cart before it can be updated.
        if not target:
            raise MenuItemError(f"Item {item_id} not in cart.")

        # A quantity of zero means the item should be removed.
        if quantity == 0:
            return [l for l in lines if l["item_id"] != item_id]

        # Update quantity only when a new quantity is provided.
        if quantity is not None:
            target["quantity"] = quantity

        # Update or clear the special request when a value is provided.
        if special_request is not None:
            target["special_request"] = special_request or None

        return lines

    # Apply the update while checking for concurrent cart modifications.
    return _mutate_cart(db, session_id, expected_version, mutate)

def _mutate_cart(
    db: Session,
    session_id: UUID,
    expected_version: int,
    mutate_fn
) -> CartResponse:
    """Apply a cart modification after checking the client's expected version."""

    # Validate the session before allowing cart modifications.
    _validate_session(db, session_id)

    # Retrieve the existing cart or initialize a new one.
    cart = db.get(Cart, session_id) or Cart(
        session_id=session_id,
        state={"lines": []},
        version=1
    )

    # Add a newly initialized cart to the current database session.
    if cart.session_id not in db:
        db.add(cart)
        db.flush()

    # Prevent overwriting changes made by another request or client.
    if cart.version != expected_version:
        # Return the latest cart state so the client can resolve the conflict.
        raise StaleCartVersionError(
            _build_response(
                session_id,
                cart.version,
                cart.state.get("lines", []),
                db
            )
        )

    # Apply the requested operation to a copy of the existing cart lines.
    new_lines = mutate_fn(list(cart.state.get("lines", [])))

    # Save the updated cart state and increment its version.
    cart.state = {"lines": new_lines}
    cart.version += 1

    # Persist the changes to the database.
    db.commit()

    # Return the updated cart with recalculated totals.
    return _build_response(session_id, cart.version, new_lines, db)

def remove_item(
    db: Session,
    session_id: UUID,
    item_id: int,
    expected_version: int
) -> CartResponse:
    """Remove an item by reusing the update operation with quantity zero."""

    return update_item(
        db,
        session_id,
        item_id,
        quantity=0,
        special_request=None,
        expected_version=expected_version
    )

def clear_cart(
    db: Session,
    session_id: UUID,
    expected_version: int
) -> CartResponse:
    """Remove all items from the cart while preserving its version history."""

    # Replace the existing cart lines with an empty list.
    return _mutate_cart(
        db,
        session_id,
        expected_version,
        lambda _: []
    )