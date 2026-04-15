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
  AlertCircle
} from 'lucide-react';
import axios from 'axios';
import { cn } from '../lib/utils';
import { Link } from 'react-router-dom';

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

  const fetchData = async () => {
    setLoading(true);
    try {
      const resp = await axios.get('/api/v1/system/overview');
      setData(resp.data.data);
    } catch (err) {
      console.error("Failed to fetch dashboard data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <div className="space-y-8 pb-12 animate-in fade-in duration-700">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-4xl font-bold shogun-title flex items-center gap-3">
            Tenshu <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-3 py-1 rounded border border-shogun-border uppercase tracking-[0.3em] ml-2">Command Center</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-2 font-medium">Monitoring the Samurai lattice and autonomous behavioral loops.</p>
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
            ENTER COMMAND <ChevronRight className="w-4 h-4" />
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          title="Neural Engine" 
          value={data?.shogun_profile?.name || "Shogun Prime"} 
          status={data?.system_health?.runtime || 'online'} 
          icon={Cpu} 
          colorClass="text-shogun-blue"
          trend="+5.2%"
          to="/shogun"
        />
        <StatCard 
          title="Active Lattice" 
          value={`${data?.active_samurai?.length || 0} Samurai`} 
          status="operational" 
          icon={Users} 
          colorClass="text-shogun-gold"
          trend="Grid Stable"
          to="/samurai"
        />
        <StatCard 
          title="Knowledge Vol." 
          value="1,248 Records" 
          status={data?.system_health?.qdrant === 'healthy' ? 'Lattice Indexed' : (data?.system_health?.qdrant || 'indexed')} 
          icon={Server} 
          colorClass={data?.system_health?.qdrant === 'healthy' ? "text-green-500" : "text-red-500"}
          trend={data?.system_health?.qdrant === 'healthy' ? "99.9% Recall" : "Sync Error"}
          to="/archives"
        />
        <StatCard 
          title="Security Tier" 
          value={data?.security_posture?.tier?.toUpperCase() || "GUARDED"} 
          status="Active" 
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
                  Active Deployment Registry
                </h3>
                <Link to="/samurai" className="text-[10px] font-bold text-shogun-blue hover:text-shogun-gold uppercase tracking-widest transition-colors flex items-center gap-1">
                   Full Fleet <ChevronRight className="w-3 h-3" />
                </Link>
             </div>
             <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-shogun-border text-shogun-subdued uppercase text-[9px] tracking-widest bg-[#050508]/30">
                      <th className="p-5 font-bold">Designation</th>
                      <th className="p-5 font-bold">Current Task</th>
                      <th className="p-5 font-bold">Engagement</th>
                      <th className="p-5 font-bold text-right">Status</th>
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
                   <Zap className="w-4 h-4 text-shogun-gold" /> Quick Actions
                </h3>
                <div className="grid grid-cols-2 gap-3">
                   <Link to="/samurai" className="flex flex-col items-center justify-center p-4 bg-[#050508] border border-shogun-border rounded-xl hover:border-shogun-gold transition-all group">
                      <Plus className="w-5 h-5 text-shogun-subdued group-hover:text-shogun-gold mb-2" />
                      <span className="text-[9px] font-bold uppercase tracking-widest text-shogun-subdued group-hover:text-shogun-text">New Samurai</span>
                   </Link>
                   <Link to="/katana" className="flex flex-col items-center justify-center p-4 bg-[#050508] border border-shogun-border rounded-xl hover:border-shogun-blue transition-all group">
                      <Settings className="w-5 h-5 text-shogun-subdued group-hover:text-shogun-blue mb-2" />
                      <span className="text-[9px] font-bold uppercase tracking-widest text-shogun-subdued group-hover:text-shogun-text">Model Setup</span>
                   </Link>
                </div>
             </div>

             <div className="shogun-card flex flex-col justify-center items-center text-center space-y-3 bg-red-500/5 border-red-500/20">
                <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center text-red-500">
                   <Power className="w-5 h-5" />
                </div>
                <div>
                   <h4 className="text-sm font-bold text-shogun-text">Emergency Stop</h4>
                   <p className="text-[10px] text-shogun-subdued mt-1 px-4">Immediately suspend all active autonomous engagement.</p>
                </div>
                <button className="px-4 py-1.5 bg-red-500 hover:bg-red-600 text-white text-[10px] font-bold uppercase tracking-[0.2em] rounded-lg transition-all shadow-lg">
                   Launch Killswitch
                </button>
             </div>
          </div>
        </div>

        {/* Recent Events Sidebar */}
        <div className="space-y-6">
           <div className="shogun-card h-full min-h-[500px] flex flex-col">
              <h3 className="font-bold text-shogun-text flex items-center gap-3 mb-6">
                <Clock className="w-4 h-4 text-shogun-blue" />
                Telemetry Feed
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
                 <div className="flex items-center gap-3 mb-3">
                    <AlertCircle className="w-4 h-4 text-shogun-gold" />
                    <span className="text-[10px] font-bold uppercase tracking-widest text-shogun-text">System Load</span>
                 </div>
                 <div className="space-y-2">
                    <div className="flex justify-between text-[10px] text-shogun-subdued font-bold uppercase">
                       <span>CPU Affinity</span>
                       <span>12%</span>
                    </div>
                    <div className="w-full h-1 bg-shogun-card rounded-full overflow-hidden">
                       <div className="h-full bg-shogun-gold" style={{ width: '12%' }} />
                    </div>
                 </div>
              </div>
           </div>
        </div>
      </div>
    </div>
  );
};
