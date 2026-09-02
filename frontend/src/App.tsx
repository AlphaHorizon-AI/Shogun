import { BrowserRouter as Router, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Shell } from './components/layout/Shell'
import { lazy, Suspense, useState, useEffect, useRef } from 'react'
import { useTranslation, I18nProvider } from './i18n'
import { AlertTriangle, Loader2, X } from 'lucide-react'

const Dashboard = lazy(() => import('./pages/Dashboard').then(module => ({ default: module.Dashboard })))
const Chat = lazy(() => import('./pages/Chat').then(module => ({ default: module.Chat })))
const ShogunProfile = lazy(() => import('./pages/ShogunProfile').then(module => ({ default: module.ShogunProfile })))
const SamuraiNetwork = lazy(() => import('./pages/SamuraiNetwork').then(module => ({ default: module.SamuraiNetwork })))
const Katana = lazy(() => import('./pages/Katana').then(module => ({ default: module.Katana })))
const ToolGate = lazy(() => import('./pages/ToolGate').then(module => ({ default: module.ToolGate })))
const Torii = lazy(() => import('./pages/Torii').then(module => ({ default: module.Torii })))
const Kaizen = lazy(() => import('./pages/Kaizen').then(module => ({ default: module.Kaizen })))
const Bushido = lazy(() => import('./pages/Bushido').then(module => ({ default: module.Bushido })))
const Archives = lazy(() => import('./pages/Archives').then(module => ({ default: module.Archives })))
const Dojo = lazy(() => import('./pages/Dojo').then(module => ({ default: module.Dojo })))
const Guide = lazy(() => import('./pages/Guide').then(module => ({ default: module.Guide })))
const Updates = lazy(() => import('./pages/Updates').then(module => ({ default: module.Updates })))
const Backups = lazy(() => import('./pages/Backups').then(module => ({ default: module.Backups })))
const SetupWizard = lazy(() => import('./pages/SetupWizard').then(module => ({ default: module.SetupWizard })))
const PrivacyTelemetry = lazy(() => import('./pages/PrivacyTelemetry').then(module => ({ default: module.PrivacyTelemetry })))
const About = lazy(() => import('./pages/About').then(module => ({ default: module.About })))

interface SystemNotification {
  id: string
  title: string
  message: string
  severity: string
}

function SystemNotifications() {
  const [notification, setNotification] = useState<SystemNotification | null>(null)
  const lastSeen = useRef<string | null>(null)

  useEffect(() => {
    let active = true
    const poll = async () => {
      try {
        const suffix = lastSeen.current ? `?after=${encodeURIComponent(lastSeen.current)}` : ''
        const response = await fetch(`/api/v1/system/notifications${suffix}`)
        const payload = await response.json()
        const items: SystemNotification[] = payload.data || []
        if (active && items.length) {
          const latest = items[items.length - 1]
          lastSeen.current = latest.id
          setNotification(latest)
        }
      } catch {
        // Notifications are supplementary; transient polling failures are harmless.
      }
    }
    poll()
    const timer = window.setInterval(poll, 2000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    if (!notification) return
    const timer = window.setTimeout(() => setNotification(null), 12000)
    return () => window.clearTimeout(timer)
  }, [notification])

  if (!notification) return null
  return (
    <div className="fixed right-5 top-5 z-[9999] w-[min(440px,calc(100vw-2.5rem))] rounded-xl border border-amber-400/50 bg-[#15120a] p-4 shadow-2xl shadow-amber-500/20">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" />
        <div className="min-w-0 flex-1">
          <p className="font-bold text-amber-200">{notification.title}</p>
          <p className="mt-1 text-sm leading-relaxed text-amber-50/80">{notification.message}</p>
        </div>
        <button onClick={() => setNotification(null)} className="text-amber-100/60 hover:text-amber-100" aria-label="Dismiss notification">
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

function TelemetryInvitation() {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    fetch('/api/v1/telemetry/status')
      .then(response => response.ok ? response.json() : null)
      .then(payload => setVisible(Boolean(payload?.show_first_run_prompt)))
      .catch(() => {})
  }, [])

  const dismiss = () => {
    setVisible(false)
    fetch('/api/v1/telemetry/dismiss', { method: 'POST' }).catch(() => {})
  }

  if (!visible) return null
  return (
    <div className="fixed bottom-5 right-5 z-[9998] w-[min(440px,calc(100vw-2.5rem))] rounded-xl border border-shogun-gold/40 bg-[#11131a] p-4 shadow-2xl">
      <button onClick={dismiss} className="absolute right-3 top-3 text-shogun-subdued hover:text-shogun-text" aria-label="Dismiss telemetry invitation">
        <X className="h-4 w-4" />
      </button>
      <h2 className="pr-8 font-bold text-shogun-gold">Help improve Shogun AFM</h2>
      <p className="mt-2 text-sm leading-relaxed text-shogun-subdued">
        You may optionally share pseudonymous installation and weekly activity statistics.
        No prompts, files, memory, messages, identities, or credentials are collected.
        Nothing is sent unless you explicitly opt in.
      </p>
      <div className="mt-3 flex gap-3">
        <a href="/privacy-telemetry" className="rounded-lg bg-shogun-gold px-3 py-2 text-xs font-bold text-black">Review exact data</a>
        <button onClick={dismiss} className="rounded-lg border border-shogun-border px-3 py-2 text-xs">No thanks</button>
      </div>
    </div>
  )
}

function BuildRefreshGuard() {
  useEffect(() => {
    let active = true
    const storageKey = 'shogun_loaded_build'

    const checkBuild = async () => {
      try {
        const response = await fetch('/api/v1/health', { cache: 'no-store' })
        const payload = await response.json()
        const currentBuild = payload?.build != null ? String(payload.build) : null
        if (!active || !currentBuild) return

        const previousBuild = sessionStorage.getItem(storageKey)
        sessionStorage.setItem(storageKey, currentBuild)

        if (previousBuild && previousBuild !== currentBuild) {
          window.location.reload()
        }
      } catch {
        // The app can still run while the server is warming up.
      }
    }

    checkBuild()
    const timer = window.setInterval(checkBuild, 5000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  return null
}

/**
 * Wrapper that checks first-run status and redirects to /setup if needed.
 * Only affects the "/" route on initial load.
 */
function FirstRunGate({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<'loading' | 'first_run' | 'ready' | 'blocked'>('loading')
  const [failureReason, setFailureReason] = useState('')
  const location = useLocation()
  const { setLanguage } = useTranslation()

  useEffect(() => {
    // Only check once, only on initial page load
    fetch('/api/v1/setup/status')
      .then(async response => {
        if (!response.ok) {
          if (response.status === 401) {
            setFailureReason('Open the private Primary Admin bootstrap link shown by the Server installer.')
          } else if (response.status === 503) {
            setFailureReason('The server infrastructure administrator credential is not configured.')
          } else {
            setFailureReason(`Setup status could not be loaded (HTTP ${response.status}).`)
          }
          setStatus('blocked')
          return null
        }
        return response.json()
      })
      .then(d => {
        if (!d) return
        const complete = d.data?.setup_complete
        if (typeof complete !== 'boolean') {
          setFailureReason('The setup service returned an invalid status response.')
          setStatus('blocked')
          return
        }
        if (d.data?.language) {
          setLanguage(d.data.language)
        }
        if (d.data?.operator_name) {
          localStorage.setItem('shogun_operator_name', d.data.operator_name)
        }
        setStatus(complete ? 'ready' : 'first_run')
      })
      .catch(() => {
        setFailureReason('The setup service is temporarily unavailable.')
        setStatus('blocked')
      })
  }, [setLanguage])

  if (status === 'loading') {
    return (
      <div className="fixed inset-0 bg-[#0a0e1a] flex flex-col items-center justify-center gap-4">
        <Loader2 className="w-8 h-8 text-[#d4a017] animate-spin" />
        <p className="text-sm text-[#555] font-mono tracking-widest uppercase">Initializing Shogun...</p>
      </div>
    )
  }

  if (status === 'blocked') {
    return (
      <div className="fixed inset-0 bg-[#0a0e1a] flex items-center justify-center p-6">
        <div className="w-full max-w-xl rounded-xl border border-amber-400/30 bg-[#121827] p-8 shadow-2xl">
          <AlertTriangle className="h-8 w-8 text-amber-400" />
          <h1 className="mt-5 text-xl font-bold text-white">Primary Admin authorization required</h1>
          <p className="mt-3 text-sm leading-relaxed text-slate-300">{failureReason}</p>
          <p className="mt-3 text-sm leading-relaxed text-slate-400">
            The setup credential is accepted only from the URL fragment, removed before the first API
            request, and retained only for this browser-tab session. Do not put it in a query string,
            bookmark, screenshot, or shared log.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-6 rounded-lg border border-amber-400/40 bg-amber-400/10 px-4 py-2 text-sm font-semibold text-amber-200 hover:bg-amber-400/20"
          >
            Retry authorization
          </button>
        </div>
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
  return (
    <SetupWizard onComplete={() => {
      window.location.href = '/guide'
    }} />
  )
}

function MissionControlRedirect() {
  const location = useLocation()
  const searchParams = new URLSearchParams(location.search)
  searchParams.set('tab', 'mission-control')
  return <Navigate to={`/chat?${searchParams.toString()}`} replace />
}

function AppContent() {
  return (
    <Router>
      <FirstRunGate>
        <Suspense fallback={<div className="fixed inset-0 bg-[#0a0e1a] flex items-center justify-center"><Loader2 className="w-8 h-8 text-[#d4a017] animate-spin" /></div>}>
          <Routes>
          {/* Setup wizard — always accessible at /setup */}
          <Route path="/setup" element={<SetupPage />} />

          {/* Main Tenshu routes (wrapped in Shell) */}
          <Route path="/" element={<Shell><Dashboard /></Shell>} />
          <Route path="/chat" element={<Shell><Chat /></Shell>} />
          <Route path="/mission-control" element={<MissionControlRedirect />} />
          <Route path="/shogun" element={<Shell><ShogunProfile /></Shell>} />
          <Route path="/samurai" element={<Shell><SamuraiNetwork /></Shell>} />
          <Route path="/katana" element={<Shell><Katana /></Shell>} />
          <Route path="/toolgate" element={<Shell><ToolGate /></Shell>} />
          <Route path="/torii" element={<Shell><Torii /></Shell>} />
          <Route path="/kaizen" element={<Shell><Kaizen /></Shell>} />
          <Route path="/bushido" element={<Shell><Bushido /></Shell>} />
          <Route path="/archives" element={<Shell><Archives /></Shell>} />
          <Route path="/dojo" element={<Shell><Dojo /></Shell>} />
          <Route path="/guide" element={<Shell><Guide /></Shell>} />
          <Route path="/updates" element={<Shell><Updates /></Shell>} />
          <Route path="/backups" element={<Shell><Backups /></Shell>} />
          <Route path="/privacy-telemetry" element={<Shell><PrivacyTelemetry /></Shell>} />
          <Route path="/about" element={<Shell><About /></Shell>} />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </FirstRunGate>
    </Router>
  )
}

function App() {
  return (
    <I18nProvider>
      <BuildRefreshGuard />
      <AppContent />
      <SystemNotifications />
      <TelemetryInvitation />
    </I18nProvider>
  )
}

export default App
