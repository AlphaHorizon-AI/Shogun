import { useState, useEffect } from 'react';
import {
  AlertTriangle,
  ArrowUpCircle,
  CheckCircle,
  Clock,
  Crown,
  Download,
  ExternalLink,
  KeyRound,
  Mail,
  Power,
  RefreshCw,
} from 'lucide-react';
import { useTranslation } from '../i18n';

const WHITE_LABEL_ACCESS_EMAIL =
  'mailto:contact@alphahorizon.io?subject=Shogun%20White%20Label%20Commercial%20Inquiry'
  + '&body=Hello%20Alpha%20Horizon%2C%0D%0A%0D%0AI%20would%20like%20to%20discuss%20Shogun%20White%20Label%20pricing%20and%20the%20appropriate%20company%20tier.%0D%0A%0D%0ACompany%3A%0D%0ACompany%20size%3A%0D%0AExpected%20users%3A%0D%0A';

type WhiteLabelResult = {
  tone: 'success' | 'error';
  message: string;
};

interface UpdateStatus {
  update_available: boolean;
  local_version: string;
  local_build: number;
  remote_version: string | null;
  remote_build: number | null;
  changelog: string | null;
  released: string | null;
  last_checked: string;
  error?: string;
  auth_required?: boolean;
  token_configured?: boolean;
  installed_version?: string;
  installed_build?: number;
  running_version?: string;
  running_build?: number;
  restart_required?: boolean;
  security_changes?: string[];
  breaking_changes?: string[];
}

export const Updates = () => {
  const { t } = useTranslation();
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const [checking, setChecking] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [installResult, setInstallResult] = useState<string | null>(null);
  const [githubToken, setGithubToken] = useState('');
  const [savingToken, setSavingToken] = useState(false);
  const [whiteLabelToken, setWhiteLabelToken] = useState('');
  const [startingWhiteLabelUpgrade, setStartingWhiteLabelUpgrade] = useState(false);
  const [whiteLabelResult, setWhiteLabelResult] = useState<WhiteLabelResult | null>(null);

  const startWhiteLabelUpgrade = async () => {
    const token = whiteLabelToken.trim();
    if (!token) return;

    setStartingWhiteLabelUpgrade(true);
    setWhiteLabelResult(null);
    try {
      const response = await fetch('/api/v1/updates/white-label/upgrade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ github_token: token }),
      });
      const data = await response.json().catch(() => ({}));
      const detail = typeof data.detail === 'string' ? data.detail : data.detail?.message;
      if (!response.ok) throw new Error(detail || `HTTP ${response.status}`);
      setWhiteLabelResult({
        tone: 'success',
        message: data.message || 'White Label upgrade started. Shogun will report when it is ready.',
      });
    } catch (error: unknown) {
      setWhiteLabelResult({
        tone: 'error',
        message: error instanceof Error ? error.message : 'Could not start the White Label upgrade.',
      });
    } finally {
      // The White Label credential is intentionally never persisted by this page.
      setWhiteLabelToken('');
      setStartingWhiteLabelUpgrade(false);
    }
  };

  const saveUpdateAccess = async () => {
    if (!githubToken.trim()) return;
    setSavingToken(true);
    setInstallResult(null);
    try {
      const response = await fetch('/api/v1/updates/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ github_token: githubToken.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      setGithubToken('');
      setStatus(data.status);
      setInstallResult('Update access saved securely on this device.');
    } catch (e: unknown) {
      setInstallResult(`Could not save update access: ${e instanceof Error ? e.message : 'Unknown error'}`);
    } finally {
      setSavingToken(false);
    }
  };

  const checkForUpdates = async (force = false) => {
    setChecking(true);
    try {
      const r = await fetch(`/api/v1/updates/check?force=${force}`);
      if (!r.ok) {
        const errData = await r.json().catch(() => null);
        throw new Error(errData?.detail || `HTTP Error ${r.status}`);
      }
      const data = await r.json();
      setStatus(data.data ? data.data : data);
    } catch (e: unknown) {
      setStatus({
        update_available: false,
        local_version: 'error',
        local_build: 0,
        remote_version: null,
        remote_build: null,
        changelog: null,
        released: null,
        last_checked: new Date().toISOString(),
        error: e instanceof Error ? e.message : 'Failed to check updates'
      });
    }
    setChecking(false);
  };

  const installUpdate = async () => {
    if (!confirm(t('updates_page.install_confirm'))) return;
    setInstalling(true);
    setInstallResult(null);
    try {
      const r = await fetch('/api/v1/updates/apply', { method: 'POST' });
      const data = await r.json();
      if (data.success) {
        const warningText = data.warnings?.length ? ` Warnings: ${data.warnings.join(' ')}` : '';
        setInstallResult(`✅ Updated to v${data.new_version} (build ${data.new_build}). ${data.files_updated} files updated. Please restart Shogun.${warningText}`);
        checkForUpdates(true);
        window.setTimeout(() => window.location.reload(), 1800);
      } else {
        setInstallResult(`❌ ${data.detail || 'Update failed'}`);
      }
    } catch (e: unknown) {
      setInstallResult(`❌ Update failed: ${e instanceof Error ? e.message : 'Unknown error'}`);
    }
    setInstalling(false);
  };

  const restartShogun = async () => {
    if (!confirm('Restart Shogun now? Active operations will stop, the Shogun browser will close, and Tenshu will reopen when startup completes.')) return;
    setRestarting(true);
    setInstallResult(null);
    try {
      const response = await fetch('/api/v1/updates/restart', { method: 'POST' });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      setInstallResult(data.browser_will_reopen
        ? 'Shogun is restarting. This browser will close and Tenshu will reopen automatically.'
        : 'Shogun is restarting through its server supervisor. Reopen Tenshu when the server is ready.');
      window.setTimeout(() => {
        // Browsers permit scripts to close dedicated/app windows. If this is a
        // user-created tab, the message remains visible while the launcher
        // opens the replacement Tenshu window.
        window.close();
      }, 450);
    } catch (error: unknown) {
      setInstallResult(`Restart failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setRestarting(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => void checkForUpdates(), 0);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <Download className="w-6 h-6 text-shogun-gold" />
          {t('updates_page.title')}
        </h1>
        <p className="text-shogun-subdued mt-1">{t('updates_page.subtitle')}</p>
      </div>

      <section className="rounded-xl border border-[#d4a017]/35 bg-gradient-to-br from-[#d4a017]/10 via-shogun-card to-violet-500/10 p-6">
        <div className="flex items-start gap-4">
          <div className="rounded-xl border border-[#d4a017]/30 bg-[#d4a017]/10 p-3">
            <Crown className="h-6 w-6 text-[#d4a017]" />
          </div>
          <div>
            <h2 className="font-bold text-shogun-text">
              {t('updates_page.white_label_title', 'Move to the full commercial edition')}
            </h2>
            <p className="mt-1 max-w-xl text-xs leading-relaxed text-shogun-subdued">
              {t(
                'updates_page.white_label_description',
                'Official Yellow Label updates may be discontinued in the future. White Label provides licensed commercial access and private-repository updates; independently maintained Yellow Label installations can continue to be updated manually.',
              )}
            </p>
          </div>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <div className="flex flex-col rounded-xl border border-shogun-border bg-shogun-bg/60 p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-shogun-text">
              <Mail className="h-4 w-4 text-[#d4a017]" />
              {t('updates_page.white_label_need_access', 'Discuss White Label for my company')}
            </div>
            <p className="mt-2 flex-1 text-xs leading-relaxed text-shogun-subdued">
              {t(
                'updates_page.white_label_need_access_description',
                'White Label is a paid commercial product. Email us to start a conversation about pricing and the appropriate company tier. Sending an inquiry does not automatically provide an access token.',
              )}
            </p>
            <a
              href={WHITE_LABEL_ACCESS_EMAIL}
              className="mt-4 inline-flex items-center justify-center gap-2 rounded-lg border border-[#d4a017]/50 px-4 py-2.5 text-sm font-semibold text-[#e6b422] transition-colors hover:bg-[#d4a017]/10"
            >
              {t('updates_page.white_label_send_email', 'Contact us about pricing')}
              <ExternalLink className="h-4 w-4" />
            </a>
          </div>

          <div className="flex flex-col rounded-xl border border-shogun-border bg-shogun-bg/60 p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-shogun-text">
              <KeyRound className="h-4 w-4 text-violet-300" />
              {t('updates_page.white_label_have_token', 'I already have an access token')}
            </div>
            <p className="mt-2 text-xs leading-relaxed text-shogun-subdued">
              {t(
                'updates_page.white_label_have_token_description',
                'Enter the token issued for the White Label repository. It is used only for this upgrade request and is not saved by this page.',
              )}
            </p>
            <div className="mt-4 space-y-3">
              <input
                type="password"
                value={whiteLabelToken}
                onChange={event => setWhiteLabelToken(event.target.value)}
                onKeyDown={event => { if (event.key === 'Enter') void startWhiteLabelUpgrade(); }}
                placeholder={t('updates_page.white_label_token_placeholder', 'White Label access token')}
                aria-label={t('updates_page.white_label_token_placeholder', 'White Label access token')}
                autoComplete="off"
                className="w-full rounded-lg border border-shogun-border bg-shogun-bg px-3 py-2.5 text-sm text-shogun-text outline-none focus:border-violet-400"
              />
              <button
                type="button"
                onClick={startWhiteLabelUpgrade}
                disabled={startingWhiteLabelUpgrade || !whiteLabelToken.trim()}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[#d4a017] px-4 py-2.5 text-sm font-bold text-black transition-colors hover:bg-[#e6b422] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {startingWhiteLabelUpgrade
                  ? t('updates_page.white_label_starting', 'Starting…')
                  : t('updates_page.upgrade_white_label', 'Upgrade to White Label')}
                <ArrowUpCircle className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {whiteLabelResult && (
          <div
            role="status"
            className={`mt-4 rounded-lg border px-4 py-3 text-xs ${
              whiteLabelResult.tone === 'success'
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                : 'border-amber-500/30 bg-amber-500/10 text-amber-200'
            }`}
          >
            {whiteLabelResult.message}
          </div>
        )}
      </section>

      {/* Version Card */}
      <div className="bg-shogun-card border border-shogun-border rounded-xl p-6">
        <div className="grid grid-cols-2 gap-6">
          <div>
            <p className="text-[10px] uppercase tracking-wider text-shogun-subdued mb-1">{t('updates_page.current_version')}</p>
            <p className="text-2xl font-bold text-white">
              v{status?.local_version || '...'}
              <span className="text-sm text-shogun-subdued ml-2">build {status?.local_build ?? '...'}</span>
            </p>
          </div>
          {status?.remote_version && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-shogun-subdued mb-1">{t('updates_page.latest_available')}</p>
              <p className="text-2xl font-bold text-emerald-400">
                v{status.remote_version}
                <span className="text-sm text-shogun-subdued ml-2">build {status.remote_build}</span>
              </p>
            </div>
          )}
        </div>

        {/* Status line */}
        <div className="mt-6 flex items-center gap-3">
          {status?.update_available ? (
            <>
              <ArrowUpCircle className="w-5 h-5 text-emerald-400" />
              <span className="text-emerald-400 font-semibold">{t('updates_page.new_version_available')}</span>
            </>
          ) : status?.error ? (
            <>
              <AlertTriangle className="w-5 h-5 text-amber-400" />
              <span className="text-amber-400">{status.error}</span>
            </>
          ) : status ? (
            <>
              <CheckCircle className="w-5 h-5 text-emerald-400" />
              <span className="text-shogun-subdued">{t('updates_page.up_to_date')}</span>
            </>
          ) : null}
        </div>

        {/* Last checked */}
        {status?.last_checked && (
          <div className="mt-3 flex items-center gap-2 text-[11px] text-shogun-subdued">
            <Clock className="w-3 h-3" />
            {t('updates_page.last_checked')}: {new Date(status.last_checked).toLocaleString()}
          </div>
        )}
      </div>

      {status?.restart_required && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 text-sm text-amber-200">
          Installed build {status.installed_build} is ready, but Shogun is still running build {status.running_build}. Restart Shogun to finish switching over.
        </div>
      )}

      {status?.auth_required && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-6 space-y-3">
          <div>
            <h3 className="text-sm font-semibold text-amber-300">Private update access</h3>
            <p className="text-xs text-shogun-subdued mt-1">
              This installation needs GitHub access to check and download updates. The token is encrypted and stored only on this device.
            </p>
          </div>
          <div className="flex gap-3">
            <input
              type="password"
              value={githubToken}
              onChange={event => setGithubToken(event.target.value)}
              onKeyDown={event => { if (event.key === 'Enter') void saveUpdateAccess(); }}
              placeholder="GitHub access token"
              autoComplete="off"
              className="flex-1 bg-shogun-bg border border-shogun-border rounded-lg px-3 py-2 text-sm text-shogun-text focus:border-amber-400 outline-none"
            />
            <button
              onClick={saveUpdateAccess}
              disabled={savingToken || !githubToken.trim()}
              className="px-4 py-2 rounded-lg bg-amber-600 text-white text-sm font-semibold hover:bg-amber-500 disabled:opacity-50"
            >
              {savingToken ? 'Checking…' : 'Save & check'}
            </button>
          </div>
        </div>
      )}

      {/* Changelog */}
      {status?.update_available && status.changelog && (
        <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-6">
          <h3 className="text-sm font-semibold text-emerald-400 mb-2">{t('updates_page.whats_new')} v{status.remote_version}</h3>
          <p className="text-shogun-text text-sm">{status.changelog}</p>
          {status.released && (
            <p className="text-[11px] text-shogun-subdued mt-3">
              {t('updates_page.released')}: {new Date(status.released).toLocaleDateString()}
            </p>
          )}
        </div>
      )}

      {status?.update_available && Boolean(status.security_changes?.length) && (
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-6">
          <h3 className="text-sm font-semibold text-blue-300 mb-2">Security changes</h3>
          <ul className="list-disc ml-5 space-y-1 text-sm text-shogun-text">
            {status.security_changes?.map(item => <li key={item}>{item}</li>)}
          </ul>
        </div>
      )}

      {status?.update_available && Boolean(status.breaking_changes?.length) && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-6">
          <h3 className="text-sm font-semibold text-amber-300 mb-2">Known breaking changes</h3>
          <ul className="list-disc ml-5 space-y-1 text-sm text-shogun-text">
            {status.breaking_changes?.map(item => <li key={item}>{item}</li>)}
          </ul>
        </div>
      )}

      {/* Install result */}
      {installResult && (
        <div className={`rounded-xl p-4 border text-sm ${
          installResult.startsWith('✅') || installResult.startsWith('Update access') || installResult.startsWith('Shogun is restarting')
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' 
            : 'bg-red-500/10 border-red-500/30 text-red-300'
        }`}>
          {installResult}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={() => checkForUpdates(true)}
          disabled={checking}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-shogun-card border border-shogun-border text-shogun-text hover:border-shogun-blue transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${checking ? 'animate-spin' : ''}`} />
          {checking ? t('updates_page.checking') : t('updates_page.check_for_updates')}
        </button>

        {status?.update_available && (
          <button
            onClick={installUpdate}
            disabled={installing}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-emerald-600 text-white font-semibold hover:bg-emerald-500 transition-colors disabled:opacity-50"
          >
            <Download className={`w-4 h-4 ${installing ? 'animate-bounce' : ''}`} />
            {installing ? t('updates_page.installing') : t('updates_page.install_update')}
          </button>
        )}

        <button
          onClick={restartShogun}
          disabled={restarting || installing}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-amber-600 text-white font-semibold hover:bg-amber-500 transition-colors disabled:opacity-50"
        >
          <Power className={`w-4 h-4 ${restarting ? 'animate-pulse' : ''}`} />
          {restarting ? 'Restarting Shogun…' : 'Restart Shogun'}
        </button>
      </div>

      {/* Info */}
      <div className="text-[11px] text-shogun-subdued border-t border-shogun-border/30 pt-4 space-y-1">
        <p>{t('updates_page.info_auto_check')}</p>
        <p>{t('updates_page.info_preserve')}</p>
        <p>{t('updates_page.info_restart')}</p>
      </div>
    </div>
  );
};
