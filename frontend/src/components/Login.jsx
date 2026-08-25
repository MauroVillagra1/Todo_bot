/**
 * Login — pantalla de inicio de sesión.
 *
 * Props:
 *   onLogin: función que recibe (token, usuario) cuando el login es exitoso
 */
import { useState } from 'react'
import { login } from '../api'

export default function Login({ onLogin }) {
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
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
        setError('No se pudo conectar con el servidor. Verificá que el backend esté corriendo.')
      }
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 to-blue-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-lg w-full max-w-md p-8">

        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-primary-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <span className="text-white text-2xl font-bold">AU</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Asistente Universitario</h1>
          <p className="text-gray-500 text-sm mt-1">Ingresá con tu cuenta institucional</p>
        </div>

        {/* Formulario */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email institucional
            </label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="tu@universidad.edu"
              required
              autoFocus
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm
                         focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
                         transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Contraseña
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm
                         focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
                         transition-colors"
            />
          </div>

          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={cargando}
            className="w-full bg-primary-600 hover:bg-primary-700 disabled:bg-primary-300
                       text-white font-medium py-2.5 px-4 rounded-lg text-sm
                       transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
          >
            {cargando ? 'Ingresando...' : 'Ingresar'}
          </button>
        </form>

        {/* Credenciales de prueba */}
        <div className="mt-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <p className="text-xs font-semibold text-gray-500 mb-2">CUENTAS DE PRUEBA</p>
          <div className="space-y-1 text-xs text-gray-600 font-mono">
            <div>admin@universidad.edu / Admin1234</div>
            <div>garcia@universidad.edu / Profe1234</div>
            <div>ana@universidad.edu / Alumno1234</div>
          </div>
        </div>

      </div>
    </div>
  )
}
