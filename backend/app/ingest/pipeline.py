"""
Pipeline de ingesta (flujo del análisis MVP §9, pasos 1-6 y 10).
Clasificación (etapa 5) y embeddings (etapa 7) se suman después.

Garantía clave: re-ejecutar sin cambios en la fuente no crea nada nuevo,
no llama al LLM y no genera embeddings.
"""
from datetime import timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ingest.chunk import dividir
from app.ingest.extract import hash_texto, html_a_texto
from app.ingest.sources import ItemCrudo, Source, obtener_adaptador
from app.models.ingesta import Chunk, EstadoIngestaEnum, Fuente, Ingesta, Publicacion
from app.services.metricas import incrementar

# Se vuelve a pedir un poco antes de la última revisión por si algo se
# publicó justo durante la corrida anterior; lo repetido se descarta por hash.
MARGEN = timedelta(minutes=5)

NUEVO, ACTUALIZADO, DUPLICADO = "nuevo", "actualizado", "duplicado"


def guardar_publicacion(db: Session, fuente: Fuente, item: ItemCrudo) -> str:
    """Guarda una versión nueva si el contenido cambió. Devuelve qué pasó."""
    texto = html_a_texto(item.contenido_html)
    h = hash_texto(f"{item.titulo}\n{texto}")

    base = db.query(Publicacion).filter(
        Publicacion.fuente_id == fuente.id, Publicacion.id_externo == item.id_externo
    )
    if base.filter(Publicacion.hash == h).first():
        return DUPLICADO  # esta versión exacta ya está guardada

    anteriores = base.filter(Publicacion.vigente.is_(True)).all()
    for anterior in anteriores:
        anterior.vigente = False  # no se borra: queda el historial

    pub = Publicacion(
        fuente_id=fuente.id,
        id_externo=item.id_externo,
        url=item.url,
        titulo=item.titulo[:500],
        contenido_original=item.contenido_html,
        fecha_publicacion=item.fecha_publicacion,
        fecha_modificacion=item.fecha_modificacion,
        hash=h,
    )
    db.add(pub)
    db.flush()
    for orden, trozo in enumerate(dividir(item.titulo, texto)):
        db.add(Chunk(publicacion_id=pub.id, orden=orden, texto=trozo, hash=hash_texto(trozo)))
    return ACTUALIZADO if anteriores else NUEVO


def procesar_fuente(db: Session, fuente: Fuente, adaptador: Source | None = None) -> Ingesta:
    adaptador = adaptador or obtener_adaptador(fuente)
    ingesta = Ingesta(fuente_id=fuente.id, detalle_errores=[])
    db.add(ingesta)
    db.commit()

    ultima_vista = fuente.ultima_revision
    if ultima_vista and ultima_vista.tzinfo is None:  # algunos drivers la devuelven sin zona
        ultima_vista = ultima_vista.replace(tzinfo=timezone.utc)
    desde = ultima_vista - MARGEN if ultima_vista else None
    errores: list[dict] = []
    # Contadores en variables locales: un rollback por ítem fallido no los pierde
    nuevos = actualizados = duplicados = 0
    estado = EstadoIngestaEnum.OK

    try:
        for item in adaptador.obtener_cambios(desde):
            try:
                resultado = guardar_publicacion(db, fuente, item)
                db.commit()  # por ítem: si el proceso muere, lo ya guardado queda
            except Exception as e:
                db.rollback()
                errores.append({"item": item.id_externo, "error": str(e)[:300]})
                continue

            if resultado == DUPLICADO:
                duplicados += 1
            else:
                nuevos += 1
                actualizados += resultado == ACTUALIZADO
            # Se usa la fecha de la fuente, no el reloj local (puede estar desfasado)
            if item.fecha_modificacion and (ultima_vista is None or item.fecha_modificacion > ultima_vista):
                ultima_vista = item.fecha_modificacion
    except Exception as e:  # la fuente no respondió o devolvió algo inválido
        db.rollback()
        errores.append({"item": None, "error": str(e)[:300]})
        estado = EstadoIngestaEnum.ERROR

    # Si algo falló no se avanza la marca: la próxima corrida lo reintenta
    # (lo que ya estaba guardado se descarta barato por hash).
    if not errores:
        fuente.ultima_revision = ultima_vista
    ingesta.estado = estado
    ingesta.nuevos = nuevos
    ingesta.duplicados = duplicados
    ingesta.errores = len(errores)
    ingesta.detalle_errores = errores
    ingesta.fin = func.now()

    incrementar(db, "documentos_procesados", nuevos)
    incrementar(db, "documentos_actualizados", actualizados)
    incrementar(db, "duplicados_descartados", duplicados)
    incrementar(db, "errores_ingesta", len(errores))
    db.commit()
    return ingesta


def procesar_fuentes_activas(db: Session, nombre: str | None = None) -> list[Ingesta]:
    consulta = db.query(Fuente).filter(Fuente.activa.is_(True))
    if nombre:
        consulta = consulta.filter(Fuente.nombre == nombre)
    return [procesar_fuente(db, fuente) for fuente in consulta.order_by(Fuente.id).all()]
