"""
Sesiones con JWT (core/tokens.py): fábrica de tokens, renovación, revocación y fuerza bruta.
"""
from datetime import timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.tokens import TokenFactory, TokenInvalido
from conftest import PASSWORD, auth

EMAIL = "ana@alu.frt.utn.edu.ar"


def _login(client, password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": EMAIL, "password": password})


# ── Fábrica de tokens ─────────────────────────────────────────────────────────

def test_la_fabrica_crea_cada_tipo_con_sus_claims(crear_usuario):
    u = crear_usuario(EMAIL)
    access = TokenFactory.validar(TokenFactory.crear("access", u), "access")
    refresh = TokenFactory.validar(TokenFactory.crear("refresh", u), "refresh")
    assert (access["sub"], access["typ"], access["rol"], access["ver"]) == (str(u.id), "access", "MIEMBRO", 0)
    assert refresh["typ"] == "refresh" and "rol" not in refresh
    assert refresh["exp"] - refresh["iat"] > access["exp"] - access["iat"]
    assert access["jti"] != TokenFactory.validar(TokenFactory.crear("access", u), "access")["jti"]


def test_un_tipo_no_sirve_como_otro(crear_usuario):
    u = crear_usuario(EMAIL)
    with pytest.raises(TokenInvalido):
        TokenFactory.validar(TokenFactory.crear("refresh", u), "access")
    with pytest.raises(ValueError):
        TokenFactory.crear("superusuario", u)


@pytest.mark.parametrize("cambio", [
    {"aud": "otra-app"}, {"iss": "otro-emisor"}, {"exp": -60},
])
def test_token_con_datos_ajenos_o_vencido_se_rechaza(crear_usuario, cambio):
    u = crear_usuario(EMAIL)
    claims = TokenFactory.validar(TokenFactory.crear("access", u), "access")
    if "exp" in cambio:
        cambio = {"exp": claims["iat"] + cambio["exp"]}
    falso = jwt.encode({**claims, **cambio}, get_settings().SECRET_KEY, algorithm="HS256")
    with pytest.raises(TokenInvalido):
        TokenFactory.validar(falso, "access")


def test_token_firmado_con_otra_clave_o_sin_firma_se_rechaza(crear_usuario):
    u = crear_usuario(EMAIL)
    claims = TokenFactory.validar(TokenFactory.crear("access", u), "access")
    for falso in (jwt.encode(claims, "otra-clave-cualquiera-de-32-bytes!!", algorithm="HS256"),
                  jwt.encode(claims, None, algorithm="none")):
        with pytest.raises(TokenInvalido):
            TokenFactory.validar(falso, "access")


# ── Login, renovación y cierre de sesión ──────────────────────────────────────

def test_login_devuelve_access_y_refresh(client, crear_usuario):
    crear_usuario(EMAIL)
    data = _login(client).json()
    assert data["access_token"] and data["refresh_token"] and data["token_type"] == "bearer"
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert r.status_code == 200 and r.headers["Cache-Control"] == "no-store"


def test_el_refresh_no_sirve_para_entrar_pero_renueva_la_sesion(client, crear_usuario):
    crear_usuario(EMAIL)
    refresh = _login(client).json()["refresh_token"]
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh}"}).status_code == 401
    nuevo = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert nuevo.status_code == 200
    assert client.get("/api/v1/auth/me",
                      headers={"Authorization": f"Bearer {nuevo.json()['access_token']}"}).status_code == 200


def test_logout_revoca_todos_los_tokens(client, crear_usuario):
    crear_usuario(EMAIL)
    sesion = _login(client).json()
    cabecera = {"Authorization": f"Bearer {sesion['access_token']}"}
    assert client.post("/api/v1/auth/logout", headers=cabecera).status_code == 200
    assert client.get("/api/v1/auth/me", headers=cabecera).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": sesion["refresh_token"]}).status_code == 401


def test_cuenta_suspendida_no_renueva(client, crear_usuario, db):
    u = crear_usuario(EMAIL)
    refresh = _login(client).json()["refresh_token"]
    u.activo = False
    db.commit()
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 403


# ── Fuerza bruta ──────────────────────────────────────────────────────────────

def test_cinco_errores_bloquean_el_login_aunque_despues_acierte(client, crear_usuario, db):
    u = crear_usuario(EMAIL)
    for _ in range(5):
        assert _login(client, "mal12345").status_code == 401
    assert _login(client).status_code == 429
    # Pasado el bloqueo vuelve a entrar y el contador se reinicia
    u.bloqueado_hasta = u.bloqueado_hasta - timedelta(minutes=16)
    db.commit()
    assert _login(client).status_code == 200
    assert u.intentos_fallidos == 0


def test_email_inexistente_da_el_mismo_error(client, crear_usuario):
    crear_usuario(EMAIL)
    r = client.post("/api/v1/auth/login", json={"email": "nadie@alu.frt.utn.edu.ar", "password": PASSWORD})
    assert r.status_code == 401 and r.json()["detail"] == _login(client, "mal12345").json()["detail"]


def test_encabezados_de_seguridad(client, crear_usuario):
    u = crear_usuario(EMAIL)
    r = client.get("/api/v1/auth/me", headers=auth(u))
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "max-age" in r.headers["Strict-Transport-Security"]
