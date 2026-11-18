
"""
Menu ingestion script.

Responsibilities:
- Read the Menu worksheet from Excel.
- Validate required fields and allowed values.
- Convert comma-separated ingredients and allergens into lists.
- Calculate semantic content hashes.
- Insert new menu items or update existing ones.
- Delete stale embeddings when semantic content changes.
- Commit all valid rows in one database transaction.

Embedding generation is handled separately.
"""

from pathlib import Path
from decimal import Decimal, InvalidOperation

import pandas as pd

from sqlalchemy import select

from app.database.connection import SessionLocal
from app.database.models import MenuItem
from app.services.menu_service import calculate_content_hash


# ------------------------------------------------------------
# PATHS
# ------------------------------------------------------------

# This script is located at backend/scripts/ingest_menu.py.
# Therefore, parents[1] points to the backend directory.
BASE_DIR = Path(__file__).resolve().parents[2]

MENU_FILE = BASE_DIR / "data" / "menu.xlsx"


# ------------------------------------------------------------
# VALIDATION CONSTANTS
# ------------------------------------------------------------

VALID_CATEGORIES = {
    "Starters",
    "Soups & Salads",
    "Burgers & Sandwiches",
    "Pizza & Pasta",
    "Main Course",
    "Desserts",
    "Drinks",
}

VALID_VEG_TYPES = {
    "veg",
    "non-veg",
    "vegan",
    "egg",
}

VALID_SPICE_LEVELS = {
    "none",
    "mild",
    "medium",
    "hot",
}


# ------------------------------------------------------------
# PARSING HELPERS
# ------------------------------------------------------------

def is_missing(value) -> bool:
    """Check whether an Excel cell is empty."""
    return pd.isna(value) or (
        isinstance(value, str) and not value.strip()
    )


def required_text(value, field: str) -> str:
    """Validate and normalize required text."""
    if is_missing(value):
        raise ValueError(f"{field} is required")

    return str(value).strip()


def parse_list(value) -> list[str]:
    """Convert comma-separated Excel text into a Python list."""
    if is_missing(value):
        return []

    return [
        part.strip()
        for part in str(value).split(",")
        if part.strip()
    ]


def parse_price(value) -> Decimal:
    """Parse and validate a non-negative price."""
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Invalid price")

    if not price.is_finite() or price < 0:
        raise ValueError(
            "Price must be a finite non-negative number"
        )

    return price


def parse_prep_time(value) -> int | None:
    """Parse preparation time as a non-negative integer."""
    if is_missing(value):
        return None

    try:
        number = float(value)
    except (ValueError, TypeError):
        raise ValueError("Invalid preparation time")

    if not number.is_integer() or number < 0:
        raise ValueError(
            "Preparation time must be a non-negative integer"
        )

    return int(number)


def parse_boolean(value) -> bool:
    """Convert supported Excel values into Python booleans."""
    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()

    if normalized in {"true", "1", "yes"}:
        return True

    if normalized in {"false", "0", "no"}:
        return False

    raise ValueError("is_available must be TRUE or FALSE")


# ------------------------------------------------------------
# ROW NORMALIZATION
# ------------------------------------------------------------

def normalize_row(row) -> dict:
    """Validate and normalize one Excel row."""

    item = {
        "name": required_text(row["name"], "name"),
        "description": required_text(
            row["description"], "description"
        ),
        "price": parse_price(row["price"]),
        "category": required_text(
            row["category"], "category"
        ),
        "veg_type": required_text(
            row["veg_type"], "veg_type"
        ).lower(),
        "spice_level": required_text(
            row["spice_level"], "spice_level"
        ).lower(),
        "prep_time_minutes": parse_prep_time(
            row["prep_time_minutes"]
        ),
        "ingredients": parse_list(row["ingredients"]),
        "allergens": parse_list(row["allergens"]),
        "is_available": parse_boolean(row["is_available"]),
    }

    if item["category"] not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category: {item['category']}"
        )

    if item["veg_type"] not in VALID_VEG_TYPES:
        raise ValueError(
            f"Invalid veg_type: {item['veg_type']}"
        )

    if item["spice_level"] not in VALID_SPICE_LEVELS:
        raise ValueError(
            f"Invalid spice_level: {item['spice_level']}"
        )

    # Hash only the fields used for semantic embedding.
    item["content_hash"] = calculate_content_hash(item)

    return item


# ------------------------------------------------------------
# EXCEL VALIDATION
# ------------------------------------------------------------

def read_and_validate_menu() -> list[dict]:
    """Read Excel and validate all rows before database changes."""

    if not MENU_FILE.exists():
        raise FileNotFoundError(
            f"Menu file not found: {MENU_FILE}"
        )

    dataframe = pd.read_excel(
        MENU_FILE,
        sheet_name="Menu",
    )

    required_columns = {
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
    }

    missing_columns = required_columns - set(dataframe.columns)

    if missing_columns:
        raise ValueError(
            f"Missing Excel columns: {missing_columns}"
        )

    normalized_items = []
    errors = []
    seen_names = set()

    for index, row in dataframe.iterrows():
        try:
            item = normalize_row(row)

            normalized_name = item["name"].casefold()

            if normalized_name in seen_names:
                raise ValueError(
                    "Duplicate item name in Excel file"
                )

            seen_names.add(normalized_name)
            normalized_items.append(item)

        except (ValueError, TypeError) as error:
            errors.append(
                f"Excel row {index + 2}: {error}"
            )

    if errors:
        print("Menu validation failed:")

        for error in errors:
            print("-", error)

        raise ValueError(
            f"Found {len(errors)} invalid rows. "
            "Nothing was imported."
        )

    return normalized_items


# ------------------------------------------------------------
# DATABASE UPSERT
# ------------------------------------------------------------

def ingest_menu():
    """Insert or update menu items in one transaction."""

    normalized_items = read_and_validate_menu()

    inserted = 0
    updated = 0
    skipped = 0

    with SessionLocal() as db:
        try:
            for data in normalized_items:

                item = db.scalar(
                    select(MenuItem).where(
                        MenuItem.name == data["name"],
                        MenuItem.deleted_at.is_(None),
                    )
                )

                # --------------------------------------------
                # INSERT
                # --------------------------------------------

                if item is None:
                    new_item = MenuItem(
                        **data,
                        inferred_fields=[],
                        needs_review=False,
                    )

                    db.add(new_item)
                    inserted += 1
                    continue

                # --------------------------------------------
                # CHECK SEMANTIC CHANGES
                # --------------------------------------------

                semantic_changed = (
                    item.content_hash != data["content_hash"]
                )

                if semantic_changed and item.embedding is not None:
                    # The old embedding no longer represents
                    # the updated menu content.
                    db.delete(item.embedding)

                # --------------------------------------------
                # UPDATE
                # --------------------------------------------

                changed = any(
                    getattr(item, field) != value
                    for field, value in data.items()
                )

                if changed:
                    for field, value in data.items():
                        setattr(item, field, value)

                    updated += 1
                else:
                    skipped += 1

            db.commit()

            print("\nMenu ingestion completed successfully!")
            print(f"Inserted: {inserted}")
            print(f"Updated:  {updated}")
            print(f"Skipped:  {skipped}")
            print(f"Total:    {len(normalized_items)}")

        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    ingest_menu()
