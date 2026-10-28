"""
Carga inicial de una fuente WordPress por tandas, de lo más nuevo a lo más viejo, cuidando
el servidor de la facultad y el cupo de Neon. Después el worker (run_ingest.py) solo trae lo nuevo.

Uso (desde backend/):
    python scripts/cargar_por_tandas.py --fuente "UTN FRT (web)" --tanda 50 --max-tandas 2
    python scripts/cargar_por_tandas.py --fuente "UTN FRT (web)" --tanda 50 --desde-tanda 3

En cada tanda: pide `tanda` elementos (posts y páginas, ordenados por fecha descendente), los guarda,
los clasifica, genera sus vectores y mira el cupo de Neon. Frena si alguna métrica pasa --tope (%).
Al terminar todo (sin --max-tandas) deja la fuente activa con la marca de revisión al día.
"""
import argparse
import os
import re
import sys
import time
from datetime import datetime, timezone
from html import unescape

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal  # noqa: E402
from app.ingest.pipeline import DUPLICADO, guardar_publicacion  # noqa: E402
from app.ingest.sources import ItemCrudo  # noqa: E402
from app.ingest.sources.wordpress import WordPressSource, _fecha_gmt  # noqa: E402
from app.ingest.verify import procesar_pendientes  # noqa: E402
from app.models.ingesta import Fuente  # noqa: E402
from app.services import embeddings, uso_neon  # noqa: E402

PAUSA = 2.0  # segundos entre pedidos al sitio


def _items(fuente: Fuente, tipo: str, pagina: int, tanda: int) -> tuple[list[ItemCrudo], int]:
    """Una página de la colección, de lo más nuevo a lo más viejo. Devuelve (items, total de páginas)."""
    src = WordPressSource(fuente)
    api = fuente.config["api"].rstrip("/")
    with src._cliente() as client:
        resp = src._get(client, f"{api}/{tipo}", {
            "per_page": tanda, "page": pagina, "orderby": "date", "order": "desc",
            "_fields": "id,link,title,content,date_gmt,modified_gmt",
        })
    excluir = re.compile(fuente.config["excluir_titulo"]) if fuente.config.get("excluir_titulo") else None
    datos = [d for d in resp.json() if not (excluir and excluir.search(unescape(d["title"]["rendered"])))]
    items = [ItemCrudo(id_externo=f"{tipo}:{d['id']}", url=d["link"], titulo=unescape(d["title"]["rendered"]),
                       contenido_html=d["content"]["rendered"], fecha_publicacion=_fecha_gmt(d.get("date_gmt")),
                       fecha_modificacion=_fecha_gmt(d.get("modified_gmt")))
             for d in datos]
    return items, int(resp.headers.get("X-WP-TotalPages", 1))


def _cupo(tope: int) -> tuple[str, bool]:
    uso = uso_neon.consumo()
    if not uso:
        return "cupo de Neon: sin datos (falta NEON_API_KEY)", False
    texto = " · ".join(f"{m['nombre']} {m['porcentaje']:.1f}%" for m in uso["metricas"])
    return f"cupo de Neon: {texto}", any(m["porcentaje"] >= tope for m in uso["metricas"])


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fuente", required=True)
    p.add_argument("--tanda", type=int, default=50)
    p.add_argument("--desde-tanda", type=int, default=1)
    p.add_argument("--max-tandas", type=int, default=0, help="0 = hasta terminar")
    p.add_argument("--tope", type=int, default=50, help="frena si una métrica de Neon pasa este %")
    p.add_argument("--tipo", help="solo esta colección (ej. pages); la fuente no se activa al terminar")
    args = p.parse_args()

    db = SessionLocal()
    fuente = db.query(Fuente).filter(Fuente.nombre == args.fuente).one()
    tipos = [args.tipo] if args.tipo else fuente.config.get("tipos", ["posts"])
    mas_nueva: datetime | None = None
    hechas = 0
    terminado = True
    try:
        for tipo in tipos:
            pagina = args.desde_tanda if tipo == tipos[0] else 1
            while True:
                if args.max_tandas and hechas >= args.max_tandas:
                    terminado = False
                    break
                items, total = _items(fuente, tipo, pagina, args.tanda)
                nuevos = 0
                for item in items:
                    if guardar_publicacion(db, fuente, item) != DUPLICADO:
                        nuevos += 1
                    db.commit()
                    if item.fecha_modificacion and (mas_nueva is None or item.fecha_modificacion > mas_nueva):
                        mas_nueva = item.fecha_modificacion
                r = procesar_pendientes(db)
                try:
                    vectores = embeddings.completar(db, embeddings.MAXIMO_POR_INGESTA)
                except Exception as e:
                    db.rollback()
                    vectores = f"no ({str(e)[:80]})"
                hechas += 1
                cupo, pasado = _cupo(args.tope)
                ultima = items[-1].fecha_publicacion.date() if items and items[-1].fecha_publicacion else "?"
                print(f"[{tipo} {pagina}/{total}] {len(items)} leídos, {nuevos} nuevos (hasta {ultima}) · "
                      f"informaciones +{r['creadas']} · vectores {vectores} · {cupo}", flush=True)
                if pasado:
                    print(f"FRENO: una métrica de Neon pasó el {args.tope} %. Seguir otro día con --desde-tanda.")
                    return 2
                if pagina >= total:
                    break
                pagina += 1
                time.sleep(PAUSA)
            if not terminado:
                break
        if terminado and args.tipo:
            print(f"LISTO {args.tipo}. Falta el resto de las colecciones antes de activar la fuente.")
        elif terminado:
            # Carga completa: el worker sigue solo con lo que cambie desde ahora
            fuente.activa = True
            fuente.ultima_revision = mas_nueva or datetime.now(timezone.utc)
            db.commit()
            print(f"LISTO: fuente activa; el worker trae lo modificado desde {fuente.ultima_revision}.")
        else:
            print(f"PAUSADO tras {hechas} tandas. Para seguir: --desde-tanda {pagina}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
