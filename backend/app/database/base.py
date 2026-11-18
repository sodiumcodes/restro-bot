from sqlalchemy.orm import DeclarativeBase

# Parent class for all our database models.
class Base(DeclarativeBase):
    """
    Common parent class for all SQLAlchemy models.

    SQLAlchemy uses Base.metadata to keep track
    of all the tables defined by our models.
    """
    pass
