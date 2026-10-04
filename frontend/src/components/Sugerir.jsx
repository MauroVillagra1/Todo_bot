/**
 * Sugerir — cualquier usuario propone un dato para sumar a la base.
 * Un moderador lo acepta (queda disponible en el chat) o lo rechaza con un motivo.
 */
import { useEffect, useState } from 'react'
import { crearSugerencia, misSugerencias } from '../api'
import { boton, campo, errorDe, fechaHora, tarjeta } from './ui'

const VACIA = { titulo: '', contenido: '', url: '' }
const ESTADOS = {
  PENDIENTE: { texto: 'En revisión', color: 'bg-amber-500/15 text-amber-400' },
  ACEPTADA:  { texto: 'Aceptada',    color: 'bg-emerald-500/15 text-emerald-400' },
  RECHAZADA: { texto: 'Rechazada',   color: 'bg-red-500/15 text-red-400' },
}

export default function Sugerir() {
  const [form, setForm] = useState(VACIA)
  const [mias, setMias] = useState([])
  const [enviando, setEnviando] = useState(false)
  const [mensaje, setMensaje] = useState(null)
  const cambiar = c => e => setForm(prev => ({ ...prev, [c]: e.target.value }))

  useEffect(() => { misSugerencias().then(setMias).catch(() => {}) }, [])

  async function enviar(e) {
    e.preventDefault()
    setEnviando(true)
    setMensaje(null)
    try {
      const nueva = await crearSugerencia({ ...form, url: form.url.trim() || null })
      setMias(prev => [nueva, ...prev])
      setForm(VACIA)
      setMensaje({ ok: true, texto: '¡Gracias! Un moderador la va a revisar.' })
    } catch (err) {
      setMensaje({ ok: false, texto: errorDe(err, 'Revisá los datos: título de 3 caracteres y texto de al menos 10.') })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="flex flex-col h-full bg-[#0a0a0c] text-[#f4f4f5] font-body [color-scheme:dark]">
      <div className="bg-[#0d0d10] border-b border-[#1e1e22] px-6 py-4">
        <h2 className="font-display text-base font-semibold">Sugerir un dato</h2>
        <p className="text-xs text-[#8b8b93] mt-0.5">
          ¿Sabés algo que UTNIA no sabe? Un cambio de aula, una fecha, un trámite… Contalo y, si un moderador lo aprueba, el chat lo va a usar.
        </p>
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto space-y-6">
          <form onSubmit={enviar} className={`${tarjeta} space-y-3`}>
            <input required minLength={3} maxLength={300} placeholder="Título (ej. Cambio de aula de Física I en la 1K01)"
                   value={form.titulo} onChange={cambiar('titulo')} className={campo} />
            <textarea required minLength={10} maxLength={5000} rows={5} placeholder="El dato, con todos los detalles que sepas"
                      value={form.contenido} onChange={cambiar('contenido')} className={campo} />
            <input type="url" placeholder="Link de dónde lo sacaste (opcional)" value={form.url}
                   onChange={cambiar('url')} className={campo} />
            <div className="flex items-center gap-3">
              <button type="submit" disabled={enviando} className={boton}>{enviando ? 'Enviando…' : 'Enviar sugerencia'}</button>
              {mensaje && <span className={`text-xs ${mensaje.ok ? 'text-emerald-400' : 'text-red-400'}`}>{mensaje.texto}</span>}
            </div>
          </form>

          {mias.length > 0 && (
            <div className={tarjeta}>
              <h3 className="text-sm font-semibold mb-1">Mis sugerencias</h3>
              <ul className="divide-y divide-[#1e1e22]">
                {mias.map(s => (
                  <li key={s.id} className="py-3 text-sm">
                    <div className="flex items-start justify-between gap-3">
                      <p className="font-medium min-w-0">{s.titulo}</p>
                      <span className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${ESTADOS[s.estado].color}`}>
                        {ESTADOS[s.estado].texto}
                      </span>
                    </div>
                    <p className="text-xs text-[#8b8b93] mt-0.5">Enviada {fechaHora(s.creada_en)}</p>
                    {s.motivo && <p className="text-xs text-red-400 mt-1">Motivo: {s.motivo}</p>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
