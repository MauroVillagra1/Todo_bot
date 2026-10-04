"""
Configuración central de la aplicación.
Lee variables del archivo .env mediante pydantic-settings.
"""
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Variables viejas en un .env (ej. RATE_LIMIT_CHAT) no deben romper el arranque
        extra="ignore",
    )

    # ── Base de datos ──────────────────────────────────────────────────────────
    DATABASE_URL: str

    # ── JWT ───────────────────────────────────────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── IA ────────────────────────────────────────────────────────────────────
    # OpenRouter — https://openrouter.ai
    OPENROUTER_API_KEY: str = ""
    AI_MODEL: str = "qwen/qwen3.8-27b:free"
    SITE_URL: str = "https://utnia.netlify.app"
    SITE_NAME: str = "Asistente UTN"

    # Modelos alternativos si AI_MODEL falla (en orden)
    # Siempre se prueban después de AI_MODEL: si AI_MODEL deja de existir, el chat sigue andando
    AI_MODELOS_RESPALDO: List[str] = ["qwen/qwen3.8-27b:free", "google/gemma-4-26b-a4b-it:free"]

    # Horas que una respuesta del chat queda en caché (se invalida sola si cambian los datos)
    CACHE_TTL_HORAS: int = 6

    # Clasificación con LLM solo cuando ninguna regla coincide; tope por corrida (0 = nunca)
    CLASIFICACION_LLM_MAX_POR_CORRIDA: int = 0

    # ── Rate limiting ─────────────────────────────────────────────────────────
    # Mensajes por usuario por minuto (se cuenta en Postgres: funciona en serverless)
    CHAT_MAX_POR_MINUTO: int = 10

    # ── Entorno ───────────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── Usuarios ──────────────────────────────────────────────────────────────
    # Solo se pueden crear cuentas (y loguearse) con estos dominios de correo
    DOMINIOS_PERMITIDOS: List[str] = ["alu.frt.utn.edu.ar"]

    @field_validator("CORS_ORIGINS", "DOMINIOS_PERMITIDOS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Acepta lista JSON ["url1","url2"] o string separado por comas desde el .env."""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json
                return json.loads(v)
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache
def get_settings() -> Settings:
    """
    Retorna una instancia única de Settings (cacheada).
    Usar como dependencia de FastAPI: Depends(get_settings).
    """
    return Settings()
