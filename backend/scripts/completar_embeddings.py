"""
Vectoriza los chunks vigentes que todavía no tienen embedding (búsqueda semántica).
La ingesta lo hace sola con lo nuevo; esto es para la carga inicial.

Uso (desde backend/):
    python scripts/completar_embeddings.py            # todos los pendientes
    python scripts/completar_embeddings.py --maximo 200
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal  # noqa: E402
from app.services import embeddings  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Embeddings de chunks pendientes")
    parser.add_argument("--maximo", type=int, help="Tope de chunks a vectorizar")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        print(f"Chunks vectorizados: {embeddings.completar(db, args.maximo)}")
    finally:
        db.close()
