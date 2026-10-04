"""
Criterios de aceptación del MVP (etapa 1):
  - Un correo no institucional no puede crear cuenta ni acceder.
  - Un MIEMBRO no puede acceder a funciones de MOD/ADMIN, ni llamando directo al backend.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.models.usuario import RolEnum
from conftest import PASSWORD, auth

NUEVO = {"nombre": "Ana Test", "password": "clave1234"}


# ── Correo institucional ──────────────────────────────────────────────────────

def test_admin_no_puede_crear_cuentas_desde_la_app(client, crear_usuario):
    admin = crear_usuario("admin@alu.frt.utn.edu.ar", RolEnum.ADMIN)
    r = client.post("/api/v1/usuarios/", json={**NUEVO, "email": "ana@alu.frt.utn.edu.ar"}, headers=auth(admin))
    assert r.status_code == 405


def test_correo_no_institucional_no_puede_loguearse_aunque_exista(client, crear_usuario):
    crear_usuario("viejo@admin.frt.utn.edu.ar", RolEnum.ADMIN)
    r = client.post("/api/v1/auth/login", json={"email": "viejo@admin.frt.utn.edu.ar", "password": PASSWORD})
    assert r.status_code == 401


def test_login_institucional_ignora_mayusculas(client, crear_usuario):
    crear_usuario("mauro.villagra1@alu.frt.utn.edu.ar")
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "Mauro.Villagra1@alu.frt.utn.edu.ar", "password": PASSWORD},
    )
    assert r.status_code == 200
    assert r.json()["usuario"]["rol"] == "MIEMBRO"


# ── RBAC en backend ───────────────────────────────────────────────────────────

ENDPOINTS_ADMIN = [
    ("get", "/api/v1/usuarios/", None),
    ("get", "/api/v1/usuarios/1", None),
    ("patch", "/api/v1/usuarios/1", {"rol": "MOD"}),
    ("post", "/api/v1/usuarios/1/ban", {"motivo": "spam"}),
    ("delete", "/api/v1/usuarios/1/ban", None),
    ("get", "/api/v1/admin/diagnostico", None),
]


@pytest.mark.parametrize("rol", [RolEnum.MIEMBRO, RolEnum.MOD])
@pytest.mark.parametrize("metodo,url,body", ENDPOINTS_ADMIN)
def test_miembro_y_mod_reciben_403_en_endpoints_admin(client, crear_usuario, rol, metodo, url, body):
    u = crear_usuario("u@alu.frt.utn.edu.ar", rol)
    r = getattr(client, metodo)(url, headers=auth(u), **({"json": body} if body else {}))
    assert r.status_code == 403


def test_miembro_no_puede_auto_ascenderse(client, crear_usuario):
    u = crear_usuario("u@alu.frt.utn.edu.ar")
    r = client.patch(f"/api/v1/usuarios/{u.id}", json={"rol": "MOD"}, headers=auth(u))
    assert r.status_code == 403


def test_sin_token_recibe_401(client, db):
    assert client.get("/api/v1/usuarios/").status_code == 401


def test_admin_cambia_rol_a_mod(client, crear_usuario):
    admin = crear_usuario("admin@alu.frt.utn.edu.ar", RolEnum.ADMIN)
    u = crear_usuario("u@alu.frt.utn.edu.ar")
    r = client.patch(f"/api/v1/usuarios/{u.id}", json={"rol": "MOD"}, headers=auth(admin))
    assert r.status_code == 200
    assert r.json()["rol"] == "MOD"


def test_admin_quita_rol_mod(client, crear_usuario):
    admin = crear_usuario("admin@alu.frt.utn.edu.ar", RolEnum.ADMIN)
    u = crear_usuario("u@alu.frt.utn.edu.ar", RolEnum.MOD)
    assert client.patch(f"/api/v1/usuarios/{u.id}", json={"rol": "MIEMBRO"}, headers=auth(admin)).json()["rol"] == "MIEMBRO"


def test_admin_no_puede_dar_rol_admin(client, crear_usuario):
    admin = crear_usuario("admin@alu.frt.utn.edu.ar", RolEnum.ADMIN)
    u = crear_usuario("u@alu.frt.utn.edu.ar")
    assert client.patch(f"/api/v1/usuarios/{u.id}", json={"rol": "ADMIN"}, headers=auth(admin)).status_code == 422


@pytest.mark.parametrize("metodo,sufijo,body", [
    ("patch", "", {"rol": "MIEMBRO"}), ("post", "/ban", {"motivo": "spam"}), ("delete", "/ban", None),
])
def test_cuentas_admin_no_se_tocan_desde_la_app(client, crear_usuario, metodo, sufijo, body):
    admin = crear_usuario("admin@alu.frt.utn.edu.ar", RolEnum.ADMIN)
    otro = crear_usuario("otro@alu.frt.utn.edu.ar", RolEnum.ADMIN)
    for objetivo in (admin, otro):
        r = getattr(client, metodo)(f"/api/v1/usuarios/{objetivo.id}{sufijo}", headers=auth(admin),
                                    **({"json": body} if body else {}))
        assert r.status_code == 403


def test_listar_y_buscar(client, crear_usuario):
    admin = crear_usuario("admin@alu.frt.utn.edu.ar", RolEnum.ADMIN)
    crear_usuario("ana@alu.frt.utn.edu.ar")
    crear_usuario("beto@alu.frt.utn.edu.ar", RolEnum.MOD)
    r = client.get("/api/v1/usuarios/?q=ANA", headers=auth(admin)).json()
    assert [u["email"] for u in r["items"]] == ["ana@alu.frt.utn.edu.ar"]
    r = client.get("/api/v1/usuarios/?rol=MOD", headers=auth(admin)).json()
    assert [u["email"] for u in r["items"]] == ["beto@alu.frt.utn.edu.ar"]


def _login(client, email):
    return client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})


def test_suspension_temporal(client, crear_usuario):
    admin = crear_usuario("admin@alu.frt.utn.edu.ar", RolEnum.ADMIN)
    u = crear_usuario("u@alu.frt.utn.edu.ar")
    r = client.post(f"/api/v1/usuarios/{u.id}/ban", json={"dias": 7, "motivo": "Spam en sugerencias"}, headers=auth(admin))
    assert r.json()["baneado_hasta"] and r.json()["activo"] is True
    r = _login(client, "u@alu.frt.utn.edu.ar")
    assert r.status_code == 403 and "suspendida hasta" in r.json()["detail"] and "Spam" in r.json()["detail"]
    assert client.get("/api/v1/auth/me", headers=auth(u)).status_code == 403  # token previo deja de servir

    client.delete(f"/api/v1/usuarios/{u.id}/ban", headers=auth(admin))
    assert _login(client, "u@alu.frt.utn.edu.ar").status_code == 200


def test_suspension_vencida_ya_no_bloquea(client, crear_usuario, db):
    u = crear_usuario("u@alu.frt.utn.edu.ar")
    u.baneado_hasta = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert _login(client, "u@alu.frt.utn.edu.ar").status_code == 200


def test_baneo_permanente(client, crear_usuario):
    admin = crear_usuario("admin@alu.frt.utn.edu.ar", RolEnum.ADMIN)
    u = crear_usuario("u@alu.frt.utn.edu.ar")
    r = client.post(f"/api/v1/usuarios/{u.id}/ban", json={"motivo": "Cuenta falsa"}, headers=auth(admin))
    assert r.json()["activo"] is False
    assert _login(client, "u@alu.frt.utn.edu.ar").json()["detail"] == "Tu cuenta fue suspendida: Cuenta falsa"
    # Con contraseña incorrecta no se revela nada
    r = client.post("/api/v1/auth/login", json={"email": "u@alu.frt.utn.edu.ar", "password": "otra12345"})
    assert r.status_code == 401


def test_usuario_inactivo_recibe_403(client, crear_usuario, db):
    u = crear_usuario("u@alu.frt.utn.edu.ar")
    u.activo = False
    db.commit()
    assert client.get("/api/v1/auth/me", headers=auth(u)).status_code == 403
