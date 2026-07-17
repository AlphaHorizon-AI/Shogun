import { useState, useEffect, useCallback } from 'react';
import {
  Monitor,
  MousePointer2,
  Eye,
  ShieldAlert,
  ShieldCheck,
  ShieldOff,
  Loader2,
  CheckCircle2,
  XCircle,
  Plus,
  Trash2,
  Play,
  Zap,
  RefreshCw,
  Lock,
  Server,
  Laptop,
  Cloud,
  Activity,
  ChevronRight,
  Target,
  Skull,
  Dog,
} from 'lucide-react';
import axios from 'axios';
import { cn } from '../lib/utils';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

interface RoninStatus {
  ronin_enabled: boolean;
  ronin_posture: string;
  active_sessions: number;
  environment: any;
  komainu: any;
  pending_approvals: number;
  capabilities_count: number;
  active_tier: string;
  desktop_available: boolean;
  desktop_active: boolean;
  visible_indicator: boolean;
  runtime: any;
}

interface RoninSession {
  id: string;
  name: string;
  agent_id: string | null;
  posture: string;
  status: string;
  environment_type: string;
  os_type: string;
  os_version: string | null;
  hostname: string | null;
  machine_id: string | null;
  is_disposable: boolean;
  last_screenshot_path: string | null;
  last_action: string | null;
  last_action_at: string | null;
  current_app: string | null;
  current_app_trust: string | null;
  action_count: number;
  komainu_level: number;
  created_at: string;
  updated_at: string;
}

interface AppTrustEntry {
  process: string | null;
  process_pattern: string | null;
  name: string;
  trust_level: string;
  platform: string;
}

interface RoninCapability {
  name: string;
  category: string;
  risk_level: string;
  requires_approval: boolean;
  description: string;
  posture_minimum: string;
  app_trust_minimum: string;
  enabled: boolean;
}

interface ApprovalRequest {
  id: string;
  agent_id: string | null;
  session_id: string | null;
  action_type: string;
  target: string | null;
  reason: string;
  risk_level: string;
  app_name: string | null;
  app_trust: string | null;
  screenshot_path: string | null;
  created_at: string;
  status: string;
}

interface AuditEntry {
  id: string;
  event_type: string;
  action: string;
  result: string;
  severity: string;
  risk_score: string;
  agent_id: string | null;
  created_at: string | null;
}

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

const ACCENT = '#f97316'; // Ronin orange
const ACCENT_DIM = '#f9731620';
const ACCENT_BORDER = '#f9731640';
const TABS = ['Control', 'Sessions', 'App Trust', 'Capabilities', 'Audit Trail'] as const;
type Tab = typeof TABS[number];

const statusColors: Record<string, { bg: string; text: string; dot: string }> = {
  idle:     { bg: 'rgba(249,115,22,0.08)', text: '#f97316', dot: '#f97316' },
  active:   { bg: 'rgba(34,197,94,0.08)',  text: '#22c55e', dot: '#22c55e' },
  paused:   { bg: 'rgba(234,179,8,0.08)',  text: '#eab308', dot: '#eab308' },
  error:    { bg: 'rgba(239,68,68,0.08)',  text: '#ef4444', dot: '#ef4444' },
  closed:   { bg: 'rgba(122,136,153,0.08)',text: '#7a8899', dot: '#7a8899' },
};

const trustColors: Record<string, { bg: string; text: string; label: string }> = {
  trusted:    { bg: 'rgba(34,197,94,0.10)',  text: '#22c55e', label: 'TRUSTED' },
  restricted: { bg: 'rgba(234,179,8,0.10)',  text: '#eab308', label: 'RESTRICTED' },
  sensitive:  { bg: 'rgba(249,115,22,0.10)', text: '#f97316', label: 'SENSITIVE' },
  forbidden:  { bg: 'rgba(239,68,68,0.10)',  text: '#ef4444', label: 'FORBIDDEN' },
};

const riskColors: Record<string, { bg: string; text: string }> = {
  low:      { bg: 'rgba(34,197,94,0.10)',  text: '#22c55e' },
  medium:   { bg: 'rgba(234,179,8,0.10)',  text: '#eab308' },
  high:     { bg: 'rgba(249,115,22,0.10)', text: '#f97316' },
  critical: { bg: 'rgba(239,68,68,0.10)',  text: '#ef4444' },
};

const envIcons: Record<string, React.ElementType> = {
  physical:       Laptop,
  vm:             Server,
  sandbox:        Lock,
  remote_desktop: Monitor,
  citrix:         Monitor,
  cloud_workspace: Cloud,
};

const komainuLevelLabels: Record<number, { label: string; color: string; desc: string }> = {
  1: { label: 'PAUSE',     color: '#eab308', desc: 'Pause session on human input' },
  2: { label: 'TERMINATE', color: '#f97316', desc: 'Kill active session on input' },
  3: { label: 'HARAKIRI',  color: '#ef4444', desc: 'Full emergency stop on input' },
};

// ═══════════════════════════════════════════════════════════════
// RONIN PAGE
// ═══════════════════════════════════════════════════════════════

export function Ronin() {
  const [tab, setTab] = useState<Tab>('Control');
  const [status, setStatus] = useState<RoninStatus | null>(null);
  const [sessions, setSessions] = useState<RoninSession[]>([]);
  const [trustEntries, setTrustEntries] = useState<AppTrustEntry[]>([]);
  const [capabilities, setCapabilities] = useState<RoninCapability[]>([]);
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [controlBusy, setControlBusy] = useState(false);

  // Create session modal
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newPosture, setNewPosture] = useState('observe_only');
  const [newKomainuLevel, setNewKomainuLevel] = useState(1);
  const [creating, setCreating] = useState(false);

  // Approval modal
  const [activeApproval, setActiveApproval] = useState<ApprovalRequest | null>(null);

  // Quick action
  const [quickAction, setQuickAction] = useState('desktop.screenshot');
  const [quickTarget, setQuickTarget] = useState('');
  const [quickValue, setQuickValue] = useState('');
  const [quickSessionId, _setQuickSessionId] = useState('');
  const [quickLoading, setQuickLoading] = useState(false);
  const [quickResult, setQuickResult] = useState<string | null>(null);

  // Capability filter
  const [capFilter, setCapFilter] = useState<string>('all');

  // Trust filter
  const [trustFilter, setTrustFilter] = useState<string>('all');

  // ── Data loading ──────────────────────────────────────────

  const loadStatus = useCallback(async () => {
    try {
      const r = await axios.get('/api/v1/ronin/status');
      setStatus(r.data?.data);
    } catch { /* ignore */ }
  }, []);

  const loadSessions = useCallback(async () => {
    try {
      const r = await axios.get('/api/v1/ronin/sessions');
      setSessions(r.data?.data || []);
    } catch { /* ignore */ }
  }, []);

  const loadTrust = useCallback(async () => {
    try {
      const r = await axios.get('/api/v1/ronin/trust');
      setTrustEntries(r.data?.data || []);
    } catch { /* ignore */ }
  }, []);

  const loadCapabilities = useCallback(async () => {
    try {
      const r = await axios.get('/api/v1/ronin/capabilities');
      setCapabilities(r.data?.data || []);
    } catch { /* ignore */ }
  }, []);

  const loadApprovals = useCallback(async () => {
    try {
      const r = await axios.get('/api/v1/ronin/approvals');
      setApprovals(r.data?.data || []);
    } catch { /* ignore */ }
  }, []);

  const loadAudit = useCallback(async () => {
    try {
      const r = await axios.get('/api/v1/ronin/audit?limit=100');
      setAudit(r.data?.data || []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    Promise.all([loadStatus(), loadSessions(), loadTrust(), loadCapabilities(), loadApprovals(), loadAudit()])
      .finally(() => setLoading(false));
  }, [loadStatus, loadSessions, loadTrust, loadCapabilities, loadApprovals, loadAudit]);

  // Poll approvals every 5 seconds
  useEffect(() => {
    const interval = setInterval(() => { loadApprovals(); loadStatus(); }, 5000);
    return () => clearInterval(interval);
  }, [loadApprovals, loadStatus]);

  // ── Actions ───────────────────────────────────────────────

  const createSession = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await axios.post('/api/v1/ronin/sessions', {
        name: newName,
        posture: newPosture,
        komainu_level: newKomainuLevel,
      });
      await loadSessions();
      await loadStatus();
      setShowCreate(false);
      setNewName('');
    } catch { /* ignore */ }
    setCreating(false);
  };

  const deleteSession = async (id: string) => {
    try {
      await axios.delete(`/api/v1/ronin/sessions/${id}`);
      await Promise.all([loadSessions(), loadStatus()]);
    } catch { /* ignore */ }
  };

  const respondApproval = async (id: string, decision: 'approved' | 'denied') => {
    try {
      await axios.post(`/api/v1/ronin/approvals/${id}`, { decision, decided_by: 'operator' });
      setActiveApproval(null);
      await Promise.all([loadApprovals(), loadStatus()]);
    } catch { /* ignore */ }
  };

  const executeQuickAction = async () => {
    if (!quickAction) return;
    setQuickLoading(true);
    setQuickResult(null);
    try {
      const r = await axios.post('/api/v1/ronin/execute', {
        action_type: quickAction,
        target: quickTarget || undefined,
        value: quickValue || undefined,
        session_id: quickSessionId || undefined,
      });
      const data = r.data?.data;
      if (data?.status === 'success') {
        setQuickResult(`✅ ${quickAction} — ${JSON.stringify(data.result_data || {}).slice(0, 300)}`);
      } else {
        setQuickResult(`❌ ${data?.status}: ${data?.error || 'Unknown error'}`);
      }
      await loadStatus();
    } catch (err: any) {
      setQuickResult(`❌ ${err.response?.data?.detail || err.message || 'Request failed'}`);
    }
    setQuickLoading(false);
  };

  const triggerHarakiri = async () => {
    if (!confirm('⚠️ HARAKIRI: This will stop ALL Ronin activity and close all sessions. Continue?')) return;
    try {
      await axios.post('/api/v1/ronin/harakiri');
      await Promise.all([loadStatus(), loadSessions(), loadApprovals()]);
    } catch { /* ignore */ }
  };

  const enableDesktopControl = async () => {
    if (!confirm('Ronin Desktop Control can operate your real mouse, keyboard, windows, and applications. Every action remains visible, verified, and audited. Enable it now?')) return;
    setControlBusy(true);
    try {
      await axios.post('/api/v1/ronin/desktop/enable', {
        confirmation: 'ENABLE RONIN DESKTOP CONTROL',
        ronin_screenshots_enabled: true,
        ronin_mouse_enabled: true,
        ronin_keyboard_enabled: true,
        ronin_window_management_enabled: true,
        ronin_native_apps_enabled: true,
        ronin_require_verification: true,
        ronin_require_high_risk_approval: true,
        ronin_block_critical_actions: true,
        ronin_visible_indicator: true,
      });
      await loadStatus();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Could not enable Ronin Desktop Control.');
    } finally {
      setControlBusy(false);
    }
  };

  const disableDesktopControl = async () => {
    setControlBusy(true);
    try {
      await axios.post('/api/v1/ronin/desktop/disable');
      await loadStatus();
    } finally {
      setControlBusy(false);
    }
  };

  const desktopKillSwitch = async () => {
    if (!confirm('Stop all Ronin Desktop Control immediately?')) return;
    await axios.post('/api/v1/ronin/desktop/kill-switch');
    await loadStatus();
  };

  // ── Render ────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#0a0e1a]">
        <Loader2 className="w-8 h-8 animate-spin" style={{ color: ACCENT }} />
      </div>
    );
  }

  const env = status?.environment || {};
  const komainu = status?.komainu || {};
  const EnvIcon = envIcons[env.environment_type] || Laptop;
  const komainuInfo = komainuLevelLabels[komainu.level] || komainuLevelLabels[1];

  return (
    <div className="flex-1 flex flex-col bg-[#0a0e1a] overflow-hidden">
      {/* ── Header ──────────────────────────────────────────── */}
      <div className="px-6 py-5 border-b border-[#1a2040] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{ background: ACCENT_DIM, border: `1px solid ${ACCENT_BORDER}` }}
          >
            <Monitor className="w-5 h-5" style={{ color: ACCENT }} />
          </div>
          <div>
            <h1 className="text-lg font-bold text-[#c8d0d8] tracking-tight">Ronin</h1>
            <p className="text-[10px] text-[#7a8899] uppercase tracking-widest font-bold">浪人 — Desktop Control Layer</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Komainu status */}
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg border cursor-default"
            style={{
              background: komainu.active ? `${komainuInfo.color}08` : '#0e1225',
              borderColor: komainu.active ? `${komainuInfo.color}30` : '#1a2040',
            }}
            title={`Komainu Guardian: ${komainu.active ? komainuInfo.desc : 'Inactive'}`}
          >
            <Dog className="w-3.5 h-3.5" style={{ color: komainu.active ? komainuInfo.color : '#7a8899' }} />
            <span
              className="text-[9px] font-bold uppercase tracking-wider"
              style={{ color: komainu.active ? komainuInfo.color : '#7a8899' }}
            >
              {komainu.active ? (komainu.paused ? 'PAUSED' : komainuInfo.label) : 'GUARDIAN OFF'}
            </span>
          </div>

          {/* Environment badge */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#0e1225] border border-[#1a2040]">
            <EnvIcon className="w-3.5 h-3.5 text-[#7a8899]" />
            <span className="text-[9px] font-bold text-[#7a8899] uppercase tracking-wider">
              {(env.environment_type || 'unknown').replace('_', ' ')}
            </span>
          </div>

          {/* Posture badge */}
          {status?.ronin_enabled ? (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#22c55e]/8 border border-[#22c55e]/20">
              <ShieldCheck className="w-3.5 h-3.5 text-[#22c55e]" />
              <span className="text-[9px] font-bold text-[#22c55e] uppercase tracking-wider">
                {status.ronin_posture.replace('_', ' ')}
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#ef4444]/8 border border-[#ef4444]/20">
              <ShieldOff className="w-3.5 h-3.5 text-[#ef4444]" />
              <span className="text-[9px] font-bold text-[#ef4444] uppercase tracking-wider">DISABLED</span>
            </div>
          )}

          {/* Harakiri button */}
          <button
            onClick={triggerHarakiri}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#ef4444]/8 border border-[#ef4444]/20 text-[#ef4444] hover:bg-[#ef4444]/20 transition-all cursor-pointer"
            title="Emergency Stop — Harakiri"
          >
            <Skull className="w-3.5 h-3.5" />
            <span className="text-[9px] font-bold uppercase tracking-wider">STOP</span>
          </button>
        </div>
      </div>

      {/* ── Pending Approvals Banner ─────────────────────────── */}
      {approvals.length > 0 && (
        <div className="px-6 py-3 bg-[#f97316]/8 border-b border-[#f97316]/20 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-[#f97316] animate-pulse" />
            <span className="text-xs font-bold text-[#f97316]">
              {approvals.length} Pending Approval{approvals.length > 1 ? 's' : ''}
            </span>
            <span className="text-[10px] text-[#f97316]/60">
              — {approvals[0].action_type} requires operator decision
            </span>
          </div>
          <button
            onClick={() => setActiveApproval(approvals[0])}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider cursor-pointer transition-all"
            style={{ background: ACCENT, color: '#0a0e1a' }}
          >
            Review
            <ChevronRight className="w-3 h-3" />
          </button>
        </div>
      )}

      {status?.desktop_active && status.visible_indicator && (
        <div className="px-6 py-2.5 bg-orange-500/10 border-b border-orange-500/30 flex items-center justify-between">
          <div className="flex items-center gap-2 text-orange-400">
            <div className="w-2 h-2 rounded-full bg-orange-400 animate-pulse" />
            <span className="text-[10px] font-black tracking-[0.2em]">RONIN DESKTOP CONTROL ACTIVE</span>
            <span className="text-[9px] text-orange-300/60">Visible, verified, and audited</span>
          </div>
          <button onClick={desktopKillSwitch} className="px-3 py-1 rounded border border-red-500/40 bg-red-500/10 text-[9px] font-bold text-red-400 hover:bg-red-500/20">KILL SWITCH</button>
        </div>
      )}

      {/* ── Tabs ────────────────────────────────────────────── */}
      <div className="px-6 pt-3 flex items-center gap-1 border-b border-[#1a2040]">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "px-4 py-2.5 text-[11px] font-bold uppercase tracking-wider transition-all duration-200 border-b-2 -mb-px cursor-pointer",
              tab === t
                ? `border-[${ACCENT}] text-[${ACCENT}]`
                : "border-transparent text-[#7a8899] hover:text-[#c8d0d8]"
            )}
            style={tab === t ? { borderColor: ACCENT, color: ACCENT } : {}}
          >
            {t}
          </button>
        ))}
      </div>

      {/* ── Content ─────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-6">

        {/* ═══ CONTROL TAB ═══ */}
        {tab === 'Control' && (
          <div className="space-y-6">
            <div className="bg-[#0e1225] border border-[#1a2040] rounded-xl p-5 flex items-center justify-between gap-6">
              <div>
                <h3 className="text-sm font-bold text-[#c8d0d8]">Full Desktop Control</h3>
                <p className="text-[10px] text-[#7a8899] mt-1 max-w-2xl">Available only in Ronin posture. Enabling grants governed mouse, keyboard, window, and application control with mandatory observation, verification, audit, protected-context blocking, and a kill switch.</p>
              </div>
              {status?.desktop_active ? (
                <button disabled={controlBusy} onClick={disableDesktopControl} className="px-4 py-2 rounded-lg border border-orange-500/40 bg-orange-500/10 text-xs font-bold text-orange-400 whitespace-nowrap">DISABLE DESKTOP CONTROL</button>
              ) : (
                <button disabled={controlBusy || !status?.desktop_available} onClick={enableDesktopControl} className="px-4 py-2 rounded-lg bg-orange-500 text-[#0a0e1a] text-xs font-black disabled:opacity-30 whitespace-nowrap">{status?.desktop_available ? 'ENABLE DESKTOP CONTROL' : 'RONIN POSTURE REQUIRED'}</button>
              )}
            </div>

            {status?.desktop_active && (
              <div className="grid grid-cols-[1.5fr_1fr] gap-4">
                <div className="bg-[#0e1225] border border-[#1a2040] rounded-xl overflow-hidden">
                  <div className="px-4 py-3 border-b border-[#1a2040] flex justify-between"><span className="text-[10px] font-bold uppercase tracking-widest text-[#7a8899]">Current Desktop</span><span className="text-[9px] text-orange-400">{status.runtime?.active_window?.title || 'No active window detected'}</span></div>
                  <div className="aspect-video bg-[#080b14] flex items-center justify-center">
                    {status.runtime?.screenshot_url ? <img src={status.runtime.screenshot_url} className="w-full h-full object-contain" alt="Current Ronin desktop" /> : <Monitor className="w-12 h-12 text-[#1a2040]" />}
                  </div>
                  <div className="grid grid-cols-3 gap-px bg-[#1a2040]">
                    <RuntimeField label="Next action" value={status.runtime?.next_action?.action_type || 'Idle'} />
                    <RuntimeField label="Verification" value={status.runtime?.verification?.passed === true ? 'Passed' : status.runtime?.verification?.passed === false ? 'Failed' : 'Pending'} />
                    <RuntimeField label="Retries" value={String(status.runtime?.retry_count || 0)} />
                  </div>
                </div>
                <div className="bg-[#0e1225] border border-[#1a2040] rounded-xl overflow-hidden">
                  <div className="px-4 py-3 border-b border-[#1a2040] text-[10px] font-bold uppercase tracking-widest text-[#7a8899]">Action Timeline</div>
                  <div className="max-h-[360px] overflow-y-auto divide-y divide-[#1a2040]">
                    {(status.runtime?.timeline || []).slice(0, 50).map((item: any, index: number) => <div key={`${item.timestamp}-${index}`} className="px-4 py-3"><div className="text-[9px] font-mono text-orange-400">{new Date(item.timestamp).toLocaleTimeString()}</div><div className="text-[10px] text-[#c8d0d8] mt-0.5">{item.message}</div></div>)}
                    {!status.runtime?.timeline?.length && <div className="p-6 text-center text-[10px] text-[#555]">No desktop actions yet.</div>}
                  </div>
                </div>
              </div>
            )}
            {/* Status Overview Cards */}
            <div className="grid grid-cols-4 gap-4">
              <StatusCard
                icon={Monitor}
                label="Sessions"
                value={String(status?.active_sessions || 0)}
                sub="Active desktop sessions"
                accent={ACCENT}
              />
              <StatusCard
                icon={Dog}
                label="Komainu"
                value={komainu.active ? (komainu.paused ? 'Paused' : 'Active') : 'Off'}
                sub={komainu.active ? komainuInfo.desc : 'Guardian not running'}
                accent={komainu.active ? komainuInfo.color : '#7a8899'}
              />
              <StatusCard
                icon={ShieldAlert}
                label="Approvals"
                value={String(status?.pending_approvals || 0)}
                sub="Waiting for operator"
                accent={status?.pending_approvals ? '#f97316' : '#22c55e'}
              />
              <StatusCard
                icon={Zap}
                label="Capabilities"
                value={String(status?.capabilities_count || 0)}
                sub="Registered actions"
                accent="#4a8cc7"
              />
            </div>

            {/* Environment Info */}
            <div className="bg-[#0e1225] border border-[#1a2040] rounded-xl p-5">
              <h3 className="text-xs font-bold text-[#7a8899] uppercase tracking-widest mb-4">
                Environment Detection
              </h3>
              <div className="grid grid-cols-3 gap-4">
                <EnvField label="Type" value={(env.environment_type || 'unknown').replace('_', ' ')} />
                <EnvField label="OS" value={`${env.os_type || 'unknown'} ${env.os_version || ''}`.trim()} />
                <EnvField label="Hostname" value={env.hostname || 'N/A'} />
                <EnvField label="Machine ID" value={env.machine_id ? env.machine_id.slice(0, 16) + '…' : 'N/A'} />
                <EnvField label="Disposable" value={env.is_disposable ? 'Yes' : 'No'} />
                <EnvField label="Hypervisor" value={env.hypervisor || 'None'} />
              </div>
            </div>

            {/* Quick Action */}
            <div className="bg-[#0e1225] border border-[#1a2040] rounded-xl p-5">
              <h3 className="text-xs font-bold text-[#7a8899] uppercase tracking-widest mb-4">
                Quick Action
              </h3>
              <div className="grid grid-cols-4 gap-3">
                <div className="space-y-1.5">
                  <label className="text-[8px] font-bold text-[#7a8899] uppercase tracking-widest">Action</label>
                  <select
                    value={quickAction}
                    onChange={(e) => setQuickAction(e.target.value)}
                    className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2.5 text-xs text-[#c8d0d8] focus:border-[#f97316] transition-colors outline-none cursor-pointer"
                  >
                    <optgroup label="Desktop">
                      <option value="desktop.screenshot">📸 Screenshot</option>
                      <option value="desktop.click">🖱️ Click</option>
                      <option value="desktop.move_mouse">↗️ Move Mouse</option>
                      <option value="desktop.type">⌨️ Type Text</option>
                      <option value="desktop.hotkey">⚡ Hotkey</option>
                      <option value="desktop.locate_image">🔍 Locate Image</option>
                      <option value="desktop.read_screen">👁️ Read Screen</option>
                    </optgroup>
                    <optgroup label="Browser">
                      <option value="browser.open">🌐 Open URL</option>
                      <option value="browser.click">🖱️ Browser Click</option>
                      <option value="browser.type">⌨️ Browser Type</option>
                      <option value="browser.extract">📄 Extract Text</option>
                      <option value="browser.screenshot">📸 Browser Screenshot</option>
                    </optgroup>
                    <optgroup label="OS">
                      <option value="os.list_windows">📋 List Windows</option>
                      <option value="os.focus_window">🔲 Focus Window</option>
                    </optgroup>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-[8px] font-bold text-[#7a8899] uppercase tracking-widest">Target</label>
                  <input
                    value={quickTarget}
                    onChange={(e) => setQuickTarget(e.target.value)}
                    className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2.5 text-xs text-[#c8d0d8] focus:border-[#f97316] transition-colors outline-none"
                    placeholder="x,y or selector"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[8px] font-bold text-[#7a8899] uppercase tracking-widest">Value</label>
                  <input
                    value={quickValue}
                    onChange={(e) => setQuickValue(e.target.value)}
                    className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2.5 text-xs text-[#c8d0d8] focus:border-[#f97316] transition-colors outline-none"
                    placeholder="text or URL"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[8px] font-bold text-[#7a8899] uppercase tracking-widest">&nbsp;</label>
                  <button
                    onClick={executeQuickAction}
                    disabled={quickLoading}
                    className="w-full flex items-center justify-center gap-2 p-2.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all cursor-pointer disabled:opacity-40"
                    style={{ background: ACCENT, color: '#0a0e1a' }}
                  >
                    {quickLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                    Execute
                  </button>
                </div>
              </div>
              {quickResult && (
                <div className={cn(
                  "mt-3 p-3 rounded-lg text-xs font-mono whitespace-pre-wrap border",
                  quickResult.startsWith('✅')
                    ? "bg-[#22c55e]/5 text-[#22c55e]/90 border-[#22c55e]/20"
                    : "bg-[#ef4444]/5 text-[#ef4444]/90 border-[#ef4444]/20"
                )}>
                  {quickResult}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ═══ SESSIONS TAB ═══ */}
        {tab === 'Sessions' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold text-[#7a8899] uppercase tracking-widest">Desktop Sessions</h2>
              <button
                onClick={() => setShowCreate(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all duration-200 cursor-pointer"
                style={{ background: ACCENT_DIM, border: `1px solid ${ACCENT_BORDER}`, color: ACCENT }}
              >
                <Plus className="w-3 h-3" />
                New Session
              </button>
            </div>

            {sessions.length === 0 ? (
              <div className="text-center py-16 space-y-3">
                <Monitor className="w-12 h-12 mx-auto" style={{ color: `${ACCENT}40` }} />
                <p className="text-sm text-[#7a8899]">No desktop sessions yet</p>
                <p className="text-xs text-[#555]">Create a session to start governing desktop control</p>
              </div>
            ) : (
              <div className="grid gap-3">
                {sessions.map((s) => {
                  const sc = statusColors[s.status] || statusColors.idle;
                  const trustInfo = trustColors[s.current_app_trust || 'restricted'] || trustColors.restricted;
                  return (
                    <div
                      key={s.id}
                      className="group bg-[#0e1225] border border-[#1a2040] rounded-xl p-4 flex items-center gap-4 hover:border-[#2a3060] transition-all duration-200"
                    >
                      {/* Status icon */}
                      <div
                        className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                        style={{ background: sc.bg }}
                      >
                        <Monitor className="w-4.5 h-4.5" style={{ color: sc.text }} />
                      </div>

                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-bold text-[#c8d0d8] truncate">{s.name}</h3>
                          <span
                            className="text-[8px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded"
                            style={{ background: sc.bg, color: sc.text }}
                          >
                            {s.status}
                          </span>
                          <span className="text-[8px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded bg-[#4a8cc7]/10 text-[#4a8cc7]">
                            {s.posture.replace('_', ' ')}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 mt-1">
                          <span className="text-[9px] text-[#555]">{s.environment_type.replace('_', ' ')}</span>
                          <span className="text-[9px] text-[#555]">•</span>
                          <span className="text-[9px] text-[#555]">{s.os_type}</span>
                          <span className="text-[9px] text-[#555]">•</span>
                          <span className="text-[9px] text-[#555]">{s.action_count} actions</span>
                          {s.hostname && (
                            <>
                              <span className="text-[9px] text-[#555]">•</span>
                              <span className="text-[9px] text-[#555] font-mono">{s.hostname}</span>
                            </>
                          )}
                        </div>
                        {s.current_app && (
                          <div className="flex items-center gap-2 mt-1">
                            <Target className="w-2.5 h-2.5 text-[#555]" />
                            <span className="text-[9px] text-[#c8d0d8]/70">{s.current_app}</span>
                            <span
                              className="text-[7px] font-bold uppercase px-1 py-0.5 rounded"
                              style={{ background: trustInfo.bg, color: trustInfo.text }}
                            >
                              {trustInfo.label}
                            </span>
                          </div>
                        )}
                        {s.last_action && (
                          <div className="flex items-center gap-1 mt-1">
                            <Activity className="w-2.5 h-2.5 text-[#555]" />
                            <span className="text-[9px] text-[#f97316]/60 font-mono">{s.last_action}</span>
                          </div>
                        )}
                      </div>

                      {/* Komainu level */}
                      <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-[#0a0e1a] border border-[#1a2040]">
                        <Dog className="w-3 h-3" style={{ color: komainuLevelLabels[s.komainu_level]?.color || '#7a8899' }} />
                        <span className="text-[8px] font-bold uppercase" style={{ color: komainuLevelLabels[s.komainu_level]?.color || '#7a8899' }}>
                          L{s.komainu_level}
                        </span>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => deleteSession(s.id)}
                          className="p-1.5 hover:bg-[#ef4444]/10 text-[#7a8899] hover:text-[#ef4444] rounded-lg transition-colors cursor-pointer"
                          title="Close session"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ═══ APP TRUST TAB ═══ */}
        {tab === 'App Trust' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold text-[#7a8899] uppercase tracking-widest">Application Trust Registry</h2>
              <div className="flex items-center gap-2">
                {['all', 'trusted', 'restricted', 'sensitive', 'forbidden'].map((f) => (
                  <button
                    key={f}
                    onClick={() => setTrustFilter(f)}
                    className={cn(
                      "px-3 py-1 rounded-lg text-[9px] font-bold uppercase tracking-wider transition-all cursor-pointer",
                      trustFilter === f
                        ? "text-[#0a0e1a]"
                        : "text-[#7a8899] bg-[#0e1225] border border-[#1a2040] hover:border-[#2a3060]"
                    )}
                    style={trustFilter === f ? {
                      background: f === 'all' ? ACCENT : (trustColors[f]?.text || ACCENT),
                    } : {}}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid gap-2">
              {trustEntries
                .filter(e => trustFilter === 'all' || e.trust_level === trustFilter)
                .map((e, i) => {
                  const tc = trustColors[e.trust_level] || trustColors.restricted;
                  return (
                    <div
                      key={i}
                      className="bg-[#0e1225] border border-[#1a2040] rounded-lg px-4 py-3 flex items-center gap-3 hover:border-[#2a3060] transition-all"
                    >
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: tc.bg }}>
                        {e.trust_level === 'forbidden'
                          ? <Lock className="w-3.5 h-3.5" style={{ color: tc.text }} />
                          : e.trust_level === 'sensitive'
                            ? <ShieldAlert className="w-3.5 h-3.5" style={{ color: tc.text }} />
                            : e.trust_level === 'trusted'
                              ? <ShieldCheck className="w-3.5 h-3.5" style={{ color: tc.text }} />
                              : <Eye className="w-3.5 h-3.5" style={{ color: tc.text }} />
                        }
                      </div>
                      <div className="flex-1 min-w-0">
                        <span className="text-xs font-bold text-[#c8d0d8]">{e.name}</span>
                        <div className="text-[9px] text-[#555] font-mono">{e.process || e.process_pattern || '—'}</div>
                      </div>
                      <span
                        className="text-[8px] font-bold uppercase tracking-widest px-2 py-0.5 rounded"
                        style={{ background: tc.bg, color: tc.text }}
                      >
                        {tc.label}
                      </span>
                      <span className="text-[8px] text-[#555] uppercase">{e.platform}</span>
                    </div>
                  );
                })}
            </div>
          </div>
        )}

        {/* ═══ CAPABILITIES TAB ═══ */}
        {tab === 'Capabilities' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold text-[#7a8899] uppercase tracking-widest">Registered Capabilities</h2>
              <div className="flex items-center gap-2">
                {['all', 'desktop', 'browser', 'os', 'app', 'ronin'].map((f) => (
                  <button
                    key={f}
                    onClick={() => setCapFilter(f)}
                    className={cn(
                      "px-3 py-1 rounded-lg text-[9px] font-bold uppercase tracking-wider transition-all cursor-pointer",
                      capFilter === f
                        ? "text-[#0a0e1a]"
                        : "text-[#7a8899] bg-[#0e1225] border border-[#1a2040] hover:border-[#2a3060]"
                    )}
                    style={capFilter === f ? { background: ACCENT } : {}}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid gap-2">
              {capabilities
                .filter(c => capFilter === 'all' || c.category === capFilter)
                .map((c, i) => {
                  const rc = riskColors[c.risk_level] || riskColors.low;
                  return (
                    <div
                      key={i}
                      className="bg-[#0e1225] border border-[#1a2040] rounded-lg px-4 py-3 flex items-center gap-3 hover:border-[#2a3060] transition-all"
                    >
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-[#0a0e1a]">
                        {c.category === 'desktop' ? <MousePointer2 className="w-3.5 h-3.5 text-[#f97316]" />
                          : c.category === 'browser' ? <Eye className="w-3.5 h-3.5 text-[#06b6d4]" />
                            : c.category === 'os' ? <Server className="w-3.5 h-3.5 text-[#a78bfa]" />
                              : c.category === 'ronin' ? <Skull className="w-3.5 h-3.5 text-[#ef4444]" />
                                : <Zap className="w-3.5 h-3.5 text-[#eab308]" />
                        }
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-[#c8d0d8] font-mono">{c.name}</span>
                          {c.requires_approval && (
                            <span className="text-[7px] font-bold uppercase px-1 py-0.5 rounded bg-[#f97316]/10 text-[#f97316]">
                              APPROVAL
                            </span>
                          )}
                        </div>
                        <div className="text-[9px] text-[#555]">{c.description}</div>
                      </div>
                      <span
                        className="text-[8px] font-bold uppercase tracking-widest px-2 py-0.5 rounded"
                        style={{ background: rc.bg, color: rc.text }}
                      >
                        {c.risk_level}
                      </span>
                      <span className="text-[8px] text-[#555] uppercase font-mono w-24 text-right">
                        ≥ {c.posture_minimum.replace('_', ' ')}
                      </span>
                    </div>
                  );
                })}
            </div>
          </div>
        )}

        {/* ═══ AUDIT TRAIL TAB ═══ */}
        {tab === 'Audit Trail' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold text-[#7a8899] uppercase tracking-widest">Ronin Audit Trail</h2>
              <button
                onClick={loadAudit}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all cursor-pointer text-[#7a8899] hover:text-[#c8d0d8] bg-[#0e1225] border border-[#1a2040]"
              >
                <RefreshCw className="w-3 h-3" />
                Refresh
              </button>
            </div>

            {audit.length === 0 ? (
              <div className="text-center py-16 space-y-3">
                <Activity className="w-12 h-12 mx-auto text-[#1a2040]" />
                <p className="text-sm text-[#7a8899]">No audit events yet</p>
                <p className="text-xs text-[#555]">Ronin actions will appear here once executed</p>
              </div>
            ) : (
              <div className="space-y-1">
                {audit.map((e, i) => {
                  const sevColor = e.severity === 'critical' ? '#ef4444'
                    : e.severity === 'warn' ? '#eab308'
                      : e.severity === 'error' ? '#ef4444'
                        : '#22c55e';
                  return (
                    <div
                      key={i}
                      className="bg-[#0e1225] border border-[#1a2040] rounded-lg px-4 py-2.5 flex items-center gap-3 hover:border-[#2a3060] transition-all"
                    >
                      <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: sevColor }} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-bold text-[#c8d0d8] font-mono">{e.event_type}</span>
                          <span
                            className="text-[7px] font-bold uppercase px-1 py-0.5 rounded"
                            style={{ background: `${sevColor}15`, color: sevColor }}
                          >
                            {e.severity}
                          </span>
                        </div>
                        <div className="text-[9px] text-[#555] truncate">{e.action}</div>
                      </div>
                      <span className="text-[8px] text-[#555] font-mono whitespace-nowrap">
                        {e.created_at ? new Date(e.created_at).toLocaleTimeString() : '—'}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ═══ CREATE SESSION MODAL ═══ */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#0e1225] border border-[#1a2040] rounded-2xl w-[440px] shadow-2xl overflow-hidden">
            <div className="p-5 border-b border-[#1a2040] flex items-center gap-3">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center"
                style={{ background: ACCENT_DIM, border: `1px solid ${ACCENT_BORDER}` }}
              >
                <Plus className="w-4 h-4" style={{ color: ACCENT }} />
              </div>
              <h3 className="text-sm font-bold text-[#c8d0d8]">New Ronin Session</h3>
            </div>
            <div className="p-5 space-y-4">
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Session Name</label>
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2.5 text-xs text-[#c8d0d8] focus:border-[#f97316] transition-colors outline-none"
                  placeholder="e.g., SAP Data Entry, Browser Research"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Posture Level</label>
                <select
                  value={newPosture}
                  onChange={(e) => setNewPosture(e.target.value)}
                  className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2.5 text-xs text-[#c8d0d8] focus:border-[#f97316] transition-colors outline-none cursor-pointer"
                >
                  <option value="observe_only">👁️ Observe Only — Screenshots & window listing</option>
                  <option value="browser_only">🌐 Browser Only — Playwright/Mado control</option>
                  <option value="desktop_limited">🖱️ Desktop Limited — Mouse, keyboard, screenshots</option>
                  <option value="desktop_full">⚡ Desktop Full — Native apps, shell, admin</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest flex items-center gap-1.5">
                  <Dog className="w-3 h-3" />
                  Komainu Guardian Level
                </label>
                <div className="flex gap-2">
                  {[1, 2, 3].map((level) => {
                    const info = komainuLevelLabels[level];
                    return (
                      <button
                        key={level}
                        onClick={() => setNewKomainuLevel(level)}
                        className={cn(
                          "flex-1 flex flex-col items-center gap-1 px-3 py-2.5 rounded-lg border text-[10px] font-bold uppercase tracking-wider transition-all cursor-pointer",
                          newKomainuLevel === level
                            ? `border-[${info.color}]`
                            : "border-[#1a2040] hover:border-[#2a3060]"
                        )}
                        style={newKomainuLevel === level ? {
                          borderColor: info.color,
                          background: `${info.color}10`,
                          color: info.color,
                        } : { color: '#7a8899' }}
                      >
                        <span>{info.label}</span>
                        <span className="text-[7px] normal-case tracking-normal font-normal opacity-60">{info.desc}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
            <div className="px-5 py-3 border-t border-[#1a2040] flex items-center justify-end gap-2">
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[#7a8899] hover:text-[#c8d0d8] transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={createSession}
                disabled={creating || !newName.trim()}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all cursor-pointer disabled:opacity-40"
                style={{ background: ACCENT, color: '#0a0e1a' }}
              >
                {creating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═══ APPROVAL MODAL ═══ */}
      {activeApproval && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#0e1225] border border-[#f97316]/30 rounded-2xl w-[480px] shadow-2xl overflow-hidden">
            <div className="p-5 border-b border-[#f97316]/20 bg-[#f97316]/5 flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-[#f97316]/15 border border-[#f97316]/30">
                <ShieldAlert className="w-4 h-4 text-[#f97316]" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-[#f97316]">Approval Required</h3>
                <p className="text-[9px] text-[#f97316]/60">Ronin is requesting permission for a high-risk action</p>
              </div>
            </div>
            <div className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <ApprovalField label="Action" value={activeApproval.action_type} />
                <ApprovalField label="Risk Level" value={activeApproval.risk_level} highlight />
                <ApprovalField label="Target" value={activeApproval.target || '—'} />
                <ApprovalField label="Application" value={activeApproval.app_name || '—'} />
                {activeApproval.app_trust && (
                  <ApprovalField label="App Trust" value={activeApproval.app_trust} />
                )}
              </div>
              <div className="p-3 bg-[#0a0e1a] rounded-lg border border-[#1a2040]">
                <p className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest mb-1">Reason</p>
                <p className="text-xs text-[#c8d0d8]">{activeApproval.reason}</p>
              </div>
            </div>
            <div className="px-5 py-4 border-t border-[#1a2040] flex items-center justify-between">
              <button
                onClick={() => setActiveApproval(null)}
                className="px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[#7a8899] hover:text-[#c8d0d8] transition-colors cursor-pointer"
              >
                Later
              </button>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => respondApproval(activeApproval.id, 'denied')}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[10px] font-bold uppercase tracking-wider bg-[#ef4444]/10 text-[#ef4444] border border-[#ef4444]/20 hover:bg-[#ef4444]/20 transition-all cursor-pointer"
                >
                  <XCircle className="w-3 h-3" />
                  Deny
                </button>
                <button
                  onClick={() => respondApproval(activeApproval.id, 'approved')}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all cursor-pointer"
                  style={{ background: '#22c55e', color: '#0a0e1a' }}
                >
                  <CheckCircle2 className="w-3 h-3" />
                  Approve
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════
// SUB-COMPONENTS
// ═══════════════════════════════════════════════════════════════

function StatusCard({ icon: Icon, label, value, sub, accent }: {
  icon: React.ElementType;
  label: string;
  value: string;
  sub: string;
  accent: string;
}) {
  return (
    <div className="bg-[#0e1225] border border-[#1a2040] rounded-xl p-4 hover:border-[#2a3060] transition-all">
      <div className="flex items-center gap-3 mb-3">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center"
          style={{ background: `${accent}12`, border: `1px solid ${accent}30` }}
        >
          <Icon className="w-4 h-4" style={{ color: accent }} />
        </div>
        <span className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">{label}</span>
      </div>
      <p className="text-2xl font-bold tracking-tight" style={{ color: accent }}>{value}</p>
      <p className="text-[9px] text-[#555] mt-1">{sub}</p>
    </div>
  );
}

function EnvField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[8px] font-bold text-[#7a8899] uppercase tracking-widest mb-0.5">{label}</p>
      <p className="text-xs text-[#c8d0d8] font-mono">{value}</p>
    </div>
  );
}

function RuntimeField({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[#0e1225] px-4 py-3">
      <div className="text-[8px] uppercase tracking-widest text-[#555]">{label}</div>
      <div className="text-[10px] font-bold text-[#c8d0d8] mt-1 truncate">{value}</div>
    </div>
  );
}

function ApprovalField({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  const rc = highlight ? (riskColors[value] || riskColors.high) : null;
  return (
    <div>
      <p className="text-[8px] font-bold text-[#7a8899] uppercase tracking-widest mb-0.5">{label}</p>
      {highlight && rc ? (
        <span
          className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded"
          style={{ background: rc.bg, color: rc.text }}
        >
          {value}
        </span>
      ) : (
        <p className="text-xs text-[#c8d0d8] font-mono truncate">{value}</p>
      )}
    </div>
  );
}
