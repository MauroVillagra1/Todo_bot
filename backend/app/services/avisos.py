"""Paros cargados por moderadores (publicaciones "paro:…"): para el banner del chat y "¿hay clases mañana?"."""
from datetime import date

from sqlalchemy.orm import Session

from app.models.informacion import EstadoInformacionEnum as E, Evidencia, Informacion
from app.models.ingesta import Publicacion

PREFIJO_PARO = "paro:"
_ACTIVOS = (E.CONFIRMADA, E.PROBABLE, E.NO_CONFIRMADA)


def paros(db: Session, desde: date, hasta: date | None = None) -> list[Informacion]:
    """Paros vigentes que tocan el rango [desde, hasta] (sin hasta: de desde en adelante)."""
    consulta = (
        db.query(Informacion)
        .join(Evidencia, Evidencia.informacion_id == Informacion.id)
        .join(Publicacion, Publicacion.id == Evidencia.publicacion_id)
        .filter(Publicacion.id_externo.like(f"{PREFIJO_PARO}%"), Publicacion.vigente.is_(True),
                Informacion.estado.in_(_ACTIVOS), Informacion.fecha_fin >= desde)
    )
    if hasta:
        consulta = consulta.filter(Informacion.fecha_inicio <= hasta)
    return consulta.order_by(Informacion.fecha_inicio, Informacion.id).distinct().all()


def todos_los_paros(db: Session, limite: int = 200) -> list[Informacion]:
    """Paros cargados que no se dieron de baja (pasados y próximos), del más nuevo al más viejo."""
    return (
        db.query(Informacion)
        .join(Evidencia, Evidencia.informacion_id == Informacion.id)
        .join(Publicacion, Publicacion.id == Evidencia.publicacion_id)
        .filter(Publicacion.id_externo.like(f"{PREFIJO_PARO}%"), Publicacion.vigente.is_(True),
                Informacion.estado != E.REEMPLAZADA)
        .order_by(Informacion.fecha_inicio.desc(), Informacion.id.desc()).distinct().limit(limite).all()
    )
