import { useState, useEffect } from 'react';
import { 
  Users, 
  Radio, 
  Plus, 
  Search, 
  MoreVertical, 
  Pause, 
  Play, 
  Trash2, 
  RefreshCw,
  X,
  Save,
  Settings,
  Zap,
} from 'lucide-react';
import axios from 'axios';
import { cn } from '../lib/utils';
import { useTranslation } from '../i18n';

export const SamuraiNetwork = () => {
  const { t } = useTranslation();
  const [agents, setAgents] = useState<any[]>([]);
  const [missions, setMissions] = useState<any[]>([]);
  const [samuraiRoles, setSamuraiRoles] = useState<any[]>([]);
  const [routingProfiles, setRoutingProfiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [editAgent, setEditAgent] = useState<any | null>(null);
  const [editForm, setEditForm] = useState({
    name: '',
    description: '',
    spawn_policy: 'manual',
    role_id: '',
    model_routing_profile_id: '',
  });
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  
  const [newAgent, setNewAgent] = useState({
    name: '',
    slug: '',
    description: '',
    role_id: '',
    model_routing_profile_id: '',
    agent_type: 'samurai',
    spawn_policy: 'manual',
    tags: [] as string[],
  });

  useEffect(() => {
    fetchAll();
  }, []);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [agentRes, missionRes, roleRes, routingRes] = await Promise.all([
        axios.get('/api/v1/agents?agent_type=samurai'),
        axios.get('/api/v1/missions'),
        axios.get('/api/v1/samurai-roles'),
        axios.get('/api/v1/model-routing-profiles'),
      ]);
      if (agentRes.data.data)   setAgents(agentRes.data.data);
      if (missionRes.data.data) setMissions(missionRes.data.data);
      if (roleRes.data.data)    setSamuraiRoles(roleRes.data.data);
      if (routingRes.data.data) setRoutingProfiles(routingRes.data.data);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getAgentMission = (agentId: string) =>
    missions.find(
      (m: any) => m.assigned_agent_id === agentId &&
        ['in_progress', 'pending', 'queued'].includes(m.status)
    );

  const estimateProgress = (mission: any): number => {
    if (!mission?.started_at) return mission?.status === 'pending' || mission?.status === 'queued' ? 5 : 0;
    const elapsed = Date.now() - new Date(mission.started_at).getTime();
    return Math.min(95, Math.round((elapsed / (5 * 60 * 1000)) * 100));
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const slug = newAgent.name.toLowerCase().replace(/\s+/g, '-');
      await axios.post('/api/v1/agents', {
        ...newAgent,
        slug,
        model_routing_profile_id: newAgent.model_routing_profile_id || null,
      });
      setShowCreateModal(false);
      setNewAgent({ name: '', slug: '', description: '', role_id: '', model_routing_profile_id: '', agent_type: 'samurai', spawn_policy: 'manual', tags: [] });
      fetchAll();
    } catch (error) {
      console.error('Error creating agent:', error);
    }
  };

  const handleAction = async (agentId: string, action: 'suspend' | 'resume' | 'delete') => {
    try {
      if (action === 'delete') {
        if (!confirm(t('samurai_network.confirm_delete'))) return;
        await axios.delete(`/api/v1/agents/${agentId}`);
      } else {
        await axios.post(`/api/v1/agents/${agentId}/${action}`);
      }
      fetchAll();
    } catch (error) {
      console.error(`Error performing ${action}:`, error);
    }
  };

  const openEditModal = (agent: any) => {
    setEditAgent(agent);
    setEditForm({
      name: agent.name || '',
      description: agent.description || '',
      spawn_policy: agent.spawn_policy || 'manual',
      role_id: agent.samurai_profile?.role_id || agent.samurai_profile?.samurai_role?.id || '',
      model_routing_profile_id: agent.model_routing_profile_id || '',
    });
    setEditError(null);
  };

  const handleEditSave = async () => {
    if (!editAgent) return;
    setEditSaving(true);
    setEditError(null);
    try {
      await axios.patch(`/api/v1/agents/${editAgent.id}`, {
        name: editForm.name,
        description: editForm.description,
        spawn_policy: editForm.spawn_policy,
        model_routing_profile_id: editForm.model_routing_profile_id || null,
        ...(editForm.role_id ? { role_id: editForm.role_id } : {}),
      });
      setEditAgent(null);
      fetchAll();
    } catch (err: any) {
      setEditError(err?.response?.data?.detail || t('samurai_network.save_failed'));
    } finally {
      setEditSaving(false);
    }
  };

  const getRoutingName = (agent: any) =>
    agent.routing_profile?.name || null;

  const filteredAgents = agents.filter(a =>
    a.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    a.slug.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            {t('samurai_network.title', 'Samurai Network')}
            <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">{t('samurai_network.fleet_status')}</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">{t('samurai_network.subtitle', 'Orchestrate specialized sub-agents across the mission grid.')}</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={fetchAll} className="p-2.5 bg-shogun-card border border-shogun-border rounded-lg text-shogun-subdued hover:text-shogun-gold transition-colors">
            <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
          </button>
          <button onClick={() => setShowCreateModal(true)} className="flex items-center gap-2 bg-shogun-blue hover:bg-shogun-blue/90 text-white font-bold py-2.5 px-6 rounded-lg transition-all shadow-shogun">
            <Plus className="w-4 h-4" /> {t('samurai_network.deploy_samurai', 'DEPLOY SAMURAI')}
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {[
          { label: t('samurai_network.total_fleet', 'Total Fleet'),  value: agents.length.toString(),                                       icon: Users,  color: 'text-shogun-gold'    },
          { label: t('samurai_network.active', 'Active'),       value: agents.filter(a => a.status === 'active').length.toString(),    icon: Play,   color: 'text-green-500'      },
          { label: t('samurai_network.suspended', 'Suspended'),    value: agents.filter(a => a.status === 'suspended').length.toString(), icon: Pause,  color: 'text-shogun-blue'    },
          { label: t('samurai_network.signal_range', 'Signal Range'), value: '100%',                                                         icon: Radio,  color: 'text-shogun-subdued' },
        ].map((item, i) => (
          <div key={i} className="shogun-card flex flex-col gap-1 border-l-2" style={{ borderLeftColor: i === 0 ? '#d4a017' : i === 1 ? '#22c55e' : i === 2 ? '#4a8cc7' : '#1a2040' }}>
            <div className="flex items-center gap-2 text-shogun-subdued mb-1">
              <item.icon className={cn("w-3 h-3", item.color)} />
              <span className="text-[9px] uppercase tracking-widest font-bold">{item.label}</span>
            </div>
            <span className="text-2xl font-bold text-shogun-text">{item.value}</span>
          </div>
        ))}
      </div>

      {/* Table */}
      <div className="shogun-card overflow-hidden !p-0">
        {/* Search bar */}
        <div className="p-4 border-b border-shogun-border bg-[#050508]/50 flex items-center justify-between gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-shogun-subdued" />
            <input
              type="text"
              placeholder={t('samurai_network.filter_placeholder')}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-shogun-card border border-shogun-border rounded-lg pl-10 pr-4 py-2 text-sm focus:border-shogun-blue transition-colors outline-none"
            />
          </div>
          <select className="bg-shogun-card border border-shogun-border rounded-lg px-3 py-2 text-xs text-shogun-subdued outline-none focus:border-shogun-blue">
            <option>{t('samurai_network.all_status')}</option>
            <option>{t('samurai_network.status_active')}</option>
            <option>{t('samurai_network.status_suspended')}</option>
          </select>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-shogun-border bg-[#050508]/30">
                <th className="p-4 text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('samurai.table_designation', 'Designation')}</th>
                <th className="p-4 text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('samurai.table_status', 'Status')}</th>
                <th className="p-4 text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('samurai.table_task', 'Current Task')}</th>
                <th className="p-4 text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('samurai.table_role', 'Role / Slug')}</th>
                <th className="p-4 text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('samurai.table_routing', 'Routing')}</th>
                <th className="p-4 text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('samurai.table_deployed', 'Deployed At')}</th>
                <th className="p-4 text-[10px] font-bold text-shogun-subdued uppercase tracking-widest text-right">{t('common.actions', 'Actions')}</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="p-12 text-center">
                    <div className="flex flex-col items-center gap-3">
                      <div className="w-6 h-6 border-2 border-shogun-gold border-t-transparent rounded-full animate-spin" />
                      <span className="text-xs text-shogun-subdued uppercase tracking-widest">{t('samurai_network.scanning_grid')}</span>
                    </div>
                  </td>
                </tr>
              ) : filteredAgents.length === 0 ? (
                <tr><td colSpan={7} className="p-12 text-center text-shogun-subdued text-sm italic">{t('samurai_network.no_samurai')}</td></tr>
              ) : filteredAgents.map((agent) => {
                const routingName = getRoutingName(agent);
                return (
                  <tr key={agent.id} className="border-b border-shogun-border hover:bg-shogun-gold/5 transition-colors group">
                    {/* Designation */}
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-shogun-card border border-shogun-border flex items-center justify-center text-shogun-gold font-bold relative">
                          {agent.name[0]}
                          <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-shogun-blue border border-[#0a0e1a] flex items-center justify-center">
                            <Users className="w-2 h-2 text-white" />
                          </div>
                        </div>
                        <div className="flex flex-col">
                          <span className="font-bold text-shogun-text text-sm">{agent.name}</span>
                          <div className="flex items-center gap-1.5">
                            <span className="text-[10px] text-shogun-subdued uppercase tracking-tighter">ID: {agent.id.slice(0, 8)}</span>
                            {agent.samurai_profile?.samurai_role && (
                              <span className="text-[9px] bg-shogun-blue/10 text-shogun-blue px-1.5 py-0.5 rounded border border-shogun-blue/20 font-bold uppercase tracking-widest">
                                {agent.samurai_profile.samurai_role.name}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </td>

                    {/* Status */}
                    <td className="p-4">
                      <div className="flex items-center gap-2">
                        <div className={cn("w-1.5 h-1.5 rounded-full", agent.status === 'active' ? "bg-green-500" : "bg-shogun-blue")} />
                        <span className={cn("text-[10px] font-bold uppercase tracking-widest", agent.status === 'active' ? "text-green-500" : "text-shogun-blue")}>
                          {agent.status}
                        </span>
                      </div>
                    </td>

                    {/* Task */}
                    <td className="p-4">
                      {(() => {
                        const mission = getAgentMission(agent.id);
                        if (!mission) return (
                          <div className="flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-shogun-subdued/40" />
                            <span className="text-[10px] text-shogun-subdued italic">{t('samurai_network.idle')}</span>
                          </div>
                        );
                        const progress = estimateProgress(mission);
                        return (
                          <div className="space-y-1.5 min-w-[180px]">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-[10px] font-bold text-shogun-text truncate max-w-[160px]" title={mission.title}>{mission.title}</span>
                              <span className="text-[9px] font-mono font-bold text-shogun-gold shrink-0">{progress}%</span>
                            </div>
                            <div className="w-full h-1.5 bg-[#0a0e1a] rounded-full overflow-hidden">
                              <div
                                className={cn("h-full rounded-full transition-all duration-700",
                                  progress < 30 ? "bg-gradient-to-r from-shogun-blue to-shogun-blue/70" :
                                  progress < 70 ? "bg-gradient-to-r from-shogun-blue via-shogun-gold/60 to-shogun-gold" :
                                  "bg-gradient-to-r from-shogun-gold to-green-400"
                                )}
                                style={{ width: `${progress}%` }}
                              />
                            </div>
                          </div>
                        );
                      })()}
                    </td>

                    {/* Role / Slug */}
                    <td className="p-4">
                      <div className="flex flex-col gap-1">
                        <code className="text-[10px] bg-shogun-card px-2 py-1 rounded border border-shogun-border text-shogun-blue w-fit">{agent.slug}</code>
                        {agent.samurai_profile?.samurai_role?.purpose && (
                          <p className="text-[9px] text-shogun-subdued italic line-clamp-1 max-w-[150px]">{agent.samurai_profile.samurai_role.purpose}</p>
                        )}
                      </div>
                    </td>

                    {/* Routing */}
                    <td className="p-4">
                      {routingName ? (
                        <div className="flex items-center gap-1.5">
                          <Zap className="w-3 h-3 text-shogun-gold/70 shrink-0" />
                          <span className="text-[10px] font-bold text-shogun-gold/90 truncate max-w-[120px]" title={routingName}>{routingName}</span>
                        </div>
                      ) : (
                        <span className="text-[10px] text-shogun-subdued italic">{t('samurai_network.default_routing')}</span>
                      )}
                    </td>

                    {/* Deployed At */}
                    <td className="p-4 text-xs text-shogun-subdued">
                      {new Date(agent.created_at).toLocaleDateString()}
                    </td>

                    {/* Actions */}
                    <td className="p-4 text-right">
                      <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        {agent.status === 'active' ? (
                          <button onClick={() => handleAction(agent.id, 'suspend')} className="p-1.5 hover:bg-shogun-blue/10 text-shogun-blue rounded transition-colors" title={t('samurai_network.suspend_agent')}>
                            <Pause className="w-3.5 h-3.5" />
                          </button>
                        ) : (
                          <button onClick={() => handleAction(agent.id, 'resume')} className="p-1.5 hover:bg-green-500/10 text-green-500 rounded transition-colors" title={t('samurai_network.resume_agent')}>
                            <Play className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <button onClick={() => handleAction(agent.id, 'delete')} className="p-1.5 hover:bg-red-500/10 text-red-500 rounded transition-colors" title={t('samurai_network.delete_agent')}>
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => openEditModal(agent)} className="p-1.5 hover:bg-shogun-gold/10 text-shogun-gold rounded transition-colors" title={t('samurai_network.configure_samurai')}>
                          <MoreVertical className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Configure / Edit Modal ───────────────────────────── */}
      {editAgent && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200"
          onClick={(e) => { if (e.target === e.currentTarget) setEditAgent(null); }}
        >
          <div className="bg-[#0a0e1a] border border-shogun-border rounded-xl w-full max-w-lg shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            {/* Header */}
            <div className="bg-shogun-card border-b border-shogun-border p-6 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <Settings className="w-4 h-4 text-shogun-gold" />
                  <h3 className="text-lg font-bold text-shogun-gold">{t('samurai_network.configure_samurai')}</h3>
                </div>
                <p className="text-[10px] text-shogun-subdued uppercase tracking-widest font-bold mt-1">
                  {editAgent.name} · <span className="font-mono">{editAgent.id.slice(0, 8)}</span>
                </p>
              </div>
              <button onClick={() => setEditAgent(null)} className="p-2 hover:bg-shogun-gold/10 text-shogun-subdued hover:text-shogun-gold rounded-lg transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Form */}
            <div className="p-6 space-y-5">
              {/* Name */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('samurai_network.unit_name')}</label>
                <input
                  type="text"
                  value={editForm.name}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-gold transition-colors outline-none"
                />
              </div>

              {/* Role */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('samurai_network.designation_role')}</label>
                <select
                  value={editForm.role_id}
                  onChange={(e) => setEditForm({ ...editForm, role_id: e.target.value })}
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-gold transition-colors outline-none cursor-pointer"
                >
                  <option value="">{t('samurai_network.keep_current_role')}</option>
                  {samuraiRoles.map((role) => (
                    <option key={role.id} value={role.id}>{role.name}</option>
                  ))}
                </select>
                {editAgent.samurai_profile?.samurai_role?.name && (
                  <p className="text-[9px] text-shogun-subdued">
                    {t('samurai_network.current')}: <span className="text-shogun-blue font-bold">{editAgent.samurai_profile.samurai_role.name}</span>
                  </p>
                )}
              </div>

              {/* Routing Profile */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-1.5">
                  <Zap className="w-3 h-3 text-shogun-gold/70" /> {t('samurai_network.routing_profile')}
                </label>
                <select
                  value={editForm.model_routing_profile_id}
                  onChange={(e) => setEditForm({ ...editForm, model_routing_profile_id: e.target.value })}
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-gold transition-colors outline-none cursor-pointer"
                >
                  <option value="">{t('samurai_network.system_default')}</option>
                  {routingProfiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}{p.is_default ? ` (${t('samurai_network.default_routing')})` : ''}
                    </option>
                  ))}
                </select>
                {editAgent.routing_profile?.name && (
                  <p className="text-[9px] text-shogun-subdued">
                    {t('samurai_network.current')}: <span className="text-shogun-gold font-bold">{editAgent.routing_profile.name}</span>
                  </p>
                )}
              </div>

              {/* Spawn Policy */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('samurai_network.spawn_policy')}</label>
                <select
                  value={editForm.spawn_policy}
                  onChange={(e) => setEditForm({ ...editForm, spawn_policy: e.target.value })}
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-gold transition-colors outline-none cursor-pointer"
                >
                  <option value="manual">{t('samurai_network.manual_deploy')}</option>
                  <option value="auto">{t('samurai_network.auto_spawn')}</option>
                  <option value="scheduled">{t('samurai_network.scheduled_routine')}</option>
                </select>
              </div>

              {/* Description */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('samurai_network.operational_directive')}</label>
                <textarea
                  value={editForm.description}
                  onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  rows={3}
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-xs focus:border-shogun-gold transition-colors outline-none resize-none"
                  placeholder={t('samurai_network.directive_placeholder')}
                />
              </div>

              {/* Error */}
              {editError && (
                <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                  <X className="w-3.5 h-3.5 text-red-400 shrink-0" />
                  <p className="text-xs text-red-400">{editError}</p>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-6 pt-0 flex gap-3">
              <button
                onClick={() => setEditAgent(null)}
                className="flex-1 bg-shogun-card hover:bg-[#1a2040] text-shogun-subdued font-bold py-2.5 rounded-lg transition-all border border-shogun-border text-sm"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={handleEditSave}
                disabled={editSaving || !editForm.name.trim()}
                className={cn(
                  "flex-1 font-bold py-2.5 rounded-lg transition-all text-sm flex items-center justify-center gap-2",
                  editSaving || !editForm.name.trim()
                    ? "bg-shogun-subdued/20 text-shogun-subdued cursor-not-allowed"
                    : "bg-shogun-gold hover:bg-shogun-gold/90 text-black shadow-shogun"
                )}
              >
                {editSaving ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                {editSaving ? t('samurai_network.saving') : t('samurai_network.save_changes')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Deploy Samurai Modal ─────────────────────────────── */}
      {showCreateModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-300"
          onClick={(e) => { if (e.target === e.currentTarget) setShowCreateModal(false); }}
        >
          <div className="bg-[#0a0e1a] border border-shogun-border rounded-xl w-full max-w-lg shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300">
            <div className="bg-shogun-card border-b border-shogun-border p-6 flex items-center justify-between">
              <div>
                <h3 className="text-xl font-bold text-shogun-gold">{t('samurai_network.deploy_new')}</h3>
                <p className="text-[10px] text-shogun-subdued uppercase tracking-widest font-bold mt-1">{t('samurai_network.initialize_fleet')}</p>
              </div>
              <button onClick={() => setShowCreateModal(false)} className="p-2 hover:bg-shogun-gold/10 text-shogun-subdued hover:text-shogun-gold rounded-lg transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreate} className="p-6 space-y-5">
              {/* Role */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('samurai_network.samurai_designation')}</label>
                <select
                  required
                  value={newAgent.role_id}
                  onChange={(e) => {
                    const selectedRole = samuraiRoles.find(r => r.id === e.target.value);
                    if (selectedRole) {
                      setNewAgent({
                        ...newAgent,
                        role_id: selectedRole.id,
                        name: selectedRole.name,
                        description: selectedRole.description || selectedRole.purpose,
                      });
                    }
                  }}
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue transition-colors outline-none cursor-pointer"
                >
                  <option value="" disabled>{t('samurai_network.select_role')}</option>
                  {samuraiRoles.map((role) => (
                    <option key={role.id} value={role.id}>{role.name}</option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                {/* Name */}
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('samurai_network.custom_unit_name')}</label>
                  <input
                    type="text"
                    required
                    value={newAgent.name}
                    onChange={(e) => setNewAgent({ ...newAgent, name: e.target.value })}
                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue transition-colors outline-none"
                    placeholder="e.g. Shadow Scout"
                  />
                </div>

                {/* Spawn Policy */}
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('samurai_network.spawn_policy')}</label>
                  <select
                    value={newAgent.spawn_policy}
                    onChange={(e) => setNewAgent({ ...newAgent, spawn_policy: e.target.value })}
                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue transition-colors outline-none cursor-pointer"
                  >
                    <option value="manual">{t('samurai_network.manual_deploy')}</option>
                    <option value="auto">{t('samurai_network.auto_spawn')}</option>
                    <option value="scheduled">{t('samurai_network.scheduled_routine')}</option>
                  </select>
                </div>
              </div>

              {/* Routing Profile */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-1.5">
                  <Zap className="w-3 h-3 text-shogun-gold/70" /> {t('samurai_network.model_routing_profile')}
                </label>
                <select
                  value={newAgent.model_routing_profile_id}
                  onChange={(e) => setNewAgent({ ...newAgent, model_routing_profile_id: e.target.value })}
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue transition-colors outline-none cursor-pointer"
                >
                  <option value="">{t('samurai_network.system_default')}</option>
                  {routingProfiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}{p.is_default ? ` (${t('samurai_network.default_routing')})` : ''}
                    </option>
                  ))}
                </select>
                <p className="text-[9px] text-shogun-subdued">{t('samurai_network.routing_description')}</p>
              </div>

              {/* Description */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('samurai_network.operational_directive')}</label>
                <textarea
                  value={newAgent.description}
                  onChange={(e) => setNewAgent({ ...newAgent, description: e.target.value })}
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-xs focus:border-shogun-blue transition-colors outline-none h-24 resize-none"
                  placeholder={t('samurai_network.auto_populate_placeholder')}
                />
              </div>

              <div className="flex gap-3 pt-1">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 bg-shogun-card hover:bg-[#1a2040] text-shogun-subdued font-bold py-3 rounded-lg transition-all border border-shogun-border"
                >
                  {t('samurai_network.abort')}
                </button>
                <button
                  type="submit"
                  disabled={!newAgent.name || !newAgent.role_id}
                  className={cn(
                    "flex-1 font-bold py-3 rounded-lg transition-all shadow-shogun",
                    (!newAgent.name || !newAgent.role_id)
                      ? "bg-shogun-subdued/20 text-shogun-subdued cursor-not-allowed"
                      : "bg-shogun-blue hover:bg-shogun-blue/90 text-white"
                  )}
                >
                  {t('samurai_network.deploy_samurai_btn')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
