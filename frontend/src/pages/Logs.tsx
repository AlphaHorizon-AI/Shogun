import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Terminal, Search, Download, RefreshCw, AlertCircle, Info,
  Activity, Filter, Trash2, Loader2, Shield, Brain, Wrench, Cpu, FileKey,
  Zap, Link2, CheckCircle2, XCircle, X, Scale, Eye, AlertOctagon
} from "lucide-react";
import axios from 'axios';
import { useSearchParams } from '../lib/routerCompat';
import { cn } from '../lib/utils';
import { useTranslation } from '../i18n';

interface LogEntry {
  id: string;
  event_id: string;
  mission_id: string | null;
  agent_id: string | null;
  user_id: string | null;
  session_id: string | null;
  trace_id: string | null;
  event_category: string;
  event_type: string;
  severity: string;
  action: string;
  summary: string;
  result: string;
  model_used: string | null;
  provider_used: string | null;
  tool_name: string | null;
  policy_ref: string | null;
  policy_decision: string | null;
  policy_reason: string | null;
  risk_score: string | null;
  detail: Record<string, any>;
  payload: Record<string, any>;
  memory_ids: string[];
  ip_address: string | null;
  occurred_at: string;
  duration_ms: number | null;
  // EU AI Act governance
  confidence_score: number | null;
  governance_flags: Record<string, any>;
  use_case_context: Record<string, any>;
}

interface AuditVerification {
  total_records: number;
  verified_records: number;
  chain_intact: boolean;
  broken_at?: number;
  message: string;
}

const CATEGORIES = [
  { key: 'all', label: 'All Events', icon: Terminal, color: 'text-shogun-blue' },
  { key: 'decision', label: 'Decision', icon: Scale, color: 'text-violet-400' },
  { key: 'oversight', label: 'Oversight', icon: Eye, color: 'text-amber-400' },
  { key: 'risk', label: 'Risk', icon: AlertOctagon, color: 'text-rose-400' },
  { key: 'model', label: 'Model', icon: Cpu, color: 'text-shogun-gold' },
  { key: 'policy', label: 'Policy', icon: Shield, color: 'text-blue-400' },
  { key: 'memory', label: 'Memory', icon: Brain, color: 'text-cyan-400' },
  { key: 'tool', label: 'Tools', icon: Wrench, color: 'text-green-400' },
  { key: 'auth', label: 'Auth', icon: Shield, color: 'text-purple-400' },
  { key: 'incident', label: 'Incident', icon: Zap, color: 'text-red-400' },
  { key: 'system', label: 'System', icon: Activity, color: 'text-shogun-subdued' },
];

function normSev(sev: string) { return sev?.toLowerCase() || 'info'; }

function getSeverityStyle(sev: string) {
  switch (normSev(sev)) {
    case 'critical': return 'text-red-400 bg-red-500/10 border-red-500/30';
    case 'error': return 'text-red-500 bg-red-500/5 border-red-500/20';
    case 'warn': return 'text-yellow-400 bg-yellow-500/5 border-yellow-500/20';
    default: return 'text-shogun-blue bg-shogun-blue/5 border-shogun-blue/20';
  }
}

function getCategoryIcon(cat: string) {
  const found = CATEGORIES.find(c => c.key === cat);
  return found ? found : CATEGORIES[0];
}

function getResultIcon(result: string) {
  switch (result?.toLowerCase()) {
    case 'success': return <CheckCircle2 className="w-3 h-3 text-green-500" />;
    case 'denied': return <XCircle className="w-3 h-3 text-red-400" />;
    case 'error': return <AlertCircle className="w-3 h-3 text-red-500" />;
    default: return <Info className="w-3 h-3 text-shogun-subdued" />;
  }
}

export function Logs() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const targetEventId = searchParams.get('event_id');
  const targetTraceId = searchParams.get('trace_id');
  const targetNodeId = searchParams.get('node_id');
  const targetEventType = searchParams.get('event_type');
  const [loading, setLoading] = useState(true);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [minSeverity, setMinSeverity] = useState('all');
  const [activeCategory, setActiveCategory] = useState('all');
  const [clearing, setClearing] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<LogEntry | null>(null);
  const [traceEvents, setTraceEvents] = useState<LogEntry[]>([]);
  const [showTrace, setShowTrace] = useState(false);
  const [auditStatus, setAuditStatus] = useState<AuditVerification | null>(null);
  const [categoryCounts, setCategoryCounts] = useState<Record<string, number>>({});

  const scrollRef = useRef<HTMLDivElement>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch logs
  const fetchLogs = useCallback(async () => {
    try {
      const params: Record<string, string> = { limit: '300' };
      if (targetEventId) {
        params.event_id = targetEventId;
      } else {
        if (minSeverity !== 'all') params.severity = minSeverity;
        if (activeCategory !== 'all') params.category = activeCategory;
        if (targetTraceId) params.trace_id = targetTraceId;
        if (targetEventType) params.event_type = targetEventType;
      }
      const res = await axios.get('/api/v1/logs', { params });
      const data: LogEntry[] = res.data.data || [];
      setLogs([...data].reverse());
      const linkedEvent = data.find((entry) =>
        (targetEventId && entry.event_id === targetEventId)
        || (targetNodeId && entry.detail?.node_id === targetNodeId)
      );
      if (linkedEvent) {
        setSelectedEvent(linkedEvent);
        setAutoRefresh(false);
      }
    } catch (error) {
      console.error('Error fetching logs:', error);
    } finally {
      setLoading(false);
    }
  }, [minSeverity, activeCategory, targetEventId, targetTraceId, targetNodeId, targetEventType]);

  // Fetch category counts
  const fetchCategories = useCallback(async () => {
    try {
      const res = await axios.get('/api/v1/logs/categories');
      setCategoryCounts(res.data.data?.categories || {});
    } catch { /* silent */ }
  }, []);

  // Fetch audit status
  const fetchAuditStatus = useCallback(async () => {
    try {
      const res = await axios.get('/api/v1/logs/audit/verify');
      setAuditStatus(res.data.data);
    } catch { /* silent */ }
  }, []);

  // Fetch trace
  const fetchTrace = useCallback(async (traceId: string) => {
    try {
      const res = await axios.get(`/api/v1/logs/trace/${traceId}`);
      setTraceEvents(res.data.data || []);
      setShowTrace(true);
    } catch { /* silent */ }
  }, []);

  useEffect(() => { setLoading(true); fetchLogs(); fetchCategories(); fetchAuditStatus(); }, [fetchLogs, fetchCategories, fetchAuditStatus]);

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (autoRefresh) {
      intervalRef.current = setInterval(() => { fetchLogs(); fetchCategories(); }, 5000);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [autoRefresh, fetchLogs, fetchCategories]);

  useEffect(() => {
    if (autoRefresh && scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [logs]);

  const filteredLogs = logs.filter(log => {
    const term = searchTerm.toLowerCase();
    return (
      log.action?.toLowerCase().includes(term) ||
      log.event_type?.toLowerCase().includes(term) ||
      log.tool_name?.toLowerCase().includes(term) ||
      log.model_used?.toLowerCase().includes(term) ||
      log.trace_id?.toLowerCase().includes(term) ||
      log.event_id?.toLowerCase().includes(term) ||
      JSON.stringify(log.detail || {}).toLowerCase().includes(term)
    );
  });

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const res = await axios.get('/api/v1/logs/audit/export', {
        params: { format: 'json', limit: '10000' },
        responseType: 'blob',
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `shogun_audit_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) { console.error('Download failed', e); }
    finally { setDownloading(false); }
  };

  const handleClear = async () => {
    if (!confirm('Clear operational logs? The immutable audit chain will NOT be affected.')) return;
    setClearing(true);
    try {
      await axios.delete('/api/v1/logs');
      setLogs([]);
      fetchCategories();
    } catch (e) { console.error('Clear failed', e); }
    finally { setClearing(false); }
  };

  const errorCount = logs.filter(l => normSev(l.severity) === 'error' || normSev(l.severity) === 'critical').length;
  const totalEvents = Object.values(categoryCounts).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-5 animate-in fade-in duration-500 max-w-[1400px] mx-auto h-[calc(100vh-140px)] flex flex-col">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            {t('logs.title', 'Event Log')}
            <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">Compliance Ready</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">{t('logs.subtitle', 'Compliance-grade event stream with full trace reconstruction.')}</p>
        </div>

        <div className="flex items-center gap-3">
          {/* Audit chain status */}
          {auditStatus && (
            <div className={cn(
              "px-3 py-2 rounded-lg border flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest",
              auditStatus.chain_intact
                ? "bg-green-500/5 border-green-500/20 text-green-500"
                : "bg-red-500/10 border-red-500/30 text-red-400 animate-pulse"
            )}>
              {auditStatus.chain_intact ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
              {auditStatus.chain_intact ? 'Chain Intact' : 'Chain Broken'}
              <span className="text-[8px] opacity-60 ml-1">{auditStatus.total_records} records</span>
            </div>
          )}

          <div className="flex items-center bg-shogun-card border border-shogun-border rounded-lg p-1">
            <button onClick={() => setAutoRefresh(true)}
              className={cn("px-3 py-1.5 text-[10px] font-bold uppercase rounded flex items-center gap-2 transition-all",
                autoRefresh ? "bg-shogun-blue text-white" : "text-shogun-subdued hover:text-shogun-text")}>
              <RefreshCw className={cn("w-3 h-3", autoRefresh && "animate-spin")} /> Live
            </button>
            <button onClick={() => setAutoRefresh(false)}
              className={cn("px-3 py-1.5 text-[10px] font-bold uppercase rounded flex items-center gap-2 transition-all",
                !autoRefresh ? "bg-[#1a2040] text-shogun-text" : "text-shogun-subdued hover:text-shogun-text")}>
              <Activity className="w-3 h-3" /> Paused
            </button>
          </div>

          <button onClick={handleDownload} disabled={downloading} title="Export immutable audit log"
            className="p-2.5 bg-shogun-card border border-shogun-border rounded-lg text-shogun-subdued hover:text-shogun-gold transition-colors disabled:opacity-40">
            {downloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
          </button>
          <button onClick={handleClear} disabled={clearing} title="Clear operational logs"
            className="p-2.5 bg-shogun-card border border-shogun-border rounded-lg text-shogun-subdued hover:text-red-400 transition-colors disabled:opacity-40">
            {clearing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      <div className="flex gap-1 bg-[#050508] p-1 rounded-xl border border-shogun-border w-full">
        {CATEGORIES.map(cat => {
          const Icon = cat.icon;
          const count = cat.key === 'all' ? totalEvents : (categoryCounts[cat.key] || 0);
          return (
            <button key={cat.key} onClick={() => setActiveCategory(cat.key)}
              style={{ flex: '1 1 0', minWidth: 0 }}
              className={cn(
                "flex items-center justify-center gap-1 px-1.5 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all whitespace-nowrap",
                activeCategory === cat.key
                  ? `${cat.color} bg-white/5 border border-white/10`
                  : "text-shogun-subdued hover:text-shogun-text border border-transparent"
              )}>
              <Icon className="w-3 h-3 shrink-0" />
              <span className="truncate">{cat.label}</span>
              {count > 0 && (
                <span className="text-[8px] bg-white/5 px-1.5 py-0.5 rounded-full ml-0.5 shrink-0">{count}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Main Panel */}
      <div className="flex-1 flex flex-col shogun-card !p-0 overflow-hidden border-shogun-blue/20">
        {/* Toolbar */}
        <div className="p-3 border-b border-shogun-border bg-[#050508]/80 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-1">
            <div className="relative max-w-sm w-full">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-shogun-subdued" />
              <input type="text" placeholder="Search events, tools, models, traces..."
                value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
                className="w-full bg-shogun-bg border border-shogun-border rounded-lg pl-9 pr-4 py-1.5 text-xs focus:border-shogun-blue outline-none transition-all" />
            </div>
            <div className="flex items-center gap-2">
              <Filter className="w-3 h-3 text-shogun-subdued" />
              <select value={minSeverity} onChange={e => setMinSeverity(e.target.value)}
                className="bg-shogun-bg border border-shogun-border rounded-lg px-2 py-1 text-[10px] font-bold uppercase text-shogun-subdued outline-none focus:border-shogun-blue">
                <option value="all">All Levels</option>
                <option value="info">Info</option>
                <option value="warn">Warn</option>
                <option value="error">Error</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>
          <div className="hidden lg:flex items-center gap-3 text-[9px] text-shogun-subdued font-bold uppercase tracking-widest">
            <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-green-500" /> Success</span>
            <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-red-500" /> Denied</span>
            <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-yellow-400" /> Warn</span>
          </div>
        </div>

        {/* Event list */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto font-mono text-[11px] leading-relaxed bg-[#02040a] scrollbar-hide">
          {loading && logs.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center opacity-30 gap-3">
              <Terminal className="w-10 h-10 animate-pulse" />
              <span className="uppercase tracking-[0.3em]">Establishing uplink...</span>
            </div>
          ) : filteredLogs.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-shogun-subdued gap-3 py-20">
              <Shield className="w-12 h-12 opacity-20" />
              <span className="text-sm italic">No events matching filters</span>
              <span className="text-[10px] opacity-50">Events will appear here as the system operates</span>
            </div>
          ) : filteredLogs.map((log, i) => {
            const catInfo = getCategoryIcon(log.event_category);
            const CatIcon = catInfo.icon;
            return (
              <div key={log.id || i}
                onClick={() => setSelectedEvent(selectedEvent?.id === log.id ? null : log)}
                className={cn(
                  "group flex items-start gap-3 py-2 px-4 hover:bg-white/[0.03] transition-colors cursor-pointer border-l-2",
                  selectedEvent?.id === log.id ? "border-shogun-blue bg-white/[0.03]" : "border-transparent"
                )}>
                <span className="text-shogun-subdued whitespace-nowrap opacity-40 select-none text-[10px] pt-0.5">
                  {new Date(log.occurred_at).toLocaleTimeString()}
                </span>

                <CatIcon className={cn("w-3.5 h-3.5 mt-0.5 shrink-0", catInfo.color)} />

                <div className={cn("w-14 text-[9px] font-bold uppercase tracking-tighter shrink-0 pt-0.5 border rounded px-1 text-center", getSeverityStyle(log.severity))}>
                  {log.severity}
                </div>

                {getResultIcon(log.result)}

                <div className="flex-1 flex flex-wrap items-baseline gap-x-2 gap-y-0.5 min-w-0">
                  <span className="text-shogun-text">{log.action}</span>
                  {log.event_type && (
                    <span className="text-[9px] bg-shogun-card px-1.5 py-0.5 rounded border border-shogun-border text-shogun-blue/70 font-bold uppercase tracking-widest">
                      {log.event_type}
                    </span>
                  )}
                  {log.model_used && (
                    <span className="text-[9px] text-shogun-gold/60">{log.model_used}</span>
                  )}
                  {log.tool_name && (
                    <span className="text-[9px] text-green-400/60">⚙ {log.tool_name}</span>
                  )}
                  {log.policy_decision && (
                    <span className={cn("text-[9px] font-bold uppercase",
                      log.policy_decision === 'denied' ? 'text-red-400' : 'text-green-400/60'
                    )}>
                      {log.policy_decision === 'denied' ? '✕ DENIED' : '✓ ' + log.policy_decision}
                    </span>
                  )}
                  {log.trace_id && (
                    <button onClick={(e) => { e.stopPropagation(); fetchTrace(log.trace_id!); }}
                      className="text-[8px] text-shogun-subdued/50 hover:text-shogun-blue font-mono flex items-center gap-0.5 transition-colors">
                      <Link2 className="w-2.5 h-2.5" />{log.trace_id.slice(0, 12)}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
          <div className="h-4" />
        </div>

        {/* Detail panel for selected event */}
        {selectedEvent && (
          <div className="border-t border-shogun-border bg-[#050508] p-4 max-h-[250px] overflow-y-auto">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-[10px] font-bold uppercase tracking-widest text-shogun-gold flex items-center gap-2">
                <FileKey className="w-3.5 h-3.5" /> Event Detail — {selectedEvent.event_id}
              </h4>
              <button onClick={() => setSelectedEvent(null)} className="text-shogun-subdued hover:text-shogun-text">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-[10px]">
              {[
                ['WHO', selectedEvent.user_id || '—'],
                ['AGENT', selectedEvent.agent_id?.slice(0, 8) || '—'],
                ['WHAT', selectedEvent.event_type],
                ['WHEN', new Date(selectedEvent.occurred_at).toISOString()],
                ['RESULT', selectedEvent.result],
                ['MODEL', selectedEvent.model_used || '—'],
                ['PROVIDER', selectedEvent.provider_used || '—'],
                ['TOOL', selectedEvent.tool_name || '—'],
                ['POLICY', selectedEvent.policy_ref || '—'],
                ['DECISION', selectedEvent.policy_decision || '—'],
                ['RISK', selectedEvent.risk_score || 'low'],
                ['TRACE', selectedEvent.trace_id || '—'],
              ].map(([label, value]) => (
                <div key={label}>
                  <div className="text-[8px] text-shogun-subdued font-bold uppercase tracking-widest mb-0.5">{label}</div>
                  <div className="text-shogun-text font-mono truncate">{value}</div>
                </div>
              ))}
            </div>
            {selectedEvent.policy_reason && (
              <div className="mt-3 p-2 bg-shogun-blue/5 border border-shogun-blue/20 rounded text-[10px]">
                <span className="text-[8px] text-shogun-blue font-bold uppercase tracking-widest">Policy Reason: </span>
                <span className="text-shogun-text">{selectedEvent.policy_reason}</span>
              </div>
            )}

            {/* EU AI Act: Confidence Indicator */}
            {selectedEvent.confidence_score != null && (
              <div className="mt-3 flex items-center gap-3">
                <span className="text-[8px] text-shogun-subdued font-bold uppercase tracking-widest">AI Confidence:</span>
                <div className="flex-1 max-w-[200px] h-2 bg-[#02040a] rounded-full overflow-hidden border border-shogun-border">
                  <div className={cn("h-full rounded-full transition-all",
                    selectedEvent.confidence_score >= 0.7 ? "bg-green-500" :
                    selectedEvent.confidence_score >= 0.4 ? "bg-yellow-400" : "bg-red-500"
                  )} style={{ width: `${Math.round(selectedEvent.confidence_score * 100)}%` }} />
                </div>
                <span className={cn("text-[10px] font-bold font-mono",
                  selectedEvent.confidence_score >= 0.7 ? "text-green-500" :
                  selectedEvent.confidence_score >= 0.4 ? "text-yellow-400" : "text-red-500"
                )}>
                  {Math.round(selectedEvent.confidence_score * 100)}%
                </span>
              </div>
            )}

            {/* EU AI Act: Governance Framework Badges */}
            {selectedEvent.use_case_context?.frameworks?.length > 0 && (
              <div className="mt-2 flex items-center gap-2 flex-wrap">
                <span className="text-[8px] text-shogun-subdued font-bold uppercase tracking-widest">Frameworks:</span>
                {selectedEvent.use_case_context.frameworks.map((fw: string) => (
                  <span key={fw} className={cn(
                    "text-[8px] font-bold uppercase px-1.5 py-0.5 rounded border",
                    fw === 'EU_AI_ACT' ? "text-violet-400 border-violet-400/30 bg-violet-500/5" :
                    fw === 'SOC2' ? "text-blue-400 border-blue-400/30 bg-blue-500/5" :
                    "text-cyan-400 border-cyan-400/30 bg-cyan-500/5"
                  )}>{fw}</span>
                ))}
                {selectedEvent.use_case_context.risk_level && (
                  <span className={cn(
                    "text-[8px] font-bold uppercase px-1.5 py-0.5 rounded border",
                    selectedEvent.use_case_context.risk_level === 'high' ? "text-red-400 border-red-400/30 bg-red-500/5" :
                    selectedEvent.use_case_context.risk_level === 'limited' ? "text-yellow-400 border-yellow-400/30 bg-yellow-500/5" :
                    "text-green-400 border-green-400/30 bg-green-500/5"
                  )}>Risk: {selectedEvent.use_case_context.risk_level}</span>
                )}
              </div>
            )}

            {/* Governance Flags */}
            {Object.keys(selectedEvent.governance_flags || {}).length > 0 && (
              <div className="mt-2 flex items-center gap-2 flex-wrap">
                <span className="text-[8px] text-shogun-subdued font-bold uppercase tracking-widest">Governance:</span>
                {Object.entries(selectedEvent.governance_flags).map(([k, v]) => (
                  <span key={k} className="text-[8px] text-amber-400/70 bg-amber-500/5 border border-amber-500/20 px-1.5 py-0.5 rounded">
                    {k}: {String(v)}
                  </span>
                ))}
              </div>
            )}

            {selectedEvent.memory_ids?.length > 0 && (
              <div className="mt-2 text-[10px]">
                <span className="text-[8px] text-cyan-400 font-bold uppercase tracking-widest">Memory IDs: </span>
                <span className="text-shogun-subdued font-mono">{selectedEvent.memory_ids.join(', ')}</span>
              </div>
            )}
            {Object.keys(selectedEvent.detail || {}).length > 0 && (
              <div className="mt-2">
                <div className="text-[8px] text-shogun-subdued font-bold uppercase tracking-widest mb-1">Detail Payload</div>
                <pre className="text-[9px] text-shogun-subdued bg-[#02040a] p-2 rounded border border-shogun-border overflow-x-auto max-h-24">
                  {JSON.stringify(selectedEvent.detail, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}

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
          </div>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <Shield className="w-3 h-3" /> Dual-Layer Logging
            </span>
            <span>Audit: <span className={auditStatus?.chain_intact ? "text-green-500" : "text-red-400"}>{auditStatus?.chain_intact ? 'INTACT' : 'BROKEN'}</span></span>
          </div>
        </div>
      </div>

      {/* Trace reconstruction modal */}
      {showTrace && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-8" onClick={() => setShowTrace(false)}>
          <div className="bg-[#0a0a12] border border-shogun-border rounded-2xl w-full max-w-3xl max-h-[80vh] overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-shogun-border flex items-center justify-between">
              <h3 className="text-sm font-bold text-shogun-gold flex items-center gap-2">
                <Link2 className="w-4 h-4" /> Trace Reconstruction
                <span className="text-[10px] text-shogun-subdued ml-2">{traceEvents.length} events in chain</span>
              </h3>
              <button onClick={() => setShowTrace(false)} className="text-shogun-subdued hover:text-shogun-text"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-4 overflow-y-auto max-h-[65vh] space-y-2">
              {traceEvents.map((ev, i) => {
                const catInfo = getCategoryIcon(ev.event_category);
                const CatIcon = catInfo.icon;
                return (
                  <div key={ev.id} className="flex items-start gap-3 p-3 bg-[#050508] rounded-lg border border-shogun-border">
                    <div className="flex flex-col items-center gap-1">
                      <div className="w-6 h-6 rounded-full bg-shogun-card border border-shogun-border flex items-center justify-center text-[9px] font-bold text-shogun-subdued">{i + 1}</div>
                      {i < traceEvents.length - 1 && <div className="w-px h-4 bg-shogun-border" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <CatIcon className={cn("w-3.5 h-3.5", catInfo.color)} />
                        <span className="text-[10px] font-bold text-shogun-text uppercase">{ev.event_type}</span>
                        {getResultIcon(ev.result)}
                        <span className="text-[9px] text-shogun-subdued ml-auto">{new Date(ev.occurred_at).toLocaleTimeString()}</span>
                      </div>
                      <p className="text-[11px] text-shogun-subdued">{ev.action}</p>
                      {ev.model_used && <span className="text-[9px] text-shogun-gold/60">Model: {ev.model_used}</span>}
                      {ev.policy_decision && (
                        <span className={cn("text-[9px] ml-2 font-bold", ev.policy_decision === 'denied' ? 'text-red-400' : 'text-green-400')}>
                          Policy: {ev.policy_decision}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
              {traceEvents.length === 0 && (
                <div className="text-center text-shogun-subdued py-8 text-sm">No events found for this trace.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
