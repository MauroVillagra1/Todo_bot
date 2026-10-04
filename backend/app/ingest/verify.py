"""
Creación de INFORMACIONES y estados de verificación (VER-01), por reglas.

Estado inicial según la confiabilidad de la fuente:
  >= 100 → CONFIRMADA   >= 80 → PROBABLE   resto → NO_CONFIRMADA
y DESACTUALIZADA cuando su vigencia (fecha_fin) ya pasó.

Vigencia (fecha_fin):
  1. La fecha más tardía mencionada en el texto, si hay.
  2. Si el título nombra un año anterior al de publicación ("Calendario 2025"
     publicado en 2026), el 31/12 de ese año.
  3. Si no, posts: 1 año desde la publicación. Páginas institucionales: sin vencimiento.
"""
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingest.classify import TIPOS_VALIDOS, anio_mencionado, clasificar, extraer_fechas
from app.ingest.extract import html_a_texto
from app.models.informacion import (
    EstadoInformacionEnum as E, Evidencia, Historial, Informacion, TipoInformacionEnum,
    Verificacion,
)
from app.models.ingesta import Fuente, Publicacion
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
    if fin:
        return inicio, fin, f"vigente hasta {fin:%d/%m/%Y} según las fechas del texto"
    anio = anio_mencionado(titulo)
    if anio and anio < publicada.year:
        return None, date(anio, 12, 31), f"el título se refiere al año {anio}"
    if es_pagina:
        return None, None, "página institucional sin vencimiento"
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


def procesar_pendientes(db: Session, hoy: date | None = None) -> dict:
    """
    Crea o actualiza la INFORMACION de cada publicación vigente que todavía no
    tiene evidencia (nuevas o versiones nuevas). Idempotente: lo ya procesado
    no se vuelve a tocar.
    """
    hoy = hoy or date.today()
    llm_restantes = get_settings().CLASIFICACION_LLM_MAX_POR_CORRIDA
    resumen = {"creadas": 0, "actualizadas": 0, "llamadas_llm": 0}

    pendientes = (
        db.query(Publicacion)
        .outerjoin(Evidencia, Evidencia.publicacion_id == Publicacion.id)
        .filter(Publicacion.vigente.is_(True), Evidencia.id.is_(None))
        .order_by(Publicacion.id)
        .all()
    )
    fuentes = {f.id: f for f in db.query(Fuente).all()}

    for i, pub in enumerate(pendientes, 1):
        fuente = fuentes[pub.fuente_id]
        texto = html_a_texto(pub.contenido_original) or pub.titulo or ""
        titulo = pub.titulo or "(sin título)"

        tipo, ambiguo = clasificar(titulo, texto)
        if ambiguo and llm_restantes > 0:
            llm_restantes -= 1
            resumen["llamadas_llm"] += 1
            try:
                tipo = _clasificar_con_llm(titulo, texto) or tipo
            except Exception:
                pass  # si el LLM falla queda OTRO

        publicada = (pub.fecha_publicacion or pub.fecha_captura).date()
        inicio, fin, motivo_vigencia = calcular_vigencia(
            titulo, texto, publicada, es_pagina=pub.id_externo.startswith("pages:")
        )
        estado = estado_por_confiabilidad(fuente.confiabilidad_base)
        explicacion = f"Fuente «{fuente.nombre}» (confiabilidad {fuente.confiabilidad_base}%); {motivo_vigencia}"
        if fin and fin < hoy:
            estado = E.DESACTUALIZADA
            explicacion += "; la vigencia ya pasó"

        # ¿Es una versión nueva de algo que ya teníamos?
        info = (
            db.query(Informacion)
            .join(Evidencia, Evidencia.informacion_id == Informacion.id)
            .join(Publicacion, Publicacion.id == Evidencia.publicacion_id)
            .filter(
                Publicacion.fuente_id == pub.fuente_id,
                Publicacion.id_externo == pub.id_externo,
                Publicacion.id != pub.id,
            )
            .order_by(Informacion.id.desc())
            .first()
        )
        if info:
            version = (db.query(func.max(Historial.version)).filter_by(informacion_id=info.id).scalar() or 0) + 1
            db.add(Historial(informacion_id=info.id, version=version, contenido_anterior=info.contenido,
                             contenido_nuevo=texto, motivo="Actualización en la fuente"))
            resumen["actualizadas"] += 1
        else:
            info = Informacion(tipo=tipo, titulo=titulo[:500], contenido=texto, estado=estado,
                               confianza=fuente.confiabilidad_base)
            db.add(info)
            db.flush()
            db.add(Historial(informacion_id=info.id, version=1, contenido_anterior=None,
                             contenido_nuevo=texto, motivo="Captura inicial"))
            resumen["creadas"] += 1

        info.tipo, info.titulo, info.contenido = tipo, titulo[:500], texto
        info.fecha_inicio, info.fecha_fin = inicio, fin
        info.estado, info.confianza = estado, fuente.confiabilidad_base
        db.add(Evidencia(informacion_id=info.id, fuente_id=fuente.id, publicacion_id=pub.id))
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
