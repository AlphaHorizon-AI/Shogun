import { useState, useEffect, useCallback } from 'react';
import {
  Cpu,
  Activity,
  FlaskConical,
  GitBranch,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCcw,
  Ban,
  RefreshCw,
  Plus,
  BarChart3,
  ChevronRight,
  Sparkles,
  Layers,
  Check,
  X,
  Loader2,
} from 'lucide-react';
import axios from 'axios';
import { cn } from '../../lib/utils';
import { useTranslation } from '../../i18n';

type SubTab = 'overview' | 'lab' | 'skills' | 'regression' | 'benchmarks';

interface LocalSkill {
  id: string;
  name: string;
  slug: string;
  status: string;
  lifecycle_state: string;
  active_version_id?: string | null;
  version?: string;
  is_builtin?: boolean;
  risk_tier?: string;
  active_version?: {
    id: string;
    version_number: number;
    status: string;
    quarantine_status?: string | null;
    quarantine_reason?: string | null;
    validation_score?: number | null;
  } | null;
  version_count?: number;
}

interface SkillVersionItem {
  id: string;
  version_number: number;
  status: string;
  content_hash: string;
  created_at: string | null;
  created_by?: string | null;
  validation_score?: number | null;
  scope?: string;
  quarantine_status?: string | null;
  quarantine_reason?: string | null;
  activated_at?: string | null;
}

interface LabRun {
  id: string;
  skill_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'unavailable';
  optimizer_model: string;
  execution_mode: string;
  current_iteration: number;
  max_iterations: number;
  total_llm_calls: number;
  max_llm_calls: number;
  total_tool_calls: number;
  max_tool_calls: number;
  total_cost_eur: number;
  max_cost_eur: number;
  best_score: number | null;
  started_at: string | null;
  completed_at: string | null;
  result_json?: any;
}

interface RegressionSuite {
  id: string;
  skill_id: string;
  name: string;
  description?: string | null;
  case_count: number;
  last_pass_rate: number | null;
  last_run_at: string | null;
  status: string;
  minimum_pass_rate?: number;
}

export interface RegressionCase {
  id: string;
  case_id: string;
  name: string;
  description?: string | null;
  input_json: any;
  expected_output_json: any;
  evaluation_criteria_json: any;
  tags: string[];
}

interface BenchmarkRun {
  id: string;
  skill_id: string;
  regression_suite_id: string;
  status: string;
  model_ids_json: string[];
  summary_json?: any;
  started_at: string | null;
  completed_at: string | null;
  results?: BenchmarkResultItem[];
}

interface BenchmarkResultItem {
  model_id: string;
  success_rate: number;
  policy_compliance: number;
  avg_tool_calls: number;
  avg_latency_seconds: number;
  avg_cost_eur: number;
  total_cases: number;
  passed_cases: number;
}

export function SkillOptTab() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<SubTab>('overview');
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);

  // Core Data
  const [skills, setSkills] = useState<LocalSkill[]>([]);
  const [selectedSkillId, setSelectedSkillId] = useState<string | null>(null);
  const [selectedSkillVersions, setSelectedSkillVersions] = useState<SkillVersionItem[]>([]);
  const [skillStaleness, setSkillStaleness] = useState<{ has_stale_tools: boolean; warnings: any[] } | null>(null);

  // Lab Data
  const [labRuns, setLabRuns] = useState<LabRun[]>([]);
  const [selectedLabRun, setSelectedLabRun] = useState<LabRun | null>(null);
  const [showNewLabModal, setShowNewLabModal] = useState(false);
  const [labForm, setLabForm] = useState({
    skill_id: '',
    optimizer_model: 'high_capability',
    execution_mode: 'mock',
    max_iterations: 10,
    max_llm_calls: 40,
    max_tool_calls: 100,
    max_cost_eur: 5.0,
  });

  // Regression Data
  const [suites, setSuites] = useState<RegressionSuite[]>([]);
  const [selectedSuiteId, setSelectedSuiteId] = useState<string | null>(null);
  const [showNewSuiteModal, setShowNewSuiteModal] = useState(false);
  const [newSuiteForm, setNewSuiteForm] = useState({
    skill_id: '',
    name: '',
    description: '',
    minimum_pass_rate: 0.95,
  });
  const [runningSuiteId, setRunningSuiteId] = useState<string | null>(null);

  // Benchmarks Data
  const [selectedBenchmark, setSelectedBenchmark] = useState<BenchmarkRun | null>(null);
  const [showNewBenchmarkModal, setShowNewBenchmarkModal] = useState(false);
  const [benchmarkForm, setBenchmarkForm] = useState({
    skill_id: '',
    regression_suite_id: '',
    model_ids: ['high_capability', 'balanced', 'economy'],
  });

  // Quarantine Action Modal/Prompt
  const [quarantinePrompt, setQuarantinePrompt] = useState<{ skillId: string; open: boolean; reason: string }>({
    skillId: '',
    open: false,
    reason: '',
  });

  // Fetch initial data
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [skillsRes, runsRes, suitesRes] = await Promise.allSettled([
        axios.get('/api/v1/skillopt/local/skills'),
        axios.get('/api/v1/skillopt/lab/runs'),
        axios.get('/api/v1/skillopt/regression/suites'),
      ]);

      if (skillsRes.status === 'fulfilled' && Array.isArray(skillsRes.value.data)) {
        setSkills(skillsRes.value.data);
        if (!selectedSkillId && skillsRes.value.data.length > 0) {
          setSelectedSkillId(skillsRes.value.data[0].id);
        }
      }

      if (runsRes.status === 'fulfilled' && Array.isArray(runsRes.value.data)) {
        setLabRuns(runsRes.value.data);
      }

      if (suitesRes.status === 'fulfilled' && Array.isArray(suitesRes.value.data)) {
        setSuites(suitesRes.value.data);
        if (!selectedSuiteId && suitesRes.value.data.length > 0) {
          setSelectedSuiteId(suitesRes.value.data[0].id);
        }
      }
    } catch (err: any) {
      console.error('Error fetching SkillOpt data:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedSkillId, selectedSuiteId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Load versions and staleness when a skill is selected
  useEffect(() => {
    if (!selectedSkillId) return;

    axios
      .get(`/api/v1/skillopt/local/skills/${selectedSkillId}/versions`)
      .then((res) => setSelectedSkillVersions(res.data || []))
      .catch((err) => console.error('Failed to load versions', err));

    axios
      .get(`/api/v1/skillopt/local/skills/${selectedSkillId}/staleness`)
      .then((res) => setSkillStaleness(res.data))
      .catch(() => setSkillStaleness(null));
  }, [selectedSkillId]);

  const showToast = (text: string, type: 'success' | 'error' | 'info' = 'info') => {
    setStatusMsg({ type, text });
    setTimeout(() => setStatusMsg(null), 4000);
  };

  // ── Actions ──────────────────────────────────────────────────────────

  const handleStartLabRun = async () => {
    if (!labForm.skill_id) {
      showToast('Please select a skill to optimize', 'error');
      return;
    }
    setLoading(true);
    try {
      const res = await axios.post('/api/v1/skillopt/lab/runs', labForm);
      const msg = res.data?.message || `Optimization run recorded (#${res.data.id.slice(0, 8)})`;
      showToast(msg, res.data?.status === 'unavailable' ? 'info' : 'success');
      setShowNewLabModal(false);
      fetchData();
      setActiveTab('lab');
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Failed to start lab run', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleCancelLabRun = async (runId: string) => {
    try {
      await axios.post(`/api/v1/skillopt/lab/runs/${runId}/cancel`);
      showToast('Optimization run cancelled', 'info');
      fetchData();
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Failed to cancel run', 'error');
    }
  };



  const handleRollbackSkill = async (skillId: string, targetVersionId?: string) => {
    if (!window.confirm('Are you sure you want to roll back this skill?')) return;
    try {
      const res = await axios.post(`/api/v1/skillopt/local/skills/${skillId}/rollback`, {
        target_version_id: targetVersionId || null,
      });
      showToast(res.data?.message || 'Skill rolled back successfully', 'success');
      fetchData();
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Rollback failed', 'error');
    }
  };

  const handleQuarantineSkill = async () => {
    if (!quarantinePrompt.reason.trim()) {
      showToast('Please provide a reason for quarantining this skill', 'error');
      return;
    }
    try {
      await axios.post(`/api/v1/skillopt/local/skills/${quarantinePrompt.skillId}/quarantine`, {
        reason: quarantinePrompt.reason,
      });
      showToast('Skill version placed under quarantine', 'info');
      setQuarantinePrompt({ skillId: '', open: false, reason: '' });
      fetchData();
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Failed to quarantine skill', 'error');
    }
  };

  const handleUnquarantineSkill = async (skillId: string) => {
    try {
      await axios.post(`/api/v1/skillopt/local/skills/${skillId}/unquarantine`);
      showToast('Quarantine removed from skill version', 'success');
      fetchData();
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Failed to remove quarantine', 'error');
    }
  };

  const handleCreateSuite = async () => {
    if (!newSuiteForm.name.trim() || !newSuiteForm.skill_id) {
      showToast('Please provide a suite name and target skill', 'error');
      return;
    }
    try {
      await axios.post('/api/v1/skillopt/regression/suites', newSuiteForm);
      showToast('Regression suite created', 'success');
      setShowNewSuiteModal(false);
      setNewSuiteForm({ skill_id: '', name: '', description: '', minimum_pass_rate: 0.95 });
      fetchData();
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Failed to create suite', 'error');
    }
  };

  const handleRunSuite = async (suiteId: string) => {
    setRunningSuiteId(suiteId);
    try {
      const res = await axios.post(`/api/v1/skillopt/regression/suites/${suiteId}/run`);
      if (res.data?.status === 'unavailable') {
        showToast(res.data.message || 'Regression suite execution is unavailable in this release', 'info');
      } else {
        showToast(`Regression run completed! Pass rate: ${(res.data.pass_rate * 100).toFixed(1)}%`, 'success');
      }
      fetchData();
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Regression run failed', 'error');
    } finally {
      setRunningSuiteId(null);
    }
  };

  const handleStartBenchmark = async () => {
    if (!benchmarkForm.skill_id || !benchmarkForm.regression_suite_id) {
      showToast('Select skill and regression suite', 'error');
      return;
    }
    setLoading(true);
    try {
      const res = await axios.post('/api/v1/skillopt/benchmarks', benchmarkForm);
      if (res.data?.status === 'unavailable') {
        showToast(res.data.message || 'Model benchmark execution is unavailable in this release', 'info');
      } else {
        showToast('Benchmark run completed!', 'success');
      }
      setShowNewBenchmarkModal(false);
      if (res.data?.id) {
        const benchDetail = await axios.get(`/api/v1/skillopt/benchmarks/${res.data.id}`);
        setSelectedBenchmark(benchDetail.data);
      }
      fetchData();
      setActiveTab('benchmarks');
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Benchmark failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Quarantined skills list for overview banner
  const quarantinedSkills = skills.filter(
    (s) => s.active_version?.quarantine_status === 'quarantined' || s.lifecycle_state === 'quarantined'
  );

  const selectedSkill = skills.find((s) => s.id === selectedSkillId) || skills[0];

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* ── Header ────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-shogun-border/60 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-shogun-gold/20 to-amber-500/10 rounded-xl border border-shogun-gold/30">
              <Cpu className="w-6 h-6 text-shogun-gold" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-shogun-text tracking-tight flex items-center gap-2.5">
                {t('skillopt.title', 'SkillOpt Lab')}
                <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-shogun-gold/15 text-shogun-gold border border-shogun-gold/30">
                  Yellow Label · Local
                </span>
              </h2>
              <p className="text-xs text-shogun-subdued mt-0.5">
                {t('skillopt.subtitle', 'Proactive local tool-chain optimization, safe evaluation, regression sweeps & model benchmarking.')}
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {statusMsg && (
            <div
              className={cn(
                'text-xs px-3 py-1.5 rounded-lg border font-medium flex items-center gap-2 animate-in fade-in slide-in-from-right-2',
                statusMsg.type === 'success' && 'bg-green-500/10 border-green-500/30 text-green-400',
                statusMsg.type === 'error' && 'bg-red-500/10 border-red-500/30 text-red-400',
                statusMsg.type === 'info' && 'bg-shogun-blue/10 border-shogun-blue/30 text-shogun-blue'
              )}
            >
              {statusMsg.type === 'success' && <CheckCircle2 className="w-3.5 h-3.5" />}
              {statusMsg.type === 'error' && <AlertTriangle className="w-3.5 h-3.5" />}
              {statusMsg.type === 'info' && <Activity className="w-3.5 h-3.5" />}
              <span>{statusMsg.text}</span>
            </div>
          )}

          <button
            onClick={() => {
              setLabForm({ ...labForm, skill_id: selectedSkillId || (skills[0]?.id ?? '') });
              setShowNewLabModal(true);
            }}
            className="flex items-center gap-2 px-3.5 py-2 bg-gradient-to-r from-shogun-gold to-[#e6b422] text-black font-semibold rounded-lg text-xs shadow-[0_0_15px_rgba(212,160,23,0.25)] hover:brightness-105 transition-all"
          >
            <FlaskConical className="w-4 h-4" />
            <span>{t('skillopt.new_run_btn', 'Start Lab Run')}</span>
          </button>

          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-[#050508] border border-shogun-border hover:border-shogun-blue/40 rounded-lg text-xs font-medium text-shogun-subdued hover:text-shogun-text transition-all"
          >
            <RefreshCw className={cn('w-3.5 h-3.5 text-shogun-blue', loading && 'animate-spin')} />
            <span>{t('common.refresh', 'Refresh')}</span>
          </button>
        </div>
      </div>

      {/* ── Sub-navigation ─────────────────────────────────────── */}
      <div className="flex items-center gap-2 border-b border-shogun-border/40 pb-2 overflow-x-auto">
        {[
          { id: 'overview' as SubTab, label: t('skillopt.nav_overview', 'Overview'), icon: Activity },
          { id: 'lab' as SubTab, label: t('skillopt.nav_lab', 'Optimization Lab'), icon: FlaskConical, count: labRuns.filter((r) => r.status === 'running').length },
          { id: 'skills' as SubTab, label: t('skillopt.nav_skills', 'Local Skills'), icon: GitBranch, count: skills.length },
          { id: 'regression' as SubTab, label: t('skillopt.nav_regression', 'Regression Suites'), icon: CheckCircle2, count: suites.length },
          { id: 'benchmarks' as SubTab, label: t('skillopt.nav_benchmarks', 'Model Benchmarks'), icon: BarChart3 },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all',
                isActive
                  ? 'bg-shogun-gold/15 text-shogun-gold border border-shogun-gold/30 shadow-[0_0_12px_rgba(212,160,23,0.1)]'
                  : 'text-shogun-subdued hover:text-shogun-text hover:bg-white/5 border border-transparent'
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
              {typeof tab.count === 'number' && tab.count > 0 && (
                <span
                  className={cn(
                    'text-[10px] px-1.5 py-0.2 rounded-full font-bold',
                    isActive ? 'bg-shogun-gold/30 text-white' : 'bg-white/10 text-shogun-subdued'
                  )}
                >
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* ── TAB 1: OVERVIEW ────────────────────────────────────── */}
      {activeTab === 'overview' && (
        <div className="space-y-6 animate-in fade-in duration-300">
          {/* Quarantined Warning Banner */}
          {quarantinedSkills.length > 0 && (
            <div className="p-4 rounded-xl border border-red-500/40 bg-red-950/20 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-red-500/20 text-red-400 mt-0.5">
                  <Ban className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-red-300">
                    {quarantinedSkills.length} Local Skill(s) in Quarantine
                  </h4>
                  <p className="text-xs text-red-300/80 mt-0.5">
                    Quarantined skills are blocked from new activations until quarantine is cleared.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setActiveTab('skills')}
                  className="px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-200 border border-red-500/40 rounded-lg text-xs font-bold transition-all"
                >
                  Inspect Quarantined
                </button>
              </div>
            </div>
          )}

          {/* Quick Metrics Bar */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="shogun-card bg-gradient-to-br from-[#07070c] to-[#0d0d16] border border-shogun-border hover:border-shogun-gold/30 transition-all p-4">
              <div className="flex items-center justify-between text-shogun-subdued text-xs">
                <span>Active Local Skills</span>
                <GitBranch className="w-4 h-4 text-shogun-gold" />
              </div>
              <p className="text-2xl font-bold text-shogun-text mt-2">{skills.length}</p>
              <p className="text-[10px] text-shogun-subdued mt-1">Managed in Tenshu SQLite</p>
            </div>

            <div className="shogun-card bg-gradient-to-br from-[#07070c] to-[#0d0d16] border border-shogun-border hover:border-shogun-blue/30 transition-all p-4">
              <div className="flex items-center justify-between text-shogun-subdued text-xs">
                <span>Active Lab Runs</span>
                <FlaskConical className="w-4 h-4 text-shogun-blue" />
              </div>
              <p className="text-2xl font-bold text-shogun-text mt-2">
                {labRuns.filter((r) => r.status === 'running').length}
              </p>
              <p className="text-[10px] text-shogun-subdued mt-1">{labRuns.length} total local runs logged</p>
            </div>

            <div className="shogun-card bg-gradient-to-br from-[#07070c] to-[#0d0d16] border border-shogun-border hover:border-green-500/30 transition-all p-4">
              <div className="flex items-center justify-between text-shogun-subdued text-xs">
                <span>Regression Health</span>
                <CheckCircle2 className="w-4 h-4 text-green-400" />
              </div>
              <p className="text-2xl font-bold text-green-400 mt-2">
                {suites.length > 0
                  ? `${Math.round((suites.filter((s) => (s.last_pass_rate ?? 0) >= 0.95).length / suites.length) * 100)}%`
                  : 'N/A'}
              </p>
              <p className="text-[10px] text-shogun-subdued mt-1">{suites.length} local suites monitored</p>
            </div>

            <div className="shogun-card bg-gradient-to-br from-[#07070c] to-[#0d0d16] border border-shogun-border hover:border-purple-500/30 transition-all p-4">
              <div className="flex items-center justify-between text-shogun-subdued text-xs">
                <span>Tool Freshness</span>
                <Layers className="w-4 h-4 text-purple-400" />
              </div>
              <p className="text-2xl font-bold text-purple-400 mt-2">
                {skillStaleness?.has_stale_tools ? 'Drift Alert' : 'Fresh'}
              </p>
              <p className="text-[10px] text-shogun-subdued mt-1">
                {skillStaleness?.warnings?.length ?? 0} schema warning(s)
              </p>
            </div>
          </div>

          {/* Dual Panel: Recent Runs & Regression Suites */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Recent Lab Runs */}
            <div className="shogun-card space-y-4">
              <div className="flex items-center justify-between border-b border-shogun-border/50 pb-3">
                <h3 className="text-sm font-bold text-shogun-text flex items-center gap-2">
                  <Activity className="w-4 h-4 text-shogun-gold" />
                  Recent Optimization Runs
                </h3>
                <button
                  onClick={() => setActiveTab('lab')}
                  className="text-xs text-shogun-gold hover:underline flex items-center gap-1"
                >
                  View All Lab Runs <ChevronRight className="w-3 h-3" />
                </button>
              </div>

              {labRuns.length === 0 ? (
                <div className="py-10 text-center text-shogun-subdued text-xs">
                  No local optimization runs yet. Click "Start Lab Run" to begin tuning a skill.
                </div>
              ) : (
                <div className="space-y-2.5">
                  {labRuns.slice(0, 5).map((run) => (
                    <div
                      key={run.id}
                      onClick={() => {
                        setSelectedLabRun(run);
                        setActiveTab('lab');
                      }}
                      className="p-3 bg-[#050508] border border-shogun-border hover:border-shogun-gold/40 rounded-xl flex items-center justify-between cursor-pointer transition-all"
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={cn(
                            'w-2 h-2 rounded-full',
                            run.status === 'completed' && 'bg-green-400 shadow-[0_0_8px_rgba(74,222,128,0.5)]',
                            run.status === 'running' && 'bg-amber-400 animate-pulse shadow-[0_0_8px_rgba(251,191,36,0.5)]',
                            run.status === 'failed' && 'bg-red-400'
                          )}
                        />
                        <div>
                          <div className="text-xs font-bold text-shogun-text">
                            Skill Run #{run.id.slice(0, 8)}
                          </div>
                          <div className="text-[10px] text-shogun-subdued">
                            Mode: <span className="uppercase text-shogun-gold">{run.execution_mode}</span> · Model: {run.optimizer_model}
                          </div>
                        </div>
                      </div>

                      <div className="text-right">
                        <span
                          className={cn(
                            'text-xs font-bold',
                            run.best_score && run.best_score >= 0.8 ? 'text-green-400' : 'text-shogun-subdued'
                          )}
                        >
                          Score: {run.best_score != null ? (run.best_score * 100).toFixed(0) + '%' : 'Pending'}
                        </span>
                        <div className="text-[10px] text-shogun-subdued">
                          Iter {run.current_iteration}/{run.max_iterations}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Regression Suites Health */}
            <div className="shogun-card space-y-4">
              <div className="flex items-center justify-between border-b border-shogun-border/50 pb-3">
                <h3 className="text-sm font-bold text-shogun-text flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-green-400" />
                  Local Regression Suites
                </h3>
                <button
                  onClick={() => setActiveTab('regression')}
                  className="text-xs text-shogun-gold hover:underline flex items-center gap-1"
                >
                  Manage Suites <ChevronRight className="w-3 h-3" />
                </button>
              </div>

              {suites.length === 0 ? (
                <div className="py-10 text-center text-shogun-subdued text-xs">
                  No regression suites registered. Create a suite to automate skill validation and safety checks.
                </div>
              ) : (
                <div className="space-y-2.5">
                  {suites.slice(0, 5).map((suite) => (
                    <div
                      key={suite.id}
                      className="p-3 bg-[#050508] border border-shogun-border rounded-xl flex items-center justify-between"
                    >
                      <div>
                        <div className="text-xs font-bold text-shogun-text">{suite.name}</div>
                        <div className="text-[10px] text-shogun-subdued">
                          {suite.case_count} cases · Min threshold: {((suite.minimum_pass_rate ?? 0.95) * 100).toFixed(0)}%
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        <div className="text-right">
                          <span
                            className={cn(
                              'text-xs font-bold',
                              (suite.last_pass_rate ?? 0) >= (suite.minimum_pass_rate ?? 0.95)
                                ? 'text-green-400'
                                : 'text-red-400'
                            )}
                          >
                            {suite.last_pass_rate != null ? `${(suite.last_pass_rate * 100).toFixed(1)}%` : 'No runs'}
                          </span>
                          <div className="text-[10px] text-shogun-subdued">
                            {suite.last_run_at ? new Date(suite.last_run_at).toLocaleDateString() : 'Pending'}
                          </div>
                        </div>
                        <button
                          onClick={() => handleRunSuite(suite.id)}
                          disabled={runningSuiteId === suite.id}
                          className="p-2 bg-shogun-card hover:bg-white/10 text-shogun-text border border-shogun-border rounded-lg text-xs transition-all disabled:opacity-50"
                        >
                          {runningSuiteId === suite.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin text-shogun-gold" />
                          ) : (
                            <Play className="w-3.5 h-3.5 text-green-400" />
                          )}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 2: SKILLOPT LAB ────────────────────────────────── */}
      {activeTab === 'lab' && (
        <div className="space-y-6 animate-in fade-in duration-300">
          {/* Execution Unavailable Notice */}
          <div className="p-3.5 bg-shogun-card border border-shogun-border/80 rounded-xl flex items-center justify-between text-xs">
            <div className="flex items-center gap-2.5">
              <FlaskConical className="w-4 h-4 text-shogun-gold" />
              <span className="text-shogun-subdued">
                <b className="text-shogun-text">Execution Status:</b> Automated optimizer execution is marked unavailable in this release. Local skill configuration, prompt inspection, and manual lifecycle management are available.
              </span>
            </div>
            <span className="text-[10px] px-2 py-0.5 rounded-full font-bold uppercase bg-slate-500/15 text-slate-300 border border-slate-500/30">
              Execution Unavailable
            </span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left: Runs List */}
            <div className="lg:col-span-1 space-y-4">
              <div className="shogun-card">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-bold text-shogun-text flex items-center gap-2">
                    <FlaskConical className="w-4 h-4 text-shogun-gold" />
                    Optimization Runs
                  </h3>
                  <button
                    onClick={() => setShowNewLabModal(true)}
                    className="p-1.5 bg-shogun-gold/20 hover:bg-shogun-gold/30 text-shogun-gold rounded-lg text-xs flex items-center gap-1 font-bold"
                  >
                    <Plus className="w-3.5 h-3.5" /> New Run
                  </button>
                </div>

                {labRuns.length === 0 ? (
                  <div className="py-12 text-center text-shogun-subdued text-xs">
                    No runs recorded yet. Click "New Run" to launch the optimization engine.
                  </div>
                ) : (
                  <div className="space-y-2.5 max-h-[600px] overflow-y-auto pr-1">
                    {labRuns.map((run) => {
                      const isSelected = selectedLabRun?.id === run.id;
                      return (
                        <div
                          key={run.id}
                          onClick={() => setSelectedLabRun(run)}
                          className={cn(
                            'p-3.5 rounded-xl border cursor-pointer transition-all text-left',
                            isSelected
                              ? 'bg-shogun-gold/10 border-shogun-gold shadow-[0_0_12px_rgba(212,160,23,0.15)]'
                              : 'bg-[#050508] border-shogun-border hover:border-shogun-gold/30'
                          )}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-bold text-xs text-shogun-text">
                              Run #{run.id.slice(0, 8)}
                            </span>
                            <span
                              className={cn(
                                'text-[10px] px-2 py-0.5 rounded-full font-bold uppercase',
                                run.status === 'completed' && 'bg-green-500/20 text-green-400 border border-green-500/30',
                                run.status === 'running' && 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
                                run.status === 'failed' && 'bg-red-500/20 text-red-400 border border-red-500/30',
                                run.status === 'cancelled' && 'bg-gray-500/20 text-gray-400 border border-gray-500/30',
                                run.status === 'unavailable' && 'bg-slate-500/20 text-slate-300 border border-slate-500/30'
                              )}
                            >
                              {run.status}
                            </span>
                          </div>
                          <div className="text-[11px] text-shogun-subdued">
                            Mode: <span className="text-shogun-text uppercase">{run.execution_mode}</span> · Model: {run.optimizer_model}
                          </div>
                          <div className="mt-2 pt-2 border-t border-shogun-border/40 flex items-center justify-between text-[10px] text-shogun-subdued">
                            <span>Iter: {run.current_iteration}/{run.max_iterations}</span>
                            <span className="font-semibold text-shogun-gold">
                              Best: {run.best_score != null ? `${(run.best_score * 100).toFixed(0)}%` : 'None'}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Right: Selected Run Details & Textual Gradients */}
            <div className="lg:col-span-2 space-y-6">
              {selectedLabRun ? (
                <div className="shogun-card space-y-6">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-shogun-border/50 pb-4">
                    <div>
                      <h3 className="text-base font-bold text-shogun-text flex items-center gap-2">
                        <span>Optimization Run Detail</span>
                        <span className="text-xs font-mono text-shogun-gold">#{selectedLabRun.id}</span>
                      </h3>
                      <p className="text-xs text-shogun-subdued mt-0.5">
                        Execution mode: <b className="uppercase text-shogun-text">{selectedLabRun.execution_mode}</b> · Target skill: {selectedLabRun.skill_id}
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      {selectedLabRun.status === 'running' && (
                        <button
                          onClick={() => handleCancelLabRun(selectedLabRun.id)}
                          className="px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/40 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all"
                        >
                          <X className="w-3.5 h-3.5" /> Cancel Run
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Budget & Resource Metrics */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3 bg-[#050508] border border-shogun-border rounded-xl">
                      <span className="text-[10px] text-shogun-subdued block">Iterations</span>
                      <span className="text-base font-bold text-shogun-text">
                        {selectedLabRun.current_iteration} / {selectedLabRun.max_iterations}
                      </span>
                    </div>
                    <div className="p-3 bg-[#050508] border border-shogun-border rounded-xl">
                      <span className="text-[10px] text-shogun-subdued block">LLM Calls</span>
                      <span className="text-base font-bold text-shogun-text">
                        {selectedLabRun.total_llm_calls} / {selectedLabRun.max_llm_calls}
                      </span>
                    </div>
                    <div className="p-3 bg-[#050508] border border-shogun-border rounded-xl">
                      <span className="text-[10px] text-shogun-subdued block">Tool Calls</span>
                      <span className="text-base font-bold text-shogun-text">
                        {selectedLabRun.total_tool_calls} / {selectedLabRun.max_tool_calls}
                      </span>
                    </div>
                    <div className="p-3 bg-[#050508] border border-shogun-border rounded-xl">
                      <span className="text-[10px] text-shogun-subdued block">Cost Incurred</span>
                      <span className="text-base font-bold text-shogun-gold">
                        €{selectedLabRun.total_cost_eur?.toFixed(3)} / €{selectedLabRun.max_cost_eur?.toFixed(2)}
                      </span>
                    </div>
                  </div>

                  {/* Textual Gradient Feedback Box (§14.6) */}
                  <div className="p-4 rounded-xl bg-gradient-to-br from-[#050508] to-[#0a0a10] border border-shogun-border space-y-3">
                    <h4 className="text-xs font-bold text-shogun-gold uppercase tracking-wider flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-shogun-gold" />
                      Textual Gradient & Evaluator Diagnostics
                    </h4>

                    {selectedLabRun.result_json?.gradient ? (
                      <div className="space-y-3 text-xs">
                        <div className="p-3 rounded-lg bg-red-950/20 border border-red-500/20 text-red-300">
                          <span className="font-bold block mb-1">Failure Summary:</span>
                          {selectedLabRun.result_json.gradient.failure_summary || 'No failure reported'}
                        </div>

                        {selectedLabRun.result_json.gradient.root_causes?.length > 0 && (
                          <div>
                            <span className="font-semibold text-shogun-subdued block mb-1">Root Causes:</span>
                            <ul className="list-disc list-inside space-y-0.5 text-shogun-text">
                              {selectedLabRun.result_json.gradient.root_causes.map((rc: string, i: number) => (
                                <li key={i}>{rc}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {selectedLabRun.result_json.gradient.recommended_changes?.length > 0 && (
                          <div>
                            <span className="font-semibold text-shogun-subdued block mb-1">Recommended Adjustments:</span>
                            <ul className="list-disc list-inside space-y-0.5 text-green-300">
                              {selectedLabRun.result_json.gradient.recommended_changes.map((rc: string, i: number) => (
                                <li key={i}>{rc}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-xs text-shogun-subdued italic">
                        No active textual gradient available yet for this run. Gradients are synthesized upon evaluation failure.
                      </p>
                    )}
                  </div>

                  {/* Weighted Evaluation Scoring (§38) */}
                  <div className="space-y-3">
                    <h4 className="text-xs font-bold text-shogun-text uppercase tracking-wider">
                      Evaluator Metric Weights (§38)
                    </h4>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                      {[
                        { label: 'Task Success', weight: '35%' },
                        { label: 'Correctness', weight: '25%' },
                        { label: 'Policy Compliance', weight: '15%' },
                        { label: 'Tool Efficiency', weight: '10%' },
                        { label: 'Robustness', weight: '7%' },
                        { label: 'Latency', weight: '5%' },
                        { label: 'Cost', weight: '3%' },
                      ].map((item, idx) => (
                        <div key={idx} className="p-2.5 rounded-lg bg-[#050508] border border-shogun-border/60">
                          <div className="text-[10px] text-shogun-subdued">{item.label}</div>
                          <div className="font-bold text-shogun-gold mt-0.5">{item.weight}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="shogun-card min-h-[350px] flex flex-col items-center justify-center text-center p-8 text-shogun-subdued">
                  <FlaskConical className="w-12 h-12 text-shogun-border mb-3" />
                  <p className="font-medium text-sm text-shogun-text">Select a Lab Run to Inspect</p>
                  <p className="text-xs text-shogun-subdued mt-1 max-w-sm">
                    View iterations, budget consumption, candidate diffs, and structured textual gradients.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 3: LOCAL SKILLS & VERSIONING ──────────────────── */}
      {activeTab === 'skills' && (
        <div className="space-y-6 animate-in fade-in duration-300">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Skills List */}
            <div className="lg:col-span-1 space-y-4">
              <div className="shogun-card space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-shogun-text flex items-center gap-2">
                    <GitBranch className="w-4 h-4 text-shogun-gold" />
                    Local Skills
                  </h3>
                  <span className="text-xs text-shogun-subdued">{skills.length} skills</span>
                </div>

                <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
                  {skills.map((sk) => {
                    const isSelected = selectedSkill?.id === sk.id;
                    const isQuarantined =
                      sk.active_version?.quarantine_status === 'quarantined' || sk.lifecycle_state === 'quarantined';
                    return (
                      <div
                        key={sk.id}
                        onClick={() => setSelectedSkillId(sk.id)}
                        className={cn(
                          'p-3.5 rounded-xl border cursor-pointer transition-all text-left',
                          isSelected
                            ? 'bg-shogun-gold/10 border-shogun-gold shadow-[0_0_12px_rgba(212,160,23,0.15)]'
                            : 'bg-[#050508] border-shogun-border hover:border-shogun-gold/30'
                        )}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-bold text-xs text-shogun-text">{sk.name}</span>
                          {isQuarantined && (
                            <span className="text-[10px] px-1.5 py-0.2 bg-red-500/20 text-red-400 rounded border border-red-500/30 font-bold uppercase">
                              Quarantined
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-shogun-subdued line-clamp-1">{sk.slug}</div>
                        <div className="mt-2 flex items-center justify-between text-[10px] text-shogun-subdued">
                          <span>Version: {sk.active_version ? `v${sk.active_version.version_number}` : 'None'}</span>
                          <span className="capitalize">{sk.status}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Selected Skill Detail & Version Timeline */}
            <div className="lg:col-span-2 space-y-6">
              {selectedSkill ? (
                <div className="space-y-6">
                  {/* Skill Header Card */}
                  <div className="shogun-card space-y-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-shogun-border/50 pb-4">
                      <div>
                        <h3 className="text-lg font-bold text-shogun-text flex items-center gap-2">
                          <span>{selectedSkill.name}</span>
                          <span className="text-xs px-2 py-0.5 rounded bg-shogun-card border border-shogun-border text-shogun-subdued font-mono">
                            {selectedSkill.slug}
                          </span>
                        </h3>
                        <p className="text-xs text-shogun-subdued mt-0.5">
                          Risk Tier: <b className="text-shogun-gold">{selectedSkill.risk_tier || 'standard'}</b> · Lifecycle:{' '}
                          <b className="capitalize text-shogun-text">{selectedSkill.lifecycle_state || 'active'}</b>
                        </p>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        {selectedSkill.active_version?.quarantine_status === 'quarantined' ? (
                          <button
                            onClick={() => handleUnquarantineSkill(selectedSkill.id)}
                            className="px-3 py-1.5 bg-green-500/20 hover:bg-green-500/30 text-green-300 border border-green-500/40 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all"
                          >
                            <Check className="w-3.5 h-3.5" /> Remove Quarantine
                          </button>
                        ) : (
                          <button
                            onClick={() =>
                              setQuarantinePrompt({ skillId: selectedSkill.id, open: true, reason: '' })
                            }
                            className="px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/40 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all"
                          >
                            <Ban className="w-3.5 h-3.5" /> Quarantine
                          </button>
                        )}

                        <button
                          onClick={() => handleRollbackSkill(selectedSkill.id)}
                          className="px-3 py-1.5 bg-shogun-card hover:bg-white/10 text-shogun-text border border-shogun-border rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all"
                        >
                          <RotateCcw className="w-3.5 h-3.5 text-shogun-gold" /> Rollback
                        </button>

                        <button
                          onClick={() => {
                            setLabForm({ ...labForm, skill_id: selectedSkill.id });
                            setShowNewLabModal(true);
                          }}
                          className="px-3 py-1.5 bg-shogun-gold hover:bg-[#e6b422] text-black rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all"
                        >
                          <FlaskConical className="w-3.5 h-3.5" /> Optimize
                        </button>
                      </div>
                    </div>

                    {/* Tool Staleness Warning */}
                    {skillStaleness?.has_stale_tools && (
                      <div className="p-3 bg-amber-950/20 border border-amber-500/30 rounded-xl text-amber-300 text-xs flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4 text-amber-400" />
                          <span>Tool schema drift detected! Tools used during validation have changed.</span>
                        </div>
                        <span className="text-[10px] bg-amber-500/20 px-2 py-0.5 rounded font-mono">
                          {skillStaleness.warnings.length} warning(s)
                        </span>
                      </div>
                    )}

                    {/* Version History Table */}
                    <div>
                      <h4 className="text-xs font-bold text-shogun-text uppercase tracking-wider mb-3">
                        Version History
                      </h4>
                      {selectedSkillVersions.length === 0 ? (
                        <p className="text-xs text-shogun-subdued italic">No version records found for this skill.</p>
                      ) : (
                        <div className="space-y-2">
                          {selectedSkillVersions.map((v) => {
                            const isActive = selectedSkill.active_version_id === v.id || v.status === 'active';
                            return (
                              <div
                                key={v.id}
                                className={cn(
                                  'p-3 rounded-xl border flex items-center justify-between text-xs transition-all',
                                  isActive
                                    ? 'bg-shogun-gold/10 border-shogun-gold/40'
                                    : 'bg-[#050508] border-shogun-border hover:border-shogun-border/80'
                                )}
                              >
                                <div className="flex items-center gap-3">
                                  <span className="font-bold text-shogun-text text-sm">v{v.version_number}</span>
                                  <div>
                                    <div className="flex items-center gap-2">
                                      <span
                                        className={cn(
                                          'text-[10px] px-1.5 py-0.2 rounded font-bold uppercase',
                                          isActive
                                            ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                                            : 'bg-shogun-card text-shogun-subdued border border-shogun-border'
                                        )}
                                      >
                                        {isActive ? 'Active' : v.status}
                                      </span>
                                      <span className="text-[10px] text-shogun-subdued font-mono">
                                        {v.content_hash.slice(0, 10)}...
                                      </span>
                                    </div>
                                    <span className="text-[10px] text-shogun-subdued">
                                      By: {v.created_by || 'system'} · Score:{' '}
                                      {v.validation_score != null ? `${(v.validation_score * 100).toFixed(0)}%` : 'N/A'}
                                    </span>
                                  </div>
                                </div>

                                <div className="flex items-center gap-2">
                                  {!isActive && (
                                    <button
                                      onClick={() => handleRollbackSkill(selectedSkill.id, v.id)}
                                      className="px-2.5 py-1 bg-[#050508] hover:bg-white/10 text-shogun-subdued hover:text-shogun-text rounded border border-shogun-border text-[10px]"
                                    >
                                      Rollback Here
                                    </button>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="shogun-card min-h-[350px] flex items-center justify-center text-center p-8 text-shogun-subdued">
                  Select a skill to inspect versions and lifecycle controls
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 4: REGRESSION SUITES ───────────────────────────── */}
      {activeTab === 'regression' && (
        <div className="space-y-6 animate-in fade-in duration-300">
          {/* Execution Unavailable Notice */}
          <div className="p-3.5 bg-shogun-card border border-shogun-border/80 rounded-xl flex items-center justify-between text-xs">
            <div className="flex items-center gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-shogun-gold" />
              <span className="text-shogun-subdued">
                <b className="text-shogun-text">Execution Status:</b> Automated regression suite execution is marked unavailable in this release. Test suites and cases can be authored and preserved for local inspection.
              </span>
            </div>
            <span className="text-[10px] px-2 py-0.5 rounded-full font-bold uppercase bg-slate-500/15 text-slate-300 border border-slate-500/30">
              Execution Unavailable
            </span>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-shogun-text">Local Regression Test Suites</h3>
              <p className="text-xs text-shogun-subdued">
                Deterministic test suites for validation, pass-rate verification & anti-regression (§14.8, §33).
              </p>
            </div>
            <button
              onClick={() => setShowNewSuiteModal(true)}
              className="flex items-center gap-2 px-3.5 py-2 bg-shogun-gold hover:bg-[#e6b422] text-black font-semibold rounded-lg text-xs transition-all"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create Regression Suite</span>
            </button>
          </div>

          {suites.length === 0 ? (
            <div className="shogun-card text-center py-16 text-shogun-subdued">
              <CheckCircle2 className="w-12 h-12 text-shogun-border mx-auto mb-3" />
              <p className="text-sm font-semibold text-shogun-text">No Regression Suites Configured</p>
              <p className="text-xs text-shogun-subdued mt-1 max-w-sm mx-auto">
                Create a test suite to ensure automated candidate proposals never break expected behavior.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {suites.map((suite) => {
                const isPassed = (suite.last_pass_rate ?? 0) >= (suite.minimum_pass_rate ?? 0.95);
                return (
                  <div
                    key={suite.id}
                    className="shogun-card bg-[#050508] border border-shogun-border hover:border-shogun-gold/30 transition-all p-4 flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <h4 className="font-bold text-sm text-shogun-text">{suite.name}</h4>
                        <span
                          className={cn(
                            'text-[10px] px-2 py-0.5 rounded-full font-bold uppercase',
                            isPassed
                              ? 'bg-green-500/15 text-green-400 border border-green-500/30'
                              : 'bg-red-500/15 text-red-400 border border-red-500/30'
                          )}
                        >
                          {suite.last_pass_rate != null ? `${(suite.last_pass_rate * 100).toFixed(0)}%` : 'Untested'}
                        </span>
                      </div>
                      <p className="text-xs text-shogun-subdued line-clamp-2 mb-4">
                        {suite.description || 'Deterministic test suite for skill verification.'}
                      </p>
                    </div>

                    <div className="pt-3 border-t border-shogun-border/40 flex items-center justify-between text-xs">
                      <span className="text-shogun-subdued">{suite.case_count} Test Cases</span>
                      <button
                        onClick={() => handleRunSuite(suite.id)}
                        disabled={runningSuiteId === suite.id}
                        className="px-3 py-1.5 bg-shogun-gold/15 hover:bg-shogun-gold/25 text-shogun-gold border border-shogun-gold/30 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all disabled:opacity-50"
                      >
                        {runningSuiteId === suite.id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Play className="w-3.5 h-3.5" />
                        )}
                        <span>Run Suite</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ── TAB 5: MODEL BENCHMARKS ───────────────────────────── */}
      {activeTab === 'benchmarks' && (
        <div className="space-y-6 animate-in fade-in duration-300">
          {/* Execution Unavailable Notice */}
          <div className="p-3.5 bg-shogun-card border border-shogun-border/80 rounded-xl flex items-center justify-between text-xs">
            <div className="flex items-center gap-2.5">
              <BarChart3 className="w-4 h-4 text-shogun-gold" />
              <span className="text-shogun-subdued">
                <b className="text-shogun-text">Execution Status:</b> Model benchmarking execution is marked unavailable in this release. Benchmark suites and results can be configured and inspected.
              </span>
            </div>
            <span className="text-[10px] px-2 py-0.5 rounded-full font-bold uppercase bg-slate-500/15 text-slate-300 border border-slate-500/30">
              Execution Unavailable
            </span>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-shogun-text">Local Model Benchmarking</h3>
              <p className="text-xs text-shogun-subdued">
                Compare models across identical local test fixtures, tool contracts & regression cases (§15, §16).
              </p>
            </div>
            <button
              onClick={() => setShowNewBenchmarkModal(true)}
              className="flex items-center gap-2 px-3.5 py-2 bg-shogun-gold hover:bg-[#e6b422] text-black font-semibold rounded-lg text-xs transition-all"
            >
              <BarChart3 className="w-3.5 h-3.5" />
              <span>Launch Benchmark</span>
            </button>
          </div>

          {selectedBenchmark?.results && selectedBenchmark.results.length > 0 ? (
            <div className="shogun-card space-y-4">
              <h4 className="text-xs font-bold text-shogun-gold uppercase tracking-wider">
                Benchmark Results Comparison Matrix
              </h4>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-shogun-border text-shogun-subdued uppercase text-[10px]">
                      <th className="py-2.5 px-3">Model</th>
                      <th className="py-2.5 px-3">Success Rate</th>
                      <th className="py-2.5 px-3">Policy Compliance</th>
                      <th className="py-2.5 px-3">Avg Tool Calls</th>
                      <th className="py-2.5 px-3">Avg Latency</th>
                      <th className="py-2.5 px-3">Avg Cost</th>
                      <th className="py-2.5 px-3">Passed Cases</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-shogun-border/40">
                    {selectedBenchmark.results.map((res, i) => (
                      <tr key={i} className="hover:bg-white/5">
                        <td className="py-3 px-3 font-bold text-shogun-text">{res.model_id}</td>
                        <td className="py-3 px-3">
                          <span className="font-semibold text-green-400">
                            {(res.success_rate * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td className="py-3 px-3">
                          <span className="font-semibold text-shogun-blue">
                            {(res.policy_compliance * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td className="py-3 px-3 text-shogun-text">{res.avg_tool_calls.toFixed(1)}</td>
                        <td className="py-3 px-3 text-shogun-subdued">{res.avg_latency_seconds.toFixed(2)}s</td>
                        <td className="py-3 px-3 text-shogun-gold">€{res.avg_cost_eur.toFixed(4)}</td>
                        <td className="py-3 px-3 text-shogun-text font-mono">
                          {res.passed_cases}/{res.total_cases}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="shogun-card text-center py-16 text-shogun-subdued">
              <BarChart3 className="w-12 h-12 text-shogun-border mx-auto mb-3" />
              <p className="text-sm font-semibold text-shogun-text">No Benchmarks Run Yet</p>
              <p className="text-xs text-shogun-subdued mt-1 max-w-sm mx-auto">
                Launch a benchmark against your regression suites to establish local competence profiles for each model.
              </p>
            </div>
          )}
        </div>
      )}

      {/* ── MODAL: New Lab Optimization Run ────────────────────── */}
      {showNewLabModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0c0c14] border border-shogun-border rounded-2xl w-full max-w-lg p-6 space-y-5 shadow-2xl animate-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-shogun-border/50 pb-3">
              <h3 className="font-bold text-base text-shogun-text flex items-center gap-2">
                <FlaskConical className="w-5 h-5 text-shogun-gold" />
                Configure Local Optimization Run
              </h3>
              <button
                onClick={() => setShowNewLabModal(false)}
                className="p-1 rounded-lg text-shogun-subdued hover:text-shogun-text hover:bg-white/10"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <label className="text-shogun-subdued block mb-1 font-medium">Target Skill *</label>
                <select
                  value={labForm.skill_id}
                  onChange={(e) => setLabForm({ ...labForm, skill_id: e.target.value })}
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-shogun-text focus:border-shogun-gold outline-none"
                >
                  <option value="">Select a skill...</option>
                  {skills.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.slug})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-shogun-subdued block mb-1 font-medium">Optimizer Model</label>
                  <select
                    value={labForm.optimizer_model}
                    onChange={(e) => setLabForm({ ...labForm, optimizer_model: e.target.value })}
                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-shogun-text focus:border-shogun-gold outline-none"
                  >
                    <option value="high_capability">High Capability Profile</option>
                    <option value="balanced">Balanced Profile</option>
                    <option value="economy">Economy Profile</option>
                  </select>
                </div>

                <div>
                  <label className="text-shogun-subdued block mb-1 font-medium">Execution Mode (§14.4)</label>
                  <select
                    value={labForm.execution_mode}
                    onChange={(e) => setLabForm({ ...labForm, execution_mode: e.target.value })}
                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-shogun-text focus:border-shogun-gold outline-none"
                  >
                    <option value="mock">MOCK (Deterministic Mock)</option>
                    <option value="fixture" disabled>FIXTURE (Unavailable)</option>
                    <option value="sandbox" disabled>SANDBOX (Unavailable)</option>
                  </select>
                </div>
              </div>

              {/* Budget Limits (§40) */}
              <div className="p-3 bg-[#050508] border border-shogun-border rounded-xl space-y-3">
                <span className="font-bold text-shogun-gold uppercase tracking-wider text-[10px] block">
                  Budget & Safety Safeguards (§40)
                </span>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-shogun-subdued text-[10px] block mb-1">Max Iterations</label>
                    <input
                      type="number"
                      value={labForm.max_iterations}
                      onChange={(e) => setLabForm({ ...labForm, max_iterations: parseInt(e.target.value) || 1 })}
                      className="w-full bg-[#0c0c14] border border-shogun-border rounded p-2 text-shogun-text"
                    />
                  </div>
                  <div>
                    <label className="text-shogun-subdued text-[10px] block mb-1">Max LLM Calls</label>
                    <input
                      type="number"
                      value={labForm.max_llm_calls}
                      onChange={(e) => setLabForm({ ...labForm, max_llm_calls: parseInt(e.target.value) || 1 })}
                      className="w-full bg-[#0c0c14] border border-shogun-border rounded p-2 text-shogun-text"
                    />
                  </div>
                  <div>
                    <label className="text-shogun-subdued text-[10px] block mb-1">Max Tool Calls</label>
                    <input
                      type="number"
                      value={labForm.max_tool_calls}
                      onChange={(e) => setLabForm({ ...labForm, max_tool_calls: parseInt(e.target.value) || 1 })}
                      className="w-full bg-[#0c0c14] border border-shogun-border rounded p-2 text-shogun-text"
                    />
                  </div>
                  <div>
                    <label className="text-shogun-subdued text-[10px] block mb-1">Max Cost (€)</label>
                    <input
                      type="number"
                      step="0.5"
                      value={labForm.max_cost_eur}
                      onChange={(e) => setLabForm({ ...labForm, max_cost_eur: parseFloat(e.target.value) || 1.0 })}
                      className="w-full bg-[#0c0c14] border border-shogun-border rounded p-2 text-shogun-text"
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-shogun-border/50">
              <button
                onClick={() => setShowNewLabModal(false)}
                className="px-4 py-2 bg-transparent hover:bg-white/5 text-shogun-subdued hover:text-shogun-text rounded-lg text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={handleStartLabRun}
                disabled={loading}
                className="px-5 py-2 bg-shogun-gold hover:bg-[#e6b422] text-black font-bold rounded-lg text-xs flex items-center gap-2 shadow-[0_0_15px_rgba(212,160,23,0.3)] transition-all"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                <span>Launch Optimization</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: Quarantine Reason ──────────────────────────── */}
      {quarantinePrompt.open && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0c0c14] border border-red-500/40 rounded-2xl w-full max-w-md p-6 space-y-4 shadow-2xl animate-in zoom-in-95">
            <div className="flex items-center gap-3 text-red-400">
              <Ban className="w-5 h-5" />
              <h3 className="font-bold text-base text-shogun-text">Quarantine Skill Version</h3>
            </div>
            <p className="text-xs text-shogun-subdued">
              Quarantine blocks new activations of this skill. Work already running is not cancelled.
            </p>
            <div>
              <label className="text-xs text-shogun-subdued block mb-1 font-medium">Reason for Quarantine *</label>
              <textarea
                value={quarantinePrompt.reason}
                onChange={(e) => setQuarantinePrompt({ ...quarantinePrompt, reason: e.target.value })}
                rows={3}
                placeholder="e.g. Failed safety check, regression detected on production inputs..."
                className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-xs text-shogun-text focus:border-red-500 outline-none"
              />
            </div>
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setQuarantinePrompt({ skillId: '', open: false, reason: '' })}
                className="px-4 py-2 bg-transparent hover:bg-white/5 text-shogun-subdued hover:text-shogun-text rounded-lg text-xs"
              >
                Cancel
              </button>
              <button
                onClick={handleQuarantineSkill}
                className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white font-bold rounded-lg text-xs transition-all shadow-[0_0_15px_rgba(239,68,68,0.3)]"
              >
                Confirm Quarantine
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: Create Suite ──────────────────────────────── */}
      {showNewSuiteModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0c0c14] border border-shogun-border rounded-2xl w-full max-w-md p-6 space-y-4 shadow-2xl animate-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-shogun-border/50 pb-3">
              <h3 className="font-bold text-base text-shogun-text flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-green-400" />
                Create Regression Suite
              </h3>
              <button onClick={() => setShowNewSuiteModal(false)}>
                <X className="w-4 h-4 text-shogun-subdued" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="text-shogun-subdued block mb-1 font-medium">Target Skill *</label>
                <select
                  value={newSuiteForm.skill_id}
                  onChange={(e) => setNewSuiteForm({ ...newSuiteForm, skill_id: e.target.value })}
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-shogun-text"
                >
                  <option value="">Select a skill...</option>
                  {skills.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-shogun-subdued block mb-1 font-medium">Suite Name *</label>
                <input
                  type="text"
                  value={newSuiteForm.name}
                  onChange={(e) => setNewSuiteForm({ ...newSuiteForm, name: e.target.value })}
                  placeholder="e.g. Core Verification Suite"
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-shogun-text"
                />
              </div>

              <div>
                <label className="text-shogun-subdued block mb-1 font-medium">Description</label>
                <textarea
                  value={newSuiteForm.description}
                  onChange={(e) => setNewSuiteForm({ ...newSuiteForm, description: e.target.value })}
                  rows={2}
                  placeholder="Validation goals and regression requirements..."
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-shogun-text"
                />
              </div>

              <div>
                <label className="text-shogun-subdued block mb-1 font-medium">Minimum Pass Rate (0.0 to 1.0)</label>
                <input
                  type="number"
                  step="0.05"
                  min="0.5"
                  max="1.0"
                  value={newSuiteForm.minimum_pass_rate}
                  onChange={(e) =>
                    setNewSuiteForm({ ...newSuiteForm, minimum_pass_rate: parseFloat(e.target.value) || 0.95 })
                  }
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-shogun-text"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-shogun-border/50">
              <button
                onClick={() => setShowNewSuiteModal(false)}
                className="px-4 py-2 text-shogun-subdued hover:text-shogun-text text-xs"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateSuite}
                className="px-4 py-2 bg-shogun-gold hover:bg-[#e6b422] text-black font-bold rounded-lg text-xs"
              >
                Create Suite
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: New Benchmark ─────────────────────────────── */}
      {showNewBenchmarkModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0c0c14] border border-shogun-border rounded-2xl w-full max-w-md p-6 space-y-4 shadow-2xl animate-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-shogun-border/50 pb-3">
              <h3 className="font-bold text-base text-shogun-text flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-shogun-gold" />
                Launch Model Benchmark
              </h3>
              <button onClick={() => setShowNewBenchmarkModal(false)}>
                <X className="w-4 h-4 text-shogun-subdued" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="text-shogun-subdued block mb-1 font-medium">Target Skill *</label>
                <select
                  value={benchmarkForm.skill_id}
                  onChange={(e) => setBenchmarkForm({ ...benchmarkForm, skill_id: e.target.value })}
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-shogun-text"
                >
                  <option value="">Select a skill...</option>
                  {skills.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-shogun-subdued block mb-1 font-medium">Regression Suite *</label>
                <select
                  value={benchmarkForm.regression_suite_id}
                  onChange={(e) => setBenchmarkForm({ ...benchmarkForm, regression_suite_id: e.target.value })}
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-shogun-text"
                >
                  <option value="">Select a suite...</option>
                  {suites.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.case_count} cases)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-shogun-subdued block mb-1 font-medium">
                  Models to Compare (comma separated)
                </label>
                <input
                  type="text"
                  value={benchmarkForm.model_ids.join(', ')}
                  onChange={(e) =>
                    setBenchmarkForm({
                      ...benchmarkForm,
                      model_ids: e.target.value.split(',').map((m) => m.trim()).filter(Boolean),
                    })
                  }
                  className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-shogun-text"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-shogun-border/50">
              <button
                onClick={() => setShowNewBenchmarkModal(false)}
                className="px-4 py-2 text-shogun-subdued hover:text-shogun-text text-xs"
              >
                Cancel
              </button>
              <button
                onClick={handleStartBenchmark}
                disabled={loading}
                className="px-4 py-2 bg-shogun-gold hover:bg-[#e6b422] text-black font-bold rounded-lg text-xs flex items-center gap-2"
              >
                {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Launch Benchmark
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
