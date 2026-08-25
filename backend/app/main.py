"""
Punto de entrada de la aplicación FastAPI.

Para levantar en desarrollo:
    uvicorn app.main:app --reload

La documentación interactiva queda disponible en:
    http://localhost:8000/docs   (Swagger UI)
    http://localhost:8000/redoc  (ReDoc)
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.routers import auth, usuarios, academico, cursadas, eventos, chat, materiales, info_cursada

settings = get_settings()

# ── Rate limiter global ───────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

# ── Instancia de la app ───────────────────────────────────────────────────────
app = FastAPI(
    title="Asistente Universitario API",
    description=(
        "Backend del Asistente Universitario Inteligente y Seguro. "
        "Gestión académica + chatbot con RAG sobre datos de la institución."
    ),
    version="0.1.0",
    # En producción conviene deshabilitar la doc pública
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# ── Middlewares ───────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(auth.router,        prefix=API_PREFIX)
app.include_router(usuarios.router,    prefix=API_PREFIX)
app.include_router(academico.router,   prefix=API_PREFIX)
app.include_router(cursadas.router,    prefix=API_PREFIX)
app.include_router(eventos.router,     prefix=API_PREFIX)
app.include_router(chat.router,        prefix=API_PREFIX)
app.include_router(materiales.router,  prefix=API_PREFIX)
app.include_router(info_cursada.router, prefix=API_PREFIX)

# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Sistema"], include_in_schema=False)
def health_check():
    """Endpoint de salud para Docker y balanceadores de carga."""
    return {"status": "ok", "version": app.version}


# ── Handler global de errores no capturados ───────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # En producción no exponemos el traceback al cliente
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor"},
    )
