"""
Instagram vía la API oficial (Instagram API with Instagram Login). Costo 0.

Requiere que el dueño de la cuenta autorice una app de Meta y genere un token
de larga duración (dura ~60 días; hay que renovarlo). El token NO va en la base:
la config de la fuente indica el nombre de la variable de entorno que lo tiene.

  config: {"token_env": "IG_TOKEN_SAE_FRT"}

Sin token, la fuente funciona solo con carga manual (no falla).

Modo Instaloader (sin API, corre solo en la PC local, nunca en Vercel ni en
GitHub Actions porque Instagram bloquea IPs de datacenter):

  config: {"instaloader": true}

Se activa solo si la variable IG_INSTALOADER=1 está definida (la pone
scripts/instagram_local.ps1); si no, la fuente no trae nada. El usuario se
toma de la URL de la fuente. Si IG_SESION tiene un usuario de Instagram, usa
la sesión guardada con `instaloader --login <usuario>` (recomendado: sin
login Instagram suele cortar las consultas).

Limitación: se lee el texto del posteo (caption); el texto dentro de las
imágenes no, porque requeriría OCR.
"""
import html
import os
from datetime import datetime, timezone
from typing import Iterator

import httpx

from app.ingest.sources.base import USER_AGENT, ItemCrudo, Source

API = "https://graph.instagram.com/v23.0"
MAX_PAGINAS = 20


def _fecha(valor: str) -> datetime:
    """Instagram devuelve '2026-09-01T12:00:00+0000'."""
    return datetime.strptime(valor, "%Y-%m-%dT%H:%M:%S%z")


def _item(id_media: str, permalink: str, caption: str, fecha: datetime) -> ItemCrudo:
    caption = caption.strip()
    return ItemCrudo(
        id_externo=f"ig:{id_media}",
        url=permalink,
        titulo=(caption.splitlines() or ["Publicación de Instagram"])[0][:150],
        contenido_html=f"<p>{html.escape(caption)}</p>".replace("\n", "<br>"),
        fecha_publicacion=fecha,
        fecha_modificacion=fecha,
    )


def usuario_de_url(url: str) -> str:
    """'https://instagram.com/sae.frt.ofc/' → 'sae.frt.ofc'."""
    return url.rstrip("/").rsplit("/", 1)[-1].lstrip("@")


# Publicaciones fijadas: aparecen primero aunque sean viejas, por eso no se corta
# en la primera publicación anterior a `desde` sino después de varias seguidas.
VIEJOS_SEGUIDOS_PARA_CORTAR = 4
MAX_POSTS_PRIMERA_VEZ = 30


class InstagramSource(Source):
    transport: httpx.BaseTransport | None = None  # solo para tests

    def obtener_cambios(self, desde: datetime | None) -> Iterator[ItemCrudo]:
        if self.config.get("instaloader"):
            yield from self._por_instaloader(desde)
            return
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
                    yield _item(m["id"], m["permalink"], m.get("caption") or "", fecha)
                url = (datos.get("paging") or {}).get("next")
                params = None  # la URL "next" ya trae todos los parámetros
                if not url:
                    return

    def posts_instaloader(self, usuario: str) -> Iterator:
        """Posts del perfil, del más nuevo al más viejo (los tests lo reemplazan)."""
        import instaloader  # solo instalado en la PC local

        loader = instaloader.Instaloader(
            download_pictures=False, download_videos=False, download_video_thumbnails=False,
            download_geotags=False, download_comments=False, save_metadata=False, quiet=True,
        )
        sesion = os.environ.get("IG_SESION", "")
        if sesion:
            loader.load_session_from_file(sesion)
        return instaloader.Profile.from_username(loader.context, usuario).get_posts()

    def _por_instaloader(self, desde: datetime | None) -> Iterator[ItemCrudo]:
        if os.environ.get("IG_INSTALOADER") != "1":
            return  # solo en la PC local

        viejos = 0
        for n, post in enumerate(self.posts_instaloader(usuario_de_url(self.fuente.url))):
            if desde is None and n >= MAX_POSTS_PRIMERA_VEZ:
                return
            fecha = post.date_utc.replace(tzinfo=timezone.utc)
            if desde and fecha <= desde:
                viejos += 1
                if viejos >= VIEJOS_SEGUIDOS_PARA_CORTAR:
                    return
                continue
            viejos = 0
            yield _item(str(post.mediaid), f"https://www.instagram.com/p/{post.shortcode}/",
                        post.caption or "", fecha)
