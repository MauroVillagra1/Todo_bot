"""Mesas de examen, calendario académico y '¿hay clases?' respondidos con SQL; sus planillas del panel."""
from datetime import date, timedelta

import pytest

from app.ingest.datos_calendario import eventos_iniciales
from app.ingest.datos_mesas import FECHAS_2026, materias_iniciales
from app.models.auditoria import RegistroCambios
from app.models.cache import CacheRespuesta
from app.models.chat import MensajeChat
from app.models.horario import HorarioClase
from app.models.calendario import EventoCalendario
from app.models.informacion import Evidencia, Historial, Informacion, Verificacion
from app.models.ingesta import Chunk, Documento, Fuente, Ingesta, Publicacion
from app.models.mesa import MesaFecha, MesaMateria
from app.models.metrica import MetricaDiaria
from app.models.usuario import RolEnum
from app.rag.calendario import responder_calendario
from app.rag.mesas import REGLA, responder_mesa
from conftest import auth

HOY = date(2026, 10, 28)  # miércoles


@pytest.fixture
def datos(db):
    engine = db.get_bind()
    for m in (Fuente, Documento, Publicacion, Chunk, Ingesta, MetricaDiaria, Informacion, Evidencia,
              Verificacion, Historial, RegistroCambios, CacheRespuesta, MensajeChat, HorarioClase):
        m.__table__.create(engine, checkfirst=True)
    db.add_all([MesaFecha(**f) for f in FECHAS_2026])
    db.add_all([MesaMateria(**m) for m in materias_iniciales()])
    db.add_all([EventoCalendario(**e) for e in eventos_iniciales()])
    db.commit()


# ── Mesas ─────────────────────────────────────────────────────────────────────

def test_materia_su_mesa_fechas_y_tribunal(db, datos):
    r = responder_mesa(db, "¿Cuándo rindo Sistemas Operativos?", hoy=HOY)
    texto = r["respuesta"]
    assert "**Sistemas Operativos** se rinde en la **Mesa III**" in texto
    assert "examen el **viernes 27/11/2026**" in texto and "inscripción hasta el miércoles 25/11/2026" in texto
    assert "lunes 07/12/2026" in texto  # 6º turno: fecha oficial (cazorla decía 09/12)
    assert "Casa Central, 15:00 h: Loandos Edmundo (presidente); vocales: Sale Ernesto" in texto
    assert "Anexo Concepción" in texto
    assert REGLA in texto
    assert "Avanzados" not in texto  # no confunde con Sistemas Operativos Avanzados


def test_sin_numero_es_la_i_y_electiva_por_nombre_corto(db, datos):
    assert "**Física I**" in responder_mesa(db, "¿cuándo es el final de física?", hoy=HOY)["respuesta"]
    texto = responder_mesa(db, "mesa de inteligencia artificial distribuida", hoy=HOY)["respuesta"]
    assert "Inteligencia Artificial Distribuida" in texto and "Mesa I**" in texto


def test_mesas_de_un_mes_y_proximas(db, datos):
    texto = responder_mesa(db, "¿Cuándo son las mesas de diciembre?", hoy=HOY)["respuesta"]
    assert "diciembre 2026" in texto
    assert "Mesa I — 6º turno: examen el **miércoles 02/12/2026**" in texto
    proximas = responder_mesa(db, "¿cuándo son las próximas mesas de examen?", hoy=HOY)["respuesta"]
    assert "lunes 23/11/2026" in proximas  # 5º turno Mesa I según la resolución


def test_inscripcion_cerrada_y_mesa_pedida(db, datos):
    texto = responder_mesa(db, "qué materias se rinden en la mesa 2", hoy=date(2026, 11, 24))["respuesta"]
    assert "- Programación Web" in texto
    assert "_(inscripción cerrada)_" in texto  # Mesa II: cierre 23/11, examen 25/11


def test_tribunales_de_un_docente(db, datos):
    texto = responder_mesa(db, "¿En qué mesas está Zamudio?", hoy=HOY)["respuesta"]
    assert "Zamudio Marcelo" in texto and "Seguridad Informática" in texto and "(vocal)" in texto


def test_regla_de_regularidad_y_lo_que_no_es_de_mesas(db, datos):
    assert responder_mesa(db, "¿La regularidad vence?", hoy=HOY)["respuesta"] == REGLA
    assert responder_mesa(db, "¿Cuándo es la prueba de suficiencia de inglés?", hoy=HOY) is None
    assert responder_mesa(db, "¿Hay becas abiertas?", hoy=HOY) is None
    assert responder_mesa(db, "¿Cuándo es el final de Química Orgánica Avanzada II?", hoy=HOY) is None


# ── Calendario ────────────────────────────────────────────────────────────────

def test_hay_clases_un_dia_normal_un_feriado_y_un_receso(db, datos):
    assert "Sí, mañana" in responder_calendario(db, "¿hay clases mañana?", hoy=HOY)["respuesta"]
    feriado = responder_calendario(db, "¿hay clases el 23/11?", hoy=HOY)["respuesta"]
    assert "no hay clases" in feriado and "Soberanía" in feriado
    receso = responder_calendario(db, "hay clases el 15/07/2026?", hoy=date(2026, 7, 1))["respuesta"]
    assert "receso académico" in receso
    domingo = responder_calendario(db, "¿hay clases el domingo?", hoy=HOY)["respuesta"]
    assert "domingo" in domingo


def test_hay_clases_con_paro_no_docente(db, datos, client, crear_usuario):
    mod = crear_usuario("mod@alu.frt.utn.edu.ar", RolEnum.SMOD)
    viernes = HOY + timedelta(days=2)
    r = client.post("/api/v1/informacion/paro", json={"tipo": "NO_DOCENTE", "fecha": viernes.isoformat()},
                    headers=auth(mod))
    assert r.status_code == 201, r.text
    texto = responder_calendario(db, "¿hay clases el viernes?", hoy=HOY)["respuesta"]
    assert "Paro no docente" in texto and "CERRADA" in texto


def test_feriados_cuatrimestre_receso_suficiencia_y_notas(db, datos):
    feriados = responder_calendario(db, "¿qué feriados hay en diciembre?", hoy=HOY)["respuesta"]
    assert "Inmaculada Concepción" in feriados and "Navidad" in feriados and "Soberanía" not in feriados
    assert "Soberanía" in responder_calendario(db, "¿cuándo es el próximo feriado?", hoy=HOY)["respuesta"]
    segundo = responder_calendario(db, "¿cuándo empieza el segundo cuatrimestre?", hoy=HOY)["respuesta"]
    assert "18/08/2026" in segundo and "1º cuatrimestre" not in segundo
    assert "13/07/2026" in responder_calendario(db, "¿cuándo son las vacaciones de invierno?", hoy=HOY)["respuesta"]
    ingles = responder_calendario(db, "¿cuándo es la prueba de suficiencia de inglés?", hoy=HOY)["respuesta"]
    assert "Idioma Extranjero" in ingles and "Informática" not in ingles
    notas = responder_calendario(db, "¿hasta cuándo presento la nota de cambio de comisión?", hoy=HOY)["respuesta"]
    assert "06/04/2026" in notas and "Documentos" in notas


def test_calendario_de_un_mes_incluye_mesas(db, datos):
    texto = responder_calendario(db, "¿qué hay en el calendario en agosto?", hoy=HOY)["respuesta"]
    assert "Inscripción a asignaturas del 2º cuatrimestre" in texto and "Exámenes finales" in texto


def test_preguntas_que_no_son_del_calendario(db, datos):
    for pregunta in ("¿Hay becas abiertas?", "¿Qué materias tengo los lunes en la 1K01?",
                     "¿Cómo me inscribo al cursado en SYSACAD?", "¿Cuándo rindo Física?"):
        assert responder_calendario(db, pregunta, hoy=HOY) is None, pregunta


# ── Panel: planillas (solo ADMIN) ─────────────────────────────────────────────

def test_mesas_y_calendario_solo_admin_editan(db, datos, client, crear_usuario):
    admin = crear_usuario("admin@alu.frt.utn.edu.ar", RolEnum.ADMIN)
    mod = crear_usuario("mod@alu.frt.utn.edu.ar", RolEnum.MOD)
    assert client.get("/api/v1/mesas/materias", headers=auth(mod)).status_code == 403
    assert client.get("/api/v1/mesas/fechas", headers=auth(mod)).status_code == 200  # el calendario las muestra
    assert client.post("/api/v1/mesas/fechas", json={"mesa": 1, "cierre_inscripcion": "2026-11-01",
                                                     "fecha_examen": "2026-11-02"}, headers=auth(mod)).status_code == 403
    assert client.get("/api/v1/calendario/", headers=auth(mod)).status_code == 200  # leer: cualquiera
    assert client.post("/api/v1/calendario/", json={"fecha_inicio": "2026-11-02", "actividad": "Algo"},
                       headers=auth(mod)).status_code == 403

    fechas = client.get("/api/v1/mesas/fechas", headers=auth(admin)).json()
    assert len(fechas) == 30
    r = client.patch(f"/api/v1/mesas/fechas/{fechas[0]['id']}", json={"fecha_examen": "2026-05-01"},
                     headers=auth(admin))
    assert r.status_code == 422  # el examen no puede ser antes del cierre

    materia = client.post("/api/v1/mesas/materias", json={"materia": "Robótica (electiva)", "mesa": 2,
                                                          "presidente": "Perez Ana", "hora": "18:00"},
                          headers=auth(admin))
    assert materia.status_code == 201, materia.text
    assert "Robótica" in responder_mesa(db, "¿cuándo rindo robótica?", hoy=HOY)["respuesta"]
    assert client.patch(f"/api/v1/mesas/materias/{materia.json()['id']}", json={"hora": "25:00"},
                        headers=auth(admin)).status_code == 422

    evento = client.post("/api/v1/calendario/", json={"fecha_inicio": "2026-11-02", "actividad": "Jornada de puertas abiertas",
                                                     "categoria": "OTRO"}, headers=auth(admin))
    assert evento.status_code == 201
    assert client.delete(f"/api/v1/calendario/{evento.json()['id']}", headers=auth(admin)).status_code == 204
    assert db.query(RegistroCambios).count() == 3


# ── Chat con contexto (como ChatGPT): seguimientos dentro del mismo chat ─────

def _preguntar(client, usuario, mensaje, conv=None):
    r = client.post("/api/v1/chat/", json={"mensaje": mensaje, "conversacion_id": conv}, headers=auth(usuario))
    assert r.status_code == 200, r.text
    return r.json()


def test_seguimiento_de_mesas_y_de_dias_en_el_mismo_chat(db, datos, client, crear_usuario, monkeypatch):
    from app.rag import answer, calendario as cal, mesas
    monkeypatch.setattr(answer, "buscar", lambda *a, **k: [])  # la búsqueda general es de Postgres
    monkeypatch.setattr(mesas, "hoy_argentina", lambda: HOY)
    monkeypatch.setattr(cal, "hoy_argentina", lambda: HOY)
    u = crear_usuario("a@alu.frt.utn.edu.ar")
    primera = _preguntar(client, u, "¿Cuándo rindo Sistemas Operativos?")
    conv = primera["conversacion_id"]
    seguimiento = _preguntar(client, u, "¿y Física?", conv)["respuesta"]
    assert "**Física I** se rinde en la **Mesa I**" in seguimiento
    # En un chat nuevo, "¿y Física?" no tiene a qué referirse
    assert "Física I" not in _preguntar(client, u, "¿y Física?")["respuesta"]

    dia = _preguntar(client, u, "¿hay clases mañana?")
    assert "lunes" in _preguntar(client, u, "¿y el lunes?", dia["conversacion_id"])["respuesta"]
    assert len(client.get("/api/v1/chat/conversaciones", headers=auth(u)).json()) == 3  # un chat = una entrada


def test_que_es_un_seguimiento():
    from app.services.chat_service import es_seguimiento
    for p in ("¿y Física?", "¿Y cuándo cierra?", "¿quién la da?", "¿y el lunes?", "Física", "¿su tribunal?"):
        assert es_seguimiento(p), p
    for p in ("¿Hay becas abiertas?", "¿Cuándo rindo Sistemas Operativos?", "¿Qué materias tengo los lunes en la 1K01?"):
        assert not es_seguimiento(p), p
