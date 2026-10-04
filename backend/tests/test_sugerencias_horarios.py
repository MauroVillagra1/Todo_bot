"""Sugerencias de usuarios (MIEMBRO propone, MOD revisa) y grilla de horarios editable (ADMIN)."""
from datetime import date

import pytest

from app.models.auditoria import RegistroCambios
from app.models.horario import HorarioClase
from app.models.informacion import Evidencia, Historial, Informacion, Verificacion
from app.models.ingesta import Chunk, Documento, Fuente, Ingesta, Publicacion
from app.models.metrica import MetricaDiaria
from app.models.sugerencia import Sugerencia
from app.models.usuario import RolEnum
from app.rag.horarios import responder_horario
from conftest import auth


@pytest.fixture
def tablas(db):
    engine = db.get_bind()
    for m in (Fuente, Documento, Publicacion, Chunk, Ingesta, MetricaDiaria, Informacion, Evidencia,
              Verificacion, Historial, HorarioClase, Sugerencia, RegistroCambios):
        m.__table__.create(engine)
    return db


SUGERENCIA = {"titulo": "Cambio de aula de Física I", "contenido": "Desde el lunes Física I de la 1K01 se da en el aula 105."}


# ── Sugerencias ───────────────────────────────────────────────────────────────

def test_miembro_sugiere_y_ve_su_estado(client, tablas, crear_usuario):
    yo = crear_usuario("alumno@alu.frt.utn.edu.ar")
    r = client.post("/api/v1/sugerencias/", json=SUGERENCIA, headers=auth(yo))
    assert r.status_code == 201 and r.json()["estado"] == "PENDIENTE"
    mias = client.get("/api/v1/sugerencias/mias", headers=auth(yo)).json()
    assert [s["titulo"] for s in mias] == [SUGERENCIA["titulo"]]


def test_miembro_no_puede_revisar(client, tablas, crear_usuario):
    yo = crear_usuario("alumno@alu.frt.utn.edu.ar")
    sid = client.post("/api/v1/sugerencias/", json=SUGERENCIA, headers=auth(yo)).json()["id"]
    assert client.get("/api/v1/sugerencias/", headers=auth(yo)).status_code == 403
    assert client.post(f"/api/v1/sugerencias/{sid}/aceptar", json={}, headers=auth(yo)).status_code == 403


def test_mod_acepta_y_queda_como_publicacion(client, tablas, crear_usuario):
    alumno = crear_usuario("alumno@alu.frt.utn.edu.ar")
    mod = crear_usuario("mod@doc.frt.utn.edu.ar", RolEnum.MOD)
    sid = client.post("/api/v1/sugerencias/", json=SUGERENCIA, headers=auth(alumno)).json()["id"]

    pendientes = client.get("/api/v1/sugerencias/", headers=auth(mod)).json()
    assert pendientes[0]["autor"].endswith("(alumno@alu.frt.utn.edu.ar)")

    r = client.post(f"/api/v1/sugerencias/{sid}/aceptar", json={"titulo": "Física I 1K01: aula 105"}, headers=auth(mod))
    assert r.status_code == 200
    assert r.json()["estado"] == "ACEPTADA" and r.json()["informacion_estado"] == "PROBABLE"
    pub = tablas.query(Publicacion).one()
    assert pub.titulo == "Física I 1K01: aula 105" and pub.id_externo == f"sugerencia:{sid}"
    assert tablas.query(Fuente).one().nombre == "Sugerencias de usuarios"
    # No se puede revisar dos veces
    assert client.post(f"/api/v1/sugerencias/{sid}/rechazar", json={"motivo": "x" * 5}, headers=auth(mod)).status_code == 409


def test_mod_rechaza_con_motivo(client, tablas, crear_usuario):
    alumno = crear_usuario("alumno@alu.frt.utn.edu.ar")
    mod = crear_usuario("mod@doc.frt.utn.edu.ar", RolEnum.MOD)
    sid = client.post("/api/v1/sugerencias/", json=SUGERENCIA, headers=auth(alumno)).json()["id"]
    r = client.post(f"/api/v1/sugerencias/{sid}/rechazar", json={"motivo": "No hay fuente oficial"}, headers=auth(mod))
    assert r.json()["estado"] == "RECHAZADA"
    assert client.get("/api/v1/sugerencias/mias", headers=auth(alumno)).json()[0]["motivo"] == "No hay fuente oficial"
    assert tablas.query(Publicacion).count() == 0


def test_limite_de_pendientes(client, tablas, crear_usuario):
    yo = crear_usuario("alumno@alu.frt.utn.edu.ar")
    for _ in range(10):
        assert client.post("/api/v1/sugerencias/", json=SUGERENCIA, headers=auth(yo)).status_code == 201
    assert client.post("/api/v1/sugerencias/", json=SUGERENCIA, headers=auth(yo)).status_code == 429


# ── Grilla de horarios ────────────────────────────────────────────────────────

BLOQUE = {"comision": "1k1", "dia": 1, "inicio": "08:00", "fin": "09:30", "materia": "Física I",
          "docente": "Pérez Ana", "aula": "105", "periodo": "Anual"}


def test_solo_admin_edita_horarios(client, tablas, crear_usuario):
    mod = crear_usuario("mod@doc.frt.utn.edu.ar", RolEnum.MOD)
    assert client.get("/api/v1/horarios/", headers=auth(mod)).status_code == 403
    assert client.post("/api/v1/horarios/", json=BLOQUE, headers=auth(mod)).status_code == 403


def test_admin_agrega_edita_y_borra(client, tablas, crear_usuario):
    admin = crear_usuario("admin@doc.frt.utn.edu.ar", RolEnum.ADMIN)
    r = client.post("/api/v1/horarios/", json=BLOQUE, headers=auth(admin))
    assert r.status_code == 201
    b = r.json()
    assert (b["comision"], b["anio"], b["origen"]) == ("1K01", 1, "Carga manual")

    r = client.patch(f"/api/v1/horarios/{b['id']}", json={"docente": "Gómez Luis", "aula": ""}, headers=auth(admin))
    assert (r.json()["docente"], r.json()["aula"]) == ("Gómez Luis", None)
    assert client.patch(f"/api/v1/horarios/{b['id']}", json={"fin": "07:00"}, headers=auth(admin)).status_code == 422

    grilla = client.get("/api/v1/horarios/", headers=auth(admin)).json()
    assert [x["materia"] for x in grilla] == ["Física I"]

    assert client.delete(f"/api/v1/horarios/{b['id']}", headers=auth(admin)).status_code == 204
    assert client.get("/api/v1/horarios/", headers=auth(admin)).json() == []
    assert [c.accion for c in tablas.query(RegistroCambios).order_by(RegistroCambios.id)] == [
        "creacion", "actualizacion", "eliminacion"]


def test_chat_responde_con_bloque_manual(client, tablas, crear_usuario):
    admin = crear_usuario("admin@doc.frt.utn.edu.ar", RolEnum.ADMIN)
    client.post("/api/v1/horarios/", json=BLOQUE, headers=auth(admin))
    r = responder_horario(tablas, "¿Qué tiene la 1K01 los lunes?", hoy=date(2026, 10, 4))
    assert "Pérez Ana" in r["respuesta"] and "[1]" in r["respuesta"]
    assert r["fuentes"][0]["titulo"] == "Horarios cargados por la administración"
