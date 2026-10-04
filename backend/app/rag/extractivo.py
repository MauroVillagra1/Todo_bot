"""
Respuesta extractiva (sin LLM): cuando la IA no está disponible (sin cupo,
caída), igual se responde con las oraciones de las fuentes encontradas que
mencionan lo que se preguntó, cada una con su cita. No inventa nada: son
frases textuales de las publicaciones.
"""
import re

from app.ingest.classify import normalizar
from app.rag.search import Resultado

MAX_FUENTES = 3
MAX_ORACIONES = 2
MAX_CARACTERES_ORACION = 280

VACIAS = {
    "que", "cual", "cuales", "cuando", "como", "donde", "hay", "para", "por", "con", "los", "las",
    "del", "una", "uno", "unos", "unas", "esta", "este", "estan", "son", "ser", "tiene", "tengo",
    "puedo", "quiero", "saber", "sobre", "algo", "alguna", "algun", "mas", "muy", "the",
}


def _raices(texto: str) -> set[str]:
    """Raíces cortas de las palabras de contenido ("inscripciones" → "inscr")."""
    return {t[:5] for t in re.findall(r"[a-z0-9]+", normalizar(texto)) if len(t) >= 4 and t not in VACIAS}


def _oraciones(texto: str) -> list[str]:
    partes = re.split(r"(?<=[.!?])\s+|\n+", texto)
    return [p.strip(" -•") for p in partes if len(p.strip()) >= 25]


def responder_extractivo(pregunta: str, resultados: list[Resultado]) -> tuple[str, list[int]]:
    """(texto, números de fuente usados). Usa las primeras fuentes con oraciones relevantes."""
    raices = _raices(pregunta)
    bloques, usados = [], []
    for n, r in enumerate(resultados, 1):
        # El chunk empieza con el título: no se repite como oración
        cuerpo = r.texto.split("\n", 1)[1] if r.texto.startswith(r.titulo) and "\n" in r.texto else r.texto
        puntuadas = []
        for i, oracion in enumerate(_oraciones(cuerpo)):
            aciertos = len(raices & _raices(oracion))
            if aciertos:
                puntuadas.append((aciertos, -i, oracion))
        elegidas = [o for *_, o in sorted(puntuadas, reverse=True)[:MAX_ORACIONES]]
        if not elegidas:
            continue
        frases = " ".join(
            o if len(o) <= MAX_CARACTERES_ORACION else o[:MAX_CARACTERES_ORACION].rsplit(" ", 1)[0] + "…"
            for o in elegidas
        )
        bloques.append(f"**{r.titulo}** [{n}]: {frases}")
        usados.append(n)
        if len(usados) == MAX_FUENTES:
            break

    if not bloques:
        return "", []
    encabezado = "Esto es lo que dicen las publicaciones que encontré (extracto textual, sin IA):"
    return "\n\n".join([encabezado, *bloques]), usados
