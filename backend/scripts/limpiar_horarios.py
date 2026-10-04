"""
Aplica la limpieza de nombres (app/ingest/limpieza_horarios.py) a los bloques
de horario ya guardados que vienen de PDFs. Los cargados a mano no se tocan.
Los PDFs nuevos ya se guardan limpios en la ingesta.

Uso (desde backend/):
    python scripts/limpiar_horarios.py            # solo muestra qué cambiaría
    python scripts/limpiar_horarios.py --aplicar
"""
import logging
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from app.core.database import SessionLocal  # noqa: E402
from app.ingest.horarios import normalizar_materia  # noqa: E402
from app.ingest.limpieza_horarios import limpiar_materia  # noqa: E402
from app.models.cache import CacheRespuesta  # noqa: E402
from app.models.horario import HorarioClase  # noqa: E402


def main(aplicar: bool) -> None:
    db = SessionLocal()
    cambios: Counter = Counter()
    borrados: Counter = Counter()
    for h in db.query(HorarioClase).filter(HorarioClase.documento_id.isnot(None)):
        limpio = limpiar_materia(h.materia, h.docente)
        if limpio is None:
            borrados[h.materia] += 1
            if aplicar:
                db.delete(h)
            continue
        materia, docente = limpio
        if (materia, docente) != (h.materia, h.docente):
            if materia != h.materia:
                cambios[f"materia: {h.materia}  →  {materia}"] += 1
            if docente != h.docente:
                cambios[f"docente: {h.docente}  →  {docente}"] += 1
            if aplicar:
                h.materia, h.materia_norm, h.docente = materia, normalizar_materia(materia)[:200], docente
    for texto, n in sorted(cambios.items()):
        print(f"{n:4d}  {texto}")
    for texto, n in sorted(borrados.items()):
        print(f"{n:4d}  se descarta: {texto}")
    print(f"\n{sum(cambios.values())} cambios, {sum(borrados.values())} filas descartadas")
    if aplicar:
        db.query(CacheRespuesta).delete()  # respuestas del chat con los nombres viejos
        db.commit()
        print("Aplicado.")
    else:
        print("Simulación: nada se guardó (usar --aplicar).")


if __name__ == "__main__":
    main("--aplicar" in sys.argv)
