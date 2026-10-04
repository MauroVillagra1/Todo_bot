/**
 * App — componente raíz que maneja el estado global de sesión.
 *
 * Flujo:
 *   Sin token → Login
 *   Con token → Chat (el sidebar de Chat maneja la navegación Chat/Panel)
 */
import { useState } from 'react'
import Login from './components/Login'
import Chat  from './components/Chat'
import { setAuthToken } from './api'

export default function App() {
  const [token,   setToken]   = useState(null)
  const [usuario, setUsuario] = useState(null)

  function handleLogin(nuevoToken, datosUsuario) {
    setToken(nuevoToken)
    setUsuario(datosUsuario)
    setAuthToken(nuevoToken)
  }

  function handleLogout() {
    setToken(null)
    setUsuario(null)
    setAuthToken(null)
  }

  if (!token || !usuario) {
    return <Login onLogin={handleLogin} />
  }

  return <Chat usuario={usuario} onLogout={handleLogout} />
}
