/**
 * Panel — panel administrativo.
 * Los formularios de carga académica se eliminaron (análisis MVP §15).
 * El panel nuevo (fuentes, métricas, usuarios) llega en la etapa 8.
 */
export default function Panel() {
  return (
    <div className="flex flex-col h-full bg-gray-50">
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <h2 className="text-base font-semibold text-gray-900">Panel de administración</h2>
        <p className="text-xs text-gray-500 mt-0.5">Fuentes, métricas y usuarios.</p>
      </div>
      <div className="flex-1 flex items-center justify-center p-6 text-gray-400 text-sm">
        En construcción.
      </div>
    </div>
  )
}
