/**
 * Mi perfil: los datos de la cuenta. Se cambian el nombre, el apellido (por separado) y la contraseña;
 * el mail institucional se muestra pero no se puede cambiar.
 *
 * Props:
 *   usuario:        datos de la sesión ({ nombre, nombre_pila, apellido, email, rol, creado_en, ... })
 *   onActualizado:  (usuario) => void — nombre nuevo (para la barra lateral)
 */
import { useState } from 'react'
import { Lock } from 'lucide-react'
import { actualizarPerfil, cambiarPassword } from '../api'
import CampoClave from './CampoClave'
import { boton, campo, errorDe, tarjeta } from './ui'

const ROLES = { ADMIN: 'Administrador', SMOD: 'Super moderador', MOD: 'Moderador', USUARIO: 'Usuario' }

function Aviso({ mensaje }) {
  if (!mensaje) return null
  return <span className={`text-xs ${mensaje.ok ? 'text-emerald-400' : 'text-red-400'}`}>{mensaje.texto}</span>
}

function Datos({ usuario, onActualizado }) {
  // Cuentas viejas sin apellido guardado: el backend separa la primera palabra como nombre
  const [nombre, setNombre] = useState(usuario.nombre_pila ?? usuario.nombre)
  const [apellido, setApellido] = useState(usuario.apellido ?? '')
  const [guardando, setGuardando] = useState(false)
  const [mensaje, setMensaje] = useState(null)
  const sinCambios = nombre.trim() === (usuario.nombre_pila ?? usuario.nombre) && apellido.trim() === (usuario.apellido ?? '')

  async function guardar(e) {
    e.preventDefault()
    if (nombre.trim().length < 2 || apellido.trim().length < 2)
      return setMensaje({ ok: false, texto: 'Completá tu nombre y tu apellido.' })
    setGuardando(true)
    setMensaje(null)
    try {
      const actualizado = await actualizarPerfil(nombre.trim(), apellido.trim())
      setNombre(actualizado.nombre_pila)
      setApellido(actualizado.apellido)
      onActualizado(actualizado)
      setMensaje({ ok: true, texto: 'Guardado.' })
    } catch (err) {
      setMensaje({ ok: false, texto: errorDe(err, 'No se pudo guardar.') })
    } finally {
      setGuardando(false)
    }
  }

  const desde = usuario.creado_en
    ? new Date(usuario.creado_en).toLocaleDateString('es-AR', { day: 'numeric', month: 'long', year: 'numeric' }) : null

  return (
    <form onSubmit={guardar} className={`${tarjeta} space-y-4`}>
      <h3 className="text-sm font-semibold text-[#f4f4f5]">Datos personales</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label className="block text-xs text-[#a1a1aa]">
          Nombre
          <input required minLength={2} maxLength={74} value={nombre} onChange={e => setNombre(e.target.value)}
                 autoComplete="given-name" className={`${campo} mt-1`} />
        </label>
        <label className="block text-xs text-[#a1a1aa]">
          Apellido
          <input required minLength={2} maxLength={74} value={apellido} onChange={e => setApellido(e.target.value)}
                 autoComplete="family-name" className={`${campo} mt-1`} />
        </label>
      </div>
      <label className="block text-xs text-[#a1a1aa]">
        Mail institucional
        <div className="relative mt-1">
          <input value={usuario.email} disabled className={`${campo} !text-[#8b8b93] cursor-not-allowed pr-10`} />
          <Lock size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#4b4b53]" />
        </div>
        <span className="block text-[11px] text-[#4b4b53] mt-1">El mail institucional no se puede cambiar.</span>
      </label>
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-[#8b8b93]">
        <span>Rol: <span className="text-[#c7c7cf]">{ROLES[usuario.rol] ?? usuario.rol}</span></span>
        {desde && <span>Cuenta creada el {desde}</span>}
      </div>
      <div className="flex items-center gap-3">
        <button type="submit" disabled={guardando || sinCambios} className={boton}>
          {guardando ? 'Guardando…' : 'Guardar cambios'}
        </button>
        <Aviso mensaje={mensaje} />
      </div>
    </form>
  )
}

function Clave() {
  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [repetida, setRepetida] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [mensaje, setMensaje] = useState(null)

  async function cambiar(e) {
    e.preventDefault()
    if (nueva.length < 8 || !/\d/.test(nueva))
      return setMensaje({ ok: false, texto: 'La contraseña nueva necesita al menos 8 caracteres y un número.' })
    if (nueva !== repetida) return setMensaje({ ok: false, texto: 'Las contraseñas nuevas no coinciden.' })
    setGuardando(true)
    setMensaje(null)
    try {
      await cambiarPassword(actual, nueva)
      setActual(''); setNueva(''); setRepetida('')
      setMensaje({ ok: true, texto: 'Listo. Se cerraron tus sesiones en otros dispositivos.' })
    } catch (err) {
      setMensaje({ ok: false, texto: errorDe(err, 'No se pudo cambiar la contraseña.') })
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form onSubmit={cambiar} className={`${tarjeta} space-y-4`}>
      <h3 className="text-sm font-semibold text-[#f4f4f5]">Cambiar contraseña</h3>
      <label className="block text-xs text-[#a1a1aa]">
        Contraseña actual
        <div className="mt-1"><CampoClave required value={actual} onChange={e => setActual(e.target.value)}
                                           autoComplete="current-password" className={campo} /></div>
      </label>
      <label className="block text-xs text-[#a1a1aa]">
        Contraseña nueva
        <div className="mt-1"><CampoClave required minLength={8} value={nueva} onChange={e => setNueva(e.target.value)}
                                           autoComplete="new-password" className={campo} /></div>
        <span className="block text-[11px] text-[#4b4b53] mt-1">Mínimo 8 caracteres, con al menos un número.</span>
      </label>
      <label className="block text-xs text-[#a1a1aa]">
        Repetí la contraseña nueva
        <div className="mt-1"><CampoClave required value={repetida} onChange={e => setRepetida(e.target.value)}
                                           autoComplete="new-password" className={campo} /></div>
      </label>
      <div className="flex items-center gap-3">
        <button type="submit" disabled={guardando || !actual || !nueva} className={boton}>
          {guardando ? 'Cambiando…' : 'Cambiar contraseña'}
        </button>
        <Aviso mensaje={mensaje} />
      </div>
    </form>
  )
}

export default function Perfil({ usuario, onActualizado }) {
  return (
    <div className="h-full overflow-y-auto bg-[#0a0a0c] text-[#f4f4f5] font-body p-6 [color-scheme:dark]">
      <div className="max-w-xl mx-auto space-y-6">
        <div>
          <h2 className="font-display text-xl font-semibold">Mi perfil</h2>
          <p className="text-sm text-[#8b8b93] mt-1">Tus datos de la cuenta.</p>
        </div>
        <Datos usuario={usuario} onActualizado={onActualizado} />
        <Clave />
      </div>
    </div>
  )
}
