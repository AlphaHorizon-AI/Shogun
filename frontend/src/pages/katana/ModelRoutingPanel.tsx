import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Activity, BrainCircuit, CheckCircle2, ChevronDown, ChevronUp, Gauge, LockKeyhole, Play, Plus, RefreshCw, Route, Server, Trash2, X, Zap } from 'lucide-react';
import { customProfileUpdate } from '../../lib/routingProfiles';

type Profile = {
  id: string; name: string; description?: string; is_default: boolean;
  rules?: Array<{ task_type: string; primary_model_id: string; fallback_model_ids: string[] }>;
  model_settings?: Record<string, { temperature?: number }>;
};
type RegistryModel = {
  id: string; model_id: string; display_name: string; provider_id?: string; provider: string; connection_type: string; enabled: boolean;
  capabilities: Record<string, boolean>; quality_tier: number; cost_tier: number; latency_tier: number;
  context_window: number; max_output_tokens: number; local: boolean; role_tags: string[];
  config_json: Record<string, unknown>;
};
type Decision = {
  selected_model: string; selected_provider: string; fallback_model?: string; reason: string;
  selected_temperature?: number;
  fallback_models?: Array<{ model_id: string; display_name: string; provider: string; temperature?: number }>;
  complexity_score: number; estimated_cost_tier: number; estimated_latency_tier: number; active_profile: string;
};
type ToolCallingProfile = {
  version: number; adapter_id: string; mode: 'native' | 'text' | 'unsupported';
  request_schema: string; response_schema: string; result_schema: string;
  status: 'verified' | 'detected' | 'inferred' | 'fallback' | 'unsupported';
  source: string; confidence: number; last_tested_at?: string | null; last_error?: string | null;
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
const AUTOMATIC_PROFILE_NAMES = new Set([
  'Balanced (Default)', 'Quality First', 'Cost Optimized',
  'Ultra Economy', 'Economy', 'Balanced', 'High Capability', 'Premium',
]);

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
  const [usage, setUsage] = useState<Record<string, any>>({});
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
  const activeIsAutomatic = Boolean(activeProfile && AUTOMATIC_PROFILE_NAMES.has(activeProfile.name));
  const registryEditable = Boolean(activeProfile && !activeIsAutomatic);
  const temperatureModels = useMemo(() => {
    if (!activeProfile) return [];
    if (activeIsAutomatic) return models.filter(item => item.enabled);
    return orderedModels(activeProfile)
      .map(id => models.find(item => item.id === id || item.model_id === id))
      .filter((item): item is RegistryModel => Boolean(item));
  }, [activeIsAutomatic, activeProfile, models]);
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
  const chooseProfile = async (item: Profile) => {
    const automatic = AUTOMATIC_PROFILE_NAMES.has(item.name);
    if (automatic) {
      if (isEditingProfiles) onEditProfiles?.();
    } else {
      selectCustomProfile(item.id);
      if (!isEditingProfiles) onEditProfiles?.();
    }
    await setActive(item);
    if (!automatic) selectCustomProfile(item.id);
  };
  const toggleCustomCreator = () => {
    if (!isEditingProfiles) {
      setNewProfileName('');
      setNewProfileDescription('');
    }
    onEditProfiles?.();
  };
  const patchModel = async (item: RegistryModel, patch: Partial<RegistryModel>) => {
    if (!registryEditable) return;
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
  const verifyToolCalling = async (item: RegistryModel) => {
    setBusy(`tools-${item.id}`);
    try {
      const response = await axios.post(`/api/v1/models/registry/${item.id}/tool-calling/test`);
      const updated: RegistryModel = response.data.data.model;
      const profileData: ToolCallingProfile = response.data.data.profile;
      setModels(current => current.map(model => model.id === item.id ? updated : model));
      setMessage(profileData.mode === 'native'
        ? `${item.display_name} verified native tool calling.`
        : `${item.display_name} will use Shogun's governed tool-calling fallback.`);
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'Tool-calling verification failed.');
    } finally { setBusy(''); }
  };
  const setProfileTemperature = async (item: RegistryModel, temperature: number) => {
    if (!activeProfile || !Number.isFinite(temperature)) return;
    const clamped = Math.max(0, Math.min(2, temperature));
    const modelSettings = {
      ...(activeProfile.model_settings || {}),
      [item.id]: {
        ...(activeProfile.model_settings?.[item.id] || {}),
        temperature: clamped,
      },
    };
    setBusy(`temperature-${item.id}`);
    try {
      const response = await axios.post(`/api/v1/models/routing/profiles/${activeProfile.id}/update`, {
        model_settings: modelSettings,
      });
      const updated: Profile = response.data.data;
      setProfiles(current => current.map(profileItem => profileItem.id === updated.id ? updated : profileItem));
      setMessage(`${item.display_name} temperature set to ${clamped.toFixed(2)} for ${activeProfile.name}.`);
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'Profile temperature could not be saved.');
    } finally { setBusy(''); }
  };
  const saveCustom = async (activate = false) => {
    if (!customProfile || customModels.length === 0) {
      setMessage('Choose at least one model for this routing profile.');
      return;
    }
    const pendingRename = customProfile.name === 'Custom' ? newProfileName.trim() : '';
    if (pendingRename && profiles.some(item => item.id !== customProfile.id && item.name.toLowerCase() === pendingRename.toLowerCase())) {
      setMessage('A routing profile with that name already exists.');
      return;
    }
    setBusy(activate ? 'custom-activate' : 'custom-save');
    try {
      const update = customProfileUpdate(
        customProfile,
        customModels,
        newProfileName,
        newProfileDescription,
      );
      const response = pendingRename
        ? await axios.post('/api/v1/model-routing-profiles', {
            ...update,
            model_settings: customProfile.model_settings || {},
            is_default: false,
          })
        : await axios.post(`/api/v1/models/routing/profiles/${customProfile.id}/update`, update);
      const saved: Profile = response.data.data;
      if (activate) {
        await axios.post('/api/v1/models/routing/profiles/active', { profile_id: saved.id });
      }
      if (pendingRename) {
        setNewProfileName('');
        setNewProfileDescription('');
      }
      setMessage(`${saved.name} routing saved${activate ? ' and activated' : ''}.`);
      await load();
      setCustomProfileId(saved.id);
      setCustomModels(orderedModels(saved));
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
      await axios.post('/api/v1/models/routing/profiles/active', { profile_id: created.id });
      setNewProfileName('');
      setNewProfileDescription('');
      setMessage(`${created.name} created and activated. Select its models and save it.`);
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
          <p className="text-xs text-shogun-subdued mt-1">Built-in profiles choose models automatically from capability, cost, speed, and task requirements. Custom profiles use your exact model order.</p></div>
        <div className="flex items-center gap-2">
          <div className={`px-3 py-2 rounded-lg border text-xs ${activeIsAutomatic ? 'border-cyan-400/30 bg-cyan-400/10' : 'border-amber-400/30 bg-amber-400/10'}`}><span className="text-shogun-subdued">Active </span><strong className={activeIsAutomatic ? 'text-cyan-300' : 'text-amber-300'}>{activeProfile?.name || 'Balanced'}</strong></div>
          {onEditProfiles && <button onClick={toggleCustomCreator} className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-[10px] font-bold uppercase tracking-wider transition-colors ${isEditingProfiles ? 'border-amber-400 bg-amber-400/15 text-amber-300' : 'border-amber-400/40 text-amber-300 hover:border-amber-300 hover:bg-amber-400/10'}`}>
            {isEditingProfiles ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />} {isEditingProfiles ? 'Close custom editor' : 'Create custom profile'}
          </button>}
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-6 gap-2">
        {profiles.map(item => {
          const automatic = AUTOMATIC_PROFILE_NAMES.has(item.name);
          const displayName = item.name === 'Custom' && isEditingProfiles && newProfileName.trim()
            ? newProfileName.trim()
            : item.name;
          const cardStyle = automatic
            ? item.is_default
              ? 'border-cyan-400/60 bg-cyan-400/10 shadow-[0_0_18px_rgba(34,211,238,0.08)]'
              : 'border-shogun-border bg-[#080b14] hover:border-cyan-400/40 hover:bg-cyan-400/5'
            : item.is_default
              ? 'border-amber-300/70 bg-amber-400/15 shadow-[0_0_18px_rgba(251,191,36,0.12)]'
              : 'border-amber-400/30 bg-amber-400/[0.06] hover:border-amber-300/70 hover:bg-amber-400/10';
          return <button key={item.id} onClick={() => chooseProfile(item)} disabled={busy === item.id}
            className={`text-left p-3 rounded-lg border transition-all ${cardStyle}`}>
            <div className="text-xs font-bold flex items-center gap-1.5">{item.is_default && <CheckCircle2 className={`w-3.5 h-3.5 ${automatic ? 'text-cyan-300' : 'text-amber-300'}`} />}{displayName}</div>
            <p className="text-[9px] text-shogun-subdued mt-1 line-clamp-2">{item.description}</p>
            <span className={`mt-2 inline-block text-[8px] font-bold uppercase tracking-wider ${automatic ? 'text-cyan-300' : 'text-amber-300'}`}>
              {automatic ? 'Fixed · automatic · read-only' : 'Custom · operator-defined'}
            </span>
          </button>;
        })}
      </div>
      {activeProfile && <div className="mt-4 rounded-lg border border-purple-400/20 bg-purple-400/[0.04] p-3">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
          <div><h4 className="text-xs font-bold text-purple-200">Profile model temperatures</h4>
            <p className="mt-1 text-[9px] text-shogun-subdued">Scoped only to <strong>{activeProfile.name}</strong>. Global model capabilities are unchanged.</p></div>
          <span className="rounded border border-purple-400/25 px-2 py-1 text-[8px] font-bold uppercase text-purple-300">0 deterministic · 2 creative</span>
        </div>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
          {temperatureModels.map(item => {
            const temperature = activeProfile.model_settings?.[item.id]?.temperature ?? 0.3;
            return <label key={`${activeProfile.id}-${item.id}`} className="flex items-center gap-3 rounded border border-shogun-border bg-[#080b14] px-3 py-2">
              <span className="min-w-0 flex-1"><strong className="block truncate text-[10px]">{item.display_name}</strong><span className="block truncate text-[8px] text-shogun-subdued">{item.provider} · {item.model_id}</span></span>
              <input type="number" min={0} max={2} step={0.05} defaultValue={temperature}
                disabled={busy === `temperature-${item.id}`}
                onBlur={event => {
                  const value = Math.max(0, Math.min(2, Number(event.currentTarget.value)));
                  event.currentTarget.value = String(value);
                  setProfileTemperature(item, value);
                }}
                className="w-20 rounded border border-purple-400/30 bg-[#050508] p-1.5 text-right font-mono text-[10px] text-purple-200 outline-none" />
            </label>;
          })}
          {!temperatureModels.length && <p className="py-2 text-[10px] text-shogun-subdued">Add or enable models in this profile to configure their temperatures.</p>}
        </div>
      </div>}
      {isEditingProfiles && <div className="mt-5 pt-5 border-t border-amber-400/20">
        <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
          <div><h4 className="text-sm font-bold">Named custom routing profiles</h4>
            <p className="text-[10px] text-shogun-subdued mt-1">Create focused profiles such as Finance or Engineering. Each profile keeps its own strict primary and fallback model order.</p></div>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => saveCustom(false)} disabled={!customProfile || busy !== '' || customModels.length === 0}
              className="px-3 py-2 rounded border border-amber-400/40 hover:bg-amber-400/10 disabled:opacity-40 text-[10px] font-bold">
              {busy === 'custom-save' ? 'Saving…' : 'Save profile'}
            </button>
            <button onClick={() => saveCustom(true)} disabled={!customProfile || busy !== '' || customModels.length === 0}
              className="px-3 py-2 rounded bg-amber-500 text-black hover:bg-amber-400 disabled:opacity-40 text-[10px] font-bold">
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
            <button onClick={createCustomProfile} disabled={!newProfileName.trim() || busy !== ''} title="Create clean custom profile" className="h-[34px] px-3 rounded border border-amber-400/40 text-amber-300 hover:bg-amber-400/10 disabled:opacity-40"><Plus className="w-4 h-4" /></button>
            <button onClick={deleteCustomProfile} disabled={!customProfile || customProfile.name === 'Custom' || customProfile.is_default || busy !== ''} title={customProfile?.is_default ? 'Activate another profile before deleting this one' : 'Delete named profile'} className="h-[34px] px-3 rounded border border-red-400/30 text-red-400 hover:bg-red-400/10 disabled:opacity-30"><Trash2 className="w-4 h-4" /></button>
          </div>
        </div>
        {customProfile ? <>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <div className="max-h-44 overflow-y-auto rounded-lg border border-shogun-border p-2 space-y-1">
            {models.filter(item => item.enabled).map(item => {
              const selected = customModels.includes(item.id);
              return <button key={item.id} onClick={() => setCustomModels(current => selected ? current.filter(id => id !== item.id) : [...current, item.id])}
                className={`w-full flex items-center justify-between gap-2 rounded p-2 text-left text-xs border ${selected ? 'border-amber-400/50 bg-amber-400/10' : 'border-transparent hover:border-shogun-border'}`}>
                <span className="truncate"><strong>{item.display_name}</strong><span className="ml-2 text-[9px] text-shogun-subdued">{item.provider}</span></span>
                {selected && <CheckCircle2 className="w-3.5 h-3.5 text-amber-300 shrink-0" />}
              </button>;
            })}
          </div>
          <div className="rounded-lg border border-shogun-border p-2 space-y-1">
            {customModels.map((id, index) => {
              const item = models.find(model => model.id === id);
              if (!item) return null;
              return <div key={id} className="flex items-center gap-2 rounded bg-[#080b14] border border-shogun-border p-2">
                <span className="w-16 text-[8px] font-bold uppercase text-amber-300">{index === 0 ? 'Primary' : `Fallback ${index}`}</span>
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
      </div>}
    </div>

    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
      <div className={`xl:col-span-2 shogun-card transition-colors ${registryEditable ? 'border-amber-400/25' : ''}`}>
        <div className="flex items-start justify-between gap-3 mb-3"><div><h4 className="font-bold flex items-center gap-2"><Server className="w-4 h-4 text-shogun-blue" /> Model Capability Registry</h4>
          <p className="text-[10px] text-shogun-subdued mt-1">Describe what each connected model can do, how capable it is, what it costs, and how quickly it responds. The router uses these as eligibility and preference signals.</p></div><button onClick={load} title="Refresh model registry"><RefreshCw className="w-4 h-4" /></button></div>
        <div className={`mb-4 flex items-start gap-2 rounded-lg border px-3 py-2 ${registryEditable ? 'border-amber-400/30 bg-amber-400/[0.07]' : 'border-cyan-400/20 bg-cyan-400/[0.05]'}`}>
          {registryEditable ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" /> : <LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-cyan-300" />}
          <div>
            <p className={`text-[10px] font-bold uppercase tracking-wider ${registryEditable ? 'text-amber-300' : 'text-cyan-300'}`}>{registryEditable ? 'Custom profile · editing enabled' : 'Automatic profile · registry locked'}</p>
            <p className="mt-0.5 text-[9px] leading-relaxed text-shogun-subdued">{registryEditable
              ? `${activeProfile?.name || 'Custom'} uses your model settings and exact primary/fallback order.`
              : `${activeProfile?.name || 'Balanced'} ranks eligible models for each task and chooses one primary plus up to two fallbacks automatically.`}</p>
          </div>
        </div>
        <div className="space-y-3 max-h-[560px] overflow-y-auto pr-1">
          {models.map(item => <div key={item.id} className={`rounded-xl border p-4 transition-opacity ${item.enabled ? 'border-shogun-border bg-[#080b14]' : 'border-shogun-border/40 opacity-60'} ${registryEditable ? '' : 'opacity-70'}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div><div className="flex items-center gap-2 flex-wrap"><span className="font-bold font-mono text-sm text-shogun-text">{item.model_id}</span><span className="text-[9px] font-bold uppercase tracking-widest border border-purple-400/30 bg-purple-500/10 text-purple-300 rounded px-1.5 py-0.5">{item.provider}</span>{item.local && <span className="text-[8px] uppercase border border-shogun-border rounded px-1.5 py-0.5">local</span>}</div>
                <p className="font-mono text-[9px] text-shogun-subdued mt-1">{item.display_name !== item.model_id ? `${item.display_name} · ` : ''}{(item.context_window / 1000).toFixed(0)}K effective context · {item.config_json?.context_limit_mode === 'manual' ? 'manual' : 'auto'}</p></div>
              <div className="flex items-center gap-2"><button onClick={() => verifyToolCalling(item)} disabled={busy === `tools-${item.id}`} className="px-2 py-1 text-[9px] border border-purple-400/40 text-purple-300 rounded hover:bg-purple-400/10 disabled:cursor-not-allowed disabled:opacity-35">{busy === `tools-${item.id}` ? 'Verifying…' : 'Verify tools'}</button><button onClick={() => testModel(item)} disabled={!registryEditable} className="px-2 py-1 text-[9px] border border-shogun-border rounded hover:border-shogun-blue disabled:cursor-not-allowed disabled:opacity-35">{busy === `test-${item.id}` ? 'Testing…' : 'Test'}</button>
                <button onClick={() => patchModel(item, { enabled: !item.enabled })} disabled={!registryEditable} aria-label={`${item.enabled ? 'Disable' : 'Enable'} ${item.display_name}`} className={`w-10 h-5 rounded-full p-0.5 disabled:cursor-not-allowed disabled:opacity-35 ${item.enabled ? 'bg-green-500' : 'bg-gray-700'}`}><span className={`block w-4 h-4 bg-white rounded-full transition-transform ${item.enabled ? 'translate-x-5' : ''}`} /></button></div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 my-3">
              {(['quality_tier','cost_tier','latency_tier'] as const).map(key => {
                const selected = TIER_OPTIONS[key].find(option => option.value === item[key]) || TIER_OPTIONS[key][2];
                return <label key={key} className="text-[9px] uppercase text-shogun-subdued">{key.replace('_tier','')}
                  <select value={item[key]} disabled={!registryEditable} onChange={event => patchModel(item, { [key]: Number(event.target.value) })} className="block w-full mt-1 bg-[#050508] border border-shogun-border rounded p-1.5 text-xs normal-case disabled:cursor-not-allowed disabled:opacity-50">
                    {TIER_OPTIONS[key].map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                  <span className="block mt-1 text-[8px] normal-case leading-tight text-shogun-subdued/70">{selected.help}</span>
                </label>;
              })}
            </div>
            <TokenBudgetControls item={item} disabled={!registryEditable || busy === item.id} onPatch={patch => patchModel(item, patch)} />
            <ToolCallingStatus item={item} />
            {usage.by_model?.[`${item.provider}:${item.model_id}`] && (() => {
              const modelUsage = usage.by_model[`${item.provider}:${item.model_id}`];
              const peakPercent = Math.min(100, Number(modelUsage.peak_context_percent || 0));
              return <div className="mb-3 rounded-lg border border-shogun-border bg-[#050508] p-2.5">
                <div className="flex flex-wrap justify-between gap-2 text-[9px] text-shogun-subdued">
                  <span><strong className="text-shogun-text">{modelUsage.events}</strong> requests</span>
                  <span><strong className="text-shogun-text">{Number(modelUsage.input_tokens).toLocaleString()}</strong> input tokens</span>
                  <span><strong className="text-shogun-text">{Number(modelUsage.output_tokens).toLocaleString()}</strong> output tokens</span>
                  <span>Peak context <strong className="text-cyan-300">{modelUsage.peak_context_percent}%</strong></span>
                </div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-shogun-border/60" title={`Peak ${modelUsage.peak_input_tokens} of ${item.context_window} tokens; average ${modelUsage.average_context_percent}%`}>
                  <div className={`h-full rounded-full ${peakPercent >= 90 ? 'bg-red-400' : peakPercent >= 70 ? 'bg-yellow-400' : 'bg-cyan-400'}`} style={{ width: `${peakPercent}%` }} />
                </div>
                <p className="mt-1 text-[8px] text-shogun-subdued/70">Estimated context use: {modelUsage.average_context_percent}% average · {Number(modelUsage.peak_input_tokens).toLocaleString()} tokens peak</p>
              </div>;
            })()}
            <p className="text-[8px] uppercase tracking-wider text-shogun-subdued mb-1.5">{registryEditable ? 'Supported task capabilities — click to enable or disable' : 'Supported task capabilities — read-only for fixed profiles'}</p>
            <div className="flex flex-wrap gap-1.5">{CAPS.map(cap => <button key={cap} disabled={!registryEditable} onClick={() => patchModel(item, { capabilities: { ...item.capabilities, [cap]: !item.capabilities?.[cap] } })}
              className={`text-[8px] uppercase px-2 py-1 rounded border disabled:cursor-not-allowed disabled:opacity-50 ${item.capabilities?.[cap] ? 'border-cyan-400/40 bg-cyan-400/10 text-cyan-300' : 'border-shogun-border text-shogun-subdued'}`}>{CAP_LABELS[cap]}</button>)}</div>
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
          {decision && <div className="mt-4 p-3 rounded-lg border border-green-400/30 bg-green-400/5">
            <p className="text-[8px] font-bold uppercase tracking-wider text-green-300/70">Primary model</p>
            <div className="font-bold text-sm text-green-300">{decision.selected_model}</div>
            <div className="text-[9px] text-shogun-subdued">{decision.selected_provider} · temperature {(decision.selected_temperature ?? 0.3).toFixed(2)}</div>
            <div className="mt-3 grid gap-1.5">
              {(decision.fallback_models?.length
                ? decision.fallback_models
                : decision.fallback_model
                  ? [{ model_id: decision.fallback_model, display_name: decision.fallback_model, provider: '' }]
                  : []
              ).map((fallback, index) => <div key={`${fallback.provider}:${fallback.model_id}`} className="flex items-center justify-between gap-2 rounded border border-shogun-border bg-[#080b14] px-2 py-1.5">
                <span className="text-[8px] font-bold uppercase text-shogun-subdued">Fallback {index + 1}</span>
                <span className="truncate text-[9px]">{fallback.display_name || fallback.model_id}{fallback.provider ? ` · ${fallback.provider}` : ''} · temp {(fallback.temperature ?? 0.3).toFixed(2)}</span>
              </div>)}
              {!decision.fallback_models?.length && !decision.fallback_model && <p className="text-[9px] text-shogun-subdued">No other eligible model is currently available.</p>}
            </div>
            <p className="text-[10px] mt-3 leading-relaxed">{decision.reason}</p>
            <div className="flex flex-wrap gap-3 mt-2 text-[8px] uppercase text-shogun-subdued"><span>{COMPLEXITY_LABELS[Math.max(1, Math.min(5, decision.complexity_score)) - 1]} task</span><span>{TIER_OPTIONS.cost_tier.find(option => option.value === decision.estimated_cost_tier)?.label || 'Unknown cost'}</span><span>{TIER_OPTIONS.latency_tier.find(option => option.value === decision.estimated_latency_tier)?.label || 'Unknown speed'}</span></div>
          </div>}
        </div>
        <div className="shogun-card"><h4 className="font-bold flex items-center gap-2 mb-3"><Activity className="w-4 h-4 text-green-400" /> Usage</h4><div className="grid grid-cols-2 gap-2 text-center">
          <Metric icon={<Zap className="w-3 h-3" />} label="Events" value={usage.events || 0} /><Metric icon={<Gauge className="w-3 h-3" />} label="Avg latency" value={`${usage.average_latency_ms || 0} ms`} />
          <Metric label="Input tokens" value={Number(usage.input_tokens || 0).toLocaleString()} /><Metric label="Output tokens" value={Number(usage.output_tokens || 0).toLocaleString()} /></div>
          <p className="mt-3 text-[8px] text-shogun-subdued/70">Token counts and context utilization are estimated when a provider does not return native usage metadata.</p></div>
      </div>
    </div>
    {message && <div className="text-xs border border-shogun-border rounded-lg px-3 py-2" onClick={() => setMessage('')}>{message}</div>}
  </div>;
}

function Metric({ icon, label, value }: { icon?: React.ReactNode; label: string; value: string | number }) {
  return <div className="rounded-lg border border-shogun-border p-2"><div className="flex items-center justify-center gap-1 text-[8px] uppercase text-shogun-subdued">{icon}{label}</div><div className="font-bold text-sm mt-1">{value}</div></div>;
}

function ToolCallingStatus({ item }: { item: RegistryModel }) {
  const profile = item.config_json?.tool_calling_profile as ToolCallingProfile | undefined;
  const mode = profile?.mode || 'text';
  const status = profile?.status || 'fallback';
  const color = mode === 'native'
    ? 'border-emerald-400/30 bg-emerald-400/[0.06] text-emerald-300'
    : mode === 'text'
      ? 'border-amber-400/30 bg-amber-400/[0.06] text-amber-300'
      : 'border-red-400/30 bg-red-400/[0.06] text-red-300';
  const label = mode === 'native' ? 'Native tool calling' : mode === 'text' ? 'Shogun fallback' : 'Tools unsupported';
  return <div className={`mb-3 rounded-lg border p-2.5 ${color}`}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <span className="text-[9px] font-bold uppercase tracking-wider">{label} · {status}</span>
      <span className="text-[8px] font-mono opacity-75">{profile?.adapter_id || 'shogun_text_v1'}</span>
    </div>
    <p className="mt-1 text-[8px] leading-relaxed opacity-70">
      {profile
        ? `${profile.request_schema} → ${profile.response_schema} · source ${profile.source} · ${Math.round((profile.confidence || 0) * 100)}% confidence`
        : 'Legacy model entry. Refresh the registry to create its persisted tool-calling profile.'}
    </p>
    {profile?.last_tested_at && <p className="mt-1 text-[8px] opacity-60">Last tested {new Date(profile.last_tested_at).toLocaleString()}</p>}
    {profile?.last_error && <p className="mt-1 text-[8px] text-red-300/80">{profile.last_error}</p>}
  </div>;
}

function TokenBudgetControls({ item, disabled, onPatch }: {
  item: RegistryModel;
  disabled: boolean;
  onPatch: (patch: Partial<RegistryModel>) => void;
}) {
  const minimum = 128;
  const context = Math.max(1024, Number(item.context_window) || 8192);
  const outputCeiling = Math.max(minimum, context - minimum);
  const initialOutput = Math.max(minimum, Math.min(Number(item.max_output_tokens) || 4096, outputCeiling));
  const configuredInput = Number(item.config_json?.max_input_tokens);
  const initialInput = Math.max(
    minimum,
    Math.min(Number.isFinite(configuredInput) ? configuredInput : context - initialOutput, context - initialOutput),
  );
  const [inputTokens, setInputTokens] = useState(initialInput);
  const [outputTokens, setOutputTokens] = useState(initialOutput);
  const contextMode = item.config_json?.context_limit_mode === 'manual' ? 'manual' : 'auto';
  const contextSource = String(item.config_json?.context_limit_source || 'detection_unavailable').replaceAll('_', ' ');

  useEffect(() => {
    setInputTokens(initialInput);
    setOutputTokens(initialOutput);
  }, [initialInput, initialOutput, item.id]);

  const configWithInput = (value: number) => ({
    ...(item.config_json || {}),
    max_input_tokens: value,
  });
  const commitInput = () => {
    if (inputTokens !== initialInput) onPatch({ config_json: configWithInput(inputTokens) });
  };
  const commitOutput = () => {
    const clampedInput = Math.min(inputTokens, context - outputTokens);
    const patch: Partial<RegistryModel> = {};
    if (outputTokens !== initialOutput) patch.max_output_tokens = outputTokens;
    if (clampedInput !== initialInput) patch.config_json = configWithInput(clampedInput);
    if (Object.keys(patch).length) onPatch(patch);
  };
  const commitContext = (value: number) => {
    if (value < 1024 || value === context) return;
    const nextOutput = Math.min(outputTokens, value - minimum);
    const nextInput = Math.min(inputTokens, value - nextOutput);
    onPatch({
      context_window: value,
      max_output_tokens: nextOutput,
      config_json: configWithInput(nextInput),
    });
  };
  const commitContextMode = (mode: 'auto' | 'manual') => {
    if (mode === contextMode) return;
    onPatch({ config_json: { ...(item.config_json || {}), context_limit_mode: mode } });
  };

  return <div className="mb-3 rounded-lg border border-shogun-border bg-[#050508] p-3">
    <div className="flex flex-wrap items-end justify-between gap-2">
      <label className="text-[9px] uppercase text-shogun-subdued">Effective runtime context
        <input type="number" min="1024" step="1024" defaultValue={context} disabled={disabled || contextMode === 'auto'}
          onBlur={event => {
            const value = Number(event.currentTarget.value);
            if (value >= 1024) commitContext(value);
            else event.currentTarget.value = String(context);
          }}
          className="ml-2 w-28 rounded border border-shogun-border bg-[#080b14] p-1 text-right font-mono text-[10px] normal-case" />
      </label>
      <span className="text-[8px] text-shogun-subdued">Input + output cannot exceed {context.toLocaleString()} tokens</span>
    </div>
    <div className="mt-2 flex flex-wrap items-center gap-2 rounded border border-cyan-400/20 bg-cyan-400/5 px-2 py-1.5">
      <button type="button" disabled={disabled} onClick={() => commitContextMode('auto')} className={`rounded px-2 py-1 text-[8px] font-bold uppercase ${contextMode === 'auto' ? 'bg-cyan-400/20 text-cyan-200' : 'text-shogun-subdued'}`}>Auto</button>
      <button type="button" disabled={disabled} onClick={() => commitContextMode('manual')} className={`rounded px-2 py-1 text-[8px] font-bold uppercase ${contextMode === 'manual' ? 'bg-amber-400/20 text-amber-200' : 'text-shogun-subdued'}`}>Manual override</button>
      <span className="text-[8px] text-shogun-subdued">Source: {contextSource}. Auto checks the Ollama runtime first, then model/provider metadata.</span>
    </div>
    <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
      <label className="text-[9px] uppercase text-shogun-subdued">
        <span className="flex justify-between gap-2"><span>Max input</span><strong className="font-mono text-cyan-300">{inputTokens.toLocaleString()}</strong></span>
        <input type="range" min={minimum} max={Math.max(minimum, context - outputTokens)} step="128"
          value={inputTokens} disabled={disabled}
          onChange={event => setInputTokens(Number(event.target.value))}
          onPointerUp={commitInput} onKeyUp={commitInput}
          aria-label={`Maximum input tokens for ${item.display_name}`}
          className="mt-2 block w-full accent-cyan-400" />
      </label>
      <label className="text-[9px] uppercase text-shogun-subdued">
        <span className="flex justify-between gap-2"><span>Max output</span><strong className="font-mono text-purple-300">{outputTokens.toLocaleString()}</strong></span>
        <input type="range" min={minimum} max={outputCeiling} step="128"
          value={outputTokens} disabled={disabled}
          onChange={event => {
            const value = Number(event.target.value);
            setOutputTokens(value);
            setInputTokens(current => Math.min(current, context - value));
          }}
          onPointerUp={commitOutput} onKeyUp={commitOutput}
          aria-label={`Maximum output tokens for ${item.display_name}`}
          className="mt-2 block w-full accent-purple-400" />
      </label>
    </div>
  </div>;
}
