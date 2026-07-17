import React, { useEffect, useState } from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useTranslation } from '../../i18n';

interface ShellProps {
  children: React.ReactNode;
}

export const Shell = ({ children }: ShellProps) => {
  const { t } = useTranslation();
  const [roninDesktopActive, setRoninDesktopActive] = useState(false);

  useEffect(() => {
    let mounted = true;
    const poll = () => fetch('/api/v1/ronin/desktop/status')
      .then(response => response.json())
      .then(payload => { if (mounted) setRoninDesktopActive(Boolean(payload?.data?.active && payload?.data?.ronin_visible_indicator)); })
      .catch(() => {});
    poll();
    const timer = window.setInterval(poll, 5000);
    return () => { mounted = false; window.clearInterval(timer); };
  }, []);

  const killRoninDesktop = async () => {
    if (!confirm('Stop Ronin Desktop Control immediately?')) return;
    await fetch('/api/v1/ronin/desktop/kill-switch', { method: 'POST' });
    setRoninDesktopActive(false);
  };
  return (
    <div className="flex flex-col h-screen w-screen bg-shogun-bg overflow-hidden text-shogun-text font-sans">
      <TopBar />
      {roninDesktopActive && (
        <div className="h-8 shrink-0 px-4 flex items-center justify-between border-b border-orange-500/40 bg-orange-500/10 text-orange-300">
          <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-orange-400 animate-pulse" /><span className="text-[9px] font-black tracking-[0.2em]">RONIN DESKTOP CONTROL ACTIVE</span></div>
          <button onClick={killRoninDesktop} className="rounded border border-red-500/40 bg-red-500/10 px-2 py-0.5 text-[8px] font-black text-red-400 hover:bg-red-500/20">KILL SWITCH</button>
        </div>
      )}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-6 relative scroll-smooth bg-shogun-card/30 flex flex-col">
          <div className="w-full max-w-[1600px] mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 flex-1">
            {children}
          </div>
          <footer className="mt-12 py-6 border-t border-shogun-border/30 text-center">
            <p className="text-[10px] text-shogun-subdued uppercase tracking-[0.2em] font-bold">
              {t('common.copyright', 'Created by Alpha Horizon · © 2026')}
            </p>
          </footer>
        </main>
      </div>
    </div>
  );
};
