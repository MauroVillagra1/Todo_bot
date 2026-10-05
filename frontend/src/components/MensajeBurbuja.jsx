/**
 * MensajeBurbuja — mensaje individual del historial de chat.
 * Tema oscuro, renderiza Markdown para mensajes del asistente.
 *
 * Props:
 *   mensaje:        { id, texto, tipo: 'usuario'|'asistente'|'error', timestamp,
 *                     estado?, fuentes?: [{numero, titulo, url, fuente, fecha}], fecha? }
 *   logoComponent:  ReactNode — avatar del asistente (LogoUTNIA)
 *   onAlternativa:  (respuesta) => void — "no me sirvió" devolvió otra respuesta
 */
import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ThumbsDown, ThumbsUp } from 'lucide-react'
import { votarRespuesta } from '../api'

// Estado de confianza de la respuesta (RAG-03)
const ESTADOS = {
  CONFIRMADA:     { label: 'Confirmada',     color: 'bg-emerald-500/15 text-emerald-400' },
  PROBABLE:       { label: 'Probable',       color: 'bg-sky-500/15 text-sky-400' },
  NO_CONFIRMADA:  { label: 'No confirmada',  color: 'bg-amber-500/15 text-amber-400' },
  DESACTUALIZADA: { label: 'Desactualizada', color: 'bg-red-500/15 text-red-400' },
  CONTRADICTORIA: { label: 'Contradictoria', color: 'bg-red-500/15 text-red-400' },
}

function fechaCorta(iso) {
  if (!iso) return null
  const [a, m, d] = iso.split('-')
  return `${d}/${m}/${a}`
}

function DetalleRespuesta({ mensaje }) {
  const estado = ESTADOS[mensaje.estado]
  const fuentes = mensaje.fuentes ?? []
  if (!estado && fuentes.length === 0) return null

  return (
    <div className="mt-2 pt-2 border-t border-[#232327] space-y-1.5">
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        {estado && (
          <span className={`px-1.5 py-0.5 rounded-full font-medium ${estado.color}`}>{estado.label}</span>
        )}
        {mensaje.fecha && <span className="text-[#8b8b93]">Información del {fechaCorta(mensaje.fecha)}</span>}
      </div>
      {fuentes.length > 0 && (
        <ol className="text-[11px] text-[#8b8b93] space-y-0.5">
          {fuentes.map(f => (
            <li key={f.numero}>
              [{f.numero}]{' '}
              <a href={f.url} target="_blank" rel="noopener noreferrer"
                 className="text-[#f2894f] underline underline-offset-2 hover:text-[#e8592e]">
                {f.titulo}
              </a>
              {' — '}{f.fuente}{f.fecha && `, ${fechaCorta(f.fecha)}`}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

/**
 * 👍 / 👎 de una respuesta. 👎 pregunta el motivo:
 *   "No me sirvió"  → el chat busca en otras fuentes (onAlternativa recibe la respuesta nueva)
 *   "Dato incorrecto" → queda para que un moderador lo revise
 */
function Votacion({ mensajeId, onAlternativa }) {
  const [voto, setVoto] = useState(null)       // 1 | -1
  const [eligiendo, setEligiendo] = useState(false)
  const [reportando, setReportando] = useState(false)
  const [comentario, setComentario] = useState('')
  const [ocupado, setOcupado] = useState(false)
  const [aviso, setAviso] = useState(null)

  async function enviar(valor, motivo = null, texto = null) {
    setOcupado(true)
    setAviso(null)
    try {
      const r = await votarRespuesta(mensajeId, valor, motivo, texto)
      setVoto(valor)
      setEligiendo(false)
      setReportando(false)
      if (motivo === 'INCORRECTO') setAviso('Gracias: un moderador lo va a revisar.')
      else if (valor > 0) setAviso('¡Gracias!')
      if (r.alternativa) onAlternativa?.(r.alternativa)
    } catch (err) {
      setAviso(err.response?.status === 429 ? 'Esperá un minuto e intentá de nuevo.' : 'No se pudo guardar el voto.')
    } finally {
      setOcupado(false)
    }
  }

  const boton = activo => `p-1 rounded-md transition-colors disabled:opacity-40 ${
    activo ? 'text-[#f2894f] bg-[#e8592e]/15' : 'text-[#6b6b73] hover:text-[#f4f4f5] hover:bg-[#232327]'}`

  return (
    <div className="mt-1 px-1 text-[11px] text-[#8b8b93]">
      <div className="flex items-center gap-1">
        <button title="Me sirvió" disabled={ocupado} onClick={() => enviar(1)} className={boton(voto === 1)}>
          <ThumbsUp size={13} />
        </button>
        <button title="No me sirvió" disabled={ocupado} onClick={() => setEligiendo(v => !v)} className={boton(voto === -1)}>
          <ThumbsDown size={13} />
        </button>
        {ocupado && <span>Buscando…</span>}
        {aviso && !ocupado && <span>{aviso}</span>}
      </div>
      {eligiendo && !reportando && (
        <div className="flex flex-wrap gap-1.5 mt-1">
          <button disabled={ocupado} onClick={() => enviar(-1, 'NO_SIRVE')}
                  className="px-2 py-1 rounded-lg border border-[#232327] hover:border-[#e8592e]/40 hover:text-[#f2894f]">
            No me sirvió: buscar en otras fuentes
          </button>
          <button disabled={ocupado} onClick={() => setReportando(true)}
                  className="px-2 py-1 rounded-lg border border-[#232327] hover:border-red-500/40 hover:text-red-400">
            Tiene un dato incorrecto
          </button>
        </div>
      )}
      {reportando && (
        <div className="flex flex-wrap items-center gap-1.5 mt-1">
          <input autoFocus maxLength={500} value={comentario} onChange={e => setComentario(e.target.value)}
                 placeholder="¿Qué está mal? (opcional)"
                 className="flex-1 min-w-[180px] bg-[#141417] border border-[#232327] rounded-lg px-2 py-1 text-[11px] text-[#f4f4f5] focus:outline-none focus:border-[#e8592e]/50" />
          <button disabled={ocupado} onClick={() => enviar(-1, 'INCORRECTO', comentario)}
                  className="px-2 py-1 rounded-lg bg-red-500/15 text-red-400 hover:bg-red-500/25">Reportar</button>
          <button onClick={() => setReportando(false)} className="px-1 hover:text-[#f4f4f5]">Cancelar</button>
        </div>
      )}
    </div>
  )
}

export default function MensajeBurbuja({ mensaje, logoComponent, onAlternativa }) {
  const esUsuario  = mensaje.tipo === 'usuario'
  const esError    = mensaje.tipo === 'error'
  const esAsistente = mensaje.tipo === 'asistente'

  return (
    <div className={`msg-in flex w-full mb-4 ${esUsuario ? 'justify-end' : 'justify-start'}`}>

      {/* Avatar asistente */}
      {!esUsuario && (
        <div className="mr-2.5 mt-0.5 flex-shrink-0">
          {logoComponent}
        </div>
      )}

      <div className={`flex flex-col max-w-[80%] ${esUsuario ? 'items-end' : 'items-start'}`}>
        <div
          className={`
            font-body text-sm leading-relaxed break-words px-4 py-2.5 rounded-2xl
            ${esUsuario
              ? 'bg-[#e8592e] text-white rounded-br-sm'
              : esError
                ? 'bg-red-500/10 text-red-300 border border-red-500/20 rounded-bl-sm'
                : 'bg-[#17171b] text-[#e4e4e7] border border-[#232327] rounded-bl-sm'
            }
          `}
        >
          {esUsuario ? (
            <span className="whitespace-pre-wrap">{mensaje.texto}</span>
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p:      ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                ul:     ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
                ol:     ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>,
                li:     ({ children }) => <li>{children}</li>,
                strong: ({ children }) => <strong className="font-semibold text-[#f4f4f5]">{children}</strong>,
                em:     ({ children }) => <em className="italic text-[#c7c7cf]">{children}</em>,
                code:   ({ children }) => (
                  <code className="bg-[#0d0d10] text-[#f2894f] px-1.5 py-0.5 rounded text-xs font-mono border border-[#232327]">
                    {children}
                  </code>
                ),
                pre:    ({ children }) => (
                  <pre className="bg-[#0d0d10] border border-[#232327] rounded-lg p-3 overflow-x-auto text-xs font-mono mb-2">
                    {children}
                  </pre>
                ),
                h1: ({ children }) => <h1 className="font-display font-bold text-base mb-1 text-[#f4f4f5]">{children}</h1>,
                h2: ({ children }) => <h2 className="font-display font-bold text-sm mb-1 text-[#f4f4f5]">{children}</h2>,
                h3: ({ children }) => <h3 className="font-display font-semibold text-sm mb-1 text-[#f4f4f5]">{children}</h3>,
                hr:  () => <hr className="my-2 border-[#232327]" />,
                a:  ({ href, children }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer"
                     className="text-[#f2894f] underline underline-offset-2 hover:text-[#e8592e]">
                    {children}
                  </a>
                ),
              }}
            >
              {mensaje.texto}
            </ReactMarkdown>
          )}
          {esAsistente && <DetalleRespuesta mensaje={mensaje} />}
        </div>

        {/* Timestamp */}
        <span className={`text-[10px] mt-1 px-1 ${esUsuario ? 'text-white/40' : 'text-[#6b6b73]'}`}>
          {mensaje.alternativa && 'Busqué en otras fuentes · '}{mensaje.timestamp}
        </span>
        {esAsistente && mensaje.mensajeId && (
          <Votacion mensajeId={mensaje.mensajeId} onAlternativa={onAlternativa} />
        )}
      </div>

      {/* Avatar usuario */}
      {esUsuario && (
        <div className="ml-2.5 mt-0.5 flex-shrink-0 w-[26px] h-[26px] rounded-full bg-[#1a1a1e]
                        border border-[#232327] flex items-center justify-center">
          <span className="text-[#8b8b93] text-[10px] font-bold">Yo</span>
        </div>
      )}

    </div>
  )
}
