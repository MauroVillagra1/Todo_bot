"""Webhook de WhatsApp (Cloud API) y cadena de proveedores de IA."""
import hashlib
import hmac
import json

import httpx
import pytest

from app.core.config import get_settings
from app.models.informacion import Evidencia, Historial, Informacion, Verificacion
from app.models.ingesta import Chunk, Documento, Fuente, Publicacion, TipoFuenteEnum
from app.models.metrica import MetricaDiaria
from app.services import llm

SECRETO = "secreto-de-la-app"
MI_NUMERO = "5493815551111"


@pytest.fixture
def wa(db, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "WHATSAPP_APP_SECRET", SECRETO)
    monkeypatch.setattr(s, "WHATSAPP_VERIFY_TOKEN", "palabra-secreta")
    monkeypatch.setattr(s, "WHATSAPP_REENVIADORES", [MI_NUMERO])
    engine = db.get_bind()
    for m in (Fuente, Documento, Publicacion, Chunk, MetricaDiaria,
              Informacion, Evidencia, Verificacion, Historial):
        m.__table__.create(engine)
    f = Fuente(nombre="Canal WhatsApp 1", tipo=TipoFuenteEnum.WHATSAPP,
               url="https://whatsapp.com/channel/x", confiabilidad_base=50, activa=True, config={})
    db.add(f)
    db.commit()
    return f


def _enviar(client, mensajes, secreto=SECRETO):
    cuerpo = json.dumps({"entry": [{"changes": [{"value": {"messages": mensajes}}]}]}).encode()
    firma = "sha256=" + hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return client.post("/api/v1/webhooks/whatsapp", content=cuerpo,
                       headers={"X-Hub-Signature-256": firma, "Content-Type": "application/json"})


def _texto(numero, texto, id_="wamid.1"):
    return {"from": numero, "id": id_, "timestamp": "1790000000", "type": "text", "text": {"body": texto}}


def test_verificacion_inicial_de_meta(client, wa):
    ok = client.get("/api/v1/webhooks/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "palabra-secreta", "hub.challenge": "123"})
    assert (ok.status_code, ok.text) == (200, "123")
    mal = client.get("/api/v1/webhooks/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "otra", "hub.challenge": "123"})
    assert mal.status_code == 403


def test_reenvio_autorizado_se_guarda_no_confirmado(client, wa, db):
    r = _enviar(client, [_texto(MI_NUMERO, "Mesas de examen de diciembre: el 10/12 en el aula 212")])
    assert r.json() == {"guardados": 1, "duplicados": 0, "ignorados": 0}
    info = db.query(Informacion).one()
    assert (info.estado.value, info.tipo.value) == ("NO_CONFIRMADA", "EXAMEN")


def test_mismo_posteo_reenviado_dos_veces_es_duplicado(client, wa):
    texto = "Mesas de examen de diciembre: el 10/12 en el aula 212"
    _enviar(client, [_texto(MI_NUMERO, texto, "wamid.1")])
    assert _enviar(client, [_texto(MI_NUMERO, texto, "wamid.2")]).json()["duplicados"] == 1


def test_numero_no_autorizado_y_mensajes_cortos_se_ignoran(client, wa, db):
    r = _enviar(client, [_texto("5491100000000", "Mensaje de un desconocido con texto largo"),
                         _texto(MI_NUMERO, "hola")])
    assert r.json() == {"guardados": 0, "duplicados": 0, "ignorados": 2}
    assert db.query(Publicacion).count() == 0


def test_foto_con_pie_se_guarda(client, wa):
    foto = {"from": MI_NUMERO, "id": "wamid.3", "timestamp": "1790000000", "type": "image",
            "image": {"id": "123", "caption": "Inscripciones abiertas hasta el 15/10"}}
    assert _enviar(client, [foto]).json()["guardados"] == 1


def test_firma_invalida_se_rechaza(client, wa):
    assert _enviar(client, [_texto(MI_NUMERO, "Texto suficientemente largo")], secreto="otro").status_code == 401


def test_sin_configurar_responde_503(client, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "WHATSAPP_APP_SECRET", "")
    assert client.post("/api/v1/webhooks/whatsapp", content=b"{}").status_code == 503


# ── Cadena de proveedores de IA ───────────────────────────────────────────────

def test_si_un_proveedor_se_queda_sin_cupo_pasa_al_siguiente(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "OPENROUTER_API_KEY", "k1")
    monkeypatch.setattr(s, "GROQ_API_KEY", "k2")
    monkeypatch.setattr(s, "GEMINI_API_KEY", "")
    monkeypatch.setattr(s, "AI_MODEL", "modelo-a:free")
    monkeypatch.setattr(s, "AI_MODELOS_RESPALDO", [])
    monkeypatch.setattr(s, "AI_PROVEEDORES", ["groq|modelo-b", "gemini|modelo-c"])
    pedidos = []

    def post_falso(self, url, json, headers):
        pedidos.append((url, json["model"]))
        if "openrouter" in url:
            return httpx.Response(429, text="free-models-per-day")
        return httpx.Response(200, json={"choices": [{"message": {"content": " hola "}}]})

    monkeypatch.setattr(httpx.Client, "post", post_falso)
    assert llm.completar([{"role": "user", "content": "x"}]) == "hola"
    # Gemini no se intenta: no tiene key
    assert [m for _, m in pedidos] == ["modelo-a:free", "modelo-b"]
