import { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Filter,
  Loader2,
  LockKeyhole,
  RefreshCw,
  Search,
  ShieldCheck,
} from 'lucide-react';
import api from '../lib/api';
import { TOOL_NAMES } from '../lib/toolRegistry';

type GateAction = 'allow' | 'confirm' | 'block';

interface Posture {
  id: string;
  name: string;
  description: string | null;
  level: number;
  is_builtin: boolean;
  tool_overrides_json: Record<string, GateAction> | null;
}

const ACTION_STYLES: Record<GateAction, string> = {
  allow: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
  confirm: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
  block: 'border-red-500/30 bg-red-500/10 text-red-300',
};

export default function ToolGate() {
  const [postures, setPostures] = useState<Posture[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [search, setSearch] = useState('');
  const [verdict, setVerdict] = useState('all');
  const [loading, setLoading] = useState(true);
  const [savingTool, setSavingTool] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchPostures = async (preferredId?: string) => {
    setLoading(true);
    try {
      const response = await api.get('/postures');
      const items = response.data as Posture[];
      setPostures(items);
      setSelectedId(current => preferredId || current || items[0]?.id || '');
    } catch {
      setMessage({ type: 'error', text: 'Gensui postures could not be loaded.' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchPostures(); }, []);

  const selected = postures.find(posture => posture.id === selectedId) || null;
  const overrides = selected?.tool_overrides_json || {};
  const allTools = useMemo(
    () => Array.from(new Set([...TOOL_NAMES, ...Object.keys(overrides)])).sort(),
    [overrides],
  );
  const filteredTools = useMemo(() => {
    const query = search.trim().toLowerCase();
    return allTools.filter(tool => (
      (!query || tool.toLowerCase().includes(query))
      && (verdict === 'all' || overrides[tool] === verdict)
    ));
  }, [allTools, overrides, search, verdict]);

  const counts = useMemo(() => ({
    allow: Object.values(overrides).filter(value => value === 'allow').length,
    confirm: Object.values(overrides).filter(value => value === 'confirm').length,
    block: Object.values(overrides).filter(value => value === 'block').length,
  }), [overrides]);

  const updateOverride = async (tool: string, action: string) => {
    if (!selected) return;
    setSavingTool(tool);
    setMessage(null);
    const next = { ...overrides };
    if (action === 'inherit') delete next[tool];
    else next[tool] = action as GateAction;
    try {
      await api.patch(`/postures/${selected.id}`, { tool_overrides_json: next });
      setMessage({ type: 'success', text: `${selected.name}: ${tool} policy updated.` });
      await fetchPostures(selected.id);
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'ToolGate policy could not be saved.' });
    } finally {
      setSavingTool(null);
    }
  };

  if (loading && postures.length === 0) {
    return <div className="flex h-72 items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-cyan-400" /></div>;
  }

  return (
    <div className="max-w-7xl space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gensui-50">ToolGate</h1>
            <span className="rounded-full border border-cyan-500/25 bg-cyan-500/10 px-2.5 py-1 text-[9px] font-bold uppercase tracking-widest text-cyan-300">
              Central authority
            </span>
          </div>
          <p className="mt-1 max-w-3xl text-sm leading-relaxed text-gensui-400">
            Define the allow, confirm, and block ceiling distributed to every Shogun using a posture. Local policy may tighten these verdicts, but cannot weaken them.
          </p>
        </div>
        <button onClick={() => fetchPostures(selectedId)} className="rounded-lg border border-gensui-700/50 bg-gensui-800/50 p-2.5 text-gensui-400 hover:text-cyan-300" title="Refresh ToolGate">
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="flex gap-3 rounded-xl border border-cyan-500/20 bg-cyan-500/[0.05] p-4">
        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-cyan-300" />
        <div>
          <p className="text-sm font-bold text-gensui-100">Gensui owns managed ToolGate policy</p>
          <p className="mt-1 text-xs leading-relaxed text-gensui-400">
            Changes are stored on the selected security posture and delivered through normal policy sync. Enrolled instances remain read-only even during a temporary connection loss.
          </p>
        </div>
      </div>

      {message && (
        <div className={`flex items-center gap-2 rounded-xl border px-4 py-3 text-sm ${
          message.type === 'success'
            ? 'border-emerald-700/40 bg-emerald-900/20 text-emerald-300'
            : 'border-red-700/40 bg-red-900/20 text-red-300'
        }`}>
          {message.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
          {message.text}
        </div>
      )}

      <div className="glass-card p-5">
        <div className="grid gap-5 lg:grid-cols-[minmax(260px,0.8fr)_2fr]">
          <div>
            <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-gensui-500">Security posture</label>
            <select value={selectedId} onChange={event => setSelectedId(event.target.value)} className="gensui-input w-full">
              {postures.map(posture => <option key={posture.id} value={posture.id}>{posture.name} · L{posture.level}</option>)}
            </select>
            {selected && (
              <div className="mt-3 rounded-lg border border-gensui-700/40 bg-gensui-900/40 p-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs font-bold text-gensui-200">{selected.name}</span>
                  {selected.is_builtin && <span className="text-[9px] uppercase tracking-widest text-gensui-500">Built-in</span>}
                </div>
                <p className="mt-2 text-[11px] leading-relaxed text-gensui-500">{selected.description || 'No posture description.'}</p>
              </div>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {[
              { label: 'Explicit rules', value: Object.keys(overrides).length, color: 'text-cyan-300' },
              { label: 'Allow', value: counts.allow, color: 'text-emerald-400' },
              { label: 'Confirm', value: counts.confirm, color: 'text-amber-400' },
              { label: 'Block', value: counts.block, color: 'text-red-400' },
            ].map(item => (
              <div key={item.label} className="rounded-xl border border-gensui-700/40 bg-gensui-900/30 p-4">
                <p className="text-[9px] font-bold uppercase tracking-widest text-gensui-500">{item.label}</p>
                <p className={`mt-2 text-2xl font-bold ${item.color}`}>{item.value}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="glass-card p-5">
        <div className="mb-4 flex flex-col justify-between gap-3 md:flex-row md:items-center">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-widest text-gensui-100">Posture tool policy</h2>
            <p className="mt-1 text-xs text-gensui-500">“Inherit” leaves the decision to lower policy layers and the Shogun runtime threshold.</p>
          </div>
          <div className="flex gap-2">
            <label className="relative">
              <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gensui-500" />
              <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search tools…" className="gensui-input w-52 pl-9 text-xs" />
            </label>
            <label className="relative">
              <Filter className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gensui-500" />
              <select value={verdict} onChange={event => setVerdict(event.target.value)} className="gensui-input pl-9 text-xs">
                <option value="all">All verdicts</option>
                <option value="allow">Allow</option>
                <option value="confirm">Confirm</option>
                <option value="block">Block</option>
              </select>
            </label>
          </div>
        </div>

        <div className="overflow-hidden rounded-xl border border-gensui-700/40">
          <table className="w-full min-w-[640px] text-left">
            <thead className="bg-gensui-900/70 text-[9px] uppercase tracking-widest text-gensui-500">
              <tr>
                <th className="px-4 py-3">Tool</th>
                <th className="px-4 py-3">Central verdict</th>
                <th className="px-4 py-3">Runtime behavior</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gensui-700/30">
              {filteredTools.map(tool => {
                const action = overrides[tool];
                return (
                  <tr key={tool} className="bg-gensui-800/15 hover:bg-gensui-800/40">
                    <td className="px-4 py-3 font-mono text-xs font-semibold text-gensui-200">{tool}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <select
                          value={action || 'inherit'}
                          disabled={!selected || savingTool === tool}
                          onChange={event => updateOverride(tool, event.target.value)}
                          className={`w-32 rounded-lg border px-2 py-2 text-xs font-bold uppercase disabled:opacity-50 ${
                            action ? ACTION_STYLES[action] : 'border-gensui-700/50 bg-gensui-900/60 text-gensui-400'
                          }`}
                        >
                          <option value="inherit">Inherit</option>
                          <option value="allow">Allow</option>
                          <option value="confirm">Confirm</option>
                          <option value="block">Block</option>
                        </select>
                        {savingTool === tool && <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan-400" />}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-[11px] text-gensui-500">
                      {action === 'allow' && 'May execute unless a stricter local or parameter rule applies.'}
                      {action === 'confirm' && 'Requires human approval or a stricter local block.'}
                      {action === 'block' && 'Hard ceiling: the tool cannot be relaxed by the managed Shogun.'}
                      {!action && 'Resolved by lower policy layers and the mode × risk threshold.'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {filteredTools.length === 0 && <p className="py-12 text-center text-sm text-gensui-500">No tools match the current filter.</p>}
        </div>
      </div>

      <div className="flex gap-3 rounded-xl border border-gensui-700/40 bg-gensui-900/30 p-4">
        <LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-gensui-400" />
        <p className="text-[11px] leading-relaxed text-gensui-500">
          Policy order is monotonic: parameter safety and any explicit block remain authoritative. When multiple layers specify a verdict, ToolGate enforces the most restrictive result.
        </p>
      </div>
    </div>
  );
}
