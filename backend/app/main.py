import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
from app.api.auth import (  # authentication
    router as auth_router, decode_token, service_token_ok, token_from_request,
)

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
app.include_router(auth_router, prefix="/api")  # authentication


# ---------------------------------------------------------------------------------------
# Nobody reaches the platform without signing in.
#
# Open without a token: the health probe, the API docs, and /api/auth/* (those endpoints do
# their own checking, and logout must work even with an expired token).
#
# Machine-to-machine: /api/ai/n8n/* is called by n8n, which has no user session, so it
# presents a shared secret header instead — see n8n/README.md.
# ---------------------------------------------------------------------------------------
PUBLIC_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}
SERVICE_PREFIX = "/api/ai/n8n"


@app.middleware("http")
async def require_authentication(request, call_next):
    path = request.url.path

    if request.method == "OPTIONS" or not path.startswith("/api") or path in PUBLIC_PATHS:
        return await call_next(request)
    if path.startswith("/api/auth"):
        return await call_next(request)

    if path.startswith(SERVICE_PREFIX):
        # Header is the normal form. The query parameter exists because n8n's AI *tool* node
        # exposes query parameters far more simply than headers, and the value is a shared
        # service secret on a localhost hop, not a user credential.
        provided = (request.headers.get("x-copilot-service-token")
                    or request.query_params.get("service_token"))
        # Either the machine secret (n8n) or a signed-in user (so an owner can inspect the
        # bridge from the dashboard or a script without holding the service secret).
        if service_token_ok(provided) or decode_token(token_from_request(request) or ""):
            return await call_next(request)
        return JSONResponse(
            {"detail": "Invalid or missing service token for the n8n bridge"}, status_code=401)

    if decode_token(token_from_request(request) or ""):
        return await call_next(request)
    return JSONResponse({"detail": "Not authenticated"}, status_code=401)

# WebSocket Endpoint
def _websocket_authorised(websocket: WebSocket) -> bool:
    """A browser cannot set an Authorization header on a WebSocket, so the token comes as
    `?token=...`. A first-message handshake would also work; the query parameter keeps the
    frontend simple and the token never leaves the same origin."""
    return bool(decode_token(websocket.query_params.get("token") or ""))


@app.websocket("/ws/{channel}")
async def websocket_channel_endpoint(websocket: WebSocket, channel: str):
    if not _websocket_authorised(websocket):
        await websocket.close(code=1008)   # policy violation
        return
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
    if not _websocket_authorised(websocket):
        await websocket.close(code=1008)
        return
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
