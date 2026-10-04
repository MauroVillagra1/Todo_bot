"""
Adaptador para sitios WordPress con REST API pública (ej. sistemasfrtutn.ar).

Detección de cambios sin scraping: `modified_after` hace que WordPress
devuelva solo lo creado o modificado desde la última revisión.
"""
import time
from datetime import datetime, timezone
from html import unescape
from typing import Iterator

import httpx

from app.ingest.sources.base import USER_AGENT, ItemCrudo, Source

PAUSA_ENTRE_PAGINAS = 1.0  # segundos: no cargar el servidor de la facultad
REINTENTOS = 2


def _fecha_gmt(valor: str | None) -> datetime | None:
    """WordPress devuelve '2026-09-02T06:13:54' (GMT sin zona) → datetime UTC."""
    if not valor:
        return None
    return datetime.fromisoformat(valor).replace(tzinfo=timezone.utc)


class WordPressSource(Source):
    transport: httpx.BaseTransport | None = None  # solo para tests
    pausa = PAUSA_ENTRE_PAGINAS

    def obtener_cambios(self, desde: datetime | None) -> Iterator[ItemCrudo]:
        api = self.config["api"].rstrip("/")
        por_pagina = int(self.config.get("por_pagina", 50))

        with httpx.Client(
            timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT},
            transport=self.transport,
        ) as client:
            for tipo in self.config.get("tipos", ["posts"]):
                pagina = 1
                while True:
                    params = {
                        "per_page": por_pagina,
                        "page": pagina,
                        # Orden por ID (único). Por "modified" la paginación no es estable:
                        # cientos de posts comparten el mismo segundo y se repetían/salteaban.
                        "orderby": "id",
                        "order": "asc",
                        "_fields": "id,link,title,content,date_gmt,modified_gmt",
                    }
                    if desde:
                        # Con zona explícita WordPress compara en GMT (verificado)
                        params["modified_after"] = desde.astimezone(timezone.utc).isoformat()

                    resp = self._get(client, f"{api}/{tipo}", params)
                    for d in resp.json():
                        yield ItemCrudo(
                            id_externo=f"{tipo}:{d['id']}",
                            url=d["link"],
                            titulo=unescape(d["title"]["rendered"]),
                            contenido_html=d["content"]["rendered"],
                            fecha_publicacion=_fecha_gmt(d.get("date_gmt")),
                            fecha_modificacion=_fecha_gmt(d.get("modified_gmt")),
                        )

                    total_paginas = int(resp.headers.get("X-WP-TotalPages", 1))
                    if pagina >= total_paginas:
                        break
                    pagina += 1
                    time.sleep(self.pausa)

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
