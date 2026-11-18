from datetime import datetime
from decimal import Decimal
from uuid import UUID
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
if TYPE_CHECKING:
    from app.database.models.session import ChatSession
    from app.database.models.menu import MenuItem
# ============================================================
# ORDER
# ============================================================

class Order(Base):
    __tablename__ = "orders"

    __table_args__ = (
        CheckConstraint(
            "order_type IN ('dine_in', 'takeaway')",
            name="ck_orders_order_type",
        ),
        CheckConstraint(
            "status IN ('placed', 'preparing', 'ready', 'completed')",
            name="ck_orders_status",
        ),
        CheckConstraint(
            """
            (order_type = 'dine_in'
                AND table_number IS NOT NULL
                AND contact IS NULL)
            OR
            (order_type = 'takeaway'
                AND contact IS NOT NULL
                AND table_number IS NULL)
            """,
            name="ck_orders_order_identification",
        ),
        CheckConstraint(
            "total_amount >= 0",
            name="ck_orders_total_nonnegative",
        ),
        Index(
            "ix_orders_status_created",
            "status",
            "created_at",
        ),
        Index(
            "ix_orders_session_created",
            "session_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id"),
        nullable=False,
    )

    order_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    table_number: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    contact: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        Text,
        default="placed",
        server_default=text("'placed'"),
        nullable=False,
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    session: Mapped["ChatSession"] = relationship(
        back_populates="orders",
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )

    idempotency_record: Mapped["OrderIdempotency | None"] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        uselist=False,
    )

# ============================================================
# ORDER ITEM
# ============================================================

class OrderItem(Base):
    __tablename__ = "order_items"

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_order_items_quantity_positive",
        ),
        CheckConstraint(
            "unit_price >= 0",
            name="ck_order_items_price_nonnegative",
        ),
        CheckConstraint(
            "line_total >= 0",
            name="ck_order_items_total_nonnegative",
        ),
        CheckConstraint(
            "line_total = unit_price * quantity",
            name="ck_order_items_line_total",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Nullable so historical orders survive hard menu-item deletion.
    menu_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("menu_items.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Snapshots preserve the values at order time.
    item_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    special_request: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    line_total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    order: Mapped["Order"] = relationship(
        back_populates="items",
    )

    menu_item: Mapped["MenuItem | None"] = relationship(
        back_populates="order_items",
    )

# ============================================================
# 8. ORDER IDEMPOTENCY
# ============================================================

class OrderIdempotency(Base):
    __tablename__ = "order_idempotency"

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "idempotency_key",
            name="uq_idempotency_session_key",
        ),
        UniqueConstraint(
            "order_id",
            name="uq_idempotency_order",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id"),
        nullable=False,
    )

    idempotency_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    request_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    session: Mapped["ChatSession"] = relationship(
        back_populates="idempotency_records",
    )

    order: Mapped["Order"] = relationship(
        back_populates="idempotency_record",
    )

