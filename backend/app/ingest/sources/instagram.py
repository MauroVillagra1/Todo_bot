"""
Instagram vía la API oficial (Instagram API with Instagram Login). Costo 0.

Requiere que el dueño de la cuenta autorice una app de Meta y genere un token
de larga duración (dura ~60 días; hay que renovarlo). El token NO va en la base:
la config de la fuente indica el nombre de la variable de entorno que lo tiene.

  config: {"token_env": "IG_TOKEN_SAE_FRT"}

Sin token, la fuente funciona solo con carga manual (no falla).
Limitación: se lee el texto del posteo (caption); el texto dentro de las
imágenes no, porque requeriría OCR.
"""
import html
import os
from datetime import datetime
from typing import Iterator

import httpx

from app.ingest.sources.base import USER_AGENT, ItemCrudo, Source

API = "https://graph.instagram.com/v23.0"
MAX_PAGINAS = 20


def _fecha(valor: str) -> datetime:
    """Instagram devuelve '2026-09-01T12:00:00+0000'."""
    return datetime.strptime(valor, "%Y-%m-%dT%H:%M:%S%z")


class InstagramSource(Source):
    transport: httpx.BaseTransport | None = None  # solo para tests

    def obtener_cambios(self, desde: datetime | None) -> Iterator[ItemCrudo]:
        token = os.environ.get(self.config.get("token_env", ""), "")
        if not token:
            return  # sin autorización por API: solo carga manual

        url: str | None = f"{API}/me/media"
        params: dict | None = {
            "fields": "id,caption,permalink,timestamp",
            "limit": 50,
            "access_token": token,
        }
        with httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT}, transport=self.transport) as client:
            for _ in range(MAX_PAGINAS):
                resp = client.get(url, params=params)
                resp.raise_for_status()
                datos = resp.json()
                for m in datos.get("data", []):  # del más nuevo al más viejo
                    fecha = _fecha(m["timestamp"])
                    if desde and fecha <= desde:
                        return
                    caption = (m.get("caption") or "").strip()
                    yield ItemCrudo(
                        id_externo=f"ig:{m['id']}",
                        url=m["permalink"],
                        titulo=(caption.splitlines() or ["Publicación de Instagram"])[0][:150],
                        contenido_html=f"<p>{html.escape(caption)}</p>".replace("\n", "<br>"),
                        fecha_publicacion=fecha,
                        fecha_modificacion=fecha,
                    )
                url = (datos.get("paging") or {}).get("next")
                params = None  # la URL "next" ya trae todos los parámetros
                if not url:
                    return
