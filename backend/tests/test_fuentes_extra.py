"""PDFs de Sistemas FRT, Instagram por API y carga manual de Instagram/WhatsApp."""
from datetime import date, datetime, timezone

import httpx
import pytest

from app.ingest.pipeline import procesar_fuente
from app.ingest.sources.instagram import InstagramSource
from app.ingest.sources.wordpress import WordPressSource
from app.ingest.verify import calcular_vigencia, procesar_pendientes
from app.models.informacion import Evidencia, Historial, Informacion, Verificacion
from app.models.ingesta import Chunk, Documento, Fuente, Ingesta, Publicacion, TipoFuenteEnum
from app.models.metrica import MetricaDiaria
from app.models.usuario import RolEnum
from conftest import auth


def pdf_con_texto(*paginas: str) -> bytes:
    """PDF mínimo válido con una línea de texto por página (sin dependencias)."""
    objetos = ["<< /Type /Catalog /Pages 2 0 R >>", None,
               "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for texto in paginas:
        flujo = f"BT /F1 12 Tf 50 700 Td ({texto}) Tj ET".encode("latin-1")
        objetos.append(f"<< /Length {len(flujo)} >>\nstream\n{flujo.decode('latin-1')}\nendstream")
        contenido = len(objetos)
        objetos.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       f"/Resources << /Font << /F1 3 0 R >> >> /Contents {contenido} 0 R >>")
        kids.append(f"{len(objetos)} 0 R")
    objetos[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"

    salida, offsets = b"%PDF-1.4\n", []
    for n, obj in enumerate(objetos, 1):
        offsets.append(len(salida))
        salida += f"{n} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    salida += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    salida += f"trailer << /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return salida


@pytest.fixture
def tablas(db):
    engine = db.get_bind()
    for m in (Fuente, Documento, Publicacion, Chunk, Ingesta, MetricaDiaria,
              Informacion, Evidencia, Verificacion, Historial):
        m.__table__.create(engine)
    return db


def _fuente(db, tipo, nombre, confiabilidad=100, config=None):
    f = Fuente(nombre=nombre, tipo=tipo, url="https://x", confiabilidad_base=confiabilidad,
               activa=True, config=config or {})
    db.add(f)
    db.commit()
    return f


# ── PDFs de WordPress ─────────────────────────────────────────────────────────

def _wordpress_pdfs(fuente, pdfs: dict[str, bytes]) -> WordPressSource:
    def responder(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/media"):
            media = [{"id": i, "title": {"rendered": nombre.rsplit(".", 1)[0]},
                      "source_url": f"https://x/wp-content/uploads/{nombre}",
                      "date_gmt": "2026-07-01T10:00:00", "modified_gmt": "2026-07-01T10:00:00",
                      "media_details": {"filesize": len(contenido)}}
                     for i, (nombre, contenido) in enumerate(pdfs.items(), 1)]
            return httpx.Response(200, json=media, headers={"X-WP-TotalPages": "1"})
        return httpx.Response(200, content=pdfs[request.url.path.rsplit("/", 1)[-1]])

    adaptador = WordPressSource(fuente)
    adaptador.transport, adaptador.pausa = httpx.MockTransport(responder), 0
    return adaptador


def test_pdfs_se_descargan_excluyendo_cvs_y_un_chunk_por_pagina(tablas):
    db = tablas
    config = {"api": "https://x/wp-json/wp/v2", "tipos": [], "pdfs": True,
              "excluir_pdf": "(?i)(^|[-_ ])(cv|curriculum)"}
    fuente = _fuente(db, TipoFuenteEnum.WORDPRESS, "PDFs", config=config)
    pdfs = {
        "HORARIO-3-PLAN-2023.pdf": pdf_con_texto("HORARIOS 2026 Comision 3K01 Aula 107",
                                                 "HORARIOS 2026 Comision 3K02 Aula 214"),
        "CV_Zamudio.pdf": pdf_con_texto("Curriculum"),
        "Curriculum-Docente-Santillan-M.pdf": pdf_con_texto("Curriculum"),
    }

    ing = procesar_fuente(db, fuente, _wordpress_pdfs(fuente, pdfs))

    assert (ing.nuevos, ing.errores) == (1, 0)
    doc = db.query(Documento).one()
    assert doc.url.endswith("HORARIO-3-PLAN-2023.pdf")
    assert [c.texto.splitlines()[1] for c in db.query(Chunk).order_by(Chunk.orden)] == [
        "HORARIOS 2026 Comision 3K01 Aula 107", "HORARIOS 2026 Comision 3K02 Aula 214"]

    # Reingesta del mismo PDF: duplicado, nada nuevo
    ing2 = procesar_fuente(db, fuente, _wordpress_pdfs(fuente, pdfs))
    assert (ing2.nuevos, db.query(Documento).count()) == (0, 1)


def test_horario_plan_2023_no_queda_desactualizado(tablas):
    db = tablas
    fuente = _fuente(db, TipoFuenteEnum.WORDPRESS, "PDFs", config={
        "api": "https://x/wp-json/wp/v2", "tipos": [], "pdfs": True})
    procesar_fuente(db, fuente, _wordpress_pdfs(fuente, {
        "1-ANO-2023.pdf": pdf_con_texto("HORARIOS 2026 1 Ano PLAN 2023 Comision 1K01")}))
    procesar_pendientes(db, hoy=date(2026, 10, 4))

    info = db.query(Informacion).one()
    assert (info.tipo.value, info.estado.value) == ("CALENDARIO", "CONFIRMADA")
    assert db.query(Evidencia).one().documento_id is not None


def test_vigencia_ignora_el_anio_del_plan():
    assert calcular_vigencia("Horario PLAN 2023", "", date(2026, 3, 1), False)[1] == date(2027, 3, 1)
    assert calcular_vigencia("Calendario 2025", "", date(2026, 2, 28), False)[1] == date(2025, 12, 31)


# ── Instagram por API ─────────────────────────────────────────────────────────

def test_instagram_sin_token_no_trae_nada_ni_falla(monkeypatch):
    monkeypatch.delenv("IG_TOKEN_TEST", raising=False)
    fuente = Fuente(nombre="IG", tipo=TipoFuenteEnum.INSTAGRAM, url="https://x",
                    confiabilidad_base=90, config={"token_env": "IG_TOKEN_TEST"})
    assert list(InstagramSource(fuente).obtener_cambios(None)) == []


def test_instagram_con_token_trae_solo_lo_nuevo(monkeypatch):
    monkeypatch.setenv("IG_TOKEN_TEST", "secreto")

    def responder(request: httpx.Request) -> httpx.Response:
        assert request.url.params["access_token"] == "secreto"
        return httpx.Response(200, json={"data": [
            {"id": "2", "caption": "Inscripciones abiertas\nhasta el 10/10", "permalink": "https://ig/p/2",
             "timestamp": "2026-09-20T12:00:00+0000"},
            {"id": "1", "caption": "Viejo", "permalink": "https://ig/p/1",
             "timestamp": "2026-08-01T12:00:00+0000"},
        ]})

    fuente = Fuente(nombre="IG", tipo=TipoFuenteEnum.INSTAGRAM, url="https://x",
                    confiabilidad_base=90, config={"token_env": "IG_TOKEN_TEST"})
    adaptador = InstagramSource(fuente)
    adaptador.transport = httpx.MockTransport(responder)

    items = list(adaptador.obtener_cambios(datetime(2026, 9, 1, tzinfo=timezone.utc)))
    assert [(i.id_externo, i.titulo) for i in items] == [("ig:2", "Inscripciones abiertas")]


# ── Carga manual (Instagram / WhatsApp) ───────────────────────────────────────

POSTEO = {"url": "https://whatsapp.com/channel/0029VaYQ0rj2phHJITlkfZ1T/123",
          "titulo": "Mesas de examen", "contenido": "Las mesas de diciembre son el 10/12.",
          "fecha_publicacion": "2026-10-01"}


def test_mod_carga_posteo_de_whatsapp_y_queda_no_confirmado(client, crear_usuario, tablas):
    db = tablas
    wa = _fuente(db, TipoFuenteEnum.WHATSAPP, "Canal WhatsApp 1", confiabilidad=50)
    mod = crear_usuario("mod@alu.frt.utn.edu.ar", RolEnum.MOD)

    r = client.post(f"/api/v1/fuentes/{wa.id}/publicaciones", json=POSTEO, headers=auth(mod))
    assert r.status_code == 201, r.text
    assert (r.json()["resultado"], r.json()["estado"], r.json()["tipo"]) == ("nuevo", "NO_CONFIRMADA", "EXAMEN")

    # Mismo link con texto corregido → versión nueva de la misma información
    r2 = client.post(f"/api/v1/fuentes/{wa.id}/publicaciones",
                     json={**POSTEO, "contenido": "Las mesas de diciembre son el 12/12."}, headers=auth(mod))
    assert r2.json()["resultado"] == "actualizado"
    assert r2.json()["informacion_id"] == r.json()["informacion_id"]
    assert db.query(Informacion).one().fecha_fin == date(2026, 12, 12)


def test_miembro_no_puede_cargar_ni_listar_fuentes(client, crear_usuario, tablas):
    wa = _fuente(tablas, TipoFuenteEnum.WHATSAPP, "Canal WhatsApp 1", confiabilidad=50)
    u = crear_usuario("u@alu.frt.utn.edu.ar", RolEnum.MIEMBRO)
    assert client.post(f"/api/v1/fuentes/{wa.id}/publicaciones", json=POSTEO, headers=auth(u)).status_code == 403
    assert client.get("/api/v1/fuentes/", headers=auth(u)).status_code == 403


def test_no_se_carga_a_mano_en_fuentes_automaticas(client, crear_usuario, tablas):
    wp = _fuente(tablas, TipoFuenteEnum.WORDPRESS, "Sistemas FRT")
    mod = crear_usuario("mod@alu.frt.utn.edu.ar", RolEnum.MOD)
    assert client.post(f"/api/v1/fuentes/{wp.id}/publicaciones", json=POSTEO, headers=auth(mod)).status_code == 400
    lista = client.get("/api/v1/fuentes/", headers=auth(mod)).json()
    assert [(f["nombre"], f["carga_manual"]) for f in lista] == [("Sistemas FRT", False)]
