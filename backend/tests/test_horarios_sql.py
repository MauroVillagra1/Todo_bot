"""
Preguntas de horarios respondidas con SQL (sin LLM), sobre el PDF real de 4º año
(plan 2023, 2º cuatrimestre 2026).
"""
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.ingest.horarios import leer_grillas, normalizar_comision, normalizar_materia, separar_docentes
from app.ingest.limpieza_horarios import limpiar_docente, limpiar_materia
from app.ingest.pipeline import guardar_grillas
from app.models.horario import HorarioClase
from app.models.informacion import Evidencia, Informacion
from app.models.ingesta import Documento, Fuente, TipoDocumentoEnum, TipoFuenteEnum
from app.rag.horarios import responder_horario

PDF = Path(__file__).parent / "fixtures" / "HORARIO-4-ANO-PLAN-2023.pdf"
OCTUBRE = date(2026, 10, 4)  # segundo cuatrimestre en curso


def responder(db, pregunta, anterior="", hoy=OCTUBRE):
    return responder_horario(db, pregunta, anterior, hoy=hoy)


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
    r = responder(base, "¿Cuándo se dicta Redes de Datos?")
    for comision in ("4K01", "4K02", "4K03"):
        assert f"**{comision}**" in r["respuesta"]
    assert "Lunes 16:15 a 18:30: Moyano Alberto — Lab. 154" in r["respuesta"]
    assert "Tecnologías" not in r["respuesta"]
    assert r["estado"] == "CONFIRMADA"
    assert r["fuentes"][0]["url"].endswith("HORARIO-4-ANO-PLAN-2023.pdf")


def test_preguntas_de_examen_no_son_de_horarios(base):
    assert responder(base, "¿Cuándo rindo Redes de Datos?") is None
    assert responder(base, "mesa de final de Redes de Datos") is None


def test_comision_con_formato_corto_y_dia(base):
    r = responder(base, "¿Qué materias tiene la 4k1 los lunes?")
    assert "Administración de Sistemas de Información" in r["respuesta"]
    assert "Redes de Datos" in r["respuesta"]
    assert "Martes" not in r["respuesta"] and "4K02" not in r["respuesta"]


def test_abreviaturas_y_docente(base):
    r = responder(base, "¿quién da ingenieria y calidad de soft en la 4K02?")
    assert "Chibilisco Vicente" in r["respuesta"] and "Vicente Francisco" in r["respuesta"]
    assert "4K01" not in r["respuesta"]


def test_electivas_por_turno(base):
    r = responder(base, "¿Qué electivas hay a la noche?")
    assert "Fundamentos de Ingeniería de Datos" in r["respuesta"]


def test_seguimiento_usa_la_comision_anterior(base):
    r = responder(base, "¿y los viernes?", anterior="¿Qué tiene la 4K01 los lunes?")
    assert "**4K01**" in r["respuesta"] and "Viernes" in r["respuesta"] and "Lunes" not in r["respuesta"]


@pytest.mark.parametrize("pregunta", [
    "¿Hay becas para sistemas de información?",  # menciona una materia pero no es de horarios
    "¿Cuándo son las mesas de examen?",
    "¿Cuándo se dicta Análisis Matemático II?",  # no está en este PDF → sigue el RAG
])
def test_preguntas_que_no_son_de_horarios_siguen_el_rag(base, pregunta):
    assert responder(base, pregunta) is None


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
    r = responder(base, "¿Qué tiene la 4K01 los lunes?")
    assert "Plan 2023" in r["respuesta"] and "Plan 2008" not in r["respuesta"]
    assert "plan 2008" in r["respuesta"]  # aviso para quien cursa el plan viejo
    viejo = responder(base, "¿Qué tiene la 4K01 los lunes en el plan 2008?")
    assert "Plan 2008" in viejo["respuesta"] and "Redes de Información" in viejo["respuesta"]


def test_materia_que_solo_existe_en_el_plan_viejo(base):
    _copia_plan_2008(base)
    r = responder(base, "¿Cuándo se dicta Redes de Información?")
    assert "Plan 2008" in r["respuesta"]


def test_lo_que_tengo_un_dia_en_mi_comision(base):
    r = responder(base, "¿Qué materias y en qué horario las tengo los lunes en la 4K01?")
    assert "- Lunes 14:00 a 16:15: Administración de Sistemas de Información — Cordero Lucas" in r["respuesta"]
    assert "- Lunes 16:15 a 18:30: Redes de Datos — Moyano Alberto — Lab. 154" in r["respuesta"]


def test_materias_de_un_docente(base):
    r = responder(base, "¿Qué materias da Moyano?")
    assert "Clases de **Moyano Alberto**" in r["respuesta"]
    assert "**4K01**" in r["respuesta"] and "**4K02**" in r["respuesta"]
    assert "Redes de Datos" in r["respuesta"] and "Nazar" not in r["respuesta"]


def test_docente_por_nombre_y_apellido_con_dia(base):
    r = responder(base, "¿Patricia Nazar da clases los martes?")
    assert "Nazar Patricia" in r["respuesta"] and "Martes" in r["respuesta"]
    assert "Lunes" not in r["respuesta"]


def test_docente_compartido_sin_guion(base):
    from app.rag.horarios import _personas
    assert _personas("Valdez Ocampo T, - Bedran Marisel") == ["valdez ocampo t", "bedran marisel"]
    assert _personas("Vicente Francisco - Chibilisco Vicente") == ["vicente francisco", "chibilisco vicente"]


def test_cuatrimestre_terminado_no_se_muestra(base):
    # El fixture es del segundo cuatrimestre: en mayo (primero en curso) no aparece…
    assert responder(base, "¿Qué tiene la 4K01 los lunes?", hoy=date(2026, 5, 4)) is None
    # …salvo que se lo pida explícitamente
    r = responder(base, "¿Qué tiene la 4K01 los lunes en el segundo cuatrimestre?", hoy=date(2026, 5, 4))
    assert "Redes de Datos" in r["respuesta"]


def test_por_docente_se_muestran_todos_los_cuatrimestres(base):
    mayo = date(2026, 5, 4)  # el fixture es del segundo cuatrimestre, que en mayo no está en curso
    r = responder(base, "¿Qué materias da Moyano?", hoy=mayo)
    assert r is not None and "Redes de Datos" in r["respuesta"]
    # Si se pide un cuatrimestre, solo ese
    assert responder(base, "¿Qué materias da Moyano en el primer cuatrimestre?", hoy=mayo) is None
    assert "Redes de Datos" in responder(base, "¿Qué materias da Moyano en el 2do cuatrimestre?", hoy=mayo)["respuesta"]


def test_horario_desactualizado_no_se_usa(base):
    base.query(Informacion).update({"estado": "DESACTUALIZADA"})
    base.commit()
    assert responder(base, "¿Cuándo se dicta Redes de Datos?") is None


# ── Nombres cortos, aclaración y conversación ─────────────────────────────────

def _agregar(db, comision, materia, dia=2, inicio="19:00", fin="21:15", electiva=True):
    doc = db.query(Documento).first()
    db.add(HorarioClase(documento_id=doc.id, comision=comision, anio=int(comision[0]), plan="2023",
                        turno="Noche", periodo="Segundo cuatrimestre", aula="159", dia=dia, inicio=inicio,
                        fin=fin, materia=materia, materia_norm=normalizar_materia(materia), electiva=electiva))
    db.commit()


def test_nombre_corto_encuentra_la_materia(base):
    _agregar(base, "3K05", "DISEÑO UX PARA PRODUCTOS DIGITALES", dia=4)
    r = responder(base, "diseño ux")
    assert "**3K05**" in r["respuesta"] and "Jueves 19:00 a 21:15" in r["respuesta"]


def test_varias_materias_distintas_pide_aclaracion(base):
    _agregar(base, "3K05", "DISEÑO UX PARA PRODUCTOS DIGITALES", dia=4)
    _agregar(base, "3K05", "FUNDAMENTOS DEL DISEÑO UX/UI", dia=2)
    r = responder(base, "¿Cuándo es diseño ux?")
    assert r["estado"] == "ACLARACION" and r["fuentes"] == []
    assert "- Diseño UX para productos digitales" in r["respuesta"]
    assert "- Fundamentos del diseño UX/UI" in r["respuesta"]
    # Con el nombre completo ya no pregunta
    completo = responder(base, "¿Cuándo es diseño ux para productos digitales?")
    assert completo["estado"] == "CONFIRMADA" and "Jueves" in completo["respuesta"]


def test_misma_materia_escrita_distinto_no_pide_aclaracion(base):
    _agregar(base, "1K01", "Algorit. y Est. De Datos", electiva=False)
    _agregar(base, "1K02", "Algoritmos y Estructuras de Datos", dia=3, electiva=False)
    r = responder(base, "¿Cuándo se dicta algoritmos y estructuras de datos?")
    assert r["estado"] == "CONFIRMADA"
    assert "**1K01**" in r["respuesta"] and "**1K02**" in r["respuesta"]


@pytest.mark.parametrize("mensaje,contiene", [
    ("Hola", "Soy UTNIA"),
    ("buenas tardes!", "Soy UTNIA"),
    ("¿Qué podés hacer?", "fuentes institucionales"),
    ("gracias!!", "De nada"),
    ("chau", "Hasta luego"),
])
def test_conversacion_basica(mensaje, contiene):
    from app.rag.conversacion import responder_conversacion
    r = responder_conversacion(mensaje)
    assert contiene in r["respuesta"] and r["estado"] == "CONVERSACION"


def test_saludo_con_pregunta_no_es_solo_conversacion():
    from app.rag.conversacion import responder_conversacion
    assert responder_conversacion("hola, ¿cuándo se dicta Redes de Datos?") is None


@pytest.mark.parametrize("texto,esperado", [
    ("Such Victor - Aparicio Gabriela", ["Such Victor", "Aparicio Gabriela"]),
    ("Ugarte Fernando -  Lopez Emmanuel", ["Ugarte Fernando", "Lopez Emmanuel"]),
    ("Valdez Ocampo T, - Bedran Marisel", ["Valdez Ocampo T", "Bedran Marisel"]),
    ("Paredi, Mario", ["Paredi, Mario"]),  # apellido, nombre: una sola persona
    ("Moya Susana - A designar", ["Moya Susana"]),
    ("Ing. RUIZ 21:00 - 22:30", ["Ing. RUIZ"]),
    ("SIN DOCENTE 18:45 - 21:00", []),
    ("21:00 - 22:30", []),
])
def test_separar_docentes(texto, esperado):
    assert separar_docentes(texto) == esperado


def test_dos_docentes_se_muestran_y_buscan_por_separado(base):
    r = responder(base, "¿Quién da Ingeniería y Calidad de Software en la 4K02?")
    assert r is not None and " - " not in r["respuesta"].split("\n", 2)[2]
    # Cada uno de los dos docentes se encuentra por su cuenta
    for apellido in ("Chibilisco", "Vicente"):
        r = responder(base, f"¿Qué materias da {apellido}?")
        assert r is not None and "Ingeniería y Calidad de Software" in r["respuesta"], apellido


# ── Limpieza de nombres ───────────────────────────────────────────────────────

@pytest.mark.parametrize("texto,esperado", [
    ("Vivente Francisco - Chibilisco Vicente", "Vicente Francisco - Chibilisco Vicente"),
    ("Paredi, Mario", "Paredi Mario"),
    ("Hadad Salomon R. - De Luca Alejandra", "Hadad Salomon Rosana - De Luca Alejandra"),
    ("Rojas Cristina Dorigatti Mariana", "Rojas Cristina - Dorigatti Mariana"),
    ("Will Adrian Lizondo Diego / Jimenez Victor", "Will Adrian - Lizondo Diego - Jimenez Victor"),
    ("Ing. MARTÍNEZ Ing. CARO", "Martinez Ariel - Caro"),
    ("Ing. SUELDO 20:15 - 22:30", "Sueldo"),  # Adrian o Adriana: no se adivina
    ("IngGONZÁLEZ QUINTEROS 18:00 -19:30", "González Quinteros Juan P"),
    ("Zakour José (Lab . 156)", "Zakhour José"),
    ("Arias Jorge Lab . 154", "Arias Jorge"),
    ("SINDOCENTE", None),
    ("A designar Jub. Torres", None),
])
def test_limpiar_docente(texto, esperado):
    assert limpiar_docente(texto) == esperado


@pytest.mark.parametrize("materia,docente,esperado", [
    ("Parad. De Programacion", None, ("Paradigmas de Programación", None)),
    ("Comunicaciones - (aux. Elías, Roberto)", None, ("Comunicaciones", "Elías Roberto")),
    ("Gestión de Datos - ( prof Such)", "Such Victor", ("Gestión de Datos", "Such Victor")),
    ("Matemática Superior (Pro. Cantó, Javier)", None, ("Matemática Superior", "Cantó Javier")),
    ("II Sistemas Operativos - Ing. Gonzalez Quinteros", None, ("Sistemas Operativos", "González Quinteros Juan P")),
    ("Bases de Datos *", None, ("Bases de Datos", None)),
    ("PROGRAMACION DE APLICACIONES VISUALES (Prof. vicente )", None,
     ("Programación de Aplicaciones Visuales", "Vicente Francisco")),
    ("Ing. Del Requerimiento", None, ("Ingeniería del Requerimiento", None)),
    ("*** cambuia de", None, None),
    ("Redes de Datos", "Moyano Alberto", ("Redes de Datos", "Moyano Alberto")),
])
def test_limpiar_materia(materia, docente, esperado):
    assert limpiar_materia(materia, docente) == esperado


def test_consulta_de_horarios_no_baja_el_pdf(base):
    """Cada clase venía con el PDF completo de su documento: gigas de transferencia."""
    from sqlalchemy import event
    sqls = []
    escuchar = lambda conn, cursor, sql, *a: sqls.append(sql)  # noqa: E731
    event.listen(base.get_bind(), "before_cursor_execute", escuchar)
    try:
        base.expire_all()
        assert responder(base, "¿Qué materias da Moyano?") is not None
    finally:
        event.remove(base.get_bind(), "before_cursor_execute", escuchar)
    consultas = " ".join(sqls)
    assert "contenido_original" not in consultas and "texto_extraido" not in consultas
