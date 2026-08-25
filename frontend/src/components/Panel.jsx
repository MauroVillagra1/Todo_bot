/**
 * Panel — interfaz de carga de datos según rol.
 *
 * profesor            → Suspensión/Reubicación | Material | Info del cursado
 * administrativo      → Evento de calendario
 * jefe_departamento   → (futuro: gestión académica)
 * administrador       → todos los tabs anteriores + Resumen del sistema
 */
import { useState } from 'react'
import SuspensionForm  from './tabs/SuspensionForm'
import EventoForm      from './tabs/EventoForm'
import MaterialForm    from './tabs/MaterialForm'
import InfoCursadaForm from './tabs/InfoCursadaForm'
import ResumenAdmin    from './tabs/ResumenAdmin'

// Definición de tabs por rol
const TABS_PROFESOR = [
  { id: 'suspension', label: '🚫 Suspensión / Reubicación' },
  { id: 'material',   label: '📎 Material de apoyo'        },
  { id: 'info',       label: '📋 Info del cursado'         },
]

const TABS_ADMINISTRATIVO = [
  { id: 'evento', label: '📅 Evento de calendario' },
]

const TABS_JEFE = [
  { id: 'resumen', label: '🔍 Resumen académico' },
]

const TABS_ADMIN = [
  { id: 'suspension', label: '🚫 Suspensión / Reubicación' },
  { id: 'material',   label: '📎 Material de apoyo'        },
  { id: 'info',       label: '📋 Info del cursado'         },
  { id: 'evento',     label: '📅 Evento de calendario'     },
  { id: 'resumen',    label: '🔍 Resumen del sistema'      },
]

function tabsPorRol(rol) {
  switch (rol) {
    case 'profesor':
    case 'profesor_directivo':
      return TABS_PROFESOR
    case 'administrativo':
      return TABS_ADMINISTRATIVO
    case 'jefe_departamento':
      return TABS_JEFE
    case 'administrador':
      return TABS_ADMIN
    default:
      return []
  }
}

function descripcionPorRol(rol) {
  switch (rol) {
    case 'profesor':
    case 'profesor_directivo':
      return 'Gestioná tus cursadas: suspensiones, material y condiciones de cursado.'
    case 'administrativo':
      return 'Cargá y gestioná eventos del calendario académico institucional.'
    case 'jefe_departamento':
      return 'Supervisá las materias y comisiones de tu departamento.'
    case 'administrador':
      return 'Acceso completo al sistema.'
    default:
      return ''
  }
}

export default function Panel({ usuario }) {
  const tabs = tabsPorRol(usuario.rol)
  const [tabActiva, setTabActiva] = useState(tabs[0]?.id ?? '')

  if (tabs.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 text-sm">
        No tenés acceso al panel de carga.
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-gray-50">

      {/* Cabecera */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <h2 className="text-base font-semibold text-gray-900">Panel de gestión</h2>
        <p className="text-xs text-gray-500 mt-0.5">{descripcionPorRol(usuario.rol)}</p>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200 px-4 flex gap-1 overflow-x-auto">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setTabActiva(tab.id)}
            className={`px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
              tabActiva === tab.id
                ? 'border-primary-600 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Contenido */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto">
          {tabActiva === 'suspension' && <SuspensionForm  usuario={usuario} />}
          {tabActiva === 'material'   && <MaterialForm    usuario={usuario} />}
          {tabActiva === 'info'       && <InfoCursadaForm usuario={usuario} />}
          {tabActiva === 'evento'     && <EventoForm      usuario={usuario} />}
          {tabActiva === 'resumen'    && <ResumenAdmin    />}
        </div>
      </div>

    </div>
  )
}
