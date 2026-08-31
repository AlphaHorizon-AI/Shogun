import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
} from '@xyflow/react'
import type { Edge, Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  Activity,
  AlertTriangle,
  Bot,
  Check,
  CircleDollarSign,
  Clock3,
  GitBranch,
  Layers3,
  Loader2,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Route,
  Send,
  Shield,
  Sparkles,
  Square,
  Target,
  Trash2,
  UserRoundCog,
  X,
} from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { cn } from '../lib/utils'

type RecordData = Record<string, any>

interface MissionSummary extends RecordData {
  id: string
  title: string
  objective: string
  status: string
  progress_percent: number
  posture_at_creation: string
  updated_at: string
}

interface MissionDetail extends MissionSummary {
  agents: RecordData[]
  tasks: RecordData[]
  plans: RecordData[]
  events: RecordData[]
  approvals: RecordData[]
  learning: RecordData[]
  artifacts: RecordData[]
}

const terminalStates = new Set(['completed', 'failed', 'cancelled'])
const activeStates = new Set(['planning', 'running', 'replanning', 'completing', 'learning'])
const pausableStates = new Set(['planning', 'running', 'waiting', 'blocked_user', 'blocked_approval', 'replanning'])

function label(value?: string) {
  return String(value || 'unknown').replaceAll('_', ' ')
}

function statusClass(status?: string) {
  const value = String(status || '').toLowerCase()
  if (value === 'completed') return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
  if (value === 'failed' || value === 'cancelled') return 'border-red-500/40 bg-red-500/10 text-red-300'
  if (value.includes('paused') || value.includes('blocked') || value === 'waiting') return 'border-amber-500/40 bg-amber-500/10 text-amber-300'
  if (activeStates.has(value) || value === 'ready' || value === 'active') return 'border-cyan-500/40 bg-cyan-500/10 text-cyan-300'
  return 'border-shogun-border bg-shogun-card text-shogun-subdued'
}

function StatusBadge({ status }: { status?: string }) {
  return (
    <span className={cn('inline-flex items-center rounded border px-2 py-1 text-[9px] font-bold uppercase tracking-widest', statusClass(status))}>
      {label(status)}
    </span>
  )
}

async function api(path: string, init?: RequestInit) {
  const response = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload.detail?.message || payload.detail || `HTTP ${response.status}`)
  return payload.data
}

interface MissionControlProps {
  embedded?: boolean
}

function MissionControlContent({ embedded = false }: MissionControlProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const [missions, setMissions] = useState<MissionSummary[]>([])
  const [mission, setMission] = useState<MissionDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedNode, setSelectedNode] = useState<RecordData | null>(null)
  const [bottomTab, setBottomTab] = useState<'timeline' | 'plans' | 'approvals' | 'learning' | 'artifacts'>('timeline')
  const [showAgents, setShowAgents] = useState(true)
  const [showTasks, setShowTasks] = useState(true)
  const [showDependencies, setShowDependencies] = useState(true)
  const [steering, setSteering] = useState('')
  const [showSpecialist, setShowSpecialist] = useState(false)
  const [specialist, setSpecialist] = useState({ role_name: '', objective: '', spawn_reason: '' })
  const [deletingMissionId, setDeletingMissionId] = useState<string | null>(null)
  const [missionAction, setMissionAction] = useState<'pause' | 'resume' | 'cancel' | null>(null)
  const [confirmingStop, setConfirmingStop] = useState(false)
  const [notice, setNotice] = useState('')
  const selectedMissionId = searchParams.get('mission')

  const selectMission = useCallback((missionId: string, replace = false) => {
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set('mission', missionId)
    if (embedded) nextParams.set('tab', 'mission-control')
    setSelectedNode(null)
    setConfirmingStop(false)
    setSearchParams(nextParams, { replace })
  }, [embedded, searchParams, setSearchParams])

  const refreshList = useCallback(async () => {
    const data = await api('/api/v1/supermode/missions?limit=200')
    setMissions(data || [])
    if (!searchParams.get('mission') && data?.[0]?.id) {
      selectMission(data[0].id, true)
    }
  }, [searchParams, selectMission])

  const refreshDetail = useCallback(async () => {
    if (!selectedMissionId) {
      setMission(null)
      return
    }
    const data = await api(`/api/v1/supermode/missions/${selectedMissionId}`)
    setMission(data)
  }, [selectedMissionId])

  const refresh = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true)
    try {
      await Promise.all([refreshList(), refreshDetail()])
      setError('')
    } catch (err: any) {
      setError(err.message || 'Supermode Canvas could not load.')
    } finally {
      if (!quiet) setLoading(false)
    }
  }, [refreshDetail, refreshList])

  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => void refresh(true), 4000)
    return () => window.clearInterval(timer)
  }, [refresh])

  const mutate = async (action: string, body?: RecordData): Promise<boolean> => {
    if (!mission) return false
    const controlAction = action === 'pause' || action === 'resume' || action === 'cancel' ? action : null
    if (controlAction) setMissionAction(controlAction)
    setNotice('')
    try {
      const updated = await api(`/api/v1/supermode/missions/${mission.id}/${action}`, {
        method: 'POST',
        body: JSON.stringify(body || {}),
      })
      if (controlAction) {
        setMission(current => current?.id === updated.id ? { ...current, ...updated } : current)
        setMissions(current => current.map(item => item.id === updated.id ? { ...item, ...updated } : item))
        setSelectedNode(current => current?.kind === 'commander' ? { ...current, record: { ...current.record, ...updated } } : current)
        setNotice(controlAction === 'pause' ? 'Mission paused. In-flight work will stop at its current checkpoint.' : controlAction === 'resume' ? 'Mission resumed.' : 'Mission stopped. No new mission work will be started.')
      } else {
        await refresh()
      }
      setError('')
      return true
    } catch (err: any) {
      setError(err.message || `Mission could not ${action}.`)
      return false
    } finally {
      if (controlAction) setMissionAction(null)
    }
  }

  const deleteMission = async (item: MissionSummary) => {
    if (!terminalStates.has(item.status)) {
      setError('Stop this mission before deleting it. Active mission runs cannot be deleted.')
      return
    }
    if (!window.confirm(`Delete the run “${item.title}”? Its run history will be removed, but generated workspace files will be kept.`)) return

    setDeletingMissionId(item.id)
    try {
      await api(`/api/v1/supermode/missions/${item.id}`, { method: 'DELETE' })
      const remainingMissions = missions.filter(candidate => candidate.id !== item.id)
      setMissions(remainingMissions)
      if (selectedMissionId === item.id) {
        setMission(null)
        setSelectedNode(null)
        const nextParams = new URLSearchParams(searchParams)
        const replacementMission = remainingMissions[0]
        if (replacementMission) nextParams.set('mission', replacementMission.id)
        else nextParams.delete('mission')
        if (embedded) nextParams.set('tab', 'mission-control')
        setSearchParams(nextParams, { replace: true })
      }
      setError('')
    } catch (err: any) {
      setError(err.message || 'Mission run could not be deleted.')
    } finally {
      setDeletingMissionId(null)
    }
  }

  const graph = useMemo(() => {
    if (!mission) return { nodes: [] as Node[], edges: [] as Edge[] }
    const nodes: Node[] = []
    const edges: Edge[] = []
    nodes.push({
      id: 'commander',
      position: { x: 360, y: 20 },
      data: {
        kind: 'commander',
        label: `⚔ Mission Commander\n${label(mission.status)} · Plan v${mission.current_plan_version}`,
        record: mission,
      },
      style: {
        width: 230,
        whiteSpace: 'pre-line',
        border: '1px solid rgba(212,160,23,.65)',
        borderRadius: 14,
        background: '#17140b',
        color: '#f5d675',
        padding: 14,
        fontWeight: 700,
        textAlign: 'center',
        boxShadow: '0 0 28px rgba(212,160,23,.13)',
      },
    })
    const agentPositions = new Map<string, { x: number; y: number }>()
    if (showAgents) {
      mission.agents.forEach((agent, index) => {
        const x = 35 + (index % 4) * 255
        const y = 180 + Math.floor(index / 4) * 190
        agentPositions.set(agent.id, { x, y })
        nodes.push({
          id: `agent:${agent.id}`,
          position: { x, y },
          data: {
            kind: 'agent',
            label: `${agent.role_name}\n${agent.source_type === 'fleet' ? 'fleet' : 'spawned'} · ${label(agent.status)}${agent.model_calls ? ` · ${agent.model_calls} calls` : ''}`,
            record: agent,
          },
          style: {
            width: 210,
            minHeight: 74,
            whiteSpace: 'pre-line',
            border: agent.status === 'failed' ? '1px solid rgba(239,68,68,.6)' : '1px solid rgba(34,211,238,.38)',
            borderRadius: 12,
            background: '#0c1720',
            color: '#bdeef4',
            padding: 12,
            textAlign: 'left',
          },
        })
        edges.push({ id: `commander-agent:${agent.id}`, source: 'commander', target: `agent:${agent.id}`, animated: agent.status === 'active', style: { stroke: '#d4a017' } })
      })
    }
    if (showTasks) {
      mission.tasks.forEach((task, index) => {
        const agentPosition = agentPositions.get(task.assigned_agent_id)
        const x = agentPosition ? agentPosition.x + 12 : 30 + (index % 4) * 250
        const y = agentPosition ? agentPosition.y + 112 + (index % 2) * 90 : 390 + Math.floor(index / 4) * 120
        nodes.push({
          id: `task:${task.id}`,
          position: { x, y },
          data: { kind: 'task', label: `${task.title}\n${label(task.status)}${task.model_name ? ` · ${task.model_name}` : ''}`, record: task },
          style: {
            width: 190,
            minHeight: 62,
            whiteSpace: 'pre-line',
            border: task.status === 'failed' ? '1px solid rgba(239,68,68,.65)' : task.status === 'completed' ? '1px solid rgba(16,185,129,.55)' : '1px solid rgba(99,102,241,.45)',
            borderRadius: 10,
            background: '#101126',
            color: '#d7dbff',
            padding: 10,
            fontSize: 11,
          },
        })
        if (showAgents && task.assigned_agent_id) {
          edges.push({ id: `agent-task:${task.id}`, source: `agent:${task.assigned_agent_id}`, target: `task:${task.id}`, animated: task.status === 'running', style: { stroke: '#4a8cc7' } })
        } else {
          edges.push({ id: `commander-task:${task.id}`, source: 'commander', target: `task:${task.id}`, style: { stroke: '#4a8cc7' } })
        }
        if (showDependencies) {
          ;(task.depends_on_task_ids || []).forEach((dependency: string) => {
            edges.push({ id: `dependency:${dependency}:${task.id}`, source: `task:${dependency}`, target: `task:${task.id}`, animated: task.status === 'ready', label: 'depends', style: { stroke: '#6366f1', strokeDasharray: '5 4' }, labelStyle: { fill: '#9298c5', fontSize: 9 } })
          })
        }
      })
    }
    return { nodes, edges }
  }, [mission, showAgents, showTasks, showDependencies])

  const detailRecord = selectedNode?.record || mission
  const selectedKind = selectedNode?.kind

  if (loading && !mission && missions.length === 0) {
    return <div className="flex h-full items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-shogun-gold" /></div>
  }

  return (
    <div className={cn('flex min-h-0 flex-col gap-3 overflow-hidden', embedded ? 'h-full' : 'h-[calc(100vh-4rem)] min-h-[720px] p-4')}>
      <header className="flex shrink-0 items-center justify-between rounded-xl border border-shogun-border bg-[#080b13] px-5 py-3 shadow-shogun">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <Target className="h-5 w-5 text-shogun-gold" />
            <h1 className="truncate text-lg font-black uppercase tracking-[0.18em] text-shogun-gold">Supermode Canvas</h1>
            {mission && <StatusBadge status={mission.status} />}
          </div>
          <p className="mt-1 truncate text-xs text-shogun-subdued">{mission?.title || 'Durable autonomous missions'}</p>
        </div>
        <div className="flex items-center gap-2">
          {mission && (
            <>
              <span className="hidden rounded-lg border border-shogun-border px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-shogun-subdued xl:inline-flex">
                <Shield className="mr-1.5 h-3.5 w-3.5" /> {mission.posture_at_creation}
              </span>
              {pausableStates.has(mission.status) ? (
                <button type="button" onClick={() => void mutate('pause')} disabled={missionAction !== null} className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-2 text-amber-300 disabled:cursor-wait disabled:opacity-50" title="Pause mission" aria-label="Pause mission">{missionAction === 'pause' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Pause className="h-4 w-4" />}</button>
              ) : mission.status.startsWith('paused') ? (
                <button type="button" onClick={() => void mutate('resume')} disabled={missionAction !== null} className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-2 text-emerald-300 disabled:cursor-wait disabled:opacity-50" title="Resume mission" aria-label="Resume mission">{missionAction === 'resume' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}</button>
              ) : null}
              {!terminalStates.has(mission.status) && <button type="button" onClick={() => setConfirmingStop(true)} disabled={missionAction !== null} className="rounded-lg border border-red-500/30 bg-red-500/10 p-2 text-red-300 disabled:cursor-wait disabled:opacity-50" title="Stop mission" aria-label="Stop mission">{missionAction === 'cancel' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />}</button>}
            </>
          )}
          <button onClick={() => void refresh()} className="rounded-lg border border-shogun-border bg-shogun-card p-2 text-shogun-subdued hover:text-shogun-text" title="Refresh"><RefreshCw className="h-4 w-4" /></button>
        </div>
      </header>

      {error && <div className="flex shrink-0 items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-xs text-red-300"><AlertTriangle className="h-4 w-4" />{error}<button className="ml-auto" onClick={() => setError('')}><X className="h-4 w-4" /></button></div>}
      {notice && <div role="status" className="flex shrink-0 items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-xs text-emerald-300"><Check className="h-4 w-4" />{notice}<button type="button" className="ml-auto" onClick={() => setNotice('')} aria-label="Dismiss status"><X className="h-4 w-4" /></button></div>}

      <div className="grid min-h-0 flex-1 grid-cols-[230px_minmax(0,1fr)_300px] gap-3">
        <aside className="min-h-0 overflow-y-auto rounded-xl border border-shogun-border bg-[#070910] p-3">
          <div className="mb-3 flex items-center justify-between px-1">
            <h2 className="text-[10px] font-black uppercase tracking-[0.18em] text-shogun-subdued">Missions</h2>
            <span className="text-[9px] text-shogun-subdued">{missions.length}</span>
          </div>
          <div className="space-y-2">
            {missions.map(item => {
              const canDelete = terminalStates.has(item.status)
              return (
                <div key={item.id} className={cn('group flex items-start rounded-lg border transition-colors', item.id === selectedMissionId ? 'border-shogun-gold/50 bg-shogun-gold/5' : 'border-shogun-border bg-shogun-card/30 hover:border-shogun-blue/40')}>
                  <button type="button" onClick={() => selectMission(item.id)} className="min-w-0 flex-1 p-3 text-left">
                    <div className="flex items-start gap-2">
                      <span className={cn('mt-1 h-2 w-2 shrink-0 rounded-full', item.status === 'completed' ? 'bg-emerald-400' : activeStates.has(item.status) ? 'animate-pulse bg-cyan-400' : item.status.includes('paused') ? 'bg-amber-400' : 'bg-shogun-subdued')} />
                      <div className="min-w-0 flex-1">
                        <p className="line-clamp-2 text-xs font-bold text-shogun-text">{item.title}</p>
                        <div className="mt-2 flex items-center justify-between text-[9px] uppercase text-shogun-subdued"><span>{label(item.status)}</span><span>{Math.round(item.progress_percent || 0)}%</span></div>
                        <div className="mt-1 h-1 overflow-hidden rounded bg-black"><div className="h-full bg-shogun-gold" style={{ width: `${Math.max(2, item.progress_percent || 0)}%` }} /></div>
                      </div>
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={() => void deleteMission(item)}
                    disabled={deletingMissionId === item.id}
                    className={cn('mr-2 mt-2 rounded-md p-1.5 transition-colors disabled:cursor-wait disabled:opacity-40', canDelete ? 'text-shogun-subdued/60 hover:bg-red-500/10 hover:text-red-300' : 'text-shogun-subdued/30 hover:bg-amber-500/10 hover:text-amber-300')}
                    title={canDelete ? `Delete ${item.title}` : 'Stop this mission before deleting it'}
                    aria-label={`Delete mission ${item.title}`}
                  >
                    {deletingMissionId === item.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                  </button>
                </div>
              )
            })}
            {missions.length === 0 && <div className="rounded-lg border border-dashed border-shogun-border p-5 text-center text-xs text-shogun-subdued">Start a mission from Supermode in Chat.</div>}
          </div>
        </aside>

        <main className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-shogun-border bg-[#05070c]">
          {mission ? (
            <>
              <div className="flex shrink-0 items-center justify-between border-b border-shogun-border px-4 py-2">
                <div className="flex items-center gap-2 text-[9px] font-bold uppercase tracking-wider text-shogun-subdued">
                  <button onClick={() => setShowAgents(value => !value)} className={cn('rounded border px-2 py-1', showAgents ? 'border-cyan-500/40 text-cyan-300' : 'border-shogun-border')}>Agents</button>
                  <button onClick={() => setShowTasks(value => !value)} className={cn('rounded border px-2 py-1', showTasks ? 'border-indigo-500/40 text-indigo-300' : 'border-shogun-border')}>Tasks</button>
                  <button onClick={() => setShowDependencies(value => !value)} className={cn('rounded border px-2 py-1', showDependencies ? 'border-purple-500/40 text-purple-300' : 'border-shogun-border')}>Dependencies</button>
                </div>
                <div className="flex items-center gap-4 text-[10px] text-shogun-subdued">
                  <span><Bot className="mr-1 inline h-3.5 w-3.5" />{mission.agents.length} agents</span>
                  <span><Activity className="mr-1 inline h-3.5 w-3.5" />{mission.tasks.filter(task => task.status === 'running').length} active</span>
                  <span><CircleDollarSign className="mr-1 inline h-3.5 w-3.5" />${Number(mission.cost_used || 0).toFixed(2)}</span>
                </div>
              </div>
              <div className="min-h-[360px] flex-1">
                <ReactFlow nodes={graph.nodes} edges={graph.edges} fitView fitViewOptions={{ padding: 0.18 }} nodesDraggable={false} nodesConnectable={false} onNodeClick={(_, node) => setSelectedNode(node.data as RecordData)} onPaneClick={() => setSelectedNode(null)} colorMode="dark">
                  <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#1f2945" />
                  <Controls showInteractive={false} />
                  <MiniMap pannable zoomable nodeColor={node => node.id === 'commander' ? '#d4a017' : node.id.startsWith('agent:') ? '#22d3ee' : '#6366f1'} maskColor="rgba(2,4,8,.72)" />
                </ReactFlow>
              </div>

              <section className="h-[270px] shrink-0 border-t border-shogun-border bg-[#080b13]">
                <div className="flex h-10 items-center gap-1 border-b border-shogun-border px-3">
                  {(['timeline', 'plans', 'approvals', 'learning', 'artifacts'] as const).map(tab => (
                    <button key={tab} onClick={() => setBottomTab(tab)} className={cn('rounded px-3 py-1.5 text-[9px] font-black uppercase tracking-wider', bottomTab === tab ? 'bg-shogun-gold/10 text-shogun-gold' : 'text-shogun-subdued hover:text-shogun-text')}>{tab}{tab === 'approvals' && mission.approvals.filter(item => item.status === 'pending').length > 0 ? ` (${mission.approvals.filter(item => item.status === 'pending').length})` : ''}</button>
                  ))}
                </div>
                <div className="h-[229px] overflow-y-auto p-3">
                  {bottomTab === 'timeline' && (
                    <div className="space-y-2">
                      {mission.events.map(event => {
                        const selected = selectedKind === 'event' && selectedNode?.record?.id === event.id
                        return (
                          <button
                            key={event.id}
                            type="button"
                            onClick={() => setSelectedNode({ kind: 'event', record: event })}
                            className={cn('flex w-full gap-3 rounded-lg border p-2.5 text-left transition-colors', selected ? 'border-cyan-400/60 bg-cyan-500/10' : 'border-shogun-border/70 bg-black/20 hover:border-cyan-500/40 hover:bg-cyan-500/5')}
                            aria-label={`Inspect timeline event ${event.summary}`}
                          >
                            <Clock3 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-cyan-400" />
                            <div className="min-w-0 flex-1">
                              <p className="text-xs text-shogun-text">{event.summary}</p>
                              <p className="mt-1 text-[9px] uppercase tracking-wider text-shogun-subdued">{label(event.event_type)} · {new Date(event.created_at).toLocaleString()}</p>
                            </div>
                            <span className="self-center text-[9px] font-bold uppercase tracking-wider text-cyan-300/70">Inspect</span>
                          </button>
                        )
                      })}
                    </div>
                  )}
                  {bottomTab === 'plans' && <div className="space-y-2">{[...mission.plans].reverse().map(plan => <div key={plan.id} className="rounded-lg border border-shogun-border bg-black/20 p-3"><div className="flex items-center justify-between"><p className="text-xs font-bold text-shogun-text">Plan v{plan.version}</p><StatusBadge status={plan.status} /></div><p className="mt-2 text-xs text-shogun-subdued">{plan.reason}</p><p className="mt-2 text-[9px] uppercase text-indigo-300">{plan.plan_json?.workstreams?.length || 0} workstreams</p></div>)}</div>}
                  {bottomTab === 'approvals' && <div className="space-y-2">{mission.approvals.length === 0 ? <p className="text-xs text-shogun-subdued">No durable approvals have been requested.</p> : mission.approvals.map(approval => <div key={approval.id} className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3"><div className="flex items-center justify-between"><p className="text-xs font-bold text-amber-200">{approval.action_type}</p><StatusBadge status={approval.status} /></div><p className="mt-2 text-xs text-shogun-subdued">{approval.reason}</p>{approval.status === 'pending' && <div className="mt-3 flex gap-2"><button onClick={() => void api(`/api/v1/supermode/approvals/${approval.id}/resolve`, { method: 'POST', body: JSON.stringify({ resolution: 'approved' }) }).then(() => refresh())} className="rounded bg-emerald-600 px-3 py-1.5 text-[10px] font-bold text-white"><Check className="mr-1 inline h-3 w-3" />Approve</button><button onClick={() => void api(`/api/v1/supermode/approvals/${approval.id}/resolve`, { method: 'POST', body: JSON.stringify({ resolution: 'denied' }) }).then(() => refresh())} className="rounded bg-red-600 px-3 py-1.5 text-[10px] font-bold text-white"><X className="mr-1 inline h-3 w-3" />Deny</button></div>}</div>)}</div>}
                  {bottomTab === 'learning' && <div className="space-y-2">{mission.learning.length === 0 ? <p className="text-xs text-shogun-subdued">Learning candidates appear after meaningful workstream checkpoints.</p> : mission.learning.map(item => <div key={item.id} className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3"><div className="flex items-center justify-between"><p className="text-[9px] font-black uppercase tracking-wider text-emerald-300">{item.learning_type}</p><span className="text-[9px] text-shogun-subdued">{Math.round((item.confidence || 0) * 100)}% confidence</span></div><p className="mt-2 text-xs leading-relaxed text-shogun-text">{item.content}</p></div>)}</div>}
                  {bottomTab === 'artifacts' && <div className="space-y-2">{mission.artifacts.length === 0 ? <p className="text-xs text-shogun-subdued">Mission artifacts will appear here with their provenance.</p> : mission.artifacts.map(item => <div key={item.id} className="rounded-lg border border-shogun-border p-3"><p className="text-xs font-bold text-shogun-text">{item.filename}</p><p className="mt-1 text-[10px] text-shogun-subdued">{item.description || item.workspace_path}</p></div>)}</div>}
                </div>
              </section>
            </>
          ) : <div className="flex h-full items-center justify-center text-sm text-shogun-subdued">Select a mission.</div>}
        </main>

        <aside className="min-h-0 overflow-y-auto rounded-xl border border-shogun-border bg-[#070910] p-4">
          {mission && detailRecord ? (
            <>
              <div className="flex items-center justify-between">
                <h2 className="text-[10px] font-black uppercase tracking-[0.18em] text-shogun-subdued">Inspector</h2>
                {selectedNode && <button onClick={() => setSelectedNode(null)} className="text-shogun-subdued hover:text-shogun-text"><X className="h-4 w-4" /></button>}
              </div>
              <div className="mt-4 rounded-lg border border-shogun-border bg-shogun-card/30 p-3">
                <div className="flex items-start gap-2">
                  {selectedKind === 'agent' ? <UserRoundCog className="h-4 w-4 text-cyan-400" /> : selectedKind === 'task' ? <Route className="h-4 w-4 text-indigo-400" /> : selectedKind === 'event' ? <Clock3 className="h-4 w-4 text-cyan-400" /> : <Target className="h-4 w-4 text-shogun-gold" />}
                  <div className="min-w-0">
                    <p className="break-words text-sm font-bold text-shogun-text">{selectedKind === 'event' ? label(detailRecord.event_type) : detailRecord.role_name || detailRecord.title}</p>
                    <div className="mt-2">{selectedKind === 'event' ? <span className="inline-flex rounded border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-[9px] font-bold uppercase tracking-widest text-cyan-300">{detailRecord.severity || 'info'}</span> : <StatusBadge status={detailRecord.status} />}</div>
                  </div>
                </div>
              </div>
              <div className="mt-4 space-y-4 text-xs">
                {selectedKind === 'event' ? (
                  <>
                    <div><p className="text-[9px] font-black uppercase tracking-wider text-shogun-subdued">Summary</p><p className="mt-1 whitespace-pre-wrap leading-relaxed text-shogun-text">{detailRecord.summary}</p></div>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="rounded-lg border border-shogun-border p-2"><p className="text-[9px] text-shogun-subdued">EVENT TYPE</p><p className="mt-1 break-words font-bold uppercase text-shogun-text">{label(detailRecord.event_type)}</p></div>
                      <div className="rounded-lg border border-shogun-border p-2"><p className="text-[9px] text-shogun-subdued">TIMESTAMP</p><p className="mt-1 font-bold text-shogun-text">{new Date(detailRecord.created_at).toLocaleString()}</p></div>
                    </div>
                    {(detailRecord.task_id || detailRecord.agent_id) && <div><p className="text-[9px] font-black uppercase tracking-wider text-shogun-subdued">Related records</p>{detailRecord.task_id && <p className="mt-1 break-all text-[10px] text-indigo-300">Task: {detailRecord.task_id}</p>}{detailRecord.agent_id && <p className="mt-1 break-all text-[10px] text-cyan-300">Agent: {detailRecord.agent_id}</p>}</div>}
                    {detailRecord.event_data && Object.keys(detailRecord.event_data).length > 0 && <div><p className="text-[9px] font-black uppercase tracking-wider text-shogun-subdued">Event data</p><pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded-lg border border-shogun-border bg-black/30 p-3 text-[10px] leading-relaxed text-shogun-text">{JSON.stringify(detailRecord.event_data, null, 2)}</pre></div>}
                  </>
                ) : (
                  <>
                    <div><p className="text-[9px] font-black uppercase tracking-wider text-shogun-subdued">Objective</p><p className="mt-1 whitespace-pre-wrap leading-relaxed text-shogun-text">{detailRecord.objective || mission.objective}</p></div>
                    {selectedKind === 'agent' && <div className="grid grid-cols-2 gap-2"><div className="rounded-lg border border-shogun-border p-2"><p className="text-[9px] text-shogun-subdued">SOURCE</p><p className={cn('mt-1 font-bold uppercase', detailRecord.source_type === 'fleet' ? 'text-emerald-300' : 'text-cyan-300')}>{detailRecord.source_type === 'fleet' ? 'Fleet Samurai' : 'Spawned specialist'}</p></div><div className="rounded-lg border border-shogun-border p-2"><p className="text-[9px] text-shogun-subdued">MISSION ROLE</p><p className="mt-1 font-bold text-shogun-text">{detailRecord.routing_preferences?.mission_role || detailRecord.role_name}</p></div></div>}
                    {detailRecord.spawn_reason && <div><p className="text-[9px] font-black uppercase tracking-wider text-shogun-subdued">{detailRecord.source_type === 'fleet' ? 'Why was this Samurai routed?' : 'Why was this agent spawned?'}</p><p className="mt-1 leading-relaxed text-shogun-text">{detailRecord.spawn_reason}</p></div>}
                    {detailRecord.agent_routing_reason && <div><p className="text-[9px] font-black uppercase tracking-wider text-shogun-subdued">Agent route</p><p className="mt-1 leading-relaxed text-emerald-200">{detailRecord.agent_routing_reason}</p></div>}
                    {detailRecord.task_summary && <div><p className="text-[9px] font-black uppercase tracking-wider text-shogun-subdued">Latest handoff</p><p className="mt-1 whitespace-pre-wrap leading-relaxed text-shogun-text">{detailRecord.task_summary}</p></div>}
                    {detailRecord.model_name && <div><p className="text-[9px] font-black uppercase tracking-wider text-shogun-subdued">Katana route</p><p className="mt-1 text-shogun-text">{detailRecord.model_name} · {detailRecord.model_provider}</p><p className="mt-1 text-[10px] text-shogun-subdued">{detailRecord.routing_reason}</p></div>}
                    {detailRecord.inherited_skill_names?.length > 0 && <div><p className="text-[9px] font-black uppercase tracking-wider text-shogun-subdued">Inherited Shogun skills</p><div className="mt-2 flex flex-wrap gap-1">{detailRecord.inherited_skill_names.map((skill: string) => <span key={skill} className="rounded border border-emerald-500/20 bg-emerald-500/5 px-2 py-1 text-[9px] text-emerald-300">{skill}</span>)}</div></div>}
                    {detailRecord.tool_allowlist?.length > 0 && <div><p className="text-[9px] font-black uppercase tracking-wider text-shogun-subdued">Available tools</p><div className="mt-2 flex flex-wrap gap-1">{detailRecord.tool_allowlist.map((tool: string) => <span key={tool} className="rounded border border-cyan-500/20 bg-cyan-500/5 px-2 py-1 text-[9px] text-cyan-300">{tool}</span>)}</div></div>}
                  </>
                )}
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-lg border border-shogun-border p-2"><p className="text-[9px] text-shogun-subdued">MODEL CALLS</p><p className="mt-1 font-bold text-shogun-text">{mission.model_calls_used} / {mission.max_model_calls}</p></div>
                  <div className="rounded-lg border border-shogun-border p-2"><p className="text-[9px] text-shogun-subdued">TOKENS</p><p className="mt-1 font-bold text-shogun-text">{Number(mission.tokens_used || 0).toLocaleString()}</p></div>
                </div>
              </div>

              {!terminalStates.has(mission.status) && (
                <div className="mt-5 border-t border-shogun-border pt-4">
                  <p className="text-[9px] font-black uppercase tracking-wider text-shogun-subdued">Message Commander</p>
                  <textarea value={steering} onChange={event => setSteering(event.target.value)} rows={3} placeholder="Add a constraint, redirect priorities, or request emphasis…" className="mt-2 w-full rounded-lg border border-shogun-border bg-black/30 p-2 text-xs text-shogun-text outline-none focus:border-shogun-blue" />
                  <button disabled={!steering.trim()} onClick={() => { void mutate('steer', { instruction: steering }); setSteering('') }} className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg bg-shogun-blue px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-white disabled:opacity-40"><Send className="h-3.5 w-3.5" />Steer mission</button>
                  <div className="mt-2 grid grid-cols-2 gap-2"><button onClick={() => void mutate('replan', { reason: 'Operator requested a fresh plan from Supermode Canvas' })} className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-2 py-2 text-[9px] font-bold uppercase text-indigo-300"><GitBranch className="mr-1 inline h-3.5 w-3.5" />Re-plan</button><button onClick={() => setShowSpecialist(value => !value)} className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-2 py-2 text-[9px] font-bold uppercase text-cyan-300"><Plus className="mr-1 inline h-3.5 w-3.5" />Specialist</button></div>
                  {showSpecialist && <div className="mt-3 space-y-2 rounded-lg border border-cyan-500/20 bg-cyan-500/5 p-3"><input value={specialist.role_name} onChange={event => setSpecialist({ ...specialist, role_name: event.target.value })} placeholder="Role name" className="w-full rounded border border-shogun-border bg-black/30 p-2 text-xs outline-none" /><input value={specialist.objective} onChange={event => setSpecialist({ ...specialist, objective: event.target.value })} placeholder="Specialist objective" className="w-full rounded border border-shogun-border bg-black/30 p-2 text-xs outline-none" /><input value={specialist.spawn_reason} onChange={event => setSpecialist({ ...specialist, spawn_reason: event.target.value })} placeholder="Why this expertise is needed" className="w-full rounded border border-shogun-border bg-black/30 p-2 text-xs outline-none" /><button disabled={!specialist.role_name || !specialist.objective || !specialist.spawn_reason} onClick={() => void api(`/api/v1/supermode/missions/${mission.id}/agents`, { method: 'POST', body: JSON.stringify({ ...specialist, role_description: 'Operator-requested mission specialist' }) }).then(() => { setShowSpecialist(false); setSpecialist({ role_name: '', objective: '', spawn_reason: '' }); return refresh() }).catch(err => setError(err.message))} className="w-full rounded bg-cyan-700 py-2 text-[9px] font-bold uppercase text-white disabled:opacity-40">Create specialist</button></div>}
                </div>
              )}

              {mission.status === 'completed' && mission.agentflow_candidate?.ready && (
                <div className="mt-5 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4">
                  <div className="flex items-center gap-2 text-emerald-300"><Sparkles className="h-4 w-4" /><p className="text-xs font-bold">Reusable process detected</p></div>
                  <p className="mt-2 text-[10px] leading-relaxed text-shogun-subdued">{mission.agentflow_candidate.description}</p>
                  <button onClick={() => void api(`/api/v1/supermode/missions/${mission.id}/agentflow-candidate`, { method: 'POST', body: '{}' }).then(data => { window.location.href = data.editor_url }).catch(err => setError(err.message))} className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-[10px] font-bold uppercase text-white"><Layers3 className="h-3.5 w-3.5" />Create draft AgentFlow</button>
                </div>
              )}
            </>
          ) : <p className="text-xs text-shogun-subdued">Select a mission to inspect it.</p>}
        </aside>
      </div>

      {confirmingStop && mission && !terminalStates.has(mission.status) && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="stop-mission-title">
          <div className="w-full max-w-md rounded-xl border border-red-500/30 bg-[#0b0d14] p-5 shadow-2xl">
            <div className="flex items-start gap-3">
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-2 text-red-300"><Square className="h-4 w-4" /></div>
              <div className="min-w-0"><h2 id="stop-mission-title" className="font-bold text-shogun-text">Stop this mission?</h2><p className="mt-2 text-xs leading-relaxed text-shogun-subdued">No new work will start. The durable run history and generated workspace files will be retained.</p><p className="mt-2 line-clamp-2 text-xs font-semibold text-shogun-text">{mission.title}</p></div>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" onClick={() => setConfirmingStop(false)} disabled={missionAction !== null} className="rounded-lg border border-shogun-border px-4 py-2 text-xs font-bold text-shogun-subdued hover:text-shogun-text disabled:opacity-50">Keep running</button>
              <button type="button" onClick={async () => { if (await mutate('cancel')) setConfirmingStop(false) }} disabled={missionAction !== null} className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-xs font-bold text-white hover:bg-red-500 disabled:cursor-wait disabled:opacity-50">{missionAction === 'cancel' && <Loader2 className="h-3.5 w-3.5 animate-spin" />}Stop mission</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export const MissionControl = ({ embedded = false }: MissionControlProps) => <ReactFlowProvider><MissionControlContent embedded={embedded} /></ReactFlowProvider>
