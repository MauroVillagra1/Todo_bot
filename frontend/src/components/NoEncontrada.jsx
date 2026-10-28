/**
 * Página 404: cualquier dirección que no es la del chat. Juliette, enojada.
 */
import Juliette from './Juliette'

export default function NoEncontrada() {
  return (
    <div className="min-h-screen bg-[#0a0a0c] text-[#f4f4f5] flex flex-col items-center justify-center text-center px-4 font-body">
      <Juliette estado="angry" size={170} titulo="Juliette enojada" />
      <p className="font-display text-6xl font-bold text-[#f2894f] mt-4">404</p>
      <h1 className="font-display text-xl font-semibold mt-2">Esta página no existe</h1>
      <p className="text-sm text-[#8b8b93] mt-1 max-w-sm">
        Juliette la buscó por toda la facultad y no la encontró. Revisá la dirección o volvé al chat.
      </p>
      <a href="/" className="mt-6 bg-[#e8592e] hover:bg-[#f2703f] text-white text-sm font-medium px-5 py-2.5 rounded-xl transition-colors">
        Volver al chat
      </a>
    </div>
  )
}
