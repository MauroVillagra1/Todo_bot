"""
Router de administración.
  GET /api/v1/admin/resumen      → panel (ADM-01) + métricas (OBS-01). MOD y ADMIN.
  GET /api/v1/admin/diagnostico  → estado de la configuración de IA en este
      despliegue. Solo ADMIN. Nunca devuelve la API key, solo si está configurada.
"""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import require_admin, require_mod
from app.models.informacion import EstadoInformacionEnum as E, Informacion
from app.models.ingesta import Documento, EstadoIngestaEnum, Fuente, Ingesta, Publicacion
from app.models.metrica import MetricaDiaria
from app.models.usuario import Usuario
from app.services import llm

router = APIRouter(prefix="/admin", tags=["Administración"])

DIAS_METRICAS = 14


@router.get("/resumen")
def resumen(db: Session = Depends(get_db), _mod=Depends(require_mod)):
    hace_7_dias = datetime.now(timezone.utc) - timedelta(days=7)
    desde_metricas = date.today() - timedelta(days=DIAS_METRICAS - 1)

    estados = dict(db.query(Informacion.estado, func.count()).group_by(Informacion.estado).all())

    # Última corrida de cada fuente: estado del sistema de un vistazo
    ultimas = (
        db.query(Ingesta)
        .filter(Ingesta.id.in_(db.query(func.max(Ingesta.id)).group_by(Ingesta.fuente_id)))
        .all()
    )
    nombres = dict(db.query(Fuente.id, Fuente.nombre).all())
    errores_recientes = [
        {"fuente": nombres.get(i.fuente_id), "inicio": i.inicio, "detalle": i.detalle_errores[:3]}
        for i in db.query(Ingesta)
        .filter(Ingesta.errores > 0, Ingesta.inicio >= hace_7_dias)
        .order_by(Ingesta.id.desc())
        .limit(5)
    ]

    metricas: dict[str, dict[str, int]] = {}
    for m in db.query(MetricaDiaria).filter(MetricaDiaria.dia >= desde_metricas):
        metricas.setdefault(m.metrica, {})[m.dia.isoformat()] = m.valor

    return {
        "fuentes": {
            "total": db.query(Fuente).count(),
            "activas": db.query(Fuente).filter(Fuente.activa.is_(True)).count(),
            "ultima_actualizacion": db.query(func.max(Fuente.ultima_revision)).scalar(),
        },
        "documentos_procesados": {
            "publicaciones": db.query(Publicacion).filter(Publicacion.vigente.is_(True)).count(),
            "pdfs": db.query(Documento).filter(Documento.vigente.is_(True)).count(),
        },
        "informacion": {
            "total": sum(estados.values()),
            "nueva_ultimos_7_dias": db.query(Informacion).filter(Informacion.created_at >= hace_7_dias).count(),
            "por_estado": {e.value: estados.get(e, 0) for e in E},
            "no_confirmada": estados.get(E.NO_CONFIRMADA, 0),
            "contradicciones": estados.get(E.CONTRADICTORIA, 0),
        },
        "ingesta": {
            "ultimas_corridas": [
                {"fuente": nombres.get(i.fuente_id), "estado": i.estado.value, "inicio": i.inicio,
                 "nuevos": i.nuevos, "errores": i.errores}
                for i in sorted(ultimas, key=lambda i: i.fuente_id)
            ],
            "con_error": sum(1 for i in ultimas if i.estado == EstadoIngestaEnum.ERROR),
            "errores_ultimos_7_dias": errores_recientes,
        },
        "usuarios": {
            "total": db.query(Usuario).count(),
            "activos": db.query(Usuario).filter(Usuario.activo.is_(True)).count(),
        },
        # {metrica: {dia: valor}} de los últimos DIAS_METRICAS días
        "metricas": metricas,
    }


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
