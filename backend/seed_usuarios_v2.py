"""
seed_usuarios_v2.py — Reemplaza TODOS los usuarios con cuentas definitivas.

Estructura de mails:
  Profesores:    nombre.apellido@doc.frt.utn.edu.ar
  Administrativos: nombre.apellido@adm.frt.utn.edu.ar
  Jefe depto:    sistemas@depto.frt.utn.edu.ar
  Administrador: admin@admin.frt.utn.edu.ar
  Alumnos:       nombre.apellido@alum.frt.utn.edu.ar

Contraseña de todas las cuentas: 123456

IMPORTANTE: conserva las relaciones cursada_profesor y usuario_comision
actualizando solo email, password y rol de usuarios existentes.
Crea las cuentas nuevas (admin, administrativo, jefe_depto) si no existen.

Uso:
    python seed_usuarios_v2.py
"""
import sys, os, re, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.usuario import RolEnum, Usuario

PASSWORD = "123456"
HASH     = hash_password(PASSWORD)


def normalizar_nombre(nombre: str) -> str:
    """Convierte 'José Augusto Nasrallah' → 'jose.augusto.nasrallah'."""
    # Quitar tildes
    s = unicodedata.normalize("NFD", nombre.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    # Reemplazar espacios y caracteres especiales por puntos
    s = re.sub(r"[^a-z0-9]+", ".", s)
    s = s.strip(".")
    return s


def email_profesor(nombre: str) -> str:
    return f"{normalizar_nombre(nombre)}@doc.frt.utn.edu.ar"


def email_alumno(nombre: str) -> str:
    return f"{normalizar_nombre(nombre)}@alum.frt.utn.edu.ar"


def upsert_usuario(db: Session, nombre: str, email: str, rol: RolEnum,
                   usuario_id: int | None = None) -> Usuario:
    """Actualiza si existe (por id o email), crea si no."""
    usuario = None
    if usuario_id:
        usuario = db.get(Usuario, usuario_id)
    if not usuario:
        usuario = db.query(Usuario).filter(Usuario.email == email).first()

    if usuario:
        usuario.nombre        = nombre
        usuario.email         = email
        usuario.rol           = rol
        usuario.password_hash = HASH
        usuario.activo        = True
        print(f"  ✏️  Actualizado: {email} ({rol.value})")
    else:
        usuario = Usuario(nombre=nombre, email=email, rol=rol,
                          password_hash=HASH, activo=True)
        db.add(usuario)
        print(f"  ✅ Creado:      {email} ({rol.value})")
    return usuario


def main():
    db: Session = SessionLocal()
    try:
        print("\n══════════════════════════════════════════════")
        print("  seed_usuarios_v2 — Actualizando cuentas")
        print("══════════════════════════════════════════════\n")

        # ── 1. Administrador del sistema ──────────────────────────────────────
        print("── Administrador ────────────────────────────")
        # Actualizar la primera cuenta admin que exista, desactivar el resto
        admins = db.query(Usuario).filter(Usuario.rol == RolEnum.administrador).order_by(Usuario.id).all()
        admin_principal = None
        for i, a in enumerate(admins):
            if i == 0:
                a.nombre        = "Administrador Sistema"
                a.email         = "admin@admin.frt.utn.edu.ar"
                a.password_hash = HASH
                a.activo        = True
                admin_principal = a
                print(f"  ✏️  Actualizado: admin@admin.frt.utn.edu.ar (id={a.id})")
            else:
                # Cuenta admin duplicada → convertir en administrativo para no perder FKs
                a.email         = f"admin.dup.{a.id}@adm.frt.utn.edu.ar"
                a.rol           = RolEnum.administrativo
                a.password_hash = HASH
                a.activo        = False
                print(f"  ⚠️  Admin duplicado id={a.id} convertido a administrativo (inactivo)")

        # ── 2. Jefe de departamento ────────────────────────────────────────────
        print("\n── Jefe de departamento ─────────────────────")
        jefe_email = "sistemas@depto.frt.utn.edu.ar"
        jefe = db.query(Usuario).filter(Usuario.email == jefe_email).first()
        if jefe:
            jefe.rol = RolEnum.jefe_departamento
            jefe.password_hash = HASH
            print(f"  ✏️  Actualizado: {jefe_email}")
        else:
            jefe = Usuario(
                nombre="Jefe Departamento Sistemas",
                email=jefe_email,
                rol=RolEnum.jefe_departamento,
                password_hash=HASH,
                activo=True,
            )
            db.add(jefe)
            print(f"  ✅ Creado: {jefe_email}")

        # ── 3. Administrativos ────────────────────────────────────────────────
        print("\n── Administrativos ──────────────────────────")
        ADMINISTRATIVOS = [
            ("Secretaria Academica", "secretaria.academica"),
            ("Bedelía FRT",          "bedelia.frt"),
        ]
        for nombre, prefijo in ADMINISTRATIVOS:
            email = f"{prefijo}@adm.frt.utn.edu.ar"
            u = db.query(Usuario).filter(Usuario.email == email).first()
            if u:
                u.rol = RolEnum.administrativo
                u.password_hash = HASH
                print(f"  ✏️  Actualizado: {email}")
            else:
                db.add(Usuario(nombre=nombre, email=email,
                               rol=RolEnum.administrativo,
                               password_hash=HASH, activo=True))
                print(f"  ✅ Creado: {email}")

        # ── 4. Profesores existentes → nuevo rol + nuevo email ─────────────────
        print("\n── Profesores (actualizar email + rol) ──────")
        profesores = db.query(Usuario).filter(
            Usuario.rol == RolEnum.profesor_directivo
        ).order_by(Usuario.nombre).all()

        emails_usados: set[str] = set()
        for prof in profesores:
            nuevo_email = email_profesor(prof.nombre)
            # Evitar duplicados de email (nombres muy parecidos)
            base = nuevo_email
            counter = 2
            while nuevo_email in emails_usados:
                partes = base.split("@")
                nuevo_email = f"{partes[0]}{counter}@{partes[1]}"
                counter += 1
            emails_usados.add(nuevo_email)

            # Si ya existe otro usuario con ese email nuevo, renombrarlo
            conflicto = db.query(Usuario).filter(
                Usuario.email == nuevo_email,
                Usuario.id != prof.id
            ).first()
            if conflicto:
                conflicto.email = f"_dup_{conflicto.id}_{conflicto.email}"

            prof.email         = nuevo_email
            prof.rol           = RolEnum.profesor
            prof.password_hash = HASH
            print(f"  ✏️  {prof.nombre:<35} → {nuevo_email}")

        # ── 5. Alumnos existentes → nuevo email ───────────────────────────────
        print("\n── Alumnos (actualizar email) ───────────────")
        alumnos = db.query(Usuario).filter(Usuario.rol == RolEnum.alumno).all()
        for al in alumnos:
            nuevo_email = email_alumno(al.nombre)
            conflicto = db.query(Usuario).filter(
                Usuario.email == nuevo_email,
                Usuario.id != al.id
            ).first()
            if conflicto:
                conflicto.email = f"_dup_{conflicto.id}_{conflicto.email}"
            al.email         = nuevo_email
            al.password_hash = HASH
            print(f"  ✏️  {al.nombre:<35} → {nuevo_email}")

        db.commit()

        # ── Resumen final ──────────────────────────────────────────────────────
        print("\n══════════════════════════════════════════════")
        print("  RESUMEN DE CUENTAS")
        print("══════════════════════════════════════════════")

        cuentas = db.query(Usuario).order_by(Usuario.rol, Usuario.nombre).all()
        roles_count = {}
        for u in cuentas:
            roles_count[u.rol.value] = roles_count.get(u.rol.value, 0) + 1

        print(f"\n  Total usuarios: {len(cuentas)}")
        for rol, cnt in sorted(roles_count.items()):
            print(f"    {rol:<22}: {cnt}")

        print("\n── Cuentas de acceso para pruebas ──────────")
        ejemplos = [
            ("Administrador",      "admin@admin.frt.utn.edu.ar"),
            ("Jefe departamento",  "sistemas@depto.frt.utn.edu.ar"),
            ("Administrativo",     "secretaria.academica@adm.frt.utn.edu.ar"),
        ]
        # Un profesor de ejemplo: Valla Sandra
        valla = db.query(Usuario).filter(Usuario.nombre.ilike("%valla%")).first()
        if valla:
            ejemplos.append(("Profesor (ej.)", valla.email))
        # Un alumno de ejemplo
        alumno = db.query(Usuario).filter(Usuario.rol == RolEnum.alumno).first()
        if alumno:
            ejemplos.append(("Alumno (ej.)", alumno.email))

        for label, email in ejemplos:
            print(f"  {label:<22}: {email}")
        print(f"  {'Contraseña':<22}: 123456")
        print("\n══════════════════════════════════════════════\n")

    except Exception as e:
        db.rollback()
        print(f"\n❌ ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
