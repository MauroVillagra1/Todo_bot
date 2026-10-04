"""
Preguntas de horarios respondidas con SQL (sin LLM), sobre el PDF real de 4º año
(plan 2023, 2º cuatrimestre 2026).
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.ingest.horarios import leer_grillas, normalizar_comision
from app.ingest.pipeline import guardar_grillas
from app.models.horario import HorarioClase
from app.models.informacion import Evidencia, Informacion
from app.models.ingesta import Documento, Fuente, TipoDocumentoEnum, TipoFuenteEnum
from app.rag.horarios import responder_horario

PDF = Path(__file__).parent / "fixtures" / "HORARIO-4-ANO-PLAN-2023.pdf"


@pytest.fixture(scope="module")
def grillas():
    return leer_grillas(PDF.read_bytes())


@pytest.fixture
def base(db, grillas):
    engine = db.get_bind()
    for m in (Fuente, Documento, Informacion, Evidencia, HorarioClase):
        m.__table__.create(engine)
    f = Fuente(nombre="Sistemas FRT (PDFs)", tipo=TipoFuenteEnum.WORDPRESS, url="https://x",
               confiabilidad_base=100, activa=True, config={})
    db.add(f)
    db.flush()
    doc = Documento(fuente_id=f.id, url="https://x/HORARIO-4-ANO-PLAN-2023.pdf", nombre="HORARIO 4 AÑO – PLAN 2023",
                    tipo=TipoDocumentoEnum.PDF, hash="h" * 64,
                    fecha_publicacion=datetime(2026, 7, 8, tzinfo=timezone.utc))
    info = Informacion(tipo="CALENDARIO", titulo="Horario 4", contenido="x", estado="CONFIRMADA", confianza=100)
    db.add_all([doc, info])
    db.flush()
    db.add(Evidencia(informacion_id=info.id, fuente_id=f.id, documento_id=doc.id, tipo_de_evidencia="TEXTO"))
    guardar_grillas(db, doc.id, grillas)
    db.commit()
    return db


# ── Lectura estructurada ──────────────────────────────────────────────────────

def test_encabezado_de_cada_comision(grillas):
    g = next(g for g in grillas if g.comision == "4K01")
    assert (g.anio, g.plan, g.turno, g.periodo, g.aula) == (4, "2023", "Tarde", "Segundo cuatrimestre", "212")


def test_materia_docente_y_laboratorio_separados(grillas):
    g = next(g for g in grillas if g.comision == "4K01")
    redes = next(b for b in g.bloques if b.dia == 1 and b.inicio == "16:15")
    assert (redes.materia, redes.docente, redes.lugar) == ("Redes de Datos", "Moyano Alberto", "Lab. 154")
    # Docente en negrita (no cursiva): se separa con el catálogo de materias
    ics = next(b for b in g.bloques if b.dia == 4 and b.inicio == "16:15")
    assert (ics.materia, ics.docente) == ("Ingeniería y Calidad de Software", "Vicente Francisco")


def test_electivas_marcadas(grillas):
    g = next(g for g in grillas if g.comision == "4K09")
    assert all(b.electiva for b in g.bloques)
    assert g.bloques[0].materia == "FUNDAMENTOS DE INGENIERIA DE DATOS"


@pytest.mark.parametrize("texto,esperado", [("1k1", "1K01"), ("4K01", "4K01"), ("2 k 03", "2K03"), ("hola", None)])
def test_normalizar_comision(texto, esperado):
    assert normalizar_comision(texto) == esperado


# ── Respuestas con SQL ────────────────────────────────────────────────────────

def test_materia_en_todas_las_comisiones(base):
    r = responder_horario(base, "¿Cuándo se dicta Redes de Datos?")
    for comision in ("4K01", "4K02", "4K03"):
        assert f"**{comision}**" in r["respuesta"]
    assert "Lunes 16:15 a 18:30: Moyano Alberto — Lab. 154" in r["respuesta"]
    assert "Tecnologías" not in r["respuesta"]
    assert r["estado"] == "CONFIRMADA"
    assert r["fuentes"][0]["url"].endswith("HORARIO-4-ANO-PLAN-2023.pdf")


def test_comision_con_formato_corto_y_dia(base):
    r = responder_horario(base, "¿Qué materias tiene la 4k1 los lunes?")
    assert "Administración de Sistemas de Información" in r["respuesta"]
    assert "Redes de Datos" in r["respuesta"]
    assert "Martes" not in r["respuesta"] and "4K02" not in r["respuesta"]


def test_abreviaturas_y_docente(base):
    r = responder_horario(base, "¿quién da ingenieria y calidad de soft en la 4K02?")
    assert "Chibilisco Vicente" in r["respuesta"] and "Vicente Francisco" in r["respuesta"]
    assert "4K01" not in r["respuesta"]


def test_electivas_por_turno(base):
    r = responder_horario(base, "¿Qué electivas hay a la noche?")
    assert "FUNDAMENTOS DE INGENIERIA DE DATOS" in r["respuesta"]


def test_seguimiento_usa_la_comision_anterior(base):
    r = responder_horario(base, "¿y los viernes?", anterior="¿Qué tiene la 4K01 los lunes?")
    assert "**4K01**" in r["respuesta"] and "Viernes" in r["respuesta"] and "Lunes" not in r["respuesta"]


@pytest.mark.parametrize("pregunta", [
    "¿Hay becas para sistemas de información?",  # menciona una materia pero no es de horarios
    "¿Cuándo son las mesas de examen?",
    "¿Cuándo se dicta Análisis Matemático II?",  # no está en este PDF → sigue el RAG
])
def test_preguntas_que_no_son_de_horarios_siguen_el_rag(base, pregunta):
    assert responder_horario(base, pregunta) is None


def _copia_plan_2008(db, materia="Redes de Información"):
    """Agrega la 4K01 del plan 2008 (otro PDF) con una materia propia de ese plan."""
    doc = db.query(Documento).first()
    for b in db.query(HorarioClase).filter(HorarioClase.comision == "4K01").all():
        db.add(HorarioClase(documento_id=doc.id, comision="4K01", anio=4, plan="2008", turno=b.turno,
                            periodo=b.periodo, aula=b.aula, dia=b.dia, inicio=b.inicio, fin=b.fin,
                            materia=materia if b.materia == "Redes de Datos" else b.materia,
                            materia_norm=(materia if b.materia == "Redes de Datos" else b.materia).lower(),
                            docente=b.docente, lugar=b.lugar, electiva=False))
    db.commit()


def test_con_dos_planes_muestra_el_mas_nuevo_y_avisa(base):
    _copia_plan_2008(base)
    r = responder_horario(base, "¿Qué tiene la 4K01 los lunes?")
    assert "Plan 2023" in r["respuesta"] and "Plan 2008" not in r["respuesta"]
    assert "plan 2008" in r["respuesta"]  # aviso para quien cursa el plan viejo
    viejo = responder_horario(base, "¿Qué tiene la 4K01 los lunes en el plan 2008?")
    assert "Plan 2008" in viejo["respuesta"] and "Redes de Información" in viejo["respuesta"]


def test_materia_que_solo_existe_en_el_plan_viejo(base):
    _copia_plan_2008(base)
    r = responder_horario(base, "¿Cuándo se dicta Redes de Información?")
    assert "Plan 2008" in r["respuesta"]


def test_horario_desactualizado_no_se_usa(base):
    base.query(Informacion).update({"estado": "DESACTUALIZADA"})
    base.commit()
    assert responder_horario(base, "¿Cuándo se dicta Redes de Datos?") is None
