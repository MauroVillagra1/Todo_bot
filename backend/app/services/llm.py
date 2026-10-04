"""
Cliente único para el LLM (API compatible con OpenAI vía OpenRouter).
Prueba los modelos en orden; si uno falla, sigue con el siguiente.
Lo usa el RAG (rag/answer.py); no se llama si la búsqueda no encontró evidencia.
"""
import httpx

from app.core.config import get_settings

settings = get_settings()

_URL_OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"


def completar(mensajes: list[dict], max_tokens: int = 500) -> str:
    """Envía `mensajes` (formato chat) y devuelve el texto de la respuesta."""
    api_key = settings.OPENROUTER_API_KEY.strip()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY no está configurada en las variables de entorno")

    # Modelos en orden de preferencia, sin repetidos
    modelos = list(dict.fromkeys([settings.AI_MODEL, *settings.AI_MODELOS_RESPALDO]))

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": settings.SITE_URL,
        "X-Title": settings.SITE_NAME,
        "Content-Type": "application/json",
    }

    errores = []
    for modelo in modelos:
        try:
            payload = {
                "model": modelo,
                "messages": mensajes,
                "temperature": 0.3,
                "max_tokens": max_tokens,
            }
            # Timeout corto: si hay que probar varios modelos no se pasa del límite de Vercel
            with httpx.Client(timeout=20) as client:
                resp = client.post(_URL_OPENROUTER, json=payload, headers=headers)
            if resp.status_code != 200:
                # El cuerpo dice por qué (key inválida, modelo inexistente, límite…)
                raise ValueError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            if not data.get("choices"):
                raise ValueError(f"sin respuesta: {str(data)[:200]}")
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            errores.append(f"{modelo} → {e}")

    raise ValueError("Todos los modelos fallaron: " + " | ".join(errores))
