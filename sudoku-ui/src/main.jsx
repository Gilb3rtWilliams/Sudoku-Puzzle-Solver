import { StrictMode, useCallback, useState } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import Splash from './Splash.jsx'
import './styles.css'

const SEEN_KEY = 'sudoku-splash-seen'

// Show the splash once per browser session. Add ?splash to the URL to see it again.
function shouldShowSplash() {
  try {
    if (new URLSearchParams(window.location.search).has('splash')) return true
    return !sessionStorage.getItem(SEEN_KEY)
  } catch {
    return true
  }
}

function Root() {
  const [showSplash, setShowSplash] = useState(shouldShowSplash)

  const finish = useCallback(() => {
    try {
      sessionStorage.setItem(SEEN_KEY, '1')
    } catch {
      /* storage unavailable: the splash just shows again next load */
    }
    setShowSplash(false)
  }, [])

  return (
    <>
      {/* The app mounts underneath so it is ready the moment the splash lifts; inert keeps it out of reach until then. */}
      <div inert={showSplash}>
        <App />
      </div>
      {showSplash && <Splash onDone={finish} />}
    </>
  )
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
