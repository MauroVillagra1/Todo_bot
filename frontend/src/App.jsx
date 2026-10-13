/**
 * App — componente raíz que maneja el estado global de sesión.
 *
 * Flujo:
 *   Al abrir: si hay un refresh token guardado se renueva la sesión (no hay que loguearse de nuevo)
 *   Sin sesión → Login
 *   Con sesión → Chat (el sidebar de Chat maneja la navegación Chat/Panel)
 */
import { useEffect, useState } from 'react'
import Login from './components/Login'
import Chat  from './components/Chat'
import { alVencer, borrarSesion, cerrarSesion, guardarSesion, renovarSesion } from './api'

export default function App() {
  const [usuario,   setUsuario]   = useState(null)
  const [iniciando, setIniciando] = useState(true)

  useEffect(() => {
    alVencer(() => { borrarSesion(); setUsuario(null) })
    renovarSesion()
      .then(sesion => setUsuario(sesion?.usuario ?? null))
      .finally(() => setIniciando(false))
  }, [])

  function handleLogin(sesion) {
    guardarSesion(sesion)
    setUsuario(sesion.usuario)
  }

  async function handleLogout() {
    await cerrarSesion()
    setUsuario(null)
  }

  if (iniciando) {
    return <div className="min-h-screen bg-[#0a0a0c]" />
  }
  if (!usuario) {
    return <Login onLogin={handleLogin} />
  }

  return <Chat usuario={usuario} onLogout={handleLogout} />
}
