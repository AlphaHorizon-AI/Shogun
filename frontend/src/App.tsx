import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { Shell } from './components/layout/Shell'
import { Dashboard } from './pages/Dashboard'
import { Chat } from './pages/Chat'
import { ShogunProfile } from './pages/ShogunProfile'
import { SamuraiNetwork } from './pages/SamuraiNetwork'
import { Katana } from './pages/Katana'
import { Torii } from './pages/Torii'
import { Kaizen } from './pages/Kaizen'
import { Bushido } from './pages/Bushido'
import { Archives } from './pages/Archives'
import { Dojo } from './pages/Dojo'
import { Logs } from './pages/Logs'
import { Guide } from './pages/Guide'
import { Nexus } from './pages/Nexus'
import { Updates } from './pages/Updates'
import { Backups } from './pages/Backups'
import { SetupWizard } from './pages/SetupWizard'
import { useState, useEffect } from 'react'
import { useTranslation, I18nProvider } from './i18n'
import { Loader2 } from 'lucide-react'

/**
 * Wrapper that checks first-run status and redirects to /setup if needed.
 * Only affects the "/" route on initial load.
 */
function FirstRunGate({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<'loading' | 'first_run' | 'ready'>('loading')
  const location = useLocation()
  const { setLanguage } = useTranslation()

  useEffect(() => {
    // Only check once, only on initial page load
    fetch('/api/v1/setup/status')
      .then(r => r.json())
      .then(d => {
        const complete = d.data?.setup_complete ?? true
        if (d.data?.language) {
          setLanguage(d.data.language)
        }
        setStatus(complete ? 'ready' : 'first_run')
      })
      .catch(() => setStatus('ready'))
  }, [setLanguage])

  if (status === 'loading') {
    return (
      <div className="fixed inset-0 bg-[#0a0e1a] flex flex-col items-center justify-center gap-4">
        <Loader2 className="w-8 h-8 text-[#d4a017] animate-spin" />
        <p className="text-sm text-[#555] font-mono tracking-widest uppercase">Initializing Shogun...</p>
      </div>
    )
  }

  // First run: redirect to /setup (unless already on /setup)
  if (status === 'first_run' && location.pathname !== '/setup') {
    return <Navigate to="/setup" replace />
  }

  return <>{children}</>
}

/**
 * Setup page wrapper — handles completion and redirect.
 */
function SetupPage() {
  const navigate = useNavigate()
  return (
    <SetupWizard onComplete={() => {
      navigate('/guide', { replace: true })
    }} />
  )
}

function AppContent() {
  return (
    <Router>
      <FirstRunGate>
        <Routes>
          {/* Setup wizard — always accessible at /setup */}
          <Route path="/setup" element={<SetupPage />} />

          {/* Main Tenshu routes (wrapped in Shell) */}
          <Route path="/" element={<Shell><Dashboard /></Shell>} />
          <Route path="/chat" element={<Shell><Chat /></Shell>} />
          <Route path="/shogun" element={<Shell><ShogunProfile /></Shell>} />
          <Route path="/samurai" element={<Shell><SamuraiNetwork /></Shell>} />
          <Route path="/katana" element={<Shell><Katana /></Shell>} />
          <Route path="/torii" element={<Shell><Torii /></Shell>} />
          <Route path="/kaizen" element={<Shell><Kaizen /></Shell>} />
          <Route path="/bushido" element={<Shell><Bushido /></Shell>} />
          <Route path="/archives" element={<Shell><Archives /></Shell>} />
          <Route path="/dojo" element={<Shell><Dojo /></Shell>} />
          <Route path="/logs" element={<Shell><Logs /></Shell>} />
          <Route path="/guide" element={<Shell><Guide /></Shell>} />
          <Route path="/nexus" element={<Shell><Nexus /></Shell>} />
          <Route path="/updates" element={<Shell><Updates /></Shell>} />
          <Route path="/backups" element={<Shell><Backups /></Shell>} />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </FirstRunGate>
    </Router>
  )
}

function App() {
  return (
    <I18nProvider>
      <AppContent />
    </I18nProvider>
  )
}

export default App
