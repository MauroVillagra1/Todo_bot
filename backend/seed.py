"""
Script de seed para datos de prueba.

Crea un conjunto mínimo de datos para poder probar todos los endpoints:
  - 1 administrador
  - 1 profesor/directivo
  - 2 alumnos
  - 2 materias
  - 1 período académico
  - 2 comisiones
  - 4 cursadas
  - Asignaciones alumno ↔ comisión y profesor ↔ cursada

Uso:
    cd backend/
    python seed.py

Se puede ejecutar varias veces sin duplicar datos (es idempotente).
"""
import sys
import os

# Asegurar que el package `app` sea importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.models import *  # registra todos los modelos en Base.metadata
from app.models.usuario import RolEnum
from app.models.academico import DuracionEnum, TipoPeriodoEnum
from app.models.cursada import ModalidadEnum, TipoExcepcionEnum


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_or_create(db: Session, model, defaults: dict, **filters):
    """
    Busca un registro por `filters`. Si no existe, lo crea con `defaults`.
    Retorna (instancia, creado: bool).
    """
    instance = db.query(model).filter_by(**filters).first()
    if instance:
        return instance, False
    instance = model(**filters, **defaults)
    db.add(instance)
    db.flush()  # obtiene el ID sin hacer commit todavía
    return instance, True


def log(created: bool, label: str):
    status = "  ✓ creado" if created else "  · ya existe"
    print(f"{status}: {label}")


# ─────────────────────────────────────────────────────────────────────────────
# Seed
# ─────────────────────────────────────────────────────────────────────────────

def seed(db: Session):

    print("\n── Usuarios ─────────────────────────────────────────────────────")

    admin, c = get_or_create(
        db, Usuario,
        defaults={"nombre": "Admin Sistema", "password_hash": hash_password("Admin1234"), "rol": RolEnum.administrador},
        email="admin@universidad.edu",
    )
    log(c, f"administrador — admin@universidad.edu / Admin1234")

    profesor, c = get_or_create(
        db, Usuario,
        defaults={"nombre": "Prof. García", "password_hash": hash_password("Profe1234"), "rol": RolEnum.profesor_directivo},
        email="garcia@universidad.edu",
    )
    log(c, f"profesor_directivo — garcia@universidad.edu / Profe1234")

    alumno1, c = get_or_create(
        db, Usuario,
        defaults={"nombre": "Ana Martínez", "password_hash": hash_password("Alumno1234"), "rol": RolEnum.alumno},
        email="ana@universidad.edu",
    )
    log(c, f"alumno — ana@universidad.edu / Alumno1234")

    alumno2, c = get_or_create(
        db, Usuario,
        defaults={"nombre": "Carlos López", "password_hash": hash_password("Alumno1234"), "rol": RolEnum.alumno},
        email="carlos@universidad.edu",
    )
    log(c, f"alumno — carlos@universidad.edu / Alumno1234")

    print("\n── Materias ─────────────────────────────────────────────────────")

    mat1, c = get_or_create(
        db, Materia,
        defaults={"nombre": "Matemática I", "duracion": DuracionEnum.cuatrimestral},
        codigo="MAT101",
    )
    log(c, "MAT101 — Matemática I")

    mat2, c = get_or_create(
        db, Materia,
        defaults={"nombre": "Programación II", "duracion": DuracionEnum.cuatrimestral},
        codigo="PRG202",
    )
    log(c, "PRG202 — Programación II")

    mat3, c = get_or_create(
        db, Materia,
        defaults={"nombre": "Base de Datos", "duracion": DuracionEnum.cuatrimestral},
        codigo="BDA301",
    )
    log(c, "BDA301 — Base de Datos")

    mat4, c = get_or_create(
        db, Materia,
        defaults={"nombre": "Inglés Técnico", "duracion": DuracionEnum.anual},
        codigo="ING101",
    )
    log(c, "ING101 — Inglés Técnico")

    print("\n── Período académico ────────────────────────────────────────────")

    periodo, c = get_or_create(
        db, PeriodoAcademico,
        defaults={
            "tipo": TipoPeriodoEnum.primer_cuatrimestre,
            "fecha_inicio": date(2025, 3, 17),
            "fecha_fin": date(2025, 7, 18),
        },
        nombre="2025 — Primer Cuatrimestre",
    )
    log(c, "2025 — Primer Cuatrimestre (17/03 → 18/07)")

    print("\n── Comisiones ───────────────────────────────────────────────────")

    comision_2k1, c = get_or_create(
        db, Comision,
        defaults={"periodo_id": periodo.id},
        nombre="2K1",
    )
    log(c, "Comisión 2K1")

    comision_3n2, c = get_or_create(
        db, Comision,
        defaults={"periodo_id": periodo.id},
        nombre="3N2",
    )
    log(c, "Comisión 3N2")

    print("\n── Inscripciones alumno ↔ comisión ──────────────────────────────")

    ins1, c = get_or_create(
        db, UsuarioComision,
        defaults={},
        usuario_id=alumno1.id,
        comision_id=comision_2k1.id,
    )
    log(c, f"Ana → Comisión 2K1")

    ins2, c = get_or_create(
        db, UsuarioComision,
        defaults={},
        usuario_id=alumno2.id,
        comision_id=comision_3n2.id,
    )
    log(c, f"Carlos → Comisión 3N2")

    print("\n── Cursadas ─────────────────────────────────────────────────────")

    cur1, c = get_or_create(
        db, Cursada,
        defaults={
            "aula": "Aula 12 — Edificio A",
            "horario": "Lunes y Miércoles 08:00–10:00",
            "modalidad": ModalidadEnum.presencial,
            "info_adicional": {"link_classroom": "https://classroom.google.com/c/MAT101"},
        },
        materia_id=mat1.id,
        comision_id=comision_2k1.id,
        periodo_id=periodo.id,
    )
    log(c, "MAT101 en 2K1 — Lun/Mié 08:00")

    cur2, c = get_or_create(
        db, Cursada,
        defaults={
            "aula": "Lab. Informática 3",
            "horario": "Martes y Jueves 14:00–16:00",
            "modalidad": ModalidadEnum.presencial,
        },
        materia_id=mat2.id,
        comision_id=comision_2k1.id,
        periodo_id=periodo.id,
    )
    log(c, "PRG202 en 2K1 — Mar/Jue 14:00")

    cur3, c = get_or_create(
        db, Cursada,
        defaults={
            "aula": "Lab. Informática 1",
            "horario": "Lunes y Viernes 18:00–20:00",
            "modalidad": ModalidadEnum.presencial,
        },
        materia_id=mat3.id,
        comision_id=comision_3n2.id,
        periodo_id=periodo.id,
    )
    log(c, "BDA301 en 3N2 — Lun/Vie 18:00")

    cur4, c = get_or_create(
        db, Cursada,
        defaults={
            "aula": None,
            "horario": "Miércoles 20:00–22:00",
            "modalidad": ModalidadEnum.virtual,
            "info_adicional": {"plataforma": "Zoom", "link": "https://zoom.us/j/123456789"},
        },
        materia_id=mat4.id,
        comision_id=comision_3n2.id,
        periodo_id=periodo.id,
    )
    log(c, "ING101 en 3N2 — Mié 20:00 (virtual)")

    print("\n── Asignación profesor ↔ cursadas ───────────────────────────────")

    for cursada, label in [(cur1, "MAT101/2K1"), (cur2, "PRG202/2K1"),
                           (cur3, "BDA301/3N2"), (cur4, "ING101/3N2")]:
        cp, c = get_or_create(
            db, CursadaProfesor,
            defaults={},
            cursada_id=cursada.id,
            profesor_id=profesor.id,
        )
        log(c, f"Prof. García → {label}")

    print("\n── Excepción de prueba ──────────────────────────────────────────")

    exc, c = get_or_create(
        db, CursadaExcepcion,
        defaults={
            "tipo": TipoExcepcionEnum.reubicacion,
            "motivo": "Refacción en Edificio A",
            "fecha_inicio": date(2025, 4, 7),
            "fecha_fin": date(2025, 4, 11),
            "aula_nueva": "Aula 5 — Edificio B",
            "horario_nuevo": None,
            "cargado_por": profesor.id,
        },
        cursada_id=cur1.id,
    )
    log(c, "Reubicación MAT101/2K1 semana del 7 al 11 de abril → Aula 5 Edificio B")

    print("\n── Evento de calendario ─────────────────────────────────────────")

    from app.models.eventos import TipoEventoEnum, AlcanceEventoEnum

    evt, c = get_or_create(
        db, EventoCalendario,
        defaults={
            "tipo": TipoEventoEnum.asueto,
            "origen": "Rectorado",
            "motivo": "Feriado nacional — Día del Trabajador",
            "fecha_fin": date(2025, 5, 1),
            "alcance": AlcanceEventoEnum.general,
            "cargado_por": admin.id,
        },
        titulo="Feriado 1° de Mayo",
        fecha_inicio=date(2025, 5, 1),
    )
    log(c, "Feriado 1° de Mayo (alcance general)")

    db.commit()
    print("\n✅ Seed completado exitosamente.\n")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Conectando a la base de datos...")
    db = SessionLocal()
    try:
        seed(db)
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error durante el seed: {e}")
        raise
    finally:
        db.close()
