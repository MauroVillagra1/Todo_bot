"""
Limpieza de los nombres que vienen de las grillas en PDF, antes de guardarlos:
  - Docentes escritos de varias formas → una sola ("Vivente Francisco" →
    "Vicente Francisco", "Paredi, Mario" → "Paredi Mario", "Ing. RUIZ" → "Ruiz").
  - Dos docentes pegados sin guion → separados con " - ".
  - Materias abreviadas o con variantes → el nombre completo
    ("Parad. De Programacion" → "Paradigmas de Programación").
  - Docente metido en el nombre de la materia ("Comunicaciones - (aux. Elías, Roberto)")
    → se pasa al campo docente.
  - Fragmentos que no son materias ("*** cambuia de", "6 hs") → se descartan.
Solo se unen variantes que claramente son lo mismo; ante la duda se dejan separadas.
"""
import re

from app.ingest.horarios import normalizar_materia, separar_docentes

# ── Docentes ──────────────────────────────────────────────────────────────────

# clave (sin tildes, minúsculas, sin puntuación) → nombre canónico "Apellido Nombre"
_DOCENTES = {
    "albarracion hernan": "Albarracin Hernan",
    "alejandra de lucas": "De Luca Alejandra",
    "alexandra dufour": "Dufour Alexandra",
    "analia barrionuevo": "Barrionuevo Analia",
    "ariel martinez": "Martinez Ariel",
    "bascolo alejandro": "Báscolo Alejandro",
    "canto javier": "Cantó Javier",
    "javier canto": "Cantó Javier",
    "caporale concepcion": "Caporale Maria Concepcion",
    "carlos mambrini": "Mambrini Carlos",
    "carrile jose maria": "Carriles José María",
    "carriles jm": "Carriles José María",
    "daniel ibarra": "Ibarra Daniel",
    "de la cruz jose": "De La Cruz José",
    "eduardo nemer": "Nemer Eduardo",
    "elias roberto": "Elías Roberto",
    "roberto elias": "Elías Roberto",
    "figueroa de la cruz": "Figueroa De La Cruz Mario",
    "figueroa dee la cruz": "Figueroa De La Cruz Mario",
    "figueroa de la cruz mario": "Figueroa De La Cruz Mario",
    "gonzales juan p": "González Quinteros Juan P",
    "gonzalez juan p": "González Quinteros Juan P",
    "gonzalez quinteros juan p": "González Quinteros Juan P",
    "gonzalez quinteros": "González Quinteros Juan P",
    "guillermo brito": "Brito Guillermo",
    "hadad rosana": "Hadad Salomon Rosana",
    "hadad salomon r": "Hadad Salomon Rosana",
    "hadad salomon rosana": "Hadad Salomon Rosana",
    "loando": "Loandos Edmundo",
    "loandos edmundos": "Loandos Edmundo",
    "marta ronveaux": "Ronveaux Marta",
    "nasrallah augusto jose": "Nasrallah José Augusto",
    "nasrallah jose": "Nasrallah José Augusto",
    "nasrallah jose augusto": "Nasrallah José Augusto",
    "quiroga hamoud": "Quiroga Hamoud Celeste",
    "susana moya": "Moya Susana",
    "valdez ocampo t": "Valdez Ocampo Teresa",
    "vivente francisco": "Vicente Francisco",
    "zakhour jose": "Zakhour José",
    "zakour jose": "Zakhour José",
    # Solo el apellido ("Ing. RUIZ", "(prof. Such)"): se completa si hay una sola persona con ese apellido
    "cabrera": "Cabrera Jorge",
    "cruz": "Cruz Pedro",
    "de la cruz": "De La Cruz José",
    "de luca": "De Luca Alejandra",
    "del prado": "Del Prado Liliana",
    "greco": "Greco Oscar",
    "lemir": "Lemir Carlos",
    "martinez": "Martinez Ariel",
    "moreno": "Moreno Patricio",
    "paredi": "Paredi Mario",
    "reynoso": "Reynoso Leandro",
    "ruiz": "Ruiz Jose Luis",
    "silva teseira": "Silva Teseira Ricardo",
    "soria": "Soria Fabian",
    "such": "Such Victor",
    "vicente": "Vicente Francisco",
    "zamudio": "Zamudio Marcelo",
    "achin": "Achín",
}

# Dos docentes que el PDF dejó pegados, sin guion
_PEGADOS = {
    "barrionuevo analia santillan matias": ["Barrionuevo Analia", "Santillan Matias"],
    "rojas cristina dorigatti mariana": ["Rojas Cristina", "Dorigatti Mariana"],
    "ugarte fernando lopez emmanuel": ["Ugarte Fernando", "Lopez Emmanuel"],
    "will adrian lizondo diego": ["Will Adrian", "Lizondo Diego"],
    "de la cruz jose gonzalez juan p": ["De La Cruz José", "González Quinteros Juan P"],
}

_TITULO = re.compile(r"^(?:ing|prof|dr|teacher)\b\.?\s*|^(?:Ing|Prof)(?=[A-ZÁÉÍÓÚÑ])", re.IGNORECASE)
_SEGUNDO_TITULO = re.compile(r"\s+(?=(?:Ing|Prof|Dr)\.?\s)")  # "Ing. MARTÍNEZ Ing. CARO"
_LAB = re.compile(r"\(?\s*lab\s*\.?\s*\d+\s*\)?", re.IGNORECASE)


def _clave(texto: str) -> str:
    return normalizar_materia(texto)


def _persona(texto: str) -> str:
    p = _TITULO.sub("", _LAB.sub(" ", texto)).replace(",", " ")
    p = re.sub(r"\s+", " ", p).strip(" -–.")
    if p.isupper() or p.islower():
        p = p.title()
    return _DOCENTES.get(_clave(p), p)


def limpiar_docente(texto: str | None) -> str | None:
    """'Vivente Francisco - Chibilisco Vicente' → 'Vicente Francisco - Chibilisco Vicente'."""
    if not texto:
        return None
    texto = _SEGUNDO_TITULO.sub(" - ", texto.replace("/", " - "))
    personas: list[str] = []
    for parte in separar_docentes(texto):
        for p in _PEGADOS.get(_clave(_persona(parte)), [_persona(parte)]):
            # "Such" (de "Gestión de Datos - (prof Such)") ya está en "Such Victor"
            if p and not any(set(_clave(p).split()) <= set(_clave(x).split()) for x in personas):
                personas.append(p)
    return " - ".join(personas)[:200] or None


# ── Materias ──────────────────────────────────────────────────────────────────

# clave normalizada → nombre completo
_MATERIAS = {
    "admin de recursos": "Administración de Recursos",
    "admin gerencial": "Administración Gerencial",
    "administracion gerencial": "Administración Gerencial",
    "administracion de sistemas de informacion": "Administración de Sistemas de Información",
    "agilidad y gestion de productos digitales": "Agilidad y Gestión de Productos Digitales",
    "alg gen y optim heuristica": "Algoritmos Genéticos y Optimización Heurística",
    "algoritmos geneticos y optimizacion heuristica": "Algoritmos Genéticos y Optimización Heurística",
    "algebra y g analitica": "Álgebra y Geometría Analítica",
    "algorit y est de datos": "Algoritmos y Estructuras de Datos",
    "analisis de sistemas": "Análisis de Sistemas",
    "analisis de sistemas de informacion": "Análisis de Sistemas de Información",
    "analisis matematico i": "Análisis Matemático I",
    "analisis matematico ii": "Análisis Matemático II",
    "analisis numerico": "Análisis Numérico",
    "arq de computadoras": "Arquitectura de Computadoras",
    "auditoria de sist de info": "Auditoría de Sistemas de Información",
    "auditoria en sistemas de informacion": "Auditoría de Sistemas de Información",
    "capital humano y gestion del conocimiento": "Capital Humano y Gestión del Conocimiento",
    "computacion en la nube": "Computación en la Nube",
    "comunicacion de datos": "Comunicación de Datos",
    "diseno de redes lan modernas": "Diseño de Redes LAN Modernas",
    "diseno de sistemas": "Diseño de Sistemas",
    "diseno de sistemas de informacion": "Diseño de Sistemas de Información",
    "diseno ux para productos digitales": "Diseño UX para Productos Digitales",
    "economia": "Economía",
    "fisica i": "Física I",
    "fisica ii": "Física II",
    "fundamentos de ingenieria de datos": "Fundamentos de Ingeniería de Datos",
    "fundamentos del diseno ux ui": "Fundamentos del Diseño UX/UI",
    "gestion de datos": "Gestión de Datos",
    "gestion de procesos de negocio": "Gestión de Procesos de Negocio",
    "gestion de procesos de negocios": "Gestión de Procesos de Negocio",
    "gestion del capital humano": "Gestión del Capital Humano",
    "habilitacion profesional": "Habilitación Profesional",
    "informatica": "Informática",
    "ing del requerimiento": "Ingeniería del Requerimiento",
    "ingenieria del requerimiento": "Ingeniería del Requerimiento",
    "ing y sociedad": "Ingeniería y Sociedad",
    "ingenieria y sociedad": "Ingeniería y Sociedad",
    "ingenieria de datos": "Ingeniería de Datos",
    "ingenieria de software": "Ingeniería de Software",
    "ingenieria y calidad de software": "Ingeniería y Calidad de Software",
    "ingles": "Inglés",
    "ingles tecnico": "Inglés Técnico",
    "innovacion y gestion de la tecnologia": "Innovación y Gestión de la Tecnología",
    "introduccion al analisis de datos": "Introducción al Análisis de Datos",
    "investigacion operativa": "Investigación Operativa",
    "legislacion": "Legislación",
    "logica y est discreta": "Lógica y Estructuras Discretas",
    "logica y estructuras discretas": "Lógica y Estructuras Discretas",
    "matematica discreta": "Matemática Discreta",
    "matematica superior": "Matemática Superior",
    "met agiles p des de software": "Metodologías Ágiles para el Desarrollo de Software",
    "nuevas tecnologias de redes wan": "Nuevas Tecnologías de Redes WAN",
    "nuevas tecnologias wan": "Nuevas Tecnologías de Redes WAN",
    "parad de programacion": "Paradigmas de Programación",
    "paradigmas de programacion": "Paradigmas de Programación",
    "prob y estadistica": "Probabilidad y Estadística",
    "probabilidades y estadisticas": "Probabilidad y Estadística",
    "prog ap distribuidas": "Programación de Aplicaciones Distribuidas",
    "programacion de aplicaciones distribuidas": "Programación de Aplicaciones Distribuidas",
    "programacion de aplicaciones visuales": "Programación de Aplicaciones Visuales",
    "quimica": "Química",
    "redes de informacion": "Redes de Información",
    "seg informatica": "Seguridad Informática",
    "seguridad informatica": "Seguridad Informática",
    "seguridad en redes e infraestructura": "Seguridad en Redes e Infraestructura",
    "simulacion": "Simulación",
    "sin y sem de los lenguajes": "Sintaxis y Semántica de los Lenguajes",
    "sintaxis y sem del lenguaje": "Sintaxis y Semántica de los Lenguajes",
    "sintaxis y semant del lenguaje": "Sintaxis y Semántica de los Lenguajes",
    "sist base de datos avanzadas": "Sistemas de Bases de Datos Avanzadas",
    "sist de base de datos avan": "Sistemas de Bases de Datos Avanzadas",
    "sist de gestion": "Sistemas de Gestión",
    "sistemas de gestion": "Sistemas de Gestión",
    "sist de info geografico": "Sistemas de Información Geográfica",
    "sist info geografico": "Sistemas de Información Geográfica",
    "sistemas de informacion geografica": "Sistemas de Información Geográfica",
    "sistemas de informacion geograficos": "Sistemas de Información Geográfica",
    "sist de representacion": "Sistemas de Representación",
    "sist y organizacion": "Sistemas y Organizaciones",
    "sist y organizaciones": "Sistemas y Organizaciones",
    "sist y proc de negocios": "Sistemas y Procesos de Negocio",
    "sistemas y procesos de negocio": "Sistemas y Procesos de Negocio",
    "sistemas y procesos de negocios": "Sistemas y Procesos de Negocio",
    "sistemas de gestion de la calidad": "Sistemas de Gestión de la Calidad",
    "sistemas de gestion para la calidad": "Sistemas de Gestión de la Calidad",
    "ii sistemas operativos": "Sistemas Operativos",
    "tecnologias para la automatizacion": "Tecnologías para la Automatización",
    "teoria de control": "Teoría de Control",
    "testing y calidad de soft": "Testing y Calidad de Software",
    "virtualizacion consolidacion de servidores": "Virtualización: Consolidación de Servidores",
}

# Pedazos de texto que el lector del PDF tomó como materia
_NO_MATERIAS = {"6 hs", "cambuia de", "numerico cambia a", "plan 2023 analisis", "pro canto javier",
                "elias roberto", "zamudio", "zamudio marcelo"}

# "Comunicaciones - (aux. Elías, Roberto)", "Matemática Superior (Pro. Cantó, Javier)",
# "Sistemas Operativos - Ing. Reynoso", "Gestión de Datos - (aux. Lemir) VIRTUAL"
_DOCENTE_EN_MATERIA = re.compile(
    r"\s*-?\s*(?:\(\s*(?:prof|pro|aux|ing)\.?\s*([^)]*)\)?|\b(?:prof|ing)\.\s*(.+))\s*(?:virtual)?\s*$", re.IGNORECASE)


def limpiar_materia(materia: str, docente: str | None) -> tuple[str, str | None] | None:
    """Devuelve (materia, docente) limpios, o None si no es una materia."""
    if _clave(materia) in _NO_MATERIAS:
        return None
    m = _DOCENTE_EN_MATERIA.search(materia)
    if m and m.start() > 0:
        materia = materia[:m.start()]
        extra = (m.group(1) or m.group(2) or "").strip(" .,")
        if extra:
            docente = f"{docente} - {extra}" if docente else extra
    materia = re.sub(r"\s*\*+\s*$", "", materia).strip(" -")
    if not materia:
        return None
    return _MATERIAS.get(_clave(materia), materia), limpiar_docente(docente)
