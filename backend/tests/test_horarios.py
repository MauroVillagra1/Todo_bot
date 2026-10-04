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
    return next(g for g in grillas if f"Comisión : {comision}" in g).splitlines()


def test_una_grilla_por_comision(grillas):
    assert len(grillas) == 7
    for comision in ("4K01", "4K02", "4K03", "4K06", "4K07", "4K08", "4K09"):
        assert any(comision in g for g in grillas), comision


def test_bloques_combinados_con_hora_de_inicio_y_fin(grillas):
    lineas = _grilla(grillas, "4K01")
    assert "Lunes 14:00 a 16:15: Administración de Sistemas de Información Cordero Lucas" in lineas
    assert "Lunes 16:15 a 18:30: Redes de Datos Moyano Alberto (Lab. 154)" in lineas
    # Bloque más corto que los demás (empieza 14:45)
    assert "Martes 14:45 a 16:15: Redes de Datos Nazar Patricia" in lineas
    assert "Viernes 16:15 a 18:30: Tecnologías para la automatización Javier Canto" in lineas


def test_turno_noche(grillas):
    lineas = _grilla(grillas, "4K03")
    assert "Lunes 19:00 a 21:15: Redes de Datos Eduardo Nemer (Lab.154)" in lineas
    assert "Viernes 21:15 a 23:30: Administración de Sistemas de Información Sardi Duilio" in lineas


def test_pdf_que_no_es_horario_usa_la_extraccion_comun():
    pdf = pdf_con_texto("Resolucion 123/2026 sobre mesas de examen")
    assert leer_horarios(pdf) is None
    assert "Resolucion 123/2026" in leer_pdf(pdf)[0]
