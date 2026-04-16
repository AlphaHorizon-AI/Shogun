import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { 
  Activity, 
  RefreshCw, 
  Target, 
  BrainCircuit, 
  ShieldCheck, 
  TrendingUp, 
  Settings2, 
  Flame,
  Binary,
  Compass,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  Save
} from "lucide-react";
import { cn } from '../lib/utils';

const API = 'http://localhost:8888/api/v1/bushido';

interface BushidoStats {
  fit_quality: number;
  active_cycles: number;
  optimization_delta: number;
  neural_load: number;
  engine_status: string;
  running_jobs: number;
}

interface Calibration {
  reflection_intensity: number;
  consolidation_rate: number;
  exploration_variance: number;
}

interface Recommendation {
  id: string;
  recommendation_type: string;
  title: string;
  description: string;
  risk_level: string;
  status: string;
  created_at: string;
}

const DEFAULT_CALIBRATION: Calibration = {
  reflection_intensity: 70,
  consolidation_rate: 45,
  exploration_variance: 24,
};

export function Bushido() {
  // ── Stats ──────────────────────────────────────────
  const [stats, setStats] = useState<BushidoStats | null>(null);
  
  // ── Calibration ────────────────────────────────────
  const [calibration, setCalibration] = useState<Calibration>(DEFAULT_CALIBRATION);
  const [calibrationDirty, setCalibrationDirty] = useState(false);
  
  // ── Insights (recommendations) ────────────────────
  const [insights, setInsights] = useState<Recommendation[]>([]);
  
  // ── UI state ───────────────────────────────────────
  const [saving, setSaving] = useState(false);
  const [reflecting, setReflecting] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // ── Load stats ─────────────────────────────────────
  const loadStats = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/stats`);
      setStats(res.data.data);
    } catch { /* silent */ }
  }, []);

  // ── Load calibration ──────────────────────────────
  const loadCalibration = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/calibration`);
      setCalibration(res.data.data);
      setCalibrationDirty(false);
    } catch { /* silent */ }
  }, []);

  // ── Load recommendations ──────────────────────────
  const loadInsights = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/recommendations`);
      const recs = (res.data.data || []).slice(0, 8);
      setInsights(recs);
    } catch { /* silent */ }
  }, []);

  // ── Initial load ──────────────────────────────────
  useEffect(() => {
    loadStats();
    loadCalibration();
    loadInsights();
  }, [loadStats, loadCalibration, loadInsights]);

  // ── Auto-refresh stats every 15s ──────────────────
  useEffect(() => {
    const interval = setInterval(loadStats, 15000);
    return () => clearInterval(interval);
  }, [loadStats]);

  // ── Handlers ──────────────────────────────────────
  const handleForceReflection = async () => {
    setReflecting(true);
    try {
      await axios.post(`${API}/run`, {
        job_type: 'persona_drift_check',
        trigger_mode: 'manual',
        priority: 50,
        scope: { agent_ids: [], memory_types: [] },
      });
      setStatusMsg({ type: 'success', text: 'Reflection cycle initiated. Monitor Insight Stream for results.' });
      // Refresh stats and insights after a delay
      setTimeout(() => { loadStats(); loadInsights(); }, 5000);
    } catch {
      setStatusMsg({ type: 'error', text: 'Failed to trigger reflection.' });
    } finally {
      setReflecting(false);
      setTimeout(() => setStatusMsg(null), 5000);
    }
  };

  const handleSaveCalibration = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/calibration`, calibration);
      setCalibrationDirty(false);
      setStatusMsg({ type: 'success', text: 'Calibration saved.' });
    } catch {
      setStatusMsg({ type: 'error', text: 'Failed to save calibration.' });
    } finally {
      setSaving(false);
      setTimeout(() => setStatusMsg(null), 4000);
    }
  };

  const handleResetBaseline = async () => {
    try {
      const res = await axios.post(`${API}/calibration/reset`);
      setCalibration({
        reflection_intensity: res.data.data.reflection_intensity,
        consolidation_rate: res.data.data.consolidation_rate,
        exploration_variance: res.data.data.exploration_variance,
      });
      setCalibrationDirty(false);
      setStatusMsg({ type: 'success', text: 'Calibration reset to baseline.' });
    } catch {
      setStatusMsg({ type: 'error', text: 'Failed to reset calibration.' });
    } finally {
      setTimeout(() => setStatusMsg(null), 4000);
    }
  };

  const updateCalibration = (key: keyof Calibration, value: number) => {
    setCalibration(prev => ({ ...prev, [key]: value }));
    setCalibrationDirty(true);
  };

  // ── Derived values ────────────────────────────────
  const engineOk = stats?.engine_status === 'synchronized';
  const consolidationDisplay = (calibration.consolidation_rate / 1000).toFixed(2);
  const varianceDisplay = (calibration.exploration_variance / 100).toFixed(2);

  // ── Risk level colors ─────────────────────────────
  const riskColors: Record<string, string> = {
    low: 'bg-green-500',
    medium: 'bg-shogun-gold',
    high: 'bg-orange-500',
    critical: 'bg-red-500',
  };

  // ── Time ago helper ───────────────────────────────
  const timeAgo = (dateStr: string) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-6xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            Bushido <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">Reflection Engine</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">Monitor and calibrate the autonomous feedback loops that optimize agent precision.</p>
        </div>
        
        <div className="flex items-center gap-3">
           <div className="px-4 py-2 bg-shogun-card border border-shogun-border rounded-lg flex items-center gap-3">
              <div className={cn(
                "w-2 h-2 rounded-full shadow-[0_0_8px_rgba(34,197,94,0.6)]",
                engineOk ? "bg-green-500 animate-pulse" : "bg-orange-500 animate-pulse"
              )} />
              <span className="text-[10px] font-bold uppercase tracking-widest text-shogun-text">
                {stats ? (engineOk ? 'Engine Synchronized' : 'Engine Degraded') : 'Connecting...'}
              </span>
           </div>
           <button 
             onClick={handleForceReflection}
             disabled={reflecting}
             className="flex items-center gap-2 bg-shogun-blue hover:bg-shogun-blue/90 text-white font-bold py-2.5 px-6 rounded-lg transition-all shadow-shogun disabled:opacity-50"
           >
             <RefreshCw className={cn("w-4 h-4", reflecting && "animate-spin")} />
             {reflecting ? 'REFLECTING...' : 'FORCE REFLECTION'}
           </button>
        </div>
      </div>

      {/* Status Message */}
      {statusMsg && (
        <div className={cn(
          "p-4 rounded-lg flex items-center gap-3 animate-in slide-in-from-top-2",
          statusMsg.type === 'success' ? "bg-green-500/10 text-green-500 border border-green-500/20" : "bg-red-500/10 text-red-500 border border-red-500/20"
        )}>
          {statusMsg.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          <span className="text-sm font-bold uppercase tracking-widest">{statusMsg.text}</span>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
         {[
           { label: 'Avg Fit Quality', value: stats ? `${stats.fit_quality}%` : '—', icon: Target, color: 'text-shogun-gold' },
           { label: 'Active Cycles', value: stats ? stats.active_cycles.toLocaleString() : '—', icon: Activity, color: 'text-shogun-blue' },
           { label: 'Optimization Delta', value: stats ? `+${stats.optimization_delta}%` : '—', icon: TrendingUp, color: 'text-green-500' },
           { label: 'Neural Load', value: stats ? `${stats.neural_load}%` : '—', icon: BrainCircuit, color: stats && stats.neural_load > 75 ? 'text-red-400' : 'text-shogun-subdued' }
         ].map((stat, i) => (
           <div key={i} className="shogun-card border-b-2 border-transparent hover:border-shogun-blue transition-all group">
              <div className="flex items-center gap-2 mb-2">
                 <stat.icon className={cn("w-3.5 h-3.5", stat.color)} />
                 <span className="text-[9px] uppercase font-bold tracking-widest text-shogun-subdued">{stat.label}</span>
              </div>
              <div className="text-2xl font-bold text-shogun-text group-hover:scale-105 transition-transform origin-left">{stat.value}</div>
           </div>
         ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Tuning Controls */}
        <div className="lg:col-span-2 space-y-6">
           <div className="shogun-card space-y-8">
              <div className="flex items-center justify-between">
                 <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                    <Settings2 className="w-5 h-5 text-shogun-blue" /> Behavior Calibration
                 </h3>
                 <div className="flex items-center gap-2">
                   {calibrationDirty && (
                     <span className="text-[9px] text-orange-400 bg-orange-500/10 px-2 py-0.5 rounded border border-orange-500/20 font-bold uppercase">unsaved</span>
                   )}
                   <span className="text-[10px] text-shogun-subdued uppercase font-bold tracking-tighter italic">Behavioral Tuning v1.0</span>
                 </div>
              </div>

              <div className="space-y-10 py-4">
                 {/* Reflection Intensity */}
                 <div className="space-y-4">
                    <div className="flex justify-between items-center">
                       <label className="text-xs font-bold text-shogun-text flex items-center gap-2 uppercase tracking-wide">
                          <Flame className="w-3.5 h-3.5 text-orange-500" /> Reflection Intensity
                       </label>
                       <span className="text-xs font-mono text-shogun-blue">{calibration.reflection_intensity}%</span>
                    </div>
                    <input 
                      type="range" 
                      min="0" 
                      max="100" 
                      value={calibration.reflection_intensity}
                      onChange={(e) => updateCalibration('reflection_intensity', parseInt(e.target.value))}
                      className="w-full h-1.5 bg-shogun-card rounded-lg appearance-none cursor-pointer accent-shogun-blue"
                    />
                    <p className="text-[10px] text-shogun-subdued">Higher intensity increases token consumption but provides far deeper logical validation.</p>
                 </div>

                 {/* Memory Consolidation Rate */}
                 <div className="space-y-4">
                    <div className="flex justify-between items-center">
                       <label className="text-xs font-bold text-shogun-text flex items-center gap-2 uppercase tracking-wide">
                          <Binary className="w-3.5 h-3.5 text-shogun-gold" /> Memory Consolidation Rate
                       </label>
                       <span className="text-xs font-mono text-shogun-gold">{consolidationDisplay} / epoch</span>
                    </div>
                    <input 
                      type="range" 
                      min="0" 
                      max="100" 
                      value={calibration.consolidation_rate}
                      onChange={(e) => updateCalibration('consolidation_rate', parseInt(e.target.value))}
                      className="w-full h-1.5 bg-shogun-card rounded-lg appearance-none cursor-pointer accent-shogun-gold"
                    />
                    <p className="text-[10px] text-shogun-subdued">Frequency of episodic-to-semantic memory transformation cycles.</p>
                 </div>
                 
                 {/* Exploration Variance */}
                 <div className="space-y-4">
                    <div className="flex justify-between items-center">
                       <label className="text-xs font-bold text-shogun-text flex items-center gap-2 uppercase tracking-wide">
                          <Compass className="w-3.5 h-3.5 text-green-500" /> Exploration Variance
                       </label>
                       <span className="text-xs font-mono text-green-500">{varianceDisplay}</span>
                    </div>
                    <input 
                      type="range" 
                      min="0" 
                      max="100" 
                      value={calibration.exploration_variance}
                      onChange={(e) => updateCalibration('exploration_variance', parseInt(e.target.value))}
                      className="w-full h-1.5 bg-shogun-card rounded-lg appearance-none cursor-pointer accent-green-500"
                    />
                    <p className="text-[10px] text-shogun-subdued">Controls how much the agent explores novel approaches vs. sticking to proven patterns.</p>
                 </div>
              </div>

              <div className="pt-6 border-t border-shogun-border flex gap-4">
                 <button 
                   onClick={handleResetBaseline}
                   className="flex-1 py-3 bg-shogun-card border border-shogun-border rounded-xl text-xs font-bold uppercase tracking-widest hover:text-shogun-gold hover:border-shogun-gold transition-all flex items-center justify-center gap-2"
                 >
                    <RotateCcw className="w-3.5 h-3.5" /> Reset To Baseline
                 </button>
                 <button 
                   onClick={handleSaveCalibration}
                   disabled={saving || !calibrationDirty}
                   className="flex-1 py-3 bg-[#1e293b] border border-shogun-blue/30 rounded-xl text-xs font-bold uppercase tracking-widest text-shogun-text hover:bg-shogun-blue transition-all shadow-[0_0_15px_rgba(74,140,199,0.1)] disabled:opacity-50 flex items-center justify-center gap-2"
                 >
                    <Save className="w-3.5 h-3.5" /> {saving ? 'Saving...' : 'Save Calibration'}
                 </button>
              </div>
           </div>
        </div>

        {/* Sidebar */}
        <div className="lg:col-span-1 space-y-6">
           {/* Insight Stream */}
           <div className="shogun-card min-h-[300px]">
              <h3 className="text-sm font-bold flex items-center gap-2 text-shogun-gold mb-6 uppercase tracking-widest">
                 <Sparkles className="w-4 h-4" /> Insight Stream
                 <span className="text-[9px] text-shogun-subdued bg-shogun-card px-1.5 py-0.5 rounded border border-shogun-border ml-auto">{insights.length}</span>
              </h3>
              
              <div className="space-y-6">
                 {insights.length === 0 && (
                   <div className="text-[10px] text-shogun-subdued text-center py-8">
                     No recommendations yet. Run a Bushido job to generate insights.
                   </div>
                 )}
                 {insights.map((insight) => (
                   <div key={insight.id} className="flex gap-4 group">
                      <div className={cn(
                        "w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 group-hover:scale-150 transition-transform",
                        riskColors[insight.risk_level] || 'bg-shogun-blue'
                      )} />
                      <div>
                         <p className="text-[11px] text-shogun-text leading-relaxed">{insight.title}</p>
                         <span className="text-[9px] text-shogun-subdued block mt-1">{insight.description.slice(0, 120)}...</span>
                         <div className="flex items-center gap-2 mt-1">
                           <span className={cn(
                             "text-[8px] font-bold uppercase px-1 py-0.5 rounded",
                             insight.risk_level === 'high' ? 'text-orange-400 bg-orange-500/10' :
                             insight.risk_level === 'critical' ? 'text-red-400 bg-red-500/10' :
                             insight.risk_level === 'medium' ? 'text-shogun-gold bg-shogun-gold/10' :
                             'text-green-400 bg-green-500/10'
                           )}>
                             {insight.risk_level}
                           </span>
                           <span className="text-[8px] text-shogun-subdued font-bold uppercase">
                             {insight.created_at ? timeAgo(insight.created_at) : ''}
                           </span>
                         </div>
                      </div>
                   </div>
                 ))}
              </div>
           </div>

           {/* Formal Verification */}
           <div className="shogun-card bg-shogun-blue/5 border-shogun-blue/20">
              <div className="flex items-center gap-3 mb-3 text-shogun-blue">
                 <ShieldCheck className="w-4 h-4" />
                 <h4 className="text-[10px] font-bold uppercase tracking-widest">Formal Verification</h4>
              </div>
              <p className="text-[10px] text-shogun-subdued leading-relaxed">
                 The Bushido engine uses formal verification loops to ensure that all behavioral optimizations remain strictly within the bounds defined in the Kaizen constitution.
              </p>
           </div>
        </div>
      </div>
    </div>
  );
}
