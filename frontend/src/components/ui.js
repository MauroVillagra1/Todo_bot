/** Estilos y utilidades compartidos por el panel y las vistas de formularios. */

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
