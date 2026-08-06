import { BrowserRouter as Router, Switch, Route, Redirect, useLocation } from 'react-router-dom'
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
const Logs = lazy(() => import('./pages/Logs').then(module => ({ default: module.Logs })))
const Guide = lazy(() => import('./pages/Guide').then(module => ({ default: module.Guide })))
const Nexus = lazy(() => import('./pages/Nexus').then(module => ({ default: module.Nexus })))
const Updates = lazy(() => import('./pages/Updates').then(module => ({ default: module.Updates })))
const Backups = lazy(() => import('./pages/Backups').then(module => ({ default: module.Backups })))
const Gensui = lazy(() => import('./pages/Gensui').then(module => ({ default: module.Gensui })))
const SetupWizard = lazy(() => import('./pages/SetupWizard').then(module => ({ default: module.SetupWizard })))
const PrivacyTelemetry = lazy(() => import('./pages/PrivacyTelemetry').then(module => ({ default: module.PrivacyTelemetry })))

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
        You may optionally share anonymous installation and weekly activity statistics.
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
        if (d.data?.operator_name) {
          localStorage.setItem('shogun_operator_name', d.data.operator_name)
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
    return <Redirect to="/setup" />
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

function AppContent() {
  return (
    <Router>
      <FirstRunGate>
        <Suspense fallback={<div className="fixed inset-0 bg-[#0a0e1a] flex items-center justify-center"><Loader2 className="w-8 h-8 text-[#d4a017] animate-spin" /></div>}>
          <Switch>
          {/* Setup wizard — always accessible at /setup */}
          <Route path="/setup" render={() => <SetupPage />} />

          {/* Main Tenshu routes (wrapped in Shell) */}
          <Route exact path="/" render={() => <Shell><Dashboard /></Shell>} />
          <Route path="/chat" render={() => <Shell><Chat /></Shell>} />
          <Route path="/shogun" render={() => <Shell><ShogunProfile /></Shell>} />
          <Route path="/samurai" render={() => <Shell><SamuraiNetwork /></Shell>} />
          <Route path="/katana" render={() => <Shell><Katana /></Shell>} />
          <Route path="/toolgate" render={() => <Shell><ToolGate /></Shell>} />
          <Route path="/torii" render={() => <Shell><Torii /></Shell>} />
          <Route path="/kaizen" render={() => <Shell><Kaizen /></Shell>} />
          <Route path="/bushido" render={() => <Shell><Bushido /></Shell>} />
          <Route path="/archives" render={() => <Shell><Archives /></Shell>} />
          <Route path="/dojo" render={() => <Shell><Dojo /></Shell>} />
          <Route path="/logs" render={() => <Shell><Logs /></Shell>} />
          <Route path="/guide" render={() => <Shell><Guide /></Shell>} />
          <Route path="/nexus" render={() => <Shell><Nexus /></Shell>} />
          <Route path="/updates" render={() => <Shell><Updates /></Shell>} />
          <Route path="/backups" render={() => <Shell><Backups /></Shell>} />
          <Route path="/gensui" render={() => <Shell><Gensui /></Shell>} />
          <Route path="/privacy-telemetry" render={() => <Shell><PrivacyTelemetry /></Shell>} />

          {/* Fallback */}
          <Route render={() => <Redirect to="/" />} />
          </Switch>
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
