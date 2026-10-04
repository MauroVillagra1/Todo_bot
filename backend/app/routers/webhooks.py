"""
Webhook de la API oficial de WhatsApp (Cloud API). Costo 0: recibir mensajes es gratis.

Flujo: un número autorizado (WHATSAPP_REENVIADORES) reenvía un posteo de un
canal al número del bot → Meta llama a este endpoint → el texto pasa por el
mismo circuito que el resto de la ingesta (hash, versionado, chunks, verificación).

  GET  /api/v1/webhooks/whatsapp  → verificación inicial que hace Meta al conectar la URL
  POST /api/v1/webhooks/whatsapp  → mensajes entrantes (firma HMAC verificada)

Siempre se responde 200 a Meta (si no, reintenta); los mensajes de números no
autorizados o sin texto se ignoran.
"""
import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.ingest.extract import hash_texto
from app.ingest.pipeline import DUPLICADO, guardar_publicacion
from app.ingest.sources import ItemCrudo
from app.ingest.verify import procesar_pendientes
from app.models.ingesta import Fuente, TipoFuenteEnum
from app.services.metricas import incrementar

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

MIN_CARACTERES = 10


def _solo_digitos(numero: str) -> str:
    return re.sub(r"\D", "", numero)


def _texto(mensaje: dict) -> str:
    """Texto del mensaje: cuerpo si es texto, pie si es foto/video/documento."""
    tipo = mensaje.get("type")
    if tipo == "text":
        return (mensaje.get("text") or {}).get("body", "")
    return (mensaje.get(tipo) or {}).get("caption", "") if tipo in ("image", "video", "document") else ""


def _fuente_whatsapp(db: Session) -> Fuente | None:
    nombre = get_settings().WHATSAPP_FUENTE
    consulta = db.query(Fuente).filter(Fuente.tipo == TipoFuenteEnum.WHATSAPP)
    if nombre:
        consulta = consulta.filter(Fuente.nombre == nombre)
    return consulta.order_by(Fuente.id).first()


@router.get("/whatsapp", response_class=PlainTextResponse)
def verificar_webhook(
    modo: str = Query("", alias="hub.mode"),
    token: str = Query("", alias="hub.verify_token"),
    desafio: str = Query("", alias="hub.challenge"),
):
    esperado = get_settings().WHATSAPP_VERIFY_TOKEN
    if esperado and modo == "subscribe" and hmac.compare_digest(token, esperado):
        return desafio
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token de verificación inválido")


@router.post("/whatsapp")
async def recibir_mensajes(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.WHATSAPP_APP_SECRET:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="WhatsApp no configurado")

    cuerpo = await request.body()
    firma = request.headers.get("X-Hub-Signature-256", "")
    esperada = "sha256=" + hmac.new(settings.WHATSAPP_APP_SECRET.encode(), cuerpo, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(firma, esperada):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Firma inválida")

    autorizados = {_solo_digitos(n) for n in settings.WHATSAPP_REENVIADORES}
    fuente = _fuente_whatsapp(db)
    resumen = {"guardados": 0, "duplicados": 0, "ignorados": 0}

    datos = json.loads(cuerpo or b"{}")
    mensajes = [
        m
        for entrada in datos.get("entry", [])
        for cambio in entrada.get("changes", [])
        for m in (cambio.get("value") or {}).get("messages", [])
    ]
    for m in mensajes:
        texto = _texto(m).strip()
        if not fuente or _solo_digitos(m.get("from", "")) not in autorizados or len(texto) < MIN_CARACTERES:
            resumen["ignorados"] += 1
            continue
        fecha = datetime.fromtimestamp(int(m.get("timestamp", 0)) or datetime.now().timestamp(), tz=timezone.utc)
        item = ItemCrudo(
            # El mismo posteo reenviado dos veces tiene otro id de mensaje: se identifica por su texto
            id_externo="wa:" + hash_texto(texto)[:32],
            url=fuente.url,
            titulo=texto.splitlines()[0][:150],
            contenido_html="".join(f"<p>{escape(linea)}</p>" for linea in texto.splitlines()),
            fecha_publicacion=fecha,
            fecha_modificacion=fecha,
        )
        if guardar_publicacion(db, fuente, item) == DUPLICADO:
            resumen["duplicados"] += 1
        else:
            resumen["guardados"] += 1
        db.commit()

    if resumen["guardados"]:
        procesar_pendientes(db)  # queda buscable en el chat de inmediato
    incrementar(db, "whatsapp_recibidos", resumen["guardados"])
    db.commit()
    return resumen
