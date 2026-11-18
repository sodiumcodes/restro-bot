from datetime import datetime
from uuid import UUID, uuid4
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
if TYPE_CHECKING:
    from app.database.models.chat import ChatMessage
    from app.database.models.cart import Cart
    from app.database.models.order import Order, OrderIdempotency
# ============================================================
# CUSTOMER SESSION
# ============================================================

class ChatSession(Base):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    last_active: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )

    cart: Mapped["Cart | None"] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )

    orders: Mapped[list["Order"]] = relationship(
        back_populates="session",
    )

    idempotency_records: Mapped[list["OrderIdempotency"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
