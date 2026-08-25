/**
 * Chat — pantalla principal del asistente.
 *
 * Props:
 *   usuario:   objeto con { nombre, email, rol }
 *   onLogout:  función para cerrar sesión
 *   sinHeader: bool — si es true, oculta el header propio (lo maneja App.jsx)
 */
import { useState, useRef, useEffect } from 'react'
import { enviarMensaje } from '../api'
import MensajeBurbuja from './MensajeBurbuja'

// Mapeo de roles para mostrar al usuario
const ROLES_DISPLAY = {
  administrador:      { label: 'Administrador', color: 'bg-purple-100 text-purple-700' },
  profesor_directivo: { label: 'Profesor / Directivo', color: 'bg-green-100 text-green-700' },
  alumno:             { label: 'Alumno', color: 'bg-blue-100 text-blue-700' },
}

function ahora() {
  return new Date().toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
}

export default function Chat({ usuario, onLogout, sinHeader = false }) {
  const [mensajes, setMensajes]           = useState([
    {
      id: 1,
      tipo: 'asistente',
      texto: `¡Hola ${usuario.nombre}! Soy tu asistente universitario. Podés preguntarme sobre horarios, aulas, materias, comisiones y el calendario académico. ¿En qué te puedo ayudar?`,
      timestamp: ahora(),
    },
  ])
  const [input, setInput]                 = useState('')
  const [escribiendo, setEscribiendo]     = useState(false)
  const [conversacionId, setConversacionId] = useState(null)
  const bottomRef                          = useRef(null)
  const inputRef                           = useRef(null)

  // Scroll automático al último mensaje
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensajes, escribiendo])

  async function handleEnviar() {
    const texto = input.trim()
    if (!texto || escribiendo) return

    // Agregar mensaje del usuario al historial
    const msgUsuario = {
      id: Date.now(),
      tipo: 'usuario',
      texto,
      timestamp: ahora(),
    }
    setMensajes(prev => [...prev, msgUsuario])
    setInput('')
    setEscribiendo(true)

    try {
      const data = await enviarMensaje(texto, conversacionId)

      if (data.conversacion_id) setConversacionId(data.conversacion_id)

      setMensajes(prev => [
        ...prev,
        {
          id: Date.now() + 1,
          tipo: 'asistente',
          texto: data.respuesta,
          timestamp: ahora(),
        },
      ])
    } catch (err) {
      let textoError = 'Ocurrió un error al procesar tu consulta. Intentá de nuevo.'
      if (err.response?.status === 401) {
        textoError = 'Tu sesión expiró. Por favor volvé a iniciar sesión.'
        onLogout()
      } else if (err.response?.status === 429) {
        textoError = 'Demasiadas consultas en poco tiempo. Esperá un momento antes de continuar.'
      } else if (err.response?.data?.detail) {
        textoError = err.response.data.detail
      }

      setMensajes(prev => [
        ...prev,
        { id: Date.now() + 1, tipo: 'error', texto: textoError, timestamp: ahora() },
      ])
    } finally {
      setEscribiendo(false)
      inputRef.current?.focus()
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleEnviar()
    }
  }

  const rolInfo = ROLES_DISPLAY[usuario.rol] ?? { label: usuario.rol, color: 'bg-gray-100 text-gray-700' }

  return (
    <div className={`flex flex-col ${sinHeader ? 'h-full' : 'h-screen'} bg-gray-50`}>

      {/* ── Header (solo si no lo maneja el padre) ──────────────────── */}
      {!sinHeader && (
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-primary-600 rounded-xl flex items-center justify-center">
            <span className="text-white text-sm font-bold">AU</span>
          </div>
          <div>
            <h1 className="text-sm font-semibold text-gray-900">Asistente Universitario</h1>
            <p className="text-xs text-gray-500">Consultas académicas</p>
          </div>
        </div>

        {/* Info del usuario */}
        <div className="flex items-center gap-3">
          <div className="text-right hidden sm:block">
            <p className="text-sm font-medium text-gray-900">{usuario.nombre}</p>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${rolInfo.color}`}>
              {rolInfo.label}
            </span>
          </div>
          <button
            onClick={onLogout}
            className="text-sm text-gray-500 hover:text-red-600 font-medium px-3 py-1.5
                       rounded-lg hover:bg-red-50 transition-colors"
          >
            Salir
          </button>
        </div>
      </header>
      )}

      {/* ── Historial de mensajes ───────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto chat-scroll px-4 py-4">
        <div className="max-w-3xl mx-auto">
          {mensajes.map(msg => (
            <MensajeBurbuja key={msg.id} mensaje={msg} />
          ))}

          {/* Indicador "escribiendo..." */}
          {escribiendo && (
            <div className="flex justify-start mb-3">
              <div className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center mr-2 mt-1 flex-shrink-0">
                <span className="text-white text-xs font-bold">AU</span>
              </div>
              <div className="bg-white border border-gray-200 shadow-sm rounded-2xl rounded-bl-sm px-4 py-3">
                <div className="flex gap-1 items-center h-4">
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </main>

      {/* ── Input de mensaje ────────────────────────────────────────────── */}
      <footer className="bg-white border-t border-gray-200 px-4 py-3">
        <div className="max-w-3xl mx-auto flex gap-3 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Escribí tu consulta... (Enter para enviar, Shift+Enter para nueva línea)"
            rows={1}
            disabled={escribiendo}
            className="flex-1 resize-none px-4 py-2.5 border border-gray-300 rounded-xl text-sm
                       focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
                       disabled:bg-gray-50 disabled:text-gray-400 transition-colors
                       max-h-32 overflow-y-auto"
            style={{ minHeight: '42px' }}
            onInput={e => {
              // Auto-resize del textarea
              e.target.style.height = 'auto'
              e.target.style.height = Math.min(e.target.scrollHeight, 128) + 'px'
            }}
          />
          <button
            onClick={handleEnviar}
            disabled={!input.trim() || escribiendo}
            className="bg-primary-600 hover:bg-primary-700 disabled:bg-gray-200 disabled:cursor-not-allowed
                       text-white disabled:text-gray-400 p-2.5 rounded-xl transition-colors
                       focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2
                       flex-shrink-0"
            aria-label="Enviar mensaje"
          >
            {/* Ícono enviar */}
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
              <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
            </svg>
          </button>
        </div>
        <p className="text-xs text-gray-400 text-center mt-2">
          El asistente responde según la información disponible en el sistema.
        </p>
      </footer>

    </div>
  )
}
