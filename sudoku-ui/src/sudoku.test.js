import { describe, expect, it } from 'vitest'
import { emptyGrid, findConflicts, sameGrid, toFlat, toRows } from './sudoku.js'

describe('findConflicts', () => {
  it('finds nothing in an empty grid', () => {
    expect(findConflicts(emptyGrid()).size).toBe(0)
  })

  it('flags a repeat in a row', () => {
    const g = emptyGrid()
    g[0] = 5
    g[8] = 5
    expect([...findConflicts(g)].sort()).toEqual([0, 8])
  })

  it('flags a repeat in a column', () => {
    const g = emptyGrid()
    g[3] = 7
    g[3 + 9 * 6] = 7
    expect(findConflicts(g).size).toBe(2)
  })

  it('flags a repeat in a box but not across boxes', () => {
    const g = emptyGrid()
    g[0] = 4
    g[10] = 4 // row 1, col 1: same box
    g[3 + 9 * 4] = 4 // different row, column and box
    expect([...findConflicts(g)].sort((a, b) => a - b)).toEqual([0, 10])
  })
})

describe('helpers', () => {
  it('round-trips rows and flat arrays', () => {
    const g = Array.from({ length: 81 }, (_, i) => i % 10)
    expect(toFlat(toRows(g))).toEqual(g)
  })

  it('compares grids', () => {
    expect(sameGrid(emptyGrid(), emptyGrid())).toBe(true)
    expect(sameGrid(emptyGrid(), null)).toBe(false)
  })
})
