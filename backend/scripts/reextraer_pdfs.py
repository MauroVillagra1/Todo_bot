"""
Vuelve a extraer el texto de los PDFs ya guardados con el extractor actual
(por ejemplo, después de mejorar pdf_a_paginas). No crea versiones nuevas:
el archivo de la fuente no cambió, solo cómo leemos su texto.

Usa el original comprimido guardado en la base; si no está (PDF > 1 MB),
lo vuelve a descargar de su URL.

Uso (desde backend/):  python scripts/reextraer_pdfs.py
"""
import gzip
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.ingest.extract import hash_bytes, hash_texto  # noqa: E402
from app.ingest.pipeline import chunks_de_paginas, leer_pdf  # noqa: E402
from app.ingest.sources.base import USER_AGENT  # noqa: E402
from app.models.ingesta import Chunk, Documento  # noqa: E402


def main() -> None:
    db = SessionLocal()
    actualizados = errores = 0
    try:
        documentos = db.query(Documento).filter(Documento.vigente.is_(True)).order_by(Documento.id).all()
        for doc in documentos:
            try:
                if doc.contenido_original:
                    contenido = gzip.decompress(doc.contenido_original)
                else:
                    contenido = httpx.get(doc.url, timeout=60, headers={"User-Agent": USER_AGENT}).content
                paginas = leer_pdf(contenido)
                texto = "\n\n".join(p for p in paginas if p)

                db.query(Chunk).filter(Chunk.documento_id == doc.id).delete()
                for orden, trozo in enumerate(chunks_de_paginas(doc.nombre, paginas)):
                    db.add(Chunk(documento_id=doc.id, orden=orden, texto=trozo, hash=hash_texto(trozo)))
                doc.texto_extraido = texto
                # Mismo criterio que el pipeline: así la próxima ingesta lo reconoce como duplicado
                doc.hash = hash_texto(f"{doc.nombre}\n{texto}") if texto else hash_bytes(contenido)
                db.commit()
                actualizados += 1
            except Exception as e:
                db.rollback()
                errores += 1
                print(f"  - {doc.url}: {str(e)[:200]}")
        print(f"[OK] PDFs reextraídos: {actualizados}, errores: {errores}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
