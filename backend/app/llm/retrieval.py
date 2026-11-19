
"""
Dietary and allergy filters for Cafe Chatbot menu retrieval.
Semantic menu retriever for Cafe Chatbot.
    ->Responsibilities:
        - Generate customer query embeddings.
        - Perform vector similarity search using pgvector.
        - Apply dietary and allergy constraints.
        - Return structured menu results.
"""

from sqlalchemy import and_
from app.database.models.menu import MenuItem


from sqlalchemy import select, cast
from pgvector.sqlalchemy import HALFVEC
from app.core.config import settings
from app.database.connection import SessionLocal
from app.database.models.menu import MenuItem, MenuEmbedding
from app.llm.embeddings import EmbeddingService

def build_menu_filters(
    dietary_preference: str,
    allergy_status: str,
    allergens: list[str],
):
    """
    Build SQLAlchemy conditions for menu eligibility.

    Dietary preference and allergy constraints are applied
    before returning menu recommendations.
    """

    conditions = [
        MenuItem.deleted_at.is_(None),
        MenuItem.is_available.is_(True),
        MenuItem.needs_review.is_(False),
    ]

    # Dietary preference filtering.
    if dietary_preference == "veg":
        conditions.append(
            MenuItem.veg_type.in_(["veg", "vegan"])
        )

    elif dietary_preference == "egg":
        conditions.append(
            MenuItem.veg_type.in_(["veg", "vegan", "egg"])
        )

    elif dietary_preference == "non-veg":
        # Non-vegetarian customers can consider all food types.
        pass

    elif dietary_preference == "no-preference":
        pass

    else:
        raise ValueError(
            f"Unsupported dietary preference: {dietary_preference}"
        )

    # Allergy filtering.
    if allergy_status == "has_allergies":

        normalized_allergens = list({
            allergen.strip().casefold()
            for allergen in allergens
            if allergen and allergen.strip()
        })

        if not normalized_allergens:
            raise ValueError(
                "Specific allergens are required for allergy filtering."
            )

        # Unknown allergen information is not considered safe.
        conditions.append(
            MenuItem.allergens.is_not(None)
        )

        # Exclude items containing any reported allergen.
        conditions.append(
            ~MenuItem.allergens.overlap(normalized_allergens)
        )

    elif allergy_status == "none":
        pass

    else:
        raise ValueError(
            "Allergy status must be explicitly known before retrieval."
        )

    return conditions

class MenuRetriever:
    """Retrieves relevant menu items using semantic search."""

    def __init__(self, top_k: int = 5):
        self.top_k = top_k
        self.embedding_service = EmbeddingService()

    def retrieve(
        self,
        dietary_preference: str,
        allergy_status: str,
        allergens: list[str],
        query: str,
    ) -> list[dict]:
        """
        Retrieve relevant menu items.
        Args:
            dietary_preference: Customer's dietary preference.
            allergy_status: Customer's allergy status.
            allergens: List of reported allergens.
            query: Customer's menu-related query.

        Returns:
            Ranked list of eligible menu items.
        """

        if not query or not query.strip():
            raise ValueError("Customer query cannot be empty.")

        # Step 1: Generate query embedding.
        query_vector = self.embedding_service.embed_query(
            query.strip()
        )

        if len(query_vector) != settings.EMBEDDING_DIM:
            raise ValueError(
                "Query embedding dimension does not match "
                "the configured embedding dimension."
            )

        # Step 2: Build eligibility filters.
        filters = build_menu_filters(
            dietary_preference=dietary_preference,
            allergy_status=allergy_status,
            allergens=allergens,
        )

        # Step 3: Cast stored vectors to halfvec.
        # This matches the existing HNSW expression index.
        half_embedding = cast(
            MenuEmbedding.embedding,
            HALFVEC(settings.EMBEDDING_DIM),
        )

        # Step 4: Calculate cosine distance.
        distance = half_embedding.cosine_distance(
            query_vector
        )

        # Step 5: Construct the retrieval query.
        statement = (
            select(
                MenuItem,
                distance.label("distance"),
            )
            .join(
                MenuEmbedding,
                MenuEmbedding.item_id == MenuItem.id,
            )
            .where(
                *filters,
                MenuEmbedding.model == settings.EMBEDDING_MODEL,
            )
            .order_by(distance)
            .limit(self.top_k)
        )

        # Step 6: Execute database query.
        with SessionLocal() as db:
            results = db.execute(statement).all()

            # Step 7: Format results.
            retrieved_items = []

            for item, distance_value in results:

                retrieved_items.append({
                    "id": item.id,
                    "name": item.name,
                    "description": item.description,
                    "price": float(item.price),
                    "category": item.category,
                    "veg_type": item.veg_type,
                    "spice_level": item.spice_level,
                    "prep_time_minutes": item.prep_time_minutes,
                    "ingredients": item.ingredients,
                    "allergens": item.allergens,
                    "similarity_score": round(
                        1 - float(distance_value), 4
                    ),
                })

            return retrieved_items

    def close(self) -> None:
        """Close the embedding service."""

        self.embedding_service.close()
