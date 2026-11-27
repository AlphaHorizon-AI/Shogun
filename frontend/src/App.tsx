import { BrowserRouter as Router, Navigate, Route, Routes } from 'react-router-dom'
import { Shell } from './components/layout/Shell'
import { lazy, Suspense, useState, useEffect, useRef } from 'react'
import { I18nProvider } from './i18n'
import { AlertTriangle, Loader2, X } from 'lucide-react'

const AgentFlow = lazy(() => import('./pages/AgentFlow').then(module => ({ default: module.AgentFlow })))
const Katana = lazy(() => import('./pages/Katana').then(module => ({ default: module.Katana })))
const ModelRoutingPanel = lazy(() => import('./pages/katana/ModelRoutingPanel'))
const WorkspaceSetup = lazy(() => import('./pages/WorkspaceSetup').then(module => ({ default: module.WorkspaceSetup })))

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
        if (!response.ok) return
        const payload = await response.json()
        const items: SystemNotification[] = payload.data || []
        if (active && items.length) {
          const latest = items[items.length - 1]
          lastSeen.current = latest.id
          setNotification(latest)
        }
      } catch {
        // Ignore transient polling failures.
      }
    }
    poll()
    const timer = window.setInterval(poll, 3000)
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

function RoutingPage() {
  const [editing, setEditing] = useState(false)
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-shogun-text tracking-tight">Routing Profiles</h2>
        <p className="text-xs text-shogun-subdued mt-1">
          Configure active model routing profiles, fallback chains, temperatures, and reasoning settings for AgentFlow nodes.
        </p>
      </div>
      <ModelRoutingPanel isEditingProfiles={editing} onEditProfiles={() => setEditing(v => !v)} />
    </div>
  )
}

function App() {
  return (
    <I18nProvider>
      <Router>
        <Suspense
          fallback={
            <div className="fixed inset-0 bg-[#0a0e1a] flex items-center justify-center">
              <Loader2 className="w-8 h-8 text-[#d4a017] animate-spin" />
            </div>
          }
        >
          <Routes>
            <Route path="/" element={<Shell><AgentFlow /></Shell>} />
            <Route path="/providers" element={<Shell><Katana /></Shell>} />
            <Route path="/routing" element={<Shell><RoutingPage /></Shell>} />
            <Route path="/workspace" element={<Shell><WorkspaceSetup /></Shell>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
        <SystemNotifications />
      </Router>
    </I18nProvider>
  )
}

export default App
