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
        m.__table__.create(engine, checkfirst=True)
    llamadas = {"llm": [], "busquedas": []}
    estado = {"resultados": [_r(1), _r(2, "PROBABLE", dia=25)], "texto": "Hasta el 28/11 [1]."}

    def buscar_falso(_db, texto, excluir=None, flexible=True):
        llamadas["busquedas"].append(texto)
        return estado["resultados"]

    def completar_falso(mensajes, max_tokens):
        llamadas["llm"].append(mensajes)
        if isinstance(estado["texto"], Exception):
            raise estado["texto"]
        return estado["texto"]

    monkeypatch.setattr(answer, "buscar", buscar_falso)
    monkeypatch.setattr(answer, "responder_horario", lambda db, p, a="": None)  # ver test_horarios_sql
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


def test_el_chat_guarda_contexto_solo_para_los_seguimientos(client, crear_usuario, rag):
    llamadas, _ = rag
    u = crear_usuario("u@alu.frt.utn.edu.ar")
    conv = _preguntar(client, u, "¿Inscripción a la beca de transporte?")["conversacion_id"]

    # Cambio de tema: se responde sola (sin mezclar con lo anterior)
    _preguntar(client, u, "¿Becas abiertas?", conv)
    assert llamadas["busquedas"][-1] == "¿Becas abiertas?"
    assert [m["role"] for m in llamadas["llm"][-1]] == ["system", "user"]

    # Seguimiento: usa la conversación para entender a qué se refiere
    _preguntar(client, u, "¿y cuándo cierra?", conv)
    assert "Becas abiertas" in llamadas["busquedas"][-2]
    assert [m["role"] for m in llamadas["llm"][-1]] == ["system", "user", "assistant", "user", "assistant", "user"]


def test_si_el_llm_falla_y_no_hay_frases_relevantes_muestra_evidencias(client, crear_usuario, rag):
    _, estado = rag
    estado["texto"] = RuntimeError("429 rate limit")
    data = _preguntar(client, crear_usuario("u@alu.frt.utn.edu.ar"), "¿Mesas?")
    assert data["respuesta"] == answer.SIN_LLM
    assert len(data["fuentes"]) == 2


def test_si_el_llm_falla_responde_con_extracto_textual(client, crear_usuario, rag):
    llamadas, estado = rag
    estado["texto"] = RuntimeError("429 free-models-per-day")
    r1 = _r(1)
    r1.titulo, r1.texto = "Inscripciones a mesas", (
        "Inscripciones a mesas\nLa inscripción a mesas de examen de diciembre es del 25/11 al 28/11 "
        "por autogestión. El aula se informa después.")
    estado["resultados"] = [r1, _r(2)]
    u = crear_usuario("u@alu.frt.utn.edu.ar")

    data = _preguntar(client, u, "¿Hasta cuándo es la inscripción a mesas de examen?")
    assert "del 25/11 al 28/11" in data["respuesta"] and "[1]" in data["respuesta"]
    assert data["estado"] == "CONFIRMADA"
    assert [f["numero"] for f in data["fuentes"]] == [1]
    # No se cachea: cuando vuelva la IA, la misma pregunta se responde completa
    estado["texto"] = "Hasta el 28/11 [1]."
    assert _preguntar(client, u, "¿Hasta cuándo es la inscripción a mesas de examen?")["respuesta"] == "Hasta el 28/11 [1]."


def test_la_ia_recibe_la_fecha_de_hoy_para_resolver_proximo(client, crear_usuario, rag, monkeypatch):
    llamadas, _ = rag
    monkeypatch.setattr(answer, "_ahora", lambda: datetime(2026, 10, 4, 2, 0, tzinfo=timezone.utc))
    _preguntar(client, crear_usuario("u@alu.frt.utn.edu.ar"), "¿Cuándo es la próxima mesa?")

    assert "FECHA DE HOY: 03/10/2026" in llamadas["llm"][-1][0]["content"]  # hora de Argentina


def test_citas_agrupadas_se_reconocen():
    from datetime import datetime
    from app.rag.answer import armar_respuesta
    from app.rag.search import Resultado
    rs = [Resultado(i, i, f"t{i}", "x", "https://x", "F", datetime(2026, 1, 1), "CONFIRMADA", 1.0) for i in (1, 2, 3)]
    r = armar_respuesta("Es una competencia [1, 2].", rs)
    assert r["respuesta"] == "Es una competencia [1][2]."
    assert [f["numero"] for f in r["fuentes"]] == [1, 2] and r["estado"] == "CONFIRMADA"


def test_fusion_prioriza_lo_que_aparece_en_las_dos_busquedas():
    from app.rag.search import _fusionar

    precisos = [{"chunk_id": 1}, {"chunk_id": 2}]
    semanticos = [{"chunk_id": 3}, {"chunk_id": 2}]
    assert [f["chunk_id"] for f in _fusionar(precisos, semanticos)] == [2, 1, 3]


def test_fichas_del_mismo_tipo_no_ocupan_todos_los_lugares():
    from app.rag.search import MAX_POR_TIPO_DE_FICHA, _mejores

    fichas = [{"chunk_id": i, "informacion_id": i, "titulo": f"Aula virtual: Materia {i} — Tecnicatura",
               "texto": "", "url": "", "fuente": "", "fecha": None, "estado": "CONFIRMADA", "puntaje": 1.0}
              for i in range(6)]
    resumen = {**fichas[0], "chunk_id": 99, "informacion_id": 99, "titulo": "Campus Virtual: Tecnicaturas"}
    titulos = [r.titulo for r in _mejores(fichas + [resumen], 0.0, 5)]
    assert len(titulos) == MAX_POR_TIPO_DE_FICHA + 1
    assert titulos[-1] == "Campus Virtual: Tecnicaturas"


def test_fechas_pasadas_se_marcan_para_la_ia():
    from datetime import date

    from app.rag.answer import marcar_fechas_pasadas

    texto = "Inscripción hasta el 11 de Octubre. Estancia del 2 al 27 de febrero de 2027. Cierre 01/09/2026. Abierto 24/7."
    marcado = marcar_fechas_pasadas(texto, date(2026, 9, 1), date(2026, 10, 12))
    assert "11 de Octubre (ya pasó)" in marcado
    assert "27 de febrero de 2027." in marcado
    assert "01/09/2026 (ya pasó)" in marcado
    assert "24/7." in marcado
