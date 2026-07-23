import { useEffect, useState } from 'react';
import {
  Shield, Plus, Pencil, Trash2, X, Save, AlertCircle, CheckCircle2,
  ChevronDown, ChevronUp, Loader2,
} from 'lucide-react';
import api from '../lib/api';
import { TOOL_NAMES } from '../lib/toolRegistry';
import { useTranslation } from '../i18n';

const PERM_KEYS = [
  { key: 'allow_external_models',    label: 'External Models',     desc: 'Use cloud AI providers (OpenAI, Anthropic, etc.)' },
  { key: 'allow_local_models',       label: 'Local Models',        desc: 'Use locally hosted models (Ollama, etc.)' },
  { key: 'allow_tool_execution',     label: 'Tool Execution',      desc: 'Execute native tools (email, calendar, memory, etc.)' },
  { key: 'allow_mado',               label: 'Mado Browser',        desc: 'Browser automation and web extraction' },
  { key: 'allow_memory_write',       label: 'Memory Write',        desc: 'Store new memories in the Archives' },
  { key: 'allow_memory_read',        label: 'Memory Read',         desc: 'Read from the Archives memory system' },
  { key: 'allow_agent_flow',         label: 'Agent Flow',          desc: 'Create and run multi-agent workflow pipelines' },
  { key: 'allow_nexus',              label: 'Nexus',               desc: 'Use the Nexus collaboration system' },
  { key: 'allow_samurai_delegation', label: 'Samurai Delegation',  desc: 'Spawn sub-agents in the Dojo' },
  { key: 'allow_scheduled_triggers', label: 'Scheduled Triggers',  desc: 'Bushido cron jobs and scheduled tasks' },
  { key: 'allow_autonomous_loops',   label: 'Autonomous Loops',    desc: 'Self-directed multi-step execution' },
  { key: 'allow_external_web',       label: 'External Web',        desc: 'Access external websites and APIs' },
  { key: 'allow_file_write',         label: 'File Write',          desc: 'Write files to the filesystem' },
  { key: 'allow_external_api',       label: 'External API',        desc: 'Make outbound HTTP API calls' },
];

interface Posture {
  id: string;
  name: string;
  description: string | null;
  level: number;
  is_builtin: boolean;
  tool_overrides_json: Record<string, string> | null;
  [key: string]: any;
}

const EMPTY_FORM = {
  name: '', description: '', level: 10,
  allow_external_models: true, allow_local_models: true, allow_tool_execution: true,
  allow_mado: true, allow_memory_write: true, allow_memory_read: true,
  allow_agent_flow: true, allow_nexus: true, allow_samurai_delegation: true,
  allow_scheduled_triggers: true, allow_autonomous_loops: true,
  allow_external_web: true, allow_file_write: true, allow_external_api: true,
  tool_overrides_json: {} as Record<string, string>,
};

export default function Postures() {
  const { t } = useTranslation();
  const [postures, setPostures] = useState<Posture[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [isBuiltinEdit, setIsBuiltinEdit] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [showOverrides, setShowOverrides] = useState(false);
  const [newOverrideTool, setNewOverrideTool] = useState('');

  useEffect(() => { fetchPostures(); }, []);

  useEffect(() => {
    if (error || success) {
      const t = setTimeout(() => { setError(null); setSuccess(null); }, 5000);
      return () => clearTimeout(t);
    }
  }, [error, success]);

  const fetchPostures = async () => {
    try {
      const res = await api.get('/postures');
      setPostures(res.data || []);
    } catch { setError('Failed to load postures'); }
    finally { setLoading(false); }
  };

  const openCreate = () => {
    setEditingId(null);
    setIsBuiltinEdit(false);
    setForm({ ...EMPTY_FORM, tool_overrides_json: {} });
    setShowOverrides(false);
    setModalOpen(true);
  };

  const openEdit = (p: Posture) => {
    setEditingId(p.id);
    setIsBuiltinEdit(p.is_builtin);
    setForm({
      name: p.name,
      description: p.description || '',
      level: p.level,
      ...Object.fromEntries(PERM_KEYS.map(pk => [pk.key, p[pk.key] ?? true])),
      tool_overrides_json: p.tool_overrides_json || {},
    } as any);
    setShowOverrides(Object.keys(p.tool_overrides_json || {}).length > 0);
    setModalOpen(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) { setError('Name is required'); return; }
    setSaving(true);
    try {
      if (editingId) {
        // Update
        const payload: any = { ...form };
        if (isBuiltinEdit) delete payload.name; // can't rename built-in
        await api.patch(`/postures/${editingId}`, payload);
        setSuccess(`Posture "${form.name}" updated`);
      } else {
        // Create
        await api.post('/postures', form);
        setSuccess(`Posture "${form.name}" created`);
      }
      setModalOpen(false);
      fetchPostures();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save posture');
    } finally { setSaving(false); }
  };

  const handleDelete = async (p: Posture) => {
    if (p.is_builtin) { setError('Cannot delete built-in postures'); return; }
    if (!confirm(`Delete posture "${p.name}"? This will unassign it from all members and groups.`)) return;
    try {
      await api.delete(`/postures/${p.id}`);
      setSuccess(`Posture "${p.name}" deleted`);
      fetchPostures();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete posture');
    }
  };

  const togglePerm = (key: string) => {
    setForm(prev => ({ ...prev, [key]: !prev[key as keyof typeof prev] }));
  };

  const addOverride = () => {
    if (!newOverrideTool) return;
    setForm(prev => ({
      ...prev,
      tool_overrides_json: { ...prev.tool_overrides_json, [newOverrideTool]: 'block' },
    }));
    setNewOverrideTool('');
  };

  const removeOverride = (tool: string) => {
    setForm(prev => {
      const copy = { ...prev.tool_overrides_json };
      delete copy[tool];
      return { ...prev, tool_overrides_json: copy };
    });
  };

  const setOverrideAction = (tool: string, action: string) => {
    setForm(prev => ({
      ...prev,
      tool_overrides_json: { ...prev.tool_overrides_json, [tool]: action },
    }));
  };

  const getLevelColor = (level: number) => {
    if (level >= 90) return 'text-red-400 bg-red-500/10 border-red-500/30';
    if (level >= 50) return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
    if (level >= 20) return 'text-cyan-400 bg-cyan-500/10 border-cyan-500/30';
    return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
  };

  const countAllowed = (p: Posture) => PERM_KEYS.filter(pk => p[pk.key]).length;
  const countBlocked = (p: Posture) => PERM_KEYS.filter(pk => !p[pk.key]).length;

  const availableTools = TOOL_NAMES.filter(t => !form.tool_overrides_json[t]);

  return (
    <div className="space-y-6 max-w-7xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gensui-50">{t('postures.title', 'Security Postures')}</h1>
          <p className="text-sm text-gensui-400 mt-1">{t('postures.subtitle', 'Define and manage what Shogun instances are allowed to do')}</p>
        </div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-1.5">
          <Plus size={16} /> {t('postures.create_posture', 'Create Posture')}
        </button>
      </div>

      {/* Banners */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-900/30 border border-red-700/40 rounded-xl text-sm text-red-300">
          <AlertCircle size={16} className="shrink-0" /> <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="flex items-center gap-2 px-4 py-3 bg-emerald-900/30 border border-emerald-700/40 rounded-xl text-sm text-emerald-300">
          <CheckCircle2 size={16} className="shrink-0" /> <span>{success}</span>
        </div>
      )}

      {/* Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {postures.map(p => {
            const overrideCount = Object.keys(p.tool_overrides_json || {}).length;
            return (
              <div key={p.id} className="glass-card p-5 group hover:border-cyan-500/30 transition-colors">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <h3 className="font-bold text-gensui-100 truncate">{p.name}</h3>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${getLevelColor(p.level)}`}>
                      L{p.level}
                    </span>
                    {p.is_builtin && (
                      <span className="text-[10px] uppercase tracking-wider text-gensui-500 bg-gensui-700/50 px-2 py-0.5 rounded-full">Built-in</span>
                    )}
                  </div>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onClick={() => openEdit(p)} className="p-1.5 text-gensui-400 hover:text-cyan-400 rounded-lg hover:bg-gensui-700/50 transition-colors" title="Edit">
                      <Pencil size={14} />
                    </button>
                    {!p.is_builtin && (
                      <button onClick={() => handleDelete(p)} className="p-1.5 text-gensui-400 hover:text-red-400 rounded-lg hover:bg-gensui-700/50 transition-colors" title="Delete">
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                </div>

                <p className="text-xs text-gensui-400 mb-4 line-clamp-2 min-h-[2rem]">{p.description}</p>

                {/* Permission badges */}
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {PERM_KEYS.map(pk => (
                    <span key={pk.key} className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                      p[pk.key] ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
                    }`}>
                      {p[pk.key] ? '✓' : '✕'} {pk.label}
                    </span>
                  ))}
                </div>

                {/* Stats row */}
                <div className="flex items-center gap-3 text-[10px] text-gensui-500 pt-2 border-t border-gensui-700/30">
                  <span className="text-emerald-400">{countAllowed(p)} allowed</span>
                  <span className="text-red-400">{countBlocked(p)} blocked</span>
                  {overrideCount > 0 && <span className="text-amber-400">{overrideCount} tool overrides</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create/Edit Modal */}
      {modalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-gensui-900 border border-gensui-700/50 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="flex items-center justify-between p-5 border-b border-gensui-700/30 sticky top-0 bg-gensui-900 z-10 rounded-t-2xl">
              <h2 className="text-lg font-bold text-gensui-50 flex items-center gap-2">
                <Shield size={18} className="text-amber-400" />
                {editingId ? `Edit: ${form.name}` : 'Create Posture'}
              </h2>
              <button onClick={() => setModalOpen(false)} className="p-1.5 text-gensui-400 hover:text-gensui-100 transition-colors">
                <X size={18} />
              </button>
            </div>

            <div className="p-5 space-y-5">
              {/* Name + Level */}
              <div className="grid grid-cols-3 gap-4">
                <div className="col-span-2">
                  <label className="text-xs text-gensui-400 block mb-1.5">Name</label>
                  <input
                    className="gensui-input w-full"
                    value={form.name}
                    onChange={e => setForm(prev => ({ ...prev, name: e.target.value }))}
                    disabled={isBuiltinEdit}
                    placeholder="e.g. PRODUCTION_SAFE"
                  />
                  {isBuiltinEdit && <p className="text-[10px] text-gensui-600 mt-1">Built-in names cannot be changed</p>}
                </div>
                <div>
                  <label className="text-xs text-gensui-400 block mb-1.5">Level (0–100)</label>
                  <input
                    type="number" min={0} max={100}
                    className="gensui-input w-full"
                    value={form.level}
                    onChange={e => setForm(prev => ({ ...prev, level: parseInt(e.target.value) || 0 }))}
                  />
                  <p className="text-[10px] text-gensui-600 mt-1">Higher = more restrictive</p>
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="text-xs text-gensui-400 block mb-1.5">Description</label>
                <textarea
                  className="gensui-input w-full resize-none"
                  rows={2}
                  value={form.description}
                  onChange={e => setForm(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Describe when this posture should be used..."
                />
              </div>

              <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/[0.05] p-4">
                <p className="text-xs font-bold text-cyan-200">Runtime permissions belong to ToolGate</p>
                <p className="mt-1 text-[10px] leading-relaxed text-gensui-500">
                  Save the posture identity here, then configure capability boundaries and per-tool verdicts from the central ToolGate page.
                </p>
              </div>

              {/* Permission Toggles */}
              <div className="hidden">
                <label className="text-xs text-gensui-400 block mb-3 uppercase tracking-widest font-bold">Permission Flags</label>
                <div className="grid grid-cols-2 gap-2">
                  {PERM_KEYS.map(pk => (
                    <button
                      key={pk.key}
                      onClick={() => togglePerm(pk.key)}
                      className={`flex items-center justify-between p-2.5 rounded-lg border text-xs transition-all ${
                        (form as any)[pk.key]
                          ? 'bg-emerald-500/5 border-emerald-500/30 text-emerald-400'
                          : 'bg-red-500/5 border-red-500/30 text-red-400'
                      }`}
                    >
                      <div className="text-left">
                        <span className="font-bold">{pk.label}</span>
                        <p className="text-[9px] text-gensui-500 mt-0.5">{pk.desc}</p>
                      </div>
                      <span className="text-lg shrink-0 ml-2">{(form as any)[pk.key] ? '✓' : '✕'}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Tool Overrides */}
              <div className="hidden">
                <button
                  onClick={() => setShowOverrides(!showOverrides)}
                  className="flex items-center gap-2 text-xs text-gensui-400 hover:text-gensui-200 transition-colors uppercase tracking-widest font-bold"
                >
                  {showOverrides ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  Tool Overrides ({Object.keys(form.tool_overrides_json).length})
                </button>

                {showOverrides && (
                  <div className="mt-3 space-y-2">
                    <p className="text-[10px] text-gensui-500">Override specific tool actions: allow, confirm, or block.</p>

                    {/* Existing overrides */}
                    {Object.entries(form.tool_overrides_json).map(([tool, action]) => (
                      <div key={tool} className="flex items-center gap-2 p-2 bg-gensui-800/50 rounded-lg">
                        <span className="text-xs text-gensui-200 font-mono flex-1">{tool}</span>
                        <select
                          value={action}
                          onChange={e => setOverrideAction(tool, e.target.value)}
                          className="gensui-input text-xs py-1 px-2 w-28"
                        >
                          <option value="allow">Allow</option>
                          <option value="confirm">Confirm</option>
                          <option value="block">Block</option>
                        </select>
                        <button onClick={() => removeOverride(tool)} className="p-1 text-gensui-500 hover:text-red-400 transition-colors">
                          <X size={14} />
                        </button>
                      </div>
                    ))}

                    {/* Add new override */}
                    {availableTools.length > 0 && (
                      <div className="flex gap-2">
                        <select
                          value={newOverrideTool}
                          onChange={e => setNewOverrideTool(e.target.value)}
                          className="gensui-input text-xs flex-1"
                        >
                          <option value="">Select a tool...</option>
                          {availableTools.map(t => <option key={t} value={t}>{t}</option>)}
                        </select>
                        <button onClick={addOverride} disabled={!newOverrideTool} className="btn-ghost text-xs px-3 disabled:opacity-30">
                          <Plus size={14} />
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 p-5 border-t border-gensui-700/30 sticky bottom-0 bg-gensui-900 rounded-b-2xl">
              <button onClick={() => setModalOpen(false)} className="btn-ghost text-sm px-4 py-2">Cancel</button>
              <button onClick={handleSave} disabled={saving} className="btn-primary flex items-center gap-1.5 text-sm px-5 py-2 disabled:opacity-50">
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                {editingId ? 'Update' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
