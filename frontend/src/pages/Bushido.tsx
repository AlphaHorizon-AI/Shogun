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
  Save,
  Clock,
  Bell,
  Plus,
  Pause,
  Play,
  Check,
  X,
  TimerReset,
  Workflow
} from "lucide-react";
import { cn } from '../lib/utils';
import { useTranslation } from '../i18n';

const API = '/api/v1/bushido';

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
  heartbeat_frequency: number;
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

interface Reminder {
  id: string;
  title: string;
  description?: string;
  schedule_type: string;
  schedule_time?: string;
  interval_minutes?: number;
  timezone: string;
  status: string;
  delivery_channel: string;
  next_run_at?: string;
  occurrence_count: number;
  origin: 'user' | 'ai' | 'system';
  item_type: string;
  reason?: string;
  confidence?: number;
  expires_at?: string;
}

interface FlowSchedule {
  id: string;
  name: string;
  frequency: string;
  schedule_time?: string;
  next_run_at?: string;
  scheduler_registered: boolean;
}

const DEFAULT_CALIBRATION: Calibration = {
  reflection_intensity: 70,
  consolidation_rate: 45,
  exploration_variance: 24,
  heartbeat_frequency: 15,
};

export function Bushido() {
  const { t } = useTranslation();
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
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [flowSchedules, setFlowSchedules] = useState<FlowSchedule[]>([]);
  const [boardView, setBoardView] = useState<'reminders' | 'flows'>('reminders');
  const [boardOrigin, setBoardOrigin] = useState<'all' | 'ai' | 'user' | 'system'>('all');
  const [showReminderForm, setShowReminderForm] = useState(false);
  const [reminderSaving, setReminderSaving] = useState(false);
  const [reminderForm, setReminderForm] = useState({
    title: '', description: '', schedule_type: 'one_time', run_at: '', schedule_time: '09:00',
    interval_minutes: 60, delivery_channel: 'web',
  });

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

  const loadReminderBoard = useCallback(async () => {
    try {
      const [reminderRes, scheduleRes] = await Promise.all([
        axios.get(`${API}/reminders`),
        axios.get(`${API}/schedules`),
      ]);
      setReminders(reminderRes.data.data || []);
      setFlowSchedules((scheduleRes.data.data || []).filter((item: { source?: string }) => item.source === 'agent_flow'));
    } catch { /* dashboard remains usable while the board reconnects */ }
  }, []);

  // ── Initial load ──────────────────────────────────
  useEffect(() => {
    loadStats();
    loadCalibration();
    loadInsights();
    loadReminderBoard();
  }, [loadStats, loadCalibration, loadInsights, loadReminderBoard]);

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
      setStatusMsg({ type: 'success', text: t('bushido.reflection_initiated') });
      // Refresh stats and insights after a delay
      setTimeout(() => { loadStats(); loadInsights(); }, 5000);
    } catch {
      setStatusMsg({ type: 'error', text: t('bushido.reflection_failed') });
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
      setStatusMsg({ type: 'success', text: t('bushido.calibration_saved') });
    } catch {
      setStatusMsg({ type: 'error', text: t('bushido.calibration_save_failed') });
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
        heartbeat_frequency: res.data.data.heartbeat_frequency,
      });
      setCalibrationDirty(false);
      setStatusMsg({ type: 'success', text: t('bushido.calibration_reset') });
    } catch {
      setStatusMsg({ type: 'error', text: t('bushido.calibration_reset_failed') });
    } finally {
      setTimeout(() => setStatusMsg(null), 4000);
    }
  };

  const updateCalibration = (key: keyof Calibration, value: number) => {
    setCalibration(prev => ({ ...prev, [key]: value }));
    setCalibrationDirty(true);
  };

  const handleCreateReminder = async () => {
    setReminderSaving(true);
    try {
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
      const payload: Record<string, unknown> = {
        title: reminderForm.title,
        description: reminderForm.description || null,
        schedule_type: reminderForm.schedule_type,
        timezone,
        delivery_channel: reminderForm.delivery_channel,
      };
      if (reminderForm.schedule_type === 'one_time') payload.run_at = new Date(reminderForm.run_at).toISOString();
      if (['daily', 'weekdays', 'weekly'].includes(reminderForm.schedule_type)) payload.schedule_time = reminderForm.schedule_time;
      if (reminderForm.schedule_type === 'weekly') payload.schedule_days = [new Date().getDay() === 0 ? 6 : new Date().getDay() - 1];
      if (reminderForm.schedule_type === 'interval') payload.interval_minutes = reminderForm.interval_minutes;
      await axios.post(`${API}/reminders`, payload);
      setReminderForm(prev => ({ ...prev, title: '', description: '', run_at: '' }));
      setShowReminderForm(false);
      setStatusMsg({ type: 'success', text: 'Reminder scheduled.' });
      await loadReminderBoard();
    } catch (error) {
      const message = axios.isAxiosError(error) ? error.response?.data?.detail : null;
      setStatusMsg({ type: 'error', text: typeof message === 'string' ? message : 'Could not schedule reminder.' });
    } finally {
      setReminderSaving(false);
      setTimeout(() => setStatusMsg(null), 4000);
    }
  };

  const handleReminderAction = async (id: string, action: 'pause' | 'resume' | 'snooze' | 'cancel' | 'complete') => {
    try {
      await axios.post(`${API}/reminders/${id}/${action}`, action === 'snooze' ? { minutes: 10 } : undefined);
      await loadReminderBoard();
    } catch {
      setStatusMsg({ type: 'error', text: `Could not ${action} reminder.` });
      setTimeout(() => setStatusMsg(null), 4000);
    }
  };

  const formatSchedule = (reminder: Reminder) => {
    if (reminder.next_run_at) return new Date(reminder.next_run_at).toLocaleString();
    return reminder.status.charAt(0).toUpperCase() + reminder.status.slice(1);
  };

  // ── Derived values ────────────────────────────────
  const engineOk = stats?.engine_status === 'synchronized';
  const consolidationDisplay = (calibration.consolidation_rate / 1000).toFixed(2);
  const varianceDisplay = (calibration.exploration_variance / 100).toFixed(2);
  const visibleBoardItems = boardOrigin === 'all' ? reminders : reminders.filter(item => item.origin === boardOrigin);

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
            {t('bushido.title')} <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">{t('bushido.badge')}</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">{t('bushido.subtitle')}</p>
        </div>
        
        <div className="flex items-center gap-3">
           <div className="px-4 py-2 bg-shogun-card border border-shogun-border rounded-lg flex items-center gap-3">
              <div className={cn(
                "w-2 h-2 rounded-full shadow-[0_0_8px_rgba(34,197,94,0.6)]",
                engineOk ? "bg-green-500 animate-pulse" : "bg-orange-500 animate-pulse"
              )} />
              <span className="text-[10px] font-bold uppercase tracking-widest text-shogun-text">
                {stats ? (engineOk ? t('bushido.engine_synchronized') : t('bushido.engine_degraded')) : t('bushido.connecting')}
              </span>
           </div>
           <button 
             onClick={handleForceReflection}
             disabled={reflecting}
             className="flex items-center gap-2 bg-shogun-blue hover:bg-shogun-blue/90 text-white font-bold py-2.5 px-6 rounded-lg transition-all shadow-shogun disabled:opacity-50"
           >
             <RefreshCw className={cn("w-4 h-4", reflecting && "animate-spin")} />
             {reflecting ? t('bushido.reflecting') : t('bushido.force_reflection')}
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

      {/* Reminder Board */}
      <section className="shogun-card space-y-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
              <Bell className="w-5 h-5 text-shogun-gold" /> Reminder Board
            </h3>
            <p className="text-[10px] text-shogun-subdued mt-1 uppercase tracking-widest">
              Shogun operational memory and user reminders
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="p-1 bg-black/20 border border-shogun-border rounded-lg flex">
              <button onClick={() => setBoardView('reminders')} className={cn(
                "px-3 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider transition-colors",
                boardView === 'reminders' ? "bg-shogun-blue text-white" : "text-shogun-subdued hover:text-shogun-text"
              )}>Board ({reminders.length})</button>
              <button onClick={() => setBoardView('flows')} className={cn(
                "px-3 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider transition-colors",
                boardView === 'flows' ? "bg-shogun-blue text-white" : "text-shogun-subdued hover:text-shogun-text"
              )}>AgentFlows ({flowSchedules.length})</button>
            </div>
            {boardView === 'reminders' && (
              <button onClick={() => setShowReminderForm(value => !value)} className="flex items-center gap-2 px-3 py-2 bg-shogun-gold/10 border border-shogun-gold/30 rounded-lg text-shogun-gold text-[10px] font-bold uppercase tracking-wider hover:bg-shogun-gold/20 transition-colors">
                <Plus className="w-3.5 h-3.5" /> New user reminder
              </button>
            )}
          </div>
        </div>

        {showReminderForm && boardView === 'reminders' && (
          <div className="p-4 rounded-xl border border-shogun-blue/30 bg-shogun-blue/5 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <input value={reminderForm.title} onChange={event => setReminderForm(prev => ({ ...prev, title: event.target.value }))} placeholder="What should I remind you about?" className="md:col-span-2 bg-black/20 border border-shogun-border rounded-lg px-3 py-2 text-sm text-shogun-text outline-none focus:border-shogun-blue" />
              <textarea value={reminderForm.description} onChange={event => setReminderForm(prev => ({ ...prev, description: event.target.value }))} placeholder="Optional details" rows={2} className="md:col-span-2 bg-black/20 border border-shogun-border rounded-lg px-3 py-2 text-sm text-shogun-text outline-none focus:border-shogun-blue resize-none" />
              <select value={reminderForm.schedule_type} onChange={event => setReminderForm(prev => ({ ...prev, schedule_type: event.target.value }))} className="bg-shogun-card border border-shogun-border rounded-lg px-3 py-2 text-xs text-shogun-text">
                <option value="one_time">One time</option><option value="daily">Daily</option><option value="weekdays">Weekdays</option><option value="weekly">Weekly</option><option value="interval">Interval</option>
              </select>
              {reminderForm.schedule_type === 'one_time' && <input type="datetime-local" value={reminderForm.run_at} onChange={event => setReminderForm(prev => ({ ...prev, run_at: event.target.value }))} className="bg-shogun-card border border-shogun-border rounded-lg px-3 py-2 text-xs text-shogun-text" />}
              {['daily', 'weekdays', 'weekly'].includes(reminderForm.schedule_type) && <input type="time" value={reminderForm.schedule_time} onChange={event => setReminderForm(prev => ({ ...prev, schedule_time: event.target.value }))} className="bg-shogun-card border border-shogun-border rounded-lg px-3 py-2 text-xs text-shogun-text" />}
              {reminderForm.schedule_type === 'interval' && <div className="flex items-center gap-2"><span className="text-[10px] uppercase text-shogun-subdued">Every</span><input type="number" min={1} value={reminderForm.interval_minutes} onChange={event => setReminderForm(prev => ({ ...prev, interval_minutes: Number(event.target.value) }))} className="w-full bg-shogun-card border border-shogun-border rounded-lg px-3 py-2 text-xs text-shogun-text" /><span className="text-[10px] uppercase text-shogun-subdued">minutes</span></div>}
              <select value={reminderForm.delivery_channel} onChange={event => setReminderForm(prev => ({ ...prev, delivery_channel: event.target.value }))} className="bg-shogun-card border border-shogun-border rounded-lg px-3 py-2 text-xs text-shogun-text">
                <option value="web">In-app</option><option value="telegram">Telegram</option><option value="teams">Teams</option><option value="both">All channels</option>
              </select>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowReminderForm(false)} className="px-4 py-2 text-[10px] uppercase font-bold text-shogun-subdued">Cancel</button>
              <button onClick={handleCreateReminder} disabled={reminderSaving || !reminderForm.title.trim() || (reminderForm.schedule_type === 'one_time' && !reminderForm.run_at)} className="px-4 py-2 rounded-lg bg-shogun-blue text-white text-[10px] uppercase font-bold disabled:opacity-40">{reminderSaving ? 'Scheduling...' : 'Schedule reminder'}</button>
            </div>
          </div>
        )}

        {boardView === 'reminders' ? (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-1 pb-2">
              {(['all', 'ai', 'user', 'system'] as const).map(origin => <button key={origin} onClick={() => setBoardOrigin(origin)} className={cn("px-2.5 py-1 rounded border text-[9px] font-bold uppercase tracking-wider", boardOrigin === origin ? 'border-shogun-blue/50 bg-shogun-blue/10 text-shogun-blue' : 'border-shogun-border text-shogun-subdued')}>{origin}</button>)}
              <span className="ml-auto text-[9px] text-shogun-subdued uppercase tracking-wider">Archives remember facts · this board tracks unresolved work</span>
            </div>
            {visibleBoardItems.length === 0 && <div className="py-8 text-center text-xs text-shogun-subdued border border-dashed border-shogun-border rounded-xl">No matching board items.</div>}
            {visibleBoardItems.map(reminder => (
              <div key={reminder.id} className="flex flex-col md:flex-row md:items-center gap-3 p-3 rounded-xl border border-shogun-border bg-black/10">
                <div className={cn("w-2 h-2 rounded-full shrink-0", reminder.status === 'due' ? 'bg-red-400 animate-pulse' : reminder.status === 'active' ? 'bg-green-500' : reminder.status === 'snoozed' ? 'bg-shogun-gold' : 'bg-shogun-subdued')} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={cn("text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border", reminder.origin === 'ai' ? 'text-purple-300 border-purple-500/30 bg-purple-500/10' : reminder.origin === 'system' ? 'text-orange-300 border-orange-500/30 bg-orange-500/10' : 'text-shogun-blue border-shogun-blue/30 bg-shogun-blue/10')}>{reminder.origin}</span>
                    <div className="text-sm font-bold text-shogun-text truncate">{reminder.title}</div>
                  </div>
                  {reminder.reason && <div className="text-[10px] text-shogun-subdued mt-1 line-clamp-2">Why: {reminder.reason}</div>}
                  <div className="text-[10px] text-shogun-subdued mt-1 flex flex-wrap gap-x-3 gap-y-1 uppercase tracking-wide">
                    <span>{reminder.item_type.replace('_', ' ')}</span><span>{formatSchedule(reminder)}</span><span>{reminder.delivery_channel}</span><span>{reminder.occurrence_count} reviews</span>{reminder.expires_at && <span>expires {new Date(reminder.expires_at).toLocaleString()}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  {['active', 'snoozed', 'due'].includes(reminder.status) && <button title="Snooze 10 minutes" onClick={() => handleReminderAction(reminder.id, 'snooze')} className="p-2 text-shogun-subdued hover:text-shogun-gold"><TimerReset className="w-4 h-4" /></button>}
                  {['active', 'snoozed', 'due'].includes(reminder.status) ? <button title="Pause" onClick={() => handleReminderAction(reminder.id, 'pause')} className="p-2 text-shogun-subdued hover:text-shogun-blue"><Pause className="w-4 h-4" /></button> : reminder.status === 'paused' && <button title="Resume" onClick={() => handleReminderAction(reminder.id, 'resume')} className="p-2 text-shogun-subdued hover:text-green-500"><Play className="w-4 h-4" /></button>}
                  {!['completed', 'cancelled'].includes(reminder.status) && <button title="Complete" onClick={() => handleReminderAction(reminder.id, 'complete')} className="p-2 text-shogun-subdued hover:text-green-500"><Check className="w-4 h-4" /></button>}
                  {!['completed', 'cancelled'].includes(reminder.status) && <button title="Cancel" onClick={() => handleReminderAction(reminder.id, 'cancel')} className="p-2 text-shogun-subdued hover:text-red-400"><X className="w-4 h-4" /></button>}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-[10px] text-shogun-subdued">Scheduled AgentFlows are shown here for visibility and remain managed by AgentFlow.</p>
            {flowSchedules.length === 0 && <div className="py-8 text-center text-xs text-shogun-subdued border border-dashed border-shogun-border rounded-xl">No scheduled AgentFlows.</div>}
            {flowSchedules.map(flow => <div key={flow.id} className="flex items-center gap-3 p-3 rounded-xl border border-shogun-border bg-black/10"><Workflow className="w-4 h-4 text-shogun-blue" /><div className="flex-1"><div className="text-sm font-bold text-shogun-text">{flow.name}</div><div className="text-[10px] text-shogun-subdued uppercase mt-1">{flow.frequency} {flow.schedule_time ? `at ${flow.schedule_time}` : ''} · {flow.next_run_at ? new Date(flow.next_run_at).toLocaleString() : 'No next run'}</div></div><span className={cn("text-[9px] font-bold uppercase px-2 py-1 rounded border", flow.scheduler_registered ? 'text-green-400 border-green-500/20 bg-green-500/10' : 'text-orange-400 border-orange-500/20 bg-orange-500/10')}>{flow.scheduler_registered ? 'Registered' : 'Not registered'}</span></div>)}
          </div>
        )}
      </section>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
         {[
           { label: t('bushido.avg_fit_quality'), value: stats ? `${stats.fit_quality}%` : '—', icon: Target, color: 'text-shogun-gold' },
           { label: t('bushido.active_cycles'), value: stats ? stats.active_cycles.toLocaleString() : '—', icon: Activity, color: 'text-shogun-blue' },
           { label: t('bushido.optimization_delta'), value: stats ? `+${stats.optimization_delta}%` : '—', icon: TrendingUp, color: 'text-green-500' },
           { label: t('bushido.neural_load'), value: stats ? `${stats.neural_load}%` : '—', icon: BrainCircuit, color: stats && stats.neural_load > 75 ? 'text-red-400' : 'text-shogun-subdued' }
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
                    <Settings2 className="w-5 h-5 text-shogun-blue" /> {t('bushido.behavior_calibration')}
                 </h3>
                 <div className="flex items-center gap-2">
                   {calibrationDirty && (
                     <span className="text-[9px] text-orange-400 bg-orange-500/10 px-2 py-0.5 rounded border border-orange-500/20 font-bold uppercase">{t('bushido.unsaved')}</span>
                   )}
                   <span className="text-[10px] text-shogun-subdued uppercase font-bold tracking-tighter italic">Behavioral Tuning v1.0</span>
                 </div>
              </div>

              <div className="space-y-10 py-4">
                 {/* Reflection Intensity */}
                 <div className="space-y-4">
                    <div className="flex justify-between items-center">
                       <label className="text-xs font-bold text-shogun-text flex items-center gap-2 uppercase tracking-wide">
                          <Flame className="w-3.5 h-3.5 text-orange-500" /> {t('bushido.reflection_intensity')}
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
                    <p className="text-[10px] text-shogun-subdued">{t('bushido.reflection_intensity_desc')}</p>
                 </div>

                 {/* Memory Consolidation Rate */}
                 <div className="space-y-4">
                    <div className="flex justify-between items-center">
                       <label className="text-xs font-bold text-shogun-text flex items-center gap-2 uppercase tracking-wide">
                          <Binary className="w-3.5 h-3.5 text-shogun-gold" /> {t('bushido.memory_consolidation_rate')}
                       </label>
                       <span className="text-xs font-mono text-shogun-gold">{consolidationDisplay} / {t('bushido.epoch')}</span>
                    </div>
                    <input 
                      type="range" 
                      min="0" 
                      max="100" 
                      value={calibration.consolidation_rate}
                      onChange={(e) => updateCalibration('consolidation_rate', parseInt(e.target.value))}
                      className="w-full h-1.5 bg-shogun-card rounded-lg appearance-none cursor-pointer accent-shogun-gold"
                    />
                    <p className="text-[10px] text-shogun-subdued">{t('bushido.memory_consolidation_desc')}</p>
                 </div>
                 
                 {/* Exploration Variance */}
                 <div className="space-y-4">
                    <div className="flex justify-between items-center">
                       <label className="text-xs font-bold text-shogun-text flex items-center gap-2 uppercase tracking-wide">
                          <Compass className="w-3.5 h-3.5 text-green-500" /> {t('bushido.exploration_variance')}
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
                    <p className="text-[10px] text-shogun-subdued">{t('bushido.exploration_variance_desc')}</p>
                 </div>

                 {/* Heartbeat Frequency */}
                 <div className="space-y-4">
                    <div className="flex justify-between items-center">
                       <label className="text-xs font-bold text-shogun-text flex items-center gap-2 uppercase tracking-wide">
                          <Clock className="w-3.5 h-3.5 text-purple-400" /> {t('bushido.heartbeat_frequency')}
                       </label>
                       <span className="text-xs font-mono text-purple-400">{calibration.heartbeat_frequency}m</span>
                    </div>
                    <input 
                      type="range" 
                      min="1" 
                      max="120" 
                      value={calibration.heartbeat_frequency}
                      onChange={(e) => updateCalibration('heartbeat_frequency', parseInt(e.target.value))}
                      className="w-full h-1.5 bg-shogun-card rounded-lg appearance-none cursor-pointer accent-purple-500"
                    />
                    <p className="text-[10px] text-shogun-subdued">{t('bushido.heartbeat_frequency_desc')}</p>
                 </div>
              </div>

              <div className="pt-6 border-t border-shogun-border flex gap-4">
                 <button 
                   onClick={handleResetBaseline}
                   className="flex-1 py-3 bg-shogun-card border border-shogun-border rounded-xl text-xs font-bold uppercase tracking-widest hover:text-shogun-gold hover:border-shogun-gold transition-all flex items-center justify-center gap-2"
                 >
                    <RotateCcw className="w-3.5 h-3.5" /> {t('bushido.reset_to_baseline')}
                 </button>
                 <button 
                   onClick={handleSaveCalibration}
                   disabled={saving || !calibrationDirty}
                   className="flex-1 py-3 bg-[#1e293b] border border-shogun-blue/30 rounded-xl text-xs font-bold uppercase tracking-widest text-shogun-text hover:bg-shogun-blue transition-all shadow-[0_0_15px_rgba(74,140,199,0.1)] disabled:opacity-50 flex items-center justify-center gap-2"
                 >
                    <Save className="w-3.5 h-3.5" /> {saving ? t('bushido.saving') : t('bushido.save_calibration')}
                 </button>
              </div>
           </div>
        </div>

        {/* Sidebar */}
        <div className="lg:col-span-1 space-y-6">
           {/* Insight Stream */}
           <div className="shogun-card min-h-[300px]">
              <h3 className="text-sm font-bold flex items-center gap-2 text-shogun-gold mb-6 uppercase tracking-widest">
                 <Sparkles className="w-4 h-4" /> {t('bushido.insight_stream')}
                 <span className="text-[9px] text-shogun-subdued bg-shogun-card px-1.5 py-0.5 rounded border border-shogun-border ml-auto">{insights.length}</span>
              </h3>
              
              <div className="space-y-6">
                 {insights.length === 0 && (
                   <div className="text-[10px] text-shogun-subdued text-center py-8">
                     {t('bushido.no_recommendations')}
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
                 <h4 className="text-[10px] font-bold uppercase tracking-widest">{t('bushido.formal_verification')}</h4>
              </div>
              <p className="text-[10px] text-shogun-subdued leading-relaxed">
                 {t('bushido.formal_verification_desc')}
              </p>
           </div>
        </div>
      </div>
    </div>
  );
}
