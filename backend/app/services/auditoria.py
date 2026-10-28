"""
Historial de cambios (registro_cambios): registrar, describir y deshacer.

Cada cambio guarda una foto del antes y del después. Deshacer no borra nada: aplica la foto
del antes, agrega una fila "deshacer" y marca la original. No se deshace un cambio si después
hubo otro sobre el mismo registro (primero hay que deshacer el posterior).
"""
from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy import Date, DateTime
from sqlalchemy.orm import Session

from app.models.auditoria import RegistroCambios
from app.models.cache import CacheRespuesta
from app.models.calendario import EventoCalendario
from app.models.documento_importante import DocumentoImportante
from app.models.horario import HorarioClase
from app.models.informacion import EstadoInformacionEnum as E, Informacion, Verificacion
from app.models.mesa import MesaFecha, MesaMateria
from app.models.usuario import RolEnum, Usuario

# Planillas del panel: se deshacen restaurando la fila tal cual
TABLAS_SIMPLES = {
    "calendario_eventos": EventoCalendario,
    "mesas_fechas": MesaFecha,
    "mesas_materias": MesaMateria,
    "horarios_clases": HorarioClase,
}

NOMBRES_TABLA = {
    "calendario_eventos": "Calendario",
    "mesas_fechas": "Mesas: fechas",
    "mesas_materias": "Mesas: materias",
    "horarios_clases": "Horarios",
    "informacion": "Información",
    "paros": "Paros",
    "documentos_importantes": "Documentos",
    "usuarios": "Usuarios",
    "sugerencias": "Sugerencias",
    "importaciones": "Importación de archivo",
    "reportes": "Reportes",
    "fuentes": "Fuentes",
}

DESHACIBLES = {
    *((t, a) for t in TABLAS_SIMPLES for a in ("creacion", "actualizacion", "eliminacion")),
    ("informacion", "creacion"), ("informacion", "baja"), ("paros", "creacion"), ("paros", "baja"),
    ("documentos_importantes", "creacion"), ("documentos_importantes", "actualizacion"),
    ("documentos_importantes", "eliminacion"),
    ("usuarios", "actualizacion"),
    ("sugerencias", "baja"),
    ("reportes", "ocultar"), ("reportes", "descartar"), ("fuentes", "actualizacion"),
    ("importaciones", "creacion"),
}


def foto(obj, campos) -> dict:
    """Valores de `campos` listos para JSON (fechas en ISO, enums por su valor)."""
    salida = {}
    for c in campos:
        v = getattr(obj, c)
        if isinstance(v, (date, datetime)):
            v = v.isoformat()
        elif hasattr(v, "value"):
            v = v.value
        salida[c] = v
    return salida


def registrar(db: Session, tabla: str, registro_id: int, accion: str, antes: dict | None, despues: dict | None,
              usuario) -> RegistroCambios:
    fila = RegistroCambios(tabla_afectada=tabla, registro_id=registro_id, valor_anterior=antes,
                           valor_nuevo=despues, accion=accion, usuario_id=usuario.id)
    db.add(fila)
    return fila


def resumen(r: RegistroCambios) -> str:
    """Una línea legible: qué registro se tocó y, si cambió, qué campos."""
    datos = r.valor_nuevo or r.valor_anterior or {}
    if r.tabla_afectada == "importaciones":
        creados = (r.valor_nuevo or {}).get("creados", {})
        partes = [f"{len(ids)} en {NOMBRES_TABLA.get(t, t)}" for t, ids in creados.items() if ids]
        return f"«{datos.get('archivo', 'archivo')}»: " + (", ".join(partes) or "nada")
    nombre = next((datos[k] for k in ("actividad", "materia", "nombre", "titulo", "email") if datos.get(k)), None)
    if r.tabla_afectada == "mesas_fechas":
        nombre = f"Mesa {datos.get('mesa')} · examen {datos.get('fecha_examen')}"
    if r.tabla_afectada == "horarios_clases" and datos.get("comision"):
        nombre = f"{datos['comision']} · {nombre}"
    texto = f"«{nombre}»" if nombre else f"#{r.registro_id}"
    if r.valor_anterior and r.valor_nuevo:
        cambios = [f"{k}: {r.valor_anterior.get(k)!s} → {v!s}" for k, v in r.valor_nuevo.items()
                   if k in r.valor_anterior and r.valor_anterior.get(k) != v]
        if cambios:
            texto += " — " + "; ".join(cambios)[:300]
    return texto


def deshacible(r: RegistroCambios) -> bool:
    return r.deshecho_por_id is None and (r.tabla_afectada, r.accion) in DESHACIBLES


# ── Deshacer ──────────────────────────────────────────────────────────────────

def _conflicto(msg: str):
    raise HTTPException(status.HTTP_409_CONFLICT, msg)


def _valores(modelo, datos: dict) -> dict:
    """Foto → valores de columnas (las fechas vuelven a ser date/datetime)."""
    salida = {}
    for k, v in datos.items():
        col = modelo.__table__.columns.get(k)
        if col is None:
            continue
        if isinstance(v, str) and isinstance(col.type, DateTime):
            v = datetime.fromisoformat(v)
        elif isinstance(v, str) and isinstance(col.type, Date):
            v = date.fromisoformat(v)
        salida[k] = v
    return salida


def _derivados(obj) -> None:
    from app.ingest.datos_mesas import norma
    from app.ingest.horarios import normalizar_materia
    if isinstance(obj, MesaMateria):
        obj.materia_norm = norma(obj.materia)
    elif isinstance(obj, HorarioClase):
        obj.materia_norm = normalizar_materia(obj.materia)[:200]


def _deshacer_simple(db: Session, modelo, registro_id: int, accion: str, antes: dict | None,
                     despues: dict | None) -> tuple[dict | None, dict | None]:
    obj = db.get(modelo, registro_id)
    campos = list((antes or despues or {}).keys())
    if accion == "creacion":
        if not obj:
            _conflicto("Ese registro ya no existe")
        actual = foto(obj, campos)
        db.delete(obj)
        return actual, None
    if accion == "actualizacion":
        if not obj:
            _conflicto("Ese registro ya no existe: no se puede volver atrás el cambio")
        actual = foto(obj, campos)
        for k, v in _valores(modelo, antes).items():
            setattr(obj, k, v)
        _derivados(obj)
        return actual, antes
    # eliminacion: se vuelve a crear con el mismo id
    if obj:
        _conflicto("Ya existe un registro con ese id")
    obj = modelo(id=registro_id, **_valores(modelo, antes))
    _derivados(obj)
    db.add(obj)
    return None, antes


def _estado_informacion(db: Session, info_id: int, estado: E, explicacion: str) -> dict:
    info = db.get(Informacion, info_id)
    if not info:
        _conflicto("Esa información ya no existe")
    anterior = {"titulo": info.titulo, "estado": info.estado.value}
    info.estado = estado
    db.add(Verificacion(informacion_id=info.id, resultado=estado, puntuacion=info.confianza, explicacion=explicacion))
    return anterior


def _deshacer_documento(db: Session, r: RegistroCambios) -> tuple[dict | None, dict | None]:
    from app.routers import documentos
    doc = db.get(DocumentoImportante, r.registro_id)
    if not doc:
        _conflicto("Ese documento ya no existe")
    campos = documentos.CAMPOS_AUDITADOS
    actual = foto(doc, campos)
    if r.accion == "creacion":
        documentos.ocultar(db, doc, "Subida deshecha desde el historial de cambios")
    else:
        for k, v in _valores(DocumentoImportante, r.valor_anterior).items():
            setattr(doc, k, v)
        db.flush()
        documentos.indexar(db, doc, documentos.url_guardada(db, doc.id))
    return actual, foto(doc, campos)


def _deshacer_usuario(db: Session, r: RegistroCambios) -> tuple[dict | None, dict | None]:
    u = db.get(Usuario, r.registro_id)
    if not u:
        _conflicto("Ese usuario ya no existe")
    if u.rol == RolEnum.ADMIN:
        _conflicto("Las cuentas ADMIN no se modifican desde la app")
    actual = foto(u, r.valor_anterior.keys())
    for k, v in _valores(Usuario, r.valor_anterior).items():
        if k != "email":
            setattr(u, k, RolEnum(v) if k == "rol" else v)
    return actual, r.valor_anterior


def _deshacer_borrado_sugerencia(db: Session, r: RegistroCambios) -> tuple[dict | None, dict | None]:
    """La sugerencia vuelve a estar aceptada y el chat a usarla."""
    from app.models.ingesta import Publicacion
    from app.models.sugerencia import EstadoSugerenciaEnum as S, Sugerencia
    s = db.get(Sugerencia, r.registro_id)
    if not s:
        _conflicto("Esa sugerencia ya no existe")
    actual = {"titulo": s.titulo, "estado": s.estado.value, "motivo": s.motivo}
    s.estado, s.motivo = S.ACEPTADA, r.valor_anterior.get("motivo")
    ultima = (db.query(Publicacion).filter(Publicacion.id_externo == f"sugerencia:{s.id}")
              .order_by(Publicacion.id.desc()).first())
    if ultima:
        ultima.vigente = True
    for info_id, estado in (r.valor_anterior.get("informaciones") or {}).items():
        info = db.get(Informacion, int(info_id))
        if info and info.estado.value != estado:
            info.estado = E(estado)
            db.add(Verificacion(informacion_id=info.id, resultado=info.estado, puntuacion=info.confianza,
                                explicacion="Borrado de la sugerencia deshecho desde el historial de cambios"))
    return actual, {"titulo": s.titulo, "estado": S.ACEPTADA.value}


def _deshacer_reporte(db: Session, r: RegistroCambios) -> tuple[dict | None, dict | None]:
    """El reporte vuelve a quedar pendiente y la información sacada del chat vuelve a usarse."""
    from app.models.voto import Voto
    voto = db.get(Voto, r.registro_id)
    if not voto:
        _conflicto("Ese reporte ya no existe")
    actual = {"titulo": f"Reporte #{voto.id}", "revisado": voto.revisado, "resolucion": voto.resolucion}
    voto.revisado, voto.revisor_id, voto.resolucion = False, None, None
    for info_id, estado in (r.valor_anterior.get("informaciones") or {}).items():
        info = db.get(Informacion, int(info_id))
        if info and info.estado.value != estado:
            info.estado = E(estado)
            db.add(Verificacion(informacion_id=info.id, resultado=info.estado, puntuacion=info.confianza,
                                explicacion="Resolución del reporte deshecha desde el historial de cambios"))
    return actual, {"titulo": f"Reporte #{voto.id}", "revisado": False}


def _deshacer_importacion(db: Session, r: RegistroCambios) -> tuple[dict | None, dict | None]:
    creados = (r.valor_nuevo or {}).get("creados", {})
    for tabla, ids in creados.items():
        if tabla in TABLAS_SIMPLES:
            for obj in db.query(TABLAS_SIMPLES[tabla]).filter(TABLAS_SIMPLES[tabla].id.in_(ids)):
                db.delete(obj)
        elif tabla == "informacion":
            for i in ids:
                if (info := db.get(Informacion, i)) and info.estado != E.REEMPLAZADA:
                    _estado_informacion(db, i, E.REEMPLAZADA, "Importación deshecha desde el historial de cambios")
    db.flush()
    # Horarios que la importación había reemplazado
    for datos in (r.valor_anterior or {}).get("horarios_clases", []):
        if not db.get(HorarioClase, datos["id"]):
            db.add(HorarioClase(**_valores(HorarioClase, datos)))
    return r.valor_nuevo, r.valor_anterior


def deshacer(db: Session, r: RegistroCambios, usuario) -> RegistroCambios:
    if r.deshecho_por_id:
        _conflicto("Ese cambio ya se deshizo")
    if (r.tabla_afectada, r.accion) not in DESHACIBLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Este tipo de cambio no se puede deshacer")
    if r.tabla_afectada != "importaciones":
        posterior = (
            db.query(RegistroCambios)
            .filter(RegistroCambios.tabla_afectada == r.tabla_afectada, RegistroCambios.registro_id == r.registro_id,
                    RegistroCambios.id > r.id, RegistroCambios.deshecho_por_id.is_(None),
                    # Solo cuentan los cambios posteriores que se pueden deshacer (no un cambio de contraseña)
                    RegistroCambios.accion.in_([a for t, a in DESHACIBLES if t == r.tabla_afectada]))
            .first()
        )
        if posterior:
            _conflicto("Hay un cambio posterior sobre el mismo registro: deshacé ese primero")

    if r.tabla_afectada in TABLAS_SIMPLES:
        antes, despues = _deshacer_simple(db, TABLAS_SIMPLES[r.tabla_afectada], r.registro_id, r.accion,
                                          r.valor_anterior, r.valor_nuevo)
    elif r.tabla_afectada in ("informacion", "paros"):
        if r.accion == "creacion":
            antes = _estado_informacion(db, r.registro_id, E.REEMPLAZADA, "Carga deshecha desde el historial de cambios")
            despues = {**antes, "estado": E.REEMPLAZADA.value}
        else:  # baja: vuelve el estado que tenía
            estado = E(r.valor_anterior["estado"])
            antes = _estado_informacion(db, r.registro_id, estado, "Baja deshecha desde el historial de cambios")
            despues = {**antes, "estado": estado.value}
    elif r.tabla_afectada == "documentos_importantes":
        antes, despues = _deshacer_documento(db, r)
    elif r.tabla_afectada == "usuarios":
        antes, despues = _deshacer_usuario(db, r)
    elif r.tabla_afectada == "sugerencias":
        antes, despues = _deshacer_borrado_sugerencia(db, r)
    elif r.tabla_afectada == "reportes":
        antes, despues = _deshacer_reporte(db, r)
    elif r.tabla_afectada == "fuentes":
        from app.models.ingesta import Fuente
        antes, despues = _deshacer_simple(db, Fuente, r.registro_id, r.accion, r.valor_anterior, r.valor_nuevo)
    else:
        antes, despues = _deshacer_importacion(db, r)

    nueva = registrar(db, r.tabla_afectada, r.registro_id, "deshacer", antes, despues, usuario)
    db.flush()
    r.deshecho_por_id = nueva.id
    db.query(CacheRespuesta).delete()  # que el chat vea el cambio ya
    db.commit()
    return nueva
