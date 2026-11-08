import { useEffect, useMemo, useRef, useState } from 'react'
import Grid from './Grid.jsx'
import PhotoPanel from './PhotoPanel.jsx'
import { solveGrid, solvePhoto } from './api.js'
import { emptyGrid, findConflicts, sameGrid, toFlat } from './sudoku.js'

const MAX_BYTES = 10 * 1024 * 1024

export default function App() {
  const [grid, setGrid] = useState(emptyGrid)
  const [readGrid, setReadGrid] = useState(null) // what the photo was read as, to know when the overlay is stale
  const [uncertain, setUncertain] = useState(() => new Set())
  const [solution, setSolution] = useState(null)
  const [solutionCount, setSolutionCount] = useState(null)
  const [message, setMessage] = useState('')
  const [isError, setIsError] = useState(false)
  const [busy, setBusy] = useState(null) // 'reading' | 'solving' | null
  const [photoUrl, setPhotoUrl] = useState(null)
  const [overlayUrl, setOverlayUrl] = useState(null)
  const [showOverlay, setShowOverlay] = useState(false)
  const photoUrlRef = useRef(null)

  const conflicts = useMemo(() => findConflicts(grid), [grid])
  const filled = grid.filter(Boolean).length
  const overlayFresh = overlayUrl && sameGrid(grid, readGrid)

  useEffect(() => () => photoUrlRef.current && URL.revokeObjectURL(photoUrlRef.current), [])

  const say = (text, error = false) => {
    setMessage(text)
    setIsError(error)
  }

  const handleFile = async (file) => {
    if (!file.type.startsWith('image/')) return say('That file is not an image. Choose a JPG or PNG photo.', true)
    if (file.size > MAX_BYTES) return say('That photo is over 10 MB. Choose a smaller one.', true)

    if (photoUrlRef.current) URL.revokeObjectURL(photoUrlRef.current)
    const url = URL.createObjectURL(file)
    photoUrlRef.current = url
    setPhotoUrl(url)
    setOverlayUrl(null)
    setShowOverlay(false)
    setSolution(null)
    setSolutionCount(null)
    say('')
    setBusy('reading')
    try {
      const res = await solvePhoto(file)
      const flat = toFlat(res.grid)
      setGrid(flat)
      setReadGrid(flat)
      setUncertain(new Set(res.uncertain.map(({ row, col }) => row * 9 + col)))
      setSolution(res.solution ? res.solution.flat() : null)
      setSolutionCount(res.solution_count)
      if (res.overlay_png_base64) {
        setOverlayUrl(`data:image/png;base64,${res.overlay_png_base64}`)
        setShowOverlay(true)
      }
      say(res.message, res.solution_count !== 1 && !res.solution)
    } catch (err) {
      say(err.message, true)
    } finally {
      setBusy(null)
    }
  }

  const handleCell = (i, value) => {
    setGrid((g) => g.map((v, j) => (j === i ? value : v)))
    setUncertain((s) => {
      if (!s.has(i)) return s
      const next = new Set(s)
      next.delete(i)
      return next
    })
    // The old answer no longer matches the edited grid.
    setSolution(null)
    setSolutionCount(null)
    say('')
  }

  const handleSolve = async () => {
    if (conflicts.size) return say('Some digits repeat in a row, column or box. Fix the red cells, then solve.', true)
    if (filled < 17) return say('Add at least 17 digits. Fewer than that never gives one unique solution.', true)
    setBusy('solving')
    try {
      const res = await solveGrid(grid)
      setSolution(res.solution ? res.solution.flat() : null)
      setSolutionCount(res.solution_count)
      say(res.message, !res.solution)
    } catch (err) {
      say(err.message, true)
    } finally {
      setBusy(null)
    }
  }

  const handleClear = () => {
    if (photoUrlRef.current) URL.revokeObjectURL(photoUrlRef.current)
    photoUrlRef.current = null
    setPhotoUrl(null)
    setOverlayUrl(null)
    setShowOverlay(false)
    setGrid(emptyGrid())
    setReadGrid(null)
    setUncertain(new Set())
    setSolution(null)
    setSolutionCount(null)
    say('')
  }

  const statusText = message || (uncertain.size ? `Check the ringed cells: ${uncertain.size} may be misread.` : '')

  return (
    <main className="page">
      <header className="masthead">
        <h1>Sudoku from a photo</h1>
        <p>Upload a photo, check what was read, fix any mistakes, then solve.</p>
      </header>

      <div className="workspace">
        <PhotoPanel
          photoUrl={photoUrl}
          overlayUrl={overlayFresh ? overlayUrl : null}
          showOverlay={showOverlay && overlayFresh}
          onToggleOverlay={() => setShowOverlay((s) => !s)}
          busy={busy === 'reading'}
          onFile={handleFile}
        />

        <section className="board" aria-label="Puzzle">
          <Grid
            grid={grid}
            solution={solution}
            uncertain={uncertain}
            conflicts={conflicts}
            disabled={busy === 'reading'}
            onChange={handleCell}
          />

          <p className={`status${isError ? ' status-error' : ''}`} role="status" aria-live="polite">
            {statusText || '\u00A0'}
          </p>

          <div className="board-actions">
            <button type="button" className="btn btn-primary" onClick={handleSolve} disabled={!!busy || filled === 0}>
              {busy === 'solving' ? 'Solving…' : 'Solve'}
            </button>
            <button type="button" className="btn" onClick={handleClear} disabled={!!busy}>
              Start over
            </button>
            {solutionCount === 2 && <span className="note">Showing one of several solutions.</span>}
          </div>

          <ul className="legend" aria-label="Key">
            <li><span className="swatch swatch-ink" aria-hidden="true">7</span> Read from the photo or typed by you</li>
            <li><span className="swatch swatch-pencil" aria-hidden="true">7</span> Solved</li>
            <li><span className="swatch swatch-ring" aria-hidden="true" /> Check this cell</li>
          </ul>
        </section>
      </div>
    </main>
  )
}
