import { useRef, useState } from 'react'

/** Drop zone before a photo is chosen; the photo (original or solved overlay) afterwards. */
export default function PhotoPanel({ photoUrl, overlayUrl, showOverlay, onToggleOverlay, busy, onFile }) {
  const fileInput = useRef(null)
  const [dragging, setDragging] = useState(false)

  const pick = (file) => file && onFile(file)

  return (
    <section className="photo" aria-label="Photo">
      <input
        ref={fileInput}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => {
          pick(e.target.files?.[0])
          e.target.value = ''
        }}
      />

      {photoUrl ? (
        <div className="photo-frame">
          <img src={showOverlay && overlayUrl ? overlayUrl : photoUrl} alt={showOverlay && overlayUrl ? 'Your photo with the solved digits drawn in' : 'Your uploaded sudoku photo'} />
          {busy && <div className="photo-busy">Reading the grid…</div>}
        </div>
      ) : (
        <button
          type="button"
          className={`dropzone${dragging ? ' dragging' : ''}`}
          onClick={() => fileInput.current?.click()}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            pick(e.dataTransfer.files?.[0])
          }}
        >
          <span className="dropzone-title">Drop a photo of a sudoku here</span>
          <span className="dropzone-hint">or click to choose one. Straight-on, well-lit photos read best.</span>
        </button>
      )}

      <div className="photo-actions">
        <button type="button" className="btn" onClick={() => fileInput.current?.click()} disabled={busy}>
          {photoUrl ? 'Choose another photo' : 'Choose photo'}
        </button>
        {overlayUrl && (
          <button type="button" className="btn btn-quiet" onClick={onToggleOverlay} aria-pressed={showOverlay}>
            {showOverlay ? 'Show original' : 'Show solved photo'}
          </button>
        )}
      </div>
    </section>
  )
}
