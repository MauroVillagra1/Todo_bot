"""
Router de administración (solo ADMIN).
  GET /api/v1/admin/diagnostico → estado de la configuración de IA en este
      despliegue. Nunca devuelve la API key, solo si está configurada.
"""
from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.dependencies import require_admin
from app.services import llm

router = APIRouter(prefix="/admin", tags=["Administración"])


@router.get("/diagnostico")
def diagnostico(_admin=Depends(require_admin)):
    settings = get_settings()
    resultado = {
        "entorno": settings.ENVIRONMENT,
        "openrouter_key_configurada": bool(settings.OPENROUTER_API_KEY.strip()),
        "ai_model": settings.AI_MODEL,
        "modelos_respaldo": settings.AI_MODELOS_RESPALDO,
    }
    try:
        # Prueba mínima (unos pocos tokens de un modelo gratuito)
        resultado["prueba_llm"] = "ok: " + llm.completar([{"role": "user", "content": "Respondé solo: ok"}], max_tokens=5)
    except Exception as e:
        resultado["prueba_llm"] = f"error: {str(e)[:600]}"
    return resultado
