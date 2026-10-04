"""Panel administrativo (etapa 8): resumen/métricas y gestión de fuentes, con permisos en backend."""
from datetime import date

import pytest

from app.models.informacion import Evidencia, Historial, Informacion, Verificacion
from app.models.ingesta import (
    Chunk, Documento, EstadoIngestaEnum, Fuente, Ingesta, Publicacion, TipoFuenteEnum,
)
from app.models.metrica import MetricaDiaria
from app.models.usuario import RolEnum
from app.services.metricas import incrementar
from conftest import auth


@pytest.fixture
def datos(db):
    engine = db.get_bind()
    for m in (Fuente, Documento, Publicacion, Chunk, Ingesta, MetricaDiaria,
              Informacion, Evidencia, Verificacion, Historial):
        m.__table__.create(engine)
    wp = Fuente(nombre="Sistemas FRT", tipo=TipoFuenteEnum.WORDPRESS, url="https://x",
                confiabilidad_base=100, activa=True, config={})
    wa = Fuente(nombre="Canal WhatsApp 1", tipo=TipoFuenteEnum.WHATSAPP, url="https://x",
                confiabilidad_base=50, activa=False, config={})
    db.add_all([wp, wa])
    db.flush()
    db.add_all([
        Ingesta(fuente_id=wp.id, estado=EstadoIngestaEnum.OK, nuevos=3, detalle_errores=[]),
        Ingesta(fuente_id=wp.id, estado=EstadoIngestaEnum.ERROR, errores=1,
                detalle_errores=[{"item": None, "error": "timeout"}]),
        Informacion(tipo="BECA", titulo="Becas", contenido="x", estado="CONFIRMADA", confianza=100),
        Informacion(tipo="AVISO", titulo="Aviso", contenido="x", estado="NO_CONFIRMADA", confianza=50),
    ])
    incrementar(db, "consultas", 4, dia=date.today())
    incrementar(db, "cache_hits", 1, dia=date.today())
    db.commit()
    return wp, wa


def test_mod_ve_el_resumen_del_sistema(client, crear_usuario, datos):
    mod = crear_usuario("mod@alu.frt.utn.edu.ar", RolEnum.MOD)
    r = client.get("/api/v1/admin/resumen", headers=auth(mod))
    assert r.status_code == 200
    data = r.json()
    assert (data["fuentes"]["total"], data["fuentes"]["activas"]) == (2, 1)
    assert data["informacion"]["no_confirmada"] == 1
    assert data["informacion"]["por_estado"]["CONFIRMADA"] == 1
    assert data["ingesta"]["con_error"] == 1  # la última corrida de Sistemas FRT falló
    assert data["ingesta"]["errores_ultimos_7_dias"][0]["detalle"][0]["error"] == "timeout"
    assert data["metricas"]["consultas"][date.today().isoformat()] == 4
    assert data["usuarios"]["total"] == 1


def test_miembro_no_ve_el_resumen(client, crear_usuario, datos):
    u = crear_usuario("u@alu.frt.utn.edu.ar", RolEnum.MIEMBRO)
    assert client.get("/api/v1/admin/resumen", headers=auth(u)).status_code == 403


def test_admin_activa_fuente_y_cambia_confiabilidad(client, crear_usuario, datos):
    _, wa = datos
    admin = crear_usuario("admin@alu.frt.utn.edu.ar", RolEnum.ADMIN)
    r = client.patch(f"/api/v1/fuentes/{wa.id}", json={"activa": True, "confiabilidad_base": 60},
                     headers=auth(admin))
    assert r.status_code == 200
    assert (r.json()["activa"], r.json()["confiabilidad_base"]) == (True, 60)
    fuera_de_rango = client.patch(f"/api/v1/fuentes/{wa.id}", json={"confiabilidad_base": 101},
                                  headers=auth(admin))
    assert fuera_de_rango.status_code == 422


@pytest.mark.parametrize("rol", [RolEnum.MIEMBRO, RolEnum.MOD])
def test_solo_admin_modifica_fuentes(client, crear_usuario, datos, rol):
    _, wa = datos
    u = crear_usuario("u@alu.frt.utn.edu.ar", rol)
    assert client.patch(f"/api/v1/fuentes/{wa.id}", json={"activa": True}, headers=auth(u)).status_code == 403
