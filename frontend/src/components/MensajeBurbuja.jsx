/**
 * MensajeBurbuja — mensaje individual del historial de chat.
 * Tema oscuro, renderiza Markdown para mensajes del asistente.
 *
 * Props:
 *   mensaje:        { id, texto, tipo: 'usuario'|'asistente'|'error', timestamp }
 *   logoComponent:  ReactNode — avatar del asistente (LogoUTNIA)
 */
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function MensajeBurbuja({ mensaje, logoComponent }) {
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
        </div>

        {/* Timestamp */}
        <span className={`text-[10px] mt-1 px-1 ${esUsuario ? 'text-white/40' : 'text-[#6b6b73]'}`}>
          {mensaje.timestamp}
        </span>
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
