from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pgvector.sqlalchemy import Vector

from app.database.base import Base

# ============================================================
# MENU ITEM
# ============================================================

class MenuItem(Base):
    __tablename__ = "menu_items"

    __table_args__ = (
        CheckConstraint(
            "price >= 0",
            name="ck_menu_items_price_nonnegative"
        ),
        CheckConstraint(
            "veg_type IN ('veg', 'non-veg', 'vegan', 'egg')",
            name="ck_menu_items_veg_type",
        ),
        CheckConstraint(
            "spice_level IN ('none', 'mild', 'medium', 'hot')",
            name="ck_menu_items_spice_level",
        ),
        CheckConstraint(
            "prep_time_minutes >= 0",
            name="ck_menu_items_prep_time",
        ),

        # Unique name only among non-deleted menu items.
        Index(
            "uq_menu_items_active_name",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    category: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    veg_type: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    spice_level: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    prep_time_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    ingredients: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True,
    )

    allergens: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True,
    )

    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
    )

    # Tracks which optional fields were inferred by the LLM.
    inferred_fields: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        default=list,
        server_default=text("ARRAY[]::TEXT[]"),
        nullable=False,
    )

    needs_review: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )

    # Used to detect changes in text used for embeddings.
    content_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Soft deletion: NULL means the item has not been deleted.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(), #lets PostgreSQL generate the creation timestamp.
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(), #updates the timestamp when SQLAlchemy updates the object.
        nullable=False,
    )

    #?note: 
    # updated_at is updated by SQLAlchemy when it issues an update. It isn't a database trigger for updates performed directly through SQL.

    # One menu item can have at most one embedding.
    embedding: Mapped["MenuEmbedding | None"] = relationship(
        back_populates="menu_item",
        cascade="all, delete-orphan",
        uselist=False,
    )

    # A menu item can appear in many historical order items.
    order_items: Mapped[list["OrderItem"]] = relationship(
        back_populates="menu_item",
    )


# ============================================================
# MENU EMBEDDING
# ============================================================

class MenuEmbedding(Base):
    __tablename__ = "menu_embeddings"

    __table_args__ = (
        Index(
            "ix_menu_embeddings_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    # Primary key is also a foreign key to menu_items.
    # This enforces one embedding per menu item.
    item_id: Mapped[int] = mapped_column(
        ForeignKey("menu_items.id", ondelete="CASCADE"),
        primary_key=True,
    )

    embedded_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    model: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Dimension 384 follows the current project specification.
    # Verify it against the actual embedding model before migration.
    embedding: Mapped[list[float]] = mapped_column(
        Vector(384),
        nullable=False,
    )

    menu_item: Mapped["MenuItem"] = relationship(
        back_populates="embedding",
    )
