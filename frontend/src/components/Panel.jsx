/**
 * Panel — lo que ve cada rango:
 *   MOD   → Cargar: solo el formulario "Cargar información"
 *   SMOD  → Cargar (+ paros: próximos y pasados, sin dos paros el mismo día), Sugerencias,
 *           Horarios, Mesas, Calendario y Usuarios (solo dar o quitar MOD). Los documentos se
 *           suben, editan y borran desde la sección Documentos del menú.
 *   ADMIN → todo lo anterior + Resumen, Reportes, Usuarios (rangos USUARIO/MOD/SMOD y suspensiones),
 *           Historial (cambios filtrables por usuario, sección y fecha; se pueden deshacer) e
 *           Importar (sube un archivo, la IA lo interpreta y se carga en la base tras revisarlo)
 * La UI solo oculta lo que no corresponde: los permisos reales se validan en el backend.
 */
import { useEffect, useState } from 'react'
import {
  aceptarSugerencia, analizarArchivo, borrarSugerencia, autoresDeCambios, cambiarRol, cargarInformacion, cargarParo, confirmarImportacion,
  darDeBajaInformacion, deshacerCambio, levantarSuspension, listarCambios, listarParos, listarReportes,
  listarSugerencias, listarUsuarios, obtenerResumen, rechazarSugerencia, resolverReporte, resumenVotos,
  suspenderUsuario,
} from '../api'
import Calendario from './Calendario'
import GrillaHorarios from './GrillaHorarios'
import GrillaMesas from './GrillaMesas'
import { boton, campo, errorDe, fechaHora, tarjeta, confirmar, pedirTexto } from './ui'

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

/** Consumo del plan gratis de Neon: al pasarse de cualquiera, Neon corta la base. */
function CupoNeon({ neon }) {
  if (!neon) {
    return (
      <div className={`${tarjeta} !p-4 text-xs text-[#8b8b93]`}>
        Cupo de la base: configurá <code>NEON_API_KEY</code> en Vercel para ver el consumo y recibir avisos.
      </div>
    )
  }
  const fecha = iso => (iso ? new Date(iso).toLocaleDateString('es-AR') : '?')
  return (
    <div className={`${tarjeta} ${neon.alerta ? '!border-amber-500/50' : ''}`}>
      <div className="flex items-baseline justify-between mb-3">
        <h3 className="text-sm font-semibold text-[#f4f4f5]">Cupo de la base (Neon, plan gratis)</h3>
        <span className="text-xs text-[#8b8b93]">{fecha(neon.desde)} – {fecha(neon.hasta)}</span>
      </div>
      {neon.alerta && (
        <p className="text-xs text-amber-400 mb-3">
          ⚠ Cerca del límite: si se supera, Neon bloquea la base hasta el próximo período.
        </p>
      )}
      <div className="space-y-3">
        {neon.metricas.map(m => (
          <div key={m.nombre}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-[#a1a1aa]">{m.nombre}</span>
              <span className={m.alerta ? 'text-amber-400 font-medium' : 'text-[#8b8b93]'}>
                {m.usado.toFixed(2)} / {m.limite} {m.unidad} ({m.porcentaje}%)
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-[#1e1e22] overflow-hidden">
              <div className={`h-full rounded-full ${m.porcentaje >= 95 ? 'bg-red-500' : m.alerta ? 'bg-amber-500' : 'bg-emerald-500'}`}
                   style={{ width: `${Math.min(m.porcentaje, 100)}%` }} />
            </div>
          </div>
        ))}
      </div>
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

      <CupoNeon neon={r.neon} />

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

const hoy = () => new Date().toISOString().split('T')[0]

// ── Cargar: información (MOD, SMOD y ADMIN) y paros (SMOD y ADMIN) ───────────

const TIPOS_PARO = [
  ['DOCENTE',    'Docente',              'La facultad está abierta'],
  ['NO_DOCENTE', 'No docente',           'La facultad está cerrada'],
  ['AMBOS',      'Docente y no docente', 'La facultad está cerrada'],
]
const PARO_VACIO = { tipo: '', fecha: hoy(), dias: 1, url: '', detalle: '' }

const TIPOS_INFORMACION = [
  ['AVISO', 'Aviso'], ['INSCRIPCION', 'Inscripción'], ['EXAMEN', 'Examen'], ['CALENDARIO', 'Calendario / horarios'],
  ['TRAMITE', 'Trámite'], ['BECA', 'Beca'], ['CONVOCATORIA', 'Convocatoria / empleo'], ['EVENTO', 'Evento'],
  ['NOTICIA', 'Noticia'], ['OTRO', 'Otro'],
]
const INFO_VACIA = { tipo: '', url: '', contenido: '', sin_vencimiento: false }

/** Formulario con envío, mensaje de resultado y vista previa de lo que quedó cargado. */
function useEnvio(enviarFn, limpiar) {
  const [enviando, setEnviando] = useState(false)
  const [mensaje, setMensaje] = useState(null)
  const [cargada, setCargada] = useState(null)

  async function enviar(e, payload) {
    e.preventDefault()
    setEnviando(true)
    setMensaje(null)
    try {
      const r = await enviarFn(payload)
      setCargada(r)
      setMensaje({ ok: true, texto: `Cargado · ${r.estado} · ya lo puede responder el chat` })
      limpiar()
    } catch (err) {
      setMensaje({ ok: false, texto: errorDe(err, 'No se pudo cargar. Revisá los datos.') })
    } finally {
      setEnviando(false)
    }
  }
  return { enviando, mensaje, cargada, enviar }
}

function Resultado({ mensaje, cargada }) {
  return (
    <>
      {mensaje && <p className={`text-xs ${mensaje.ok ? 'text-emerald-400' : 'text-red-400'}`}>{mensaje.texto}</p>}
      {mensaje?.ok && cargada && (
        <div className="bg-[#141417] border border-[#232327] rounded-xl p-3 text-xs">
          <p className="font-medium text-[#f4f4f5]">{cargada.titulo}</p>
          <p className="text-[#a1a1aa] whitespace-pre-line mt-1">{cargada.contenido}</p>
        </div>
      )}
    </>
  )
}

function FormParo({ onCargado }) {
  const [form, setForm] = useState(PARO_VACIO)
  const cambiar = c => e => setForm(prev => ({ ...prev, [c]: e.target.value }))
  const { enviando, mensaje, cargada, enviar } = useEnvio(cargarParo, () => { setForm(PARO_VACIO); onCargado?.() })
  const elegido = TIPOS_PARO.find(([id]) => id === form.tipo)

  function enviarParo(e) {
    enviar(e, {
      tipo: form.tipo, fecha: form.fecha, dias: Number(form.dias),
      url: form.url.trim() || null, detalle: form.detalle.trim() || null,
    })
  }

  return (
    <form onSubmit={enviarParo} className={`${tarjeta} space-y-3`}>
      <div>
        <h3 className="text-sm font-semibold text-[#f4f4f5]">Avisar un paro</h3>
        <p className="text-xs text-[#8b8b93] mt-0.5">El chat va a responder si hay paro y si la facultad está abierta o cerrada.</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        {TIPOS_PARO.map(([id, nombre, efecto]) => (
          <button key={id} type="button" onClick={() => setForm(prev => ({ ...prev, tipo: id }))}
                  className={`text-left rounded-xl border px-3 py-2 text-sm transition-colors ${form.tipo === id
                    ? 'border-[#e8592e] bg-[#e8592e]/10 text-[#f4f4f5]' : 'border-[#232327] text-[#a1a1aa] hover:border-[#3a3a40]'}`}>
            <span className="block font-medium">{nombre}</span>
            <span className={`block text-xs ${id === 'DOCENTE' ? 'text-emerald-400' : 'text-red-400'}`}>{efecto}</span>
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <label className="block text-xs text-[#a1a1aa]">
          Fecha (primer día)
          <input required type="date" value={form.fecha} onChange={cambiar('fecha')} className={`${campo} mt-1`} />
        </label>
        <label className="block text-xs text-[#a1a1aa]">
          Cantidad de días
          <input required type="number" min={1} max={30} value={form.dias} onChange={cambiar('dias')} className={`${campo} mt-1`} />
        </label>
      </div>
      <input type="url" placeholder="Link al comunicado (opcional)" value={form.url} onChange={cambiar('url')} className={campo} />
      <textarea rows={2} maxLength={2000} placeholder="Aclaraciones (opcional): gremio, si hay mesas de examen, etc."
                value={form.detalle} onChange={cambiar('detalle')} className={campo} />
      <div className="flex items-center gap-3">
        <button type="submit" disabled={enviando || !elegido} className={boton}>{enviando ? 'Cargando…' : 'Avisar paro'}</button>
        {!elegido && <span className="text-xs text-[#8b8b93]">Elegí el tipo de paro</span>}
      </div>
      <Resultado mensaje={mensaje} cargada={cargada} />
    </form>
  )
}

function FormInformacion() {
  const [form, setForm] = useState(INFO_VACIA)
  const cambiar = c => e => setForm(prev => ({ ...prev, [c]: e.target.value }))
  const { enviando, mensaje, cargada, enviar } = useEnvio(cargarInformacion, () => setForm(INFO_VACIA))

  return (
    <form onSubmit={e => enviar(e, { tipo: form.tipo, contenido: form.contenido, url: form.url.trim() || null,
                                     sin_vencimiento: form.sin_vencimiento })}
          className={`${tarjeta} space-y-3`}>
      <div>
        <h3 className="text-sm font-semibold text-[#f4f4f5]">Cargar información</h3>
        <p className="text-xs text-[#8b8b93] mt-0.5">La primera línea del texto se usa como título.</p>
      </div>
      <select required value={form.tipo} onChange={cambiar('tipo')} className={campo}>
        <option value="">Tipo de información…</option>
        {TIPOS_INFORMACION.map(([id, nombre]) => <option key={id} value={id}>{nombre}</option>)}
      </select>
      <input type="url" placeholder="Link (opcional)" value={form.url} onChange={cambiar('url')} className={campo} />
      <textarea required minLength={10} rows={6} placeholder="Información" value={form.contenido}
                onChange={cambiar('contenido')} className={campo} />
      <label className="flex items-center gap-2 text-xs text-[#a1a1aa]">
        <input type="checkbox" checked={form.sin_vencimiento} className="accent-[#e8592e]"
               onChange={e => setForm(prev => ({ ...prev, sin_vencimiento: e.target.checked }))} />
        No vence (reglamentos, requisitos, normativa). Si no, vence con la última fecha del texto o al año.
      </label>
      <button type="submit" disabled={enviando} className={boton}>{enviando ? 'Cargando…' : 'Cargar'}</button>
      <Resultado mensaje={mensaje} cargada={cargada} />
    </form>
  )
}

const fechaCorta = iso => (iso ? new Date(`${iso}T12:00:00`).toLocaleDateString('es-AR') : '?')

function FilaParo({ p, onBaja }) {
  return (
    <li className="py-2 flex items-center justify-between gap-3 text-sm">
      <span className="min-w-0">
        <span className="text-[#f4f4f5]">{p.titulo}</span>
        <span className="block text-xs text-[#8b8b93]">
          {fechaCorta(p.fecha_inicio)}{p.fecha_fin && p.fecha_fin !== p.fecha_inicio ? ` al ${fechaCorta(p.fecha_fin)}` : ''}
        </span>
      </span>
      {onBaja && <button onClick={() => onBaja(p)} className="text-xs text-red-400 hover:underline flex-shrink-0">Dar de baja</button>}
    </li>
  )
}

/** Paros próximos (se muestran arriba del chat) y los que ya pasaron. */
function ListaParos({ version }) {
  const [lista, setLista] = useState(null)
  const [verPasados, setVerPasados] = useState(false)
  const [error, setError] = useState(null)
  useEffect(() => { listarParos().then(setLista).catch(e => setError(errorDe(e, 'No se pudieron cargar los paros.'))) }, [version])

  async function baja(p) {
    if (!(await confirmar('Deja de mostrarse arriba del chat y el chat no lo responde más.',
                          { titulo: `¿Dar de baja «${p.titulo}»?`, boton: 'Sí, dar de baja' }))) return
    try {
      await darDeBajaInformacion(p.informacion_id)
      setLista(prev => ({ ...prev, proximos: prev.proximos.filter(x => x.informacion_id !== p.informacion_id) }))
    } catch (err) { setError(errorDe(err, 'No se pudo dar de baja')) }
  }

  return (
    <div className={tarjeta}>
      <h3 className="text-sm font-semibold text-[#f4f4f5] mb-1">Paros próximos</h3>
      <p className="text-xs text-[#8b8b93]">Se muestran arriba del chat. No se puede cargar otro paro en un día que ya tiene uno.</p>
      {!lista ? <p className="text-sm text-[#8b8b93] mt-2">{error ?? 'Cargando…'}</p> : (
        <>
          {lista.proximos.length === 0
            ? <p className="text-sm text-[#8b8b93] mt-2">No hay paros cargados de hoy en adelante.</p>
            : <ul className="divide-y divide-[#1e1e22]">{lista.proximos.map(p => <FilaParo key={p.informacion_id} p={p} onBaja={baja} />)}</ul>}
          <button onClick={() => setVerPasados(v => !v)} className="text-xs text-[#f2894f] hover:underline mt-3">
            {verPasados ? 'Ocultar' : 'Ver'} paros que ya pasaron ({lista.pasados.length})
          </button>
          {verPasados && (
            <ul className="divide-y divide-[#1e1e22] opacity-80">{lista.pasados.map(p => <FilaParo key={p.informacion_id} p={p} />)}</ul>
          )}
          {error && <p className="text-xs text-red-400 mt-1">{error}</p>}
        </>
      )}
    </div>
  )
}

function Cargar({ conParos }) {
  const [version, setVersion] = useState(0)
  return (
    <div className="space-y-6">
      {conParos && <ListaParos version={version} />}
      {conParos && <FormParo onCargado={() => setVersion(v => v + 1)} />}
      <FormInformacion />
    </div>
  )
}

// ── Sugerencias (SMOD y ADMIN) ────────────────────────────────────────────────

function TarjetaSugerencia({ s, onRevisada }) {
  const [titulo, setTitulo] = useState(s.titulo)
  const [contenido, setContenido] = useState(s.contenido)
  const [motivo, setMotivo] = useState('')
  const [rechazando, setRechazando] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)

  async function revisar(accion) {
    setEnviando(true)
    setError(null)
    try {
      onRevisada(accion === 'aceptar'
        ? await aceptarSugerencia(s.id, { titulo, contenido })
        : await rechazarSugerencia(s.id, motivo))
    } catch (err) {
      setError(errorDe(err, 'No se pudo guardar'))
      setEnviando(false)
    }
  }

  return (
    <div className={`${tarjeta} space-y-3`}>
      <p className="text-xs text-[#8b8b93]">
        {s.autor} · {fechaHora(s.creada_en)}
        {s.url && <> · <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-[#f2894f] hover:underline">ver fuente</a></>}
      </p>
      <input value={titulo} onChange={e => setTitulo(e.target.value)} className={`${campo} font-medium`} />
      <textarea rows={4} value={contenido} onChange={e => setContenido(e.target.value)} className={campo} />
      {rechazando && (
        <input autoFocus placeholder="Motivo del rechazo (lo ve quien la envió)" value={motivo}
               onChange={e => setMotivo(e.target.value)} className={campo} />
      )}
      <div className="flex items-center gap-3">
        {rechazando ? (
          <>
            <button disabled={enviando || motivo.trim().length < 3} onClick={() => revisar('rechazar')}
                    className="bg-red-500/80 hover:bg-red-500 disabled:bg-[#232327] disabled:text-[#4b4b53] text-white px-4 py-2 rounded-xl text-sm font-medium">
              Confirmar rechazo
            </button>
            <button onClick={() => setRechazando(false)} className="text-xs text-[#8b8b93] hover:underline">Cancelar</button>
          </>
        ) : (
          <>
            <button disabled={enviando} onClick={() => revisar('aceptar')} className={boton}>
              {enviando ? 'Guardando…' : 'Aceptar y publicar'}
            </button>
            <button onClick={() => setRechazando(true)} className="text-sm text-red-400 hover:underline">Rechazar</button>
          </>
        )}
        {error && <span className="text-xs text-red-400">{error}</span>}
      </div>
    </div>
  )
}

const FILTROS_SUGERENCIAS = [['PENDIENTE', 'Pendientes'], ['ACEPTADA', 'Aceptadas'], ['RECHAZADA', 'Rechazadas'], ['BORRADA', 'Borradas']]

function Sugerencias() {
  const [estado, setEstado] = useState('PENDIENTE')
  const [lista, setLista] = useState(null)
  const [error, setError] = useState(null)
  const [aviso, setAviso] = useState(null)

  useEffect(() => {
    setLista(null)
    listarSugerencias(estado).then(setLista).catch(e => setError(errorDe(e, 'No se pudieron cargar las sugerencias.')))
  }, [estado])

  function revisada(s) {
    setLista(prev => prev.filter(x => x.id !== s.id))
    setAviso(s.estado === 'ACEPTADA'
      ? `«${s.titulo}» publicada${s.informacion_estado ? ` (${s.informacion_estado})` : ''}: ya la usa el chat.`
      : `«${s.titulo}» rechazada.`)
  }

  async function borrar(s) {
    const motivo = await pedirTexto(`«${s.titulo}» deja de usarse en el chat. Queda en el historial de cambios.`,
                                    { titulo: '¿Borrar esta sugerencia?', placeholder: 'Motivo (obligatorio)' })
    if (!motivo) return
    try {
      await borrarSugerencia(s.id, motivo)
      setLista(prev => prev.filter(x => x.id !== s.id))
      setAviso(`«${s.titulo}» borrada: el chat ya no la usa.`)
    } catch (err) {
      setError(errorDe(err, 'No se pudo borrar'))
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-1">
        {FILTROS_SUGERENCIAS.map(([id, label]) => (
          <button key={id} onClick={() => setEstado(id)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
                    estado === id ? 'bg-[#e8592e]/15 text-[#f2894f]' : 'text-[#8b8b93] hover:text-[#f4f4f5] hover:bg-[#17171b]'}`}>
            {label}
          </button>
        ))}
      </div>
      {aviso && <p className="text-xs text-emerald-400">{aviso}</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}
      {!lista ? <p className="text-sm text-[#8b8b93]">Cargando…</p>
        : lista.length === 0 ? <p className="text-sm text-[#8b8b93]">No hay sugerencias {estado === 'PENDIENTE' ? 'para revisar' : 'en esta lista'}.</p>
        : estado === 'PENDIENTE' ? lista.map(s => <TarjetaSugerencia key={s.id} s={s} onRevisada={revisada} />)
        : (
          <ul className={`${tarjeta} divide-y divide-[#1e1e22]`}>
            {lista.map(s => (
              <li key={s.id} className="py-3 text-sm">
                <p className="font-medium text-[#f4f4f5]">{s.titulo}</p>
                <p className="text-xs text-[#8b8b93] mt-0.5">{s.autor} · revisada {fechaHora(s.revisada_en)}</p>
                <p className="text-xs text-[#a1a1aa] mt-1 whitespace-pre-line">{s.contenido}</p>
                {s.motivo && <p className="text-xs text-red-400 mt-1">Motivo: {s.motivo}</p>}
                {estado === 'ACEPTADA' && (
                  <button onClick={() => borrar(s)} className="text-xs text-red-400 hover:underline mt-2">
                    Borrar (el chat deja de usarla)
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
    </div>
  )
}

// ── Reportes de "dato incorrecto" (solo ADMIN) ────────────────────────────────

function TarjetaReporte({ r, onResuelto }) {
  const [elegidas, setElegidas] = useState(() => r.informaciones.map(i => i.id))
  const [nota, setNota] = useState('')
  const [error, setError] = useState(null)
  const alternar = id => setElegidas(prev => (prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]))

  async function resolver(accion) {
    setError(null)
    try {
      await resolverReporte(r.id, accion, elegidas, nota)
      onResuelto(r.id, accion)
    } catch (err) {
      setError(errorDe(err, 'No se pudo guardar'))
    }
  }

  return (
    <div className={`${tarjeta} space-y-3`}>
      <p className="text-xs text-[#8b8b93]">{r.autor} · {fechaHora(r.creado_en)}</p>
      {r.comentario && <p className="text-sm text-red-300">«{r.comentario}»</p>}
      <div className="text-xs space-y-1">
        <p className="text-[#8b8b93]">Pregunta: <span className="text-[#f4f4f5]">{r.pregunta ?? '—'}</span></p>
        <p className="text-[#8b8b93] whitespace-pre-line">Respuesta: <span className="text-[#c7c7cf]">{r.respuesta}</span></p>
      </div>
      {r.informaciones.length > 0 ? (
        <div className="space-y-1">
          <p className="text-xs text-[#a1a1aa]">Información que usó la respuesta (marcá la que está mal):</p>
          {r.informaciones.map(i => (
            <label key={i.id} className="flex items-start gap-2 text-xs">
              <input type="checkbox" checked={elegidas.includes(i.id)} onChange={() => alternar(i.id)}
                     className="mt-0.5 accent-[#e8592e]" />
              <span>
                {i.url ? <a href={i.url} target="_blank" rel="noopener noreferrer" className="text-[#f2894f] hover:underline">{i.titulo}</a>
                       : <span className="text-[#f4f4f5]">{i.titulo}</span>}
                <span className="text-[#8b8b93]"> · {i.estado} · votos {i.puntaje_votos}
                  {i.reportes > 1 && <span className="text-red-400"> · {i.reportes} reportes</span>}</span>
              </span>
            </label>
          ))}
        </div>
      ) : (
        <p className="text-xs text-[#8b8b93]">Esta respuesta salió de los horarios (no hay información para ocultar): corregila en la grilla.</p>
      )}
      <input placeholder="Nota (opcional)" value={nota} onChange={e => setNota(e.target.value)} className={`${campo} !py-1.5 text-xs`} />
      <div className="flex items-center gap-3">
        {r.informaciones.length > 0 && (
          <button disabled={!elegidas.length} onClick={() => resolver('ocultar')}
                  className="bg-red-500/80 hover:bg-red-500 disabled:bg-[#232327] disabled:text-[#4b4b53] text-white px-4 py-2 rounded-xl text-sm font-medium">
            Sacar del chat
          </button>
        )}
        <button onClick={() => resolver('descartar')} className="text-sm text-[#8b8b93] hover:text-[#f4f4f5] hover:underline">
          Descartar (está bien)
        </button>
        {error && <span className="text-xs text-red-400">{error}</span>}
      </div>
    </div>
  )
}

function Reportes() {
  const [lista, setLista] = useState(null)
  const [votos, setVotos] = useState(null)
  const [error, setError] = useState(null)
  const [aviso, setAviso] = useState(null)

  useEffect(() => {
    listarReportes().then(setLista).catch(e => setError(errorDe(e, 'No se pudieron cargar los reportes.')))
    resumenVotos().then(setVotos).catch(() => {})
  }, [])

  function resuelto(id, accion) {
    setLista(prev => prev.filter(x => x.id !== id))
    setVotos(v => v && { ...v, reportes_pendientes: Math.max(0, v.reportes_pendientes - 1) })
    setAviso(accion === 'ocultar' ? 'Listo: el chat ya no usa esa información.' : 'Reporte descartado.')
  }

  return (
    <div className="space-y-4">
      {votos && (
        <div className="grid grid-cols-3 gap-3">
          <Dato titulo="Me sirvió" valor={votos.positivos} />
          <Dato titulo="No me sirvió / incorrecto" valor={votos.negativos} />
          <Dato titulo="Reportes pendientes" valor={votos.reportes_pendientes} alerta={votos.reportes_pendientes > 0} />
        </div>
      )}
      {aviso && <p className="text-xs text-emerald-400">{aviso}</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}
      {!lista ? <p className="text-sm text-[#8b8b93]">Cargando…</p>
        : lista.length === 0 ? <p className="text-sm text-[#8b8b93]">No hay reportes de datos incorrectos para revisar.</p>
        : lista.map(r => <TarjetaReporte key={r.id} r={r} onResuelto={resuelto} />)}
    </div>
  )
}

// ── Usuarios (SMOD: dar o quitar MOD; ADMIN: rangos y suspensiones) ───────────

const DURACIONES = [['1', '1 día'], ['3', '3 días'], ['7', '7 días'], ['30', '30 días'], ['', 'Permanente']]
const ROLES = { ADMIN: 'Admin', SMOD: 'Super mod', MOD: 'Moderador', USUARIO: 'Usuario' }
const RANGOS_ASIGNABLES = ['USUARIO', 'MOD', 'SMOD']

function estadoCuenta(u) {
  if (!u.activo) return { texto: 'Baneado', color: 'bg-red-500/15 text-red-400' }
  if (u.baneado_hasta && new Date(u.baneado_hasta) > new Date())
    return { texto: `Suspendido hasta ${fechaHora(u.baneado_hasta)}`, color: 'bg-amber-500/15 text-amber-400' }
  return { texto: 'Activo', color: 'bg-emerald-500/15 text-emerald-400' }
}

function FilaUsuario({ u, onCambio, esAdmin: actorAdmin }) {
  const [suspendiendo, setSuspendiendo] = useState(false)
  const [dias, setDias] = useState('7')
  const [motivo, setMotivo] = useState('')
  const [error, setError] = useState(null)
  const estado = estadoCuenta(u)
  const esAdmin = u.rol === 'ADMIN'
  const sancionado = estado.texto !== 'Activo'

  async function hacer(accion) {
    setError(null)
    try {
      onCambio(await accion())
      setSuspendiendo(false)
      setMotivo('')
    } catch (err) {
      setError(errorDe(err, 'No se pudo guardar'))
    }
  }

  return (
    <li className="py-3 text-sm space-y-2">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium text-[#f4f4f5] truncate">{u.nombre}</p>
          <p className="text-xs text-[#8b8b93] truncate">{u.email}</p>
          {sancionado && u.motivo_ban && <p className="text-xs text-[#8b8b93] mt-0.5">Motivo: {u.motivo_ban}</p>}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 text-xs flex-wrap justify-end">
          <span className={`px-2 py-0.5 rounded-full ${estado.color}`}>{estado.texto}</span>
          {esAdmin ? (
            <span className="px-2 py-0.5 rounded-full bg-[#e8592e]/15 text-[#f2894f]">Admin</span>
          ) : actorAdmin ? (
            <select value={u.rol} onChange={e => hacer(() => cambiarRol(u.id, e.target.value))}
                    className={`${campo} !w-auto !py-1 text-xs`} title="Rango">
              {RANGOS_ASIGNABLES.map(r => <option key={r} value={r}>{ROLES[r]}</option>)}
            </select>
          ) : u.rol === 'SMOD' ? (
            <span className="px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-300">Super mod</span>
          ) : (
            <button onClick={() => hacer(() => cambiarRol(u.id, u.rol === 'MOD' ? 'USUARIO' : 'MOD'))}
                    className={`px-2 py-1 rounded-lg border ${u.rol === 'MOD'
                      ? 'border-sky-500/30 text-sky-400 hover:bg-sky-500/10' : 'border-[#232327] text-[#a1a1aa] hover:text-[#f4f4f5]'}`}>
              {u.rol === 'MOD' ? 'Quitar MOD' : 'Hacer MOD'}
            </button>
          )}
          {actorAdmin && !esAdmin && (
            <>
              {sancionado ? (
                <button onClick={() => hacer(() => levantarSuspension(u.id))}
                        className="px-2 py-1 rounded-lg text-emerald-400 hover:bg-emerald-500/10">
                  Levantar sanción
                </button>
              ) : (
                <button onClick={() => setSuspendiendo(v => !v)} className="px-2 py-1 rounded-lg text-red-400 hover:bg-red-500/10">
                  Suspender
                </button>
              )}
            </>
          )}
        </div>
      </div>
      {suspendiendo && (
        <div className="flex flex-wrap items-center gap-2">
          <select value={dias} onChange={e => setDias(e.target.value)} className={`${campo} !w-auto !py-1 text-xs`}>
            {DURACIONES.map(([v, t]) => <option key={t} value={v}>{t}</option>)}
          </select>
          <input autoFocus placeholder="Motivo (lo ve la persona al entrar)" value={motivo} onChange={e => setMotivo(e.target.value)}
                 className={`${campo} !py-1 text-xs flex-1 min-w-[180px]`} />
          <button disabled={motivo.trim().length < 3}
                  onClick={() => hacer(() => suspenderUsuario(u.id, dias ? Number(dias) : null, motivo))}
                  className="text-xs text-red-400 hover:underline disabled:text-[#4b4b53] disabled:no-underline">
            {dias ? 'Suspender' : 'Banear para siempre'}
          </button>
        </div>
      )}
      {error && <p className="text-xs text-red-400">{error}</p>}
    </li>
  )
}

function Usuarios({ esAdmin }) {
  const [usuarios, setUsuarios] = useState(null)
  const [q, setQ] = useState('')
  const [rol, setRol] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    const t = setTimeout(() => {
      listarUsuarios({ q, rol })
        .then(r => setUsuarios(r.items))
        .catch(e => setError(errorDe(e, 'No se pudieron cargar los usuarios.')))
    }, 250)
    return () => clearTimeout(t)
  }, [q, rol])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <input placeholder="Buscar por nombre o email…" value={q} onChange={e => setQ(e.target.value)}
               className={`${campo} !w-auto flex-1 min-w-[200px]`} />
        <select value={rol} onChange={e => setRol(e.target.value)} className={`${campo} !w-auto`}>
          <option value="">Todos los roles</option>
          {Object.entries(ROLES).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
        </select>
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <div className={tarjeta}>
        <h3 className="text-sm font-semibold text-[#f4f4f5] mb-1">Usuarios {usuarios && `(${usuarios.length})`}</h3>
        <p className="text-xs text-[#8b8b93]">
          Las cuentas se crean con el registro (mail institucional; los docentes entran como Moderador).
          {esAdmin ? ' Las cuentas Admin no se modifican desde acá.' : ' Podés dar o quitar el rango de Moderador.'}
        </p>
        {!usuarios ? <p className="text-sm text-[#8b8b93] mt-3">Cargando…</p> : (
          <ul className="divide-y divide-[#1e1e22]">
            {usuarios.map(u => (
              <FilaUsuario key={u.id} u={u} esAdmin={esAdmin}
                           onCambio={nuevo => setUsuarios(prev => prev.map(x => (x.id === nuevo.id ? nuevo : x)))} />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

// ── Historial de cambios (ADMIN) ──────────────────────────────────────────────

const SECCIONES = [
  ['calendario_eventos', 'Calendario'], ['mesas_fechas', 'Mesas: fechas'], ['mesas_materias', 'Mesas: materias'],
  ['horarios_clases', 'Horarios'], ['informacion', 'Información'], ['paros', 'Paros'],
  ['documentos_importantes', 'Documentos'], ['usuarios', 'Usuarios'], ['sugerencias', 'Sugerencias'],
  ['importaciones', 'Importación de archivo'], ['reportes', 'Reportes'], ['fuentes', 'Fuentes'],
]
const ACCIONES = {
  creacion: ['Alta', 'bg-emerald-500/15 text-emerald-400'],
  actualizacion: ['Edición', 'bg-sky-500/15 text-sky-400'],
  eliminacion: ['Borrado', 'bg-red-500/15 text-red-400'],
  baja: ['Baja', 'bg-red-500/15 text-red-400'],
  aceptacion: ['Aceptada', 'bg-emerald-500/15 text-emerald-400'],
  rechazo: ['Rechazada', 'bg-amber-500/15 text-amber-400'],
  deshacer: ['Deshacer', 'bg-violet-500/15 text-violet-300'],
  ocultar: ['Sacado del chat', 'bg-red-500/15 text-red-400'],
  descartar: ['Reporte descartado', 'bg-[#1e1e22] text-[#a1a1aa]'],
  cambio_clave: ['Cambio de contraseña', 'bg-[#1e1e22] text-[#a1a1aa]'],
}
const FILTROS_VACIOS = { usuario_id: '', tabla: '', accion: '', desde: '', hasta: '' }

function Foto({ titulo, datos }) {
  return (
    <div className="min-w-0">
      <p className="text-[#8b8b93] mb-1">{titulo}</p>
      <pre className="bg-[#141417] border border-[#232327] rounded-lg p-2 whitespace-pre-wrap break-words text-[#c7c7cf]">
        {datos ? JSON.stringify(datos, null, 2) : '—'}
      </pre>
    </div>
  )
}

function FilaCambio({ c, onDeshecho }) {
  const [abierto, setAbierto] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)
  const [accion, color] = ACCIONES[c.accion] ?? [c.accion, 'bg-[#1e1e22] text-[#a1a1aa]']

  async function deshacer() {
    if (!(await confirmar(`${c.seccion}: ${c.resumen}`,
                          { titulo: '¿Deshacer este cambio?', boton: 'Sí, deshacer', icono: 'question' }))) return
    setEnviando(true)
    setError(null)
    try { onDeshecho(c.id, await deshacerCambio(c.id)) }
    catch (err) { setError(errorDe(err, 'No se pudo deshacer')) }
    finally { setEnviando(false) }
  }

  return (
    <li className="py-3 text-sm space-y-1">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs text-[#8b8b93]">
            {fechaHora(c.fecha)} · {c.usuario} · <span className={`px-1.5 py-0.5 rounded-full ${color}`}>{accion}</span>
            {' '}· {c.seccion}
          </p>
          <p className={`mt-1 break-words ${c.deshecho_por_id ? 'text-[#8b8b93] line-through' : 'text-[#f4f4f5]'}`}>{c.resumen}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 text-xs">
          <button onClick={() => setAbierto(v => !v)} className="text-[#8b8b93] hover:text-[#f4f4f5]">
            {abierto ? 'Ocultar' : 'Detalle'}
          </button>
          {c.deshecho_por_id ? (
            <span className="px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-300">Deshecho</span>
          ) : c.deshacible && (
            <button disabled={enviando} onClick={deshacer}
                    className="px-2 py-1 rounded-lg border border-[#232327] text-[#f2894f] hover:bg-[#e8592e]/10 disabled:opacity-50">
              {enviando ? 'Deshaciendo…' : 'Deshacer'}
            </button>
          )}
        </div>
      </div>
      {abierto && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
          <Foto titulo="Antes" datos={c.valor_anterior} />
          <Foto titulo="Después" datos={c.valor_nuevo} />
        </div>
      )}
      {error && <p className="text-xs text-red-400">{error}</p>}
    </li>
  )
}

function Historial() {
  const [filtros, setFiltros] = useState(FILTROS_VACIOS)
  const [autores, setAutores] = useState([])
  const [pagina, setPagina] = useState(null)  // { items, total, page }
  const [error, setError] = useState(null)
  const filtrar = c => e => setFiltros(prev => ({ ...prev, [c]: e.target.value }))

  useEffect(() => { autoresDeCambios().then(setAutores).catch(() => {}) }, [])
  useEffect(() => {
    setPagina(null)
    setError(null)
    listarCambios(filtros).then(setPagina).catch(e => setError(errorDe(e, 'No se pudo cargar el historial.')))
  }, [filtros])

  async function cargarMas() {
    try {
      const siguiente = await listarCambios({ ...filtros, page: pagina.page + 1 })
      setPagina(prev => ({ ...siguiente, items: [...prev.items, ...siguiente.items] }))
    } catch (err) { setError(errorDe(err, 'No se pudo cargar más.')) }
  }

  function deshecho(id, nuevo) {
    setPagina(prev => ({
      ...prev, total: prev.total + 1,
      items: [nuevo, ...prev.items.map(c => (c.id === id ? { ...c, deshecho_por_id: nuevo.id, deshacible: false } : c))],
    }))
  }

  return (
    <div className="space-y-4">
      <div className={`${tarjeta} grid grid-cols-1 sm:grid-cols-5 gap-2`}>
        <select value={filtros.usuario_id} onChange={filtrar('usuario_id')} className={campo}>
          <option value="">Todos los usuarios</option>
          {autores.map(a => <option key={a.id} value={a.id}>{a.nombre} ({a.cambios})</option>)}
        </select>
        <select value={filtros.tabla} onChange={filtrar('tabla')} className={campo}>
          <option value="">Todas las secciones</option>
          {SECCIONES.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
        </select>
        <select value={filtros.accion} onChange={filtrar('accion')} className={campo}>
          <option value="">Todas las acciones</option>
          {Object.entries(ACCIONES).map(([v, [t]]) => <option key={v} value={v}>{t}</option>)}
        </select>
        <label className="text-xs text-[#a1a1aa]">Desde
          <input type="date" value={filtros.desde} onChange={filtrar('desde')} className={`${campo} mt-1`} />
        </label>
        <label className="text-xs text-[#a1a1aa]">Hasta
          <input type="date" value={filtros.hasta} onChange={filtrar('hasta')} className={`${campo} mt-1`} />
        </label>
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <div className={tarjeta}>
        <div className="flex items-baseline justify-between">
          <h3 className="text-sm font-semibold text-[#f4f4f5]">Cambios {pagina && `(${pagina.total})`}</h3>
          {filtros !== FILTROS_VACIOS && (
            <button onClick={() => setFiltros(FILTROS_VACIOS)} className="text-xs text-[#8b8b93] hover:underline">Limpiar filtros</button>
          )}
        </div>
        <p className="text-xs text-[#8b8b93]">
          Deshacer vuelve el registro a como estaba. Si hubo un cambio posterior sobre lo mismo, primero deshacé ese.
        </p>
        {!pagina ? <p className="text-sm text-[#8b8b93] mt-3">{error ? '' : 'Cargando…'}</p>
          : pagina.items.length === 0 ? <p className="text-sm text-[#8b8b93] mt-3">No hay cambios con esos filtros.</p>
          : (
            <ul className="divide-y divide-[#1e1e22]">
              {pagina.items.map(c => <FilaCambio key={c.id} c={c} onDeshecho={deshecho} />)}
            </ul>
          )}
        {pagina && pagina.items.length < pagina.total && (
          <button onClick={cargarMas} className="text-xs text-[#f2894f] hover:underline mt-3">Cargar más</button>
        )}
      </div>
    </div>
  )
}

// ── Importar archivos (ADMIN) ─────────────────────────────────────────────────

const DIAS = ['', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']
const METODOS = {
  grilla: ['Grilla de horarios leída del PDF', 'text-emerald-400'],
  ia: ['Interpretado con IA: revisá cada dato antes de guardar', 'text-amber-400'],
  texto: ['Sin IA: se propone el texto como una información', 'text-amber-400'],
}
const rango = (a, b) => `${fechaCorta(a)}${b && b !== a ? ` al ${fechaCorta(b)}` : ''}`
const SECCIONES_IMPORTAR = [
  ['calendario', 'Calendario académico', e => `${rango(e.fecha_inicio, e.fecha_fin)} · ${e.actividad} (${e.categoria})${e.detalle ? ` — ${e.detalle}` : ''}`],
  ['mesas_fechas', 'Fechas de mesas', f => `Mesa ${f.mesa}${f.turno ? ` · turno ${f.turno}` : ''}: cierre ${fechaCorta(f.cierre_inscripcion)} · examen ${fechaCorta(f.fecha_examen)}`],
  ['mesas_materias', 'Materias y tribunales', m => `${m.materia} · Mesa ${m.mesa} · ${m.sede}${m.hora ? ` · ${m.hora}` : ''}${[m.presidente, m.vocal1, m.vocal2].some(Boolean) ? ` · ${[m.presidente, m.vocal1, m.vocal2].filter(Boolean).join(', ')}` : ''}`],
  ['horarios', 'Horarios', h => `${h.comision} · ${DIAS[h.dia]} ${h.inicio}–${h.fin} · ${h.materia}${h.docente ? ` — ${h.docente}` : ''}${h.aula ? ` · aula ${h.aula}` : ''}`],
]
const sinMarca = lista => lista.filter(x => x._ok).map(({ _ok, ...x }) => x)

function Importar() {
  const [archivo, setArchivo] = useState(null)
  const [analizando, setAnalizando] = useState(false)
  const [vista, setVista] = useState(null)
  const [reemplazar, setReemplazar] = useState(true)
  const [guardando, setGuardando] = useState(false)
  const [resultado, setResultado] = useState(null)
  const [error, setError] = useState(null)

  async function analizar(e) {
    e.preventDefault()
    setAnalizando(true)
    setError(null)
    setResultado(null)
    setVista(null)
    try {
      const v = await analizarArchivo(archivo)
      const marcar = lista => lista.map(x => ({ ...x, _ok: true }))
      setVista({ ...v, calendario: marcar(v.calendario), mesas_fechas: marcar(v.mesas_fechas),
                 mesas_materias: marcar(v.mesas_materias), horarios: marcar(v.horarios), informacion: marcar(v.informacion) })
    } catch (err) {
      setError(errorDe(err, 'No se pudo analizar el archivo.'))
    } finally {
      setAnalizando(false)
    }
  }

  const cambiar = (seccion, i, cambios) =>
    setVista(prev => ({ ...prev, [seccion]: prev[seccion].map((x, j) => (j === i ? { ...x, ...cambios } : x)) }))
  const elegidos = vista ? ['calendario', 'mesas_fechas', 'mesas_materias', 'horarios', 'informacion']
    .reduce((n, s) => n + vista[s].filter(x => x._ok).length, 0) : 0

  async function guardar() {
    setGuardando(true)
    setError(null)
    try {
      const r = await confirmarImportacion({
        archivo: vista.archivo, reemplazar_horarios: reemplazar,
        calendario: sinMarca(vista.calendario), mesas_fechas: sinMarca(vista.mesas_fechas),
        mesas_materias: sinMarca(vista.mesas_materias), horarios: sinMarca(vista.horarios),
        informacion: sinMarca(vista.informacion),
      })
      setResultado(r)
      setVista(null)
      setArchivo(null)
    } catch (err) {
      setError(errorDe(err, 'No se pudo guardar. Revisá los datos.'))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={analizar} className={`${tarjeta} space-y-3`}>
        <div>
          <h3 className="text-sm font-semibold text-[#f4f4f5]">Importar un archivo</h3>
          <p className="text-xs text-[#8b8b93] mt-0.5">
            Subí un PDF, Word (.docx), .txt, .csv o .md (hasta 4 MB). Se interpreta y te muestra qué cargaría en el
            calendario, las mesas, los horarios o como información del chat. Nada se guarda hasta que confirmes,
            y la importación entera se puede deshacer desde el Historial.
          </p>
        </div>
        <input type="file" accept=".pdf,.docx,.txt,.csv,.md" onChange={e => setArchivo(e.target.files?.[0] ?? null)}
               className="block text-sm text-[#a1a1aa] file:mr-3 file:rounded-lg file:border-0 file:bg-[#1e1e22] file:px-3 file:py-1.5 file:text-[#f4f4f5]" />
        <button type="submit" disabled={!archivo || analizando} className={boton}>
          {analizando ? 'Analizando (puede tardar hasta un minuto)…' : 'Analizar'}
        </button>
      </form>

      {error && <p className="text-sm text-red-400">{error}</p>}
      {resultado && (
        <p className="text-sm text-emerald-400">
          Listo: {Object.entries(resultado.creados).map(([t, n]) => `${n} en ${t.replaceAll('_', ' ')}`).join(', ') || 'nada'}
          {resultado.reemplazados > 0 && ` (se reemplazaron ${resultado.reemplazados} bloques de horario)`}.
          Ya lo usa el chat. Si algo salió mal, deshacelo en Historial.
        </p>
      )}

      {vista && (
        <div className={`${tarjeta} space-y-4`}>
          <div>
            <h3 className="text-sm font-semibold text-[#f4f4f5]">Vista previa de «{vista.archivo}»</h3>
            <p className={`text-xs mt-0.5 ${METODOS[vista.metodo]?.[1] ?? ''}`}>{METODOS[vista.metodo]?.[0]}</p>
            {vista.avisos.map((a, i) => <p key={i} className="text-xs text-amber-400 mt-1">⚠ {a}</p>)}
          </div>

          {SECCIONES_IMPORTAR.filter(([s]) => vista[s].length > 0).map(([s, titulo, texto]) => (
            <div key={s}>
              <p className="text-xs font-semibold text-[#a1a1aa] mb-1">{titulo} ({vista[s].filter(x => x._ok).length}/{vista[s].length})</p>
              <ul className="space-y-1 max-h-72 overflow-y-auto">
                {vista[s].map((x, i) => (
                  <li key={i}>
                    <label className="flex items-start gap-2 text-xs text-[#c7c7cf]">
                      <input type="checkbox" checked={x._ok} onChange={e => cambiar(s, i, { _ok: e.target.checked })}
                             className="mt-0.5 accent-[#e8592e]" />
                      <span className={x._ok ? '' : 'line-through text-[#8b8b93]'}>{texto(x)}</span>
                    </label>
                  </li>
                ))}
              </ul>
              {s === 'horarios' && (
                <label className="flex items-center gap-2 text-xs text-[#a1a1aa] mt-2">
                  <input type="checkbox" checked={reemplazar} onChange={e => setReemplazar(e.target.checked)} className="accent-[#e8592e]" />
                  Reemplazar los horarios que ya tienen esas comisiones (recomendado)
                </label>
              )}
            </div>
          ))}

          {vista.informacion.length > 0 && (
            <div className="space-y-3">
              <p className="text-xs font-semibold text-[#a1a1aa]">Información para el chat (la primera línea es el título)</p>
              {vista.informacion.map((x, i) => (
                <div key={i} className={`space-y-2 border border-[#1e1e22] rounded-xl p-3 ${x._ok ? '' : 'opacity-50'}`}>
                  <div className="flex flex-wrap items-center gap-3 text-xs">
                    <label className="flex items-center gap-2 text-[#a1a1aa]">
                      <input type="checkbox" checked={x._ok} onChange={e => cambiar('informacion', i, { _ok: e.target.checked })}
                             className="accent-[#e8592e]" />
                      Cargar
                    </label>
                    <select value={x.tipo} onChange={e => cambiar('informacion', i, { tipo: e.target.value })}
                            className={`${campo} !w-auto !py-1 text-xs`}>
                      {TIPOS_INFORMACION.map(([id, nombre]) => <option key={id} value={id}>{nombre}</option>)}
                    </select>
                    <label className="flex items-center gap-2 text-[#a1a1aa]">
                      <input type="checkbox" checked={x.sin_vencimiento} className="accent-[#e8592e]"
                             onChange={e => cambiar('informacion', i, { sin_vencimiento: e.target.checked })} />
                      No vence
                    </label>
                  </div>
                  <textarea rows={5} value={x.contenido} onChange={e => cambiar('informacion', i, { contenido: e.target.value })}
                            className={`${campo} text-xs`} />
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center gap-3">
            <button onClick={guardar} disabled={guardando || elegidos === 0} className={boton}>
              {guardando ? 'Guardando…' : `Guardar ${elegidos} dato${elegidos === 1 ? '' : 's'}`}
            </button>
            <button onClick={() => setVista(null)} className="text-sm text-[#8b8b93] hover:underline">Descartar</button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Panel ─────────────────────────────────────────────────────────────────────

export default function Panel({ usuario }) {
  const rol = usuario?.rol
  const esAdmin = rol === 'ADMIN'
  const esSmod = esAdmin || rol === 'SMOD'
  const tabs = [
    ...(esAdmin ? [{ id: 'resumen', label: 'Resumen' }] : []),
    { id: 'cargar', label: 'Cargar' },
    ...(esSmod ? [{ id: 'sugerencias', label: 'Sugerencias' }] : []),
    ...(esAdmin ? [{ id: 'reportes', label: 'Reportes' }] : []),
    ...(esSmod ? [{ id: 'horarios', label: 'Horarios' }, { id: 'mesas', label: 'Mesas' },
                  { id: 'calendario', label: 'Calendario' }, { id: 'usuarios', label: 'Usuarios' }] : []),
    ...(esAdmin ? [{ id: 'historial', label: 'Historial' }, { id: 'importar', label: 'Importar' }] : []),
  ]
  const [tab, setTab] = useState(tabs[0].id)

  return (
    <div className="flex flex-col h-full bg-[#0a0a0c] text-[#f4f4f5] font-body [color-scheme:dark]">
      <div className="bg-[#0d0d10] border-b border-[#1e1e22] px-6 pt-4">
        <h2 className="font-display text-base font-semibold text-[#f4f4f5]">{esAdmin ? 'Panel de administración' : 'Panel'}</h2>
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
        <div className={`${['horarios', 'mesas', 'calendario', 'historial', 'importar'].includes(tab) ? 'max-w-6xl' : 'max-w-3xl'} mx-auto`}>
          {tab === 'resumen' && esAdmin && <Resumen />}
          {tab === 'cargar' && <Cargar conParos={esSmod} />}
          {tab === 'sugerencias' && esSmod && <Sugerencias />}
          {tab === 'reportes' && esAdmin && <Reportes />}
          {tab === 'horarios' && esSmod && <GrillaHorarios />}
          {tab === 'mesas' && esSmod && <GrillaMesas />}
          {tab === 'calendario' && esSmod && <Calendario editable />}
          {tab === 'usuarios' && esSmod && <Usuarios esAdmin={esAdmin} />}
          {tab === 'historial' && esAdmin && <Historial />}
          {tab === 'importar' && esAdmin && <Importar />}
        </div>
      </div>
    </div>
  )
}
