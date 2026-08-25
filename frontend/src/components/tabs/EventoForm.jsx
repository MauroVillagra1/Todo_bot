/**
 * EventoForm — carga un evento de calendario institucional.
 * Tipos: paro, asueto, evento_cultural, fecha_examen, otro.
 * El campo "origen" se asigna automáticamente en el backend con el nombre del usuario.
 */
import { useState, useEffect } from 'react'
import {
  listarComisiones,
  listarMaterias,
  listarCursadas,
  cargarEvento,
} from '../../api'

const hoy = () => new Date().toISOString().split('T')[0]

const TIPOS = [
  { value: 'paro',            label: '✊ Paro'           },
  { value: 'asueto',          label: '🏖️ Asueto'         },
  { value: 'evento_cultural', label: '🎭 Evento cultural' },
  { value: 'fecha_examen',    label: '📝 Fecha de examen' },
  { value: 'otro',            label: '📌 Otro'            },
]

export default function EventoForm() {
  const [comisiones, setComisiones] = useState([])
  const [materias,   setMaterias]   = useState({})
  const [cursadas,   setCursadas]   = useState([])

  const [titulo,      setTitulo]      = useState('')
  const [tipo,        setTipo]        = useState('paro')
  const [motivo,      setMotivo]      = useState('')
  const [fechaInicio, setFechaInicio] = useState(hoy())
  const [fechaFin,    setFechaFin]    = useState(hoy())
  const [horaInicio,  setHoraInicio]  = useState('')
  const [horaFin,     setHoraFin]     = useState('')
  const [alcance,     setAlcance]     = useState('general')
  const [comisionId,  setComisionId]  = useState('')
  const [cursadaId,   setCursadaId]   = useState('')

  const [cargando,  setCargando]  = useState(false)
  const [resultado, setResultado] = useState(null)

  useEffect(() => {
    listarComisiones().then(setComisiones).catch(console.error)
    listarMaterias().then(lista => {
      const mapa = {}
      lista.forEach(m => { mapa[m.id] = `${m.nombre} (${m.codigo})` })
      setMaterias(mapa)
    }).catch(console.error)
  }, [])

  useEffect(() => {
    if (alcance === 'materia_especifica' && comisionId) {
      listarCursadas(comisionId).then(setCursadas).catch(console.error)
    } else {
      setCursadas([])
      setCursadaId('')
    }
  }, [alcance, comisionId])

  async function handleSubmit(e) {
    e.preventDefault()
    setCargando(true)
    setResultado(null)

    const payload = {
      titulo,
      tipo,
      // origen se asigna en el backend automáticamente
      motivo:       motivo || null,
      fecha_inicio: fechaInicio,
      fecha_fin:    fechaFin,
      hora_inicio:  horaInicio || null,
      hora_fin:     horaFin    || null,
      alcance,
      comision_id:  alcance === 'comision'           ? Number(comisionId) : null,
      cursada_id:   alcance === 'materia_especifica'  ? Number(cursadaId)  : null,
    }

    try {
      await cargarEvento(payload)
      setResultado({ ok: true, msg: '¡Evento registrado! Ya es visible para los alumnos.' })
      setTitulo(''); setMotivo('')
      setFechaInicio(hoy()); setFechaFin(hoy())
      setHoraInicio(''); setHoraFin('')
      setAlcance('general'); setComisionId(''); setCursadaId('')
    } catch (err) {
      const detail = err.response?.data?.detail
      setResultado({
        ok: false,
        msg: typeof detail === 'string' ? detail : 'Error al guardar el evento.',
      })
    } finally {
      setCargando(false)
    }
  }

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-900 mb-1">Nuevo evento de calendario</h3>
      <p className="text-xs text-gray-500 mb-5">
        Registrá paros, asuetos, exámenes y otros eventos. El evento quedará visible
        para los alumnos y el asistente lo va a incluir en sus respuestas.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">

        {/* Título */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Título del evento <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={titulo}
            onChange={e => setTitulo(e.target.value)}
            required
            minLength={2}
            placeholder="Ej: Paro nacional docente, Examen final Análisis I..."
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {/* Tipo */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-2">
            Tipo <span className="text-red-500">*</span>
          </label>
          <div className="flex flex-wrap gap-2">
            {TIPOS.map(t => (
              <button
                key={t.value}
                type="button"
                onClick={() => setTipo(t.value)}
                className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                  tipo === t.value
                    ? 'bg-primary-600 border-primary-600 text-white'
                    : 'border-gray-300 text-gray-600 hover:border-primary-400'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Descripción / Motivo */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Descripción <span className="text-gray-400 font-normal">(opcional)</span>
          </label>
          <textarea
            value={motivo}
            onChange={e => setMotivo(e.target.value)}
            rows={2}
            placeholder="Describí brevemente el evento para que el asistente pueda responder preguntas al respecto..."
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none
                       focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {/* Fechas */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Fecha inicio <span className="text-red-500">*</span>
            </label>
            <input
              type="date"
              value={fechaInicio}
              onChange={e => setFechaInicio(e.target.value)}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Fecha fin <span className="text-red-500">*</span>
            </label>
            <input
              type="date"
              value={fechaFin}
              min={fechaInicio}
              onChange={e => setFechaFin(e.target.value)}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>

        {/* Horas (opcionales) */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Hora inicio <span className="text-gray-400 font-normal">(opcional)</span>
            </label>
            <input
              type="time"
              value={horaInicio}
              onChange={e => setHoraInicio(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Hora fin <span className="text-gray-400 font-normal">(opcional)</span>
            </label>
            <input
              type="time"
              value={horaFin}
              onChange={e => setHoraFin(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>

        {/* Alcance */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-2">Alcance del evento</label>
          <div className="flex flex-col gap-2">
            {[
              { value: 'general',            label: '🌐 General — afecta a toda la institución' },
              { value: 'comision',           label: '👥 Por comisión — solo una comisión'       },
              { value: 'materia_especifica', label: '📚 Por materia — solo una cursada puntual' },
            ].map(a => (
              <label key={a.value} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="alcance"
                  value={a.value}
                  checked={alcance === a.value}
                  onChange={() => setAlcance(a.value)}
                  className="text-primary-600"
                />
                <span className="text-sm text-gray-700">{a.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Selector de comisión */}
        {(alcance === 'comision' || alcance === 'materia_especifica') && (
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Comisión <span className="text-red-500">*</span>
            </label>
            <select
              value={comisionId}
              onChange={e => setComisionId(e.target.value)}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">Seleccioná una comisión...</option>
              {comisiones.map(c => (
                <option key={c.id} value={c.id}>{c.nombre}</option>
              ))}
            </select>
          </div>
        )}

        {/* Selector de cursada */}
        {alcance === 'materia_especifica' && comisionId && (
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Materia / Cursada <span className="text-red-500">*</span>
            </label>
            <select
              value={cursadaId}
              onChange={e => setCursadaId(e.target.value)}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">Seleccioná una materia...</option>
              {cursadas.map(c => (
                <option key={c.id} value={c.id}>
                  {materias[c.materia_id] || `Cursada #${c.id}`}
                </option>
              ))}
            </select>
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

        <button
          type="submit"
          disabled={cargando || !titulo}
          className="w-full bg-primary-600 hover:bg-primary-700 disabled:bg-gray-200
                     disabled:text-gray-400 disabled:cursor-not-allowed text-white
                     font-medium py-2.5 rounded-lg text-sm transition-colors"
        >
          {cargando ? 'Guardando...' : 'Registrar evento'}
        </button>

      </form>
    </div>
  )
}
