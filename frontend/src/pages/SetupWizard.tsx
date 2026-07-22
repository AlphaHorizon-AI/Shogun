import { useState, useEffect, useCallback } from 'react';
import {
  Globe, FolderOpen, User, Shield, Cpu, FileText, Zap, ChevronRight,
  ChevronLeft, Check, CheckCircle2, AlertCircle, Database, HardDrive,
  Settings, ScrollText, X, GripVertical, Loader2, Sparkles, Crosshair,
  Monitor, Mouse, Keyboard, Camera, AlertTriangle, Users, UserPlus, Server
} from 'lucide-react';
import axios from 'axios';
import { AVAILABLE_LANGUAGES, useTranslation } from '../i18n';
import type { LanguageMeta } from '../i18n';

// ── Types ──────────────────────────────────────────────────────

interface ProviderConfig {
  id: string;
  provider_type: string;
  name: string;
  api_key: string;
  base_url: string;
  models: string[];            // User-selected models (used in Step 7)
  discoveredModels: string[];  // All models found via API
  status: 'pending' | 'testing' | 'connected' | 'failed';
  auth_type: string;
}

interface TeamMemberConfig {
  id: string;
  display_name: string;
  email: string;
  channel: 'telegram' | 'microsoft_teams';
  telegram_user_id: string;
  teams_aad_object_id: string;
  teams_user_principal_name: string;
}

interface SetupWizardProps {
  onComplete: () => void;
}

// ── Constants ──────────────────────────────────────────────────

const TOTAL_STEPS = 9;

const PROVIDER_CARDS = [
  { type: 'openai',     label: 'OpenAI',      icon: '⚡', color: '#10a37f' },
  { type: 'anthropic',  label: 'Anthropic',    icon: '🧠', color: '#d4a017' },
  { type: 'google',     label: 'Google Gemini',icon: '✨', color: '#4285f4' },
  { type: 'ollama',     label: 'Ollama',       icon: '🦙', color: '#ffffff' },
  { type: 'openrouter', label: 'OpenRouter',   icon: '🌐', color: '#6366f1' },
  { type: 'perplexity', label: 'Perplexity',   icon: '🔍', color: '#20b2aa' },
];

const ROUTING_PROFILES = [
  { id: 'ultra_economy', name: 'Ultra Economy', description: 'Lowest cost; strongly prefers local and cheap models.' },
  { id: 'economy', name: 'Economy', description: 'Low-cost daily work with practical escalation.' },
  { id: 'balanced', name: 'Balanced', description: 'Recommended balance of cost, speed, and quality.' },
  { id: 'high_capability', name: 'High Capability', description: 'Uses stronger models earlier for complex work.' },
  { id: 'premium', name: 'Premium', description: 'Maximum configured quality with visible cost controls.' },
  { id: 'custom', name: 'Custom', description: 'Use only your ordered model selection with capability and safety gates.' },
];

const DEFAULT_DIRECTIVES = `priorities:
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
  - tactical_analysis: shogun_priority`;

const DEFAULT_CONSTITUTION = `# SHOGUN SYSTEM CONSTITUTION
# --- Global Behavioral Principles ---

core_directives:
  - id: zero_harm
    rule: "Operations must not compromise host system integrity."
    severity: CRITICAL

  - id: transparency
    rule: "All autonomous spawns must be logged to the Torii registry."
    severity: HIGH

  - id: human_oversight
    rule: "No irreversible actions without human approval."
    severity: BALANCED

autonomy_limits:
  max_recursion_depth: 3
  prohibited_tools:
    - shell_rm_root
    - network_sniffing
  approval_required: true

data_sovereignty:
  retention_policy: episodic_decay
  privacy_tier: maximal`;

const DEFAULT_MANDATE = `# The Mandate

## Title
**Shogun — Primary Orchestrator**

## Mandate Statement

You are the primary orchestrating AI of the Shogun platform.

Your responsibility is to ensure that all operations, agents, and workflows are coordinated, efficient, and aligned with the operator's objectives.

---

## Core Objective

Maintain operational excellence across the Samurai network. Ensure that sub-agents are effectively deployed, monitored, and guided toward their assigned tasks.

---

## Operating Principles

### Relevance over volume
Focus on meaningful work, not busy work.

### Clarity over complexity
Communicate clearly and concisely.

### Stewardship over passivity
Proactively maintain the system, don't merely observe.

### Trust over hype
Reliability and consistency build trust.`;

// ── Component ──────────────────────────────────────────────────

export const SetupWizard = ({ onComplete }: SetupWizardProps) => {
  const { t, language: activeLanguage, setLanguage: setI18nLanguage } = useTranslation();
  const [step, setStep] = useState(1);
  const [animDir, setAnimDir] = useState<'left' | 'right'>('left');

  // Step 1: Language & Identity
  const [language, setLanguage] = useState(activeLanguage);
  const [operatorName, setOperatorName] = useState('Daimyo');
  const [installationMode, setInstallationMode] = useState<'single' | 'team'>('single');
  const [teamMembers, setTeamMembers] = useState<TeamMemberConfig[]>([]);

  const addTeamMember = () => setTeamMembers(prev => [...prev, {
    id: crypto.randomUUID(),
    display_name: '',
    email: '',
    channel: 'telegram',
    telegram_user_id: '',
    teams_aad_object_id: '',
    teams_user_principal_name: '',
  }]);

  const updateTeamMember = (id: string, updates: Partial<TeamMemberConfig>) => {
    setTeamMembers(prev => prev.map(member => member.id === id ? { ...member, ...updates } : member));
  };

  const teamSetupValid = installationMode === 'single' || (
    operatorName.trim().length > 0 &&
    teamMembers.length > 0 &&
    teamMembers.every(member =>
      member.display_name.trim().length > 0 &&
      (member.channel === 'telegram'
        ? member.telegram_user_id.trim().length > 0
        : member.teams_aad_object_id.trim().length > 0 || member.teams_user_principal_name.trim().length > 0)
    )
  );

  // Sync wizard language choice → global i18n context
  const handleLanguageSelect = (code: string) => {
    setLanguage(code);
    setI18nLanguage(code);
  };

  // Step 2: Path
  const [dataPath, setDataPath] = useState('');

  // Step 3: Identity
  const [agentName, setAgentName] = useState('Shogun Prime');
  const [description, setDescription] = useState('Master orchestrator of the Samurai Network.');
  const [personaId, setPersonaId] = useState('');
  const [personas, setPersonas] = useState<any[]>([]);
  const [autonomy, setAutonomy] = useState(50);
  const [tone, setTone] = useState('analytical');
  const [riskTolerance, setRiskTolerance] = useState('medium');
  const [verbosity, setVerbosity] = useState('medium');
  const [planningDepth, setPlanningDepth] = useState('medium');
  const [toolUsage, setToolUsage] = useState('balanced');
  const [securityBias, setSecurityBias] = useState('balanced');
  const [memoryStyle, setMemoryStyle] = useState('focused');

  // Step 4: Directives
  const [directives, setDirectives] = useState(DEFAULT_DIRECTIVES);

  // Step 5: Providers
  const [providers, setProviders] = useState<ProviderConfig[]>([]);
  const [activeProviderType, setActiveProviderType] = useState('');

  // Step 6: Constitution & Mandate
  const [constitution, setConstitution] = useState(DEFAULT_CONSTITUTION);
  const [mandate, setMandate] = useState(DEFAULT_MANDATE);

  // Step 7: Models
  const [routingProfile, setRoutingProfile] = useState('custom');
  const [primaryModel, setPrimaryModel] = useState('');
  const [fallbackModels, setFallbackModels] = useState<string[]>([]);

  // Step 8: Ronin Desktop Control (optional)
  const [roninEnabled, setRoninEnabled] = useState(false);
  const [roninCheck, setRoninCheck] = useState<any>(null);
  const [roninInstalling, setRoninInstalling] = useState(false);
  const [roninInstallResult, setRoninInstallResult] = useState<string | null>(null);
  const [roninAcknowledged, setRoninAcknowledged] = useState(false);
  const [serverMode, setServerMode] = useState(false);

  // Step 9: Completing
  const [completing, setCompleting] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [completionError, setCompletionError] = useState<string | null>(null);

  // ── Load initial data ────────────────────────────────────────
  useEffect(() => {
    const load = async () => {
      try {
        const [statusRes, personasRes] = await Promise.allSettled([
          axios.get('/api/v1/setup/status'),
          axios.get('/api/v1/personas'),
        ]);
        if (statusRes.status === 'fulfilled') {
          setDataPath(statusRes.value.data.data?.data_path || '');
          setServerMode(statusRes.value.data.data?.deployment_mode === 'server');
          const configuredLanguage = statusRes.value.data.data?.language;
          if (configuredLanguage && AVAILABLE_LANGUAGES.some(item => item.code === configuredLanguage)) {
            setLanguage(configuredLanguage);
            void setI18nLanguage(configuredLanguage);
          }
        }
        if (personasRes.status === 'fulfilled') {
          setPersonas(personasRes.value.data.data || []);
        }
      } catch {}
    };
    load();
  }, [setI18nLanguage]);

  const formatTranslation = (key: string, values: Record<string, string | number>) => {
    return Object.entries(values).reduce(
      (result, [name, value]) => result.replaceAll(`{${name}}`, String(value)),
      t(key),
    );
  };

  const routingProfiles = ROUTING_PROFILES.map(item => ({
    ...item,
    name: t(`setup.routing_${item.id}`),
    description: t(`setup.routing_${item.id}_desc`),
  }));

  // ── Navigation ───────────────────────────────────────────────
  const goNext = useCallback(() => {
    if (step < TOTAL_STEPS) {
      setAnimDir('left');
      setStep(s => s + 1);
    }
  }, [step]);

  const goBack = useCallback(() => {
    if (step > 1) {
      setAnimDir('right');
      setStep(s => s - 1);
    }
  }, [step]);

  // ── Provider management ──────────────────────────────────────
  const addProvider = (type: string) => {
    const existing = providers.find(p => p.provider_type === type);
    if (existing) {
      setActiveProviderType(type);
      return;
    }
    const label = PROVIDER_CARDS.find(p => p.type === type)?.label || type;
    const isLocal = ['ollama', 'lmstudio', 'local'].includes(type);
    setProviders(prev => [...prev, {
      id: crypto.randomUUID(),
      provider_type: type,
      name: label,
      api_key: '',
      base_url: isLocal ? 'http://127.0.0.1:11434' : '',
      models: [],
      discoveredModels: [],
      status: 'pending' as const,
      auth_type: isLocal ? 'none' : 'api_key',
    }]);
    setActiveProviderType(type);
  };

  const updateProvider = (id: string, updates: Partial<ProviderConfig>) => {
    setProviders(prev => prev.map(p => p.id === id ? { ...p, ...updates } : p));
  };

  const removeProvider = (id: string) => {
    setProviders(prev => prev.filter(p => p.id !== id));
    setActiveProviderType('');
  };

  const testProvider = async (prov: ProviderConfig) => {
    updateProvider(prov.id, { status: 'testing' });
    const isLocal = ['ollama', 'lmstudio', 'local'].includes(prov.provider_type);

    // Determine the base URL for the /v1/models call
    const BASE_URLS: Record<string, string> = {
      openai: 'https://api.openai.com',
      anthropic: 'https://api.anthropic.com',
      google: 'https://generativelanguage.googleapis.com',
      openrouter: 'https://openrouter.ai/api',
      perplexity: 'https://api.perplexity.ai',
    };
    const baseUrl = prov.base_url || BASE_URLS[prov.provider_type] || '';

    try {
      // Try to fetch models from the provider's API
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (prov.api_key) {
        headers['Authorization'] = `Bearer ${prov.api_key}`;
      }

      const modelsUrl = isLocal
        ? `${baseUrl}/api/tags`   // Ollama uses /api/tags
        : `${baseUrl}/v1/models`;

      const res = await fetch(modelsUrl, { headers, signal: AbortSignal.timeout(8000) });

      if (res.ok) {
        const json = await res.json();
        let discoveredModels: string[] = [];

        if (isLocal && json.models) {
          // Ollama format: { models: [{ name: "llama3:latest" }, ...] }
          discoveredModels = json.models.map((m: any) => m.name || m.model).filter(Boolean);
        } else if (json.data) {
          // OpenAI-compatible format: { data: [{ id: "gpt-4o" }, ...] }
          discoveredModels = json.data.map((m: any) => m.id).filter(Boolean);
        }

        // Store discovered models separately — user picks from these
        updateProvider(prov.id, { status: 'connected', discoveredModels: discoveredModels });
      } else {
        // API responded but with error — still mark connected if we have credentials
        if (prov.api_key || isLocal) {
          updateProvider(prov.id, { status: 'connected' });
        } else {
          updateProvider(prov.id, { status: 'failed' });
        }
      }
    } catch {
      // Network error — fall back to credential check
      if (prov.api_key || isLocal) {
        updateProvider(prov.id, { status: 'connected' });
      } else {
        updateProvider(prov.id, { status: 'failed' });
      }
    }
  };

  // ── Build model options from configured providers ────────────
  const allModelOptions = providers
    .filter(p => p.status === 'connected')
    .flatMap(prov => {
      const models = prov.models.length > 0 ? prov.models : [prov.name];
      return models.map(m => ({
        value: `${prov.id}::${m}`,
        label: m,
        group: `${prov.provider_type.toUpperCase()} — ${prov.name}`,
      }));
    });

  // ── Sync Active Persona traits ────────────────────────────────
  const handlePersonaChange = (val: string) => {
    setPersonaId(val);
    const p = personas.find(x => x.id === val);
    if (p) {
      if (p.tone) setTone(p.tone);
      if (p.risk_tolerance) setRiskTolerance(p.risk_tolerance);
      if (p.verbosity) setVerbosity(p.verbosity);
      if (p.planning_depth) setPlanningDepth(p.planning_depth);
      if (p.tool_usage_style) setToolUsage(p.tool_usage_style);
      if (p.security_bias) setSecurityBias(p.security_bias);
      if (p.memory_style) setMemoryStyle(p.memory_style);
      if (p.autonomy) {
        if (p.autonomy === 'low' || p.autonomy === 'guarded') setAutonomy(25);
        else if (p.autonomy === 'medium' || p.autonomy === 'tactical') setAutonomy(50);
        else if (p.autonomy === 'high' || p.autonomy === 'campaign') setAutonomy(75);
        else if (p.autonomy === 'critical' || p.autonomy === 'ronin') setAutonomy(100);
        else {
           const num = parseInt(p.autonomy);
           if (!isNaN(num)) setAutonomy(num);
        }
      }
    }
  };

  // ── Complete setup ───────────────────────────────────────────
  const handleComplete = async () => {
    setCompleting(true);
    setCompletionError(null);
    try {
      await axios.post('/api/v1/setup/complete', {
        language,
        operator_name: operatorName,
        installation_mode: installationMode,
        team_members: installationMode === 'team' ? [
          {
            display_name: operatorName,
            is_primary: true,
            channel: 'web',
          },
          ...teamMembers.map(member => ({
            display_name: member.display_name,
            email: member.email || null,
            is_primary: false,
            channel: member.channel,
            telegram_user_id: member.channel === 'telegram' ? member.telegram_user_id : null,
            teams_aad_object_id: member.channel === 'microsoft_teams' ? member.teams_aad_object_id || null : null,
            teams_user_principal_name: member.channel === 'microsoft_teams' ? member.teams_user_principal_name || null : null,
          })),
        ] : [],
        data_path: dataPath,
        agent_name: agentName,
        description,
        persona_id: personaId || null,
        autonomy,
        tone,
        risk_tolerance: riskTolerance,
        verbosity,
        planning_depth: planningDepth,
        tool_usage_style: toolUsage,
        security_bias: securityBias,
        memory_style: memoryStyle,
        behavioral_directives: directives,
        providers: providers.filter(p => p.status === 'connected').map(p => ({
          provider_type: p.provider_type,
          name: p.name,
          auth_type: p.auth_type,
          api_key: p.api_key || null,
          base_url: p.base_url || null,
          models: p.models,
        })),
        constitution,
        mandate,
        primary_model: primaryModel,
        fallback_models: fallbackModels,
        routing_profile: routingProfile,
        ronin_enabled: roninEnabled,
      });

      // Store language & operator in localStorage
      localStorage.setItem('shogun_language', language);
      localStorage.setItem('shogun_operator_name', operatorName);

      setCompleted(true);
      setTimeout(() => {
        onComplete();
      }, 2500);
    } catch (err) {
      console.error('Setup failed:', err);
      let message = t('setup.completion_error_help');
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail;
        if (typeof detail === 'string' && detail.trim()) message = detail;
      }
      setCompletionError(message);
      setCompleting(false);
    }
  };

  // ── Step progress bar ────────────────────────────────────────
  const ProgressBar = () => (
    <div className="flex items-center justify-center gap-1 mb-8">
      {Array.from({ length: TOTAL_STEPS }, (_, i) => {
        const stepNum = i + 1;
        const isCompleted = stepNum < step;
        const isCurrent = stepNum === step;
        return (
          <div key={i} className="flex items-center">
            <div className={`
              w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-500
              ${isCompleted ? 'bg-[#d4a017] text-black' : ''}
              ${isCurrent ? 'bg-[#3b82f6] text-white ring-2 ring-[#3b82f6]/40 ring-offset-2 ring-offset-[#0a0e1a]' : ''}
              ${!isCompleted && !isCurrent ? 'bg-[#1a1f2e] text-[#555] border border-[#2a2f3e]' : ''}
            `}>
              {isCompleted ? <Check className="w-4 h-4" /> : stepNum}
            </div>
            {i < TOTAL_STEPS - 1 && (
              <div className={`w-6 h-0.5 mx-0.5 transition-all duration-500 ${
                stepNum < step ? 'bg-[#d4a017]' : 'bg-[#1a1f2e]'
              }`} />
            )}
          </div>
        );
      })}
    </div>
  );

  // ── Select helper ────────────────────────────────────────────
  const Select = ({ value, onChange, children, className = '' }: any) => (
    <select
      value={value}
      onChange={(e: any) => onChange(e.target.value)}
      className={`w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm text-white focus:border-[#3b82f6] outline-none transition-colors ${className}`}
    >
      {children}
    </select>
  );

  // ── Content per step ─────────────────────────────────────────
  const renderStep = () => {
    switch (step) {

      // ═══════════════════════════════════════════════════════════
      // STEP 1: Language
      // ═══════════════════════════════════════════════════════════
      case 1:
        return (
          <div className="space-y-8">
            <div className="text-center">
              <Globe className="w-12 h-12 text-[#d4a017] mx-auto mb-4" />
              <h2 className="text-3xl font-bold text-white">{t('setup.step1_title')}</h2>
              <p className="text-sm text-[#888] mt-2 max-w-lg mx-auto">{t('setup.step1_subtitle')}</p>
            </div>
            <div className="max-w-3xl mx-auto bg-[#0d1117]/60 border border-[#1a1f2e] rounded-xl p-4 text-sm text-[#999] leading-relaxed">
              <p>{t('setup.step1_explainer')}</p>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-5 lg:grid-cols-7 gap-3 max-w-4xl mx-auto">
              {AVAILABLE_LANGUAGES.map((lang: LanguageMeta) => (
                <button
                  key={lang.code}
                  onClick={() => handleLanguageSelect(lang.code)}
                  className={`
                    p-4 rounded-xl border-2 transition-all duration-300 text-center group hover:scale-[1.03]
                    ${language === lang.code
                      ? 'border-[#d4a017] bg-[#d4a017]/10 shadow-[0_0_20px_rgba(212,160,23,0.15)]'
                      : 'border-[#2a2f3e] bg-[#0d1117] hover:border-[#3b82f6]/50'}
                  `}
                >
                  <span className="text-2xl block mb-2">{lang.flag}</span>
                  <span className="text-sm font-bold text-white block">{lang.name}</span>
                  <span className="text-[10px] text-[#666] block mt-0.5">{lang.englishName}</span>
                  {language === lang.code && (
                    <CheckCircle2 className="w-4 h-4 text-[#d4a017] mx-auto mt-2" />
                  )}
                </button>
              ))}
            </div>

            <div className="max-w-3xl mx-auto pt-4 border-t border-[#1a1f2e] space-y-5">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setInstallationMode('single')}
                  className={`p-4 rounded-xl border-2 text-left transition-all ${installationMode === 'single' ? 'border-[#d4a017] bg-[#d4a017]/10' : 'border-[#2a2f3e] bg-[#0d1117]'}`}
                >
                  <User className="w-5 h-5 text-[#d4a017] mb-2" />
                  <p className="font-bold text-white">{t('setup.mode_single')}</p>
                  <p className="text-xs text-[#777] mt-1">{t('setup.mode_single_desc')}</p>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setInstallationMode('team');
                    if (teamMembers.length === 0) addTeamMember();
                  }}
                  className={`p-4 rounded-xl border-2 text-left transition-all ${installationMode === 'team' ? 'border-[#3b82f6] bg-[#3b82f6]/10' : 'border-[#2a2f3e] bg-[#0d1117]'}`}
                >
                  <Users className="w-5 h-5 text-[#3b82f6] mb-2" />
                  <p className="font-bold text-white">{t('setup.mode_team')}</p>
                  <p className="text-xs text-[#777] mt-1">{t('setup.mode_team_desc')}</p>
                </button>
              </div>

              <div>
                <label className="text-[10px] text-[#888] uppercase tracking-widest font-bold block mb-1.5">
                  {installationMode === 'team' ? t('setup.primary_admin_name') : t('setup.calling_name')}
                </label>
                <input
                  type="text"
                  value={operatorName}
                  onChange={e => setOperatorName(e.target.value)}
                  placeholder="Daimyo"
                  className="w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm font-mono text-white focus:border-[#d4a017] outline-none transition-colors"
                />
                <p className="text-[10px] text-[#666] mt-2">
                  {installationMode === 'team'
                    ? t('setup.primary_admin_desc')
                    : t('setup.calling_name_desc')}
                </p>
              </div>

              {installationMode === 'team' && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-bold text-white">{t('setup.team_members')}</p>
                      <p className="text-[10px] text-[#666]">{t('setup.team_members_desc')}</p>
                    </div>
                    <button type="button" onClick={addTeamMember} className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[#3b82f6]/15 text-[#60a5fa] text-xs font-bold hover:bg-[#3b82f6]/25">
                      <UserPlus className="w-4 h-4" /> {t('setup.add_member')}
                    </button>
                  </div>
                  {teamMembers.map((member, index) => (
                    <div key={member.id} className="bg-[#0d1117] border border-[#2a2f3e] rounded-xl p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <p className="text-xs font-bold text-[#3b82f6] uppercase tracking-widest">{formatTranslation('setup.member_number', { number: index + 1 })}</p>
                        <button type="button" onClick={() => setTeamMembers(prev => prev.filter(item => item.id !== member.id))} className="text-[#666] hover:text-red-400">
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <input value={member.display_name} onChange={e => updateTeamMember(member.id, { display_name: e.target.value })} placeholder={t('setup.full_name')} className="bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm text-white focus:border-[#3b82f6] outline-none" />
                        <input value={member.email} onChange={e => updateTeamMember(member.id, { email: e.target.value })} placeholder={t('setup.email_optional')} className="bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm text-white focus:border-[#3b82f6] outline-none" />
                        <select value={member.channel} onChange={e => updateTeamMember(member.id, { channel: e.target.value as TeamMemberConfig['channel'] })} className="bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm text-white focus:border-[#3b82f6] outline-none">
                          <option value="telegram">Telegram</option>
                          <option value="microsoft_teams">Microsoft Teams</option>
                        </select>
                        {member.channel === 'telegram' ? (
                          <input value={member.telegram_user_id} onChange={e => updateTeamMember(member.id, { telegram_user_id: e.target.value })} placeholder={t('setup.telegram_user_id')} className="bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm font-mono text-white focus:border-[#3b82f6] outline-none" />
                        ) : (
                          <input value={member.teams_user_principal_name} onChange={e => updateTeamMember(member.id, { teams_user_principal_name: e.target.value })} placeholder={t('setup.teams_upn')} className="bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm font-mono text-white focus:border-[#3b82f6] outline-none" />
                        )}
                      </div>
                      {member.channel === 'microsoft_teams' && (
                        <input value={member.teams_aad_object_id} onChange={e => updateTeamMember(member.id, { teams_aad_object_id: e.target.value })} placeholder={t('setup.teams_object_id')} className="w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm font-mono text-white focus:border-[#3b82f6] outline-none" />
                      )}
                    </div>
                  ))}
                  {!teamSetupValid && <p className="text-xs text-amber-400">{t('setup.team_validation')}</p>}
                </div>
              )}
            </div>
          </div>
        );

      // ═══════════════════════════════════════════════════════════
      // STEP 2: Installation Path
      // ═══════════════════════════════════════════════════════════
      case 2:
        return (
          <div className="space-y-8">
            <div className="text-center">
              <FolderOpen className="w-12 h-12 text-[#3b82f6] mx-auto mb-4" />
              <h2 className="text-3xl font-bold text-white">{t('setup.step2_title')}</h2>
              <p className="text-sm text-[#888] mt-2 max-w-lg mx-auto">{t('setup.step2_subtitle')}</p>
            </div>
            <div className="max-w-xl mx-auto bg-[#0d1117]/60 border border-[#1a1f2e] rounded-xl p-4 text-sm text-[#999] leading-relaxed">
              <p>{t('setup.step2_explainer')}</p>
            </div>
            <div className="max-w-xl mx-auto">
              <div className="bg-[#0d1117] border border-[#d4a017]/30 rounded-xl p-6 space-y-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] text-[#888] uppercase tracking-widest font-bold">{t('setup.step2_data_dir')}</label>
                  <input
                    type="text"
                    value={dataPath}
                    onChange={e => setDataPath(e.target.value)}
                    placeholder="C:\Users\you\Shogun\data"
                    className="w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm font-mono text-[#d4a017] focus:border-[#d4a017] outline-none transition-colors"
                  />
                  <p className="text-[10px] text-[#555]">{t('setup.step2_path_help')}</p>
                </div>
                <div className="h-px bg-[#2a2f3e]" />
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { icon: Database, label: t('setup.step2_database'), sub: 'shogun.db' },
                    { icon: HardDrive, label: t('setup.step2_vector'), sub: 'qdrant/' },
                    { icon: Settings, label: t('setup.step2_configs'), sub: 'configs/' },
                    { icon: ScrollText, label: t('setup.step2_logs'), sub: 'logs/' },
                  ].map(({ icon: Icon, label, sub }) => (
                    <div key={label} className="flex items-center gap-2.5 p-2.5 rounded-lg bg-[#0a0e1a] border border-[#1a1f2e]">
                      <Icon className="w-4 h-4 text-[#3b82f6]" />
                      <div>
                        <p className="text-xs font-medium text-white">{label}</p>
                        <p className="text-[10px] text-[#555] font-mono">{sub}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        );

      // ═══════════════════════════════════════════════════════════
      // STEP 3: Identity & Persona
      // ═══════════════════════════════════════════════════════════
      case 3:
        return (
          <div className="space-y-6">
            <div className="text-center">
              <User className="w-12 h-12 text-[#d4a017] mx-auto mb-4" />
              <h2 className="text-3xl font-bold text-white">{t('setup.step3_title')}</h2>
              <p className="text-sm text-[#888] mt-2 max-w-lg mx-auto">{t('setup.step3_subtitle')}</p>
            </div>
            <div className="max-w-4xl mx-auto bg-[#0d1117]/60 border border-[#1a1f2e] rounded-xl p-4 text-sm text-[#999] leading-relaxed">
              <p>{t('setup.step3_explainer')}</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
              {/* Left: Identity */}
              <div className="bg-[#0d1117] border border-[#2a2f3e] rounded-xl p-5 space-y-4">
                <h3 className="text-sm font-bold text-[#d4a017] uppercase tracking-widest flex items-center gap-2">
                  <User className="w-4 h-4" /> {t('setup.step8_identity')}
                </h3>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">{t('setup.step3_agent_name')}</label>
                  <input
                    type="text"
                    value={agentName}
                    onChange={e => setAgentName(e.target.value)}
                    placeholder={t('setup.step3_agent_name_placeholder')}
                    className="w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm text-white focus:border-[#d4a017] outline-none transition-colors"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">{t('setup.step3_description')}</label>
                  <textarea
                    value={description}
                    onChange={e => setDescription(e.target.value)}
                    placeholder={t('setup.step3_description_placeholder')}
                    className="w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm text-white focus:border-[#d4a017] outline-none transition-colors min-h-[80px] resize-y"
                  />
                </div>
                {personas.length > 0 && (
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">{t('setup.step3_persona')}</label>
                    <Select value={personaId} onChange={handlePersonaChange}>
                      <option value="">{t('setup.step3_select_persona')}</option>
                      {personas.map((p: any) => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                    </Select>
                  </div>
                )}
              </div>

              {/* Right: Autonomy & Logic */}
              <div className="bg-[#0d1117] border border-[#2a2f3e] rounded-xl p-5 space-y-4">
                <h3 className="text-sm font-bold text-[#3b82f6] uppercase tracking-widest flex items-center gap-2">
                  <Zap className="w-4 h-4" /> {t('setup.autonomy_logic')}
                </h3>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">{t('setup.step3_autonomy')}</label>
                    <span className="text-[#3b82f6] font-mono font-bold text-sm">{autonomy}%</span>
                  </div>
                  <input type="range" min="0" max="100" step="10" value={autonomy}
                    onChange={e => setAutonomy(parseInt(e.target.value))}
                    className="w-full accent-[#3b82f6]" />
                </div>
                <div className="grid grid-cols-2 gap-2.5">
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">{t('setup.step3_tone')}</label>
                    <Select value={tone} onChange={setTone}>
                      <option value="analytical">{t('setup.step3_tone_analytical')}</option>
                      <option value="direct">{t('setup.step3_tone_direct')}</option>
                      <option value="supportive">{t('setup.step3_tone_supportive')}</option>
                      <option value="strategic">{t('setup.step3_tone_strategic')}</option>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">{t('setup.step3_risk')}</label>
                    <Select value={riskTolerance} onChange={setRiskTolerance}>
                      <option value="low">{t('setup.step3_risk_low')}</option>
                      <option value="medium">{t('setup.step3_risk_medium')}</option>
                      <option value="high">{t('setup.step3_risk_high')}</option>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">{t('setup.step3_verbosity')}</label>
                    <Select value={verbosity} onChange={setVerbosity}>
                      <option value="low">{t('setup.step3_verbosity_low')}</option>
                      <option value="medium">{t('setup.step3_verbosity_medium')}</option>
                      <option value="high">{t('setup.step3_verbosity_high')}</option>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">{t('setup.step3_planning')}</label>
                    <Select value={planningDepth} onChange={setPlanningDepth}>
                      <option value="low">{t('setup.step3_planning_low')}</option>
                      <option value="medium">{t('setup.step3_planning_medium')}</option>
                      <option value="high">{t('setup.step3_planning_high')}</option>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">{t('setup.step3_tool_usage')}</label>
                    <Select value={toolUsage} onChange={setToolUsage}>
                      <option value="conservative">{t('setup.step3_tool_conservative')}</option>
                      <option value="balanced">{t('setup.step3_tool_balanced')}</option>
                      <option value="aggressive">{t('setup.step3_tool_aggressive')}</option>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">{t('setup.step3_security_bias')}</label>
                    <Select value={securityBias} onChange={setSecurityBias}>
                      <option value="strict">{t('setup.step3_security_strict')}</option>
                      <option value="balanced">{t('setup.step3_security_balanced')}</option>
                      <option value="open">{t('setup.step3_security_open')}</option>
                    </Select>
                  </div>
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">{t('setup.step3_memory')}</label>
                  <Select value={memoryStyle} onChange={setMemoryStyle}>
                    <option value="conservative">{t('setup.step3_memory_conservative')}</option>
                    <option value="focused">{t('setup.step3_memory_focused')}</option>
                    <option value="expansive">{t('setup.step3_memory_expansive')}</option>
                  </Select>
                </div>
              </div>
            </div>
          </div>
        );

      // ═══════════════════════════════════════════════════════════
      // STEP 4: Behavioral Directives
      // ═══════════════════════════════════════════════════════════
      case 4:
        return (
          <div className="space-y-6">
            <div className="text-center">
              <Shield className="w-12 h-12 text-[#d4a017] mx-auto mb-4" />
              <h2 className="text-3xl font-bold text-white">{t('setup.step4_title')}</h2>
              <p className="text-sm text-[#888] mt-2 max-w-lg mx-auto">{t('setup.step4_subtitle')}</p>
            </div>
            <div className="max-w-3xl mx-auto bg-[#0d1117]/60 border border-[#1a1f2e] rounded-xl p-4 text-sm text-[#999] leading-relaxed">
              <p>{t('setup.step4_explainer')}</p>
            </div>
            <div className="max-w-3xl mx-auto">
              <div className="bg-[#0d1117] border border-[#2a2f3e] rounded-xl overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2 border-b border-[#2a2f3e] bg-[#0a0e1a]">
                  <span className="text-[10px] font-bold text-[#888] uppercase tracking-widest">{t('setup.yaml_configuration')}</span>
                  <button
                    onClick={() => setDirectives(DEFAULT_DIRECTIVES)}
                    className="text-[10px] font-bold text-[#3b82f6] hover:text-[#d4a017] uppercase tracking-widest transition-colors"
                  >
                    {t('setup.step4_reset')}
                  </button>
                </div>
                <textarea
                  spellCheck={false}
                  value={directives}
                  onChange={e => setDirectives(e.target.value)}
                  className="w-full bg-[#050508] p-5 font-mono text-xs leading-relaxed text-white focus:outline-none min-h-[400px] resize-y"
                />
              </div>
            </div>
          </div>
        );

      // ═══════════════════════════════════════════════════════════
      // STEP 5: Model Provider
      // ═══════════════════════════════════════════════════════════
      case 5: {
        const activeProv = providers.find(p => p.provider_type === activeProviderType);
        const connectedCount = providers.filter(p => p.status === 'connected').length;
        return (
          <div className="space-y-6">
            <div className="text-center">
              <Cpu className="w-12 h-12 text-[#3b82f6] mx-auto mb-4" />
              <h2 className="text-3xl font-bold text-white">{t('setup.step5_title')}</h2>
              <p className="text-sm text-[#888] mt-2 max-w-lg mx-auto">
                {t('setup.step5_subtitle')}
                {connectedCount > 0 && <span className="text-[#d4a017] font-bold"> ({connectedCount} {t('setup.step5_added')})</span>}
              </p>
            </div>
            <div className="max-w-2xl mx-auto bg-[#0d1117]/60 border border-[#1a1f2e] rounded-xl p-4 text-sm text-[#999] leading-relaxed">
              <p>{t('setup.step5_explainer')}</p>
            </div>

            {/* Provider type cards */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 max-w-2xl mx-auto">
              {PROVIDER_CARDS.map(card => {
                const exists = providers.find(p => p.provider_type === card.type);
                const isActive = activeProviderType === card.type;
                return (
                  <button
                    key={card.type}
                    onClick={() => addProvider(card.type)}
                    className={`
                      p-4 rounded-xl border-2 transition-all duration-300 text-center relative group hover:scale-[1.03]
                      ${isActive ? 'border-[#3b82f6] bg-[#3b82f6]/10' : exists?.status === 'connected' ? 'border-[#d4a017]/50 bg-[#d4a017]/5' : 'border-[#2a2f3e] bg-[#0d1117] hover:border-[#3b82f6]/50'}
                    `}
                  >
                    <span className="text-2xl block mb-1">{card.icon}</span>
                    <span className="text-sm font-bold text-white block">{card.label}</span>
                    {exists?.status === 'connected' && (
                      <CheckCircle2 className="w-4 h-4 text-[#d4a017] absolute top-2 right-2" />
                    )}
                  </button>
                );
              })}
            </div>

            {/* Active provider form */}
            {activeProv && (
              <div className="max-w-xl mx-auto bg-[#0d1117] border border-[#2a2f3e] rounded-xl p-5 space-y-4 animate-in slide-in-from-bottom-3 duration-300">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-white">{activeProv.name}</h3>
                  <button onClick={() => removeProvider(activeProv.id)} className="text-[#666] hover:text-red-400 transition-colors">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">{t('setup.step5_provider_name')}</label>
                  <input
                    value={activeProv.name}
                    onChange={e => updateProvider(activeProv.id, { name: e.target.value })}
                    className="w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm text-white focus:border-[#3b82f6] outline-none transition-colors"
                  />
                </div>

                {['ollama', 'lmstudio', 'local'].includes(activeProv.provider_type) ? (
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">{t('setup.step5_base_url')}</label>
                    <input
                      value={activeProv.base_url}
                      onChange={e => updateProvider(activeProv.id, { base_url: e.target.value })}
                      placeholder="http://127.0.0.1:11434"
                      className="w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm font-mono text-white focus:border-[#3b82f6] outline-none transition-colors"
                    />
                  </div>
                ) : (
                  <>
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">{t('setup.auth_type')}</label>
                      <Select
                        value={activeProv.auth_type}
                        onChange={(val: string) => updateProvider(activeProv.id, { auth_type: val })}
                      >
                        <option value="api_key">{t('setup.step5_api_key')}</option>
                        <option value="oauth">OAuth</option>
                      </Select>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">
                        {activeProv.auth_type === 'oauth' ? t('setup.oauth_token') : t('setup.step5_api_key')}
                      </label>
                      <input
                        type="password"
                        value={activeProv.api_key}
                        onChange={e => updateProvider(activeProv.id, { api_key: e.target.value })}
                        placeholder={activeProv.auth_type === 'oauth' ? 'Bearer ...' : 'sk-...'}
                        className="w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm font-mono text-white focus:border-[#3b82f6] outline-none transition-colors"
                      />
                    </div>
                  </>
                )}

                {/* ── Discovered Models (browse & pick) ── */}
                {activeProv.discoveredModels.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">{t('setup.available_models')}</label>
                      <span className="text-[10px] text-[#555]">{formatTranslation('setup.models_found', { count: activeProv.discoveredModels.length })}</span>
                    </div>
                    <div className="bg-[#050508] border border-[#2a2f3e] rounded-lg max-h-40 overflow-y-auto">
                      {activeProv.discoveredModels.map(m => {
                        const isSelected = activeProv.models.includes(m);
                        return (
                          <div
                            key={m}
                            onDoubleClick={() => {
                              if (!isSelected) {
                                updateProvider(activeProv.id, { models: [...activeProv.models, m] });
                              }
                            }}
                            className={`
                              flex items-center justify-between px-3 py-1.5 text-[11px] font-mono cursor-pointer select-none
                              border-b border-[#1a1f2e] last:border-b-0 transition-colors
                              ${isSelected
                                ? 'text-[#d4a017] bg-[#d4a017]/5'
                                : 'text-[#999] hover:bg-[#1a1f2e] hover:text-white'}
                            `}
                          >
                            <span className="truncate">{m}</span>
                            {isSelected && <CheckCircle2 className="w-3 h-3 text-[#d4a017] shrink-0" />}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* ── Selected Models (used in Step 7) ── */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] font-bold text-[#d4a017] uppercase tracking-widest">{t('setup.selected_models')}</label>
                    {activeProv.models.length > 0 && (
                      <span className="text-[10px] text-[#d4a017] font-bold">{formatTranslation('setup.models_selected', { count: activeProv.models.length })}</span>
                    )}
                  </div>
                  {activeProv.models.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5 p-2.5 bg-[#0a0e1a] border border-[#d4a017]/20 rounded-lg">
                      {activeProv.models.map(m => (
                        <span key={m} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-[#d4a017]/10 border border-[#d4a017]/30 text-[10px] font-mono text-[#d4a017]">
                          {m}
                          <button
                            onClick={() => updateProvider(activeProv.id, { models: activeProv.models.filter(x => x !== m) })}
                            className="text-[#d4a017]/40 hover:text-red-400 transition-colors"
                          >
                            <X className="w-2.5 h-2.5" />
                          </button>
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[10px] text-[#555] italic py-2 text-center">{t('setup.no_models_selected')} {activeProv.discoveredModels.length > 0 ? t('setup.double_click_add') : t('setup.test_or_add_model')}</p>
                  )}
                  <div className="flex gap-2">
                    <input
                      data-manual-model-input
                      placeholder={t('setup.type_model_name')}
                      className="flex-1 bg-[#050508] border border-[#2a2f3e] rounded-lg p-2 text-xs font-mono text-white focus:border-[#3b82f6] outline-none transition-colors"
                      onKeyDown={e => {
                        if (e.key === 'Enter') {
                          const val = (e.target as HTMLInputElement).value.trim();
                          if (val && !activeProv.models.includes(val)) {
                            updateProvider(activeProv.id, { models: [...activeProv.models, val] });
                            (e.target as HTMLInputElement).value = '';
                          }
                        }
                      }}
                    />
                    <button
                      onClick={() => {
                        const input = document.querySelector<HTMLInputElement>('[data-manual-model-input]');
                        if (input && input.value.trim()) {
                          const val = input.value.trim();
                          if (!activeProv.models.includes(val)) {
                            updateProvider(activeProv.id, { models: [...activeProv.models, val] });
                            input.value = '';
                          }
                        }
                      }}
                      className="px-3 py-2 rounded-lg bg-[#1a1f2e] border border-[#2a2f3e] text-[10px] font-bold text-[#888] hover:text-white hover:border-[#3b82f6] transition-all"
                    >
                      {t('setup.add')}
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={() => testProvider(activeProv)}
                    disabled={activeProv.status === 'testing'}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#3b82f6] hover:bg-[#3b82f6]/80 text-white text-sm font-bold transition-all disabled:opacity-50"
                  >
                    {activeProv.status === 'testing' ? (
                      <><Loader2 className="w-4 h-4 animate-spin" /> {t('setup.step5_testing')}</>
                    ) : (
                      <><Zap className="w-4 h-4" /> {t('setup.step5_test')}</>
                    )}
                  </button>
                  {activeProv.status === 'connected' && (
                    <span className="text-sm text-green-400 flex items-center gap-1"><CheckCircle2 className="w-4 h-4" /> {t('setup.step5_connected')}</span>
                  )}
                  {activeProv.status === 'failed' && (
                    <span className="text-sm text-red-400 flex items-center gap-1"><AlertCircle className="w-4 h-4" /> {t('setup.step5_failed')}</span>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      }

      // ═══════════════════════════════════════════════════════════
      // STEP 6: Constitution & Mandate
      // ═══════════════════════════════════════════════════════════
      case 6:
        return (
          <div className="space-y-6">
            <div className="text-center">
              <FileText className="w-12 h-12 text-[#d4a017] mx-auto mb-4" />
              <h2 className="text-3xl font-bold text-white">{t('setup.step6_title')}</h2>
              <p className="text-sm text-[#888] mt-2 max-w-lg mx-auto">{t('setup.step6_subtitle')}</p>
            </div>
            <div className="max-w-5xl mx-auto bg-[#0d1117]/60 border border-[#1a1f2e] rounded-xl p-4 text-sm text-[#999] leading-relaxed">
              <p>{t('setup.step6_explainer')}</p>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 max-w-5xl mx-auto">
              {/* Constitution */}
              <div className="bg-[#0d1117] border border-[#2a2f3e] rounded-xl overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2 border-b border-[#2a2f3e] bg-[#0a0e1a]">
                  <span className="text-[10px] font-bold text-[#d4a017] uppercase tracking-widest">⚖️ {t('setup.step6_constitution')} (YAML)</span>
                  <button onClick={() => setConstitution(DEFAULT_CONSTITUTION)}
                    className="text-[10px] font-bold text-[#3b82f6] hover:text-[#d4a017] uppercase tracking-widest transition-colors">
                    {t('setup.step6_use_defaults')}
                  </button>
                </div>
                <textarea
                  spellCheck={false}
                  value={constitution}
                  onChange={e => setConstitution(e.target.value)}
                  className="w-full bg-[#050508] p-4 font-mono text-[11px] leading-relaxed text-white focus:outline-none min-h-[350px] resize-y"
                />
              </div>
              {/* Mandate */}
              <div className="bg-[#0d1117] border border-[#2a2f3e] rounded-xl overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2 border-b border-[#2a2f3e] bg-[#0a0e1a]">
                  <span className="text-[10px] font-bold text-[#3b82f6] uppercase tracking-widest">📜 {t('setup.step6_mandate')} (Markdown)</span>
                  <button onClick={() => setMandate(DEFAULT_MANDATE)}
                    className="text-[10px] font-bold text-[#3b82f6] hover:text-[#d4a017] uppercase tracking-widest transition-colors">
                    {t('setup.step6_use_defaults')}
                  </button>
                </div>
                <textarea
                  spellCheck={false}
                  value={mandate}
                  onChange={e => setMandate(e.target.value)}
                  className="w-full bg-[#050508] p-4 font-mono text-[11px] leading-relaxed text-white focus:outline-none min-h-[350px] resize-y"
                />
              </div>
            </div>
          </div>
        );

      // ═══════════════════════════════════════════════════════════
      // STEP 7: Models
      // ═══════════════════════════════════════════════════════════
      case 7:
        return (
          <div className="space-y-6">
            <div className="text-center">
              <Cpu className="w-12 h-12 text-[#d4a017] mx-auto mb-4" />
              <h2 className="text-3xl font-bold text-white">{t('setup.step7_title')}</h2>
              <p className="text-sm text-[#888] mt-2 max-w-lg mx-auto">{t('setup.step7_subtitle')}</p>
            </div>
            <div className="max-w-4xl mx-auto bg-[#0d1117]/60 border border-[#1a1f2e] rounded-xl p-4 text-sm text-[#999] leading-relaxed">
              <p>{t('setup.step7_explainer')}</p>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 max-w-5xl mx-auto">
              {routingProfiles.map(item => (
                <button key={item.id} onClick={() => setRoutingProfile(item.id)}
                  className={`text-left rounded-xl border p-3 transition-all ${routingProfile === item.id ? 'border-purple-400 bg-purple-400/10' : 'border-[#2a2f3e] bg-[#0d1117] hover:border-purple-400/40'}`}>
                  <div className="flex items-center gap-2 text-xs font-bold text-white">
                    {routingProfile === item.id && <CheckCircle2 className="w-3.5 h-3.5 text-purple-400" />}{item.name}
                  </div>
                  <p className="text-[9px] text-[#777] mt-1 leading-relaxed">{item.description}</p>
                </button>
              ))}
            </div>
            {routingProfile === 'custom' ? <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
              {/* Primary */}
              <div className="bg-[#0d1117] border border-[#2a2f3e] rounded-xl p-5 space-y-4">
                <h3 className="text-sm font-bold text-[#3b82f6] uppercase tracking-widest flex items-center gap-2">
                  <Cpu className="w-4 h-4" /> {t('setup.step7_primary')}
                </h3>
                <p className="text-[10px] text-[#666]">{t('setup.step7_primary_desc')}</p>
                {allModelOptions.length === 0 ? (
                  <p className="text-xs text-[#888] italic text-center py-4">{t('setup.step7_no_providers')}</p>
                ) : (
                  <select
                    value={primaryModel}
                    onChange={e => setPrimaryModel(e.target.value)}
                    className="w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-3 text-sm font-mono text-white focus:border-[#d4a017] outline-none transition-colors"
                  >
                    <option value="">— {t('setup.step7_select_model')} —</option>
                    {allModelOptions.map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label} ({opt.group})</option>
                    ))}
                  </select>
                )}
                {primaryModel && (
                  <div className="flex items-center gap-2 p-2.5 rounded-lg bg-[#d4a017]/5 border border-[#d4a017]/20">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#d4a017] shrink-0" />
                    <span className="text-xs font-mono text-[#d4a017] font-bold truncate">{primaryModel.split('::')[1]}</span>
                    <span className="text-[9px] text-[#888] ml-auto shrink-0">{t('setup.step7_primary').toUpperCase()}</span>
                  </div>
                )}
              </div>
              {/* Fallback */}
              <div className="bg-[#0d1117] border border-[#2a2f3e] rounded-xl p-5 space-y-4">
                <h3 className="text-sm font-bold text-[#d4a017] uppercase tracking-widest flex items-center gap-2">
                  <Sparkles className="w-4 h-4" /> {t('setup.step7_fallback')}
                </h3>
                <p className="text-[10px] text-[#666]">{t('setup.step7_fallback_desc')}</p>
                {allModelOptions.length === 0 ? (
                  <p className="text-xs text-[#888] italic text-center py-4">{t('setup.step7_no_providers')}</p>
                ) : (
                  <>
                    <select
                      value=""
                      onChange={e => {
                        const val = e.target.value;
                        if (val && val !== primaryModel && !fallbackModels.includes(val)) {
                          setFallbackModels(prev => [...prev, val]);
                        }
                      }}
                      className="w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-3 text-sm font-mono text-white focus:border-[#3b82f6] outline-none transition-colors"
                    >
                      <option value="">— {t('setup.step7_add_fallback')} —</option>
                      {allModelOptions
                        .filter(opt => opt.value !== primaryModel && !fallbackModels.includes(opt.value))
                        .map(opt => (
                          <option key={opt.value} value={opt.value}>{opt.label} ({opt.group})</option>
                        ))}
                    </select>
                    {fallbackModels.length > 0 ? (
                      <div className="space-y-1.5">
                        {fallbackModels.map((fm, i) => (
                          <div key={fm}
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
                            className="flex items-center gap-2 p-2.5 rounded-lg border border-[#3b82f6]/20 bg-[#3b82f6]/5 cursor-grab active:cursor-grabbing transition-colors select-none"
                          >
                            <GripVertical className="w-3.5 h-3.5 text-[#555] shrink-0" />
                            <span className="text-[9px] font-bold text-[#3b82f6] w-5 shrink-0">#{i + 1}</span>
                            <span className="text-xs font-mono text-white flex-1 truncate">{fm.split('::')[1]}</span>
                            <button onClick={() => setFallbackModels(prev => prev.filter(f => f !== fm))} className="text-[#555] hover:text-red-400 transition-colors shrink-0 p-0.5">
                              <X className="w-3 h-3" />
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-[11px] text-[#888] italic text-center py-2">{t('setup.step7_no_fallbacks')}</p>
                    )}
                  </>
                )}
              </div>
            </div> : (
              <div className="max-w-4xl mx-auto rounded-xl border border-purple-400/20 bg-purple-400/5 p-5 text-center">
                <p className="text-sm font-bold text-purple-200">{formatTranslation('setup.routing_automatic', { profile: routingProfiles.find(item => item.id === routingProfile)?.name || routingProfile })}</p>
                <p className="text-[10px] text-[#888] mt-1">{t('setup.routing_later')}</p>
              </div>
            )}
          </div>
        );

      // ═══════════════════════════════════════════════════════════
      // STEP 8: Rise, Shogun!
      // ═══════════════════════════════════════════════════════════
      // ═══════════════════════════════════════════════════════════
      // STEP 8: Ronin Desktop Control (Optional)
      // ═══════════════════════════════════════════════════════════
      case 8: {
        if (serverMode) {
          return (
            <div className="space-y-6">
              <div className="text-center">
                <Server className="w-12 h-12 text-[#3b82f6] mx-auto mb-4" />
                <h2 className="text-3xl font-bold text-white">{t('setup.server_mode_title')}</h2>
                <p className="text-sm text-[#888] mt-2 max-w-lg mx-auto">{t('setup.server_mode_subtitle')}</p>
              </div>
              <div className="max-w-3xl mx-auto bg-[#0d1117] border border-[#3b82f6]/30 rounded-xl p-6">
                <div className="flex items-start gap-4">
                  <Shield className="w-6 h-6 text-[#3b82f6] shrink-0" />
                  <div className="space-y-2">
                    <h3 className="text-sm font-bold text-white">{t('setup.server_mode_ronin_unavailable')}</h3>
                    <p className="text-xs text-[#999] leading-relaxed">{t('setup.server_mode_ronin_explainer')}</p>
                  </div>
                </div>
              </div>
            </div>
          );
        }

        const handleRoninCheck = async () => {
          try {
            const res = await axios.get('/api/v1/setup/ronin-check');
            setRoninCheck(res.data.data);
          } catch { setRoninCheck(null); }
        };

        const handleRoninInstall = async () => {
          setRoninInstalling(true);
          setRoninInstallResult(null);
          try {
            const res = await axios.post('/api/v1/setup/ronin-install');
            if (res.data.data?.status === 'success') {
              setRoninInstallResult('success');
              handleRoninCheck(); // refresh status
            } else {
              setRoninInstallResult(res.data.data?.message || t('setup.installation_failed'));
            }
          } catch {
            setRoninInstallResult(t('setup.installation_network_error'));
          } finally {
            setRoninInstalling(false);
          }
        };

        // Auto-check on first render of this step
        if (!roninCheck) { handleRoninCheck(); }

        return (
          <div className="space-y-6">
            <div className="text-center">
              <Crosshair className="w-12 h-12 text-[#f97316] mx-auto mb-4" />
              <h2 className="text-3xl font-bold text-white">{t('setup.ronin_title')}</h2>
              <p className="text-sm text-[#888] mt-2 max-w-lg mx-auto">
                {t('setup.ronin_subtitle')}
              </p>
            </div>

            <div className="max-w-3xl mx-auto bg-[#0d1117]/60 border border-[#1a1f2e] rounded-xl p-4 text-sm text-[#999] leading-relaxed">
              <p>{t('setup.ronin_explainer')}</p>
            </div>

            {/* Enable toggle */}
            <div className="max-w-3xl mx-auto">
              <div className="bg-[#0d1117] border border-[#2a2f3e] rounded-xl p-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Monitor className="w-5 h-5 text-[#f97316]" />
                    <div>
                      <h3 className="text-sm font-bold text-white">{t('setup.ronin_enable')}</h3>
                      <p className="text-[10px] text-[#666]">{t('setup.ronin_enable_desc')}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => { setRoninEnabled(!roninEnabled); if (!roninEnabled && !roninCheck) { handleRoninCheck(); } }}
                    className={`relative w-12 h-6 rounded-full transition-all duration-300 ${
                      roninEnabled ? 'bg-[#f97316]' : 'bg-[#2a2f3e]'
                    }`}
                  >
                    <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all duration-300 ${
                      roninEnabled ? 'left-[26px]' : 'left-0.5'
                    }`} />
                  </button>
                </div>
              </div>
            </div>

            {roninEnabled && (
              <div className="max-w-3xl mx-auto space-y-4 animate-in slide-in-from-top-3 duration-300">
                {/* OS Detection */}
                {roninCheck && (
                  <div className="bg-[#0d1117] border border-[#2a2f3e] rounded-xl p-5 space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-[#3b82f6] uppercase tracking-widest">{t('setup.ronin_system_detection')}</h3>
                      <button onClick={handleRoninCheck} className="text-[10px] text-[#3b82f6] hover:text-[#d4a017] font-bold uppercase tracking-widest">
                        {t('common.refresh')}
                      </button>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="bg-[#0a0e1a] border border-[#1a1f2e] rounded-lg p-3">
                        <p className="text-[9px] text-[#888] uppercase tracking-widest font-bold">{t('setup.ronin_operating_system')}</p>
                        <p className="text-sm font-bold text-white mt-1">{roninCheck.os}</p>
                      </div>
                      {roninCheck.display_server && (
                        <div className="bg-[#0a0e1a] border border-[#1a1f2e] rounded-lg p-3">
                          <p className="text-[9px] text-[#888] uppercase tracking-widest font-bold">{t('setup.ronin_display_server')}</p>
                          <p className="text-sm font-bold text-white mt-1 uppercase">{roninCheck.display_server}</p>
                        </div>
                      )}
                    </div>

                    {/* Dependency status — click to install missing */}
                    <div className="space-y-2">
                      <p className="text-[9px] text-[#888] uppercase tracking-widest font-bold">{t('setup.ronin_dependencies')} <span className="text-[#555] normal-case font-normal">— {t('setup.ronin_click_missing')}</span></p>
                      <div className="grid grid-cols-2 gap-2">
                        {Object.entries(roninCheck.deps || {}).map(([name, info]: [string, any]) => {
                          const isInstalling = (roninCheck as any)?.[`_installing_${name}`];
                          return (
                            <button
                              key={name}
                              disabled={info.installed || isInstalling}
                              onClick={async () => {
                                if (info.installed) return;
                                setRoninCheck((prev: any) => ({ ...prev, [`_installing_${name}`]: true }));
                                try {
                                  const res = await axios.post('/api/v1/setup/ronin-install-dep', { dep_name: name });
                                  if (res.data.data?.status === 'success') {
                                    handleRoninCheck();
                                  } else {
                                    setRoninInstallResult(res.data.data?.message || formatTranslation('setup.ronin_failed_dep', { name }));
                                  }
                                } catch {
                                  setRoninInstallResult(formatTranslation('setup.ronin_failed_dep', { name }));
                                } finally {
                                  setRoninCheck((prev: any) => ({ ...prev, [`_installing_${name}`]: false }));
                                }
                              }}
                              className={`flex items-center gap-2 p-2.5 rounded-lg border text-left transition-all ${
                                info.installed
                                  ? 'bg-green-500/5 border-green-500/20'
                                  : isInstalling
                                    ? 'bg-orange-500/5 border-orange-500/20 animate-pulse'
                                    : 'bg-red-500/5 border-red-500/20 hover:border-[#f97316]/50 hover:bg-[#f97316]/5 cursor-pointer'
                              } disabled:cursor-default`}
                            >
                              {isInstalling
                                ? <Loader2 className="w-3.5 h-3.5 text-[#f97316] animate-spin shrink-0" />
                                : info.installed
                                  ? <CheckCircle2 className="w-3.5 h-3.5 text-green-500 shrink-0" />
                                  : <AlertCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />
                              }
                              <div>
                                <p className="text-xs font-bold text-white">{name}</p>
                                <p className="text-[9px] text-[#666]">{
                                  isInstalling ? t('setup.ronin_installing') :
                                  info.installed ? `v${info.version}` : t('setup.ronin_click_install')
                                }</p>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* Install button */}
                    {!roninCheck.all_core_installed && (
                      <button
                        onClick={handleRoninInstall}
                        disabled={roninInstalling}
                        className="w-full py-3 rounded-lg bg-[#f97316] hover:bg-[#f97316]/80 text-black font-bold text-sm transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                      >
                        {roninInstalling ? (
                          <><Loader2 className="w-4 h-4 animate-spin" /> {t('setup.ronin_installing_dependencies')}</>
                        ) : (
                          <>{t('setup.ronin_install_dependencies')}</>
                        )}
                      </button>
                    )}

                    {roninInstallResult === 'success' && (
                      <div className="flex items-center gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                        <CheckCircle2 className="w-4 h-4 text-green-500" />
                        <span className="text-sm text-green-500 font-medium">{t('setup.ronin_install_success')}</span>
                      </div>
                    )}
                    {roninInstallResult && roninInstallResult !== 'success' && (
                      <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                        <AlertCircle className="w-4 h-4 text-red-400" />
                        <span className="text-sm text-red-400 font-medium">{roninInstallResult}</span>
                      </div>
                    )}

                    {/* OS-specific notes */}
                    {roninCheck.notes?.length > 0 && (
                      <div className="bg-orange-500/5 border border-orange-500/20 rounded-lg p-3 space-y-1">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="w-3.5 h-3.5 text-orange-400 shrink-0" />
                          <span className="text-[10px] font-bold text-orange-400 uppercase tracking-widest">{t('setup.ronin_platform_notes')}</span>
                        </div>
                        {roninCheck.notes.map((note: string, i: number) => (
                          <p key={i} className="text-[11px] text-[#999] leading-relaxed pl-5">{note}</p>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Capabilities preview */}
                <div className="bg-[#0d1117] border border-[#2a2f3e] rounded-xl p-5">
                  <h3 className="text-sm font-bold text-[#d4a017] uppercase tracking-widest mb-3">{t('setup.ronin_capabilities')}</h3>
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { icon: Camera, label: t('setup.ronin_screenshots'), desc: t('setup.ronin_screenshots_desc') },
                      { icon: Mouse, label: t('setup.ronin_mouse'), desc: t('setup.ronin_mouse_desc') },
                      { icon: Keyboard, label: t('setup.ronin_keyboard'), desc: t('setup.ronin_keyboard_desc') },
                    ].map(({ icon: Icon, label, desc }) => (
                      <div key={label} className="bg-[#0a0e1a] border border-[#1a1f2e] rounded-lg p-3 text-center">
                        <Icon className="w-6 h-6 text-[#f97316] mx-auto mb-2" />
                        <p className="text-xs font-bold text-white">{label}</p>
                        <p className="text-[9px] text-[#666] mt-0.5">{desc}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Risk acknowledgment */}
                <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-5">
                  <label className="flex items-start gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={roninAcknowledged}
                      onChange={e => setRoninAcknowledged(e.target.checked)}
                      className="mt-1 accent-[#f97316] w-4 h-4 shrink-0"
                    />
                    <div>
                      <p className="text-sm font-bold text-white">{t('setup.ronin_acknowledge')}</p>
                      <p className="text-[10px] text-[#999] leading-relaxed mt-1">{t('setup.ronin_acknowledge_desc')}</p>
                    </div>
                  </label>
                </div>
              </div>
            )}
          </div>
        );
      }

      // ═══════════════════════════════════════════════════════════
      // STEP 9: Complete Setup
      // ═══════════════════════════════════════════════════════════
      case 9: {
        if (completed) {
          return (
            <div className="flex flex-col items-center justify-center min-h-[400px] animate-in fade-in zoom-in duration-700">
              <div className="w-24 h-24 rounded-full bg-[#d4a017]/20 flex items-center justify-center mb-6 animate-pulse">
                <CheckCircle2 className="w-12 h-12 text-[#d4a017]" />
              </div>
              <h2 className="text-4xl font-bold text-[#d4a017] mb-2">{t('setup.step8_risen')}</h2>
              <p className="text-sm text-[#888]">{t('common.loading')}</p>
            </div>
          );
        }

        const selectedLang = AVAILABLE_LANGUAGES.find(l => l.code === language);
        const connectedProviders = providers.filter(p => p.status === 'connected');

        return (
          <div className="space-y-6">
            <div className="text-center">
              <div className="text-5xl mb-4">⚔️</div>
              <h2 className="text-3xl font-bold text-white">{t('setup.step8_title')}</h2>
              <p className="text-sm text-[#888] mt-2 max-w-lg mx-auto">{t('setup.step8_subtitle')}</p>
            </div>
            <div className="max-w-3xl mx-auto bg-[#0d1117]/60 border border-[#1a1f2e] rounded-xl p-4 text-sm text-[#999] leading-relaxed">
              <p>{t('setup.step8_explainer')}</p>
            </div>

            {/* Summary grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 max-w-3xl mx-auto">
              {[
                { label: t('setup.step8_language'), value: selectedLang ? `${selectedLang.flag} ${selectedLang.name}` : language, color: '#d4a017' },
                { label: t('setup.step8_identity'), value: agentName, color: '#d4a017' },
                { label: t('setup.step3_tone'), value: t(`setup.step3_tone_${tone}`), color: '#3b82f6' },
                { label: t('setup.step3_autonomy'), value: `${autonomy}%`, color: '#3b82f6' },
                { label: t('setup.step3_risk'), value: t(`setup.step3_risk_${riskTolerance}`), color: '#3b82f6' },
                { label: t('setup.step8_provider'), value: `${connectedProviders.length} ${t('setup.step5_connected')}`, color: connectedProviders.length > 0 ? '#22c55e' : '#888' },
                { label: t('setup.routing_profile'), value: routingProfiles.find(item => item.id === routingProfile)?.name || routingProfile, color: '#a78bfa' },
                { label: t('setup.step8_model'), value: routingProfile === 'custom' && primaryModel ? primaryModel.split('::')[1] : t('setup.automatic'), color: routingProfile === 'custom' && primaryModel ? '#d4a017' : '#3b82f6' },
                { label: t('setup.step8_security'), value: t(`setup.step3_security_${securityBias}`), color: '#3b82f6' },
                { label: t('setup.step7_fallback'), value: `${fallbackModels.length}`, color: fallbackModels.length > 0 ? '#22c55e' : '#888' },
              ].map(item => (
                <div key={item.label} className="bg-[#0d1117] border border-[#2a2f3e] rounded-xl p-3.5 text-center">
                  <p className="text-[9px] font-bold text-[#888] uppercase tracking-widest mb-1">{item.label}</p>
                  <p className="text-sm font-bold capitalize truncate" style={{ color: item.color }}>{item.value}</p>
                </div>
              ))}
            </div>

            {/* Legal Disclaimer */}
            <div className="max-w-3xl mx-auto bg-orange-500/5 border border-orange-500/20 rounded-xl p-5">
              <div className="flex items-start gap-4">
                <AlertCircle className="w-5 h-5 text-orange-400 shrink-0 mt-0.5" />
                <div className="space-y-3">
                  <h4 className="text-[11px] font-bold text-white uppercase tracking-widest flex items-center gap-2">
                    <Shield className="w-3.5 h-3.5 text-orange-400" />
                    {t('guide.disclaimer_title', 'Disclaimer')}
                  </h4>
                  <p className="text-[10px] text-[#999] leading-relaxed">
                    {t('guide.disclaimer_body')}
                  </p>
                  <p className="text-[10px] font-bold text-white leading-relaxed">
                    {t('guide.disclaimer_oversight')}
                  </p>
                </div>
              </div>
            </div>

            {completionError && (
              <div className="max-w-2xl mx-auto flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-left">
                <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-bold text-red-300">{t('setup.completion_error_title')}</p>
                  <p className="text-xs text-red-200/80 mt-1 leading-relaxed">{completionError}</p>
                </div>
              </div>
            )}

            {/* Rise + Cancel buttons */}
            <div className="flex items-center justify-center gap-4 pt-4">
              <button
                onClick={goBack}
                disabled={completing}
                className="px-6 py-3.5 rounded-xl font-bold text-sm border border-[#2a2f3e] text-[#888] hover:text-white hover:border-[#555] transition-all disabled:opacity-30"
              >
                <span className="flex items-center gap-2">
                  <ChevronLeft className="w-4 h-4" /> {t('setup.back')}
                </span>
              </button>
              <button
                onClick={handleComplete}
                disabled={completing}
                className="
                  relative px-12 py-4 rounded-2xl font-bold text-lg text-black
                  bg-gradient-to-r from-[#d4a017] via-[#e6b422] to-[#d4a017]
                  hover:from-[#e6b422] hover:via-[#f0c040] hover:to-[#e6b422]
                  shadow-[0_0_40px_rgba(212,160,23,0.3)] hover:shadow-[0_0_60px_rgba(212,160,23,0.5)]
                  transition-all duration-500 disabled:opacity-50
                  animate-in zoom-in duration-500
                "
              >
                {completing ? (
                  <span className="flex items-center gap-3">
                    <Loader2 className="w-5 h-5 animate-spin" /> {t('setup.step8_configuring')}
                  </span>
                ) : (
                  <span className="flex items-center gap-3">
                    ⚔️ {t('setup.step8_rise')}
                  </span>
                )}
                {!completing && (
                  <div className="absolute inset-0 rounded-2xl border-2 border-[#d4a017]/50 animate-ping opacity-20" />
                )}
              </button>
            </div>
          </div>
        );
      }

      default:
        return null;
    }
  };

  // ── Main render ──────────────────────────────────────────────
  return (
    <div className="fixed inset-0 bg-[#0a0e1a] text-white overflow-y-auto z-50">
      {/* Subtle grid background */}
      <div className="fixed inset-0 opacity-[0.03] pointer-events-none"
        style={{ backgroundImage: 'linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)', backgroundSize: '40px 40px' }} />

      <div className="relative max-w-5xl mx-auto px-6 py-10">
        {/* Header */}
        <div className="text-center mb-6">
          <h1 className="text-sm font-bold text-[#d4a017] uppercase tracking-[0.3em]">{t('setup.wizard_title')}</h1>
          <p className="text-[11px] text-[#555] mt-1">{formatTranslation('setup.progress', { current: step, total: TOTAL_STEPS })}</p>
        </div>

        {/* Progress bar */}
        <ProgressBar />

        {/* Step content with animation */}
        <div key={step} className={`animate-in ${animDir === 'left' ? 'slide-in-from-right-5' : 'slide-in-from-left-5'} fade-in duration-400`}>
          {renderStep()}
        </div>

        {/* Navigation */}
        {step < 9 && step !== 8 && (
          <div className="flex items-center justify-between mt-10 max-w-3xl mx-auto">
            <button
              onClick={goBack}
              disabled={step === 1}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg border border-[#2a2f3e] text-sm font-bold text-[#888] hover:text-white hover:border-[#555] transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" /> {t('setup.back')}
            </button>
            {step === 5 && providers.filter(p => p.status === 'connected').length === 0 ? (
              <button
                onClick={goNext}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-bold text-[#888] hover:text-[#d4a017] transition-all"
              >
                {t('setup.skip')} <ChevronRight className="w-4 h-4" />
              </button>
            ) : null}
            <button
              onClick={goNext}
              disabled={step === 1 && (!operatorName.trim() || !teamSetupValid)}
              className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-[#3b82f6] hover:bg-[#3b82f6]/80 text-sm font-bold text-white shadow-lg shadow-[#3b82f6]/20 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            >
              {t('setup.next')} <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Step 8 (Ronin) custom navigation */}
        {step === 8 && (
          <div className="flex items-center justify-between mt-10 max-w-3xl mx-auto">
            <button
              onClick={goBack}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg border border-[#2a2f3e] text-sm font-bold text-[#888] hover:text-white hover:border-[#555] transition-all"
            >
              <ChevronLeft className="w-4 h-4" /> {t('setup.back')}
            </button>
            {!roninEnabled && !serverMode && (
              <button
                onClick={goNext}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-bold text-[#888] hover:text-[#d4a017] transition-all"
              >
                {t('setup.ronin_skip')} <ChevronRight className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={goNext}
              disabled={roninEnabled && !roninAcknowledged}
              className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-[#3b82f6] hover:bg-[#3b82f6]/80 text-sm font-bold text-white shadow-lg shadow-[#3b82f6]/20 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            >
              {t('setup.next')} <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
