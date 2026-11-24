from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock
import pytest
from sqlalchemy.exc import IntegrityError
from app.database.models import MenuItem
from app.services import menu_service

# --------------------------------------------------
# create_menu_item tests
# --------------------------------------------------

def test_create_menu_item_adds_commits_and_refreshes_item():
    db = MagicMock()

    item = menu_service.create_menu_item(
        db,
        name="CRUD Test Sandwich",
        description="Temporary item for testing",
        price=Decimal("149.00"),
        category="Sandwiches",
        veg_type="veg",
        spice_level="mild",
        content_hash="temporary-test-hash",
    )

    assert isinstance(item, MenuItem)
    assert item.name == "CRUD Test Sandwich"
    assert item.description == "Temporary item for testing"
    assert item.price == Decimal("149.00")
    assert item.category == "Sandwiches"
    assert item.veg_type == "veg"
    assert item.spice_level == "mild"
    assert item.content_hash == "temporary-test-hash"

    db.add.assert_called_once_with(item)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(item)


def test_create_menu_item_rolls_back_on_integrity_error():
    db = MagicMock()
    db.commit.side_effect = IntegrityError(
        "INSERT",
        {},
        Exception("duplicate active menu item"),
    )

    with pytest.raises(IntegrityError):
        menu_service.create_menu_item(
            db,
            name="Duplicate Sandwich",
            description="Test description",
            price=Decimal("149.00"),
            content_hash="duplicate-hash",
        )

    db.add.assert_called_once()
    db.rollback.assert_called_once()
    db.refresh.assert_not_called()


# --------------------------------------------------
# get_menu_item tests
# --------------------------------------------------

def test_get_menu_item_returns_active_item():
    db = MagicMock()
    expected_item = MenuItem(
        name="Paneer Sandwich",
        description="Grilled paneer sandwich",
        price=Decimal("149.00"),
        content_hash="paneer-sandwich-hash",
    )
    db.scalar.return_value = expected_item

    result = menu_service.get_menu_item(db, item_id=1)

    assert result is expected_item
    db.scalar.assert_called_once()


def test_get_menu_item_returns_none_when_item_does_not_exist():
    db = MagicMock()
    db.scalar.return_value = None

    result = menu_service.get_menu_item(db, item_id=999)

    assert result is None
    db.scalar.assert_called_once()