"""
Conversación básica (saludos, agradecimientos, ayuda) con respuestas fijas:
sin LLM, sin costo y sin riesgo de inventar información institucional.
Si el mensaje trae además una pregunta ("hola, ¿cuándo es AM1?"), no se
responde acá: sigue a horarios / búsqueda.
"""
import re

from app.ingest.classify import normalizar

EJEMPLOS = (
    "- ¿Qué materias tengo los lunes en la 1K01?\n"
    "- ¿Cuándo se dicta Análisis Matemático I?\n"
    "- ¿Qué materias da Moyano?\n"
    "- ¿Hay becas abiertas?"
)
PRESENTACION = (
    "Soy UTNIA, el asistente de la carrera de Ingeniería en Sistemas de la UTN FRT. "
    "Te ayudo con horarios de cursado, avisos, inscripciones, becas, pasantías y otras novedades "
    "publicadas por la facultad, y siempre te muestro de dónde sale la información."
)

# (patrón, respuesta). El patrón tiene que cubrir el mensaje completo (salvo signos).
_INTENCIONES = [
    (r"(hola|holis|holaa+|buenas|buen dia|buenos dias|buenas tardes|buenas noches|hey|que tal|saludos)"
     r"( (utnia|bot|che))?( que tal)?( como (estas|andas|va))?",
     f"¡Hola! {PRESENTACION}\n\nPodés preguntarme, por ejemplo:\n{EJEMPLOS}"),
    (r"(como (estas|andas|va|te va)|todo bien|que onda)( (utnia|bot))?",
     "¡Todo bien, gracias por preguntar! ¿En qué te puedo ayudar? Por ejemplo:\n" + EJEMPLOS),
    (r"((muchas )?gracias|mil gracias|gracias (genio|crack|capo)|genial|perfecto|joya|buenisimo|excelente|"
     r"de una|dale|ok|okey|listo|barbaro)( gracias)?",
     "¡De nada! Si necesitás algo más, preguntame."),
    (r"(chau|chao|adios|hasta luego|hasta manana|nos vemos|bye)( (gracias|utnia))?",
     "¡Hasta luego! Cuando quieras, acá estoy."),
    (r"(quien sos|que sos|que (podes|puedes|sabes) hacer|para que servis|en que (me )?(podes|puedes) ayudar|"
     r"ayuda|help|como funciona(s)?|que (se )?te puedo preguntar)",
     f"{PRESENTACION}\n\nRespondo solo con información de fuentes institucionales (la web de "
     f"Sistemas FRT, sus PDFs de horarios y los canales autorizados). Si algo no está publicado, te lo digo.\n\n"
     f"Probá con:\n{EJEMPLOS}"),
]


def responder_conversacion(mensaje: str) -> dict | None:
    texto = re.sub(r"[^a-z0-9ñ ]", " ", normalizar(mensaje))
    texto = re.sub(r"\s+", " ", texto).strip()
    if not texto or len(texto.split()) > 8:
        return None
    for patron, respuesta in _INTENCIONES:
        if re.fullmatch(patron, texto):
            return {"respuesta": respuesta, "estado": "CONVERSACION", "fuentes": [], "fecha_informacion": None}
    return None
