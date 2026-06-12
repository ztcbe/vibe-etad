"""zvibe main app — API routes + frontend static served on single port."""
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_current_user_ws
from common.errors import AppError
from common.logging import setup_logging
from db.session import get_session
from db.models.user import User


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


app = FastAPI(title="zvibe", version="0.1.0", lifespan=lifespan)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Media uploads ──
import pathlib
upload_dir = pathlib.Path(settings.MEDIA_UPLOAD_DIR)
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media/uploads", StaticFiles(directory=str(upload_dir)), name="media-uploads")

# ── API Routers (registered FIRST — take priority over static mount) ──
from modules.auth.router import router as auth_router
from modules.profiles.router import router as profile_router
from modules.media.router import router as media_router
from modules.assistant.router import router as assistant_router
from modules.matching.router import router as matching_router
from modules.chat.router import router as chat_router
from modules.admin.router import router as admin_router

app.include_router(auth_router, prefix="/api")
app.include_router(profile_router, prefix="/api")
app.include_router(media_router, prefix="/api")
app.include_router(assistant_router, prefix="/api")
app.include_router(matching_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(admin_router, prefix="/api")

# ── WebSocket ──
from modules.chat.websocket import chat_websocket


@app.websocket("/ws/chats/{match_id}")
async def ws_chat(
    websocket: WebSocket,
    match_id: uuid.UUID,
    user: User = Depends(get_current_user_ws),
    db: AsyncSession = Depends(get_session),
):
    await chat_websocket(websocket, match_id, user, db)


# ── Health check ──
@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Error handler ──
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "error": {"code": exc.code, "message": exc.message, "details": exc.details},
            "meta": {},
        },
    )


# ── Frontend static (MOUNT LAST — only catches non-API paths) ──
frontend_dir = pathlib.Path(__file__).parent.parent.parent / "frontend"
if frontend_dir.exists():
    # Mount CSS, JS, assets
    app.mount("/css", StaticFiles(directory=str(frontend_dir / "css")), name="frontend-css")
    app.mount("/js", StaticFiles(directory=str(frontend_dir / "js")), name="frontend-js")
    app.mount("/assets", StaticFiles(directory=str(frontend_dir / "assets")), name="frontend-assets")
    # Serve index.html for all other non-API routes (SPA fallback)
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
