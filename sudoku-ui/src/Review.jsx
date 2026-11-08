/**
 * Left-hand panel while playing: instructions before the first check, then the verdict and one
 * card per wrong cell. Each card explains the mistake first; the correct digit stays hidden until
 * the player asks for it, so they can have another go.
 */
export default function Review({ result, active, revealed, onActivate, onReveal, onFill }) {
  if (!result) {
    return (
      <section className="review" aria-label="Review">
        <h2 className="review-title">Your answers</h2>
        <p className="review-lead">
          Fill in the blank cells. Nothing is graded until you press <strong>Check my answers</strong>; then any
          mistakes are explained here.
        </p>
      </section>
    )
  }

  const { mistakes, stale, solved, entered, correct, wrong, blank } = result

  return (
    <section className="review" aria-label="Review">
      <h2 className="review-title">{solved ? 'Solved!' : 'Your answers'}</h2>

      <div role="status" aria-live="polite">
        {stale ? (
          <p className="review-lead">You've changed answers since the last check. Press Check my answers again.</p>
        ) : (
          <p className={`review-lead${wrong ? ' review-lead-bad' : ''}`}>{result.message}</p>
        )}
      </div>

      {!stale && (
        <dl className="review-stats">
          <div><dt>Entered</dt><dd>{entered}</dd></div>
          <div><dt>Right</dt><dd>{correct}</dd></div>
          <div><dt>Wrong</dt><dd>{wrong}</dd></div>
          <div><dt>Left</dt><dd>{blank}</dd></div>
        </dl>
      )}

      {mistakes.length > 0 && (
        <ol className="mistakes">
          {mistakes.map((m) => {
            const i = m.row * 9 + m.col
            const isRevealed = revealed.has(i)
            return (
              <li key={i} className={`mistake${active === i ? ' mistake-active' : ''}`}>
                <button type="button" className="mistake-head" onClick={() => onActivate(m)} aria-pressed={active === i}>
                  Row {m.row + 1}, column {m.col + 1}
                  <span className="mistake-entered">you entered {m.entered}</span>
                </button>
                <p className="mistake-why">{m.explanation}</p>
                {isRevealed ? (
                  <p className="mistake-answer">
                    The correct digit is <strong>{m.correct_digit}</strong>.{' '}
                    <button type="button" className="link-btn" onClick={() => onFill(i, m.correct_digit)}>
                      Fill it in
                    </button>
                  </p>
                ) : (
                  <button type="button" className="btn btn-quiet btn-small" onClick={() => onReveal(i)}>
                    Show answer
                  </button>
                )}
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}
