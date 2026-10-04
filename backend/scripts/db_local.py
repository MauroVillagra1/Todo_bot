"""
Base PostgreSQL local para desarrollo (sin instalar nada: paquete pgserver).
Los datos quedan en backend/.pgdata; la dirección se escribe en backend/.env.local,
que pisa al DATABASE_URL de .env (Neon) mientras exista.

Uso (desde backend/):
    pip install pgserver
    python scripts/db_local.py           # levanta la base y escribe .env.local
    python scripts/db_local.py --apagar  # la detiene y borra .env.local (vuelve a Neon)

Primera vez, después de levantarla:
    python -P -c "from alembic.config import main; main()" upgrade head
"""
import os
import re
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(BACKEND, ".pgdata")
ENV_LOCAL = os.path.join(BACKEND, ".env.local")
BASE = "utnia"


def main() -> None:
    import pgserver

    if "--apagar" in sys.argv:
        srv = pgserver.get_server(DATOS, cleanup_mode="stop")
        srv.cleanup()
        if os.path.exists(ENV_LOCAL):
            os.remove(ENV_LOCAL)
        print("Base local detenida. El backend vuelve a usar el DATABASE_URL de .env.")
        return

    srv = pgserver.get_server(DATOS, cleanup_mode=None)  # queda corriendo al salir
    if BASE not in srv.psql(f"SELECT datname FROM pg_database WHERE datname = '{BASE}';"):
        srv.psql(f"CREATE DATABASE {BASE};")
    url = re.sub(r"/[^/?]*(\?|$)", f"/{BASE}\\1", srv.get_uri(), count=1)
    url = re.sub(r"^postgres(ql)?://", "postgresql://", url)
    with open(ENV_LOCAL, "w", encoding="utf-8") as f:
        f.write("# Generado por scripts/db_local.py: base local de desarrollo (pisa a .env)\n")
        f.write(f"DATABASE_URL={url}\n")
    print(f"Base local corriendo: {url}")
    print("Escrito .env.local. Para volver a Neon: python scripts/db_local.py --apagar")


if __name__ == "__main__":
    main()
