import { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Filter,
  Loader2,
  LockKeyhole,
  Plus,
  RefreshCw,
  Save,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
} from 'lucide-react';
import api from '../lib/api';
import { TOOL_NAMES } from '../lib/toolRegistry';

type GateAction = 'allow' | 'confirm' | 'block';
type AdvancedAction = 'confirm' | 'block';
type AdvancedMatchType = 'contains' | 'word';

interface AdvancedRule {
  id: string;
  label: string;
  pattern: string;
  match_type: AdvancedMatchType;
  action: AdvancedAction;
  tools: string[];
  case_sensitive: boolean;
  enabled: boolean;
}

interface AdvancedControls {
  enabled: boolean;
  rules: AdvancedRule[];
}

interface Posture {
  id: string;
  name: string;
  description: string | null;
  level: number;
  is_builtin: boolean;
  tool_overrides_json: Record<string, GateAction> | null;
  advanced_toolgate_json: AdvancedControls | null;
  [key: string]: any;
}

const ACTION_STYLES: Record<GateAction, string> = {
  allow: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
  confirm: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
  block: 'border-red-500/30 bg-red-500/10 text-red-300',
};

const CAPABILITY_KEYS = [
  { key: 'allow_external_models', label: 'External Models' },
  { key: 'allow_local_models', label: 'Local Models' },
  { key: 'allow_tool_execution', label: 'Tool Execution' },
  { key: 'allow_mado', label: 'Mado Browser' },
  { key: 'allow_memory_write', label: 'Memory Write' },
  { key: 'allow_memory_read', label: 'Memory Read' },
  { key: 'allow_agent_flow', label: 'Agent Flow' },
  { key: 'allow_nexus', label: 'Nexus' },
  { key: 'allow_samurai_delegation', label: 'Samurai Delegation' },
  { key: 'allow_scheduled_triggers', label: 'Scheduled Triggers' },
  { key: 'allow_autonomous_loops', label: 'Autonomous Loops' },
  { key: 'allow_external_web', label: 'External Web' },
  { key: 'allow_file_write', label: 'File Write' },
  { key: 'allow_external_api', label: 'External API' },
];

export default function ToolGate() {
  const [postures, setPostures] = useState<Posture[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [search, setSearch] = useState('');
  const [verdict, setVerdict] = useState('all');
  const [loading, setLoading] = useState(true);
  const [savingTool, setSavingTool] = useState<string | null>(null);
  const [savingCapability, setSavingCapability] = useState<string | null>(null);
  const [savingAdvanced, setSavingAdvanced] = useState(false);
  const [advancedDraft, setAdvancedDraft] = useState<AdvancedControls>({ enabled: false, rules: [] });
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
  const enabledCapabilities = selected
    ? CAPABILITY_KEYS.filter(item => selected[item.key] !== false).length
    : 0;
  const capabilityRisk = Math.round((enabledCapabilities / CAPABILITY_KEYS.length) * 100);

  useEffect(() => {
    setAdvancedDraft(selected?.advanced_toolgate_json || { enabled: false, rules: [] });
  }, [selectedId, selected?.advanced_toolgate_json]);

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

  const updateCapability = async (key: string, enabled: boolean) => {
    if (!selected) return;
    setSavingCapability(key);
    setMessage(null);
    try {
      await api.patch(`/postures/${selected.id}`, { [key]: enabled });
      setMessage({ type: 'success', text: `${selected.name}: capability boundary updated.` });
      await fetchPostures(selected.id);
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Capability boundary could not be saved.' });
    } finally {
      setSavingCapability(null);
    }
  };

  const updateAdvancedRule = (id: string, patch: Partial<AdvancedRule>) => {
    setAdvancedDraft(current => ({
      ...current,
      rules: current.rules.map(rule => rule.id === id ? { ...rule, ...patch } : rule),
    }));
  };

  const addAdvancedRule = () => {
    setAdvancedDraft(current => ({
      ...current,
      enabled: true,
      rules: [
        ...current.rules,
        {
          id: `rule-${Date.now()}`,
          label: '',
          pattern: '',
          match_type: 'contains',
          action: 'confirm',
          tools: [],
          case_sensitive: false,
          enabled: true,
        },
      ],
    }));
  };

  const saveAdvancedControls = async () => {
    if (!selected) return;
    setSavingAdvanced(true);
    setMessage(null);
    try {
      await api.patch(`/postures/${selected.id}`, { advanced_toolgate_json: advancedDraft });
      setMessage({ type: 'success', text: `${selected.name}: advanced controls updated.` });
      await fetchPostures(selected.id);
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Advanced controls could not be saved.' });
    } finally {
      setSavingAdvanced(false);
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
        <div className="mb-5 flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <div className="flex items-center gap-2">
              <SlidersHorizontal className="h-4 w-4 text-orange-400" />
              <h2 className="text-sm font-bold uppercase tracking-widest text-gensui-100">Advanced controls</h2>
              <span className="rounded border border-orange-500/25 bg-orange-500/10 px-2 py-1 text-[9px] font-bold uppercase tracking-widest text-orange-300">
                Fleet content rules
              </span>
            </div>
            <p className="mt-1 max-w-3xl text-xs leading-relaxed text-gensui-500">
              Flag words or phrases in tool arguments across every Shogun assigned this posture. Matching calls can require confirmation or be blocked outright.
            </p>
          </div>
          <button
            type="button"
            disabled={!selected}
            onClick={() => setAdvancedDraft(current => ({ ...current, enabled: !current.enabled }))}
            className={`flex items-center gap-3 rounded-lg border px-3 py-2 text-xs font-bold disabled:opacity-50 ${
              advancedDraft.enabled
                ? 'border-orange-500/35 bg-orange-500/10 text-orange-200'
                : 'border-gensui-700/50 bg-gensui-900/50 text-gensui-400'
            }`}
          >
            <span className={`relative h-5 w-10 rounded-full border ${
              advancedDraft.enabled ? 'border-orange-400/40 bg-orange-500/20' : 'border-gensui-700 bg-gensui-950'
            }`}>
              <span className={`absolute top-0.5 h-4 w-4 rounded-full transition-all ${
                advancedDraft.enabled ? 'left-5 bg-orange-300' : 'left-0.5 bg-gensui-500'
              }`} />
            </span>
            Advanced mode {advancedDraft.enabled ? 'on' : 'off'}
          </button>
        </div>

        <div className="space-y-3">
          {advancedDraft.rules.map((rule, index) => (
            <div key={rule.id} className="rounded-xl border border-gensui-700/40 bg-gensui-900/30 p-4">
              <div className="grid gap-3 xl:grid-cols-[minmax(150px,0.8fr)_minmax(220px,1.4fr)_130px_130px_minmax(180px,1fr)_auto] xl:items-end">
                <label className="space-y-1">
                  <span className="text-[9px] font-bold uppercase tracking-widest text-gensui-500">Rule label</span>
                  <input
                    value={rule.label}
                    onChange={event => updateAdvancedRule(rule.id, { label: event.target.value })}
                    placeholder={`Rule ${index + 1}`}
                    maxLength={120}
                    className="gensui-input w-full text-xs"
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-[9px] font-bold uppercase tracking-widest text-gensui-500">Word or phrase</span>
                  <input
                    value={rule.pattern}
                    onChange={event => updateAdvancedRule(rule.id, { pattern: event.target.value })}
                    placeholder="e.g. confidential"
                    maxLength={200}
                    className="gensui-input w-full font-mono text-xs"
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-[9px] font-bold uppercase tracking-widest text-gensui-500">Match</span>
                  <select
                    value={rule.match_type}
                    onChange={event => updateAdvancedRule(rule.id, { match_type: event.target.value as AdvancedMatchType })}
                    className="gensui-input w-full text-xs"
                  >
                    <option value="contains">Contains</option>
                    <option value="word">Whole word</option>
                  </select>
                </label>
                <label className="space-y-1">
                  <span className="text-[9px] font-bold uppercase tracking-widest text-gensui-500">Verdict</span>
                  <select
                    value={rule.action}
                    onChange={event => updateAdvancedRule(rule.id, { action: event.target.value as AdvancedAction })}
                    className={`w-full rounded-lg border px-2 py-2 text-xs font-bold uppercase ${ACTION_STYLES[rule.action]}`}
                  >
                    <option value="confirm">Confirm</option>
                    <option value="block">Block</option>
                  </select>
                </label>
                <label className="space-y-1">
                  <span className="text-[9px] font-bold uppercase tracking-widest text-gensui-500">Applies to</span>
                  <select
                    value={rule.tools[0] || '*'}
                    onChange={event => updateAdvancedRule(rule.id, { tools: event.target.value === '*' ? [] : [event.target.value] })}
                    className="gensui-input w-full font-mono text-xs"
                  >
                    <option value="*">All tools</option>
                    {allTools.map(tool => <option key={tool} value={tool}>{tool}</option>)}
                  </select>
                </label>
                <div className="flex items-center justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => updateAdvancedRule(rule.id, { enabled: !rule.enabled })}
                    className={`rounded border px-2.5 py-2 text-[9px] font-bold uppercase ${
                      rule.enabled ? 'border-emerald-500/25 text-emerald-300' : 'border-gensui-700 text-gensui-500'
                    }`}
                  >
                    {rule.enabled ? 'Active' : 'Paused'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setAdvancedDraft(current => ({
                      ...current,
                      rules: current.rules.filter(item => item.id !== rule.id),
                    }))}
                    className="rounded border border-red-500/20 p-2 text-red-300 hover:bg-red-500/10"
                    title="Remove rule"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
              <label className="mt-3 flex items-center gap-2 text-[10px] text-gensui-500">
                <input
                  type="checkbox"
                  checked={rule.case_sensitive}
                  onChange={event => updateAdvancedRule(rule.id, { case_sensitive: event.target.checked })}
                />
                Case-sensitive match
              </label>
            </div>
          ))}
          {advancedDraft.rules.length === 0 && (
            <div className="rounded-xl border border-dashed border-gensui-700/50 p-6 text-center text-xs text-gensui-500">
              No advanced content rules are defined for this posture.
            </div>
          )}
        </div>

        <div className="mt-4 flex flex-wrap justify-between gap-3">
          <button
            type="button"
            disabled={!selected}
            onClick={addAdvancedRule}
            className="flex items-center gap-2 rounded-lg border border-orange-500/25 px-3 py-2 text-xs font-bold text-orange-300 hover:bg-orange-500/10 disabled:opacity-50"
          >
            <Plus className="h-4 w-4" /> Add content rule
          </button>
          <button
            type="button"
            disabled={!selected || savingAdvanced || advancedDraft.rules.some(rule => !rule.pattern.trim())}
            onClick={saveAdvancedControls}
            className="flex items-center gap-2 rounded-lg bg-orange-400 px-4 py-2.5 text-xs font-bold text-gensui-950 disabled:opacity-50"
          >
            {savingAdvanced ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save advanced controls
          </button>
        </div>
      </div>

      <div className="glass-card p-5">
        <div className="mb-4 flex flex-col justify-between gap-4 md:flex-row md:items-start">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-widest text-gensui-100">Capability boundaries</h2>
            <p className="mt-1 max-w-3xl text-xs leading-relaxed text-gensui-500">
              The centrally distributed capability ceiling for the selected posture. Per-tool verdicts below can only narrow this surface.
            </p>
          </div>
          <div className="min-w-52 rounded-lg border border-gensui-700/40 bg-gensui-900/40 p-3">
            <div className="flex justify-between text-[9px] font-bold uppercase tracking-widest text-gensui-500">
              <span>Exposure index</span>
              <span className={capabilityRisk <= 35 ? 'text-emerald-400' : capabilityRisk <= 70 ? 'text-amber-400' : 'text-red-400'}>
                {capabilityRisk}/100
              </span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-gensui-950">
              <div
                className={`h-full rounded-full ${capabilityRisk <= 35 ? 'bg-emerald-400' : capabilityRisk <= 70 ? 'bg-amber-400' : 'bg-red-400'}`}
                style={{ width: `${capabilityRisk}%` }}
              />
            </div>
          </div>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {CAPABILITY_KEYS.map(item => {
            const enabled = selected?.[item.key] !== false;
            return (
              <button
                key={item.key}
                disabled={!selected || savingCapability === item.key}
                onClick={() => updateCapability(item.key, !enabled)}
                className={`flex items-center justify-between rounded-lg border p-3 text-left text-xs transition-colors disabled:opacity-50 ${
                  enabled
                    ? 'border-emerald-500/25 bg-emerald-500/[0.06] text-emerald-300'
                    : 'border-red-500/25 bg-red-500/[0.06] text-red-300'
                }`}
              >
                <span className="font-semibold">{item.label}</span>
                {savingCapability === item.key
                  ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  : <span className="text-[9px] font-bold uppercase">{enabled ? 'Allowed' : 'Blocked'}</span>}
              </button>
            );
          })}
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
