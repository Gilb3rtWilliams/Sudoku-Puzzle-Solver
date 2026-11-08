import { useImperativeHandle, useRef } from 'react'
import { SIZE, rowOf, colOf } from './sudoku.js'

/**
 * The editable 9x9 grid.
 * - `grid`: what the user sees as given (0 = blank)
 * - `solution`: optional solved grid, shown in pencil inside blank cells
 * - `uncertain`: Set of indexes the reader wasn't sure about
 * - `conflicts`: Set of indexes whose digit repeats in a row, column or box
 * - `givens`: when playing, the locked clues (flat array, 0 = player-editable); null while setting up
 * - `wrong`: Set of indexes the checker marked wrong
 * - `related`: Set of indexes to wash in blue (the cells that explain a mistake)
 * - `pointed`: Set of indexes to circle in dashed blue (the cell an explanation step deduces)
 * - `hint`: {index, digit} shown in pencil in that blank cell
 * - `ref`: exposes focus(i) so a mistake card can jump to its cell
 */
export default function Grid({ grid, solution, uncertain, conflicts, disabled, onChange, givens = null, wrong, related, pointed, hint, ref }) {
  const inputs = useRef([])
  useImperativeHandle(ref, () => ({ focus: (i) => inputs.current[i]?.focus() }), [])

  const focusCell = (i) => inputs.current[i]?.focus()

  const handleKeyDown = (e, i) => {
    const moves = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -SIZE, ArrowDown: SIZE }
    if (!(e.key in moves)) return
    e.preventDefault()
    const next = i + moves[e.key]
    const sameRow = rowOf(next) === rowOf(i)
    if (next < 0 || next >= SIZE * SIZE) return
    if ((e.key === 'ArrowLeft' || e.key === 'ArrowRight') && !sameRow) return
    focusCell(next)
  }

  const handleChange = (e, i) => {
    const digit = e.target.value.replace(/[^1-9]/g, '').slice(-1)
    onChange(i, digit ? Number(digit) : 0)
  }

  return (
    <div className="grid" role="group" aria-label="Sudoku grid">
      {grid.map((value, i) => {
        const r = rowOf(i)
        const c = colOf(i)
        const classes = ['cell']
        if (c % 3 === 2 && c < SIZE - 1) classes.push('box-right')
        if (r % 3 === 2 && r < SIZE - 1) classes.push('box-bottom')
        if (uncertain.has(i)) classes.push('uncertain')
        if (conflicts.has(i)) classes.push('conflict')
        const locked = !!givens?.[i]
        if (locked) classes.push('given')
        else if (givens && value) classes.push('entry')
        if (wrong?.has(i)) classes.push('wrong')
        if (related?.has(i)) classes.push('related')
        if (pointed?.has(i)) classes.push('pointed')
        const solved = !value ? (hint?.index === i ? hint.digit : solution ? solution[i] : 0) : 0
        const label =
          `Row ${r + 1}, column ${c + 1}` +
          (locked ? ', given clue' : '') +
          (value ? `, ${value}` : solved ? `, solved as ${solved}` : ', blank') +
          (uncertain.has(i) ? ', check this cell' : '') +
          (conflicts.has(i) ? ', repeats in its row, column or box' : '') +
          (wrong?.has(i) ? ', marked wrong' : '')
        return (
          <div className={classes.join(' ')} key={i}>
            <input
              ref={(el) => (inputs.current[i] = el)}
              type="text"
              inputMode="numeric"
              autoComplete="off"
              maxLength={2}
              value={value || ''}
              placeholder={solved ? String(solved) : ''}
              disabled={disabled}
              readOnly={locked}
              aria-label={label}
              onChange={(e) => handleChange(e, i)}
              onKeyDown={(e) => handleKeyDown(e, i)}
              onFocus={(e) => e.target.select()}
            />
          </div>
        )
      })}
    </div>
  )
}
