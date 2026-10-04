"""
Extracción de texto con herramientas locales (PRO-01). Sin LLM.
"""
import hashlib
import re

from bs4 import BeautifulSoup

_ETIQUETAS_RUIDO = ["script", "style", "noscript", "iframe", "svg", "form", "button"]


def html_a_texto(html: str) -> str:
    """HTML → texto plano con un párrafo por línea."""
    sopa = BeautifulSoup(html or "", "html.parser")
    for etiqueta in sopa(_ETIQUETAS_RUIDO):
        etiqueta.decompose()
    lineas = (re.sub(r"\s+", " ", linea).strip() for linea in sopa.get_text("\n").splitlines())
    return "\n".join(linea for linea in lineas if linea)


def hash_texto(texto: str) -> str:
    """sha256 del texto normalizado: cambios solo de espacios no cuentan como versión nueva."""
    normalizado = re.sub(r"\s+", " ", texto).strip().lower()
    return hashlib.sha256(normalizado.encode("utf-8")).hexdigest()
