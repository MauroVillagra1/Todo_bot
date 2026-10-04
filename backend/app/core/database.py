"""
Configuración de SQLAlchemy y sesión de base de datos.
Habilita la extensión pgvector al crear la conexión.
"""
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# ── Motor de base de datos ─────────────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    # pool_pre_ping valida la conexión antes de usarla (evita errores por
    # conexiones colgadas después de que Postgres reinicia)
    pool_pre_ping=True,
    # En desarrollo, echo=True muestra las queries generadas en consola
    echo=settings.is_development,
)


@event.listens_for(engine, "connect")
def _enable_pgvector(dbapi_conn, connection_record):
    """Activa la extensión pgvector si está disponible (silencia el error si no lo está)."""
    try:
        with dbapi_conn.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        dbapi_conn.commit()
    except Exception:
        dbapi_conn.rollback()


# ── Fábrica de sesiones ────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# ── Clase base para todos los modelos ORM ─────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Dependencia de FastAPI ─────────────────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """
    Dependencia inyectable que abre una sesión de DB por request
    y la cierra automáticamente al terminar (incluso si hay error).

    Uso en un router:
        db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
