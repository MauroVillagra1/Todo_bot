"""
Alembic env.py — punto de entrada para la generación y ejecución de migraciones.

Puntos clave:
  1. Lee DATABASE_URL desde el .env (a través de Settings), no desde alembic.ini.
  2. Importa todos los modelos vía app.models para que Alembic los detecte
     al usar `alembic revision --autogenerate`.
  3. Soporta tanto modo "offline" (genera SQL sin conectar) como "online"
     (ejecuta contra la DB real).
"""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ── Asegurar que el package `app` sea importable ─────────────────────────────
# Alembic se ejecuta desde backend/, así que agregamos ese directorio al path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Importar Base y todos los modelos para autogenerate ──────────────────────
from app.core.database import Base  # noqa: E402
import app.models  # noqa: E402 — importa el __init__.py que registra todos los modelos

# ── Leer DATABASE_URL desde la configuración de la app ───────────────────────
from app.core.config import get_settings  # noqa: E402

settings = get_settings()

# ── Configuración de Alembic ──────────────────────────────────────────────────
config = context.config

# Inyectar la URL real (desde .env) en la config de Alembic
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Configurar logging según alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata de los modelos: Alembic la usa para calcular diff al autogenerar
target_metadata = Base.metadata


# ── Modo offline ──────────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """
    Genera SQL de migraciones sin conectarse a la base de datos.
    Útil para revisar los cambios antes de aplicarlos.

    Comando: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Incluir los esquemas de pgvector en la comparación
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Modo online ───────────────────────────────────────────────────────────────
def run_migrations_online() -> None:
    """
    Aplica migraciones directamente contra la base de datos.

    Comando: alembic upgrade head
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # NullPool: sin pool para migraciones, una conexión y listo
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,      # detecta cambios de tipo de columna
            compare_server_default=True,  # detecta cambios en defaults
        )

        with context.begin_transaction():
            context.run_migrations()


# ── Entry point ───────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
