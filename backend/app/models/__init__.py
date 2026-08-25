"""
Importa todos los modelos para que Alembic los detecte al generar migraciones.
Si agregás un modelo nuevo, importalo acá.
"""
from app.models.usuario import Usuario
from app.models.academico import (
    Materia,
    PeriodoAcademico,
    Comision,
    UsuarioComision,
)
from app.models.cursada import (
    Cursada,
    CursadaProfesor,
    CursadaExcepcion,
)
from app.models.eventos import EventoCalendario
from app.models.material import MaterialApoyo
from app.models.auditoria import RegistroCambios

__all__ = [
    "Usuario",
    "Materia",
    "PeriodoAcademico",
    "Comision",
    "UsuarioComision",
    "Cursada",
    "CursadaProfesor",
    "CursadaExcepcion",
    "EventoCalendario",
    "MaterialApoyo",
    "RegistroCambios",
]
