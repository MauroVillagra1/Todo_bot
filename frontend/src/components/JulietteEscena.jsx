/**
 * JulietteEscena — Juliette en una escena (solo en pantallas de PC), con un globo de diálogo que
 * muestra frases al azar: una nueva cada 30 segundos, escrita de a poco.
 *   'programando' → con la notebook (por ahora sin usar)
 *   'estudiando'  → con un cuaderno de notas (Documentos)
 *   'agenda'      → con el calendario del día (Calendario)
 *   'ideas'       → con una lamparita (Sugerir dato)
 * El dibujo es fijo (no hay datos del usuario adentro): se arma como texto SVG una sola vez.
 */
import { useEffect, useMemo, useRef, useState } from 'react'

const INK = '#1c1416', SK = '#f2c6a6'
const MESES = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC']

const ESTILOS = `
.je-burbuja{background:#fff;color:${INK};border:3px solid ${INK};border-radius:20px;padding:10px 16px;font-weight:700;
  font-size:.9rem;line-height:1.3;position:relative;min-height:2.6em;width:100%;box-sizing:border-box;display:flex;
  align-items:center;justify-content:center;text-align:center;font-family:"Trebuchet MS","Segoe UI",system-ui,sans-serif}
.je-burbuja::after{content:"";position:absolute;left:50%;bottom:-12px;width:15px;height:15px;background:#fff;
  border-right:3px solid ${INK};border-bottom:3px solid ${INK};transform:translateX(-50%) rotate(45deg)}
.je-svg{overflow:visible}
.je-svg .je-float{animation:je-float 3s ease-in-out infinite}
@keyframes je-float{50%{transform:translateY(-8px)}}
.je-svg .je-eyes{transform-box:fill-box;transform-origin:center;animation:je-blink 4.2s infinite}
@keyframes je-blink{0%,93%,100%{transform:scaleY(1)}96%{transform:scaleY(.06)}}
.je-svg .je-pupil{transition:transform .25s ease-out}
.je-svg .je-hair{transform-origin:150px 40px;animation:je-hair 3s ease-in-out infinite}
@keyframes je-hair{50%{transform:rotate(-1.2deg)}}
.je-svg .je-arm{transform-origin:188px 238px;animation:je-wave 5s ease-in-out infinite}
@keyframes je-wave{0%,70%,100%{transform:rotate(0)}76%{transform:rotate(-55deg)}82%{transform:rotate(-30deg)}88%{transform:rotate(-55deg)}94%{transform:rotate(-10deg)}}
.je-svg .je-ln{transform-box:fill-box;transform-origin:left;animation:je-typ 3.6s steps(6) infinite}
.je-svg .je-ln:nth-of-type(2){animation-delay:.5s}.je-svg .je-ln:nth-of-type(3){animation-delay:1s}.je-svg .je-ln:nth-of-type(4){animation-delay:1.5s}
@keyframes je-typ{0%{transform:scaleX(0)}60%,100%{transform:scaleX(1)}}
.je-svg .je-cur{animation:je-cur .8s steps(1) infinite}
@keyframes je-cur{50%{opacity:0}}
.je-svg .je-cal{transform-origin:227px 264px;animation:je-wig 2.6s ease-in-out infinite}
@keyframes je-wig{50%{transform:rotate(4deg)}}
.je-svg .je-bulb{animation:je-bob 2s ease-in-out infinite}
@keyframes je-bob{50%{transform:translateY(-6px)}}
.je-svg .je-glow{transform-box:fill-box;transform-origin:center;animation:je-gl 1.2s ease-in-out infinite}
@keyframes je-gl{50%{transform:scale(1.3);opacity:.2}}
.je-svg .je-rays{animation:je-ry 1.2s ease-in-out infinite}
@keyframes je-ry{50%{opacity:.25}}
@media (prefers-reduced-motion:reduce){.je-svg *{animation:none!important}}
`

let estilosPuestos = false
function ponerEstilos() {
  if (estilosPuestos || typeof document === 'undefined') return
  const style = document.createElement('style')
  style.textContent = ESTILOS
  document.head.appendChild(style)
  estilosPuestos = true
}

// ── Piezas del dibujo (mismas formas que el diseño original) ──────────────────

const hand = (x, y) => `<circle cx="${x}" cy="${y}" r="9" fill="${SK}" stroke="${INK}" stroke-width="3.5"/>`
function arm(x1, y1, x2, y2, hx, hy, cls = '') {
  const d = `M${x1} ${y1}L${x2} ${y2}`
  return `<g class="${cls}"><path d="${d}" stroke="${INK}" stroke-width="17" stroke-linecap="round"/>` +
    `<path d="${d}" stroke="#fff" stroke-width="10" stroke-linecap="round"/>${hx ? hand(hx, hy) : ''}</g>`
}
const LEGS = `<path d="M136 288v22M164 288v22" stroke="${INK}" stroke-width="12" stroke-linecap="round"/>` +
  `<ellipse cx="134" cy="314" rx="15" ry="8" fill="#f08a24" stroke="${INK}" stroke-width="4"/>` +
  `<ellipse cx="166" cy="314" rx="15" ry="8" fill="#f08a24" stroke="${INK}" stroke-width="4"/>`
const SHIRT = `<path d="M112 222h76l8 66c-16 8-36 12-46 12s-30-4-46-12z" fill="#fff" stroke="${INK}" stroke-width="4" stroke-linejoin="round"/>` +
  `<g transform="translate(150 264) scale(.42)"><path d="M-12-69A70 70 0 0 0 -12 69" fill="none" stroke="${INK}" stroke-width="7" stroke-linecap="round"/>` +
  `<path d="M12-69A70 70 0 0 1 12 69" fill="none" stroke="#f08a24" stroke-width="7" stroke-linecap="round"/>` +
  `<g fill="none" stroke="${INK}" stroke-width="9"><path d="M-34-46C-34-20-18-9 0-9S34-20 34-46"/><path d="M-34 46C-34 20-18 9 0 9S34 20 34 46"/><path d="M0-50V50M-44 0H44"/></g></g>`
const STD = arm(114, 238, 96, 264, 92, 272) + arm(188, 238, 206, 260, 212, 268, 'je-arm')
const BR = {
  n: ['M84 114Q104 106 128 114', 'M172 114Q196 106 216 114'],
  f: ['M84 110Q108 110 128 118', 'M172 118Q192 110 216 110'],
  r: ['M84 108Q104 98 128 108', 'M172 108Q196 98 216 108'],
}
const MO = { s: ['M139 198c4 9 18 9 22 0z', '#d9526b'], b: ['M132 192c4 22 32 22 36 0z', '#d9526b'], f: ['M141 201q9 5 18 0', 'none'] }

function head(brow, mouth, feliz) {
  const eye = cx => `<g class="je-eyes"><ellipse cx="${cx}" cy="156" rx="25" ry="28" fill="#fff" stroke="${INK}" stroke-width="3.5"/>` +
    `<g class="je-pupil"><ellipse cx="${cx}" cy="160" rx="17" ry="21" fill="#5a3426"/><ellipse cx="${cx}" cy="162" rx="9" ry="12" fill="#150b09"/>` +
    `<circle cx="${cx - 7}" cy="150" r="6.5" fill="#fff"/><circle cx="${cx + 8}" cy="170" r="3" fill="#fff"/></g></g>`
  return `<g><g class="je-hair"><ellipse cx="150" cy="138" rx="106" ry="96" fill="#2d1b18"/>` +
    `<path d="M48 150c-6 40-6 72-18 98 16 6 34-2 44-18 8-22 6-52 4-80zM252 150c6 40 6 72 18 98-16 6-34-2-44-18-8-22-6-52-4-80z" fill="#2d1b18"/></g>` +
    `<ellipse cx="150" cy="144" rx="96" ry="84" fill="${SK}" stroke="${INK}" stroke-width="4"/>` +
    `<ellipse cx="80" cy="190" rx="16" ry="9" fill="#ee8a86" opacity=".55"/><ellipse cx="220" cy="190" rx="16" ry="9" fill="#ee8a86" opacity=".55"/>` +
    (feliz ? `<g fill="none" stroke="${INK}" stroke-width="5.5" stroke-linecap="round"><path d="M82 166Q106 134 130 166"/><path d="M170 166Q194 134 218 166"/></g>`
      : eye(106) + eye(194)) +
    `<path d="M78 134Q106 106 134 134Q106 120 78 134Z" fill="#c98f78" opacity=".5"/><path d="M166 134Q194 106 222 134Q194 120 166 134Z" fill="#c98f78" opacity=".5"/>` +
    `<g fill="none" stroke="${INK}" stroke-width="5" stroke-linecap="round"><path d="M78 140Q106 116 134 140M78 140L62 126"/><path d="M166 140Q194 116 222 140M222 140L238 126"/></g>` +
    `<g fill="none" stroke="#2d1b18" stroke-width="5" stroke-linecap="round"><path d="${brow[0]}"/><path d="${brow[1]}"/></g>` +
    `<path d="${mouth[0]}" fill="${mouth[1]}" stroke="${INK}" stroke-width="3.5" stroke-linejoin="round" stroke-linecap="round"/>` +
    `<g class="je-hair"><path d="M150 34C84 34 44 78 52 152C62 138 66 124 70 112C100 106 132 92 150 72Z" fill="#2d1b18"/>` +
    `<path d="M150 34C216 34 256 78 248 152C238 138 234 124 230 112C200 106 168 92 150 72Z" fill="#2d1b18"/>` +
    `<path d="M100 50c-14 14-24 32-28 52M200 50c14 14 24 32 28 52M64 126c-2 10-2 18-4 26M236 126c2 10 2 18 4 26" stroke="#4d322b" stroke-width="3.5" stroke-linecap="round" fill="none"/></g>` +
    `<circle cx="53" cy="180" r="6.5" fill="none" stroke="#e2b02c" stroke-width="3.5"/><circle cx="247" cy="180" r="6.5" fill="none" stroke="#e2b02c" stroke-width="3.5"/></g>`
}

const LAPTOP = `<path d="M90 300h120l-7 9H97z" fill="#3a3a46" stroke="${INK}" stroke-width="3" stroke-linejoin="round"/>` +
  `<rect x="100" y="244" width="100" height="56" rx="6" fill="#2a2a35" stroke="${INK}" stroke-width="3.5"/><rect x="106" y="250" width="88" height="44" rx="3" fill="#12141c"/>` +
  `<rect class="je-ln" x="112" y="256" width="34" height="4" rx="2" fill="#f08a24"/><rect class="je-ln" x="120" y="264" width="50" height="4" rx="2" fill="#8fd9a8"/>` +
  `<rect class="je-ln" x="120" y="272" width="28" height="4" rx="2" fill="#e8e0d8"/><rect class="je-ln" x="112" y="280" width="40" height="4" rx="2" fill="#f08a24"/>` +
  `<rect class="je-cur" x="156" y="279" width="5" height="7" fill="#fff"/>`
const BOOK = `<g transform="rotate(-10 88 264)"><rect x="68" y="238" width="36" height="54" rx="4" fill="#f08a24" stroke="${INK}" stroke-width="3.5"/>` +
  `<rect x="100" y="241" width="4" height="48" fill="#fff"/><rect x="75" y="248" width="20" height="5" rx="2" fill="#fff"/><rect x="75" y="258" width="14" height="4" rx="2" fill="#fff" opacity=".8"/></g>`
const T = 'font-family="Trebuchet MS,sans-serif" font-weight="700" text-anchor="middle"'
function calendario() {
  const hoy = new Date()
  return `<g class="je-cal"><rect x="200" y="238" width="54" height="50" rx="6" fill="#fff" stroke="${INK}" stroke-width="3.5"/>` +
    `<path d="M200 244a6 6 0 0 1 6-6h42a6 6 0 0 1 6 6v8h-54z" fill="#f08a24" stroke="${INK}" stroke-width="3.5" stroke-linejoin="round"/>` +
    `<rect x="212" y="231" width="5" height="13" rx="2.5" fill="${INK}"/><rect x="237" y="231" width="5" height="13" rx="2.5" fill="${INK}"/>` +
    `<text x="227" y="249" font-size="8" fill="#fff" ${T}>${MESES[hoy.getMonth()]}</text>` +
    `<circle cx="227" cy="272" r="11" fill="#e03a3a"/><text x="227" y="277" font-size="13" fill="#fff" ${T}>${hoy.getDate()}</text>` +
    `<g fill="#bbb"><circle cx="210" cy="262" r="1.8"/><circle cx="244" cy="262" r="1.8"/><circle cx="210" cy="280" r="1.8"/><circle cx="244" cy="280" r="1.8"/></g>` +
    `${hand(204, 283)}</g>`
}
const RAYS = [-165, -130, -95, -60, -25].map(a => {
  const r = a * Math.PI / 180
  return `<line x1="${(232 + 24 * Math.cos(r)).toFixed(1)}" y1="${(34 + 24 * Math.sin(r)).toFixed(1)}" x2="${(232 + 34 * Math.cos(r)).toFixed(1)}" y2="${(34 + 34 * Math.sin(r)).toFixed(1)}"/>`
}).join('')
const BULB = `<g class="je-bulb"><circle class="je-glow" cx="232" cy="34" r="26" fill="#ffe066" opacity=".45"/>` +
  `<g class="je-rays" stroke="#f0a020" stroke-width="3.5" stroke-linecap="round">${RAYS}</g>` +
  `<circle cx="232" cy="34" r="16" fill="#ffe066" stroke="${INK}" stroke-width="3.5"/><rect x="225" y="48" width="14" height="10" rx="3" fill="#cfcfd6" stroke="${INK}" stroke-width="3"/>` +
  `<path d="M227 38q5-9 10 0" fill="none" stroke="#f08a24" stroke-width="2.5" stroke-linecap="round"/></g>`

// mirada fija (null = sigue al mouse)
const ESCENAS = {
  programando: () => ({ mirada: [0, 9], svg: LEGS + SHIRT + LAPTOP + arm(114, 238, 106, 296, 108, 303) + arm(186, 238, 194, 296, 192, 303) + head(BR.f, MO.f) }),
  estudiando: () => ({ mirada: null, svg: LEGS + BOOK + arm(114, 238, 98, 268, 94, 276) + arm(188, 238, 206, 260, 212, 268, 'je-arm') + SHIRT + head(BR.n, MO.s, true) }),
  agenda: () => ({ mirada: [7, 4], svg: LEGS + arm(114, 238, 96, 264, 92, 272) + arm(188, 238, 202, 276) + SHIRT + calendario() + head(BR.n, MO.s) }),
  ideas: () => ({ mirada: null, svg: LEGS + STD + SHIRT + BULB + head(BR.r, MO.b) }),
}

const INTERVALO = 30_000
const azar = (lista, salvo) => {
  const opciones = lista.length > 1 ? lista.filter(m => m !== salvo) : lista
  return opciones[Math.floor(Math.random() * opciones.length)]
}

export default function JulietteEscena({ escena, mensajes, size = 220, className = '' }) {
  ponerEstilos()
  const dibujo = useMemo(() => ESCENAS[escena](), [escena])
  const svg = useRef(null)
  const [frase, setFrase] = useState(() => azar(mensajes))
  const [n, setN] = useState(0)

  // Una frase nueva cada 30 segundos (distinta de la anterior)
  useEffect(() => {
    const t = setInterval(() => setFrase(f => azar(mensajes, f)), INTERVALO)
    return () => clearInterval(t)
  }, [mensajes])

  // Se escribe de a poco, como en el diseño original
  useEffect(() => {
    setN(0)
    const t = setInterval(() => setN(i => (i >= frase.length ? (clearInterval(t), i) : i + 1)), 45)
    return () => clearInterval(t)
  }, [frase])

  // Ojos: fijos en lo que hace, o siguiendo al mouse
  useEffect(() => {
    const pupilas = () => svg.current?.querySelectorAll('.je-pupil') ?? []
    if (dibujo.mirada) {
      pupilas().forEach(p => { p.style.transform = `translate(${dibujo.mirada[0]}px,${dibujo.mirada[1]}px)` })
      return
    }
    function mover(e) {
      const r = svg.current?.getBoundingClientRect()
      if (!r) return
      const dx = Math.max(-1, Math.min(1, (e.clientX - r.left - r.width / 2) / 200))
      const dy = Math.max(-1, Math.min(1, (e.clientY - r.top - r.height * 0.45) / 200))
      pupilas().forEach(p => { p.style.transform = `translate(${dx * 6}px,${dy * 5}px)` })
    }
    window.addEventListener('mousemove', mover)
    return () => window.removeEventListener('mousemove', mover)
  }, [dibujo])

  return (
    <div className={`flex-col items-center gap-4 ${className}`} style={{ width: size }}>
      <div className="je-burbuja" aria-live="polite">{frase.slice(0, n)}</div>
      <svg ref={svg} className="je-svg" viewBox="0 0 300 340" width={size} height={size * 340 / 300} role="img"
           aria-label={`Juliette (${escena})`}
           dangerouslySetInnerHTML={{
             __html: `<ellipse cx="150" cy="332" rx="62" ry="6" fill="#000" opacity=".15"/><g class="je-float">${dibujo.svg}</g>`,
           }} />
    </div>
  )
}

// Frases de cada escena
export const FRASES = {
  documentos: [
    'Asegurate de que no se te venza el plazo',
    '¿También odiás cuando la fila del Departamento Alumnos es muy larga?',
  ],
  calendario: [
    'Planificá bien tu día',
    'No veo la hora de que llegue un finde largo',
  ],
  sugerir: [
    'Tus aportes son necesarios',
    'La comunidad necesita de todos para crecer',
  ],
}
