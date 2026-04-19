import { useState, useEffect } from 'react';
import { HardDrive, Plus, Trash2, RotateCcw, Settings, Clock, Archive, ToggleLeft, ToggleRight } from 'lucide-react';

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

  useEffect(() => { loadBackups(); loadSettings(); }, []);

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <HardDrive className="w-6 h-6 text-shogun-gold" />
            Backups
          </h1>
          <p className="text-shogun-subdued mt-1">Protect your data with scheduled and manual backups.</p>
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
          
          {/* Enable toggle */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white font-medium">Automatic Backups</p>
              <p className="text-[11px] text-shogun-subdued">Automatically back up on a schedule.</p>
            </div>
            <button
              onClick={() => updateSettings({ enabled: !settings.enabled })}
              className="text-shogun-gold"
            >
              {settings.enabled ? <ToggleRight className="w-8 h-8" /> : <ToggleLeft className="w-8 h-8 text-shogun-subdued" />}
            </button>
          </div>

          {/* Interval */}
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

          {/* Max backups */}
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

          {/* Vector memory toggle */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white font-medium">Include Vector Memory</p>
              <p className="text-[11px] text-shogun-subdued">Include Qdrant data (significantly increases backup size).</p>
            </div>
            <button
              onClick={() => updateSettings({ include_vector_memory: !settings.include_vector_memory })}
              className="text-shogun-gold"
            >
              {settings.include_vector_memory ? <ToggleRight className="w-8 h-8" /> : <ToggleLeft className="w-8 h-8 text-shogun-subdued" />}
            </button>
          </div>
        </div>
      )}

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

      {/* Info footer */}
      <div className="text-[11px] text-shogun-subdued border-t border-shogun-border/30 pt-4 space-y-1">
        <p>• Backups include: database, configs, governance documents, and environment settings.</p>
        <p>• Vector memory (Qdrant) is excluded by default due to size — enable in settings if needed.</p>
        <p>• After restoring a backup, restart Shogun for changes to take effect.</p>
      </div>
    </div>
  );
};
