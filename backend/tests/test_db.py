
from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database.connection import get_db

from tests.test_router import router

@router.get("/test/db-connection")
def health_check(db: Session = Depends(get_db)):
    try:
        # Execute a simple query to verify database connectivity.
        db.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "application": "Cafe Chatbot",
            "database": "connected"
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed"
        )
