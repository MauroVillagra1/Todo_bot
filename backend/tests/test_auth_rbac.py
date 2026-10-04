"""
Criterios de aceptación del MVP (etapa 1):
  - Un correo no institucional no puede crear cuenta ni acceder.
  - Un MIEMBRO no puede acceder a funciones de MOD/ADMIN, ni llamando directo al backend.
"""
import pytest

from app.models.usuario import RolEnum
from conftest import PASSWORD, auth

NUEVO = {"nombre": "Ana Test", "password": "clave1234"}


# ── Correo institucional ──────────────────────────────────────────────────────

def test_admin_no_puede_crear_cuenta_con_correo_no_institucional(client, crear_usuario):
    admin = crear_usuario("admin@alu.frt.utn.edu.ar", RolEnum.ADMIN)
    for email in ("ana@gmail.com", "ana@frt.utn.edu.ar", "ana@alu.frt.utn.edu.ar.evil.com"):
        r = client.post("/api/v1/usuarios/", json={**NUEVO, "email": email}, headers=auth(admin))
        assert r.status_code == 422, email


def test_admin_crea_cuenta_institucional_como_miembro_y_en_minusculas(client, crear_usuario):
    admin = crear_usuario("admin@alu.frt.utn.edu.ar", RolEnum.ADMIN)
    r = client.post(
        "/api/v1/usuarios/",
        json={**NUEVO, "email": "Ana.Test1@ALU.frt.utn.edu.ar"},
        headers=auth(admin),
    )
    assert r.status_code == 201
    assert r.json()["email"] == "ana.test1@alu.frt.utn.edu.ar"
    assert r.json()["rol"] == "MIEMBRO"


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


def test_no_se_puede_cambiar_email_a_uno_no_institucional(client, crear_usuario):
    admin = crear_usuario("admin@alu.frt.utn.edu.ar", RolEnum.ADMIN)
    u = crear_usuario("ana@alu.frt.utn.edu.ar")
    r = client.patch(f"/api/v1/usuarios/{u.id}", json={"email": "ana@gmail.com"}, headers=auth(admin))
    assert r.status_code == 422


# ── RBAC en backend ───────────────────────────────────────────────────────────

ENDPOINTS_ADMIN = [
    ("get", "/api/v1/usuarios/", None),
    ("get", "/api/v1/usuarios/1", None),
    ("post", "/api/v1/usuarios/", {**NUEVO, "email": "x@alu.frt.utn.edu.ar"}),
    ("patch", "/api/v1/usuarios/1", {"rol": "ADMIN"}),
]


@pytest.mark.parametrize("rol", [RolEnum.MIEMBRO, RolEnum.MOD])
@pytest.mark.parametrize("metodo,url,body", ENDPOINTS_ADMIN)
def test_miembro_y_mod_reciben_403_en_endpoints_admin(client, crear_usuario, rol, metodo, url, body):
    u = crear_usuario("u@alu.frt.utn.edu.ar", rol)
    r = getattr(client, metodo)(url, headers=auth(u), **({"json": body} if body else {}))
    assert r.status_code == 403


def test_miembro_no_puede_auto_ascenderse(client, crear_usuario):
    u = crear_usuario("u@alu.frt.utn.edu.ar")
    r = client.patch(f"/api/v1/usuarios/{u.id}", json={"rol": "ADMIN"}, headers=auth(u))
    assert r.status_code == 403


def test_sin_token_recibe_401(client, db):
    assert client.get("/api/v1/usuarios/").status_code == 401


def test_admin_cambia_rol_a_mod(client, crear_usuario):
    admin = crear_usuario("admin@alu.frt.utn.edu.ar", RolEnum.ADMIN)
    u = crear_usuario("u@alu.frt.utn.edu.ar")
    r = client.patch(f"/api/v1/usuarios/{u.id}", json={"rol": "MOD"}, headers=auth(admin))
    assert r.status_code == 200
    assert r.json()["rol"] == "MOD"


@pytest.mark.parametrize("cambio", [{"activo": False}, {"rol": "MIEMBRO"}])
def test_admin_no_puede_quitarse_acceso_a_si_mismo(client, crear_usuario, cambio):
    admin = crear_usuario("admin@alu.frt.utn.edu.ar", RolEnum.ADMIN)
    r = client.patch(f"/api/v1/usuarios/{admin.id}", json=cambio, headers=auth(admin))
    assert r.status_code == 400


def test_usuario_inactivo_recibe_403(client, crear_usuario, db):
    u = crear_usuario("u@alu.frt.utn.edu.ar")
    u.activo = False
    db.commit()
    assert client.get("/api/v1/auth/me", headers=auth(u)).status_code == 403
