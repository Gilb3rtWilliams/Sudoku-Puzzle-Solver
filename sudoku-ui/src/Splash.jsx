import { useCallback, useEffect, useMemo, useState } from 'react'
import './splash.css'

/**
 * Splash screen: a solved grid decrypts itself out of noise, then dissolves back into a puzzle
 * (the clues stay, everything else is erased), and one cell is circled in red pen with its
 * row, column and box washed in: the three constraints that make a Sudoku solvable.
 *
 * All timing lives in T (milliseconds). CSS only reacts to the phase classes set from here, so
 * there is one place to tune the choreography.
 */
const T = {
  wave: 650, // first digit starts scrambling
  dissolve: 3400, // non-clue digits start fading out
  ring: 4600, // red-pen circle + row/column/box wash
  title: 4700, // title and tagline arrive
  end: 5400, // animation clock stops
  auto: 8500, // continue on its own if nobody does anything
  leave: 650, // exit transition length (keep in sync with splash.css)
}

const SIZE = 9
const CELL = 30
const SOLUTION = (
  '534678912' + '672195348' + '198342567' +
  '859761423' + '426853791' + '713924856' +
  '961537284' + '287419635' + '345286179'
).split('').map(Number)

// Clue mask for the first 41 cells; the rest mirrors it (180° rotational symmetry, like a printed puzzle).
const HALF = '100100010' + '010001001' + '001000100' + '100010000' + '01001'
const CLUES = (() => {
  const mask = new Array(SIZE * SIZE).fill(false)
  for (let i = 0; i < HALF.length; i++) {
    mask[i] = HALF[i] === '1'
    mask[SIZE * SIZE - 1 - i] = HALF[i] === '1'
  }
  return mask
})()

const FOCUS = 40 // the circled cell (centre of the board)
const FOCUS_ROW = Math.floor(FOCUS / SIZE)
const FOCUS_COL = FOCUS % SIZE
const FOCUS_BOX = { row: Math.floor(FOCUS_ROW / 3) * 3, col: Math.floor(FOCUS_COL / 3) * 3 }

const mid = (n) => n * CELL + CELL / 2

function digitFor(i, t) {
  const row = Math.floor(i / SIZE)
  const col = i % SIZE
  const start = T.wave + (row + col) * 70
  const lock = start + 650 + ((i * 37) % 11) * 45
  const tick = Math.floor(t / 90)

  if (t < start) return { phase: 'hidden', ch: SOLUTION[i] }
  if (t < lock) {
    const h = (Math.imul(i + 1, 2654435761) ^ Math.imul(tick + 1, 40503) ^ Math.imul(tick + 7, i + 3)) >>> 0
    return { phase: 'noise', ch: 1 + ((h >>> 8) % SIZE) }
  }
  if (t < T.dissolve) return { phase: 'solved', ch: SOLUTION[i] }
  return { phase: CLUES[i] ? 'clue' : 'gone', ch: SOLUTION[i] }
}

function Lines() {
  const out = []
  for (let k = 0; k <= SIZE; k++) {
    const thick = k % 3 === 0
    const p = k * CELL
    const delay = thick ? k * 40 : 250 + k * 45
    const cls = thick ? 'sp-line sp-line--box' : 'sp-line'
    const style = { animationDelay: `${delay}ms` }
    out.push(
      <line key={`h${k}`} className={cls} style={style} x1={0} y1={p} x2={SIZE * CELL} y2={p} pathLength={1} />,
      <line key={`v${k}`} className={cls} style={{ animationDelay: `${delay + 60}ms` }} x1={p} y1={0} x2={p} y2={SIZE * CELL} pathLength={1} />,
    )
  }
  return out
}

export default function Splash({ onDone }) {
  const reduced = useMemo(
    () => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches,
    [],
  )
  const [t, setT] = useState(reduced ? T.end : 0)
  const [leaving, setLeaving] = useState(false)

  const leave = useCallback(() => setLeaving(true), [])

  // Animation clock, throttled to ~16 fps: plenty for flickering digits, cheap for 81 cells.
  useEffect(() => {
    if (reduced) return undefined
    let raf
    let last = -Infinity
    const start = performance.now()
    const frame = (now) => {
      const elapsed = Math.min(now - start, T.end)
      if (elapsed - last >= 60 || elapsed >= T.end) {
        last = elapsed
        setT(elapsed)
      }
      if (elapsed < T.end) raf = requestAnimationFrame(frame)
    }
    raf = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(raf)
  }, [reduced])

  // Continue on its own, or on any click / key press.
  useEffect(() => {
    const auto = setTimeout(leave, reduced ? 4000 : T.auto)
    const onKey = (e) => {
      if (e.key === 'Tab' || e.metaKey || e.ctrlKey || e.altKey || e.key === 'Shift') return
      leave()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      clearTimeout(auto)
      window.removeEventListener('keydown', onKey)
    }
  }, [leave, reduced])

  useEffect(() => {
    if (!leaving) return undefined
    const id = setTimeout(onDone, T.leave)
    return () => clearTimeout(id)
  }, [leaving, onDone])

  const cls = [
    'splash',
    t >= T.dissolve && 'is-puzzle',
    t >= T.ring && 'is-ringed',
    t >= T.title && 'is-titled',
    leaving && 'is-leaving',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={cls} role="dialog" aria-modal="true" aria-label="Sudoku from a photo" onClick={leave}>
      <div className="splash-stage">
        <svg className="splash-grid" viewBox="-8 -8 286 286" aria-hidden="true" focusable="false">
          {/* the three constraints on the circled cell */}
          <rect className="sp-wash" x={0} y={FOCUS_ROW * CELL} width={SIZE * CELL} height={CELL} />
          <rect className="sp-wash" x={FOCUS_COL * CELL} y={0} width={CELL} height={SIZE * CELL} />
          <rect className="sp-wash" x={FOCUS_BOX.col * CELL} y={FOCUS_BOX.row * CELL} width={CELL * 3} height={CELL * 3} />

          <Lines />

          {SOLUTION.map((_, i) => {
            const { phase, ch } = digitFor(i, t)
            return (
              <text
                key={i}
                className={`sp-digit sp-digit--${phase}`}
                x={mid(i % SIZE)}
                y={mid(Math.floor(i / SIZE))}
                dy="0.36em"
                textAnchor="middle"
                style={{ transitionDelay: phase === 'gone' ? `${((i * 53) % 17) * 40}ms` : undefined }}
              >
                {ch}
              </text>
            )
          })}

          <ellipse className="sp-ring" cx={mid(FOCUS_COL)} cy={mid(FOCUS_ROW)} rx={13.5} ry={12.5} transform={`rotate(-8 ${mid(FOCUS_COL)} ${mid(FOCUS_ROW)})`} pathLength={1} />
        </svg>

        <div className="splash-copy">
          <h1 className="splash-title" aria-label="Sudoku">
            {'SUDOKU'.split('').map((ch, i) => (
              <span key={i} aria-hidden="true" style={{ '--i': i }}>
                {ch}
              </span>
            ))}
          </h1>
          <p className="splash-tagline">
            Nine rows. Nine columns. <span className="splash-answer">One answer.</span>
          </p>
          <button type="button" className="splash-begin" onClick={leave}>
            Begin
          </button>
          <p className="splash-hint" aria-hidden="true">or press any key</p>
        </div>
      </div>
    </div>
  )
}
