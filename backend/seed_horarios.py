"""
Actualiza los horarios reales de todas las cursadas en la base de datos.
Reemplaza los valores "A confirmar" con los horarios verificados del PDF.

Uso:
    python seed_horarios.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.academico import Comision, Materia
from app.models.cursada import Cursada

# ─────────────────────────────────────────────────────────────────────────────
# DATOS VERIFICADOS
# Formato: { "COMISION": { "COD_MATERIA": "horario_texto" } }
# ─────────────────────────────────────────────────────────────────────────────

HORARIOS = {

    # ── 1º AÑO ───────────────────────────────────────────────────────────────
    "1K01": {
        "P23-AM1":  "Lunes 08:00-09:30 | Jueves 08:00-09:30",
        "P23-AGA":  "Martes 08:00-09:30 | Viernes 08:00-09:30",
        "P23-AED":  "Martes 09:30-11:00 (Lab.154) | Viernes 10:15-12:30 (Lab.151)",
        "P23-AC":   "Miércoles 10:15-11:45 | Jueves 11:00-12:30",
        "P23-F1":   "Martes 11:00-12:30 | Jueves 09:30-11:00",
        "P23-LED":  "Lunes 10:15-12:30",
        "P23-SPN":  "Miércoles 08:00-10:15",
        "P23-IS":   "Miércoles 11:45-12:30",
    },
    "1K02": {
        "P23-AM1":  "Martes 10:15-12:30 | Miércoles 09:30-12:30",
        "P23-AGA":  "Martes 08:00-09:30 | Jueves 11:00-12:30 | Viernes 08:00-11:00",
        "P23-AED":  "Miércoles 08:00-09:30 (Lab.151) | Jueves 09:30-11:00",
        "P23-AC":   "Lunes 08:00-09:30 | Jueves 08:00-09:30",
        "P23-F1":   "Lunes 09:30-12:30",
        "P23-LED":  "Viernes 11:00-13:15",
        "P23-SPN":  "Martes 08:00-10:15",
        "P23-IS":   "Lunes 09:30-10:15",
    },
    "1K03": {
        "P23-AM1":  "Lunes 08:00-09:30 | Viernes 10:15-12:30",
        "P23-AGA":  "Miércoles 10:15-12:30 | Jueves 09:30-11:00",
        "P23-AED":  "Lunes 09:30-11:00 | Viernes 08:00-09:30 (Lab.151)",
        "P23-AC":   "Martes 11:00-12:30 | Jueves 08:00-09:30",
        "P23-F1":   "Lunes 11:00-12:30 | Martes 08:00-09:30",
        "P23-LED":  "Miércoles 08:00-10:15",
        "P23-SPN":  "Jueves 11:00-13:15",
        "P23-IS":   "Martes 09:30-11:00",
    },
    "1K04": {
        "P23-AM1":  "Martes 08:00-09:30 | Viernes 10:15-12:30",
        "P23-AGA":  "Miércoles 10:15-12:30 | Jueves 08:00-09:30",
        "P23-AED":  "Lunes 11:00-12:30 (Lab.151) | Jueves 11:00-13:15 (Lab.151)",
        "P23-AC":   "Lunes 09:30-11:00 | Jueves 09:30-11:00",
        "P23-F1":   "Lunes 08:00-09:30 | Miércoles 08:00-10:15",
        "P23-LED":  "Viernes 08:00-09:30",
        "P23-SPN":  "Martes 09:30-13:15",
        "P23-IS":   "Martes 09:30-10:15",
    },
    "1K05": {
        "P23-AM1":  "Jueves 11:45-12:30 | Viernes 08:00-10:15",
        "P23-AGA":  "Martes 09:30-11:45 | Miércoles 08:00-10:15",
        "P23-AED":  "Miércoles 10:15-11:00 (Lab.154) | Jueves 08:00-09:30 (Lab.151)",
        "P23-AC":   "Martes 08:00-09:30 | Jueves 10:15-11:45",
        "P23-F1":   "Miércoles 11:00-12:30 | Viernes 10:15-12:30",
        "P23-LED":  "Lunes 08:00-11:45",
        "P23-SPN":  "Lunes 11:45-12:30",
        "P23-IS":   "Martes 11:45-12:30",
    },
    "1K06": {
        "P23-AM1":  "Lunes 10:15-12:30 | Jueves 10:15-11:45",
        "P23-AGA":  "Martes 08:00-09:30 | Miércoles 08:00-09:30",
        "P23-AED":  "Martes 10:15-11:45 (Lab.154) | Jueves 08:00-09:30 (Lab.154)",
        "P23-AC":   "Martes 09:30-10:15 | Viernes 10:15-11:45",
        "P23-F1":   "Lunes 08:00-10:15 | Jueves 11:45-12:30",
        "P23-LED":  "Miércoles 09:30-11:45",
        "P23-SPN":  "Viernes 08:00-09:30",
        "P23-IS":   "Viernes 11:45-12:30",
    },
    "1K07": {
        "P23-AM1":  "Miércoles 16:15-18:30 | Jueves 13:15-15:30",
        "P23-AGA":  "Lunes 16:15-18:30 | Jueves 17:00-18:30",
        "P23-AED":  "Martes 13:15-14:45 (Lab.151) | Viernes 17:00-19:15 (Lab.151)",
        "P23-AC":   "Martes 14:45-15:30 | Viernes 15:30-17:00",
        "P23-F1":   "Lunes 14:00-16:15 | Viernes 14:00-15:30",
        "P23-LED":  "Martes 15:30-18:30",
        "P23-SPN":  "Miércoles 14:00-16:15",
        "P23-IS":   "Jueves 15:30-17:00",
    },
    "1K08": {
        "P23-AM1":  "Miércoles 14:00-15:30 | Jueves 15:30-17:00",
        "P23-AGA":  "Lunes 14:00-16:15 | Jueves 14:00-15:30",
        "P23-AED":  "Martes 17:00-18:30 | Viernes 17:00-19:15 (Lab.154)",
        "P23-AC":   "Martes 15:30-17:00 | Viernes 14:00-15:30",
        "P23-F1":   "Lunes 16:15-18:30 | Viernes 15:30-17:00",
        "P23-LED":  "Martes 14:00-15:30",
        "P23-SPN":  "Miércoles 15:30-18:30",
        "P23-IS":   "Jueves 17:00-18:30",
    },
    "1K09": {
        "P23-AM1":  "Miércoles 19:00-21:15 | Jueves 19:00-21:15",
        "P23-AGA":  "Lunes 19:00-21:15 | Jueves 17:30-19:00",
        "P23-AED":  "Lunes 21:15-23:30 (Lab.154) | Martes 19:00-20:30",
        "P23-AC":   "Jueves 21:15-23:30 | Viernes 18:15-19:00",
        "P23-F1":   "Viernes 19:00-21:15",
        "P23-LED":  "Miércoles 21:15-23:30",
        "P23-SPN":  "Martes 20:30-22:45",
        "P23-IS":   "Viernes 21:15-23:30",
    },
    "1K10": {
        "P23-AM1":  "Martes 18:15-19:45 | Miércoles 18:15-21:15",
        "P23-AGA":  "Lunes 20:30-22:45 | Jueves 18:15-19:45",
        "P23-AED":  "Jueves 19:45-21:15 (Lab.155) | Miércoles 21:15-23:30 (Lab.151)",
        "P23-AC":   "Martes 22:00-23:30 | Viernes 19:45-21:15",
        "P23-F1":   "Martes 19:45-22:00 | Viernes 18:15-19:45",
        "P23-LED":  "Lunes 19:00-20:30",
        "P23-SPN":  "Viernes 21:15-23:30",
        "P23-IS":   "Jueves 21:15-23:30",
    },

    # ── 2º AÑO ───────────────────────────────────────────────────────────────
    "2K01": {
        "P23-AM2":  "Lunes 08:00-09:30 | Jueves 08:00-13:15",
        "P23-F2":   "Miércoles 08:00-11:00 | Viernes 08:00-11:00",
        "P23-PP":   "Lunes 12:30-14:00 (Lab.151) | Martes 09:30-11:00 (Lab.151)",
        "P23-SO":   "Lunes 09:30-11:00 | Viernes 12:30-14:00 (Lab.155)",
        "P23-SSL":  "Lunes 11:00-12:30 (Lab.151) | Viernes 11:00-12:30 (Lab.154)",
        "P23-ASI":  "Martes 11:00-13:15 | Miércoles 11:00-13:15",
    },
    "2K02": {
        "P23-AM2":  "Lunes 10:15-11:45 | Martes 08:00-10:15",
        "P23-F2":   "Miércoles 10:15-11:45 | Viernes 11:00-13:15",
        "P23-PP":   "Lunes 08:45-10:15 (Lab.151) | Martes 10:15-11:45 (Lab.151)",
        "P23-SO":   "Lunes 11:45-13:15 | Viernes 09:30-11:00 (Lab.155)",
        "P23-SSL":  "Martes 11:45-13:15 (Lab.151) | Viernes 08:00-09:30 (Lab.154)",
        "P23-ASI":  "Miércoles 08:00-10:15 | Jueves 08:00-10:15",
    },
    "2K03": {
        "P23-AM2":  "Lunes 11:45-14:00 | Martes 10:15-11:45",
        "P23-F2":   "Miércoles 10:15-11:45 | Viernes 09:30-13:15",
        "P23-PP":   "Lunes 09:30-11:00 (Lab.154) | Jueves 08:00-09:30 (Lab.155)",
        "P23-SO":   "Lunes 08:00-09:30 | Viernes 08:00-09:30 (Lab.155)",
        "P23-SSL":  "Miércoles 08:45-10:15 (Lab.154) | Jueves 09:30-11:00",
        "P23-ASI":  "Martes 08:00-10:15 | Jueves 11:00-13:15",
    },
    "2K04": {
        "P23-AM2":  "Martes 13:15-19:15 | Viernes 13:15-15:30",
        "P23-F2":   "Miércoles 13:15-16:15 | Viernes 18:30-19:15",
        "P23-PP":   "Miércoles 16:15-18:30 (Lab.151) | Jueves 18:30-19:15 (Lab.155)",
        "P23-SO":   "Lunes 15:30-17:00 | Jueves 17:00-18:30 (Lab.151)",
        "P23-SSL":  "Lunes 17:00-18:30 (Lab.151) | Jueves 16:15-17:00",
        "P23-ASI":  "Lunes 13:15-15:30 | Viernes 15:30-18:30",
    },
    "2K05": {
        "P23-AM2":  "Martes 13:15-19:15",
        "P23-F2":   "Miércoles 16:15-19:15 | Viernes 13:15-16:15",
        "P23-PP":   "Miércoles 14:45-16:15 (Lab.151) | Jueves 16:15-17:45 (Lab.155)",
        "P23-SO":   "Lunes 14:00-15:30 | Jueves 14:45-16:15 (Lab.151)",
        "P23-SSL":  "Lunes 15:30-17:00 (Lab.151) | Jueves 17:45-19:15",
        "P23-ASI":  "Lunes 17:00-19:15 | Viernes 16:15-19:15",
    },
    "2K06": {
        "P23-AM2":  "Lunes 20:30-23:30 | Miércoles 19:00-21:15",
        "P23-F2":   "Martes 19:00-21:15 | Viernes 21:15-23:30",
        "P23-PP":   "Lunes 19:00-20:30 (Lab.151) | Jueves 18:15-19:00 (Lab.151)",
        "P23-SO":   "Lunes 17:30-19:00 (Aula 231)",
        "P23-SSL":  "Jueves 19:00-20:30 (Lab.151) | Viernes 19:00-21:15 (Lab.151)",
        "P23-ASI":  "Martes 21:15-23:30 | Miércoles 21:15-23:30",
    },
    "2K07": {
        "P23-AM2":  "Lunes 19:00-20:30 | Martes 21:15-23:30",
        "P23-F2":   "Miércoles 21:15-23:30 | Viernes 18:15-20:30",
        "P23-PP":   "Lunes 22:00-23:30 | Viernes 20:30-23:30 (Lab.154)",
        "P23-SO":   "Lunes 17:30-19:00 (Aula 231) | Lunes 20:30-22:00",
        "P23-SSL":  "Jueves 20:30-23:30",
        "P23-ASI":  "Martes 19:00-21:15 | Miércoles 19:00-21:15",
    },

    # ── 3º AÑO ───────────────────────────────────────────────────────────────
    "3K01": {
        "P23-ECO":  "Miércoles 13:15-16:15 | Viernes 13:15-14:00",
        "P23-CD":   "Jueves 16:15-17:00 | Viernes 16:15-17:00",
        "P23-AN":   "Lunes 16:15-18:30 | Martes 15:30-18:30",
        "P23-DS":   "Jueves 17:00-18:30 | Viernes 17:00-18:30 (Lab.154)",
        "P23-DSI":  "Lunes 14:00-16:15 | Miércoles 16:15-18:30",
        "P23-SI":   "Martes 13:15-15:30 (Lab.155)",
    },
    "3K02": {
        "P23-ECO":  "Miércoles 16:15-19:15 | Viernes 14:45-16:15",
        "P23-CD":   "Jueves 16:15-17:45 | Viernes 16:15-17:45",
        "P23-AN":   "Lunes 14:00-16:15 | Miércoles 14:00-16:15",
        "P23-DS":   "Martes 14:45-16:15 (Lab.154) | Viernes 17:45-20:00 (Lab.154)",
        "P23-DSI":  "Lunes 16:15-18:30 | Jueves 14:45-16:15",
    },
    "3K03": {
        "P23-ECO":  "Lunes 13:15-15:30 | Martes 15:30-18:30 | Viernes 17:00-18:30",
        "P23-CD":   "Martes 17:00-18:30 | Miércoles 15:30-17:00",
        "P23-AN":   "Lunes 15:30-18:30 | Jueves 15:30-17:00",
        "P23-DS":   "Martes 14:00-15:30 (Lab.154) | Viernes 14:45-17:00 (Lab.154)",
        "P23-DSI":  "Miércoles 17:00-18:30 | Viernes 13:15-14:45",
    },
    "3K04": {
        "P23-ECO":  "Lunes 19:00-21:15 | Viernes 18:15-21:15",
        "P23-CD":   "Martes 19:00-20:30 | Miércoles 19:00-20:30",
        "P23-AN":   "Jueves 20:30-23:30 | Viernes 21:15-23:30",
        "P23-DS":   "Martes 20:30-22:00 (Lab.154) | Jueves 19:00-20:30 (Lab.154)",
        "P23-DSI":  "Lunes 21:15-23:30 | Miércoles 20:30-22:45",
    },
    "3K05": {
        "P23-UXD":  "Jueves 19:00-21:15",
        "P23-UXUI": "Martes 19:00-21:15",
    },
    "3K07": {
        "P23-SEM":  "Martes 16:00-18:15 | Miércoles 16:00-18:15",
    },

    # ── 4º AÑO ───────────────────────────────────────────────────────────────
    "4K01": {
        "P23-RD":   "Lunes 16:15-18:30 | Martes 14:45-16:15 | Jueves 14:00-16:15",
        "P23-ICS":  "Martes 16:15-18:30 | Jueves 16:15-18:30",
        "P23-TA":   "Miércoles 16:15-18:30 | Viernes 16:15-18:30",
        "P23-ADSI": "Lunes 14:00-16:15 | Viernes 14:00-16:15",
    },
    "4K02": {
        "P23-RD":   "Lunes 14:00-16:15 | Martes 16:15-18:30 | Jueves 16:15-18:30 (Lab.154)",
        "P23-ICS":  "Miércoles 16:15-18:30 | Jueves 14:00-16:15",
        "P23-TA":   "Miércoles 14:00-16:15 | Viernes 14:00-16:15",
        "P23-ADSI": "Lunes 16:15-18:30 | Viernes 16:15-18:30",
    },
    "4K03": {
        "P23-RD":   "Lunes 19:00-21:15 | Martes 19:00-21:15 | Jueves 19:00-21:15",
        "P23-ICS":  "Miércoles 21:15-23:30 | Jueves 21:15-23:30",
        "P23-TA":   "Miércoles 19:00-21:15 | Viernes 19:00-21:15",
        "P23-ADSI": "Lunes 21:15-23:30 | Viernes 21:15-23:30",
    },
    "4K06": {
        "P23-CLOUD": "Lunes/Viernes 17:00-18:30 (Lab.156)",
        "P23-AGOH":  "Jueves 13:15-16:15 (Lab.156)",
        "P23-SGC":   "Martes 16:15-18:30 (Aula 108) | Jueves 16:15-18:30",
    },
    "4K07": {
        "P23-SIG":  "Martes 16:00-18:15 (Lab.151)",
        "P23-SRI":  "Miércoles 16:00-18:15 (Lab.156)",
    },
    "4K08": {
        "P23-PAD":  "Miércoles 17:45-20:45 (Lab.155)",
    },
    "4K09": {
        "P23-FID":  "Martes 19:00-20:30 | Jueves 19:00-20:30",
    },
}

# ─────────────────────────────────────────────────────────────────────────────

def actualizar_horarios(db: Session):
    actualizados = 0
    no_encontrados = []

    for nombre_comision, materias in HORARIOS.items():
        comision = db.query(Comision).filter_by(nombre=nombre_comision).first()
        if not comision:
            no_encontrados.append(f"Comisión no encontrada: {nombre_comision}")
            continue

        for codigo_materia, horario in materias.items():
            materia = db.query(Materia).filter_by(codigo=codigo_materia).first()
            if not materia:
                no_encontrados.append(f"Materia no encontrada: {codigo_materia}")
                continue

            cursada = db.query(Cursada).filter_by(
                comision_id=comision.id,
                materia_id=materia.id,
            ).first()

            if not cursada:
                no_encontrados.append(
                    f"Cursada no encontrada: {codigo_materia} en {nombre_comision}"
                )
                continue

            cursada.horario = horario
            actualizados += 1
            print(f"  ✓ {nombre_comision} / {codigo_materia}: {horario[:50]}...")

    db.commit()

    print(f"\n{'═'*60}")
    print(f"✅ Horarios actualizados: {actualizados}")
    if no_encontrados:
        print(f"\n⚠️  No encontrados ({len(no_encontrados)}):")
        for x in no_encontrados:
            print(f"  - {x}")
    print(f"{'═'*60}\n")


if __name__ == "__main__":
    print("Actualizando horarios en la base de datos...\n")
    db = SessionLocal()
    try:
        actualizar_horarios(db)
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error: {e}")
        import traceback; traceback.print_exc()
        raise
    finally:
        db.close()
