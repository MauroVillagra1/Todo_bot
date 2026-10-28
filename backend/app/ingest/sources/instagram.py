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

Modo Apify (recomendado: corre en GitHub Actions, sin la PC local):

  config: {"apify": true}

Usa el actor "Instagram Post Scraper" de Apify con el token de la variable APIFY_TOKEN
(sin token la fuente no trae nada y no falla). Trae solo publicaciones (no historias), solo el
texto (caption), de la más nueva a la más vieja: la primera vez MAX_POSTS_PRIMERA_VEZ y después
lo publicado desde la última revisión. Si una publicación no tiene descripción, se lee el texto
del flyer con Gemini (services/flyers.py; hasta MAX_FLYERS_POR_CORRIDA). Todas se guardan con el
link de la publicación en el texto, para que el chat lo muestre.

Limitación (API oficial e Instaloader): se lee el texto del posteo (caption), no el de las imágenes.
"""
import html
import os
from datetime import datetime, timezone
from typing import Iterator

import httpx

from app.ingest.sources.base import USER_AGENT, ItemCrudo, Source

API = "https://graph.instagram.com/v23.0"
APIFY_ACTOR = "https://api.apify.com/v2/acts/apify~instagram-post-scraper/run-sync-get-dataset-items"
APIFY_TIMEOUT = 300  # segundos: el actor corre y devuelve los posts en la misma llamada
MAX_FLYERS_POR_CORRIDA = 30  # posts sin descripción leídos con IA por cuenta y corrida (cupo de Gemini)
MAX_PAGINAS = 20


def _fecha(valor: str) -> datetime:
    """Instagram devuelve '2026-09-01T12:00:00+0000'."""
    return datetime.strptime(valor, "%Y-%m-%dT%H:%M:%S%z")


def _item(id_media: str, permalink: str, caption: str, fecha: datetime, con_link: bool = False) -> ItemCrudo:
    caption = caption.strip()
    contenido = f"<p>{html.escape(caption)}</p>".replace("\n", "<br>")
    if con_link:  # el chat puede citar la publicación con su link
        contenido += f"<p>Publicación de Instagram: {html.escape(permalink)}</p>"
    return ItemCrudo(
        id_externo=f"ig:{id_media}",
        url=permalink,
        titulo=(caption.splitlines() or ["Publicación de Instagram"])[0][:150],
        contenido_html=contenido,
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
        if self.config.get("apify"):
            yield from self._por_apify(desde)
            return
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

    def _por_apify(self, desde: datetime | None) -> Iterator[ItemCrudo]:
        token = os.environ.get("APIFY_TOKEN", "")
        if not token:
            return  # sin token de Apify no se lee (no es un error)
        entrada = {"username": [usuario_de_url(self.fuente.url)], "resultsLimit": MAX_POSTS_PRIMERA_VEZ}
        if desde:
            entrada["onlyPostsNewerThan"] = desde.date().isoformat()
        with httpx.Client(timeout=APIFY_TIMEOUT, transport=self.transport) as client:
            resp = client.post(APIFY_ACTOR, params={"token": token}, json=entrada)
            resp.raise_for_status()
            posts = resp.json()
        flyers = 0
        for post in posts:
            if not post.get("timestamp") or post.get("error"):
                continue
            fecha = datetime.fromisoformat(post["timestamp"].replace("Z", "+00:00"))
            if desde and fecha <= desde:
                continue
            caption = (post.get("caption") or "").strip()
            if not caption:  # sin descripción: se lee el flyer (solo estas)
                imagen = post.get("displayUrl") or next(iter(post.get("images") or []), None)
                if not imagen or flyers >= MAX_FLYERS_POR_CORRIDA:
                    continue
                flyers += 1
                caption = self.leer_flyer(imagen) or ""
                if not caption:
                    continue  # la imagen no tiene texto informativo
            url = post.get("url") or f"https://www.instagram.com/p/{post.get('shortCode')}/"
            yield _item(str(post.get("id") or post.get("shortCode")), url, caption, fecha, con_link=True)

    @staticmethod
    def leer_flyer(url_imagen: str) -> str | None:
        """Texto del flyer con IA (los tests lo reemplazan)."""
        from app.services.flyers import leer_flyer
        return leer_flyer(url_imagen)

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
