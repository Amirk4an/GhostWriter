import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { WidgetSurface } from './components/WidgetSurface.tsx'

/**
 * Второе окно Electron открывается с hash `ghostSurface=widget`.
 */
function parseGhostSurface(): 'panel' | 'widget' {
  const raw = window.location.hash.replace(/^#/, '')
  if (new URLSearchParams(raw).get('ghostSurface') === 'widget') {
    return 'widget'
  }
  return 'panel'
}

const surface = parseGhostSurface()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {surface === 'widget' ? <WidgetSurface /> : <App />}
  </StrictMode>,
)
