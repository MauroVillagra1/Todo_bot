/** Estilos y utilidades compartidos por el panel y las vistas de formularios. */
import Swal from 'sweetalert2'

export const campo = 'w-full bg-[#141417] border border-[#232327] rounded-xl px-3 py-2 text-sm text-[#f4f4f5] placeholder-[#4b4b53] focus:outline-none focus:border-[#e8592e]/50 transition-colors'
export const tarjeta = 'bg-[#0d0d10] border border-[#1e1e22] rounded-2xl p-5'
export const boton = 'bg-[#e8592e] hover:bg-[#f2703f] disabled:bg-[#232327] disabled:text-[#4b4b53] text-white px-4 py-2 rounded-xl text-sm font-medium transition-colors'

export function fechaHora(iso) {
  return iso ? new Date(iso).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' }) : 'nunca'
}

export function errorDe(err, porDefecto) {
  const detalle = err.response?.data?.detail
  if (typeof detalle === 'string') return detalle
  if (Array.isArray(detalle)) return detalle.map(d => d.msg).join(' · ')
  return porDefecto
}

// ── Diálogos (SweetAlert2) con los colores de la app, en lugar de confirm() del navegador ──

const TEMA = {
  background: '#0d0d10', color: '#f4f4f5', confirmButtonColor: '#e8592e', cancelButtonColor: '#232327',
  customClass: { popup: 'rounded-2xl border border-[#232327]' },
}

/** Pide confirmación; devuelve true si la persona aceptó. */
export async function confirmar(texto, { titulo = '¿Estás seguro?', boton = 'Sí, borrar', icono = 'warning' } = {}) {
  const r = await Swal.fire({
    ...TEMA, title: titulo, text: texto, icon: icono, showCancelButton: true,
    confirmButtonText: boton, cancelButtonText: 'Cancelar', reverseButtons: true, focusCancel: true,
  })
  return r.isConfirmed
}

/** Pide un texto obligatorio (ej. un motivo); devuelve el texto o null si se canceló. */
export async function pedirTexto(texto, { titulo = 'Confirmar', boton = 'Sí, borrar', placeholder = '' } = {}) {
  const r = await Swal.fire({
    ...TEMA, title: titulo, text: texto, icon: 'warning', input: 'text', inputPlaceholder: placeholder,
    showCancelButton: true, confirmButtonText: boton, cancelButtonText: 'Cancelar', reverseButtons: true,
    inputValidator: v => (!v || v.trim().length < 3 ? 'Escribí un motivo (al menos 3 letras).' : undefined),
  })
  return r.isConfirmed ? r.value.trim() : null
}
