from datetime import datetime
from uuid import UUID
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
if TYPE_CHECKING:
    from app.database.models.session import ChatSession
# ============================================================
# CART
# ============================================================

class Cart(Base):
    __tablename__ = "carts"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Stores cart lines and relevant ordering state.
    state: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )

    # Optimistic concurrency control.
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default=text("1"),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    session: Mapped["ChatSession"] = relationship(
        back_populates="cart",
    )
