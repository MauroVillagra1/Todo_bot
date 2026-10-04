"""
Envío de mails por SMTP (Gmail con contraseña de aplicación, Brevo, etc.).
Sin SMTP configurado: en desarrollo el mail se escribe en el log; en
producción se rechaza el envío (no se puede crear la cuenta sin el código).
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailNoConfigurado(Exception):
    pass


def enviar_email(destinatario: str, asunto: str, texto: str) -> None:
    s = get_settings()
    if not (s.SMTP_HOST and s.SMTP_USUARIO and s.SMTP_PASSWORD):
        if s.ENVIRONMENT in ("development", "test"):
            logger.warning("SMTP sin configurar. Mail a %s — %s:\n%s", destinatario, asunto, texto)
            return
        raise EmailNoConfigurado("El envío de correos no está configurado")

    msg = EmailMessage()
    msg["From"] = s.SMTP_REMITENTE or s.SMTP_USUARIO
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.set_content(texto)

    contexto = ssl.create_default_context()
    if s.SMTP_PORT == 465:
        with smtplib.SMTP_SSL(s.SMTP_HOST, s.SMTP_PORT, context=contexto, timeout=20) as smtp:
            smtp.login(s.SMTP_USUARIO, s.SMTP_PASSWORD)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(s.SMTP_HOST, s.SMTP_PORT, timeout=20) as smtp:
            smtp.starttls(context=contexto)
            smtp.login(s.SMTP_USUARIO, s.SMTP_PASSWORD)
            smtp.send_message(msg)
