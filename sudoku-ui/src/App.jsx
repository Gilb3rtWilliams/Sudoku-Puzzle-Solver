import { useEffect, useMemo, useRef, useState } from 'react'
import Grid from './Grid.jsx'
import PhotoPanel from './PhotoPanel.jsx'
import Review from './Review.jsx'
import { checkAnswers, solveGrid, solvePhoto } from './api.js'
import { emptyGrid, findConflicts, sameGrid, toFlat } from './sudoku.js'

const MAX_BYTES = 10 * 1024 * 1024
const NO_CELLS = new Set()
const STEPS = ['Puzzle', 'Your answers', 'Review']

export default function App() {
  const [grid, setGrid] = useState(emptyGrid)
  const [readGrid, setReadGrid] = useState(null) // what the photo was read as, to know when the overlay is stale
  const [uncertain, setUncertain] = useState(() => new Set())
  const [solution, setSolution] = useState(null)
  const [solutionCount, setSolutionCount] = useState(null)
  const [message, setMessage] = useState('')
  const [isError, setIsError] = useState(false)
  const [busy, setBusy] = useState(null) // 'reading' | 'solving' | 'checking' | null
  const [photoUrl, setPhotoUrl] = useState(null)
  const [overlayUrl, setOverlayUrl] = useState(null)
  const [showOverlay, setShowOverlay] = useState(false)
  const photoUrlRef = useRef(null)

  // Play mode: `givens` is the locked puzzle (null while the puzzle is still being set up).
  const [givens, setGivens] = useState(null)
  const [checkResult, setCheckResult] = useState(null)
  const [revealed, setRevealed] = useState(() => new Set())
  const [active, setActive] = useState(null) // index of the mistake being looked at
  const gridRef = useRef(null)

  const playing = givens !== null
  const conflicts = useMemo(() => findConflicts(grid), [grid])
  const filled = grid.filter(Boolean).length
  const overlayFresh = overlayUrl && sameGrid(grid, readGrid)
  const answers = playing ? grid.filter((v, i) => v && !givens[i]).length : 0

  const wrongCells = useMemo(
    () => (checkResult ? new Set(checkResult.mistakes.map((m) => m.row * 9 + m.col)) : NO_CELLS),
    [checkResult],
  )
  const relatedCells = useMemo(() => {
    const m = checkResult?.mistakes.find((x) => x.row * 9 + x.col === active)
    return m ? new Set(m.clashes.map((c) => c.row * 9 + c.col)) : NO_CELLS
  }, [checkResult, active])

  useEffect(() => () => photoUrlRef.current && URL.revokeObjectURL(photoUrlRef.current), [])

  const say = (text, error = false) => {
    setMessage(text)
    setIsError(error)
  }

  const resetReview = () => {
    setCheckResult(null)
    setRevealed(new Set())
    setActive(null)
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
    if (givens?.[i]) return // clues are locked while playing
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
    if (checkResult) {
      // This cell is being redone, so drop its verdict; the rest stay until the next check.
      setCheckResult((r) => r && { ...r, stale: true, mistakes: r.mistakes.filter((m) => m.row * 9 + m.col !== i) })
      setRevealed((s) => {
        if (!s.has(i)) return s
        const next = new Set(s)
        next.delete(i)
        return next
      })
      if (active === i) setActive(null)
    }
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

  // Lock the puzzle and start asking for answers. Only a puzzle with exactly one solution can be graded.
  const handleStartPlay = async () => {
    if (conflicts.size) return say('Some digits repeat in a row, column or box. Fix the red cells first.', true)
    if (filled < 17) return say('Add at least 17 digits. Fewer than that never gives one unique solution.', true)
    setBusy('solving')
    try {
      const res = await solveGrid(grid)
      if (res.solution_count !== 1) {
        return say(
          res.solution_count
            ? 'This puzzle has more than one solution, so there is no single right answer to check. Look for a missing or misread clue.'
            : res.message,
          true,
        )
      }
      setGivens(grid.slice())
      setSolution(null)
      setSolutionCount(null)
      setUncertain(new Set())
      resetReview()
      say('')
    } catch (err) {
      say(err.message, true)
    } finally {
      setBusy(null)
    }
  }

  const handleCheck = async () => {
    setBusy('checking')
    try {
      const res = await checkAnswers(givens, grid)
      if (res.status !== 'ok') return say(res.message, true)
      setCheckResult(res)
      setRevealed(new Set())
      setActive(null)
      say('')
    } catch (err) {
      say(err.message, true)
    } finally {
      setBusy(null)
    }
  }

  const handleClearAnswers = () => {
    setGrid(givens.slice())
    resetReview()
    say('')
  }

  const leavePlay = () => {
    setGivens(null)
    resetReview()
  }

  const handleEditPuzzle = () => {
    setGrid(givens.slice()) // drop the answers; the clues go back to being editable
    leavePlay()
    say('')
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
    leavePlay()
    say('')
  }

  const handleActivate = (m) => {
    const i = m.row * 9 + m.col
    setActive(i)
    gridRef.current?.focus(i)
  }

  const handleReveal = (i) => setRevealed((s) => new Set(s).add(i))

  const statusText = message || (!playing && uncertain.size ? `Check the ringed cells: ${uncertain.size} may be misread.` : '')
  const step = !playing ? 0 : checkResult ? 2 : 1

  return (
    <main className="page">
      <header className="masthead">
        <h1>Sudoku from a photo</h1>
        <p>
          {checkResult?.solved
            ? 'Every cell is right. Well done!'
            : playing
              ? 'Fill in the blanks. Nothing is graded until you ask.'
              : 'Upload a photo, check what was read, fix any mistakes, then start playing.'}
        </p>
        <ol className="steps" aria-label="Progress">
          {STEPS.map((label, i) => (
            <li key={label} className={i === step ? 'step-current' : i < step ? 'step-done' : ''} aria-current={i === step ? 'step' : undefined}>
              <span className="step-num" aria-hidden="true">{i + 1}</span>
              {label}
            </li>
          ))}
        </ol>
      </header>

      <div className={`workspace${playing ? ' workspace-play' : ''}`}>
        {playing ? (
          <Review
            result={checkResult}
            active={active}
            revealed={revealed}
            onActivate={handleActivate}
            onReveal={handleReveal}
            onFill={handleCell}
          />
        ) : (
          <PhotoPanel
            photoUrl={photoUrl}
            overlayUrl={overlayFresh ? overlayUrl : null}
            showOverlay={showOverlay && overlayFresh}
            onToggleOverlay={() => setShowOverlay((s) => !s)}
            busy={busy === 'reading'}
            onFile={handleFile}
          />
        )}

        <section className="board" aria-label="Puzzle">
          <Grid
            ref={gridRef}
            grid={grid}
            solution={solution}
            uncertain={uncertain}
            conflicts={playing ? NO_CELLS : conflicts}
            givens={givens}
            wrong={wrongCells}
            related={relatedCells}
            disabled={busy === 'reading'}
            onChange={handleCell}
          />

          <p className={`status${isError ? ' status-error' : ''}`} role="status" aria-live="polite">
            {statusText || ' '}
          </p>

          <div className="board-actions">
            {playing ? (
              <>
                <button type="button" className="btn btn-primary" onClick={handleCheck} disabled={!!busy || answers === 0}>
                  {busy === 'checking' ? 'Checking…' : 'Check my answers'}
                </button>
                <button type="button" className="btn" onClick={handleClearAnswers} disabled={!!busy || answers === 0}>
                  Clear my answers
                </button>
                <button type="button" className="btn btn-quiet" onClick={handleEditPuzzle} disabled={!!busy}>
                  Edit puzzle
                </button>
                <button type="button" className="btn btn-quiet" onClick={handleClear} disabled={!!busy}>
                  New puzzle
                </button>
              </>
            ) : (
              <>
                <button type="button" className="btn btn-primary" onClick={handleStartPlay} disabled={!!busy || filled === 0}>
                  {busy === 'solving' ? 'Working…' : 'Start playing'}
                </button>
                <button type="button" className="btn" onClick={handleSolve} disabled={!!busy || filled === 0}>
                  Solve for me
                </button>
                <button type="button" className="btn btn-quiet" onClick={handleClear} disabled={!!busy}>
                  Start over
                </button>
                {solutionCount === 2 && <span className="note">Showing one of several solutions.</span>}
              </>
            )}
          </div>

          <ul className="legend" aria-label="Key">
            {playing ? (
              <>
                <li><span className="swatch swatch-ink" aria-hidden="true">7</span> Given clue</li>
                <li><span className="swatch swatch-pencil" aria-hidden="true">7</span> Your answer</li>
                <li><span className="swatch swatch-ring" aria-hidden="true" /> Marked wrong</li>
              </>
            ) : (
              <>
                <li><span className="swatch swatch-ink" aria-hidden="true">7</span> Read from the photo or typed by you</li>
                <li><span className="swatch swatch-pencil" aria-hidden="true">7</span> Solved</li>
                <li><span className="swatch swatch-ring" aria-hidden="true" /> Check this cell</li>
              </>
            )}
          </ul>
        </section>
      </div>
    </main>
  )
}
