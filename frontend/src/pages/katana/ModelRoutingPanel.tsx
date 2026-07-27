import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Activity, BrainCircuit, CheckCircle2, ChevronDown, ChevronUp, Edit2, Gauge, Play, Plus, RefreshCw, Route, Server, Trash2, X, Zap } from 'lucide-react';

type Profile = {
  id: string; name: string; description?: string; is_default: boolean;
  rules?: Array<{ task_type: string; primary_model_id: string; fallback_model_ids: string[] }>;
};
type RegistryModel = {
  id: string; model_id: string; display_name: string; provider: string; connection_type: string; enabled: boolean;
  capabilities: Record<string, boolean>; quality_tier: number; cost_tier: number; latency_tier: number;
  context_window: number; local: boolean; role_tags: string[];
};
type Decision = {
  selected_model: string; selected_provider: string; fallback_model?: string; reason: string;
  complexity_score: number; estimated_cost_tier: number; estimated_latency_tier: number; active_profile: string;
};

const TASKS = ['simple_chat', 'summarization', 'planning', 'complex_reasoning', 'coding_plan', 'coding_edit',
  'test_failure_analysis', 'visual_understanding', 'browser_task', 'desktop_task', 'self_verification',
  'final_review', 'stack_planning', 'stack_step_execution', 'context_compaction'];
const CAPS = ['reasoning', 'coding', 'vision', 'tool_use', 'long_context', 'json_mode'];
const CAP_LABELS: Record<string, string> = {
  reasoning: 'Reasoning',
  coding: 'Coding',
  vision: 'Images & vision',
  tool_use: 'Tool use',
  long_context: 'Long documents',
  json_mode: 'Structured output',
};

const TIER_OPTIONS = {
  quality_tier: [
    { value: 1, label: 'Basic', help: 'Simple and routine work' },
    { value: 2, label: 'Standard', help: 'Everyday general tasks' },
    { value: 3, label: 'Strong', help: 'Reliable professional work' },
    { value: 4, label: 'Advanced', help: 'Difficult or specialized work' },
    { value: 5, label: 'Frontier', help: 'Highest available capability' },
  ],
  cost_tier: [
    { value: 1, label: 'Very low cost', help: 'Preferred by economy profiles' },
    { value: 2, label: 'Low cost', help: 'Budget-friendly usage' },
    { value: 3, label: 'Moderate cost', help: 'Balanced price point' },
    { value: 4, label: 'High cost', help: 'Use for demanding work' },
    { value: 5, label: 'Premium cost', help: 'Most expensive tier' },
  ],
  latency_tier: [
    { value: 1, label: 'Fastest', help: 'Best for interactive work' },
    { value: 2, label: 'Fast', help: 'Usually responds quickly' },
    { value: 3, label: 'Moderate', help: 'Normal response time' },
    { value: 4, label: 'Slow', help: 'Longer response time' },
    { value: 5, label: 'Slowest', help: 'Use when speed is secondary' },
  ],
} as const;

const COMPLEXITY_LABELS = ['Simple', 'Routine', 'Involved', 'Complex', 'Expert'];
const AUTOMATIC_PROFILE_NAMES = new Set(['Ultra Economy', 'Economy', 'Balanced', 'High Capability', 'Premium']);

const orderedModels = (profile?: Profile): string[] => {
  const rule = profile?.rules?.find(item => item.task_type === '*') || profile?.rules?.[0];
  return rule?.primary_model_id
    ? [String(rule.primary_model_id), ...(rule.fallback_model_ids || []).map(String)]
    : [];
};

type ModelRoutingPanelProps = {
  isEditingProfiles?: boolean;
  onEditProfiles?: () => void;
};

export default function ModelRoutingPanel({ isEditingProfiles = false, onEditProfiles }: ModelRoutingPanelProps) {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [models, setModels] = useState<RegistryModel[]>([]);
  const [usage, setUsage] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [taskType, setTaskType] = useState('coding_edit');
  const [profile, setProfile] = useState('balanced');
  const [complexity, setComplexity] = useState(4);
  const [requirements, setRequirements] = useState<string[]>(['coding', 'tool_use']);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [customModels, setCustomModels] = useState<string[]>([]);
  const [customProfileId, setCustomProfileId] = useState('');
  const [newProfileName, setNewProfileName] = useState('');
  const [newProfileDescription, setNewProfileDescription] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const [profilesRes, registryRes, usageRes] = await Promise.all([
        axios.get('/api/v1/models/routing/profiles'), axios.get('/api/v1/models/registry'),
        axios.get('/api/v1/models/usage/summary'),
      ]);
      const loadedProfiles: Profile[] = profilesRes.data.data || [];
      setProfiles(loadedProfiles);
      setModels(registryRes.data.data || []);
      setUsage(usageRes.data.data || {});
      const active = (profilesRes.data.data || []).find((item: Profile) => item.is_default);
      if (active) setProfile(active.id);
      const editableProfiles = loadedProfiles.filter(item => item.name === 'Custom' || !AUTOMATIC_PROFILE_NAMES.has(item.name));
      const selected = editableProfiles.find(item => item.id === customProfileId)
        || editableProfiles.find(item => item.name === 'Custom')
        || editableProfiles[0];
      setCustomProfileId(selected?.id || '');
      setCustomModels(orderedModels(selected));
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'Model routing data could not be loaded.');
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const activeProfile = useMemo(() => profiles.find(item => item.is_default), [profiles]);
  const customProfiles = useMemo(
    () => profiles.filter(item => item.name === 'Custom' || !AUTOMATIC_PROFILE_NAMES.has(item.name)),
    [profiles],
  );
  const customProfile = useMemo(
    () => customProfiles.find(item => item.id === customProfileId) || customProfiles[0],
    [customProfiles, customProfileId],
  );
  const selectCustomProfile = (profileId: string) => {
    const selected = customProfiles.find(item => item.id === profileId);
    setCustomProfileId(profileId);
    setCustomModels(orderedModels(selected));
  };
  const setActive = async (item: Profile) => {
    setBusy(item.id);
    try {
      await axios.post('/api/v1/models/routing/profiles/active', { profile_id: item.id });
      setMessage(`${item.name} is now the active routing profile.`); await load();
    } catch (error: any) { setMessage(error?.response?.data?.detail || 'Profile could not be activated.'); }
    finally { setBusy(''); }
  };
  const patchModel = async (item: RegistryModel, patch: Partial<RegistryModel>) => {
    setBusy(item.id);
    try {
      const response = await axios.patch(`/api/v1/models/registry/${item.id}`, patch);
      setModels(current => current.map(model => model.id === item.id ? response.data.data : model));
      setMessage(`${item.display_name} updated.`);
    } catch (error: any) { setMessage(error?.response?.data?.detail || 'Model metadata could not be updated.'); }
    finally { setBusy(''); }
  };
  const testModel = async (item: RegistryModel) => {
    setBusy(`test-${item.id}`);
    try { await axios.post(`/api/v1/models/registry/${item.id}/test`); setMessage(`${item.display_name} is reachable.`); }
    catch (error: any) { setMessage(error?.response?.data?.detail || 'Connection test failed.'); }
    finally { setBusy(''); }
  };
  const saveCustom = async (activate = false) => {
    if (!customProfile || customModels.length === 0) {
      setMessage('Choose at least one model for this routing profile.');
      return;
    }
    setBusy(activate ? 'custom-activate' : 'custom-save');
    try {
      await axios.post(`/api/v1/models/routing/profiles/${customProfile.id}/update`, {
        rules: [{
          task_type: '*', primary_model_id: customModels[0], fallback_model_ids: customModels.slice(1),
        }],
      });
      if (activate) {
        await axios.post('/api/v1/models/routing/profiles/active', { profile_id: customProfile.id });
      }
      setMessage(`${customProfile.name} routing saved${activate ? ' and activated' : ''}.`);
      await load();
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'Routing profile could not be saved.');
    } finally { setBusy(''); }
  };
  const createCustomProfile = async () => {
    const name = newProfileName.trim();
    if (!name) return;
    if (profiles.some(item => item.name.toLowerCase() === name.toLowerCase())) {
      setMessage('A routing profile with that name already exists.');
      return;
    }
    setBusy('custom-create');
    try {
      const response = await axios.post('/api/v1/model-routing-profiles', {
        name,
        description: newProfileDescription.trim() || null,
        rules: [],
        is_default: false,
      });
      const created: Profile = response.data.data;
      setNewProfileName('');
      setNewProfileDescription('');
      setMessage(`${created.name} created. Select its models and save it.`);
      await load();
      setCustomProfileId(created.id);
      setCustomModels([]);
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'Routing profile could not be created.');
    } finally { setBusy(''); }
  };
  const deleteCustomProfile = async () => {
    if (!customProfile || customProfile.name === 'Custom' || customProfile.is_default) return;
    if (!window.confirm(`Delete routing profile "${customProfile.name}"?`)) return;
    setBusy('custom-delete');
    try {
      await axios.delete(`/api/v1/model-routing-profiles/${customProfile.id}`);
      setCustomProfileId('');
      setMessage(`${customProfile.name} deleted.`);
      await load();
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'Routing profile could not be deleted.');
    } finally { setBusy(''); }
  };
  const preview = async () => {
    setBusy('preview'); setDecision(null);
    try {
      const response = await axios.post('/api/v1/models/route/preview', {
        prompt: `Preview ${taskType}`, task_type: taskType, complexity_override: complexity,
        required_capabilities: requirements, profile_override: profile,
      });
      setDecision(response.data.data);
    } catch (error: any) { setMessage(error?.response?.data?.detail || 'No eligible route found.'); }
    finally { setBusy(''); }
  };

  if (loading) return <div className="shogun-card flex items-center gap-3 text-sm text-shogun-subdued"><RefreshCw className="w-4 h-4 animate-spin" /> Loading governed routing…</div>;
  return <div className="space-y-6 mb-8">
    <div className="shogun-card border-purple-500/30 bg-purple-500/5">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-5">
        <div><h3 className="font-bold flex items-center gap-2"><Route className="w-5 h-5 text-purple-400" /> Model Routing Profiles</h3>
          <p className="text-xs text-shogun-subdued mt-1">Cheapest sufficient model, with governed escalation and hard capability filters.</p></div>
        <div className="flex items-center gap-2">
          <div className="px-3 py-2 rounded-lg border border-purple-400/30 bg-purple-400/10 text-xs"><span className="text-shogun-subdued">Active </span><strong className="text-purple-300">{activeProfile?.name || 'Balanced'}</strong></div>
          {onEditProfiles && <button onClick={onEditProfiles} className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-[10px] font-bold uppercase tracking-wider transition-colors ${isEditingProfiles ? 'border-purple-400 bg-purple-400/15 text-purple-300' : 'border-shogun-border text-shogun-subdued hover:border-purple-400/40 hover:text-purple-300'}`}>
            <Edit2 className="w-3.5 h-3.5" /> {isEditingProfiles ? 'Close editor' : 'Edit profiles'}
          </button>}
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-6 gap-2">
        {profiles.map(item =>
          <button key={item.id} onClick={() => setActive(item)} disabled={busy === item.id}
            className={`text-left p-3 rounded-lg border transition-all ${item.is_default ? 'border-purple-400 bg-purple-400/15' : 'border-shogun-border hover:border-purple-400/40'}`}>
            <div className="text-xs font-bold flex items-center gap-1.5">{item.is_default && <CheckCircle2 className="w-3.5 h-3.5 text-purple-400" />}{item.name}</div>
            <p className="text-[9px] text-shogun-subdued mt-1 line-clamp-2">{item.description}</p>
          </button>)}
      </div>
      <div className="mt-5 pt-5 border-t border-purple-400/20">
        <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
          <div><h4 className="text-sm font-bold">Named custom routing profiles</h4>
            <p className="text-[10px] text-shogun-subdued mt-1">Create focused profiles such as Finance or Engineering. Each profile keeps its own strict primary and fallback model order.</p></div>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => saveCustom(false)} disabled={!customProfile || busy !== '' || customModels.length === 0}
              className="px-3 py-2 rounded border border-purple-400/40 hover:bg-purple-400/10 disabled:opacity-40 text-[10px] font-bold">
              {busy === 'custom-save' ? 'Saving…' : 'Save profile'}
            </button>
            <button onClick={() => saveCustom(true)} disabled={!customProfile || busy !== '' || customModels.length === 0}
              className="px-3 py-2 rounded bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-[10px] font-bold">
              {busy === 'custom-activate' ? 'Saving…' : 'Save & activate'}
            </button>
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] gap-2 mb-3">
          <label className="text-[9px] uppercase text-shogun-subdued">Edit profile
            <select value={customProfile?.id || ''} onChange={event => selectCustomProfile(event.target.value)} className="block w-full mt-1 bg-[#050508] border border-shogun-border rounded p-2 text-xs normal-case">
              {customProfiles.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-[9px] uppercase text-shogun-subdued">New profile name
              <input value={newProfileName} onChange={event => setNewProfileName(event.target.value)} placeholder="Finance" className="block w-full mt-1 bg-[#050508] border border-shogun-border rounded p-2 text-xs normal-case" />
            </label>
            <label className="text-[9px] uppercase text-shogun-subdued">Description
              <input value={newProfileDescription} onChange={event => setNewProfileDescription(event.target.value)} placeholder="Models for finance work" className="block w-full mt-1 bg-[#050508] border border-shogun-border rounded p-2 text-xs normal-case" />
            </label>
          </div>
          <div className="flex items-end gap-1">
            <button onClick={createCustomProfile} disabled={!newProfileName.trim() || busy !== ''} title="Create named profile" className="h-[34px] px-3 rounded border border-purple-400/40 text-purple-300 hover:bg-purple-400/10 disabled:opacity-40"><Plus className="w-4 h-4" /></button>
            <button onClick={deleteCustomProfile} disabled={!customProfile || customProfile.name === 'Custom' || customProfile.is_default || busy !== ''} title={customProfile?.is_default ? 'Activate another profile before deleting this one' : 'Delete named profile'} className="h-[34px] px-3 rounded border border-red-400/30 text-red-400 hover:bg-red-400/10 disabled:opacity-30"><Trash2 className="w-4 h-4" /></button>
          </div>
        </div>
        {customProfile ? <>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <div className="max-h-44 overflow-y-auto rounded-lg border border-shogun-border p-2 space-y-1">
            {models.filter(item => item.enabled).map(item => {
              const selected = customModels.includes(item.id);
              return <button key={item.id} onClick={() => setCustomModels(current => selected ? current.filter(id => id !== item.id) : [...current, item.id])}
                className={`w-full flex items-center justify-between gap-2 rounded p-2 text-left text-xs border ${selected ? 'border-purple-400/50 bg-purple-400/10' : 'border-transparent hover:border-shogun-border'}`}>
                <span className="truncate"><strong>{item.display_name}</strong><span className="ml-2 text-[9px] text-shogun-subdued">{item.provider}</span></span>
                {selected && <CheckCircle2 className="w-3.5 h-3.5 text-purple-400 shrink-0" />}
              </button>;
            })}
          </div>
          <div className="rounded-lg border border-shogun-border p-2 space-y-1">
            {customModels.map((id, index) => {
              const item = models.find(model => model.id === id);
              if (!item) return null;
              return <div key={id} className="flex items-center gap-2 rounded bg-[#080b14] border border-shogun-border p-2">
                <span className="w-16 text-[8px] font-bold uppercase text-purple-300">{index === 0 ? 'Primary' : `Fallback ${index}`}</span>
                <span className="text-xs flex-1 truncate">{item.display_name}</span>
                <button disabled={index === 0} onClick={() => setCustomModels(current => { const next = [...current]; [next[index - 1], next[index]] = [next[index], next[index - 1]]; return next; })}><ChevronUp className="w-3.5 h-3.5" /></button>
                <button disabled={index === customModels.length - 1} onClick={() => setCustomModels(current => { const next = [...current]; [next[index], next[index + 1]] = [next[index + 1], next[index]]; return next; })}><ChevronDown className="w-3.5 h-3.5" /></button>
                <button onClick={() => setCustomModels(current => current.filter(value => value !== id))}><X className="w-3.5 h-3.5 text-red-400" /></button>
              </div>;
            })}
            {!customModels.length && <p className="text-[10px] text-shogun-subdued text-center py-6">Select models from the registry.</p>}
          </div>
        </div>
        </> : <p className="text-[10px] text-shogun-subdued py-4">Create a named profile to configure its model order.</p>}
      </div>
    </div>

    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
      <div className="xl:col-span-2 shogun-card">
        <div className="flex items-center justify-between mb-4"><div><h4 className="font-bold flex items-center gap-2"><Server className="w-4 h-4 text-shogun-blue" /> Model Capability Registry</h4>
          <p className="text-[10px] text-shogun-subdued mt-1">Describe what each connected model can do, how capable it is, what it costs, and how quickly it responds. The router uses these as eligibility and preference signals.</p></div><button onClick={load}><RefreshCw className="w-4 h-4" /></button></div>
        <div className="space-y-3 max-h-[560px] overflow-y-auto pr-1">
          {models.map(item => <div key={item.id} className={`rounded-xl border p-4 ${item.enabled ? 'border-shogun-border bg-[#080b14]' : 'border-shogun-border/40 opacity-60'}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div><div className="flex items-center gap-2 flex-wrap"><span className="font-bold font-mono text-sm text-shogun-text">{item.model_id}</span><span className="text-[9px] font-bold uppercase tracking-widest border border-purple-400/30 bg-purple-500/10 text-purple-300 rounded px-1.5 py-0.5">{item.provider}</span>{item.local && <span className="text-[8px] uppercase border border-shogun-border rounded px-1.5 py-0.5">local</span>}</div>
                <p className="font-mono text-[9px] text-shogun-subdued mt-1">{item.display_name !== item.model_id ? `${item.display_name} · ` : ''}{(item.context_window / 1000).toFixed(0)}K context window</p></div>
              <div className="flex items-center gap-2"><button onClick={() => testModel(item)} className="px-2 py-1 text-[9px] border border-shogun-border rounded hover:border-shogun-blue">{busy === `test-${item.id}` ? 'Testing…' : 'Test'}</button>
                <button onClick={() => patchModel(item, { enabled: !item.enabled })} className={`w-10 h-5 rounded-full p-0.5 ${item.enabled ? 'bg-green-500' : 'bg-gray-700'}`}><span className={`block w-4 h-4 bg-white rounded-full transition-transform ${item.enabled ? 'translate-x-5' : ''}`} /></button></div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 my-3">
              {(['quality_tier','cost_tier','latency_tier'] as const).map(key => {
                const selected = TIER_OPTIONS[key].find(option => option.value === item[key]) || TIER_OPTIONS[key][2];
                return <label key={key} className="text-[9px] uppercase text-shogun-subdued">{key.replace('_tier','')}
                  <select value={item[key]} onChange={event => patchModel(item, { [key]: Number(event.target.value) })} className="block w-full mt-1 bg-[#050508] border border-shogun-border rounded p-1.5 text-xs normal-case">
                    {TIER_OPTIONS[key].map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                  <span className="block mt-1 text-[8px] normal-case leading-tight text-shogun-subdued/70">{selected.help}</span>
                </label>;
              })}
            </div>
            <p className="text-[8px] uppercase tracking-wider text-shogun-subdued mb-1.5">Supported task capabilities — click to enable or disable</p>
            <div className="flex flex-wrap gap-1.5">{CAPS.map(cap => <button key={cap} onClick={() => patchModel(item, { capabilities: { ...item.capabilities, [cap]: !item.capabilities?.[cap] } })}
              className={`text-[8px] uppercase px-2 py-1 rounded border ${item.capabilities?.[cap] ? 'border-cyan-400/40 bg-cyan-400/10 text-cyan-300' : 'border-shogun-border text-shogun-subdued'}`}>{CAP_LABELS[cap]}</button>)}</div>
            <div className="mt-2 flex flex-wrap gap-1">{(item.role_tags || []).map(tag => <span key={tag} className="rounded bg-purple-400/10 px-1.5 py-0.5 text-[8px] uppercase text-purple-300">{tag}</span>)}</div>
          </div>)}
          {!models.length && <p className="text-sm text-shogun-subdued text-center py-8">Connect a model provider to populate the registry.</p>}
        </div>
      </div>

      <div className="space-y-6">
        <div className="shogun-card"><h4 className="font-bold flex items-center gap-2 mb-4"><BrainCircuit className="w-4 h-4 text-shogun-gold" /> Preview Decision</h4>
          <div className="space-y-3"><label className="text-[9px] uppercase text-shogun-subdued">Task type<select value={taskType} onChange={event => setTaskType(event.target.value)} className="block w-full mt-1 bg-[#050508] border border-shogun-border rounded p-2 text-xs">{TASKS.map(item => <option key={item}>{item}</option>)}</select></label>
            <label className="text-[9px] uppercase text-shogun-subdued">Profile<select value={profile} onChange={event => setProfile(event.target.value)} className="block w-full mt-1 bg-[#050508] border border-shogun-border rounded p-2 text-xs">{profiles.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            <label className="text-[9px] uppercase text-shogun-subdued">Task complexity: <strong className="text-shogun-text normal-case">{COMPLEXITY_LABELS[complexity - 1]}</strong><input type="range" min="1" max="5" value={complexity} onChange={event => setComplexity(Number(event.target.value))} className="block w-full mt-2" /></label>
            <div className="flex flex-wrap gap-1">{CAPS.map(cap => <button key={cap} onClick={() => setRequirements(current => current.includes(cap) ? current.filter(item => item !== cap) : [...current, cap])} className={`text-[8px] border rounded px-1.5 py-1 ${requirements.includes(cap) ? 'border-shogun-gold text-shogun-gold' : 'border-shogun-border text-shogun-subdued'}`}>{CAP_LABELS[cap]}</button>)}</div>
            <button onClick={preview} disabled={busy === 'preview'} className="w-full flex items-center justify-center gap-2 p-2 rounded bg-purple-600 hover:bg-purple-500 font-bold text-xs"><Play className="w-3.5 h-3.5" /> Preview route</button>
          </div>
          {decision && <div className="mt-4 p-3 rounded-lg border border-green-400/30 bg-green-400/5"><div className="font-bold text-sm text-green-300">{decision.selected_model}</div><div className="text-[9px] text-shogun-subdued">{decision.selected_provider} · fallback {decision.fallback_model || 'none'}</div><p className="text-[10px] mt-2 leading-relaxed">{decision.reason}</p><div className="flex flex-wrap gap-3 mt-2 text-[8px] uppercase text-shogun-subdued"><span>{COMPLEXITY_LABELS[Math.max(1, Math.min(5, decision.complexity_score)) - 1]} task</span><span>{TIER_OPTIONS.cost_tier.find(option => option.value === decision.estimated_cost_tier)?.label || 'Unknown cost'}</span><span>{TIER_OPTIONS.latency_tier.find(option => option.value === decision.estimated_latency_tier)?.label || 'Unknown speed'}</span></div></div>}
        </div>
        <div className="shogun-card"><h4 className="font-bold flex items-center gap-2 mb-3"><Activity className="w-4 h-4 text-green-400" /> Usage</h4><div className="grid grid-cols-2 gap-2 text-center">
          <Metric icon={<Zap className="w-3 h-3" />} label="Events" value={usage.events || 0} /><Metric icon={<Gauge className="w-3 h-3" />} label="Avg latency" value={`${usage.average_latency_ms || 0} ms`} />
          <Metric label="Input tokens" value={usage.input_tokens || 0} /><Metric label="Output tokens" value={usage.output_tokens || 0} /></div></div>
      </div>
    </div>
    {message && <div className="text-xs border border-shogun-border rounded-lg px-3 py-2" onClick={() => setMessage('')}>{message}</div>}
  </div>;
}

function Metric({ icon, label, value }: { icon?: React.ReactNode; label: string; value: string | number }) {
  return <div className="rounded-lg border border-shogun-border p-2"><div className="flex items-center justify-center gap-1 text-[8px] uppercase text-shogun-subdued">{icon}{label}</div><div className="font-bold text-sm mt-1">{value}</div></div>;
}
