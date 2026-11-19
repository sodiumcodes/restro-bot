
"""
Generate and persist embeddings for Cafe Chatbot menu items.

Responsibilities:
- Find active menu items with missing or outdated embeddings.
- Build semantic text using the shared menu service.
- Generate one independent embedding per menu item.
- Persist embeddings in menu_embeddings.
- Skip items whose text and embedding model are unchanged.

Run from the backend directory:
    python -m scripts.generate_embeddings
"""

from sqlalchemy import select

from app.core.config import settings
from app.database.connection import SessionLocal
from app.database.models import MenuItem
from app.database.models.menu import MenuEmbedding
from app.llm.embeddings import EmbeddingService
from app.services.menu_service import build_embedding_text


def menu_item_to_dict(item: MenuItem) -> dict:
    """Convert a SQLAlchemy menu item into the format expected by build_embedding_text()."""

    return {
        "name": item.name,
        "description": item.description,
        "category": item.category,
        "veg_type": item.veg_type,
        "spice_level": item.spice_level,
        "ingredients": item.ingredients,
        "allergens": item.allergens,
    }


def fetch_menu_items() -> list[dict]:
    """
    Fetch active menu items and their existing embeddings.

    Returns plain dictionaries so the database session can be
    closed before making external API calls.
    """

    with SessionLocal() as db:

        statement = (
            select(MenuItem, MenuEmbedding)
            .outerjoin(
                MenuEmbedding,
                MenuEmbedding.item_id == MenuItem.id,
            )
            .where(MenuItem.deleted_at.is_(None))
            .order_by(MenuItem.id)
        )

        results = db.execute(statement).all()

        items = []

        for item, existing_embedding in results:

            embedded_text = build_embedding_text(
                menu_item_to_dict(item)
            )

            # An embedding is current only when both its text
            # and its model match the current configuration.
            is_up_to_date = (
                existing_embedding is not None
                and existing_embedding.embedded_text == embedded_text
                and existing_embedding.model == settings.EMBEDDING_MODEL
            )

            items.append({
                "id": item.id,
                "content_hash": item.content_hash,
                "embedded_text": embedded_text,
                "needs_embedding": not is_up_to_date,
            })

        # End the read transaction before external API calls.
        db.rollback()

        return items


def generate_embeddings(
    items: list[dict],
    service: EmbeddingService,
) -> list[dict]:
    """
    Generate embeddings for items that need them.

    EmbeddingService handles API batching internally.
    Each input text still receives its own independent vector.
    """

    pending_items = [
        item for item in items
        if item["needs_embedding"]
    ]

    if not pending_items:
        return []

    texts = [
        item["embedded_text"]
        for item in pending_items
    ]

    vectors = service.embed_documents(texts)

    if len(vectors) != len(pending_items):
        raise RuntimeError(
            "Embedding count does not match menu item count."
        )

    generated = []

    for item, vector in zip(pending_items, vectors):

        if len(vector) != service.dimension:
            raise RuntimeError(
                f"Invalid embedding dimension for menu item {item['id']}. "
                f"Expected {service.dimension}, got {len(vector)}."
            )

        generated.append({
            **item,
            "vector": vector,
        })

    return generated


def save_embeddings(generated: list[dict]) -> tuple[int, int]:
    """
    Insert or update embeddings in one database transaction.

    Re-check the menu content before saving so that an item
    changed during API generation doesn't receive a stale vector.
    """

    inserted = 0
    updated = 0
    skipped = 0

    if not generated:
        return inserted, updated

    generated_by_id = {
        item["id"]: item
        for item in generated
    }

    item_ids = list(generated_by_id)

    with SessionLocal() as db:

        try:
            statement = (
                select(MenuItem, MenuEmbedding)
                .outerjoin(
                    MenuEmbedding,
                    MenuEmbedding.item_id == MenuItem.id,
                )
                .where(MenuItem.id.in_(item_ids))
            )

            results = db.execute(statement).all()

            for menu_item, existing_embedding in results:

                generated_item = generated_by_id[menu_item.id]

                # Ignore items that were deleted while embeddings
                # were being generated.
                if menu_item.deleted_at is not None:
                    skipped += 1
                    continue

                current_text = build_embedding_text(
                    menu_item_to_dict(menu_item)
                )

                # Prevent saving an embedding generated from
                # outdated menu content.
                if (
                    current_text != generated_item["embedded_text"]
                    or menu_item.content_hash != generated_item["content_hash"]
                ):
                    skipped += 1
                    continue

                if existing_embedding is None:

                    embedding_record = MenuEmbedding(
                        item_id=menu_item.id,
                        embedded_text=generated_item["embedded_text"],
                        model=settings.EMBEDDING_MODEL,
                        embedding=generated_item["vector"],
                    )

                    db.add(embedding_record)
                    inserted += 1

                else:

                    existing_embedding.embedded_text = (
                        generated_item["embedded_text"]
                    )
                    existing_embedding.model = settings.EMBEDDING_MODEL
                    existing_embedding.embedding = generated_item["vector"]

                    updated += 1

            db.commit()

        except Exception:
            db.rollback()
            raise

    return inserted, updated


def main():

    service = EmbeddingService()

    try:
        print("\nStarting menu embedding generation...")

        # Step 1: Fetch menu items.
        items = fetch_menu_items()

        total_items = len(items)

        # Step 2: Identify items that need embeddings.
        pending_items = [
            item for item in items
            if item["needs_embedding"]
        ]

        already_current = total_items - len(pending_items)

        print(f"\nActive menu items: {total_items}")
        print(f"Already up to date: {already_current}")
        print(f"Need embeddings: {len(pending_items)}")
        print(f"Embedding model: {service.model}")
        print(f"Embedding dimensions: {service.dimension}")
        print(f"Batch size: {service.batch_size}")

        if not pending_items:
            print("\nAll menu embeddings are up to date.")
            return

        # Step 3: Generate embeddings.
        generated = generate_embeddings(items, service)

        print(f"\nGenerated vectors: {len(generated)}")

        # Step 4: Persist embeddings.
        inserted, updated = save_embeddings(generated)

        print("\nEmbedding generation completed!")
        print(f"Inserted: {inserted}")
        print(f"Updated:  {updated}")
        print(f"Skipped:  {already_current + len(generated) - inserted - updated}")
        print(f"Total active items: {total_items}")

    finally:
        service.close()


if __name__ == "__main__":
    main()
