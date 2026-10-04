"""
Entrypoint del worker de ingesta.

Uso (desde backend/):
    python scripts/run_ingest.py                      # todas las fuentes activas
    python scripts/run_ingest.py --fuente "Sistemas FRT"

Sale con código 1 si alguna fuente terminó con error (GitHub Actions lo marca en rojo).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal  # noqa: E402
from app.ingest.pipeline import procesar_fuentes_activas  # noqa: E402
from app.ingest.verify import actualizar_vigencias, procesar_pendientes  # noqa: E402
from app.models.ingesta import EstadoIngestaEnum, Fuente  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingesta de fuentes activas")
    parser.add_argument("--fuente", help="Nombre exacto de una fuente activa")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        ingestas = procesar_fuentes_activas(db, args.fuente)
        if not ingestas:
            print("No hay fuentes activas para procesar.")
        hubo_error = False
        for ing in ingestas:
            nombre = db.get(Fuente, ing.fuente_id).nombre
            print(
                f"[{ing.estado.value}] {nombre}: nuevos={ing.nuevos} "
                f"duplicados={ing.duplicados} errores={ing.errores}"
            )
            for err in ing.detalle_errores[:10]:
                print(f"    - {err['item']}: {err['error']}")
            hubo_error |= ing.estado == EstadoIngestaEnum.ERROR

        # Clasificación y verificación de lo nuevo (sin LLM salvo ambigüedad real)
        r = procesar_pendientes(db)
        vencidas = actualizar_vigencias(db)
        print(
            f"[OK] Informaciones: creadas={r['creadas']} actualizadas={r['actualizadas']} "
            f"llamadas_llm={r['llamadas_llm']} desactualizadas={vencidas}"
        )
        return 1 if hubo_error else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
