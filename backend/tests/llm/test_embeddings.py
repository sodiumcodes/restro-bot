
from app.llm.embeddings import EmbeddingService

def main():
    service = EmbeddingService()

    try:
        # Test individual query embedding
        query = "Something spicy and vegetarian"

        vector = service.embed_query(query)

        print("Query embedding dimensions:", len(vector))

        # Test multiple independent menu embeddings
        menu_items = [
            "Paneer Tikka. Grilled paneer with Indian spices.",
            "Cold Coffee. Chilled coffee with ice cream.",
            "Veg Burger. Burger with vegetable patty.",
        ]

        embeddings = service.embed_documents(menu_items)

        print("Number of menu embeddings:", len(embeddings))

        for index, embedding in enumerate(embeddings):
            print(
                f"Menu item {index + 1}: "
                f"{len(embedding)} dimensions"
            )

    finally:
        service.close()


if __name__ == "__main__":
    main()
