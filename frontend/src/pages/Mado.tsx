import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AppWindow,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Download,
  ExternalLink,
  Image,
  Loader2,
  Maximize2,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  ShieldAlert,
  Trash2,
  X,
  XCircle,
} from 'lucide-react';
import axios from 'axios';
import { cn } from '../lib/utils';

interface MadoStatus {
  installed: boolean;
  version: string | null;
  active_sessions: number;
  mado_path: string;
  profiles_path: string;
  screenshots_path: string;
  downloads_path: string;
}

interface MadoSession {
  id: string;
  name: string;
  profile_name: string;
  status: string;
  browser_mode: string;
  last_url: string | null;
  last_active_at: string | null;
  session_data?: Record<string, any>;
}

interface MadoRuntimeSession {
  session_id: string;
  status: string;
  profile_id?: string;
  posture?: string;
  mode: string;
  stack_run_id?: string;
  current_url?: string;
  title?: string;
  last_action?: string;
  last_screenshot?: string;
  last_verification?: { status?: string; passed?: boolean };
  last_error?: string;
  retry_count: number;
  timeline: Array<{ timestamp: string; event_type: string; message: string }>;
}

interface Screenshot {
  filename: string;
  size_bytes: number;
  created_at: string;
}

type Tab = 'Overview' | 'Sessions' | 'Screenshots' | 'Permissions' | 'Advanced';

const ACCENT = '#06b6d4';
const TABS: Tab[] = ['Overview', 'Sessions', 'Screenshots', 'Permissions', 'Advanced'];

export function Mado() {
  const [tab, setTab] = useState<Tab>('Overview');
  const [status, setStatus] = useState<MadoStatus | null>(null);
  const [sessions, setSessions] = useState<MadoSession[]>([]);
  const [screenshots, setScreenshots] = useState<Screenshot[]>([]);
  const [runtimeSessions, setRuntimeSessions] = useState<MadoRuntimeSession[]>([]);
  const [madoConfig, setMadoConfig] = useState<Record<string, any>>({});
  const [savingConfig, setSavingConfig] = useState(false);
  const [loading, setLoading] = useState(true);
  const [installing, setInstalling] = useState(false);
  const [workingSession, setWorkingSession] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  const agentSession = useMemo(
    () => sessions.find((session) => session.profile_name === 'native_skill') || null,
    [sessions],
  );

  const refresh = useCallback(async () => {
    try {
      const [statusResponse, sessionsResponse, screenshotsResponse] = await Promise.all([
        axios.get('/api/v1/mado/status'),
        axios.get('/api/v1/mado/sessions'),
        axios.get('/api/v1/mado/screenshots'),
      ]);
      setStatus(statusResponse.data?.data || null);
      setRuntimeSessions(statusResponse.data?.meta?.runtime_sessions || []);
      setMadoConfig(statusResponse.data?.meta?.config || {});
      setSessions(sessionsResponse.data?.data || []);
      setScreenshots(screenshotsResponse.data?.data || []);
    } catch (error) {
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : '';
      setMessage({ type: 'error', text: detail || 'Mado status could not be loaded.' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const installChromium = async () => {
    setInstalling(true);
    setMessage(null);
    try {
      const response = await axios.post('/api/v1/mado/install');
      const result = response.data?.data;
      if (!result?.success) {
        throw new Error(result?.error || 'Chromium installation failed.');
      }
      setMessage({ type: 'success', text: 'Chromium installed. Mado is ready.' });
      await refresh();
    } catch (error) {
      const detail = axios.isAxiosError(error)
        ? error.response?.data?.detail
        : error instanceof Error
          ? error.message
          : '';
      setMessage({ type: 'error', text: detail || 'Chromium installation failed.' });
    } finally {
      setInstalling(false);
    }
  };

  const resetSession = async (session: MadoSession) => {
    setWorkingSession(session.id);
    setMessage(null);
    try {
      await axios.delete(`/api/v1/mado/sessions/${session.id}`);
      setMessage({
        type: 'success',
        text: session.profile_name === 'native_skill'
          ? 'Agent browser reset. Shogun will create a clean session when it browses again.'
          : `Browser session “${session.name}” removed.`,
      });
      await refresh();
    } catch (error) {
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : '';
      setMessage({ type: 'error', text: detail || 'The browser session could not be reset.' });
    } finally {
      setWorkingSession(null);
    }
  };

  const controlSession = async (session: MadoSession, action: 'pause' | 'resume' | 'close') => {
    setWorkingSession(session.id);
    setMessage(null);
    try {
      await axios.post(`/api/v1/mado/sessions/${session.id}/${action}`);
      setMessage({ type: 'success', text: `Mado session ${action}d.` });
      await refresh();
    } catch (error) {
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : '';
      setMessage({ type: 'error', text: detail || `Could not ${action} the Mado session.` });
    } finally {
      setWorkingSession(null);
    }
  };

  const triggerKillSwitch = async () => {
    if (!confirm('Stop every active Mado browser session now? Logs and artifacts will be preserved.')) return;
    await axios.post('/api/v1/mado/kill-switch');
    setMessage({ type: 'success', text: 'Mado kill switch stopped all active browser sessions.' });
    await refresh();
  };

  const saveMadoConfig = async () => {
    setSavingConfig(true);
    try {
      const editableKeys = [
        'enabled', 'default_mode', 'headless_allowed', 'visible_allowed', 'allowed_domains',
        'blocked_domains', 'allow_external_urls', 'allow_persistent_profiles',
        'allow_authenticated_sessions', 'allow_file_downloads', 'allow_file_uploads',
        'allow_form_submit', 'require_verification', 'max_pages_per_run', 'max_runtime_seconds',
        'default_navigation_timeout_ms', 'default_action_timeout_ms', 'retry', 'page_readiness', 'audit',
      ];
      const payload = Object.fromEntries(editableKeys.filter((key) => key in madoConfig).map((key) => [key, madoConfig[key]]));
      const response = await axios.patch('/api/v1/mado/config', payload);
      setMadoConfig(response.data?.data || madoConfig);
      setMessage({ type: 'success', text: 'Mado permissions and reliability settings saved.' });
    } catch (error) {
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : '';
      setMessage({ type: 'error', text: detail || 'Mado settings could not be saved.' });
    } finally {
      setSavingConfig(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[420px] items-center justify-center bg-[#0a0e1a]">
        <Loader2 className="h-8 w-8 animate-spin" style={{ color: ACCENT }} />
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-[#0a0e1a]">
      <div className="flex items-center justify-between border-b border-[#1a2040] px-6 py-5">
        <div className="flex items-center gap-3">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-xl"
            style={{ background: `${ACCENT}12`, border: `1px solid ${ACCENT}30` }}
          >
            <AppWindow className="h-5 w-5" style={{ color: ACCENT }} />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-[#c8d0d8]">Mado</h1>
            <p className="text-[10px] font-bold uppercase tracking-widest text-[#7a8899]">
              Managed browser runtime
            </p>
          </div>
        </div>

        <button
          onClick={refresh}
          className="rounded-lg border border-[#1a2040] p-2 text-[#7a8899] transition-colors hover:text-[#c8d0d8]"
          title="Refresh Mado status"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {message && (
        <div
          className={cn(
            'flex items-center gap-2 border-b px-6 py-3 text-xs font-semibold',
            message.type === 'success'
              ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300'
              : 'border-red-500/20 bg-red-500/10 text-red-300',
          )}
        >
          {message.type === 'success'
            ? <CheckCircle2 className="h-4 w-4 shrink-0" />
            : <XCircle className="h-4 w-4 shrink-0" />}
          {message.text}
        </div>
      )}

      <div className="flex items-center gap-1 border-b border-[#1a2040] px-6 pt-3">
        {TABS.map((item) => (
          <button
            key={item}
            onClick={() => setTab(item)}
            className={cn(
              '-mb-px border-b-2 px-4 py-2.5 text-[11px] font-bold uppercase tracking-wider transition-colors',
              tab === item
                ? 'border-cyan-500 text-cyan-400'
                : 'border-transparent text-[#7a8899] hover:text-[#c8d0d8]',
            )}
          >
            {item}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {runtimeSessions.some((session) => session.status === 'active') && (
          <div className="mx-auto mb-5 flex max-w-4xl items-center justify-between rounded-xl border border-cyan-400/40 bg-cyan-500/10 px-4 py-3">
            <div className="flex items-center gap-3">
              <span className="relative flex h-3 w-3"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-60" /><span className="relative inline-flex h-3 w-3 rounded-full bg-cyan-400" /></span>
              <div><p className="text-xs font-bold text-cyan-200">MADO BROWSER ACTIVE</p><p className="text-[9px] text-cyan-200/60">Browser actions are visible, verified, recoverable, and audited.</p></div>
            </div>
            <button onClick={triggerKillSwitch} className="rounded-lg border border-red-400/40 bg-red-500/10 px-3 py-2 text-[9px] font-bold uppercase tracking-wider text-red-300 hover:bg-red-500/20">Stop all sessions</button>
          </div>
        )}
        {tab === 'Overview' && (
          <div className="mx-auto max-w-4xl space-y-5">
            <div className="grid gap-4 md:grid-cols-3">
              <StatusCard
                title="Browser engine"
                value={status?.installed ? 'Ready' : 'Not installed'}
                detail={status?.version || 'Managed Chromium'}
                healthy={Boolean(status?.installed)}
              />
              <StatusCard
                title="Agent browser"
                value={agentSession ? agentSession.status : 'Starts automatically'}
                detail={agentSession?.last_url || 'Created when Shogun first browses'}
                healthy={Boolean(agentSession && agentSession.status !== 'error')}
              />
              <StatusCard
                title="Active sessions"
                value={String(status?.active_sessions || 0)}
                detail="Limited by the active Torii posture"
                healthy
              />
            </div>

            <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/[0.06] p-5">
              <div className="flex items-start gap-3">
                <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-cyan-400" />
                <div className="flex-1">
                  <h2 className="text-sm font-bold text-[#c8d0d8]">Permissions belong to Torii</h2>
                  <p className="mt-1 text-xs leading-relaxed text-[#7a8899]">
                    Mado does not maintain a second permission system. The active security posture controls
                    whether Shogun may browse, use visible sessions, download or upload files, and how many
                    browser sessions may run.
                  </p>
                  <a
                    href="/torii"
                    className="mt-3 inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-cyan-400 hover:text-cyan-300"
                  >
                    Open Torii permissions
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            </div>

            {!status?.installed && (
              <div className="rounded-xl border border-[#1a2040] bg-[#0e1225] p-5">
                <h2 className="text-sm font-bold text-[#c8d0d8]">Install the browser engine</h2>
                <p className="mt-1 text-xs text-[#7a8899]">
                  Chromium is the only component Mado needs before Shogun can browse.
                </p>
                <button
                  onClick={installChromium}
                  disabled={installing}
                  className="mt-4 inline-flex items-center gap-2 rounded-lg bg-cyan-500 px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[#071018] disabled:opacity-50"
                >
                  {installing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
                  {installing ? 'Installing…' : 'Install Chromium'}
                </button>
              </div>
            )}

            {agentSession && (
              <div className="flex items-center justify-between rounded-xl border border-[#1a2040] bg-[#0e1225] p-5">
                <div className="min-w-0">
                  <h2 className="text-sm font-bold text-[#c8d0d8]">Agent browser session</h2>
                  <p className="mt-1 truncate text-xs text-[#7a8899]">
                    {agentSession.last_url || 'No page visited yet'}
                  </p>
                </div>
                <button
                  onClick={() => resetSession(agentSession)}
                  disabled={workingSession === agentSession.id}
                  className="ml-4 inline-flex shrink-0 items-center gap-2 rounded-lg border border-[#1a2040] px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-[#7a8899] hover:border-cyan-500/40 hover:text-cyan-400 disabled:opacity-50"
                >
                  {workingSession === agentSession.id
                    ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    : <RotateCcw className="h-3.5 w-3.5" />}
                  Reset
                </button>
              </div>
            )}
          </div>
        )}

        {tab === 'Sessions' && (
          <div className="mx-auto max-w-5xl space-y-4">
            <div><h2 className="text-xs font-bold uppercase tracking-widest text-[#7a8899]">Live browser sessions</h2><p className="mt-1 text-[10px] text-[#555]">Runtime state, Stack association, verification, errors, and recent trajectory.</p></div>
            {sessions.length === 0 ? <div className="rounded-xl border border-[#1a2040] p-10 text-center text-xs text-[#7a8899]">No Mado sessions.</div> : sessions.map((session) => {
              const runtime = runtimeSessions.find((item) => item.session_id === session.id);
              const history = runtime?.timeline || session.session_data?.action_history || [];
              return <div key={session.id} className="overflow-hidden rounded-xl border border-[#1a2040] bg-[#0e1225]">
                <div className="flex items-start justify-between border-b border-[#1a2040] p-4">
                  <div className="min-w-0"><div className="flex items-center gap-2"><span className={cn('h-2 w-2 rounded-full', (runtime?.status || session.status) === 'active' ? 'bg-emerald-400' : (runtime?.status || session.status) === 'error' ? 'bg-red-400' : 'bg-amber-400')} /><h3 className="text-sm font-bold text-[#c8d0d8]">{session.name}</h3><span className="rounded bg-cyan-500/10 px-1.5 py-0.5 text-[8px] uppercase text-cyan-300">{runtime?.mode || session.browser_mode}</span></div><p className="mt-1 truncate text-[10px] text-[#7a8899]">{runtime?.title || runtime?.current_url || session.last_url || 'No page loaded'}</p><p className="mt-1 text-[8px] text-[#555]">Profile {runtime?.profile_id || session.profile_name} · Posture {runtime?.posture || session.session_data?.posture || 'current'} · Stack {runtime?.stack_run_id || session.session_data?.stack_run_id || 'standalone'}</p></div>
                  <div className="ml-4 flex gap-1">{(runtime?.status || session.status) === 'paused' ? <button title="Resume" onClick={() => controlSession(session, 'resume')} className="rounded p-2 text-emerald-400 hover:bg-emerald-500/10"><Play className="h-4 w-4" /></button> : <button title="Pause" onClick={() => controlSession(session, 'pause')} className="rounded p-2 text-amber-400 hover:bg-amber-500/10"><Pause className="h-4 w-4" /></button>}<button title="Close" onClick={() => controlSession(session, 'close')} className="rounded p-2 text-red-400 hover:bg-red-500/10"><X className="h-4 w-4" /></button></div>
                </div>
                <div className="grid gap-3 p-4 md:grid-cols-4"><Metric label="Last action" value={runtime?.last_action || session.session_data?.last_action || 'None'} /><Metric label="Verification" value={runtime?.last_verification?.status || session.session_data?.last_verification?.status || 'Pending'} /><Metric label="Retries" value={String(runtime?.retry_count || 0)} /><Metric label="Status" value={runtime?.last_error || session.session_data?.last_error || runtime?.status || session.status} danger={Boolean(runtime?.last_error || session.session_data?.last_error)} /></div>
                {history.length > 0 && <div className="border-t border-[#1a2040] p-4"><p className="mb-2 text-[8px] font-bold uppercase tracking-widest text-[#7a8899]">Recent execution trajectory</p><div className="max-h-40 space-y-1 overflow-y-auto">{history.slice(-8).reverse().map((item: any, index: number) => <div key={`${item.timestamp}-${index}`} className="flex gap-3 rounded bg-[#080b15] px-2 py-1.5 text-[9px]"><span className="w-16 shrink-0 text-[#555]">{item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : ''}</span><span className="w-44 shrink-0 text-cyan-400">{item.event_type || item.action}</span><span className="truncate text-[#7a8899]">{item.message || item.status || item.error}</span></div>)}</div></div>}
              </div>;
            })}
          </div>
        )}

        {tab === 'Screenshots' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xs font-bold uppercase tracking-widest text-[#7a8899]">Captured screenshots</h2>
                <p className="mt-1 text-[10px] text-[#555]">Evidence captured by Shogun and AgentFlow browser tasks</p>
              </div>
              <button onClick={refresh} className="rounded-lg p-2 text-[#7a8899] hover:bg-[#1a2040] hover:text-[#c8d0d8]">
                <RefreshCw className="h-3.5 w-3.5" />
              </button>
            </div>

            {screenshots.length === 0 ? (
              <div className="py-16 text-center">
                <Image className="mx-auto h-10 w-10 text-cyan-500/30" />
                <p className="mt-3 text-sm text-[#7a8899]">No screenshots yet</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                {screenshots.map((screenshot, index) => (
                  <button
                    key={screenshot.filename}
                    onClick={() => setLightboxIndex(index)}
                    className="group overflow-hidden rounded-xl border border-[#1a2040] bg-[#0e1225] text-left hover:border-cyan-500/40"
                  >
                    <div className="relative aspect-video overflow-hidden bg-[#080b15]">
                      <img
                        src={`/mado/screenshots/${screenshot.filename}`}
                        alt={screenshot.filename}
                        className="h-full w-full object-cover opacity-80 transition-all group-hover:scale-105 group-hover:opacity-100"
                      />
                      <div className="absolute inset-0 flex items-center justify-center bg-black/0 transition-colors group-hover:bg-black/30">
                        <Maximize2 className="h-5 w-5 text-white opacity-0 transition-opacity group-hover:opacity-100" />
                      </div>
                    </div>
                    <div className="p-3">
                      <p className="truncate text-[10px] font-bold text-[#c8d0d8]">{screenshot.filename}</p>
                      <p className="mt-1 text-[8px] text-[#555]">{(screenshot.size_bytes / 1024).toFixed(1)} KB</p>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'Permissions' && (
          <div className="mx-auto max-w-4xl space-y-5">
            <div className="rounded-xl border border-amber-400/25 bg-amber-500/[0.06] p-4"><div className="flex gap-3"><ShieldAlert className="h-5 w-5 shrink-0 text-amber-400" /><div><h2 className="text-sm font-bold text-amber-200">Mado Browser permissions</h2><p className="mt-1 text-xs leading-relaxed text-[#7a8899]">These settings narrow the active Torii posture. They never grant capabilities that the posture blocks. Authenticated profiles and external URLs remain opt-in.</p></div></div></div>
            <div className="grid gap-3 md:grid-cols-2">
              {[
                ['enabled', 'Enable Mado', 'Allow governed browser sessions'],
                ['headless_allowed', 'Allow headless mode', 'Run managed browser sessions without a window'],
                ['visible_allowed', 'Allow visible mode', 'Show Chromium while Mado operates'],
                ['allow_external_urls', 'Allow external URLs', 'Permit URLs outside the configured domain list'],
                ['allow_persistent_profiles', 'Allow persistent profiles', 'Keep local browser state between sessions'],
                ['allow_authenticated_sessions', 'Allow authenticated sessions', 'Use profiles that may contain saved login state'],
                ['require_verification', 'Require verification', 'Verify key browser outcomes before completion'],
              ].map(([key, label, detail]) => <label key={key} className="flex cursor-pointer items-center justify-between rounded-xl border border-[#1a2040] bg-[#0e1225] p-4"><div><p className="text-xs font-bold text-[#c8d0d8]">{label}</p><p className="mt-1 text-[9px] text-[#555]">{detail}</p></div><input type="checkbox" checked={Boolean(madoConfig[key])} onChange={(event) => setMadoConfig((current) => ({ ...current, [key]: event.target.checked }))} className="h-4 w-4 accent-cyan-500" /></label>)}
              <label className="flex cursor-pointer items-center justify-between rounded-xl border border-[#1a2040] bg-[#0e1225] p-4"><div><p className="text-xs font-bold text-[#c8d0d8]">Capture evidence screenshots</p><p className="mt-1 text-[9px] text-[#555]">Save visual evidence on errors and verification</p></div><input type="checkbox" checked={Boolean(madoConfig.audit?.capture_screenshots_on_error && madoConfig.audit?.capture_screenshots_on_verification)} onChange={(event) => setMadoConfig((current) => ({ ...current, audit: { ...(current.audit || {}), capture_screenshots_on_error: event.target.checked, capture_screenshots_on_verification: event.target.checked, log_all_actions: true } }))} className="h-4 w-4 accent-cyan-500" /></label>
            </div>
            <div className="grid gap-4 rounded-xl border border-[#1a2040] bg-[#0e1225] p-4 md:grid-cols-2"><ConfigText label="Allowed domains" value={(madoConfig.allowed_domains || []).join(', ')} onChange={(value) => setMadoConfig((current) => ({ ...current, allowed_domains: value.split(',').map((item) => item.trim()).filter(Boolean) }))} /><ConfigText label="Blocked domains" value={(madoConfig.blocked_domains || []).join(', ')} onChange={(value) => setMadoConfig((current) => ({ ...current, blocked_domains: value.split(',').map((item) => item.trim()).filter(Boolean) }))} /><ConfigSelect label="Default browser mode" value={madoConfig.default_mode || 'visible'} options={['visible', 'headless']} onChange={(value) => setMadoConfig((current) => ({ ...current, default_mode: value }))} /><ConfigSelect label="File downloads" value={madoConfig.allow_file_downloads || 'approval'} options={['blocked', 'approval', 'allowed']} onChange={(value) => setMadoConfig((current) => ({ ...current, allow_file_downloads: value }))} /><ConfigSelect label="File uploads" value={madoConfig.allow_file_uploads || 'approval'} options={['blocked', 'approval', 'allowed']} onChange={(value) => setMadoConfig((current) => ({ ...current, allow_file_uploads: value }))} /><ConfigSelect label="Form submission" value={madoConfig.allow_form_submit || 'approval'} options={['blocked', 'approval', 'allowed']} onChange={(value) => setMadoConfig((current) => ({ ...current, allow_form_submit: value }))} /><ConfigNumber label="Maximum pages per run" value={madoConfig.max_pages_per_run || 50} onChange={(value) => setMadoConfig((current) => ({ ...current, max_pages_per_run: value }))} /><ConfigNumber label="Maximum runtime (seconds)" value={madoConfig.max_runtime_seconds || 1800} onChange={(value) => setMadoConfig((current) => ({ ...current, max_runtime_seconds: value }))} /></div>
            <button onClick={saveMadoConfig} disabled={savingConfig} className="inline-flex items-center gap-2 rounded-lg bg-cyan-500 px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[#071018] disabled:opacity-50">{savingConfig ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />} Save Mado settings</button>
          </div>
        )}

        {tab === 'Advanced' && (
          <div className="mx-auto max-w-4xl space-y-6">
            <div>
              <h2 className="text-xs font-bold uppercase tracking-widest text-[#7a8899]">Advanced diagnostics</h2>
              <p className="mt-1 text-[10px] text-[#555]">
                Runtime details for troubleshooting. Browser permissions remain in Torii.
              </p>
            </div>

            <div className="rounded-xl border border-[#1a2040] bg-[#0e1225]">
              <div className="border-b border-[#1a2040] px-4 py-3 text-xs font-bold text-[#c8d0d8]">Runtime sessions</div>
              {sessions.length === 0 ? (
                <p className="p-5 text-xs text-[#7a8899]">No browser sessions have been created.</p>
              ) : sessions.map((session) => (
                <div key={session.id} className="flex items-center gap-4 border-b border-[#1a2040]/70 px-4 py-3 last:border-0">
                  <div className={cn(
                    'h-2 w-2 shrink-0 rounded-full',
                    session.status === 'active' ? 'bg-emerald-400' : session.status === 'error' ? 'bg-red-400' : 'bg-[#7a8899]',
                  )} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-[#c8d0d8]">{session.name}</span>
                      {session.profile_name === 'native_skill' && (
                        <span className="rounded bg-cyan-500/10 px-1.5 py-0.5 text-[8px] font-bold uppercase text-cyan-400">Agent managed</span>
                      )}
                    </div>
                    <p className="mt-0.5 truncate text-[9px] text-[#555]">
                      {session.profile_name} · {session.browser_mode} · {session.last_url || 'No URL'}
                    </p>
                  </div>
                  <button
                    onClick={() => resetSession(session)}
                    disabled={workingSession === session.id}
                    title="Remove browser session"
                    className="rounded-lg p-2 text-[#7a8899] hover:bg-red-500/10 hover:text-red-400 disabled:opacity-50"
                  >
                    {workingSession === session.id
                      ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      : <Trash2 className="h-3.5 w-3.5" />}
                  </button>
                </div>
              ))}
            </div>

            {status && (
              <div className="rounded-xl border border-[#1a2040] bg-[#0e1225] p-4">
                <h3 className="text-xs font-bold text-[#c8d0d8]">Storage paths</h3>
                <div className="mt-3 space-y-2">
                  {[
                    ['Profiles', status.profiles_path],
                    ['Screenshots', status.screenshots_path],
                    ['Downloads', status.downloads_path],
                  ].map(([label, value]) => (
                    <div key={label} className="flex gap-4 text-[10px]">
                      <span className="w-24 shrink-0 font-bold uppercase tracking-wider text-[#7a8899]">{label}</span>
                      <span className="min-w-0 break-all font-mono text-[#555]">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {lightboxIndex !== null && screenshots[lightboxIndex] && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm"
          onClick={() => setLightboxIndex(null)}
        >
          <button
            onClick={() => setLightboxIndex(null)}
            className="absolute right-4 top-4 rounded-full bg-black/50 p-2 text-white/80 hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>
          {lightboxIndex > 0 && (
            <button
              onClick={(event) => { event.stopPropagation(); setLightboxIndex(lightboxIndex - 1); }}
              className="absolute left-4 rounded-full bg-black/50 p-2 text-white/80 hover:text-white"
            >
              <ChevronLeft className="h-6 w-6" />
            </button>
          )}
          {lightboxIndex < screenshots.length - 1 && (
            <button
              onClick={(event) => { event.stopPropagation(); setLightboxIndex(lightboxIndex + 1); }}
              className="absolute right-4 rounded-full bg-black/50 p-2 text-white/80 hover:text-white"
            >
              <ChevronRight className="h-6 w-6" />
            </button>
          )}
          <img
            src={`/mado/screenshots/${screenshots[lightboxIndex].filename}`}
            alt={screenshots[lightboxIndex].filename}
            className="max-h-[85vh] max-w-[90vw] rounded-lg object-contain shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}

function StatusCard({
  title,
  value,
  detail,
  healthy,
}: {
  title: string;
  value: string;
  detail: string;
  healthy: boolean;
}) {
  return (
    <div className="rounded-xl border border-[#1a2040] bg-[#0e1225] p-4">
      <div className="flex items-center gap-2">
        <div className={cn('h-2 w-2 rounded-full', healthy ? 'bg-emerald-400' : 'bg-amber-400')} />
        <span className="text-[9px] font-bold uppercase tracking-widest text-[#7a8899]">{title}</span>
      </div>
      <p className="mt-3 truncate text-sm font-bold capitalize text-[#c8d0d8]">{value}</p>
      <p className="mt-1 truncate text-[9px] text-[#555]">{detail}</p>
    </div>
  );
}

function Metric({ label, value, danger = false }: { label: string; value: string; danger?: boolean }) {
  return <div className="rounded-lg bg-[#080b15] p-3"><p className="text-[8px] font-bold uppercase tracking-widest text-[#555]">{label}</p><p className={cn('mt-2 truncate text-[10px] font-semibold', danger ? 'text-red-300' : 'text-[#c8d0d8]')}>{value}</p></div>;
}

function ConfigText({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="text-[9px] font-bold uppercase tracking-wider text-[#7a8899]">{label}<input value={value} onChange={(event) => onChange(event.target.value)} placeholder="example.com, portal.example.com" className="mt-2 w-full rounded-lg border border-[#1a2040] bg-[#080b15] px-3 py-2 text-xs font-normal normal-case text-[#c8d0d8] outline-none focus:border-cyan-500/50" /></label>;
}

function ConfigNumber({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return <label className="text-[9px] font-bold uppercase tracking-wider text-[#7a8899]">{label}<input type="number" min={1} value={value} onChange={(event) => onChange(Math.max(1, Number(event.target.value)))} className="mt-2 w-full rounded-lg border border-[#1a2040] bg-[#080b15] px-3 py-2 text-xs font-normal text-[#c8d0d8] outline-none focus:border-cyan-500/50" /></label>;
}

function ConfigSelect({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return <label className="text-[9px] font-bold uppercase tracking-wider text-[#7a8899]">{label}<select value={value} onChange={(event) => onChange(event.target.value)} className="mt-2 w-full rounded-lg border border-[#1a2040] bg-[#080b15] px-3 py-2 text-xs font-normal capitalize text-[#c8d0d8] outline-none focus:border-cyan-500/50">{options.map((option) => <option key={option} value={option}>{option.replaceAll('_', ' ')}</option>)}</select></label>;
}
