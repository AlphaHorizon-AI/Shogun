import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  Activity, AlertTriangle, BrainCircuit, CheckCircle2, ChevronRight,
  FileText, Loader2, Power, RefreshCw, Search, ShieldCheck, Sparkles,
  Target, XCircle,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import SkillTrajectoriesPanel from './SkillTrajectoriesPanel';

type Skill = {
  id: string; name: string; slug: string; version: string; skill_type: string;
  status: string; exam_status: string; source_id?: string; tags: string[];
  triggers: string[]; use_when: string[]; avoid_when: string[]; requires_tools: string[];
  minimum_posture: string; risk_tier: string; priority: number; conflict_group?: string;
  model_hint?: string; max_context_tokens: number; activation_mode: string;
  body_text?: string; brief_text?: string; verification_checklist: string[];
  last_used_at?: string; usage_count: number; success_count: number; failure_count: number;
  manifest?: { source?: string; description?: string };
};

type SkillRun = {
  id: string; run_id?: string; stack_run_id?: string; step_run_id?: string; skill_id: string;
  skill_name?: string; activation_reason: string; relevance_score: number; activation_mode: string;
  usage_location: string; injected_tokens: number; posture: string; conflict_notes: string[];
  outcome: string; outcome_summary?: string; created_at: string;
};

type ActivationResult = {
  run_id: string; context_block: string; total_injected_tokens: number;
  active_skills: Array<{ active_skill_run_id: string; skill_id: string; name: string; skill_type: string;
    relevance_score: number; activation_reason: string; activation_mode: string; brief: string;
    injected_tokens: number; verification_checklist: string[] }>;
  considered_skills: Array<{ skill_id: string; name: string; relevance_score: number; reason: string }>;
  blocked_skills: Array<{ skill_id: string; name: string; relevance_score: number; reason: string; blocked_reason: string }>;
  conflict_notes: string[];
};

const unwrap = (value: any) => value?.data?.data ?? value?.data ?? value;
const formatTime = (value?: string) => value ? new Date(value).toLocaleString() : 'Never';

export default function ActiveSkillsPanel() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [runs, setRuns] = useState<SkillRun[]>([]);
  const [selected, setSelected] = useState<Skill | null>(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [objective, setObjective] = useState('Write a complete Shogun implementation build paper');
  const [posture, setPosture] = useState('campaign');
  const [activation, setActivation] = useState<ActivationResult | null>(null);
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [skillResponse, runResponse] = await Promise.all([
        axios.get('/api/v1/skills'),
        axios.get('/api/v1/skills/active-runs', { params: { limit: 100 } }),
      ]);
      const nextSkills = unwrap(skillResponse) || [];
      setSkills(nextSkills);
      setRuns(unwrap(runResponse) || []);
      if (selected) setSelected(nextSkills.find((item: Skill) => item.id === selected.id) || null);
    } catch (error: any) {
      setMessage({ kind: 'error', text: error.response?.data?.detail || 'Could not load active skill usage.' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return skills;
    return skills.filter(skill => [skill.name, skill.skill_type, skill.status, ...(skill.tags || [])]
      .some(value => String(value).toLowerCase().includes(query)));
  }, [skills, search]);

  const enabled = skills.filter(skill => skill.status === 'installed').length;
  const successful = runs.filter(run => run.outcome === 'success').length;

  const toggle = async (skill: Skill) => {
    setBusy(skill.id);
    try {
      const action = skill.status === 'disabled' ? 'enable' : 'disable';
      await axios.post(`/api/v1/skills/${skill.id}/${action}`);
      setMessage({ kind: 'ok', text: `${skill.name} ${action}d.` });
      await load();
    } catch (error: any) {
      setMessage({ kind: 'error', text: error.response?.data?.detail || 'Skill status could not be changed.' });
    } finally { setBusy(null); }
  };

  const maintenance = async (skill: Skill, action: 'rebuild-brief' | 'reindex') => {
    setBusy(`${skill.id}:${action}`);
    try {
      await axios.post(`/api/v1/skills/${skill.id}/${action}`);
      setMessage({ kind: 'ok', text: `${skill.name}: ${action === 'reindex' ? 'semantic index updated' : 'brief rebuilt'}.` });
      await load();
    } catch (error: any) {
      setMessage({ kind: 'error', text: error.response?.data?.detail || `${action} failed.` });
    } finally { setBusy(null); }
  };

  const testActivation = async () => {
    if (!objective.trim()) return;
    setBusy('activate');
    try {
      const response = await axios.post('/api/v1/skills/activate', {
        run_id: `katana-preview-${Date.now()}`,
        objective,
        context: 'Katana Active Usage preview',
        posture,
        available_tools: posture === 'campaign' || posture === 'ronin'
          ? ['chat', 'agent_flow', 'stacks', 'ide.file.read', 'ide.file.apply_patch', 'ide.task.run']
          : ['chat', 'agent_flow', 'stacks'],
        max_skills: 5,
        usage_location: 'katana_preview',
        ide_enabled: posture === 'campaign' || posture === 'ronin',
      });
      setActivation(unwrap(response));
      await load();
    } catch (error: any) {
      setMessage({ kind: 'error', text: error.response?.data?.detail || 'Activation preview failed.' });
    } finally { setBusy(null); }
  };

  if (loading && !skills.length) return (
    <div className="shogun-card flex items-center justify-center py-24 gap-3 text-shogun-subdued">
      <Loader2 className="w-5 h-5 animate-spin text-purple-400" /> Loading active skill usage…
    </div>
  );

  return <div className="space-y-5">
    {message && <div className={cn('rounded-lg border px-4 py-3 text-sm flex items-center gap-2',
      message.kind === 'ok' ? 'border-green-500/30 bg-green-500/5 text-green-400' : 'border-red-500/30 bg-red-500/5 text-red-400')}>
      {message.kind === 'ok' ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
      {message.text}
    </div>}

    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {[
        ['Installed & enabled', enabled, Power, 'text-green-400'],
        ['Total activations', runs.length, Activity, 'text-purple-400'],
        ['Successful outcomes', successful, ShieldCheck, 'text-cyan-400'],
        ['Context ceiling', '2,500 tokens', BrainCircuit, 'text-shogun-gold'],
      ].map(([label, value, Icon, color]: any) => <div key={label} className="shogun-card !p-4">
        <div className="flex items-center justify-between"><span className="text-[9px] uppercase tracking-widest text-shogun-subdued">{label}</span><Icon className={cn('w-4 h-4', color)} /></div>
        <div className="mt-2 text-xl font-bold text-shogun-text">{value}</div>
      </div>)}
    </div>

    <SkillTrajectoriesPanel />

    <div className="shogun-card border-purple-500/20">
      <div className="flex flex-col lg:flex-row lg:items-end gap-3">
        <div className="flex-1">
          <label className="text-[9px] uppercase tracking-widest font-bold text-purple-300">Activation Preview</label>
          <textarea value={objective} onChange={event => setObjective(event.target.value)} rows={2}
            className="mt-2 w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm outline-none focus:border-purple-500" />
        </div>
        <select value={posture} onChange={event => setPosture(event.target.value)}
          className="bg-[#050508] border border-shogun-border rounded-lg px-3 py-3 text-sm">
          {['shrine', 'guarded', 'tactical', 'campaign', 'ronin'].map(item => <option key={item} value={item}>{item.toUpperCase()}</option>)}
        </select>
        <button onClick={testActivation} disabled={busy === 'activate'}
          className="rounded-lg bg-purple-500/20 border border-purple-400/40 text-purple-200 px-5 py-3 text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 disabled:opacity-50">
          {busy === 'activate' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />} Activate Skills
        </button>
      </div>
      {activation && <div className="mt-5 grid lg:grid-cols-3 gap-4 border-t border-shogun-border pt-5">
        <div className="lg:col-span-2 space-y-2">
          <div className="flex items-center justify-between text-[10px] uppercase tracking-widest font-bold"><span>Active for this run</span><span className="text-purple-300">{activation.total_injected_tokens} tokens</span></div>
          {activation.active_skills.length ? activation.active_skills.map(item => <div key={item.active_skill_run_id} className="rounded-lg border border-purple-500/20 bg-purple-500/5 p-3">
            <div className="flex items-center gap-2"><Target className="w-4 h-4 text-purple-400" /><b className="text-sm">{item.name}</b><span className="ml-auto text-xs font-mono text-purple-300">{item.relevance_score.toFixed(2)}</span></div>
            <p className="text-xs text-shogun-subdued mt-1">{item.activation_reason} · {item.activation_mode} · {item.injected_tokens} tokens</p>
          </div>) : <p className="text-sm text-shogun-subdued">No skill crossed the activation threshold.</p>}
        </div>
        <div className="space-y-3">
          <div><p className="text-[10px] uppercase tracking-widest font-bold text-shogun-subdued">Blocked</p>
            {activation.blocked_skills.slice(0, 6).map(item => <p key={item.skill_id} className="text-xs text-orange-300 mt-1">{item.name}: {item.blocked_reason}</p>)}</div>
          {activation.conflict_notes.length > 0 && <div><p className="text-[10px] uppercase tracking-widest font-bold text-shogun-subdued">Conflicts resolved</p>
            {activation.conflict_notes.map(note => <p key={note} className="text-xs text-shogun-subdued mt-1">{note}</p>)}</div>}
        </div>
      </div>}
    </div>

    <div className="grid lg:grid-cols-5 gap-5">
      <div className="lg:col-span-3 shogun-card">
        <div className="flex items-center gap-3 mb-4"><div className="relative flex-1"><Search className="w-4 h-4 absolute left-3 top-3 text-shogun-subdued" />
          <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search installed skills…" className="w-full bg-[#050508] border border-shogun-border rounded-lg py-2.5 pl-9 pr-3 text-sm" /></div>
          <button onClick={load} className="p-2.5 border border-shogun-border rounded-lg"><RefreshCw className="w-4 h-4" /></button></div>
        <div className="space-y-2 max-h-[620px] overflow-y-auto pr-1">
          {filtered.map(skill => <button key={skill.id} onClick={() => setSelected(skill)} className={cn('w-full text-left rounded-lg border p-3 transition-colors', selected?.id === skill.id ? 'border-purple-500/50 bg-purple-500/5' : 'border-shogun-border bg-[#050508] hover:border-shogun-subdued/50')}>
            <div className="flex items-center gap-2"><BrainCircuit className="w-4 h-4 text-purple-400" /><b className="text-sm truncate">{skill.name}</b>
              <span className={cn('ml-auto text-[9px] uppercase font-bold', skill.status === 'installed' ? 'text-green-400' : 'text-shogun-subdued')}>{skill.status}</span><ChevronRight className="w-4 h-4 text-shogun-subdued" /></div>
            <div className="mt-2 flex flex-wrap gap-2 text-[9px] uppercase tracking-wider text-shogun-subdued"><span>{skill.skill_type}</span><span>Exam: {skill.exam_status}</span><span>{skill.minimum_posture}+</span><span>{skill.usage_count} uses</span></div>
          </button>)}
        </div>
      </div>

      <div className="lg:col-span-2 shogun-card">
        {selected ? <div className="space-y-4">
          <div><p className="text-[9px] uppercase tracking-widest text-purple-300">Skill Detail</p><h3 className="text-xl font-bold mt-1">{selected.name}</h3><p className="text-xs text-shogun-subdued">v{selected.version} · {selected.activation_mode} · priority {selected.priority} · {selected.manifest?.source || 'local'}</p></div>
          <div className="flex gap-2"><button onClick={() => toggle(selected)} disabled={busy === selected.id} className={cn('flex-1 rounded-lg border py-2 text-xs font-bold uppercase', selected.status === 'disabled' ? 'border-green-500/30 text-green-400' : 'border-red-500/30 text-red-300')}>
            {selected.status === 'disabled' ? 'Enable' : 'Disable'}</button>
            <button onClick={() => maintenance(selected, 'rebuild-brief')} className="px-3 rounded-lg border border-shogun-border" title="Rebuild brief"><FileText className="w-4 h-4" /></button>
            <button onClick={() => maintenance(selected, 'reindex')} className="px-3 rounded-lg border border-shogun-border" title="Reindex"><RefreshCw className="w-4 h-4" /></button></div>
          <div className="grid grid-cols-3 gap-2 text-center"><div className="bg-[#050508] rounded p-2"><b>{selected.usage_count}</b><p className="text-[8px] uppercase text-shogun-subdued">Uses</p></div><div className="bg-[#050508] rounded p-2"><b className="text-green-400">{selected.success_count}</b><p className="text-[8px] uppercase text-shogun-subdued">Success</p></div><div className="bg-[#050508] rounded p-2"><b className="text-red-400">{selected.failure_count}</b><p className="text-[8px] uppercase text-shogun-subdued">Failed</p></div></div>
          <div><p className="text-[9px] uppercase tracking-widest font-bold text-shogun-subdued mb-1">Compact brief</p><pre className="whitespace-pre-wrap text-xs leading-relaxed bg-[#050508] border border-shogun-border rounded-lg p-3 max-h-52 overflow-auto">{selected.brief_text || 'Brief not built yet.'}</pre></div>
          {selected.body_text && <details><summary className="text-[9px] uppercase tracking-widest font-bold text-shogun-subdued cursor-pointer">Full skill body</summary><pre className="mt-2 whitespace-pre-wrap text-xs leading-relaxed bg-[#050508] border border-shogun-border rounded-lg p-3 max-h-72 overflow-auto">{selected.body_text}</pre></details>}
          {selected.requires_tools?.length > 0 && <div><p className="text-[9px] uppercase tracking-widest font-bold text-shogun-subdued">Required tools</p><div className="flex flex-wrap gap-1 mt-2">{selected.requires_tools.map(item => <code key={item} className="text-[9px] px-2 py-1 rounded bg-cyan-500/5 border border-cyan-500/20 text-cyan-300">{item}</code>)}</div></div>}
          {selected.verification_checklist?.length > 0 && <div><p className="text-[9px] uppercase tracking-widest font-bold text-shogun-subdued">Verification checklist</p>{selected.verification_checklist.map(item => <p key={item} className="text-xs mt-1 flex gap-2"><CheckCircle2 className="w-3.5 h-3.5 text-green-400 shrink-0" />{item}</p>)}</div>}
          <p className="text-[10px] text-shogun-subdued">Last used: {formatTime(selected.last_used_at)}</p>
        </div> : <div className="h-full min-h-72 flex flex-col items-center justify-center text-center text-shogun-subdued"><BrainCircuit className="w-10 h-10 text-purple-400/40 mb-3" /><p className="text-sm">Select a skill to inspect its brief, compatibility gates, usage, and verification checklist.</p></div>}
      </div>
    </div>

    <div className="shogun-card">
      <div className="flex items-center gap-2 mb-3"><Activity className="w-4 h-4 text-purple-400" /><h3 className="font-bold">Recent Skill Usage</h3></div>
      <div className="overflow-x-auto"><table className="w-full text-xs"><thead className="text-[9px] uppercase tracking-widest text-shogun-subdued border-b border-shogun-border"><tr><th className="text-left py-2">Skill</th><th className="text-left">Where</th><th className="text-left">Reason</th><th>Score</th><th>Tokens</th><th>Outcome</th><th className="text-right">When</th></tr></thead>
        <tbody>{runs.slice(0, 30).map(run => <tr key={run.id} className="border-b border-shogun-border/50"><td className="py-2 font-semibold">{run.skill_name || run.skill_id}</td><td>{run.usage_location}</td><td className="max-w-xs truncate text-shogun-subdued">{run.activation_reason}</td><td className="text-center font-mono">{run.relevance_score.toFixed(2)}</td><td className="text-center">{run.injected_tokens}</td><td className={cn('text-center uppercase text-[9px] font-bold', run.outcome === 'success' ? 'text-green-400' : run.outcome === 'failed' ? 'text-red-400' : 'text-shogun-subdued')}>{run.outcome}</td><td className="text-right text-shogun-subdued">{formatTime(run.created_at)}</td></tr>)}</tbody></table></div>
      {!runs.length && <p className="text-sm text-shogun-subdued py-8 text-center"><AlertTriangle className="w-4 h-4 inline mr-2" />No skill activations recorded yet.</p>}
    </div>
  </div>;
}
