"""
Router de documentos importantes (notas y formularios para descargar).
  GET    /api/v1/documentos                → lista (cualquier usuario), sin el archivo
  GET    /api/v1/documentos/{id}/archivo   → descarga (público: el chat lo cita con este link)
  POST   /api/v1/documentos                → subir (ADMIN): archivo ≤ 2 MB, nombre y descripción opcional
  DELETE /api/v1/documentos/{id}           → borrar (ADMIN)

Al subirlo se lee su texto (PDF o Word) y, si no se escribió una descripción, se genera una
(IA, o el comienzo del texto si la IA no está disponible). Nombre + descripción + texto entran
al pipeline como publicación: el chat sabe para qué sirve cada documento y lo cita con el link.
"""
import io
import logging
import re
import zipfile
from datetime import datetime, timezone
from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.ingest.pipeline import guardar_publicacion
from app.ingest.sources import ItemCrudo
from app.ingest.verify import procesar_pendientes
from app.models.cache import CacheRespuesta
from app.models.documento_importante import DocumentoImportante
from app.models.informacion import (
    EstadoInformacionEnum as E, Evidencia, Informacion, TipoInformacionEnum, Verificacion,
)
from app.models.ingesta import Fuente, Publicacion, TipoFuenteEnum

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documentos", tags=["Documentos importantes"])

FUENTE_DOCUMENTOS = "Documentos importantes"
MAX_BYTES = 2 * 1024 * 1024
TIPOS = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
}
MAX_TEXTO_INDEXADO = 6000
PREFIJO = "documento:"


class DocumentoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    descripcion: str
    archivo_nombre: str
    content_type: str
    tamano: int
    creado_en: datetime


def texto_de(contenido: bytes, extension: str) -> str:
    """Texto del archivo (vacío si es imagen o un PDF escaneado: no hay OCR)."""
    try:
        if extension == ".pdf":
            from pypdf import PdfReader
            paginas = [p.extract_text() or "" for p in PdfReader(io.BytesIO(contenido)).pages]
            texto = "\n".join(paginas)
        elif extension == ".docx":
            with zipfile.ZipFile(io.BytesIO(contenido)) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
            xml = re.sub(r"</w:p>", "\n", xml)
            texto = re.sub(r"<[^>]+>", "", xml)
        else:
            return ""
    except Exception as e:
        logger.warning("No se pudo leer el texto del documento: %s", str(e)[:200])
        return ""
    # Formularios: líneas de puntos y espacios de más
    texto = re.sub(r"[.…_]{4,}", " … ", texto)
    texto = re.sub(r"[ \t]+", " ", texto)
    return "\n".join(l.strip() for l in texto.splitlines() if l.strip())


def describir(nombre: str, texto: str) -> str:
    """Para qué sirve el documento, en 1-2 frases (IA). Sin IA: el comienzo del texto."""
    if texto:
        try:
            from app.services.llm import completar
            prompt = ("Este es el texto de un documento de la UTN Facultad Regional Tucumán que los estudiantes "
                      "descargan. En 1 o 2 frases en español, explicá para qué sirve, a quién se dirige y qué datos "
                      f"hay que completar. No inventes nada.\n\nNombre: {nombre}\n\nTexto:\n{texto[:2500]}")
            respuesta = completar([{"role": "user", "content": prompt}], max_tokens=150).strip()
            if len(respuesta) > 20:
                return respuesta[:1000]
        except Exception as e:
            logger.warning("Sin IA para describir el documento: %s", str(e)[:200])
        return texto[:300].replace("\n", " ") + ("…" if len(texto) > 300 else "")
    return f"Documento «{nombre}» para descargar."


def _fuente(db: Session) -> Fuente:
    fuente = db.query(Fuente).filter(Fuente.nombre == FUENTE_DOCUMENTOS).first()
    if not fuente:
        fuente = Fuente(nombre=FUENTE_DOCUMENTOS, tipo=TipoFuenteEnum.MANUAL, url=get_settings().SITE_URL,
                        confiabilidad_base=100, activa=True, config={})
        db.add(fuente)
        db.flush()
    return fuente


def url_descarga(request: Request, documento_id: int) -> str:
    url = str(request.url_for("descargar_documento", documento_id=documento_id))
    # Detrás del proxy de Vercel la URL interna llega como http
    return url if "localhost" in url or "127.0.0.1" in url or "testserver" in url else url.replace("http://", "https://", 1)


def indexar(db: Session, doc: DocumentoImportante, url: str) -> None:
    """Publicación del documento: queda buscable en el chat, sin vencimiento, citada con el link de descarga."""
    fuente = _fuente(db)
    texto = doc.texto_extraido or ""
    contenido = (f"Documento para descargar: «{doc.nombre}».\n{doc.descripcion}\n"
                 f"Se descarga desde la sección Documentos de UTNIA (menú) o desde este enlace: {url}")
    if texto:
        contenido += f"\n\nContenido del documento:\n{texto[:MAX_TEXTO_INDEXADO]}"
    ahora = datetime.now(timezone.utc)
    item = ItemCrudo(
        id_externo=f"{PREFIJO}{doc.id}", url=url, titulo=f"Documento: {doc.nombre}",
        contenido_html="".join(f"<p>{escape(l)}</p>" for l in contenido.splitlines()),
        fecha_publicacion=ahora, fecha_modificacion=ahora,
    )
    guardar_publicacion(db, fuente, item)
    db.commit()
    procesar_pendientes(db)
    for info in _informaciones(db, doc.id):
        info.tipo = TipoInformacionEnum.TRAMITE
        info.fecha_fin = None  # un formulario no vence por las fechas que tenga adentro
        info.estado = E.CONFIRMADA
    db.query(CacheRespuesta).delete()
    db.commit()


def _informaciones(db: Session, documento_id: int) -> list[Informacion]:
    return (
        db.query(Informacion)
        .join(Evidencia, Evidencia.informacion_id == Informacion.id)
        .join(Publicacion, Publicacion.id == Evidencia.publicacion_id)
        .filter(Publicacion.id_externo == f"{PREFIJO}{documento_id}")
        .distinct().all()
    )


@router.get("", response_model=list[DocumentoRead])
def listar(db: Session = Depends(get_db), _usuario=Depends(get_current_user)):
    return db.query(DocumentoImportante).order_by(DocumentoImportante.nombre).all()


@router.get("/{documento_id}/archivo", name="descargar_documento")
def descargar(documento_id: int, db: Session = Depends(get_db)):
    doc = db.get(DocumentoImportante, documento_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    return Response(
        content=doc.contenido, media_type=doc.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc.archivo_nombre)}",
            # La CDN de Vercel lo guarda un día: cada descarga no vuelve a leer la base (cupo de Neon)
            "Cache-Control": "public, max-age=3600, s-maxage=86400",
        },
    )


@router.post("", response_model=DocumentoRead, status_code=status.HTTP_201_CREATED)
async def subir(
    request: Request,
    archivo: UploadFile = File(...),
    nombre: str = Form(..., min_length=3, max_length=200),
    descripcion: str | None = Form(None, max_length=1000),
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    archivo_nombre = (archivo.filename or "documento").rsplit("/", 1)[-1].rsplit("\\", 1)[-1][:255]
    extension = ("." + archivo_nombre.rsplit(".", 1)[-1].lower()) if "." in archivo_nombre else ""
    if extension not in TIPOS:
        raise HTTPException(422, "Formato no permitido: PDF, Word (.docx/.doc) o imagen (JPG/PNG)")
    contenido = await archivo.read(MAX_BYTES + 1)
    if len(contenido) > MAX_BYTES:
        raise HTTPException(413, "El archivo pesa más de 2 MB: comprimilo o exportalo de nuevo a PDF")
    if not contenido:
        raise HTTPException(422, "El archivo está vacío")

    texto = texto_de(contenido, extension)
    doc = DocumentoImportante(
        nombre=nombre.strip(), descripcion=(descripcion or "").strip() or describir(nombre.strip(), texto),
        archivo_nombre=archivo_nombre, content_type=TIPOS[extension], tamano=len(contenido),
        contenido=contenido, texto_extraido=texto or None, subido_por=admin.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    indexar(db, doc, url_descarga(request, doc.id))
    return doc


@router.delete("/{documento_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(documento_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    doc = db.get(DocumentoImportante, documento_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    # El chat deja de citarlo (la información queda en el historial, como todo)
    for info in _informaciones(db, documento_id):
        info.estado = E.REEMPLAZADA
        db.add(Verificacion(informacion_id=info.id, resultado=E.REEMPLAZADA, puntuacion=info.confianza,
                            explicacion="Documento borrado por un administrador"))
    db.query(Publicacion).filter(Publicacion.id_externo == f"{PREFIJO}{documento_id}").update({"vigente": False})
    db.delete(doc)
    db.query(CacheRespuesta).delete()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
