"""Staff service handling order tracking, menu availability, and inferred data review."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import MenuItem, Order
from app.schemas.order_schema import OrderResponse
from app.schemas.staff_schema import MenuItemStaffResponse
from app.services.menu_service import calculate_content_hash
from app.services.order_service import _format_order

class StaffError(Exception):
    """Base staff error."""

class OrderNotFoundError(StaffError):
    """Raised when the requested order does not exist."""

class MenuItemNotFoundError(StaffError):
    """Raised when the requested menu item does not exist."""

class InvalidStatusTransitionError(StaffError):
    """Raised when an order status change is not permitted."""

# Defines the allowed status transitions for an order.
# Each status maps to a set of statuses it can transition into.
VALID_TRANSITIONS = {
    "placed": {"preparing", "completed"},
    "preparing": {"ready", "completed"},
    "ready": {"completed"},
    "completed": set(),  # Completed orders cannot transition further.
}


def get_order(db: Session, order_id: int) -> OrderResponse:
    """Retrieve a specific order using its ID."""

    # Fetch the order by its primary key.
    order = db.get(Order, order_id)

    # Raise an error if the order does not exist.
    if not order:
        raise OrderNotFoundError(f"Order {order_id} not found.")

    # Convert the database order object into the standard API response.
    return _format_order(order)


def list_orders(
    db: Session,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0
) -> list[OrderResponse]:
    """Retrieve orders with optional status filtering and pagination."""

    # Build a query that returns the newest orders first.
    stmt = (
        select(Order)
        .order_by(Order.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    # Apply the status filter only when a status is provided.
    if status:
        stmt = stmt.where(Order.status == status)

    # Execute the query and convert each order into its response schema.
    return [_format_order(o) for o in db.scalars(stmt).all()]

def list_menu_items(
    db: Session,
    limit: int = 100,
    offset: int = 0
) -> list[MenuItemStaffResponse]:
    """Retrieve active menu items with pagination."""

    # Exclude soft-deleted items and order the results by item ID.
    stmt = (
        select(MenuItem)
        .where(MenuItem.deleted_at.is_(None))
        .order_by(MenuItem.id)
        .offset(offset)
        .limit(limit)
    )

    # Convert the retrieved SQLAlchemy objects into staff response schemas.
    return [
        MenuItemStaffResponse.model_validate(m)
        for m in db.scalars(stmt).all()
    ]


def update_order_status(
    db: Session,
    order_id: int,
    new_status: str
) -> OrderResponse:
    """Update an order's status after validating the transition."""

    # Retrieve the requested order.
    order = db.get(Order, order_id)

    # Ensure the order exists before attempting an update.
    if not order:
        raise OrderNotFoundError(f"Order {order_id} not found.")

    # Get the statuses allowed from the order's current status.
    # Return an empty set if the current status has no defined transitions.
    allowed = VALID_TRANSITIONS.get(order.status, set())

    # Prevent invalid status changes.
    if new_status not in allowed:
        raise InvalidStatusTransitionError(
            f"Cannot transition order from '{order.status}' to '{new_status}'."
        )

    # Update the order's status.
    order.status = new_status

    # Persist the status change to the database.
    db.commit()

    # Refresh the object to retrieve its latest database state.
    db.refresh(order)

    # Return the updated order in the standard response format.
    return _format_order(order)


def toggle_item_availability(
    db: Session,
    item_id: int,
    is_available: bool
) -> MenuItemStaffResponse:
    """Enable or disable a menu item without regenerating its embedding."""

    # Fetch the menu item only if it has not been soft-deleted.
    item = db.scalar(
        select(MenuItem).where(
            MenuItem.id == item_id,
            MenuItem.deleted_at.is_(None)
        )
    )

    # Raise an error if the item does not exist or has been deleted.
    if not item:
        raise MenuItemNotFoundError(f"Menu item {item_id} not found.")

    # Update availability so other services can immediately filter the item.
    item.is_available = is_available

    # Save the availability change.
    db.commit()

    # Refresh the object with the latest database values.
    db.refresh(item)

    # Return the updated menu item using the staff response schema.
    return MenuItemStaffResponse.model_validate(item)


def list_review_items(db: Session) -> list[MenuItemStaffResponse]:
    """Retrieve menu items that require staff verification."""

    # Fetch non-deleted menu items marked for review.
    stmt = (
        select(MenuItem)
        .where(
            MenuItem.needs_review.is_(True),
            MenuItem.deleted_at.is_(None)
        )
        .order_by(MenuItem.id)
    )

    # Convert the matching menu items into staff response schemas.
    return [
        MenuItemStaffResponse.model_validate(m)
        for m in db.scalars(stmt).all()
    ]

def review_menu_item(
    db: Session,
    item_id: int,
    updates: dict
) -> tuple[MenuItemStaffResponse, bool]:
    """Allow staff to verify inferred menu fields and detect embedding changes."""

    # Fetch the requested menu item, excluding soft-deleted records.
    item = db.scalar(
        select(MenuItem).where(
            MenuItem.id == item_id,
            MenuItem.deleted_at.is_(None)
        )
    )

    # Stop the review operation if the item does not exist.
    if not item:
        raise MenuItemNotFoundError(f"Menu item {item_id} not found.")

    # Only these menu fields are allowed to be modified through review.
    allowed = {
        "allergens",
        "veg_type",
        "spice_level",
        "ingredients",
        "category"
    }

    # Retrieve the fields whose values were originally inferred by the system.
    inferred = set(item.inferred_fields or [])

    # Apply staff corrections to the permitted fields.
    for field in allowed:
        if field in updates and updates[field] is not None:
            setattr(item, field, updates[field])

            # Remove corrected fields from the inferred fields list
            # because their values have now been explicitly reviewed.
            inferred.discard(field)

    # Save the remaining fields that still contain inferred values.
    item.inferred_fields = list(inferred)

    # Update the review flag. By default, the item is marked as reviewed.
    item.needs_review = updates.get("needs_review", False)

    # Collect all fields used to generate the semantic embedding text.
    # Changes to these fields may affect the meaning of the menu item.
    item_dict = {
        "name": item.name,
        "description": item.description,
        "category": item.category,
        "veg_type": item.veg_type,
        "spice_level": item.spice_level,
        "ingredients": item.ingredients,
        "allergens": item.allergens
    }

    # Generate a hash representing the current semantic content.
    new_hash = calculate_content_hash(item_dict)

    # Determine whether the semantic content has changed.
    # The boolean indicates whether a new embedding needs to be generated.
    reembed_needed = new_hash != item.content_hash

    if reembed_needed:
        # Store the new hash so future checks use the updated content.
        item.content_hash = new_hash

        # Remove the old embedding because it represents outdated content.
        # The embedding generation process must create its replacement.
        if item.embedding:
            db.delete(item.embedding)

    # Persist staff corrections and any embedding-related changes.
    db.commit()

    # Refresh the item to retrieve its latest database state.
    db.refresh(item)

    # Return the updated menu item and whether re-embedding is required.
    return MenuItemStaffResponse.model_validate(item), reembed_needed
