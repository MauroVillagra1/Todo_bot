"""
Adaptador para sitios WordPress con REST API pública (ej. sistemasfrtutn.ar).

Detección de cambios sin scraping: `modified_after` hace que WordPress
devuelva solo lo creado o modificado desde la última revisión.

Config de la fuente:
  api          URL base de la REST API (…/wp-json/wp/v2)
  tipos        colecciones de contenido a leer (["posts", "pages"])
  pdfs         true → también descarga los PDFs de la biblioteca de medios
  excluir_pdf  regex sobre el nombre del archivo para no descargarlo (ej. CVs)
"""
import re
import time
from datetime import datetime, timezone
from html import unescape
from typing import Iterator

import httpx

from app.ingest.sources.base import USER_AGENT, DocumentoCrudo, ItemCrudo, Source

PAUSA_ENTRE_PAGINAS = 1.0  # segundos: no cargar el servidor de la facultad
REINTENTOS = 2
MAX_BYTES_PDF = 15 * 1024 * 1024


def _fecha_gmt(valor: str | None) -> datetime | None:
    """WordPress devuelve '2026-09-02T06:13:54' (GMT sin zona) → datetime UTC."""
    if not valor:
        return None
    return datetime.fromisoformat(valor).replace(tzinfo=timezone.utc)


class WordPressSource(Source):
    transport: httpx.BaseTransport | None = None  # solo para tests
    pausa = PAUSA_ENTRE_PAGINAS

    def _cliente(self) -> httpx.Client:
        return httpx.Client(
            timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT},
            transport=self.transport,
        )

    def _paginar(self, client: httpx.Client, url: str, params: dict, desde: datetime | None) -> Iterator[dict]:
        """Recorre todas las páginas de una colección, ordenada por ID."""
        pagina = 1
        while True:
            consulta = {
                **params,
                "per_page": int(self.config.get("por_pagina", 50)),
                "page": pagina,
                # Orden por ID (único). Por "modified" la paginación no es estable:
                # cientos de posts comparten el mismo segundo y se repetían/salteaban.
                "orderby": "id",
                "order": "asc",
            }
            if desde:
                # Con zona explícita WordPress compara en GMT (verificado)
                consulta["modified_after"] = desde.astimezone(timezone.utc).isoformat()

            resp = self._get(client, url, consulta)
            yield from resp.json()

            if pagina >= int(resp.headers.get("X-WP-TotalPages", 1)):
                break
            pagina += 1
            time.sleep(self.pausa)

    def obtener_cambios(self, desde: datetime | None) -> Iterator[ItemCrudo]:
        api = self.config["api"].rstrip("/")
        with self._cliente() as client:
            for tipo in self.config.get("tipos", ["posts"]):
                campos = {"_fields": "id,link,title,content,date_gmt,modified_gmt"}
                for d in self._paginar(client, f"{api}/{tipo}", campos, desde):
                    yield ItemCrudo(
                        id_externo=f"{tipo}:{d['id']}",
                        url=d["link"],
                        titulo=unescape(d["title"]["rendered"]),
                        contenido_html=d["content"]["rendered"],
                        fecha_publicacion=_fecha_gmt(d.get("date_gmt")),
                        fecha_modificacion=_fecha_gmt(d.get("modified_gmt")),
                    )

    def obtener_documentos(self, desde: datetime | None) -> Iterator[DocumentoCrudo]:
        if not self.config.get("pdfs"):
            return
        api = self.config["api"].rstrip("/")
        excluir = re.compile(self.config["excluir_pdf"]) if self.config.get("excluir_pdf") else None
        params = {
            "mime_type": "application/pdf",
            "_fields": "id,title,source_url,date_gmt,modified_gmt,media_details",
        }
        with self._cliente() as client:
            for m in self._paginar(client, f"{api}/media", params, desde):
                url = m["source_url"]
                archivo = url.rsplit("/", 1)[-1]
                tamanio = (m.get("media_details") or {}).get("filesize") or 0
                if (excluir and excluir.search(archivo)) or tamanio > MAX_BYTES_PDF:
                    continue
                resp = self._get(client, url, {})
                time.sleep(self.pausa)
                yield DocumentoCrudo(
                    url=url,
                    nombre=unescape(m["title"]["rendered"]) or archivo,
                    contenido=resp.content,
                    fecha_publicacion=_fecha_gmt(m.get("date_gmt")),
                    fecha_modificacion=_fecha_gmt(m.get("modified_gmt")),
                )

    @staticmethod
    def _get(client: httpx.Client, url: str, params: dict) -> httpx.Response:
        for intento in range(REINTENTOS + 1):
            try:
                resp = client.get(url, params=params)
                if resp.status_code < 500:
                    resp.raise_for_status()
                    return resp
            except httpx.TransportError:
                if intento == REINTENTOS:
                    raise
            time.sleep(2 * (intento + 1))
        resp.raise_for_status()
        return resp
