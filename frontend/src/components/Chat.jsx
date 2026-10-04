/**
 * Chat — pantalla principal del asistente UTNIA.
 * Incluye sidebar con navegación Chat/Panel para staff y admin.
 */
import { useState, useRef, useEffect } from 'react'
import { Send, LogOut, Sparkles, User, LayoutDashboard, MessageSquare } from 'lucide-react'
import { enviarMensaje as apiEnviarMensaje } from '../api'
import MensajeBurbuja from './MensajeBurbuja'
import Panel from './Panel'

const ROLES_DISPLAY = {
  root:           { label: 'Root',              color: 'bg-red-500/15 text-red-400' },
  master:         { label: 'Master',            color: 'bg-[#e8592e]/15 text-[#f2894f]' },
  administrativo: { label: 'Administrativo',    color: 'bg-sky-500/15 text-sky-400' },
  jefe_area:      { label: 'Jefe de Área',      color: 'bg-emerald-500/15 text-emerald-400' },
  docente:        { label: 'Docente',           color: 'bg-violet-500/15 text-violet-400' },
  estudiante:     { label: 'Estudiante',        color: 'bg-gray-500/15 text-gray-400' },
  // aliases legacy
  administrador:     { label: 'Master',         color: 'bg-[#e8592e]/15 text-[#f2894f]' },
  jefe_departamento: { label: 'Jefe de Área',   color: 'bg-emerald-500/15 text-emerald-400' },
  profesor_directivo:{ label: 'Docente',        color: 'bg-violet-500/15 text-violet-400' },
  profesor:          { label: 'Docente',        color: 'bg-violet-500/15 text-violet-400' },
  alumno:            { label: 'Estudiante',     color: 'bg-gray-500/15 text-gray-400' },
}

const PREGUNTAS_EJEMPLO = [
  '¿Cuándo son las próximas mesas de examen?',
  '¿Qué eventos organiza la carrera de Sistemas?',
  '¿Cuándo abren las inscripciones?',
]

// Hasta la migración de roles (etapa 1) solo el administrador tiene panel
const TIENE_PANEL = ['administrador']

function ahora() {
  return new Date().toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
}

// ── Logo UTNIA ────────────────────────────────────────────────────────────────
const LOGO_URL = 'https://res.cloudinary.com/dol1ba0ld/image/upload/v1787954474/asd/Preguntale_a_UTNIA_xwocbf.png'

function LogoUTNIA({ size = 36 }) {
  return (
    <img
      src={LOGO_URL}
      alt="UTNIA"
      width={size}
      height={size}
      className="rounded-full flex-shrink-0 object-cover"
      style={{ width: size, height: size }}
    />
  )
}

export default function Chat({ usuario = { nombre: 'Invitado', rol: 'alumno' }, onLogout = () => {} }) {
  const [mensajes, setMensajes]             = useState([])
  const [input, setInput]                   = useState('')
  const [escribiendo, setEscribiendo]       = useState(false)
  const [conversacionId, setConversacionId] = useState(null)
  const [vista, setVista]                   = useState('chat') // 'chat' | 'panel'
  const bottomRef                            = useRef(null)
  const inputRef                             = useRef(null)

  const tienePanel = TIENE_PANEL.includes(usuario.rol)
  const rolInfo    = ROLES_DISPLAY[usuario.rol] ?? { label: usuario.rol, color: 'bg-gray-500/15 text-gray-300' }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensajes, escribiendo])

  async function enviar(textoForzado) {
    const texto = (textoForzado ?? input).trim()
    if (!texto || escribiendo) return

    // Si está en panel, cambiar a chat
    if (vista === 'panel') setVista('chat')

    const msgUsuario = { id: Date.now(), tipo: 'usuario', texto, timestamp: ahora() }
    setMensajes(prev => [...prev, msgUsuario])
    setInput('')
    setEscribiendo(true)

    try {
      const data = await apiEnviarMensaje(texto, conversacionId)
      if (data.conversacion_id) setConversacionId(data.conversacion_id)
      setMensajes(prev => [
        ...prev,
        { id: Date.now() + 1, tipo: 'asistente', texto: data.respuesta, timestamp: ahora() },
      ])
    } catch (err) {
      let textoError = 'Ocurrió un error al procesar tu consulta. Intentá de nuevo.'
      if (err.response?.status === 401) {
        textoError = 'Tu sesión expiró. Por favor volvé a iniciar sesión.'
        onLogout()
      } else if (err.response?.status === 429) {
        textoError = 'Demasiadas consultas en poco tiempo. Esperá un momento.'
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
      enviar()
    }
  }

  function nuevaConsulta() {
    setMensajes([])
    setConversacionId(null)
    setVista('chat')
    setTimeout(() => inputRef.current?.focus(), 50)
  }

  const hayConversacion = mensajes.length > 0

  return (
    <div className="flex h-screen bg-[#0a0a0c] text-[#f4f4f5]">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');
        .font-display { font-family: 'Space Grotesk', sans-serif; }
        .font-body    { font-family: 'Inter', sans-serif; }
        .chat-scroll::-webkit-scrollbar       { width: 5px; }
        .chat-scroll::-webkit-scrollbar-thumb { background: #2a2a30; border-radius: 999px; }
        .chat-scroll::-webkit-scrollbar-track { background: transparent; }
        @keyframes fadein { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
        .msg-in { animation: fadein 0.22s ease-out; }
        @keyframes bounce-dot { 0%,80%,100% { transform:translateY(0); } 40% { transform:translateY(-5px); } }
        .dot-bounce { animation: bounce-dot 1.2s infinite ease-in-out; }
      `}</style>

      {/* ── Sidebar ──────────────────────────────────────────────────────── */}
      <aside className="w-16 md:w-56 flex-shrink-0 bg-[#0d0d10] border-r border-[#1e1e22] flex flex-col py-4">

        {/* Logo + nombre */}
        <div className="flex items-center gap-2.5 px-3 mb-6">
          <LogoUTNIA size={34} />
          <span className="hidden md:block font-display font-semibold text-[15px] tracking-tight text-[#f4f4f5]">
            UTNIA
          </span>
        </div>

        {/* Nueva consulta */}
        <button
          onClick={nuevaConsulta}
          className="flex items-center justify-center md:justify-start gap-2 mx-3 mb-4 px-3 py-2 rounded-lg
                     text-sm font-body font-medium text-[#a8a8b3] border border-[#232327]
                     hover:border-[#e8592e]/40 hover:text-[#f2894f] transition-colors"
        >
          <Sparkles size={15} className="flex-shrink-0" />
          <span className="hidden md:block">Nueva consulta</span>
        </button>

        {/* Nav Chat / Panel — solo para staff */}
        {tienePanel && (
          <nav className="flex flex-col gap-1 px-3 mb-4">
            <button
              onClick={() => setVista('chat')}
              className={`flex items-center justify-center md:justify-start gap-2 px-3 py-2 rounded-lg
                          text-sm font-body font-medium transition-colors ${
                vista === 'chat'
                  ? 'bg-[#e8592e]/15 text-[#f2894f]'
                  : 'text-[#8b8b93] hover:text-[#f4f4f5] hover:bg-[#17171b]'
              }`}
            >
              <MessageSquare size={15} className="flex-shrink-0" />
              <span className="hidden md:block">Chat</span>
            </button>
            <button
              onClick={() => setVista('panel')}
              className={`flex items-center justify-center md:justify-start gap-2 px-3 py-2 rounded-lg
                          text-sm font-body font-medium transition-colors ${
                vista === 'panel'
                  ? 'bg-[#e8592e]/15 text-[#f2894f]'
                  : 'text-[#8b8b93] hover:text-[#f4f4f5] hover:bg-[#17171b]'
              }`}
            >
              <LayoutDashboard size={15} className="flex-shrink-0" />
              <span className="hidden md:block">Panel</span>
            </button>
          </nav>
        )}

        <div className="flex-1" />

        {/* Usuario / logout */}
        <div className="px-3 pt-4 border-t border-[#1e1e22]">
          <div className="flex items-center gap-2.5 mb-3">
            <div className="w-8 h-8 rounded-full bg-[#1a1a1e] border border-[#232327] flex items-center justify-center flex-shrink-0">
              <User size={14} className="text-[#8b8b93]" />
            </div>
            <div className="hidden md:block min-w-0">
              <p className="text-xs font-body font-medium text-[#f4f4f5] truncate leading-tight">
                {usuario.nombre}
              </p>
              <span className={`inline-block text-[10px] px-1.5 py-0.5 mt-0.5 rounded-full font-medium ${rolInfo.color}`}>
                {rolInfo.label}
              </span>
            </div>
          </div>
          <button
            onClick={onLogout}
            className="w-full flex items-center justify-center md:justify-start gap-2 text-xs font-body
                       text-[#8b8b93] hover:text-[#f2894f] px-2 py-1.5 rounded-lg hover:bg-[#17171b] transition-colors"
          >
            <LogOut size={13} />
            <span className="hidden md:block">Salir</span>
          </button>
        </div>
      </aside>

      {/* ── Panel de carga ───────────────────────────────────────────────── */}
      {vista === 'panel' && tienePanel ? (
        <div className="flex-1 overflow-hidden">
          <Panel usuario={usuario} darkMode />
        </div>
      ) : (
        /* ── Área de chat ─────────────────────────────────────────────── */
        <div className="flex-1 flex flex-col min-w-0">

          {/* Main scroll */}
          <main className="flex-1 overflow-y-auto chat-scroll px-4">
            {!hayConversacion ? (
              /* Pantalla de bienvenida */
              <div className="h-full flex flex-col items-center justify-center text-center px-4">
                <LogoUTNIA size={56} />
                <h1 className="font-display text-2xl md:text-3xl font-semibold mt-6 mb-2 tracking-tight">
                  Preguntale a UTNIA
                </h1>
                <p className="font-body text-sm text-[#8b8b93] mb-8">
                  ¡Hola, {usuario.nombre.split(' ')[0]}! Podés preguntarme sobre horarios, aulas y materias.
                </p>
                <div className="flex flex-col gap-2.5 w-full max-w-md">
                  {PREGUNTAS_EJEMPLO.map(p => (
                    <button
                      key={p}
                      onClick={() => enviar(p)}
                      className="font-body text-sm text-left text-[#c7c7cf] bg-[#141417]
                                 hover:bg-[#1a1a1e] border border-[#232327] hover:border-[#e8592e]/40
                                 rounded-full px-5 py-3 transition-colors"
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              /* Historial */
              <div className="max-w-2xl mx-auto py-6 space-y-1">
                {mensajes.map(msg => (
                  <MensajeBurbuja key={msg.id} mensaje={msg} logoComponent={<LogoUTNIA size={26} />} />
                ))}

                {/* Indicador escribiendo */}
                {escribiendo && (
                  <div className="msg-in flex justify-start mb-4">
                    <div className="mr-2.5 mt-0.5 flex-shrink-0"><LogoUTNIA size={26} /></div>
                    <div className="bg-[#17171b] border border-[#232327] rounded-2xl rounded-bl-sm px-4 py-3">
                      <div className="flex gap-1 items-center h-4">
                        <span className="w-1.5 h-1.5 bg-[#6b6b73] rounded-full dot-bounce [animation-delay:-0.3s]" />
                        <span className="w-1.5 h-1.5 bg-[#6b6b73] rounded-full dot-bounce [animation-delay:-0.15s]" />
                        <span className="w-1.5 h-1.5 bg-[#6b6b73] rounded-full dot-bounce" />
                      </div>
                    </div>
                  </div>
                )}
                <div ref={bottomRef} />
              </div>
            )}
          </main>

          {/* Input */}
          <footer className="px-4 pb-5 pt-2">
            <div className="max-w-2xl mx-auto flex gap-2.5 items-end bg-[#141417] border border-[#232327]
                            focus-within:border-[#e8592e]/50 rounded-2xl px-3 py-2 transition-colors">
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Escribí tu consulta..."
                rows={1}
                disabled={escribiendo}
                className="flex-1 resize-none bg-transparent font-body text-sm text-[#f4f4f5]
                           placeholder-[#4b4b53] focus:outline-none disabled:text-[#4b4b53]
                           max-h-32 overflow-y-auto py-1.5"
                style={{ minHeight: '24px' }}
                onInput={e => {
                  e.target.style.height = 'auto'
                  e.target.style.height = Math.min(e.target.scrollHeight, 128) + 'px'
                }}
              />
              <button
                onClick={() => enviar()}
                disabled={!input.trim() || escribiendo}
                className="bg-[#e8592e] hover:bg-[#f2703f] disabled:bg-[#232327] disabled:cursor-not-allowed
                           text-white disabled:text-[#4b4b53] p-2 rounded-xl transition-colors flex-shrink-0"
                aria-label="Enviar mensaje"
              >
                <Send size={16} />
              </button>
            </div>
            <p className="text-[11px] font-body text-[#4b4b53] text-center mt-2">
              El asistente responde según la información disponible en el sistema.
            </p>
          </footer>
        </div>
      )}
    </div>
  )
}
