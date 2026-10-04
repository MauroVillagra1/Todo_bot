"""
División del texto en fragmentos chicos para la búsqueda (PRO-03).
Se corta por párrafos; cada chunk lleva el título para no perder contexto.
"""

MAX_CARACTERES = 1200  # ≈ 300 tokens


def dividir(titulo: str, texto: str, max_caracteres: int = MAX_CARACTERES) -> list[str]:
    if not texto.strip():
        return []

    chunks: list[str] = []
    actual: list[str] = []
    largo = 0
    for parrafo in texto.split("\n"):
        # Párrafo gigante: se corta en pedazos fijos
        while len(parrafo) > max_caracteres:
            chunks.append(parrafo[:max_caracteres])
            parrafo = parrafo[max_caracteres:]
        if actual and largo + len(parrafo) > max_caracteres:
            chunks.append("\n".join(actual))
            actual, largo = [], 0
        actual.append(parrafo)
        largo += len(parrafo) + 1
    if actual:
        chunks.append("\n".join(actual))

    return [f"{titulo}\n{c}" if titulo else c for c in chunks]
