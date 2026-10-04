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

from app.core.config import get_settings
from app.routers import admin, auth, usuarios, chat, fuentes, horarios, sugerencias, webhooks

settings = get_settings()

# ── Instancia de la app ───────────────────────────────────────────────────────
app = FastAPI(
    title="Asistente Universitario API",
    description=(
        "Backend de la Plataforma de Información Universitaria UTN FRT. "
        "Chatbot con RAG sobre información institucional verificada."
    ),
    version="0.1.0",
    # En producción conviene deshabilitar la doc pública
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# ── Middlewares ───────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(auth.router,     prefix=API_PREFIX)
app.include_router(usuarios.router, prefix=API_PREFIX)
app.include_router(chat.router,     prefix=API_PREFIX)
app.include_router(fuentes.router,  prefix=API_PREFIX)
app.include_router(admin.router,    prefix=API_PREFIX)
app.include_router(sugerencias.router, prefix=API_PREFIX)
app.include_router(horarios.router, prefix=API_PREFIX)
app.include_router(webhooks.router, prefix=API_PREFIX)

# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Sistema"], include_in_schema=False)
def health_check():
    """Endpoint de salud para Docker y balanceadores de carga."""
    return {"status": "ok", "version": app.version}


# ── Handler global de errores no capturados ───────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    origin = request.headers.get("origin", "")
    headers = {}
    if origin in settings.CORS_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor"},
        headers=headers,
    )
