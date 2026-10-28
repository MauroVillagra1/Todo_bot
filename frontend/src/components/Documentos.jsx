/**
 * Documentos importantes: notas y formularios para descargar (todos los usuarios).
 * ADMIN además sube (PDF, Word o imagen de hasta 2 MB), corrige la fecha, lo marca como desactualizado
 * (se sigue descargando, con aviso) y borra. El backend lee el contenido y,
 * si no se escribe una descripción, genera una: así el chat sabe para qué sirve cada documento.
 */
import { useEffect, useRef, useState } from 'react'
import { Download, FileText, Trash2, Upload } from 'lucide-react'
import { actualizarDocumento, borrarDocumento, listarDocumentos, subirDocumento, urlDocumento } from '../api'
import { boton, campo, errorDe, tarjeta } from './ui'

const MAX_MB = 2

const fechaCorta = iso => {
  if (!iso) return ''
  const [a, m, d] = iso.slice(0, 10).split('-')
  return `${d}/${m}/${a}`
}

function tamano(bytes) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
}

function Subir({ onSubido }) {
  const [archivo, setArchivo] = useState(null)
  const [nombre, setNombre] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [fecha, setFecha] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)
  const input = useRef(null)

  function elegir(e) {
    const f = e.target.files?.[0]
    setError(null)
    if (f && f.size > MAX_MB * 1024 * 1024) {
      setError(`Pesa ${tamano(f.size)}: el máximo es ${MAX_MB} MB. Comprimilo o exportalo de nuevo a PDF.`)
      e.target.value = ''
      return
    }
    setArchivo(f ?? null)
    if (f && !nombre) setNombre(f.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').trim())
  }

  async function subir(e) {
    e.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      onSubido(await subirDocumento(archivo, nombre, descripcion, fecha))
      setArchivo(null); setNombre(''); setDescripcion(''); setFecha('')
      if (input.current) input.current.value = ''
    } catch (err) {
      setError(errorDe(err, 'No se pudo subir el documento.'))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={subir} className={`${tarjeta} space-y-3`}>
      <div>
        <h3 className="text-sm font-semibold text-[#f4f4f5]">Subir documento</h3>
        <p className="text-xs text-[#8b8b93] mt-0.5">
          PDF, Word o imagen de hasta {MAX_MB} MB. Si dejás la descripción vacía, se genera leyendo el documento.
        </p>
      </div>
      <input ref={input} required type="file" accept=".pdf,.docx,.doc,.jpg,.jpeg,.png" onChange={elegir}
             className="block w-full text-xs text-[#a1a1aa] file:mr-3 file:rounded-lg file:border-0 file:bg-[#1e1e22] file:px-3 file:py-2 file:text-[#f4f4f5]" />
      <input required minLength={3} maxLength={200} placeholder="Nombre (ej. Nota de cambio de comisión)" value={nombre}
             onChange={e => setNombre(e.target.value)} className={campo} />
      <textarea rows={2} maxLength={1000} placeholder="Para qué sirve y cuándo se presenta (opcional)" value={descripcion}
                onChange={e => setDescripcion(e.target.value)} className={campo} />
      <label className="block text-xs text-[#a1a1aa]">
        Fecha del documento (opcional: la que figura en el documento o la de su última versión)
        <input type="date" value={fecha} onChange={e => setFecha(e.target.value)} className={`${campo} mt-1 !w-auto`} />
      </label>
      <div className="flex items-center gap-3">
        <button type="submit" disabled={enviando || !archivo} className={`${boton} flex items-center gap-2`}>
          <Upload size={14} /> {enviando ? 'Subiendo y analizando…' : 'Subir'}
        </button>
        {error && <span className="text-xs text-red-400">{error}</span>}
      </div>
    </form>
  )
}

export default function Documentos({ esAdmin = false }) {
  const [documentos, setDocumentos] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => { listarDocumentos().then(setDocumentos).catch(e => setError(errorDe(e, 'No se pudieron cargar los documentos.'))) }, [])

  async function cambiar(d, cambios) {
    setError(null)
    try {
      const nuevo = await actualizarDocumento(d.id, cambios)
      setDocumentos(prev => prev.map(x => (x.id === nuevo.id ? nuevo : x)))
    } catch (err) { setError(errorDe(err, 'No se pudo guardar')) }
  }

  async function borrar(d) {
    if (!confirm(`¿Borrar «${d.nombre}»? El chat deja de ofrecerlo.`)) return
    try { await borrarDocumento(d.id); setDocumentos(prev => prev.filter(x => x.id !== d.id)) }
    catch (err) { setError(errorDe(err, 'No se pudo borrar')) }
  }

  return (
    <div className="h-full overflow-y-auto bg-[#0a0a0c] text-[#f4f4f5] font-body p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        <div>
          <h2 className="font-display text-xl font-semibold">Documentos</h2>
          <p className="text-sm text-[#8b8b93] mt-1">Notas y formularios para presentar en la facultad. Descargalos, completalos y presentalos en término.</p>
        </div>
        {esAdmin && <Subir onSubido={d => setDocumentos(prev => [...(prev ?? []), d].sort((a, b) => a.nombre.localeCompare(b.nombre)))} />}
        {error && <p className="text-sm text-red-400">{error}</p>}
        {!documentos ? <p className="text-sm text-[#8b8b93]">Cargando…</p> : (
          <ul className="space-y-3">
            {documentos.map(d => (
              <li key={d.id} className={`${tarjeta} flex gap-4 items-start ${d.desactualizado ? 'opacity-70' : ''}`}>
                <div className="w-10 h-10 rounded-xl bg-[#e8592e]/10 text-[#f2894f] flex items-center justify-center flex-shrink-0">
                  <FileText size={18} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-[#f4f4f5]">{d.nombre}</p>
                    {d.desactualizado && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-amber-500/15 text-amber-300">
                        Desactualizado
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-[#a1a1aa] mt-1 whitespace-pre-line">{d.descripcion}</p>
                  <p className="text-[11px] text-[#8b8b93] mt-1.5 flex flex-wrap items-center gap-x-2">
                    <span>
                      Fecha del documento:{' '}
                      {esAdmin ? (
                        <input type="date" value={d.fecha_documento ?? ''} title="Fecha del documento"
                               onChange={e => cambiar(d, { fecha_documento: e.target.value || null })}
                               className="bg-transparent border-b border-[#232327] text-[11px] text-[#c7c7cf] [color-scheme:dark]" />
                      ) : (d.fecha_documento ? fechaCorta(d.fecha_documento) : 'sin fecha')}
                    </span>
                    <span>· Subido el {fechaCorta(d.creado_en)}</span>
                  </p>
                  <p className="text-[11px] text-[#4b4b53] mt-0.5">{d.archivo_nombre} · {tamano(d.tamano)}</p>
                  {esAdmin && (
                    <button onClick={() => cambiar(d, { desactualizado: !d.desactualizado })}
                            className="text-[11px] text-[#f2894f] hover:underline mt-1">
                      {d.desactualizado ? 'Marcar como vigente' : 'Marcar como desactualizado'}
                    </button>
                  )}
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <a href={urlDocumento(d.id)} download className="flex items-center gap-1.5 text-xs font-medium text-[#f2894f] border border-[#e8592e]/30 hover:bg-[#e8592e]/10 rounded-lg px-3 py-1.5">
                    <Download size={13} /> Descargar
                  </a>
                  {esAdmin && (
                    <button onClick={() => borrar(d)} title="Borrar" className="text-[#4b4b53] hover:text-red-400 p-2"><Trash2 size={14} /></button>
                  )}
                </div>
              </li>
            ))}
            {documentos.length === 0 && <p className="text-sm text-[#8b8b93]">Todavía no hay documentos.</p>}
          </ul>
        )}
      </div>
    </div>
  )
}
