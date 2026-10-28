"""Roles MOD / SMOD / ADMIN, paros sin duplicados, historial de cambios con deshacer e importación de archivos."""
from datetime import date, timedelta

import pytest

from app.models.auditoria import RegistroCambios
from app.models.cache import CacheRespuesta
from app.models.calendario import EventoCalendario
from app.models.horario import HorarioClase
from app.models.informacion import EstadoInformacionEnum as E, Evidencia, Historial, Informacion, Verificacion
from app.models.ingesta import Chunk, Documento, Fuente, Ingesta, Publicacion
from app.models.metrica import MetricaDiaria
from app.models.usuario import RolEnum, Usuario
from app.routers import importar
from conftest import auth

MANANA = date.today() + timedelta(days=1)


@pytest.fixture(autouse=True)
def tablas(db):
    engine = db.get_bind()
    for m in (Fuente, Documento, Publicacion, Chunk, Ingesta, MetricaDiaria, Informacion, Evidencia,
              Verificacion, Historial, CacheRespuesta, HorarioClase):
        m.__table__.create(engine, checkfirst=True)


@pytest.fixture
def usuarios(crear_usuario):
    return {rol: crear_usuario(f"{rol.value.lower()}@alu.frt.utn.edu.ar", rol) for rol in RolEnum}


def _paro(client, quien, fecha=MANANA, dias=1):
    return client.post("/api/v1/informacion/paro", json={"tipo": "DOCENTE", "fecha": fecha.isoformat(), "dias": dias},
                       headers=auth(quien))


# ── Permisos ──────────────────────────────────────────────────────────────────

def test_mod_solo_carga_informacion(client, usuarios):
    mod = usuarios[RolEnum.MOD]
    r = client.post("/api/v1/informacion", json={"tipo": "AVISO", "contenido": "Aviso de prueba para todos"},
                    headers=auth(mod))
    assert r.status_code == 201, r.text
    assert _paro(client, mod).status_code == 403
    assert client.get("/api/v1/calendario/", headers=auth(mod)).status_code == 200
    assert client.post("/api/v1/calendario/", json={"fecha_inicio": "2026-11-02", "actividad": "Algo"},
                       headers=auth(mod)).status_code == 403
    assert client.get("/api/v1/usuarios/", headers=auth(mod)).status_code == 403
    assert client.get("/api/v1/sugerencias/", headers=auth(mod)).status_code == 403


def test_smod_tiene_panel_limitado(client, usuarios):
    smod = usuarios[RolEnum.SMOD]
    assert client.post("/api/v1/calendario/", json={"fecha_inicio": "2026-11-02", "actividad": "Algo"},
                       headers=auth(smod)).status_code == 201
    assert client.get("/api/v1/usuarios/", headers=auth(smod)).status_code == 200
    for url in ("/api/v1/admin/resumen", "/api/v1/reportes/", "/api/v1/historial", "/api/v1/fuentes/"):
        assert client.get(url, headers=auth(smod)).status_code == 403, url


def test_smod_solo_da_o_quita_mod(client, usuarios):
    smod, miembro = usuarios[RolEnum.SMOD], usuarios[RolEnum.MIEMBRO]
    url = f"/api/v1/usuarios/{miembro.id}"
    assert client.patch(url, json={"rol": "MOD"}, headers=auth(smod)).json()["rol"] == "MOD"
    assert client.patch(url, json={"rol": "MIEMBRO"}, headers=auth(smod)).json()["rol"] == "MIEMBRO"
    assert client.patch(url, json={"rol": "SMOD"}, headers=auth(smod)).status_code == 403
    otro_smod = usuarios[RolEnum.SMOD]
    assert client.patch(f"/api/v1/usuarios/{otro_smod.id}", json={"rol": "MOD"}, headers=auth(smod)).status_code == 403
    assert client.post(f"{url}/ban", json={"motivo": "spam"}, headers=auth(smod)).status_code == 403


def test_admin_da_smod_pero_no_admin(client, usuarios):
    admin, miembro = usuarios[RolEnum.ADMIN], usuarios[RolEnum.MIEMBRO]
    url = f"/api/v1/usuarios/{miembro.id}"
    assert client.patch(url, json={"rol": "SMOD"}, headers=auth(admin)).json()["rol"] == "SMOD"
    assert client.patch(url, json={"rol": "ADMIN"}, headers=auth(admin)).status_code == 422


# ── Paros ─────────────────────────────────────────────────────────────────────

def test_no_se_cargan_dos_paros_el_mismo_dia(client, usuarios):
    smod = usuarios[RolEnum.SMOD]
    assert _paro(client, smod, dias=3).status_code == 201
    r = _paro(client, smod, fecha=MANANA + timedelta(days=2))  # se superpone con el anterior
    assert r.status_code == 409 and "Ya hay un paro" in r.json()["detail"]
    assert _paro(client, smod, fecha=MANANA + timedelta(days=3)).status_code == 201  # el día siguiente, sí


def test_lista_paros_proximos_y_pasados(client, db, usuarios):
    smod = usuarios[RolEnum.SMOD]
    _paro(client, smod)
    viejo = _paro(client, smod, fecha=date.today() - timedelta(days=10)).json()
    lista = client.get("/api/v1/informacion/paros", headers=auth(smod)).json()
    assert len(lista["proximos"]) == 1 and lista["proximos"][0]["fecha_inicio"] == MANANA.isoformat()
    assert [p["informacion_id"] for p in lista["pasados"]] == [viejo["informacion_id"]]


# ── Historial y deshacer ──────────────────────────────────────────────────────

def _ultimo(client, admin, **filtros):
    return client.get("/api/v1/historial", params=filtros, headers=auth(admin)).json()["items"][0]


def _deshacer(client, admin, cambio_id):
    return client.post(f"/api/v1/historial/{cambio_id}/deshacer", headers=auth(admin))


def test_historial_filtra_y_deshace_calendario(client, db, usuarios):
    admin, smod = usuarios[RolEnum.ADMIN], usuarios[RolEnum.SMOD]
    ev = client.post("/api/v1/calendario/", json={"fecha_inicio": "2026-11-02", "actividad": "Charla"},
                     headers=auth(smod)).json()
    client.patch(f"/api/v1/calendario/{ev['id']}", json={"actividad": "Charla de bienvenida"}, headers=auth(smod))

    pagina = client.get("/api/v1/historial", params={"usuario_id": smod.id}, headers=auth(admin)).json()
    assert pagina["total"] == 2
    cambio = pagina["items"][0]
    assert cambio["accion"] == "actualizacion" and "Charla → Charla de bienvenida" in cambio["resumen"]
    assert client.get("/api/v1/historial", params={"usuario_id": admin.id}, headers=auth(admin)).json()["total"] == 0
    hoy = date.today().isoformat()
    assert client.get("/api/v1/historial", params={"desde": hoy, "hasta": hoy}, headers=auth(admin)).json()["total"] == 2
    autores = client.get("/api/v1/historial/autores", headers=auth(admin)).json()
    assert [(a["id"], a["cambios"]) for a in autores] == [(smod.id, 2)]

    # La creación no se puede deshacer mientras haya una edición posterior
    creacion = pagina["items"][1]
    assert _deshacer(client, admin, creacion["id"]).status_code == 409
    assert _deshacer(client, admin, cambio["id"]).status_code == 200
    assert db.get(EventoCalendario, ev["id"]).actividad == "Charla"
    assert _deshacer(client, admin, cambio["id"]).status_code == 409  # ya se deshizo
    assert _deshacer(client, admin, creacion["id"]).status_code == 200
    assert db.get(EventoCalendario, ev["id"]) is None


def test_deshacer_borrado_recupera_el_evento(client, db, usuarios):
    admin = usuarios[RolEnum.ADMIN]
    ev = client.post("/api/v1/calendario/", json={"fecha_inicio": "2026-11-02", "fecha_fin": "2026-11-04",
                                                  "actividad": "Inscripción"}, headers=auth(admin)).json()
    client.delete(f"/api/v1/calendario/{ev['id']}", headers=auth(admin))
    assert _deshacer(client, admin, _ultimo(client, admin)["id"]).status_code == 200
    vuelto = db.get(EventoCalendario, ev["id"])
    assert (vuelto.actividad, vuelto.fecha_fin) == ("Inscripción", date(2026, 11, 4))


def test_deshacer_cambio_de_rol_y_paro(client, db, usuarios):
    admin, miembro = usuarios[RolEnum.ADMIN], usuarios[RolEnum.MIEMBRO]
    client.patch(f"/api/v1/usuarios/{miembro.id}", json={"rol": "SMOD"}, headers=auth(admin))
    assert _deshacer(client, admin, _ultimo(client, admin, tabla="usuarios")["id"]).status_code == 200
    db.expire_all()
    assert db.get(Usuario, miembro.id).rol == RolEnum.MIEMBRO

    _paro(client, usuarios[RolEnum.SMOD])
    assert len(client.get("/api/v1/informacion/avisos", headers=auth(miembro)).json()) == 1
    assert _deshacer(client, admin, _ultimo(client, admin, tabla="paros")["id"]).status_code == 200
    assert client.get("/api/v1/informacion/avisos", headers=auth(miembro)).json() == []


def test_sugerencias_quedan_en_el_historial_sin_deshacer(client, db, usuarios):
    admin = usuarios[RolEnum.ADMIN]
    db.add(RegistroCambios(tabla_afectada="sugerencias", registro_id=1, accion="rechazo", usuario_id=admin.id,
                           valor_anterior={"titulo": "x"}, valor_nuevo={"titulo": "x", "estado": "RECHAZADA"}))
    db.commit()
    cambio = _ultimo(client, admin)
    assert cambio["deshacible"] is False
    assert _deshacer(client, admin, cambio["id"]).status_code == 400


# ── Importar archivos ─────────────────────────────────────────────────────────

def test_importar_con_ia_y_deshacer(client, db, usuarios, monkeypatch):
    admin = usuarios[RolEnum.ADMIN]
    respuesta = """```json
    {"calendario": [{"fecha_inicio": "2026-11-09", "fecha_fin": "2026-11-13", "actividad": "Inscripción a electivas",
                     "categoria": "INSCRIPCION", "detalle": null},
                    {"fecha_inicio": "mañana", "actividad": "Mal formado"}],
     "mesas_fechas": [{"mesa": 1, "turno": 5, "cierre_inscripcion": "2026-11-18", "fecha_examen": "2026-11-23"}],
     "mesas_materias": [],
     "informacion": [{"tipo": "TRAMITE", "contenido": "Requisitos de la beca\\nPresentar DNI y certificado.",
                      "sin_vencimiento": true}]}
    ```"""
    monkeypatch.setattr("app.services.llm.completar", lambda *a, **k: respuesta)
    archivo = ("novedades.txt", "Texto del archivo con inscripciones, mesas y becas.".encode(), "text/plain")
    assert client.post("/api/v1/importar/analizar", files={"archivo": archivo},
                       headers=auth(usuarios[RolEnum.SMOD])).status_code == 403
    vista = client.post("/api/v1/importar/analizar", files={"archivo": archivo}, headers=auth(admin)).json()
    assert vista["metodo"] == "ia"
    assert [e["actividad"] for e in vista["calendario"]] == ["Inscripción a electivas"]
    assert any("Mal formado" in a for a in vista["avisos"])
    assert len(vista["mesas_fechas"]) == 1 and len(vista["informacion"]) == 1

    r = client.post("/api/v1/importar/confirmar", json=vista, headers=auth(admin))
    assert r.status_code == 201, r.text
    assert r.json()["creados"] == {"calendario_eventos": 1, "mesas_fechas": 1, "informacion": 1}
    info = db.query(Informacion).one()
    assert info.estado == E.CONFIRMADA and info.fecha_fin is None
    assert "novedades.txt" in _ultimo(client, admin)["resumen"]

    assert _deshacer(client, admin, r.json()["cambio_id"]).status_code == 200
    db.expire_all()
    assert db.query(EventoCalendario).count() == 0
    assert db.get(Informacion, info.id).estado == E.REEMPLAZADA


def test_importar_sin_ia_propone_el_texto(client, usuarios, monkeypatch):
    def falla(*a, **k):
        raise ValueError("sin IA")
    monkeypatch.setattr("app.services.llm.completar", falla)
    vista = client.post("/api/v1/importar/analizar", headers=auth(usuarios[RolEnum.ADMIN]),
                        files={"archivo": ("aviso.md", "Aviso: cambia el aula de Física I al 105".encode())}).json()
    assert vista["metodo"] == "texto"
    assert vista["informacion"][0]["contenido"].startswith("Aviso: cambia el aula")


def test_importar_horarios_reemplaza_la_comision(client, db, usuarios):
    admin = usuarios[RolEnum.ADMIN]
    db.add(HorarioClase(comision="1K01", anio=1, dia=1, inicio="08:00", fin="10:00", materia="Física I",
                        materia_norm="fisica i"))
    db.commit()
    bloque = {"comision": "1K01", "dia": 2, "inicio": "10:00", "fin": "12:00", "materia": "Química"}
    r = client.post("/api/v1/importar/confirmar", json={"archivo": "1K01.pdf", "horarios": [bloque]},
                    headers=auth(admin))
    assert r.json()["reemplazados"] == 1
    assert [h.materia for h in db.query(HorarioClase)] == ["Química"]
    _deshacer(client, admin, r.json()["cambio_id"])
    db.expire_all()
    assert [h.materia for h in db.query(HorarioClase)] == ["Física I"]
