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

// ── Chat ──────────────────────────────────────────────────────────────────────

export async function enviarMensaje(mensaje, conversacion_id = null) {
  const { data } = await api.post('/api/v1/chat/', { mensaje, conversacion_id })
  return data  // { respuesta, conversacion_id, fuentes }
}

// ── Académico — listas para selects ──────────────────────────────────────────

/** Lista todas las comisiones. */
export async function listarComisiones() {
  const { data } = await api.get('/api/v1/comisiones')
  return data  // [{ id, nombre, periodo_id, ... }]
}

/** Lista todas las materias (paginado, trae hasta 200). */
export async function listarMaterias() {
  const { data } = await api.get('/api/v1/materias?page=1&page_size=200')
  return data.items  // [{ id, codigo, nombre, ... }]
}

/** Lista cursadas, opcionalmente filtrando por comisión. */
export async function listarCursadas(comision_id = null) {
  const params = comision_id ? `?comision_id=${comision_id}&page_size=100` : '?page_size=200'
  const { data } = await api.get(`/api/v1/cursadas${params}`)
  return data.items  // [{ id, materia_id, comision_id, aula, horario, ... }]
}

/** Lista eventos, opcionalmente filtrando por fechas. */
export async function listarEventos(fecha_desde = null, fecha_hasta = null) {
  const params = new URLSearchParams()
  if (fecha_desde) params.set('fecha_desde', fecha_desde)
  if (fecha_hasta) params.set('fecha_hasta', fecha_hasta)
  const qs = params.toString() ? `?${params.toString()}` : ''
  const { data } = await api.get(`/api/v1/eventos${qs}`)
  return data  // [EventoCalendarioRead]
}

// ── Excepciones (suspensiones / reubicaciones) ────────────────────────────────

/**
 * Carga una suspensión o reubicación para una cursada.
 * @param {number} cursada_id
 * @param {object} payload  { tipo, motivo, fecha_inicio, fecha_fin, aula_nueva?, horario_nuevo? }
 */
export async function cargarExcepcion(cursada_id, payload) {
  const { data } = await api.post(`/api/v1/cursadas/${cursada_id}/excepciones`, {
    cursada_id,
    ...payload,
  })
  return data  // CursadaExcepcionRead
}

/** Lista las excepciones vigentes de una cursada (opcionalmente filtra por fecha). */
export async function listarExcepciones(cursada_id, fecha = null) {
  const qs = fecha ? `?fecha=${fecha}` : ''
  const { data } = await api.get(`/api/v1/cursadas/${cursada_id}/excepciones${qs}`)
  return data
}

// ── Eventos de calendario ─────────────────────────────────────────────────────

/**
 * Carga un evento de calendario institucional.
 * @param {object} payload  { titulo, tipo, origen?, motivo?, fecha_inicio, fecha_fin,
 *                            hora_inicio?, hora_fin?, alcance, comision_id?, cursada_id? }
 */
export async function cargarEvento(payload) {
  const { data } = await api.post('/api/v1/eventos/', payload)
  return data  // EventoCalendarioRead
}

// ── Materiales de apoyo ───────────────────────────────────────────────────────

/**
 * Carga material de apoyo a una cursada.
 * @param {object} payload  { cursada_id, tipo, titulo, url?, descripcion? }
 */
export async function cargarMaterial(payload) {
  const { data } = await api.post('/api/v1/materiales/', payload)
  return data  // MaterialRead
}

/** Lista los materiales de una cursada. */
export async function listarMateriales(cursada_id) {
  const { data } = await api.get(`/api/v1/materiales/cursada/${cursada_id}`)
  return data
}

/** Elimina un material (solo quien lo cargó o admin). */
export async function eliminarMaterial(material_id) {
  await api.delete(`/api/v1/materiales/${material_id}`)
}

// ── Admin: búsqueda de usuarios ───────────────────────────────────────────────

export async function listarUsuarios(rol = null) {
  const qs = rol ? `?rol=${rol}` : ''
  const { data } = await api.get(`/api/v1/usuarios${qs}`)
  return data
}

export default api
