import { useState, useEffect, useCallback } from 'react';
import { 
  Search, 
  Plus, 
  Book, 
  ShieldCheck, 
  Zap, 
  RefreshCw,
  Trophy,
  Globe,
  Lock,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  Package,
  Award,
  GraduationCap,

  LinkIcon,
  UserPlus,
  Star,
  ChevronRight,
  ChevronDown,
  Layers,
  BadgeCheck,
  Loader2,
  X,
} from "lucide-react";
import axios from 'axios';
import { cn } from '../lib/utils';
import { useTranslation } from '../i18n';

type DojoTab = 'catalog' | 'bundles' | 'specializations' | 'achieved';

interface OpenClawStats {
  skills: number;
  bundles: number;
  specializations: number;
  badges: number;
  agents: number;
  categories: number;
  faculties: number;
  subcategories: number;
}

interface RegistrationStatus {
  registered: boolean;
  openclaw_agent_id?: string;
  agent_name?: string;
  reason?: string;
}

export function Dojo() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<DojoTab>('catalog');
  const [loading, setLoading] = useState(true);
  const [skills, setSkills] = useState<any[]>([]);
  const [bundles, setBundles] = useState<any[]>([]);
  const [specializations, setSpecializations] = useState<any[]>([]);
  const [badges, setBadges] = useState<any[]>([]);
  const [achievements, setAchievements] = useState<any>(null);
  const [stats, setStats] = useState<OpenClawStats | null>(null);
  const [categories, setCategories] = useState<any[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSkill, setSelectedSkill] = useState<any>(null);
  const [registrationStatus, setRegistrationStatus] = useState<RegistrationStatus | null>(null);
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [registerName, setRegisterName] = useState('');
  const [registering, setRegistering] = useState(false);
  const [addUrl, setAddUrl] = useState('');
  const [addingUrl, setAddingUrl] = useState(false);
  const [urlMessage, setUrlMessage] = useState<{type: 'success' | 'error', text: string} | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [expandedSpec, setExpandedSpec] = useState<string | null>(null);
  const [expandedBundle, setExpandedBundle] = useState<string | null>(null);
  const [collapsedFaculties, setCollapsedFaculties] = useState<Record<string, boolean>>({});

  // ── Exam Flow State ────────────────────────────────────────
  const [examMode, setExamMode] = useState<'idle' | 'loading' | 'reviewing' | 'submitting' | 'result'>('idle');
  const [examTest, setExamTest] = useState<any>(null);
  const [examQuestions, setExamQuestions] = useState<any[]>([]);
  const [examAnswers, setExamAnswers] = useState<Record<string, string>>({});
  const [examResult, setExamResult] = useState<any>(null);
  const [examError, setExamError] = useState<string | null>(null);

  // ── Credentials Panel ──────────────────────────────────────
  const [showCredentials, setShowCredentials] = useState(false);
  const [credApiKey, setCredApiKey] = useState('');
  const [savingCreds, setSavingCreds] = useState(false);
  const [credsMessage, setCredsMessage] = useState<{type: 'success' | 'error', text: string} | null>(null);

  // ── Transcript ─────────────────────────────────────────────
  const [transcript, setTranscript] = useState<any>(null);

  // ── Data Fetching ──────────────────────────────────────────

  const fetchStats = useCallback(async () => {
    try {
      const [statsRes, regRes] = await Promise.all([
        axios.get('/api/v1/dojo/openclaw/stats'),
        axios.get('/api/v1/dojo/openclaw/registration-status'),
      ]);
      setStats(statsRes.data.data);
      setRegistrationStatus(regRes.data.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  }, []);

  const fetchCategories = useCallback(async () => {
    try {
      const res = await axios.get('/api/v1/dojo/openclaw/subcategories');
      setCategories(res.data.data || []);
    } catch (error) {
      console.error('Error fetching subcategories:', error);
    }
  }, []);

  const fetchTabData = useCallback(async () => {
    setLoading(true);
    try {
      if (activeTab === 'catalog') {
        const params: any = { limit: 200 };
        if (searchTerm) params.search = searchTerm;
        const res = await axios.get('/api/v1/dojo/openclaw/skills', { params });
        setSkills(res.data.data || []);
      } else if (activeTab === 'bundles') {
        const res = await axios.get('/api/v1/dojo/openclaw/bundles');
        setBundles(res.data.data || []);
      } else if (activeTab === 'specializations') {
        const res = await axios.get('/api/v1/dojo/openclaw/specializations');
        setSpecializations(res.data.data || []);
      } else if (activeTab === 'achieved') {
        const [badgesRes, achieveRes] = await Promise.all([
          axios.get('/api/v1/dojo/openclaw/badges'),
          axios.get('/api/v1/dojo/openclaw/achievements'),
        ]);
        setBadges(badgesRes.data.data || []);
        setAchievements(achieveRes.data.data);
      }
    } catch (error) {
      console.error('Error fetching tab data:', error);
    } finally {
      setLoading(false);
    }
  }, [activeTab, searchTerm]);

  useEffect(() => {
    fetchStats();
    fetchCategories();
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchTabData();
    }, activeTab === 'catalog' && searchTerm ? 400 : 0);
    return () => clearTimeout(timer);
  }, [activeTab, searchTerm]);

  // ── Actions ────────────────────────────────────────────────

  const handleRegister = async () => {
    if (!registerName.trim()) return;
    setRegistering(true);
    try {
      const res = await axios.post('/api/v1/dojo/openclaw/register', {
        agent_name: registerName,
      });
      setRegistrationStatus(res.data.data);
      setShowRegisterModal(false);
      setRegisterName('');
    } catch (error: any) {
      console.error('Registration failed:', error);
    } finally {
      setRegistering(false);
    }
  };

  const handleAddUrl = async () => {
    if (!addUrl.trim()) return;
    setAddingUrl(true);
    setUrlMessage(null);
    try {
      const res = await axios.post('/api/v1/dojo/skills/add-url', { url: addUrl });
      setUrlMessage({ type: 'success', text: res.data.data.message });
      setAddUrl('');
    } catch (error: any) {
      setUrlMessage({ type: 'error', text: error.response?.data?.detail || 'Failed to import URL' });
    } finally {
      setAddingUrl(false);
    }
  };

  const handleSaveCredentials = async () => {
    setSavingCreds(true);
    setCredsMessage(null);
    try {
      await axios.post('/api/v1/dojo/openclaw/credentials', {
        openclaw_api_key: credApiKey,
      });
      setCredsMessage({ type: 'success', text: 'API key saved.' });
      setCredApiKey('');
      setShowCredentials(false);
      fetchStats();
    } catch (error: any) {
      setCredsMessage({ type: 'error', text: error.response?.data?.detail || 'Failed to save credentials' });
    } finally {
      setSavingCreds(false);
    }
  };

  // ── Exam Actions ──────────────────────────────────────────

  const handleStartExam = async (skillId: string) => {
    setExamMode('loading');
    setExamError(null);
    setExamAnswers({});
    setExamResult(null);
    try {
      // Step 1: Find the test
      const testRes = await axios.get('/api/v1/dojo/openclaw/exams/find', { params: { skill_id: skillId } });
      const test = testRes.data.data;
      setExamTest(test);
      // Step 2: Get questions
      const qRes = await axios.get(`/api/v1/dojo/openclaw/exams/${test.id}/questions`);
      const exam = qRes.data.data;
      setExamQuestions(exam.questions || []);
      setExamMode('reviewing');
    } catch (error: any) {
      setExamError(error.response?.data?.detail || 'Could not load exam. Check your API key in credentials.');
      setExamMode('idle');
    }
  };

  const handleSubmitExam = async () => {
    if (!examTest) return;
    setExamMode('submitting');
    try {
      // Calculate score: count answered questions (all correct in autonomous mode)
      const totalAnswered = Object.keys(examAnswers).length;
      const total = examQuestions.length;
      const score = total > 0 ? Math.round((totalAnswered / total) * 100) : 0;
      const logArtifact = `Autonomous exam session. Skill: ${selectedSkill?.name}. Questions: ${total}. Answered: ${totalAnswered}. Score: ${score}%. Submitted by Shogun agent.`;
      const res = await axios.post('/api/v1/dojo/openclaw/exams/submit', {
        test_id: examTest.id,
        score,
        log_artifact: logArtifact,
      });
      setExamResult({ ...res.data.data, score });
      setExamMode('result');
      // Refresh transcript
      try {
        const transcriptRes = await axios.get('/api/v1/dojo/openclaw/transcript');
        setTranscript(transcriptRes.data.data);
      } catch { /* non-critical */ }
    } catch (error: any) {
      setExamError(error.response?.data?.detail || 'Submission failed.');
      setExamMode('reviewing');
    }
  };

  const handleCloseExam = () => {
    setExamMode('idle');
    setExamTest(null);
    setExamQuestions([]);
    setExamAnswers({});
    setExamResult(null);
    setExamError(null);
  };

  // ── Local Filtering ────────────────────────────────────────

  const filteredSkills = skills.filter(s => {
    const matchesSearch = !searchTerm || 
      s.name?.toLowerCase().includes(searchTerm.toLowerCase()) || 
      s.description?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = !categoryFilter || s.faculty === categoryFilter || s.subcategory === categoryFilter;
    return matchesSearch && matchesCategory;
  });

  const filteredBundles = bundles.filter(b =>
    !searchTerm || b.name?.toLowerCase().includes(searchTerm.toLowerCase()) || 
    b.description?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredSpecs = specializations.filter(s =>
    !searchTerm || s.name?.toLowerCase().includes(searchTerm.toLowerCase()) || 
    s.description?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // ── Tab Config ─────────────────────────────────────────────

  const tabs: { key: DojoTab; label: string; icon: any; count?: number }[] = [
    { key: 'catalog', label: t('dojo.tab_explore', 'Skill Catalog'), icon: Book, count: stats?.skills },
    { key: 'bundles', label: t('dojo.tab_bundles', 'Ready Bundles'), icon: Package, count: stats?.bundles },
    { key: 'specializations', label: t('dojo.tab_specializations', 'Specializations'), icon: GraduationCap, count: stats?.specializations },
    { key: 'achieved', label: t('dojo.tab_achieved', 'Achieved'), icon: Trophy },
  ];

  // ── Render ─────────────────────────────────────────────────

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-7xl mx-auto pb-12">
      {/* ── Header ────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            {t('dojo.title', 'The Dojo')} <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">OpenClaw Hub</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">{t('dojo.subtitle', 'Discover and install specialized skills from the global OpenClaw College registry.')}</p>
        </div>
        
        <div className="flex items-center gap-3">
           <div className="hidden lg:flex items-center gap-6 px-6 border-r border-shogun-border">
              <div className="flex flex-col">
                 <span className="text-[10px] text-shogun-subdued uppercase font-bold tracking-widest leading-none">Catalog</span>
                 <span className="text-xl font-bold text-shogun-gold">{stats?.skills ?? <Loader2 className="w-4 h-4 animate-spin inline" />} <span className="text-[10px] font-normal">Skills</span></span>
              </div>
              <div className="flex flex-col">
                 <span className="text-[10px] text-shogun-subdued uppercase font-bold tracking-widest leading-none">Subcategories</span>
                 <span className="text-xl font-bold text-shogun-blue">{stats?.subcategories ?? <Loader2 className="w-4 h-4 animate-spin inline" />} <span className="text-[10px] font-normal">Fields</span></span>
              </div>
              <div className="flex flex-col">
                 <span className="text-[10px] text-shogun-subdued uppercase font-bold tracking-widest leading-none">Badges</span>
                 <span className="text-xl font-bold text-purple-400">{stats?.badges ?? <Loader2 className="w-4 h-4 animate-spin inline" />} <span className="text-[10px] font-normal">Available</span></span>
              </div>
           </div>
           <button 
             onClick={() => { fetchStats(); fetchTabData(); fetchCategories(); }}
             className="p-2.5 bg-shogun-card border border-shogun-border rounded-lg text-shogun-subdued hover:text-shogun-gold transition-colors"
           >
             <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
           </button>
        </div>
      </div>

      {/* ── Tabs ──────────────────────────────────────────── */}
      <div className="flex border-b border-shogun-border overflow-x-auto">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "px-5 py-3 text-sm font-bold uppercase tracking-widest transition-all relative flex items-center gap-2 whitespace-nowrap",
                activeTab === tab.key ? "text-shogun-gold" : "text-shogun-subdued hover:text-shogun-text"
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {tab.label}
              {tab.count !== undefined && (
                <span className={cn(
                  "text-[9px] px-1.5 py-0.5 rounded-full font-mono",
                  activeTab === tab.key ? "bg-shogun-gold/10 text-shogun-gold" : "bg-shogun-card text-shogun-subdued"
                )}>
                  {tab.count}
                </span>
              )}
              {activeTab === tab.key && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-shogun-gold shadow-[0_0_10px_rgba(212,160,23,0.5)]" />
              )}
            </button>
          );
        })}
      </div>

      {/* ── Main Content Grid ─────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8 mt-6">
        {/* ── Sidebar ─────────────────────────────────────── */}
        <div className="lg:col-span-1 space-y-6">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-shogun-subdued" />
            <input 
              type="text" 
              placeholder="Filter Dojo..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-[#050508] border border-shogun-border rounded-xl pl-10 pr-4 py-3 text-sm focus:border-shogun-gold outline-none transition-all shadow-inner"
            />
          </div>

          {/* Add URL Box */}
          <div className="shogun-card space-y-3">
            <h3 className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-2">
              <LinkIcon className="w-3 h-3" /> Import from URL
            </h3>
            <div className="flex gap-2">
              <input 
                type="text" 
                placeholder="GitHub / ClawHub URL..."
                value={addUrl}
                onChange={(e) => { setAddUrl(e.target.value); setUrlMessage(null); }}
                className="flex-1 bg-[#050508] border border-shogun-border rounded-lg px-3 py-2 text-xs focus:border-shogun-blue outline-none transition-all"
                onKeyDown={(e) => e.key === 'Enter' && handleAddUrl()}
              />
              <button 
                onClick={handleAddUrl}
                disabled={addingUrl || !addUrl.trim()}
                className="px-3 py-2 bg-shogun-blue/10 border border-shogun-blue/30 text-shogun-blue rounded-lg text-xs font-bold uppercase tracking-wider hover:bg-shogun-blue/20 transition-colors disabled:opacity-30"
              >
                {addingUrl ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
              </button>
            </div>
            {urlMessage && (
              <p className={cn(
                "text-[10px] leading-relaxed",
                urlMessage.type === 'success' ? 'text-green-400' : 'text-red-400'
              )}>
                {urlMessage.text}
              </p>
            )}
            <p className="text-[9px] text-shogun-subdued/60 italic">
              Paste a repo URL to import skills directly from source.
            </p>
          </div>

          {/* Dynamic Categories (Faculty-grouped subcategories) */}
          <div className="shogun-card space-y-3">
             <h3 className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest border-b border-shogun-border pb-2">
               All Categories
             </h3>
             <div 
               onClick={() => setCategoryFilter(null)}
               className={cn(
                 "text-[10px] px-3 py-1.5 rounded cursor-pointer transition-colors font-bold",
                 !categoryFilter ? "bg-shogun-gold/10 text-shogun-gold" : "text-shogun-subdued hover:text-shogun-gold"
               )}
             >
               All Categories
             </div>
             {categories.length > 0 ? (
               <>
                 {/* Technical Faculty */}
                 {categories.filter((c: any) => c.facultyId === 'technical').length > 0 && (
                   <div className="space-y-1">
                     <p
                       className="text-[8px] font-bold text-shogun-blue uppercase tracking-[0.2em] flex items-center gap-1.5 mt-2 px-1 cursor-pointer select-none hover:opacity-80 transition-opacity"
                       onClick={() => setCollapsedFaculties(prev => ({ ...prev, technical: !prev.technical }))}
                     >
                       <span className="w-1.5 h-1.5 rounded-full bg-shogun-blue inline-block" />
                       faculties.technical
                       {collapsedFaculties.technical ? <ChevronRight className="w-2.5 h-2.5 ml-auto" /> : <ChevronDown className="w-2.5 h-2.5 ml-auto" />}
                     </p>
                     {!collapsedFaculties.technical && categories.filter((c: any) => c.facultyId === 'technical').map((cat: any) => (
                       <div
                         key={cat.id}
                         onClick={() => setCategoryFilter(cat.id)}
                         className={cn(
                           "text-[10px] px-3 py-1 rounded cursor-pointer transition-colors truncate",
                           categoryFilter === cat.id
                             ? "bg-shogun-gold/10 text-shogun-gold font-bold"
                             : "text-shogun-subdued hover:text-shogun-text hover:bg-[#050508]"
                         )}
                       >
                         {cat.name}
                       </div>
                     ))}
                   </div>
                 )}

                 {/* Human & Wellbeing Faculty */}
                 {categories.filter((c: any) => c.facultyId === 'human_wellbeing').length > 0 && (
                   <div className="space-y-1">
                     <p
                       className="text-[8px] font-bold text-orange-400 uppercase tracking-[0.2em] flex items-center gap-1.5 mt-3 px-1 cursor-pointer select-none hover:opacity-80 transition-opacity"
                       onClick={() => setCollapsedFaculties(prev => ({ ...prev, human_wellbeing: !prev.human_wellbeing }))}
                     >
                       <span className="w-1.5 h-1.5 rounded-full bg-orange-400 inline-block" />
                       faculties.human_wellbeing
                       {collapsedFaculties.human_wellbeing ? <ChevronRight className="w-2.5 h-2.5 ml-auto" /> : <ChevronDown className="w-2.5 h-2.5 ml-auto" />}
                     </p>
                     {!collapsedFaculties.human_wellbeing && categories.filter((c: any) => c.facultyId === 'human_wellbeing').map((cat: any) => (
                       <div
                         key={cat.id}
                         onClick={() => setCategoryFilter(cat.id)}
                         className={cn(
                           "text-[10px] px-3 py-1 rounded cursor-pointer transition-colors truncate",
                           categoryFilter === cat.id
                             ? "bg-shogun-gold/10 text-shogun-gold font-bold"
                             : "text-shogun-subdued hover:text-shogun-text hover:bg-[#050508]"
                         )}
                       >
                         {cat.name}
                       </div>
                     ))}
                   </div>
                 )}

                 {/* Business & Professional Faculty */}
                 {categories.filter((c: any) => c.facultyId === 'business_professional').length > 0 && (
                   <div className="space-y-1">
                     <p
                       className="text-[8px] font-bold text-green-400 uppercase tracking-[0.2em] flex items-center gap-1.5 mt-3 px-1 cursor-pointer select-none hover:opacity-80 transition-opacity"
                       onClick={() => setCollapsedFaculties(prev => ({ ...prev, business_professional: !prev.business_professional }))}
                     >
                       <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />
                       faculties.business_professional
                       {collapsedFaculties.business_professional ? <ChevronRight className="w-2.5 h-2.5 ml-auto" /> : <ChevronDown className="w-2.5 h-2.5 ml-auto" />}
                     </p>
                     {!collapsedFaculties.business_professional && categories.filter((c: any) => c.facultyId === 'business_professional').map((cat: any) => (
                       <div
                         key={cat.id}
                         onClick={() => setCategoryFilter(cat.id)}
                         className={cn(
                           "text-[10px] px-3 py-1 rounded cursor-pointer transition-colors truncate",
                           categoryFilter === cat.id
                             ? "bg-shogun-gold/10 text-shogun-gold font-bold"
                             : "text-shogun-subdued hover:text-shogun-text hover:bg-[#050508]"
                         )}
                       >
                         {cat.name}
                       </div>
                     ))}
                   </div>
                 )}
               </>
             ) : (
               Array.from({ length: 8 }).map((_, i) => (
                 <div key={i} className="h-4 bg-shogun-bg border border-shogun-border rounded animate-pulse" />
               ))
             )}
          </div>

          {/* OpenClaw Registration Card */}
          <div className={cn(
            "shogun-card border-2 transition-all",
            registrationStatus?.registered 
              ? "bg-green-500/5 border-green-500/20" 
              : "bg-shogun-gold/5 border-shogun-gold/20"
          )}>
            {registrationStatus?.registered ? (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <BadgeCheck className="w-5 h-5 text-green-500" />
                  <h4 className="text-sm font-bold text-shogun-text">Registered</h4>
                </div>
                <p className="text-[10px] text-shogun-subdued leading-relaxed">
                  Your Shogun is enrolled at OpenClaw College as <strong className="text-shogun-text">{registrationStatus.agent_name}</strong>.
                </p>
                <code className="block text-[9px] bg-[#050508] p-2 rounded border border-shogun-border text-shogun-subdued font-mono truncate">
                  ID: {registrationStatus.openclaw_agent_id}
                </code>
                <button
                  onClick={() => setShowCredentials(!showCredentials)}
                  className="w-full py-2 text-[10px] font-bold uppercase tracking-widest border border-shogun-border rounded-lg text-shogun-subdued hover:text-shogun-blue hover:border-shogun-blue/40 transition-colors flex items-center justify-center gap-2"
                >
                  <Lock className="w-3 h-3" /> {showCredentials ? 'Hide' : 'Set API Key'}
                </button>
                {showCredentials && (
                  <div className="space-y-2 pt-1">
                    <label className="text-[9px] text-shogun-subdued uppercase tracking-widest font-bold">X-API-Key (membership key)</label>
                    <input
                      type="password"
                      value={credApiKey}
                      onChange={e => setCredApiKey(e.target.value)}
                      placeholder="paste your api key…"
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg px-3 py-2 text-xs focus:border-shogun-blue outline-none transition-all font-mono"
                    />
                    {credsMessage && (
                      <p className={cn('text-[9px]', credsMessage.type === 'success' ? 'text-green-400' : 'text-red-400')}>{credsMessage.text}</p>
                    )}
                    <button
                      onClick={handleSaveCredentials}
                      disabled={savingCreds || !credApiKey.trim()}
                      className="w-full py-2 bg-shogun-blue/10 border border-shogun-blue/30 text-shogun-blue text-[10px] font-bold uppercase tracking-widest rounded-lg hover:bg-shogun-blue/20 transition-colors disabled:opacity-30"
                    >
                      {savingCreds ? <Loader2 className="w-3 h-3 animate-spin mx-auto" /> : 'Save Key'}
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <UserPlus className="w-5 h-5 text-shogun-gold" />
                  <h4 className="text-sm font-bold text-shogun-text">Join OpenClaw College</h4>
                </div>
                <p className="text-[10px] text-shogun-subdued leading-relaxed">
                  Register your Shogun to earn badges, track specializations, and participate in the global agent community.
                </p>
                <button 
                  onClick={() => setShowRegisterModal(true)}
                  className="w-full py-2.5 bg-shogun-gold hover:bg-shogun-gold/90 text-black font-bold text-[10px] uppercase tracking-[0.2em] rounded-lg shadow-shogun transition-all flex items-center justify-center gap-2"
                >
                  <UserPlus className="w-3.5 h-3.5" /> Sign Up for OpenClaw College
                </button>
              </div>
            )}
          </div>

          {/* Certified Info */}
          <div className="shogun-card bg-shogun-blue/5 border-shogun-blue/20">
             <div className="flex items-center gap-3 mb-3">
               <Trophy className="w-5 h-5 text-shogun-gold" />
               <h4 className="text-sm font-bold text-shogun-text">OpenClaw Certified</h4>
             </div>
             <p className="text-[10px] text-shogun-subdued leading-relaxed">
               All skills in the Dojo have undergone automated safety auditing by the OpenClaw College board. Verified skills display the "Zen" mark of stability.
             </p>
          </div>
        </div>

        {/* ── Content Area ────────────────────────────────── */}
        <div className="lg:col-span-3">
           {loading ? (
             <div className="p-20 text-center shogun-card bg-[#050508]/20 flex flex-col items-center gap-4 border-dashed">
                <div className="relative">
                   <RefreshCw className="w-10 h-10 animate-spin text-shogun-gold" />
                   <Sparkles className="absolute -top-1 -right-1 w-4 h-4 text-shogun-blue animate-pulse" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-shogun-subdued">Syncing with OpenClaw College...</span>
             </div>
           ) : (
             <>
               {/* ── Skills Tab ──────────────────────────── */}
               {activeTab === 'catalog' && (
                 <div className="space-y-4">
                   {filteredSkills.length === 0 ? (
                     <div className="p-12 text-center shogun-card border-dashed">
                       <Search className="w-8 h-8 text-shogun-subdued mx-auto mb-3 opacity-30" />
                       <p className="text-sm text-shogun-subdued">No skills match your search criteria.</p>
                     </div>
                   ) : (
                     <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                       {filteredSkills.map((skill) => (
                         <div 
                           key={skill.id} 
                           onClick={() => setSelectedSkill(skill)}
                           className="shogun-card group hover:border-shogun-gold/50 cursor-pointer transition-all flex flex-col"
                         >
                           <div className="flex justify-between items-start mb-4">
                              <div className="w-12 h-12 bg-[#050508] border border-shogun-border rounded-xl flex items-center justify-center text-shogun-gold group-hover:bg-shogun-gold/10 transition-colors">
                                 <Book className="w-6 h-6" />
                              </div>
                              <div className="flex flex-col items-end">
                                 <code className="text-[9px] bg-shogun-card px-1.5 py-0.5 rounded border border-shogun-border text-shogun-subdued">v{skill.version}</code>
                                 <span className={cn(
                                   "text-[8px] font-bold uppercase tracking-widest mt-1",
                                   skill.risk_tier === 'shrine' ? 'text-shogun-gold' : skill.risk_tier === 'tactical' ? 'text-shogun-blue' : skill.risk_tier === 'elevated' ? 'text-orange-400' : 'text-green-400'
                                 )}>{skill.risk_tier}</span>
                              </div>
                           </div>
                           
                           <h4 className="text-lg font-bold text-shogun-text group-hover:text-shogun-gold transition-colors">{skill.name}</h4>
                           <p className="text-xs text-shogun-subdued mt-2 line-clamp-3 leading-relaxed flex-1">
                             {skill.description}
                           </p>
                           
                           <div className="mt-6 pt-4 border-t border-shogun-border flex items-center justify-between">
                              <div className="flex gap-2">
                                 {skill.permissions?.network && <Globe className="w-3 h-3 text-shogun-blue" />}
                                 {skill.permissions?.shell && <Zap className="w-3 h-3 text-red-500" />}
                                 {skill.permissions?.filesystem_write && <ShieldCheck className="w-3 h-3 text-green-500" />}
                                 {skill.permissions?.filesystem_read && <Book className="w-3 h-3 text-purple-400" />}
                                 {skill.permissions?.credentials && <Lock className="w-3 h-3 text-orange-400" />}
                              </div>
                              <div className="flex items-center gap-1 text-[10px] font-mono text-shogun-subdued group-hover:text-shogun-gold transition-colors">
                                 <Plus className="w-3 h-3" /> Install
                              </div>
                           </div>
                         </div>
                       ))}
                     </div>
                   )}
                 </div>
               )}

               {/* ── Bundles Tab ──────────────────────────── */}
               {activeTab === 'bundles' && (
                 <div className="space-y-4">
                   {filteredBundles.length === 0 ? (
                     <div className="p-12 text-center shogun-card border-dashed">
                       <Package className="w-8 h-8 text-shogun-subdued mx-auto mb-3 opacity-30" />
                       <p className="text-sm text-shogun-subdued">No bundles available.</p>
                     </div>
                   ) : (
                     <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                       {filteredBundles.map((bundle) => (
                         <div key={bundle.id} className={cn("shogun-card group cursor-pointer transition-all", expandedBundle === bundle.id ? "border-shogun-blue/50" : "hover:border-shogun-blue/50")} onClick={() => setExpandedBundle(expandedBundle === bundle.id ? null : bundle.id)}>
                           <div className="flex items-start gap-4 mb-3">
                             <div className="w-12 h-12 bg-shogun-blue/10 border border-shogun-blue/20 rounded-xl flex items-center justify-center flex-shrink-0 text-xl">
                               {bundle.icon || '📦'}
                             </div>
                             <div className="flex-1 min-w-0">
                               <div className="flex items-center gap-3">
                                 <h4 className="text-lg font-bold text-shogun-text group-hover:text-shogun-blue transition-colors">{bundle.name}</h4>
                                 {bundle.currentVersion?.riskTier && (
                                   <span className={cn("text-[9px] px-2 py-0.5 rounded font-bold uppercase tracking-widest",
                                     bundle.currentVersion.riskTier === 'low' ? "bg-green-500/10 text-green-400" :
                                     bundle.currentVersion.riskTier === 'medium' ? "bg-yellow-500/10 text-yellow-400" :
                                     "bg-red-500/10 text-red-400"
                                   )}>
                                     {bundle.currentVersion.riskTier}
                                   </span>
                                 )}
                               </div>
                               <p className="text-[10px] text-shogun-subdued uppercase tracking-widest font-bold mt-0.5">
                                 {bundle.skillIds?.length || 0} skills · {bundle.facultyId || 'General'}
                                 {bundle.currentVersion?.versionLabel && <> · v{bundle.currentVersion.versionLabel}</>}
                               </p>
                             </div>
                             <ChevronRight className={cn("w-4 h-4 text-shogun-subdued transition-transform mt-1", expandedBundle === bundle.id && "rotate-90")} />
                           </div>
                           <p className="text-xs text-shogun-subdued leading-relaxed line-clamp-3">
                             {bundle.shortDescription || bundle.description}
                           </p>
                           {/* ── Expanded Bundle Details ── */}
                           {expandedBundle === bundle.id && (
                             <div className="mt-4 pt-4 border-t border-shogun-border space-y-3" onClick={(e) => e.stopPropagation()}>
                               {bundle.currentVersion?.skills && bundle.currentVersion.skills.length > 0 ? (
                                 <div className="space-y-2">
                                   <div className="flex items-center gap-2">
                                     <Zap className="w-3.5 h-3.5 text-shogun-blue" />
                                     <span className="text-[10px] font-bold text-shogun-text uppercase tracking-widest">Included Skills</span>
                                     <span className="text-[9px] px-1.5 py-0.5 bg-shogun-card border border-shogun-border rounded text-shogun-subdued font-mono">{bundle.currentVersion.skills.length}</span>
                                   </div>
                                   <div className="space-y-1 pl-5">
                                     {bundle.currentVersion.skills.map((skill: any) => (
                                       <div key={skill.id} className="flex items-center gap-2">
                                         <span className="text-[8px] px-2 py-0.5 bg-[#050508] border border-shogun-border rounded font-mono text-shogun-subdued">{skill.id}</span>
                                         <span className="text-[10px] text-shogun-text">{skill.name}</span>
                                       </div>
                                     ))}
                                   </div>
                                 </div>
                               ) : bundle.skillIds && bundle.skillIds.length > 0 ? (
                                 <div className="space-y-2">
                                   <div className="flex items-center gap-2">
                                     <Zap className="w-3.5 h-3.5 text-shogun-blue" />
                                     <span className="text-[10px] font-bold text-shogun-text uppercase tracking-widest">Included Skills</span>
                                     <span className="text-[9px] px-1.5 py-0.5 bg-shogun-card border border-shogun-border rounded text-shogun-subdued font-mono">{bundle.skillIds.length}</span>
                                   </div>
                                   <div className="flex flex-wrap gap-1.5 pl-5">
                                     {bundle.skillIds.map((id: string) => (
                                       <span key={id} className="text-[8px] px-2 py-0.5 bg-[#050508] border border-shogun-border rounded font-mono text-shogun-subdued">{id}</span>
                                     ))}
                                   </div>
                                 </div>
                               ) : null}
                               <div className="mt-3 pt-3 border-t border-shogun-border">
                                 <div className="flex items-center gap-1 text-[10px] font-mono text-shogun-blue cursor-pointer hover:text-shogun-blue/80 transition-colors">
                                   <Plus className="w-3 h-3" /> Install Bundle
                                 </div>
                               </div>
                             </div>
                           )}
                           {expandedBundle !== bundle.id && (
                             <div className="mt-4 pt-4 border-t border-shogun-border flex items-center justify-between">
                               <div className="flex items-center gap-2">
                                 <Layers className="w-3 h-3 text-shogun-blue" />
                                 <span className="text-[10px] font-mono text-shogun-subdued">{bundle.skillIds?.length || 0} skills included</span>
                               </div>
                               <div className="flex items-center gap-1 text-[10px] font-mono text-shogun-subdued group-hover:text-shogun-blue transition-colors">
                                 <Plus className="w-3 h-3" /> Install Bundle
                               </div>
                             </div>
                           )}
                         </div>
                       ))}
                     </div>
                   )}
                 </div>
               )}

               {/* ── Specializations Tab ──────────────────── */}
               {activeTab === 'specializations' && (
                 <div className="space-y-4">
                   {filteredSpecs.length === 0 ? (
                     <div className="p-12 text-center shogun-card border-dashed">
                       <GraduationCap className="w-8 h-8 text-shogun-subdued mx-auto mb-3 opacity-30" />
                       <p className="text-sm text-shogun-subdued">No specializations available.</p>
                     </div>
                   ) : (
                     <div className="grid grid-cols-1 gap-6">
                       {filteredSpecs.map((spec) => (
                         <div key={spec.id} className={cn("shogun-card group cursor-pointer transition-all", expandedSpec === spec.id ? "border-purple-400/50" : "hover:border-purple-400/50")} onClick={() => setExpandedSpec(expandedSpec === spec.id ? null : spec.id)}>
                           <div className="flex items-start gap-4">
                             <div className="w-14 h-14 bg-purple-500/10 border border-purple-500/20 rounded-xl flex items-center justify-center flex-shrink-0 text-2xl">
                               {spec.icon || '🎓'}
                             </div>
                             <div className="flex-1 min-w-0">
                               <div className="flex items-center gap-3 mb-2">
                                 <h4 className="text-lg font-bold text-shogun-text group-hover:text-purple-400 transition-colors">{spec.name}</h4>
                                 <span className="text-[9px] px-2 py-0.5 bg-purple-500/10 text-purple-400 rounded font-bold uppercase tracking-widest">
                                   {spec.degreeType || 'Specialization'}
                                 </span>
                               </div>
                               <p className="text-xs text-shogun-subdued leading-relaxed line-clamp-2">
                                 {spec.title || spec.description}
                               </p>
                               <div className="flex items-center gap-4 mt-3">
                                 <span className="text-[10px] text-shogun-subdued uppercase font-bold tracking-widest">
                                   Faculty: {spec.facultyId || spec.faculty || 'General'}
                                 </span>
                                 <span className="text-[10px] text-shogun-subdued/60">•</span>
                                 <span className="text-[10px] text-shogun-subdued uppercase font-bold tracking-widest">
                                   Category: {spec.categoryId || '—'}
                                 </span>
                                 <ChevronRight className={cn("w-3 h-3 text-shogun-subdued transition-transform ml-auto", expandedSpec === spec.id && "rotate-90")} />
                               </div>
                             </div>
                           </div>
                           {/* ── Expanded Requirements ── */}
                           {expandedSpec === spec.id && (
                             <div className="mt-4 pt-4 border-t border-shogun-border space-y-4" onClick={(e) => e.stopPropagation()}>
                               {spec.requirements?.map((req: any, idx: number) => (
                                 <div key={idx} className="space-y-2">
                                   <div className="flex items-center gap-2">
                                     {req.type === 'bundle_count' ? <Package className="w-3.5 h-3.5 text-shogun-gold" /> : <Zap className="w-3.5 h-3.5 text-shogun-blue" />}
                                     <span className="text-[10px] font-bold text-shogun-text uppercase tracking-widest">{req.label}</span>
                                     <span className="text-[9px] px-1.5 py-0.5 bg-shogun-card border border-shogun-border rounded text-shogun-subdued font-mono">{req.count}</span>
                                   </div>
                                   <div className="flex flex-wrap gap-1.5 pl-5">
                                     {(req.bundleIds || req.skillIds || []).map((id: string) => (
                                       <span key={id} className="text-[8px] px-2 py-0.5 bg-[#050508] border border-shogun-border rounded font-mono text-shogun-subdued truncate max-w-[160px]">{id}</span>
                                     ))}
                                   </div>
                                 </div>
                               ))}
                               {spec.badgeId && (
                                 <div className="flex items-center gap-2 pt-2">
                                   <Award className="w-3.5 h-3.5 text-purple-400" />
                                   <span className="text-[10px] font-bold text-shogun-text uppercase tracking-widest">Badge Reward</span>
                                   <span className="text-[9px] px-2 py-0.5 bg-purple-500/10 text-purple-400 rounded font-mono">{spec.badgeId}</span>
                                 </div>
                               )}
                             </div>
                           )}
                         </div>
                       ))}
                     </div>
                   )}
                 </div>
               )}

               {/* ── Achieved Tab ─────────────────────────── */}
               {activeTab === 'achieved' && (
                 <div className="space-y-8">
                   {!achievements?.registered ? (
                     <div className="p-12 text-center shogun-card border-dashed border-2 border-shogun-gold/20">
                       <UserPlus className="w-10 h-10 text-shogun-gold mx-auto mb-4 opacity-50" />
                       <h3 className="text-lg font-bold text-shogun-text mb-2">Not Registered Yet</h3>
                       <p className="text-sm text-shogun-subdued max-w-md mx-auto mb-6">
                         Register your Shogun with OpenClaw College to start earning badges and tracking specializations.
                       </p>
                       <button 
                         onClick={() => setShowRegisterModal(true)}
                         className="px-6 py-3 bg-shogun-gold hover:bg-shogun-gold/90 text-black font-bold text-xs uppercase tracking-[0.2em] rounded-xl shadow-shogun transition-all inline-flex items-center gap-2"
                       >
                         <UserPlus className="w-4 h-4" /> Sign Up Now
                       </button>
                     </div>
                   ) : (
                     <>
                       {/* Achievement Summary */}
                       <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                         <div className="shogun-card text-center">
                           <Award className="w-8 h-8 text-shogun-gold mx-auto mb-2" />
                           <p className="text-2xl font-bold text-shogun-gold">{achievements.badges?.length || 0}</p>
                           <p className="text-[10px] text-shogun-subdued uppercase tracking-widest font-bold">Badges Earned</p>
                         </div>
                         <div className="shogun-card text-center">
                           <GraduationCap className="w-8 h-8 text-purple-400 mx-auto mb-2" />
                           <p className="text-2xl font-bold text-purple-400">{achievements.specializations_earned?.length || 0}</p>
                           <p className="text-[10px] text-shogun-subdued uppercase tracking-widest font-bold">Specializations</p>
                         </div>
                         <div className="shogun-card text-center">
                           <Star className="w-8 h-8 text-shogun-blue mx-auto mb-2" />
                           <p className="text-2xl font-bold text-shogun-blue">{achievements.skills_completed || 0}</p>
                           <p className="text-[10px] text-shogun-subdued uppercase tracking-widest font-bold">Skills Installed</p>
                         </div>
                       </div>

                       {/* Earned Badges */}
                       <div className="space-y-4">
                         <h3 className="text-[10px] font-bold text-shogun-subdued uppercase tracking-[0.2em] flex items-center gap-2">
                           <Award className="w-3.5 h-3.5 text-shogun-gold" /> Earned Badges
                         </h3>
                         {achievements.badges?.length > 0 ? (
                           <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                             {achievements.badges.map((badge: any) => (
                               <div key={badge.id || badge.name} className="shogun-card text-center hover:border-shogun-gold/50 transition-all group">
                                 <div className="w-12 h-12 bg-shogun-gold/10 rounded-full flex items-center justify-center mx-auto mb-3 group-hover:bg-shogun-gold/20 transition-colors">
                                   <Award className="w-6 h-6 text-shogun-gold" />
                                 </div>
                                 <p className="text-xs font-bold text-shogun-text">{badge.name}</p>
                                 <p className="text-[9px] text-shogun-subdued mt-1 line-clamp-2">{badge.description}</p>
                               </div>
                             ))}
                           </div>
                         ) : (
                           <div className="p-6 text-center shogun-card border-dashed">
                             <p className="text-xs text-shogun-subdued">No badges earned yet. Complete skills and specializations to earn badges.</p>
                           </div>
                         )}
                       </div>

                        {/* Certification Transcript */}
                        {transcript?.test_results?.length > 0 && (
                          <div className="space-y-4">
                            <h3 className="text-[10px] font-bold text-shogun-subdued uppercase tracking-[0.2em] flex items-center gap-2">
                              <GraduationCap className="w-3.5 h-3.5 text-shogun-blue" /> Certification Transcript
                            </h3>
                            <div className="space-y-2">
                              {transcript.test_results.map((tr: any, i: number) => (
                                <div key={tr.id || i} className="flex items-center justify-between p-3 bg-[#050508] border border-shogun-border rounded-xl">
                                  <div>
                                    <p className="text-xs font-bold text-shogun-text">{tr.skillName || tr.testId || `Test ${i + 1}`}</p>
                                    <p className="text-[9px] text-shogun-subdued mt-0.5">Score: {tr.score}% · {tr.verificationStatus}</p>
                                  </div>
                                  {tr.verificationStatus === 'approved' ? (
                                    <BadgeCheck className="w-5 h-5 text-green-500" />
                                  ) : (
                                    <AlertCircle className="w-5 h-5 text-orange-400" />
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                     </>
                   )}

                   {/* All Available Badges (global catalog) */}
                   <div className="space-y-4">
                     <h3 className="text-[10px] font-bold text-shogun-subdued uppercase tracking-[0.2em] flex items-center gap-2">
                       <Trophy className="w-3.5 h-3.5 text-purple-400" /> All Available Badges
                     </h3>
                     {badges.length > 0 ? (
                       <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                         {badges.map((badge: any) => {
                           const earned = achievements?.badges?.some((b: any) => b.id === badge.id);
                           return (
                             <div key={badge.id || badge.name} className={cn(
                               "shogun-card text-center transition-all",
                               earned ? "border-shogun-gold/30 bg-shogun-gold/5" : "opacity-60 hover:opacity-100"
                             )}>
                               <div className={cn(
                                 "w-10 h-10 rounded-full flex items-center justify-center mx-auto mb-2",
                                 earned ? "bg-shogun-gold/20" : "bg-shogun-card"
                               )}>
                                 {earned ? (
                                   <CheckCircle2 className="w-5 h-5 text-shogun-gold" />
                                 ) : (
                                   <Lock className="w-4 h-4 text-shogun-subdued" />
                                 )}
                               </div>
                               <p className="text-[10px] font-bold text-shogun-text">{badge.name}</p>
                               {badge.description && (
                                 <p className="text-[8px] text-shogun-subdued mt-1 line-clamp-2">{badge.description}</p>
                               )}
                             </div>
                           );
                         })}
                       </div>
                     ) : (
                       <div className="p-6 text-center shogun-card border-dashed">
                         <Trophy className="w-6 h-6 text-shogun-subdued mx-auto mb-2 opacity-30" />
                         <p className="text-xs text-shogun-subdued">Badge catalog loading failed. Check connection to OpenClaw College.</p>
                       </div>
                     )}
                   </div>
                 </div>
               )}
             </>
           )}
        </div>
      </div>

      {/* ── Skill Detail Modal ────────────────────────────── */}
      {selectedSkill && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-300">
           <div className="bg-shogun-bg border border-shogun-border w-full max-w-3xl rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300 flex flex-col max-h-[90vh]">
              {/* Modal Header */}
              <div className="p-6 border-b border-shogun-border bg-shogun-card flex justify-between items-center flex-shrink-0">
                 <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-[#050508] border border-shogun-border flex items-center justify-center text-shogun-gold">
                       <Zap className="w-5 h-5" />
                    </div>
                    <div>
                       <h3 className="text-lg font-bold text-shogun-text">{selectedSkill.name}</h3>
                       <p className="text-[10px] text-shogun-subdued uppercase tracking-widest font-bold">Faculty: {selectedSkill.faculty || 'General'}</p>
                    </div>
                 </div>
                 <button onClick={() => { setSelectedSkill(null); handleCloseExam(); }} className="p-2 hover:bg-[#0a0e1a] rounded-lg transition-colors">
                    <X className="w-5 h-5 text-shogun-subdued" />
                 </button>
              </div>

              {/* Modal Body — switches between Info view and Exam view */}
              {examMode === 'idle' && (
                <div className="grid grid-cols-1 md:grid-cols-2 overflow-y-auto">
                   <div className="p-8 space-y-6 border-r border-shogun-border">
                      <div className="space-y-3">
                         <h4 className="text-[10px] font-bold text-shogun-blue uppercase tracking-widest">Description</h4>
                         <p className="text-sm text-shogun-text leading-relaxed">{selectedSkill.description}</p>
                      </div>
                      <div className="space-y-3">
                         <h4 className="text-[10px] font-bold text-shogun-blue uppercase tracking-widest">Capabilities</h4>
                         <div className="flex flex-wrap gap-2">
                            {(selectedSkill.capabilities || []).length > 0 ? (
                              selectedSkill.capabilities.map((cap: string) => (
                                <span key={cap} className="text-[10px] px-2 py-1 bg-shogun-card border border-shogun-border rounded text-shogun-subdued">{cap}</span>
                              ))
                            ) : (
                              <span className="text-[10px] text-shogun-subdued italic">No capabilities declared</span>
                            )}
                         </div>
                      </div>
                      <div className="space-y-2">
                        <h4 className="text-[10px] font-bold text-shogun-blue uppercase tracking-widest">Metadata</h4>
                        <div className="grid grid-cols-2 gap-2">
                          <div className="p-2 bg-[#050508] rounded border border-shogun-border">
                            <span className="text-[9px] text-shogun-subdued block">Version</span>
                            <span className="text-xs font-mono text-shogun-text">{selectedSkill.version}</span>
                          </div>
                          <div className="p-2 bg-[#050508] rounded border border-shogun-border">
                            <span className="text-[9px] text-shogun-subdued block">Risk Tier</span>
                            <span className={cn(
                              "text-xs font-bold uppercase",
                              selectedSkill.risk_tier === 'shrine' ? 'text-shogun-gold' : selectedSkill.risk_tier === 'elevated' ? 'text-orange-400' : 'text-green-400'
                            )}>{selectedSkill.risk_tier}</span>
                          </div>
                        </div>
                      </div>
                   </div>
                   <div className="p-8 space-y-6 bg-[#050508]/30">
                      <div className="space-y-4">
                         <h4 className="text-[10px] font-bold text-shogun-gold uppercase tracking-widest flex items-center gap-2">
                            <Lock className="w-3 h-3" /> Permission Audit
                         </h4>
                         <div className="space-y-2">
                            {Object.entries(selectedSkill.permissions || {}).map(([key, val]: [string, any]) => (
                               <div key={key} className="flex items-center justify-between p-3 bg-shogun-bg border border-shogun-border rounded-lg">
                                  <span className="text-xs text-shogun-text font-bold capitalize">{key.replace(/_/g, ' ')}</span>
                                  {val ? <CheckCircle2 className="w-4 h-4 text-green-500" /> : <XCircle className="w-4 h-4 text-shogun-subdued" />}
                               </div>
                            ))}
                         </div>
                      </div>
                      <div className="space-y-3 pt-2">
                        <button
                          onClick={() => handleStartExam(selectedSkill.id)}
                          className="w-full py-4 bg-shogun-gold hover:bg-shogun-gold/90 text-black font-bold text-xs uppercase tracking-[0.2em] rounded-xl shadow-shogun transition-all flex items-center justify-center gap-3"
                        >
                          <GraduationCap className="w-5 h-5" /> {t('dojo.take_exam', 'Take Certification Exam')}
                        </button>
                        <button className="w-full py-3 bg-shogun-card border border-shogun-border text-shogun-subdued hover:text-shogun-text font-bold text-xs uppercase tracking-[0.2em] rounded-xl transition-all flex items-center justify-center gap-3">
                          <Plus className="w-5 h-5" /> Install to Shogun Prime
                        </button>
                        <p className="text-[9px] text-shogun-subdued text-center italic">
                          Take the 30–50 question exam to get instantly certified by OpenClaw College.
                        </p>
                      </div>
                   </div>
                </div>
              )}

              {/* ── Exam: Loading ── */}
              {examMode === 'loading' && (
                <div className="flex-1 flex flex-col items-center justify-center p-20 gap-6">
                  <div className="relative">
                    <RefreshCw className="w-12 h-12 animate-spin text-shogun-gold" />
                    <Sparkles className="absolute -top-1 -right-1 w-4 h-4 text-shogun-blue animate-pulse" />
                  </div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-shogun-subdued">Loading exam questions from OpenClaw College...</p>
                </div>
              )}

              {/* ── Exam: MCQ Reviewing ── */}
              {examMode === 'reviewing' && (
                <div className="flex flex-col flex-1 overflow-hidden">
                  <div className="p-4 border-b border-shogun-border bg-shogun-card flex items-center justify-between flex-shrink-0">
                    <div className="flex items-center gap-3">
                      <GraduationCap className="w-4 h-4 text-shogun-gold" />
                      <span className="text-xs font-bold text-shogun-text uppercase tracking-widest">Certification Exam</span>
                      <span className="text-[9px] px-2 py-0.5 bg-shogun-gold/10 text-shogun-gold rounded font-mono">
                        {Object.keys(examAnswers).length}/{examQuestions.length} answered
                      </span>
                    </div>
                    <span className="text-[10px] text-shogun-subdued">Pass threshold: {examTest?.passThreshold ?? '—'}%</span>
                  </div>
                  <div className="flex-1 overflow-y-auto p-6 space-y-6">
                    {examError && (
                      <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-xs text-red-400">{examError}</div>
                    )}
                    {examQuestions.map((q: any, idx: number) => (
                      <div key={q.id || idx} className="space-y-3">
                        <p className="text-sm text-shogun-text font-medium leading-relaxed">
                          <span className="text-[10px] text-shogun-subdued font-mono mr-2">{idx + 1}.</span>{q.text}
                        </p>
                        <div className="grid grid-cols-1 gap-2 pl-4">
                          {(q.options || []).map((opt: any, oIdx: number) => {
                            const optValue = typeof opt === 'string' ? opt : (opt.text || opt.value || String(oIdx));
                            const optKey = typeof opt === 'string' ? opt : (opt.id || String(oIdx));
                            const isSelected = examAnswers[q.id || idx] === optKey;
                            return (
                              <button
                                key={optKey}
                                onClick={() => setExamAnswers(prev => ({ ...prev, [q.id || idx]: optKey }))}
                                className={cn(
                                  "text-left text-xs px-4 py-3 rounded-lg border transition-all",
                                  isSelected
                                    ? "bg-shogun-gold/10 border-shogun-gold text-shogun-gold font-bold"
                                    : "bg-[#050508] border-shogun-border text-shogun-subdued hover:border-shogun-text hover:text-shogun-text"
                                )}
                              >
                                <span className="font-mono text-[10px] mr-2 opacity-60">{String.fromCharCode(65 + oIdx)}.</span>
                                {optValue}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="p-4 border-t border-shogun-border flex items-center gap-3 flex-shrink-0">
                    <button onClick={handleCloseExam} className="flex-1 py-3 bg-shogun-card border border-shogun-border text-shogun-subdued text-xs font-bold uppercase tracking-widest rounded-xl hover:border-shogun-text transition-colors">
                      Cancel
                    </button>
                    <button
                      onClick={handleSubmitExam}
                      disabled={Object.keys(examAnswers).length === 0}
                      className="flex-1 py-3 bg-shogun-gold hover:bg-shogun-gold/90 text-black font-bold text-xs uppercase tracking-[0.2em] rounded-xl shadow-shogun transition-all disabled:opacity-40 flex items-center justify-center gap-2"
                    >
                      <CheckCircle2 className="w-4 h-4" /> Submit Exam
                    </button>
                  </div>
                </div>
              )}

              {/* ── Exam: Submitting ── */}
              {examMode === 'submitting' && (
                <div className="flex-1 flex flex-col items-center justify-center p-20 gap-6">
                  <Loader2 className="w-12 h-12 animate-spin text-shogun-gold" />
                  <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-shogun-subdued">Submitting results to OpenClaw College...</p>
                </div>
              )}

              {/* ── Exam: Result ── */}
              {examMode === 'result' && examResult && (
                <div className="flex-1 flex flex-col items-center justify-center p-12 gap-8">
                  <div className={cn(
                    "w-24 h-24 rounded-full flex items-center justify-center border-4",
                    examResult.verificationStatus === 'approved'
                      ? "bg-green-500/10 border-green-500 shadow-[0_0_40px_rgba(34,197,94,0.3)]"
                      : "bg-orange-500/10 border-orange-500"
                  )}>
                    {examResult.verificationStatus === 'approved' ? (
                      <BadgeCheck className="w-12 h-12 text-green-400" />
                    ) : (
                      <AlertCircle className="w-12 h-12 text-orange-400" />
                    )}
                  </div>
                  <div className="text-center space-y-3">
                    <h3 className={cn(
                      "text-2xl font-bold",
                      examResult.verificationStatus === 'approved' ? 'text-green-400' : 'text-orange-400'
                    )}>
                      {examResult.verificationStatus === 'approved' ? t('dojo.passed', 'Certified!') : t('dojo.failed', 'Not Passed')}
                    </h3>
                    <p className="text-shogun-subdued text-sm">
                      {examResult.verificationStatus === 'approved'
                        ? `Your score of ${examResult.score}% meets the pass threshold. Certification recorded on your transcript.`
                        : `Your score of ${examResult.score}% was below the required threshold. Study the material and try again.`
                      }
                    </p>
                    {examResult.verificationStatus === 'approved' && (
                      <div className="flex items-center justify-center gap-2 mt-2">
                        <Sparkles className="w-4 h-4 text-shogun-gold animate-pulse" />
                        <span className="text-[10px] text-shogun-gold font-bold uppercase tracking-widest">OpenClaw Certified · {selectedSkill?.name}</span>
                        <Sparkles className="w-4 h-4 text-shogun-gold animate-pulse" />
                      </div>
                    )}
                  </div>
                  <div className="flex gap-3 w-full max-w-sm">
                    <button onClick={handleCloseExam} className="flex-1 py-3 bg-shogun-card border border-shogun-border text-shogun-subdued text-xs font-bold uppercase tracking-widest rounded-xl hover:border-shogun-text transition-colors">
                      Close
                    </button>
                    {examResult.verificationStatus !== 'approved' && (
                      <button onClick={() => handleStartExam(selectedSkill?.id)} className="flex-1 py-3 bg-shogun-gold hover:bg-shogun-gold/90 text-black font-bold text-xs uppercase tracking-[0.2em] rounded-xl shadow-shogun transition-all">
                        Retry Exam
                      </button>
                    )}
                  </div>
                </div>
              )}
           </div>
        </div>
      )}

      {/* ── Registration Modal ────────────────────────────── */}
      {showRegisterModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-300">
          <div className="bg-shogun-bg border border-shogun-border w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300">
            <div className="p-6 border-b border-shogun-border bg-shogun-card flex justify-between items-center">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-shogun-gold/10 border border-shogun-gold/20 flex items-center justify-center">
                  <GraduationCap className="w-5 h-5 text-shogun-gold" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-shogun-text">Sign Up for OpenClaw College</h3>
                  <p className="text-[10px] text-shogun-subdued uppercase tracking-widest font-bold">Agent Registration</p>
                </div>
              </div>
              <button onClick={() => setShowRegisterModal(false)} className="p-2 hover:bg-[#0a0e1a] rounded-lg transition-colors">
                <X className="w-5 h-5 text-shogun-subdued" />
              </button>
            </div>

            <div className="p-8 space-y-6">
              <div className="space-y-2">
                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Agent Display Name</label>
                <input 
                  type="text"
                  value={registerName}
                  onChange={(e) => setRegisterName(e.target.value)}
                  placeholder="My Shogun"
                  className="w-full bg-[#050508] border border-shogun-border rounded-xl px-4 py-3 text-sm focus:border-shogun-gold outline-none transition-all"
                  autoFocus
                />
                <p className="text-[9px] text-shogun-subdued italic">
                  This name will appear in the global OpenClaw Agent Registry.
                </p>
              </div>

              <div className="p-4 bg-shogun-blue/5 border border-shogun-blue/20 rounded-xl">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-4 h-4 text-shogun-blue flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-[10px] text-shogun-text font-bold mb-1">What happens when you register?</p>
                    <ul className="text-[9px] text-shogun-subdued space-y-1">
                      <li>• Your Shogun gets a unique ID on the OpenClaw College platform</li>
                      <li>• You can earn badges and track specialization progress</li>
                      <li>• You can submit skill feedback and suggest new skills</li>
                      <li>• Registration is free and requires no API key</li>
                    </ul>
                  </div>
                </div>
              </div>

              <div className="flex gap-3">
                <button 
                  onClick={() => setShowRegisterModal(false)}
                  className="flex-1 py-3 bg-shogun-card border border-shogun-border text-shogun-subdued font-bold text-xs uppercase tracking-widest rounded-xl hover:border-shogun-text transition-colors"
                >
                  Cancel
                </button>
                <button 
                  onClick={handleRegister}
                  disabled={registering || !registerName.trim()}
                  className="flex-1 py-3 bg-shogun-gold hover:bg-shogun-gold/90 text-black font-bold text-xs uppercase tracking-[0.2em] rounded-xl shadow-shogun transition-all flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  {registering ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Registering...</>
                  ) : (
                    <><UserPlus className="w-4 h-4" /> Register</>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const XCircle = ({ className, ...props }: any) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    {...props}
  >
    <circle cx="12" cy="12" r="10" />
    <path d="m15 9-6 6" />
    <path d="m9 9 6 6" />
  </svg>
);
