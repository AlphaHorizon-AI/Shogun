import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import {
  AlertTriangle, BarChart3, CheckCircle2, ExternalLink, Eye, EyeOff, Loader2, Radio,
  Send, ShieldCheck, ToggleLeft, ToggleRight, Trash2, XCircle,
} from 'lucide-react';
import {
  getInfrastructureAdminToken,
  infrastructureRequestConfig,
  setInfrastructureAdminToken,
} from '../lib/infrastructureAuth';

interface TelemetryStatus {
  enabled: boolean;
  requires_consent_renewal: boolean;
  consent_notice_version: string | null;
  required_consent_version: string;
  consented_at: string | null;
  installation_id_abbreviated: string | null;
  last_sent_at: string | null;
  next_scheduled_at: string | null;
  last_result: string | null;
  queued_events: number;
  privacy_notice_url: string;
  shared_fields: string[];
  never_shared: string[];
}

interface Preview {
  payload: Record<string, unknown>;
  notice: string;
}

interface CollegeTelemetrySettings {
  enabled: boolean;
  shared_fields: string[];
  never_shared: string[];
  last_delivery: { state: string; at: string | null; error: string | null };
}

const formatDate = (value: string | null) =>
  value ? new Date(value).toLocaleString() : 'Not yet';

export function PrivacyTelemetry() {
  const [status, setStatus] = useState<TelemetryStatus | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [token, setToken] = useState(getInfrastructureAdminToken);
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [identifier, setIdentifier] = useState('');
  const [collegeTelemetry, setCollegeTelemetry] = useState<CollegeTelemetrySettings | null>(null);
  const [savingCollegeTelemetry, setSavingCollegeTelemetry] = useState(false);
  const [collegeTelemetryError, setCollegeTelemetryError] = useState('');

  const config = useCallback(() => infrastructureRequestConfig(token), [token]);
  const loadCollegeTelemetry = useCallback(async () => {
    try {
      const response = await axios.get('/api/v1/system/college-telemetry');
      setCollegeTelemetry(response.data.data);
      setCollegeTelemetryError('');
    } catch {
      setCollegeTelemetry(null);
      setCollegeTelemetryError('Could not load OpenClaw College sharing settings.');
    }
  }, []);

  const refresh = useCallback(async () => {
    setError('');
    try {
      const [statusResponse, previewResponse] = await Promise.all([
        axios.get('/api/v1/telemetry/status', config()),
        axios.get('/api/v1/telemetry/preview', config()),
      ]);
      setStatus(statusResponse.data);
      setPreview(previewResponse.data);
    } catch {
      setError('Administrator authorization is required to view telemetry settings.');
    }
  }, [config]);

  useEffect(() => {
    const timer = window.setTimeout(() => void refresh(), 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadCollegeTelemetry(), 0);
    return () => window.clearTimeout(timer);
  }, [loadCollegeTelemetry]);

  const toggleCollegeTelemetry = async () => {
    if (!collegeTelemetry) return;
    setSavingCollegeTelemetry(true);
    setCollegeTelemetryError('');
    try {
      const response = await axios.put('/api/v1/system/college-telemetry', {
        enabled: !collegeTelemetry.enabled,
      });
      setCollegeTelemetry(response.data.data);
    } catch (caught) {
      setCollegeTelemetryError(axios.isAxiosError(caught)
        ? String(caught.response?.data?.detail || caught.message)
        : 'Could not update OpenClaw College sharing settings.');
    } finally {
      setSavingCollegeTelemetry(false);
    }
  };

  const act = async (name: string, action: () => Promise<unknown>) => {
    setBusy(name);
    setError('');
    setMessage('');
    try {
      await action();
      setMessage(name === 'enable' ? 'Telemetry enabled with explicit consent.' : 'Action completed.');
      await refresh();
    } catch (caught) {
      setError(axios.isAxiosError(caught)
        ? String(caught.response?.data?.detail || caught.message)
        : 'The action could not be completed.');
    } finally {
      setBusy('');
    }
  };

  return (
    <div className="min-h-full bg-shogun-bg p-6 text-shogun-text">
      <div className="mx-auto max-w-5xl space-y-6">
        <header>
          <div className="flex items-center gap-3">
            <ShieldCheck className="h-7 w-7 text-shogun-gold" />
            <div>
              <h1 className="text-2xl font-bold">Privacy &amp; Telemetry</h1>
              <p className="text-sm text-shogun-subdued">
                Voluntary, pseudonymous installation statistics. Disabled by default.
              </p>
            </div>
          </div>
        </header>

        <section className="rounded-xl border border-shogun-border bg-shogun-card p-5">
          <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-shogun-subdued">
            Server administrator token (kept in this browser session only)
          </label>
          <input
            type="password"
            value={token}
            onChange={(event) => {
              setToken(event.target.value);
              setInfrastructureAdminToken(event.target.value);
            }}
            onBlur={() => void refresh()}
            placeholder="Desktop installations do not require a token"
            className="w-full rounded-lg border border-shogun-border bg-black/20 px-3 py-2 text-sm"
          />
        </section>

        {error && <div className="flex gap-2 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300"><XCircle className="h-5 w-5" />{error}</div>}
        {message && <div className="flex gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-emerald-300"><CheckCircle2 className="h-5 w-5" />{message}</div>}

        <section className="space-y-5 rounded-xl border border-shogun-border bg-shogun-card p-6">
          <div className="flex items-start justify-between gap-5">
            <div className="flex gap-3">
              <div className="rounded-lg bg-cyan-500/10 p-2.5 text-cyan-300"><BarChart3 className="h-5 w-5" /></div>
              <div>
                <h2 className="text-sm font-semibold text-white">OpenClaw College ecosystem intelligence</h2>
                <p className="mt-1 max-w-xl text-xs leading-relaxed text-shogun-subdued">
                  Contribute anonymous, coarse model-performance signals to ecosystem benchmarks. Sharing is on by default and can be disabled at any time.
                </p>
              </div>
            </div>
            <button
              onClick={() => void toggleCollegeTelemetry()}
              disabled={!collegeTelemetry || savingCollegeTelemetry}
              className="shrink-0 text-cyan-300 disabled:opacity-40"
              title={collegeTelemetry?.enabled ? 'Disable ecosystem sharing' : 'Enable ecosystem sharing'}
            >
              {collegeTelemetry?.enabled ? <ToggleRight className="h-9 w-9" /> : <ToggleLeft className="h-9 w-9 text-shogun-subdued" />}
            </button>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/[0.04] p-4">
              <div className="mb-2 flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-emerald-300"><ShieldCheck className="h-3.5 w-3.5" /> Never shared</div>
              <p className="text-[11px] leading-relaxed text-shogun-subdued">Prompts, outputs, files, agent names, credentials, exact IP addresses, or error contents.</p>
            </div>
            <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/[0.04] p-4">
              <div className="mb-2 text-[10px] font-bold uppercase tracking-wider text-cyan-300">Coarse signals only</div>
              <p className="text-[11px] leading-relaxed text-shogun-subdued">Model, provider, task category, success, bucketed usage, local/cloud, country code, Shogun version, and a weekly rotating anonymous ID.</p>
            </div>
          </div>
          {collegeTelemetryError && <p className="text-xs text-red-300">{collegeTelemetryError}</p>}
          <div className="flex items-center justify-between text-[11px] text-shogun-subdued">
            <span>Status: <strong className={collegeTelemetry?.enabled ? 'text-emerald-300' : 'text-shogun-text'}>{collegeTelemetry?.enabled ? 'Contributing anonymously' : 'Not sharing'}</strong></span>
            <a href="https://www.openclawcollege.com/#/dashboard" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-cyan-300 hover:underline">View ecosystem insights <ExternalLink className="h-3 w-3" /></a>
          </div>
        </section>

        {status && (
          <>
            <section className="grid gap-4 rounded-xl border border-shogun-border bg-shogun-card p-5 md:grid-cols-2">
              <div>
                <div className="flex items-center gap-2">
                  {status.enabled ? <Radio className="h-5 w-5 text-emerald-400" /> : <EyeOff className="h-5 w-5 text-shogun-subdued" />}
                  <h2 className="font-bold">Anonymous installation telemetry: {status.enabled ? 'Enabled' : 'Disabled'}</h2>
                </div>
                <p className="mt-2 text-sm text-shogun-subdued">
                  Shogun shares at most one small weekly status signal. No prompts, files,
                  memories, messages, agent activity, or personal identities are collected.
                </p>
              </div>
              <dl className="grid grid-cols-2 gap-2 text-sm">
                <dt className="text-shogun-subdued">Installation ID</dt><dd>{status.installation_id_abbreviated || 'Not created'}</dd>
                <dt className="text-shogun-subdued">Consent date</dt><dd>{formatDate(status.consented_at)}</dd>
                <dt className="text-shogun-subdued">Notice version</dt><dd>{status.consent_notice_version || 'None'}</dd>
                <dt className="text-shogun-subdued">Last sent</dt><dd>{formatDate(status.last_sent_at)}</dd>
                <dt className="text-shogun-subdued">Next signal</dt><dd>{formatDate(status.next_scheduled_at)}</dd>
                <dt className="text-shogun-subdued">Last result</dt><dd>{status.last_result || 'No attempt'}</dd>
              </dl>
            </section>

            {!status.enabled && (
              <section className="rounded-xl border border-shogun-gold/30 bg-shogun-card p-5">
                <h2 className="font-bold">Help improve Shogun AFM</h2>
                <p className="mt-2 text-sm text-shogun-subdued">
                  Optionally share installation, version, platform family, installation type,
                  operating mode, and a weekly active-installation signal with Alpha Horizon.
                  Declining does not change any Shogun feature, update, or support access.
                </p>
                <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-lg border border-shogun-border p-3">
                  <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} className="mt-1" />
                  <span className="text-sm">
                    I choose to share anonymous installation statistics and accept telemetry
                    notice version {status.required_consent_version}. This choice is separate
                    from the Shogun licence.
                  </span>
                </label>
                <button
                  disabled={!confirmed || !!busy}
                  onClick={() => void act('enable', () => axios.post(
                    '/api/v1/telemetry/enable',
                    { notice_version: status.required_consent_version, confirmed: true },
                    config(),
                  ))}
                  className="mt-4 rounded-lg bg-shogun-gold px-4 py-2 text-sm font-bold text-black disabled:opacity-40"
                >
                  {busy === 'enable' ? 'Enabling…' : 'Enable telemetry'}
                </button>
              </section>
            )}

            <section className="grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-shogun-border bg-shogun-card p-5">
                <h3 className="font-bold text-emerald-300">Exact fields shared</h3>
                <ul className="mt-3 space-y-1 text-sm text-shogun-subdued">
                  {status.shared_fields.map((field) => <li key={field}>• {field}</li>)}
                </ul>
              </div>
              <div className="rounded-xl border border-shogun-border bg-shogun-card p-5">
                <h3 className="font-bold text-red-300">Never shared</h3>
                <ul className="mt-3 space-y-1 text-sm text-shogun-subdued">
                  {status.never_shared.map((field) => <li key={field}>• {field}</li>)}
                </ul>
              </div>
            </section>

            {preview && (
              <section className="rounded-xl border border-shogun-border bg-shogun-card p-5">
                <h3 className="flex items-center gap-2 font-bold"><Eye className="h-4 w-4" />Exact next heartbeat payload preview</h3>
                <pre className="mt-3 overflow-auto rounded-lg bg-black/30 p-4 text-xs text-emerald-200">{JSON.stringify(preview.payload, null, 2)}</pre>
                <p className="mt-2 text-xs text-shogun-subdued">{preview.notice}</p>
              </section>
            )}

            <section className="flex flex-wrap gap-3 rounded-xl border border-shogun-border bg-shogun-card p-5">
              <a href={status.privacy_notice_url} target="_blank" rel="noreferrer" className="rounded-lg border border-shogun-border px-4 py-2 text-sm hover:border-shogun-gold">Privacy notice</a>
              <button disabled={!status.enabled || !!busy} onClick={() => void act('test', () => axios.post('/api/v1/telemetry/test', {}, config()))} className="flex items-center gap-2 rounded-lg border border-shogun-border px-4 py-2 text-sm disabled:opacity-40"><Send className="h-4 w-4" />Send test event</button>
              <button disabled={!status.enabled || !!busy} onClick={() => void act('disable', () => axios.post('/api/v1/telemetry/disable', {}, config()))} className="rounded-lg border border-amber-500/50 px-4 py-2 text-sm text-amber-300 disabled:opacity-40">Disable</button>
              <button disabled={!status.installation_id_abbreviated || !!busy} onClick={() => void act('delete', () => axios.post('/api/v1/telemetry/delete', {}, config()))} className="flex items-center gap-2 rounded-lg border border-red-500/50 px-4 py-2 text-sm text-red-300 disabled:opacity-40"><Trash2 className="h-4 w-4" />Delete my telemetry data</button>
              <button onClick={() => void act('identifier', async () => {
                if (!window.confirm('Show the full pseudonymous installation identifier?')) return;
                const response = await axios.get('/api/v1/telemetry/identifier', config());
                setIdentifier(response.data.installation_id || 'Not created');
              })} className="rounded-lg border border-shogun-border px-4 py-2 text-sm">Show identifier</button>
            </section>
            {identifier && <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm"><AlertTriangle className="mr-2 inline h-4 w-4 text-amber-400" />Installation ID: <code>{identifier}</code></div>}
          </>
        )}
        {busy && <Loader2 className="mx-auto h-6 w-6 animate-spin text-shogun-gold" />}
      </div>
    </div>
  );
}
