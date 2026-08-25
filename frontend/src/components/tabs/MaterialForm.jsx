/**
 * MaterialForm — carga material de apoyo.
 * Profesores: solo ven sus cursadas asignadas (/cursadas/mias).
 * Admin: ve todas (selector con comisión primero).
 */
import { useState, useEffect } from 'react'
import api, { listarComisiones, listarCursadas, cargarMaterial, listarMateriales, eliminarMaterial } from '../../api'

const TIPOS = [
  { value: 'apunte',       label: '📄 Apunte'      },
  { value: 'video',        label: '🎬 Video'        },
  { value: 'ejercicio',    label: '✏️ Ejercicio'    },
  { value: 'bibliografia', label: '📚 Bibliografía' },
  { value: 'otro',         label: '📎 Otro'         },
]

const ES_PROFESOR = rol => rol === 'profesor' || rol === 'profesor_directivo'

export default function MaterialForm({ usuario }) {
  const esProfesor = ES_PROFESOR(usuario.rol)

  // Para profesores: sus cursadas directamente
  const [misCursadas,  setMisCursadas]  = useState([])
  const [materias,     setMaterias]     = useState({})
  const [comisiones,   setComisiones]   = useState({})

  // Para admin: selector comisión → cursadas
  const [todasComisiones, setTodasComisiones] = useState([])
  const [comisionId,      setComisionId]      = useState('')
  const [cursadasComision, setCursadasComision] = useState([])

  const [cursadaId,   setCursadaId]   = useState('')
  const [tipo,        setTipo]        = useState('apunte')
  const [titulo,      setTitulo]      = useState('')
  const [url,         setUrl]         = useState('')
  const [descripcion, setDescripcion] = useState('')

  const [materiales, setMateriales] = useState([])
  const [cargando,   setCargando]   = useState(false)
  const [resultado,  setResultado]  = useState(null)
  const [eliminando, setEliminando] = useState(null)

  // Cargar datos iniciales
  useEffect(() => {
    const p = [
      api.get('/api/v1/materias?page_size=200').then(r => r.data.items),
      api.get('/api/v1/comisiones').then(r => r.data),
    ]
    if (esProfesor) p.push(api.get('/api/v1/cursadas/mias').then(r => r.data))
    else            p.push(Promise.resolve([]))

    Promise.all(p).then(([materiasList, comisionesList, misCur]) => {
      const mm = {}; materiasList.forEach(m => { mm[m.id] = m })
      const cc = {}; comisionesList.forEach(c => { cc[c.id] = c })
      setMaterias(mm)
      setComisiones(cc)
      if (esProfesor) setMisCursadas(misCur)
      else setTodasComisiones(comisionesList)
    }).catch(console.error)
  }, [esProfesor])

  // Admin: cuando cambia la comisión, cargar cursadas de esa comisión
  useEffect(() => {
    if (esProfesor || !comisionId) { setCursadasComision([]); setCursadaId(''); return }
    listarCursadas(comisionId).then(setCursadasComision).catch(console.error)
    setCursadaId('')
  }, [comisionId, esProfesor])

  // Cargar materiales cuando cambia la cursada
  useEffect(() => {
    if (!cursadaId) { setMateriales([]); return }
    listarMateriales(Number(cursadaId)).then(setMateriales).catch(console.error)
  }, [cursadaId])

  const listaCursadas = esProfesor ? misCursadas : cursadasComision

  async function handleSubmit(e) {
    e.preventDefault()
    if (!cursadaId) return
    setCargando(true); setResultado(null)
    try {
      await cargarMaterial({ cursada_id: Number(cursadaId), tipo, titulo, url: url || null, descripcion: descripcion || null })
      setResultado({ ok: true, msg: '¡Material cargado correctamente!' })
      setTitulo(''); setUrl(''); setDescripcion('')
      const lista = await listarMateriales(Number(cursadaId))
      setMateriales(lista)
    } catch (err) {
      const detail = err.response?.data?.detail
      setResultado({ ok: false, msg: typeof detail === 'string' ? detail : 'Error al cargar el material.' })
    } finally {
      setCargando(false)
    }
  }

  async function handleEliminar(id) {
    if (!confirm('¿Eliminás este material?')) return
    setEliminando(id)
    try {
      await eliminarMaterial(id)
      setMateriales(prev => prev.filter(m => m.id !== id))
    } catch { alert('No se pudo eliminar el material.') }
    finally { setEliminando(null) }
  }

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-900 mb-1">Material de apoyo</h3>
      <p className="text-xs text-gray-500 mb-5">
        {esProfesor
          ? 'Cargá materiales para tus cursadas asignadas.'
          : 'Cargá materiales para cualquier cursada.'}
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">

        {/* Admin: selector comisión */}
        {!esProfesor && (
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Comisión</label>
            <select value={comisionId} onChange={e => setComisionId(e.target.value)} required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-primary-500">
              <option value="">Seleccioná una comisión...</option>
              {todasComisiones.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select>
          </div>
        )}

        {/* Materia / Cursada */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Materia / Cursada</label>
          <select value={cursadaId} onChange={e => setCursadaId(e.target.value)} required
            disabled={!esProfesor && !comisionId}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-primary-500
                       disabled:bg-gray-50 disabled:text-gray-400">
            <option value="">
              {!esProfesor && !comisionId ? 'Primero elegí una comisión' : 'Seleccioná una materia...'}
            </option>
            {listaCursadas.map(c => {
              const mat = materias[c.materia_id]
              const com = comisiones[c.comision_id]
              return (
                <option key={c.id} value={c.id}>
                  {mat ? `${mat.nombre} (${mat.codigo})` : `Cursada #${c.id}`}
                  {com && !esProfesor ? ` — ${com.nombre}` : ''}
                  {esProfesor && com ? ` — Comisión ${com.nombre}` : ''}
                </option>
              )
            })}
          </select>
        </div>

        {/* Tipo */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-2">Tipo de material</label>
          <div className="flex flex-wrap gap-2">
            {TIPOS.map(t => (
              <button key={t.value} type="button" onClick={() => setTipo(t.value)}
                className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                  tipo === t.value
                    ? 'bg-primary-600 border-primary-600 text-white'
                    : 'border-gray-300 text-gray-600 hover:border-primary-400'
                }`}>
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Título */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Título <span className="text-red-500">*</span></label>
          <input type="text" value={titulo} onChange={e => setTitulo(e.target.value)}
            required minLength={2} placeholder="Ej: Resumen Unidad 3 — Recursividad"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-primary-500" />
        </div>

        {/* URL */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            URL / Link <span className="text-gray-400 font-normal">(opcional)</span>
          </label>
          <input type="url" value={url} onChange={e => setUrl(e.target.value)}
            placeholder="https://drive.google.com/..."
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-primary-500" />
        </div>

        {/* Descripción */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Descripción <span className="text-gray-400 font-normal">(opcional)</span>
          </label>
          <textarea value={descripcion} onChange={e => setDescripcion(e.target.value)}
            rows={2} placeholder="Breve descripción del contenido..."
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none
                       focus:outline-none focus:ring-2 focus:ring-primary-500" />
        </div>

        {resultado && (
          <div className={`rounded-lg px-4 py-3 text-sm ${
            resultado.ok ? 'bg-green-50 border border-green-200 text-green-700'
                         : 'bg-red-50 border border-red-200 text-red-700'
          }`}>
            {resultado.ok ? '✅ ' : '❌ '}{resultado.msg}
          </div>
        )}

        <button type="submit" disabled={cargando || !cursadaId || !titulo}
          className="w-full bg-primary-600 hover:bg-primary-700 disabled:bg-gray-200
                     disabled:text-gray-400 disabled:cursor-not-allowed text-white
                     font-medium py-2.5 rounded-lg text-sm transition-colors">
          {cargando ? 'Guardando...' : 'Cargar material'}
        </button>
      </form>

      {/* Lista de materiales */}
      {cursadaId && materiales.length > 0 && (
        <div className="mt-6">
          <h4 className="text-xs font-semibold text-gray-700 mb-3 uppercase tracking-wide">
            Materiales cargados ({materiales.length})
          </h4>
          <ul className="space-y-2">
            {materiales.map(m => (
              <li key={m.id} className="bg-white border border-gray-200 rounded-lg px-4 py-3
                                        flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{m.titulo}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {TIPOS.find(t => t.value === m.tipo)?.label ?? m.tipo}
                    {m.descripcion && ` — ${m.descripcion}`}
                  </p>
                  {m.url && (
                    <a href={m.url} target="_blank" rel="noopener noreferrer"
                      className="text-xs text-primary-600 hover:underline break-all">{m.url}</a>
                  )}
                </div>
                <button onClick={() => handleEliminar(m.id)} disabled={eliminando === m.id}
                  className="text-red-400 hover:text-red-600 text-xs flex-shrink-0
                             disabled:opacity-40 transition-colors" title="Eliminar">
                  {eliminando === m.id ? '...' : '🗑️'}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {cursadaId && materiales.length === 0 && (
        <p className="mt-4 text-xs text-gray-400 text-center">Sin materiales cargados todavía.</p>
      )}
    </div>
  )
}
