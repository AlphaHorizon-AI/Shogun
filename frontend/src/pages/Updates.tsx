import { useState, useEffect } from 'react';
import { Download, RefreshCw, CheckCircle, AlertTriangle, ArrowUpCircle, Clock } from 'lucide-react';
import { useTranslation } from '../i18n';

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
}

export const Updates = () => {
  const { t } = useTranslation();
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const [checking, setChecking] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [installResult, setInstallResult] = useState<string | null>(null);

  const checkForUpdates = async (force = false) => {
    setChecking(true);
    try {
      const r = await fetch(`/api/v1/updates/check?force=${force}`);
      const data = await r.json();
      setStatus(data);
    } catch {
      setStatus(null);
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
        setInstallResult(`✅ Updated to v${data.new_version} (build ${data.new_build}). ${data.files_updated} files updated. Please restart Shogun.`);
        checkForUpdates(true);
      } else {
        setInstallResult(`❌ ${data.detail || 'Update failed'}`);
      }
    } catch (e: any) {
      setInstallResult(`❌ Update failed: ${e.message}`);
    }
    setInstalling(false);
  };

  useEffect(() => { checkForUpdates(); }, []);

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

      {/* Install result */}
      {installResult && (
        <div className={`rounded-xl p-4 border text-sm ${
          installResult.startsWith('✅') 
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
