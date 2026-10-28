"""Documentos importantes (subir, descargar, que el chat los encuentre, borrar), historial de chat y avisos de paro."""
import io
import zipfile
from datetime import date, timedelta

import pytest

from app.models.cache import CacheRespuesta
from app.models.chat import MensajeChat
from app.models.documento_importante import DocumentoImportante
from app.models.informacion import Evidencia, Historial, Informacion, Verificacion
from app.models.ingesta import Chunk, Documento, Fuente, Ingesta, Publicacion
from app.models.metrica import MetricaDiaria
from app.models.usuario import RolEnum
from app.models.voto import Voto
from app.routers import documentos
from conftest import auth


@pytest.fixture(autouse=True)
def tablas(db, monkeypatch):
    engine = db.get_bind()
    for m in (Fuente, Documento, Publicacion, Chunk, Ingesta, MetricaDiaria, Informacion, Evidencia,
              Verificacion, Historial, CacheRespuesta, DocumentoImportante, MensajeChat, Voto):
        m.__table__.create(engine)
    monkeypatch.setattr(documentos, "describir", lambda nombre, texto: f"Sirve para {nombre.lower()}.")


def _docx(texto: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f"<w:document><w:body><w:p><w:r><w:t>{texto}</w:t></w:r></w:p></w:body></w:document>")
    return buf.getvalue()


def test_documentos_admin_sube_todos_descargan_y_el_chat_lo_encuentra(client, db, crear_usuario):
    admin = crear_usuario("admin@alu.frt.utn.edu.ar", RolEnum.ADMIN)
    miembro = crear_usuario("a@alu.frt.utn.edu.ar")
    archivo = ("CAMBIO DE COMISIÓN.docx", _docx("REF. CAMBIO DE COMISIÓN. Solicito cambio de comisión en la materia ……"),
               "application/octet-stream")
    assert client.post("/api/v1/documentos", files={"archivo": archivo}, data={"nombre": "Cambio de comisión"},
                       headers=auth(miembro)).status_code == 403
    r = client.post("/api/v1/documentos", files={"archivo": archivo}, data={"nombre": "Cambio de comisión"},
                    headers=auth(admin))
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["descripcion"] == "Sirve para cambio de comisión."

    lista = client.get("/api/v1/documentos", headers=auth(miembro)).json()
    assert [d["nombre"] for d in lista] == ["Cambio de comisión"]
    descarga = client.get(f"/api/v1/documentos/{doc['id']}/archivo")  # público: el chat lo cita con el link
    assert descarga.status_code == 200 and descarga.content == archivo[1]
    assert "attachment" in descarga.headers["content-disposition"]

    info = db.query(Informacion).one()
    assert info.tipo.value == "TRAMITE" and info.estado.value == "CONFIRMADA" and info.fecha_fin is None
    assert "cambio de comisión" in db.query(Chunk).first().texto.lower()

    assert client.delete(f"/api/v1/documentos/{doc['id']}", headers=auth(admin)).status_code == 204
    db.refresh(info)
    assert info.estado.value == "REEMPLAZADA"
    assert client.get(f"/api/v1/documentos/{doc['id']}/archivo").status_code == 404


def test_documentos_formato_y_tamano(client, crear_usuario):
    admin = crear_usuario("admin@alu.frt.utn.edu.ar", RolEnum.ADMIN)
    exe = client.post("/api/v1/documentos", files={"archivo": ("virus.exe", b"MZ", "application/octet-stream")},
                      data={"nombre": "Algo"}, headers=auth(admin))
    assert exe.status_code == 422
    grande = client.post("/api/v1/documentos", files={"archivo": ("x.pdf", b"0" * (2 * 1024 * 1024 + 1), "application/pdf")},
                         data={"nombre": "Grande"}, headers=auth(admin))
    assert grande.status_code == 413


def test_conversaciones_propias_con_fuentes(client, db, crear_usuario):
    u = crear_usuario("a@alu.frt.utn.edu.ar")
    otro = crear_usuario("b@alu.frt.utn.edu.ar")
    r = client.post("/api/v1/chat/", json={"mensaje": "hola"}, headers=auth(u))
    conv = r.json()["conversacion_id"]
    client.post("/api/v1/chat/", json={"mensaje": "gracias", "conversacion_id": conv}, headers=auth(u))

    lista = client.get("/api/v1/chat/conversaciones", headers=auth(u)).json()
    assert len(lista) == 1 and lista[0]["titulo"] == "hola" and lista[0]["mensajes"] == 4
    mensajes = client.get(f"/api/v1/chat/conversaciones/{conv}", headers=auth(u)).json()
    assert [m["rol"] for m in mensajes] == ["user", "assistant", "user", "assistant"]
    assert mensajes[1]["estado"] == "CONVERSACION"
    # Nadie ve ni borra conversaciones ajenas
    assert client.get(f"/api/v1/chat/conversaciones/{conv}", headers=auth(otro)).status_code == 404
    assert client.delete(f"/api/v1/chat/conversaciones/{conv}", headers=auth(otro)).status_code == 404
    assert client.delete(f"/api/v1/chat/conversaciones/{conv}", headers=auth(u)).status_code == 204
    assert client.get("/api/v1/chat/conversaciones", headers=auth(u)).json() == []


def test_avisos_de_paro_y_baja(client, crear_usuario):
    mod = crear_usuario("mod@alu.frt.utn.edu.ar", RolEnum.MOD)
    miembro = crear_usuario("a@alu.frt.utn.edu.ar")
    manana = date.today() + timedelta(days=1)
    paro = client.post("/api/v1/informacion/paro", json={"tipo": "NO_DOCENTE", "fecha": manana.isoformat()},
                       headers=auth(mod)).json()
    client.post("/api/v1/informacion", json={"tipo": "AVISO", "contenido": "Otro aviso que no es un paro"}, headers=auth(mod))
    avisos = client.get("/api/v1/informacion/avisos", headers=auth(miembro)).json()
    assert [a["informacion_id"] for a in avisos] == [paro["informacion_id"]]

    assert client.delete(f"/api/v1/informacion/{paro['informacion_id']}", headers=auth(miembro)).status_code == 403
    assert client.delete(f"/api/v1/informacion/{paro['informacion_id']}", headers=auth(mod)).status_code == 204
    assert client.get("/api/v1/informacion/avisos", headers=auth(miembro)).json() == []


def test_informacion_sin_vencimiento(client, crear_usuario):
    mod = crear_usuario("mod@alu.frt.utn.edu.ar", RolEnum.MOD)
    texto = "Ordenanza 1549 (2024): reglamento de adscripción de cátedra. Vigente desde el 28/02/2024."
    vence = client.post("/api/v1/informacion", json={"tipo": "TRAMITE", "contenido": texto}, headers=auth(mod)).json()
    assert vence["estado"] == "DESACTUALIZADA"  # por la fecha vieja del texto
    permanente = client.post("/api/v1/informacion", json={"tipo": "TRAMITE", "contenido": texto + " ",
                                                          "sin_vencimiento": True}, headers=auth(mod)).json()
    assert permanente["estado"] == "CONFIRMADA" and permanente["fecha_fin"] is None
