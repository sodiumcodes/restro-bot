
"""
Embedding service for Cafe Chatbot.

Responsibilities:
- Generate embeddings for multiple menu items.
- Generate embeddings for individual customer queries.
- Validate embedding dimensions and values.
- Communicate with OpenRouter through its OpenAI-compatible API.
"""

import math
from typing import Sequence
from langchain_openai import OpenAI
from app.core.config import settings

class EmbeddingError(Exception):
    """Raised when embedding generation or validation fails."""


class EmbeddingService:
    """Generates and validates menu and query embeddings."""

    def __init__(self) -> None:
        """Initialize the OpenRouter embedding client."""

        if settings.EMBEDDING_PROVIDER.lower() != "openrouter":
            raise ValueError(
                f"Unsupported embedding provider: "
                f"{settings.EMBEDDING_PROVIDER}"
            )

        if not settings.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is missing.")

        if settings.EMBEDDING_DIM <= 0:
            raise ValueError("EMBEDDING_DIM must be positive.")

        if settings.EMBEDDING_BATCH_SIZE <= 0:
            raise ValueError("EMBEDDING_BATCH_SIZE must be positive.")

        self.model = settings.EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIM
        self.batch_size = settings.EMBEDDING_BATCH_SIZE

        # OpenAI SDK configured to communicate with OpenRouter.
        # SDK automatically retries selected transient API errors.
        self.client = OpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
            timeout=30.0,
            max_retries=3,
        )

    def _validate_embedding(
        self,
        embedding: Sequence[float],
    ) -> list[float]:
        """
        Validate one embedding vector.

        Ensures:
        - Correct dimensions.
        - Numeric values.
        - No NaN or infinity values.
        """

        if not embedding:
            raise EmbeddingError("Received an empty embedding.")

        if len(embedding) != self.dimension:
            raise EmbeddingError(
                f"Expected {self.dimension} dimensions, "
                f"received {len(embedding)}."
            )

        validated = []

        for value in embedding:
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise EmbeddingError(
                    "Embedding contains a non-numeric value."
                ) from exc

            if not math.isfinite(number):
                raise EmbeddingError(
                    "Embedding contains NaN or infinity."
                )

            validated.append(number)

        return validated

    def embed_documents(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]:
        """
        Generate one embedding per input text.

        Multiple texts are sent in batches to reduce API request overhead.

        Output order always matches input order.
        """

        if not texts:
            return []

        normalized_texts = list(texts)

        if any(
            not isinstance(text, str) or not text.strip()
            for text in normalized_texts
        ):
            raise ValueError(
                "All embedding inputs must be non-empty strings."
            )

        all_embeddings: list[list[float]] = []

        # Process the inputs in configurable batches.
        for start in range(
            0,
            len(normalized_texts),
            self.batch_size,
        ):
            batch = normalized_texts[
                start:start + self.batch_size
            ]

            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                    encoding_format="float",
                )

                # Sort by API input index to guarantee ordering.
                sorted_data = sorted(
                    response.data,
                    key=lambda item: item.index,
                )

                if len(sorted_data) != len(batch):
                    raise EmbeddingError(
                        "API returned an incomplete batch response."
                    )

                batch_embeddings = []

                for expected_index, item in enumerate(sorted_data):
                    if item.index != expected_index:
                        raise EmbeddingError(
                            "API response contains missing or "
                            "invalid input indices."
                        )

                    embedding = self._validate_embedding(
                        item.embedding
                    )

                    batch_embeddings.append(embedding)

                all_embeddings.extend(batch_embeddings)

            except EmbeddingError:
                raise

            except Exception as exc:
                raise EmbeddingError(
                    f"Failed to generate embeddings for "
                    f"batch starting at index {start}."
                ) from exc

        if len(all_embeddings) != len(normalized_texts):
            raise EmbeddingError(
                "Embedding count does not match input count."
            )

        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        """
        Generate an embedding for a single customer query.
        """

        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                "Query text must be a non-empty string."
            )

        embeddings = self.embed_documents([text])

        return embeddings[0]

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self.client.close()
