/**
 * SuspensionForm — el profesor carga una suspensión o reubicación de clase.
 *
 * - Solo muestra las cursadas asignadas al profesor logueado (/cursadas/mias).
 * - Muestra los días habituales de la cursada seleccionada.
 * - Al elegir una fecha que NO coincide con esos días, muestra una advertencia
 *   pero permite continuar.
 */
import { useState, useEffect } from 'react'
import api from '../../api'

const hoy = () => new Date().toISOString().split('T')[0]

const DIAS_IDX = { 0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo' }
const DIAS_NORM = {
  lunes: 0, martes: 1, 'miércoles': 2, miercoles: 2,
  jueves: 3, viernes: 4, 'sábado': 5, sabado: 5, domingo: 6,
}

function diasEnHorario(horario) {
  if (!horario) return []
  const h = horario.toLowerCase()
  return [...new Set(
    Object.entries(DIAS_NORM)
      .filter(([d]) => h.includes(d))
      .map(([, idx]) => idx)
  )].sort()
}

function advertenciaDia(fechaStr, diasCursada) {
  if (!fechaStr || diasCursada.length === 0) return null
  const fecha = new Date(fechaStr + 'T12:00:00') // evitar offset TZ
  const diaSemana = fecha.getDay() === 0 ? 6 : fecha.getDay() - 1  // 0=lunes
  if (!diasCursada.includes(diaSemana)) {
    const nombreDia = DIAS_IDX[diaSemana]
    const diasHabituales = diasCursada.map(d => DIAS_IDX[d]).join(', ')
    return `La fecha elegida es ${nombreDia}, pero esta cursada se dicta los ${diasHabituales}. Podés continuar igual.`
  }
  return null
}

export default function SuspensionForm({ usuario }) {
  const [misCursadas, setMisCursadas] = useState([])
  const [materias,    setMaterias]    = useState({})
  const [comisiones,  setComisiones]  = useState({})

  const [cursadaId,    setCursadaId]    = useState('')
  const [tipo,         setTipo]         = useState('suspension')
  const [fecha,        setFecha]        = useState(hoy())
  const [motivo,       setMotivo]       = useState('')
  const [aulaNueva,    setAulaNueva]    = useState('')
  const [horarioNuevo, setHorarioNuevo] = useState('')

  const [cargando,    setCargando]    = useState(false)
  const [resultado,   setResultado]   = useState(null)
  const [advertencia, setAdvertencia] = useState(null)

  // Cargar mis cursadas + mapas de materia/comisión
  useEffect(() => {
    Promise.all([
      api.get('/api/v1/cursadas/mias').then(r => r.data),
      api.get('/api/v1/materias?page_size=200').then(r => r.data.items),
      api.get('/api/v1/comisiones').then(r => r.data),
    ]).then(([cursadas, materiasList, comisionesList]) => {
      setMisCursadas(cursadas)
      const mm = {}; materiasList.forEach(m => { mm[m.id] = m })
      setMaterias(mm)
      const cc = {}; comisionesList.forEach(c => { cc[c.id] = c })
      setComisiones(cc)
    }).catch(console.error)
  }, [])

  // Recalcular advertencia cuando cambia fecha o cursada
  const cursadaSeleccionada = misCursadas.find(c => c.id === Number(cursadaId))
  useEffect(() => {
    if (!cursadaSeleccionada) { setAdvertencia(null); return }
    const dias = diasEnHorario(cursadaSeleccionada.horario)
    setAdvertencia(advertenciaDia(fecha, dias))
  }, [fecha, cursadaId, cursadaSeleccionada])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!cursadaId) return
    setCargando(true)
    setResultado(null)

    try {
      const res = await api.post(`/api/v1/cursadas/${cursadaId}/excepciones`, {
        cursada_id:    Number(cursadaId),
        tipo,
        motivo:        motivo || null,
        fecha,
        aula_nueva:    tipo === 'reubicacion' ? aulaNueva    || null : null,
        horario_nuevo: tipo === 'reubicacion' ? horarioNuevo || null : null,
      })
      const msg = res.data.advertencia
        ? `Registrado. ⚠️ ${res.data.advertencia}`
        : '¡Listo! La excepción fue registrada correctamente.'
      setResultado({ ok: true, msg })
      setMotivo(''); setAulaNueva(''); setHorarioNuevo('')
      setFecha(hoy())
    } catch (err) {
      const detail = err.response?.data?.detail
      setResultado({ ok: false, msg: typeof detail === 'string' ? detail : 'Error al guardar.' })
    } finally {
      setCargando(false)
    }
  }

  const diasCursada = cursadaSeleccionada ? diasEnHorario(cursadaSeleccionada.horario) : []

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-900 mb-1">Suspensión o reubicación de clase</h3>
      <p className="text-xs text-gray-500 mb-5">
        Solo podés gestionar las materias donde estás asignado como profesor.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">

        {/* Tipo */}
        <div className="flex gap-3">
          {['suspension', 'reubicacion'].map(t => (
            <button key={t} type="button" onClick={() => setTipo(t)}
              className={`flex-1 py-2.5 px-4 rounded-lg border text-sm font-medium transition-colors ${
                tipo === t
                  ? 'bg-primary-600 border-primary-600 text-white'
                  : 'border-gray-300 text-gray-600 hover:border-primary-400'
              }`}>
              {t === 'suspension' ? '🚫 Suspensión' : '📍 Reubicación'}
            </button>
          ))}
        </div>

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

          {/* Días habituales */}
          {cursadaSeleccionada && (
            <div className="mt-2 px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-xs text-blue-700">
                <span className="font-medium">Horario habitual: </span>
                {cursadaSeleccionada.horario || 'No especificado'}
              </p>
              {diasCursada.length > 0 && (
                <p className="text-xs text-blue-600 mt-0.5">
                  Días: {diasCursada.map(d => DIAS_IDX[d]).join(', ')}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Fecha del día */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Fecha <span className="text-red-500">*</span></label>
          <input type="date" value={fecha}
            onChange={e => setFecha(e.target.value)} required
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-primary-500" />
          <p className="text-xs text-gray-400 mt-1">La suspensión o reubicación aplica solo a este día.</p>
        </div>

        {/* Advertencia de día */}
        {advertencia && (
          <div className="bg-amber-50 border border-amber-300 rounded-lg px-4 py-2.5 text-xs text-amber-700">
            ⚠️ {advertencia}
          </div>
        )}

        {/* Motivo (obligatorio para suspensión) */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Motivo{tipo === 'suspension' ? <span className="text-red-500"> *</span> : <span className="text-gray-400 font-normal"> (opcional)</span>}
          </label>
          <textarea value={motivo} onChange={e => setMotivo(e.target.value)}
            required={tipo === 'suspension'} rows={2}
            placeholder="Ej: Paro docente, enfermedad, viaje institucional..."
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none
                       focus:outline-none focus:ring-2 focus:ring-primary-500" />
        </div>

        {/* Campos extra para reubicación */}
        {tipo === 'reubicacion' && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-3">
            <p className="text-xs font-medium text-blue-700">Nueva ubicación (completá al menos uno)</p>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Aula nueva</label>
              <input type="text" value={aulaNueva} onChange={e => setAulaNueva(e.target.value)}
                placeholder="Ej: Aula 210, Lab. 154..."
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                           focus:outline-none focus:ring-2 focus:ring-primary-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Horario nuevo</label>
              <input type="text" value={horarioNuevo} onChange={e => setHorarioNuevo(e.target.value)}
                placeholder="Ej: Jueves 18:00-20:00"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                           focus:outline-none focus:ring-2 focus:ring-primary-500" />
            </div>
          </div>
        )}

        {/* Resultado */}
        {resultado && (
          <div className={`rounded-lg px-4 py-3 text-sm ${
            resultado.ok
              ? 'bg-green-50 border border-green-200 text-green-700'
              : 'bg-red-50 border border-red-200 text-red-700'
          }`}>
            {resultado.ok ? '✅ ' : '❌ '}{resultado.msg}
          </div>
        )}

        <button type="submit" disabled={cargando || !cursadaId}
          className="w-full bg-primary-600 hover:bg-primary-700 disabled:bg-gray-200
                     disabled:text-gray-400 disabled:cursor-not-allowed text-white
                     font-medium py-2.5 rounded-lg text-sm transition-colors">
          {cargando ? 'Guardando...' : `Registrar ${tipo === 'suspension' ? 'suspensión' : 'reubicación'}`}
        </button>

      </form>
    </div>
  )
}
