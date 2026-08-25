"""
Entry point para Vercel (serverless ASGI).
Vercel importa la variable `app` de este archivo.
"""
import sys
import os

# Asegurar que el directorio raíz del backend esté en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: F401 — Vercel usa esta variable
