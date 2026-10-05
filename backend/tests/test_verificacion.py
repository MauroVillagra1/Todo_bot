"""Clasificación por reglas, fechas y estados de verificación (etapa 5)."""
from datetime import date, datetime, timezone

import pytest

from app.ingest.classify import clasificar, extraer_fechas
from app.ingest.verify import actualizar_vigencias, calcular_vigencia, procesar_pendientes
from app.models.informacion import (
    EstadoInformacionEnum as E, Evidencia, Historial, Informacion, TipoInformacionEnum as T,
    Verificacion,
)
from app.models.ingesta import Chunk, Documento, Fuente, Publicacion, TipoFuenteEnum
from app.models.metrica import MetricaDiaria

PUB = date(2026, 9, 1)


# ── Clasificación ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("titulo,esperado", [
    ("BECAS GCUB", T.BECA),
    ("¡Convocatoria Abierta! Becas de grado Stipendium Hungaricum", T.BECA),  # empate → BECA
    ("RECUPERACIÓN – ANÁLISIS DE SISTEMAS DE INFORMACIÓN", T.EXAMEN),
    ("Inscripción habilitada – Ingeniería en Sistemas de Información", T.INSCRIPCION),
    ("Calendario Académico 2026 – Facultad Regional Tucumán", T.CALENDARIO),
    ("Horario PROVISORIO – Segundo Cuatrimestre 2026", T.CALENDARIO),
    ("¡Oportunidad de Pasantía en SAT – Aguas del Tucumán!", T.CONVOCATORIA),
    ("Charla de Concientización sobre Grooming", T.EVENTO),
    ("Atención estudiantes – Algoritmos y Estructuras de Datos", T.AVISO),
    ("Entrevista a María Sofía Medina: Historias que Inspiran", T.NOTICIA),
])
def test_clasifica_titulos_reales_de_sistemas_frt(titulo, esperado):
    tipo, ambiguo = clasificar(titulo, "")
    assert (tipo, ambiguo) == (esperado, False)


def test_sin_coincidencias_es_otro_y_ambiguo():
    assert clasificar("Memoria en hilo y voces", "Un recorrido fotográfico.") == (T.OTRO, True)


def test_no_confunde_palabras_parciales():
    # "finalmente" no es "final"; "becario" no es "beca"
    assert clasificar("Finalmente llegó", "El becario habló")[0] == T.OTRO


# ── Fechas ────────────────────────────────────────────────────────────────────

def test_extrae_fechas_numericas_y_textuales():
    texto = "Inscripción del 10 al 15 de septiembre. Cierre definitivo 29/09/2026."
    assert extraer_fechas(texto, PUB) == (date(2026, 9, 10), date(2026, 9, 29))


def test_fecha_sin_anio_usa_el_de_publicacion():
    assert extraer_fechas("La mesa es el 3 de octubre", PUB) == (date(2026, 10, 3), date(2026, 10, 3))


def test_descarta_fechas_implausibles_y_horas():
    texto = "Fundada el 12/08/1952. Horario 18.30 a 20.00. Resolución 1/2."
    assert extraer_fechas(texto, PUB) == (None, None)


def test_vigencia_por_anio_en_titulo_y_paginas():
    assert calcular_vigencia("Calendario Académico 2025", "", date(2026, 2, 28), False)[1] == date(2025, 12, 31)
    assert calcular_vigencia("Autoridades", "texto", PUB, es_pagina=True)[1] is None
    assert calcular_vigencia("Aviso", "texto", PUB, es_pagina=False)[1] == date(2027, 9, 1)


# ── Informaciones ─────────────────────────────────────────────────────────────

@pytest.fixture
def tablas(db):
    engine = db.get_bind()
    for m in (Fuente, Documento, Publicacion, Chunk, MetricaDiaria,
              Informacion, Evidencia, Verificacion, Historial):
        m.__table__.create(engine)
    return db


def _fuente(db, confiabilidad):
    f = Fuente(nombre=f"F{confiabilidad}", tipo=TipoFuenteEnum.WORDPRESS, url="https://x",
               confiabilidad_base=confiabilidad, activa=True, config={})
    db.add(f)
    db.commit()
    return f


def _pub(db, fuente, id_ext, titulo, html, vigente=True):
    p = Publicacion(fuente_id=fuente.id, id_externo=id_ext, url="https://x/" + id_ext, titulo=titulo,
                    contenido_original=html, hash=f"{id_ext}{html}"[:64].ljust(64, "0"),
                    fecha_publicacion=datetime(2026, 9, 1, tzinfo=timezone.utc), vigente=vigente)
    db.add(p)
    db.commit()
    return p


@pytest.mark.parametrize("confiabilidad,estado", [(100, E.CONFIRMADA), (90, E.PROBABLE), (50, E.NO_CONFIRMADA)])
def test_estado_inicial_segun_confiabilidad(tablas, confiabilidad, estado):
    db = tablas
    _pub(db, _fuente(db, confiabilidad), "posts:1", "Mesas de examen", "<p>Mesa el 3 de octubre</p>")
    procesar_pendientes(db, hoy=date(2026, 9, 2))

    info = db.query(Informacion).one()
    assert (info.estado, info.tipo, info.fecha_fin) == (estado, T.EXAMEN, date(2026, 10, 3))
    assert db.query(Evidencia).one().publicacion_id is not None
    assert db.query(Verificacion).one().resultado == estado


def test_procesar_pendientes_es_idempotente(tablas):
    db = tablas
    _pub(db, _fuente(db, 100), "posts:1", "Becas", "<p>Becas 2026</p>")
    assert procesar_pendientes(db, hoy=PUB)["creadas"] == 1
    assert procesar_pendientes(db, hoy=PUB) == {"creadas": 0, "actualizadas": 0, "llamadas_llm": 0}


def test_version_nueva_actualiza_la_misma_informacion_con_historial(tablas):
    db = tablas
    fuente = _fuente(db, 100)
    vieja = _pub(db, fuente, "posts:1", "Mesas de examen", "<p>Mesa el 3 de octubre</p>")
    procesar_pendientes(db, hoy=PUB)

    vieja.vigente = False
    _pub(db, fuente, "posts:1", "Mesas de examen", "<p>Mesa el 10 de octubre</p>")
    r = procesar_pendientes(db, hoy=PUB)

    assert (r["creadas"], r["actualizadas"]) == (0, 1)
    info = db.query(Informacion).one()
    assert info.fecha_fin == date(2026, 10, 10)
    versiones = db.query(Historial).order_by(Historial.version).all()
    assert [v.version for v in versiones] == [1, 2]
    assert "3 de octubre" in versiones[1].contenido_anterior


def test_vigencia_vencida_pasa_a_desactualizada(tablas):
    db = tablas
    _pub(db, _fuente(db, 100), "posts:1", "Mesas de examen", "<p>Mesa el 3 de octubre</p>")
    procesar_pendientes(db, hoy=PUB)

    assert actualizar_vigencias(db, hoy=date(2026, 10, 3)) == 0
    assert actualizar_vigencias(db, hoy=date(2026, 10, 4)) == 1
    assert db.query(Informacion).one().estado == E.DESACTUALIZADA


def test_pagina_fija_no_vence_por_una_fecha_vieja():
    from datetime import date
    from app.ingest.verify import calcular_vigencia
    _, fin, motivo = calcular_vigencia("SYSACAD: avisos", "Inscripción a partir del Lunes 10 de agosto de 2026",
                                       date(2026, 10, 5), es_pagina=True)
    assert fin is None and "mientras esté publicada" in motivo
