/**
 * Panel — MOD y ADMIN.
 *   Resumen   → estado del sistema y métricas (ADM-01, OBS-01)
 *   Fuentes   → carga manual de Instagram/WhatsApp; ADMIN además activa/desactiva y ajusta confiabilidad
 *   Usuarios  → solo ADMIN: crear cuentas, cambiar rol, activar/desactivar, resetear contraseña
 * La UI solo oculta lo que no corresponde: los permisos reales se validan en el backend.
 */
import { useEffect, useState } from 'react'
import {
  actualizarFuente, actualizarUsuario, cargarPublicacionManual, crearUsuario,
  listarFuentes, listarUsuarios, obtenerResumen,
} from '../api'

const campo = 'w-full bg-[#141417] border border-[#232327] rounded-xl px-3 py-2 text-sm text-[#f4f4f5] placeholder-[#4b4b53] focus:outline-none focus:border-[#e8592e]/50 transition-colors'
const tarjeta = 'bg-[#0d0d10] border border-[#1e1e22] rounded-2xl p-5'
const boton = 'bg-[#e8592e] hover:bg-[#f2703f] disabled:bg-[#232327] disabled:text-[#4b4b53] text-white px-4 py-2 rounded-xl text-sm font-medium transition-colors'

function fechaHora(iso) {
  return iso ? new Date(iso).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' }) : 'nunca'
}

function errorDe(err, porDefecto) {
  const detalle = err.response?.data?.detail
  if (typeof detalle === 'string') return detalle
  if (Array.isArray(detalle)) return detalle.map(d => d.msg).join(' · ')
  return porDefecto
}

// ── Resumen ───────────────────────────────────────────────────────────────────

const METRICAS = [
  ['consultas', 'Consultas'],
  ['cache_hits', 'Respondidas desde caché'],
  ['llamadas_llm', 'Llamadas a la IA'],
  ['consultas_sin_evidencia', 'Sin información'],
  ['errores_llm', 'Fallas de la IA'],
  ['documentos_procesados', 'Documentos nuevos'],
  ['duplicados_descartados', 'Duplicados descartados'],
  ['errores_ingesta', 'Errores de ingesta'],
]

function Dato({ titulo, valor, detalle, alerta }) {
  return (
    <div className={`${tarjeta} !p-4`}>
      <p className="text-xs text-[#8b8b93]">{titulo}</p>
      <p className={`text-2xl font-semibold mt-1 ${alerta ? 'text-red-400' : 'text-[#f4f4f5]'}`}>{valor}</p>
      {detalle && <p className="text-xs text-[#8b8b93] mt-0.5">{detalle}</p>}
    </div>
  )
}

function Resumen() {
  const [r, setR] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => { obtenerResumen().then(setR).catch(e => setError(errorDe(e, 'No se pudo cargar el resumen.'))) }, [])

  if (error) return <p className="text-sm text-red-400">{error}</p>
  if (!r) return <p className="text-sm text-[#8b8b93]">Cargando…</p>

  const total = m => Object.values(r.metricas[m] ?? {}).reduce((a, b) => a + b, 0)
  const info = r.informacion

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <Dato titulo="Fuentes activas" valor={`${r.fuentes.activas} / ${r.fuentes.total}`}
              detalle={`Última actualización: ${fechaHora(r.fuentes.ultima_actualizacion)}`} />
        <Dato titulo="Documentos" valor={r.documentos_procesados.publicaciones + r.documentos_procesados.pdfs}
              detalle={`${r.documentos_procesados.publicaciones} publicaciones · ${r.documentos_procesados.pdfs} PDFs`} />
        <Dato titulo="Información" valor={info.total} detalle={`${info.nueva_ultimos_7_dias} nueva en 7 días`} />
        <Dato titulo="No confirmada" valor={info.no_confirmada} />
        <Dato titulo="Contradicciones" valor={info.contradicciones} alerta={info.contradicciones > 0} />
        <Dato titulo="Usuarios" valor={r.usuarios.total} detalle={`${r.usuarios.activos} activos`} />
      </div>

      <div className={tarjeta}>
        <h3 className="text-sm font-semibold text-[#f4f4f5] mb-3">Últimos 14 días</h3>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          {METRICAS.map(([clave, nombre]) => (
            <div key={clave} className="flex justify-between border-b border-[#1e1e22] py-1">
              <dt className="text-[#a1a1aa]">{nombre}</dt>
              <dd className="font-medium text-[#f4f4f5]">{total(clave)}</dd>
            </div>
          ))}
        </dl>
      </div>

      <div className={tarjeta}>
        <h3 className="text-sm font-semibold text-[#f4f4f5] mb-3">Estado de la ingesta</h3>
        <ul className="divide-y divide-[#1e1e22] text-sm">
          {r.ingesta.ultimas_corridas.map(c => (
            <li key={c.fuente} className="py-2 flex justify-between gap-3">
              <span className="text-[#f4f4f5]">{c.fuente}</span>
              <span className="text-xs text-[#8b8b93]">
                {fechaHora(c.inicio)} · {c.nuevos} nuevos ·{' '}
                <span className={c.estado === 'ERROR' ? 'text-red-400 font-medium' : 'text-emerald-400'}>{c.estado}</span>
              </span>
            </li>
          ))}
        </ul>
        {r.ingesta.errores_ultimos_7_dias.length > 0 && (
          <div className="mt-3 text-xs text-red-400 space-y-1">
            {r.ingesta.errores_ultimos_7_dias.map((e, i) => (
              <p key={i}>{e.fuente} ({fechaHora(e.inicio)}): {e.detalle.map(d => d.error).join(' · ')}</p>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Fuentes ───────────────────────────────────────────────────────────────────

const hoy = () => new Date().toISOString().split('T')[0]
const POSTEO_VACIO = { url: '', titulo: '', contenido: '', fecha_publicacion: hoy() }
const RESULTADOS = {
  nuevo:       'Publicación cargada',
  actualizado: 'Se guardó como versión nueva de la publicación anterior',
  duplicado:   'Esa publicación ya estaba cargada con el mismo texto',
}

function CargaManual({ fuentes, onCargada }) {
  const manuales = fuentes.filter(f => f.carga_manual)
  const [fuenteId, setFuenteId] = useState('')
  const [form, setForm] = useState(POSTEO_VACIO)
  const [enviando, setEnviando] = useState(false)
  const [mensaje, setMensaje] = useState(null)
  const cambiar = c => e => setForm(prev => ({ ...prev, [c]: e.target.value }))

  async function enviar(e) {
    e.preventDefault()
    setEnviando(true)
    setMensaje(null)
    try {
      const r = await cargarPublicacionManual(fuenteId, form)
      setMensaje({ ok: true, texto: `${RESULTADOS[r.resultado]} · ${r.tipo ?? ''} · ${r.estado ?? ''}` })
      if (r.resultado !== 'duplicado') setForm(POSTEO_VACIO)
      onCargada()
    } catch (err) {
      setMensaje({ ok: false, texto: errorDe(err, 'Revisá los datos: link válido, título y texto de al menos 10 caracteres.') })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={enviar} className={`${tarjeta} space-y-3`}>
      <div>
        <h3 className="text-sm font-semibold text-[#f4f4f5]">Cargar publicación de Instagram o WhatsApp</h3>
        <p className="text-xs text-[#8b8b93] mt-0.5">
          Copiá el texto del posteo y su link. Queda con el estado que corresponde a la confiabilidad de la fuente.
        </p>
      </div>
      <select required value={fuenteId} onChange={e => setFuenteId(e.target.value)} className={campo}>
        <option value="">Elegí la fuente…</option>
        {manuales.map(f => <option key={f.id} value={f.id}>{f.nombre} ({f.confiabilidad_base}%)</option>)}
      </select>
      <input required type="url" placeholder="Link al posteo" value={form.url} onChange={cambiar('url')} className={campo} />
      <input required minLength={3} placeholder="Título" value={form.titulo} onChange={cambiar('titulo')} className={campo} />
      <textarea required minLength={10} rows={6} placeholder="Texto del posteo" value={form.contenido}
                onChange={cambiar('contenido')} className={campo} />
      <label className="block text-xs text-[#a1a1aa]">
        Fecha de publicación
        <input required type="date" value={form.fecha_publicacion} onChange={cambiar('fecha_publicacion')} className={`${campo} mt-1`} />
      </label>
      <div className="flex items-center gap-3">
        <button type="submit" disabled={enviando} className={boton}>{enviando ? 'Cargando…' : 'Cargar'}</button>
        {mensaje && <span className={`text-xs ${mensaje.ok ? 'text-emerald-400' : 'text-red-400'}`}>{mensaje.texto}</span>}
      </div>
    </form>
  )
}

function FilaFuente({ fuente, esAdmin, onCambio }) {
  const [confiabilidad, setConfiabilidad] = useState(fuente.confiabilidad_base)
  const [error, setError] = useState(null)

  async function guardar(cambios) {
    setError(null)
    try { onCambio(await actualizarFuente(fuente.id, cambios)) }
    catch (err) { setError(errorDe(err, 'No se pudo guardar')) }
  }

  return (
    <li className="py-3 text-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <a href={fuente.url} target="_blank" rel="noopener noreferrer" className="font-medium text-[#f4f4f5] hover:underline">
            {fuente.nombre}
          </a>
          <p className="text-xs text-[#8b8b93]">
            {fuente.carga_manual ? 'Carga manual' : `Automática · última revisión: ${fechaHora(fuente.ultima_revision)}`}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 text-xs">
          {esAdmin ? (
            <>
              <input type="number" min={0} max={100} value={confiabilidad}
                     onChange={e => setConfiabilidad(Number(e.target.value))}
                     onBlur={() => confiabilidad !== fuente.confiabilidad_base && guardar({ confiabilidad_base: confiabilidad })}
                     className="w-16 bg-[#141417] border border-[#232327] text-[#f4f4f5] rounded-lg px-2 py-1" title="Confiabilidad base (%)" />
              <button onClick={() => guardar({ activa: !fuente.activa })}
                      className={`px-2 py-1 rounded-full ${fuente.activa ? 'bg-emerald-500/15 text-emerald-400' : 'bg-[#1e1e22] text-[#8b8b93]'}`}>
                {fuente.activa ? 'Activa' : 'Inactiva'}
              </button>
            </>
          ) : (
            <>
              <span className="text-[#8b8b93]">{fuente.confiabilidad_base}%</span>
              <span className={`px-2 py-0.5 rounded-full ${fuente.activa ? 'bg-emerald-500/15 text-emerald-400' : 'bg-[#1e1e22] text-[#8b8b93]'}`}>
                {fuente.activa ? 'Activa' : 'Inactiva'}
              </span>
            </>
          )}
        </div>
      </div>
      {error && <p className="text-xs text-red-400 mt-1">{error}</p>}
    </li>
  )
}

function Fuentes({ esAdmin }) {
  const [fuentes, setFuentes] = useState([])
  const [error, setError] = useState(null)
  const cargar = () => listarFuentes().then(setFuentes).catch(e => setError(errorDe(e, 'No se pudieron cargar las fuentes.')))
  useEffect(() => { cargar() }, [])

  return (
    <div className="space-y-6">
      {error && <p className="text-sm text-red-400">{error}</p>}
      <CargaManual fuentes={fuentes} onCargada={cargar} />
      <div className={tarjeta}>
        <h3 className="text-sm font-semibold text-[#f4f4f5] mb-1">Fuentes</h3>
        {esAdmin && <p className="text-xs text-[#8b8b93]">Cambiá la confiabilidad (0-100) o activá/desactivá con un clic.</p>}
        <ul className="divide-y divide-[#1e1e22]">
          {fuentes.map(f => (
            <FilaFuente key={f.id} fuente={f} esAdmin={esAdmin}
                        onCambio={nueva => setFuentes(prev => prev.map(x => (x.id === nueva.id ? nueva : x)))} />
          ))}
        </ul>
      </div>
    </div>
  )
}

// ── Usuarios (ADMIN) ──────────────────────────────────────────────────────────

const USUARIO_VACIO = { nombre: '', email: '', rol: 'MIEMBRO', password: '' }

function FilaUsuario({ u, yo, onCambio }) {
  const [password, setPassword] = useState('')
  const [mensaje, setMensaje] = useState(null)

  async function guardar(cambios, ok) {
    setMensaje(null)
    try {
      onCambio(await actualizarUsuario(u.id, cambios))
      if (ok) setMensaje({ ok: true, texto: ok })
    } catch (err) {
      setMensaje({ ok: false, texto: errorDe(err, 'No se pudo guardar') })
    }
  }

  return (
    <li className="py-3 text-sm space-y-2">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium text-[#f4f4f5] truncate">{u.nombre}{u.id === yo && ' (vos)'}</p>
          <p className="text-xs text-[#8b8b93] truncate">{u.email}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <select value={u.rol} disabled={u.id === yo} onChange={e => guardar({ rol: e.target.value })}
                  className="bg-[#141417] border border-[#232327] text-[#f4f4f5] rounded-lg px-2 py-1 text-xs">
            <option>MIEMBRO</option><option>MOD</option><option>ADMIN</option>
          </select>
          <button disabled={u.id === yo} onClick={() => guardar({ activo: !u.activo })}
                  className={`px-2 py-1 rounded-full text-xs ${u.activo ? 'bg-emerald-500/15 text-emerald-400' : 'bg-[#1e1e22] text-[#8b8b93]'}`}>
            {u.activo ? 'Activo' : 'Inactivo'}
          </button>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <input type="password" placeholder="Nueva contraseña (mín. 8, con un número)" value={password}
               onChange={e => setPassword(e.target.value)} className={`${campo} !py-1 text-xs`} />
        <button disabled={password.length < 8}
                onClick={() => guardar({ password }, 'Contraseña actualizada').then(() => setPassword(''))}
                className="text-xs text-[#f2894f] hover:underline disabled:text-[#4b4b53] disabled:no-underline whitespace-nowrap">
          Resetear
        </button>
      </div>
      {mensaje && <p className={`text-xs ${mensaje.ok ? 'text-emerald-400' : 'text-red-400'}`}>{mensaje.texto}</p>}
    </li>
  )
}

function Usuarios({ yo }) {
  const [usuarios, setUsuarios] = useState([])
  const [form, setForm] = useState(USUARIO_VACIO)
  const [mensaje, setMensaje] = useState(null)
  const cambiar = c => e => setForm(prev => ({ ...prev, [c]: e.target.value }))
  useEffect(() => { listarUsuarios().then(setUsuarios).catch(e => setMensaje({ ok: false, texto: errorDe(e, 'No se pudieron cargar los usuarios.') })) }, [])

  async function crear(e) {
    e.preventDefault()
    setMensaje(null)
    try {
      const nuevo = await crearUsuario(form)
      setUsuarios(prev => [...prev, nuevo])
      setForm(USUARIO_VACIO)
      setMensaje({ ok: true, texto: `Cuenta creada para ${nuevo.email}` })
    } catch (err) {
      setMensaje({ ok: false, texto: errorDe(err, 'No se pudo crear la cuenta') })
    }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={crear} className={`${tarjeta} space-y-3`}>
        <div>
          <h3 className="text-sm font-semibold text-[#f4f4f5]">Crear cuenta</h3>
          <p className="text-xs text-[#8b8b93] mt-0.5">Solo correos institucionales. Pasale la contraseña a la persona por un medio seguro.</p>
        </div>
        <input required minLength={2} placeholder="Nombre" value={form.nombre} onChange={cambiar('nombre')} className={campo} />
        <input required type="email" placeholder="usuario@alu.frt.utn.edu.ar o @doc.frt.utn.edu.ar" value={form.email} onChange={cambiar('email')} className={campo} />
        <div className="flex gap-2">
          <select value={form.rol} onChange={cambiar('rol')} className={campo}>
            <option>MIEMBRO</option><option>MOD</option><option>ADMIN</option>
          </select>
          <input required minLength={8} type="password" placeholder="Contraseña inicial" value={form.password}
                 onChange={cambiar('password')} className={campo} />
        </div>
        <div className="flex items-center gap-3">
          <button type="submit" className={boton}>Crear</button>
          {mensaje && <span className={`text-xs ${mensaje.ok ? 'text-emerald-400' : 'text-red-400'}`}>{mensaje.texto}</span>}
        </div>
      </form>

      <div className={tarjeta}>
        <h3 className="text-sm font-semibold text-[#f4f4f5] mb-1">Usuarios ({usuarios.length})</h3>
        <ul className="divide-y divide-[#1e1e22]">
          {usuarios.map(u => (
            <FilaUsuario key={u.id} u={u} yo={yo}
                         onCambio={nuevo => setUsuarios(prev => prev.map(x => (x.id === nuevo.id ? nuevo : x)))} />
          ))}
        </ul>
      </div>
    </div>
  )
}

// ── Panel ─────────────────────────────────────────────────────────────────────

export default function Panel({ usuario }) {
  const esAdmin = usuario?.rol === 'ADMIN'
  const tabs = [
    { id: 'resumen', label: 'Resumen' },
    { id: 'fuentes', label: 'Fuentes' },
    ...(esAdmin ? [{ id: 'usuarios', label: 'Usuarios' }] : []),
  ]
  const [tab, setTab] = useState('resumen')

  return (
    <div className="flex flex-col h-full bg-[#0a0a0c] text-[#f4f4f5] font-body [color-scheme:dark]">
      <div className="bg-[#0d0d10] border-b border-[#1e1e22] px-6 pt-4">
        <h2 className="font-display text-base font-semibold text-[#f4f4f5]">Panel de administración</h2>
        <div className="flex gap-1 mt-2 overflow-x-auto">
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
                    className={`px-4 py-2 text-sm font-medium border-b-2 whitespace-nowrap ${
                      tab === t.id ? 'border-[#e8592e] text-[#f2894f]' : 'border-transparent text-[#8b8b93] hover:text-[#f4f4f5]'}`}>
              {t.label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto">
          {tab === 'resumen' && <Resumen />}
          {tab === 'fuentes' && <Fuentes esAdmin={esAdmin} />}
          {tab === 'usuarios' && esAdmin && <Usuarios yo={usuario.id} />}
        </div>
      </div>
    </div>
  )
}
