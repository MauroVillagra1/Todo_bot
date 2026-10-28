/**
 * Input de contraseña con un botón (ojito) para verla u ocultarla.
 * Recibe las mismas props que un <input>; `className` es el estilo del input.
 */
import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'

export default function CampoClave({ className = '', ...props }) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="relative">
      <input {...props} type={visible ? 'text' : 'password'} className={`${className} pr-10`} />
      <button type="button" onClick={() => setVisible(v => !v)} tabIndex={-1}
              aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
              title={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
              className="absolute inset-y-0 right-0 px-3 flex items-center text-[#6b6b73] hover:text-[#f2894f] transition-colors">
        {visible ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  )
}
