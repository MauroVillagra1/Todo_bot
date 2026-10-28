"""
Lee el texto de un flyer (imagen) con Gemini. Solo para publicaciones de Instagram sin descripción:
las que tienen texto se cargan con su descripción y no gastan este cupo.
"""
import base64
import logging

import httpx

from app.services import llm

logger = logging.getLogger(__name__)

MAX_BYTES_IMAGEN = 5 * 1024 * 1024
SIN_TEXTO = "SIN_TEXTO"
PROMPT = (
    "Es un flyer publicado en Instagram por la UTN Facultad Regional Tucumán. Transcribí en español todo "
    "el texto informativo que tiene (título, fechas, horarios, lugares, requisitos, links, contactos), en "
    "el orden en que se lee, en líneas simples y sin agregar nada que no esté en la imagen. La primera "
    f"línea tiene que ser el título. Si la imagen no tiene texto informativo, respondé solo: {SIN_TEXTO}"
)


def leer_flyer(url_imagen: str) -> str | None:
    """Texto del flyer, o None si no tiene texto, no se pudo descargar o la IA no está disponible."""
    if not llm._key("gemini"):
        return None
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            imagen = client.get(url_imagen)
            imagen.raise_for_status()
            if len(imagen.content) > MAX_BYTES_IMAGEN:
                return None
            tipo = imagen.headers.get("content-type", "image/jpeg").split(";")[0]
            modelo = llm.modelo_auto("gemini")
            if not modelo:
                return None
            datos = f"data:{tipo};base64,{base64.b64encode(imagen.content).decode()}"
            resp = client.post(
                f"{llm.PROVEEDORES['gemini'][0]}/chat/completions",
                headers={"Authorization": f"Bearer {llm._key('gemini')}"},
                json={"model": modelo, "max_tokens": 800, "temperature": 0.1, "messages": [{"role": "user", "content": [
                    {"type": "text", "text": PROMPT}, {"type": "image_url", "image_url": {"url": datos}}]}]},
                timeout=60,
            )
            resp.raise_for_status()
            texto = (resp.json()["choices"][0]["message"].get("content") or "").strip()
    except Exception as e:
        logger.warning("No se pudo leer el flyer: %s", str(e)[:200])
        return None
    return None if not texto or SIN_TEXTO in texto[:30] else texto
