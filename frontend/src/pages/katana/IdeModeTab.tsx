import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, CheckCircle2, Code2, Copy, FolderGit2, Power, RefreshCw, Shield, Unplug, Wifi } from 'lucide-react';
import { cn } from '../../lib/utils';

const warning = `IDE Mode gives Shogun access to an approved development workspace. In Campaign posture, Shogun may inspect and edit code, run approved tasks, read diagnostics, and use Git status/diff. In Ronin posture, broader terminal and Git operations may be configured. Enable only for trusted repositories and tasks.`;

export const IdeModeTab = () => {
  const [status, setStatus] = useState<any>(null);
  const [workspaces, setWorkspaces] = useState<any[]>([]);
  const [pairing, setPairing] = useState<any>(null);
  const [routingProfile, setRoutingProfile] = useState('Balanced');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const load = useCallback(async () => {
    const [s, w, routing] = await Promise.all([
      axios.get('/api/v1/ide/status'),
      axios.get('/api/v1/ide/workspaces').catch(() => ({ data: { data: [] } })),
      axios.get('/api/v1/models/routing/profiles/active').catch(() => ({ data: { data: null } })),
    ]);
    setStatus(s.data.data); setWorkspaces(w.data.data || []);
    setRoutingProfile(routing.data.data?.name || 'Balanced');
  }, []);
  useEffect(() => { load().catch(() => setMessage('Unable to load IDE Mode status.')); }, [load]);

  const perform = async (fn: () => Promise<any>, ok: string) => {
    setBusy(true); setMessage('');
    try { await fn(); setMessage(ok); await load(); } catch (e: any) { setMessage(e?.response?.data?.detail || 'The IDE operation failed.'); }
    finally { setBusy(false); }
  };
  if (!status) return <div className="shogun-card flex items-center gap-3 text-shogun-subdued"><RefreshCw className="w-4 h-4 animate-spin" /> Loading IDE Mode…</div>;

  return <div className="space-y-5 animate-in fade-in duration-300">
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
      <section className="shogun-card xl:col-span-2 space-y-5">
        <div className="flex items-start justify-between gap-5">
          <div><div className="flex items-center gap-2"><Code2 className="w-5 h-5 text-purple-400"/><h3 className="font-bold text-shogun-text">Shogun IDE Mode</h3></div><p className="text-xs text-shogun-subdued mt-1">Governed autonomous development through the VS Code Adapter.</p></div>
          <span className={cn('px-2.5 py-1 rounded border text-[9px] font-bold uppercase', status.enabled ? 'text-green-400 border-green-500/30 bg-green-500/10' : 'text-shogun-subdued border-shogun-border')}>{status.enabled ? 'Enabled' : 'Disabled'}</span>
        </div>
        {!status.available && <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-200"><b>Posture locked.</b> IDE Mode is only available in Campaign and Ronin. Current posture: {String(status.posture).toUpperCase()}.</div>}
        {status.available && !status.enabled && <div className="rounded-lg border border-amber-500/25 bg-amber-500/5 p-4 flex gap-3"><AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5"/><p className="text-xs leading-relaxed text-amber-100/80">{warning}</p></div>}
        <div className="flex flex-wrap gap-3">
          {!status.enabled ? <button disabled={!status.available || busy} onClick={() => { if (window.confirm(warning)) perform(() => axios.post('/api/v1/ide/enable', { confirmed: true, remember_workspace: false }), 'IDE Mode enabled for this session.'); }} className="px-4 py-2 rounded-lg bg-purple-600 text-white text-xs font-bold disabled:opacity-30 flex items-center gap-2"><Power className="w-4 h-4"/> Enable IDE Mode</button>
          : <button disabled={busy} onClick={() => perform(() => axios.post('/api/v1/ide/disable'), 'IDE Mode disabled and all bridge sessions revoked.')} className="px-4 py-2 rounded-lg border border-red-500/35 bg-red-500/10 text-red-300 text-xs font-bold flex items-center gap-2"><Unplug className="w-4 h-4"/> Disable</button>}
          <button onClick={() => load()} className="px-3 py-2 rounded-lg border border-shogun-border text-shogun-subdued text-xs flex items-center gap-2"><RefreshCw className="w-3.5 h-3.5"/> Refresh</button>
        </div>
      </section>
      <section className="shogun-card space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-widest text-shogun-text">Runtime Status</h3>
        {[['Posture', status.posture], ['Routing profile', routingProfile], ['Provider', 'VS Code Adapter'], ['Connections', status.connected_instances], ['Approved workspaces', status.approved_workspaces]].map(([k,v]) => <div key={String(k)} className="flex justify-between text-xs border-b border-shogun-border/40 pb-2"><span className="text-shogun-subdued">{k}</span><b className="text-shogun-text">{String(v)}</b></div>)}
        <button disabled={!status.enabled || busy} onClick={() => perform(() => axios.post('/api/v1/ide/kill-switch'), 'IDE kill switch activated.')} className="w-full mt-2 px-3 py-2 rounded border border-red-500/30 text-red-300 text-[10px] font-bold uppercase disabled:opacity-30">Stop all IDE work</button>
      </section>
    </div>
    {status.enabled && <section className="shogun-card space-y-4">
      <div className="flex items-center justify-between"><div><h3 className="font-bold text-sm text-shogun-text">VS Code Pairing</h3><p className="text-xs text-shogun-subdued">Create a one-time, ten-minute localhost token for Shogun IDE Bridge.</p></div><Wifi className={cn('w-5 h-5', status.connected_instances ? 'text-green-400' : 'text-shogun-subdued')}/></div>
      {!pairing ? <button disabled={busy} onClick={() => perform(async () => { const r=await axios.post('/api/v1/ide/pairing/create'); setPairing(r.data.data); }, 'Pairing token created.')} className="px-4 py-2 bg-shogun-blue/20 border border-shogun-blue/30 rounded-lg text-xs font-bold text-shogun-blue">Create pairing token</button>
      : <div className="rounded-lg bg-[#050508] border border-shogun-border p-4 space-y-2"><div className="flex items-center gap-2"><code className="text-purple-300 text-sm break-all flex-1">{pairing.token}</code><button onClick={() => navigator.clipboard.writeText(pairing.token)} title="Copy token"><Copy className="w-4 h-4 text-shogun-subdued"/></button></div><p className="text-[10px] text-shogun-subdued">Bridge: {pairing.bridge_url} · expires {new Date(pairing.expires_at).toLocaleTimeString()}</p></div>}
    </section>}
    {status.enabled && <section className="shogun-card space-y-4">
      <div className="flex items-center gap-2"><FolderGit2 className="w-4 h-4 text-shogun-gold"/><h3 className="font-bold text-sm">Registered Workspaces</h3></div>
      {workspaces.length === 0 ? <p className="text-xs text-shogun-subdued italic">No VS Code workspace registered yet. Pair the Shogun IDE Bridge, then open a folder in VS Code.</p> : workspaces.map(ws => <div key={ws.id} className="rounded-lg border border-shogun-border bg-[#050508] p-4 flex items-center justify-between gap-4"><div className="min-w-0"><div className="flex items-center gap-2"><b className="text-sm text-shogun-text">{ws.name}</b>{ws.approved && <CheckCircle2 className="w-3.5 h-3.5 text-green-400"/>}</div><p className="text-[10px] text-shogun-subdued truncate">{ws.root_path}</p></div><button onClick={() => perform(() => axios.post(`/api/v1/ide/workspaces/${ws.id}/${ws.approved ? 'revoke' : 'approve'}`), ws.approved ? 'Workspace access revoked.' : 'Workspace approved.')} className={cn('px-3 py-1.5 rounded border text-[10px] font-bold uppercase', ws.approved ? 'border-red-500/30 text-red-300' : 'border-green-500/30 text-green-300')}>{ws.approved ? 'Revoke' : 'Approve'}</button></div>)}
    </section>}
    <section className="shogun-card"><div className="flex gap-3"><Shield className="w-4 h-4 text-purple-400 shrink-0"/><div><h4 className="text-xs font-bold">Enforced safeguards</h4><p className="text-[11px] text-shogun-subdued mt-1 leading-relaxed">Workspace approval, traversal and symlink protection, protected-secret rules, Campaign command allowlists, snapshots before writes, Git push disabled by default, central audit events, self-verification hooks, and an immediate kill switch.</p></div></div></section>
    {message && <div className="fixed bottom-6 right-6 z-50 rounded-lg border border-shogun-border bg-[#0a0e1a] px-4 py-3 text-xs shadow-2xl">{message}</div>}
  </div>;
};
