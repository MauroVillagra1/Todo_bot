"""
Importa todos los modelos para que Alembic los detecte al generar migraciones.
Si agregás un modelo nuevo, importalo acá.
"""
from app.models.usuario import Usuario
from app.models.auditoria import RegistroCambios
from app.models.chat import MensajeChat
from app.models.ingesta import Chunk, Documento, Fuente, Ingesta, Publicacion
from app.models.metrica import MetricaDiaria
from app.models.informacion import Evidencia, Historial, Informacion, Verificacion

__all__ = [
    "Usuario",
    "RegistroCambios",
    "MensajeChat",
    "Fuente",
    "Documento",
    "Publicacion",
    "Chunk",
    "Ingesta",
    "MetricaDiaria",
    "Informacion",
    "Evidencia",
    "Verificacion",
    "Historial",
]
