"""
Router de reportes de usuarios (MOD y ADMIN): respuestas votadas como "dato incorrecto".
  GET  /api/v1/reportes                 → pendientes, con la pregunta, la respuesta y las fuentes
  POST /api/v1/reportes/{id}/resolver   → "ocultar": las informaciones elegidas dejan de usarse
                                          en el chat (DESACTUALIZADA, con su verificación);
                                          "descartar": el reporte no corresponde
  GET  /api/v1/reportes/resumen         → 👍 / 👎 totales y reportes pendientes
"""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_mod
from app.models.cache import CacheRespuesta
from app.models.chat import MensajeChat
from app.models.informacion import EstadoInformacionEnum as E, Evidencia, Informacion, Verificacion
from app.models.ingesta import Documento, Publicacion
from app.models.usuario import Usuario
from app.models.voto import MotivoVotoEnum, Voto

router = APIRouter(prefix="/reportes", tags=["Reportes"])


class InformacionReportada(BaseModel):
    id: int
    titulo: str
    url: str | None
    estado: str
    reportes: int  # cuántos "incorrecto" pendientes la incluyen
    puntaje_votos: int


class ReporteRead(BaseModel):
    id: int
    autor: str
    comentario: str | None
    creado_en: datetime
    pregunta: str | None
    respuesta: str
    informaciones: list[InformacionReportada]


class Resolucion(BaseModel):
    accion: Literal["ocultar", "descartar"]
    informacion_ids: list[int] = []  # para "ocultar"
    nota: str = Field(default="", max_length=250)


def _url(db: Session, informacion_id: int) -> str | None:
    fila = (
        db.query(Publicacion.url, Documento.url)
        .select_from(Evidencia)
        .outerjoin(Publicacion, Publicacion.id == Evidencia.publicacion_id)
        .outerjoin(Documento, Documento.id == Evidencia.documento_id)
        .filter(Evidencia.informacion_id == informacion_id)
        .first()
    )
    return (fila[0] or fila[1]) if fila else None


@router.get("/", response_model=list[ReporteRead])
def listar_reportes(db: Session = Depends(get_db), _mod=Depends(require_mod)):
    votos = (
        db.query(Voto, MensajeChat, Usuario)
        .join(MensajeChat, MensajeChat.id == Voto.mensaje_id)
        .join(Usuario, Usuario.id == Voto.usuario_id)
        .filter(Voto.motivo == MotivoVotoEnum.INCORRECTO, Voto.revisado.is_(False))
        .order_by(Voto.id)
        .limit(50)
        .all()
    )
    # Cuántos reportes pendientes tiene cada información (para priorizar)
    conteo: dict[int, int] = {}
    for _, m, _ in votos:
        for i in m.informacion_ids or []:
            conteo[i] = conteo.get(i, 0) + 1
    salida = []
    for v, m, u in votos:
        pregunta = (
            db.query(MensajeChat.contenido)
            .filter(MensajeChat.conversacion_id == m.conversacion_id, MensajeChat.rol == "user",
                    MensajeChat.id < m.id)
            .order_by(MensajeChat.id.desc())
            .scalar()
        )
        infos = db.query(Informacion).filter(Informacion.id.in_(m.informacion_ids or [])).all()
        salida.append(ReporteRead(
            id=v.id, autor=f"{u.nombre} ({u.email})", comentario=v.comentario, creado_en=v.creado_en,
            pregunta=pregunta, respuesta=m.contenido,
            informaciones=[InformacionReportada(id=i.id, titulo=i.titulo, url=_url(db, i.id), estado=i.estado.value,
                                                reportes=conteo.get(i.id, 0), puntaje_votos=i.puntaje_votos)
                           for i in infos],
        ))
    return salida


@router.post("/{voto_id}/resolver", status_code=status.HTTP_204_NO_CONTENT)
def resolver_reporte(voto_id: int, datos: Resolucion, db: Session = Depends(get_db), mod=Depends(require_mod)):
    voto = db.get(Voto, voto_id)
    if not voto or voto.motivo != MotivoVotoEnum.INCORRECTO:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reporte no encontrado")
    if voto.revisado:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El reporte ya fue revisado")
    nota = datos.nota.strip()
    if datos.accion == "ocultar":
        permitidas = set(db.get(MensajeChat, voto.mensaje_id).informacion_ids or [])
        elegidas = [i for i in datos.informacion_ids if i in permitidas]
        if not elegidas:
            raise HTTPException(status_code=422, detail="Elegí qué información sacar del chat")
        for info in db.query(Informacion).filter(Informacion.id.in_(elegidas)):
            info.estado = E.DESACTUALIZADA
            db.add(Verificacion(
                informacion_id=info.id, resultado=E.DESACTUALIZADA, puntuacion=info.confianza,
                explicacion=f"Reportada como incorrecta por usuarios; revisada por {mod.nombre}"
                            + (f": {nota}" if nota else ""),
            ))
        db.query(CacheRespuesta).delete()  # que el chat deje de usarla ya
        voto.resolucion = f"Ocultadas: {', '.join(map(str, elegidas))}" + (f". {nota}" if nota else "")
    else:
        voto.resolucion = "Descartado" + (f": {nota}" if nota else "")
    voto.revisado, voto.revisor_id = True, mod.id
    db.commit()


@router.get("/resumen")
def resumen_votos(db: Session = Depends(get_db), _mod=Depends(require_mod)):
    filas = dict(db.query(Voto.valor, func.count()).group_by(Voto.valor).all())
    pendientes = (db.query(Voto)
                  .filter(Voto.motivo == MotivoVotoEnum.INCORRECTO, Voto.revisado.is_(False)).count())
    return {"positivos": filas.get(1, 0), "negativos": filas.get(-1, 0), "reportes_pendientes": pendientes}
