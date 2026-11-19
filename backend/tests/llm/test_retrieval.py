import pytest
from app.llm import retrieval
# --------------------------------------------------
# build_menu_filters tests
# The assertions count filters: there are 3 base eligibility filters, and each dietary preference or allergy selection adds more on top.
# --------------------------------------------------

def test_build_menu_filters_for_vegetarian_without_allergies():
    filters = retrieval.build_menu_filters(
        dietary_preference="veg",
        allergy_status="none",
        allergens=[],
    )

    # Base eligibility filters plus the vegetarian filter.
    assert len(filters) == 4


def test_build_menu_filters_for_egg_preference():
    filters = retrieval.build_menu_filters(
        dietary_preference="egg",
        allergy_status="none",
        allergens=[],
    )

    # Base eligibility filters plus the egg filter.
    assert len(filters) == 4


def test_build_menu_filters_for_non_veg():
    filters = retrieval.build_menu_filters(
        dietary_preference="non-veg",
        allergy_status="none",
        allergens=[],
    )

    # Non-veg needs no dietary filter, so only the base filters remain.
    assert len(filters) == 3


def test_build_menu_filters_normalizes_allergens():
    # Messy input: extra spaces, uppercase, and blank entries.
    filters = retrieval.build_menu_filters(
        dietary_preference="no-preference",
        allergy_status="has_allergies",
        allergens=[" Nuts ", "DAIRY", "", "  "],
    )

    # Three base filters plus "allergens is not null" and overlap exclusion.
    assert len(filters) == 5


def test_build_menu_filters_requires_specific_allergens():
    # has_allergies with only blank entries means no usable allergen was given.
    with pytest.raises(ValueError, match="Specific allergens are required"):
        retrieval.build_menu_filters(
            dietary_preference="veg",
            allergy_status="has_allergies",
            allergens=[" ", ""],
        )


def test_build_menu_filters_rejects_unknown_dietary_preference():
    with pytest.raises(ValueError, match="Unsupported dietary preference"):
        retrieval.build_menu_filters(
            dietary_preference="keto",
            allergy_status="none",
            allergens=[],
        )


def test_build_menu_filters_requires_explicit_allergy_status():
    # "unknown" is not accepted: the user must answer yes or no.
    with pytest.raises(ValueError, match="Allergy status"):
        retrieval.build_menu_filters(
            dietary_preference="veg",
            allergy_status="unknown",
            allergens=[],
        )


# --------------------------------------------------
# MenuRetriever tests
# --------------------------------------------------

def test_retrieve_rejects_empty_query(monkeypatch):
    class FakeEmbeddingService:
        def embed_query(self, query):
            # If the empty query reaches the embedding step, the test fails.
            raise AssertionError("Embedding must not run for an empty query")

        def close(self):
            pass

    monkeypatch.setattr(retrieval, "EmbeddingService", FakeEmbeddingService)
    retriever = retrieval.MenuRetriever()

    # Whitespace-only counts as empty.
    with pytest.raises(ValueError, match="query cannot be empty"):
        retriever.retrieve("veg", "none", [], "   ")


def test_retrieve_rejects_wrong_embedding_dimension(monkeypatch):
    class FakeEmbeddingService:
        def embed_query(self, query):
            # Only 2 numbers, while the configured dimension is 384.
            return [0.1, 0.2]

        def close(self):
            pass

    monkeypatch.setattr(retrieval.settings, "EMBEDDING_DIM", 384)
    monkeypatch.setattr(retrieval, "EmbeddingService", FakeEmbeddingService)
    retriever = retrieval.MenuRetriever()

    with pytest.raises(ValueError, match="dimension does not match"):
        retriever.retrieve("veg", "none", [], "spicy vegetarian food")


def test_close_closes_embedding_service(monkeypatch):
    class FakeEmbeddingService:
        closed = False

        def close(self):
            self.closed = True

    monkeypatch.setattr(retrieval, "EmbeddingService", FakeEmbeddingService)
    retriever = retrieval.MenuRetriever()

    retriever.close()

    assert retriever.embedding_service.closed is True


def test_build_menu_filters_for_no_preference_without_allergies():
    filters = retrieval.build_menu_filters(
        dietary_preference="no-preference",
        allergy_status="none",
        allergens=[],
    )

    # No dietary filter and no allergen filters, so only the base filters.
    assert len(filters) == 3


def test_build_menu_filters_combines_diet_and_allergen_filters():
    filters = retrieval.build_menu_filters(
        dietary_preference="veg",
        allergy_status="has_allergies",
        allergens=["nuts"],
    )

    # 3 base + 1 vegetarian + 2 allergen filters.
    assert len(filters) == 6


def test_build_menu_filters_requires_allergens_when_list_is_empty():
    # Existing test covers blank strings; this covers a truly empty list.
    with pytest.raises(ValueError, match="Specific allergens are required"):
        retrieval.build_menu_filters(
            dietary_preference="veg",
            allergy_status="has_allergies",
            allergens=[],
        )