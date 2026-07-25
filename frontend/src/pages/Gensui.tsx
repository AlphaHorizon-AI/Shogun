import { useState, useEffect, useCallback } from 'react';
import {
  Shield,
  Wifi,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Link2,
  Unlink,
  RefreshCw,
  Server,
  Globe,
  Key,
  Tag,
  Clock,
  ShieldCheck,
  ShieldAlert,
  Zap,
  Eye,
  PenTool,
  Network,
  Bot,
  FileCode2,
  Compass,
  MousePointerClick,
} from 'lucide-react';
import axios from 'axios';
import { cn } from '../lib/utils';
import {
  getInfrastructureAdminToken,
  infrastructureRequestConfig,
  setInfrastructureAdminToken,
} from '../lib/infrastructureAuth';
import { useTranslation } from '../i18n';

// ── Types ──────────────────────────────────────────────────────

interface GensuiStatus {
  enabled: boolean;
  server_url: string;
  instance_name: string;
  environment: string;
  enrolled: boolean;
  connected: boolean;
  shogun_id: string | null;
  effective_posture: {
    posture_name?: string;
    rules?: Record<string, boolean>;
  } | null;
  last_sync_at: string | null;
}

interface TestResult {
  reachable: boolean;
  service?: string;
  version?: string;
  error?: string;
}

// ── Permission map ─────────────────────────────────────────────

const PERMISSION_CONFIG: { key: string; label: string; icon: any }[] = [
  { key: 'allow_external_models', label: 'External Models', icon: Globe },
  { key: 'allow_local_models', label: 'Local Models', icon: Server },
  { key: 'allow_tool_execution', label: 'Tool Execution', icon: Zap },
  { key: 'allow_mado', label: 'Mado Browser', icon: Eye },
  { key: 'allow_memory_write', label: 'Memory Write', icon: PenTool },
  { key: 'allow_memory_read', label: 'Memory Read', icon: Eye },
  { key: 'allow_agent_flow', label: 'Agent Flow', icon: Network },
  { key: 'allow_nexus', label: 'Nexus Comms', icon: Network },
  { key: 'allow_samurai_delegation', label: 'Samurai Delegation', icon: Bot },
  { key: 'allow_scheduled_triggers', label: 'Scheduled Triggers', icon: Clock },
  { key: 'allow_autonomous_loops', label: 'Autonomous Loops', icon: RefreshCw },
  { key: 'allow_external_web', label: 'External Web', icon: Globe },
  { key: 'allow_file_write', label: 'File Write', icon: FileCode2 },
  { key: 'allow_external_api', label: 'External APIs', icon: Compass },
];

// ── Helpers ────────────────────────────────────────────────────

function formatTime(iso: string | null) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString([], {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch { return iso; }
}

// ── Main Component ─────────────────────────────────────────────

export function Gensui() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<GensuiStatus | null>(null);
  const [loading, setLoading] = useState(true);

  // Connection form
  const [serverUrl, setServerUrl] = useState('http://localhost:8787');
  const [enrollmentToken, setEnrollmentToken] = useState('');
  const [instanceName, setInstanceName] = useState('');
  const [environment, setEnvironment] = useState('development');
  const [infrastructureToken, setInfrastructureTokenState] = useState(
    getInfrastructureAdminToken,
  );

  // Actions
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [connectMsg, setConnectMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [disconnecting, setDisconnecting] = useState(false);
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);

  // ── Fetch status ──────────────────────────────────────────

  const fetchStatus = useCallback(async () => {
    try {
      const res = await axios.get('/api/v1/gensui/status');
      setStatus(res.data);
    } catch (err) {
      console.error('Gensui status error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const poll = setInterval(fetchStatus, 15000);
    return () => clearInterval(poll);
  }, [fetchStatus]);

  // ── Test connectivity ─────────────────────────────────────

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await axios.post(
        '/api/v1/gensui/test',
        { server_url: serverUrl },
        infrastructureRequestConfig(infrastructureToken),
      );
      setTestResult(res.data);
    } catch (err: any) {
      setTestResult({ reachable: false, error: err.response?.data?.detail || 'Test failed' });
    } finally {
      setTesting(false);
    }
  };

  // ── Connect ───────────────────────────────────────────────

  const handleConnect = async () => {
    setConnecting(true);
    setConnectMsg(null);
    try {
      const res = await axios.post(
        '/api/v1/gensui/connect',
        {
          server_url: serverUrl,
          enrollment_token: enrollmentToken || null,
          instance_name: instanceName || null,
          environment,
        },
        infrastructureRequestConfig(infrastructureToken),
      );
      setConnectMsg({ type: 'success', text: res.data.message || 'Connected' });
      await fetchStatus();
    } catch (err: any) {
      setConnectMsg({ type: 'error', text: err.response?.data?.detail || 'Connection failed' });
    } finally {
      setConnecting(false);
    }
  };

  // ── Disconnect ────────────────────────────────────────────

  const handleDisconnect = async () => {
    setDisconnecting(true);
    try {
      await axios.post(
        '/api/v1/gensui/disconnect',
        {},
        infrastructureRequestConfig(infrastructureToken),
      );
      setConfirmDisconnect(false);
      await fetchStatus();
    } catch (err) {
      console.error('Disconnect error:', err);
    } finally {
      setDisconnecting(false);
    }
  };

  // ── Loading state ─────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
      </div>
    );
  }

  const isConnected = status?.enabled && status?.enrolled;

  // ── Render ────────────────────────────────────────────────

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-5xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            {t('gensui.title', 'Gensui')}
            <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">
              Fleet Command
            </span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">
            {t('gensui.subtitle', 'Connect this Shogun instance to a Gensui server for centralized fleet management, posture enforcement, and security coordination.')}
          </p>
        </div>
        <button
          onClick={fetchStatus}
          className="p-2.5 bg-shogun-card border border-shogun-border rounded-lg text-shogun-subdued hover:text-shogun-gold transition-colors self-start"
        >
          <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
        </button>
      </div>

      <div className="shogun-card">
        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-1.5">
          <Key className="w-3 h-3" /> Infrastructure Admin Token
        </label>
        <input
          type="password"
          autoComplete="off"
          value={infrastructureToken}
          onChange={event => {
            const value = event.target.value;
            setInfrastructureTokenState(value);
            setInfrastructureAdminToken(value);
          }}
          placeholder="Required by Shogun Server mode"
          className="mt-2 w-full bg-[#050508] border border-shogun-border rounded-xl px-4 py-3 text-sm font-mono focus:border-indigo-500 outline-none transition-all"
        />
        <p className="mt-2 text-[10px] text-shogun-subdued">
          Kept only in this browser tab session. Desktop requests from localhost do not require it.
        </p>
      </div>

      {/* ── Connected State ─────────────────────────────────── */}
      {isConnected ? (
        <div className="space-y-6">
          {/* Connection Status Card */}
          <div className="shogun-card bg-emerald-500/5 border-emerald-500/20">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                  <Wifi className="w-7 h-7 text-emerald-400" />
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-lg font-bold text-shogun-text">
                      {status?.connected ? t('gensui.connected', 'Connected to Gensui') : t('gensui.enrolled_offline', 'Enrolled — Connection Lost')}
                    </p>
                    <span className={cn(
                      'w-2.5 h-2.5 rounded-full animate-pulse',
                      status?.connected ? 'bg-emerald-500' : 'bg-amber-500'
                    )} />
                  </div>
                  <div className="flex items-center gap-4 text-xs text-shogun-subdued">
                    <span className="flex items-center gap-1.5">
                      <Server className="w-3 h-3" />
                      {status?.server_url}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Tag className="w-3 h-3" />
                      {status?.environment}
                    </span>
                  </div>
                </div>
              </div>
              <button
                onClick={() => setConfirmDisconnect(true)}
                className="px-4 py-2.5 bg-red-500/10 border border-red-500/20 text-red-400 font-bold text-xs uppercase tracking-widest rounded-xl hover:bg-red-500/20 transition-all flex items-center gap-2"
              >
                <Unlink className="w-3.5 h-3.5" /> Disconnect
              </button>
            </div>
          </div>

          {/* Enrollment Info */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="shogun-card">
              <p className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest mb-2">Shogun ID</p>
              <code className="text-xs font-mono text-shogun-text break-all">{status?.shogun_id || '—'}</code>
            </div>
            <div className="shogun-card">
              <p className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest mb-2">Instance Name</p>
              <p className="text-sm font-bold text-shogun-text">{status?.instance_name || '—'}</p>
            </div>
            <div className="shogun-card">
              <p className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest mb-2">Last Sync</p>
              <p className="text-sm text-shogun-text flex items-center gap-1.5">
                <Clock className="w-3 h-3 text-shogun-subdued" />
                {formatTime(status?.last_sync_at || null)}
              </p>
            </div>
          </div>

          {/* Active Posture */}
          {status?.effective_posture && (
            <div className="shogun-card">
              <div className="flex items-center gap-3 mb-5">
                <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                  <ShieldCheck className="w-5 h-5 text-indigo-400" />
                </div>
                <div>
                  <p className="text-[10px] font-bold text-indigo-400 uppercase tracking-widest">Active Posture</p>
                  <p className="text-lg font-bold text-shogun-text">
                    {status.effective_posture.posture_name || 'Default'}
                  </p>
                </div>
              </div>

              {status.effective_posture.rules && (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                  {PERMISSION_CONFIG.map(({ key, label, icon: Icon }) => {
                    const allowed = status.effective_posture?.rules?.[key] ?? true;
                    return (
                      <div
                        key={key}
                        className={cn(
                          'flex items-center gap-2 px-3 py-2 rounded-xl border text-xs font-semibold transition-all',
                          allowed
                            ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-400'
                            : 'bg-red-500/5 border-red-500/20 text-red-400'
                        )}
                      >
                        <Icon className="w-3.5 h-3.5 flex-shrink-0" />
                        <span className="truncate">{label}</span>
                        {allowed
                          ? <CheckCircle2 className="w-3 h-3 ml-auto flex-shrink-0" />
                          : <XCircle className="w-3 h-3 ml-auto flex-shrink-0" />}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* No posture info */}
          {!status?.effective_posture && (
            <div className="shogun-card border-dashed flex items-center gap-4 p-6">
              <ShieldAlert className="w-8 h-8 text-amber-400" />
              <div>
                <p className="text-sm font-bold text-shogun-text">Awaiting Posture Sync</p>
                <p className="text-xs text-shogun-subdued mt-1">
                  No posture received from Gensui yet. This may mean enrollment is pending approval, or the server hasn't assigned a policy.
                </p>
              </div>
            </div>
          )}
        </div>
      ) : (
        /* ── Not Connected — Setup Form ───────────────────────── */
        <div className="space-y-6">
          {/* Hero Card */}
          <div className="shogun-card border-dashed border-2 border-indigo-500/20 p-8 flex flex-col md:flex-row items-center gap-8">
            <div className="w-24 h-24 rounded-3xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center flex-shrink-0">
              <Shield className="w-12 h-12 text-indigo-400" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-shogun-text mb-2">{t('gensui.not_connected', 'Not Connected to Gensui')}</h3>
              <p className="text-sm text-shogun-subdued leading-relaxed max-w-xl">
                {t('gensui.connect_desc', 'Connect this Shogun instance to a Gensui Central Command server for fleet-wide security posture management, remote policy enforcement, telemetry monitoring, and emergency Harakiri capabilities.')}
              </p>
            </div>
          </div>

          {/* Connection Form */}
          <div className="shogun-card">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                <Link2 className="w-5 h-5 text-indigo-400" />
              </div>
              <div>
                <h3 className="text-base font-bold text-shogun-text">{t('gensui.connect_title', 'Connect to Gensui Server')}</h3>
                <p className="text-[10px] text-shogun-subdued uppercase tracking-widest font-bold">Fleet Enrollment</p>
              </div>
            </div>

            <div className="space-y-5">
              {/* Server URL */}
              <div className="space-y-2">
                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-1.5">
                  <Server className="w-3 h-3" /> Server URL *
                </label>
                <div className="flex gap-2">
                  <input
                    value={serverUrl}
                    onChange={e => setServerUrl(e.target.value)}
                    placeholder="http://localhost:8787"
                    className="flex-1 bg-[#050508] border border-shogun-border rounded-xl px-4 py-3 text-sm focus:border-indigo-500 outline-none transition-all"
                  />
                  <button
                    onClick={handleTest}
                    disabled={testing || !serverUrl.trim()}
                    className="px-5 py-3 bg-shogun-card border border-shogun-border text-shogun-text font-bold text-xs uppercase tracking-widest rounded-xl hover:border-indigo-500 transition-all disabled:opacity-40 flex items-center gap-2"
                  >
                    {testing
                      ? <Loader2 className="w-4 h-4 animate-spin" />
                      : <MousePointerClick className="w-4 h-4" />}
                    {t('gensui.test', 'Test Connection')}
                  </button>
                </div>
                {testResult && (
                  <div className={cn(
                    'flex items-center gap-2 text-xs px-3 py-2 rounded-lg',
                    testResult.reachable
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-red-500/10 text-red-400 border border-red-500/20'
                  )}>
                    {testResult.reachable ? (
                      <>
                        <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                        <span>Gensui {testResult.version} reachable — ready to connect</span>
                      </>
                    ) : (
                      <>
                        <XCircle className="w-4 h-4 flex-shrink-0" />
                        <span>{testResult.error}</span>
                      </>
                    )}
                  </div>
                )}
              </div>

              {/* Enrollment Token */}
              <div className="space-y-2">
                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-1.5">
                  <Key className="w-3 h-3" /> Enrollment Token
                </label>
                <input
                  value={enrollmentToken}
                  onChange={e => setEnrollmentToken(e.target.value)}
                  placeholder="Paste the enrollment token from Gensui admin panel..."
                  className="w-full bg-[#050508] border border-shogun-border rounded-xl px-4 py-3 text-sm font-mono focus:border-indigo-500 outline-none transition-all"
                />
                <p className="text-[10px] text-shogun-subdued">
                  Generate this token in the Gensui Admin UI → Enrollment page. Leave empty to connect without auto-enrollment.
                </p>
              </div>

              {/* Instance Name + Environment */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-1.5">
                    <Tag className="w-3 h-3" /> Instance Name
                  </label>
                  <input
                    value={instanceName}
                    onChange={e => setInstanceName(e.target.value)}
                    placeholder="My Shogun (auto-detected)"
                    className="w-full bg-[#050508] border border-shogun-border rounded-xl px-4 py-3 text-sm focus:border-indigo-500 outline-none transition-all"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-1.5">
                    <Globe className="w-3 h-3" /> Environment
                  </label>
                  <select
                    value={environment}
                    onChange={e => setEnvironment(e.target.value)}
                    className="w-full bg-[#050508] border border-shogun-border rounded-xl px-4 py-3 text-sm focus:border-indigo-500 outline-none transition-all appearance-none"
                  >
                    <option value="development">Development</option>
                    <option value="staging">Staging</option>
                    <option value="production">Production</option>
                  </select>
                </div>
              </div>

              {/* Connect message */}
              {connectMsg && (
                <div className={cn(
                  'flex items-center gap-2 text-xs px-3 py-2 rounded-lg',
                  connectMsg.type === 'success'
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'bg-red-500/10 text-red-400 border border-red-500/20'
                )}>
                  {connectMsg.type === 'success'
                    ? <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                    : <XCircle className="w-4 h-4 flex-shrink-0" />}
                  <span>{connectMsg.text}</span>
                </div>
              )}

              {/* Connect button */}
              <button
                onClick={handleConnect}
                disabled={connecting || !serverUrl.trim()}
                className="w-full py-3.5 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs uppercase tracking-[0.15em] rounded-xl shadow-lg transition-all disabled:opacity-40 flex items-center justify-center gap-2"
              >
                {connecting
                  ? <Loader2 className="w-4 h-4 animate-spin" />
                  : <Link2 className="w-4 h-4" />}
                {connecting
                  ? t('gensui.connecting', 'Connecting...')
                  : t('gensui.connect_btn', 'Connect to Gensui')}
              </button>
            </div>
          </div>

          {/* How it works */}
          <div className="shogun-card">
            <p className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest mb-4">How It Works</p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                { icon: Link2, title: 'Enroll', desc: 'Submit your enrollment token to register this Shogun instance with the Gensui server.' },
                { icon: ShieldCheck, title: 'Receive Policy', desc: 'Gensui pushes security posture and permission rules that are enforced locally by the Torii.' },
                { icon: Wifi, title: 'Stay Connected', desc: 'Heartbeats, telemetry, and command polling run in the background to maintain the fleet link.' },
              ].map(({ icon: Icon, title, desc }) => (
                <div key={title} className="flex items-start gap-3 p-4 rounded-xl border border-shogun-border bg-shogun-card/50">
                  <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center flex-shrink-0">
                    <Icon className="w-4 h-4 text-indigo-400" />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-shogun-text">{title}</p>
                    <p className="text-[11px] text-shogun-subdued mt-0.5 leading-relaxed">{desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Disconnect Confirmation Modal ─────────────────────── */}
      {confirmDisconnect && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-shogun-bg border border-red-500/30 w-full max-w-sm rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-6 border-b border-red-500/20 bg-red-500/5 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
                <Unlink className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <h3 className="text-base font-bold text-shogun-text">Disconnect from Gensui</h3>
                <p className="text-[10px] text-red-400 uppercase tracking-widest font-bold">Fleet link will be severed</p>
              </div>
            </div>
            <div className="p-6 space-y-4">
              <p className="text-sm text-shogun-subdued">
                This will stop all heartbeats, policy sync, and command polling. Your Shogun will operate independently without fleet oversight.
              </p>
              <div className="flex items-center gap-2 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 px-3 py-2 rounded-lg">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>Any cached posture will be cleared. The Torii will revert to local-only policies.</span>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => setConfirmDisconnect(false)}
                  className="flex-1 py-3 bg-shogun-card border border-shogun-border text-shogun-subdued font-bold text-xs uppercase tracking-widest rounded-xl hover:border-shogun-text transition-colors"
                >Cancel</button>
                <button
                  onClick={handleDisconnect}
                  disabled={disconnecting}
                  className="flex-1 py-3 bg-red-600 hover:bg-red-500 text-white font-bold text-xs uppercase tracking-widest rounded-xl transition-all disabled:opacity-40 flex items-center justify-center gap-2"
                >
                  {disconnecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Unlink className="w-4 h-4" />}
                  Disconnect
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
