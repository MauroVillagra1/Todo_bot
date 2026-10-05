"""Catálogo público del Campus Virtual (Moodle): una publicación por aula, con docentes."""
from datetime import datetime, timedelta, timezone

import httpx

from app.ingest.sources import obtener_adaptador
from app.ingest.sources.moodle import MoodleSource
from app.models.ingesta import Fuente, TipoFuenteEnum

B = "https://campus.test"
PAGINAS = {
    "/course/index.php": f'<div class="categoryname"><a href="{B}/course/index.php?categoryid=1">CARRERAS DE GRADO</a></div>',
    "/course/index.php?categoryid=1": f'<div class="categoryname"><a href="{B}/course/index.php?categoryid=5">Ingeniería en Sistemas de Información</a></div>',
    "/course/index.php?categoryid=5": (
        f'<div class="categoryname"><a href="{B}/course/index.php?categoryid=7">Periodo Lectivo 2026</a></div>'
        f'<div class="categoryname"><a href="{B}/course/index.php?categoryid=8">Periodo Lectivo 2025</a></div>'),
    "/course/index.php?categoryid=7&perpage=all": f'<div class="categoryname"><a href="{B}/course/index.php?categoryid=9">2do-Nivel ISI</a></div>',
    "/course/index.php?categoryid=9&perpage=all": f'<div class="coursename"><a href="{B}/course/view.php?id=42">Sistemas Operativos</a></div>',
    "/course/info.php?id=42": '<ul class="teachers"><li>Teacher: Loandos Edmundo</li><li>Teacher: Reynoso Leandro</li>'
                              '<li>Non-editing teacher: Perez Ana</li></ul>',
}


def _fuente(**config):
    return Fuente(id=1, nombre="Campus", tipo=TipoFuenteEnum.WEB, url=B, confiabilidad_base=100, activa=True,
                  config={"moodle": True, "categoria": "Ingeniería en Sistemas de Información", "solo": "2026", **config})


def _adaptador(fuente):
    def responder(req: httpx.Request):
        ruta = req.url.raw_path.decode()
        return httpx.Response(200, text=PAGINAS[ruta]) if ruta in PAGINAS else httpx.Response(404)
    a = obtener_adaptador(fuente)
    a.transport, a.pausa = httpx.MockTransport(responder), 0
    return a


def test_se_elige_el_adaptador_moodle_por_config():
    assert isinstance(obtener_adaptador(_fuente()), MoodleSource)


def test_una_publicacion_por_aula_con_docentes():
    items = list(_adaptador(_fuente()).obtener_cambios(None))
    assert len(items) == 1  # el período 2025 se saltea
    item = items[0]
    assert item.id_externo == "curso:42" and item.url == f"{B}/course/view.php?id=42"
    assert item.titulo == "Aula virtual: Sistemas Operativos (2do-Nivel ISI)"
    assert "Docentes: Loandos Edmundo, Reynoso Leandro." in item.contenido_html
    assert "Ayudante: Perez Ana." in item.contenido_html
    assert "Periodo Lectivo 2026 / 2do-Nivel ISI" in item.contenido_html


def test_no_revisa_de_nuevo_antes_de_24_horas():
    hace_un_rato = datetime.now(timezone.utc) - timedelta(hours=3)
    assert list(_adaptador(_fuente()).obtener_cambios(hace_un_rato)) == []


# ── Páginas sueltas (avisos del SYSACAD) ──────────────────────────────────────

def test_pagina_recorta_el_bloque_de_avisos():
    html = ("<html><body><h1>Sistema Académico SYSACAD</h1><p>Inicio de sesión</p><form>Legajo: <input></form>"
            "<p>IMPORTANTE</p><p>¡INSCRIPCION 2do CUATRIMESTRE a partir del Lunes 10 de AGOSTO!</p>"
            "<p>Mails: dptoalumnos@frt.utn.edu.ar</p><p>En caso de error, imprimir esta pantalla</p></body></html>")
    f = Fuente(id=2, nombre="SYSACAD", tipo=TipoFuenteEnum.WEB, url=B, confiabilidad_base=100, activa=True,
               config={"paginas": [{"url": f"{B}/login.asp", "titulo": "SYSACAD: avisos",
                                    "desde": "Inicio de sesión", "hasta": "En caso de error"}]})
    a = obtener_adaptador(f)
    a.transport = httpx.MockTransport(lambda req: httpx.Response(200, content=html.encode("latin-1")))
    [item] = list(a.obtener_cambios(None))
    assert item.id_externo == f"pages:{B}/login.asp" and item.titulo == "SYSACAD: avisos"
    assert "INSCRIPCION 2do CUATRIMESTRE" in item.contenido_html and "dptoalumnos@frt.utn.edu.ar" in item.contenido_html
    assert "Legajo" not in item.contenido_html and "imprimir" not in item.contenido_html


def test_pregunta_de_aula_virtual_no_va_a_horarios(db):
    from app.rag.horarios import responder_horario
    assert responder_horario(db, "¿Tiene aula virtual Sistemas Operativos?") is None
