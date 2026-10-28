/**
 * GrillaMesas — SMOD y ADMIN. Planillas de las mesas de examen que usa el chat:
 *   Fechas   → por turno, el cierre de inscripción y el día del examen de la Mesa I, II y III
 *   Materias → en qué mesa se rinde cada materia y su tribunal (sede, presidente, vocales, hora)
 * Cada celda se guarda al salir de ella.
 */
import { useEffect, useMemo, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import {
  actualizarMesaFecha, actualizarMesaMateria, borrarMesaFecha, borrarMesaMateria, crearMesaFecha, crearMesaMateria,
  listarMesasFechas, listarMesasMaterias,
} from '../api'
import { Celda, celda } from './GrillaHorarios'
import { errorDe, tarjeta, confirmar } from './ui'

const ROMANO = { 1: 'I', 2: 'II', 3: 'III' }
const SEDES = ['Casa Central', 'Anexo Concepción']
const hoyISO = () => new Date().toISOString().split('T')[0]

function Fechas() {
  const [fechas, setFechas] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => { listarMesasFechas().then(setFechas).catch(e => setError(errorDe(e, 'No se pudieron cargar las fechas.'))) }, [])

  // turno → { 1: fecha, 2: fecha, 3: fecha }
  const turnos = useMemo(() => {
    const t = {}
    for (const f of fechas ?? []) (t[f.turno ?? 0] ??= {})[f.mesa] = f
    return Object.entries(t).sort(([a], [b]) => (Number(a) || 99) - (Number(b) || 99))
  }, [fechas])

  async function guardar(f, cambios) {
    setError(null)
    try {
      const nueva = await actualizarMesaFecha(f.id, cambios)
      setFechas(prev => prev.map(x => (x.id === nueva.id ? nueva : x)))
    } catch (err) { setError(errorDe(err, 'No se pudo guardar')); throw err }
  }
  async function borrar(f) {
    if (!(await confirmar(`¿Borrar la Mesa ${ROMANO[f.mesa]} del ${f.turno}º turno?`))) return
    try { await borrarMesaFecha(f.id); setFechas(prev => prev.filter(x => x.id !== f.id)) }
    catch (err) { setError(errorDe(err, 'No se pudo borrar')) }
  }
  async function agregarTurno() {
    setError(null)
    const turno = Math.max(0, ...(fechas ?? []).map(f => f.turno ?? 0)) + 1
    try {
      const nuevas = []
      for (const mesa of [1, 2, 3]) nuevas.push(await crearMesaFecha({ mesa, turno, cierre_inscripcion: hoyISO(), fecha_examen: hoyISO() }))
      setFechas(prev => [...prev, ...nuevas])
    } catch (err) { setError(errorDe(err, 'No se pudo agregar el turno')) }
  }

  if (!fechas) return <p className="text-sm text-[#8b8b93]">{error ?? 'Cargando…'}</p>
  const hoy = hoyISO()

  return (
    <div className={`${tarjeta} !p-0 overflow-hidden`}>
      <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-[#1e1e22]">
        <div>
          <h3 className="text-sm font-semibold text-[#f4f4f5]">Fechas de examen</h3>
          <p className="text-xs text-[#8b8b93]">Arriba el cierre de inscripción; abajo el día del examen.</p>
        </div>
        <button onClick={agregarTurno} className="flex items-center gap-1 text-xs text-[#f2894f] hover:underline">
          <Plus size={13} /> Agregar turno
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead className="text-[11px] uppercase tracking-wide text-[#8b8b93] bg-[#111114]">
            <tr>
              <th className="px-3 py-2 font-medium w-16">Turno</th>
              {[1, 2, 3].map(m => <th key={m} className="px-2 font-medium">Mesa {ROMANO[m]}</th>)}
            </tr>
          </thead>
          <tbody>
            {turnos.map(([turno, mesas]) => {
              const pasado = Object.values(mesas).every(f => f.fecha_examen < hoy)
              return (
                <tr key={turno} className={`border-t border-[#1e1e22] align-top ${pasado ? 'opacity-50' : ''}`}>
                  <td className="px-3 py-2 text-xs text-[#a1a1aa]">{Number(turno) ? `${turno}º` : '—'}</td>
                  {[1, 2, 3].map(m => {
                    const f = mesas[m]
                    if (!f) return <td key={m} className="px-2 text-xs text-[#4b4b53]">—</td>
                    return (
                      <td key={m} className="px-1 py-1">
                        <div className="flex items-center gap-1">
                          <span className="text-[10px] text-[#8b8b93] w-14">Cierre</span>
                          <Celda tipo="date" valor={f.cierre_inscripcion} onGuardar={v => guardar(f, { cierre_inscripcion: v })} />
                        </div>
                        <div className="flex items-center gap-1">
                          <span className="text-[10px] text-[#f2894f] w-14">Examen</span>
                          <Celda tipo="date" valor={f.fecha_examen} onGuardar={v => guardar(f, { fecha_examen: v })} />
                          <button onClick={() => borrar(f)} title="Borrar" className="text-[#4b4b53] hover:text-red-400 p-1">
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {error && <p className="text-xs text-red-400 px-4 py-2">{error}</p>}
    </div>
  )
}

function FilaMateria({ m, onCambio, onBorrado, setError }) {
  async function guardar(cambios) {
    setError(null)
    try { onCambio(await actualizarMesaMateria(m.id, cambios)) }
    catch (err) { setError(errorDe(err, 'No se pudo guardar')); throw err }
  }
  async function borrar() {
    if (!(await confirmar(`¿Borrar ${m.materia} (${m.sede})?`))) return
    try { await borrarMesaMateria(m.id); onBorrado(m.id) }
    catch (err) { setError(errorDe(err, 'No se pudo borrar')) }
  }
  return (
    <tr className="border-t border-[#1e1e22] hover:bg-[#111114]">
      <td className="min-w-[200px]"><Celda valor={m.materia} onGuardar={v => guardar({ materia: v })} /></td>
      <td className="w-20">
        <select value={m.mesa} onChange={e => guardar({ mesa: Number(e.target.value) }).catch(() => {})} className={celda}>
          {[1, 2, 3].map(n => <option key={n} value={n}>{ROMANO[n]}</option>)}
        </select>
      </td>
      <td className="w-36">
        <select value={m.sede} onChange={e => guardar({ sede: e.target.value }).catch(() => {})} className={celda}>
          {SEDES.map(s => <option key={s}>{s}</option>)}
        </select>
      </td>
      <td className="min-w-[150px]"><Celda valor={m.presidente} placeholder="A confirmar" onGuardar={v => guardar({ presidente: v })} /></td>
      <td className="min-w-[140px]"><Celda valor={m.vocal1} placeholder="—" onGuardar={v => guardar({ vocal1: v })} /></td>
      <td className="min-w-[140px]"><Celda valor={m.vocal2} placeholder="—" onGuardar={v => guardar({ vocal2: v })} /></td>
      <td className="w-20"><Celda tipo="time" valor={m.hora} onGuardar={v => guardar({ hora: v })} /></td>
      <td className="w-8 text-center">
        <button onClick={borrar} title="Borrar" className="text-[#4b4b53] hover:text-red-400 p-1"><Trash2 size={13} /></button>
      </td>
    </tr>
  )
}

const MATERIA_VACIA = { materia: '', sede: 'Casa Central', presidente: '', vocal1: '', vocal2: '', hora: '' }

function Materias() {
  const [materias, setMaterias] = useState(null)
  const [error, setError] = useState(null)
  const [mesa, setMesa] = useState(1)
  const [filtro, setFiltro] = useState('')
  const [nueva, setNueva] = useState(null)
  useEffect(() => { listarMesasMaterias().then(setMaterias).catch(e => setError(errorDe(e, 'No se pudieron cargar las materias.'))) }, [])

  const visibles = useMemo(() => {
    const q = filtro.trim().toLowerCase()
    return (materias ?? []).filter(m => m.mesa === mesa
      && (!q || [m.materia, m.presidente, m.vocal1, m.vocal2].some(x => x?.toLowerCase().includes(q))))
  }, [materias, mesa, filtro])

  async function crear() {
    setError(null)
    try {
      const m = await crearMesaMateria({ ...nueva, mesa, anio_tribunal: new Date().getFullYear() })
      setMaterias(prev => [...prev, m])
      setNueva(null)
    } catch (err) { setError(errorDe(err, 'Completá al menos la materia')) }
  }

  if (!materias) return <p className="text-sm text-[#8b8b93]">{error ?? 'Cargando…'}</p>
  const cambiar = c => e => setNueva(prev => ({ ...prev, [c]: e.target.value }))

  return (
    <div className={`${tarjeta} !p-0 overflow-hidden`}>
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-b border-[#1e1e22]">
        <div className="flex items-center gap-1">
          {[1, 2, 3].map(n => (
            <button key={n} onClick={() => setMesa(n)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
                      n === mesa ? 'bg-[#e8592e]/15 text-[#f2894f]' : 'text-[#8b8b93] hover:text-[#f4f4f5] hover:bg-[#17171b]'}`}>
              Mesa {ROMANO[n]}
            </button>
          ))}
        </div>
        <input placeholder="Buscar materia o docente…" value={filtro} onChange={e => setFiltro(e.target.value)}
               className="bg-[#141417] border border-[#232327] rounded-lg px-3 py-1.5 text-xs text-[#f4f4f5] flex-1 min-w-[160px]" />
        <button onClick={() => setNueva(MATERIA_VACIA)} className="flex items-center gap-1 text-xs text-[#f2894f] hover:underline">
          <Plus size={13} /> Agregar materia
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead className="text-[11px] uppercase tracking-wide text-[#8b8b93] bg-[#111114]">
            <tr>
              <th className="px-2 py-2 font-medium">Materia</th><th className="px-2 font-medium">Mesa</th>
              <th className="px-2 font-medium">Sede</th><th className="px-2 font-medium">Presidente</th>
              <th className="px-2 font-medium">Vocal 1</th><th className="px-2 font-medium">Vocal 2</th>
              <th className="px-2 font-medium">Hora</th><th />
            </tr>
          </thead>
          <tbody>
            {nueva && (
              <tr className="border-t border-[#e8592e]/30 bg-[#e8592e]/5">
                <td><input autoFocus placeholder="Materia" value={nueva.materia} onChange={cambiar('materia')} className={celda} /></td>
                <td className="px-2 text-xs text-[#a1a1aa]">{ROMANO[mesa]}</td>
                <td><select value={nueva.sede} onChange={cambiar('sede')} className={celda}>{SEDES.map(s => <option key={s}>{s}</option>)}</select></td>
                <td><input placeholder="Presidente" value={nueva.presidente} onChange={cambiar('presidente')} className={celda} /></td>
                <td><input placeholder="Vocal 1" value={nueva.vocal1} onChange={cambiar('vocal1')} className={celda} /></td>
                <td><input placeholder="Vocal 2" value={nueva.vocal2} onChange={cambiar('vocal2')} className={celda} /></td>
                <td><input type="time" value={nueva.hora} onChange={cambiar('hora')} className={celda} /></td>
                <td className="whitespace-nowrap px-1">
                  <button onClick={crear} className="text-xs text-emerald-400 hover:underline mr-2">Guardar</button>
                  <button onClick={() => setNueva(null)} className="text-xs text-[#8b8b93] hover:underline">Cancelar</button>
                </td>
              </tr>
            )}
            {visibles.map(m => (
              <FilaMateria key={m.id} m={m} setError={setError}
                           onCambio={n => setMaterias(prev => prev.map(x => (x.id === n.id ? n : x)))}
                           onBorrado={id => setMaterias(prev => prev.filter(x => x.id !== id))} />
            ))}
          </tbody>
        </table>
        {visibles.length === 0 && <p className="text-xs text-[#8b8b93] px-4 py-3">No hay materias{filtro && ' que coincidan'}.</p>}
      </div>
      {error && <p className="text-xs text-red-400 px-4 py-2">{error}</p>}
    </div>
  )
}

export default function GrillaMesas() {
  return (
    <div className="space-y-6">
      <Fechas />
      <Materias />
    </div>
  )
}
