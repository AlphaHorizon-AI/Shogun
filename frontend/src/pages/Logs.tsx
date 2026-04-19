import { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Terminal, 
  Search, 
  Download, 
  RefreshCw, 
  AlertCircle, 
  Info, 
  AlertTriangle,
  Activity,
  Filter,
  Trash2,
  Loader2,
} from "lucide-react";
import axios from 'axios';
import { cn } from '../lib/utils';

// ── Types ─────────────────────────────────────────────────────

interface LogEntry {
  id: string;
  mission_id: string | null;
  agent_id: string | null;
  event_type: string;
  severity: string;       // lowercase from DB: 'info' | 'warn' | 'error' | 'critical'
  summary: string;        // the actual log message field
  payload: Record<string, any>;
  occurred_at: string;    // ISO timestamp
}

// ── Helpers ───────────────────────────────────────────────────

function normSev(sev: string) { return sev?.toLowerCase() || 'info'; }

function getSeverityColor(sev: string) {
  switch (normSev(sev)) {
    case 'error':    return 'text-red-500';
    case 'critical': return 'text-red-400 bg-red-500/10 px-1 rounded animate-pulse';
    case 'warn':     return 'text-yellow-400';
    default:         return 'text-shogun-blue';
  }
}

function getSeverityIcon(sev: string) {
  switch (normSev(sev)) {
    case 'error':
    case 'critical': return <AlertCircle className="w-3.5 h-3.5" />;
    case 'warn':     return <AlertTriangle className="w-3.5 h-3.5" />;
    default:         return <Info className="w-3.5 h-3.5" />;
  }
}

// ── Component ─────────────────────────────────────────────────

export function Logs() {
  const [loading, setLoading] = useState(true);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [minSeverity, setMinSeverity] = useState('all');   // 'all' | 'info' | 'warn' | 'error'
  const [clearing, setClearing] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Fetch ──────────────────────────────────────────────────

  const fetchLogs = useCallback(async () => {
    try {
      const params: Record<string, string> = {};
      if (minSeverity !== 'all') params.severity = minSeverity;
      const res = await axios.get('/api/v1/logs', { params });
      // API returns newest-first; reverse so oldest is at top (auto-scroll to bottom = latest)
      const data: LogEntry[] = res.data.data || [];
      setLogs([...data].reverse());
    } catch (error) {
      console.error('Error fetching logs:', error);
    } finally {
      setLoading(false);
    }
  }, [minSeverity]);

  useEffect(() => {
    setLoading(true);
    fetchLogs();
  }, [minSeverity]);

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (autoRefresh) {
      intervalRef.current = setInterval(fetchLogs, 5000);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [autoRefresh, fetchLogs]);

  // Auto-scroll to bottom on new data
  useEffect(() => {
    if (autoRefresh && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  // ── Client-side search (across already-filtered data) ──────

  const filteredLogs = logs.filter(log => {
    const term = searchTerm.toLowerCase();
    return (
      log.summary?.toLowerCase().includes(term) ||
      log.event_type?.toLowerCase().includes(term) ||
      log.severity?.toLowerCase().includes(term)
    );
  });

  // ── Download ───────────────────────────────────────────────

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const params: Record<string, string> = { limit: '5000' };
      if (minSeverity !== 'all') params.severity = minSeverity;
      const res = await axios.get('/api/v1/logs', { params });
      const data: LogEntry[] = res.data.data || [];
      const lines = data.map(l =>
        `[${l.occurred_at}] [${l.severity.toUpperCase()}] [${l.event_type}] ${l.summary}`
      ).join('\n');
      const blob = new Blob([lines], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `shogun_logs_${new Date().toISOString().slice(0, 10)}.txt`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) { console.error('Download failed', e); }
    finally { setDownloading(false); }
  };

  // ── Clear ──────────────────────────────────────────────────

  const handleClear = async () => {
    if (!confirm('Clear all log entries from the database? This cannot be undone.')) return;
    setClearing(true);
    try {
      await axios.delete('/api/v1/logs');
      setLogs([]);
    } catch (e) { console.error('Clear failed', e); }
    finally { setClearing(false); }
  };

  // ── Counts for status bar ──────────────────────────────────

  const errorCount  = logs.filter(l => normSev(l.severity) === 'error' || normSev(l.severity) === 'critical').length;
  const warnCount   = logs.filter(l => normSev(l.severity) === 'warn').length;

  // ── Render ─────────────────────────────────────────────────

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-7xl mx-auto h-[calc(100vh-140px)] flex flex-col">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            System Logs
            <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">Audit Trail</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">Real-time telemetry and execution history across the Samurai lattice.</p>
        </div>

        <div className="flex items-center gap-3">
          {/* Live / Paused toggle */}
          <div className="flex items-center bg-shogun-card border border-shogun-border rounded-lg p-1">
            <button
              onClick={() => setAutoRefresh(true)}
              className={cn("px-3 py-1.5 text-[10px] font-bold uppercase rounded flex items-center gap-2 transition-all",
                autoRefresh ? "bg-shogun-blue text-white" : "text-shogun-subdued hover:text-shogun-text")}
            >
              <RefreshCw className={cn("w-3 h-3", autoRefresh && "animate-spin")} /> Live
            </button>
            <button
              onClick={() => setAutoRefresh(false)}
              className={cn("px-3 py-1.5 text-[10px] font-bold uppercase rounded flex items-center gap-2 transition-all",
                !autoRefresh ? "bg-[#1a2040] text-shogun-text" : "text-shogun-subdued hover:text-shogun-text")}
            >
              <Activity className="w-3 h-3" /> Paused
            </button>
          </div>

          {/* Download */}
          <button
            onClick={handleDownload}
            disabled={downloading}
            title="Download logs as .txt"
            className="p-2.5 bg-shogun-card border border-shogun-border rounded-lg text-shogun-subdued hover:text-shogun-gold transition-colors disabled:opacity-40"
          >
            {downloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
          </button>

          {/* Clear */}
          <button
            onClick={handleClear}
            disabled={clearing}
            title="Clear all logs"
            className="p-2.5 bg-shogun-card border border-shogun-border rounded-lg text-shogun-subdued hover:text-red-400 transition-colors disabled:opacity-40"
          >
            {clearing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Log Panel */}
      <div className="flex-1 flex flex-col shogun-card !p-0 overflow-hidden border-shogun-blue/20">
        {/* Toolbar */}
        <div className="p-4 border-b border-shogun-border bg-[#050508]/80 flex items-center justify-between gap-4">
          <div className="flex items-center gap-4 flex-1">
            {/* Search */}
            <div className="relative max-w-md w-full">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-shogun-subdued" />
              <input
                type="text"
                placeholder="Search events, types..."
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                className="w-full bg-shogun-bg border border-shogun-border rounded-lg pl-10 pr-4 py-2 text-xs focus:border-shogun-blue outline-none transition-all"
              />
            </div>

            {/* Severity filter */}
            <div className="flex items-center gap-2">
              <Filter className="w-3.5 h-3.5 text-shogun-subdued" />
              <select
                value={minSeverity}
                onChange={e => setMinSeverity(e.target.value)}
                className="bg-shogun-bg border border-shogun-border rounded-lg px-3 py-1.5 text-[10px] font-bold uppercase text-shogun-subdued outline-none focus:border-shogun-blue"
              >
                <option value="all">All Levels</option>
                <option value="info">Info</option>
                <option value="warn">Warn</option>
                <option value="error">Error</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>

          {/* Legend */}
          <div className="hidden lg:flex items-center gap-3 text-[10px] text-shogun-subdued font-bold uppercase tracking-widest">
            <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-shogun-blue" /> Info</span>
            <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-yellow-400" /> Warn</span>
            <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-red-500" /> Error</span>
          </div>
        </div>

        {/* Log lines */}
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
            <div
              key={log.id || i}
              className="group flex items-start gap-4 py-1 hover:bg-white/5 transition-colors -mx-4 px-4 border-l-2 border-transparent hover:border-shogun-blue"
            >
              {/* Timestamp */}
              <span className="text-shogun-subdued whitespace-nowrap opacity-50 select-none">
                [{new Date(log.occurred_at).toLocaleTimeString()}]
              </span>

              {/* Severity badge */}
              <div className={cn("flex items-center gap-1.5 w-20 font-bold uppercase tracking-tighter select-none flex-shrink-0", getSeverityColor(log.severity))}>
                {getSeverityIcon(log.severity)}
                {log.severity.toUpperCase()}
              </div>

              {/* Message + tags */}
              <div className="flex-1 flex flex-wrap items-baseline gap-2">
                <span className="text-shogun-text font-medium">{log.summary}</span>
                {log.event_type && (
                  <span className="text-[9px] bg-shogun-card px-1.5 py-0.5 rounded border border-shogun-border text-shogun-blue/70 font-bold uppercase tracking-widest">
                    {log.event_type}
                  </span>
                )}
                {log.agent_id && (
                  <span className="text-[9px] text-shogun-subdued/50 font-mono">
                    agent:{log.agent_id.slice(0, 8)}
                  </span>
                )}
                {log.mission_id && (
                  <span className="text-[9px] text-shogun-subdued/50 font-mono">
                    mission:{log.mission_id.slice(0, 8)}
                  </span>
                )}
              </div>
            </div>
          ))}
          <div className="h-4" />
        </div>

        {/* Status bar */}
        <div className="p-3 bg-shogun-card/50 border-t border-shogun-border flex items-center justify-between text-[9px] text-shogun-subdued font-bold uppercase tracking-widest">
          <div className="flex items-center gap-4">
            <span className={cn("flex items-center gap-1.5", autoRefresh ? "text-shogun-blue" : "text-shogun-subdued")}>
              <Activity className="w-3 h-3" />
              {autoRefresh ? 'Live · 5s' : 'Paused'}
            </span>
            <span>{filteredLogs.length} / {logs.length} events</span>
            {errorCount > 0 && (
              <span className="flex items-center gap-1 text-red-400">
                <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                {errorCount} error{errorCount !== 1 ? 's' : ''}
              </span>
            )}
            {warnCount > 0 && (
              <span className="flex items-center gap-1 text-yellow-400">
                <div className="w-1.5 h-1.5 rounded-full bg-yellow-400" />
                {warnCount} warn{warnCount !== 1 ? 's' : ''}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            Terminal Node: <span className="text-shogun-text px-1 bg-shogun-bg border border-shogun-border rounded ml-1">Tenshu-Local-01</span>
          </div>
        </div>
      </div>
    </div>
  );
}
