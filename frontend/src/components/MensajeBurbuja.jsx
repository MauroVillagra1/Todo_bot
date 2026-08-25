/**
 * MensajeBurbuja — muestra un mensaje individual del historial de chat.
 * Renderiza Markdown para los mensajes del asistente.
 *
 * Props:
 *   mensaje: { texto, tipo: 'usuario' | 'asistente' | 'error', timestamp }
 */
import ReactMarkdown from 'react-markdown'

export default function MensajeBurbuja({ mensaje }) {
  const esUsuario = mensaje.tipo === 'usuario'
  const esError   = mensaje.tipo === 'error'

  return (
    <div className={`flex w-full mb-3 ${esUsuario ? 'justify-end' : 'justify-start'}`}>

      {/* Avatar del asistente */}
      {!esUsuario && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center mr-2 mt-1">
          <span className="text-white text-xs font-bold">AU</span>
        </div>
      )}

      <div className={`max-w-[75%] flex flex-col ${esUsuario ? 'items-end' : 'items-start'}`}>
        <div
          className={`
            px-4 py-3 rounded-2xl text-sm leading-relaxed break-words
            ${esUsuario
              ? 'bg-primary-600 text-white rounded-br-sm'
              : esError
                ? 'bg-red-50 text-red-700 border border-red-200 rounded-bl-sm'
                : 'bg-white text-gray-800 border border-gray-200 shadow-sm rounded-bl-sm'
            }
          `}
        >
          {esUsuario ? (
            // Mensajes del usuario: texto plano
            <span className="whitespace-pre-wrap">{mensaje.texto}</span>
          ) : (
            // Mensajes del asistente y errores: renderizar Markdown
            <ReactMarkdown
              components={{
                // Párrafos con espaciado
                p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                // Listas
                ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>,
                li: ({ children }) => <li>{children}</li>,
                // Negrita
                strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                // Código inline
                code: ({ children }) => (
                  <code className="bg-gray-100 text-gray-800 px-1 py-0.5 rounded text-xs font-mono">
                    {children}
                  </code>
                ),
                // Encabezados
                h1: ({ children }) => <h1 className="font-bold text-base mb-1">{children}</h1>,
                h2: ({ children }) => <h2 className="font-bold text-sm mb-1">{children}</h2>,
                h3: ({ children }) => <h3 className="font-semibold text-sm mb-1">{children}</h3>,
                // Separador horizontal
                hr: () => <hr className="my-2 border-gray-200" />,
              }}
            >
              {mensaje.texto}
            </ReactMarkdown>
          )}
        </div>

        {/* Timestamp */}
        <span className="text-xs text-gray-400 mt-1 px-1">
          {mensaje.timestamp}
        </span>
      </div>

      {/* Avatar del usuario */}
      {esUsuario && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center ml-2 mt-1">
          <span className="text-gray-600 text-xs font-bold">Yo</span>
        </div>
      )}

    </div>
  )
}
