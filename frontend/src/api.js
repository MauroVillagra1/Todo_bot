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

export async function listarUsuarios() {
  const { data } = await api.get('/api/v1/usuarios/?page=1&page_size=100')
  return data.items  // [{ id, nombre, email, rol, activo, creado_en, ... }]
}

export async function crearUsuario(payload) {
  const { data } = await api.post('/api/v1/usuarios/', payload)  // { nombre, email, rol, password }
  return data
}

export async function actualizarUsuario(id, cambios) {
  const { data } = await api.patch(`/api/v1/usuarios/${id}`, cambios)  // { rol?, activo?, password?, ... }
  return data
}

export default api
