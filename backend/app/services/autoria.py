"""
Quién cargó cada información: el chat lo muestra al pie de la respuesta, en gris
("_Cargado por Ana García (ana.garcia@doc.frt.utn.edu.ar)_").

Se busca en:
  · el historial de cambios: información y paros cargados desde el panel, importaciones de archivos
  · documentos importantes: quién lo subió
  · sugerencias aceptadas: quién la propuso y quién la aprobó
Lo que viene de las fuentes automáticas (página de la facultad, campus…) no tiene autor.
"""
from sqlalchemy.orm import Session

from app.models.auditoria import RegistroCambios
from app.models.documento_importante import DocumentoImportante
from app.models.informacion import Evidencia
from app.models.ingesta import Publicacion
from app.models.sugerencia import Sugerencia
from app.models.usuario import Usuario


def _persona(u: Usuario | None) -> str | None:
    return f"{u.nombre} ({u.email})" if u else None


def _por_prefijo(db: Session, ids: list[int], prefijo: str) -> dict[int, int]:
    """{informacion_id: N} de las publicaciones "prefijoN" que respaldan esas informaciones."""
    filas = (
        db.query(Evidencia.informacion_id, Publicacion.id_externo)
        .join(Publicacion, Publicacion.id == Evidencia.publicacion_id)
        .filter(Evidencia.informacion_id.in_(ids), Publicacion.id_externo.like(f"{prefijo}%"))
        .all()
    )
    salida = {}
    for info_id, externo in filas:
        numero = externo[len(prefijo):]
        if numero.isdigit():
            salida[info_id] = int(numero)
    return salida


def autores(db: Session, informacion_ids: list[int]) -> dict[int, str]:
    """{informacion_id: "Nombre Apellido (mail)"} de las que cargó una persona."""
    ids = [i for i in informacion_ids if i]
    if not ids:
        return {}
    salida: dict[int, str] = {}

    for r, u in (
        db.query(RegistroCambios, Usuario).join(Usuario, Usuario.id == RegistroCambios.usuario_id)
        .filter(RegistroCambios.tabla_afectada.in_(("informacion", "paros")), RegistroCambios.accion == "creacion",
                RegistroCambios.registro_id.in_(ids))
    ):
        salida[r.registro_id] = f"Cargado por {_persona(u)}"

    faltan = set(ids) - set(salida)
    if faltan:  # importaciones: un solo registro con la lista de lo creado
        for r, u in (
            db.query(RegistroCambios, Usuario).join(Usuario, Usuario.id == RegistroCambios.usuario_id)
            .filter(RegistroCambios.tabla_afectada == "importaciones", RegistroCambios.accion == "creacion")
        ):
            for i in faltan & set((r.valor_nuevo or {}).get("creados", {}).get("informacion", [])):
                salida[i] = f"Cargado por {_persona(u)} (importado de «{r.valor_nuevo.get('archivo', 'un archivo')}»)"

    for info_id, doc_id in _por_prefijo(db, ids, "documento:").items():
        doc = db.get(DocumentoImportante, doc_id)
        if doc and doc.subido_por and (persona := _persona(db.get(Usuario, doc.subido_por))):
            salida.setdefault(info_id, f"Subido por {persona}")

    for info_id, sug_id in _por_prefijo(db, ids, "sugerencia:").items():
        s = db.get(Sugerencia, sug_id)
        if not s:
            continue
        autor, revisor = _persona(db.get(Usuario, s.usuario_id)), _persona(db.get(Usuario, s.revisor_id)) if s.revisor_id else None
        partes = [f"Sugerido por {autor}" if autor else None, f"aprobado por {revisor}" if revisor else None]
        if any(partes):
            salida.setdefault(info_id, " · ".join(p for p in partes if p))
    return salida


def nota_de_carga(db: Session, informacion_ids: list[int]) -> str | None:
    """Línea en cursiva (se ve gris en el chat) con quién cargó lo que usó la respuesta, o None."""
    por_info = autores(db, informacion_ids)
    textos = list(dict.fromkeys(por_info[i] for i in informacion_ids if i in por_info))  # sin repetir, en orden
    return "\n".join(f"_{t}_" for t in textos) if textos else None
