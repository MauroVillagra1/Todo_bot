/**
 * Login — pantalla de inicio de sesión.
 * Tema oscuro consistente con el resto de la app.
 *
 * Props:
 *   onLogin: función que recibe (token, usuario) cuando el login es exitoso
 */
import { useState } from 'react'
import { login } from '../api'

const LOGO_URL = 'https://res.cloudinary.com/dol1ba0ld/image/upload/v1787954474/asd/Preguntale_a_UTNIA_xwocbf.png'

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

export default function Login({ onLogin }) {
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [cargando, setCargando] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setCargando(true)
    try {
      const data = await login(email, password)
      onLogin(data.access_token, data.usuario)
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Email o contraseña incorrectos.')
      } else if (err.response?.status === 422) {
        setError('Por favor completá todos los campos.')
      } else {
        setError('No se pudo conectar con el servidor.')
      }
    } finally {
      setCargando(false)
    }
  }

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
          <p className="font-body text-sm text-[#8b8b93] mt-1">
            Ingresá con tu cuenta institucional
          </p>
        </div>

        {/* Card */}
        <div className="bg-[#0d0d10] border border-[#1e1e22] rounded-2xl p-6">
          <form onSubmit={handleSubmit} className="space-y-4">

            <div>
              <label className="block font-body text-xs font-medium text-[#8b8b93] mb-1.5">
                Email institucional
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="tu@frt.utn.edu.ar"
                required
                autoFocus
                className="w-full bg-[#141417] border border-[#232327] rounded-xl px-4 py-2.5
                           font-body text-sm text-[#f4f4f5] placeholder-[#4b4b53]
                           focus:outline-none focus:border-[#e8592e]/50 transition-colors"
              />
            </div>

            <div>
              <label className="block font-body text-xs font-medium text-[#8b8b93] mb-1.5">
                Contraseña
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full bg-[#141417] border border-[#232327] rounded-xl px-4 py-2.5
                           font-body text-sm text-[#f4f4f5] placeholder-[#4b4b53]
                           focus:outline-none focus:border-[#e8592e]/50 transition-colors"
              />
            </div>

            {/* Error */}
            {error && (
              <div className="bg-red-500/10 border border-red-500/20 text-red-300 font-body text-sm px-4 py-3 rounded-xl">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={cargando}
              className="w-full bg-[#e8592e] hover:bg-[#f2703f] disabled:bg-[#232327]
                         disabled:text-[#4b4b53] disabled:cursor-not-allowed
                         text-white font-body font-medium py-2.5 px-4 rounded-xl text-sm
                         transition-colors focus:outline-none mt-2"
            >
              {cargando ? 'Ingresando...' : 'Ingresar'}
            </button>
          </form>
        </div>

        <p className="font-body text-[11px] text-[#4b4b53] text-center mt-4">
          UTN — Facultad Regional Tucumán
        </p>
      </div>
    </div>
  )
}
