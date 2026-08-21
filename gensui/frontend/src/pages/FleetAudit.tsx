import { useEffect, useState, useCallback } from 'react';
import {
  FileSearch, Shield, AlertTriangle, Users, BarChart3,
  Download, CheckCircle, XCircle, Activity, Cpu,
  Clock, TrendingUp, ShieldCheck, RefreshCw
} from 'lucide-react';
import api from '../lib/api';
import { useTranslation } from '../i18n';

type Tab = 'overview' | 'members' | 'telemetry' | 'compliance' | 'log';

interface FleetStats {
  total_entries: number;
  last_24h: number;
  last_7d: number;
  by_action: Record<string, number>;
  by_actor_type: Record<string, number>;
  security_critical_30d: number;
  chain_integrity: { valid: boolean; checked: number; errors: number };
}

interface MemberSummary {
  member_id: string;
  instance_name: string;
  enrollment_status: string;
  audit_events: number;
  telemetry_events: number;
  critical_events: number;
  last_event_at: string | null;
}

interface TelemetryData {
  total: number;
  period: { since: string; until: string };
  by_category: Record<string, number>;
  by_severity: Record<string, number>;
  by_event_type: Record<string, number>;
  by_member: Record<string, number>;
}

interface ComplianceReport {
  report_generated_at: string;
  period: string;
  report_purpose?: string;
  assessment_notice?: string;
  fleet: { total_members: number; active_members: number };
  security_events: {
    harakiri_activations: number;
    posture_changes: number;
    enrollment_events: number;
    token_revocations: number;
    critical_telemetry: number;
  };
  chain_integrity: { valid: boolean; entries_verified: number; chain_breaks: number };
  compliance_frameworks: string[];
}

const SEV_COLORS: Record<string, string> = {
  info: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/30',
  warn: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
  error: 'text-red-400 bg-red-500/10 border-red-500/30',
  critical: 'text-red-500 bg-red-500/20 border-red-500/40',
};

export default function FleetAudit() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>('overview');
  const [stats, setStats] = useState<FleetStats | null>(null);
  const [members, setMembers] = useState<MemberSummary[]>([]);
  const [telemetry, setTelemetry] = useState<TelemetryData | null>(null);
  const [compliance, setCompliance] = useState<ComplianceReport | null>(null);
  const [auditEntries, setAuditEntries] = useState<any[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [actionFilter, setActionFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (tab === 'overview') {
        const r = await api.get('/fleet-audit/stats');
        setStats(r.data);
      } else if (tab === 'members') {
        const r = await api.get('/fleet-audit/members');
        setMembers(r.data.members || []);
      } else if (tab === 'telemetry') {
        const r = await api.get('/fleet-audit/telemetry');
        setTelemetry(r.data);
      } else if (tab === 'compliance') {
        const r = await api.get('/fleet-audit/compliance');
        setCompliance(r.data);
      } else if (tab === 'log') {
        const params: any = { limit: 200 };
        if (actionFilter) params.action = actionFilter;
        const r = await api.get('/audit', { params });
        setAuditEntries(r.data.entries || []);
        setAuditTotal(r.data.total || 0);
      }
    } catch (e) {
      console.error('Fleet audit load error:', e);
    }
    setLoading(false);
  }, [tab, actionFilter]);

  useEffect(() => { load(); }, [load]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const r = await api.get('/fleet-audit/export', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([r.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `gensui_audit_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (e) { console.error('Export error:', e); }
    setExporting(false);
  };

  const TABS: { id: Tab; label: string; icon: any }[] = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'members', label: 'Per Member', icon: Users },
    { id: 'telemetry', label: 'Telemetry', icon: Activity },
    { id: 'compliance', label: 'Governance Evidence', icon: ShieldCheck },
    { id: 'log', label: 'Raw Log', icon: FileSearch },
  ];

  return (
    <div className="space-y-6 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gensui-50">{t('fleet_audit.title', 'Fleet Audit Dashboard')}</h1>
          <p className="text-sm text-gensui-400 mt-1">{t('fleet_audit.subtitle', 'Multi-instance audit analytics, governance-evidence summaries, and chain-link checks')}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="gensui-btn-secondary flex items-center gap-2 text-xs">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
          <button onClick={handleExport} disabled={exporting} className="gensui-btn-primary flex items-center gap-2 text-xs">
            <Download size={14} /> {exporting ? t('fleet_audit.exporting', 'Exporting...') : t('fleet_audit.export_csv', 'Export CSV')}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gensui-800/40 p-1 rounded-lg border border-gensui-700/30">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs font-medium transition-all ${
              tab === t.id
                ? 'bg-gensui-600/40 text-gensui-50 border border-gensui-500/30'
                : 'text-gensui-400 hover:text-gensui-200 hover:bg-gensui-700/30'
            }`}
          >
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <RefreshCw className="animate-spin text-gensui-500" size={24} />
        </div>
      ) : (
        <>
          {/* ── Overview ── */}
          {tab === 'overview' && stats && (
            <div className="space-y-6">
              {/* Stat Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="glass-card p-4 space-y-1">
                  <div className="text-xs text-gensui-500 uppercase tracking-wider">{t('fleet_audit.total_events', 'Total Events')}</div>
                  <div className="text-2xl font-bold text-gensui-50">{stats.total_entries.toLocaleString()}</div>
                </div>
                <div className="glass-card p-4 space-y-1">
                  <div className="text-xs text-gensui-500 uppercase tracking-wider flex items-center gap-1"><Clock size={12} /> {t('fleet_audit.last_24h', 'Last 24h')}</div>
                  <div className="text-2xl font-bold text-cyan-400">{stats.last_24h.toLocaleString()}</div>
                </div>
                <div className="glass-card p-4 space-y-1">
                  <div className="text-xs text-gensui-500 uppercase tracking-wider flex items-center gap-1"><TrendingUp size={12} /> {t('fleet_audit.last_7d', 'Last 7d')}</div>
                  <div className="text-2xl font-bold text-emerald-400">{stats.last_7d.toLocaleString()}</div>
                </div>
                <div className="glass-card p-4 space-y-1">
                  <div className="text-xs text-gensui-500 uppercase tracking-wider flex items-center gap-1"><AlertTriangle size={12} /> {t('fleet_audit.critical_30d', 'Critical (30d)')}</div>
                  <div className="text-2xl font-bold text-red-400">{stats.security_critical_30d}</div>
                </div>
              </div>

              {/* Chain Integrity */}
              <div className={`glass-card p-4 border-l-4 ${stats.chain_integrity.valid ? 'border-l-emerald-500' : 'border-l-red-500'}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {stats.chain_integrity.valid
                      ? <CheckCircle className="text-emerald-400" size={20} />
                      : <XCircle className="text-red-400" size={20} />
                    }
                    <div>
                      <div className="text-sm font-bold text-gensui-100">
                        Chain Links {stats.chain_integrity.valid ? 'Consistent ✓' : 'MISMATCH ✗'}
                      </div>
                      <div className="text-xs text-gensui-400">
                        {stats.chain_integrity.checked} entries verified
                        {stats.chain_integrity.errors > 0 && ` — ${stats.chain_integrity.errors} chain break(s) detected`}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Action Breakdown */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="glass-card p-4 space-y-3">
                  <div className="text-xs font-bold text-gensui-200 uppercase tracking-wider">By Action</div>
                  <div className="space-y-1 max-h-64 overflow-y-auto">
                    {Object.entries(stats.by_action).map(([action, count]) => (
                      <div key={action} className="flex items-center justify-between py-1 px-2 rounded hover:bg-gensui-700/30">
                        <span className="text-xs text-gensui-300 font-mono">{action}</span>
                        <span className="text-xs text-gensui-500">{count}</span>
                      </div>
                    ))}
                    {Object.keys(stats.by_action).length === 0 && (
                      <p className="text-xs text-gensui-500 text-center py-4">No actions recorded</p>
                    )}
                  </div>
                </div>
                <div className="glass-card p-4 space-y-3">
                  <div className="text-xs font-bold text-gensui-200 uppercase tracking-wider">By Actor Type</div>
                  <div className="space-y-2">
                    {Object.entries(stats.by_actor_type).map(([actor, count]) => {
                      const total = stats.total_entries || 1;
                      const pct = Math.round((count / total) * 100);
                      return (
                        <div key={actor} className="space-y-1">
                          <div className="flex justify-between text-xs">
                            <span className="text-gensui-300 capitalize">{actor}</span>
                            <span className="text-gensui-500">{count} ({pct}%)</span>
                          </div>
                          <div className="h-1.5 bg-gensui-700/50 rounded-full overflow-hidden">
                            <div className="h-full bg-cyan-500/60 rounded-full transition-all" style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── Per Member ── */}
          {tab === 'members' && (
            <div className="glass-card overflow-hidden">
              <table className="gensui-table">
                <thead>
                  <tr>
                    <th>Instance</th>
                    <th>Status</th>
                    <th>Audit Events</th>
                    <th>Telemetry</th>
                    <th>Critical</th>
                    <th>Last Event</th>
                  </tr>
                </thead>
                <tbody>
                  {members.map(m => (
                    <tr key={m.member_id}>
                      <td>
                        <div className="flex items-center gap-2">
                          <Cpu size={14} className="text-cyan-400" />
                          <span className="text-sm text-gensui-200 font-medium">{m.instance_name}</span>
                        </div>
                      </td>
                      <td>
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${
                          m.enrollment_status === 'active'
                            ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
                            : 'text-gensui-500 bg-gensui-700/30 border-gensui-600/30'
                        }`}>
                          {m.enrollment_status}
                        </span>
                      </td>
                      <td className="text-gensui-300 text-sm">{m.audit_events.toLocaleString()}</td>
                      <td className="text-gensui-300 text-sm">{m.telemetry_events.toLocaleString()}</td>
                      <td>
                        <span className={`text-sm font-bold ${m.critical_events > 0 ? 'text-red-400' : 'text-gensui-500'}`}>
                          {m.critical_events}
                        </span>
                      </td>
                      <td className="text-xs text-gensui-500">
                        {m.last_event_at ? new Date(m.last_event_at).toLocaleString() : '—'}
                      </td>
                    </tr>
                  ))}
                  {members.length === 0 && (
                    <tr><td colSpan={6} className="text-center py-8 text-gensui-500">No fleet members</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* ── Telemetry Analytics ── */}
          {tab === 'telemetry' && telemetry && (
            <div className="space-y-6">
              <div className="glass-card p-4">
                <div className="flex items-center justify-between mb-4">
                  <div className="text-xs text-gensui-500">
                    Period: {new Date(telemetry.period.since).toLocaleDateString()} — {new Date(telemetry.period.until).toLocaleDateString()}
                  </div>
                  <div className="text-lg font-bold text-gensui-50">{telemetry.total.toLocaleString()} events</div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* By Severity */}
                <div className="glass-card p-4 space-y-3">
                  <div className="text-xs font-bold text-gensui-200 uppercase tracking-wider">By Severity</div>
                  <div className="space-y-2">
                    {Object.entries(telemetry.by_severity).map(([sev, count]) => (
                      <div key={sev} className="flex items-center justify-between">
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${SEV_COLORS[sev] || 'text-gensui-400 bg-gensui-700/30 border-gensui-600/30'}`}>
                          {sev}
                        </span>
                        <span className="text-sm text-gensui-300 font-medium">{count.toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* By Category */}
                <div className="glass-card p-4 space-y-3">
                  <div className="text-xs font-bold text-gensui-200 uppercase tracking-wider">By Category</div>
                  <div className="space-y-2">
                    {Object.entries(telemetry.by_category).map(([cat, count]) => (
                      <div key={cat} className="flex items-center justify-between">
                        <span className="text-xs text-gensui-300 capitalize">{cat}</span>
                        <span className="text-sm text-gensui-300 font-medium">{count.toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* By Event Type */}
                <div className="glass-card p-4 space-y-3">
                  <div className="text-xs font-bold text-gensui-200 uppercase tracking-wider">Top Event Types</div>
                  <div className="space-y-1 max-h-48 overflow-y-auto">
                    {Object.entries(telemetry.by_event_type).map(([type, count]) => (
                      <div key={type} className="flex items-center justify-between py-0.5">
                        <span className="text-xs text-gensui-400 font-mono truncate mr-2">{type}</span>
                        <span className="text-xs text-gensui-500 shrink-0">{count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* By Member */}
              {Object.keys(telemetry.by_member).length > 0 && (
                <div className="glass-card p-4 space-y-3">
                  <div className="text-xs font-bold text-gensui-200 uppercase tracking-wider">Events by Member</div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                    {Object.entries(telemetry.by_member).map(([mid, count]) => (
                      <div key={mid} className="bg-gensui-800/40 border border-gensui-700/30 rounded-lg p-3 text-center">
                        <div className="text-lg font-bold text-gensui-200">{count.toLocaleString()}</div>
                        <div className="text-[10px] text-gensui-500 font-mono truncate">{mid.slice(0, 12)}…</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Governance evidence (legacy API route: compliance) ── */}
          {tab === 'compliance' && compliance && (
            <div className="space-y-6">
              <div className="glass-card p-5 border-l-4 border-l-cyan-500">
                <div className="flex items-center gap-3 mb-4">
                  <ShieldCheck size={24} className="text-cyan-400" />
                  <div>
                    <h2 className="text-lg font-bold text-gensui-50">Governance Evidence Summary</h2>
                    <p className="text-xs text-gensui-400">Generated: {new Date(compliance.report_generated_at).toLocaleString()} — Period: {compliance.period.replace('_', ' ')}</p>
                  </div>
                </div>
                <div className="flex gap-2">
                  {compliance.compliance_frameworks.map(fw => (
                    <span key={fw} className="text-xs px-2 py-1 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-400">{fw}</span>
                  ))}
                </div>
                <p className="mt-4 text-xs leading-relaxed text-amber-200/80">
                  {compliance.assessment_notice || 'This summary can support a human assessment. It does not establish conformity or prove that every relevant event was captured.'}
                </p>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <div className="glass-card p-4 space-y-1">
                  <div className="text-xs text-gensui-500 uppercase tracking-wider">Fleet Members</div>
                  <div className="text-2xl font-bold text-gensui-50">{compliance.fleet.active_members} / {compliance.fleet.total_members}</div>
                  <div className="text-xs text-gensui-400">active / total</div>
                </div>
                <div className="glass-card p-4 space-y-1">
                  <div className="text-xs text-gensui-500 uppercase tracking-wider">Harakiri Activations</div>
                  <div className={`text-2xl font-bold ${compliance.security_events.harakiri_activations > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                    {compliance.security_events.harakiri_activations}
                  </div>
                </div>
                <div className="glass-card p-4 space-y-1">
                  <div className="text-xs text-gensui-500 uppercase tracking-wider">Posture Changes</div>
                  <div className="text-2xl font-bold text-amber-400">{compliance.security_events.posture_changes}</div>
                </div>
                <div className="glass-card p-4 space-y-1">
                  <div className="text-xs text-gensui-500 uppercase tracking-wider">Enrollment Events</div>
                  <div className="text-2xl font-bold text-cyan-400">{compliance.security_events.enrollment_events}</div>
                </div>
                <div className="glass-card p-4 space-y-1">
                  <div className="text-xs text-gensui-500 uppercase tracking-wider">Token Revocations</div>
                  <div className={`text-2xl font-bold ${compliance.security_events.token_revocations > 0 ? 'text-orange-400' : 'text-gensui-500'}`}>
                    {compliance.security_events.token_revocations}
                  </div>
                </div>
                <div className="glass-card p-4 space-y-1">
                  <div className="text-xs text-gensui-500 uppercase tracking-wider">Critical Telemetry</div>
                  <div className={`text-2xl font-bold ${compliance.security_events.critical_telemetry > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                    {compliance.security_events.critical_telemetry}
                  </div>
                </div>
              </div>

              {/* Chain Integrity */}
              <div className={`glass-card p-4 border-l-4 ${compliance.chain_integrity.valid ? 'border-l-emerald-500' : 'border-l-red-500'}`}>
                <div className="flex items-center gap-3">
                  {compliance.chain_integrity.valid
                    ? <CheckCircle className="text-emerald-400" size={20} />
                    : <XCircle className="text-red-400" size={20} />
                  }
                  <div>
                    <div className="text-sm font-bold text-gensui-100">
                      Audit Chain Links: {compliance.chain_integrity.valid ? 'CONSISTENT' : 'MISMATCH DETECTED'}
                    </div>
                    <div className="text-xs text-gensui-400">
                      {compliance.chain_integrity.entries_verified} entries verified — {compliance.chain_integrity.chain_breaks} break(s)
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── Raw Log ── */}
          {tab === 'log' && (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <input
                  className="gensui-input w-64"
                  placeholder="Filter by action..."
                  value={actionFilter}
                  onChange={e => setActionFilter(e.target.value)}
                />
                <span className="text-xs text-gensui-500">{auditTotal} total entries</span>
              </div>
              <div className="glass-card overflow-hidden">
                <table className="gensui-table">
                  <thead>
                    <tr><th>Time</th><th>Actor</th><th>Action</th><th>Target</th><th>Reason</th><th>IP</th></tr>
                  </thead>
                  <tbody>
                    {auditEntries.map(e => (
                      <tr key={e.id}>
                        <td className="text-xs text-gensui-500 whitespace-nowrap">{e.timestamp ? new Date(e.timestamp).toLocaleString() : '—'}</td>
                        <td><span className="text-xs text-gensui-300">{e.actor_type}</span></td>
                        <td className="text-gensui-200 font-mono text-xs">{e.action}</td>
                        <td className="text-xs text-gensui-400">{e.target_type} {e.target_id?.slice(0, 8)}</td>
                        <td className="text-xs text-gensui-500 max-w-xs truncate">{e.reason || '—'}</td>
                        <td className="text-xs text-gensui-600 font-mono">{e.ip_address || '—'}</td>
                      </tr>
                    ))}
                    {auditEntries.length === 0 && (
                      <tr><td colSpan={6} className="text-center py-8 text-gensui-500">No audit entries</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
