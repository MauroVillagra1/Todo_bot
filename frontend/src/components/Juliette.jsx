/**
 * Juliette — la mascota animada del asistente (SVG chibi).
 *
 * Props:
 *   estado: 'neutral' | 'happy' (feliz) | 'sad' (triste) | 'sigh' (suspira) | 'angry' (enojada)
 *           | 'think' (pensando) | 'talk' (hablando)
 *   size:   ancho en px (el alto se ajusta solo)
 *   mirar:  true → los ojos siguen al mouse (solo en la grande, no en cada mensaje)
 * Tocarla la hace saltar (y guiña si está tranquila).
 * Sin ids: puede haber muchas en la página (una por mensaje). Los estilos se inyectan una vez.
 */
import { useEffect, useRef, useState } from 'react'

const ESTILOS = `
.juliette{overflow:visible;cursor:pointer;-webkit-tap-highlight-color:transparent}
.juliette .j-float{animation:j-float 3s ease-in-out infinite}
@keyframes j-float{50%{transform:translateY(-9px)}}
.juliette .j-eyes{transform-box:fill-box;transform-origin:center;animation:j-blink 4.2s infinite}
@keyframes j-blink{0%,93%,100%{transform:scaleY(1)}96%{transform:scaleY(.06)}}
.juliette .j-pupil{transition:transform .25s ease-out}
.juliette .j-hair{transform-origin:150px 40px;animation:j-hair 3s ease-in-out infinite}
@keyframes j-hair{50%{transform:rotate(-1.2deg)}}
.juliette .j-arm{transform-origin:188px 238px;animation:j-wave 5s ease-in-out infinite}
@keyframes j-wave{0%,70%,100%{transform:rotate(0)}76%{transform:rotate(-55deg)}82%{transform:rotate(-30deg)}88%{transform:rotate(-55deg)}94%{transform:rotate(-10deg)}}
.juliette .j-head{transform-origin:150px 250px}
.juliette .j-mouth{transform-box:fill-box;transform-origin:center}
.juliette.j-talking .j-mouth{animation:j-talk .26s ease-in-out infinite}
@keyframes j-talk{50%{transform:scaleY(2.2)}}
.juliette .j-hop{animation:j-hop .55s ease-out}
@keyframes j-hop{35%{transform:translateY(-28px) scale(1.04)}}
.juliette .j-xs{display:none}
.juliette.s-happy .j-happyEyes,.juliette.s-happy .j-hearts,.juliette.s-happy .j-blushy,.juliette.s-sad .j-tears,
.juliette.s-sigh .j-puff,.juliette.s-sigh .j-lids,.juliette.s-angry .j-rage,.juliette.s-angry .j-steam,
.juliette.s-angry .j-vein,.juliette.s-think .j-dots,.juliette.s-talk .j-waves,.juliette.j-wink .j-winkEye,
.juliette.j-wink .j-tongue{display:inline}
.juliette.s-happy .j-eyes,.juliette.j-wink .j-eyeR{display:none}
.juliette.s-sad .j-head{animation:j-droop 3s ease-in-out infinite}
@keyframes j-droop{50%{transform:translateY(5px) rotate(-1.5deg)}}
.juliette.s-sigh .j-head{animation:j-sigh 3.4s ease-in-out infinite}
@keyframes j-sigh{0%,100%{transform:translateY(0)}30%{transform:translateY(-6px) scale(1.01)}60%{transform:translateY(7px)}}
.juliette.s-angry .j-head{animation:j-shake .12s linear infinite}
@keyframes j-shake{25%{transform:translateX(-2px)}75%{transform:translateX(2px)}}
.juliette.s-think .j-head{animation:j-tilt 2.4s ease-in-out infinite}
@keyframes j-tilt{50%{transform:rotate(4deg)}}
.juliette .j-drop{transform-box:fill-box;animation:j-drop 1.4s ease-in infinite}
.juliette .j-tears g:nth-child(2) .j-drop{animation-delay:.5s}
@keyframes j-drop{0%{transform:translateY(-4px);opacity:0}25%{opacity:1}100%{transform:translateY(36px);opacity:0}}
.juliette .j-puff circle{transform-box:fill-box;animation:j-puff 2.2s ease-out infinite}
.juliette .j-puff circle:nth-child(2){animation-delay:.25s}.juliette .j-puff circle:nth-child(3){animation-delay:.5s}
@keyframes j-puff{0%{opacity:0;transform:translate(0,0) scale(.5)}30%{opacity:.95}100%{opacity:0;transform:translate(46px,-14px) scale(1.7)}}
.juliette .j-steam circle{transform-box:fill-box;animation:j-steam 1.1s ease-out infinite}
.juliette .j-steam circle:nth-child(2),.juliette .j-steam circle:nth-child(4){animation-delay:.3s}
@keyframes j-steam{0%{opacity:0;transform:translateY(8px) scale(.6)}40%{opacity:1}100%{opacity:0;transform:translateY(-22px) scale(1.3)}}
.juliette .j-vein{transform-box:fill-box;transform-origin:center;animation:j-pulse .5s ease-in-out infinite}
@keyframes j-pulse{50%{transform:scale(1.4);opacity:.7}}
.juliette .j-dots circle{animation:j-dot 1.2s infinite}
.juliette .j-dots circle:nth-child(2){animation-delay:.2s}.juliette .j-dots circle:nth-child(3){animation-delay:.4s}
@keyframes j-dot{0%,100%{opacity:.2;transform:translateY(0)}50%{opacity:1;transform:translateY(-6px)}}
.juliette .j-hearts text{animation:j-rise 1.8s ease-out infinite;font-size:22px;fill:#f0507a}
.juliette .j-hearts text:nth-child(2){animation-delay:.6s}.juliette .j-hearts text:nth-child(3){animation-delay:1.2s}
@keyframes j-rise{0%{opacity:0;transform:translateY(14px)}30%{opacity:1}100%{opacity:0;transform:translateY(-26px)}}
.juliette .j-waves path{animation:j-wv .5s ease-in-out infinite alternate}
.juliette .j-waves path:nth-child(2){animation-delay:.25s}
@keyframes j-wv{from{opacity:.2}to{opacity:1}}
@media (prefers-reduced-motion:reduce){.juliette *{animation:none!important}}
`

// Cejas, boca y mirada de cada estado
const CARAS = {
  neutral: { l: 'M84 114Q104 106 128 114', r: 'M172 114Q196 106 216 114', m: 'M139 198c4 9 18 9 22 0z', c: '#d9526b' },
  happy:   { l: 'M84 110Q104 100 128 110', r: 'M172 110Q196 100 216 110', m: 'M132 192c4 22 32 22 36 0z', c: '#d9526b' },
  sad:     { l: 'M84 120Q108 116 128 104', r: 'M172 104Q192 116 216 120', m: 'M138 208Q150 194 162 208', c: 'none', p: [0, 8] },
  sigh:    { l: 'M84 118Q104 114 128 120', r: 'M172 120Q196 114 216 118', m: 'M144 202c0-7 12-7 12 0c0 8-12 8-12 0z', c: '#7a2a3c', p: [0, 9] },
  angry:   { l: 'M84 104Q108 108 128 122', r: 'M172 122Q192 108 216 104', m: 'M136 210Q150 196 164 210', c: 'none', p: [0, 3] },
  think:   { l: 'M84 108Q104 94 128 106', r: 'M172 118Q196 114 216 118', m: 'M142 205Q152 200 160 203', c: 'none', p: [8, -10] },
  talk:    { l: 'M84 112Q104 104 128 112', r: 'M172 112Q196 104 216 112', m: 'M139 196c4 12 18 12 22 0z', c: '#d9526b' },
}

let estilosPuestos = false
function ponerEstilos() {
  if (estilosPuestos || typeof document === 'undefined') return
  const style = document.createElement('style')
  style.textContent = ESTILOS
  document.head.appendChild(style)
  estilosPuestos = true
}

const INK = '#1c1416'

export default function Juliette({ estado = 'neutral', size = 48, mirar = false, className = '', titulo }) {
  const svg = useRef(null)
  const [mirada, setMirada] = useState([0, 0])
  const [salto, setSalto] = useState(false)
  const [guino, setGuino] = useState(false)
  const cara = CARAS[estado] ?? CARAS.neutral
  ponerEstilos()

  useEffect(() => {
    if (!mirar) return
    function mover(e) {
      const r = svg.current?.getBoundingClientRect()
      if (!r) return
      const dx = Math.max(-1, Math.min(1, (e.clientX - r.left - r.width / 2) / 200))
      const dy = Math.max(-1, Math.min(1, (e.clientY - r.top - r.height * 0.45) / 200))
      setMirada([dx * 6, dy * 5])
    }
    window.addEventListener('mousemove', mover)
    return () => window.removeEventListener('mousemove', mover)
  }, [mirar])

  function tocar() {
    setSalto(true)
    setTimeout(() => setSalto(false), 600)
    if (estado === 'neutral') {
      setGuino(true)
      setTimeout(() => setGuino(false), 1400)
    }
  }

  const [px, py] = cara.p ?? mirada
  const pupila = { transform: `translate(${px}px, ${py}px)` }
  const clases = ['juliette', `s-${estado}`, estado === 'talk' && 'j-talking', guino && 'j-wink', className]
    .filter(Boolean).join(' ')

  return (
    <svg ref={svg} viewBox="0 24 300 316" width={size} height={size * 316 / 300} className={clases} onClick={tocar}
         role="img" aria-label={titulo ?? `Juliette (${estado})`}>
      <ellipse cx="150" cy="330" rx="62" ry="7" fill="#000" opacity=".15" />
      <g className={`j-float${salto ? ' j-hop' : ''}`}>
        {/* piernas */}
        <path d="M136 288v22M164 288v22" stroke={INK} strokeWidth="12" strokeLinecap="round" />
        <ellipse cx="134" cy="314" rx="15" ry="8" fill="#f08a24" stroke={INK} strokeWidth="4" />
        <ellipse cx="166" cy="314" rx="15" ry="8" fill="#f08a24" stroke={INK} strokeWidth="4" />
        {/* brazos con manga blanca */}
        <g>
          <path d="M114 238L96 264" stroke={INK} strokeWidth="17" strokeLinecap="round" />
          <path d="M114 238L96 264" stroke="#fff" strokeWidth="10" strokeLinecap="round" />
          <circle cx="92" cy="272" r="9" fill="#f2c6a6" stroke={INK} strokeWidth="3.5" />
        </g>
        <g className="j-arm">
          <path d="M188 238L206 260" stroke={INK} strokeWidth="17" strokeLinecap="round" />
          <path d="M188 238L206 260" stroke="#fff" strokeWidth="10" strokeLinecap="round" />
          <circle cx="212" cy="268" r="9" fill="#f2c6a6" stroke={INK} strokeWidth="3.5" />
        </g>
        {/* remera blanca con logo UTN */}
        <path d="M112 222h76l8 66c-16 8-36 12-46 12s-30-4-46-12z" fill="#fff" stroke={INK} strokeWidth="4" strokeLinejoin="round" />
        <g transform="translate(150 264) scale(.42)">
          <path d="M-12-69A70 70 0 0 0 -12 69" fill="none" stroke={INK} strokeWidth="7" strokeLinecap="round" />
          <path d="M12-69A70 70 0 0 1 12 69" fill="none" stroke="#f08a24" strokeWidth="7" strokeLinecap="round" />
          <g fill="none" stroke={INK} strokeWidth="9">
            <path d="M-34-46C-34-20-18-9 0-9S34-20 34-46" />
            <path d="M-34 46C-34 20-18 9 0 9S34 20 34 46" />
            <path d="M0-50V50M-44 0H44" />
          </g>
        </g>
        <g className="j-head">
          {/* pelo atrás */}
          <g className="j-hair">
            <ellipse cx="150" cy="138" rx="106" ry="96" fill="#2d1b18" />
            <path d="M48 150c-6 40-6 72-18 98 16 6 34-2 44-18 8-22 6-52 4-80zM252 150c6 40 6 72 18 98-16 6-34-2-44-18-8-22-6-52-4-80z" fill="#2d1b18" />
          </g>
          {/* cara */}
          <ellipse cx="150" cy="144" rx="96" ry="84" fill="#f2c6a6" stroke={INK} strokeWidth="4" />
          <ellipse className="j-rage j-xs" cx="150" cy="150" rx="90" ry="76" fill="#ff5a4a" opacity=".2" />
          <ellipse cx="80" cy="190" rx="16" ry="9" fill="#ee8a86" opacity=".55" />
          <ellipse cx="220" cy="190" rx="16" ry="9" fill="#ee8a86" opacity=".55" />
          <g className="j-blushy j-xs">
            <ellipse cx="80" cy="190" rx="18" ry="11" fill="#ff7f90" opacity=".5" />
            <ellipse cx="220" cy="190" rx="18" ry="11" fill="#ff7f90" opacity=".5" />
          </g>
          {/* ojos */}
          <g className="j-eyes j-eyeL">
            <ellipse cx="106" cy="156" rx="25" ry="28" fill="#fff" stroke={INK} strokeWidth="3.5" />
            <g className="j-pupil" style={pupila}>
              <ellipse cx="106" cy="160" rx="17" ry="21" fill="#5a3426" /><ellipse cx="106" cy="162" rx="9" ry="12" fill="#150b09" />
              <circle cx="99" cy="150" r="6.5" fill="#fff" /><circle cx="114" cy="170" r="3" fill="#fff" />
            </g>
          </g>
          <g className="j-eyes j-eyeR">
            <ellipse cx="194" cy="156" rx="25" ry="28" fill="#fff" stroke={INK} strokeWidth="3.5" />
            <g className="j-pupil" style={pupila}>
              <ellipse cx="194" cy="160" rx="17" ry="21" fill="#5a3426" /><ellipse cx="194" cy="162" rx="9" ry="12" fill="#150b09" />
              <circle cx="187" cy="150" r="6.5" fill="#fff" /><circle cx="202" cy="170" r="3" fill="#fff" />
            </g>
          </g>
          <g className="j-lids j-xs">
            <path d="M78 124h56v28h-56zM166 124h56v28h-56z" fill="#f2c6a6" />
            <path d="M80 152h52M168 152h52" stroke={INK} strokeWidth="4.5" strokeLinecap="round" />
          </g>
          <g className="j-happyEyes j-xs" fill="none" stroke={INK} strokeWidth="5.5" strokeLinecap="round">
            <path d="M82 166Q106 134 130 166" /><path d="M170 166Q194 134 218 166" />
          </g>
          <path className="j-winkEye j-xs" d="M170 160Q194 178 218 160" fill="none" stroke={INK} strokeWidth="5.5" strokeLinecap="round" />
          {/* delineado */}
          <path d="M78 134Q106 106 134 134Q106 120 78 134Z" fill="#c98f78" opacity=".5" />
          <path d="M166 134Q194 106 222 134Q194 120 166 134Z" fill="#c98f78" opacity=".5" />
          <g fill="none" stroke={INK} strokeWidth="5" strokeLinecap="round">
            <path d="M78 140Q106 116 134 140M78 140L62 126" /><path d="M166 140Q194 116 222 140M222 140L238 126" />
          </g>
          {/* cejas */}
          <g fill="none" stroke="#2d1b18" strokeWidth="5" strokeLinecap="round">
            <path d={cara.l} /><path d={cara.r} />
          </g>
          {/* boca */}
          <g className="j-mouth">
            <path d={cara.m} fill={cara.c} stroke={INK} strokeWidth="3.5" strokeLinejoin="round" strokeLinecap="round" />
          </g>
          <path className="j-tongue j-xs" d="M145 203c0 13 4 18 5 18s5-5 5-18z" fill="#ff8aa0" stroke={INK} strokeWidth="3" />
          {/* flequillo */}
          <g className="j-hair">
            <path d="M150 34C84 34 44 78 52 152C62 138 66 124 70 112C100 106 132 92 150 72Z" fill="#2d1b18" />
            <path d="M150 34C216 34 256 78 248 152C238 138 234 124 230 112C200 106 168 92 150 72Z" fill="#2d1b18" />
            <path d="M100 50c-14 14-24 32-28 52M200 50c14 14 24 32 28 52M64 126c-2 10-2 18-4 26M236 126c2 10 2 18 4 26"
                  stroke="#4d322b" strokeWidth="3.5" strokeLinecap="round" fill="none" />
          </g>
          {/* aritos */}
          <circle cx="53" cy="180" r="6.5" fill="none" stroke="#e2b02c" strokeWidth="3.5" />
          <circle cx="247" cy="180" r="6.5" fill="none" stroke="#e2b02c" strokeWidth="3.5" />
          {/* extras de emoción */}
          <g className="j-tears j-xs">
            <g transform="translate(86 176)"><path className="j-drop" d="M0 0c5 8 7 12 0 15c-7-3-5-7 0-15z" fill="#8fd0ff" stroke={INK} strokeWidth="1.8" /></g>
            <g transform="translate(214 176)"><path className="j-drop" d="M0 0c5 8 7 12 0 15c-7-3-5-7 0-15z" fill="#8fd0ff" stroke={INK} strokeWidth="1.8" /></g>
          </g>
          <g className="j-puff j-xs" fill="#fff" stroke={INK} strokeWidth="2.5">
            <circle cx="172" cy="205" r="5" /><circle cx="172" cy="205" r="7" /><circle cx="172" cy="205" r="9" />
          </g>
          <g className="j-steam j-xs" fill="#fff" stroke={INK} strokeWidth="2.5">
            <circle cx="34" cy="96" r="9" /><circle cx="24" cy="78" r="7" /><circle cx="266" cy="96" r="9" /><circle cx="276" cy="78" r="7" />
          </g>
          <path className="j-vein j-xs" d="M222 56c6 0 8 4 8 8M240 56c-6 0-8 4-8 8M222 72c6 0 8-4 8-8M240 72c-6 0-8-4-8-8"
                fill="none" stroke="#e03a3a" strokeWidth="4" strokeLinecap="round" />
          <g className="j-dots j-xs" fill="#f2894f">
            <circle cx="212" cy="30" r="6" /><circle cx="232" cy="22" r="6" /><circle cx="252" cy="14" r="6" />
          </g>
          <g className="j-hearts j-xs"><text x="240" y="60">♥</text><text x="262" y="96">♥</text><text x="30" y="70">♥</text></g>
          <g className="j-waves j-xs" fill="none" stroke={INK} strokeWidth="3.5" strokeLinecap="round">
            <path d="M184 194q8 8 0 16" /><path d="M194 188q14 14 0 28" />
          </g>
        </g>
      </g>
    </svg>
  )
}
