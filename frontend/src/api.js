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

// ── Admin: búsqueda de usuarios ───────────────────────────────────────────────

export async function listarUsuarios(rol = null) {
  const qs = rol ? `?rol=${rol}` : ''
  const { data } = await api.get(`/api/v1/usuarios${qs}`)
  return data
}

export default api
