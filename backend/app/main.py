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
from app.routers import (
    admin, auth, calendario, chat, documentos, fuentes, historial, horarios, importar, informacion, mesas, reportes,
    sugerencias, usuarios, webhooks,
)

settings = get_settings()
API_PREFIX = "/api/v1"

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
    # Sin esto el esquema con todos los endpoints quedaba público aunque /docs no
    openapi_url="/openapi.json" if settings.is_development else None,
)

# ── Middlewares ───────────────────────────────────────────────────────────────
# La sesión viaja en el header Authorization (no en cookies): sin credenciales de navegador
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

ENCABEZADOS_DE_SEGURIDAD = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


@app.middleware("http")
async def encabezados_de_seguridad(request: Request, call_next):
    respuesta = await call_next(request)
    for nombre, valor in ENCABEZADOS_DE_SEGURIDAD.items():
        respuesta.headers.setdefault(nombre, valor)
    if not settings.is_development:  # en desarrollo /docs carga scripts de un CDN
        respuesta.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    # Tokens y datos de la cuenta: que ningún proxy ni el navegador los guarden
    if request.url.path.startswith(f"{API_PREFIX}/auth"):
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth.router,     prefix=API_PREFIX)
app.include_router(usuarios.router, prefix=API_PREFIX)
app.include_router(chat.router,     prefix=API_PREFIX)
app.include_router(fuentes.router,  prefix=API_PREFIX)
app.include_router(informacion.router, prefix=API_PREFIX)
app.include_router(mesas.router, prefix=API_PREFIX)
app.include_router(calendario.router, prefix=API_PREFIX)
app.include_router(documentos.router, prefix=API_PREFIX)
app.include_router(admin.router,    prefix=API_PREFIX)
app.include_router(sugerencias.router, prefix=API_PREFIX)
app.include_router(horarios.router, prefix=API_PREFIX)
app.include_router(reportes.router, prefix=API_PREFIX)
app.include_router(historial.router, prefix=API_PREFIX)
app.include_router(importar.router, prefix=API_PREFIX)
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

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor"},
        headers=headers,
    )
