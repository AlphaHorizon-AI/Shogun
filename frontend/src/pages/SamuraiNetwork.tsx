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
  RefreshCw
} from 'lucide-react';
import axios from 'axios';
import { cn } from '../lib/utils';

export const SamuraiNetwork = () => {
  const [agents, setAgents] = useState<any[]>([]);
  const [missions, setMissions] = useState<any[]>([]);
  const [samuraiRoles, setSamuraiRoles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  
  const [newAgent, setNewAgent] = useState({
    name: '',
    slug: '',
    description: '',
    role_id: '',
    agent_type: 'samurai',
    spawn_policy: 'manual',
    tags: []
  });

  useEffect(() => {
    fetchAgents();
  }, []);

  const fetchAgents = async () => {
    setLoading(true);
    try {
      const [agentRes, missionRes, roleRes] = await Promise.all([
        axios.get('/api/v1/agents?agent_type=samurai'),
        axios.get('/api/v1/missions'),
        axios.get('/api/v1/samurai-roles'),
      ]);
      if (agentRes.data.data) {
        setAgents(agentRes.data.data);
      }
      if (missionRes.data.data) {
        setMissions(missionRes.data.data);
      }
      if (roleRes.data.data) {
        setSamuraiRoles(roleRes.data.data);
      }
    } catch (error) {
      console.error('Error fetching agents:', error);
    } finally {
      setLoading(false);
    }
  };

  // Get active mission for a given agent
  const getAgentMission = (agentId: string) => {
    return missions.find(
      (m: any) => m.assigned_agent_id === agentId && ['in_progress', 'pending', 'queued'].includes(m.status)
    );
  };

  // Estimate progress from elapsed time (simulated—replace with real progress field when available)
  const estimateProgress = (mission: any): number => {
    if (!mission?.started_at) return mission?.status === 'pending' || mission?.status === 'queued' ? 5 : 0;
    const start = new Date(mission.started_at).getTime();
    const now = Date.now();
    const elapsed = now - start;
    // Assume tasks take ~5 minutes on average, cap at 95% (never 100 until completed)
    return Math.min(95, Math.round((elapsed / (5 * 60 * 1000)) * 100));
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const slug = newAgent.name.toLowerCase().replace(/\s+/g, '-');
      await axios.post('/api/v1/agents', { ...newAgent, slug });
      setShowCreateModal(false);
      setNewAgent({ 
        name: '', 
        slug: '', 
        description: '', 
        role_id: '',
        agent_type: 'samurai', 
        spawn_policy: 'manual', 
        tags: [] 
      });
      fetchAgents();
    } catch (error) {
      console.error('Error creating agent:', error);
    }
  };

  const handleAction = async (agentId: string, action: 'suspend' | 'resume' | 'delete') => {
    try {
      if (action === 'delete') {
        if (!confirm('Are you sure you want to delete this samurai?')) return;
        await axios.delete(`/api/v1/agents/${agentId}`);
      } else {
        await axios.post(`/api/v1/agents/${agentId}/${action}`);
      }
      fetchAgents();
    } catch (error) {
      console.error(`Error performing ${action}:`, error);
    }
  };

  const filteredAgents = agents.filter(a => 
    a.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
    a.slug.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            Samurai Network <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">Fleet Status</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">Orchestrate specialized sub-agents across the mission grid.</p>
        </div>
        
        <div className="flex items-center gap-3">
          <button 
            onClick={fetchAgents}
            className="p-2.5 bg-shogun-card border border-shogun-border rounded-lg text-shogun-subdued hover:text-shogun-gold transition-colors"
          >
            <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
          </button>
          <button 
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 bg-shogun-blue hover:bg-shogun-blue/90 text-white font-bold py-2.5 px-6 rounded-lg transition-all shadow-shogun"
          >
            <Plus className="w-4 h-4" />
            DEPLOY SAMURAI
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
         {[
           { label: 'Total Fleet', value: agents.length.toString(), icon: Users, color: 'text-shogun-gold' },
           { label: 'Active', value: agents.filter(a => a.status === 'active').length.toString(), icon: Play, color: 'text-green-500' },
           { label: 'Suspended', value: agents.filter(a => a.status === 'suspended').length.toString(), icon: Pause, color: 'text-shogun-blue' },
           { label: 'Signal Range', value: '100%', icon: Radio, color: 'text-shogun-subdued' }
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

      <div className="shogun-card overflow-hidden !p-0">
        <div className="p-4 border-b border-shogun-border bg-[#050508]/50 flex items-center justify-between gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-shogun-subdued" />
            <input 
              type="text"
              placeholder="Filter by name or slug..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-shogun-card border border-shogun-border rounded-lg pl-10 pr-4 py-2 text-sm focus:border-shogun-blue transition-colors outline-none"
            />
          </div>
          <div className="flex gap-2">
            <select className="bg-shogun-card border border-shogun-border rounded-lg px-3 py-2 text-xs text-shogun-subdued outline-none focus:border-shogun-blue">
              <option>All Status</option>
              <option>Active</option>
              <option>Suspended</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-shogun-border bg-[#050508]/30">
                <th className="p-4 text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Designation</th>
                <th className="p-4 text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Status</th>
                <th className="p-4 text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Current Task</th>
                <th className="p-4 text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Role / Slug</th>
                <th className="p-4 text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Deployed At</th>
                <th className="p-4 text-[10px] font-bold text-shogun-subdued uppercase tracking-widest text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="p-12 text-center">
                    <div className="flex flex-col items-center gap-3">
                      <div className="w-6 h-6 border-2 border-shogun-gold border-t-transparent rounded-full animate-spin" />
                      <span className="text-xs text-shogun-subdued uppercase tracking-widest">Scanning Grid...</span>
                    </div>
                  </td>
                </tr>
              ) : filteredAgents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-12 text-center text-shogun-subdued text-sm italic">
                    No active Samurai found in this sector.
                  </td>
                </tr>
              ) : filteredAgents.map((agent) => (
                <tr key={agent.id} className="border-b border-shogun-border hover:bg-shogun-gold/5 transition-colors group">
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-shogun-card border border-shogun-border flex items-center justify-center text-shogun-gold font-bold relative group">
                        {agent.name[0]}
                        {/* Role icon/label tooltip */}
                        <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-shogun-blue border border-[#0a0e1a] flex items-center justify-center overflow-hidden">
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
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                       <div className={cn(
                         "w-1.5 h-1.5 rounded-full",
                         agent.status === 'active' ? "bg-green-500" : "bg-shogun-blue"
                       )} />
                       <span className={cn(
                         "text-[10px] font-bold uppercase tracking-widest",
                         agent.status === 'active' ? "text-green-500" : "text-shogun-blue"
                       )}>
                         {agent.status}
                       </span>
                    </div>
                  </td>
                  <td className="p-4">
                    {(() => {
                      const mission = getAgentMission(agent.id);
                      if (!mission) {
                        return (
                          <div className="flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-shogun-subdued/40" />
                            <span className="text-[10px] text-shogun-subdued italic">Idle — No active task</span>
                          </div>
                        );
                      }
                      const progress = estimateProgress(mission);
                      return (
                        <div className="space-y-1.5 min-w-[200px]">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-[10px] font-bold text-shogun-text truncate max-w-[180px]" title={mission.title}>{mission.title}</span>
                            <span className="text-[9px] font-mono font-bold text-shogun-gold shrink-0">{progress}%</span>
                          </div>
                          <div className="w-full h-1.5 bg-[#0a0e1a] rounded-full overflow-hidden">
                            <div 
                              className={cn(
                                "h-full rounded-full transition-all duration-700",
                                progress < 30 ? "bg-gradient-to-r from-shogun-blue to-shogun-blue/70" :
                                progress < 70 ? "bg-gradient-to-r from-shogun-blue via-shogun-gold/60 to-shogun-gold" :
                                "bg-gradient-to-r from-shogun-gold to-green-400"
                              )}
                              style={{ width: `${progress}%` }}
                            />
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span className={cn(
                              "text-[8px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded",
                              mission.status === 'in_progress' ? "text-shogun-blue bg-shogun-blue/10" :
                              mission.status === 'pending' ? "text-shogun-gold bg-shogun-gold/10" :
                              "text-shogun-subdued bg-[#0a0e1a]"
                            )}>{mission.status.replace('_', ' ')}</span>
                            <span className="text-[8px] text-shogun-subdued">{mission.priority}</span>
                          </div>
                        </div>
                      );
                    })()}
                  </td>
                  <td className="p-4">
                    <div className="flex flex-col gap-1">
                      <code className="text-[10px] bg-shogun-card px-2 py-1 rounded border border-shogun-border text-shogun-blue w-fit">
                        {agent.slug}
                      </code>
                      {agent.samurai_profile?.samurai_role?.purpose && (
                        <p className="text-[9px] text-shogun-subdued italic line-clamp-1 max-w-[150px]" title={agent.samurai_profile.samurai_role.description}>
                          {agent.samurai_profile.samurai_role.purpose}
                        </p>
                      )}
                    </div>
                  </td>
                  <td className="p-4 text-xs text-shogun-subdued">
                    {new Date(agent.created_at).toLocaleDateString()}
                  </td>
                  <td className="p-4 text-right">
                    <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      {agent.status === 'active' ? (
                        <button 
                          onClick={() => handleAction(agent.id, 'suspend')}
                          className="p-1.5 hover:bg-shogun-blue/10 text-shogun-blue rounded transition-colors" 
                          title="Suspend Agent"
                        >
                          <Pause className="w-3.5 h-3.5" />
                        </button>
                      ) : (
                        <button 
                          onClick={() => handleAction(agent.id, 'resume')}
                          className="p-1.5 hover:bg-green-500/10 text-green-500 rounded transition-colors" 
                          title="Resume Agent"
                        >
                          <Play className="w-3.5 h-3.5" />
                        </button>
                      )}
                      <button 
                         onClick={() => handleAction(agent.id, 'delete')}
                         className="p-1.5 hover:bg-red-500/10 text-red-500 rounded transition-colors" 
                         title="Delete Agent"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                      <button className="p-1.5 hover:bg-shogun-gold/10 text-shogun-gold rounded transition-colors" title="Manage Config">
                        <MoreVertical className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Deploy Samurai Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-300">
          <div className="bg-[#0a0e1a] border border-shogun-border rounded-xl w-full max-w-lg shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300">
            <div className="bg-shogun-card border-b border-shogun-border p-6">
              <h3 className="text-xl font-bold text-shogun-gold">Deploy New Samurai</h3>
              <p className="text-[10px] text-shogun-subdued uppercase tracking-widest font-bold mt-1">Initialize fleet expansion</p>
            </div>

            <form onSubmit={handleCreate} className="p-8 space-y-6">
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-1.5 col-span-2">
                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Samurai Designation (Role)</label>
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
                          description: selectedRole.description || selectedRole.purpose
                        });
                      }
                    }}
                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue transition-colors outline-none cursor-pointer"
                  >
                    <option value="" disabled>Select a role...</option>
                    {samuraiRoles.map((role) => (
                      <option key={role.id} value={role.id}>{role.name}</option>
                    ))}
                  </select>
                </div>
                
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Custom Unit Name</label>
                  <input 
                    type="text" 
                    required
                    value={newAgent.name}
                    onChange={(e) => setNewAgent({ ...newAgent, name: e.target.value })}
                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue transition-colors outline-none"
                    placeholder="e.g. Shadow Scout"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Spawn Policy</label>
                  <select 
                    value={newAgent.spawn_policy}
                    onChange={(e) => setNewAgent({ ...newAgent, spawn_policy: e.target.value })}
                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue transition-colors outline-none cursor-pointer"
                  >
                    <option value="manual">Manual Deploy</option>
                    <option value="auto">Auto-Spawn (Reactive)</option>
                    <option value="scheduled">Scheduled Routine</option>
                  </select>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Operational Directive (Description)</label>
                <textarea 
                  value={newAgent.description}
                  onChange={(e) => setNewAgent({ ...newAgent, description: e.target.value })}
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-xs focus:border-shogun-blue transition-colors outline-none h-32 resize-none"
                  placeholder="Select a designation to auto-populate this..."
                />
              </div>

              <div className="flex gap-3 pt-2">
                <button 
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 bg-shogun-card hover:bg-[#1a2040] text-shogun-subdued font-bold py-3 rounded-lg transition-all border border-shogun-border"
                >
                  ABORT
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
                  DEPART MISSION
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
