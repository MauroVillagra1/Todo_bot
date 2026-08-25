/**
 * ResumenAdmin — vista solo para administradores.
 * Permite buscar cursadas por comisión y ver las excepciones activas hoy.
 */
import { useState, useEffect } from 'react'
import {
  listarComisiones,
  listarMaterias,
  listarCursadas,
  listarExcepciones,
  listarEventos,
} from '../../api'

const hoy = () => new Date().toISOString().split('T')[0]

export default function ResumenAdmin() {
  const [comisiones,  setComisiones]  = useState([])
  const [materias,    setMaterias]    = useState({})
  const [comisionId,  setComisionId]  = useState('')
  const [cursadas,    setCursadas]    = useState([])
  const [excepciones, setExcepciones] = useState({})  // cursada_id → [excepciones hoy]
  const [eventos,     setEventos]     = useState([])
  const [cargando,    setCargando]    = useState(false)

  useEffect(() => {
    listarComisiones().then(setComisiones).catch(console.error)
    listarMaterias().then(lista => {
      const mapa = {}
      lista.forEach(m => { mapa[m.id] = `${m.nombre} (${m.codigo})` })
      setMaterias(mapa)
    }).catch(console.error)

    // Eventos de hoy en adelante
    listarEventos(hoy()).then(setEventos).catch(console.error)
  }, [])

  async function handleBuscar() {
    if (!comisionId) return
    setCargando(true)
    try {
      const lista = await listarCursadas(comisionId)
      setCursadas(lista)

      // Para cada cursada, traer excepciones vigentes hoy
      const exMap = {}
      await Promise.all(
        lista.map(async c => {
          const excs = await listarExcepciones(c.id)  // trae desde hoy en adelante
          if (excs.length > 0) exMap[c.id] = excs
        })
      )
      setExcepciones(exMap)
    } catch (err) {
      console.error(err)
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="space-y-8">

      {/* ── Sección: buscar por comisión ─────────────────────────────── */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-1">Buscar por comisión</h3>
        <p className="text-xs text-gray-500 mb-4">
          Ver todas las cursadas de una comisión y las excepciones activas para hoy.
        </p>

        <div className="flex gap-2">
          <select
            value={comisionId}
            onChange={e => setComisionId(e.target.value)}
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">Seleccioná una comisión...</option>
            {comisiones.map(c => (
              <option key={c.id} value={c.id}>{c.nombre}</option>
            ))}
          </select>
          <button
            onClick={handleBuscar}
            disabled={!comisionId || cargando}
            className="bg-primary-600 hover:bg-primary-700 disabled:bg-gray-200
                       disabled:text-gray-400 text-white px-4 py-2 rounded-lg text-sm
                       font-medium transition-colors"
          >
            {cargando ? '...' : 'Buscar'}
          </button>
        </div>

        {/* Resultados de cursadas */}
        {cursadas.length > 0 && (
          <div className="mt-4 space-y-2">
            {cursadas.map(c => {
              const excsHoy = excepciones[c.id] || []
              return (
                <div
                  key={c.id}
                  className={`bg-white border rounded-lg px-4 py-3 ${
                    excsHoy.length > 0 ? 'border-amber-300 bg-amber-50' : 'border-gray-200'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {materias[c.materia_id] || `Cursada #${c.id}`}
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        Aula: {c.aula || 'sin asignar'} · {c.horario || 'horario sin confirmar'}
                      </p>
                    </div>
                    {excsHoy.length > 0 && (
                      <span className="text-xs bg-amber-100 text-amber-700 border border-amber-200
                                       px-2 py-0.5 rounded-full font-medium flex-shrink-0">
                        ⚠️ Excepción activa
                      </span>
                    )}
                  </div>

                  {/* Detalle de excepciones activas hoy */}
                  {excsHoy.map(ex => (
                    <div key={ex.id} className="mt-2 text-xs text-amber-800 bg-amber-100
                                                 rounded px-3 py-2 border border-amber-200">
                      <span className="font-medium capitalize">{ex.tipo}</span>
                      {ex.motivo && ` — ${ex.motivo}`}
                      {ex.aula_nueva && ` · Nueva aula: ${ex.aula_nueva}`}
                      {ex.horario_nuevo && ` · Nuevo horario: ${ex.horario_nuevo}`}
                      <span className="text-amber-600 ml-1">
                        ({ex.fecha_inicio} → {ex.fecha_fin})
                      </span>
                    </div>
                  ))}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* ── Sección: próximos eventos ─────────────────────────────────── */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-1">Eventos próximos</h3>
        <p className="text-xs text-gray-500 mb-4">
          Eventos de calendario cargados en el sistema desde hoy en adelante.
        </p>

        {eventos.length === 0 ? (
          <p className="text-xs text-gray-400">No hay eventos registrados próximamente.</p>
        ) : (
          <ul className="space-y-2">
            {eventos.slice(0, 10).map(ev => (
              <li
                key={ev.id}
                className="bg-white border border-gray-200 rounded-lg px-4 py-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{ev.titulo}</p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {ev.fecha_inicio === ev.fecha_fin
                        ? ev.fecha_inicio
                        : `${ev.fecha_inicio} → ${ev.fecha_fin}`}
                      {ev.hora_inicio && ` · ${ev.hora_inicio}`}
                      {ev.origen && ` · ${ev.origen}`}
                    </p>
                    {ev.motivo && (
                      <p className="text-xs text-gray-500 mt-1">{ev.motivo}</p>
                    )}
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0 ${
                    ev.alcance === 'general'
                      ? 'bg-blue-100 text-blue-700'
                      : ev.alcance === 'comision'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-purple-100 text-purple-700'
                  }`}>
                    {ev.alcance === 'general' ? '🌐 General'
                      : ev.alcance === 'comision' ? '👥 Comisión'
                      : '📚 Materia'}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

    </div>
  )
}
