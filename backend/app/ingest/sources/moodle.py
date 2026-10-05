"""
Adaptador para el catálogo público de un Moodle (ej. Campus Virtual frt.cvg.utn.edu.ar).

Sin iniciar sesión solo se ve el catálogo: qué carreras y cursos hay, qué materias
tienen aula virtual y quiénes son sus docentes. El contenido de cada aula pide
usuario y no se lee. Genera:
  - una publicación por categoría (carrera, tecnicatura, nivel…) con lo que contiene
  - una publicación por aula, con la carrera, el nivel, los docentes y el link
Los períodos lectivos de otros años ("Periodo Lectivo 2025") se saltean.

Config de la fuente:
  categoria   opcional: recorrer solo esa categoría (ej. "Ingeniería en Sistemas de Información")
  cada_horas  no vuelve a recorrer antes de este intervalo (default 24): el sitio es de la facultad
"""
import re
import time
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Iterator

import httpx
from bs4 import BeautifulSoup

from app.ingest.sources.base import USER_AGENT, ItemCrudo, Source

PAUSA = 0.5  # segundos entre pedidos
_ROLES = {"teacher": "Docente", "non-editing teacher": "Ayudante", "profesor": "Docente",
          "profesor sin permiso de edición": "Ayudante"}
_PERIODO = re.compile(r"periodo lectivo\s*(\d{4})", re.IGNORECASE)
# Partes de la ruta que no son la carrera ("Periodo Lectivo 2026", "2do-Nivel ISI", "1er-Año")
_NO_CARRERA = re.compile(r"periodo lectivo|nivel|año|otros espacios|carreras de|ciclos|cursos de", re.IGNORECASE)


def _rol_y_nombre(texto: str) -> tuple[str, str]:
    """'Teacher: Arias Jorge' → ('Docente', 'Arias Jorge')."""
    rol, _, nombre = texto.partition(":")
    return _ROLES.get(rol.strip().lower(), rol.strip()), nombre.strip()


def carrera(ruta: list[str]) -> str:
    """La categoría más específica que es una carrera: [CARRERAS DE GRADO, Ing. Civil, Periodo 2026, 1er-Nivel] → Ing. Civil."""
    candidatas = [r for r in ruta if not _NO_CARRERA.search(r)]
    return candidatas[-1] if candidatas else ruta[-1]


def _periodo_viejo(nombre: str, anio: int) -> bool:
    m = _PERIODO.search(nombre)
    return bool(m) and int(m.group(1)) != anio


def _parrafos(partes: list[str]) -> str:
    return "".join(f"<p>{escape(p)}</p>" for p in partes)


class MoodleSource(Source):
    transport: httpx.BaseTransport | None = None  # solo para tests
    pausa = PAUSA

    def _cliente(self) -> httpx.Client:
        return httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT},
                            transport=self.transport)

    def _pagina(self, client: httpx.Client, url: str) -> BeautifulSoup:
        time.sleep(self.pausa)
        resp = client.get(url)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    def _subcategorias(self, sopa: BeautifulSoup) -> list[tuple[str, str]]:
        return [(a.get_text(" ", strip=True), a["href"]) for a in sopa.select(".categoryname a") if a.get("href")]

    def obtener_cambios(self, desde: datetime | None) -> Iterator[ItemCrudo]:
        ahora = datetime.now(timezone.utc)
        if desde and ahora - desde < timedelta(hours=float(self.config.get("cada_horas", 24))):
            return  # ya se revisó hace poco
        base = self.fuente.url.rstrip("/")
        with self._cliente() as client:
            raiz = self._subcategorias(self._pagina(client, f"{base}/course/index.php"))
            buscada = self.config.get("categoria")
            if not buscada:
                for nombre, href in raiz:
                    yield from self._recorrer(client, base, href, [nombre], ahora)
                return
            # Una sola categoría: suele estar un nivel adentro ("CARRERAS DE GRADO" → la carrera)
            for nombre, href in raiz:
                if nombre == buscada:
                    yield from self._recorrer(client, base, href, [nombre], ahora)
                    return
                for sub, sub_href in self._subcategorias(self._pagina(client, href)):
                    if sub == buscada:
                        yield from self._recorrer(client, base, sub_href, [nombre, sub], ahora)
                        return
            raise ValueError(f"No está la categoría «{buscada}» en el campus")

    def _recorrer(self, client: httpx.Client, base: str, url: str, ruta: list[str],
                  ahora: datetime) -> Iterator[ItemCrudo]:
        sopa = self._pagina(client, url + ("&" if "?" in url else "?") + "perpage=all")
        cursos = []
        for a in sopa.select(".coursename a"):
            m = re.search(r"[?&]id=(\d+)", a.get("href", ""))
            if m:
                cursos.append((a.get_text(" ", strip=True), m.group(1)))
        subs = [(n, h) for n, h in self._subcategorias(sopa) if not _periodo_viejo(n, ahora.year)]

        if cursos or subs:
            yield self._item_categoria(url, ruta, subs, cursos, ahora)
        for nombre, curso_id in cursos:
            ficha = self._pagina(client, f"{base}/course/info.php?id={curso_id}")
            docentes = [_rol_y_nombre(li.get_text(" ", strip=True)) for li in ficha.select(".teachers li")]
            resumen = ficha.select_one(".summary")
            yield self._item_curso(base, curso_id, nombre, ruta, docentes,
                                   resumen.get_text(" ", strip=True) if resumen else "", ahora)
        for nombre, href in subs:
            yield from self._recorrer(client, base, href, ruta + [nombre], ahora)

    def _item_categoria(self, url: str, ruta: list[str], subs: list[tuple[str, str]],
                        cursos: list[tuple[str, str]], ahora: datetime) -> ItemCrudo:
        m = re.search(r"categoryid=(\d+)", url)
        partes = [f"En el Campus Virtual de la UTN FRT, «{ruta[-1]}» está en: {' / '.join(ruta)}."]
        if subs:
            partes.append(f"Incluye: {', '.join(n for n, _ in subs)}.")
        if cursos:
            partes.append(f"Aulas virtuales ({len(cursos)}): {', '.join(n for n, _ in cursos)}.")
        return ItemCrudo(
            id_externo=f"categoria:{m.group(1) if m else ' / '.join(ruta)}",
            url=url,
            titulo=f"Campus Virtual: {ruta[-1]}",
            contenido_html=_parrafos(partes),
            fecha_publicacion=None,
            fecha_modificacion=ahora,  # el catálogo no tiene fechas propias
        )

    def _item_curso(self, base: str, curso_id: str, nombre: str, ruta: list[str],
                    docentes: list[tuple[str, str]], resumen: str, ahora: datetime) -> ItemCrudo:
        url = f"{base}/course/view.php?id={curso_id}"
        de = carrera(ruta)
        partes = [f"Aula virtual de {nombre} en el Campus Virtual de la UTN FRT.",
                  f"Carrera: {de}. Ubicación: {' / '.join(ruta)}."]
        por_rol: dict[str, list[str]] = {}
        for rol, persona in docentes:
            por_rol.setdefault(rol, []).append(persona)
        for rol, personas in por_rol.items():
            partes.append(f"{rol}{'s' if len(personas) > 1 else ''}: {', '.join(personas)}.")
        if not docentes:
            partes.append("El campus no lista docentes para esta aula.")
        if resumen:
            partes.append(resumen)
        partes.append(f"Para entrar al aula hace falta iniciar sesión en el campus: {url}")
        nivel = ruta[-1] if ruta[-1] != de else ""
        return ItemCrudo(
            id_externo=f"curso:{curso_id}",
            url=url,
            titulo=f"Aula virtual: {nombre} — {de}" + (f" ({nivel})" if nivel else ""),
            contenido_html=_parrafos(partes),
            fecha_publicacion=None,
            fecha_modificacion=ahora,
        )
