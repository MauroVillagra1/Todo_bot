/**
 * Chat — pantalla principal de Juliette, la asistente de la UTN FRT.
 * Sidebar: Chat, Calendario, Documentos y Sugerir dato (todos), Panel (staff y admin) y el
 * historial de conversaciones del usuario. Arriba del chat, un aviso por cada paro vigente.
 */
import { useState, useRef, useEffect } from 'react'
import {
  Send, LogOut, Sparkles, User, LayoutDashboard, MessageSquare, Lightbulb, CalendarDays, FileText, Trash2,
  AlertTriangle, X,
} from 'lucide-react'
import {
  enviarMensaje as apiEnviarMensaje, borrarConversacion, listarAvisos, listarConversaciones, obtenerConversacion,
} from '../api'
import Calendario from './Calendario'
import Documentos from './Documentos'
import Juliette from './Juliette'
import JulietteEscena, { FRASES } from './JulietteEscena'
import MensajeBurbuja from './MensajeBurbuja'
import Panel from './Panel'
import Perfil from './Perfil'
import Sugerir from './Sugerir'

const ROLES_DISPLAY = {
  ADMIN:   { label: 'Admin',     color: 'bg-[#e8592e]/15 text-[#f2894f]' },
  MOD:     { label: 'Moderador', color: 'bg-sky-500/15 text-sky-400' },
  MIEMBRO: { label: 'Miembro',   color: 'bg-gray-500/15 text-gray-400' },
}

const PREGUNTAS_EJEMPLO = [
  '¿Qué materias tengo los lunes en la 1K01?',
  '¿Cuándo se dicta Análisis Matemático I?',
  '¿Cuándo rindo Sistemas Operativos?',
  '¿Hay clases mañana?',
]

// La UI solo oculta el acceso: los permisos reales se validan en el backend
const TIENE_PANEL = ['MOD', 'ADMIN']

// Logo de siempre: arriba a la izquierda (Juliette acompaña en el chat)
const LOGO_URL = 'https://res.cloudinary.com/dol1ba0ld/image/upload/v1787954474/asd/Preguntale_a_UTNIA_xwocbf.png'

function ahora(fecha = new Date()) {
  return new Date(fecha).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
}

/** Mensaje guardado en el backend → formato de MensajeBurbuja. */
function desdeHistorial(m) {
  return m.rol === 'user'
    ? { id: `h${m.id}`, tipo: 'usuario', texto: m.contenido, timestamp: ahora(m.creado_en) }
    : { id: `h${m.id}`, tipo: 'asistente', texto: m.contenido, timestamp: ahora(m.creado_en), estado: m.estado,
        fuentes: m.fuentes ?? [], fecha: m.fecha_informacion, mensajeId: m.id }
}

/** Paro vigente: aviso arriba del chat (se puede cerrar por esta sesión). */
function AvisoParo({ aviso, onCerrar }) {
  const cerrada = /CERRADA/.test(aviso.contenido)
  return (
    <div className={`flex gap-3 items-start rounded-xl border px-4 py-3 text-sm font-body ${
      cerrada ? 'border-red-500/30 bg-red-500/10 text-red-200' : 'border-amber-500/30 bg-amber-500/10 text-amber-100'}`}>
      <AlertTriangle size={16} className="mt-0.5 flex-shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{aviso.titulo}</p>
        <p className="text-xs opacity-90 mt-0.5 whitespace-pre-line">{aviso.contenido.split('\n').slice(1).join('\n')}</p>
      </div>
      <button onClick={onCerrar} aria-label="Cerrar aviso" className="opacity-70 hover:opacity-100"><X size={14} /></button>
    </div>
  )
}

export default function Chat({ usuario = { nombre: 'Invitado', rol: 'MIEMBRO' }, onLogout = () => {}, onPerfil = () => {} }) {
  const [mensajes, setMensajes]             = useState([])
  const [input, setInput]                   = useState('')
  const [escribiendo, setEscribiendo]       = useState(false)
  const [conversacionId, setConversacionId] = useState(null)
  const [vista, setVista]                   = useState('chat') // 'chat' | 'calendario' | 'documentos' | 'sugerir' | 'panel'
  const [conversaciones, setConversaciones] = useState([])
  const [avisos, setAvisos]                 = useState([])
  const [avisosCerrados, setAvisosCerrados] = useState([])
  const bottomRef                            = useRef(null)
  const inputRef                             = useRef(null)

  const tienePanel = TIENE_PANEL.includes(usuario.rol)
  const rolInfo    = ROLES_DISPLAY[usuario.rol] ?? { label: usuario.rol, color: 'bg-gray-500/15 text-gray-300' }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensajes, escribiendo])

  const cargarConversaciones = () => listarConversaciones().then(setConversaciones).catch(() => {})
  useEffect(() => {
    cargarConversaciones()
    listarAvisos().then(setAvisos).catch(() => {})
  }, [])

  async function abrirConversacion(id) {
    try {
      const historial = await obtenerConversacion(id)
      setMensajes(historial.map(desdeHistorial))
      setConversacionId(id)
      setVista('chat')
    } catch { cargarConversaciones() }
  }

  async function eliminarConversacion(c) {
    if (!confirm(`¿Borrar la conversación «${c.titulo}»?`)) return
    try {
      await borrarConversacion(c.id)
      setConversaciones(prev => prev.filter(x => x.id !== c.id))
      if (c.id === conversacionId) nuevaConsulta()
    } catch { /* ya no existía */ }
  }

  async function enviar(textoForzado) {
    const texto = (textoForzado ?? input).trim()
    if (!texto || escribiendo) return

    // Si está en otra vista, volver al chat
    if (vista !== 'chat') setVista('chat')

    const msgUsuario = { id: Date.now(), tipo: 'usuario', texto, timestamp: ahora() }
    setMensajes(prev => [...prev, msgUsuario])
    setInput('')
    setEscribiendo(true)

    try {
      const data = await apiEnviarMensaje(texto, conversacionId)
      if (data.conversacion_id) setConversacionId(data.conversacion_id)
      cargarConversaciones()
      setMensajes(prev => [
        ...prev,
        {
          id: Date.now() + 1, tipo: 'asistente', texto: data.respuesta, timestamp: ahora(),
          estado: data.estado, fuentes: data.fuentes ?? [], fecha: data.fecha_informacion,
          mensajeId: data.mensaje_id, animar: true,
        },
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

  /** "No me sirvió": el backend busca en otras fuentes y la respuesta nueva se suma al chat. */
  function agregarAlternativa(alt) {
    setMensajes(prev => [
      ...prev,
      {
        id: Date.now(), tipo: 'asistente', texto: alt.respuesta, timestamp: ahora(), alternativa: true,
        estado: alt.estado, fuentes: alt.fuentes ?? [], fecha: alt.fecha_informacion, mensajeId: alt.mensaje_id,
        animar: true,
      },
    ])
  }

  /** Ya se escribió: al volver al chat no se repite la animación. */
  function terminoDeEscribir(id) {
    setMensajes(prev => prev.map(m => (m.id === id ? { ...m, animar: false } : m)))
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
          <img src={LOGO_URL} alt="Juliette" width={34} height={34}
               className="rounded-full flex-shrink-0 object-cover" style={{ width: 34, height: 34 }} />
          <span className="hidden md:block font-display font-semibold text-[15px] tracking-tight text-[#f4f4f5]">
            Juliette
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
          <span className="hidden md:block">Nuevo chat</span>
        </button>

        {/* Nav: Chat y Sugerir para todos; Panel solo para staff */}
        <nav className="flex flex-col gap-1 px-3 mb-4">
          {[
            { id: 'chat', label: 'Chat', Icono: MessageSquare },
            { id: 'calendario', label: 'Calendario', Icono: CalendarDays },
            { id: 'documentos', label: 'Documentos', Icono: FileText },
            { id: 'sugerir', label: 'Sugerir dato', Icono: Lightbulb },
            ...(tienePanel ? [{ id: 'panel', label: 'Panel', Icono: LayoutDashboard }] : []),
          ].map(({ id, label, Icono }) => (
            <button
              key={id}
              onClick={() => setVista(id)}
              title={label}
              className={`flex items-center justify-center md:justify-start gap-2 px-3 py-2 rounded-lg
                          text-sm font-body font-medium transition-colors ${
                vista === id
                  ? 'bg-[#e8592e]/15 text-[#f2894f]'
                  : 'text-[#8b8b93] hover:text-[#f4f4f5] hover:bg-[#17171b]'
              }`}
            >
              <Icono size={15} className="flex-shrink-0" />
              <span className="hidden md:block">{label}</span>
            </button>
          ))}
        </nav>

        <div className="flex-1 md:hidden" />
        {/* Historial de conversaciones (solo con la barra ancha) */}
        <div className="flex-1 min-h-0 overflow-y-auto chat-scroll px-3 hidden md:block">
          {conversaciones.length > 0 && (
            <>
              <p className="text-[10px] uppercase tracking-wide text-[#4b4b53] font-body font-medium px-1 mb-1">Chats</p>
              <ul className="space-y-0.5">
                {conversaciones.map(c => (
                  <li key={c.id} className="group flex items-center">
                    <button onClick={() => abrirConversacion(c.id)} title={c.titulo}
                            className={`flex-1 min-w-0 text-left text-xs font-body px-2 py-1.5 rounded-lg truncate transition-colors ${
                              c.id === conversacionId && vista === 'chat'
                                ? 'bg-[#17171b] text-[#f4f4f5]' : 'text-[#8b8b93] hover:text-[#f4f4f5] hover:bg-[#17171b]'}`}>
                      {c.titulo || 'Conversación'}
                    </button>
                    <button onClick={() => eliminarConversacion(c)} title="Borrar conversación"
                            className="opacity-0 group-hover:opacity-100 text-[#4b4b53] hover:text-red-400 p-1">
                      <Trash2 size={12} />
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>

        {/* Usuario / logout */}
        <div className="px-3 pt-4 border-t border-[#1e1e22]">
          <button onClick={() => setVista('perfil')} title="Mi perfil"
                  className={`w-full flex items-center gap-2.5 mb-2 p-1.5 -mx-1.5 rounded-lg text-left transition-colors ${
                    vista === 'perfil' ? 'bg-[#e8592e]/15' : 'hover:bg-[#17171b]'}`}>
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
              <span className="block text-[10px] text-[#6b6b73] mt-0.5">Mi perfil</span>
            </div>
          </button>
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
      ) : vista === 'perfil' ? (
        <div className="flex-1 overflow-hidden">
          <Perfil usuario={usuario} onActualizado={onPerfil} />
        </div>
      ) : vista === 'documentos' ? (
        <div className="flex-1 overflow-hidden">
          <Documentos esAdmin={usuario.rol === 'ADMIN'} />
        </div>
      ) : vista === 'calendario' ? (
        <div className="flex-1 overflow-y-auto bg-[#0a0a0c] text-[#f4f4f5] font-body p-6 [color-scheme:dark]">
          <div className="max-w-6xl mx-auto flex gap-10 items-start justify-center">
            <div className="flex-1 min-w-0 max-w-3xl space-y-4">
              <h2 className="font-display text-xl font-semibold">Calendario académico</h2>
              <Calendario />
            </div>
            <JulietteEscena escena="agenda" mensajes={FRASES.calendario} size={210}
                            className="hidden lg:flex sticky top-6 flex-shrink-0" />
          </div>
        </div>
      ) : vista === 'sugerir' ? (
        <div className="flex-1 overflow-hidden">
          <Sugerir />
        </div>
      ) : (
        /* ── Área de chat ─────────────────────────────────────────────── */
        <div className="flex-1 flex flex-col min-w-0">

          {/* Paros vigentes */}
          {avisos.filter(a => !avisosCerrados.includes(a.informacion_id)).length > 0 && (
            <div className="px-4 pt-4 space-y-2 max-w-2xl w-full mx-auto">
              {avisos.filter(a => !avisosCerrados.includes(a.informacion_id)).map(a => (
                <AvisoParo key={a.informacion_id} aviso={a}
                           onCerrar={() => setAvisosCerrados(prev => [...prev, a.informacion_id])} />
              ))}
            </div>
          )}

          {/* Main scroll */}
          <main className="flex-1 overflow-y-auto chat-scroll px-4">
            {!hayConversacion ? (
              /* Pantalla de bienvenida */
              <div className="h-full flex flex-col items-center justify-center text-center px-4">
                <Juliette size={130} mirar titulo="Juliette te saluda" />
                <h1 className="font-display text-2xl md:text-3xl font-semibold mt-4 mb-2 tracking-tight">
                  Preguntale a Juliette
                </h1>
                <p className="font-body text-sm text-[#8b8b93] mb-8">
                  ¡Hola, {usuario.nombre.split(' ')[0]}! Podés preguntarme sobre horarios, mesas de examen, el calendario y trámites.
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
                  <MensajeBurbuja key={msg.id} mensaje={msg} onAlternativa={agregarAlternativa}
                                  onAnimado={terminoDeEscribir} />
                ))}

                {/* Mientras busca la respuesta: Juliette pensando */}
                {escribiendo && (
                  <div className="msg-in flex items-end justify-start mb-4">
                    <div className="mr-2 flex-shrink-0"><Juliette estado="think" size={44} /></div>
                    <span className="font-body text-xs text-[#8b8b93] mb-2">Juliette está pensando…</span>
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
