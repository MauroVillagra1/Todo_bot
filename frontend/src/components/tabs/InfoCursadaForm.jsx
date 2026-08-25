/**
 * InfoCursadaForm — el profesor carga/edita la información de su cursada:
 * condiciones de aprobación, cantidad de parciales, TFI, modalidad, etc.
 * Al seleccionar una cursada, carga la info existente (si la hay).
 */
import { useState, useEffect } from 'react'
import api from '../../api'

export default function InfoCursadaForm({ usuario }) {
  const [misCursadas, setMisCursadas] = useState([])
  const [materias,    setMaterias]    = useState({})
  const [comisiones,  setComisiones]  = useState({})

  const [cursadaId,              setCursadaId]              = useState('')
  const [condicionesAprobacion,  setCondicionesAprobacion]  = useState('')
  const [cantidadParciales,      setCantidadParciales]      = useState('')
  const [tieneTfi,               setTieneTfi]               = useState(false)
  const [descripcionTfi,         setDescripcionTfi]         = useState('')
  const [modalidadCursado,       setModalidadCursado]       = useState('')
  const [infoAdicional,          setInfoAdicional]          = useState('')

  const [cargando,      setCargando]      = useState(false)
  const [cargandoInfo,  setCargandoInfo]  = useState(false)
  const [resultado,     setResultado]     = useState(null)

  // Cargar mis cursadas + mapas
  useEffect(() => {
    Promise.all([
      api.get('/api/v1/cursadas/mias').then(r => r.data),
      api.get('/api/v1/materias?page_size=200').then(r => r.data.items),
      api.get('/api/v1/comisiones').then(r => r.data),
    ]).then(([cursadas, materiasList, comisionesList]) => {
      setMisCursadas(cursadas)
      const mm = {}; materiasList.forEach(m => { mm[m.id] = m })
      const cc = {}; comisionesList.forEach(c => { cc[c.id] = c })
      setMaterias(mm); setComisiones(cc)
    }).catch(console.error)
  }, [])

  // Cuando cambia la cursada, cargar info existente
  useEffect(() => {
    if (!cursadaId) {
      setCondicionesAprobacion(''); setCantidadParciales('')
      setTieneTfi(false); setDescripcionTfi('')
      setModalidadCursado(''); setInfoAdicional('')
      return
    }
    setCargandoInfo(true)
    api.get(`/api/v1/info-cursada/${cursadaId}`)
      .then(r => {
        const d = r.data
        if (d) {
          setCondicionesAprobacion(d.condiciones_aprobacion ?? '')
          setCantidadParciales(d.cantidad_parciales ?? '')
          setTieneTfi(d.tiene_tfi ?? false)
          setDescripcionTfi(d.descripcion_tfi ?? '')
          setModalidadCursado(d.modalidad_cursado ?? '')
          setInfoAdicional(d.info_adicional ?? '')
        } else {
          setCondicionesAprobacion(''); setCantidadParciales('')
          setTieneTfi(false); setDescripcionTfi('')
          setModalidadCursado(''); setInfoAdicional('')
        }
      })
      .catch(console.error)
      .finally(() => setCargandoInfo(false))
  }, [cursadaId])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!cursadaId) return
    setCargando(true); setResultado(null)
    try {
      await api.put(`/api/v1/info-cursada/${cursadaId}`, {
        cursada_id:             Number(cursadaId),
        condiciones_aprobacion: condicionesAprobacion || null,
        cantidad_parciales:     cantidadParciales !== '' ? Number(cantidadParciales) : null,
        tiene_tfi:              tieneTfi,
        descripcion_tfi:        descripcionTfi || null,
        modalidad_cursado:      modalidadCursado || null,
        info_adicional:         infoAdicional || null,
      })
      setResultado({ ok: true, msg: '¡Información guardada correctamente!' })
    } catch (err) {
      const detail = err.response?.data?.detail
      setResultado({ ok: false, msg: typeof detail === 'string' ? detail : 'Error al guardar.' })
    } finally {
      setCargando(false)
    }
  }

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-900 mb-1">Información del cursado</h3>
      <p className="text-xs text-gray-500 mb-5">
        Cargá las condiciones, modalidad y datos del cursado para que los alumnos puedan consultarlo.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">

        {/* Mis cursadas */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Materia / Comisión <span className="text-red-500">*</span>
          </label>
          <select value={cursadaId} onChange={e => setCursadaId(e.target.value)} required
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-primary-500">
            <option value="">Seleccioná una materia...</option>
            {misCursadas.map(c => {
              const mat = materias[c.materia_id]
              const com = comisiones[c.comision_id]
              return (
                <option key={c.id} value={c.id}>
                  {mat ? `${mat.nombre} (${mat.codigo})` : `Cursada #${c.id}`}
                  {com ? ` — Comisión ${com.nombre}` : ''}
                </option>
              )
            })}
          </select>
        </div>

        {cargandoInfo && (
          <p className="text-xs text-gray-400 text-center py-2">Cargando información existente...</p>
        )}

        {cursadaId && !cargandoInfo && (
          <>
            {/* Modalidad */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Modalidad de cursado <span className="text-gray-400 font-normal">(opcional)</span>
              </label>
              <input type="text" value={modalidadCursado}
                onChange={e => setModalidadCursado(e.target.value)}
                placeholder="Ej: Presencial obligatorio, puede rendir libre, etc."
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                           focus:outline-none focus:ring-2 focus:ring-primary-500" />
            </div>

            {/* Condiciones de aprobación */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Condiciones de aprobación <span className="text-gray-400 font-normal">(opcional)</span>
              </label>
              <textarea value={condicionesAprobacion}
                onChange={e => setCondicionesAprobacion(e.target.value)} rows={3}
                placeholder="Ej: 60% de asistencia, 4 en cada parcial, promedio mínimo 6 para promocionar..."
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none
                           focus:outline-none focus:ring-2 focus:ring-primary-500" />
            </div>

            {/* Cantidad de parciales */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Cantidad de parciales <span className="text-gray-400 font-normal">(opcional)</span>
              </label>
              <input type="number" min="0" max="10" value={cantidadParciales}
                onChange={e => setCantidadParciales(e.target.value)}
                placeholder="Ej: 2"
                className="w-32 border border-gray-300 rounded-lg px-3 py-2 text-sm
                           focus:outline-none focus:ring-2 focus:ring-primary-500" />
            </div>

            {/* TFI */}
            <div className="space-y-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={tieneTfi}
                  onChange={e => setTieneTfi(e.target.checked)}
                  className="w-4 h-4 text-primary-600 rounded" />
                <span className="text-sm text-gray-700 font-medium">Tiene TFI (Trabajo Final Integrador)</span>
              </label>
              {tieneTfi && (
                <textarea value={descripcionTfi}
                  onChange={e => setDescripcionTfi(e.target.value)} rows={2}
                  placeholder="Describí brevemente el TFI: formato, grupal/individual, fecha tentativa..."
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none
                             focus:outline-none focus:ring-2 focus:ring-primary-500" />
              )}
            </div>

            {/* Info adicional libre */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Información adicional <span className="text-gray-400 font-normal">(libre — opcional)</span>
              </label>
              <textarea value={infoAdicional}
                onChange={e => setInfoAdicional(e.target.value)} rows={4}
                placeholder="Cualquier información relevante: bibliografía, fechas tentativas de parciales, link del aula virtual, grupos de WhatsApp, etc."
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

            <button type="submit" disabled={cargando}
              className="w-full bg-primary-600 hover:bg-primary-700 disabled:bg-gray-200
                         disabled:text-gray-400 disabled:cursor-not-allowed text-white
                         font-medium py-2.5 rounded-lg text-sm transition-colors">
              {cargando ? 'Guardando...' : 'Guardar información'}
            </button>
          </>
        )}

      </form>
    </div>
  )
}
