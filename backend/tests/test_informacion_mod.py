"""Carga directa de información y avisos de paro por MOD/ADMIN."""
from datetime import date, timedelta

import pytest

from app.models.informacion import Evidencia, Historial, Informacion, Verificacion
from app.models.ingesta import Chunk, Documento, Fuente, Ingesta, Publicacion
from app.models.metrica import MetricaDiaria
from app.models.usuario import RolEnum
from conftest import auth

URL = "/api/v1/informacion"


@pytest.fixture(autouse=True)
def tablas(db):
    engine = db.get_bind()
    for m in (Fuente, Documento, Publicacion, Chunk, Ingesta, MetricaDiaria,
              Informacion, Evidencia, Verificacion, Historial):
        m.__table__.create(engine, checkfirst=True)


@pytest.fixture
def mod(crear_usuario):
    return crear_usuario("mod@alu.frt.utn.edu.ar", RolEnum.SMOD)


def test_miembro_no_puede_cargar(client, crear_usuario):
    miembro = crear_usuario("a@alu.frt.utn.edu.ar")
    r = client.post(URL, json={"tipo": "AVISO", "contenido": "Algo importante para todos"}, headers=auth(miembro))
    assert r.status_code == 403


def test_carga_con_tipo_elegido_y_sin_link(client, db, mod):
    # El texto habla de una beca, pero el MOD eligió TRAMITE: manda lo que eligió
    r = client.post(URL, json={"tipo": "TRAMITE", "contenido": "Becas: entregar la constancia en Bedelía\nDetalle"},
                    headers=auth(mod))
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["tipo"] == "TRAMITE"
    assert data["estado"] == "CONFIRMADA"
    assert data["titulo"] == "Becas: entregar la constancia en Bedelía"
    assert db.query(Chunk).count() >= 1  # queda buscable


def test_tipo_y_contenido_obligatorios(client, mod):
    assert client.post(URL, json={"contenido": "Algo importante para todos"}, headers=auth(mod)).status_code == 422
    assert client.post(URL, json={"tipo": "AVISO"}, headers=auth(mod)).status_code == 422
    assert client.post(URL, json={"tipo": "AVISO", "contenido": "x", "url": "no-es-link"},
                       headers=auth(mod)).status_code == 422


@pytest.mark.parametrize("tipo, quien, abierta", [
    ("DOCENTE", "docente", True),
    ("NO_DOCENTE", "no docente", False),
    ("AMBOS", "docente y no docente", False),
])
def test_paro_abierta_o_cerrada(client, mod, tipo, quien, abierta):
    fecha = date.today() + timedelta(days=3)
    r = client.post(f"{URL}/paro", json={"tipo": tipo, "fecha": fecha.isoformat()}, headers=auth(mod))
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["tipo"] == "AVISO"
    assert data["titulo"] == f"Paro {quien}: {fecha:%d/%m/%Y}"
    assert ("ABIERTA" in data["contenido"]) is abierta
    assert ("CERRADA" in data["contenido"]) is not abierta
    assert data["fecha_fin"] == fecha.isoformat()  # vence solo cuando pasa el paro


def test_paro_de_varios_dias(client, mod):
    fecha = date.today() + timedelta(days=1)
    fin = fecha + timedelta(days=2)
    r = client.post(f"{URL}/paro", json={"tipo": "DOCENTE", "fecha": fecha.isoformat(), "dias": 3,
                                         "detalle": "Adhiere CONADU"}, headers=auth(mod))
    data = r.json()
    assert "de 3 días" in data["contenido"]
    assert f"{fin:%d/%m/%Y}" in data["contenido"]
    assert "Adhiere CONADU" in data["contenido"]
    assert data["fecha_fin"] == fin.isoformat()


def test_paro_dias_validos(client, mod):
    hoy = date.today().isoformat()
    assert client.post(f"{URL}/paro", json={"tipo": "DOCENTE", "fecha": hoy, "dias": 0},
                       headers=auth(mod)).status_code == 422
    assert client.post(f"{URL}/paro", json={"tipo": "OTRO", "fecha": hoy},
                       headers=auth(mod)).status_code == 422
