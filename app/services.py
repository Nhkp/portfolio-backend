from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.config import Settings, get_settings
from app.models import CVDocument
from app.repositories import CVRepository, PaperRepository
from app.storage import CVStorage


@dataclass(frozen=True)
class CVDownload:
    filename: str
    content_type: str
    content: bytes


class CVService:
    def __init__(
        self,
        repository: CVRepository,
        storage: CVStorage,
        settings: Settings | None = None,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.settings = settings or get_settings()

    def get_active_cv(self) -> CVDownload:
        document = self.repository.get_active()
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curriculum Vitae not found")

        content = self.storage.download_pdf(document.storage_bucket, document.storage_path)
        return CVDownload(filename=document.filename, content_type=document.content_type, content=content)

    async def replace_cv(self, upload: UploadFile) -> CVDocument:
        if upload.content_type != "application/pdf":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CV must be a PDF")

        content = await upload.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CV file is empty")

        if len(content) > self.settings.max_cv_upload_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="CV file is too large")

        checksum = sha256(content).hexdigest()
        filename = upload.filename or "cv.pdf"
        storage_path = f"cv/{uuid4()}.pdf"

        self.storage.upload_pdf(storage_path, content)
        return self.repository.create_active(
            filename=filename,
            content_type="application/pdf",
            storage_bucket=self.storage.bucket,
            storage_path=storage_path,
            size_bytes=len(content),
            checksum_sha256=checksum,
        )


class PaperService:
    def __init__(self, repository: PaperRepository, storage: CVStorage) -> None:
        self.repository = repository
        self.storage = storage

    def get_paper(self, filename: str) -> CVDownload:
        document = self.repository.get_by_filename(filename)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")

        content = self.storage.download_pdf(document.storage_bucket, document.storage_path)
        return CVDownload(filename=document.filename, content_type=document.content_type, content=content)


def as_pdf_stream(download: CVDownload) -> BytesIO:
    return BytesIO(download.content)
