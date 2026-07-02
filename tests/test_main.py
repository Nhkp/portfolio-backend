import os
import sys
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_KEY"] = "test-key"
os.environ["ADMIN_API_KEY"] = "secret"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import get_db
from app.models import Base, CVDocument, PaperDocument
from app.storage import get_cv_storage
from main import app


class FakeStorage:
    bucket = "cvs"

    def __init__(self) -> None:
        self.files: dict[tuple[str, str], bytes] = {}

    def upload_pdf(self, path: str, content: bytes) -> None:
        self.files[(self.bucket, path)] = content

    def download_pdf(self, bucket: str, path: str) -> bytes:
        return self.files[(bucket, path)]


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def fake_storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture()
def client(db_session: Session, fake_storage: FakeStorage) -> Generator[TestClient, None, None]:
    def override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_cv_storage] = lambda: fake_storage
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_read_main(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}


def test_api_root(client: TestClient) -> None:
    response = client.get("/api")
    assert response.status_code == 200
    assert response.json() == {
        "message": "Portfolio Backend API",
        "endpoints": ["/api/cv", "/api/paper/{filename}", "/health"],
    }


def test_can_api_removed(client: TestClient) -> None:
    response = client.get("/api/can/status")
    assert response.status_code == 404


def test_health_check_success() -> None:
    mock_db = MagicMock()
    mock_db.execute.return_value = None
    app.dependency_overrides[get_db] = lambda: mock_db

    response = TestClient(app).get("/health")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_health_check_failure() -> None:
    mock_db = MagicMock()
    mock_db.execute.side_effect = Exception("Connection failed")
    app.dependency_overrides[get_db] = lambda: mock_db

    response = TestClient(app).get("/health")

    app.dependency_overrides.clear()
    assert response.status_code == 500
    assert "Database error" in response.json()["detail"]


def test_get_cv_not_found(client: TestClient) -> None:
    response = client.get("/api/cv")

    assert response.status_code == 404
    assert response.json() == {"detail": "Curriculum Vitae not found"}


def test_get_cv_streams_active_cv(
    client: TestClient,
    db_session: Session,
    fake_storage: FakeStorage,
) -> None:
    document = CVDocument(
        filename="cv.pdf",
        content_type="application/pdf",
        storage_bucket="cvs",
        storage_path="cv/current.pdf",
        size_bytes=8,
        checksum_sha256="a" * 64,
        is_active=True,
    )
    db_session.add(document)
    db_session.commit()
    fake_storage.files[("cvs", "cv/current.pdf")] = b"%PDF-1.4"

    response = client.get("/api/cv")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-1.4"


def test_get_paper_not_found(client: TestClient) -> None:
    response = client.get("/api/paper/missing.pdf")

    assert response.status_code == 404
    assert response.json() == {"detail": "Paper not found"}


def test_get_paper_streams_document(
    client: TestClient,
    db_session: Session,
    fake_storage: FakeStorage,
) -> None:
    document = PaperDocument(
        filename="paper.pdf",
        content_type="application/pdf",
        storage_bucket="papers",
        storage_path="paper/paper.pdf",
        size_bytes=8,
        checksum_sha256="c" * 64,
    )
    db_session.add(document)
    db_session.commit()
    fake_storage.files[("papers", "paper/paper.pdf")] = b"%PDF-1.4"

    response = client.get("/api/paper/paper.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'inline; filename="paper.pdf"'
    assert response.content == b"%PDF-1.4"


def test_admin_upload_requires_api_key(client: TestClient) -> None:
    response = client.put(
        "/api/admin/cv",
        files={"file": ("cv.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 401


def test_admin_upload_rejects_non_pdf(client: TestClient) -> None:
    response = client.put(
        "/api/admin/cv",
        headers={"X-Admin-API-Key": "secret"},
        files={"file": ("cv.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "CV must be a PDF"}


def test_admin_upload_creates_active_cv(
    client: TestClient,
    db_session: Session,
    fake_storage: FakeStorage,
) -> None:
    previous = CVDocument(
        filename="old.pdf",
        content_type="application/pdf",
        storage_bucket="cvs",
        storage_path="cv/old.pdf",
        size_bytes=8,
        checksum_sha256="b" * 64,
        is_active=True,
    )
    db_session.add(previous)
    db_session.commit()

    response = client.put(
        "/api/admin/cv",
        headers={"X-Admin-API-Key": "secret"},
        files={"file": ("new.pdf", b"%PDF-1.4 new", "application/pdf")},
    )

    assert response.status_code == 201
    assert response.json()["filename"] == "new.pdf"
    assert response.json()["is_active"] is True
    active_documents = db_session.query(CVDocument).filter(CVDocument.is_active.is_(True)).all()
    assert len(active_documents) == 1
    assert active_documents[0].filename == "new.pdf"
    assert list(fake_storage.files.values()) == [b"%PDF-1.4 new"]
