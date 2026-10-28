"""
Servicio de chat: límite por minuto, mensajes guardados y delegación al RAG.
Los mensajes y el límite viven en Postgres (tabla mensajes_chat) porque en
serverless (Vercel) no hay memoria compartida entre invocaciones.
"""
import uuid
from datetime import timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.chat import MensajeChat
from app.models.informacion import Informacion
from app.models.voto import MotivoVotoEnum, Voto, peso
from app.models.usuario import Usuario
from app.rag.answer import responder

settings = get_settings()

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
    # Cada pregunta se responde sola: los mensajes anteriores de la conversación no se usan
    # ("y de mecatrónica?" mezclaba temas). La conversación se guarda solo para mostrarla.
    resultado = responder(db, pregunta, [])

    respuesta = _guardar_respuesta(db, usuario, conv_id, resultado, pregunta=pregunta)
    return {**resultado, "conversacion_id": conv_id, "mensaje_id": respuesta.id}


def _informaciones(resultado: dict) -> list[int]:
    return sorted({f["informacion_id"] for f in resultado.get("fuentes", []) if f.get("informacion_id")})


def _guardar_respuesta(db: Session, usuario: Usuario, conv_id: str, resultado: dict,
                       pregunta: str | None = None) -> MensajeChat:
    if pregunta is not None:
        db.add(MensajeChat(conversacion_id=conv_id, usuario_id=usuario.id, rol="user", contenido=pregunta))
    respuesta = MensajeChat(conversacion_id=conv_id, usuario_id=usuario.id, rol="assistant",
                            contenido=resultado["respuesta"], informacion_ids=_informaciones(resultado),
                            datos={k: resultado.get(k) for k in ("estado", "fuentes", "fecha_informacion")})
    db.add(respuesta)
    db.commit()
    return respuesta


# ── Votos ─────────────────────────────────────────────────────────────────────

class MensajeNoEncontrado(Exception):
    pass


SIN_OTRA_FUENTE = ("No encontré otra fuente con información sobre eso. Si sabés dónde está el dato, "
                   "podés proponerlo desde «Sugerir dato».")


def votar(db: Session, usuario: Usuario, mensaje_id: int, valor: int,
          motivo: MotivoVotoEnum | None, comentario: str | None) -> dict:
    """
    Guarda (o cambia) el voto del usuario sobre una respuesta suya y ajusta el puntaje de
    las informaciones que usó. Con "no me sirvió" busca de nuevo sin esas fuentes.
    """
    mensaje = db.get(MensajeChat, mensaje_id)
    if not mensaje or mensaje.usuario_id != usuario.id or mensaje.rol != "assistant":
        raise MensajeNoEncontrado()
    motivo = None if valor > 0 else (motivo or MotivoVotoEnum.NO_SIRVE)

    voto = db.query(Voto).filter(Voto.mensaje_id == mensaje.id, Voto.usuario_id == usuario.id).first()
    antes = peso(voto.valor, voto.motivo) if voto else 0
    if not voto:
        voto = Voto(mensaje_id=mensaje.id, usuario_id=usuario.id)
        db.add(voto)
    voto.valor, voto.motivo, voto.comentario = valor, motivo, (comentario or "").strip()[:500] or None
    voto.revisado = motivo != MotivoVotoEnum.INCORRECTO  # solo los "incorrecto" esperan a un MOD
    delta = peso(valor, motivo) - antes
    if delta and mensaje.informacion_ids:
        db.query(Informacion).filter(Informacion.id.in_(mensaje.informacion_ids)).update(
            {Informacion.puntaje_votos: Informacion.puntaje_votos + delta}, synchronize_session=False)
    db.commit()

    alternativa = None
    if motivo == MotivoVotoEnum.NO_SIRVE:
        verificar_limite(usuario, db)
        pregunta = (
            db.query(MensajeChat.contenido)
            .filter(MensajeChat.conversacion_id == mensaje.conversacion_id, MensajeChat.usuario_id == usuario.id,
                    MensajeChat.rol == "user", MensajeChat.id < mensaje.id)
            .order_by(MensajeChat.id.desc())
            .scalar()
        )
        if pregunta:
            resultado = responder(db, pregunta, [], excluir=list(mensaje.informacion_ids or []))
            if not resultado.get("fuentes"):
                resultado = {**resultado, "respuesta": SIN_OTRA_FUENTE, "estado": "NO_CONFIRMADA"}
            nueva = _guardar_respuesta(db, usuario, mensaje.conversacion_id, resultado)
            alternativa = {**resultado, "conversacion_id": mensaje.conversacion_id, "mensaje_id": nueva.id}
    return {"valor": valor, "motivo": motivo.value if motivo else None, "alternativa": alternativa}


# ── Historial de conversaciones ───────────────────────────────────────────────

MAX_CONVERSACIONES = 50


def listar_conversaciones(db: Session, usuario: Usuario) -> list[dict]:
    """Las conversaciones del usuario, la más reciente primero, con su primera pregunta como título."""
    ultimas = (
        db.query(MensajeChat.conversacion_id, func.max(MensajeChat.creado_en).label("ultima"),
                 func.count(MensajeChat.id).label("mensajes"), func.min(MensajeChat.id).label("primero"))
        .filter(MensajeChat.usuario_id == usuario.id)
        .group_by(MensajeChat.conversacion_id)
        .order_by(func.max(MensajeChat.creado_en).desc())
        .limit(MAX_CONVERSACIONES)
        .all()
    )
    titulos = dict(
        db.query(MensajeChat.id, MensajeChat.contenido).filter(MensajeChat.id.in_([u.primero for u in ultimas])).all()
    )
    return [{"id": u.conversacion_id, "titulo": (titulos.get(u.primero) or "")[:80], "ultima": u.ultima,
             "mensajes": u.mensajes} for u in ultimas]


def mensajes_de(db: Session, usuario: Usuario, conversacion_id: str) -> list[MensajeChat]:
    return (
        db.query(MensajeChat)
        .filter(MensajeChat.usuario_id == usuario.id, MensajeChat.conversacion_id == conversacion_id)
        .order_by(MensajeChat.id)
        .all()
    )


def borrar_conversacion(db: Session, usuario: Usuario, conversacion_id: str) -> int:
    """Borra los mensajes (y sus votos, en cascada). Devuelve cuántos había."""
    mensajes = mensajes_de(db, usuario, conversacion_id)
    for m in mensajes:
        db.delete(m)
    db.commit()
    return len(mensajes)
