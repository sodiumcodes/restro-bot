"""Fixtures for end-to-end integration and conversation testing."""
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database.connection import get_db, engine
from app.database.models import MenuItem
from app.core.config import settings
from app.core.rate_limit import chat_limiter, session_limiter

TEST_DB_URL = settings.DATABASE_URL
TestSession = sessionmaker(bind=engine)

def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: end-to-end integration and conversation tests")

@pytest.fixture(scope="session")
def setup_test_db():
    # Verify vector extension exists on test database
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()

@pytest.fixture
def db_session(setup_test_db):
    # Reset all tables between tests to ensure test isolation
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE chat_messages, order_idempotency, order_items, orders, carts, menu_embeddings, menu_items, sessions, llm_fallback_log CASCADE;"))
        conn.commit()
    session = TestSession()
    # Seed fixed known menu for deterministic assertions
    items = [
        MenuItem(id=1, name="Margherita Pizza", description="Classic cheese pizza", price=Decimal("250.00"), veg_type="veg", category="Pizza", allergens=[], is_available=True, content_hash="h1"),
        MenuItem(id=2, name="Paneer Tikka", description="Spiced cottage cheese skewers", price=Decimal("220.00"), veg_type="veg", category="Starters", allergens=["dairy"], is_available=True, content_hash="h2"),
        MenuItem(id=3, name="Chicken Biryani", description="Aromatic spiced rice with chicken", price=Decimal("300.00"), veg_type="non-veg", category="Mains", allergens=[], is_available=True, content_hash="h3"),
        MenuItem(id=4, name="Brownie", description="Warm chocolate brownie with walnuts", price=Decimal("150.00"), veg_type="veg", category="Dessert", allergens=["nuts"], is_available=True, content_hash="h4"),
        MenuItem(id=5, name="Cold Coffee", description="Chilled brewed coffee with milk", price=Decimal("120.00"), veg_type="veg", category="Beverages", allergens=["milk"], is_available=False, content_hash="h5"),
    ]
    session.add_all(items)
    session.commit()
    yield session
    session.close()

@pytest.fixture
def client(db_session):
    # Clear in-memory rate limit windows between tests
    chat_limiter.requests.clear()
    session_limiter.requests.clear()
    # Override database dependency with isolated test session
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
