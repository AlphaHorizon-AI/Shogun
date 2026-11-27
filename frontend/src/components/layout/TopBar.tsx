import { useState } from 'react';
import { Activity, Loader2, Power } from 'lucide-react';

export const TopBar = () => {
  const [shuttingDown, setShuttingDown] = useState(false);

  const shutdownServer = async () => {
    if (!confirm('Shut down Shogun AgentFlow now? Any active flow runs will be cancelled.')) return;
    setShuttingDown(true);
    try {
      const response = await fetch('/api/v1/system/shutdown', { method: 'POST' });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${response.status}`);
      }
      window.setTimeout(() => window.close(), 350);
    } catch (error: unknown) {
      setShuttingDown(false);
      alert(`Could not shut down: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  return (
    <header className="h-[64px] w-full bg-gradient-to-r from-[#050508] to-shogun-bg border-b border-shogun-border flex items-center justify-between px-6 shrink-0 shadow-lg relative z-10">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 bg-shogun-card rounded-lg flex items-center justify-center border border-shogun-border">
          <img src="/shogun-agentflow-desktop.png" alt="Shogun AgentFlow" className="w-7 h-7 object-contain" />
        </div>
        <div className="flex flex-col">
          <h1 className="text-shogun-gold text-base font-bold tracking-widest leading-none">SHOGUN AGENTFLOW</h1>
          <span className="text-shogun-subdued text-[10px] uppercase tracking-[0.2em] font-medium">
            Bare-Bones Workflow Runtime
          </span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 px-3 py-1.5 bg-[#050508] rounded-full border border-shogun-border">
          <Activity className="w-3.5 h-3.5 text-green-500 animate-pulse" />
          <span className="text-[11px] font-semibold text-shogun-text tracking-wide uppercase">READY</span>
        </div>

        <button
          type="button"
          onClick={shutdownServer}
          disabled={shuttingDown}
          className="flex items-center gap-2 rounded-lg border border-red-500/35 bg-red-500/10 px-3 py-1.5 text-[10px] font-black tracking-wider text-red-300 transition-colors hover:border-red-400/60 hover:bg-red-500/20 disabled:cursor-wait disabled:opacity-60"
          title="Shut down Shogun AgentFlow"
        >
          {shuttingDown ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Power className="h-3.5 w-3.5" />}
          <span>{shuttingDown ? 'STOPPING' : 'SHUT DOWN'}</span>
        </button>
      </div>
    </header>
  );
};
