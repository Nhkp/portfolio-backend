# from local_db.db import engine, get_db
# from local_db.models import Base, CVFile
from supabase_db.db import load_pdf, store_pdf, is_pdf_already_stored, pdfs
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from fastapi import FastAPI, WebSocket, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import asyncio
import random
import time

import os
import psycopg2
import logging


app = FastAPI()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
# Base.metadata.create_all(bind=engine)


@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.on_event("startup")
def preload_pdfs():
    for pdf_key, pdf_info in pdfs.items():
        table_name = pdf_info["table_name"]
        path = pdf_info["path"]
        filename = os.path.basename(path)
        if is_pdf_already_stored(table_name=table_name, filename=filename):
            logger.info(f"{filename} already exists in Supabase table {table_name}, skipping preload.")
            continue
        logger.info(f"Preloading {filename} into Supabase table {table_name}...")
        store_pdf(table_name=table_name, pdf_path=path)

@app.get("/api/cv")
def get_cv():
    logger.info("Received request for CV download.")
    cv = load_pdf("cv", "English_CV_2025.pdf")
    if not cv:
        logger.warning("Curriculum Vitae not found in Supabase.")
        raise HTTPException(status_code=404, detail="Curriculum Vitae not found")
    temp_path = f"/tmp/{cv.get('filename', 'cv.pdf')}"
    with open(temp_path, "wb") as f:
        f.write(cv.get("filedata", ""))
    logger.info(f"Serving CV file: {cv.get('filename', 'cv.pdf')}")
    return FileResponse(temp_path, filename=cv.get("filename", "cv.pdf"))

@app.get("/api/paper/{paper_name}")
def get_paper(paper_name: str):
    logger.info(f"Received request for paper download: {paper_name}")
    paper = load_pdf("papers", paper_name)
    if not paper:
        logger.warning(f"Paper not found in Supabase: {paper_name}")
        raise HTTPException(status_code=404, detail="Paper not found")
    temp_path = f"/tmp/{paper.get('filename', paper_name)}"
    with open(temp_path, "wb") as f:
        f.write(paper.get("filedata", ""))
    logger.info(f"Serving paper file: {paper.get('filename', paper_name)}")
    return FileResponse(temp_path, filename=paper.get("filename", paper_name))

# # DB health check endpoint
# @app.get("/health")
# def health_check(db: Session = Depends(get_db)):
#     """Healthcheck endpoint : check database connection."""
#     try:
#         db.execute(text("SELECT 1"))
#         return {"status": "ok", "database": "connected"}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Database error: {e}")
