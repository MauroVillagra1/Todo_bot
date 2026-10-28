"""
Importar un archivo al chat (solo ADMIN): se sube, se interpreta y se carga en la base,
como cuando se le pasan los archivos a mano a quien mantiene el sistema.
  POST /api/v1/importar/analizar   → archivo (PDF, Word .docx, .txt, .csv o .md, hasta 4 MB).
       Devuelve una vista previa, sin guardar nada:
         · PDF de grilla de horarios → bloques de clase (lector de celdas, si pdfplumber está instalado)
         · el resto → la IA extrae actividades del calendario, fechas de mesas, materias con su
           tribunal e información general. Sin IA disponible: todo el texto como una información.
  POST /api/v1/importar/confirmar  → guarda lo elegido (y corregido) de la vista previa.
       Todo queda como UN cambio en el historial: deshacerlo borra lo importado.
"""
import json
import logging
import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.ingest.datos_mesas import norma
from app.ingest.horarios import normalizar_materia
from app.models.cache import CacheRespuesta
from app.models.calendario import CATEGORIAS, EventoCalendario
from app.models.horario import HorarioClase
from app.models.mesa import MesaFecha, MesaMateria
from app.models.informacion import TipoInformacionEnum
from app.routers import informacion as router_informacion
from app.routers.calendario import EventoCreate
from app.routers.documentos import texto_de
from app.routers.horarios import BloqueCreate
from app.routers.informacion import InformacionManual
from app.routers.mesas import FechaCreate, MateriaCreate
from app.services.auditoria import foto, registrar

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/importar", tags=["Importar archivos"])

MAX_BYTES = 4 * 1024 * 1024  # Vercel no acepta cuerpos de más de 4,5 MB
EXTENSIONES = (".pdf", ".docx", ".txt", ".csv", ".md")
MAX_TEXTO_IA = 9000
MAX_ITEMS = 500
CAMPOS_HORARIO = ("documento_id", "comision", "anio", "plan", "turno", "periodo", "aula", "dia", "inicio", "fin",
                  "materia", "materia_norm", "docente", "lugar", "electiva")


class Vista(BaseModel):
    archivo: str
    metodo: str  # cómo se interpretó: "grilla", "ia" o "texto"
    calendario: list[EventoCreate] = []
    mesas_fechas: list[FechaCreate] = []
    mesas_materias: list[MateriaCreate] = []
    horarios: list[BloqueCreate] = []
    informacion: list[InformacionManual] = []
    avisos: list[str] = []


class Confirmacion(BaseModel):
    archivo: str = Field(max_length=255)
    calendario: list[EventoCreate] = Field([], max_length=MAX_ITEMS)
    mesas_fechas: list[FechaCreate] = Field([], max_length=MAX_ITEMS)
    mesas_materias: list[MateriaCreate] = Field([], max_length=MAX_ITEMS)
    horarios: list[BloqueCreate] = Field([], max_length=MAX_ITEMS * 4)
    informacion: list[InformacionManual] = Field([], max_length=50)
    # Las comisiones importadas pierden los bloques que tenían (se recuperan deshaciendo)
    reemplazar_horarios: bool = True


class Resultado(BaseModel):
    cambio_id: int
    creados: dict[str, int]
    reemplazados: int


# ── Interpretar ───────────────────────────────────────────────────────────────

def _texto(contenido: bytes, extension: str) -> str:
    if extension in (".pdf", ".docx"):
        return texto_de(contenido, extension)
    for codificacion in ("utf-8-sig", "latin-1"):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return ""


def _horarios_de_pdf(contenido: bytes, avisos: list[str]) -> list[BloqueCreate]:
    try:
        from app.ingest.horarios import leer_grillas
        from app.ingest.limpieza_horarios import limpiar_materia
        grillas = leer_grillas(contenido) or []
    except ImportError:
        avisos.append("El lector de grillas de horarios (pdfplumber) no está instalado en el servidor: "
                      "si es un PDF de horarios, cargalo con la ingesta o a mano en la pestaña Horarios.")
        return []
    except Exception as e:
        logger.warning("No se pudo leer la grilla: %s", str(e)[:200])
        return []
    bloques = []
    for g in grillas:
        if not g.comision:
            avisos.append(f"Una grilla sin comisión reconocible quedó afuera: «{g.encabezado[:80]}»")
            continue
        for b in g.bloques:
            limpio = limpiar_materia(b.materia, b.docente) if b.materia else None
            if not limpio:
                continue
            materia, docente = limpio
            try:
                bloques.append(BloqueCreate(
                    comision=g.comision, anio=g.anio, plan=g.plan, turno=g.turno, periodo=g.periodo, aula=g.aula,
                    dia=b.dia, inicio=b.inicio, fin=b.fin, materia=materia[:200], docente=docente,
                    lugar=b.lugar[:60] or None, electiva=b.electiva,
                ))
            except ValidationError:
                avisos.append(f"Bloque descartado (datos incompletos): {g.comision} {materia[:60]}")
    return bloques


PROMPT = """Sos el asistente que carga datos de la UTN Facultad Regional Tucumán en una base de datos.
Del texto de abajo, extraé SOLO lo que figure explícitamente (no inventes nada) y respondé ÚNICAMENTE un JSON:
{
  "calendario": [{"fecha_inicio": "AAAA-MM-DD", "fecha_fin": "AAAA-MM-DD o null", "actividad": "...",
                  "categoria": "una de: %s", "detalle": "texto corto o null"}],
  "mesas_fechas": [{"mesa": 1-3, "turno": número o null, "cierre_inscripcion": "AAAA-MM-DD", "fecha_examen": "AAAA-MM-DD"}],
  "mesas_materias": [{"materia": "...", "mesa": 1-3, "sede": "Casa Central" o "Anexo Concepción",
                      "presidente": "..." o null, "vocal1": "..." o null, "vocal2": "..." o null, "hora": "HH:MM" o null}],
  "informacion": [{"tipo": "una de: %s", "contenido": "texto completo y autosuficiente; la primera línea es el título",
                   "sin_vencimiento": true si es normativa o requisito permanente}]
}
Reglas: actividades con fecha (inscripciones, clases, feriados, plazos) van en "calendario"; turnos de exámenes
finales en "mesas_fechas"; tribunales de examen en "mesas_materias"; todo lo demás útil para estudiantes
(requisitos, trámites, avisos, becas) en "informacion". Listas vacías si no hay nada de ese tipo.

Archivo: %s

Texto:
%s"""


def _json_de(respuesta: str) -> dict:
    respuesta = re.sub(r"^```(?:json)?|```$", "", respuesta.strip(), flags=re.MULTILINE)
    inicio, fin = respuesta.find("{"), respuesta.rfind("}")
    return json.loads(respuesta[inicio:fin + 1])


def _validos(modelo, crudos, nombre: str, avisos: list[str]) -> list:
    salida = []
    for c in (crudos or [])[:MAX_ITEMS]:
        try:
            salida.append(modelo.model_validate(c))
        except (ValidationError, TypeError, ValueError):
            avisos.append(f"Se descartó un dato de {nombre} que la IA no completó bien: {str(c)[:120]}")
    return salida


def _con_ia(texto: str, archivo: str, vista: Vista) -> bool:
    from app.services.llm import completar
    prompt = PROMPT % (", ".join(CATEGORIAS), ", ".join(t.value for t in TipoInformacionEnum), archivo,
                       texto[:MAX_TEXTO_IA])
    try:
        datos = _json_de(completar([{"role": "user", "content": prompt}], max_tokens=3000))
    except Exception as e:
        logger.warning("La IA no pudo interpretar el archivo: %s", str(e)[:300])
        vista.avisos.append("La IA no está disponible o no devolvió datos legibles: se propone el texto como una información.")
        return False
    vista.calendario = _validos(EventoCreate, datos.get("calendario"), "calendario", vista.avisos)
    vista.mesas_fechas = _validos(FechaCreate, datos.get("mesas_fechas"), "mesas", vista.avisos)
    vista.mesas_materias = _validos(MateriaCreate, datos.get("mesas_materias"), "tribunales", vista.avisos)
    vista.informacion = _validos(InformacionManual, datos.get("informacion"), "información", vista.avisos)
    if len(texto) > MAX_TEXTO_IA:
        vista.avisos.append(f"El archivo es largo: la IA leyó los primeros {MAX_TEXTO_IA} caracteres. "
                            "Revisá que no falte nada o dividilo en partes.")
    return True


@router.post("/analizar", response_model=Vista)
async def analizar(archivo: UploadFile = File(...), _admin=Depends(require_admin)):
    nombre = (archivo.filename or "archivo").rsplit("/", 1)[-1].rsplit("\\", 1)[-1][:255]
    extension = ("." + nombre.rsplit(".", 1)[-1].lower()) if "." in nombre else ""
    if extension not in EXTENSIONES:
        raise HTTPException(422, "Formato no permitido: PDF, Word (.docx), .txt, .csv o .md")
    contenido = await archivo.read(MAX_BYTES + 1)
    if len(contenido) > MAX_BYTES:
        raise HTTPException(413, "El archivo pesa más de 4 MB: dividilo en partes")
    if not contenido:
        raise HTTPException(422, "El archivo está vacío")

    vista = Vista(archivo=nombre, metodo="texto")
    if extension == ".pdf":
        vista.horarios = _horarios_de_pdf(contenido, vista.avisos)
        if vista.horarios:
            vista.metodo = "grilla"
            return vista

    texto = _texto(contenido, extension).strip()
    if len(texto) < 20:
        raise HTTPException(422, "No se pudo leer texto del archivo (¿es un PDF escaneado o una imagen?)")
    if _con_ia(texto, nombre, vista):
        vista.metodo = "ia"
    if not any((vista.calendario, vista.mesas_fechas, vista.mesas_materias, vista.informacion)):
        vista.informacion = [InformacionManual(tipo=TipoInformacionEnum.OTRO, contenido=texto[:20000])]
        if vista.metodo == "ia":
            vista.avisos.append("La IA no encontró datos estructurados: se propone el texto como una información.")
    return vista


# ── Guardar ───────────────────────────────────────────────────────────────────

@router.post("/confirmar", response_model=Resultado, status_code=status.HTTP_201_CREATED)
def confirmar(datos: Confirmacion, db: Session = Depends(get_db), admin=Depends(require_admin)):
    creados: dict[str, list[int]] = {}

    def agregar(tabla: str, obj) -> None:
        db.add(obj)
        db.flush()
        creados.setdefault(tabla, []).append(obj.id)

    for e in datos.calendario:
        if e.fecha_fin and e.fecha_fin < e.fecha_inicio:
            raise HTTPException(422, f"«{e.actividad}»: la fecha de fin es anterior a la de inicio")
        valores = e.model_dump()
        valores["actividad"] = valores["actividad"].strip()
        if valores["fecha_fin"] == valores["fecha_inicio"]:
            valores["fecha_fin"] = None
        agregar("calendario_eventos", EventoCalendario(**valores))
    for f in datos.mesas_fechas:
        if f.cierre_inscripcion > f.fecha_examen:
            raise HTTPException(422, f"Mesa {f.mesa}: el cierre de inscripción es posterior al examen")
        agregar("mesas_fechas", MesaFecha(**f.model_dump()))
    for m in datos.mesas_materias:
        valores = m.model_dump()
        valores["materia"] = valores["materia"].strip()
        agregar("mesas_materias", MesaMateria(materia_norm=norma(valores["materia"]), **valores))

    # Horarios: las comisiones importadas reemplazan a las que había (quedan guardadas para deshacer)
    reemplazados = []
    if datos.horarios and datos.reemplazar_horarios:
        comisiones = {b.comision for b in datos.horarios}
        for h in db.query(HorarioClase).filter(HorarioClase.comision.in_(comisiones)):
            reemplazados.append({"id": h.id, **foto(h, CAMPOS_HORARIO)})
            db.delete(h)
        db.flush()
    for b in datos.horarios:
        if b.inicio >= b.fin:
            raise HTTPException(422, f"{b.comision} {b.materia}: la hora de fin es anterior a la de inicio")
        valores = b.model_dump()
        valores["anio"] = valores["anio"] or int(valores["comision"][0])
        valores["materia"] = valores["materia"].strip()
        agregar("horarios_clases", HorarioClase(documento_id=None, materia_norm=normalizar_materia(valores["materia"])[:200],
                                                **valores))
    db.commit()

    # Información: pasa por el pipeline (queda buscable en el chat de inmediato)
    for i in datos.informacion:
        contenido = i.contenido.strip()
        cargada = router_informacion._cargar(db, i.tipo, router_informacion._titulo_de(contenido), contenido, i.url,
                                             prefijo="importado:", sin_vencimiento=i.sin_vencimiento)
        creados.setdefault("informacion", []).append(cargada.informacion_id)

    cambio = registrar(db, "importaciones", 0, "creacion",
                       {"horarios_clases": reemplazados} if reemplazados else None,
                       {"archivo": datos.archivo, "creados": creados}, admin)
    db.query(CacheRespuesta).delete()
    db.commit()
    return Resultado(cambio_id=cambio.id, creados={t: len(ids) for t, ids in creados.items()},
                     reemplazados=len(reemplazados))
