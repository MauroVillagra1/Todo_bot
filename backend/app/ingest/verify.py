"""
Creación de INFORMACIONES y estados de verificación (VER-01), por reglas.

Estado inicial según la confiabilidad de la fuente:
  >= 100 → CONFIRMADA   >= 80 → PROBABLE   resto → NO_CONFIRMADA
y DESACTUALIZADA cuando su vigencia (fecha_fin) ya pasó.

Vigencia (fecha_fin):
  1. La fecha más tardía mencionada en el texto, si hay.
  2. Si el título nombra un año anterior al de publicación ("Calendario 2025"
     publicado en 2026), el 31/12 de ese año.
  3. Si no, posts y archivos: 1 año desde la publicación. Páginas institucionales: sin vencimiento.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingest.classify import TIPOS_VALIDOS, anio_mencionado, clasificar, extraer_fechas
from app.ingest.extract import html_a_texto
from app.models.informacion import (
    EstadoInformacionEnum as E, Evidencia, Historial, Informacion, TipoInformacionEnum,
    Verificacion,
)
from app.models.ingesta import Documento, Fuente, Publicacion
from app.services.metricas import incrementar

VIGENCIA_SIN_FECHA = timedelta(days=365)
_ESTADOS_ACTIVOS = (E.CONFIRMADA, E.PROBABLE, E.NO_CONFIRMADA)


def estado_por_confiabilidad(confiabilidad: int) -> E:
    if confiabilidad >= 100:
        return E.CONFIRMADA
    if confiabilidad >= 80:
        return E.PROBABLE
    return E.NO_CONFIRMADA


def calcular_vigencia(
    titulo: str, texto: str, publicada: date, es_pagina: bool
) -> tuple[date | None, date | None, str]:
    """Devuelve (fecha_inicio, fecha_fin, explicación)."""
    inicio, fin = extraer_fechas(f"{titulo}\n{texto}", publicada)
    # Una página fija (inscripciones, contactos, avisos del SYSACAD) vale mientras siga
    # publicada: una fecha vieja en un párrafo no la vuelve desactualizada.
    if es_pagina:
        return inicio, None, "página institucional: vigente mientras esté publicada"
    if fin:
        return inicio, fin, f"vigente hasta {fin:%d/%m/%Y} según las fechas del texto"
    # El encabezado del texto también cuenta: un PDF "1-ANO-2023" dice "HORARIOS 2026"
    anio = anio_mencionado(f"{titulo}\n{texto[:200]}")
    if anio and anio < publicada.year:
        return None, date(anio, 12, 31), f"se refiere al año {anio}"
    return None, publicada + VIGENCIA_SIN_FECHA, "sin fechas en el texto: se asume 1 año desde la publicación"


def _clasificar_con_llm(titulo: str, texto: str) -> TipoInformacionEnum | None:
    """Solo para casos que ninguna regla resolvió. Respuesta validada contra la lista fija."""
    from app.services.llm import completar

    prompt = (
        f"Clasificá este aviso universitario en UNA de estas categorías: {', '.join(TIPOS_VALIDOS)}.\n"
        f"Respondé solo con la categoría.\n\nTítulo: {titulo}\nTexto: {texto[:600]}"
    )
    respuesta = completar([{"role": "user", "content": prompt}], max_tokens=10).strip().upper()
    return TipoInformacionEnum(respuesta) if respuesta in TIPOS_VALIDOS else None


@dataclass
class _Origen:
    """Publicación o documento pendiente, con lo que hace falta para verificarlo."""
    fuente_id: int
    titulo: str
    texto: str
    publicada: date
    es_pagina: bool
    evidencia: dict           # {"publicacion_id": …} o {"documento_id": …}
    version_anterior: object  # query de la INFORMACION de versiones anteriores


def _pendientes(db: Session) -> list[_Origen]:
    """Publicaciones y documentos vigentes que todavía no tienen evidencia."""
    origenes: list[_Origen] = []

    pubs = (
        db.query(Publicacion)
        .outerjoin(Evidencia, Evidencia.publicacion_id == Publicacion.id)
        .filter(Publicacion.vigente.is_(True), Evidencia.id.is_(None))
        .order_by(Publicacion.id)
        .all()
    )
    for p in pubs:
        anterior = (
            db.query(Informacion)
            .join(Evidencia, Evidencia.informacion_id == Informacion.id)
            .join(Publicacion, Publicacion.id == Evidencia.publicacion_id)
            .filter(Publicacion.fuente_id == p.fuente_id, Publicacion.id_externo == p.id_externo,
                    Publicacion.id != p.id)
        )
        origenes.append(_Origen(
            fuente_id=p.fuente_id,
            titulo=p.titulo or "(sin título)",
            texto=html_a_texto(p.contenido_original) or p.titulo or "",
            publicada=(p.fecha_publicacion or p.fecha_captura).date(),
            es_pagina=p.id_externo.startswith("pages:"),
            evidencia={"publicacion_id": p.id},
            version_anterior=anterior,
        ))

    docs = (
        db.query(Documento)
        .outerjoin(Evidencia, Evidencia.documento_id == Documento.id)
        .filter(Documento.vigente.is_(True), Evidencia.id.is_(None))
        .order_by(Documento.id)
        .all()
    )
    for d in docs:
        anterior = (
            db.query(Informacion)
            .join(Evidencia, Evidencia.informacion_id == Informacion.id)
            .join(Documento, Documento.id == Evidencia.documento_id)
            .filter(Documento.fuente_id == d.fuente_id, Documento.url == d.url, Documento.id != d.id)
        )
        origenes.append(_Origen(
            fuente_id=d.fuente_id,
            titulo=d.nombre or d.url.rsplit("/", 1)[-1],
            texto=d.texto_extraido or d.nombre or "",
            publicada=(d.fecha_publicacion or d.fecha_captura).date(),
            es_pagina=False,
            evidencia={"documento_id": d.id},
            version_anterior=anterior,
        ))
    return origenes


def procesar_pendientes(db: Session, hoy: date | None = None) -> dict:
    """
    Crea o actualiza la INFORMACION de cada publicación o documento vigente que
    todavía no tiene evidencia (nuevos o versiones nuevas). Idempotente: lo ya
    procesado no se vuelve a tocar.
    """
    hoy = hoy or date.today()
    llm_restantes = get_settings().CLASIFICACION_LLM_MAX_POR_CORRIDA
    resumen = {"creadas": 0, "actualizadas": 0, "llamadas_llm": 0}
    fuentes = {f.id: f for f in db.query(Fuente).all()}

    for i, o in enumerate(_pendientes(db), 1):
        fuente = fuentes[o.fuente_id]
        tipo, ambiguo = clasificar(o.titulo, o.texto)
        if ambiguo and llm_restantes > 0:
            llm_restantes -= 1
            resumen["llamadas_llm"] += 1
            try:
                tipo = _clasificar_con_llm(o.titulo, o.texto) or tipo
            except Exception:
                pass  # si el LLM falla queda OTRO

        inicio, fin, motivo_vigencia = calcular_vigencia(o.titulo, o.texto, o.publicada, o.es_pagina)
        estado = estado_por_confiabilidad(fuente.confiabilidad_base)
        explicacion = f"Fuente «{fuente.nombre}» (confiabilidad {fuente.confiabilidad_base}%); {motivo_vigencia}"
        if fin and fin < hoy:
            estado = E.DESACTUALIZADA
            explicacion += "; la vigencia ya pasó"

        # ¿Es una versión nueva de algo que ya teníamos?
        info = o.version_anterior.order_by(Informacion.id.desc()).first()
        if info:
            version = (db.query(func.max(Historial.version)).filter_by(informacion_id=info.id).scalar() or 0) + 1
            db.add(Historial(informacion_id=info.id, version=version, contenido_anterior=info.contenido,
                             contenido_nuevo=o.texto, motivo="Actualización en la fuente"))
            resumen["actualizadas"] += 1
        else:
            info = Informacion(tipo=tipo, titulo=o.titulo[:500], contenido=o.texto, estado=estado,
                               confianza=fuente.confiabilidad_base)
            db.add(info)
            db.flush()
            db.add(Historial(informacion_id=info.id, version=1, contenido_anterior=None,
                             contenido_nuevo=o.texto, motivo="Captura inicial"))
            resumen["creadas"] += 1

        info.tipo, info.titulo, info.contenido = tipo, o.titulo[:500], o.texto
        info.fecha_inicio, info.fecha_fin = inicio, fin
        info.estado, info.confianza = estado, fuente.confiabilidad_base
        db.add(Evidencia(informacion_id=info.id, fuente_id=fuente.id, **o.evidencia))
        db.add(Verificacion(informacion_id=info.id, resultado=estado,
                            puntuacion=fuente.confiabilidad_base, explicacion=explicacion))
        if i % 50 == 0:
            db.commit()

    incrementar(db, "llamadas_llm", resumen["llamadas_llm"])
    db.commit()
    return resumen


def actualizar_vigencias(db: Session, hoy: date | None = None) -> int:
    """Marca DESACTUALIZADA la información cuya vigencia venció desde la última corrida."""
    hoy = hoy or date.today()
    vencidas = (
        db.query(Informacion)
        .filter(Informacion.estado.in_(_ESTADOS_ACTIVOS), Informacion.fecha_fin < hoy)
        .all()
    )
    for info in vencidas:
        info.estado = E.DESACTUALIZADA
        db.add(Verificacion(informacion_id=info.id, resultado=E.DESACTUALIZADA,
                            puntuacion=info.confianza,
                            explicacion=f"Vigencia vencida el {info.fecha_fin:%d/%m/%Y}"))
    db.commit()
    return len(vencidas)
