"""
Registro público con código al mail institucional y recuperación de contraseña.
"""
import re
from datetime import datetime, timedelta, timezone

import pytest

from app.models.codigo import CodigoVerificacion
from app.models.usuario import Usuario
from app.routers import auth as auth_router
from app.services.email import EmailNoConfigurado
from conftest import PASSWORD

ALU = "ana.perez@alu.frt.utn.edu.ar"
DATOS = {"nombre": "Ana Pérez", "email": ALU, "password": "clave1234"}


@pytest.fixture
def mails(db, monkeypatch):
    CodigoVerificacion.__table__.create(db.get_bind())
    enviados = []
    monkeypatch.setattr(auth_router, "enviar_email",
                        lambda dest, asunto, texto: enviados.append((dest, re.search(r"\d{6}", texto)[0])))
    return enviados


def _sin_espera(db):
    """Simula que pasó más de un minuto desde el último código."""
    for c in db.query(CodigoVerificacion):
        c.creado_en = datetime.now(timezone.utc) - timedelta(minutes=2)
    db.commit()


def test_registro_completo_crea_miembro_y_devuelve_token(client, db, mails):
    r = client.post("/api/v1/auth/registro", json=DATOS)
    assert r.status_code == 200, r.text
    assert db.query(Usuario).count() == 0  # todavía no existe
    destino, codigo = mails[-1]
    assert destino == ALU

    r = client.post("/api/v1/auth/registro/verificar", json={"email": ALU, "codigo": codigo})
    assert r.status_code == 201, r.text
    assert r.json()["usuario"]["rol"] == "MIEMBRO" and r.json()["access_token"]
    assert client.post("/api/v1/auth/login", json={"email": ALU, "password": "clave1234"}).status_code == 200
    # el código ya no sirve
    assert client.post("/api/v1/auth/registro/verificar", json={"email": ALU, "codigo": codigo}).status_code == 400


def test_docentes_tambien_pueden_registrarse(client, mails):
    r = client.post("/api/v1/auth/registro", json={**DATOS, "email": "jgomez@doc.frt.utn.edu.ar"})
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("email", ["ana@gmail.com", "ana@frt.utn.edu.ar", "ana@alu.frt.utn.edu.ar.evil.com",
                                   "ana@admin.frt.utn.edu.ar"])
def test_solo_dominios_alu_y_doc(client, mails, email):
    assert client.post("/api/v1/auth/registro", json={**DATOS, "email": email}).status_code == 422
    assert mails == []


def test_cuenta_existente_no_se_puede_registrar(client, mails, crear_usuario):
    crear_usuario(ALU)
    r = client.post("/api/v1/auth/registro", json={**DATOS, "email": ALU.upper()})
    assert r.status_code == 409
    assert "Ya existe" in r.json()["detail"]
    assert mails == []


def test_codigo_incorrecto_agota_intentos(client, db, mails):
    client.post("/api/v1/auth/registro", json=DATOS)
    codigo = mails[-1][1]
    malo = "000000" if codigo != "000000" else "111111"
    for _ in range(auth_router.MAX_INTENTOS):
        r = client.post("/api/v1/auth/registro/verificar", json={"email": ALU, "codigo": malo})
        assert r.status_code == 400
    # ni el correcto sirve después de agotar los intentos
    r = client.post("/api/v1/auth/registro/verificar", json={"email": ALU, "codigo": codigo})
    assert r.status_code == 400 and "Demasiados intentos" in r.json()["detail"]
    assert db.query(Usuario).count() == 0


def test_codigo_vencido(client, db, mails):
    client.post("/api/v1/auth/registro", json=DATOS)
    db.query(CodigoVerificacion).one().expira_en = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    r = client.post("/api/v1/auth/registro/verificar", json={"email": ALU, "codigo": mails[-1][1]})
    assert r.status_code == 400 and "venció" in r.json()["detail"]


def test_esperar_entre_codigos_y_solo_vale_el_ultimo(client, db, mails):
    client.post("/api/v1/auth/registro", json=DATOS)
    assert client.post("/api/v1/auth/registro", json=DATOS).status_code == 429
    _sin_espera(db)
    assert client.post("/api/v1/auth/registro", json=DATOS).status_code == 200
    viejo, nuevo = mails[0][1], mails[1][1]
    if viejo != nuevo:
        assert client.post("/api/v1/auth/registro/verificar", json={"email": ALU, "codigo": viejo}).status_code == 400
    assert client.post("/api/v1/auth/registro/verificar", json={"email": ALU, "codigo": nuevo}).status_code == 201


def test_sin_smtp_en_produccion_no_guarda_codigo(client, db, mails, monkeypatch):
    def falla(*_):
        raise EmailNoConfigurado()
    monkeypatch.setattr(auth_router, "enviar_email", falla)
    assert client.post("/api/v1/auth/registro", json=DATOS).status_code == 503
    assert db.query(CodigoVerificacion).count() == 0


def test_recuperar_contrasena_con_codigo(client, mails, crear_usuario):
    crear_usuario(ALU)
    r = client.post("/api/v1/auth/recuperar", json={"email": ALU})
    assert r.status_code == 200
    codigo = mails[-1][1]

    r = client.post("/api/v1/auth/recuperar/confirmar",
                    json={"email": ALU, "codigo": codigo, "password": "nueva12345"})
    assert r.status_code == 200, r.text
    assert client.post("/api/v1/auth/login", json={"email": ALU, "password": PASSWORD}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": ALU, "password": "nueva12345"}).status_code == 200


def test_recuperar_no_revela_si_la_cuenta_existe(client, mails, crear_usuario):
    crear_usuario(ALU)
    existe = client.post("/api/v1/auth/recuperar", json={"email": ALU})
    no_existe = client.post("/api/v1/auth/recuperar", json={"email": "nadie@alu.frt.utn.edu.ar"})
    assert existe.json() == no_existe.json()
    assert [d for d, _ in mails] == [ALU]


def test_recuperar_exige_contrasena_valida(client, mails, crear_usuario):
    crear_usuario(ALU)
    client.post("/api/v1/auth/recuperar", json={"email": ALU})
    r = client.post("/api/v1/auth/recuperar/confirmar",
                    json={"email": ALU, "codigo": mails[-1][1], "password": "sinnumeros"})
    assert r.status_code == 422
