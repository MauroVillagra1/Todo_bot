"""
Cliente único para el LLM. Varios proveedores gratuitos con la misma API
(compatible con OpenAI); se prueban en orden y si uno falla o se quedó sin
cupo se pasa al siguiente. Los proveedores sin API key configurada se saltean.

  AI_PROVEEDORES = ["openrouter|qwen/qwen3.8-27b:free", "groq|<modelo>", "gemini|<modelo>"]

Lo usa el RAG (rag/answer.py); no se llama si la búsqueda no encontró evidencia.
"""
import httpx

from app.core.config import get_settings

settings = get_settings()

# proveedor → (URL del endpoint de chat, nombre del setting con la API key)
PROVEEDORES = {
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "GEMINI_API_KEY"),
}


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
        url, setting_key = PROVEEDORES[proveedor]
        api_key = (getattr(settings, setting_key, "") or "").strip()
        if not api_key:
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
                resp = client.post(url, json=payload, headers=headers)
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
