"""
Ingesta (etapa 3). Criterio de aceptación clave:
  re-ejecutar la ingesta sin cambios en la fuente no crea nada nuevo.
"""
from datetime import datetime, timezone

import pytest

from app.ingest.chunk import dividir
from app.ingest.extract import hash_texto, html_a_texto
from app.ingest.pipeline import procesar_fuente
from app.ingest.sources import ItemCrudo, Source
from app.models.ingesta import (
    Chunk, Documento, EstadoIngestaEnum, Fuente, Ingesta, Publicacion, TipoFuenteEnum,
)
from app.models.metrica import MetricaDiaria


def _fecha(dia: int) -> datetime:
    return datetime(2026, 9, dia, 12, 0, tzinfo=timezone.utc)


def _item(id_: str, html: str, dia: int, titulo: str = "Mesas de examen") -> ItemCrudo:
    return ItemCrudo(
        id_externo=id_, url=f"https://sistemasfrtutn.ar/{id_}", titulo=titulo,
        contenido_html=html, fecha_publicacion=_fecha(1), fecha_modificacion=_fecha(dia),
    )


class FuenteFalsa(Source):
    """Simula WordPress: devuelve solo lo modificado después de `desde`."""

    def __init__(self, fuente, items, falla_en=None):
        super().__init__(fuente)
        self.items = items
        self.falla_en = falla_en
        self.pedidos_desde = []

    def obtener_cambios(self, desde):
        self.pedidos_desde.append(desde)
        for item in self.items:
            if self.falla_en == item.id_externo:
                raise ConnectionError("la fuente se cayó")
            if desde is None or item.fecha_modificacion > desde:
                yield item


@pytest.fixture
def fuente(db):
    engine = db.get_bind()
    for modelo in (Fuente, Documento, Publicacion, Chunk, Ingesta, MetricaDiaria):
        modelo.__table__.create(engine)
    f = Fuente(nombre="Sistemas FRT", tipo=TipoFuenteEnum.WORDPRESS, url="https://x",
               confiabilidad_base=100, activa=True, config={})
    db.add(f)
    db.commit()
    return f


# ── Extracción y chunks ───────────────────────────────────────────────────────

def test_html_a_texto_quita_scripts_y_espacios():
    html = "<p>Inscripciones   abiertas</p><script>alert(1)</script><p>Hasta el <b>10/10</b></p>"
    assert html_a_texto(html) == "Inscripciones abiertas\nHasta el\n10/10"


def test_hash_ignora_espacios_y_mayusculas():
    assert hash_texto("Mesa  de\nExamen") == hash_texto("mesa de examen")
    assert hash_texto("mesa de examen") != hash_texto("mesa de examenes")


def test_dividir_respeta_el_maximo_y_agrega_titulo():
    texto = "\n".join(["a" * 500] * 5)
    chunks = dividir("Titulo", texto, max_caracteres=1200)
    assert len(chunks) == 3
    assert all(c.startswith("Titulo\n") for c in chunks)
    assert all(len(c) <= 1200 + len("Titulo\n") for c in chunks)
    assert dividir("Titulo", "   ") == []


# ── Adaptador WordPress ───────────────────────────────────────────────────────

def test_wordpress_pagina_por_id_y_pide_solo_lo_modificado():
    import httpx

    from app.ingest.sources.wordpress import WordPressSource

    pedidos = []

    def responder(request: httpx.Request) -> httpx.Response:
        pedidos.append(dict(request.url.params))
        pagina = int(request.url.params["page"])
        post = {"id": pagina, "link": f"https://x/{pagina}", "title": {"rendered": "A &amp; B"},
                "content": {"rendered": "<p>x</p>"}, "date_gmt": "2026-09-01T10:00:00",
                "modified_gmt": "2026-09-02T06:13:54"}
        return httpx.Response(200, json=[post], headers={"X-WP-TotalPages": "2"})

    fuente = Fuente(nombre="WP", tipo=TipoFuenteEnum.WORDPRESS, url="https://x",
                    confiabilidad_base=100, config={"api": "https://x/wp-json/wp/v2", "tipos": ["posts"]})
    adaptador = WordPressSource(fuente)
    adaptador.transport, adaptador.pausa = httpx.MockTransport(responder), 0

    items = list(adaptador.obtener_cambios(_fecha(1)))

    assert [i.id_externo for i in items] == ["posts:1", "posts:2"]
    assert items[0].titulo == "A & B"
    assert items[0].fecha_modificacion == datetime(2026, 9, 2, 6, 13, 54, tzinfo=timezone.utc)
    # orden estable (id) y fecha con zona explícita para que WordPress compare en GMT
    assert all(p["orderby"] == "id" for p in pedidos)
    assert pedidos[0]["modified_after"] == "2026-09-01T12:00:00+00:00"


# ── Pipeline ──────────────────────────────────────────────────────────────────

def test_reingesta_sin_cambios_no_crea_nada(db, fuente):
    items = [_item("posts:1", "<p>Mesas de diciembre</p>", 2), _item("posts:2", "<p>Becas</p>", 3)]

    primera = procesar_fuente(db, fuente, FuenteFalsa(fuente, items))
    assert (primera.estado, primera.nuevos, primera.duplicados) == (EstadoIngestaEnum.OK, 2, 0)
    # fecha de la fuente, no reloj local (SQLite la devuelve sin zona)
    assert fuente.ultima_revision.replace(tzinfo=timezone.utc) == _fecha(3)
    total_pubs, total_chunks = db.query(Publicacion).count(), db.query(Chunk).count()

    adaptador = FuenteFalsa(fuente, items)
    segunda = procesar_fuente(db, fuente, adaptador)
    assert adaptador.pedidos_desde[0] is not None  # pidió solo lo modificado
    assert (segunda.nuevos, segunda.errores) == (0, 0)
    assert db.query(Publicacion).count() == total_pubs
    assert db.query(Chunk).count() == total_chunks


def test_repetido_dentro_del_margen_se_descarta_por_hash(db, fuente):
    item = _item("posts:1", "<p>Mesas</p>", 2)
    procesar_fuente(db, fuente, FuenteFalsa(fuente, [item]))

    class SinFiltro(FuenteFalsa):  # devuelve todo, ignorando `desde`
        def obtener_cambios(self, desde):
            yield from self.items

    ing = procesar_fuente(db, fuente, SinFiltro(fuente, [item]))
    assert (ing.nuevos, ing.duplicados) == (0, 1)


def test_cambio_de_contenido_crea_version_y_conserva_la_anterior(db, fuente):
    procesar_fuente(db, fuente, FuenteFalsa(fuente, [_item("posts:1", "<p>Mesa el 10/12</p>", 2)]))
    ing = procesar_fuente(db, fuente, FuenteFalsa(fuente, [_item("posts:1", "<p>Mesa el 12/12</p>", 5)]))

    assert ing.nuevos == 1
    versiones = db.query(Publicacion).filter_by(id_externo="posts:1").order_by(Publicacion.id).all()
    assert [v.vigente for v in versiones] == [False, True]
    assert "12/12" in versiones[1].contenido_original
    metricas = {m.metrica: m.valor for m in db.query(MetricaDiaria)}
    assert metricas["documentos_actualizados"] == 1


def test_si_la_fuente_falla_no_avanza_la_marca(db, fuente):
    items = [_item("posts:1", "<p>Uno</p>", 2), _item("posts:2", "<p>Dos</p>", 3)]
    ing = procesar_fuente(db, fuente, FuenteFalsa(fuente, items, falla_en="posts:2"))

    assert ing.estado == EstadoIngestaEnum.ERROR
    assert ing.nuevos == 1 and ing.errores == 1
    assert fuente.ultima_revision is None  # la próxima corrida vuelve a pedir todo
    assert db.query(Publicacion).count() == 1  # lo ya procesado quedó guardado
