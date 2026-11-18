from decimal import Decimal
from fastapi import Depends
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.connection import SessionLocal
from app.services.menu_service import (
    create_menu_item,
    get_menu_item,
    get_all_menu_items,
    update_menu_item,
    soft_delete_menu_item,
)
from app.api.v1.router import test_router as router

# crud ops
def main(db: Session = Depends(get_db)) :
    test_item = None

    try:
        # 1. CREATE
        test_item = create_menu_item(
            db,
            name="CRUD Test Sandwich",
            description="Temporary item for testing database operations",
            price=Decimal("149.00"),
            category="Sandwiches",
            veg_type="veg",
            spice_level="mild",
            content_hash="temporary-test-hash",
        )

        print("CREATED:", test_item.id, test_item.name)

        # 2. READ
        item = get_menu_item(db, test_item.id)

        print("READ:", item.name, item.price)

        # 3. READ ALL
        items = get_all_menu_items(db)

        print("TOTAL ACTIVE MENU ITEMS:", len(items))

        # 4. UPDATE
        updated_item = update_menu_item(
            db,
            test_item.id,
            {"price": Decimal("159.00")},
        )

        print("UPDATED PRICE:", updated_item.price)

        # 5. SOFT DELETE
        deleted = soft_delete_menu_item(db, test_item.id)

        print("SOFT DELETE:", deleted)

        # 6. VERIFY DELETION
        deleted_item = get_menu_item(db, test_item.id)

        print("ITEM AFTER DELETION:", deleted_item)

        # 7. CLEAN UP TEST RECORD
        if test_item:
            db.delete(test_item)
            db.commit()
            print("TEST RECORD CLEANED UP")
        return{
            "message": "it worked as expected"
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

if __name__ == "__main__":
    main()