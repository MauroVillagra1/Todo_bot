/**
 * Login — inicio de sesión, registro con código al mail institucional y
 * recuperación de contraseña. Tema oscuro consistente con el resto de la app.
 *
 * Pantallas: login → registro → verificar (código) | recuperar → restablecer (código + nueva contraseña)
 * Las reglas reales (dominios, cuentas repetidas, intentos) las valida el backend.
 *
 * Props:
 *   onLogin: función que recibe (token, usuario) cuando el login es exitoso
 */
import { useState } from 'react'
import {
  confirmarRecuperacion, login, solicitarRecuperacion, solicitarRegistro, verificarRegistro,
} from '../api'

const LOGO_URL = 'https://res.cloudinary.com/dol1ba0ld/image/upload/v1787954474/asd/Preguntale_a_UTNIA_xwocbf.png'
const DOMINIOS = ['alu.frt.utn.edu.ar', 'doc.frt.utn.edu.ar']

const campo = `w-full bg-[#141417] border border-[#232327] rounded-xl px-4 py-2.5
               font-body text-sm text-[#f4f4f5] placeholder-[#4b4b53]
               focus:outline-none focus:border-[#e8592e]/50 transition-colors`
const botonPrincipal = `w-full bg-[#e8592e] hover:bg-[#f2703f] disabled:bg-[#232327]
                        disabled:text-[#4b4b53] disabled:cursor-not-allowed
                        text-white font-body font-medium py-2.5 px-4 rounded-xl text-sm
                        transition-colors focus:outline-none mt-2`
const enlace = 'font-body text-xs text-[#8b8b93] hover:text-[#f2894f] transition-colors'

const SUBTITULOS = {
  login:       'Ingresá con tu cuenta institucional',
  registro:    'Creá tu cuenta con tu mail institucional',
  verificar:   'Revisá tu mail institucional',
  recuperar:   'Recuperá tu contraseña',
  restablecer: 'Elegí una contraseña nueva',
}

function LogoUTNIA({ size = 48 }) {
  return (
    <img
      src={LOGO_URL}
      alt="UTNIA"
      width={size}
      height={size}
      className="rounded-full object-cover flex-shrink-0"
      style={{ width: size, height: size }}
    />
  )
}

function Campo({ etiqueta, ayuda, ...props }) {
  return (
    <div>
      <label className="block font-body text-xs font-medium text-[#8b8b93] mb-1.5">{etiqueta}</label>
      <input {...props} className={campo} />
      {ayuda && <p className="font-body text-[11px] text-[#4b4b53] mt-1">{ayuda}</p>}
    </div>
  )
}

function errorDe(err, porDefecto) {
  const detalle = err.response?.data?.detail
  if (typeof detalle === 'string') return detalle
  if (Array.isArray(detalle)) return detalle.map(d => d.msg.replace(/^Value error, /, '')).join(' · ')
  if (!err.response) return 'No se pudo conectar con el servidor.'
  return porDefecto
}

function emailValido(email) {
  return DOMINIOS.includes(email.trim().toLowerCase().split('@')[1] ?? '')
}

export default function Login({ onLogin }) {
  const [pantalla, setPantalla] = useState('login')
  const [nombre,   setNombre]   = useState('')
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [repetida, setRepetida] = useState('')
  const [codigo,   setCodigo]   = useState('')
  const [error,    setError]    = useState('')
  const [aviso,    setAviso]    = useState('')
  const [cargando, setCargando] = useState(false)

  function ir(nueva, mensaje = '') {
    setPantalla(nueva)
    setError('')
    setAviso(mensaje)
    setCodigo('')
    if (nueva === 'login' || nueva === 'restablecer') { setPassword(''); setRepetida('') }
  }

  // Ejecuta una acción con estado de carga y errores uniformes
  async function ejecutar(accion, porDefecto) {
    setError('')
    setCargando(true)
    try {
      await accion()
    } catch (err) {
      setError(errorDe(err, porDefecto))
    } finally {
      setCargando(false)
    }
  }

  function validarCuenta() {
    if (!emailValido(email)) return 'Usá tu mail @alu.frt.utn.edu.ar o @doc.frt.utn.edu.ar.'
    if (password.length < 8 || !/\d/.test(password)) return 'La contraseña necesita al menos 8 caracteres y un número.'
    if (password !== repetida) return 'Las contraseñas no coinciden.'
    return ''
  }

  function handleLogin(e) {
    e.preventDefault()
    ejecutar(async () => {
      const data = await login(email, password)
      onLogin(data.access_token, data.usuario)
    }, 'No se pudo iniciar sesión.')
  }

  function handleRegistro(e) {
    e.preventDefault()
    const problema = validarCuenta()
    if (problema) return setError(problema)
    ejecutar(async () => {
      const data = await solicitarRegistro(nombre, email, password)
      ir('verificar', data.mensaje)
    }, 'No se pudo enviar el código.')
  }

  function handleVerificar(e) {
    e.preventDefault()
    ejecutar(async () => {
      const data = await verificarRegistro(email, codigo)
      onLogin(data.access_token, data.usuario)
    }, 'No se pudo verificar el código.')
  }

  function reenviarRegistro() {
    ejecutar(async () => {
      const data = await solicitarRegistro(nombre, email, password)
      setAviso(data.mensaje)
    }, 'No se pudo reenviar el código.')
  }

  function handleRecuperar(e) {
    e.preventDefault()
    if (!emailValido(email)) return setError('Usá tu mail @alu.frt.utn.edu.ar o @doc.frt.utn.edu.ar.')
    ejecutar(async () => {
      const data = await solicitarRecuperacion(email)
      ir('restablecer', data.mensaje)
    }, 'No se pudo enviar el código.')
  }

  function handleRestablecer(e) {
    e.preventDefault()
    const problema = validarCuenta()
    if (problema) return setError(problema)
    ejecutar(async () => {
      const data = await confirmarRecuperacion(email, codigo, password)
      ir('login', data.mensaje)
    }, 'No se pudo cambiar la contraseña.')
  }

  const campoEmail = (
    <Campo etiqueta="Email institucional" type="email" value={email} onChange={e => setEmail(e.target.value)}
           placeholder="tu@alu.frt.utn.edu.ar" required autoFocus autoComplete="email" />
  )
  const camposPassword = (nueva) => (
    <>
      <Campo etiqueta={nueva ? 'Contraseña nueva' : 'Contraseña'} type="password" value={password}
             onChange={e => setPassword(e.target.value)} placeholder="••••••••" required minLength={8}
             autoComplete="new-password" ayuda="Mínimo 8 caracteres, con al menos un número." />
      <Campo etiqueta="Repetí la contraseña" type="password" value={repetida}
             onChange={e => setRepetida(e.target.value)} placeholder="••••••••" required autoComplete="new-password" />
    </>
  )
  const campoCodigo = (
    <Campo etiqueta="Código de 6 dígitos" value={codigo} required autoFocus
           onChange={e => setCodigo(e.target.value.replace(/\D/g, '').slice(0, 6))}
           placeholder="123456" inputMode="numeric" autoComplete="one-time-code" pattern="\d{6}"
           ayuda={`Lo enviamos a ${email}. Vence en 15 minutos; revisá también la carpeta de spam.`} />
  )

  return (
    <div className="min-h-screen bg-[#0a0a0c] flex items-center justify-center p-4">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');
        .font-display { font-family: 'Space Grotesk', sans-serif; }
        .font-body    { font-family: 'Inter', sans-serif; }
      `}</style>

      <div className="w-full max-w-sm">

        {/* Logo + título */}
        <div className="flex flex-col items-center mb-8">
          <LogoUTNIA size={52} />
          <h1 className="font-display text-2xl font-semibold text-[#f4f4f5] mt-4 tracking-tight">
            UTNIA
          </h1>
          <p className="font-body text-sm text-[#8b8b93] mt-1">{SUBTITULOS[pantalla]}</p>
        </div>

        {/* Card */}
        <div className="bg-[#0d0d10] border border-[#1e1e22] rounded-2xl p-6">
          {pantalla === 'login' && (
            <form onSubmit={handleLogin} className="space-y-4">
              {campoEmail}
              <Campo etiqueta="Contraseña" type="password" value={password} onChange={e => setPassword(e.target.value)}
                     placeholder="••••••••" required autoComplete="current-password" />
              <div className="flex justify-end -mt-2">
                <button type="button" onClick={() => ir('recuperar')} className={enlace}>
                  ¿Olvidaste tu contraseña?
                </button>
              </div>
              <Mensajes error={error} aviso={aviso} />
              <button type="submit" disabled={cargando} className={botonPrincipal}>
                {cargando ? 'Ingresando...' : 'Ingresar'}
              </button>
              <button type="button" onClick={() => ir('registro')}
                      className="w-full border border-[#232327] hover:border-[#e8592e]/50 hover:text-[#f2894f]
                                 text-[#f4f4f5] font-body font-medium py-2.5 px-4 rounded-xl text-sm transition-colors">
                Crear cuenta
              </button>
            </form>
          )}

          {pantalla === 'registro' && (
            <form onSubmit={handleRegistro} className="space-y-4">
              <Campo etiqueta="Nombre y apellido" value={nombre} onChange={e => setNombre(e.target.value)}
                     placeholder="Ana Pérez" required minLength={2} maxLength={150} autoFocus autoComplete="name" />
              <Campo etiqueta="Email institucional" type="email" value={email} onChange={e => setEmail(e.target.value)}
                     placeholder="tu@alu.frt.utn.edu.ar" required autoComplete="email"
                     ayuda="Solo @alu.frt.utn.edu.ar o @doc.frt.utn.edu.ar." />
              {camposPassword(false)}
              <Mensajes error={error} aviso={aviso} />
              <button type="submit" disabled={cargando} className={botonPrincipal}>
                {cargando ? 'Enviando código...' : 'Enviar código de verificación'}
              </button>
              <Volver onClick={() => ir('login')} texto="¿Ya tenés cuenta? Iniciá sesión" />
            </form>
          )}

          {pantalla === 'verificar' && (
            <form onSubmit={handleVerificar} className="space-y-4">
              {campoCodigo}
              <Mensajes error={error} aviso={aviso} />
              <button type="submit" disabled={cargando || codigo.length !== 6} className={botonPrincipal}>
                {cargando ? 'Verificando...' : 'Crear cuenta'}
              </button>
              <div className="flex justify-between">
                <button type="button" onClick={() => ir('registro')} className={enlace}>Cambiar datos</button>
                <button type="button" onClick={reenviarRegistro} disabled={cargando} className={enlace}>
                  Reenviar código
                </button>
              </div>
            </form>
          )}

          {pantalla === 'recuperar' && (
            <form onSubmit={handleRecuperar} className="space-y-4">
              {campoEmail}
              <p className="font-body text-xs text-[#8b8b93]">Te enviamos un código para elegir una contraseña nueva.</p>
              <Mensajes error={error} aviso={aviso} />
              <button type="submit" disabled={cargando} className={botonPrincipal}>
                {cargando ? 'Enviando...' : 'Enviar código'}
              </button>
              <Volver onClick={() => ir('login')} texto="Volver a iniciar sesión" />
            </form>
          )}

          {pantalla === 'restablecer' && (
            <form onSubmit={handleRestablecer} className="space-y-4">
              {campoCodigo}
              {camposPassword(true)}
              <Mensajes error={error} aviso={aviso} />
              <button type="submit" disabled={cargando || codigo.length !== 6} className={botonPrincipal}>
                {cargando ? 'Guardando...' : 'Cambiar contraseña'}
              </button>
              <div className="flex justify-between">
                <button type="button" onClick={() => ir('login')} className={enlace}>Volver</button>
                <button type="button" onClick={handleRecuperar} disabled={cargando} className={enlace}>
                  Reenviar código
                </button>
              </div>
            </form>
          )}
        </div>

        <p className="font-body text-[11px] text-[#4b4b53] text-center mt-4">
          UTN — Facultad Regional Tucumán
        </p>
      </div>
    </div>
  )
}

function Mensajes({ error, aviso }) {
  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/20 text-red-300 font-body text-sm px-4 py-3 rounded-xl">
        {error}
      </div>
    )
  }
  if (aviso) {
    return (
      <div className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 font-body text-sm px-4 py-3 rounded-xl">
        {aviso}
      </div>
    )
  }
  return null
}

function Volver({ onClick, texto }) {
  return (
    <div className="text-center">
      <button type="button" onClick={onClick} className={enlace}>{texto}</button>
    </div>
  )
}
