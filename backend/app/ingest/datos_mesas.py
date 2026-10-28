"""
Datos iniciales de las mesas de examen (la migración 24 los carga; después se editan en el panel).

  FECHAS_2026  → calendario académico 2026 (Res. 2394/2025 CD): por mesa y turno, (cierre de inscripción,
                 examen). El listado "Mesas 2026" (cazorla) coincide salvo el 5º turno de la Mesa I y el
                 6º de la Mesa III: valen las fechas de la resolución.
  TRIBUNALES   → "Tribunales docentes mesas examen final 2025" de I.S.I. (Mesa I, II y III),
                 Casa Central y Anexo Concepción
  SIN_TRIBUNAL → materias del listado 2026 que no figuran en los tribunales (ciencias básicas, etc.)

Cuando una materia figura en mesas distintas, manda el listado 2026 (Testing y Calidad del
Software: Mesa 1 en los tribunales 2025, Mesa 2 en 2026).
"""
from datetime import date

from app.ingest.horarios import normalizar_materia


def _d(texto: str) -> date:
    dia, mes, anio = texto.split("-")
    return date(int(anio), int(mes), int(dia))


_CALENDARIO = {
    1: ["07-05-2026 11-05-2026", "05-06-2026 09-06-2026", "30-07-2026 03-08-2026", "07-09-2026 09-09-2026",
        "18-11-2026 23-11-2026", "30-11-2026 02-12-2026", "10-12-2026 14-12-2026", "10-02-2027 16-02-2027",
        "21-02-2027 23-02-2027", "03-03-2027 07-03-2027"],
    2: ["18-05-2026 20-05-2026", "15-06-2026 18-06-2026", "03-08-2026 05-08-2026", "10-09-2026 14-09-2026",
        "23-11-2026 25-11-2026", "02-12-2026 04-12-2026", "14-12-2026 16-12-2026", "16-02-2027 18-02-2027",
        "23-02-2027 25-02-2027", "07-03-2027 09-03-2027"],
    3: ["27-05-2026 29-05-2026", "19-06-2026 23-06-2026", "05-08-2026 07-08-2026", "22-09-2026 25-09-2026",
        "25-11-2026 27-11-2026", "03-12-2026 07-12-2026", "16-12-2026 18-12-2026", "17-02-2027 21-02-2027",
        "24-02-2027 28-02-2027", "09-03-2027 11-03-2027"],
}

FECHAS_2026 = [
    {"mesa": mesa, "turno": turno, "cierre_inscripcion": _d(par.split()[0]), "fecha_examen": _d(par.split()[1])}
    for mesa, pares in _CALENDARIO.items() for turno, par in enumerate(pares, 1)
]

CC, ANEXO = "Casa Central", "Anexo Concepción"

# (materia, mesa, sede, presidente, vocal 1, vocal 2, hora)
TRIBUNALES = [
    # ── Mesa 1 ──
    ("Administración de Recursos", 1, CC, "Cordero Lucas", "Arias Jorge Daniel", "Sueldo Adriana", "17:00"),
    ("Administración Gerencial", 1, CC, "Hadad Salomon Rosana", "Rodriguez Sergio Gustavo", "Dorigatti Mariana", "15:00"),
    ("Algoritmos y Estructuras de Datos", 1, CC, "Valla Sandra", "Moyano Alberto", None, "15:00"),
    ("Algoritmos Genéticos y Optimización Heurística (electiva)", 1, CC, "Will Adrian", "Araujo Pedro", None, "16:00"),
    ("Análisis de Sistemas", 1, CC, "Marsiglia Silvana", "Sueldo Adriana", None, "15:00"),
    ("Análisis de Sistemas de Información", 1, CC, "Marsiglia Silvana", "Sueldo Adriana", None, "15:00"),
    ("Aplicaciones Ágiles Centradas en Datos (electiva)", 1, CC, "De la Cruz Jose Sabino", "Ibarra Daniel", "Juarez Gustavo", "19:00"),
    ("Comunicaciones", 1, CC, "Carrasco Agustin", "Such Victor", "Moyano Alberto", "15:00"),
    ("Comunicación de Datos", 1, CC, "Carrasco Agustin", "Such Victor", "Moyano Alberto", "15:00"),
    ("Gestión de Datos", 1, CC, "Tejerizo Raul Eugenio", "Juarez Gustavo", "Ibarra Daniel", "15:00"),
    ("Bases de Datos", 1, CC, "Tejerizo Raul Eugenio", "Juarez Gustavo", "Ibarra Daniel", "15:00"),
    ("Implementación de Base de Datos (electiva)", 1, CC, "Zalazar Ana Sofia", "Buabud Jorge", "Cordero Lucas", "19:00"),
    ("Inteligencia Artificial", 1, CC, "Figueroa de la Cruz Mario", "Will Adrian", "Araujo Pedro", "18:00"),
    ("Inteligencia Artificial Distribuida (electiva)", 1, CC, "Araujo Pedro", "Will Adrian", "Figueroa de la Cruz Mario", "15:00"),
    ("Investigación Operativa", 1, CC, "Rojas Cristina", "Fraga Alvaro", "Teri Maria Eugenia", "15:00"),
    ("Matemática Superior", 1, CC, "Gianinetto Francisca", "Vega Caro Luis", "Teri Maria Eugenia", "15:00"),
    ("Análisis Numérico", 1, CC, "Gianinetto Francisca", "Vega Caro Luis", "Teri Maria Eugenia", "15:00"),
    ("Metodología de Diseño de Sistemas (electiva)", 1, CC, "Juarez Gustavo", "Sardi Duilio", "Bascolo Alejandro", "15:00"),
    ("Nuevas Tecnologías de Redes WAN (electiva)", 1, CC, "Figueroa de la Cruz Mario", "Loandos Edmundo", "Carriles Luis Maria", "15:00"),
    ("Probabilidad y Estadística", 1, CC, "Gianinetto Francisca", "Teri Maria Eugenia", "Vega Caro Luis", "15:00"),
    ("Redes Avanzadas (electiva)", 1, CC, "Saade Sergio", "Loandos Edmundo", "Sale Ernesto Jose", "15:00"),
    ("Simulación", 1, CC, "Teri Maria Eugenia", "Vega Caro Luis", "Solorzano Diana", "15:00"),
    ("Virtualización: Consolidación de Servidores (electiva)", 1, CC, "Carriles Maria", "Loandos Edmundo", "Figueroa de la Cruz Mario", "15:00"),
    ("Algoritmos y Estructuras de Datos", 1, ANEXO, "Cruz Pedro", None, None, "15:00"),
    ("Comunicaciones", 1, ANEXO, "Such Victor", None, None, "15:00"),
    ("Comunicación de Datos", 1, ANEXO, None, None, None, "15:00"),
    ("Gestión de Datos", 1, ANEXO, None, None, None, "15:00"),
    ("Bases de Datos", 1, ANEXO, None, None, None, "15:00"),
    ("Probabilidad y Estadística", 1, ANEXO, "Paredi Mario", None, None, "15:00"),
    ("Matemática Superior", 1, ANEXO, "Canto Javier", None, None, "15:00"),
    ("Análisis Numérico", 1, ANEXO, "Canto Javier", None, None, "15:00"),
    ("Análisis de Sistemas", 1, ANEXO, None, None, None, "15:00"),
    ("Análisis de Sistemas de Información", 1, ANEXO, None, None, None, "15:00"),
    # ── Mesa 2 ──
    ("Auditoría de Sistemas de Información", 2, CC, "Solorzano Diana", "Sueldo Adriana", "Tejerizo Raul", "19:00"),
    ("Comunicaciones y Redes", 2, CC, "Nazar Patricia Yolanda", "Ibarra Daniel", "Carrasco Agustin", "15:00"),
    ("Dirección y Evaluación de Proyectos Informáticos", 2, CC, "Maigua Gustavo Gabriel", "Zalazar Ana Sofia", "Cordero Lucas Elio", "19:00"),
    ("Diseño de Sistemas", 2, CC, "Bustos Thames Juan Pablo", None, None, "15:00"),
    ("Diseño de Sistemas de Información", 2, CC, "Bustos Thames Juan Pablo", None, None, "15:00"),
    ("Gestión del Capital Humano", 2, CC, "Cordero Lucas Elio", "Vega Caro Luis", None, "19:00"),
    ("Innovación Tecnológica, Gestión del Cambio y Reingeniería", 2, CC, "Sardi Duilio Agustin", "Juarez Gustavo", "Marsiglia Silvana", "19:00"),
    ("Inteligencia Empresarial y Data Mining", 2, CC, "Araujo Pedro", "Figueroa de la Cruz Mario", "Will Adrian", "15:00"),
    ("Programación de Aplicaciones Distribuidas", 2, CC, "De la Cruz Jose Sabino", "Sal Esteban", "Vicente Chibilisco", "19:00"),
    ("Programación Web", 2, CC, "Vicente Chibilisco", "Montesinos Leonardo Rafael", "De la Cruz Jose Sabino", "19:00"),
    ("Redes de Información", 2, CC, "Nazar Patricia Yolanda", "Ibarra Daniel", "Carrasco Agustin", "15:00"),
    ("Reingeniería", 2, CC, "Sardi Duilio Agustin", "Juarez Gustavo", "Marsiglia Silvana", "19:00"),
    ("Sintaxis y Semántica de los Lenguajes", 2, CC, "Buabud Jorge", "Ronveaux Marta", "Politi Sergio Luis", "15:00"),
    ("Sistemas de Información Geográficos", 2, CC, "Bascolo Alejandro", "Arias Jorge", "Zamudio Marcelo", "19:00"),
    ("Sistemas Industriales", 2, CC, "Vega Caro Luis", "Rojas Cristina", "Teri Maria Eugenia", "15:00"),
    ("Sistemas Informáticos Industriales", 2, CC, "Vega Caro Luis", "Rojas Cristina", "Teri Maria Eugenia", "15:00"),
    ("Sistemas Informáticos para la Gestión de la Calidad", 2, CC, "Solorzano Diana", "Hadad Salomon Rosana", "Zalazar Ana Sofia", "19:00"),
    ("Sistemas Operativos Avanzados", 2, CC, "De la Cruz Jose Sabino", "Sale Ernesto", "Loandos Edmundo", "19:00"),
    ("Sistemas y Organizaciones", 2, CC, "Hadad Salomon Rosana", "Moya Norma Susana", "Ronveaux Marta", "15:00"),
    ("Sistemas y Procesos de Negocios", 2, CC, "Hadad Salomon Rosana", "Moya Norma Susana", "Ronveaux Marta", "15:00"),
    ("Testing y Calidad del Software", 2, CC, "Sal Esteban", None, None, "19:00"),
    ("Sintaxis y Semántica de los Lenguajes", 2, ANEXO, "Silva Teseira", "De Luca Alejandra", None, "15:00"),
    ("Sistemas y Organizaciones", 2, ANEXO, "De Luca Alejandra", "Silva Teseira", None, "15:00"),
    ("Sistemas y Procesos de Negocios", 2, ANEXO, "De Luca Alejandra", "Silva Teseira", None, "15:00"),
    ("Diseño de Sistemas", 2, ANEXO, "Zamudio Marcelo", None, None, "15:00"),
    ("Diseño de Sistemas de Información", 2, ANEXO, "Zamudio Marcelo", None, None, "15:00"),
    # ── Mesa 3 ──
    ("Arquitectura de Computadoras", 3, CC, "Nasrallah Augusto Jose", "Caporale Maria Concepcion", "Sale Ernesto", "15:00"),
    ("Gestión de Herramientas de Diseño y Desarrollo de Software", 3, CC, "Zamudio Marcelo", "Bascolo Alejandro", None, "15:00"),
    ("Habilitación Profesional", 3, CC, "Rodriguez Sergio", "Hadad Salomon Rosana", "Solorzano Diana", "15:00"),
    ("Seminario Integrador", 3, CC, "Rodriguez Sergio", "Hadad Salomon Rosana", "Solorzano Diana", "15:00"),
    ("Ingeniería de Requerimientos", 3, CC, "Maigua Gustavo Gabriel", "Zalazar Ana Sofia", "Sueldo Adriana", "15:00"),
    ("Ingeniería de Software", 3, CC, "Vicente Francisco", None, None, "15:00"),
    ("Introducción al Proceso Unificado de Desarrollo", 3, CC, "Vicente Francisco", "Zamudio Marcelo", None, "19:00"),
    ("Matemática Discreta", 3, CC, "Such Victor", "Valdez Ocampo Teresa", None, "15:00"),
    ("Metodologías Ágiles para el Desarrollo de Software", 3, CC, "Moreno Patricio", None, None, "15:00"),
    ("Lógica y Estructuras Discretas", 3, CC, "Such Victor", "Valdez Ocampo Teresa", None, "15:00"),
    ("Paradigmas de Programación", 3, CC, "De la Cruz Jose Sabino", "Garcia Rosas Edwin", None, "17:00"),
    ("Programación de Aplicaciones Visuales", 3, CC, "Vicente Francisco", "Loandos Edmundo", "Zamudio Marcelo", "17:00"),
    ("Proyecto Final", 3, CC, "Soria Walter Fabian", "Ugarte Fernando", "Lopez Emmanuel", "15:00"),
    ("Seguridad Informática", 3, CC, "Zakhour Jose Daniel", "Arias Jorge Daniel", "Zamudio Marcelo", "15:00"),
    ("Sistemas de Bases de Datos Avanzadas", 3, CC, "Sardi Duilio", "Juarez Gustavo", "Dorigatti Mariana", "19:00"),
    ("Sistemas de Gestión", 3, CC, "Rojas Cristina", "Dorigatti Mariana", None, "15:00"),
    ("Sistemas Operativos", 3, CC, "Loandos Edmundo", "Sale Ernesto", None, "15:00"),
    ("Teoría de Control", 3, CC, "Vega Caro Luis", "Gianinetto Francisca", "Teri Maria Eugenia", "15:00"),
    ("Gestión de Procesos de Negocio", 3, CC, "Dorigatti Mariana", "Rojas Cristina", None, "17:00"),
    ("Arquitectura de Computadoras", 3, ANEXO, "Carrion Martin", None, None, "15:00"),
    ("Matemática Discreta", 3, ANEXO, "Elia Roberto", None, None, "15:00"),
    ("Lógica y Estructuras Discretas", 3, ANEXO, "Elia Roberto", None, None, "15:00"),
    ("Paradigmas de Programación", 3, ANEXO, "De la Cruz Jose Sabino", "Gonzalez Quinteros Juan P.", None, "17:00"),
    ("Sistemas Operativos", 3, ANEXO, "Gonzalez Quinteros Juan P.", "De la Cruz Jose Sabino", None, "15:00"),
    ("Programación de Aplicaciones Visuales", 3, ANEXO, None, None, None, "15:00"),
    ("Seguridad Informática", 3, ANEXO, None, None, None, "15:00"),
    ("Seminario Integrador", 3, ANEXO, None, None, None, "15:00"),
]

SIN_TRIBUNAL = [
    ("Análisis Matemático I", 1), ("Economía", 1), ("Física I", 1), ("Legislación", 1),
    ("Soporte a la Gestión de Datos con Programación Visual", 1),
    ("Álgebra y Geometría Analítica", 2), ("Física II", 2), ("Inglés Técnico II", 2), ("Química", 2),
    ("Sistemas de Representación", 2),
    ("Análisis Matemático II", 3), ("Ingeniería y Sociedad", 3), ("Diseño de Interfaz Gráfica", 3),
]


def norma(materia: str) -> str:
    """Nombre normalizado para buscar: sin "(electiva)" ("IA distribuida" igual la encuentra)."""
    return normalizar_materia(materia.replace("(electiva)", ""))[:200]


def materias_iniciales() -> list[dict]:
    filas = [
        {"materia": m, "materia_norm": norma(m), "mesa": mesa, "sede": sede,
         "presidente": p, "vocal1": v1, "vocal2": v2, "hora": hora, "anio_tribunal": 2025}
        for m, mesa, sede, p, v1, v2, hora in TRIBUNALES
    ]
    filas += [
        {"materia": m, "materia_norm": norma(m), "mesa": mesa, "sede": CC,
         "presidente": None, "vocal1": None, "vocal2": None, "hora": None, "anio_tribunal": None}
        for m, mesa in SIN_TRIBUNAL
    ]
    return filas
