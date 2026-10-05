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

/**
 * Inyecta el token JWT en cada request.
 */
export function setAuthToken(token) {
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`
  } else {
    delete api.defaults.headers.common['Authorization']
  }
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function login(email, password) {
  const { data } = await api.post('/api/v1/auth/login', { email, password })
  return data  // { access_token, token_type, usuario }
}

/** Paso 1 del registro: manda un código de 6 dígitos al mail institucional. */
export async function solicitarRegistro(nombre, email, password) {
  const { data } = await api.post('/api/v1/auth/registro', { nombre, email, password })
  return data  // { mensaje }
}

/** Paso 2: con el código correcto se crea la cuenta y queda logueado. */
export async function verificarRegistro(email, codigo) {
  const { data } = await api.post('/api/v1/auth/registro/verificar', { email, codigo })
  return data  // { access_token, token_type, usuario }
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

// ── Fuentes (MOD y ADMIN) ─────────────────────────────────────────────────────

export async function listarFuentes() {
  const { data } = await api.get('/api/v1/fuentes/')
  return data  // [{ id, nombre, tipo, url, confiabilidad_base, activa, ultima_revision, carga_manual }]
}

/** Carga a mano un posteo autorizado de Instagram o de un canal de WhatsApp. */
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

export default api
