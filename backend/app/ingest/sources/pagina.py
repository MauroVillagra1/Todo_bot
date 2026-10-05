"""
Adaptador para páginas sueltas con avisos (ej. el bloque "IMPORTANTE" del ingreso al SYSACAD).
Una publicación por página; si el texto cambia, queda como versión nueva.

Config de la fuente:
  paginas     [{"url", "titulo", "desde"?, "hasta"?}]: desde/hasta recortan el texto útil
  cada_horas  no vuelve a leer antes de este intervalo (default 6)
"""
import re
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Iterator

import httpx
from bs4 import BeautifulSoup

from app.ingest.sources.base import USER_AGENT, ItemCrudo, Source


def recortar(texto: str, desde: str | None, hasta: str | None) -> str:
    if desde and desde in texto:
        texto = texto[texto.index(desde) + len(desde):]
    if hasta and hasta in texto:
        texto = texto[:texto.index(hasta)]
    return texto.strip()


class PaginaSource(Source):
    transport: httpx.BaseTransport | None = None  # solo para tests

    def obtener_cambios(self, desde: datetime | None) -> Iterator[ItemCrudo]:
        ahora = datetime.now(timezone.utc)
        if desde and ahora - desde < timedelta(hours=float(self.config.get("cada_horas", 6))):
            return
        with httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT},
                          transport=self.transport) as client:
            for p in self.config.get("paginas", []):
                resp = client.get(p["url"])
                resp.raise_for_status()
                sopa = BeautifulSoup(resp.content, "html.parser")  # bytes: detecta la codificación
                for t in sopa(["script", "style", "form", "input", "button"]):
                    t.decompose()
                lineas = [re.sub(r"\s+", " ", x).strip() for x in sopa.get_text("\n").splitlines()]
                texto = recortar("\n".join(x for x in lineas if x), p.get("desde"), p.get("hasta"))
                if not texto:
                    continue
                yield ItemCrudo(
                    # "pages:" → página institucional: sin vencimiento salvo que el texto tenga fechas
                    id_externo=f"pages:{p['url']}",
                    url=p["url"],
                    titulo=p["titulo"],
                    contenido_html="".join(f"<p>{escape(x)}</p>" for x in texto.splitlines()),
                    fecha_publicacion=None,
                    fecha_modificacion=ahora,
                )
