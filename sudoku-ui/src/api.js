const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

async function request(path, options) {
  let res
  try {
    res = await fetch(`${BASE}${path}`, options)
  } catch {
    throw new Error(`Can't reach the solver at ${BASE}. Is the backend running?`)
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = body?.detail
    const text = typeof detail === 'string' ? detail : 'Something went wrong on the server.'
    throw new Error(text)
  }
  return body
}

/** Upload a photo. Resolves with the grid as read, the solution (if any) and an overlay image. */
export function solvePhoto(file) {
  const form = new FormData()
  form.append('file', file)
  return request('/solve', { method: 'POST', body: form })
}

/** Solve a grid (flat array of 81) after the user has corrected it. */
export function solveGrid(grid) {
  const rows = Array.from({ length: 9 }, (_, r) => grid.slice(r * 9, r * 9 + 9))
  return request('/solve-grid', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ grid: rows }),
  })
}
