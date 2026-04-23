import { useEffect, useState } from 'react';
import {
  Activity,
  Shield,
  Users,
  RefreshCw,
  Cpu,
  Server,
  Lock,
  Clock,
  ChevronRight,
  Plus,
  Settings,
  Power,
  Zap,
  LayoutGrid,
  TrendingUp,
  AlertCircle,
  ShieldAlert,
  X,
} from 'lucide-react';
import axios from 'axios';
import { cn } from '../lib/utils';
import { Link } from 'react-router-dom';
import { HarakiriModal } from '../components/HarakiriModal';
import { useTranslation } from '../i18n';

const StatCard = ({ title, value, status, icon: Icon, colorClass, trend, to }: any) => {
  const content = (
    <div className={cn("shogun-card group transition-all duration-300 relative overflow-hidden", to && "cursor-pointer hover:border-shogun-blue/50 hover:shadow-lg hover:shadow-shogun-blue/5")}>
      <div className="absolute -right-2 -bottom-2 opacity-[0.03] group-hover:opacity-[0.07] transition-opacity">
         <Icon className="w-24 h-24" />
      </div>
      <div className="flex justify-between items-start mb-4 relative z-10">
        <div className={cn("p-2 rounded-lg bg-opacity-10", colorClass.replace('text-', 'bg-'))}>
          <Icon className={cn("w-5 h-5", colorClass)} />
        </div>
        <div className="flex flex-col items-end">
          {status && (
            <span className={cn("text-[8px] uppercase font-bold px-2 py-0.5 rounded-full border mb-1", 
              status === 'healthy' || status === 'online' || status === 'active' ? "text-green-500 border-green-500/30 bg-green-500/5" : "text-shogun-gold border-shogun-gold/30 bg-shogun-gold/5")}>
              {status}
            </span>
          )}
          {trend && <span className="text-[9px] text-green-500 flex items-center gap-1 font-bold"><TrendingUp className="w-2.5 h-2.5" /> {trend}</span>}
        </div>
      </div>
      <div className="space-y-1 relative z-10">
        <h3 className="text-shogun-subdued text-[10px] font-bold uppercase tracking-widest">{title}</h3>
        <p className="text-2xl font-bold text-shogun-text group-hover:text-shogun-gold transition-colors">{value}</p>
      </div>
    </div>
  );
  return to ? <Link to={to} className="block">{content}</Link> : content;
};

export const Dashboard = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [posture, setPosture] = useState<any>(null);
  const [killWorking, setKillWorking] = useState(false);
  const [showHarakiri, setShowHarakiri] = useState(false);
  const [metrics, setMetrics] = useState<any>(null);
  const { t } = useTranslation();

  const fetchData = async () => {
    setLoading(true);
    try {
      const [overviewRes, postureRes] = await Promise.all([
        axios.get('/api/v1/system/overview'),
        axios.get('/api/v1/security/posture'),
      ]);
      setData(overviewRes.data.data);
      setPosture(postureRes.data.data);
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleKillSwitch = async () => {
    if (posture?.kill_switch_active) {
      if (!confirm(t('dashboard.reset_confirm', 'Reset Harakiri? Posture will be restored to TACTICAL.'))) return;
      setKillWorking(true);
      try {
        const res = await axios.delete('/api/v1/security/kill-switch');
        setPosture(res.data.data);
      } catch { /* ignore */ } finally { setKillWorking(false); }
      return;
    }
    // Activate — show two-step modal
    setShowHarakiri(true);
  };

  const confirmHarakiri = async () => {
    setShowHarakiri(false);
    setKillWorking(true);
    try {
      const res = await axios.post('/api/v1/security/kill-switch');
      setPosture(res.data.data);
    } catch { /* ignore */ } finally { setKillWorking(false); }
  };

  const fetchMetrics = async () => {
    try {
      const res = await axios.get('/api/v1/system/metrics');
      setMetrics(res.data.data);
    } catch { /* silent */ }
  };

  useEffect(() => {
    fetchData();
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-8 pb-12 animate-in fade-in duration-700">

      {/* ── Kill switch banner ── */}
      {posture?.kill_switch_active && (
        <div className="flex items-center justify-between gap-4 p-4 bg-red-500/10 border border-red-500/40 rounded-xl animate-pulse shadow-[0_0_30px_rgba(239,68,68,0.15)]">
          <div className="flex items-center gap-3">
            <ShieldAlert className="w-5 h-5 text-red-500 shrink-0" />
            <div>
              <span className="text-sm font-bold text-red-400 uppercase tracking-wider">{t('topbar.harakiri_active', '⛔ GLOBAL KILL-SWITCH ACTIVE')}</span>
              <p className="text-[10px] text-red-400/70 mt-0.5">{t('dashboard.harakiri_suspended', 'All autonomous agent activity is suspended. Posture locked to SHRINE.')}</p>
            </div>
          </div>
          <button
            onClick={handleKillSwitch}
            disabled={killWorking}
            className="flex items-center gap-2 px-4 py-2 bg-red-500 hover:bg-red-600 text-white font-bold text-xs rounded-lg transition-all shrink-0 disabled:opacity-50"
          >
            <X className="w-3.5 h-3.5" /> {t('topbar.reset_harakiri', 'Reset Kill Switch')}
          </button>
        </div>
      )}

      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-4xl font-bold shogun-title flex items-center gap-3">
            Tenshu <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-3 py-1 rounded border border-shogun-border uppercase tracking-[0.3em] ml-2">{t('dashboard.title_command_center', 'Command Center')}</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-2 font-medium">{t('dashboard.title_desc', 'Monitoring the Samurai lattice and autonomous behavioral loops.')}</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchData}
            disabled={loading}
            className="p-2.5 bg-shogun-card border border-shogun-border rounded-lg text-shogun-subdued hover:text-shogun-gold transition-colors"
          >
            <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
          </button>
          <Link to="/chat" className="flex items-center gap-2 bg-shogun-blue hover:bg-shogun-blue/90 text-white font-bold py-2.5 px-6 rounded-lg transition-all shadow-shogun">
            {t('dashboard.enter_command', 'ENTER COMMAND')} <ChevronRight className="w-4 h-4" />
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          title={t('dashboard.system_health', 'Neural Engine')} 
          value={data?.shogun_profile?.name || "Shogun Prime"} 
          status={data?.system_health?.runtime || 'online'} 
          icon={Cpu} 
          colorClass="text-shogun-blue"
          trend="+5.2%"
          to="/shogun"
        />
        <StatCard 
          title={t('dashboard.active_samurai', 'Active Lattice')} 
          value={`${data?.active_samurai?.length || 0} ${t('dashboard.samurai_unit', 'Samurai')}`} 
          status={t('dashboard.operational', 'operational')} 
          icon={Users} 
          colorClass="text-shogun-gold"
          trend={t('dashboard.grid_stable', 'Grid Stable')}
          to="/samurai"
        />
        <StatCard 
          title={t('dashboard.database', 'Knowledge Vol.')} 
          value={`${data?.knowledge_volume?.toLocaleString() || '1,248'} ${t('dashboard.records', 'Records')}`} 
          status={data?.system_health?.qdrant === 'healthy' ? t('dashboard.lattice_indexed', 'Lattice Indexed') : (data?.system_health?.qdrant || t('dashboard.indexed', 'indexed'))} 
          icon={Server} 
          colorClass={data?.system_health?.qdrant === 'healthy' ? "text-green-500" : "text-red-500"}
          trend={data?.system_health?.qdrant === 'healthy' ? t('dashboard.recall', '99.9% Recall') : t('dashboard.sync_error', 'Sync Error')}
          to="/archives"
        />
        <StatCard 
          title={t('dashboard.security_posture', 'Security Tier')} 
          value={data?.security_posture?.tier?.toUpperCase() || "GUARDED"} 
          status={t('common.active', 'Active')} 
          icon={Shield} 
          colorClass="text-red-500"
          to="/torii"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Feed */}
        <div className="lg:col-span-2 space-y-8">
          <div className="shogun-card overflow-hidden !p-0">
             <div className="p-5 border-b border-shogun-border bg-[#050508]/50 flex items-center justify-between">
                <h3 className="font-bold text-shogun-text flex items-center gap-3">
                  <LayoutGrid className="w-4 h-4 text-shogun-blue" />
                  {t('dashboard.active_deployment', 'Active Deployment Registry')}
                </h3>
                <Link to="/samurai" className="text-[10px] font-bold text-shogun-blue hover:text-shogun-gold uppercase tracking-widest transition-colors flex items-center gap-1">
                   {t('dashboard.full_fleet', 'Full Fleet')} <ChevronRight className="w-3 h-3" />
                </Link>
             </div>
             <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-shogun-border text-shogun-subdued uppercase text-[9px] tracking-widest bg-[#050508]/30">
                      <th className="p-5 font-bold">{t('dashboard.designation', 'Designation')}</th>
                      <th className="p-5 font-bold">{t('dashboard.current_task', 'Current Task')}</th>
                      <th className="p-5 font-bold">{t('dashboard.engagement', 'Engagement')}</th>
                      <th className="p-5 font-bold text-right">{t('dashboard.status', 'Status')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-shogun-border">
                    {(data?.active_samurai || []).map((s: any) => (
                      <tr key={s.id} className="group hover:bg-shogun-gold/5 transition-all">
                        <td className="p-5">
                           <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded bg-[#050508] border border-shogun-border flex items-center justify-center font-bold text-shogun-gold text-xs group-hover:border-shogun-gold/50">
                                 {s.name[0]}
                              </div>
                              <span className="font-bold text-shogun-text">{s.name}</span>
                           </div>
                        </td>
                        <td className="p-5 text-shogun-subdued text-xs font-medium">{s.current_task}</td>
                        <td className="p-5">
                           <div className="w-24 h-1.5 bg-shogun-card rounded-full overflow-hidden">
                              <div className="h-full bg-shogun-blue rounded-full" style={{ width: s.status === 'active' ? '85%' : '15%' }} />
                           </div>
                        </td>
                        <td className="p-5 text-right">
                           <span className={cn(
                             "text-[9px] px-2 py-0.5 rounded border font-bold uppercase tracking-tighter",
                             s.status === 'active' ? "text-green-500 border-green-500/20 bg-green-500/5" : "text-shogun-subdued border-shogun-subdued/20 bg-shogun-subdued/5"
                           )}>
                             {s.status}
                           </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
             </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
             <div className="shogun-card space-y-4">
                <h3 className="font-bold text-shogun-text flex items-center gap-2">
                   <Zap className="w-4 h-4 text-shogun-gold" /> {t('dashboard.quick_actions', 'Quick Actions')}
                </h3>
                <div className="grid grid-cols-2 gap-3">
                   <Link to="/samurai" className="flex flex-col items-center justify-center p-4 bg-[#050508] border border-shogun-border rounded-xl hover:border-shogun-gold transition-all group">
                      <Plus className="w-5 h-5 text-shogun-subdued group-hover:text-shogun-gold mb-2" />
                      <span className="text-[9px] font-bold uppercase tracking-widest text-shogun-subdued group-hover:text-shogun-text">{t('dashboard.new_samurai', 'New Samurai')}</span>
                   </Link>
                   <Link to="/katana" className="flex flex-col items-center justify-center p-4 bg-[#050508] border border-shogun-border rounded-xl hover:border-shogun-blue transition-all group">
                      <Settings className="w-5 h-5 text-shogun-subdued group-hover:text-shogun-blue mb-2" />
                      <span className="text-[9px] font-bold uppercase tracking-widest text-shogun-subdued group-hover:text-shogun-text">{t('dashboard.model_setup', 'Model Setup')}</span>
                   </Link>
                </div>
             </div>

              <div className="shogun-card flex flex-col justify-center items-center text-center space-y-3 bg-red-500/5 border-red-500/20">
                 <div className={cn(
                   'w-10 h-10 rounded-full flex items-center justify-center',
                   posture?.kill_switch_active ? 'bg-red-500 text-white animate-pulse' : 'bg-red-500/20 text-red-500'
                 )}>
                    <Power className="w-5 h-5" />
                 </div>
                 <div>
                    <h4 className="text-sm font-bold text-shogun-text">
                      {posture?.kill_switch_active ? t('dashboard.harakiri_activated', 'Harakiri Active') : t('dashboard.harakiri', 'Emergency Stop')}
                    </h4>
                    <p className="text-[10px] text-shogun-subdued mt-1 px-4">
                      {posture?.kill_switch_active
                        ? t('dashboard.harakiri_suspended', 'All agents suspended. Posture: SHRINE.')
                        : t('dashboard.harakiri_desc', 'Immediately suspend all active autonomous engagement.')}
                    </p>
                 </div>
                 <button
                   onClick={handleKillSwitch}
                   disabled={killWorking}
                   className={cn(
                     'flex items-center gap-3 text-white rounded-lg transition-all shadow-lg disabled:opacity-50 active:scale-95 px-5 py-2',
                     posture?.kill_switch_active
                       ? 'bg-green-600 hover:bg-green-700'
                       : 'bg-red-500 hover:bg-red-600'
                   )}
                 >
                   <Power className="w-4 h-4 shrink-0" />
                   <div className="flex flex-col items-start">
                     <span className="text-[10px] font-bold uppercase tracking-[0.2em] leading-tight">
                       {killWorking ? t('common.loading', 'Working...') : posture?.kill_switch_active ? t('topbar.reset_harakiri', 'Reset Harakiri') : t('dashboard.harakiri', 'Harakiri')}
                     </span>
                     {!killWorking && (
                       <span className="text-[8px] font-normal opacity-70 tracking-widest leading-tight">[{t('torii.kill_switch', 'Kill Switch')}]</span>
                     )}
                   </div>
                 </button>
              </div>
          </div>
        </div>

        {/* Recent Events Sidebar */}
        <div className="space-y-6">
           <div className="shogun-card h-full min-h-[500px] flex flex-col">
              <h3 className="font-bold text-shogun-text flex items-center gap-3 mb-6">
                <Clock className="w-4 h-4 text-shogun-blue" />
                {t('dashboard.recent_events', 'Telemetry Feed')}
              </h3>
              
              <div className="space-y-8 flex-1">
                 {(data?.recent_events || []).map((event: any, i: number) => (
                   <div key={i} className="flex gap-4 group">
                      <div className="flex flex-col items-center">
                         <div className={cn(
                           "p-1.5 rounded-lg border",
                           event.type === 'security' ? "text-red-500 border-red-500/30 bg-red-500/5" :
                           event.type === 'agent' ? "text-shogun-gold border-shogun-gold/30 bg-shogun-gold/5" : "text-shogun-blue border-shogun-blue/30 bg-shogun-blue/5"
                         )}>
                            {event.type === 'security' ? <Lock className="w-3 h-3" /> : event.type === 'agent' ? <Users className="w-3 h-3" /> : <Activity className="w-3 h-3" />}
                         </div>
                         {i < data.recent_events.length - 1 && <div className="w-px flex-1 bg-shogun-border my-2" />}
                      </div>
                      <div className="pb-4">
                         <p className="text-xs text-shogun-text font-medium leading-relaxed group-hover:text-shogun-gold transition-colors">{event.message}</p>
                         <span className="text-[9px] text-shogun-subdued uppercase font-bold mt-2 block tracking-widest">{event.timestamp}</span>
                      </div>
                   </div>
                 ))}
              </div>

               <div className="mt-8 p-4 bg-[#050508] border border-shogun-border rounded-xl">
                  <div className="flex items-center gap-3 mb-4">
                     <AlertCircle className="w-4 h-4 text-shogun-gold" />
                     <span className="text-[10px] font-bold uppercase tracking-widest text-shogun-text">{t('dashboard.system_load', 'System Load')}</span>
                  </div>
                  <div className="space-y-3">
                     {[
                       { label: t('dashboard.cpu_usage', 'CPU'), value: metrics?.cpu_percent ?? 0, detail: `${metrics?.cpu_percent ?? 0}%` },
                       { label: t('dashboard.memory_usage', 'Memory'), value: metrics?.memory_percent ?? 0, detail: `${metrics?.memory_used_gb ?? 0} / ${metrics?.memory_total_gb ?? 0} GB` },
                       { label: t('dashboard.disk_usage', 'Disk'), value: metrics?.disk_percent ?? 0, detail: `${metrics?.disk_used_gb ?? 0} / ${metrics?.disk_total_gb ?? 0} GB` },
                     ].map((m) => (
                       <div key={m.label}>
                         <div className="flex justify-between text-[10px] font-bold uppercase mb-1">
                            <span className="text-shogun-subdued">{m.label}</span>
                            <span className={cn(
                              m.value > 85 ? "text-red-500" : m.value > 60 ? "text-shogun-gold" : "text-green-500"
                            )}>{m.detail}</span>
                         </div>
                         <div className="w-full h-1 bg-shogun-card rounded-full overflow-hidden">
                            <div
                              className={cn(
                                "h-full rounded-full transition-all duration-700",
                                m.value > 85 ? "bg-red-500" : m.value > 60 ? "bg-shogun-gold" : "bg-green-500"
                              )}
                              style={{ width: `${m.value}%` }}
                            />
                         </div>
                       </div>
                     ))}
                  </div>
               </div>
           </div>
        </div>
      </div>

      {/* Harakiri two-step confirmation modal */}
      {showHarakiri && (
        <HarakiriModal
          onConfirm={confirmHarakiri}
          onCancel={() => setShowHarakiri(false)}
        />
      )}
    </div>
  );
};
