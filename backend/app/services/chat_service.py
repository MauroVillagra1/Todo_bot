"""
Servicio de chat.

Etapa 0: todavía no hay información institucional cargada (la ingesta llega
en las etapas 2-5), así que no se llama al LLM — regla "sin evidencia, sin LLM".
El historial y el límite por minuto ya viven en Postgres (tabla mensajes_chat).
"""
import uuid
from datetime import timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.chat import MensajeChat
from app.models.usuario import Usuario

settings = get_settings()

RESPUESTA_SIN_INFORMACION = (
    "Todavía no tengo información institucional cargada para responder. "
    "Estado: NO CONFIRMADA."
)


class LimiteExcedido(Exception):
    """El usuario superó CHAT_MAX_POR_MINUTO."""


def verificar_limite(usuario: Usuario, db: Session) -> None:
    """Cuenta los mensajes del usuario en el último minuto (funciona en serverless)."""
    # Ventana calculada con el reloj de la base: es el mismo que pone creado_en
    desde = func.now() - timedelta(minutes=1)
    enviados = (
        db.query(MensajeChat)
        .filter(
            MensajeChat.usuario_id == usuario.id,
            MensajeChat.rol == "user",
            MensajeChat.creado_en >= desde,
        )
        .count()
    )
    if enviados >= settings.CHAT_MAX_POR_MINUTO:
        raise LimiteExcedido()


def responder_consulta(
    pregunta: str,
    usuario: Usuario,
    db: Session,
    conversacion_id: Optional[str] = None,
) -> dict:
    conv_id = conversacion_id or str(uuid.uuid4())
    respuesta = RESPUESTA_SIN_INFORMACION

    db.add_all([
        MensajeChat(conversacion_id=conv_id, usuario_id=usuario.id, rol="user", contenido=pregunta),
        MensajeChat(conversacion_id=conv_id, usuario_id=usuario.id, rol="assistant", contenido=respuesta),
    ])
    db.commit()

    return {
        "respuesta": respuesta,
        "conversacion_id": conv_id,
        "fuentes": [],
    }
