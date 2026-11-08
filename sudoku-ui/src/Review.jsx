/**
 * Left-hand panel while playing: instructions before the first check, a hint card when one was
 * asked for, then the verdict and one card per wrong cell. Explanations come first; the correct
 * digit stays hidden until the player asks for it, so they can have another go.
 */
function Steps({ steps, owner, on, activeStep, onStep, label }) {
  if (!steps.length) return null
  return (
    <details className="mistake-steps">
      <summary>{label(steps.length)}</summary>
      <ol>
        {steps.map((st) => {
          const active = on && activeStep === st.number
          return (
            <li key={st.number}>
              <button
                type="button"
                className={`step-btn${active ? ' step-btn-on' : ''}`}
                aria-pressed={active}
                onClick={() => onStep(owner, st)}
              >
                {st.text}
              </button>
            </li>
          )
        })}
      </ol>
    </details>
  )
}

function HintCard({ hint, level, onLevel, onClose, active, activeStep, onStep, onFill }) {
  const i = hint.row * 9 + hint.col
  return (
    <div className={`hint-card${active === 'hint' ? ' hint-card-active' : ''}`}>
      <div className="hint-head">
        <strong>Hint</strong>
        <button type="button" className="link-btn" onClick={onClose}>
          Close
        </button>
      </div>

      {hint.wrong_entries > 0 && (
        <p className="hint-warn">
          {hint.wrong_entries === 1 ? 'One of your answers is' : `${hint.wrong_entries} of your answers are`} wrong.
          This hint ignores {hint.wrong_entries === 1 ? 'it' : 'them'}; press Check my answers to see which.
        </p>
      )}

      <p className="hint-nudge">{hint.nudge}</p>

      {level === 0 && (
        <button type="button" className="btn btn-quiet btn-small" onClick={() => onLevel(1)}>
          Show the reasoning
        </button>
      )}

      {level >= 1 && (
        <>
          <p className="mistake-why">{hint.explanation}</p>
          <Steps
            steps={hint.steps}
            owner="hint"
            on={active === 'hint'}
            activeStep={activeStep}
            onStep={onStep}
            label={(n) => `Show the ${n} step${n === 1 ? '' : 's'} this relies on`}
          />
        </>
      )}

      {level === 1 && (
        <button type="button" className="btn btn-quiet btn-small" onClick={() => onLevel(2)}>
          Show answer
        </button>
      )}

      {level >= 2 && (
        <p className="mistake-answer">
          Row {hint.row + 1}, column {hint.col + 1} is <strong>{hint.correct_digit}</strong>.{' '}
          <button type="button" className="link-btn" onClick={() => onFill(i, hint.correct_digit)}>
            Fill it in
          </button>
        </p>
      )}
    </div>
  )
}

export default function Review({
  result, active, activeStep, hint, hintLevel, onHintLevel, onHintClose,
  revealed, onActivate, onStep, onReveal, onFill,
}) {
  const hintCard = hint && (
    <HintCard
      hint={hint}
      level={hintLevel}
      onLevel={onHintLevel}
      onClose={onHintClose}
      active={active}
      activeStep={activeStep}
      onStep={onStep}
      onFill={onFill}
    />
  )

  if (!result) {
    return (
      <section className="review" aria-label="Review">
        <h2 className="review-title">Your answers</h2>
        <p className="review-lead">
          Fill in the blank cells. Nothing is graded until you press <strong>Check my answers</strong>; then any
          mistakes are explained here. Stuck? <strong>Hint</strong> gives the most direct next move, a little at a time.
        </p>
        {hintCard}
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

      {hintCard}

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
                  {m.kind === 'contradiction' && <span className="mistake-kind">shown by contradiction</span>}
                </button>
                <p className="mistake-why">{m.explanation}</p>
                <Steps
                  steps={m.steps}
                  owner={m}
                  on={active === i}
                  activeStep={activeStep}
                  onStep={onStep}
                  label={(n) =>
                    m.kind === 'contradiction'
                      ? `Show the ${n} step${n === 1 ? '' : 's'} of the argument`
                      : `Show the ${n} step${n === 1 ? '' : 's'} this relies on`
                  }
                />
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
