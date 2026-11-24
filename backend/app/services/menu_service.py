import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import MenuItem

def create_menu_item(
    db: Session,
    *,
    name: str,
    description: str,
    price: Decimal,
    content_hash: str,
    **optional_fields,
) -> MenuItem:
    """Create and persist a menu item."""

    item = MenuItem(
        name=name,
        description=description,
        price=price,
        content_hash=content_hash,
        **optional_fields,
    )

    try:
        db.add(item)
        db.commit()
        # After committing, refreshing retrieves the latest database values, including generated IDs and server-generated timestamps.
        db.refresh(item)
        return item

    except IntegrityError:
        # Suppose we attempt to create a menu item with a duplicate active name. PostgreSQL rejects the insertion.
        #The session is then in a failed transaction state. rollback() resets it so it can be used again.
        db.rollback()
        raise


def get_menu_item(db: Session, item_id: int) -> MenuItem | None:
    """Retrieve one active menu item by ID."""

    statement = select(MenuItem).where(
        MenuItem.id == item_id,
        MenuItem.deleted_at.is_(None),
    )

    return db.scalar(statement)


def get_all_menu_items(db: Session) -> list[MenuItem]:
    """Retrieve all active menu items."""

    statement = (
        select(MenuItem)
        .where(MenuItem.deleted_at.is_(None))
        .order_by(MenuItem.name)
    )

    return list(db.scalars(statement).all())


def update_menu_item(
    db: Session,
    item_id: int,
    updates: dict,
) -> MenuItem | None:
    """Update an existing active menu item."""

    item = get_menu_item(db, item_id)

    if item is None:
        return None

    allowed_fields = {
        "name",
        "description",
        "price",
        "category",
        "veg_type",
        "spice_level",
        "prep_time_minutes",
        "ingredients",
        "allergens",
        "is_available",
        "inferred_fields",
        "needs_review",
        "content_hash",
    }

    invalid_fields = set(updates) - allowed_fields

    if invalid_fields:
        raise ValueError(
            f"Invalid update fields: {invalid_fields}"
        )

    for field, value in updates.items():
        setattr(item, field, value)

    try:
        db.commit()
        db.refresh(item)
        return item

    except IntegrityError:
        db.rollback()
        raise


def soft_delete_menu_item(
    db: Session,
    item_id: int,
) -> bool:
    """Soft-delete a menu item without physically removing it."""

    item = get_menu_item(db, item_id)

    if item is None:
        return False

    item.deleted_at = datetime.now(timezone.utc)
    item.is_available = False

    db.commit()

    return True


def normalize_optional_list(value) -> list[str]:
    """
    Normalize optional list fields such as ingredients and allergens.

    Handles None, empty lists, empty dictionaries, and empty strings.
    """

    if value is None:
        return []

    if isinstance(value, dict):
        if not value:
            return []

        raise ValueError(
            "Expected a list, received a non-empty dictionary."
        )

    if isinstance(value, str):
        value = value.strip()

        if value in {"", "{}", "[]"}:
            return []

        # Support comma-separated strings.
        return [
            part.strip()
            for part in value.split(",")
            if part.strip()
        ]

    if isinstance(value, (list, tuple, set)):
        return [
            str(item).strip()
            for item in value
            if item is not None and str(item).strip()
        ]

    raise ValueError(
        f"Unsupported list field type: {type(value).__name__}"
    )


def build_embedding_text(item: dict) -> str:
    """
    Build the semantic text representation of a menu item.

    Missing optional values are represented as 'Not specified'.
    This function must remain consistent between menu ingestion
    and embedding generation.
    """

    name = str(item.get("name") or "").strip()
    description = str(item.get("description") or "").strip()

    if not name:
        raise ValueError("Menu item name cannot be empty.")

    if not description:
        raise ValueError(
            f"Description is missing for menu item: {name}"
        )

    category = item.get("category") or "Not specified"
    veg_type = item.get("veg_type") or "Not specified"
    spice_level = item.get("spice_level") or "Not specified"

    ingredients = normalize_optional_list(
        item.get("ingredients")
    )

    allergens = normalize_optional_list(
        item.get("allergens")
    )

    return (
        f"Name: {name}\n"
        f"Description: {description}\n"
        f"Category: {category}\n"
        f"Dietary type: {veg_type}\n"
        f"Spice level: {spice_level}\n"
        f"Ingredients: {', '.join(ingredients) or 'Not specified'}\n"
        f"Allergens: {', '.join(allergens) or 'Not specified'}"
    )


def calculate_content_hash(item: dict) -> str:
    """
    Generate a stable SHA-256 hash of the semantic menu content.
    """

    content = build_embedding_text(item)

    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()
