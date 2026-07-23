import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Clock3,
  FlaskConical,
  Loader2,
  LockKeyhole,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  WifiOff,
} from 'lucide-react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { cn } from '../lib/utils';

type GateAction = 'allow' | 'confirm' | 'block';

interface ToolRecord {
  name: string;
  category: string;
  risk: string;
  default_action: GateAction;
  local_override: GateAction | null;
  campaign_override: GateAction | null;
  gensui_override: GateAction | null;
  effective_action: GateAction;
  reason: string;
}

interface ToolGateData {
  authority: {
    mode: 'standalone' | 'gensui';
    editable: boolean;
    enrolled: boolean;
    connected: boolean;
    server_url: string;
    last_sync_at: string | null;
    effective_posture: Record<string, unknown> | null;
  };
  active_tier: string;
  active_campaign_preset: string | null;
  mode: string;
  local_overrides: Record<string, GateAction>;
  tools: ToolRecord[];
  pending_confirmations: Array<{
    confirm_id: string;
    tool_name: string;
    risk_level: string;
    reason: string;
  }>;
}

const ACTION_STYLES: Record<GateAction, string> = {
  allow: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
  confirm: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
  block: 'border-red-500/30 bg-red-500/10 text-red-300',
};

const RISK_STYLES: Record<string, string> = {
  low: 'text-emerald-400',
  medium: 'text-cyan-400',
  high: 'text-amber-400',
  critical: 'text-red-400',
};

function ActionBadge({ action }: { action: GateAction }) {
  return (
    <span className={cn('inline-flex min-w-20 justify-center rounded-md border px-2 py-1 text-[10px] font-bold uppercase tracking-widest', ACTION_STYLES[action])}>
      {action}
    </span>
  );
}

function formatSync(value: string | null) {
  if (!value) return 'No policy sync recorded';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function ToolGate() {
  const navigate = useNavigate();
  const [data, setData] = useState<ToolGateData | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingTool, setSavingTool] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [actionFilter, setActionFilter] = useState('all');
  const [simulationTool, setSimulationTool] = useState('');
  const [simulationArgs, setSimulationArgs] = useState('{}');
  const [simulating, setSimulating] = useState(false);
  const [simulation, setSimulation] = useState<{
    action: GateAction;
    risk_level: string;
    reason: string;
    parameter_flags: string[];
  } | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/v1/security/toolgate');
      const payload = response.data.data as ToolGateData;
      setData(payload);
      setSimulationTool(current => current || payload.tools[0]?.name || '');
    } catch {
      setMessage({ type: 'error', text: 'ToolGate status could not be loaded.' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const categories = useMemo(
    () => Array.from(new Set(data?.tools.map(tool => tool.category) || [])).sort(),
    [data],
  );

  const filteredTools = useMemo(() => {
    const query = search.trim().toLowerCase();
    return (data?.tools || []).filter(tool => (
      (!query || tool.name.toLowerCase().includes(query) || tool.category.toLowerCase().includes(query))
      && (category === 'all' || tool.category === category)
      && (actionFilter === 'all' || tool.effective_action === actionFilter)
    ));
  }, [data, search, category, actionFilter]);

  const counts = useMemo(() => ({
    allow: data?.tools.filter(tool => tool.effective_action === 'allow').length || 0,
    confirm: data?.tools.filter(tool => tool.effective_action === 'confirm').length || 0,
    block: data?.tools.filter(tool => tool.effective_action === 'block').length || 0,
  }), [data]);

  const changeOverride = async (toolName: string, value: string) => {
    if (!data?.authority.editable) return;
    setSavingTool(toolName);
    setMessage(null);
    const next = { ...data.local_overrides };
    if (value === 'default') delete next[toolName];
    else next[toolName] = value as GateAction;
    try {
      await axios.put('/api/v1/security/toolgate/overrides', { overrides: next });
      setMessage({ type: 'success', text: `ToolGate rule updated for ${toolName}.` });
      await fetchData();
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'ToolGate rule could not be saved.' });
    } finally {
      setSavingTool(null);
    }
  };

  const runSimulation = async () => {
    setSimulating(true);
    setSimulation(null);
    setMessage(null);
    try {
      const args = JSON.parse(simulationArgs);
      if (!args || Array.isArray(args) || typeof args !== 'object') throw new Error('Arguments must be a JSON object.');
      const response = await axios.post('/api/v1/security/toolgate/simulate', {
        tool_name: simulationTool,
        args,
      });
      setSimulation(response.data.data);
    } catch (error: any) {
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || error.message || 'Simulation failed.',
      });
    } finally {
      setSimulating(false);
    }
  };

  if (loading && !data) {
    return <div className="flex h-64 items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-shogun-gold" /></div>;
  }

  if (!data) return null;
  const managed = data.authority.mode === 'gensui';

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-14 animate-in fade-in duration-500">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="shogun-title text-3xl font-bold">ToolGate</h1>
            <span className="rounded border border-shogun-border bg-shogun-card px-2 py-1 text-[9px] uppercase tracking-[0.22em] text-shogun-subdued">
              Runtime permissions
            </span>
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-shogun-subdued">
            The enforcement layer between model intent and tool execution. Inspect the effective verdict, require human approval, or block individual capabilities.
          </p>
        </div>
        <button onClick={fetchData} className="self-start rounded-lg border border-shogun-border bg-shogun-card p-2.5 text-shogun-subdued transition-colors hover:text-shogun-gold" title="Refresh ToolGate">
          <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
        </button>
      </div>

      <div className={cn(
        'rounded-xl border p-4',
        managed
          ? data.authority.connected ? 'border-indigo-400/25 bg-indigo-500/[0.07]' : 'border-amber-400/30 bg-amber-500/[0.07]'
          : 'border-emerald-400/25 bg-emerald-500/[0.06]',
      )}>
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div className="flex gap-3">
            {managed
              ? data.authority.connected ? <ShieldCheck className="mt-0.5 h-5 w-5 text-indigo-300" /> : <WifiOff className="mt-0.5 h-5 w-5 text-amber-300" />
              : <SlidersHorizontal className="mt-0.5 h-5 w-5 text-emerald-300" />}
            <div>
              <p className="text-sm font-bold text-shogun-text">
                {managed
                  ? data.authority.connected ? 'Managed by Gensui' : 'Managed by Gensui — connection offline'
                  : 'Standalone authority'}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-shogun-subdued">
                {managed
                  ? `This view is read-only. The last known central policy remains enforced. ${formatSync(data.authority.last_sync_at)}.`
                  : 'Local ToolGate overrides are editable in Tenshu. Torii and parameter-aware checks may still tighten the result.'}
              </p>
            </div>
          </div>
          {managed && (
            <button onClick={() => navigate('/gensui')} className="flex items-center gap-2 self-start rounded-lg border border-indigo-400/25 bg-indigo-500/10 px-3 py-2 text-xs font-bold text-indigo-200 hover:bg-indigo-500/20">
              View Gensui connection <ChevronRight className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {message && (
        <div className={cn(
          'flex items-center gap-2 rounded-lg border px-4 py-3 text-sm',
          message.type === 'success' ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-200' : 'border-red-500/25 bg-red-500/10 text-red-200',
        )}>
          {message.type === 'success' ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {[
          { label: 'Active tier', value: data.active_tier.toUpperCase(), color: 'text-shogun-gold' },
          { label: 'Allow', value: counts.allow, color: 'text-emerald-400' },
          { label: 'Confirm', value: counts.confirm, color: 'text-amber-400' },
          { label: 'Block', value: counts.block, color: 'text-red-400' },
          { label: 'Pending approval', value: data.pending_confirmations.length, color: 'text-indigo-300' },
        ].map(card => (
          <div key={card.label} className="shogun-card">
            <p className="text-[9px] font-bold uppercase tracking-widest text-shogun-subdued">{card.label}</p>
            <p className={cn('mt-2 text-2xl font-bold', card.color)}>{card.value}</p>
          </div>
        ))}
      </div>

      <div className="shogun-card space-y-4">
        <div className="flex flex-col justify-between gap-3 lg:flex-row lg:items-center">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-widest text-shogun-text">Effective tool policy</h2>
            <p className="mt-1 text-xs text-shogun-subdued">Default thresholds plus local, Campaign, Gensui, and parameter-aware restrictions.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <label className="relative">
              <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-shogun-subdued" />
              <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search tools…" className="w-52 rounded-lg border border-shogun-border bg-shogun-bg py-2 pl-9 pr-3 text-xs text-shogun-text outline-none focus:border-shogun-blue" />
            </label>
            <select value={category} onChange={event => setCategory(event.target.value)} className="rounded-lg border border-shogun-border bg-shogun-bg px-3 py-2 text-xs text-shogun-text">
              <option value="all">All categories</option>
              {categories.map(item => <option key={item} value={item}>{item}</option>)}
            </select>
            <select value={actionFilter} onChange={event => setActionFilter(event.target.value)} className="rounded-lg border border-shogun-border bg-shogun-bg px-3 py-2 text-xs text-shogun-text">
              <option value="all">All verdicts</option>
              <option value="allow">Allow</option>
              <option value="confirm">Confirm</option>
              <option value="block">Block</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto rounded-lg border border-shogun-border/70">
          <table className="w-full min-w-[920px] text-left">
            <thead className="bg-[#080b12] text-[9px] uppercase tracking-widest text-shogun-subdued">
              <tr>
                <th className="px-4 py-3">Tool</th>
                <th className="px-4 py-3">Risk</th>
                <th className="px-4 py-3">Effective</th>
                <th className="px-4 py-3">Policy layers</th>
                <th className="px-4 py-3">Standalone override</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-shogun-border/60">
              {filteredTools.map(tool => (
                <tr key={tool.name} className="bg-shogun-card/20 hover:bg-shogun-card/50">
                  <td className="px-4 py-3">
                    <p className="font-mono text-xs font-semibold text-shogun-text">{tool.name}</p>
                    <p className="mt-1 text-[9px] uppercase tracking-widest text-shogun-subdued">{tool.category}</p>
                  </td>
                  <td className={cn('px-4 py-3 text-[10px] font-bold uppercase tracking-wider', RISK_STYLES[tool.risk])}>{tool.risk}</td>
                  <td className="px-4 py-3"><ActionBadge action={tool.effective_action} /></td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1.5">
                      {tool.gensui_override && <span className="rounded bg-indigo-500/10 px-2 py-1 text-[9px] text-indigo-300">Gensui: {tool.gensui_override}</span>}
                      {tool.campaign_override && <span className="rounded bg-orange-500/10 px-2 py-1 text-[9px] text-orange-300">Campaign: {tool.campaign_override}</span>}
                      {tool.local_override && <span className="rounded bg-cyan-500/10 px-2 py-1 text-[9px] text-cyan-300">Local: {tool.local_override}</span>}
                      {!tool.gensui_override && !tool.campaign_override && !tool.local_override && <span className="text-[10px] text-shogun-subdued">Mode default: {tool.default_action}</span>}
                    </div>
                    <p className="mt-1.5 max-w-xl truncate text-[9px] text-shogun-subdued" title={tool.reason}>{tool.reason}</p>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <select
                        value={tool.local_override || 'default'}
                        disabled={!data.authority.editable || savingTool === tool.name}
                        onChange={event => changeOverride(tool.name, event.target.value)}
                        className="w-32 rounded-lg border border-shogun-border bg-shogun-bg px-2 py-2 text-xs text-shogun-text disabled:cursor-not-allowed disabled:opacity-45"
                      >
                        <option value="default">Use default</option>
                        <option value="allow">Allow</option>
                        <option value="confirm">Confirm</option>
                        <option value="block">Block</option>
                      </select>
                      {savingTool === tool.name && <Loader2 className="h-3.5 w-3.5 animate-spin text-shogun-gold" />}
                      {!data.authority.editable && <LockKeyhole className="h-3.5 w-3.5 text-indigo-300" />}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filteredTools.length === 0 && <p className="py-10 text-center text-sm text-shogun-subdued">No tools match the current filters.</p>}
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.25fr_0.75fr]">
        <div className="shogun-card space-y-4">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-shogun-blue" />
            <h2 className="text-sm font-bold uppercase tracking-widest text-shogun-text">Policy simulator</h2>
          </div>
          <p className="text-xs leading-relaxed text-shogun-subdued">Evaluate a proposed call—including dangerous parameters—without executing it.</p>
          <div className="grid gap-3 md:grid-cols-[240px_1fr]">
            <select value={simulationTool} onChange={event => setSimulationTool(event.target.value)} className="rounded-lg border border-shogun-border bg-shogun-bg px-3 py-2.5 font-mono text-xs text-shogun-text">
              {data.tools.map(tool => <option key={tool.name} value={tool.name}>{tool.name}</option>)}
            </select>
            <textarea value={simulationArgs} onChange={event => setSimulationArgs(event.target.value)} rows={4} spellCheck={false} className="rounded-lg border border-shogun-border bg-shogun-bg px-3 py-2.5 font-mono text-xs text-shogun-text outline-none focus:border-shogun-blue" placeholder='{"path":"C:/workspace/report.docx"}' />
          </div>
          <button onClick={runSimulation} disabled={simulating || !simulationTool} className="flex items-center gap-2 rounded-lg bg-shogun-blue px-4 py-2.5 text-xs font-bold text-white transition-opacity disabled:opacity-50">
            {simulating ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />} Evaluate call
          </button>
          {simulation && (
            <div className="rounded-lg border border-shogun-border bg-shogun-bg/60 p-4">
              <div className="flex items-center gap-3">
                <ActionBadge action={simulation.action} />
                <span className={cn('text-[10px] font-bold uppercase tracking-widest', RISK_STYLES[simulation.risk_level])}>{simulation.risk_level} risk</span>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-shogun-subdued">{simulation.reason}</p>
              {simulation.parameter_flags.length > 0 && <p className="mt-2 font-mono text-[10px] text-amber-300">{simulation.parameter_flags.join(' · ')}</p>}
            </div>
          )}
        </div>

        <div className="shogun-card space-y-4">
          <div className="flex items-center gap-2">
            <Clock3 className="h-4 w-4 text-amber-300" />
            <h2 className="text-sm font-bold uppercase tracking-widest text-shogun-text">Pending approvals</h2>
          </div>
          {data.pending_confirmations.length === 0 ? (
            <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-shogun-border py-10 text-center">
              <CheckCircle2 className="h-6 w-6 text-emerald-400" />
              <p className="text-xs text-shogun-subdued">No tool calls are waiting for approval.</p>
            </div>
          ) : data.pending_confirmations.map(item => (
            <div key={item.confirm_id} className="rounded-lg border border-amber-500/20 bg-amber-500/[0.05] p-3">
              <p className="font-mono text-xs font-bold text-shogun-text">{item.tool_name}</p>
              <p className="mt-1 text-[10px] text-shogun-subdued">{item.reason}</p>
            </div>
          ))}
          <button onClick={() => navigate('/chat')} className="flex items-center gap-2 text-xs font-bold text-shogun-blue hover:text-shogun-gold">
            Resolve approvals in Chat <ChevronRight className="h-3.5 w-3.5" />
          </button>
          <div className="flex gap-2 rounded-lg bg-shogun-bg/70 p-3">
            <CircleHelp className="mt-0.5 h-4 w-4 shrink-0 text-shogun-subdued" />
            <p className="text-[10px] leading-relaxed text-shogun-subdued">Confirmations auto-deny after 60 seconds. Every verdict and operator decision remains available in Logs.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
