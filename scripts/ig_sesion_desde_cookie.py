"""
Guarda la sesión de Instagram para Instaloader a partir de la cookie `sessionid`
del navegador (cuando `instaloader --login` pide checkpoint y
`--load-cookies` no encuentra la sesión).

Uso (PowerShell, desde la raíz del repo):
    python scripts/ig_sesion_desde_cookie.py maurito_cordoba1

Pide el valor de la cookie sin mostrarlo en pantalla. Se copia desde el
navegador con la sesión de Instagram iniciada: F12 → Aplicación →
Cookies → https://www.instagram.com → sessionid → Valor.
"""
import sys
from getpass import getpass

import instaloader


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python scripts/ig_sesion_desde_cookie.py USUARIO")
        return 2
    usuario = sys.argv[1]
    sessionid = getpass("Pegá el valor de la cookie sessionid (no se ve) y Enter: ").strip()
    if not sessionid:
        print("No se ingresó nada.")
        return 1

    loader = instaloader.Instaloader(quiet=True)
    loader.context._session.cookies.set("sessionid", sessionid, domain=".instagram.com")
    loader.context.username = usuario
    conectado = loader.test_login()
    if not conectado:
        print("Instagram no aceptó esa cookie: revisá que la sesión siga iniciada y copiala de nuevo.")
        return 1
    loader.save_session_to_file()
    print(f"Sesión guardada para {conectado}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
