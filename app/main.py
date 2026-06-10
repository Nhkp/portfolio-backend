import asyncio
import logging
import random
import time

from fastapi import BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, UploadFile, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.repositories import CVRepository
from app.services import CVService, as_pdf_stream
from app.storage import CVStorage, get_cv_storage


logger = logging.getLogger(__name__)

simulation_running = False
messages_sent = 0
connected_clients: list[WebSocket] = []
recent_messages: list["CANMessage"] = []


class CANMessage(BaseModel):
    id: str
    data: list[int]
    direction: str = "TX"
    timestamp: float = time.time()


class SimulationStatus(BaseModel):
    running: bool
    messages_sent: int
    bus_load: float


async def simulate_can_bus() -> None:
    global simulation_running, messages_sent, recent_messages

    while simulation_running:
        await asyncio.sleep(random.uniform(0.1, 0.5))
        msg = CANMessage(
            id=hex(random.randint(0x100, 0x7FF)),
            data=[random.randint(0, 255) for _ in range(8)],
            direction=random.choice(["TX", "RX"]),
            timestamp=time.time(),
        )
        messages_sent += 1
        recent_messages.insert(0, msg)
        recent_messages = recent_messages[:100]
        for ws in connected_clients:
            await ws.send_json(msg.model_dump())


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

    @app.post("/api/can/start")
    async def start_simulation(background_tasks: BackgroundTasks) -> dict[str, str]:
        global simulation_running
        if not simulation_running:
            simulation_running = True
            background_tasks.add_task(simulate_can_bus)
            logger.info("CAN simulation started.")
        else:
            logger.info("CAN simulation already running.")
        return {"status": "started"}

    @app.post("/api/can/stop")
    async def stop_simulation() -> dict[str, str]:
        global simulation_running
        simulation_running = False
        logger.info("CAN simulation stopped.")
        return {"status": "stopped"}

    @app.post("/api/can/send")
    async def send_custom_message(message: CANMessage) -> dict[str, object]:
        global messages_sent, recent_messages
        messages_sent += 1
        message.timestamp = time.time()
        message.direction = "TX"
        recent_messages.insert(0, message)
        recent_messages = recent_messages[:100]
        logger.info("Custom CAN message sent: %s", message)
        for ws in connected_clients:
            await ws.send_json(message.model_dump())
        return {"status": "sent", "message": message}

    @app.get("/api/can/status", response_model=SimulationStatus)
    async def get_status() -> SimulationStatus:
        logger.info("CAN simulation status requested.")
        return SimulationStatus(
            running=simulation_running,
            messages_sent=messages_sent,
            bus_load=random.uniform(0, 100) if simulation_running else 0.0,
        )

    @app.get("/api/can/messages")
    async def get_can_messages() -> list[dict[str, object]]:
        logger.info("Returning %s CAN messages.", len(recent_messages))
        return [msg.model_dump() for msg in recent_messages]

    @app.websocket("/api/can/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        connected_clients.append(websocket)
        logger.info("WebSocket client connected.")
        try:
            while True:
                await websocket.receive_text()
        except Exception:
            connected_clients.remove(websocket)
            logger.info("WebSocket client disconnected.")

    return app


app = create_app()
