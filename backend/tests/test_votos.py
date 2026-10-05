"""Votos sobre las respuestas: puntaje acotado, "no me sirvió" busca otra fuente, reportes para MOD."""
import pytest

from app.models.cache import CacheRespuesta
from app.models.chat import MensajeChat
from app.models.informacion import Evidencia, Informacion, Verificacion
from app.models.ingesta import Documento, Fuente, Publicacion
from app.models.metrica import MetricaDiaria
from app.models.usuario import RolEnum
from app.models.voto import Voto
from app.services import chat_service
from conftest import auth


@pytest.fixture
def tablas(db):
    engine = db.get_bind()
    for m in (Fuente, Documento, Publicacion, Informacion, Evidencia, Verificacion, MensajeChat, Voto,
              CacheRespuesta, MetricaDiaria):
        m.__table__.create(engine)
    for n in (1, 2, 3):
        db.add(Informacion(id=n, tipo="BECA", titulo=f"Beca {n}", contenido="x", estado="CONFIRMADA", confianza=100))
    db.commit()
    return db


@pytest.fixture
def respuestas(monkeypatch):
    """El RAG simulado: la primera respuesta usa las informaciones 1 y 2; sin ellas, la 3."""
    llamadas = []

    def responder(db, pregunta, historial, excluir=None):
        llamadas.append(excluir)
        ids = [3] if excluir else [1, 2]
        return {"respuesta": f"Respuesta con {ids}", "estado": "CONFIRMADA", "fecha_informacion": None,
                "desde_cache": False,
                "fuentes": [{"numero": n, "informacion_id": i, "titulo": f"Beca {i}", "url": "https://x",
                             "fuente": "F", "estado": "CONFIRMADA"} for n, i in enumerate(ids, 1)]}

    monkeypatch.setattr(chat_service, "responder", responder)
    return llamadas


def _preguntar(client, usuario, texto="¿Hay becas?"):
    r = client.post("/api/v1/chat/", json={"mensaje": texto}, headers=auth(usuario))
    assert r.status_code == 200
    return r.json()


def _puntajes(db):
    db.expire_all()
    return {i.id: i.puntaje_votos for i in db.query(Informacion).order_by(Informacion.id)}


def test_la_respuesta_trae_mensaje_id_y_guarda_las_fuentes(client, tablas, crear_usuario, respuestas):
    yo = crear_usuario("a@alu.frt.utn.edu.ar")
    r = _preguntar(client, yo)
    assert r["mensaje_id"] and r["fuentes"][0]["informacion_id"] == 1
    assert tablas.get(MensajeChat, r["mensaje_id"]).informacion_ids == [1, 2]


def test_votar_ajusta_el_puntaje_y_se_puede_cambiar(client, tablas, crear_usuario, respuestas):
    yo = crear_usuario("a@alu.frt.utn.edu.ar")
    mid = _preguntar(client, yo)["mensaje_id"]
    client.post(f"/api/v1/chat/mensajes/{mid}/voto", json={"valor": 1}, headers=auth(yo))
    assert _puntajes(tablas) == {1: 1, 2: 1, 3: 0}
    # Cambiar el voto reemplaza el anterior (no se suma)
    client.post(f"/api/v1/chat/mensajes/{mid}/voto", json={"valor": -1, "motivo": "INCORRECTO",
                                                            "comentario": "La fecha está mal"}, headers=auth(yo))
    assert _puntajes(tablas) == {1: -2, 2: -2, 3: 0}
    assert tablas.query(Voto).count() == 1


def test_no_me_sirvio_busca_sin_esas_fuentes(client, tablas, crear_usuario, respuestas):
    yo = crear_usuario("a@alu.frt.utn.edu.ar")
    mid = _preguntar(client, yo)["mensaje_id"]
    r = client.post(f"/api/v1/chat/mensajes/{mid}/voto", json={"valor": -1}, headers=auth(yo)).json()
    assert r["motivo"] == "NO_SIRVE"
    assert respuestas[-1] == [1, 2]  # se excluyeron las fuentes de la primera respuesta
    alt = r["alternativa"]
    assert alt["respuesta"] == "Respuesta con [3]" and alt["mensaje_id"] != mid
    assert tablas.get(MensajeChat, alt["mensaje_id"]).informacion_ids == [3]


def test_no_se_vota_la_respuesta_de_otro(client, tablas, crear_usuario, respuestas):
    a = crear_usuario("a@alu.frt.utn.edu.ar")
    b = crear_usuario("b@alu.frt.utn.edu.ar")
    mid = _preguntar(client, a)["mensaje_id"]
    assert client.post(f"/api/v1/chat/mensajes/{mid}/voto", json={"valor": 1}, headers=auth(b)).status_code == 404


def test_mod_revisa_un_reporte_y_oculta_el_dato(client, tablas, crear_usuario, respuestas):
    alumno = crear_usuario("a@alu.frt.utn.edu.ar")
    mod = crear_usuario("m@doc.frt.utn.edu.ar", RolEnum.MOD)
    mid = _preguntar(client, alumno)["mensaje_id"]
    client.post(f"/api/v1/chat/mensajes/{mid}/voto", json={"valor": -1, "motivo": "INCORRECTO",
                                                            "comentario": "La beca 2 cerró"}, headers=auth(alumno))
    assert client.get("/api/v1/reportes/", headers=auth(alumno)).status_code == 403

    [rep] = client.get("/api/v1/reportes/", headers=auth(mod)).json()
    assert rep["pregunta"] == "¿Hay becas?" and rep["comentario"] == "La beca 2 cerró"
    assert [i["id"] for i in rep["informaciones"]] == [1, 2]

    r = client.post(f"/api/v1/reportes/{rep['id']}/resolver", json={"accion": "ocultar", "informacion_ids": [2]},
                    headers=auth(mod))
    assert r.status_code == 204
    tablas.expire_all()
    assert tablas.get(Informacion, 2).estado.value == "DESACTUALIZADA"
    assert tablas.get(Informacion, 1).estado.value == "CONFIRMADA"
    assert client.get("/api/v1/reportes/", headers=auth(mod)).json() == []
    assert client.get("/api/v1/reportes/resumen", headers=auth(mod)).json() == {
        "positivos": 0, "negativos": 1, "reportes_pendientes": 0}


def test_no_me_sirvio_no_es_reporte(client, tablas, crear_usuario, respuestas):
    alumno = crear_usuario("a@alu.frt.utn.edu.ar")
    mod = crear_usuario("m@doc.frt.utn.edu.ar", RolEnum.MOD)
    mid = _preguntar(client, alumno)["mensaje_id"]
    client.post(f"/api/v1/chat/mensajes/{mid}/voto", json={"valor": -1}, headers=auth(alumno))
    assert client.get("/api/v1/reportes/", headers=auth(mod)).json() == []
