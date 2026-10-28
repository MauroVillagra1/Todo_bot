/**
 * Calendario académico, mes por mes (con los turnos de exámenes finales intercalados).
 *   editable=false → vista para todos los usuarios (menú "Calendario")
 *   editable=true  → planilla del panel (solo ADMIN): cada celda se guarda al salir de ella
 * Los turnos de examen se editan en el panel, pestaña "Mesas".
 */
import { useEffect, useMemo, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { actualizarEvento, borrarEvento, crearEvento, listarCalendario, listarMesasFechas } from '../api'
import { Celda, celda } from './GrillaHorarios'
import { boton, campo, errorDe, tarjeta } from './ui'

export const CATEGORIAS = {
  CLASES: ['Clases', 'bg-emerald-500/15 text-emerald-400'],
  INSCRIPCION: ['Inscripción', 'bg-sky-500/15 text-sky-400'],
  NOTAS: ['Notas', 'bg-violet-500/15 text-violet-300'],
  SUFICIENCIA: ['Suficiencia', 'bg-amber-500/15 text-amber-300'],
  EXAMENES: ['Exámenes', 'bg-[#e8592e]/15 text-[#f2894f]'],
  RECESO: ['Receso', 'bg-teal-500/15 text-teal-300'],
  FERIADO: ['Feriado', 'bg-red-500/15 text-red-400'],
  ASUETO: ['Asueto', 'bg-pink-500/15 text-pink-300'],
  PLAZO: ['Plazo', 'bg-yellow-500/15 text-yellow-300'],
  OTRO: ['Otro', 'bg-[#1e1e22] text-[#a1a1aa]'],
}
const MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
const DIAS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb']
const ROMANO = { 1: 'I', 2: 'II', 3: 'III' }

const hoyISO = () => new Date().toISOString().split('T')[0]
const fecha = iso => { const [a, m, d] = iso.split('-').map(Number); return new Date(a, m - 1, d) }
const corta = iso => { const f = fecha(iso); return `${DIAS[f.getDay()]} ${String(f.getDate()).padStart(2, '0')}/${String(f.getMonth() + 1).padStart(2, '0')}` }
const clave = iso => iso.slice(0, 7)  // "2026-11"

function Etiqueta({ categoria }) {
  const [texto, color] = CATEGORIAS[categoria] ?? CATEGORIAS.OTRO
  return <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium whitespace-nowrap ${color}`}>{texto}</span>
}

function FilaEditable({ e, onCambio, onBorrado, setError }) {
  async function guardar(cambios) {
    setError(null)
    try { onCambio(await actualizarEvento(e.id, cambios)) }
    catch (err) { setError(errorDe(err, 'No se pudo guardar')); throw err }
  }
  async function borrar() {
    if (!confirm(`¿Borrar «${e.actividad}»?`)) return
    try { await borrarEvento(e.id); onBorrado(e.id) }
    catch (err) { setError(errorDe(err, 'No se pudo borrar')) }
  }
  return (
    <tr className="border-t border-[#1e1e22] hover:bg-[#111114]">
      <td className="w-32"><Celda tipo="date" valor={e.fecha_inicio} onGuardar={v => guardar({ fecha_inicio: v })} /></td>
      <td className="w-32"><Celda tipo="date" valor={e.fecha_fin} onGuardar={v => guardar({ fecha_fin: v || null })} /></td>
      <td className="min-w-[260px]"><Celda valor={e.actividad} onGuardar={v => guardar({ actividad: v })} /></td>
      <td className="w-32">
        <select value={e.categoria} onChange={ev => guardar({ categoria: ev.target.value }).catch(() => {})} className={celda}>
          {Object.entries(CATEGORIAS).map(([id, [texto]]) => <option key={id} value={id}>{texto}</option>)}
        </select>
      </td>
      <td className="min-w-[160px]"><Celda valor={e.detalle} placeholder="—" onGuardar={v => guardar({ detalle: v })} /></td>
      <td className="w-8 text-center">
        <button onClick={borrar} title="Borrar" className="text-[#4b4b53] hover:text-red-400 p-1"><Trash2 size={13} /></button>
      </td>
    </tr>
  )
}

const EVENTO_VACIO = { fecha_inicio: hoyISO(), fecha_fin: '', actividad: '', categoria: 'OTRO', detalle: '' }

function NuevoEvento({ onCreado }) {
  const [f, setF] = useState(EVENTO_VACIO)
  const [error, setError] = useState(null)
  const cambiar = c => e => setF(prev => ({ ...prev, [c]: e.target.value }))
  async function crear(e) {
    e.preventDefault()
    setError(null)
    try {
      onCreado(await crearEvento({ ...f, fecha_fin: f.fecha_fin || null }))
      setF(EVENTO_VACIO)
    } catch (err) { setError(errorDe(err, 'Revisá los datos')) }
  }
  return (
    <form onSubmit={crear} className={`${tarjeta} space-y-3`}>
      <h3 className="text-sm font-semibold text-[#f4f4f5]">Agregar actividad</h3>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <label className="text-xs text-[#a1a1aa]">Desde<input required type="date" value={f.fecha_inicio} onChange={cambiar('fecha_inicio')} className={`${campo} mt-1`} /></label>
        <label className="text-xs text-[#a1a1aa]">Hasta (opcional)<input type="date" value={f.fecha_fin} onChange={cambiar('fecha_fin')} className={`${campo} mt-1`} /></label>
        <label className="text-xs text-[#a1a1aa] col-span-2">Categoría
          <select value={f.categoria} onChange={cambiar('categoria')} className={`${campo} mt-1`}>
            {Object.entries(CATEGORIAS).map(([id, [texto]]) => <option key={id} value={id}>{texto}</option>)}
          </select>
        </label>
        <input required minLength={3} placeholder="Actividad" value={f.actividad} onChange={cambiar('actividad')} className={`${campo} col-span-2 sm:col-span-4`} />
        <input placeholder="Detalle (opcional): cierre de inscripción, carácter del feriado…" value={f.detalle} onChange={cambiar('detalle')} className={`${campo} col-span-2 sm:col-span-4`} />
      </div>
      <div className="flex items-center gap-3">
        <button type="submit" className={boton}>Agregar</button>
        {error && <span className="text-xs text-red-400">{error}</span>}
      </div>
    </form>
  )
}

export default function Calendario({ editable = false }) {
  const [eventos, setEventos] = useState(null)
  const [mesas, setMesas] = useState([])
  const [error, setError] = useState(null)
  const [mes, setMes] = useState(clave(hoyISO()))
  const [categoria, setCategoria] = useState('')

  useEffect(() => {
    listarCalendario().then(setEventos).catch(e => setError(errorDe(e, 'No se pudo cargar el calendario.')))
    listarMesasFechas().then(setMesas).catch(() => {})
  }, [])

  // Meses con algo: los de cada actividad (todo su rango) y los de los exámenes
  const meses = useMemo(() => {
    const s = new Set()
    for (const e of eventos ?? []) {
      const d = fecha(e.fecha_inicio), fin = fecha(e.fecha_fin ?? e.fecha_inicio)
      for (let a = d.getFullYear(), m = d.getMonth(); a < fin.getFullYear() || (a === fin.getFullYear() && m <= fin.getMonth()); m === 11 ? (a++, m = 0) : m++)
        s.add(`${a}-${String(m + 1).padStart(2, '0')}`)
    }
    for (const f of mesas) s.add(clave(f.fecha_examen))
    return [...s].sort()
  }, [eventos, mesas])
  const actual = meses.includes(mes) ? mes : (meses.find(m => m >= clave(hoyISO())) ?? meses[0])

  const delMes = useMemo(() => {
    if (!actual) return []
    const [a, m] = actual.split('-').map(Number)
    const inicio = `${actual}-01`, fin = `${actual}-${new Date(a, m, 0).getDate()}`
    const filas = (eventos ?? [])
      .filter(e => e.fecha_inicio <= fin && (e.fecha_fin ?? e.fecha_inicio) >= inicio)
      .filter(e => !categoria || e.categoria === categoria)
      .map(e => ({ ...e, tipo: 'evento', orden: e.fecha_inicio }))
    if (!categoria || categoria === 'EXAMENES')
      for (const f of mesas.filter(f => clave(f.fecha_examen) === actual))
        filas.push({ id: `m${f.id}`, tipo: 'mesa', orden: f.fecha_examen, ...f })
    return filas.sort((x, y) => x.orden.localeCompare(y.orden))
  }, [eventos, mesas, actual, categoria])

  if (!eventos) return <p className={`text-sm ${error ? 'text-red-400' : 'text-[#8b8b93]'}`}>{error ?? 'Cargando…'}</p>
  const hoy = hoyISO()
  const idx = meses.indexOf(actual)
  const [anioActual, mesActual] = (actual ?? '2026-01').split('-').map(Number)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <button disabled={idx <= 0} onClick={() => setMes(meses[idx - 1])}
                  className="px-2 py-1 rounded-lg text-[#8b8b93] hover:text-[#f4f4f5] disabled:opacity-30">‹</button>
          <h3 className="font-display text-lg font-semibold text-[#f4f4f5] w-44 text-center">{MESES[mesActual - 1]} {anioActual}</h3>
          <button disabled={idx >= meses.length - 1} onClick={() => setMes(meses[idx + 1])}
                  className="px-2 py-1 rounded-lg text-[#8b8b93] hover:text-[#f4f4f5] disabled:opacity-30">›</button>
        </div>
        <select value={categoria} onChange={e => setCategoria(e.target.value)} className={`${campo} !w-auto`}>
          <option value="">Todas las categorías</option>
          {Object.entries(CATEGORIAS).map(([id, [texto]]) => <option key={id} value={id}>{texto}</option>)}
        </select>
        <span className="text-xs text-[#8b8b93]">Calendario académico 2026 · Res. 2394/2025 CD</span>
      </div>

      {editable ? (
        <div className={`${tarjeta} !p-0 overflow-hidden`}>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="text-[11px] uppercase tracking-wide text-[#8b8b93] bg-[#111114]">
                <tr>
                  <th className="px-2 py-2 font-medium">Desde</th><th className="px-2 font-medium">Hasta</th>
                  <th className="px-2 font-medium">Actividad</th><th className="px-2 font-medium">Categoría</th>
                  <th className="px-2 font-medium">Detalle</th><th />
                </tr>
              </thead>
              <tbody>
                {delMes.map(e => e.tipo === 'mesa' ? (
                  <tr key={e.id} className="border-t border-[#1e1e22] text-xs text-[#8b8b93]">
                    <td className="px-2 py-1.5" colSpan={2}>{corta(e.fecha_examen)}</td>
                    <td className="px-2" colSpan={4}>{e.turno}º turno de exámenes — Mesa {ROMANO[e.mesa]} (inscripción hasta {corta(e.cierre_inscripcion)}) · se edita en «Mesas»</td>
                  </tr>
                ) : (
                  <FilaEditable key={e.id} e={e} setError={setError}
                                onCambio={n => setEventos(prev => prev.map(x => (x.id === n.id ? n : x)))}
                                onBorrado={id => setEventos(prev => prev.filter(x => x.id !== id))} />
                ))}
              </tbody>
            </table>
            {delMes.length === 0 && <p className="text-xs text-[#8b8b93] px-4 py-3">Nada en este mes.</p>}
          </div>
        </div>
      ) : (
        <ul className={`${tarjeta} divide-y divide-[#1e1e22] !py-1`}>
          {delMes.map(e => {
            const hasta = e.tipo === 'mesa' ? e.fecha_examen : (e.fecha_fin ?? e.fecha_inicio)
            const pasado = hasta < hoy
            const enCurso = !pasado && (e.tipo === 'mesa' ? e.fecha_examen === hoy : e.fecha_inicio <= hoy)
            return (
              <li key={e.id} className={`py-3 flex gap-3 ${pasado ? 'opacity-45' : ''}`}>
                <div className="w-28 flex-shrink-0 text-xs text-[#c7c7cf] font-medium">
                  {e.tipo === 'mesa' ? corta(e.fecha_examen)
                    : e.fecha_fin ? <>{corta(e.fecha_inicio)}<span className="text-[#8b8b93]"> al</span><br />{corta(e.fecha_fin)}</> : corta(e.fecha_inicio)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Etiqueta categoria={e.tipo === 'mesa' ? 'EXAMENES' : e.categoria} />
                    {enCurso && <span className="text-[10px] text-emerald-400 font-medium">en curso</span>}
                  </div>
                  <p className="text-sm text-[#f4f4f5] mt-1">
                    {e.tipo === 'mesa' ? `${e.turno}º turno de exámenes finales — Mesa ${ROMANO[e.mesa]}` : e.actividad}
                  </p>
                  {(e.tipo === 'mesa' || e.detalle) && (
                    <p className="text-xs text-[#8b8b93] mt-0.5">
                      {e.tipo === 'mesa' ? `Inscripción hasta el ${corta(e.cierre_inscripcion)}` : e.detalle}
                    </p>
                  )}
                </div>
              </li>
            )
          })}
          {delMes.length === 0 && <li className="py-3 text-sm text-[#8b8b93]">Nada en este mes.</li>}
        </ul>
      )}
      {error && <p className="text-xs text-red-400">{error}</p>}
      {editable && <NuevoEvento onCreado={n => { setEventos(prev => [...prev, n]); setMes(clave(n.fecha_inicio)) }} />}
    </div>
  )
}
