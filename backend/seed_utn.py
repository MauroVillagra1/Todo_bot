"""
Seed de datos reales — UTN FRT 2026 / Plan 2023
Ingeniería en Sistemas de Información

Fuente: PDFs de horarios 2026 + Plan de Estudios 2008 (título intermedio)

⚠️  Los horarios de 3º año (3K01–3K04) tienen margen de error en el cruce
    materia↔franja exacta. Se cargan como "A confirmar" según la instrucción.
⚠️  2K03 y 2K04 tienen datos solapados en el PDF original — se cargan con
    aula/turno provisional, revisar manualmente.
⚠️  Plan 2008 se carga como materias separadas (prefijo "[2008]") para no
    mezclarlas con el Plan 2023.

Uso:
    cd backend/
    python seed_utn.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from difflib import SequenceMatcher
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.academico import (
    Comision, Materia, PeriodoAcademico, UsuarioComision, DuracionEnum, TipoPeriodoEnum
)
from app.models.cursada import Cursada, CursadaProfesor, ModalidadEnum
from app.models.usuario import Usuario, RolEnum
from datetime import date

# ─────────────────────────────────────────────────────────────────────────────
# Contadores globales para el resumen final
# ─────────────────────────────────────────────────────────────────────────────
stats = {
    "periodos":   {"creados": 0, "existentes": 0},
    "materias":   {"creados": 0, "existentes": 0},
    "comisiones": {"creados": 0, "existentes": 0},
    "profesores": {"creados": 0, "existentes": 0},
    "cursadas":   {"creados": 0, "existentes": 0},
    "asignaciones": {"creados": 0, "existentes": 0},
}
casos_a_confirmar = []   # horarios marcados "A confirmar"
casos_dudosos_prof = []  # nombres similares de profesores para revisión manual

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def similitud(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

def nombre_similar(nombre: str, existentes: list[Usuario], umbral=0.82) -> Usuario | None:
    """Busca un profesor existente con nombre muy similar (evita duplicados por typos)."""
    for u in existentes:
        s = similitud(nombre, u.nombre)
        if s >= umbral:
            return u
        if s >= 0.70:
            casos_dudosos_prof.append(
                f"  ⚠️  '{nombre}' vs '{u.nombre}' (similitud {s:.0%}) — revisar manualmente"
            )
    return None

def log(accion: str, entidad: str, nombre: str):
    simbolo = "✓" if accion == "creado" else "·"
    print(f"  {simbolo} [{entidad}] {accion}: {nombre}")

# ─────────────────────────────────────────────────────────────────────────────
# Funciones de creación
# ─────────────────────────────────────────────────────────────────────────────

def crear_periodo(db: Session, nombre: str, tipo: TipoPeriodoEnum,
                  f_inicio: date, f_fin: date) -> PeriodoAcademico:
    obj = db.query(PeriodoAcademico).filter_by(nombre=nombre).first()
    if obj:
        log("ya existe", "Período", nombre)
        stats["periodos"]["existentes"] += 1
        return obj
    obj = PeriodoAcademico(nombre=nombre, tipo=tipo, fecha_inicio=f_inicio, fecha_fin=f_fin)
    db.add(obj); db.flush()
    log("creado", "Período", nombre)
    stats["periodos"]["creados"] += 1
    return obj


def crear_materia(db: Session, nombre: str, codigo: str,
                  duracion: DuracionEnum) -> Materia:
    obj = db.query(Materia).filter_by(codigo=codigo).first()
    if obj:
        stats["materias"]["existentes"] += 1
        return obj
    obj = Materia(nombre=nombre, codigo=codigo, duracion=duracion)
    db.add(obj); db.flush()
    log("creado", "Materia", f"{codigo} — {nombre}")
    stats["materias"]["creados"] += 1
    return obj


def crear_comision(db: Session, nombre: str, periodo_id: int) -> Comision:
    obj = db.query(Comision).filter_by(nombre=nombre, periodo_id=periodo_id).first()
    if obj:
        stats["comisiones"]["existentes"] += 1
        return obj
    obj = Comision(nombre=nombre, periodo_id=periodo_id)
    db.add(obj); db.flush()
    log("creado", "Comisión", nombre)
    stats["comisiones"]["creados"] += 1
    return obj


def crear_profesor(db: Session, nombre_raw: str,
                   todos_los_profes: list[Usuario]) -> Usuario:
    nombre = nombre_raw.strip()
    # Buscar exacto primero
    obj = db.query(Usuario).filter(
        Usuario.nombre == nombre,
        Usuario.rol == RolEnum.profesor_directivo
    ).first()
    if obj:
        stats["profesores"]["existentes"] += 1
        return obj
    # Buscar similar
    similar = nombre_similar(nombre, todos_los_profes)
    if similar:
        stats["profesores"]["existentes"] += 1
        return similar
    # Crear nuevo
    email = (nombre.lower()
             .replace(" ", ".")
             .replace("á","a").replace("é","e").replace("í","i")
             .replace("ó","o").replace("ú","u").replace("ñ","n")
             [:40]) + "@docente.utn.edu.ar"
    # Evitar email duplicado
    sufijo = 1
    email_final = email
    while db.query(Usuario).filter_by(email=email_final).first():
        email_final = email.replace("@", f"{sufijo}@")
        sufijo += 1
    obj = Usuario(
        nombre=nombre,
        email=email_final,
        password_hash=hash_password("Docente1234"),
        rol=RolEnum.profesor_directivo,
        activo=True,
    )
    db.add(obj); db.flush()
    todos_los_profes.append(obj)
    log("creado", "Profesor", nombre)
    stats["profesores"]["creados"] += 1
    return obj


def crear_cursada(db: Session, materia_id: int, comision_id: int,
                  periodo_id: int, aula: str | None, horario: str | None,
                  modalidad=ModalidadEnum.presencial) -> tuple[Cursada, bool]:
    """Retorna (cursada, es_nueva)."""
    obj = db.query(Cursada).filter_by(
        materia_id=materia_id, comision_id=comision_id, periodo_id=periodo_id
    ).first()
    if obj:
        stats["cursadas"]["existentes"] += 1
        return obj, False
    obj = Cursada(
        materia_id=materia_id,
        comision_id=comision_id,
        periodo_id=periodo_id,
        aula=aula,
        horario=horario or "A confirmar",
        modalidad=modalidad,
    )
    db.add(obj); db.flush()
    stats["cursadas"]["creados"] += 1
    if not horario or horario == "A confirmar":
        casos_a_confirmar.append(
            f"  Cursada materia_id={materia_id} comision_id={comision_id} — horario pendiente"
        )
    return obj, True


def asignar_profesor_cursada(db: Session, cursada_id: int, profesor_id: int):
    obj = db.query(CursadaProfesor).filter_by(
        cursada_id=cursada_id, profesor_id=profesor_id
    ).first()
    if obj:
        stats["asignaciones"]["existentes"] += 1
        return
    db.add(CursadaProfesor(cursada_id=cursada_id, profesor_id=profesor_id))
    db.flush()
    stats["asignaciones"]["creados"] += 1


# ─────────────────────────────────────────────────────────────────────────────
# DATOS
# ─────────────────────────────────────────────────────────────────────────────

# ── Materias Plan 2023 ────────────────────────────────────────────────────────
MATERIAS_ANUAL = [
    # 1º año
    ("Análisis Matemático I",                "P23-AM1",  DuracionEnum.anual),
    ("Álgebra y Geometría Analítica",         "P23-AGA",  DuracionEnum.anual),
    ("Algoritmos y Estructuras de Datos",     "P23-AED",  DuracionEnum.anual),
    ("Arquitectura de Computadoras",          "P23-AC",   DuracionEnum.anual),
    ("Física I",                              "P23-F1",   DuracionEnum.anual),
    ("Lógica y Estructuras Discretas",        "P23-LED",  DuracionEnum.anual),
    ("Sistemas y Procesos de Negocio",        "P23-SPN",  DuracionEnum.anual),
    ("Ingeniería y Sociedad",                 "P23-IS",   DuracionEnum.anual),
    # 2º año
    ("Análisis Matemático II",                "P23-AM2",  DuracionEnum.anual),
    ("Física II",                             "P23-F2",   DuracionEnum.anual),
    ("Paradigmas de Programación",            "P23-PP",   DuracionEnum.anual),
    ("Sistemas Operativos",                   "P23-SO",   DuracionEnum.anual),
    ("Sintaxis y Semántica de los Lenguajes", "P23-SSL",  DuracionEnum.anual),
    ("Análisis de Sistemas de Información",   "P23-ASI",  DuracionEnum.anual),
]

MATERIAS_CUATRIMESTRAL = [
    # 3º año
    ("Economía",                              "P23-ECO",  DuracionEnum.cuatrimestral),
    ("Comunicación de Datos",                 "P23-CD",   DuracionEnum.cuatrimestral),
    ("Análisis Numérico",                     "P23-AN",   DuracionEnum.cuatrimestral),
    ("Desarrollo de Software",                "P23-DS",   DuracionEnum.cuatrimestral),
    ("Diseño de Sistemas de Información",     "P23-DSI",  DuracionEnum.cuatrimestral),
    ("Seguridad Informática",                 "P23-SI",   DuracionEnum.cuatrimestral),
    ("Diseño UX para Productos Digitales",    "P23-UXD",  DuracionEnum.cuatrimestral),
    ("Fundamentos del Diseño UX/UI",          "P23-UXUI", DuracionEnum.cuatrimestral),
    ("Seminario Integrador",                  "P23-SEM",  DuracionEnum.cuatrimestral),
    # 4º año
    ("Redes de Datos",                        "P23-RD",   DuracionEnum.cuatrimestral),
    ("Ingeniería y Calidad de Software",      "P23-ICS",  DuracionEnum.cuatrimestral),
    ("Tecnologías para la Automatización",    "P23-TA",   DuracionEnum.cuatrimestral),
    ("Administración de Sistemas de Información","P23-ADSI",DuracionEnum.cuatrimestral),
    ("Computación en la Nube",                "P23-CLOUD",DuracionEnum.cuatrimestral),
    ("Algoritmos Genéticos y Optimización Heurística","P23-AGOH",DuracionEnum.cuatrimestral),
    ("Sistemas de Gestión de la Calidad",     "P23-SGC",  DuracionEnum.cuatrimestral),
    ("Sistemas de Información Geográfica",    "P23-SIG",  DuracionEnum.cuatrimestral),
    ("Seguridad en Redes e Infraestructura",  "P23-SRI",  DuracionEnum.cuatrimestral),
    ("Programación de Aplicaciones Distribuidas","P23-PAD",DuracionEnum.cuatrimestral),
    ("Fundamentos de Ingeniería de Datos",    "P23-FID",  DuracionEnum.cuatrimestral),
]

# ── Materias Plan 2008 (prefijo [2008] para no mezclar) ──────────────────────
MATERIAS_2008 = [
    ("[2008] Análisis Matemático I",          "08-AM1",   DuracionEnum.anual),
    ("[2008] Álgebra y Geometría Analítica",  "08-AGA",   DuracionEnum.anual),
    ("[2008] Matemática Discreta",            "08-MD",    DuracionEnum.anual),
    ("[2008] Sistemas y Organizaciones",      "08-SYO",   DuracionEnum.anual),
    ("[2008] Algoritmos y Estructuras",       "08-AED",   DuracionEnum.anual),
    ("[2008] Arquitectura de Computadoras",   "08-AC",    DuracionEnum.anual),
    ("[2008] Física I",                       "08-F1",    DuracionEnum.anual),
    ("[2008] Sistemas de Representación",     "08-SR",    DuracionEnum.anual),
    ("[2008] Ingeniería y Sociedad",          "08-IS",    DuracionEnum.anual),
    ("[2008] Química",                        "08-QUI",   DuracionEnum.anual),
    ("[2008] Análisis Matemático II",         "08-AM2",   DuracionEnum.anual),
    ("[2008] Física II",                      "08-F2",    DuracionEnum.anual),
    ("[2008] Análisis de Sistemas",           "08-AS",    DuracionEnum.anual),
    ("[2008] Sintaxis y Semántica",           "08-SSL",   DuracionEnum.cuatrimestral),
    ("[2008] Paradigmas de Programación",     "08-PP",    DuracionEnum.cuatrimestral),
    ("[2008] Sistemas Operativos",            "08-SO",    DuracionEnum.anual),
    ("[2008] Inglés I",                       "08-ING1",  DuracionEnum.anual),
    ("[2008] Probabilidades y Estadísticas",  "08-PE",    DuracionEnum.cuatrimestral),
    ("[2008] Diseño de Sistemas",             "08-DS",    DuracionEnum.anual),
    ("[2008] Comunicaciones",                 "08-COM",   DuracionEnum.cuatrimestral),
    ("[2008] Matemática Superior",            "08-MS",    DuracionEnum.cuatrimestral),
    ("[2008] Gestión de Datos",               "08-GD",    DuracionEnum.cuatrimestral),
    ("[2008] Economía",                       "08-ECO",   DuracionEnum.cuatrimestral),
    ("[2008] Redes de Información",           "08-RI",    DuracionEnum.cuatrimestral),
    ("[2008] Inglés II",                      "08-ING2",  DuracionEnum.anual),
    ("[2008] Habilitación Profesional",       "08-HP",    DuracionEnum.cuatrimestral),
]

# ── Comisiones 1º y 2º año (período anual) ────────────────────────────────────
COMISIONES_ANUAL = [
    # nombre, aula, turno, lista de profesores
    ("1K01","103/105","Mañana", ["Montesino Rafael","Susana Moya","Dip Marisol","Nasrallah José","Greco Oscar","Such Victor","Aparicio Gabriela","Caporale Maria Concepcion"]),
    ("1K02","107/109","Mañana", ["Arias Jorge","Cruz Pedro","Nasrallah José","Susana Moya","Dip Marisol","Moyano Alberto","Valdez Ocampo T.","Bedran Marisel"]),
    ("1K03","Sub 7/Sub 9","Mañana",["Carrion Martin","Canto Javier","Such Victor","Aparicio Gabriela","Valla Sandra","Caporale Maria Concepcion","Moya Susana"]),
    ("1K04","104/106","Mañana", ["Nasrallah José","Carrion Martin","Valla Sandra","Cruz Pedro","Susana Moya","Dip Marisol","Valdez Ocampo T.","Bedran Marisel"]),
    ("1K05","Sub 8/Sub 10","Mañana",["Caporale Maria Concepcion","Canto Javier","Such Victor","Aparicio Gabriela","Montesino Rafael","Herrera Fernando","Dip Marisol"]),
    ("1K06","108/110","Mañana", ["Cruz Pedro","Nasrallah Augusto José","Herrera Fernando","Montesino Rafael","Such Victor","Aparicio Gabriela","De Luca Alejandra","Dip Marisol"]),
    ("1K07","103/105","Tarde",  ["Montesino Rafael","Guillermo Brito","Valdez Ocampo Teresa","De Luca Alejandra","Dip Marisol","Caporale Concepcion","Martinez Ariel","Bedran Marisel","Mambrini Carlos"]),
    ("1K08","104/106","Tarde",  ["Valdez Ocampo Teresa","Martinez Ariel","Bedran Marisel","Nasrallah José Augusto","Dip Marisol","Cruz Pedro","Oris Ramon","Valla Sandra"]),
    ("1K09","115","Noche",      ["Caporale Concepcion","Valla Sandra","De Luca Alejandra","Ballesteros Walter","Martinez Ariel","Bedran Marisel"]),
    ("1K10","112","Noche",      ["Martinez Ariel","Bedran Marisel","Montesino Rafael","Carlos Mambrini","Analia Barrionuevo","De Luca Alejandra","Dip Marisol"]),
    ("2K01","212","Mañana",     ["Bonaparte Ubaldo","Sale Ernesto","Bedran Marisel","Ronveaux Marta","Del Prado Liliana","Rodriguez Sandra","Loandos Edmundo","Albarracion Hernan"]),
    ("2K02","214","Mañana",     ["Bedran Marisel","Albarracion Hernan","Del Prado Liliana","Rodriguez Sandra","Sale Ernesto","Bonaparte Ubaldo","Ronveaux Marta"]),
    ("2K03","—","Mañana",       ["Sale Ernesto","Garcia Rosas Edwin","Loandos Edmundo","Del Prado Liliana","Ronveaux Marta","Silva Teseira Ricardo","Rodriguez Sandra"]),  # ⚠️ aula dudosa
    ("2K04","216","Tarde",      ["Sale Ernesto","Garcia Rosas Edwin","Loandos Edmundo","Del Prado Liliana","Ronveaux Marta","Silva Teseira Ricardo","Rodriguez Sandra"]),  # ⚠️ solapado con 2K03
    ("2K05","114/117","Tarde",  ["Del Prado Liliana","Silva Teseira Ricardo","Loandos Edmundo","Bonaparte Ubaldo","Gonzalez Juan P.","Rodriguez Sandra","Ronveaux Marta","Garcia Rosas Edwin"]),
    ("2K06","116","Noche",      ["Sale Ernesto","Bonaparte Ubaldo","Silva Teseira Ricardo","Garcia Rosas Edwin","Alexandra Dufour","Politi Sergio","Sueldo Adriana"]),
    ("2K07","104/106","Noche",  ["Loandos Edmundo","Garcia Rosas Edwin","De La Cruz José","Bedran Marisel","Ronveaux Marta","Rodriguez Sandra","Del Prado Liliana","Gonzalez Juan P.","Marsiglia Silvana","Dufour Alexandra","Politi Sergio"]),
]

# Materias que corresponden a 1º y 2º año (para asignar a comisiones anuales)
MATERIAS_1_ANIO = ["P23-AM1","P23-AGA","P23-AED","P23-AC","P23-F1","P23-LED","P23-SPN","P23-IS"]
MATERIAS_2_ANIO = ["P23-AM2","P23-F2","P23-PP","P23-SO","P23-SSL","P23-ASI"]

# ── Comisiones 3º año (período cuatrimestral) ─────────────────────────────────
# Estructura: nombre, aula, [(codigo_materia, [profesores], horario)]
COMISIONES_3 = [
    ("3K01","107/109",[
        ("P23-ECO",  ["Carrile Jose Maria"],              "A confirmar"),
        ("P23-CD",   ["Bustos Thames Juan Pablo","Carrasco Agustin"],"A confirmar"),
        ("P23-AN",   ["Carrasco Agustin","Herrera Fernando"],        "A confirmar"),
        ("P23-DS",   ["Vega Caro Luis","Vera Hector","Zamudio Marcelo"],"A confirmar"),
        ("P23-DSI",  ["Vicente Francisco","Chibilisco Vicente"],     "A confirmar"),
        ("P23-SI",   [],                                             "A confirmar"),
    ]),
    ("3K02","214",[
        ("P23-AN",   [],                                             "A confirmar"),
        ("P23-DS",   ["Vega Caro Luis","Vera Hector"],               "A confirmar"),
        ("P23-CD",   ["Bustos Thames Juan Pablo","Carrasco Agustin","Herrera Fernando"],"A confirmar"),
        ("P23-DSI",  ["Chibilisco Vicente","Burgos Carla"],          "A confirmar"),
        ("P23-ECO",  [],                                             "A confirmar"),
    ]),
    ("3K03","216",[
        ("P23-DS",   ["Vicente Francisco","Chibilisco Vicente","Burgos Carla"],"A confirmar"),
        ("P23-AN",   ["Herrera Fernando"],                           "A confirmar"),
        ("P23-CD",   ["Canto Javier","Santos Gonzalo"],              "A confirmar"),
        ("P23-DSI",  ["Such Victor","Bustos Thames Juan Pablo"],     "A confirmar"),
        ("P23-ECO",  [],                                             "A confirmar"),
    ]),
    ("3K04","119",[
        ("P23-CD",   ["Such Victor","Herrera Fernando"],             "A confirmar"),
        ("P23-DS",   ["Vicente Francisco","Chibilisco Vicente"],     "A confirmar"),
        ("P23-AN",   ["Canto Javier","Santos Gonzalo","Zamudio Marcelo"],"A confirmar"),
        ("P23-DSI",  ["Bustos Thames Juan Pablo"],                   "A confirmar"),
        ("P23-ECO",  [],                                             "A confirmar"),
    ]),
    ("3K05","159",[
        ("P23-UXD",  ["Analia Barrionuevo"],                         "A confirmar"),
        ("P23-UXUI", ["Analia Barrionuevo"],                         "A confirmar"),
    ]),
    ("3K07","S1",[
        ("P23-SEM",  ["Rodriguez Sergio"],                           "A confirmar"),  # ⚠️ dos bloques horarios en PDF
    ]),
]

# ── Comisiones 4º año (período cuatrimestral) ─────────────────────────────────
COMISIONES_4 = [
    ("4K01","212",[
        ("P23-RD",   ["Cordero Lucas","Moyano Alberto"],             "A confirmar"),
        ("P23-ICS",  ["Nazar Patricia"],                             "A confirmar"),
        ("P23-TA",   ["Chibilisco Vicente","Vega Caro Luis","Vicente Francisco"],"A confirmar"),
        ("P23-ADSI", ["Canto Javier","Sardi Duilio"],                "A confirmar"),
    ]),
    ("4K02","159",[
        ("P23-RD",   ["Cordero Lucas","Moyano Alberto"],             "A confirmar"),
        ("P23-ICS",  ["Nazar Patricia"],                             "A confirmar"),
        ("P23-TA",   ["Vega Caro Luis","Vicente Francisco","Canto Javier"],"A confirmar"),
        ("P23-ADSI", ["Chibilisco Vicente","Quiroga Hamoud Celeste"],"A confirmar"),
    ]),
    ("4K03","116",[
        ("P23-RD",   ["Eduardo Nemer","Nazar Patricia"],             "A confirmar"),
        ("P23-ICS",  ["Vega Caro Luis","Cordero Lucas"],             "A confirmar"),
        ("P23-TA",   ["Vicente Francisco","Chibilisco Vicente"],     "A confirmar"),
        ("P23-ADSI", ["Canto Javier","Sardi Duilio"],                "A confirmar"),
    ]),
    ("4K06","—",[
        ("P23-CLOUD",["A designar"],                                 "A confirmar"),
        ("P23-AGOH", ["Will Adrian"],                                "A confirmar"),
        ("P23-SGC",  ["Lizondo Diego","Solorzano Diana","Torres Juan E."],"A confirmar"),
    ]),
    ("4K07","—",[
        ("P23-SIG",  [],                                             "A confirmar"),
        ("P23-SRI",  ["Bascolo Alejandro","Ibarra Daniel"],          "A confirmar"),
    ]),
    ("4K08","Lab 155",[
        ("P23-PAD",  ["De La Cruz José"],                            "A confirmar"),
    ]),
    ("4K09","S2",[
        ("P23-FID",  ["Araujo Pedro"],                               "A confirmar"),
    ]),
]


# ─────────────────────────────────────────────────────────────────────────────
# SEED PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def seed(db: Session):

    # ── 1. Períodos ───────────────────────────────────────────────────────────
    print("\n── Períodos ─────────────────────────────────────────────────────")
    periodo_anual = crear_periodo(
        db, "Ciclo Lectivo Anual 2026",
        TipoPeriodoEnum.anual,
        date(2026, 3, 16), date(2026, 12, 11)
    )
    periodo_2c = crear_periodo(
        db, "2do Cuatrimestre 2026",
        TipoPeriodoEnum.segundo_cuatrimestre,
        date(2026, 8, 3), date(2026, 12, 11)
    )

    # ── 2. Materias ───────────────────────────────────────────────────────────
    print("\n── Materias Plan 2023 ───────────────────────────────────────────")
    materias = {}
    for nombre, codigo, duracion in MATERIAS_ANUAL + MATERIAS_CUATRIMESTRAL:
        materias[codigo] = crear_materia(db, nombre, codigo, duracion)

    print("\n── Materias Plan 2008 ───────────────────────────────────────────")
    for nombre, codigo, duracion in MATERIAS_2008:
        crear_materia(db, nombre, codigo, duracion)

    # ── 3. Profesores (se van acumulando para detección de similares) ─────────
    print("\n── Profesores ───────────────────────────────────────────────────")
    todos_los_profes: list[Usuario] = list(
        db.query(Usuario).filter(Usuario.rol == RolEnum.profesor_directivo).all()
    )

    def prof(nombre: str) -> Usuario:
        return crear_profesor(db, nombre, todos_los_profes)

    # ── 4. Comisiones 1º y 2º año (anuales) ──────────────────────────────────
    print("\n── Comisiones 1º y 2º año (anuales) ────────────────────────────")
    for nombre_com, aula, turno, profesores_raw in COMISIONES_ANUAL:
        com = crear_comision(db, nombre_com, periodo_anual.id)

        # Determinar materias según si es 1K o 2K
        if nombre_com.startswith("1K"):
            codigos_mat = MATERIAS_1_ANIO
        else:
            codigos_mat = MATERIAS_2_ANIO

        # Obtener objetos de profesor
        prof_objs = [prof(p) for p in profesores_raw]

        # Crear una cursada por materia en esta comisión
        # (horario "A confirmar" porque el PDF no da día/hora por materia individual)
        for cod in codigos_mat:
            mat = materias[cod]
            cursada, _ = crear_cursada(
                db, mat.id, com.id, periodo_anual.id,
                aula=aula, horario="A confirmar"
            )
            # Asignar todos los profesores de la comisión a todas las cursadas
            # (los docentes están por comisión en el PDF, no por materia individual)
            for p in prof_objs:
                asignar_profesor_cursada(db, cursada.id, p.id)

    # ── 5. Comisiones 3º año (2do cuatrimestre) ───────────────────────────────
    print("\n── Comisiones 3º año (2do cuatrimestre) ─────────────────────────")
    for nombre_com, aula, materias_list in COMISIONES_3:
        com = crear_comision(db, nombre_com, periodo_2c.id)
        for cod_mat, profesores_raw, horario in materias_list:
            mat = materias[cod_mat]
            cursada, _ = crear_cursada(
                db, mat.id, com.id, periodo_2c.id,
                aula=aula, horario=horario
            )
            for p_nombre in profesores_raw:
                if p_nombre and p_nombre != "A designar":
                    p = prof(p_nombre)
                    asignar_profesor_cursada(db, cursada.id, p.id)

    # ── 6. Comisiones 4º año (2do cuatrimestre) ───────────────────────────────
    print("\n── Comisiones 4º año (2do cuatrimestre) ─────────────────────────")
    for nombre_com, aula, materias_list in COMISIONES_4:
        com = crear_comision(db, nombre_com, periodo_2c.id)
        for cod_mat, profesores_raw, horario in materias_list:
            mat = materias[cod_mat]
            cursada, _ = crear_cursada(
                db, mat.id, com.id, periodo_2c.id,
                aula=aula, horario=horario
            )
            for p_nombre in profesores_raw:
                if p_nombre and p_nombre != "A designar":
                    p = prof(p_nombre)
                    asignar_profesor_cursada(db, cursada.id, p.id)

    db.commit()

    # ── 7. Resumen ────────────────────────────────────────────────────────────
    print("\n" + "═"*60)
    print("✅ SEED UTN FRT 2026 — RESUMEN")
    print("═"*60)
    for entidad, s in stats.items():
        print(f"  {entidad:15} creados: {s['creados']:3}  |  ya existían: {s['existentes']}")

    if casos_a_confirmar:
        print(f"\n⚠️  HORARIOS 'A CONFIRMAR' ({len(casos_a_confirmar)}):")
        print("  (Revisar contra el PDF original para cargar los horarios exactos)")
        for c in casos_a_confirmar[:10]:
            print(c)
        if len(casos_a_confirmar) > 10:
            print(f"  ... y {len(casos_a_confirmar)-10} más.")

    if casos_dudosos_prof:
        print(f"\n⚠️  NOMBRES DE PROFESORES DUDOSOS ({len(casos_dudosos_prof)}) — REVISAR MANUALMENTE:")
        for c in set(casos_dudosos_prof):
            print(c)

    print("\n  Notas adicionales:")
    print("  · 2K03 y 2K04: aula/turno provisional, verificar en el PDF original")
    print("  · 3K07: Seminario Integrador con dos bloques horarios en el PDF — confirmar cuál aplica")
    print("  · Plan 2008: cargado con prefijo [2008], NO mezclar con Plan 2023")
    print("  · Todos los profesores tienen contraseña inicial: Docente1234")
    print("═"*60 + "\n")


if __name__ == "__main__":
    print("Conectando a la base de datos...")
    db = SessionLocal()
    try:
        seed(db)
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error durante el seed: {e}")
        import traceback; traceback.print_exc()
        raise
    finally:
        db.close()
