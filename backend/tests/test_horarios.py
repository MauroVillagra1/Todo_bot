"""
Lectura de grillas de horarios (Excel → PDF con celdas combinadas).
Fixture: PDF público de sistemasfrtutn.ar (4º año, plan 2023, 2º cuatrimestre 2026).
"""
from pathlib import Path

import pytest

from app.ingest.horarios import leer_horarios
from app.ingest.pipeline import leer_pdf
from test_fuentes_extra import pdf_con_texto

PDF = Path(__file__).parent / "fixtures" / "HORARIO-4-ANO-PLAN-2023.pdf"


@pytest.fixture(scope="module")
def grillas():
    return leer_horarios(PDF.read_bytes())


def _grilla(grillas, comision):
    return next(g for g in grillas if f"Comisión {comision}" in g).splitlines()


def test_una_grilla_por_comision(grillas):
    assert len(grillas) == 7
    for comision in ("4K01", "4K02", "4K03", "4K06", "4K07", "4K08", "4K09"):
        assert any(comision in g for g in grillas), comision


def test_bloques_combinados_con_hora_de_inicio_y_fin(grillas):
    lineas = _grilla(grillas, "4K01")
    assert lineas[0] == ("Horario — Comisión 4K01 · 4º año · Plan 2023 · Segundo cuatrimestre"
                         " · Turno Tarde · Aula 212")
    assert "Lunes 14:00 a 16:15: Administración de Sistemas de Información — Docente: Cordero Lucas" in lineas
    assert "Lunes 16:15 a 18:30: Redes de Datos — Docente: Moyano Alberto — Lab. 154" in lineas
    # Bloque más corto que los demás (empieza 14:45)
    assert "Martes 14:45 a 16:15: Redes de Datos — Docente: Nazar Patricia" in lineas
    assert "Viernes 16:15 a 18:30: Tecnologías para la automatización — Docente: Javier Canto" in lineas


def test_turno_noche(grillas):
    lineas = _grilla(grillas, "4K03")
    assert "Lunes 19:00 a 21:15: Redes de Datos — Docente: Eduardo Nemer — Lab. 154" in lineas
    assert "Viernes 21:15 a 23:30: Administración de Sistemas de Información — Docente: Sardi Duilio" in lineas


def test_bloque_partido_por_una_linea_se_une(grillas):
    # 4K08: el docente quedó separado de la materia por una línea dentro de la celda
    lineas = _grilla(grillas, "4K08")
    assert ("Miércoles 17:45 a 20:45: PROGRAMACION DE APLICACIONES DISTRIBUIDAS (electiva)"
            " — Docente: De La Cruz José — Lab. 155") in lineas


@pytest.fixture(scope="module")
def segundo_anio():
    from app.ingest.horarios import leer_grillas
    return {g.comision: g for g in leer_grillas((PDF.parent / "2-ANO-2023.pdf").read_bytes())}


def test_segundo_anio_todas_las_comisiones_completas(segundo_anio):
    # Encabezados al pie de la página anterior y grillas cortadas por el salto de página
    assert sorted(segundo_anio) == ["2K01", "2K02", "2K03", "2K04", "2K05", "2K06", "2K07"]
    assert all(len(g.bloques) == 12 and g.plan == "2023" and g.periodo == "Anual" for g in segundo_anio.values())


def test_bloque_cortado_por_salto_de_pagina(segundo_anio):
    textos = [b.texto() for b in segundo_anio["2K07"].bloques]
    assert "Martes 17:30 a 19:00: Sistemas Operativos — Docente: Gonzalez Juan P. — Aula 231" in textos
    assert "Viernes 18:15 a 19:45: Fisica II" in textos


def test_fuentes_sin_negrita_ni_cursiva_en_el_nombre(segundo_anio):
    # Este PDF usa "CIDFont+F2" (materia) y "CIDFont+F4" (docente)
    textos = [b.texto() for b in segundo_anio["2K03"].bloques]
    assert "Jueves 08:00 a 09:30: Parad. De Programacion — Docente: Garcia Rosas Edwin — Lab. 155" in textos


def test_pdf_que_no_es_horario_usa_la_extraccion_comun():
    pdf = pdf_con_texto("Resolucion 123/2026 sobre mesas de examen")
    assert leer_horarios(pdf) is None
    assert "Resolucion 123/2026" in leer_pdf(pdf)[0]
