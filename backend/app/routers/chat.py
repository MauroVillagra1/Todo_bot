"""
Router del chatbot con IA.
Usa Groq (Llama 3) con contexto de la DB filtrado por rol del usuario.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.usuario import Usuario
from app.services.chat_service import responder_consulta

settings = get_settings()
limiter  = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/chat", tags=["Chatbot IA"])


class ChatRequest(BaseModel):
    mensaje: str
    conversacion_id: str | None = None


class ChatResponse(BaseModel):
    respuesta: str
    conversacion_id: str | None = None
    fuentes: list[str] = []


@router.post("/", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_CHAT)
def chat(
    request: Request,
    request_data: ChatRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Endpoint principal del asistente.
    Construye el contexto según el rol del usuario y consulta a Groq/Llama 3.
    """
    if not request_data.mensaje.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El mensaje no puede estar vacío",
        )

    try:
        resultado = responder_consulta(
            pregunta=request_data.mensaje,
            usuario=current_user,
            db=db,
            conversacion_id=request_data.conversacion_id,
        )
        return ChatResponse(**resultado)

    except Exception as e:
        # Si la API key de Groq no está configurada o hay error de red
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="El servicio de IA no está configurado. Agregá GROQ_API_KEY al .env",
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error al procesar la consulta: {error_msg}",
        )
