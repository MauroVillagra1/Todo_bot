"""
Fixtures de tests: SQLite en memoria (nunca toca Neon).
Las variables de entorno se fijan antes de importar la app porque
Settings se cachea en la primera importación.
"""
import os
import sys

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ENVIRONMENT"] = "test"
os.environ["DOMINIOS_PERMITIDOS"] = '["alu.frt.utn.edu.ar"]'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.database import get_db  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models.usuario import RolEnum, Usuario  # noqa: E402

PASSWORD = "clave1234"


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _funciones_postgres(dbapi_conn, _):
        # chunks.tsv es una columna generada con to_tsvector (Postgres)
        dbapi_conn.create_function("to_tsvector", 2, lambda _cfg, texto: texto, deterministic=True)
        dbapi_conn.create_function("sin_tildes", 1, lambda texto: texto, deterministic=True)

    Usuario.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    app.dependency_overrides[get_db] = lambda: session
    yield session
    session.close()
    app.dependency_overrides.clear()


@pytest.fixture
def client(db):
    return TestClient(app)


@pytest.fixture
def crear_usuario(db):
    def _crear(email: str, rol: RolEnum = RolEnum.MIEMBRO) -> Usuario:
        u = Usuario(nombre="Test", email=email, rol=rol, password_hash=hash_password(PASSWORD))
        db.add(u)
        db.commit()
        return u
    return _crear


def auth(usuario: Usuario) -> dict:
    token = create_access_token(subject=usuario.id, rol=usuario.rol.value)
    return {"Authorization": f"Bearer {token}"}
