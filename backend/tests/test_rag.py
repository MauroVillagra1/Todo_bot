"""
RAG (etapa 6). Criterios de aceptación:
  - Cada respuesta factual muestra estado, fuente(s) y fecha, y nunca cita fuentes inexistentes.
  - Sin evidencia suficiente, el chatbot lo indica en lugar de inventar (y no llama al LLM).
La búsqueda full-text es de Postgres: acá se reemplaza por resultados fijos.
"""
from datetime import datetime, timezone

import pytest

from app.models.cache import CacheRespuesta
from app.models.chat import MensajeChat
from app.models.informacion import Informacion
from app.models.ingesta import Chunk
from app.models.metrica import MetricaDiaria
from app.models.usuario import RolEnum
from app.rag import answer
from app.rag.search import Resultado
from conftest import auth


def _r(n, estado="CONFIRMADA", dia=20):
    return Resultado(chunk_id=n, informacion_id=n, titulo=f"Aviso {n}", texto=f"Texto {n}",
                     url=f"https://sistemasfrtutn.ar/{n}", fuente="Sistemas FRT",
                     fecha=datetime(2026, 11, dia, tzinfo=timezone.utc), estado=estado, puntaje=1.0)


@pytest.fixture
def rag(db, monkeypatch):
    engine = db.get_bind()
    for m in (MensajeChat, CacheRespuesta, MetricaDiaria, Informacion, Chunk):
        m.__table__.create(engine)
    llamadas = {"llm": [], "busquedas": []}
    estado = {"resultados": [_r(1), _r(2, "PROBABLE", dia=25)], "texto": "Hasta el 28/11 [1]."}

    def buscar_falso(_db, texto):
        llamadas["busquedas"].append(texto)
        return estado["resultados"]

    def completar_falso(mensajes, max_tokens):
        llamadas["llm"].append(mensajes)
        if isinstance(estado["texto"], Exception):
            raise estado["texto"]
        return estado["texto"]

    monkeypatch.setattr(answer, "buscar", buscar_falso)
    monkeypatch.setattr(answer.llm, "completar", completar_falso)
    # El rate limit usa now() de Postgres: en SQLite no aplica
    monkeypatch.setattr("app.routers.chat.verificar_limite", lambda u, d: None)
    return llamadas, estado


def _preguntar(client, usuario, texto, conv=None):
    r = client.post("/api/v1/chat/", json={"mensaje": texto, "conversacion_id": conv}, headers=auth(usuario))
    assert r.status_code == 200, r.text
    return r.json()


def test_respuesta_con_estado_fuentes_y_fecha_de_la_base(client, crear_usuario, rag):
    u = crear_usuario("u@alu.frt.utn.edu.ar", RolEnum.MIEMBRO)
    data = _preguntar(client, u, "¿Hasta cuándo me inscribo a mesas?")

    assert data["respuesta"] == "Hasta el 28/11 [1]."
    assert data["estado"] == "CONFIRMADA"
    assert data["fecha_informacion"] == "2026-11-20"
    assert [(f["numero"], f["url"]) for f in data["fuentes"]] == [(1, "https://sistemasfrtutn.ar/1")]


def test_citas_inexistentes_se_descartan(client, crear_usuario, rag):
    _, estado = rag
    estado["texto"] = "Es el 28/11 [1] según la resolución 123 [7]."
    data = _preguntar(client, crear_usuario("u@alu.frt.utn.edu.ar"), "¿Fecha?")

    assert "[7]" not in data["respuesta"]
    assert [f["numero"] for f in data["fuentes"]] == [1]


def test_estado_es_el_peor_entre_las_fuentes_citadas(client, crear_usuario, rag):
    _, estado = rag
    estado["texto"] = "Abre el 20/11 [1] y cierra el 25/11 [2]."
    data = _preguntar(client, crear_usuario("u@alu.frt.utn.edu.ar"), "¿Fechas?")
    assert data["estado"] == "PROBABLE"
    assert data["fecha_informacion"] == "2026-11-25"


def test_sin_citas_queda_no_confirmada(client, crear_usuario, rag):
    _, estado = rag
    estado["texto"] = "Creo que es en noviembre."
    data = _preguntar(client, crear_usuario("u@alu.frt.utn.edu.ar"), "¿Cuándo?")
    assert data["estado"] == "NO_CONFIRMADA"
    assert len(data["fuentes"]) == 2  # se muestran las consultadas


def test_sin_evidencia_no_llama_al_llm(client, crear_usuario, rag):
    llamadas, estado = rag
    estado["resultados"] = []
    data = _preguntar(client, crear_usuario("u@alu.frt.utn.edu.ar"), "¿Quién ganó el mundial?")

    assert data["respuesta"] == answer.SIN_EVIDENCIA
    assert (data["estado"], data["fuentes"]) == ("NO_CONFIRMADA", [])
    assert llamadas["llm"] == []


def test_segunda_pregunta_igual_sale_de_cache_sin_llm(client, crear_usuario, rag):
    llamadas, _ = rag
    u = crear_usuario("u@alu.frt.utn.edu.ar")
    primera = _preguntar(client, u, "¿Hasta cuándo me inscribo?")
    segunda = _preguntar(client, u, "  hasta cuando me INSCRIBO ")

    assert (primera["desde_cache"], segunda["desde_cache"]) == (False, True)
    assert segunda["respuesta"] == primera["respuesta"]
    assert len(llamadas["llm"]) == 1


def test_cache_se_invalida_si_cambian_los_datos(client, crear_usuario, rag, db):
    llamadas, _ = rag
    u = crear_usuario("u@alu.frt.utn.edu.ar")
    _preguntar(client, u, "¿Becas?")
    db.add(Informacion(tipo="BECA", titulo="Nueva beca", contenido="x", estado="CONFIRMADA", confianza=100))
    db.commit()
    assert _preguntar(client, u, "¿Becas?")["desde_cache"] is False
    assert len(llamadas["llm"]) == 2


def test_seguimiento_usa_historial_y_no_cache(client, crear_usuario, rag):
    llamadas, _ = rag
    u = crear_usuario("u@alu.frt.utn.edu.ar")
    conv = _preguntar(client, u, "¿Mesas de diciembre?")["conversacion_id"]
    _preguntar(client, u, "¿y cuándo cierra?", conv)

    assert "Mesas de diciembre" in llamadas["busquedas"][-1]  # busca con la pregunta anterior
    assert [m["role"] for m in llamadas["llm"][-1]] == ["system", "user", "assistant", "user"]


def test_si_el_llm_falla_muestra_evidencias(client, crear_usuario, rag):
    _, estado = rag
    estado["texto"] = RuntimeError("429 rate limit")
    data = _preguntar(client, crear_usuario("u@alu.frt.utn.edu.ar"), "¿Mesas?")
    assert data["respuesta"] == answer.SIN_LLM
    assert len(data["fuentes"]) == 2
