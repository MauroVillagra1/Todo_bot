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
        # .env.local (no se sube) pisa a .env: ahí va la base local de desarrollo
        env_file=(".env", ".env.local"),
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

    # Otros proveedores gratuitos de respaldo ("proveedor|modelo"), en orden.
    # Sin su API key se saltean. Ver services/llm.py.
    AI_PROVEEDORES: List[str] = ["gemini|auto", "groq|auto"]
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

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
    DOMINIOS_PERMITIDOS: List[str] = ["alu.frt.utn.edu.ar", "doc.frt.utn.edu.ar"]

    # ── Mail (códigos de registro y recuperación de contraseña) ───────────────
    # Gmail: smtp.gmail.com, puerto 465 y una "contraseña de aplicación" de 16 letras
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USUARIO: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_REMITENTE: str = ""  # ej. "UTNIA <utnia.frt@gmail.com>"; vacío = SMTP_USUARIO

    # ── WhatsApp (Cloud API oficial): reenvíos de posteos de canales al número del bot ──
    WHATSAPP_VERIFY_TOKEN: str = ""   # palabra secreta elegida al conectar el webhook en Meta
    WHATSAPP_APP_SECRET: str = ""     # "Clave secreta de la app" de Meta: verifica la firma
    WHATSAPP_REENVIADORES: List[str] = []  # números autorizados a reenviar (solo dígitos)
    WHATSAPP_FUENTE: str = ""          # fuente donde se guardan; vacío = la primera de WhatsApp

    # ── Cupo de Neon (plan gratis): se consulta su API para avisar antes de pasarse ──
    NEON_API_KEY: str = ""             # Neon → Account settings → API keys (empieza con "napi_")
    NEON_ORG_ID: str = ""              # "org-…": los proyectos de una organización se listan con este ID
    NEON_LIMITE_TRANSFER_GB: float = 5.0
    NEON_LIMITE_CU_HORAS: float = 100.0
    NEON_LIMITE_STORAGE_GB: float = 0.5
    NEON_AVISO_PORCENTAJE: int = 80    # desde acá el panel y la ingesta avisan

    @field_validator(
        "CORS_ORIGINS", "DOMINIOS_PERMITIDOS", "AI_PROVEEDORES", "WHATSAPP_REENVIADORES", mode="before"
    )
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

    # Un valor mal cargado en el panel de Vercel no debe tirar abajo toda la API
    @field_validator("SMTP_PORT", mode="before")
    @classmethod
    def parse_smtp_port(cls, v):
        v = str(v).strip().strip('"\'')
        return int(v) if v.isdigit() else 465

    @field_validator("SMTP_HOST", "SMTP_USUARIO", "SMTP_REMITENTE", mode="before")
    @classmethod
    def sin_espacios_ni_comillas(cls, v):
        return str(v).strip().strip('"\'') if v is not None else ""

    @field_validator("SMTP_PASSWORD", mode="before")
    @classmethod
    def password_de_aplicacion(cls, v):
        """Google muestra la contraseña de aplicación como 'abcd efgh ijkl mnop': los espacios sobran."""
        return "".join(str(v).split()).strip('"\'') if v is not None else ""

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
