"""
Cliente único para el LLM. Varios proveedores gratuitos con la misma API
(compatible con OpenAI); se prueban en orden y si uno falla o se quedó sin
cupo se pasa al siguiente. Los proveedores sin API key configurada se saltean.

  AI_PROVEEDORES = ["gemini|auto", "groq|auto"]   (por defecto)

"auto" = el backend le pregunta al proveedor qué modelos tiene y elige uno
según sus preferencias: alcanza con cargar la API key, y sigue andando
aunque el proveedor retire modelos (Google ya retiró los gemini-2.5).

Lo usa el RAG (rag/answer.py); no se llama si la búsqueda no encontró evidencia.
"""
import re

import httpx

from app.core.config import get_settings

settings = get_settings()

# proveedor → (URL base OpenAI-compatible, setting con la API key)
PROVEEDORES = {
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"),
}
# Groq: el primero disponible de esta lista
PREFERIDOS_GROQ = ["llama-3.3-70b", "llama-4-maverick", "llama-4-scout", "gpt-oss-120b", "qwen", "llama-3.1-8b"]
_NO_CHAT = ("embed", "tts", "audio", "image", "vision", "guard", "whisper", "live", "preview", "native")

_modelos_auto: dict[str, str | None] = {}  # cache por proceso


def _key(proveedor: str) -> str:
    return (getattr(settings, PROVEEDORES[proveedor][1], "") or "").strip()


def elegir_modelo(proveedor: str, ids: list[str]) -> str | None:
    """Modelo para "auto" entre los disponibles del proveedor."""
    ids = [i.removeprefix("models/") for i in ids if not any(x in i.lower() for x in _NO_CHAT)]
    if proveedor == "gemini":
        # El "flash-lite" estable más nuevo: rápido, gratis y no gasta tokens "pensando"
        versiones = [(float(m.group(1)), i) for i in ids if (m := re.fullmatch(r"gemini-(\d+(?:\.\d+)?)-flash-lite", i))]
        return max(versiones)[1] if versiones else None
    if proveedor == "groq":
        return next((i for pref in PREFERIDOS_GROQ for i in sorted(ids) if pref in i), None)
    return None


def modelo_auto(proveedor: str) -> str | None:
    if proveedor not in _modelos_auto:
        try:
            resp = httpx.get(f"{PROVEEDORES[proveedor][0]}/models",
                             headers={"Authorization": f"Bearer {_key(proveedor)}"}, timeout=15)
            resp.raise_for_status()
            _modelos_auto[proveedor] = elegir_modelo(proveedor, [m["id"] for m in resp.json().get("data", [])])
        except Exception:
            return None  # no se cachea: se reintenta en el próximo pedido
    return _modelos_auto[proveedor]


def cadena_de_modelos() -> list[tuple[str, str]]:
    """[(proveedor, modelo)] en orden, sin repetidos. AI_MODEL (OpenRouter) va primero."""
    entradas = [f"openrouter|{settings.AI_MODEL}", *settings.AI_PROVEEDORES,
                *(f"openrouter|{m}" for m in settings.AI_MODELOS_RESPALDO)]
    cadena = []
    for entrada in dict.fromkeys(entradas):
        proveedor, _, modelo = entrada.partition("|")
        if proveedor in PROVEEDORES and modelo:
            cadena.append((proveedor, modelo))
    return cadena


def completar(mensajes: list[dict], max_tokens: int = 500) -> str:
    """Envía `mensajes` (formato chat) y devuelve el texto de la respuesta."""
    errores = []
    for proveedor, modelo in cadena_de_modelos():
        api_key = _key(proveedor)
        if not api_key:
            continue
        if modelo == "auto":
            modelo = modelo_auto(proveedor)
            if not modelo:
                errores.append(f"{proveedor}/auto → no se pudo elegir modelo (¿key inválida?)")
                continue
        payload = {
            "model": modelo,
            "messages": mensajes,
            "temperature": 0.3,
            "max_tokens": max_tokens,
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        if proveedor == "openrouter":
            # Los modelos "de razonamiento" (ej. qwen3) gastan los tokens pensando
            # y devuelven content vacío; además razonar no aporta en RAG y cuesta más
            payload["reasoning"] = {"enabled": False}
            headers |= {"HTTP-Referer": settings.SITE_URL, "X-Title": settings.SITE_NAME}
        try:
            # Timeout corto: si hay que probar varios modelos no se pasa del límite de Vercel
            with httpx.Client(timeout=20) as client:
                resp = client.post(f"{PROVEEDORES[proveedor][0]}/chat/completions", json=payload, headers=headers)
            if resp.status_code != 200:
                # El cuerpo dice por qué (key inválida, modelo inexistente, sin cupo…)
                raise ValueError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            contenido = ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
            if not contenido:
                raise ValueError(f"respuesta vacía: {str(data)[:200]}")
            return contenido.strip()
        except Exception as e:
            errores.append(f"{proveedor}/{modelo} → {e}")

    if not errores:
        raise ValueError("No hay ningún proveedor de IA con API key configurada")
    raise ValueError("Todos los modelos fallaron: " + " | ".join(errores))
