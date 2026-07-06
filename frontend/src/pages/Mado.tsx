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
  RefreshCw,
  RotateCcw,
  ShieldCheck,
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
}

interface Screenshot {
  filename: string;
  size_bytes: number;
  created_at: string;
}

type Tab = 'Overview' | 'Screenshots' | 'Advanced';

const ACCENT = '#06b6d4';
const TABS: Tab[] = ['Overview', 'Screenshots', 'Advanced'];

export function Mado() {
  const [tab, setTab] = useState<Tab>('Overview');
  const [status, setStatus] = useState<MadoStatus | null>(null);
  const [sessions, setSessions] = useState<MadoSession[]>([]);
  const [screenshots, setScreenshots] = useState<Screenshot[]>([]);
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
