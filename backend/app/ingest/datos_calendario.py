"""
Calendario académico 2026 de la FRT (Resolución N.º 2394/2025 del Consejo Directivo).
Anexo I: actividades (sin los turnos de exámenes finales, que están en datos_mesas.py).
Anexo II: feriados, días no laborables y asuetos 2026/2027 (sujetos a cambios del Ejecutivo Nacional).
La migración 24 los carga; después se editan en el panel (solo ADMIN).
"""
from datetime import date


def _d(texto: str) -> date:
    dia, mes, anio = texto.split("/")
    return date(int(anio), int(mes), int(dia))


# (desde, hasta o None, actividad, categoría, detalle)
_ANEXO_I = [
    ("09/03/2026", "27/03/2026", "Presentación de notas de cambio de especialidad y/o cursado simultáneo", "NOTAS", None),
    ("20/03/2026", None, "Fecha límite de presentación de planificación de cátedra (Ord. 1549) para su aprobación por el C.D.", "PLAZO", None),
    ("23/03/2026", "27/03/2026", "Inscripción de 1º a 6º año para todas las carreras y aplicación del art. 5.3.1 Ord. 1549", "INSCRIPCION", None),
    ("30/03/2026", "31/07/2026", "Clases del 1º cuatrimestre (16 semanas)", "CLASES", "Inicio de clases del 1º cuatrimestre: 30/03/2026"),
    ("06/04/2026", "17/04/2026", "Presentación de notas: aplicación del art. 5.3.1, inscripción fuera de término, cambio de comisión, ampliación de cupo, baja de regularidad, recursado de asignaturas anuales y del 1º cuatrimestre y cambio de plan", "NOTAS", None),
    ("20/04/2026", None, "1ª prueba de suficiencia de Idioma Extranjero (Inglés I y II)", "SUFICIENCIA", "Cierre y/o anulación de inscripción: 16/04/2026"),
    ("22/04/2026", None, "1ª prueba de suficiencia de Fundamentos de Informática", "SUFICIENCIA", "Cierre y/o anulación de inscripción: 20/04/2026"),
    ("24/04/2026", None, "1ª prueba de suficiencia de Sistemas de Representación", "SUFICIENCIA", "Cierre y/o anulación de inscripción: 22/04/2026"),
    ("13/07/2026", "24/07/2026", "Receso académico (receso de invierno)", "RECESO", None),
    ("27/07/2026", "31/07/2026", "Desarrollo de actividades académicas (semana 16 del 1º cuatrimestre)", "CLASES", None),
    ("29/07/2026", None, "Reservado para mesas especiales", "EXAMENES", None),
    ("31/07/2026", None, "Vencimiento del plazo para presentar planillas de regularidad de materias cuatrimestrales (1º c.) y/o aprobación directa", "PLAZO", None),
    ("31/07/2026", None, "Finalización del 1º cuatrimestre", "CLASES", None),
    ("10/08/2026", "14/08/2026", "Inscripción a asignaturas del 2º cuatrimestre", "INSCRIPCION", None),
    ("18/08/2026", "04/12/2026", "Clases del 2º cuatrimestre (16 semanas)", "CLASES", "Inicio de clases del 2º cuatrimestre: 18/08/2026"),
    ("18/08/2026", "21/08/2026", "Presentación de notas de inscripción fuera de término para materias del 2º cuatrimestre, ampliación de cupo y baja de regularidad", "NOTAS", None),
    ("31/08/2026", None, "Plazo para concluir los estudios del nivel secundario (art. 22.1 Ord. 1549)", "PLAZO", None),
    ("05/10/2026", None, "2ª prueba de suficiencia de Idioma Extranjero (Inglés I y II)", "SUFICIENCIA", "Cierre o anulación de inscripción: 01/10/2026"),
    ("07/10/2026", None, "2ª prueba de suficiencia de Fundamentos de Informática", "SUFICIENCIA", "Cierre o anulación de inscripción: 05/10/2026"),
    ("09/10/2026", None, "2ª prueba de suficiencia de Sistemas de Representación", "SUFICIENCIA", "Cierre o anulación de inscripción: 07/10/2026"),
    ("16/10/2026", None, "Reservado para mesas especiales", "EXAMENES", None),
    ("31/10/2026", None, "Vencimiento del plazo para presentar solicitud de ingreso por equivalencia", "PLAZO", None),
    ("04/12/2026", None, "Finalización del 2º cuatrimestre", "CLASES", None),
    ("22/12/2026", None, "Vencimiento del plazo para presentar planillas de regularidad de materias anuales, cuatrimestrales (2º c.) y/o promocionales", "PLAZO", None),
    ("01/01/2027", "11/02/2027", "Receso académico (receso de verano)", "RECESO", None),
    ("31/03/2027", None, "Finalización del período lectivo 2026", "OTRO", None),
]

# (fecha, carácter, conmemoración)
_ANEXO_II = [
    ("24/03/2026", "Feriado Nacional Inamovible", "Día de la Memoria por la Verdad y la Justicia"),
    ("02/04/2026", "Feriado Nacional Inamovible", "Jueves Santo y Día del Veterano y de los Caídos en la Guerra de Malvinas"),
    ("03/04/2026", "Feriado Nacional Inamovible", "Viernes Santo"),
    ("01/05/2026", "Feriado Nacional Inamovible", "Día del Trabajador"),
    ("02/05/2026", "Asueto Académico", "Día del Docente Tecnológico - UTN"),
    ("25/05/2026", "Feriado Nacional Inamovible", "Día de la Revolución de Mayo"),
    ("15/06/2026", "Feriado trasladado", "Paso a la inmortalidad del General Don Martín Miguel de Güemes"),
    ("20/06/2026", "Feriado Nacional Inamovible", "Paso a la inmortalidad del General Manuel Belgrano"),
    ("09/07/2026", "Feriado Nacional Inamovible", "Día de la Independencia"),
    ("17/08/2026", "Feriado Nacional", "Paso a la inmortalidad del General San Martín"),
    ("19/08/2026", "Asueto Académico Administrativo", "Aniversario de la creación de la Universidad Tecnológica Nacional"),
    ("21/09/2026", "Asueto Académico", "Día del Estudiante"),
    ("24/09/2026", "Feriado Provincial", "Aniversario de la Batalla de Tucumán"),
    ("12/10/2026", "Feriado Nacional", "Día del Respeto a la Diversidad Cultural"),
    ("23/11/2026", "Feriado Trasladado", "Día de la Soberanía Nacional (20/11)"),
    ("26/11/2026", "Asueto Administrativo", "Día del Personal No Docente"),
    ("08/12/2026", "Feriado Nacional Inamovible", "Día de la Inmaculada Concepción"),
    ("24/12/2026", "Asueto Académico Administrativo", "Nochebuena"),
    ("25/12/2026", "Feriado Nacional Inamovible", "Navidad"),
    ("31/12/2026", "Asueto Académico Administrativo", "Fin de Año"),
    ("01/01/2027", "Feriado Nacional", "Año Nuevo"),
    ("08/02/2027", "Feriado Nacional", "Carnaval"),
    ("09/02/2027", "Feriado Nacional", "Carnaval"),
    ("24/03/2027", "Feriado Nacional", "Día de la Memoria por la Verdad y la Justicia"),
]


def eventos_iniciales() -> list[dict]:
    filas = [
        {"fecha_inicio": _d(desde), "fecha_fin": _d(hasta) if hasta else None, "actividad": actividad,
         "categoria": categoria, "detalle": detalle}
        for desde, hasta, actividad, categoria, detalle in _ANEXO_I
    ]
    filas += [
        {"fecha_inicio": _d(fecha), "fecha_fin": None, "actividad": conmemoracion,
         "categoria": "ASUETO" if "asueto" in caracter.lower() else "FERIADO", "detalle": caracter}
        for fecha, caracter, conmemoracion in _ANEXO_II
    ]
    return filas
