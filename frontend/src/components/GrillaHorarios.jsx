/**
 * GrillaHorarios — solo ADMIN. Tabla tipo planilla de los horarios que usa el chat:
 * año → comisión → bloques (día, hora, materia, docente, aula, lugar).
 * Cada celda se guarda al salir de ella; las filas nuevas quedan como "Carga manual".
 */
import { useEffect, useMemo, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { actualizarBloque, borrarBloque, crearBloque, listarHorarios } from '../api'
import { boton, campo, errorDe, tarjeta } from './ui'

const DIAS = { 1: 'Lunes', 2: 'Martes', 3: 'Miércoles', 4: 'Jueves', 5: 'Viernes', 6: 'Sábado' }
const PERIODOS = ['Anual', 'Primer cuatrimestre', 'Segundo cuatrimestre']
const celda = 'w-full bg-transparent px-2 py-1.5 text-xs text-[#f4f4f5] placeholder-[#4b4b53] rounded focus:outline-none focus:bg-[#141417] focus:ring-1 focus:ring-[#e8592e]/50'

const claveGrupo = b => `${b.comision}|${b.plan ?? ''}|${b.periodo ?? ''}`

/** Input que guarda al perder el foco (o con Enter) solo si el valor cambió. */
function Celda({ valor, onGuardar, placeholder, tipo = 'text', ancho }) {
  const [v, setV] = useState(valor ?? '')
  useEffect(() => { setV(valor ?? '') }, [valor])
  const guardar = () => { if (v !== (valor ?? '')) onGuardar(v).catch(() => setV(valor ?? '')) }
  return (
    <input type={tipo} value={v} placeholder={placeholder} onChange={e => setV(e.target.value)} onBlur={guardar}
           onKeyDown={e => e.key === 'Enter' && e.currentTarget.blur()} className={`${celda} ${ancho ?? ''}`} />
  )
}

function FilaBloque({ b, onCambio, onBorrado, setError }) {
  async function guardar(cambios) {
    setError(null)
    try { onCambio(await actualizarBloque(b.id, cambios)) }
    catch (err) { setError(errorDe(err, 'No se pudo guardar')); throw err }
  }
  async function borrar() {
    if (!confirm(`¿Borrar ${b.materia} (${DIAS[b.dia]} ${b.inicio})?`)) return
    try { await borrarBloque(b.id); onBorrado(b.id) }
    catch (err) { setError(errorDe(err, 'No se pudo borrar')) }
  }
  return (
    <tr className="border-t border-[#1e1e22] hover:bg-[#111114]">
      <td className="w-28">
        <select value={b.dia} onChange={e => guardar({ dia: Number(e.target.value) }).catch(() => {})} className={celda}>
          {Object.entries(DIAS).map(([n, d]) => <option key={n} value={n}>{d}</option>)}
        </select>
      </td>
      <td className="w-20"><Celda tipo="time" valor={b.inicio} onGuardar={v => guardar({ inicio: v })} /></td>
      <td className="w-20"><Celda tipo="time" valor={b.fin} onGuardar={v => guardar({ fin: v })} /></td>
      <td className="min-w-[180px]"><Celda valor={b.materia} onGuardar={v => guardar({ materia: v })} /></td>
      <td className="min-w-[150px]"><Celda valor={b.docente} placeholder="Sin docente" onGuardar={v => guardar({ docente: v })} /></td>
      <td className="w-20"><Celda valor={b.aula} placeholder="—" onGuardar={v => guardar({ aula: v })} /></td>
      <td className="w-24"><Celda valor={b.lugar} placeholder="—" onGuardar={v => guardar({ lugar: v })} /></td>
      <td className="w-8 text-center">
        <input type="checkbox" checked={b.electiva} title="Electiva" className="accent-[#e8592e]"
               onChange={e => guardar({ electiva: e.target.checked }).catch(() => {})} />
      </td>
      <td className="w-8 text-center">
        <button onClick={borrar} title={`Borrar · origen: ${b.origen}`} className="text-[#4b4b53] hover:text-red-400 p-1">
          <Trash2 size={13} />
        </button>
      </td>
    </tr>
  )
}

function FilaNueva({ base, onCreado, onCancelar }) {
  const [f, setF] = useState({ dia: 1, inicio: '', fin: '', materia: '', docente: '', aula: base.aula ?? '', lugar: '' })
  const [error, setError] = useState(null)
  const cambiar = c => e => setF(prev => ({ ...prev, [c]: e.target.value }))
  async function guardar() {
    setError(null)
    try {
      onCreado(await crearBloque({
        ...f, dia: Number(f.dia), comision: base.comision, anio: base.anio, plan: base.plan,
        periodo: base.periodo, turno: base.turno,
      }))
    } catch (err) { setError(errorDe(err, 'Completá día, horas y materia')) }
  }
  return (
    <>
      <tr className="border-t border-[#e8592e]/30 bg-[#e8592e]/5">
        <td><select value={f.dia} onChange={cambiar('dia')} className={celda}>
          {Object.entries(DIAS).map(([n, d]) => <option key={n} value={n}>{d}</option>)}
        </select></td>
        <td><input type="time" value={f.inicio} onChange={cambiar('inicio')} className={celda} /></td>
        <td><input type="time" value={f.fin} onChange={cambiar('fin')} className={celda} /></td>
        <td><input autoFocus placeholder="Materia" value={f.materia} onChange={cambiar('materia')} className={celda} /></td>
        <td><input placeholder="Docente" value={f.docente} onChange={cambiar('docente')} className={celda} /></td>
        <td><input placeholder="Aula" value={f.aula} onChange={cambiar('aula')} className={celda} /></td>
        <td><input placeholder="Lab." value={f.lugar} onChange={cambiar('lugar')} className={celda} /></td>
        <td colSpan={2} className="whitespace-nowrap px-1">
          <button onClick={guardar} className="text-xs text-emerald-400 hover:underline mr-2">Guardar</button>
          <button onClick={onCancelar} className="text-xs text-[#8b8b93] hover:underline">Cancelar</button>
        </td>
      </tr>
      {error && <tr><td colSpan={9} className="text-xs text-red-400 px-2 pb-2">{error}</td></tr>}
    </>
  )
}

function TablaComision({ bloques, onCambio, onBorrado, onCreado }) {
  const [agregando, setAgregando] = useState(false)
  const [error, setError] = useState(null)
  const b0 = bloques[0]
  const detalle = [b0.plan && `Plan ${b0.plan}`, b0.periodo, b0.turno && `Turno ${b0.turno.toLowerCase()}`].filter(Boolean).join(' · ')
  const ordenados = [...bloques].sort((a, b) => a.dia - b.dia || a.inicio.localeCompare(b.inicio))

  return (
    <div className={`${tarjeta} !p-0 overflow-hidden`}>
      <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-[#1e1e22]">
        <div>
          <h4 className="text-sm font-semibold text-[#f4f4f5]">{b0.comision}</h4>
          {detalle && <p className="text-xs text-[#8b8b93]">{detalle}</p>}
        </div>
        <button onClick={() => setAgregando(true)} className="flex items-center gap-1 text-xs text-[#f2894f] hover:underline">
          <Plus size={13} /> Agregar materia
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead className="text-[11px] uppercase tracking-wide text-[#8b8b93] bg-[#111114]">
            <tr>
              <th className="px-2 py-2 font-medium">Día</th><th className="px-2 font-medium">Inicio</th>
              <th className="px-2 font-medium">Fin</th><th className="px-2 font-medium">Materia</th>
              <th className="px-2 font-medium">Profesor</th><th className="px-2 font-medium">Aula</th>
              <th className="px-2 font-medium">Lugar</th><th className="px-1 font-medium" title="Electiva">Elec.</th><th />
            </tr>
          </thead>
          <tbody>
            {ordenados.map(b => <FilaBloque key={b.id} b={b} onCambio={onCambio} onBorrado={onBorrado} setError={setError} />)}
            {agregando && <FilaNueva base={b0} onCancelar={() => setAgregando(false)}
                                     onCreado={n => { onCreado(n); setAgregando(false) }} />}
          </tbody>
        </table>
      </div>
      {error && <p className="text-xs text-red-400 px-4 py-2">{error}</p>}
    </div>
  )
}

const COMISION_VACIA = { comision: '', plan: '2023', periodo: 'Anual', turno: '', dia: 1, inicio: '', fin: '', materia: '', docente: '', aula: '' }

function NuevaComision({ onCreado }) {
  const [f, setF] = useState(COMISION_VACIA)
  const [error, setError] = useState(null)
  const cambiar = c => e => setF(prev => ({ ...prev, [c]: e.target.value }))
  async function crear(e) {
    e.preventDefault()
    setError(null)
    try {
      onCreado(await crearBloque({ ...f, dia: Number(f.dia) }))
      setF(COMISION_VACIA)
    } catch (err) { setError(errorDe(err, 'Revisá los datos')) }
  }
  return (
    <form onSubmit={crear} className={`${tarjeta} space-y-3`}>
      <div>
        <h3 className="text-sm font-semibold text-[#f4f4f5]">Agregar comisión o materia suelta</h3>
        <p className="text-xs text-[#8b8b93] mt-0.5">El año se toma del primer número de la comisión (1K01 → 1º año).</p>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <input required placeholder="Comisión (1K01)" value={f.comision} onChange={cambiar('comision')} className={campo} />
        <input placeholder="Plan" value={f.plan} onChange={cambiar('plan')} className={campo} />
        <select value={f.periodo} onChange={cambiar('periodo')} className={campo}>
          {PERIODOS.map(p => <option key={p}>{p}</option>)}
        </select>
        <input placeholder="Turno (Mañana, Tarde, Noche)" value={f.turno} onChange={cambiar('turno')} className={campo} />
        <select value={f.dia} onChange={cambiar('dia')} className={campo}>
          {Object.entries(DIAS).map(([n, d]) => <option key={n} value={n}>{d}</option>)}
        </select>
        <input required type="time" value={f.inicio} onChange={cambiar('inicio')} className={campo} title="Inicio" />
        <input required type="time" value={f.fin} onChange={cambiar('fin')} className={campo} title="Fin" />
        <input placeholder="Aula" value={f.aula} onChange={cambiar('aula')} className={campo} />
        <input required placeholder="Materia" value={f.materia} onChange={cambiar('materia')} className={`${campo} col-span-2`} />
        <input placeholder="Profesor" value={f.docente} onChange={cambiar('docente')} className={`${campo} col-span-2`} />
      </div>
      <div className="flex items-center gap-3">
        <button type="submit" className={boton}>Agregar</button>
        {error && <span className="text-xs text-red-400">{error}</span>}
      </div>
    </form>
  )
}

export default function GrillaHorarios() {
  const [bloques, setBloques] = useState(null)
  const [error, setError] = useState(null)
  const [anio, setAnio] = useState(null)
  const [filtro, setFiltro] = useState('')

  useEffect(() => { listarHorarios().then(setBloques).catch(e => setError(errorDe(e, 'No se pudieron cargar los horarios.'))) }, [])

  // año → [bloques de cada comisión]
  const porAnio = useMemo(() => {
    const anios = {}
    const q = filtro.trim().toLowerCase()
    for (const b of bloques ?? []) {
      if (q && ![b.comision, b.materia, b.docente, b.aula].some(x => x?.toLowerCase().includes(q))) continue
      const a = b.anio ?? 0
      ;((anios[a] ??= {})[claveGrupo(b)] ??= []).push(b)
    }
    return anios
  }, [bloques, filtro])

  const anios = Object.keys(porAnio).map(Number).sort((a, b) => (a || 99) - (b || 99))
  const actual = anios.includes(anio) ? anio : anios[0]

  const reemplazar = n => setBloques(prev => prev.map(x => (x.id === n.id ? n : x)))
  const quitar = id => setBloques(prev => prev.filter(x => x.id !== id))
  const agregar = n => { setBloques(prev => [...prev, n]); setAnio(n.anio) }

  if (error) return <p className="text-sm text-red-400">{error}</p>
  if (!bloques) return <p className="text-sm text-[#8b8b93]">Cargando…</p>

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1">
          {anios.map(a => (
            <button key={a} onClick={() => setAnio(a)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
                      a === actual ? 'bg-[#e8592e]/15 text-[#f2894f]' : 'text-[#8b8b93] hover:text-[#f4f4f5] hover:bg-[#17171b]'}`}>
              {a ? `${a}º año` : 'Sin año'}
            </button>
          ))}
        </div>
        <input placeholder="Buscar comisión, materia, profesor o aula…" value={filtro} onChange={e => setFiltro(e.target.value)}
               className={`${campo} !w-auto flex-1 min-w-[200px]`} />
      </div>

      {anios.length === 0 && <p className="text-sm text-[#8b8b93]">No hay horarios{filtro && ' que coincidan'}.</p>}
      {actual !== undefined && Object.entries(porAnio[actual] ?? {})
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([clave, grupo]) => (
          <TablaComision key={clave} bloques={grupo} onCambio={reemplazar} onBorrado={quitar} onCreado={agregar} />
        ))}

      <NuevaComision onCreado={agregar} />
    </div>
  )
}
