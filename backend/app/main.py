import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.services.event_bus import event_bus
from app.ws.manager import manager as ws_manager
from ai.orchestrator import orchestrator
from iot.simulator import simulator

# Import API routers
from app.api.sensors import router as sensors_router
from app.api.machines import router as machines_router
from app.api.workers import router as workers_router
from app.api.incidents import router as incidents_router
from app.api.actions import router as actions_router
from app.api.ai import router as ai_router
from app.api.digital_twin import router as digital_twin_router
from app.api.demo import router as demo_router
from app.api.general import router as general_router
from app.api.n8n_bridge import router as n8n_bridge_router  # Engineer 1 (AI/n8n bridge)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Industrial_Copilot backend...")
    
    # Subscribe AI orchestrator to all events
    event_bus.subscribe("*", orchestrator.handle_event)
    
    # Start IoT background simulator
    sim_task = asyncio.create_task(simulator.start())
    
    yield
    
    logger.info("Shutting down Industrial_Copilot...")
    simulator.stop()
    sim_task.cancel()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for competition demo convenience
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers under /api
app.include_router(sensors_router, prefix="/api")
app.include_router(machines_router, prefix="/api")
app.include_router(workers_router, prefix="/api")
app.include_router(incidents_router, prefix="/api")
app.include_router(actions_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(digital_twin_router, prefix="/api")
app.include_router(demo_router, prefix="/api")
app.include_router(general_router, prefix="/api")
app.include_router(n8n_bridge_router, prefix="/api")  # Engineer 1 (AI/n8n bridge)

# WebSocket Endpoint
@app.websocket("/ws/{channel}")
async def websocket_channel_endpoint(websocket: WebSocket, channel: str):
    await ws_manager.connect(websocket, channel)
    try:
        while True:
            # Keep connection open, receive any client messages or pings
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel)
    except Exception as e:
        logger.error(f"WebSocket error on channel {channel}: {e}")
        ws_manager.disconnect(websocket, channel)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket, "all")
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "all")
    except Exception as e:
        ws_manager.disconnect(websocket, "all")

@app.get("/")
def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "RUNNING",
        "docs_url": "/docs"
    }

@app.get("/health")
def health():
    return {"status": "HEALTHY"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.BACKEND_HOST, port=settings.BACKEND_PORT, reload=True)
