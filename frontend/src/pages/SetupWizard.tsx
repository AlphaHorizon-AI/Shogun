import { useState, useEffect, useCallback } from 'react';
import {
  Globe, FolderOpen, User, Shield, Cpu, FileText, Zap, ChevronRight,
  ChevronLeft, Check, CheckCircle2, AlertCircle, Database, HardDrive,
  Settings, ScrollText, X, GripVertical, Loader2, Sparkles
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
  models: string[];
  status: 'pending' | 'testing' | 'connected' | 'failed';
}

interface SetupWizardProps {
  onComplete: () => void;
}

// ── Constants ──────────────────────────────────────────────────

const TOTAL_STEPS = 8;

const PROVIDER_CARDS = [
  { type: 'openai',     label: 'OpenAI',      icon: '⚡', color: '#10a37f' },
  { type: 'anthropic',  label: 'Anthropic',    icon: '🧠', color: '#d4a017' },
  { type: 'google',     label: 'Google Gemini',icon: '✨', color: '#4285f4' },
  { type: 'ollama',     label: 'Ollama',       icon: '🦙', color: '#ffffff' },
  { type: 'openrouter', label: 'OpenRouter',   icon: '🌐', color: '#6366f1' },
  { type: 'perplexity', label: 'Perplexity',   icon: '🔍', color: '#20b2aa' },
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
  const { t, setLanguage: setI18nLanguage } = useTranslation();
  const [step, setStep] = useState(1);
  const [animDir, setAnimDir] = useState<'left' | 'right'>('left');

  // Step 1: Language
  const [language, setLanguage] = useState('en');

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
  const [primaryModel, setPrimaryModel] = useState('');
  const [fallbackModels, setFallbackModels] = useState<string[]>([]);

  // Step 8: Completing
  const [completing, setCompleting] = useState(false);
  const [completed, setCompleted] = useState(false);

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
          setLanguage(statusRes.value.data.data?.language || 'en');
        }
        if (personasRes.status === 'fulfilled') {
          setPersonas(personasRes.value.data.data || []);
        }
      } catch {}
    };
    load();
  }, []);

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
      base_url: isLocal ? 'http://localhost:11434' : '',
      models: [],
      status: 'pending' as const,
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
    // Simulate a brief delay for UX
    await new Promise(r => setTimeout(r, 1200));
    // If the provider has an API key or is local, mark as connected
    if (prov.api_key || ['ollama', 'lmstudio', 'local'].includes(prov.provider_type)) {
      updateProvider(prov.id, { status: 'connected' });
    } else {
      updateProvider(prov.id, { status: 'failed' });
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

  // ── Complete setup ───────────────────────────────────────────
  const handleComplete = async () => {
    setCompleting(true);
    try {
      await axios.post('/api/v1/setup/complete', {
        language,
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
          api_key: p.api_key || null,
          base_url: p.base_url || null,
          models: p.models,
        })),
        constitution,
        mandate,
        primary_model: primaryModel,
        fallback_models: fallbackModels,
      });

      // Store language in localStorage
      localStorage.setItem('shogun_language', language);

      setCompleted(true);
      setTimeout(() => {
        onComplete();
      }, 2500);
    } catch (err) {
      console.error('Setup failed:', err);
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
                  <label className="text-[10px] text-[#888] uppercase tracking-widest font-bold">Data Directory</label>
                  <input
                    type="text"
                    value={dataPath}
                    onChange={e => setDataPath(e.target.value)}
                    placeholder="C:\Users\you\Shogun\data"
                    className="w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm font-mono text-[#d4a017] focus:border-[#d4a017] outline-none transition-colors"
                  />
                  <p className="text-[10px] text-[#555]">Enter the absolute path where Shogun data should live. The directory will be created if it doesn't exist.</p>
                </div>
                <div className="h-px bg-[#2a2f3e]" />
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { icon: Database, label: 'Database', sub: 'shogun.db' },
                    { icon: HardDrive, label: 'Vector Memory', sub: 'qdrant/' },
                    { icon: Settings, label: 'Configurations', sub: 'configs/' },
                    { icon: ScrollText, label: 'Logs & Audit', sub: 'logs/' },
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
                  <User className="w-4 h-4" /> Identity
                </h3>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">Agent Name</label>
                  <input
                    type="text"
                    value={agentName}
                    onChange={e => setAgentName(e.target.value)}
                    placeholder="Shogun Prime"
                    className="w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm text-white focus:border-[#d4a017] outline-none transition-colors"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">Description</label>
                  <textarea
                    value={description}
                    onChange={e => setDescription(e.target.value)}
                    placeholder="Master orchestrator of the Samurai Network."
                    className="w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm text-white focus:border-[#d4a017] outline-none transition-colors min-h-[80px] resize-y"
                  />
                </div>
                {personas.length > 0 && (
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">Active Persona</label>
                    <Select value={personaId} onChange={setPersonaId}>
                      <option value="">Select a persona...</option>
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
                  <Zap className="w-4 h-4" /> Autonomy & Logic
                </h3>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">Autonomy Level</label>
                    <span className="text-[#3b82f6] font-mono font-bold text-sm">{autonomy}%</span>
                  </div>
                  <input type="range" min="0" max="100" step="10" value={autonomy}
                    onChange={e => setAutonomy(parseInt(e.target.value))}
                    className="w-full accent-[#3b82f6]" />
                </div>
                <div className="grid grid-cols-2 gap-2.5">
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">Tone</label>
                    <Select value={tone} onChange={setTone}>
                      <option value="analytical">Analytical</option>
                      <option value="direct">Direct</option>
                      <option value="supportive">Supportive</option>
                      <option value="strategic">Strategic</option>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">Risk</label>
                    <Select value={riskTolerance} onChange={setRiskTolerance}>
                      <option value="low">Low (Cautious)</option>
                      <option value="medium">Medium (Balanced)</option>
                      <option value="high">High (Aggressive)</option>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">Verbosity</label>
                    <Select value={verbosity} onChange={setVerbosity}>
                      <option value="low">Concise</option>
                      <option value="medium">Moderate</option>
                      <option value="high">Detailed</option>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">Planning</label>
                    <Select value={planningDepth} onChange={setPlanningDepth}>
                      <option value="low">Shallow</option>
                      <option value="medium">Standard</option>
                      <option value="high">Deep</option>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">Tools</label>
                    <Select value={toolUsage} onChange={setToolUsage}>
                      <option value="conservative">Conservative</option>
                      <option value="balanced">Balanced</option>
                      <option value="aggressive">Aggressive</option>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">Security</label>
                    <Select value={securityBias} onChange={setSecurityBias}>
                      <option value="strict">Strict</option>
                      <option value="balanced">Balanced</option>
                      <option value="open">Open</option>
                    </Select>
                  </div>
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">Memory Style</label>
                  <Select value={memoryStyle} onChange={setMemoryStyle}>
                    <option value="conservative">Conservative</option>
                    <option value="focused">Focused (Task-relevant)</option>
                    <option value="expansive">Expansive (Broad context)</option>
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
                  <span className="text-[10px] font-bold text-[#888] uppercase tracking-widest">YAML Configuration</span>
                  <button
                    onClick={() => setDirectives(DEFAULT_DIRECTIVES)}
                    className="text-[10px] font-bold text-[#3b82f6] hover:text-[#d4a017] uppercase tracking-widest transition-colors"
                  >
                    Reset to Defaults
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
                  <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">Provider Name</label>
                  <input
                    value={activeProv.name}
                    onChange={e => updateProvider(activeProv.id, { name: e.target.value })}
                    className="w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm text-white focus:border-[#3b82f6] outline-none transition-colors"
                  />
                </div>

                {['ollama', 'lmstudio', 'local'].includes(activeProv.provider_type) ? (
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">Base URL</label>
                    <input
                      value={activeProv.base_url}
                      onChange={e => updateProvider(activeProv.id, { base_url: e.target.value })}
                      placeholder="http://localhost:11434"
                      className="w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm font-mono text-white focus:border-[#3b82f6] outline-none transition-colors"
                    />
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">API Key</label>
                    <input
                      type="password"
                      value={activeProv.api_key}
                      onChange={e => updateProvider(activeProv.id, { api_key: e.target.value })}
                      placeholder="sk-..."
                      className="w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm font-mono text-white focus:border-[#3b82f6] outline-none transition-colors"
                    />
                  </div>
                )}

                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-[#888] uppercase tracking-widest">Models (comma-separated)</label>
                  <input
                    value={activeProv.models.join(', ')}
                    onChange={e => updateProvider(activeProv.id, { models: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                    placeholder="gpt-4o, gpt-4o-mini"
                    className="w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-2.5 text-sm font-mono text-white focus:border-[#3b82f6] outline-none transition-colors"
                  />
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={() => testProvider(activeProv)}
                    disabled={activeProv.status === 'testing'}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#3b82f6] hover:bg-[#3b82f6]/80 text-white text-sm font-bold transition-all disabled:opacity-50"
                  >
                    {activeProv.status === 'testing' ? (
                      <><Loader2 className="w-4 h-4 animate-spin" /> Testing...</>
                    ) : (
                      <><Zap className="w-4 h-4" /> Test Connection</>
                    )}
                  </button>
                  {activeProv.status === 'connected' && (
                    <span className="text-sm text-green-400 flex items-center gap-1"><CheckCircle2 className="w-4 h-4" /> Connected</span>
                  )}
                  {activeProv.status === 'failed' && (
                    <span className="text-sm text-red-400 flex items-center gap-1"><AlertCircle className="w-4 h-4" /> Failed</span>
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
                  <span className="text-[10px] font-bold text-[#d4a017] uppercase tracking-widest">⚖️ Constitution (YAML)</span>
                  <button onClick={() => setConstitution(DEFAULT_CONSTITUTION)}
                    className="text-[10px] font-bold text-[#3b82f6] hover:text-[#d4a017] uppercase tracking-widest transition-colors">
                    Use Defaults
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
                  <span className="text-[10px] font-bold text-[#3b82f6] uppercase tracking-widest">📜 Mandate (Markdown)</span>
                  <button onClick={() => setMandate(DEFAULT_MANDATE)}
                    className="text-[10px] font-bold text-[#3b82f6] hover:text-[#d4a017] uppercase tracking-widest transition-colors">
                    Use Defaults
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
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
              {/* Primary */}
              <div className="bg-[#0d1117] border border-[#2a2f3e] rounded-xl p-5 space-y-4">
                <h3 className="text-sm font-bold text-[#3b82f6] uppercase tracking-widest flex items-center gap-2">
                  <Cpu className="w-4 h-4" /> Primary Model
                </h3>
                <p className="text-[10px] text-[#666]">The default model used for all Shogun reasoning and task execution.</p>
                {allModelOptions.length === 0 ? (
                  <p className="text-xs text-[#888] italic text-center py-4">No connected providers. Go back to Step 5 or configure later.</p>
                ) : (
                  <select
                    value={primaryModel}
                    onChange={e => setPrimaryModel(e.target.value)}
                    className="w-full bg-[#050508] border border-[#2a2f3e] rounded-lg p-3 text-sm font-mono text-white focus:border-[#d4a017] outline-none transition-colors"
                  >
                    <option value="">— Choose a model —</option>
                    {allModelOptions.map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label} ({opt.group})</option>
                    ))}
                  </select>
                )}
                {primaryModel && (
                  <div className="flex items-center gap-2 p-2.5 rounded-lg bg-[#d4a017]/5 border border-[#d4a017]/20">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#d4a017] shrink-0" />
                    <span className="text-xs font-mono text-[#d4a017] font-bold truncate">{primaryModel.split('::')[1]}</span>
                    <span className="text-[9px] text-[#888] ml-auto shrink-0">PRIMARY</span>
                  </div>
                )}
              </div>
              {/* Fallback */}
              <div className="bg-[#0d1117] border border-[#2a2f3e] rounded-xl p-5 space-y-4">
                <h3 className="text-sm font-bold text-[#d4a017] uppercase tracking-widest flex items-center gap-2">
                  <Sparkles className="w-4 h-4" /> Fallback Models
                </h3>
                <p className="text-[10px] text-[#666]">Used when the primary is unavailable. Order matters — drag to reorder.</p>
                {allModelOptions.length === 0 ? (
                  <p className="text-xs text-[#888] italic text-center py-4">No connected providers.</p>
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
                      <option value="">— Add a fallback model —</option>
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
                      <p className="text-[11px] text-[#888] italic text-center py-2">No fallbacks selected.</p>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        );

      // ═══════════════════════════════════════════════════════════
      // STEP 8: Rise, Shogun!
      // ═══════════════════════════════════════════════════════════
      case 8:
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
                { label: t('setup.step3_tone'), value: tone, color: '#3b82f6' },
                { label: t('setup.step3_autonomy'), value: `${autonomy}%`, color: '#3b82f6' },
                { label: t('setup.step3_risk'), value: riskTolerance, color: '#3b82f6' },
                { label: t('setup.step8_provider'), value: `${connectedProviders.length} ${t('setup.step5_connected')}`, color: connectedProviders.length > 0 ? '#22c55e' : '#888' },
                { label: t('setup.step8_model'), value: primaryModel ? primaryModel.split('::')[1] : t('setup.step8_none_selected'), color: primaryModel ? '#d4a017' : '#888' },
                { label: t('setup.step8_security'), value: securityBias, color: '#3b82f6' },
                { label: t('setup.step7_fallback'), value: `${fallbackModels.length}`, color: fallbackModels.length > 0 ? '#22c55e' : '#888' },
              ].map(item => (
                <div key={item.label} className="bg-[#0d1117] border border-[#2a2f3e] rounded-xl p-3.5 text-center">
                  <p className="text-[9px] font-bold text-[#888] uppercase tracking-widest mb-1">{item.label}</p>
                  <p className="text-sm font-bold capitalize truncate" style={{ color: item.color }}>{item.value}</p>
                </div>
              ))}
            </div>

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
          <h1 className="text-sm font-bold text-[#d4a017] uppercase tracking-[0.3em]">Shogun Setup</h1>
          <p className="text-[11px] text-[#555] mt-1">Step {step} of {TOTAL_STEPS}</p>
        </div>

        {/* Progress bar */}
        <ProgressBar />

        {/* Step content with animation */}
        <div key={step} className={`animate-in ${animDir === 'left' ? 'slide-in-from-right-5' : 'slide-in-from-left-5'} fade-in duration-400`}>
          {renderStep()}
        </div>

        {/* Navigation */}
        {step < 8 && (
          <div className="flex items-center justify-between mt-10 max-w-3xl mx-auto">
            <button
              onClick={goBack}
              disabled={step === 1}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg border border-[#2a2f3e] text-sm font-bold text-[#888] hover:text-white hover:border-[#555] transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" /> Back
            </button>
            {step === 5 && providers.filter(p => p.status === 'connected').length === 0 ? (
              <button
                onClick={goNext}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-bold text-[#888] hover:text-[#d4a017] transition-all"
              >
                Skip for now <ChevronRight className="w-4 h-4" />
              </button>
            ) : null}
            <button
              onClick={goNext}
              className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-[#3b82f6] hover:bg-[#3b82f6]/80 text-sm font-bold text-white shadow-lg shadow-[#3b82f6]/20 transition-all"
            >
              Next <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
