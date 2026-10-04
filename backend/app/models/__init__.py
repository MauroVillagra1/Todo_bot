"""
Importa todos los modelos para que Alembic los detecte al generar migraciones.
Si agregás un modelo nuevo, importalo acá.
"""
from app.models.usuario import Usuario
from app.models.auditoria import RegistroCambios
from app.models.chat import MensajeChat

__all__ = [
    "Usuario",
    "RegistroCambios",
    "MensajeChat",
]
