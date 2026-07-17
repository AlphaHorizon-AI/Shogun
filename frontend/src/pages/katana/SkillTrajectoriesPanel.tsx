import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  Activity, AlertTriangle, CheckCircle2, Download, FileSearch, Loader2,
  RefreshCw, Search, ShieldCheck, Sparkles, Wrench,
} from 'lucide-react';
import { cn } from '../../lib/utils';

type Trajectory = {
  id: string; skill_name: string; skill_version: string; run_id?: string;
  task_summary: string; model_id?: string; model_profile?: string; posture: string;
  status: string; final_outcome: string; contribution: string; score: number;
  created_at: string; finalized_at?: string;
};

type Improvement = {
  id: string; skill_name: string; issue_type: string; observed_problem: string;
  suggested_improvement: string; validation_idea: string; priority: string;
  status: string; based_on_trajectory_id?: string; created_at: string;
};

const unwrap = (value: any) => value?.data?.data ?? value?.data ?? value;
const scoreColor = (score: number) => score > .5 ? 'text-green-400' : score < 0 ? 'text-red-400' : 'text-amber-300';

export default function SkillTrajectoriesPanel() {
  const [trajectories, setTrajectories] = useState<Trajectory[]>([]);
  const [improvements, setImprovements] = useState<Improvement[]>([]);
  const [detail, setDetail] = useState<any>(null);
  const [query, setQuery] = useState('');
  const [outcome, setOutcome] = useState('');
  const [view, setView] = useState<'trajectories' | 'improvements'>('trajectories');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true); setError('');
    try {
      const [trajectoryResponse, improvementResponse] = await Promise.all([
        axios.get('/api/v1/skills/trajectories', { params: { limit: 200 } }),
        axios.get('/api/v1/skills/improvement-candidates', { params: { limit: 200 } }),
      ]);
      setTrajectories(unwrap(trajectoryResponse) || []);
      setImprovements(unwrap(improvementResponse) || []);
    } catch (reason: any) {
      setError(reason.response?.data?.detail || 'Could not load skill trajectories.');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => trajectories.filter(item => {
    const matchesOutcome = !outcome || item.final_outcome === outcome;
    const needle = query.trim().toLowerCase();
    return matchesOutcome && (!needle || [item.skill_name, item.task_summary, item.run_id, item.model_id]
      .some(value => String(value || '').toLowerCase().includes(needle)));
  }), [trajectories, query, outcome]);

  const finalized = trajectories.filter(item => item.finalized_at);
  const successes = finalized.filter(item => item.final_outcome === 'success').length;
  const average = finalized.length ? finalized.reduce((total, item) => total + item.score, 0) / finalized.length : 0;
  const skillPerformance = useMemo(() => {
    const grouped = new Map<string, Trajectory[]>();
    trajectories.forEach(item => grouped.set(item.skill_name, [...(grouped.get(item.skill_name) || []), item]));
    return Array.from(grouped.entries()).map(([name, items]) => ({
      name, uses: items.length,
      average: items.reduce((total, item) => total + item.score, 0) / items.length,
      success: items.filter(item => item.final_outcome === 'success').length,
      failed: items.filter(item => item.final_outcome === 'failure').length,
      blocked: items.filter(item => item.final_outcome === 'blocked').length,
      lastUsed: items.map(item => item.created_at).sort().slice(-1)[0],
    })).sort((a, b) => b.uses - a.uses);
  }, [trajectories]);

  const inspect = async (id: string) => {
    try { setDetail(unwrap(await axios.get(`/api/v1/skills/trajectories/${id}`))); }
    catch (reason: any) { setError(reason.response?.data?.detail || 'Could not load trajectory detail.'); }
  };

  const exportData = async (format: 'jsonl' | 'markdown' | 'zip') => {
    try {
      const response = await axios.post('/api/v1/skills/trajectories/export', {
        format, outcome: outcome || null, include_raw_prompts: false, include_full_tool_outputs: false,
      }, { responseType: 'blob' });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url; link.download = `skill-trajectories.${format === 'markdown' ? 'md' : format}`; link.click();
      URL.revokeObjectURL(url);
    } catch (reason: any) { setError(reason.response?.data?.detail || 'Trajectory export failed.'); }
  };

  return <div className="shogun-card border-purple-500/20 space-y-4">
    <div className="flex flex-col lg:flex-row lg:items-center gap-3">
      <div><p className="text-[9px] uppercase tracking-widest text-purple-300">Order 10 Evidence</p>
        <h3 className="text-lg font-bold">Skill Trajectories</h3>
        <p className="text-xs text-shogun-subdued">Redacted activation, tool, verification, outcome, and improvement evidence.</p></div>
      <div className="lg:ml-auto flex flex-wrap gap-2">
        <button onClick={() => setView('trajectories')} className={cn('px-3 py-2 rounded-lg border text-xs', view === 'trajectories' ? 'border-purple-400 text-purple-200 bg-purple-500/10' : 'border-shogun-border')}>Trajectories</button>
        <button onClick={() => setView('improvements')} className={cn('px-3 py-2 rounded-lg border text-xs', view === 'improvements' ? 'border-amber-400 text-amber-200 bg-amber-500/10' : 'border-shogun-border')}>Improvements ({improvements.length})</button>
        {(['jsonl', 'markdown', 'zip'] as const).map(format => <button key={format} onClick={() => exportData(format)} className="px-3 py-2 rounded-lg border border-shogun-border text-[10px] uppercase flex items-center gap-1"><Download className="w-3 h-3" />{format}</button>)}
        <button onClick={load} className="p-2 rounded-lg border border-shogun-border"><RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} /></button>
      </div>
    </div>

    {error && <div className="rounded-lg border border-red-500/30 bg-red-500/5 text-red-300 p-3 text-xs flex gap-2"><AlertTriangle className="w-4 h-4" />{error}</div>}

    <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
      {[
        ['Captured', trajectories.length, Activity], ['Finalized', finalized.length, CheckCircle2],
        ['Success rate', finalized.length ? `${Math.round(100 * successes / finalized.length)}%` : '—', ShieldCheck],
        ['Average score', finalized.length ? average.toFixed(2) : '—', Sparkles],
      ].map(([label, value, Icon]: any) => <div key={label} className="rounded-lg bg-[#050508] border border-shogun-border p-3"><div className="flex justify-between text-[9px] uppercase text-shogun-subdued"><span>{label}</span><Icon className="w-3.5 h-3.5 text-purple-400" /></div><b className="text-lg mt-1 block">{value}</b></div>)}
    </div>

    {skillPerformance.length > 0 && <details className="rounded-lg bg-[#050508] border border-shogun-border" open>
      <summary className="cursor-pointer px-4 py-3 text-xs font-bold uppercase tracking-wider">Skill Performance</summary>
      <div className="overflow-x-auto max-h-52"><table className="w-full text-xs"><thead className="text-[9px] uppercase text-shogun-subdued border-y border-shogun-border"><tr><th className="text-left px-4 py-2">Skill</th><th>Uses</th><th>Avg score</th><th>Success</th><th>Failed</th><th>Blocked</th><th className="text-right px-4">Last used</th></tr></thead><tbody>
        {skillPerformance.map(item => <tr key={item.name} className="border-b border-shogun-border/50"><td className="px-4 py-2 font-semibold">{item.name}</td><td className="text-center">{item.uses}</td><td className={cn('text-center font-mono', scoreColor(item.average))}>{item.average.toFixed(2)}</td><td className="text-center text-green-400">{item.success}</td><td className="text-center text-red-400">{item.failed}</td><td className="text-center text-amber-300">{item.blocked}</td><td className="text-right px-4 text-shogun-subdued">{item.lastUsed ? new Date(item.lastUsed).toLocaleString() : '—'}</td></tr>)}
      </tbody></table></div>
    </details>}

    {loading && !trajectories.length ? <div className="py-12 flex justify-center gap-2 text-sm text-shogun-subdued"><Loader2 className="w-4 h-4 animate-spin" />Loading evidence…</div> : view === 'improvements' ?
      <div className="grid lg:grid-cols-2 gap-3">{improvements.map(item => <div key={item.id} className="rounded-lg bg-[#050508] border border-amber-500/20 p-4">
        <div className="flex gap-2"><Wrench className="w-4 h-4 text-amber-400" /><b className="text-sm">{item.skill_name}</b><span className="ml-auto text-[9px] uppercase text-amber-300">{item.priority}</span></div>
        <p className="text-xs text-red-300 mt-3">{item.observed_problem}</p><p className="text-xs mt-2">{item.suggested_improvement}</p><p className="text-[10px] text-shogun-subdued mt-2">Validate: {item.validation_idea}</p>
        {item.based_on_trajectory_id && <button onClick={() => { setView('trajectories'); inspect(item.based_on_trajectory_id!); }} className="text-[10px] text-purple-300 mt-3">Open source trajectory →</button>}
      </div>)}</div> : <>
        <div className="flex flex-col md:flex-row gap-2"><div className="relative flex-1"><Search className="absolute left-3 top-2.5 w-4 h-4 text-shogun-subdued" /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search skill, task, run, or model…" className="w-full bg-[#050508] border border-shogun-border rounded-lg pl-9 pr-3 py-2 text-xs" /></div>
          <select value={outcome} onChange={event => setOutcome(event.target.value)} className="bg-[#050508] border border-shogun-border rounded-lg px-3 py-2 text-xs"><option value="">All outcomes</option>{['unknown', 'success', 'partial_success', 'failure', 'blocked'].map(item => <option key={item}>{item}</option>)}</select></div>
        <div className="grid lg:grid-cols-5 gap-3"><div className="lg:col-span-3 overflow-auto max-h-96"><table className="w-full text-xs"><thead className="text-[9px] uppercase text-shogun-subdued border-b border-shogun-border"><tr><th className="text-left py-2">Skill / task</th><th>Model</th><th>Outcome</th><th>Score</th></tr></thead><tbody>
          {filtered.map(item => <tr key={item.id} onClick={() => inspect(item.id)} className="border-b border-shogun-border/50 hover:bg-purple-500/5 cursor-pointer"><td className="py-2"><b>{item.skill_name}</b><p className="text-[10px] text-shogun-subdued max-w-sm truncate">{item.task_summary}</p></td><td className="text-center text-shogun-subdued">{item.model_id || item.model_profile || '—'}</td><td className="text-center uppercase text-[9px]">{item.final_outcome}</td><td className={cn('text-center font-mono', scoreColor(item.score))}>{item.score.toFixed(2)}</td></tr>)}
        </tbody></table>{!filtered.length && <p className="text-center text-sm text-shogun-subdued py-10">No matching trajectories.</p>}</div>
        <div className="lg:col-span-2 rounded-lg bg-[#050508] border border-shogun-border p-4 max-h-96 overflow-auto">{detail ? <div className="space-y-3">
          <div className="flex gap-2"><FileSearch className="w-4 h-4 text-purple-400" /><b>{detail.skill_name}</b></div><p className="text-xs text-shogun-subdued">{detail.episode?.task_summary}</p>
          <div><p className="text-[9px] uppercase text-shogun-subdued">Selection</p><p className="text-xs">{detail.episode?.selection_reason}</p></div>
          <div><p className="text-[9px] uppercase text-shogun-subdued">Timeline</p>{(detail.trajectory?.events || []).map((event: any, index: number) => <p key={`${event.timestamp}-${index}`} className="text-[10px] border-l border-purple-500/30 pl-2 py-1"><b>{event.type}</b> — {event.summary}</p>)}</div>
          <div className="text-[10px] text-shogun-subdued">{detail.tool_links?.length || 0} linked tools · {detail.verification_links?.length || 0} verifications · {detail.improvement_candidates?.length || 0} improvements</div>
        </div> : <div className="h-full flex items-center justify-center text-center text-xs text-shogun-subdued">Select a trajectory to inspect its full redacted timeline.</div>}</div></div>
      </>}
  </div>;
}
