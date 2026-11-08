// Grids are flat arrays of 81 numbers (0 = blank), row by row.

export const SIZE = 9
export const emptyGrid = () => Array(SIZE * SIZE).fill(0)

export const toFlat = (rows) => rows.flat()
export const toRows = (flat) =>
  Array.from({ length: SIZE }, (_, r) => flat.slice(r * SIZE, (r + 1) * SIZE))

export const rowOf = (i) => Math.floor(i / SIZE)
export const colOf = (i) => i % SIZE
export const boxOf = (i) => Math.floor(rowOf(i) / 3) * 3 + Math.floor(colOf(i) / 3)

/** Indexes of cells whose digit repeats in the same row, column or box. */
export function findConflicts(grid) {
  const conflicts = new Set()
  const groups = [rowOf, colOf, boxOf]
  for (const keyOf of groups) {
    const seen = new Map() // "group:digit" -> first index
    grid.forEach((v, i) => {
      if (!v) return
      const key = `${keyOf(i)}:${v}`
      if (seen.has(key)) {
        conflicts.add(i)
        conflicts.add(seen.get(key))
      } else {
        seen.set(key, i)
      }
    })
  }
  return conflicts
}

export const sameGrid = (a, b) => !!a && !!b && a.every((v, i) => v === b[i])
