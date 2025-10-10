from local_db.db import engine, get_db
from local_db.models import Base, CVFile
from supabase_db.db import load_cv, store_cv, is_cv_already_stored
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

import os
import psycopg2


app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")
Base.metadata.create_all(bind=engine)


@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.on_event("startup")
def preload_resume():
    db: Session = next(get_db())
    if not db.query(CVFile).first():
        print("Preloading resume into database...")
        pdf_path = "data/English_CV_2025.pdf"
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            resume = CVFile(filename="English_CV_2025.pdf", filedata=pdf_bytes)
            db.add(resume)
            db.commit()
    else:
        print("Resume already exists in database, skipping preload.")
    db.close()

@app.on_event("startup")
def preload_cv():
    if not is_cv_already_stored():
        print("Preloading CV into Supabase...")
        store_cv()
    else:
        print("CV already exists in Supabase, skipping preload.")

@app.get("/api/local/cv")
def get_cv(db: Session = Depends(get_db)):
    resume = db.query(CVFile).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Curriculum Vitae not found")
    temp_path = f"/tmp/{resume.filename}"
    with open(temp_path, "wb") as f:
        f.write(resume.filedata)
    return FileResponse(temp_path, filename=resume.filename)

@app.get("/api/cv")
def get_cv():
    cv = load_cv()
    if not cv:
        raise HTTPException(status_code=404, detail="Curriculum Vitae not found")
    temp_path = f"/tmp/{cv.get("filename", "cv.pdf")}"
    with open(temp_path, "wb") as f:
        f.write(cv.get("filedata", ""))
    return FileResponse(temp_path, filename=cv.get("filename", "cv.pdf"))


# DB health check endpoint
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Healthcheck endpoint : check database connection."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
