"""
Cliente único para el LLM (API compatible con OpenAI vía OpenRouter).
Prueba los modelos en orden; si uno falla, sigue con el siguiente.
Lo usa el pipeline RAG (etapa 6); el chat no lo llama mientras no haya evidencia.
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

    ultimo_error = None
    for modelo in modelos:
        try:
            payload = {
                "model": modelo,
                "messages": mensajes,
                "temperature": 0.3,
                "max_tokens": max_tokens,
            }
            with httpx.Client(timeout=30) as client:
                resp = client.post(_URL_OPENROUTER, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            if not data.get("choices"):
                raise ValueError(f"Sin respuesta del modelo {modelo}")
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            ultimo_error = e

    raise ValueError(f"Todos los modelos fallaron. Último error: {ultimo_error}")
