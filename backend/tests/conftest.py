import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db import Base, get_db
from sqlalchemy.pool import StaticPool

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from sqlalchemy import inspect
def override_get_db():
    print(f"DEBUG: override_get_db called. Tables: {inspect(engine).get_table_names()}")
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()
app.dependency_overrides[get_db] = override_get_db
app.state.limiter.enabled = False

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    print("DEBUG: setup_database running. Tables:", Base.metadata.tables.keys())
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture()
def db_session():
    with TestingSessionLocal() as session:
        yield session
