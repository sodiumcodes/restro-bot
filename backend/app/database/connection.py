from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Engine manages database connections and their connection pool.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True, #checks whether a pooled connection is still alive before using it.
    echo=settings.DEBUG #prints SQL statements during development.
)

# SessionLocal is a factory that creates new database sessions.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

# FastAPI dependency: provides a session to an API request.
def get_db():
    db = SessionLocal()

    try:
        #makes the session available to the API endpoint.
        yield db 
    finally:
        db.close()
