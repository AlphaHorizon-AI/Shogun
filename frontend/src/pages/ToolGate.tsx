import { Fragment, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Clock3,
  FlaskConical,
  FolderOpen,
  Loader2,
  LockKeyhole,
  Minus,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
  WifiOff,
  X,
} from 'lucide-react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { cn } from '../lib/utils';

type GateAction = 'allow' | 'confirm' | 'block';
type AdvancedAction = 'confirm' | 'block';
type AdvancedMatchType = 'contains' | 'word';
type TierType = 'shrine' | 'guarded' | 'tactical' | 'campaign' | 'ronin';

interface SecurityPolicy {
  id: string;
  name: string;
  tier: TierType;
  description: string | null;
  permissions: Record<string, Record<string, unknown>>;
  kill_switch_enabled: boolean;
  dry_run_supported: boolean;
  is_builtin: boolean;
}

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

interface FilesystemFolder {
  id: string;
  path: string;
  kind: 'internal' | 'network';
  read: boolean;
  write: boolean;
  create: boolean;
  delete: boolean;
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
  capabilities: {
    permissions: Record<string, Record<string, unknown>>;
    risk_score: number;
    editable: boolean;
    source: 'agent_override' | 'custom_policy' | 'builtin_tier';
  };
  scope: {
    key: string;
    kind: 'tier' | 'custom_policy';
    label: string;
    base_tier: string;
    policy_id: string | null;
  };
  active_tier: string;
  active_campaign_preset: string | null;
  mode: string;
  local_overrides: Record<string, GateAction>;
  advanced_controls: {
    enabled: boolean;
    rules: AdvancedRule[];
    editable: boolean;
    source: 'local' | 'gensui';
  };
  filesystem_controls: {
    enabled: boolean;
    folders: FilesystemFolder[];
    editable: boolean;
    source: 'local' | 'gensui';
  };
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

const COMMS_LABELS: Record<string, string> = {
  allow_read_email: 'Read mail',
  allow_send_email: 'Mail writes (send and delete)',
  allow_read_calendar: 'Read calendar events',
  allow_create_events: 'Calendar writes (create, edit, and delete)',
  allow_list_cron: 'List scheduled jobs',
  allow_manage_cron: 'Manage scheduled jobs',
};

const DEFAULT_POLICY_PERMISSIONS: Record<string, Record<string, unknown>> = {
  filesystem: { mode: 'scoped', allowed_paths: [], allow_home_access: false, allow_arbitrary_paths: false },
  network: { mode: 'allowlist', allowed_domains: [], allow_arbitrary_requests: false },
  shell: { enabled: false, allowed_binaries: [] },
  skills: { allow_auto_install: false, require_approval: true, allow_untrusted: false },
  subagents: { allow_spawn: true, max_active: 5, allow_auto_spawn: false },
  memory: { allow_write: true, allow_bulk_delete: false },
  comms: {
    allow_read_email: true,
    allow_send_email: true,
    allow_read_calendar: true,
    allow_create_events: true,
    allow_list_cron: true,
    allow_manage_cron: false,
  },
  mado_browser: {},
  agentflow: {},
  flow_stack: {},
  visual_intake: {},
  ide_mode: {},
};

const emptyPolicyDraft = (permissions = structuredClone(DEFAULT_POLICY_PERMISSIONS)) => ({
  id: null as string | null,
  name: '',
  tier: 'tactical' as TierType,
  description: '',
  permissions,
  kill_switch_enabled: true,
  dry_run_supported: true,
});

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

function errorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    return error.response?.data?.detail || error.message || fallback;
  }
  return error instanceof Error ? error.message : fallback;
}

export function ToolGate() {
  const navigate = useNavigate();
  const [data, setData] = useState<ToolGateData | null>(null);
  const [policies, setPolicies] = useState<SecurityPolicy[]>([]);
  const [builtInPolicies, setBuiltInPolicies] = useState<SecurityPolicy[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingTool, setSavingTool] = useState<string | null>(null);
  const [expandedTool, setExpandedTool] = useState<string | null>(null);
  const [filesystemDraft, setFilesystemDraft] = useState<{ enabled: boolean; folders: FilesystemFolder[] }>({
    enabled: false,
    folders: [],
  });
  const [savingFilesystem, setSavingFilesystem] = useState(false);
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
  const [capabilityDraft, setCapabilityDraft] = useState<Record<string, Record<string, unknown>>>({});
  const [savingCapabilities, setSavingCapabilities] = useState(false);
  const [advancedDraft, setAdvancedDraft] = useState<{ enabled: boolean; rules: AdvancedRule[] }>({
    enabled: false,
    rules: [],
  });
  const [savingAdvanced, setSavingAdvanced] = useState(false);
  const [showPolicyEditor, setShowPolicyEditor] = useState(false);
  const [policyDraft, setPolicyDraft] = useState(emptyPolicyDraft);
  const [savingPolicy, setSavingPolicy] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [response, policiesResponse] = await Promise.all([
        axios.get('/api/v1/security/toolgate'),
        axios.get('/api/v1/security/policies'),
      ]);
      const payload = response.data.data as ToolGateData;
      const normalized: ToolGateData = {
        ...payload,
        scope: payload.scope || {
          key: `tier:${payload.active_tier || 'tactical'}`,
          kind: 'tier',
          label: (payload.active_tier || 'tactical').toUpperCase(),
          base_tier: payload.active_tier || 'tactical',
          policy_id: null,
        },
        capabilities: payload.capabilities || {
          permissions: {},
          risk_score: 0,
          editable: false,
          source: 'builtin_tier',
        },
        advanced_controls: payload.advanced_controls || {
          enabled: false,
          rules: [],
          editable: payload.authority?.editable ?? true,
          source: payload.authority?.mode === 'gensui' ? 'gensui' : 'local',
        },
        filesystem_controls: payload.filesystem_controls || {
          enabled: false,
          folders: [],
          editable: payload.authority?.editable ?? true,
          source: 'local',
        },
      };
      setData(normalized);
      const policyRecords = (policiesResponse.data.data || []) as SecurityPolicy[];
      setPolicies(policyRecords.filter(policy => !policy.is_builtin));
      setBuiltInPolicies(policyRecords.filter(policy => policy.is_builtin));
      setCapabilityDraft(normalized.capabilities.permissions || {});
      setAdvancedDraft({
        enabled: normalized.advanced_controls.enabled,
        rules: normalized.advanced_controls.rules || [],
      });
      setFilesystemDraft({
        enabled: normalized.filesystem_controls.enabled,
        folders: normalized.filesystem_controls.folders || [],
      });
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
    } catch (error: unknown) {
      setMessage({ type: 'error', text: errorMessage(error, 'ToolGate rule could not be saved.') });
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
    } catch (error: unknown) {
      setMessage({
        type: 'error',
        text: errorMessage(error, 'Simulation failed.'),
      });
    } finally {
      setSimulating(false);
    }
  };

  const updateCapability = (categoryName: string, key: string, value: unknown) => {
    setCapabilityDraft(current => ({
      ...current,
      [categoryName]: {
        ...(current[categoryName] || {}),
        [key]: value,
      },
    }));
  };

  const saveCapabilities = async () => {
    if (!data) return;
    setSavingCapabilities(true);
    setMessage(null);
    try {
      await axios.put('/api/v1/security/toolgate/capabilities', {
        permissions: capabilityDraft,
      });
      setMessage({ type: 'success', text: `Capability boundaries saved for ${data.scope.label}.` });
      await fetchData();
    } catch (error: unknown) {
      setMessage({
        type: 'error',
        text: errorMessage(error, 'Capability boundaries could not be saved.'),
      });
    } finally {
      setSavingCapabilities(false);
    }
  };

  const addAdvancedRule = (toolName?: string) => {
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
          tools: toolName ? [toolName] : [],
          case_sensitive: false,
          enabled: true,
        },
      ],
    }));
  };

  const addFilesystemFolder = () => {
    setFilesystemDraft(current => ({
      ...current,
      enabled: true,
      folders: [
        ...current.folders,
        {
          id: `folder-${Date.now()}`,
          path: '',
          kind: 'internal',
          read: true,
          write: false,
          create: false,
          delete: false,
        },
      ],
    }));
  };

  const updateFilesystemFolder = (id: string, patch: Partial<FilesystemFolder>) => {
    setFilesystemDraft(current => ({
      ...current,
      folders: current.folders.map(folder => folder.id === id ? { ...folder, ...patch } : folder),
    }));
  };

  const saveFilesystemControls = async () => {
    setSavingFilesystem(true);
    setMessage(null);
    try {
      await axios.put('/api/v1/security/toolgate/filesystem', filesystemDraft);
      setMessage({ type: 'success', text: 'Shared filesystem controls saved.' });
      await fetchData();
    } catch (error: unknown) {
      setMessage({ type: 'error', text: errorMessage(error, 'Filesystem controls could not be saved.') });
    } finally {
      setSavingFilesystem(false);
    }
  };

  const updateAdvancedRule = (id: string, patch: Partial<AdvancedRule>) => {
    setAdvancedDraft(current => ({
      ...current,
      rules: current.rules.map(rule => rule.id === id ? { ...rule, ...patch } : rule),
    }));
  };

  const saveAdvancedControls = async () => {
    if (!data) return;
    setSavingAdvanced(true);
    setMessage(null);
    try {
      await axios.put('/api/v1/security/toolgate/advanced', advancedDraft);
      setMessage({ type: 'success', text: `Advanced controls saved for ${data.scope.label}.` });
      await fetchData();
    } catch (error: unknown) {
      setMessage({
        type: 'error',
        text: errorMessage(error, 'Advanced ToolGate controls could not be saved.'),
      });
    } finally {
      setSavingAdvanced(false);
    }
  };

  const openCreatePolicy = () => {
    setPolicyDraft(emptyPolicyDraft(policyDefaultsForTier('tactical')));
    setShowPolicyEditor(true);
  };

  const policyDefaultsForTier = (tier: TierType) => {
    const permissions = structuredClone(DEFAULT_POLICY_PERMISSIONS);
    const preset = builtInPolicies.find(policy => policy.tier === tier);
    Object.entries(preset?.permissions || {}).forEach(([categoryName, values]) => {
      permissions[categoryName] = {
        ...(permissions[categoryName] || {}),
        ...(values || {}),
      };
    });
    return permissions;
  };

  const openEditPolicy = (policy: SecurityPolicy) => {
    const permissions = policyDefaultsForTier(policy.tier);
    Object.entries(policy.permissions || {}).forEach(([categoryName, values]) => {
      permissions[categoryName] = {
        ...(permissions[categoryName] || {}),
        ...(values || {}),
      };
    });
    setPolicyDraft({
      id: policy.id,
      name: policy.name,
      tier: policy.tier,
      description: policy.description || '',
      permissions,
      kill_switch_enabled: policy.kill_switch_enabled,
      dry_run_supported: policy.dry_run_supported,
    });
    setShowPolicyEditor(true);
  };

  const updatePolicyPermission = (categoryName: string, key: string, value: unknown) => {
    setPolicyDraft(current => ({
      ...current,
      permissions: {
        ...current.permissions,
        [categoryName]: {
          ...(current.permissions[categoryName] || {}),
          [key]: value,
        },
      },
    }));
  };

  const savePolicy = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!data || !data.authority.editable || !policyDraft.name.trim()) return;
    setSavingPolicy(true);
    setMessage(null);
    const body = {
      name: policyDraft.name.trim(),
      tier: policyDraft.tier,
      description: policyDraft.description.trim(),
      permissions: policyDraft.permissions,
      kill_switch_enabled: policyDraft.kill_switch_enabled,
      dry_run_supported: policyDraft.dry_run_supported,
    };
    try {
      if (policyDraft.id) {
        await axios.patch(`/api/v1/security/policies/${policyDraft.id}`, body);
        setMessage({ type: 'success', text: `${body.name} was updated.` });
      } else {
        await axios.post('/api/v1/security/policies', body);
        setMessage({ type: 'success', text: `${body.name} was created and is now available in Torii.` });
      }
      setShowPolicyEditor(false);
      await fetchData();
    } catch (error: unknown) {
      setMessage({ type: 'error', text: errorMessage(error, 'Custom posture could not be saved.') });
    } finally {
      setSavingPolicy(false);
    }
  };

  const deletePolicy = async (policy: SecurityPolicy) => {
    if (!data || !data.authority.editable || !confirm(`Delete custom posture "${policy.name}"?`)) return;
    const wasActive = data.scope.policy_id === policy.id;
    setMessage(null);
    try {
      await axios.delete(`/api/v1/security/policies/${policy.id}`);
      setMessage({
        type: 'success',
        text: `${policy.name} was deleted.${wasActive ? ` Torii returned to its ${policy.tier.toUpperCase()} base tier.` : ''}`,
      });
      await fetchData();
    } catch (error: unknown) {
      setMessage({ type: 'error', text: errorMessage(error, 'Custom posture could not be deleted.') });
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
                  : `Overrides are saved only for ${data.scope.label}. Switching tier or custom policy loads that scope's own ToolGate rules.`}
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

      <div className="shogun-card space-y-4">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-violet-300" />
              <h2 className="text-sm font-bold uppercase tracking-widest text-shogun-text">Custom posture library</h2>
            </div>
            <p className="mt-1 max-w-3xl text-xs leading-relaxed text-shogun-subdued">
              Create and maintain reusable security postures here. Torii remains the single place where a built-in or custom posture is activated.
            </p>
          </div>
          <button
            type="button"
            disabled={!data.authority.editable}
            onClick={openCreatePolicy}
            className="flex items-center gap-2 self-start rounded-lg border border-violet-400/30 bg-violet-500/10 px-3 py-2 text-xs font-bold text-violet-200 hover:bg-violet-500/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Plus className="h-4 w-4" /> Create custom posture
          </button>
        </div>

        {managed && (
          <div className="flex gap-2 rounded-lg border border-indigo-400/20 bg-indigo-500/[0.05] p-3">
            <LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-indigo-300" />
            <p className="text-xs leading-relaxed text-indigo-100/75">
              Custom posture lifecycle is centrally owned by Gensui while this Tenshu is enrolled.
            </p>
          </div>
        )}

        {policies.length === 0 ? (
          <div className="rounded-lg border border-dashed border-shogun-border p-6 text-center">
            <p className="text-xs font-bold text-shogun-text">No custom postures yet</p>
            <p className="mt-1 text-[10px] text-shogun-subdued">Create one here; it will immediately appear in Torii's posture selector.</p>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {policies.map(policy => {
              const active = data.scope.policy_id === policy.id;
              return (
                <div
                  key={policy.id}
                  className={cn(
                    'rounded-lg border p-4',
                    active ? 'border-violet-400/45 bg-violet-500/[0.07]' : 'border-shogun-border/70 bg-shogun-bg/45',
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="truncate text-sm font-bold text-shogun-text">{policy.name}</p>
                        {active && <span className="rounded border border-emerald-400/25 bg-emerald-500/10 px-1.5 py-0.5 text-[8px] font-bold uppercase text-emerald-300">Active</span>}
                      </div>
                      <p className="mt-1 text-[9px] font-bold uppercase tracking-widest text-violet-300">
                        Base {policy.tier}
                      </p>
                    </div>
                    <div className="flex shrink-0 gap-1">
                      <button
                        type="button"
                        disabled={!data.authority.editable}
                        onClick={() => openEditPolicy(policy)}
                        className="rounded border border-shogun-border p-2 text-shogun-subdued hover:border-violet-400/30 hover:text-violet-200 disabled:opacity-40"
                        title="Edit custom posture"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        disabled={!data.authority.editable}
                        onClick={() => deletePolicy(policy)}
                        className="rounded border border-red-500/15 p-2 text-red-300/70 hover:bg-red-500/10 hover:text-red-300 disabled:opacity-40"
                        title="Delete custom posture"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                  <p className="mt-3 line-clamp-2 min-h-8 text-[10px] leading-relaxed text-shogun-subdued">
                    {policy.description || 'No description'}
                  </p>
                  <div className="mt-3 flex gap-2 text-[9px] uppercase tracking-wider text-shogun-subdued">
                    <span>{Object.keys(policy.permissions || {}).length} capability groups</span>
                    <span>·</span>
                    <span>{policy.kill_switch_enabled ? 'Kill switch' : 'No kill switch'}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {[
          { label: data.scope.kind === 'custom_policy' ? 'Custom tier' : 'Active tier', value: data.scope.label, color: 'text-shogun-gold' },
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

      <div className="shogun-card space-y-5">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-shogun-gold" />
              <h2 className="text-sm font-bold uppercase tracking-widest text-shogun-text">Capability boundaries</h2>
            </div>
            <p className="mt-1 max-w-3xl text-xs leading-relaxed text-shogun-subdued">
              The policy ceiling for filesystem, network, applications, workflows, memory, and delegation. Runtime tool verdicts below can only narrow these capabilities.
            </p>
          </div>
          <div className="min-w-56 rounded-lg border border-shogun-border bg-shogun-bg/70 p-3">
            <div className="flex items-center justify-between text-[9px] font-bold uppercase tracking-widest text-shogun-subdued">
              <span>Capability Risk Index</span>
              <span className={cn(
                data.capabilities.risk_score <= 25 ? 'text-emerald-400'
                  : data.capabilities.risk_score <= 50 ? 'text-shogun-gold'
                    : data.capabilities.risk_score <= 75 ? 'text-orange-400' : 'text-red-400',
              )}>{data.capabilities.risk_score}/100</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-black/40">
              <div
                className={cn(
                  'h-full rounded-full transition-all',
                  data.capabilities.risk_score <= 25 ? 'bg-emerald-400'
                    : data.capabilities.risk_score <= 50 ? 'bg-shogun-gold'
                      : data.capabilities.risk_score <= 75 ? 'bg-orange-400' : 'bg-red-500',
                )}
                style={{ width: `${data.capabilities.risk_score}%` }}
              />
            </div>
          </div>
        </div>

        {!data.capabilities.editable && (
          <div className="flex items-start justify-between gap-4 rounded-lg border border-amber-400/20 bg-amber-500/[0.05] p-3">
            <div className="flex gap-2">
              <LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
              <p className="text-xs leading-relaxed text-amber-100/75">
                {managed
                  ? 'Capability boundaries are centrally owned by Gensui.'
                  : 'Built-in tiers are protected presets. Create or edit custom postures in the library above; activate one in Torii to inspect it here.'}
              </p>
            </div>
            {!managed && (
              <button onClick={() => navigate('/torii')} className="shrink-0 text-xs font-bold text-shogun-gold hover:text-white">
                Select in Torii
              </button>
            )}
          </div>
        )}

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {Object.entries(capabilityDraft).map(([categoryName, permissions]) => (
            <div key={categoryName} className="rounded-lg border border-shogun-border/70 bg-shogun-bg/45 p-3">
              <p className="mb-3 text-[10px] font-bold uppercase tracking-[0.18em] text-shogun-gold">
                {categoryName.replace(/_/g, ' ')}
              </p>
              {categoryName === 'comms' && (
                <p className="mb-3 text-[9px] leading-relaxed text-shogun-subdued">
                  Single authority for Comms, Mail, and Calendar. These rules also govern direct UI actions.
                </p>
              )}
              <div className="space-y-2">
                {Object.entries(permissions || {}).map(([key, value]) => (
                  <label key={key} className="flex min-h-8 items-center justify-between gap-3 text-[10px] text-shogun-subdued">
                    <span className="capitalize">{categoryName === 'comms' ? COMMS_LABELS[key] || key.replace(/_/g, ' ') : key.replace(/_/g, ' ')}</span>
                    {typeof value === 'boolean' ? (
                      <button
                        type="button"
                        disabled={!data.capabilities.editable}
                        onClick={() => updateCapability(categoryName, key, !value)}
                        className={cn(
                          'relative h-5 w-10 rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-55',
                          value ? 'border-emerald-500/40 bg-emerald-500/20' : 'border-red-500/30 bg-red-500/10',
                        )}
                      >
                        <span className={cn(
                          'absolute top-0.5 h-4 w-4 rounded-full transition-all',
                          value ? 'left-5 bg-emerald-400' : 'left-0.5 bg-red-400',
                        )} />
                      </button>
                    ) : typeof value === 'number' ? (
                      <input
                        type="number"
                        disabled={!data.capabilities.editable}
                        value={value}
                        onChange={event => updateCapability(categoryName, key, Number(event.target.value))}
                        className="w-20 rounded border border-shogun-border bg-shogun-bg px-2 py-1 text-right text-[10px] text-shogun-text disabled:opacity-55"
                      />
                    ) : Array.isArray(value) ? (
                      <input
                        disabled={!data.capabilities.editable}
                        value={value.join(', ')}
                        onChange={event => updateCapability(
                          categoryName,
                          key,
                          event.target.value.split(',').map(item => item.trim()).filter(Boolean),
                        )}
                        placeholder="Comma-separated"
                        className="w-44 rounded border border-shogun-border bg-shogun-bg px-2 py-1 text-right text-[10px] text-shogun-text disabled:opacity-55"
                      />
                    ) : key === 'mode' ? (
                      <select
                        disabled={!data.capabilities.editable}
                        value={String(value)}
                        onChange={event => updateCapability(categoryName, key, event.target.value)}
                        className="rounded border border-shogun-border bg-shogun-bg px-2 py-1 text-[10px] uppercase text-shogun-text disabled:opacity-55"
                      >
                        {['full', 'scoped', 'allowlist', 'disabled'].map(option => <option key={option} value={option}>{option}</option>)}
                      </select>
                    ) : (
                      <input
                        disabled={!data.capabilities.editable}
                        value={String(value ?? '')}
                        onChange={event => updateCapability(categoryName, key, event.target.value)}
                        className="w-36 rounded border border-shogun-border bg-shogun-bg px-2 py-1 text-right text-[10px] text-shogun-text disabled:opacity-55"
                      />
                    )}
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>

        {data.capabilities.editable && (
          <div className="flex justify-end">
            <button
              onClick={saveCapabilities}
              disabled={savingCapabilities}
              className="flex items-center gap-2 rounded-lg bg-shogun-gold px-4 py-2.5 text-xs font-bold text-black disabled:opacity-50"
            >
              {savingCapabilities ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Save capability boundaries
            </button>
          </div>
        )}
      </div>

      <div className="shogun-card space-y-5">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <div className="flex items-center gap-2">
              <SlidersHorizontal className="h-4 w-4 text-orange-400" />
              <h2 className="text-sm font-bold uppercase tracking-widest text-shogun-text">Advanced controls</h2>
              <span className="rounded border border-orange-400/20 bg-orange-500/10 px-2 py-1 text-[9px] font-bold uppercase tracking-widest text-orange-300">
                Content-aware
              </span>
            </div>
            <p className="mt-1 max-w-3xl text-xs leading-relaxed text-shogun-subdued">
              Flag words or phrases inside tool arguments and require confirmation or block the call. Rules can apply globally or only to one tool and never weaken a stricter safety decision.
            </p>
          </div>
          <button
            type="button"
            disabled={!data.advanced_controls.editable}
            onClick={() => setAdvancedDraft(current => ({ ...current, enabled: !current.enabled }))}
            className={cn(
              'flex items-center gap-3 rounded-lg border px-3 py-2 text-xs font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-55',
              advancedDraft.enabled
                ? 'border-orange-400/35 bg-orange-500/10 text-orange-200'
                : 'border-shogun-border bg-shogun-bg text-shogun-subdued',
            )}
          >
            <span className={cn(
              'relative h-5 w-10 rounded-full border',
              advancedDraft.enabled ? 'border-orange-400/40 bg-orange-500/20' : 'border-shogun-border bg-black/30',
            )}>
              <span className={cn(
                'absolute top-0.5 h-4 w-4 rounded-full transition-all',
                advancedDraft.enabled ? 'left-5 bg-orange-300' : 'left-0.5 bg-shogun-subdued',
              )} />
            </span>
            Advanced mode {advancedDraft.enabled ? 'on' : 'off'}
          </button>
        </div>

        {!data.advanced_controls.editable && (
          <div className="flex gap-2 rounded-lg border border-indigo-400/20 bg-indigo-500/[0.05] p-3">
            <LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-indigo-300" />
            <p className="text-xs leading-relaxed text-indigo-100/75">
              These content rules are centrally owned by Gensui and remain enforced from the cached policy if the connection is temporarily unavailable.
            </p>
          </div>
        )}

        <div className="rounded-xl border border-cyan-400/20 bg-cyan-500/[0.04] p-4">
          <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
            <div>
              <div className="flex items-center gap-2">
                <FolderOpen className="h-4 w-4 text-cyan-300" />
                <p className="text-xs font-bold uppercase tracking-widest text-shogun-text">File access</p>
                <span className="rounded border border-cyan-400/20 bg-cyan-500/10 px-2 py-1 text-[9px] font-bold uppercase tracking-widest text-cyan-200">
                  One shared setup
                </span>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-shogun-subdued">
                Add each local or network folder once, then choose exactly which operations all file tools may perform there.
              </p>
            </div>
            <button
              type="button"
              disabled={!data.filesystem_controls.editable}
              onClick={() => setFilesystemDraft(current => ({ ...current, enabled: !current.enabled }))}
              className={cn(
                'flex items-center gap-3 rounded-lg border px-3 py-2 text-xs font-bold disabled:cursor-not-allowed disabled:opacity-55',
                filesystemDraft.enabled
                  ? 'border-cyan-400/35 bg-cyan-500/10 text-cyan-200'
                  : 'border-shogun-border bg-shogun-bg text-shogun-subdued',
              )}
            >
              <span className={cn(
                'relative h-5 w-10 rounded-full border',
                filesystemDraft.enabled ? 'border-cyan-400/40 bg-cyan-500/20' : 'border-shogun-border bg-black/30',
              )}>
                <span className={cn(
                  'absolute top-0.5 h-4 w-4 rounded-full transition-all',
                  filesystemDraft.enabled ? 'left-5 bg-cyan-300' : 'left-0.5 bg-shogun-subdued',
                )} />
              </span>
              Folder permissions {filesystemDraft.enabled ? 'on' : 'off'}
            </button>
          </div>

          <div className="mt-4 overflow-x-auto rounded-lg border border-shogun-border/70">
            <div className="min-w-[760px]">
              <div className="grid grid-cols-[minmax(260px,1fr)_110px_repeat(4,76px)_44px] bg-[#080b12] px-3 py-2 text-center text-[9px] font-bold uppercase tracking-widest text-shogun-subdued">
                <span className="text-left">Folder</span>
                <span>Type</span>
                <span>Read</span>
                <span>Write</span>
                <span>Create</span>
                <span>Delete</span>
                <span />
              </div>
              {filesystemDraft.folders.map(folder => (
                <div key={folder.id} className="grid grid-cols-[minmax(260px,1fr)_110px_repeat(4,76px)_44px] items-center gap-0 border-t border-shogun-border/60 px-3 py-2">
                  <input
                    value={folder.path}
                    disabled={!data.filesystem_controls.editable}
                    onChange={event => updateFilesystemFolder(folder.id, { path: event.target.value })}
                    placeholder={folder.kind === 'network' ? '\\\\server\\share\\folder' : 'input, output, or C:\\Approved'}
                    className="mr-2 rounded-md border border-shogun-border bg-shogun-bg px-3 py-2 font-mono text-xs text-shogun-text outline-none focus:border-cyan-400 disabled:opacity-45"
                  />
                  <select
                    value={folder.kind}
                    disabled={!data.filesystem_controls.editable}
                    onChange={event => updateFilesystemFolder(folder.id, { kind: event.target.value as FilesystemFolder['kind'] })}
                    className="mr-2 rounded-md border border-shogun-border bg-shogun-bg px-2 py-2 text-xs text-shogun-text disabled:opacity-45"
                  >
                    <option value="internal">Internal</option>
                    <option value="network">Network</option>
                  </select>
                  {(['read', 'write', 'create', 'delete'] as const).map(operation => (
                    <label key={operation} className="flex justify-center">
                      <input
                        type="checkbox"
                        checked={folder[operation]}
                        disabled={!data.filesystem_controls.editable}
                        onChange={event => updateFilesystemFolder(folder.id, { [operation]: event.target.checked })}
                        className="h-4 w-4 accent-cyan-400"
                        aria-label={`${operation} permission for ${folder.path || 'folder'}`}
                      />
                    </label>
                  ))}
                  <button
                    type="button"
                    disabled={!data.filesystem_controls.editable}
                    onClick={() => setFilesystemDraft(current => ({
                      ...current,
                      folders: current.folders.filter(item => item.id !== folder.id),
                    }))}
                    className="rounded p-2 text-red-300 hover:bg-red-500/10 disabled:opacity-45"
                    title="Remove folder"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
              {filesystemDraft.folders.length === 0 && (
                <p className="border-t border-shogun-border/60 px-4 py-6 text-center text-xs text-shogun-subdued">
                  No folders configured. Add a folder to begin.
                </p>
              )}
            </div>
          </div>

          {data.filesystem_controls.editable && (
            <div className="mt-3 flex flex-wrap justify-between gap-3">
              <button
                type="button"
                onClick={addFilesystemFolder}
                className="flex items-center gap-2 rounded-lg border border-cyan-400/25 px-3 py-2 text-xs font-bold text-cyan-200 hover:bg-cyan-500/10"
              >
                <Plus className="h-4 w-4" /> Add folder
              </button>
              <button
                type="button"
                onClick={saveFilesystemControls}
                disabled={savingFilesystem || filesystemDraft.folders.some(folder => !folder.path.trim())}
                className="flex items-center gap-2 rounded-lg bg-cyan-300 px-4 py-2.5 text-xs font-bold text-black disabled:opacity-50"
              >
                {savingFilesystem ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Save file access
              </button>
            </div>
          )}
        </div>

        <div className="space-y-3">
          {advancedDraft.rules.map((rule, index) => (
            <div key={rule.id} className="rounded-lg border border-shogun-border/70 bg-shogun-bg/45 p-4">
              <div className="grid gap-3 xl:grid-cols-[minmax(150px,0.8fr)_minmax(220px,1.4fr)_130px_130px_minmax(180px,1fr)_auto] xl:items-end">
                <label className="space-y-1">
                  <span className="text-[9px] font-bold uppercase tracking-widest text-shogun-subdued">Rule label</span>
                  <input
                    disabled={!data.advanced_controls.editable}
                    value={rule.label}
                    onChange={event => updateAdvancedRule(rule.id, { label: event.target.value })}
                    placeholder={`Rule ${index + 1}`}
                    maxLength={120}
                    className="w-full rounded border border-shogun-border bg-shogun-bg px-3 py-2 text-xs text-shogun-text disabled:opacity-55"
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-[9px] font-bold uppercase tracking-widest text-shogun-subdued">Word or phrase</span>
                  <input
                    disabled={!data.advanced_controls.editable}
                    value={rule.pattern}
                    onChange={event => updateAdvancedRule(rule.id, { pattern: event.target.value })}
                    placeholder="e.g. confidential"
                    maxLength={200}
                    className="w-full rounded border border-shogun-border bg-shogun-bg px-3 py-2 font-mono text-xs text-shogun-text disabled:opacity-55"
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-[9px] font-bold uppercase tracking-widest text-shogun-subdued">Match</span>
                  <select
                    disabled={!data.advanced_controls.editable}
                    value={rule.match_type}
                    onChange={event => updateAdvancedRule(rule.id, { match_type: event.target.value as AdvancedMatchType })}
                    className="w-full rounded border border-shogun-border bg-shogun-bg px-2 py-2 text-xs text-shogun-text disabled:opacity-55"
                  >
                    <option value="contains">Contains</option>
                    <option value="word">Whole word</option>
                  </select>
                </label>
                <label className="space-y-1">
                  <span className="text-[9px] font-bold uppercase tracking-widest text-shogun-subdued">Verdict</span>
                  <select
                    disabled={!data.advanced_controls.editable}
                    value={rule.action}
                    onChange={event => updateAdvancedRule(rule.id, { action: event.target.value as AdvancedAction })}
                    className={cn('w-full rounded border px-2 py-2 text-xs font-bold uppercase disabled:opacity-55', ACTION_STYLES[rule.action])}
                  >
                    <option value="confirm">Confirm</option>
                    <option value="block">Block</option>
                  </select>
                </label>
                <label className="space-y-1">
                  <span className="text-[9px] font-bold uppercase tracking-widest text-shogun-subdued">Applies to</span>
                  <select
                    disabled={!data.advanced_controls.editable}
                    value={rule.tools[0] || '*'}
                    onChange={event => updateAdvancedRule(rule.id, { tools: event.target.value === '*' ? [] : [event.target.value] })}
                    className="w-full rounded border border-shogun-border bg-shogun-bg px-2 py-2 font-mono text-xs text-shogun-text disabled:opacity-55"
                  >
                    <option value="*">All tools</option>
                    {data.tools.map(tool => <option key={tool.name} value={tool.name}>{tool.name}</option>)}
                  </select>
                </label>
                <div className="flex items-center justify-end gap-2">
                  <button
                    type="button"
                    disabled={!data.advanced_controls.editable}
                    onClick={() => updateAdvancedRule(rule.id, { enabled: !rule.enabled })}
                    className={cn(
                      'rounded border px-2.5 py-2 text-[9px] font-bold uppercase disabled:opacity-55',
                      rule.enabled ? 'border-emerald-500/25 text-emerald-300' : 'border-shogun-border text-shogun-subdued',
                    )}
                  >
                    {rule.enabled ? 'Active' : 'Paused'}
                  </button>
                  <button
                    type="button"
                    disabled={!data.advanced_controls.editable}
                    onClick={() => setAdvancedDraft(current => ({
                      ...current,
                      rules: current.rules.filter(item => item.id !== rule.id),
                    }))}
                    className="rounded border border-red-500/20 p-2 text-red-300 hover:bg-red-500/10 disabled:opacity-55"
                    title="Remove rule"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
              <label className="mt-3 flex items-center gap-2 text-[10px] text-shogun-subdued">
                <input
                  type="checkbox"
                  disabled={!data.advanced_controls.editable}
                  checked={rule.case_sensitive}
                  onChange={event => updateAdvancedRule(rule.id, { case_sensitive: event.target.checked })}
                />
                Case-sensitive match
              </label>
            </div>
          ))}
          {advancedDraft.rules.length === 0 && (
            <div className="rounded-lg border border-dashed border-shogun-border p-6 text-center text-xs text-shogun-subdued">
              No advanced content rules are defined for this policy.
            </div>
          )}
        </div>

        {data.advanced_controls.editable && (
          <div className="flex flex-wrap justify-between gap-3">
            <button
              type="button"
              onClick={() => addAdvancedRule()}
              className="flex items-center gap-2 rounded-lg border border-orange-400/25 px-3 py-2 text-xs font-bold text-orange-300 hover:bg-orange-500/10"
            >
              <Plus className="h-4 w-4" /> Add content rule
            </button>
            <button
              type="button"
              onClick={saveAdvancedControls}
              disabled={savingAdvanced || advancedDraft.rules.some(rule => !rule.pattern.trim())}
              className="flex items-center gap-2 rounded-lg bg-orange-400 px-4 py-2.5 text-xs font-bold text-black disabled:opacity-50"
            >
              {savingAdvanced ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Save advanced controls
            </button>
          </div>
        )}
      </div>

      <div className="shogun-card space-y-4">
        <div className="flex flex-col justify-between gap-3 lg:flex-row lg:items-center">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-widest text-shogun-text">Effective tool policy</h2>
            <p className="mt-1 text-xs text-shogun-subdued">
              {data.scope.kind === 'custom_policy'
                ? `${data.scope.label} inherits ${data.scope.base_tier.toUpperCase()} thresholds; its ToolGate overrides remain isolated from every other tier.`
                : `Default ${data.scope.base_tier.toUpperCase()} thresholds plus local, Campaign, Gensui, and parameter-aware restrictions.`}
            </p>
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
                <th className="w-12 px-3 py-3"><span className="sr-only">Details</span></th>
                <th className="px-4 py-3">Tool</th>
                <th className="px-4 py-3">Risk</th>
                <th className="px-4 py-3">Effective</th>
                <th className="px-4 py-3">Policy layers</th>
                <th className="px-4 py-3">Standalone override</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-shogun-border/60">
              {filteredTools.map(tool => {
                const expanded = expandedTool === tool.name;
                const toolRules = advancedDraft.rules.filter(rule => rule.tools.length === 0 || rule.tools.includes(tool.name));
                return (
                <Fragment key={tool.name}>
                <tr className="bg-shogun-card/20 hover:bg-shogun-card/50">
                  <td className="px-3 py-3">
                    <button
                      type="button"
                      onClick={() => setExpandedTool(expanded ? null : tool.name)}
                      className="rounded-md border border-shogun-border p-1.5 text-shogun-subdued transition-colors hover:border-shogun-gold/50 hover:text-shogun-gold"
                      aria-expanded={expanded}
                      aria-label={`${expanded ? 'Collapse' : 'Expand'} controls for ${tool.name}`}
                    >
                      {expanded ? <Minus className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
                    </button>
                  </td>
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
                {expanded && (
                  <tr className="bg-[#080b12]/70">
                    <td colSpan={6} className="px-6 py-5">
                      <div className="space-y-5">
                        <div className="flex flex-col justify-between gap-3 lg:flex-row lg:items-start">
                          <div>
                            <p className="text-xs font-bold uppercase tracking-widest text-shogun-text">Detailed controls · {tool.name}</p>
                            <p className="mt-1 max-w-3xl text-xs text-shogun-subdued">{tool.reason}</p>
                          </div>
                          {data.advanced_controls.editable && (
                            <button
                              type="button"
                              onClick={() => addAdvancedRule(tool.name)}
                              className="flex shrink-0 items-center gap-2 rounded-lg border border-orange-400/25 px-3 py-2 text-xs font-bold text-orange-300 hover:bg-orange-500/10"
                            >
                              <Plus className="h-3.5 w-3.5" /> Add argument restriction
                            </button>
                          )}
                        </div>

                        <div className="rounded-lg border border-shogun-border/70 bg-shogun-card/30 p-4">
                          <p className="text-[10px] font-bold uppercase tracking-widest text-shogun-subdued">Argument restrictions</p>
                          {toolRules.length ? (
                            <div className="mt-3 space-y-2">
                              {toolRules.map(rule => (
                                <div key={rule.id} className="grid gap-2 rounded-md border border-shogun-border/60 p-3 lg:grid-cols-[1fr_8rem_7rem] lg:items-center">
                                  <div>
                                    <input
                                      value={rule.pattern}
                                      onChange={event => updateAdvancedRule(rule.id, { pattern: event.target.value })}
                                      disabled={!data.advanced_controls.editable}
                                      placeholder="Text or argument pattern"
                                      className="w-full rounded-md border border-shogun-border bg-shogun-bg px-2.5 py-2 font-mono text-xs text-shogun-text outline-none focus:border-orange-400 disabled:opacity-45"
                                    />
                                    <p className="mt-1 text-[9px] uppercase tracking-wider text-shogun-subdued">
                                      {rule.tools.length === 0 ? 'All tools' : 'This tool'}
                                    </p>
                                  </div>
                                  <select
                                    value={rule.action}
                                    onChange={event => updateAdvancedRule(rule.id, { action: event.target.value as AdvancedAction })}
                                    disabled={!data.advanced_controls.editable}
                                    className="rounded-md border border-shogun-border bg-shogun-bg px-2.5 py-2 text-xs text-shogun-text disabled:opacity-45"
                                  >
                                    <option value="confirm">Confirm</option>
                                    <option value="block">Block</option>
                                  </select>
                                  <label className="flex items-center gap-2 text-[10px] text-shogun-subdued">
                                    <input
                                      type="checkbox"
                                      checked={rule.enabled}
                                      onChange={event => updateAdvancedRule(rule.id, { enabled: event.target.checked })}
                                      disabled={!data.advanced_controls.editable}
                                    />
                                    Enabled
                                  </label>
                                </div>
                              ))}
                              {data.advanced_controls.editable && (
                                <div className="flex justify-end pt-1">
                                  <button
                                    type="button"
                                    onClick={saveAdvancedControls}
                                    disabled={savingAdvanced || advancedDraft.rules.some(rule => !rule.pattern.trim())}
                                    className="flex items-center gap-2 rounded-lg border border-orange-400/25 px-3 py-2 text-xs font-bold text-orange-300 disabled:opacity-50"
                                  >
                                    {savingAdvanced ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                                    Save restrictions
                                  </button>
                                </div>
                              )}
                            </div>
                          ) : (
                            <p className="mt-2 text-xs text-shogun-subdued">No advanced content rules currently apply to this tool.</p>
                          )}
                        </div>

                      </div>
                    </td>
                  </tr>
                )}
                </Fragment>
              )})}
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

      {showPolicyEditor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/75 backdrop-blur-sm" onClick={() => !savingPolicy && setShowPolicyEditor(false)} />
          <form
            onSubmit={savePolicy}
            className="relative flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-shogun-border bg-shogun-bg shadow-2xl"
          >
            <div className="flex items-start justify-between border-b border-shogun-border p-5">
              <div>
                <h3 className="text-lg font-bold text-shogun-text">
                  {policyDraft.id ? 'Edit custom posture' : 'Create custom posture'}
                </h3>
                <p className="mt-1 text-xs text-shogun-subdued">
                  Define the reusable policy here. Activation remains an explicit choice in Torii.
                </p>
              </div>
              <button type="button" onClick={() => setShowPolicyEditor(false)} className="rounded-lg p-2 text-shogun-subdued hover:bg-shogun-card hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 space-y-5 overflow-y-auto p-5">
              <div className="grid gap-4 md:grid-cols-2">
                <label className="space-y-1.5">
                  <span className="text-[9px] font-bold uppercase tracking-widest text-shogun-subdued">Posture name</span>
                  <input
                    required
                    maxLength={255}
                    value={policyDraft.name}
                    onChange={event => setPolicyDraft(current => ({ ...current, name: event.target.value }))}
                    placeholder="e.g. Research Samurai"
                    className="w-full rounded-lg border border-shogun-border bg-[#050508] px-3 py-2.5 text-sm text-shogun-text outline-none focus:border-violet-400"
                  />
                </label>
                <label className="space-y-1.5">
                  <span className="text-[9px] font-bold uppercase tracking-widest text-shogun-subdued">Base tier</span>
                  <select
                    value={policyDraft.tier}
                    onChange={event => setPolicyDraft(current => ({ ...current, tier: event.target.value as TierType }))}
                    className="w-full rounded-lg border border-shogun-border bg-[#050508] px-3 py-2.5 text-sm uppercase text-shogun-text outline-none focus:border-violet-400"
                  >
                    {(['shrine', 'guarded', 'tactical', 'campaign', 'ronin'] as TierType[]).map(tier => (
                      <option key={tier} value={tier}>{tier}</option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="block space-y-1.5">
                <span className="text-[9px] font-bold uppercase tracking-widest text-shogun-subdued">Description</span>
                <textarea
                  rows={3}
                  maxLength={1000}
                  value={policyDraft.description}
                  onChange={event => setPolicyDraft(current => ({ ...current, description: event.target.value }))}
                  placeholder="Explain when this posture should be selected."
                  className="w-full rounded-lg border border-shogun-border bg-[#050508] px-3 py-2.5 text-sm text-shogun-text outline-none focus:border-violet-400"
                />
              </label>

              <div className="grid gap-3 md:grid-cols-2">
                <label className="flex items-center justify-between rounded-lg border border-shogun-border bg-shogun-card/40 p-3 text-xs text-shogun-subdued">
                  Global kill switch available
                  <input
                    type="checkbox"
                    checked={policyDraft.kill_switch_enabled}
                    onChange={event => setPolicyDraft(current => ({ ...current, kill_switch_enabled: event.target.checked }))}
                  />
                </label>
                <label className="flex items-center justify-between rounded-lg border border-shogun-border bg-shogun-card/40 p-3 text-xs text-shogun-subdued">
                  Dry-run simulation supported
                  <input
                    type="checkbox"
                    checked={policyDraft.dry_run_supported}
                    onChange={event => setPolicyDraft(current => ({ ...current, dry_run_supported: event.target.checked }))}
                  />
                </label>
              </div>

              <div>
                <h4 className="text-[10px] font-bold uppercase tracking-[0.18em] text-shogun-text">Capability boundaries</h4>
                <p className="mt-1 text-[10px] text-shogun-subdued">
                  These are the maximum runtime capabilities of this posture. Tool verdicts and advanced content rules may narrow them further.
                </p>
                <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {Object.entries(policyDraft.permissions).map(([categoryName, permissions]) => (
                    <div key={categoryName} className="rounded-lg border border-shogun-border/70 bg-[#050508] p-3">
                      <p className="mb-3 text-[10px] font-bold uppercase tracking-[0.18em] text-violet-300">
                        {categoryName.replace(/_/g, ' ')}
                      </p>
                      {Object.keys(permissions || {}).length === 0 ? (
                        <p className="text-[10px] italic text-shogun-subdued">Uses base-tier defaults</p>
                      ) : (
                        <div className="space-y-2">
                          {Object.entries(permissions || {}).map(([key, value]) => (
                            <label key={key} className="flex min-h-8 items-center justify-between gap-3 text-[10px] text-shogun-subdued">
                              <span className="capitalize">{key.replace(/_/g, ' ')}</span>
                              {typeof value === 'boolean' ? (
                                <button
                                  type="button"
                                  onClick={() => updatePolicyPermission(categoryName, key, !value)}
                                  className={cn(
                                    'relative h-5 w-10 rounded-full border transition-colors',
                                    value ? 'border-emerald-500/40 bg-emerald-500/20' : 'border-red-500/30 bg-red-500/10',
                                  )}
                                >
                                  <span className={cn('absolute top-0.5 h-4 w-4 rounded-full transition-all', value ? 'left-5 bg-emerald-400' : 'left-0.5 bg-red-400')} />
                                </button>
                              ) : typeof value === 'number' ? (
                                <input
                                  type="number"
                                  value={value}
                                  onChange={event => updatePolicyPermission(categoryName, key, Number(event.target.value))}
                                  className="w-20 rounded border border-shogun-border bg-shogun-bg px-2 py-1 text-right text-[10px] text-shogun-text"
                                />
                              ) : Array.isArray(value) ? (
                                <input
                                  value={value.join(', ')}
                                  onChange={event => updatePolicyPermission(categoryName, key, event.target.value.split(',').map(item => item.trim()).filter(Boolean))}
                                  placeholder="Comma-separated"
                                  className="w-44 rounded border border-shogun-border bg-shogun-bg px-2 py-1 text-right text-[10px] text-shogun-text"
                                />
                              ) : key === 'mode' ? (
                                <select
                                  value={String(value)}
                                  onChange={event => updatePolicyPermission(categoryName, key, event.target.value)}
                                  className="rounded border border-shogun-border bg-shogun-bg px-2 py-1 text-[10px] uppercase text-shogun-text"
                                >
                                  {['full', 'scoped', 'allowlist', 'disabled'].map(option => <option key={option} value={option}>{option}</option>)}
                                </select>
                              ) : (
                                <input
                                  value={String(value ?? '')}
                                  onChange={event => updatePolicyPermission(categoryName, key, event.target.value)}
                                  className="w-36 rounded border border-shogun-border bg-shogun-bg px-2 py-1 text-right text-[10px] text-shogun-text"
                                />
                              )}
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 border-t border-shogun-border p-4">
              <button type="button" onClick={() => setShowPolicyEditor(false)} className="px-4 py-2.5 text-xs font-bold text-shogun-subdued hover:text-white">
                Cancel
              </button>
              <button
                type="submit"
                disabled={savingPolicy || !policyDraft.name.trim()}
                className="flex items-center gap-2 rounded-lg bg-violet-400 px-4 py-2.5 text-xs font-bold text-black disabled:opacity-50"
              >
                {savingPolicy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                {policyDraft.id ? 'Save custom posture' : 'Create custom posture'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
