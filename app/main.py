from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.repositories import CVRepository, PaperRepository
from app.services import CVService, PaperService, as_pdf_stream
from app.storage import CVStorage, get_cv_storage


def create_app() -> FastAPI:
    app = FastAPI(title="Portfolio Backend")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"message": "Hello World"}

    @app.get("/api")
    async def api_root() -> dict[str, object]:
        return {
            "message": "Portfolio Backend API",
            "endpoints": ["/api/cv", "/api/paper/{filename}", "/health"],
        }

    @app.get("/health")
    def health_check(db: Session = Depends(get_db)) -> dict[str, str]:
        try:
            db.execute(text("SELECT 1"))
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {exc}") from exc
        return {"status": "ok", "database": "connected"}

    @app.get("/api/cv")
    def get_cv(
        db: Session = Depends(get_db),
        storage: CVStorage = Depends(get_cv_storage),
    ) -> StreamingResponse:
        service = CVService(CVRepository(db), storage)
        download = service.get_active_cv()
        headers = {"Content-Disposition": f'attachment; filename="{download.filename}"'}
        return StreamingResponse(as_pdf_stream(download), media_type=download.content_type, headers=headers)

    @app.get("/api/paper/{filename}")
    def get_paper(
        filename: str,
        db: Session = Depends(get_db),
        storage: CVStorage = Depends(get_cv_storage),
    ) -> StreamingResponse:
        service = PaperService(PaperRepository(db), storage)
        download = service.get_paper(filename)
        headers = {"Content-Disposition": f'inline; filename="{download.filename}"'}
        return StreamingResponse(as_pdf_stream(download), media_type=download.content_type, headers=headers)

    @app.put("/api/admin/cv", status_code=status.HTTP_201_CREATED)
    async def upload_cv(
        file: UploadFile = File(...),
        x_admin_api_key: str = Header(default=""),
        db: Session = Depends(get_db),
        storage: CVStorage = Depends(get_cv_storage),
    ) -> dict[str, object]:
        settings = get_settings()
        if not settings.admin_api_key or x_admin_api_key != settings.admin_api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin API key")

        service = CVService(CVRepository(db), storage, settings)
        document = await service.replace_cv(file)
        db.commit()
        return {
            "id": document.id,
            "filename": document.filename,
            "size_bytes": document.size_bytes,
            "checksum_sha256": document.checksum_sha256,
            "is_active": document.is_active,
        }

    return app


app = create_app()
