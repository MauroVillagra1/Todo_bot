"""
Router del chatbot.
El límite de consultas por minuto se valida contra Postgres (ver chat_service).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.usuario import Usuario
from app.services.chat_service import LimiteExcedido, responder_consulta, verificar_limite

router = APIRouter(prefix="/chat", tags=["Chatbot IA"])


class ChatRequest(BaseModel):
    mensaje: str = Field(max_length=2000)
    conversacion_id: str | None = Field(default=None, max_length=36)


class ChatResponse(BaseModel):
    respuesta: str
    conversacion_id: str | None = None
    fuentes: list[str] = []


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
