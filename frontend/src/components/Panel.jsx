/**
 * Panel — panel de MOD y ADMIN.
 * Por ahora: carga manual de posteos de Instagram/WhatsApp y estado de las fuentes.
 * Métricas y gestión de usuarios llegan en la etapa 8.
 * Los permisos reales se validan en el backend; acá solo se muestra la UI.
 */
import { useEffect, useState } from 'react'
import { cargarPublicacionManual, listarFuentes } from '../api'

const hoy = () => new Date().toISOString().split('T')[0]
const VACIO = { url: '', titulo: '', contenido: '', fecha_publicacion: hoy() }

const RESULTADOS = {
  nuevo:       'Publicación cargada',
  actualizado: 'Se guardó como versión nueva de la publicación anterior',
  duplicado:   'Esa publicación ya estaba cargada con el mismo texto',
}

function fechaHora(iso) {
  return iso ? new Date(iso).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' }) : 'nunca'
}

function CargaManual({ fuentes, onCargada }) {
  const manuales = fuentes.filter(f => f.carga_manual)
  const [fuenteId, setFuenteId] = useState('')
  const [form, setForm] = useState(VACIO)
  const [enviando, setEnviando] = useState(false)
  const [mensaje, setMensaje] = useState(null)

  const cambiar = campo => e => setForm(prev => ({ ...prev, [campo]: e.target.value }))

  async function enviar(e) {
    e.preventDefault()
    setEnviando(true)
    setMensaje(null)
    try {
      const r = await cargarPublicacionManual(fuenteId, form)
      setMensaje({ ok: true, texto: `${RESULTADOS[r.resultado]} · ${r.tipo ?? ''} · ${r.estado ?? ''}` })
      if (r.resultado !== 'duplicado') setForm(VACIO)
      onCargada()
    } catch (err) {
      const detalle = err.response?.data?.detail
      setMensaje({ ok: false, texto: typeof detalle === 'string' ? detalle : 'Revisá los datos: link válido, título y texto de al menos 10 caracteres.' })
    } finally {
      setEnviando(false)
    }
  }

  const campo = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500'

  return (
    <form onSubmit={enviar} className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-gray-900">Cargar publicación de Instagram o WhatsApp</h3>
        <p className="text-xs text-gray-500 mt-0.5">
          Copiá el texto del posteo y su link. Queda con el estado que corresponde a la confiabilidad de la fuente.
        </p>
      </div>

      <select required value={fuenteId} onChange={e => setFuenteId(e.target.value)} className={campo}>
        <option value="">Elegí la fuente…</option>
        {manuales.map(f => (
          <option key={f.id} value={f.id}>{f.nombre} ({f.confiabilidad_base}%)</option>
        ))}
      </select>
      <input required type="url" placeholder="Link al posteo" value={form.url} onChange={cambiar('url')} className={campo} />
      <input required minLength={3} placeholder="Título" value={form.titulo} onChange={cambiar('titulo')} className={campo} />
      <textarea required minLength={10} rows={6} placeholder="Texto del posteo" value={form.contenido}
                onChange={cambiar('contenido')} className={campo} />
      <label className="block text-xs text-gray-600">
        Fecha de publicación
        <input required type="date" value={form.fecha_publicacion} onChange={cambiar('fecha_publicacion')}
               className={`${campo} mt-1`} />
      </label>

      <div className="flex items-center gap-3">
        <button type="submit" disabled={enviando}
                className="bg-primary-600 hover:bg-primary-700 disabled:bg-gray-300 text-white px-4 py-2 rounded-lg text-sm font-medium">
          {enviando ? 'Cargando…' : 'Cargar'}
        </button>
        {mensaje && (
          <span className={`text-xs ${mensaje.ok ? 'text-emerald-700' : 'text-red-600'}`}>{mensaje.texto}</span>
        )}
      </div>
    </form>
  )
}

function ListaFuentes({ fuentes }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-3">Fuentes</h3>
      <ul className="divide-y divide-gray-100">
        {fuentes.map(f => (
          <li key={f.id} className="py-2 flex items-center justify-between gap-3 text-sm">
            <div className="min-w-0">
              <a href={f.url} target="_blank" rel="noopener noreferrer" className="font-medium text-gray-900 hover:underline">
                {f.nombre}
              </a>
              <p className="text-xs text-gray-500">
                {f.carga_manual ? 'Carga manual' : `Automática · última revisión: ${fechaHora(f.ultima_revision)}`}
              </p>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0 text-xs">
              <span className="text-gray-500">{f.confiabilidad_base}%</span>
              <span className={`px-2 py-0.5 rounded-full ${f.activa ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
                {f.activa ? 'Activa' : 'Inactiva'}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function Panel() {
  const [fuentes, setFuentes] = useState([])
  const [error, setError] = useState(null)

  function cargar() {
    listarFuentes().then(setFuentes).catch(() => setError('No se pudieron cargar las fuentes.'))
  }
  useEffect(cargar, [])

  return (
    <div className="flex flex-col h-full bg-gray-50">
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <h2 className="text-base font-semibold text-gray-900">Panel de administración</h2>
        <p className="text-xs text-gray-500 mt-0.5">Fuentes y carga manual. Métricas y usuarios: próximamente.</p>
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">
          {error && <p className="text-sm text-red-600">{error}</p>}
          <CargaManual fuentes={fuentes} onCargada={cargar} />
          <ListaFuentes fuentes={fuentes} />
        </div>
      </div>
    </div>
  )
}
