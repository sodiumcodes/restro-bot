"""Retention service purging expired customer data per retention policy."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database.models import Cart, ChatMessage, ChatSession, LLMFallbackLog, Order


def cleanup_retention(db: Session, days: int | None = None, dry_run: bool = False) -> dict[str, int]:
    """
    Purge chat messages, carts, LLM fallback logs, and non-order sessions older than retention period.
    Anonymizes contact details on past orders without deleting financial order records.
    """
    retention_days = days if days is not None else settings.RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    # 1. Identify expired messages
    msg_stmt = select(ChatMessage.id).where(ChatMessage.created_at < cutoff)
    msg_ids = list(db.scalars(msg_stmt).all())

    # 2. Identify expired LLM fallback logs
    log_stmt = select(LLMFallbackLog.id).where(LLMFallbackLog.created_at < cutoff)
    log_ids = list(db.scalars(log_stmt).all())

    # 3. Identify sessions without completed orders eligible for full deletion
    ordered_sessions = select(Order.session_id)
    session_stmt = select(ChatSession.id).where(
        ChatSession.created_at < cutoff,
        ChatSession.id.not_in(ordered_sessions),
    )
    session_ids = list(db.scalars(session_stmt).all())

    # 4. Identify carts eligible for deletion
    cart_stmt = select(Cart.session_id).where(Cart.updated_at < cutoff)
    cart_ids = list(db.scalars(cart_stmt).all())

    # 5. Orders with contact to anonymize
    order_stmt = select(Order.id).where(Order.created_at < cutoff, Order.contact.is_not(None))
    order_ids = list(db.scalars(order_stmt).all())

    counts = {
        "chat_messages": len(msg_ids),
        "llm_logs": len(log_ids),
        "carts": len(cart_ids),
        "sessions": len(session_ids),
        "orders_anonymized": len(order_ids),
    }

    if dry_run:
        return counts

    # Execute mutations in single transaction
    if msg_ids:
        db.execute(delete(ChatMessage).where(ChatMessage.id.in_(msg_ids)))
    if log_ids:
        db.execute(delete(LLMFallbackLog).where(LLMFallbackLog.id.in_(log_ids)))
    if cart_ids:
        db.execute(delete(Cart).where(Cart.session_id.in_(cart_ids)))
    if session_ids:
        db.execute(delete(ChatSession).where(ChatSession.id.in_(session_ids)))
    if order_ids:
        db.execute(update(Order).where(Order.id.in_(order_ids)).values(contact=None))

    db.commit()
    return counts
