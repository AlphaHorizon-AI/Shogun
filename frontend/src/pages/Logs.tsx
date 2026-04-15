import { useState, useEffect, useRef } from 'react';
import { 
  Terminal, 
  Search, 
  Download, 
  RefreshCw, 
  AlertCircle, 
  Info, 
  AlertTriangle,
  Activity,
  Filter
} from "lucide-react";
import axios from 'axios';
import { cn } from '../lib/utils';

export function Logs() {
  const [loading, setLoading] = useState(true);
  const [logs, setLogs] = useState<any[]>([]);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [minSeverity, setMinSeverity] = useState('INFO');
  
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchLogs();
    let interval: any;
    if (autoRefresh) {
      interval = setInterval(fetchLogs, 5000);
    }
    return () => clearInterval(interval);
  }, [autoRefresh, minSeverity]);

  const fetchLogs = async () => {
    try {
      const res = await axios.get(`/api/v1/logs${minSeverity !== 'ALL' ? `?severity=${minSeverity}` : ''}`);
      setLogs(res.data.data || []);
    } catch (error) {
      console.error('Error fetching logs:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (scrollRef.current && autoRefresh) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const filteredLogs = logs.filter(log => 
    log.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
    log.event_type?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getSeverityColor = (sev: string) => {
    switch(sev) {
      case 'ERROR': return 'text-red-500';
      case 'WARN': return 'text-shogun-gold';
      case 'CRITICAL': return 'text-shogun-gold bg-red-500/10 px-1 rounded animate-pulse';
      default: return 'text-shogun-blue';
    }
  };

  const getSeverityIcon = (sev: string) => {
    switch(sev) {
      case 'ERROR': return <AlertCircle className="w-3.5 h-3.5" />;
      case 'WARN': return <AlertTriangle className="w-3.5 h-3.5" />;
      default: return <Info className="w-3.5 h-3.5" />;
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-7xl mx-auto h-[calc(100vh-140px)] flex flex-col">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            System Logs <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">Audit Trail</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">Real-time telemetry and execution history across the Samurai lattice.</p>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="flex items-center bg-shogun-card border border-shogun-border rounded-lg p-1">
             <button 
               onClick={() => setAutoRefresh(true)}
               className={cn("px-3 py-1.5 text-[10px] font-bold uppercase rounded flex items-center gap-2 transition-all", autoRefresh ? "bg-shogun-blue text-white" : "text-shogun-subdued hover:text-shogun-text")}
             >
                <RefreshCw className={cn("w-3 h-3", autoRefresh && "animate-spin")} />
                Live
             </button>
             <button 
               onClick={() => setAutoRefresh(false)}
               className={cn("px-3 py-1.5 text-[10px] font-bold uppercase rounded flex items-center gap-2 transition-all", !autoRefresh ? "bg-[#1a2040] text-shogun-text" : "text-shogun-subdued hover:text-shogun-text")}
             >
                <Activity className="w-3 h-3" />
                Paused
             </button>
          </div>
          <button className="p-2.5 bg-shogun-card border border-shogun-border rounded-lg text-shogun-subdued hover:text-shogun-gold transition-colors">
            <Download className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 flex flex-col shogun-card !p-0 overflow-hidden border-shogun-blue/20">
        <div className="p-4 border-b border-shogun-border bg-[#050508]/80 flex items-center justify-between gap-4">
          <div className="flex items-center gap-4 flex-1">
            <div className="relative max-w-md w-full">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-shogun-subdued" />
              <input 
                type="text"
                placeholder="Search event history..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-shogun-bg border border-shogun-border rounded-lg pl-10 pr-4 py-2 text-xs focus:border-shogun-blue outline-none transition-all"
              />
            </div>
            
            <div className="flex items-center gap-2">
               <Filter className="w-3.5 h-3.5 text-shogun-subdued" />
               <select 
                 value={minSeverity}
                 onChange={(e) => setMinSeverity(e.target.value)}
                 className="bg-shogun-bg border border-shogun-border rounded-lg px-3 py-1.5 text-[10px] font-bold uppercase text-shogun-subdued outline-none focus:border-shogun-blue"
               >
                 <option value="ALL">All Levels</option>
                 <option value="INFO">Info+</option>
                 <option value="WARN">Warn+</option>
                 <option value="ERROR">Error Only</option>
               </select>
            </div>
          </div>
          
          <div className="flex items-center gap-3 text-[10px] text-shogun-subdued font-bold uppercase tracking-widest hidden lg:flex">
             <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-shogun-blue" /> Info</span>
             <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-shogun-gold" /> Warning</span>
             <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-red-500" /> Error</span>
          </div>
        </div>

        <div 
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-4 font-mono text-[11px] leading-relaxed bg-[#02040a] scrollbar-hide"
        >
          {loading && logs.length === 0 ? (
             <div className="h-full flex flex-col items-center justify-center opacity-30 gap-3">
                <Terminal className="w-10 h-10 animate-pulse" />
                <span className="uppercase tracking-[0.3em]">Establishing Uplink...</span>
             </div>
          ) : filteredLogs.length === 0 ? (
             <div className="h-full flex items-center justify-center text-shogun-subdued italic">
                No logs matching your current filters.
             </div>
          ) : filteredLogs.map((log, i) => (
            <div key={log.id || i} className="group flex items-start gap-4 py-1 hover:bg-white/5 transition-colors -mx-4 px-4 border-l-2 border-transparent hover:border-shogun-blue">
               <span className="text-shogun-subdued whitespace-nowrap opacity-50 select-none">[{new Date(log.created_at || Date.now()).toLocaleTimeString()}]</span>
               <div className={cn("flex items-center gap-2 w-20 font-bold uppercase tracking-tighter select-none", getSeverityColor(log.severity))}>
                  {getSeverityIcon(log.severity)}
                  {log.severity}
               </div>
               <div className="flex-1">
                  <span className="text-shogun-text font-medium">{log.message}</span>
                  {log.event_type && <span className="ml-3 text-[9px] bg-shogun-card px-1.5 py-0.5 rounded border border-shogun-border text-shogun-blue/70 font-bold uppercase tracking-widest">{log.event_type}</span>}
                  {log.duration_ms && <span className="ml-2 text-shogun-subdued opacity-50 italic">({log.duration_ms}ms)</span>}
               </div>
            </div>
          ))}
          <div className="h-4" />
        </div>

        <div className="p-3 bg-shogun-card/50 border-t border-shogun-border flex items-center justify-between text-[9px] text-shogun-subdued font-bold uppercase tracking-widest">
           <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5 text-shogun-blue">
                <Activity className="w-3 h-3" />
                Stream Healthy
              </span>
              <span>Loaded {logs.length} operations</span>
           </div>
           <div className="flex items-center gap-1">
              Terminal Node: <span className="text-shogun-text px-1 bg-shogun-bg border border-shogun-border rounded">Tenshu-Local-01</span>
           </div>
        </div>
      </div>
    </div>
  );
}
