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

@app.get("/api/cv/{language}")
def get_cv(language: str):
    logger.info(f"Received request for CV download in {language}.")
    # cv = load_pdf("cv", f"CV_{language}.pdf")
    cv = load_pdf("cv", f"English_CV_2025.pdf")
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




# Allow your Vercel frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["https://your-vercel-domain.vercel.app"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======== MODELS ========
class CANMessage(BaseModel):
    id: str  # e.g. "0x123"
    data: List[int]  # e.g. [0, 0, 0, 0, 0, 0, 0, 0]
    direction: str = "TX"  # TX or RX
    timestamp: float = time.time()

class SimulationStatus(BaseModel):
    running: bool
    messages_sent: int
    bus_load: float


# ======== STATE ========
simulation_running = False
messages_sent = 0
connected_clients: List[WebSocket] = []
recent_messages: List[CANMessage] = []  # Add this global list


# ======== SIMULATION LOOP ========
async def simulate_can_bus():
    """Generate random CAN messages while simulation is running."""
    global simulation_running, messages_sent, recent_messages

    while simulation_running:
        await asyncio.sleep(random.uniform(0.1, 0.5))  # message rate
        msg = CANMessage(
            id=hex(random.randint(0x100, 0x7FF)),
            data=[random.randint(0, 255) for _ in range(8)],
            direction=random.choice(["TX", "RX"]),
            timestamp=time.time(),
        )
        messages_sent += 1
        recent_messages.insert(0, msg)
        recent_messages = recent_messages[:100]  # Keep only last 100
        # broadcast to all clients
        for ws in connected_clients:
            await ws.send_json(msg.dict())


# ======== ROUTES ========
@app.post("/api/can/start")
async def start_simulation(background_tasks: BackgroundTasks):
    global simulation_running
    if not simulation_running:
        simulation_running = True
        background_tasks.add_task(simulate_can_bus)
        logger.info("CAN simulation started.")
    else:
        logger.info("CAN simulation already running.")
    return {"status": "started"}


@app.post("/api/can/stop")
async def stop_simulation():
    global simulation_running
    simulation_running = False
    logger.info("CAN simulation stopped.")
    return {"status": "stopped"}


@app.post("/api/can/send")
async def send_custom_message(message: CANMessage):
    global messages_sent, recent_messages
    messages_sent += 1
    message.timestamp = time.time()
    message.direction = "TX"
    recent_messages.insert(0, message)
    recent_messages = recent_messages[:100]
    logger.info(f"Custom CAN message sent: {message}")
    # broadcast to clients
    for ws in connected_clients:
        await ws.send_json(message.dict())
    return {"status": "sent", "message": message}


@app.get("/api/can/status", response_model=SimulationStatus)
async def get_status():
    logger.info("CAN simulation status requested.")
    return SimulationStatus(
        running=simulation_running,
        messages_sent=messages_sent,
        bus_load=random.uniform(0, 100) if simulation_running else 0.0,
    )


@app.get("/api/can/messages")
async def get_can_messages():
    logger.info(f"Returning {len(recent_messages)} CAN messages.")
    """Get the list of recent CAN messages."""
    return [msg.dict() for msg in recent_messages]


# ======== REAL-TIME MONITOR ========
@app.websocket("/api/can/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    logger.info("WebSocket client connected.")
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except Exception:
        connected_clients.remove(websocket)
        logger.info("WebSocket client disconnected.")
