"""
Adaptador para el catálogo público de un Moodle (ej. Campus Virtual frt.cvg.utn.edu.ar).

Sin iniciar sesión solo se ve el catálogo: qué materias tienen aula virtual, en qué
nivel y quiénes son sus docentes. El contenido de cada aula pide usuario y no se lee.
Una publicación por aula: "Aula virtual de X (2do-Nivel ISI)" con docentes y link.

Config de la fuente:
  categoria     nombre de la categoría raíz a recorrer (ej. "Ingeniería en Sistemas de Información")
  solo          texto que deben contener las subcategorías del primer nivel (ej. "2026"); opcional
  cada_horas    no vuelve a recorrer antes de este intervalo (default 24): el sitio es de la facultad
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


def _rol_y_nombre(texto: str) -> tuple[str, str]:
    """'Teacher: Arias Jorge' → ('Docente', 'Arias Jorge')."""
    rol, _, nombre = texto.partition(":")
    return _ROLES.get(rol.strip().lower(), rol.strip()), nombre.strip()


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

    def _cursos(self, client: httpx.Client, url: str, ruta: list[str]) -> Iterator[tuple[list[str], str, str]]:
        """Recorre la categoría y sus subcategorías: (ruta, nombre del curso, id)."""
        sopa = self._pagina(client, url + ("&" if "?" in url else "?") + "perpage=all")
        for a in sopa.select(".coursename a"):
            m = re.search(r"[?&]id=(\d+)", a.get("href", ""))
            if m:
                yield ruta, a.get_text(" ", strip=True), m.group(1)
        for nombre, href in self._subcategorias(sopa):
            yield from self._cursos(client, href, ruta + [nombre])

    def obtener_cambios(self, desde: datetime | None) -> Iterator[ItemCrudo]:
        ahora = datetime.now(timezone.utc)
        if desde and ahora - desde < timedelta(hours=float(self.config.get("cada_horas", 24))):
            return  # ya se revisó hace poco
        base = self.fuente.url.rstrip("/")
        with self._cliente() as client:
            raiz = self._pagina(client, f"{base}/course/index.php")
            categorias = dict(self._subcategorias(raiz))
            # La carrera suele estar dentro de "CARRERAS DE GRADO"
            if self.config["categoria"] not in categorias:
                for nombre, href in list(categorias.items()):
                    categorias.update(self._subcategorias(self._pagina(client, href)))
            url_carrera = categorias[self.config["categoria"]]

            periodos = self._subcategorias(self._pagina(client, url_carrera))
            solo = self.config.get("solo", "")
            for periodo, href in periodos:
                if solo and solo not in periodo:
                    continue
                for ruta, nombre, curso_id in self._cursos(client, href, [periodo]):
                    ficha = self._pagina(client, f"{base}/course/info.php?id={curso_id}")
                    docentes = [_rol_y_nombre(li.get_text(" ", strip=True)) for li in ficha.select(".teachers li")]
                    resumen = ficha.select_one(".summary")
                    yield self._item(base, curso_id, nombre, ruta, docentes,
                                     resumen.get_text(" ", strip=True) if resumen else "", ahora)

    def _item(self, base: str, curso_id: str, nombre: str, ruta: list[str],
              docentes: list[tuple[str, str]], resumen: str, ahora: datetime) -> ItemCrudo:
        nivel = " / ".join(ruta)
        url = f"{base}/course/view.php?id={curso_id}"
        partes = [f"Aula virtual de {nombre} en el Campus Virtual de la UTN FRT ({nivel}).",
                  f"Carrera: {self.config['categoria']}."]
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
        return ItemCrudo(
            id_externo=f"curso:{curso_id}",
            url=url,
            titulo=f"Aula virtual: {nombre} ({ruta[-1]})",
            contenido_html="".join(f"<p>{escape(p)}</p>" for p in partes),
            fecha_publicacion=None,
            # Marca de revisión: el catálogo no tiene fechas propias
            fecha_modificacion=ahora,
        )
