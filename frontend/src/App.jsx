/**
 * App — componente raíz que maneja el estado global de sesión.
 *
 * Flujo:
 *   Sin token → Login
 *   Con token + rol alumno → Chat
 *   Con token + rol profesor_directivo | administrador → Panel (con acceso al Chat también)
 */
import { useState } from 'react'
import Login  from './components/Login'
import Chat   from './components/Chat'
import Panel  from './components/Panel'
import { setAuthToken } from './api'

export default function App() {
  const [token,   setToken]   = useState(null)
  const [usuario, setUsuario] = useState(null)
  // 'chat' | 'panel'  — vista activa para staff/admin
  const [vista,   setVista]   = useState('chat')

  function handleLogin(nuevoToken, datosUsuario) {
    setToken(nuevoToken)
    setUsuario(datosUsuario)
    setAuthToken(nuevoToken)
    // Staff/admin empiezan en el panel
    if (datosUsuario.rol !== 'alumno') {
      setVista('panel')
    }
  }

  function handleLogout() {
    setToken(null)
    setUsuario(null)
    setAuthToken(null)
    setVista('chat')
  }

  if (!token || !usuario) {
    return <Login onLogin={handleLogin} />
  }

  // Alumnos van directo al chat
  if (usuario.rol === 'alumno') {
    return <Chat usuario={usuario} onLogout={handleLogout} />
  }

  // Staff / Admin: barra de navegación superior + vista activa
  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Barra de navegación de vistas */}
      <nav className="bg-white border-b border-gray-200 px-4 py-2 flex items-center gap-2 shadow-sm">
        <div className="flex items-center gap-2 mr-4">
          <div className="w-8 h-8 bg-primary-600 rounded-xl flex items-center justify-center">
            <span className="text-white text-xs font-bold">AU</span>
          </div>
          <span className="text-sm font-semibold text-gray-700 hidden sm:block">
            Asistente Universitario
          </span>
        </div>

        <button
          onClick={() => setVista('chat')}
          className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            vista === 'chat'
              ? 'bg-primary-600 text-white'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          💬 Chat
        </button>

        <button
          onClick={() => setVista('panel')}
          className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            vista === 'panel'
              ? 'bg-primary-600 text-white'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          📋 Panel de carga
        </button>

        {/* Espaciador */}
        <div className="flex-1" />

        {/* Info usuario */}
        <span className="text-sm text-gray-500 hidden sm:block">{usuario.nombre}</span>
        <button
          onClick={handleLogout}
          className="text-sm text-gray-500 hover:text-red-600 font-medium px-3 py-1.5
                     rounded-lg hover:bg-red-50 transition-colors"
        >
          Salir
        </button>
      </nav>

      {/* Vista activa */}
      <div className="flex-1 overflow-hidden">
        {vista === 'chat'
          ? <Chat usuario={usuario} onLogout={handleLogout} sinHeader />
          : <Panel usuario={usuario} />
        }
      </div>
    </div>
  )
}
