"""
Router del chatbot.
El límite de consultas por minuto se valida contra Postgres (ver chat_service).
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.usuario import Usuario
from app.models.voto import MotivoVotoEnum
from app.services.chat_service import (
    LimiteExcedido, MensajeNoEncontrado, responder_consulta, verificar_limite, votar,
)

router = APIRouter(prefix="/chat", tags=["Chatbot IA"])


class ChatRequest(BaseModel):
    mensaje: str = Field(max_length=2000)
    conversacion_id: str | None = Field(default=None, max_length=36)


class FuenteRespuesta(BaseModel):
    numero: int
    informacion_id: int | None = None
    titulo: str
    url: str
    fuente: str
    fecha: str | None = None
    estado: str


class ChatResponse(BaseModel):
    respuesta: str
    conversacion_id: str | None = None
    # CONFIRMADA | PROBABLE | NO_CONFIRMADA | DESACTUALIZADA (RAG-03);
    # CONVERSACION (saludos) y ACLARACION (pide precisar) no llevan datos institucionales
    estado: str
    fuentes: list[FuenteRespuesta] = []
    fecha_informacion: str | None = None
    desde_cache: bool = False
    mensaje_id: int | None = None  # para votar la respuesta


class VotoRequest(BaseModel):
    valor: Literal[1, -1]
    motivo: MotivoVotoEnum | None = None  # solo con -1: NO_SIRVE (default) | INCORRECTO
    comentario: str | None = Field(default=None, max_length=500)


class VotoResponse(BaseModel):
    valor: int
    motivo: str | None
    alternativa: ChatResponse | None = None  # "no me sirvió": respuesta con otras fuentes


@router.post("/", response_model=ChatResponse)
def chat(
    request_data: ChatRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Endpoint principal del asistente."""
    if not request_data.mensaje.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El mensaje no puede estar vacío",
        )

    try:
        verificar_limite(current_user, db)
    except LimiteExcedido:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas consultas. Esperá un minuto e intentá de nuevo.",
        )

    resultado = responder_consulta(
        pregunta=request_data.mensaje,
        usuario=current_user,
        db=db,
        conversacion_id=request_data.conversacion_id,
    )
    return ChatResponse(**resultado)


@router.post("/mensajes/{mensaje_id}/voto", response_model=VotoResponse)
def votar_respuesta(
    mensaje_id: int,
    datos: VotoRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """👍 / 👎 sobre una respuesta propia. Con 👎 "no me sirvió" devuelve otra respuesta."""
    try:
        return VotoResponse(**votar(db, current_user, mensaje_id, datos.valor, datos.motivo, datos.comentario))
    except MensajeNoEncontrado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Respuesta no encontrada")
    except LimiteExcedido:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Demasiadas consultas. Esperá un minuto e intentá de nuevo.")
