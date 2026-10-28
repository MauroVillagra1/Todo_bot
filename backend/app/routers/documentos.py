"""
Router de documentos importantes (notas y formularios para descargar).
  GET    /api/v1/documentos                → lista (cualquier usuario), sin el archivo
  GET    /api/v1/documentos/{id}/archivo   → descarga (público: el chat lo cita con este link)
  POST   /api/v1/documentos                → subir (SMOD y ADMIN): archivo ≤ 2 MB, nombre, descripción y fecha opcionales
  PATCH  /api/v1/documentos/{id}           → corregir nombre, descripción o fecha, o marcarlo desactualizado (SMOD y ADMIN)
  DELETE /api/v1/documentos/{id}           → borrar (SMOD y ADMIN): se oculta; se recupera desde el historial
Todo cambio queda en el historial de cambios (se puede deshacer).

Al subirlo se lee su texto (PDF o Word) y, si no se escribió una descripción, se genera una
(IA, o el comienzo del texto si la IA no está disponible). Nombre + descripción + texto entran
al pipeline como publicación: el chat sabe para qué sirve cada documento y lo cita con el link.
"""
import io
import logging
import re
import zipfile
from datetime import date, datetime, timezone
from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_smod
from app.ingest.pipeline import guardar_publicacion
from app.ingest.sources import ItemCrudo
from app.ingest.verify import procesar_pendientes
from app.models.cache import CacheRespuesta
from app.models.documento_importante import DocumentoImportante
from app.models.informacion import (
    EstadoInformacionEnum as E, Evidencia, Informacion, TipoInformacionEnum, Verificacion,
)
from app.models.ingesta import Fuente, Publicacion, TipoFuenteEnum
from app.services.auditoria import foto, registrar

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
CAMPOS_AUDITADOS = ("nombre", "descripcion", "fecha_documento", "desactualizado", "borrado")


class DocumentoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    descripcion: str
    archivo_nombre: str
    content_type: str
    tamano: int
    fecha_documento: date | None
    desactualizado: bool
    creado_en: datetime


class DocumentoUpdate(BaseModel):
    nombre: str | None = Field(None, min_length=3, max_length=200)
    descripcion: str | None = Field(None, min_length=3, max_length=1000)
    fecha_documento: date | None = None
    desactualizado: bool | None = None


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
    contenido = f"Documento para descargar: «{doc.nombre}».\n{doc.descripcion}\n"
    if doc.fecha_documento:
        contenido += f"Fecha del documento: {doc.fecha_documento:%d/%m/%Y}.\n"
    if doc.desactualizado:
        contenido += "ATENCIÓN: este documento está marcado como desactualizado; consultá en la facultad si sigue vigente.\n"
    contenido += f"Se descarga desde la sección Documentos del chat (menú) o desde este enlace: {url}"
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
    estado = E.DESACTUALIZADA if doc.desactualizado else E.CONFIRMADA
    # La última versión vuelve a valer aunque se hubiera borrado el documento (deshacer un borrado)
    ultima = (db.query(Publicacion).filter(Publicacion.id_externo == f"{PREFIJO}{doc.id}")
              .order_by(Publicacion.id.desc()).first())
    ultima.vigente = True
    de_la_ultima = {i for (i,) in db.query(Evidencia.informacion_id).filter(Evidencia.publicacion_id == ultima.id)}
    for info in _informaciones(db, doc.id):
        if info.estado == E.REEMPLAZADA and info.id not in de_la_ultima:
            continue
        info.tipo = TipoInformacionEnum.TRAMITE
        info.fecha_fin = None  # un formulario no vence por las fechas que tenga adentro
        if info.estado != estado:
            db.add(Verificacion(informacion_id=info.id, resultado=estado, puntuacion=info.confianza,
                                explicacion="Marcado como desactualizado desde el panel" if doc.desactualizado
                                else "Documento vigente según el panel"))
        info.estado = estado
    db.query(CacheRespuesta).delete()
    db.commit()


def url_guardada(db: Session, documento_id: int) -> str:
    """Link de descarga con el que se indexó (para reindexar sin el request a mano)."""
    url = (db.query(Publicacion.url).filter(Publicacion.id_externo == f"{PREFIJO}{documento_id}")
           .order_by(Publicacion.id.desc()).limit(1).scalar())
    return url or get_settings().SITE_URL


def ocultar(db: Session, doc: DocumentoImportante, explicacion: str) -> None:
    """Borrado recuperable: no se lista ni se descarga y el chat deja de citarlo (falta el commit)."""
    doc.borrado = True
    for info in _informaciones(db, doc.id):
        if info.estado != E.REEMPLAZADA:
            info.estado = E.REEMPLAZADA
            db.add(Verificacion(informacion_id=info.id, resultado=E.REEMPLAZADA, puntuacion=info.confianza,
                                explicacion=explicacion))
    db.query(Publicacion).filter(Publicacion.id_externo == f"{PREFIJO}{doc.id}").update({"vigente": False})
    db.query(CacheRespuesta).delete()


def _vigente(db: Session, documento_id: int) -> DocumentoImportante:
    doc = db.get(DocumentoImportante, documento_id)
    if not doc or doc.borrado:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    return doc


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
    return (db.query(DocumentoImportante).filter(DocumentoImportante.borrado.is_(False))
            .order_by(DocumentoImportante.nombre).all())


@router.get("/{documento_id}/archivo", name="descargar_documento")
def descargar(documento_id: int, db: Session = Depends(get_db)):
    doc = _vigente(db, documento_id)
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
    fecha_documento: date | None = Form(None),
    db: Session = Depends(get_db),
    admin=Depends(require_smod),
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
        contenido=contenido, texto_extraido=texto or None, subido_por=admin.id, fecha_documento=fecha_documento,
    )
    db.add(doc)
    db.flush()
    registrar(db, "documentos_importantes", doc.id, "creacion", None, foto(doc, CAMPOS_AUDITADOS), admin)
    db.commit()
    db.refresh(doc)
    indexar(db, doc, url_descarga(request, doc.id))
    return doc


@router.patch("/{documento_id}", response_model=DocumentoRead)
def actualizar(documento_id: int, datos: DocumentoUpdate, request: Request, db: Session = Depends(get_db),
               usuario=Depends(require_smod)):
    doc = _vigente(db, documento_id)
    antes = foto(doc, CAMPOS_AUDITADOS)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        if valor is None and campo in ("nombre", "descripcion", "desactualizado"):
            raise HTTPException(422, f"«{campo}» no puede quedar vacío")
        setattr(doc, campo, valor.strip() if isinstance(valor, str) else valor)
    registrar(db, "documentos_importantes", doc.id, "actualizacion", antes, foto(doc, CAMPOS_AUDITADOS), usuario)
    db.commit()
    indexar(db, doc, url_descarga(request, doc.id))  # versión nueva para el chat (y el estado que corresponde)
    db.refresh(doc)
    return doc


@router.delete("/{documento_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(documento_id: int, db: Session = Depends(get_db), usuario=Depends(require_smod)):
    doc = _vigente(db, documento_id)
    antes = foto(doc, CAMPOS_AUDITADOS)
    ocultar(db, doc, "Documento borrado desde el panel")
    registrar(db, "documentos_importantes", doc.id, "eliminacion", antes, foto(doc, CAMPOS_AUDITADOS), usuario)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
