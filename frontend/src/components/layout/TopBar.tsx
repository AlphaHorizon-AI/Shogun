import { useState } from 'react';
import { Activity, ShieldCheck, Database, Globe, Loader2, Power } from 'lucide-react';
import { useTranslation } from '../../i18n';

export const TopBar = () => {
  const { language, setLanguage, languages, t } = useTranslation();
  const [shuttingDown, setShuttingDown] = useState(false);

  const shutdownTenshu = async () => {
    if (!confirm('Safely shut down Tenshu now? Active operations will stop, managed processes will close, and the dedicated Shogun browser window will exit.')) return;
    setShuttingDown(true);
    try {
      const response = await fetch('/api/v1/updates/shutdown', { method: 'POST' });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      window.setTimeout(() => window.close(), 350);
    } catch (error: unknown) {
      setShuttingDown(false);
      alert(`Tenshu could not shut down: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  return (
    <header className="h-[68px] w-full bg-gradient-to-r from-[#050508] to-shogun-bg border-b border-shogun-border flex items-center justify-between px-6 shrink-0 shadow-lg relative z-10">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-shogun-card rounded-lg flex items-center justify-center border border-shogun-border group hover:border-shogun-gold transition-colors duration-300">
           <img src="/shogun-logo.png" alt="Shogun" className="w-8 h-8 object-contain drop-shadow-[0_0_8px_rgba(212,160,23,0.3)] transition-transform group-hover:scale-110" />
        </div>
        <div className="flex flex-col">
          <h1 className="text-shogun-gold text-lg font-bold tracking-widest leading-none">SHOGUN</h1>
          <span className="text-shogun-subdued text-[10px] uppercase tracking-[0.2em] font-medium">{t('dashboard.title', 'The Tenshu — Control Terminal')}</span>
        </div>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2 px-3 py-1.5 bg-[#050508] rounded-full border border-shogun-border transition-all hover:border-shogun-blue">
          <Activity className="w-3.5 h-3.5 text-green-500 animate-pulse" />
          <span className="text-[11px] font-semibold text-shogun-text tracking-wide truncate max-w-[100px] uppercase">{t('topbar.system_ready', 'SYSTEM READY')}</span>
        </div>

        <div className="flex items-center gap-2 bg-[#0a0e1a] border border-[#1a1f2e] rounded-lg px-2 py-1">
          <Globe className="w-4 h-4 text-shogun-subdued" />
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="bg-transparent text-xs text-shogun-text font-medium outline-none appearance-none cursor-pointer hover:text-white"
          >
            {languages.map((lang) => (
              <option key={lang.code} value={lang.code} className="bg-[#0a0e1a]">
                {lang.flag} {lang.name}
              </option>
            ))}
          </select>
        </div>
        
        <div className="flex items-center gap-4 text-shogun-subdued">
          <div className="flex items-center gap-1.5 group cursor-default">
            <Database className="w-4 h-4 group-hover:text-shogun-blue transition-colors" />
            <span className="text-xs">{t('topbar.healthy', 'Healthy')}</span>
          </div>
          <div className="flex items-center gap-1.5 group cursor-default">
            <ShieldCheck className="w-4 h-4 group-hover:text-shogun-blue transition-colors" />
            <span className="text-xs">{t('topbar.guarded', 'Guarded')}</span>
          </div>
        </div>

        <button
          type="button"
          onClick={shutdownTenshu}
          disabled={shuttingDown}
          className="flex items-center gap-2 rounded-lg border border-red-500/35 bg-red-500/10 px-3 py-2 text-[10px] font-black tracking-wider text-red-300 transition-colors hover:border-red-400/60 hover:bg-red-500/20 disabled:cursor-wait disabled:opacity-60"
          title="Safely shut down Tenshu"
        >
          {shuttingDown ? <Loader2 className="h-4 w-4 animate-spin" /> : <Power className="h-4 w-4" />}
          <span className="hidden xl:inline">{shuttingDown ? 'SHUTTING DOWN' : 'SHUT DOWN'}</span>
        </button>
      </div>
    </header>
  );
};
