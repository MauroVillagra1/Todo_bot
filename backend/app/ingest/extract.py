"""
Extracción de texto con herramientas locales (PRO-01). Sin LLM.
"""
import hashlib
import io
import logging
import re

from bs4 import BeautifulSoup

# pypdf avisa por cada PDF mal armado ("Multiple definitions…"); no son errores
logging.getLogger("pypdf").setLevel(logging.ERROR)

_ETIQUETAS_RUIDO = ["script", "style", "noscript", "iframe", "svg", "form", "button"]


def html_a_texto(html: str) -> str:
    """HTML → texto plano con un párrafo por línea."""
    sopa = BeautifulSoup(html or "", "html.parser")
    for etiqueta in sopa(_ETIQUETAS_RUIDO):
        etiqueta.decompose()
    lineas = (re.sub(r"\s+", " ", linea).strip() for linea in sopa.get_text("\n").splitlines())
    return "\n".join(linea for linea in lineas if linea)


def pdf_a_paginas(contenido: bytes) -> list[str]:
    """Texto de cada página de un PDF (vacío si es escaneado: no hay OCR para mantener costo 0)."""
    from pypdf import PdfReader

    lector = PdfReader(io.BytesIO(contenido))
    paginas = []
    for pagina in lector.pages:
        texto = pagina.extract_text() or ""
        lineas = (re.sub(r"\s+", " ", linea).strip() for linea in texto.splitlines())
        paginas.append("\n".join(linea for linea in lineas if linea))
    return paginas


def hash_bytes(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def hash_texto(texto: str) -> str:
    """sha256 del texto normalizado: cambios solo de espacios no cuentan como versión nueva."""
    normalizado = re.sub(r"\s+", " ", texto).strip().lower()
    return hashlib.sha256(normalizado.encode("utf-8")).hexdigest()
