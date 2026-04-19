import { useState, useEffect } from 'react';
import { HardDrive, Plus, Trash2, RotateCcw, Settings, Clock, Archive, ToggleLeft, ToggleRight, Activity, RefreshCw, FileText, ChevronRight, Database, Download, CheckCircle2, AlertCircle, HelpCircle } from 'lucide-react';
import axios from 'axios';

interface BackupFile {
  filename: string;
  size: number;
  size_formatted: string;
  created_at: string;
}

interface BackupSettings {
  enabled: boolean;
  interval_hours: number;
  max_backups: number;
  include_vector_memory: boolean;
  last_backup: string | null;
  backup_dir: string | null;
}

export const Backups = () => {
  const [backups, setBackups] = useState<BackupFile[]>([]);
  const [settings, setSettings] = useState<BackupSettings | null>(null);
  const [creating, setCreating] = useState(false);
  const [restoring, setRestoring] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [activeTab, setActiveTab] = useState<'backups' | 'data'>('backups');

  // Data Management state
  const [stats, setStats] = useState<any>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [exportPath, setExportPath] = useState('C:\\Shogun_Backups');
  const [exportMsg, setExportMsg] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  const loadBackups = async () => {
    try {
      const r = await fetch('/api/v1/backups/list');
      const data = await r.json();
      setBackups(data.backups || []);
    } catch { /* */ }
  };

  const loadSettings = async () => {
    try {
      const r = await fetch('/api/v1/backups/settings');
      const data = await r.json();
      setSettings(data);
    } catch { /* */ }
  };

  const updateSettings = async (updates: Partial<BackupSettings>) => {
    try {
      const r = await fetch('/api/v1/backups/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      const data = await r.json();
      setSettings(data);
      setMessage({ type: 'success', text: 'Settings saved.' });
      setTimeout(() => setMessage(null), 3000);
    } catch {
      setMessage({ type: 'error', text: 'Failed to save settings.' });
    }
  };

  const createBackup = async () => {
    setCreating(true);
    setMessage(null);
    try {
      const r = await fetch('/api/v1/backups/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label: 'manual' }),
      });
      const data = await r.json();
      if (data.success) {
        setMessage({ type: 'success', text: `Backup created: ${data.filename} (${data.files_count} files)` });
        loadBackups();
        loadSettings();
      } else {
        setMessage({ type: 'error', text: data.detail || 'Backup failed.' });
      }
    } catch {
      setMessage({ type: 'error', text: 'Backup failed.' });
    }
    setCreating(false);
  };

  const deleteBackup = async (filename: string) => {
    if (!confirm(`Delete ${filename}?`)) return;
    try {
      await fetch(`/api/v1/backups/${filename}`, { method: 'DELETE' });
      loadBackups();
      setMessage({ type: 'success', text: 'Backup deleted.' });
      setTimeout(() => setMessage(null), 3000);
    } catch { /* */ }
  };

  const restoreBackup = async (filename: string) => {
    if (!confirm('This will overwrite your current database and configs. A restart is required afterwards. Continue?')) return;
    setRestoring(filename);
    try {
      const r = await fetch(`/api/v1/backups/restore/${filename}`, { method: 'POST' });
      const data = await r.json();
      if (data.success) {
        setMessage({ type: 'success', text: `Restored ${data.files_restored} files. Please restart Shogun.` });
      } else {
        setMessage({ type: 'error', text: data.detail || 'Restore failed.' });
      }
    } catch {
      setMessage({ type: 'error', text: 'Restore failed.' });
    }
    setRestoring(null);
  };

  // Data Management functions
  const fetchBackupStats = async () => {
    setStatsLoading(true);
    try {
      const res = await axios.get('/api/v1/system/backup/info');
      setStats(res.data.data);
    } catch { /* silent */ }
    finally { setStatsLoading(false); }
  };

  const handleExport = async (strategy: 'json' | 'raw') => {
    setStatsLoading(true);
    try {
      const include_db = strategy === 'raw';
      const res = await axios.get('/api/v1/system/backup/export', {
        params: { save_path: exportPath, include_db },
      });
      const saved = res.data?.data?.saved_to || exportPath;
      setExportMsg({ type: 'success', text: `Backup saved to ${saved}` });
      fetchBackupStats();
    } catch (err: any) {
      const msg = err.response?.data?.meta?.error || err.response?.data?.detail || 'Export failed';
      setExportMsg({ type: 'error', text: msg });
    } finally { setStatsLoading(false); }
  };

  useEffect(() => { loadBackups(); loadSettings(); }, []);
  useEffect(() => { if (activeTab === 'data') fetchBackupStats(); }, [activeTab]);

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <HardDrive className="w-6 h-6 text-shogun-gold" />
            Backups & Data Management
          </h1>
          <p className="text-shogun-subdued mt-1">Protect your data with scheduled backups and manage your database.</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-shogun-card border border-shogun-border text-shogun-subdued hover:text-shogun-text hover:border-shogun-blue transition-colors text-sm"
          >
            <Settings className="w-4 h-4" />
            Settings
          </button>
          <button
            onClick={createBackup}
            disabled={creating}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-shogun-gold text-black font-semibold hover:bg-shogun-gold/80 transition-colors text-sm disabled:opacity-50"
          >
            <Plus className={`w-4 h-4 ${creating ? 'animate-spin' : ''}`} />
            {creating ? 'Creating...' : 'Backup Now'}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 p-1 bg-shogun-card border border-shogun-border rounded-xl w-fit">
        {[
          { id: 'backups' as const, label: 'Scheduled Backups', icon: Clock },
          { id: 'data' as const, label: 'Data Management', icon: Database },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeTab === tab.id
                ? 'bg-shogun-bg text-shogun-gold border border-shogun-border shadow-shogun'
                : 'text-shogun-subdued hover:text-shogun-text'
            }`}
          >
            <tab.icon className="w-3.5 h-3.5" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Message */}
      {message && (
        <div className={`rounded-xl p-4 border text-sm ${
          message.type === 'success' 
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' 
            : 'bg-red-500/10 border-red-500/30 text-red-300'
        }`}>
          {message.text}
        </div>
      )}

      {/* Settings Panel */}
      {showSettings && settings && (
        <div className="bg-shogun-card border border-shogun-border rounded-xl p-6 space-y-5">
          <h2 className="text-sm font-bold text-shogun-gold uppercase tracking-wider">Backup Settings</h2>
          
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white font-medium">Automatic Backups</p>
              <p className="text-[11px] text-shogun-subdued">Automatically back up on a schedule.</p>
            </div>
            <button onClick={() => updateSettings({ enabled: !settings.enabled })} className="text-shogun-gold">
              {settings.enabled ? <ToggleRight className="w-8 h-8" /> : <ToggleLeft className="w-8 h-8 text-shogun-subdued" />}
            </button>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white font-medium">Backup Interval</p>
              <p className="text-[11px] text-shogun-subdued">How often to create automatic backups.</p>
            </div>
            <select
              value={settings.interval_hours}
              onChange={(e) => updateSettings({ interval_hours: Number(e.target.value) })}
              className="bg-shogun-bg border border-shogun-border rounded-lg px-3 py-1.5 text-sm text-white"
            >
              <option value={1}>Every hour</option>
              <option value={6}>Every 6 hours</option>
              <option value={12}>Every 12 hours</option>
              <option value={24}>Every 24 hours</option>
              <option value={48}>Every 2 days</option>
              <option value={168}>Weekly</option>
            </select>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white font-medium">Backups to Keep</p>
              <p className="text-[11px] text-shogun-subdued">Older backups beyond this limit are automatically deleted.</p>
            </div>
            <select
              value={settings.max_backups}
              onChange={(e) => updateSettings({ max_backups: Number(e.target.value) })}
              className="bg-shogun-bg border border-shogun-border rounded-lg px-3 py-1.5 text-sm text-white"
            >
              {[1, 2, 3, 5, 7, 10, 15, 20].map(n => (
                <option key={n} value={n}>{n} backups</option>
              ))}
            </select>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white font-medium">Include Vector Memory</p>
              <p className="text-[11px] text-shogun-subdued">Include Qdrant data (significantly increases backup size).</p>
            </div>
            <button onClick={() => updateSettings({ include_vector_memory: !settings.include_vector_memory })} className="text-shogun-gold">
              {settings.include_vector_memory ? <ToggleRight className="w-8 h-8" /> : <ToggleLeft className="w-8 h-8 text-shogun-subdued" />}
            </button>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════ */}
      {/* TAB: Scheduled Backups                     */}
      {/* ═══════════════════════════════════════════ */}
      {activeTab === 'backups' && (
        <>
          {/* Status Summary */}
          {settings && (
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-shogun-card border border-shogun-border rounded-xl p-4 text-center">
                <p className="text-[10px] uppercase tracking-wider text-shogun-subdued mb-1">Schedule</p>
                <p className="text-lg font-bold text-white">
                  {settings.enabled ? `Every ${settings.interval_hours}h` : 'Disabled'}
                </p>
              </div>
              <div className="bg-shogun-card border border-shogun-border rounded-xl p-4 text-center">
                <p className="text-[10px] uppercase tracking-wider text-shogun-subdued mb-1">Total Backups</p>
                <p className="text-lg font-bold text-white">{backups.length}</p>
              </div>
              <div className="bg-shogun-card border border-shogun-border rounded-xl p-4 text-center">
                <p className="text-[10px] uppercase tracking-wider text-shogun-subdued mb-1">Last Backup</p>
                <p className="text-lg font-bold text-white">
                  {settings.last_backup ? new Date(settings.last_backup).toLocaleDateString() : 'Never'}
                </p>
              </div>
            </div>
          )}

          {/* Backup List */}
          <div className="bg-shogun-card border border-shogun-border rounded-xl overflow-hidden">
            <div className="px-6 py-4 border-b border-shogun-border">
              <h2 className="text-sm font-bold text-white">Available Backups</h2>
            </div>

            {backups.length === 0 ? (
              <div className="p-8 text-center text-shogun-subdued">
                <Archive className="w-10 h-10 mx-auto mb-3 opacity-30" />
                <p>No backups yet.</p>
                <p className="text-[11px] mt-1">Create one manually or enable automatic backups.</p>
              </div>
            ) : (
              <div className="divide-y divide-shogun-border/50">
                {backups.map((b) => (
                  <div key={b.filename} className="px-6 py-4 flex items-center justify-between hover:bg-shogun-bg/50 transition-colors">
                    <div className="flex items-center gap-4">
                      <HardDrive className="w-5 h-5 text-shogun-blue" />
                      <div>
                        <p className="text-sm text-white font-medium">{b.filename}</p>
                        <div className="flex items-center gap-3 text-[11px] text-shogun-subdued mt-0.5">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(b.created_at).toLocaleString()}
                          </span>
                          <span>{b.size_formatted}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => restoreBackup(b.filename)}
                        disabled={restoring === b.filename}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] bg-shogun-bg border border-shogun-border text-shogun-subdued hover:text-amber-400 hover:border-amber-400/50 transition-colors disabled:opacity-50"
                      >
                        <RotateCcw className={`w-3 h-3 ${restoring === b.filename ? 'animate-spin' : ''}`} />
                        {restoring === b.filename ? 'Restoring...' : 'Restore'}
                      </button>
                      <button
                        onClick={() => deleteBackup(b.filename)}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] bg-shogun-bg border border-shogun-border text-shogun-subdued hover:text-red-400 hover:border-red-400/50 transition-colors"
                      >
                        <Trash2 className="w-3 h-3" />
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* ═══════════════════════════════════════════ */}
      {/* TAB: Data Management                       */}
      {/* ═══════════════════════════════════════════ */}
      {activeTab === 'data' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 animate-in slide-in-from-bottom-4">
          
          {/* Statistics Sidebar */}
          <div className="lg:col-span-4 space-y-6">
            <section className="bg-shogun-card border border-shogun-border rounded-xl p-5">
              <h3 className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest mb-4 flex items-center gap-2">
                <Activity className="w-3 h-3" /> System Snapshot
              </h3>
              {statsLoading ? (
                <div className="flex items-center gap-3 py-6 text-shogun-subdued animate-pulse">
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span className="text-xs uppercase font-bold tracking-widest">Scanning DB...</span>
                </div>
              ) : stats ? (
                <div className="space-y-4">
                  {stats.tables && Object.entries(stats.tables).map(([table, count]: [string, any]) => (
                    <div key={table} className="flex justify-between items-center bg-shogun-bg p-3 rounded-lg border border-shogun-border">
                      <span className="text-[10px] text-shogun-subdued uppercase font-bold">{table.replace(/_/g, ' ')}</span>
                      <span className="text-sm font-bold text-shogun-text">{count}</span>
                    </div>
                  ))}
                  <div className="pt-4 border-t border-shogun-border text-center">
                    <p className="text-[9px] text-shogun-subdued uppercase font-bold">Total Rows</p>
                    <p className="text-lg font-bold text-shogun-blue">{stats.total_rows ?? '—'}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-[9px] text-shogun-subdued uppercase font-bold">Database Size</p>
                    <p className="text-2xl font-bold text-shogun-text">~{((stats.db_size_bytes || 0) / 1024 / 1024).toFixed(2)} MB</p>
                  </div>
                </div>
              ) : (
                <div className="py-6 text-center italic text-shogun-subdued text-xs">Click "Refresh" to scan the database.</div>
              )}
              <button 
                onClick={fetchBackupStats}
                className="w-full mt-4 py-2 border border-shogun-border rounded-lg text-[9px] font-bold uppercase tracking-widest hover:text-shogun-blue transition-colors"
              >
                Refresh Snapshot
              </button>
            </section>

            <div className="bg-indigo-500/5 border border-indigo-500/20 rounded-xl p-5">
              <div className="flex items-center gap-2 text-indigo-400 mb-2">
                <HelpCircle className="w-4 h-4" />
                <span className="text-[10px] font-bold uppercase tracking-widest">Why Export?</span>
              </div>
              <p className="text-[10px] text-shogun-subdued leading-relaxed">
                Your Shogun stores months of custom knowledge, trained skills, and secure identities. 
                Exporting allows you to migrate your entire mind-state to a new server or recover from hardware failure.
              </p>
            </div>
          </div>

          {/* Export/Import Actions */}
          <div className="lg:col-span-8 space-y-6">
            <section className="bg-shogun-card border border-shogun-border rounded-xl p-6 space-y-6">
              <div>
                <h3 className="text-lg font-bold text-shogun-text mb-1">Export Library</h3>
                <p className="text-xs text-shogun-subdued">Pack your entire intelligence store into a portable ZIP bundle.</p>
              </div>

              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Target Backup Directory</label>
                  <input 
                    type="text"
                    value={exportPath}
                    onChange={e => setExportPath(e.target.value)}
                    className="w-full bg-shogun-bg border border-shogun-border rounded-lg px-4 py-2.5 text-xs font-mono outline-none focus:border-shogun-blue text-white"
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <button 
                    onClick={() => handleExport('json')}
                    disabled={statsLoading}
                    className="p-6 bg-shogun-bg border border-shogun-border rounded-2xl text-left hover:border-shogun-blue transition-all group disabled:opacity-50"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <FileText className="w-6 h-6 text-shogun-blue" />
                      <ChevronRight className="w-4 h-4 text-shogun-subdued group-hover:translate-x-1 transition-transform" />
                    </div>
                    <div className="font-bold text-shogun-text">Safe JSON Bundle</div>
                    <p className="text-[10px] text-shogun-subdued mt-1">Exports every table individually. Safest for moving between Shogun versions.</p>
                  </button>
                  
                  <button 
                    onClick={() => handleExport('raw')}
                    disabled={statsLoading}
                    className="p-6 bg-shogun-bg border border-shogun-border rounded-2xl text-left hover:border-shogun-gold transition-all group disabled:opacity-50"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <Database className="w-6 h-6 text-shogun-gold" />
                      <ChevronRight className="w-4 h-4 text-shogun-subdued group-hover:translate-x-1 transition-transform" />
                    </div>
                    <div className="font-bold text-shogun-text">Raw Database Swap</div>
                    <p className="text-[10px] text-shogun-subdued mt-1">Copies the actual Shogun.db file directly. Fast, requires same version.</p>
                  </button>
                </div>
              </div>

              {exportMsg && (
                <div className={`p-3 rounded-lg flex items-center gap-3 text-xs font-bold uppercase ${
                  exportMsg.type === 'success' ? "bg-green-500/10 text-green-500 border border-green-500/20" : "bg-red-500/10 text-red-500 border border-red-500/20"
                }`}>
                  {exportMsg.type === 'success' ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                  {exportMsg.text}
                </div>
              )}
            </section>

            <section className="bg-shogun-card border border-dashed border-shogun-border rounded-xl flex flex-col items-center justify-center p-12 text-center group cursor-pointer hover:bg-shogun-blue/[0.02] hover:border-shogun-blue/40 transition-all">
              <div className="w-16 h-16 rounded-full bg-shogun-bg border border-shogun-border flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Download className="w-8 h-8 text-shogun-subdued group-hover:text-shogun-blue transition-colors" />
              </div>
              <h4 className="text-lg font-bold text-shogun-text mb-1">Import Shogun State</h4>
              <p className="text-xs text-shogun-subdued max-w-sm">
                Drag and drop a previously exported <strong>.zip</strong> bundle here to restore your agents, memories, and settings.
              </p>
              <input type="file" className="hidden" accept=".zip" />
            </section>
          </div>
        </div>
      )}

      {/* Info footer */}
      <div className="text-[11px] text-shogun-subdued border-t border-shogun-border/30 pt-4 space-y-1">
        <p>• Backups include: database, configs, governance documents, and environment settings.</p>
        <p>• Vector memory (Qdrant) is excluded by default due to size — enable in settings if needed.</p>
        <p>• After restoring a backup, restart Shogun for changes to take effect.</p>
      </div>
    </div>
  );
};
