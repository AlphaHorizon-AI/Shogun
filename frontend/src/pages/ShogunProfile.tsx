import { useState, useEffect, useRef } from 'react';
import { 
  User, 
  Shield, 
  Zap, 
  Cpu, 
  Save, 
  ChevronRight, 
  Code, 
  Workflow,
  CheckCircle2,
  AlertCircle,
  Activity,
  Database,
  Clock,
  Settings,
  RefreshCw,
  Server,
  X,
  GripVertical,
} from 'lucide-react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { cn } from '../lib/utils';
import { useTranslation } from '../i18n';

type TabType = 'general' | 'models' | 'behavior' | 'permissions' | 'operations';

export const ShogunProfile = () => {
  const [activeTab, setActiveTab] = useState<TabType>('general');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
  const [systemHealth, setSystemHealth] = useState<any>(null);
  const [customJob, setCustomJob] = useState({
    name: '',
    type: 'memory_consolidation',
    frequency: 'nightly',
    scheduleTime: '02:00',
    scheduleDays: ['mon', 'wed', 'fri'] as string[],
    scheduleDay: 1,
    minuteOffset: 0,
    scheduleDateTime: '',
    priority: 50,
    memoryTypes: ['episodic', 'semantic'] as string[],
    taskInstruction: '',
    allAgents: true,
    dryRun: false,
    autoApprove: false,
  });
  const [schedules, setSchedules] = useState<any[]>([]);
  const [runningJobs, setRunningJobs] = useState<Record<string, boolean>>({});
  const navigate = useNavigate();
  const { t } = useTranslation();
  
  const [shogunData, setShogunData] = useState<any>({
    name: 'Shogun Prime',
    slug: 'primary-shogun',
    status: 'active',
    persona_id: '',
    model_routing_profile_id: '',
    security_policy_id: '',
    description: 'Master orchestrator of the Samurai Network.',
    autonomy: 50,
    risk_tolerance: 'low',
    verbosity: 'medium',
  });

  const [personas, setPersonas] = useState<any[]>([]);
  const [routingProfiles, setRoutingProfiles] = useState<any[]>([]);
  const [securityPolicies, setSecurityPolicies] = useState<any[]>([]);
  const [providers, setProviders] = useState<any[]>([]);
  const [tools, setTools] = useState<any[]>([]);
  const [primaryModel, setPrimaryModel] = useState('');
  const [fallbackModels, setFallbackModels] = useState<string[]>([]);
  const [customPermissions, setCustomPermissions] = useState<any>(null);
  const [customPolicyName, setCustomPolicyName] = useState('');

  // Compute security risk score from permissions (keys are lowercase in DB)
  const computeRiskScore = (perms: any): number => {
    if (!perms) return 0;
    let risk = 0;
    const check = (cat: string, key: string, riskyVals: any[], weight: number) => {
      // Support both lowercase and uppercase keys
      const category = perms?.[cat] || perms?.[cat.toUpperCase()] || perms?.[cat.toLowerCase()];
      if (!category) return;
      const val = category[key] ?? category[key.toUpperCase()] ?? category[key.toLowerCase()];
      if (val !== undefined && riskyVals.includes(val)) risk += weight;
    };
    // Risky permissions (add risk)
    check('filesystem', 'mode', ['full', 'FULL'], 15);
    check('filesystem', 'allow_home_access', [true], 10);
    check('filesystem', 'allow_arbitrary_paths', [true], 15);
    check('network', 'mode', ['full', 'FULL'], 15);
    check('network', 'allow_arbitrary_requests', [true], 10);
    check('shell', 'enabled', [true], 15);
    check('skills', 'allow_auto_install', [true], 5);
    check('skills', 'allow_untrusted', [true], 10);
    check('subagents', 'allow_spawn', [true], 5);
    check('subagents', 'allow_auto_spawn', [true], 10);
    check('memory', 'allow_bulk_delete', [true], 10);
    // Restrictive permissions (reduce risk)
    check('filesystem', 'mode', ['scoped', 'SCOPED', 'disabled', 'DISABLED'], -5);
    check('network', 'mode', ['disabled', 'DISABLED'], -10);
    check('shell', 'enabled', [false], -5);
    check('skills', 'require_approval', [true], -5);
    return Math.max(0, Math.min(100, risk));
  };

  // Plain-language tooltips for permission properties
  const permissionTooltips: Record<string, Record<string, string>> = {
    filesystem: {
      _category: 'Controls what files and folders the agent can read, write, or access on your system.',
      mode: 'How freely the agent can access files. "Full" = unrestricted, "Scoped" = only in designated folders, "Disabled" = no file access.',
      allowed_paths: 'Specific folders the agent is allowed to work in when in Scoped mode.',
      allow_home_access: 'Whether the agent can read or write files in your personal home directory.',
      allow_arbitrary_paths: 'Whether the agent can access ANY folder on the system, even outside its designated workspace.',
    },
    network: {
      _category: 'Controls whether the agent can make internet requests, call APIs, or reach external services.',
      mode: 'How freely the agent can use the network. "Full" = unrestricted, "Allowlist" = only approved sites, "Disabled" = no internet.',
      allowed_domains: 'Specific websites or APIs the agent is allowed to contact when in Allowlist mode.',
      allow_arbitrary_requests: 'Whether the agent can contact ANY website or API, even ones not on the approved list.',
    },
    shell: {
      _category: 'Controls whether the agent can run system commands (like terminal/command-line operations).',
      enabled: 'Whether the agent is allowed to execute system commands at all.',
      allowed_binaries: 'Specific programs the agent is allowed to run (e.g., "python", "git"). Empty means none.',
    },
    skills: {
      _category: 'Controls how the agent discovers, installs, and uses skill modules (plugins).',
      allow_auto_install: 'Whether the agent can automatically download and install new skills without asking.',
      require_approval: 'Whether a human must approve before the agent uses any new skill for the first time.',
      allow_untrusted: 'Whether the agent can use skills from unverified or third-party sources.',
    },
    subagents: {
      _category: 'Controls whether the agent can create and manage helper agents (Samurai) to delegate tasks.',
      allow_spawn: 'Whether the agent is allowed to create sub-agents at all.',
      max_active: 'Maximum number of sub-agents that can be running at the same time.',
      allow_auto_spawn: 'Whether the agent can create sub-agents on its own without asking for permission first.',
    },
    memory: {
      _category: 'Controls how the agent stores and manages its knowledge and conversation history.',
      allow_write: 'Whether the agent can save new information to its long-term memory.',
      allow_bulk_delete: 'Whether the agent can erase large amounts of its stored knowledge at once.',
    },
  };

  const getTooltip = (category: string, prop?: string): string => {
    const catKey = category.toLowerCase();
    if (!prop) return permissionTooltips[catKey]?._category || '';
    return permissionTooltips[catKey]?.[prop.toLowerCase()] || permissionTooltips[catKey]?.[prop] || '';
  };

  const activePermissions = customPermissions || securityPolicies.find(p => p.id === shogunData.security_policy_id)?.permissions || null;
  const basePermissions = securityPolicies.find(p => p.id === shogunData.security_policy_id)?.permissions || null;
  const isCustomPolicy = customPermissions !== null && JSON.stringify(customPermissions) !== JSON.stringify(basePermissions);
  const riskScore = computeRiskScore(activePermissions);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const results = await Promise.allSettled([
        axios.get('/api/v1/agents/shogun'),
        axios.get('/api/v1/personas'),
        axios.get('/api/v1/model-routing-profiles'),
        axios.get('/api/v1/security/policies'),
        axios.get('/api/v1/system/health'),
        axios.get('/api/v1/model-providers'),
        axios.get('/api/v1/tools'),
      ]);
      
      const [agentRes, personasRes, routingRes, policiesRes, healthRes, providersRes, toolsRes] = results;

      if (agentRes.status === 'fulfilled' && agentRes.value.data.data) {
        const agent = agentRes.value.data.data;
        setShogunData(agent);
        // ── Restore model selections saved in bushido_settings ──
        const bs = agent.bushido_settings || {};
        if (bs.primary_model) setPrimaryModel(bs.primary_model);
        if (bs.fallback_models) setFallbackModels(bs.fallback_models);
        if (bs.custom_permissions) setCustomPermissions(bs.custom_permissions);
      }
      if (healthRes.status === 'fulfilled' && healthRes.value.data.data) {
        setSystemHealth(healthRes.value.data.data);
      }
      if (personasRes.status === 'fulfilled' && personasRes.value.data.data) {
        setPersonas(personasRes.value.data.data);
      }
      if (routingRes.status === 'fulfilled' && routingRes.value.data.data) {
        setRoutingProfiles(routingRes.value.data.data);
      }
      if (policiesRes.status === 'fulfilled' && policiesRes.value.data.data) {
        setSecurityPolicies(policiesRes.value.data.data);
      }
      if (providersRes.status === 'fulfilled' && providersRes.value.data.data) {
        setProviders(providersRes.value.data.data);
      }
      if (toolsRes.status === 'fulfilled' && toolsRes.value.data.data) {
        setTools(toolsRes.value.data.data);
      }
      // Fetch schedules separately (non-fatal)
      try {
        const schRes = await axios.get('/api/v1/bushido/schedules');
        if (schRes.data.data) setSchedules(schRes.data.data);
      } catch { /* schedules table may not exist yet on first boot */ }
    } catch (error) {
      console.error('Error fetching Shogun data:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchSchedules = async () => {
    try {
      const res = await axios.get('/api/v1/bushido/schedules');
      if (res.data.data) setSchedules(res.data.data);
    } catch { /* ignore */ }
  };

  const handlePresetToggle = async (jobType: string) => {
    try {
      const res = await axios.patch(`/api/v1/bushido/schedules/preset/${jobType}/toggle`);
      if (res.data.data) {
        setSchedules(prev => prev.map(s => s.job_type === jobType ? res.data.data : s));
      }
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to toggle schedule.' });
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };

  const getPresetSchedule = (jobType: string) => schedules.find(s => s.job_type === jobType && s.is_preset);

  const handleSave = async () => {
    setSaving(true);
    setStatusMessage(null);
    try {
      // Merge model selections + custom permissions into bushido_settings so they persist
      const payload = {
        ...shogunData,
        bushido_settings: {
          ...(shogunData.bushido_settings || {}),
          primary_model: primaryModel,
          fallback_models: fallbackModels,
          // Persist custom permission overrides (e.g. allowed_domains, network mode)
          custom_permissions: customPermissions,
        },
      };
      await axios.patch(`/api/v1/agents/${(shogunData as any).id}`, payload);
      setStatusMessage({ type: 'success', text: 'Shogun configuration saved successfully.' });
    } catch (error) {
      setStatusMessage({ type: 'error', text: 'Failed to save configuration.' });
    } finally {
      setSaving(false);
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleAvatarClick = () => {
    fileInputRef.current?.click();
  };

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      setStatusMessage({ type: 'success', text: 'Uploading avatar...' });
      const res = await axios.post(`/api/v1/agents/${(shogunData as any).id}/avatar`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setShogunData({ ...shogunData, avatar_url: res.data.data.avatar_url });
      setStatusMessage({ type: 'success', text: 'Avatar updated successfully.' });
    } catch (error) {
      console.error('Avatar upload failed:', error);
      setStatusMessage({ type: 'error', text: 'Failed to upload avatar.' });
    } finally {
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-8 h-8 border-4 border-shogun-gold border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-5xl mx-auto pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-6">
          <div 
            onClick={handleAvatarClick}
            className="w-20 h-20 bg-shogun-card rounded-2xl border border-shogun-gold/30 flex items-center justify-center shadow-shogun relative cursor-pointer group hover:border-shogun-gold/60 transition-all overflow-hidden"
          >
            {shogunData.avatar_url ? (
              <img src={shogunData.avatar_url} alt="Shogun Avatar" className="w-full h-full object-cover" />
            ) : (
              <img src="/assets/shogun-default-avatar.jpg" alt="Shogun Avatar" className="w-full h-full object-cover" />
            )}
            <div className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
              <Cpu className="w-6 h-6 text-shogun-gold" />
            </div>
            <div className="absolute -bottom-1 -right-1 w-5 h-5 bg-green-500 border-2 border-[#0a0e1a] rounded-full shadow-lg" />
          </div>
          <input 
            type="file" 
            ref={fileInputRef} 
            className="hidden" 
            accept="image/*"
            onChange={handleAvatarUpload}
          />
          <div>
            <h2 className="text-3xl font-bold shogun-title">{shogunData.name}</h2>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-[10px] bg-shogun-gold/10 text-shogun-gold px-2 py-0.5 rounded border border-shogun-gold/20 font-bold tracking-widest uppercase">
                {t('shogun_profile.primary_agent', 'Primary Agent')}
              </span>
              <span className="text-xs text-shogun-subdued flex items-center gap-1">
                <Workflow className="w-3 h-3" /> System Orchestrator
              </span>
            </div>
          </div>
        </div>
        
        <button 
          onClick={handleSave}
          disabled={saving}
          className="flex items-center justify-center gap-2 bg-shogun-gold hover:bg-shogun-gold/90 text-black font-bold py-2 px-6 rounded-lg transition-all shadow-shogun disabled:opacity-50"
        >
          {saving ? <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" /> : <Save className="w-4 h-4" />}
          {t('common.save_changes', 'SAVE CHANGES')}
        </button>
      </div>

      {statusMessage && (
        <div className={cn(
          "p-3 rounded-lg flex items-center gap-3 animate-in slide-in-from-top-2",
          statusMessage.type === 'success' ? "bg-green-500/10 text-green-500 border border-green-500/20" : "bg-red-500/10 text-red-500 border border-red-500/20"
        )}>
          {statusMessage.type === 'success' ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
          <span className="text-sm font-medium">{statusMessage.text}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-shogun-border">
        {(['general', 'models', 'behavior', 'permissions', 'operations'] as TabType[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              "px-6 py-3 text-sm font-bold uppercase tracking-widest transition-all relative",
              activeTab === tab ? "text-shogun-gold" : "text-shogun-subdued hover:text-shogun-text"
            )}
          >
            {t(`shogun_profile.tab_${tab}`, tab)}
            {activeTab === tab && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-shogun-gold shadow-[0_0_10px_rgba(212,160,23,0.5)]" />
            )}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {activeTab === 'general' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="shogun-card space-y-4">
              <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                <User className="w-5 h-5 text-shogun-gold" /> {t('shogun_profile.identity', 'Identity & Persona')}
              </h3>
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t("profile.agent_name", "Agent Name")}</label>
                  <input 
                    type="text" 
                    value={shogunData.name}
                    onChange={(e) => setShogunData({ ...shogunData, name: e.target.value })}
                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-gold transition-colors"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t("profile.active_persona", "Active Persona")}</label>
                  <select 
                    value={shogunData.persona_id || ''}
                    onChange={(e) => {
                      const persona = personas.find(p => p.id === e.target.value);
                      setShogunData({ 
                        ...shogunData, 
                        persona_id: e.target.value,
                        description: persona?.description || shogunData.description,
                        autonomy: persona ? (persona.autonomy === "high" ? 80 : persona.autonomy === "low" ? 20 : 50) : shogunData.autonomy,
                        risk_tolerance: persona?.risk_tolerance || shogunData.risk_tolerance,
                        verbosity: persona?.verbosity || shogunData.verbosity,
                        tone: persona?.tone || shogunData.tone || 'analytical',
                        planning_depth: persona?.planning_depth || shogunData.planning_depth || 'medium',
                        tool_usage_style: persona?.tool_usage_style || shogunData.tool_usage_style || 'balanced',
                        security_bias: persona?.security_bias || shogunData.security_bias || 'balanced',
                        memory_style: persona?.memory_style || shogunData.memory_style || 'focused',
                      });
                    }}
                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-gold transition-colors"
                  >
                    <option value="">Select a persona...</option>
                    {personas.map(p => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                  {shogunData.persona_id && (() => {
                    const p = personas.find(p => p.id === shogunData.persona_id);
                    if (!p) return null;
                    return (
                      <div className="grid grid-cols-3 gap-1.5 mt-2">
                        <span className="text-[8px] text-center py-1 rounded bg-shogun-gold/10 text-shogun-gold border border-shogun-gold/20 uppercase font-bold">{p.tone}</span>
                        <span className="text-[8px] text-center py-1 rounded bg-shogun-blue/10 text-shogun-blue border border-shogun-blue/20 uppercase font-bold">{p.security_bias}</span>
                        <span className="text-[8px] text-center py-1 rounded bg-green-500/10 text-green-500 border border-green-500/20 uppercase font-bold">{p.autonomy}</span>
                      </div>
                    );
                  })()}
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t("profile.description", "Description")}</label>
                  <textarea 
                    value={shogunData.description || ''}
                    onChange={(e) => setShogunData({ ...shogunData, description: e.target.value })}
                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-gold transition-colors min-h-[100px]"
                  />
                </div>
              </div>
            </div>

            <div className="shogun-card space-y-4">
              <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                <Zap className="w-5 h-5 text-shogun-blue" /> {t('shogun_profile.autonomy_logic', 'Autonomy & Logic')}
              </h3>
              <div className="space-y-5 pt-2">
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t("profile.autonomy_level", "Autonomy Level")}</label>
                    <span className="text-shogun-blue font-mono font-bold">{shogunData.autonomy}%</span>
                  </div>
                  <input 
                    type="range" 
                    min="0" 
                    max="100" 
                    step="10"
                    value={shogunData.autonomy}
                    onChange={(e) => setShogunData({ ...shogunData, autonomy: parseInt(e.target.value) })}
                    className="w-full accent-shogun-blue"
                  />
                  <p className="text-[10px] text-shogun-subdued italic">Higher levels allow Shogun to spawn sub-agents and execute complex tools without explicit operator confirmation.</p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('setup.step3_tone', 'Tone')}</label>
                    <select 
                      value={shogunData.tone || 'analytical'}
                      onChange={(e) => setShogunData({ ...shogunData, tone: e.target.value })}
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2 text-xs focus:border-shogun-blue transition-colors"
                    >
                      <option value="analytical">{t('setup.step3_tone_analytical', 'Analytical')}</option>
                      <option value="direct">{t('setup.step3_tone_direct', 'Direct')}</option>
                      <option value="supportive">{t('setup.step3_tone_supportive', 'Supportive')}</option>
                      <option value="strategic">{t('setup.step3_tone_strategic', 'Strategic')}</option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('setup.step3_risk', 'Risk Tolerance')}</label>
                    <select 
                      value={shogunData.risk_tolerance}
                      onChange={(e) => setShogunData({ ...shogunData, risk_tolerance: e.target.value })}
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2 text-xs focus:border-shogun-blue transition-colors"
                    >
                      <option value="low">{t('setup.step3_risk_low', 'Low (Cautious)')}</option>
                      <option value="medium">{t('setup.step3_risk_medium', 'Medium (Balanced)')}</option>
                      <option value="high">{t('setup.step3_risk_high', 'High (Aggressive)')}</option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('setup.step3_verbosity', 'Verbosity')}</label>
                    <select 
                      value={shogunData.verbosity}
                      onChange={(e) => setShogunData({ ...shogunData, verbosity: e.target.value })}
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2 text-xs focus:border-shogun-blue transition-colors"
                    >
                      <option value="low">{t('setup.step3_verbosity_low', 'Concise')}</option>
                      <option value="medium">{t('setup.step3_verbosity_medium', 'Moderate')}</option>
                      <option value="high">{t('setup.step3_verbosity_high', 'Detailed')}</option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('setup.step3_planning', 'Planning Depth')}</label>
                    <select 
                      value={shogunData.planning_depth || 'medium'}
                      onChange={(e) => setShogunData({ ...shogunData, planning_depth: e.target.value })}
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2 text-xs focus:border-shogun-blue transition-colors"
                    >
                      <option value="low">{t('setup.step3_planning_low', 'Shallow (Act fast)')}</option>
                      <option value="medium">{t('setup.step3_planning_medium', 'Standard (Plan then act)')}</option>
                      <option value="high">{t('setup.step3_planning_high', 'Deep (Exhaustive planning)')}</option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('setup.step3_tool_usage', 'Tool Usage')}</label>
                    <select 
                      value={shogunData.tool_usage_style || 'balanced'}
                      onChange={(e) => setShogunData({ ...shogunData, tool_usage_style: e.target.value })}
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2 text-xs focus:border-shogun-blue transition-colors"
                    >
                      <option value="conservative">{t('setup.step3_tool_conservative', 'Conservative (Minimal)')}</option>
                      <option value="balanced">{t('setup.step3_tool_balanced', 'Balanced')}</option>
                      <option value="aggressive">{t('setup.step3_tool_aggressive', 'Aggressive (Chain freely)')}</option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('setup.step3_security_bias', 'Security Bias')}</label>
                    <select 
                      value={shogunData.security_bias || 'balanced'}
                      onChange={(e) => setShogunData({ ...shogunData, security_bias: e.target.value })}
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2 text-xs focus:border-shogun-blue transition-colors"
                    >
                      <option value="strict">{t('setup.step3_security_strict', 'Strict (Least privilege)')}</option>
                      <option value="balanced">{t('setup.step3_security_balanced', 'Balanced')}</option>
                      <option value="open">{t('setup.step3_security_open', 'Open (Trust-first)')}</option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('setup.step3_memory', 'Memory Style')}</label>
                    <select 
                      value={shogunData.memory_style || 'focused'}
                      onChange={(e) => setShogunData({ ...shogunData, memory_style: e.target.value })}
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2 text-xs focus:border-shogun-blue transition-colors"
                    >
                      <option value="conservative">{t('setup.step3_memory_conservative', 'Conservative (Minimal retention)')}</option>
                      <option value="focused">{t('setup.step3_memory_focused', 'Focused (Task-relevant)')}</option>
                      <option value="expansive">{t('setup.step3_memory_expansive', 'Expansive (Broad context)')}</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'models' && (() => {
          // Build a flat list of all available model options from every provider
          const allModelOptions = providers
            .filter(p => p.status !== 'disabled')
            .flatMap((prov: any) => {
              const modelIds: string[] = prov.config?.models?.length
                ? prov.config.models
                : prov.config?.model_id
                  ? [prov.config.model_id]
                  : [prov.name];
              return modelIds.map((modelId: string) => ({
                value: `${prov.id}::${modelId}`,
                label: modelId,
                group: `${prov.provider_type?.toUpperCase()} — ${prov.name}`,
                providerType: prov.provider_type,
              }));
            });

          return (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* ── Primary Model ──────────────────────────────── */}
              <div className="shogun-card space-y-4">
                <div>
                  <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                    <Cpu className="w-5 h-5 text-shogun-blue" /> Primary Model
                  </h3>
                  <p className="text-[10px] text-shogun-subdued mt-1">The default model used for all Shogun reasoning and task execution.</p>
                </div>

                {allModelOptions.length === 0 ? (
                  <div className="p-4 bg-[#050508] border border-shogun-border rounded-xl text-center space-y-2">
                    <p className="text-sm text-shogun-subdued">No active providers found.</p>
                    <button onClick={() => navigate('/katana')} className="text-xs text-shogun-blue hover:text-shogun-gold font-bold uppercase tracking-widest">
                      Configure in The Katana →
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t("profile.select_model", "Select Model")}</label>
                    <select
                      value={primaryModel}
                      onChange={e => setPrimaryModel(e.target.value)}
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm font-mono focus:border-shogun-gold outline-none transition-colors"
                    >
                      <option value="">— Choose a model —</option>
                      {providers.filter(p => p.status !== 'disabled').map((prov: any) => {
                        const modelIds: string[] = prov.config?.models?.length
                          ? prov.config.models
                          : prov.config?.model_id
                            ? [prov.config.model_id]
                            : [prov.name];
                        return (
                          <optgroup key={prov.id} label={`${prov.provider_type?.toUpperCase()} — ${prov.name}`}>
                            {modelIds.map((modelId: string) => (
                              <option key={`${prov.id}::${modelId}`} value={`${prov.id}::${modelId}`}>
                                {modelId}
                              </option>
                            ))}
                          </optgroup>
                        );
                      })}
                    </select>

                    {primaryModel && (
                      <div className="flex items-center gap-2 p-2.5 rounded-lg bg-shogun-gold/5 border border-shogun-gold/20">
                        <CheckCircle2 className="w-3.5 h-3.5 text-shogun-gold shrink-0" />
                        <span className="text-xs font-mono text-shogun-gold font-bold truncate">
                          {primaryModel.split('::')[1]}
                        </span>
                        <span className="text-[9px] text-shogun-subdued ml-auto shrink-0">PRIMARY</span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* ── Fallback Models ────────────────────────────── */}
              <div className="shogun-card space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                      <Workflow className="w-5 h-5 text-shogun-gold" /> Fallback Models
                    </h3>
                    <p className="text-[10px] text-shogun-subdued mt-1">Used when the primary is unavailable. Order matters.</p>
                  </div>
                  <span className="text-[10px] bg-shogun-gold/10 text-shogun-gold px-2 py-0.5 rounded border border-shogun-gold/20 font-bold shrink-0">
                    {fallbackModels.length} selected
                  </span>
                </div>

                {allModelOptions.length === 0 ? (
                  <div className="p-4 bg-[#050508] border border-shogun-border rounded-xl text-center">
                    <p className="text-sm text-shogun-subdued">No active providers.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {/* Add dropdown */}
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t("profile.add_fallback", "Add Fallback")}</label>
                      <select
                        value=""
                        onChange={e => {
                          const val = e.target.value;
                          if (val && val !== primaryModel && !fallbackModels.includes(val)) {
                            setFallbackModels(prev => [...prev, val]);
                          }
                        }}
                        className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm font-mono focus:border-shogun-blue outline-none transition-colors"
                      >
                        <option value="">— Add a fallback model —</option>
                        {providers.filter(p => p.status !== 'disabled').map((prov: any) => {
                          const modelIds: string[] = prov.config?.models?.length
                            ? prov.config.models
                            : prov.config?.model_id
                              ? [prov.config.model_id]
                              : [prov.name];
                          return (
                            <optgroup key={prov.id} label={`${prov.provider_type?.toUpperCase()} — ${prov.name}`}>
                              {modelIds
                                .filter((modelId: string) => {
                                  const key = `${prov.id}::${modelId}`;
                                  return key !== primaryModel && !fallbackModels.includes(key);
                                })
                                .map((modelId: string) => (
                                  <option key={`${prov.id}::${modelId}`} value={`${prov.id}::${modelId}`}>
                                    {modelId}
                                  </option>
                                ))}
                            </optgroup>
                          );
                        })}
                      </select>
                    </div>

                    {/* Selected fallbacks as draggable ordered chips */}
                    {fallbackModels.length > 0 ? (
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t("profile.fallback_order", "Fallback Order")}</label>
                        <p className="text-[9px] text-shogun-subdued/50">Drag to reorder priority.</p>
                        {fallbackModels.map((fm, i) => (
                          <div
                            key={fm}
                            draggable
                            onDragStart={e => { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(i)); }}
                            onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }}
                            onDrop={e => {
                              e.preventDefault();
                              const from = Number(e.dataTransfer.getData('text/plain'));
                              if (from === i) return;
                              setFallbackModels(prev => {
                                const next = [...prev];
                                const [moved] = next.splice(from, 1);
                                next.splice(i, 0, moved);
                                return next;
                              });
                            }}
                            className="flex items-center gap-2 p-2.5 rounded-lg border border-shogun-blue/20 bg-shogun-blue/5 cursor-grab active:cursor-grabbing active:border-shogun-blue/50 active:bg-shogun-blue/10 transition-colors select-none"
                          >
                            <GripVertical className="w-3.5 h-3.5 text-shogun-subdued/40 shrink-0" />
                            <span className="text-[9px] font-bold text-shogun-blue w-5 shrink-0">#{i + 1}</span>
                            <span className="text-xs font-mono text-shogun-text flex-1 truncate">{fm.split('::')[1]}</span>
                            <button
                              onClick={() => setFallbackModels(prev => prev.filter(f => f !== fm))}
                              className="text-shogun-subdued hover:text-red-400 transition-colors shrink-0 p-0.5"
                              title="Remove"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-[11px] text-shogun-subdued italic text-center py-2">No fallbacks selected — the primary model will always be used.</p>
                    )}
                  </div>
                )}

                {/* Routing Strategy */}
                {routingProfiles.length > 0 && (
                  <div className="space-y-2 pt-2 border-t border-shogun-border">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t("profile.routing_strategy", "Routing Strategy")}</label>
                    <select
                      value={shogunData.model_routing_profile_id || ''}
                      onChange={e => setShogunData({ ...shogunData, model_routing_profile_id: e.target.value })}
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none transition-colors"
                    >
                      <option value="">— Select routing strategy —</option>
                      {routingProfiles.map((rp: any) => (
                        <option key={rp.id} value={rp.id}>{rp.name}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            </div>
          );
        })()}


        {activeTab === 'behavior' && (
          <div className="shogun-card">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                <Code className="w-5 h-5 text-shogun-gold" /> {t('shogun_profile.behavioral_directives', 'Behavioral Directives')}
              </h3>
              <span className="text-[10px] font-mono text-shogun-subdued">v1.0.4-LTS</span>
            </div>
            <div className="relative group">
              <textarea 
                spellCheck={false}
                defaultValue={`priorities:
  - Safety before autonomy
  - Use existing trusted skills when possible
  - Escalate ambiguous high-risk actions
  - Maintain stealth in network operations

operational_constraints:
  - shell_access: restricted_to_container
  - memory_retention: long_term
  - verification_threshold: 0.85

delegation_rules:
  - research: delegate_to_samurai
  - coding: delegate_to_samurai
  - tactical_analysis: shogun_priority`}
                className="w-full bg-[#050508] border border-shogun-border rounded-xl p-6 font-mono text-xs leading-relaxed text-shogun-text focus:border-shogun-gold transition-colors min-h-[400px] resize-y scrollbar-hide"
              />
              <div className="absolute top-4 right-4 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <span className="text-[10px] bg-shogun-card px-2 py-1 rounded border border-shogun-border text-shogun-subdued">YAML Mode</span>
              </div>
            </div>
            <p className="text-[10px] text-shogun-subdued mt-4 italic">
              * Note: These directives are the core philosophical foundation that Shogun uses to validate its own reasoning processes.
            </p>
          </div>
        )}

        {activeTab === 'permissions' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="shogun-card space-y-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                  <Shield className="w-5 h-5 text-shogun-gold" /> {t('shogun_profile.authority_metrics', 'Authority Metrics')}
                </h3>
                {isCustomPolicy && (
                  <span className="text-[9px] font-bold uppercase tracking-widest px-2 py-1 rounded border border-shogun-blue/30 bg-shogun-blue/10 text-shogun-blue">Custom</span>
                )}
              </div>

              {/* Risk Meter */}
              <div className="p-4 bg-[#050508] rounded-xl border border-shogun-border">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Security Risk Index</span>
                  <span className={cn(
                    "text-sm font-bold font-mono",
                    riskScore <= 25 ? "text-green-400" : riskScore <= 50 ? "text-shogun-gold" : riskScore <= 75 ? "text-orange-400" : "text-red-400"
                  )}>{riskScore}/100</span>
                </div>
                <div className="w-full h-2.5 bg-[#0a0e1a] rounded-full overflow-hidden">
                  <div 
                    className={cn(
                      "h-full rounded-full transition-all duration-500",
                      riskScore <= 25 ? "bg-gradient-to-r from-green-500 to-green-400" : 
                      riskScore <= 50 ? "bg-gradient-to-r from-green-400 via-yellow-400 to-shogun-gold" : 
                      riskScore <= 75 ? "bg-gradient-to-r from-yellow-400 via-orange-400 to-orange-500" : 
                      "bg-gradient-to-r from-orange-500 via-red-500 to-red-600"
                    )}
                    style={{ width: `${riskScore}%` }}
                  />
                </div>
                <div className="flex justify-between mt-1">
                  <span className="text-[8px] text-green-400/60">LOCKED DOWN</span>
                  <span className="text-[8px] text-shogun-gold/60">BALANCED</span>
                  <span className="text-[8px] text-red-400/60">PERMISSIVE</span>
                </div>
              </div>

              <div className="space-y-3">
                 <div className="space-y-1.5">
                   <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t("profile.base_policy", "Base Policy")}</label>
                   <select 
                     value={shogunData.security_policy_id || ''}
                     onChange={(e) => {
                       setShogunData({ ...shogunData, security_policy_id: e.target.value });
                       setCustomPermissions(null);
                       setCustomPolicyName('');
                     }}
                     className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-gold transition-colors"
                   >
                     <option value="">Select security tier...</option>
                     {securityPolicies.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                   </select>
                 </div>

                {/* Custom policy name (shown when modified) */}
                {isCustomPolicy && (
                  <div className="space-y-1.5 p-3 bg-shogun-blue/5 border border-shogun-blue/20 rounded-xl">
                    <label className="text-[10px] font-bold text-shogun-blue uppercase tracking-widest">{t("profile.custom_policy_name", "Custom Policy Name")}</label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={customPolicyName}
                        onChange={(e) => setCustomPolicyName(e.target.value)}
                        placeholder="e.g. Project Alpha — Relaxed"
                        className="flex-1 bg-[#050508] border border-shogun-border rounded-lg p-2 text-xs focus:border-shogun-blue transition-colors"
                      />
                      <button className="px-4 py-2 bg-shogun-blue/20 border border-shogun-blue/30 rounded-lg text-[10px] font-bold text-shogun-blue uppercase tracking-widest hover:bg-shogun-blue/30 transition-all">
                        Save
                      </button>
                    </div>
                  </div>
                )}
                
                {activePermissions ? (
                  Object.entries(activePermissions).map(([category, perms]: [string, any], i) => (
                    <div key={i} className="p-3 bg-[#050508] rounded-xl border border-shogun-border space-y-2">
                      <div className="flex items-center gap-2 pb-1 border-b border-shogun-border/50 group/cat">
                        <Shield className="w-3.5 h-3.5 text-shogun-gold" />
                        <div className="relative">
                          <span className="text-xs font-bold uppercase tracking-wider text-shogun-text cursor-help">{category.replace(/_/g, ' ')}</span>
                          {getTooltip(category) && (
                            <div className="absolute left-0 bottom-full mb-2 w-64 p-2.5 bg-[#0a0e1a] border border-shogun-gold/30 rounded-lg text-[10px] text-shogun-text leading-relaxed shadow-xl opacity-0 pointer-events-none group-hover/cat:opacity-100 transition-opacity duration-200 z-50">
                              <div className="absolute -bottom-1 left-4 w-2 h-2 bg-[#0a0e1a] border-r border-b border-shogun-gold/30 rotate-45" />
                              {getTooltip(category)}
                            </div>
                          )}
                        </div>
                      </div>
                      {typeof perms === 'object' && perms !== null && !Array.isArray(perms) ? (
                        <div className="grid gap-1">
                          {Object.entries(perms).map(([prop, propVal]: [string, any], j) => {
                            const isBool = typeof propVal === 'boolean';
                            const isMode = prop.toLowerCase() === 'mode';
                            const isNumber = typeof propVal === 'number';
                            const isArray = Array.isArray(propVal);
                            
                            const togglePermission = (newVal: any) => {
                              const updated = JSON.parse(JSON.stringify(activePermissions));
                              updated[category][prop] = newVal;
                              setCustomPermissions(updated);
                            };

                            return (
                              <div key={j} className={cn("py-1.5 px-2 rounded hover:bg-[#0a0e1a] transition-colors", isArray ? "space-y-2" : "flex items-center justify-between")}>
                                <div className="relative group/tip">
                                  <span className={cn("text-[10px] text-shogun-subdued font-medium capitalize", getTooltip(category, prop) && "border-b border-dashed border-shogun-subdued/30 cursor-help")}>{prop.replace(/_/g, ' ').toLowerCase()}</span>
                                  {getTooltip(category, prop) && (
                                    <div className="absolute left-0 bottom-full mb-2 w-56 p-2 bg-[#0a0e1a] border border-shogun-border rounded-lg text-[10px] text-shogun-text/80 leading-relaxed shadow-xl opacity-0 pointer-events-none group-hover/tip:opacity-100 transition-opacity duration-200 z-50">
                                      <div className="absolute -bottom-1 left-3 w-2 h-2 bg-[#0a0e1a] border-r border-b border-shogun-border rotate-45" />
                                      {getTooltip(category, prop)}
                                    </div>
                                  )}
                                </div>
                                <div className={cn("flex items-center gap-2", isArray && "flex-wrap")}>
                                  {isBool ? (
                                    <button
                                      onClick={() => togglePermission(!propVal)}
                                      className={cn(
                                        "w-10 h-5 rounded-full relative transition-all duration-300 border",
                                        propVal 
                                          ? "bg-green-500/20 border-green-500/40" 
                                          : "bg-red-500/10 border-red-500/30"
                                      )}
                                    >
                                      <div className={cn(
                                        "absolute top-0.5 w-4 h-4 rounded-full transition-all duration-300",
                                        propVal ? "left-5 bg-green-400" : "left-0.5 bg-red-400"
                                      )} />
                                    </button>
                                  ) : isMode ? (
                                    <select
                                      value={String(propVal)}
                                      onChange={(e) => togglePermission(e.target.value)}
                                      className="bg-[#0a0a10] border border-shogun-border rounded px-2 py-0.5 text-[10px] font-bold uppercase text-shogun-gold focus:border-shogun-gold transition-colors"
                                    >
                                      <option value="full">Full</option>
                                      <option value="scoped">Scoped</option>
                                      <option value="allowlist">Allowlist</option>
                                      <option value="disabled">Disabled</option>
                                    </select>
                                  ) : isNumber ? (
                                    <input
                                      type="number"
                                      value={propVal}
                                      onChange={(e) => togglePermission(parseInt(e.target.value) || 0)}
                                      className="w-16 bg-[#0a0a10] border border-shogun-border rounded px-2 py-0.5 text-[10px] font-bold text-shogun-blue text-center focus:border-shogun-blue transition-colors"
                                    />
                                  ) : isArray ? (
                                    <div className="w-full space-y-1.5">
                                      <div className="flex flex-wrap gap-1">
                                        {propVal.length === 0 && (
                                          <span className="text-[9px] text-shogun-subdued italic">
                                            {category.toLowerCase() === 'network' && prop.toLowerCase() === 'allowed_domains' 
                                              ? 'No APIs selected — choose from the Katana Toolbox below' 
                                              : 'No entries — type below to add'}
                                          </span>
                                        )}
                                        {propVal.map((item: string, k: number) => (
                                          <span key={k} className="inline-flex items-center gap-1 text-[9px] font-mono bg-shogun-gold/10 text-shogun-gold border border-shogun-gold/20 px-2 py-0.5 rounded">
                                            {item}
                                            <button 
                                              onClick={() => {
                                                const newArr = [...propVal];
                                                newArr.splice(k, 1);
                                                togglePermission(newArr);
                                              }}
                                              className="text-shogun-gold/50 hover:text-red-400 transition-colors ml-0.5"
                                            >×</button>
                                          </span>
                                        ))}
                                      </div>
                                      {/* Provider-based selector for allowed_domains */}
                                      {category.toLowerCase() === 'network' && prop.toLowerCase() === 'allowed_domains' ? (
                                        <div className="space-y-1">
                                          {tools.length > 0 ? (
                                            tools.map((tool: any) => {
                                              const domain = tool.base_url ? (() => { try { return new URL(tool.base_url).hostname; } catch { return tool.slug; } })() : tool.slug;
                                              const isSelected = propVal.includes(domain);
                                              return (
                                                <button
                                                  key={tool.id}
                                                  onClick={() => {
                                                    if (isSelected) {
                                                      togglePermission(propVal.filter((d: string) => d !== domain));
                                                    } else {
                                                      togglePermission([...propVal, domain]);
                                                    }
                                                  }}
                                                  className={cn(
                                                    "w-full flex items-center justify-between p-2 rounded-lg border text-left transition-all",
                                                    isSelected 
                                                      ? "border-shogun-gold/40 bg-shogun-gold/5" 
                                                      : "border-shogun-border hover:border-shogun-subdued"
                                                  )}
                                                >
                                                  <div className="flex items-center gap-2">
                                                    <div className={cn(
                                                      "w-3.5 h-3.5 rounded border-2 flex items-center justify-center transition-all",
                                                      isSelected ? "border-shogun-gold bg-shogun-gold" : "border-shogun-subdued"
                                                    )}>
                                                      {isSelected && <CheckCircle2 className="w-2 h-2 text-black" />}
                                                    </div>
                                                    <div>
                                                      <span className="text-[10px] font-bold text-shogun-text">{tool.name}</span>
                                                      <span className="text-[8px] text-shogun-subdued ml-2 font-mono">{domain}</span>
                                                    </div>
                                                  </div>
                                                  <div className="flex items-center gap-1.5">
                                                    <span className="text-[8px] text-shogun-blue/60 uppercase">{tool.connector_type || 'api'}</span>
                                                    <span className={cn(
                                                      "text-[8px] font-bold uppercase px-1.5 py-0.5 rounded",
                                                      tool.status === 'connected' ? "text-green-400 bg-green-500/10" : "text-shogun-subdued bg-[#0a0e1a]"
                                                    )}>
                                                      {tool.status === 'connected' ? 'Active' : tool.status}
                                                    </span>
                                                  </div>
                                                </button>
                                              );
                                            })
                                          ) : (
                                            <p className="text-[9px] text-shogun-subdued italic py-2">No tools or APIs registered in The Katana Toolbox yet.</p>
                                          )}
                                          <div className="pt-1 border-t border-shogun-border/30 space-y-1">
                                            <div className="flex items-center justify-between">
                                              <span className="text-[8px] text-shogun-subdued uppercase tracking-widest font-bold">Add Custom Website</span>
                                              {!propVal.includes('*.*') && (
                                                <span className="text-[8px] text-shogun-subdued italic">Type <code className="text-red-400 font-mono font-bold">*.*</code> to allow all</span>
                                              )}
                                            </div>
                                            {propVal.includes('*.*') && (
                                              <div className="flex items-center gap-2 p-2 bg-red-500/10 border border-red-500/30 rounded-lg">
                                                <span className="text-[9px] font-bold text-red-400 uppercase tracking-widest">⚠ All websites permitted</span>
                                                <span className="text-[8px] text-red-400/60">— The agent can access any domain without restriction.</span>
                                              </div>
                                            )}
                                            <input
                                              type="text"
                                              placeholder="e.g. github.com or *.* for unrestricted"
                                              className="w-full bg-[#0a0a10] border border-shogun-border rounded px-2 py-1 text-[10px] font-mono text-shogun-text placeholder:text-shogun-subdued/40 focus:border-shogun-gold transition-colors"
                                              onKeyDown={(e) => {
                                                if (e.key === 'Enter' && (e.target as HTMLInputElement).value.trim()) {
                                                  togglePermission([...propVal, (e.target as HTMLInputElement).value.trim()]);
                                                  (e.target as HTMLInputElement).value = '';
                                                }
                                              }}
                                            />
                                          </div>
                                        </div>
                                      ) : (
                                        <input
                                          type="text"
                                          placeholder={`Add ${prop.replace(/_/g, ' ').toLowerCase()}…`}
                                          className="w-full bg-[#0a0a10] border border-shogun-border rounded px-2 py-1 text-[10px] font-mono text-shogun-text placeholder:text-shogun-subdued/40 focus:border-shogun-gold transition-colors"
                                          onKeyDown={(e) => {
                                            if (e.key === 'Enter' && (e.target as HTMLInputElement).value.trim()) {
                                              togglePermission([...propVal, (e.target as HTMLInputElement).value.trim()]);
                                              (e.target as HTMLInputElement).value = '';
                                            }
                                          }}
                                        />
                                      )}
                                    </div>
                                  ) : (
                                    <span className={cn(
                                      "text-[10px] font-bold uppercase px-2 py-0.5 rounded border",
                                      "text-shogun-gold bg-shogun-gold/10 border-shogun-gold/20"
                                    )}>
                                      {String(propVal)}
                                    </span>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <span className="text-[10px] text-shogun-subdued font-bold uppercase">{String(perms)}</span>
                      )}
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-shogun-subdued italic p-4 text-center">Select a policy to view and customize constraints.</p>
                )}

                {/* Reset to preset */}
                {isCustomPolicy && (
                  <button
                    onClick={() => { setCustomPermissions(null); setCustomPolicyName(''); }}
                    className="w-full py-2 bg-[#050508] border border-shogun-border rounded-lg text-[10px] font-bold text-shogun-subdued hover:text-red-400 hover:border-red-400/30 transition-all uppercase tracking-widest"
                  >
                    Reset to Preset
                  </button>
                )}
              </div>
            </div>

            <div className="shogun-card space-y-6">
              <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                <Workflow className="w-5 h-5 text-shogun-blue" /> Skill Inventory
              </h3>
              <div className="space-y-2">
                {[
                  { name: 'Core Sentinel', type: 'System', size: '124KB' },
                  { name: 'Tactical Analyzer', type: 'Intelligence', size: '2.1MB' },
                  { name: 'Samurai Spawner', type: 'Orchestration', size: '450KB' },
                ].map((skill, i) => (
                  <div 
                    key={i} 
                    onClick={() => navigate('/dojo')}
                    className="flex items-center justify-between p-3 border-b border-shogun-border last:border-0 hover:bg-[#0a0e1a] transition-colors rounded cursor-pointer group"
                  >
                    <div className="flex flex-col">
                      <span className="text-sm font-bold text-shogun-text group-hover:text-shogun-gold transition-colors">{skill.name}</span>
                      <span className="text-[10px] text-shogun-subdued uppercase tracking-widest">{skill.type}</span>
                    </div>
                    <ChevronRight className="w-4 h-4 text-shogun-border group-hover:text-shogun-gold transition-colors" />
                  </div>
                ))}
              </div>
              <button 
                onClick={() => navigate('/dojo')}
                className="w-full py-2 bg-[#050508] border border-shogun-border rounded text-[10px] font-bold text-shogun-subdued hover:text-shogun-gold hover:border-shogun-gold transition-all uppercase tracking-widest"
              >
                Browse Dojo for Skills
              </button>
            </div>
          </div>
        )}

        {activeTab === 'operations' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="shogun-card space-y-6">
              <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                <Activity className="w-5 h-5 text-shogun-blue" /> System Diagnostics
              </h3>
              <div className="grid grid-cols-1 gap-4">
                <div className="p-4 bg-[#050508] border border-shogun-border rounded-xl flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      "p-2 rounded-lg",
                      systemHealth?.qdrant === 'healthy' ? "bg-green-500/10 text-green-500" : "bg-red-500/10 text-red-500"
                    )}>
                      <Database className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-sm font-bold">Vector Engine (Qdrant)</p>
                      <p className="text-[10px] text-shogun-subdued uppercase tracking-widest">
                        {systemHealth?.qdrant === 'healthy' ? 'Lattice Synchronized' : 'Offline / Disk Error'}
                      </p>
                    </div>
                  </div>
                  <span className={cn(
                    "text-[8px] font-bold px-2 py-0.5 rounded border uppercase",
                    systemHealth?.qdrant === 'healthy' ? "text-green-500 border-green-500/30" : "text-red-500 border-red-500/30"
                  )}>
                    {systemHealth?.qdrant || 'offline'}
                  </span>
                </div>

                <div className="p-4 bg-[#050508] border border-shogun-border rounded-xl flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-shogun-blue/10 text-shogun-blue">
                      <Server className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-sm font-bold">Relational Core</p>
                      <p className="text-[10px] text-shogun-subdued uppercase tracking-widest">SQLite Performance: Optimal</p>
                    </div>
                  </div>
                  <span className="text-[8px] font-bold text-green-500 border border-green-500/30 px-2 py-0.5 rounded uppercase">Healthy</span>
                </div>
              </div>

              <div className="mt-4 p-4 bg-shogun-blue/5 border border-shogun-blue/20 rounded-xl">
                                                <div className="flex items-center gap-2 mb-2">
                  <RefreshCw className="w-3 h-3 text-shogun-blue animate-spin-slow" />
                  <span className="text-[10px] font-bold uppercase tracking-widest text-shogun-blue">Lattice Sync</span>
                </div>
                <p className="text-[10px] text-shogun-subdued leading-relaxed">
                  Vector indices are automatically synchronized every 15 minutes. The last successful sync occurred {Math.floor(Math.random() * 10) + 1} minutes ago.
                </p>
              </div>
            </div>

            <div className="shogun-card space-y-6">
              <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                <Clock className="w-5 h-5 text-shogun-gold" /> Operational Cadence (Cron)
              </h3>
              <div className="space-y-4">
                {[
                  { jobType: 'memory_consolidation',  label: 'Nightly Consolidation',    desc: 'Merge episodic traces into semantic memory.',          icon: RefreshCw, cronLabel: 'Every night at 02:00' },
                  { jobType: 'performance_audit',      label: 'Weekly Performance Audit', desc: 'Review agent fit metrics and behavioral drift.',        icon: Shield,    cronLabel: 'Every Monday at 03:00' },
                  { jobType: 'skill_health_check',     label: 'Skill Health Check',       desc: 'Verify third-party tool connectivity and versions.',    icon: Settings,  cronLabel: 'Every night at 04:00' },
                  { jobType: 'persona_drift_check',    label: 'Persona Drift Monitor',    desc: 'Detect deviations from core identity blueprints.',      icon: User,      cronLabel: 'Every Sunday at 05:00' },
                ].map((job) => {
                  const schedule = getPresetSchedule(job.jobType);
                  const isEnabled = schedule ? schedule.is_enabled : (shogunData.bushido_settings?.[job.jobType] ?? false);
                  const isRunning = runningJobs[job.jobType];
                  return (
                    <div key={job.jobType} className="p-4 bg-[#050508] border border-shogun-border rounded-xl space-y-3 group hover:border-shogun-gold/30 transition-all">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <job.icon className="w-4 h-4 text-shogun-gold opacity-70" />
                          <span className="text-sm font-bold">{job.label}</span>
                        </div>
                        <button
                          onClick={() => handlePresetToggle(job.jobType)}
                          className={cn(
                            "w-10 h-5 rounded-full relative transition-all duration-300",
                            isEnabled ? "bg-shogun-gold" : "bg-shogun-card border border-shogun-border"
                          )}
                        >
                          <div className={cn(
                            "absolute top-1 w-3 h-3 rounded-full bg-white transition-all duration-300",
                            isEnabled ? "left-6" : "left-1 bg-shogun-subdued"
                          )} />
                        </button>
                      </div>
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <p className="text-[10px] text-shogun-subdued italic">{job.desc}</p>
                          <button
                            disabled={isRunning}
                            className={cn(
                              "text-[9px] font-bold uppercase tracking-tighter transition-colors flex items-center gap-1",
                              isRunning ? "text-shogun-subdued cursor-not-allowed" : "text-shogun-blue hover:text-shogun-gold"
                            )}
                            onClick={async () => {
                              setRunningJobs(p => ({ ...p, [job.jobType]: true }));
                              try {
                                setStatusMessage({ type: 'success', text: `Triggering ${job.label}…` });
                                await axios.post('/api/v1/bushido/run', { job_type: job.jobType });
                                setStatusMessage({ type: 'success', text: `${job.label} dispatched.` });
                              } catch {
                                setStatusMessage({ type: 'error', text: 'Failed to trigger maintenance.' });
                              } finally {
                                setRunningJobs(p => ({ ...p, [job.jobType]: false }));
                                setTimeout(() => setStatusMessage(null), 3000);
                              }
                            }}
                          >
                            {isRunning && <RefreshCw className="w-2.5 h-2.5 animate-spin" />}
                            {isRunning ? 'Running…' : 'Run Now'}
                          </button>
                        </div>
                        {/* Fixed schedule label */}
                        <div className={cn(
                          "flex items-center gap-1.5 transition-all duration-300",
                          isEnabled ? "opacity-100" : "opacity-40"
                        )}>
                          <Clock className="w-2.5 h-2.5 text-shogun-gold/60 shrink-0" />
                          <span className="text-[9px] font-mono text-shogun-gold/70 uppercase tracking-widest">
                            {job.cronLabel}
                          </span>
                          <span className={cn(
                            "ml-auto text-[8px] font-bold uppercase px-1.5 py-0.5 rounded border",
                            isEnabled
                              ? "text-green-400 border-green-500/30 bg-green-500/10"
                              : "text-shogun-subdued border-shogun-border"
                          )}>
                            {isEnabled ? 'Active' : 'Paused'}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* ── Custom Job Creator ────────────────────────── */}
            <div className="md:col-span-2 shogun-card space-y-6">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                  <Settings className="w-5 h-5 text-shogun-blue" /> Create Custom Job
                </h3>
                <span className="text-[10px] bg-shogun-blue/10 text-shogun-blue px-2 py-0.5 rounded border border-shogun-blue/20 font-bold uppercase tracking-widest">Builder</span>
              </div>

              {(() => {
                const [jobName, setJobName] = [customJob.name, (v: string) => setCustomJob({...customJob, name: v})];
                const [jobType, setJobType] = [customJob.type, (v: string) => setCustomJob({...customJob, type: v})];
                const [frequency, setFrequency] = [customJob.frequency, (v: string) => setCustomJob({...customJob, frequency: v})];
                const [priority, setPriority] = [customJob.priority, (v: number) => setCustomJob({...customJob, priority: v})];
                const [memoryTypes, setMemoryTypes] = [customJob.memoryTypes, (v: string[]) => setCustomJob({...customJob, memoryTypes: v})];
                const [allAgents, setAllAgents] = [customJob.allAgents, (v: boolean) => setCustomJob({...customJob, allAgents: v})];
                const [dryRun, setDryRun] = [customJob.dryRun, (v: boolean) => setCustomJob({...customJob, dryRun: v})];
                const [autoApprove, setAutoApprove] = [customJob.autoApprove, (v: boolean) => setCustomJob({...customJob, autoApprove: v})];

                const toggleMemory = (t: string) => {
                  setMemoryTypes(memoryTypes.includes(t) ? memoryTypes.filter(m => m !== t) : [...memoryTypes, t]);
                };

                return (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* Column 1: Identity */}
                    <div className="space-y-5">
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t("profile.job_name", "Job Name")}</label>
                        <input
                          type="text"
                          placeholder="e.g. Weekly Context Prune"
                          value={jobName}
                          onChange={(e) => setJobName(e.target.value)}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-gold transition-colors"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t("profile.job_type", "Job Type")}</label>
                        <div className="space-y-2">
                          {[
                            { value: 'memory_consolidation', label: 'Memory Consolidation', desc: 'Merge & prune memory traces' },
                            { value: 'performance_audit', label: 'Performance Audit', desc: 'Review execution quality metrics' },
                            { value: 'skill_health_check', label: 'Skill Health Check', desc: 'Verify tool connectivity' },
                            { value: 'persona_drift_check', label: 'Persona Drift Check', desc: 'Detect behavioral deviation' },
                            { value: 'custom_task', label: 'Custom Task', desc: 'Any repeating instruction — API calls, syncs, monitoring' },
                          ].map(jt => (
                            <button
                              key={jt.value}
                              onClick={() => setJobType(jt.value)}
                              className={cn(
                                "w-full text-left p-2.5 rounded-lg border transition-all",
                                jobType === jt.value
                                  ? jt.value === 'custom_task' ? "border-shogun-blue bg-shogun-blue/10" : "border-shogun-gold bg-shogun-gold/10"
                                  : "border-shogun-border hover:border-shogun-subdued"
                              )}
                            >
                              <span className={cn("text-xs font-bold", jobType === jt.value ? (jt.value === 'custom_task' ? 'text-shogun-blue' : 'text-shogun-gold') : "text-shogun-text")}>{jt.label}</span>
                              <p className="text-[9px] text-shogun-subdued mt-0.5">{jt.desc}</p>
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="space-y-3">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t("profile.frequency", "Frequency")}</label>
                        <div className="grid grid-cols-5 gap-1.5">
                          {['one-off', 'hourly', 'nightly', 'weekly', 'monthly'].map(f => (
                            <button 
                              key={f}
                              onClick={() => setFrequency(f)}
                              className={cn(
                                "p-2 rounded-lg text-[10px] font-bold uppercase tracking-widest border transition-all",
                                frequency === f 
                                  ? (f === 'one-off' ? "border-shogun-blue bg-shogun-blue/10 text-shogun-blue" : "border-shogun-gold bg-shogun-gold/10 text-shogun-gold")
                                  : "border-shogun-border text-shogun-subdued hover:border-shogun-subdued"
                              )}
                            >
                              {f === 'one-off' ? 'One-off' : f}
                            </button>
                          ))}
                        </div>

                        {/* Contextual schedule controls */}
                        <div className="p-3 bg-[#050508] border border-shogun-border rounded-xl space-y-3 animate-in fade-in">
                          {frequency === 'one-off' && (
                            <div className="space-y-2">
                              <span className="text-[10px] text-shogun-subdued uppercase tracking-widest">Scheduled date & time</span>
                              <input
                                type="datetime-local"
                                value={customJob.scheduleDateTime}
                                onChange={(e) => setCustomJob({...customJob, scheduleDateTime: e.target.value})}
                                className="w-full bg-[#0a0a10] border border-shogun-border rounded-lg px-3 py-2 text-sm font-mono text-shogun-blue focus:border-shogun-blue transition-colors"
                              />
                              <p className="text-[9px] text-shogun-subdued italic">
                                {customJob.scheduleDateTime 
                                  ? `Runs once on ${new Date(customJob.scheduleDateTime).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })} at ${new Date(customJob.scheduleDateTime).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`
                                  : 'Select a future date and time for this one-time task.'}
                              </p>
                            </div>
                          )}

                          {frequency === 'hourly' && (
                            <div className="space-y-2">
                              <div className="flex justify-between items-center">
                                <span className="text-[10px] text-shogun-subdued uppercase tracking-widest">Minute offset</span>
                                <span className="text-xs font-mono font-bold text-shogun-gold">:{String(customJob.minuteOffset).padStart(2, '0')}</span>
                              </div>
                              <input
                                type="range" min="0" max="55" step="5"
                                value={customJob.minuteOffset}
                                onChange={(e) => setCustomJob({...customJob, minuteOffset: parseInt(e.target.value)})}
                                className="w-full accent-shogun-gold"
                              />
                              <p className="text-[9px] text-shogun-subdued italic">Runs every hour at :{String(customJob.minuteOffset).padStart(2, '0')}</p>
                            </div>
                          )}

                          {frequency === 'nightly' && (
                            <div className="space-y-2">
                              <span className="text-[10px] text-shogun-subdued uppercase tracking-widest">Run at</span>
                              <div className="flex items-center gap-3">
                                <input
                                  type="time"
                                  value={customJob.scheduleTime}
                                  onChange={(e) => setCustomJob({...customJob, scheduleTime: e.target.value})}
                                  className="bg-[#0a0a10] border border-shogun-border rounded-lg px-3 py-2 text-sm font-mono text-shogun-gold focus:border-shogun-gold transition-colors"
                                />
                                <span className="text-[10px] text-shogun-subdued">local time, every night</span>
                              </div>
                            </div>
                          )}

                          {frequency === 'weekly' && (
                            <div className="space-y-3">
                              <div className="space-y-2">
                                <span className="text-[10px] text-shogun-subdued uppercase tracking-widest">Active days</span>
                                <div className="flex gap-1.5">
                                  {['mon','tue','wed','thu','fri','sat','sun'].map(day => (
                                    <button
                                      key={day}
                                      onClick={() => {
                                        const days = customJob.scheduleDays.includes(day)
                                          ? customJob.scheduleDays.filter(d => d !== day)
                                          : [...customJob.scheduleDays, day];
                                        setCustomJob({...customJob, scheduleDays: days});
                                      }}
                                      className={cn(
                                        "w-9 h-9 rounded-lg text-[10px] font-bold uppercase border transition-all",
                                        customJob.scheduleDays.includes(day)
                                          ? "border-shogun-gold bg-shogun-gold/15 text-shogun-gold"
                                          : "border-shogun-border text-shogun-subdued hover:border-shogun-subdued"
                                      )}
                                    >
                                      {day.charAt(0).toUpperCase() + day.slice(1, 2)}
                                    </button>
                                  ))}
                                </div>
                              </div>
                              <div className="space-y-1.5">
                                <span className="text-[10px] text-shogun-subdued uppercase tracking-widest">Run at</span>
                                <div className="flex items-center gap-3">
                                  <input
                                    type="time"
                                    value={customJob.scheduleTime}
                                    onChange={(e) => setCustomJob({...customJob, scheduleTime: e.target.value})}
                                    className="bg-[#0a0a10] border border-shogun-border rounded-lg px-3 py-2 text-sm font-mono text-shogun-gold focus:border-shogun-gold transition-colors"
                                  />
                                  <span className="text-[10px] text-shogun-subdued">
                                    on {customJob.scheduleDays.length === 0 ? 'no days' : customJob.scheduleDays.map(d => d.charAt(0).toUpperCase() + d.slice(1)).join(', ')}
                                  </span>
                                </div>
                              </div>
                            </div>
                          )}

                          {frequency === 'monthly' && (
                            <div className="space-y-3">
                              <span className="text-[10px] text-shogun-subdued uppercase tracking-widest">Select day</span>
                              <div className="grid grid-cols-7 gap-1">
                                {Array.from({ length: 28 }, (_, i) => i + 1).map(day => (
                                  <button
                                    key={day}
                                    onClick={() => setCustomJob({...customJob, scheduleDay: day})}
                                    className={cn(
                                      "w-full aspect-square rounded-md text-[10px] font-bold transition-all border",
                                      customJob.scheduleDay === day
                                        ? "border-shogun-gold bg-shogun-gold text-black"
                                        : "border-shogun-border text-shogun-subdued hover:border-shogun-gold/40 hover:text-shogun-text"
                                    )}
                                  >
                                    {day}
                                  </button>
                                ))}
                              </div>
                              <div className="space-y-1.5 pt-1">
                                <span className="text-[10px] text-shogun-subdued uppercase tracking-widest">Run at</span>
                                <div className="flex items-center gap-3">
                                  <input
                                    type="time"
                                    value={customJob.scheduleTime}
                                    onChange={(e) => setCustomJob({...customJob, scheduleTime: e.target.value})}
                                    className="bg-[#0a0a10] border border-shogun-border rounded-lg px-3 py-2 text-sm font-mono text-shogun-gold focus:border-shogun-gold transition-colors"
                                  />
                                  <span className="text-[10px] text-shogun-subdued">
                                    on the {customJob.scheduleDay}{customJob.scheduleDay === 1 ? 'st' : customJob.scheduleDay === 2 ? 'nd' : customJob.scheduleDay === 3 ? 'rd' : 'th'} of each month
                                  </span>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Column 2: Parameters */}
                    <div className="space-y-5">
                      <div className="space-y-3">
                        <div className="flex justify-between items-center">
                          <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t("profile.priority", "Priority")}</label>
                          <span className="text-shogun-gold font-mono font-bold text-xs">
                            {priority <= 25 ? 'Low' : priority <= 50 ? 'Normal' : priority <= 75 ? 'High' : 'Critical'}
                          </span>
                        </div>
                        <input
                          type="range" min="0" max="100" step="5"
                          value={priority}
                          onChange={(e) => setPriority(parseInt(e.target.value))}
                          className="w-full accent-shogun-gold"
                        />
                        <div className="flex justify-between text-[8px] text-shogun-subdued uppercase tracking-widest">
                          <span>Low</span><span>Normal</span><span>High</span><span>Critical</span>
                        </div>
                      </div>

                      {(jobType === 'memory_consolidation' || jobType === 'performance_audit') && (
                        <div className="space-y-2">
                          <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">
                            {jobType === 'memory_consolidation' ? 'Memory Types to Consolidate' : 'Memory Types to Audit'}
                          </label>
                          <div className="grid grid-cols-2 gap-2">
                            {['episodic', 'semantic', 'procedural', 'persona'].map(t => (
                              <button
                                key={t}
                                onClick={() => toggleMemory(t)}
                                className={cn(
                                  "flex items-center gap-2 p-2 rounded-lg text-[10px] font-bold border transition-all",
                                  memoryTypes.includes(t) 
                                    ? "border-shogun-blue bg-shogun-blue/10 text-shogun-blue"
                                    : "border-shogun-border text-shogun-subdued hover:border-shogun-subdued"
                                )}
                              >
                                <div className={cn(
                                  "w-3 h-3 rounded border-2 flex items-center justify-center transition-all",
                                  memoryTypes.includes(t) ? "border-shogun-blue bg-shogun-blue" : "border-shogun-subdued"
                                )}>
                                  {memoryTypes.includes(t) && <CheckCircle2 className="w-2 h-2 text-white" />}
                                </div>
                                <span className="capitalize">{t}</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                      {jobType === 'skill_health_check' && (
                        <div className="p-3 bg-[#050508] border border-shogun-border rounded-xl">
                          <p className="text-[10px] text-shogun-subdued">
                            <span className="font-bold text-shogun-blue uppercase">Scope:</span> Verifies connectivity to all installed skills and third-party integrations. No memory parameters required.
                          </p>
                        </div>
                      )}

                      {jobType === 'persona_drift_check' && (
                        <div className="p-3 bg-[#050508] border border-shogun-border rounded-xl">
                          <p className="text-[10px] text-shogun-subdued">
                            <span className="font-bold text-shogun-gold uppercase">Scope:</span> Compares current behavioral patterns against the active persona blueprint. Flags deviations exceeding threshold.
                          </p>
                        </div>
                      )}

                      {jobType === 'custom_task' && (
                        <div className="space-y-2">
                          <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t("profile.task_instruction", "Task Instruction")}</label>
                          <textarea
                            value={customJob.taskInstruction}
                            onChange={(e) => setCustomJob({...customJob, taskInstruction: e.target.value})}
                            placeholder="e.g. Check the latest tech news via the NewsAPI connector and store a summary in episodic memory. Flag any articles mentioning our product competitors."
                            rows={4}
                            className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm leading-relaxed focus:border-shogun-blue transition-colors resize-none placeholder:text-shogun-subdued/50"
                          />
                          <p className="text-[9px] text-shogun-subdued italic">
                            The Shogun will execute this instruction on the defined schedule. Use natural language — reference installed skills, APIs, or connectors by name.
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Column 3: Options + Submit */}
                    <div className="space-y-5">
                      <div className="space-y-3">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t("profile.options", "Options")}</label>

                        <div 
                          onClick={() => setAllAgents(!allAgents)}
                          className={cn(
                            "flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-all",
                            allAgents ? "border-shogun-gold/30 bg-shogun-gold/5" : "border-shogun-border hover:border-shogun-subdued"
                          )}
                        >
                          <div className="flex items-center gap-2">
                            <Workflow className="w-3.5 h-3.5 text-shogun-subdued" />
                            <div>
                              <span className="text-xs font-semibold">Include Samurai metrics</span>
                              <p className="text-[9px] text-shogun-subdued">Factor sub-agent data into the audit</p>
                            </div>
                          </div>
                          <div className={cn(
                            "w-8 h-4 rounded-full relative transition-all duration-300",
                            allAgents ? "bg-shogun-gold" : "bg-shogun-card border border-shogun-border"
                          )}>
                            <div className={cn(
                              "absolute top-0.5 w-3 h-3 rounded-full transition-all duration-300",
                              allAgents ? "left-4 bg-white" : "left-0.5 bg-shogun-subdued"
                            )} />
                          </div>
                        </div>

                        <div
                          onClick={() => setDryRun(!dryRun)}
                          className={cn(
                            "flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-all",
                            dryRun ? "border-shogun-blue/30 bg-shogun-blue/5" : "border-shogun-border hover:border-shogun-subdued"
                          )}
                        >
                          <div className="flex items-center gap-2">
                            <Activity className="w-3.5 h-3.5 text-shogun-subdued" />
                            <span className="text-xs font-semibold">Dry run (preview only)</span>
                          </div>
                          <div className={cn(
                            "w-8 h-4 rounded-full relative transition-all duration-300",
                            dryRun ? "bg-shogun-blue" : "bg-shogun-card border border-shogun-border"
                          )}>
                            <div className={cn(
                              "absolute top-0.5 w-3 h-3 rounded-full transition-all duration-300",
                              dryRun ? "left-4 bg-white" : "left-0.5 bg-shogun-subdued"
                            )} />
                          </div>
                        </div>

                        <div
                          onClick={() => setAutoApprove(!autoApprove)}
                          className={cn(
                            "flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-all",
                            autoApprove ? "border-green-500/30 bg-green-500/5" : "border-shogun-border hover:border-shogun-subdued"
                          )}
                        >
                          <div className="flex items-center gap-2">
                            <CheckCircle2 className="w-3.5 h-3.5 text-shogun-subdued" />
                            <span className="text-xs font-semibold">Auto-approve results</span>
                          </div>
                          <div className={cn(
                            "w-8 h-4 rounded-full relative transition-all duration-300",
                            autoApprove ? "bg-green-500" : "bg-shogun-card border border-shogun-border"
                          )}>
                            <div className={cn(
                              "absolute top-0.5 w-3 h-3 rounded-full transition-all duration-300",
                              autoApprove ? "left-4 bg-white" : "left-0.5 bg-shogun-subdued"
                            )} />
                          </div>
                        </div>
                      </div>

                      <button
                        onClick={async () => {
                          if (!jobName.trim()) {
                            setStatusMessage({ type: 'error', text: 'Please provide a job name.' });
                            setTimeout(() => setStatusMessage(null), 3000);
                            return;
                          }
                          try {
                            setStatusMessage({ type: 'success', text: `Creating "${jobName}"...` });
                            const payload = {
                              name: jobName,
                              job_type: jobType,
                              frequency: frequency,
                              schedule_time: customJob.scheduleTime,
                              schedule_days: frequency === 'weekly' ? customJob.scheduleDays : null,
                              schedule_day: frequency === 'monthly' ? customJob.scheduleDay : null,
                              minute_offset: frequency === 'hourly' ? customJob.minuteOffset : 0,
                              schedule_datetime: frequency === 'one-off' ? customJob.scheduleDateTime : null,
                              scope: { agent_ids: [], memory_types: memoryTypes },
                              priority,
                              all_agents: allAgents,
                              dry_run: dryRun,
                              auto_approve: autoApprove,
                              task_instruction: jobType === 'custom_task' ? customJob.taskInstruction : null,
                              is_enabled: true,
                            };
                            const res = await axios.post('/api/v1/bushido/schedules', payload);
                            if (res.data.data) {
                              setSchedules(prev => [...prev, res.data.data]);
                            }
                            setStatusMessage({ type: 'success', text: `"${jobName}" created and scheduled.` });
                            setCustomJob({ name: '', type: 'memory_consolidation', frequency: 'nightly', scheduleTime: '02:00', scheduleDays: ['mon', 'wed', 'fri'], scheduleDay: 1, minuteOffset: 0, scheduleDateTime: '', priority: 50, memoryTypes: ['episodic', 'semantic'], taskInstruction: '', allAgents: true, dryRun: false, autoApprove: false });
                          } catch {
                            setStatusMessage({ type: 'error', text: 'Failed to create schedule.' });
                          } finally {
                            setTimeout(() => setStatusMessage(null), 3000);
                          }
                        }}
                        className="w-full py-3 bg-gradient-to-r from-shogun-gold to-yellow-600 hover:from-yellow-600 hover:to-shogun-gold text-black font-bold rounded-lg transition-all shadow-shogun text-sm uppercase tracking-widest flex items-center justify-center gap-2"
                      >
                        <Zap className="w-4 h-4" />
                        Create & Schedule Job
                      </button>
                    </div>
                  </div>
                );
              })()}
            </div>

            {/* ── Active Schedules ──────────────────────────── */}
            {schedules.filter(s => !s.is_preset).length > 0 && (
              <div className="md:col-span-2 shogun-card space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                    <Clock className="w-5 h-5 text-shogun-gold" /> Active Custom Schedules
                  </h3>
                  <button
                    onClick={fetchSchedules}
                    className="text-[10px] font-bold text-shogun-subdued hover:text-shogun-gold transition-colors uppercase tracking-widest flex items-center gap-1"
                  >
                    <RefreshCw className="w-3 h-3" /> Refresh
                  </button>
                </div>
                <div className="space-y-2">
                  {schedules.filter(s => !s.is_preset).map((s: any) => (
                    <div key={s.id} className="flex items-center justify-between p-3 bg-[#050508] border border-shogun-border rounded-xl hover:border-shogun-gold/20 transition-all">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className={cn(
                          "w-2 h-2 rounded-full shrink-0",
                          s.is_enabled ? "bg-green-400" : "bg-shogun-subdued"
                        )} />
                        <div className="min-w-0">
                          <p className="text-sm font-bold truncate">{s.name}</p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-[9px] font-mono text-shogun-subdued uppercase tracking-wider">
                              {s.job_type.replace(/_/g, ' ')}
                            </span>
                            <span className="text-shogun-subdued/30">·</span>
                            <span className="text-[9px] font-mono text-shogun-gold/70 uppercase tracking-wider">
                              {s.frequency}
                              {s.schedule_time ? ` @ ${s.schedule_time}` : ''}
                            </span>
                            {s.dry_run && (
                              <span className="text-[8px] font-bold text-shogun-blue uppercase tracking-widest bg-shogun-blue/10 border border-shogun-blue/20 px-1.5 py-0.5 rounded">Dry Run</span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0 ml-3">
                        <button
                          onClick={async () => {
                            try {
                              const res = await axios.patch(`/api/v1/bushido/schedules/${s.id}/toggle`);
                              if (res.data.data) setSchedules(prev => prev.map(x => x.id === s.id ? res.data.data : x));
                            } catch { /* ignore */ }
                          }}
                          className={cn(
                            "w-8 h-4 rounded-full relative transition-all duration-300 shrink-0",
                            s.is_enabled ? "bg-shogun-gold" : "bg-shogun-card border border-shogun-border"
                          )}
                        >
                          <div className={cn(
                            "absolute top-0.5 w-3 h-3 rounded-full transition-all duration-300",
                            s.is_enabled ? "left-4 bg-white" : "left-0.5 bg-shogun-subdued"
                          )} />
                        </button>
                        <button
                          onClick={async () => {
                            try {
                              await axios.delete(`/api/v1/bushido/schedules/${s.id}`);
                              setSchedules(prev => prev.filter(x => x.id !== s.id));
                            } catch { /* ignore */ }
                          }}
                          className="text-shogun-subdued hover:text-red-400 transition-colors p-1"
                          title="Delete schedule"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
