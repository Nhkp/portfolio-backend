from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CVDocument, PaperDocument


class CVRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active(self) -> CVDocument | None:
        return self.db.scalar(select(CVDocument).where(CVDocument.is_active.is_(True)).limit(1))

    def create_active(
        self,
        *,
        filename: str,
        content_type: str,
        storage_bucket: str,
        storage_path: str,
        size_bytes: int,
        checksum_sha256: str,
    ) -> CVDocument:
        self.db.query(CVDocument).filter(CVDocument.is_active.is_(True)).update({"is_active": False})
        document = CVDocument(
            filename=filename,
            content_type=content_type,
            storage_bucket=storage_bucket,
            storage_path=storage_path,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
            is_active=True,
        )
        self.db.add(document)
        self.db.flush()
        return document


class PaperRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_filename(self, filename: str) -> PaperDocument | None:
        return self.db.scalar(select(PaperDocument).where(PaperDocument.filename == filename).limit(1))
