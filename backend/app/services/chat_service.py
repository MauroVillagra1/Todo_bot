"""
Servicio de chat: límite por minuto, historial y delegación al RAG.
El historial y el límite viven en Postgres (tabla mensajes_chat) porque en
serverless (Vercel) no hay memoria compartida entre invocaciones.
"""
import uuid
from datetime import timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.chat import MensajeChat
from app.models.usuario import Usuario
from app.rag.answer import responder

settings = get_settings()

TURNOS_HISTORIAL = 2  # pares pregunta/respuesta que se mandan al LLM


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


def _historial(db: Session, usuario: Usuario, conversacion_id: str) -> list[dict]:
    mensajes = (
        db.query(MensajeChat)
        .filter(MensajeChat.conversacion_id == conversacion_id, MensajeChat.usuario_id == usuario.id)
        .order_by(MensajeChat.id.desc())
        .limit(TURNOS_HISTORIAL * 2)
        .all()
    )
    return [{"role": m.rol, "content": m.contenido} for m in reversed(mensajes)]


def responder_consulta(
    pregunta: str,
    usuario: Usuario,
    db: Session,
    conversacion_id: Optional[str] = None,
) -> dict:
    conv_id = conversacion_id or str(uuid.uuid4())
    historial = _historial(db, usuario, conv_id) if conversacion_id else []

    resultado = responder(db, pregunta, historial)

    db.add_all([
        MensajeChat(conversacion_id=conv_id, usuario_id=usuario.id, rol="user", contenido=pregunta),
        MensajeChat(conversacion_id=conv_id, usuario_id=usuario.id, rol="assistant",
                    contenido=resultado["respuesta"]),
    ])
    db.commit()
    return {**resultado, "conversacion_id": conv_id}
