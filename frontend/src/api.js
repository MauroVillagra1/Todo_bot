/**
 * Cliente HTTP centralizado.
 * La URL base se toma de la variable de entorno VITE_API_URL.
 * Si no está definida, usa el proxy de Vite (/api → localhost:8000).
 */
import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

// ── Sesión (JWT) ──────────────────────────────────────────────────────────────
// El access token (15 min) vive solo en memoria. El refresh token (7 días) se guarda en
// localStorage para no perder la sesión al recargar; cuando el access vence, el
// interceptor pide uno nuevo con el refresh y repite el pedido sin que el usuario lo note.
const CLAVE_REFRESH = 'utnia_refresh'
let alVencerSesion = () => {}

function leerRefresh() {
  try { return localStorage.getItem(CLAVE_REFRESH) } catch { return null }
}

/** Guarda la sesión que devuelven login, registro y refresh ({ access_token, refresh_token }). */
export function guardarSesion({ access_token, refresh_token }) {
  api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
  try { localStorage.setItem(CLAVE_REFRESH, refresh_token) } catch { /* modo privado: solo esta pestaña */ }
}

export function borrarSesion() {
  delete api.defaults.headers.common['Authorization']
  try { localStorage.removeItem(CLAVE_REFRESH) } catch { /* nada guardado */ }
}

/** App avisa qué hacer cuando la sesión ya no se puede renovar (volver al login). */
export function alVencer(callback) {
  alVencerSesion = callback
}

let renovando = null  // un solo pedido de renovación aunque fallen varios a la vez

/** Con el refresh guardado pide un par nuevo. Devuelve { access_token, refresh_token, usuario } o null. */
export async function renovarSesion() {
  const refresh = leerRefresh()
  if (!refresh) return null
  renovando ??= axios.post(`${BASE_URL}/api/v1/auth/refresh`, { refresh_token: refresh })
    .then(({ data }) => { guardarSesion(data); return data })
    .catch(() => { borrarSesion(); return null })
    .finally(() => { renovando = null })
  return renovando
}

api.interceptors.response.use(
  respuesta => respuesta,
  async error => {
    const pedido = error.config
    const esDeSesion = pedido?.url?.includes('/api/v1/auth/')
    if (error.response?.status === 401 && pedido && !pedido._reintento && !esDeSesion) {
      pedido._reintento = true
      const sesion = await renovarSesion()
      if (sesion) {
        pedido.headers['Authorization'] = `Bearer ${sesion.access_token}`
        return api(pedido)
      }
      alVencerSesion()
    }
    return Promise.reject(error)
  },
)

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function login(email, password) {
  const { data } = await api.post('/api/v1/auth/login', { email, password })
  return data  // { access_token, refresh_token, token_type, usuario }
}

/** Cierra la sesión en el servidor (revoca los tokens en todos los dispositivos) y en este navegador. */
export async function cerrarSesion() {
  try { await api.post('/api/v1/auth/logout') } catch { /* sin conexión o ya vencida: igual se borra */ }
  borrarSesion()
}

/** Paso 1 del registro: manda un código de 6 dígitos al mail institucional. */
export async function solicitarRegistro(nombre, email, password) {
  const { data } = await api.post('/api/v1/auth/registro', { nombre, email, password })
  return data  // { mensaje }
}

/** Paso 2: con el código correcto se crea la cuenta y queda logueado. */
export async function verificarRegistro(email, codigo) {
  const { data } = await api.post('/api/v1/auth/registro/verificar', { email, codigo })
  return data  // { access_token, refresh_token, token_type, usuario }
}

export async function solicitarRecuperacion(email) {
  const { data } = await api.post('/api/v1/auth/recuperar', { email })
  return data  // { mensaje }
}

export async function confirmarRecuperacion(email, codigo, password) {
  const { data } = await api.post('/api/v1/auth/recuperar/confirmar', { email, codigo, password })
  return data  // { mensaje }
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export async function enviarMensaje(mensaje, conversacion_id = null) {
  const { data } = await api.post('/api/v1/chat/', { mensaje, conversacion_id })
  return data  // { respuesta, conversacion_id, fuentes }
}

/** 👍 (valor 1) o 👎 (valor -1, motivo NO_SIRVE | INCORRECTO). Con NO_SIRVE trae `alternativa`. */
export async function votarRespuesta(mensajeId, valor, motivo = null, comentario = null) {
  const { data } = await api.post(`/api/v1/chat/mensajes/${mensajeId}/voto`, { valor, motivo, comentario })
  return data  // { valor, motivo, alternativa: { respuesta, mensaje_id, fuentes, ... } | null }
}

// ── Reportes de "dato incorrecto" (MOD y ADMIN) ───────────────────────────────

export async function listarReportes() {
  const { data } = await api.get('/api/v1/reportes/')
  return data
}

export async function resolverReporte(id, accion, informacionIds = [], nota = '') {
  await api.post(`/api/v1/reportes/${id}/resolver`, { accion, informacion_ids: informacionIds, nota })
}

export async function resumenVotos() {
  const { data } = await api.get('/api/v1/reportes/resumen')
  return data  // { positivos, negativos, reportes_pendientes }
}

// ── Fuentes (MOD y ADMIN) ─────────────────────────────────────────────────────

export async function listarFuentes() {
  const { data } = await api.get('/api/v1/fuentes/')
  return data  // [{ id, nombre, tipo, url, confiabilidad_base, activa, ultima_revision, carga_manual }]
}

/** Carga a mano un posteo autorizado de Instagram o de un canal de WhatsApp. */
/** Dato cargado por un MOD: { tipo, contenido, url? }. Queda CONFIRMADO y buscable en el chat. */
export async function cargarInformacion(payload) {
  const { data } = await api.post('/api/v1/informacion', payload)
  return data  // { informacion_id, titulo, contenido, tipo, estado, fecha_fin }
}

/** Aviso de paro: { tipo: DOCENTE | NO_DOCENTE | AMBOS, fecha, dias, url?, detalle? }. */
export async function cargarParo(payload) {
  const { data } = await api.post('/api/v1/informacion/paro', payload)
  return data
}

export async function cargarPublicacionManual(fuenteId, payload) {
  const { data } = await api.post(`/api/v1/fuentes/${fuenteId}/publicaciones`, payload)
  return data  // { resultado, publicacion_id, informacion_id, estado, tipo }
}

/** Activar/desactivar una fuente o cambiar su confiabilidad (solo ADMIN). */
export async function actualizarFuente(fuenteId, cambios) {
  const { data } = await api.patch(`/api/v1/fuentes/${fuenteId}`, cambios)
  return data
}

// ── Panel (MOD y ADMIN) ───────────────────────────────────────────────────────

export async function obtenerResumen() {
  const { data } = await api.get('/api/v1/admin/resumen')
  return data
}

// ── Usuarios (solo ADMIN) ─────────────────────────────────────────────────────

export async function listarUsuarios({ q = '', rol = '' } = {}) {
  const params = new URLSearchParams({ page: 1, page_size: 200, q })
  if (rol) params.set('rol', rol)
  const { data } = await api.get(`/api/v1/usuarios/?${params}`)
  return data  // { items: [{ id, nombre, email, rol, activo, baneado_hasta, motivo_ban, ... }], total }
}

/** Dar o quitar el rango de moderador: rol = 'MOD' | 'MIEMBRO'. */
export async function cambiarRol(id, rol) {
  const { data } = await api.patch(`/api/v1/usuarios/${id}`, { rol })
  return data
}

/** dias = null → baneo permanente. */
export async function suspenderUsuario(id, dias, motivo) {
  const { data } = await api.post(`/api/v1/usuarios/${id}/ban`, { dias, motivo })
  return data
}

export async function levantarSuspension(id) {
  const { data } = await api.delete(`/api/v1/usuarios/${id}/ban`)
  return data
}

// ── Sugerencias ───────────────────────────────────────────────────────────────

/** Cualquier usuario propone un dato; queda PENDIENTE hasta que un MOD lo revise. */
export async function crearSugerencia(payload) {
  const { data } = await api.post('/api/v1/sugerencias/', payload)  // { titulo, contenido, url? }
  return data
}

export async function misSugerencias() {
  const { data } = await api.get('/api/v1/sugerencias/mias')
  return data  // [{ id, titulo, contenido, url, estado, motivo, creada_en, revisada_en, informacion_estado }]
}

/** MOD y ADMIN */
export async function listarSugerencias(estado = 'PENDIENTE') {
  const { data } = await api.get(`/api/v1/sugerencias/?estado=${estado}`)
  return data
}

export async function aceptarSugerencia(id, cambios = {}) {
  const { data } = await api.post(`/api/v1/sugerencias/${id}/aceptar`, cambios)  // { titulo?, contenido? }
  return data
}

export async function rechazarSugerencia(id, motivo) {
  const { data } = await api.post(`/api/v1/sugerencias/${id}/rechazar`, { motivo })
  return data
}

// ── Grilla de horarios (solo ADMIN) ───────────────────────────────────────────

export async function listarHorarios() {
  const { data } = await api.get('/api/v1/horarios/')
  return data  // [{ id, comision, anio, plan, turno, periodo, aula, dia, inicio, fin, materia, docente, lugar, electiva, origen }]
}

export async function crearBloque(payload) {
  const { data } = await api.post('/api/v1/horarios/', payload)
  return data
}

export async function actualizarBloque(id, cambios) {
  const { data } = await api.patch(`/api/v1/horarios/${id}`, cambios)
  return data
}

export async function borrarBloque(id) {
  await api.delete(`/api/v1/horarios/${id}`)
}

// ── Avisos de paro (banner del chat) ──────────────────────────────────────────

export async function listarAvisos() {
  const { data } = await api.get('/api/v1/informacion/avisos')
  return data  // [{ informacion_id, titulo, contenido, fecha_inicio, fecha_fin, ... }]
}

/** MOD/ADMIN: deja de usarse en el chat (ej. un paro que se levantó). */
export async function darDeBajaInformacion(id) {
  await api.delete(`/api/v1/informacion/${id}`)
}

// ── Mesas de examen (solo ADMIN) ──────────────────────────────────────────────

export const listarMesasFechas = () => api.get('/api/v1/mesas/fechas').then(r => r.data)
export const crearMesaFecha = payload => api.post('/api/v1/mesas/fechas', payload).then(r => r.data)
export const actualizarMesaFecha = (id, cambios) => api.patch(`/api/v1/mesas/fechas/${id}`, cambios).then(r => r.data)
export const borrarMesaFecha = id => api.delete(`/api/v1/mesas/fechas/${id}`)
export const listarMesasMaterias = () => api.get('/api/v1/mesas/materias').then(r => r.data)
export const crearMesaMateria = payload => api.post('/api/v1/mesas/materias', payload).then(r => r.data)
export const actualizarMesaMateria = (id, cambios) => api.patch(`/api/v1/mesas/materias/${id}`, cambios).then(r => r.data)
export const borrarMesaMateria = id => api.delete(`/api/v1/mesas/materias/${id}`)

// ── Calendario académico (leer: todos; editar: ADMIN) ─────────────────────────

export const listarCalendario = () => api.get('/api/v1/calendario/').then(r => r.data)
export const crearEvento = payload => api.post('/api/v1/calendario/', payload).then(r => r.data)
export const actualizarEvento = (id, cambios) => api.patch(`/api/v1/calendario/${id}`, cambios).then(r => r.data)
export const borrarEvento = id => api.delete(`/api/v1/calendario/${id}`)

// ── Documentos importantes (descargar: todos; subir y borrar: ADMIN) ──────────

export const listarDocumentos = () => api.get('/api/v1/documentos').then(r => r.data)
export const urlDocumento = id => `${BASE_URL}/api/v1/documentos/${id}/archivo`

/** archivo: File del input; nombre obligatorio; descripción opcional (si falta, la genera el backend). */
export async function subirDocumento(archivo, nombre, descripcion) {
  const form = new FormData()
  form.append('archivo', archivo)
  form.append('nombre', nombre)
  if (descripcion?.trim()) form.append('descripcion', descripcion.trim())
  const { data } = await api.post('/api/v1/documentos', form, { headers: { 'Content-Type': 'multipart/form-data' } })
  return data
}

export const borrarDocumento = id => api.delete(`/api/v1/documentos/${id}`)

// ── Historial de conversaciones ───────────────────────────────────────────────

export const listarConversaciones = () => api.get('/api/v1/chat/conversaciones').then(r => r.data)
export const obtenerConversacion = id => api.get(`/api/v1/chat/conversaciones/${id}`).then(r => r.data)
export const borrarConversacion = id => api.delete(`/api/v1/chat/conversaciones/${id}`)

export default api
