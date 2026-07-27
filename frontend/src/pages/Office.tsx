import { useState, useEffect, useCallback } from 'react';
import {
  FileSpreadsheet,
  FileText,
  Presentation,
  Mail,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Shield,
  FolderOpen,
  RefreshCw,
  Trash2,
  Info,
  ChevronDown,
  ChevronUp,
  Save,
  Power,
  Loader2,
  HardDrive,
} from 'lucide-react';
import { setSafeObjectPath } from '../lib/safeObjectPath';

// ── Types ────────────────────────────────────────────────────────────

interface OfficeAppInfo {
  name: string;
  installed: boolean;
  version: string;
  build: string;
  path: string;
  error: string;
}

interface OfficeStatus {
  enabled: boolean;
  platform_supported: boolean;
  platform_name: string;
  minimum_posture: string;
  message: string;
  excel: OfficeAppInfo;
  word: OfficeAppInfo;
  powerpoint: OfficeAppInfo;
  outlook: OfficeAppInfo;
  folders_configured: boolean;
  process_status: Record<string, any>;
}

interface OfficeConfig {
  enabled: boolean;
  minimum_posture: string;
  folders: {
    input: string;
    output: string;
    templates: string;
    temp: string;
  };
  excel: { enabled: boolean; visible: boolean; allow_macros: boolean; allow_external_links: boolean; overwrite_originals: boolean; timeout_seconds: number };
  word: { enabled: boolean; visible: boolean; allow_macros: boolean; overwrite_originals: boolean; timeout_seconds: number };
  powerpoint: { enabled: boolean; visible: boolean; allow_macros: boolean; overwrite_originals: boolean; timeout_seconds: number };
  outlook: { enabled: boolean; mode: string; allow_send: boolean; require_confirmation: boolean; allow_external_recipients: boolean; allowed_recipient_domains: string[]; timeout_seconds: number };
  safety: { block_path_traversal: boolean; block_shortcuts: boolean; block_unc_paths: boolean; version_outputs: boolean; require_output_validation: boolean; max_file_size_mb: number };
  logging: { enabled: boolean; level: string };
  output_retention_days: number;
  temp_cleanup_on_startup: boolean;
}

// ── Subcomponents ────────────────────────────────────────────────────

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium tracking-wide ${
      ok ? 'bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30'
         : 'bg-red-500/15 text-red-400 ring-1 ring-red-500/30'
    }`}>
      {ok ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
      {label}
    </span>
  );
}

function AppCard({ app, appConfig, onToggle }: { app: OfficeAppInfo; appConfig: { enabled: boolean }; onToggle: () => void }) {
  const icons: Record<string, any> = {
    Excel: FileSpreadsheet,
    Word: FileText,
    PowerPoint: Presentation,
    Outlook: Mail,
  };
  const colors: Record<string, string> = {
    Excel: 'text-green-400',
    Word: 'text-blue-400',
    PowerPoint: 'text-orange-400',
    Outlook: 'text-cyan-400',
  };
  const Icon = icons[app.name] || HardDrive;
  const color = colors[app.name] || 'text-gray-400';

  return (
    <div className={`relative rounded-xl border p-5 transition-all duration-300 ${
      app.installed && appConfig.enabled
        ? 'border-[#d4a017]/30 bg-[#0f1422]/80 shadow-lg shadow-[#d4a017]/5'
        : 'border-[#1e2436] bg-[#0c1019]/60 opacity-70'
    }`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`p-2.5 rounded-lg bg-[#151b2e] ${color}`}>
            <Icon className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">{app.name}</h3>
            {app.version && <p className="text-xs text-gray-500 mt-0.5">v{app.version}</p>}
          </div>
        </div>
        <button
          onClick={onToggle}
          disabled={!app.installed}
          className={`relative w-10 h-5 rounded-full transition-all duration-300 ${
            appConfig.enabled && app.installed
              ? 'bg-[#d4a017]'
              : 'bg-[#1e2436]'
          } ${!app.installed ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
        >
          <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-md transition-transform duration-300 ${
            appConfig.enabled && app.installed ? 'translate-x-5.5 left-0' : 'left-0.5'
          }`} />
        </button>
      </div>
      <div className="flex gap-2 flex-wrap">
        <StatusBadge ok={app.installed} label={app.installed ? 'Installed' : 'Not found'} />
        {app.installed && (
          <StatusBadge ok={appConfig.enabled} label={appConfig.enabled ? 'Enabled' : 'Disabled'} />
        )}
      </div>
      {app.error && !app.installed && (
        <p className="text-xs text-red-400/70 mt-2 font-mono">{app.error}</p>
      )}
    </div>
  );
}

function SectionHeader({ icon: Icon, title, subtitle, expanded, onToggle }: {
  icon: any; title: string; subtitle?: string; expanded: boolean; onToggle: () => void;
}) {
  return (
    <button onClick={onToggle} className="w-full flex items-center justify-between p-4 rounded-xl bg-[#0f1422] border border-[#1e2436] hover:border-[#d4a017]/30 transition-all group">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-[#151b2e] text-[#d4a017]">
          <Icon className="w-4 h-4" />
        </div>
        <div className="text-left">
          <h2 className="text-sm font-semibold text-white">{title}</h2>
          {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
        </div>
      </div>
      {expanded ? <ChevronUp className="w-4 h-4 text-gray-500" /> : <ChevronDown className="w-4 h-4 text-gray-500" />}
    </button>
  );
}

function FolderInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-400 mb-1.5">{label}</label>
      <div className="flex items-center gap-2">
        <FolderOpen className="w-4 h-4 text-gray-500 flex-shrink-0" />
        <input
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={`C:\\Users\\...\\Documents\\Office\\${label.toLowerCase()}`}
          className="flex-1 bg-[#0a0e1a] border border-[#1e2436] rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#d4a017]/50 transition-colors font-mono"
        />
      </div>
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────────

export function Office() {
  const [status, setStatus] = useState<OfficeStatus | null>(null);
  const [config, setConfig] = useState<OfficeConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    folders: true,
    safety: false,
    outlook: false,
  });
  const [unsavedChanges, setUnsavedChanges] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

  const fetchData = useCallback(async () => {
    try {
      const [statusRes, configRes] = await Promise.all([
        fetch('/api/v1/office/status').then(r => r.json()),
        fetch('/api/v1/office/config').then(r => r.json()),
      ]);
      if (statusRes.success) setStatus(statusRes.data);
      if (configRes.success) setConfig(configRes.data);
    } catch (err) {
      console.error('Failed to load Office data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    setSaveMessage('');
    try {
      const res = await fetch('/api/v1/office/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      const data = await res.json();
      if (data.success) {
        setConfig(data.data);
        setUnsavedChanges(false);
        setSaveMessage('Configuration saved successfully');
        setTimeout(() => setSaveMessage(''), 3000);
      }
    } catch (err) {
      setSaveMessage('Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleDetect = async () => {
    setDetecting(true);
    try {
      const res = await fetch('/api/v1/office/detect', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        await fetchData(); // Refresh all data
      }
    } catch (err) {
      console.error('Detection failed:', err);
    } finally {
      setDetecting(false);
    }
  };

  const handleCleanup = async (type: 'temp' | 'outputs') => {
    try {
      const res = await fetch(`/api/v1/office/cleanup-${type}`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setSaveMessage(`Cleaned up ${data.data.removed_count} files`);
        setTimeout(() => setSaveMessage(''), 3000);
      }
    } catch (err) {
      console.error('Cleanup failed:', err);
    }
  };

  const updateConfig = (path: string, value: any) => {
    if (!config) return;
    const updated = setSafeObjectPath(config, path, value);
    setConfig(updated);
    setUnsavedChanges(true);
  };

  const toggleSection = (key: string) => {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="w-8 h-8 text-[#d4a017] animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-20">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Office App Mode</h1>
          <p className="text-sm text-gray-500 mt-1">
            Controlled Microsoft Office automation — Excel, Word, PowerPoint, Outlook
          </p>
        </div>
        <div className="flex items-center gap-3">
          {unsavedChanges && (
            <span className="text-xs text-amber-400 animate-pulse">Unsaved changes</span>
          )}
          {saveMessage && (
            <span className="text-xs text-emerald-400">{saveMessage}</span>
          )}
          <button
            onClick={handleSave}
            disabled={saving || !unsavedChanges}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              unsavedChanges
                ? 'bg-[#d4a017] text-black hover:bg-[#e6b422] shadow-lg shadow-[#d4a017]/20'
                : 'bg-[#1e2436] text-gray-500 cursor-not-allowed'
            }`}
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Save
          </button>
        </div>
      </div>

      {/* Master Enable */}
      {config && (
        <div className={`rounded-xl border p-5 transition-all duration-500 ${
          config.enabled
            ? 'border-[#d4a017]/40 bg-gradient-to-r from-[#0f1422] to-[#131926] shadow-xl shadow-[#d4a017]/10'
            : 'border-[#1e2436] bg-[#0c1019]/80'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className={`p-3 rounded-xl transition-colors duration-500 ${
                config.enabled ? 'bg-[#d4a017]/15 text-[#d4a017]' : 'bg-[#151b2e] text-gray-500'
              }`}>
                <Power className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">Office App Mode</h2>
                <p className="text-xs text-gray-500 mt-0.5">
                  {config.enabled ? 'Active — AI agents can interact with Office applications' : 'Disabled — Enable to allow Office automation'}
                </p>
              </div>
            </div>
            <button
              onClick={() => updateConfig('enabled', !config.enabled)}
              className={`relative w-14 h-7 rounded-full transition-all duration-500 ${
                config.enabled ? 'bg-[#d4a017]' : 'bg-[#1e2436]'
              }`}
            >
              <span className={`absolute top-1 w-5 h-5 rounded-full bg-white shadow-lg transition-transform duration-500 ${
                config.enabled ? 'translate-x-8 left-0' : 'left-1'
              }`} />
            </button>
          </div>
          {!status?.platform_supported && (
            <div className="mt-3 flex items-center gap-2 text-xs text-amber-400 bg-amber-500/10 rounded-lg p-3">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>{status?.message || 'Office App Mode requires Windows with Microsoft Office installed.'}</span>
            </div>
          )}
        </div>
      )}

      {/* Application Detection */}
      {status && config && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Applications</h2>
            <button
              onClick={handleDetect}
              disabled={detecting}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-gray-400 bg-[#151b2e] hover:bg-[#1e2436] border border-[#1e2436] hover:border-[#d4a017]/30 transition-all"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${detecting ? 'animate-spin' : ''}`} />
              Re-detect
            </button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <AppCard app={status.excel} appConfig={config.excel} onToggle={() => updateConfig('excel.enabled', !config.excel.enabled)} />
            <AppCard app={status.word} appConfig={config.word} onToggle={() => updateConfig('word.enabled', !config.word.enabled)} />
            <AppCard app={status.powerpoint} appConfig={config.powerpoint} onToggle={() => updateConfig('powerpoint.enabled', !config.powerpoint.enabled)} />
            <AppCard app={status.outlook} appConfig={config.outlook} onToggle={() => updateConfig('outlook.enabled', !config.outlook.enabled)} />
          </div>
        </div>
      )}

      {/* Folder Configuration */}
      {config && (
        <div className="space-y-2">
          <SectionHeader icon={FolderOpen} title="Approved Folders" subtitle="File boundaries for input, output, templates, and temp" expanded={expandedSections.folders} onToggle={() => toggleSection('folders')} />
          {expandedSections.folders && (
            <div className="rounded-xl border border-[#1e2436] bg-[#0f1422]/60 p-5 space-y-4 animate-in slide-in-from-top-2 duration-300">
              <div className="flex items-start gap-2 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                <Info className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
                <p className="text-xs text-blue-300">
                  All file operations are restricted to these folders. Files outside these boundaries will be rejected.
                  Configure all four folders before enabling Office App Mode.
                </p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FolderInput label="Input" value={config.folders.input} onChange={v => updateConfig('folders.input', v)} />
                <FolderInput label="Output" value={config.folders.output} onChange={v => updateConfig('folders.output', v)} />
                <FolderInput label="Templates" value={config.folders.templates} onChange={v => updateConfig('folders.templates', v)} />
                <FolderInput label="Temp" value={config.folders.temp} onChange={v => updateConfig('folders.temp', v)} />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Safety Settings */}
      {config && (
        <div className="space-y-2">
          <SectionHeader icon={Shield} title="Safety & Security" subtitle="Path validation, macro blocking, output versioning" expanded={expandedSections.safety} onToggle={() => toggleSection('safety')} />
          {expandedSections.safety && (
            <div className="rounded-xl border border-[#1e2436] bg-[#0f1422]/60 p-5 space-y-4 animate-in slide-in-from-top-2 duration-300">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {[
                  { key: 'safety.block_path_traversal', label: 'Block path traversal', desc: 'Prevent ../ escape attacks' },
                  { key: 'safety.block_shortcuts', label: 'Block .lnk files', desc: 'Prevent shortcut escape' },
                  { key: 'safety.block_unc_paths', label: 'Block UNC paths', desc: 'Prevent network path access' },
                  { key: 'safety.version_outputs', label: 'Version outputs', desc: 'Auto-timestamp output files' },
                  { key: 'safety.require_output_validation', label: 'Validate outputs', desc: 'Verify output file integrity' },
                  { key: 'temp_cleanup_on_startup', label: 'Cleanup temp on startup', desc: 'Remove temp files at boot' },
                ].map(item => {
                  const keys = item.key.split('.');
                  const val = keys.length === 2 ? (config as any)[keys[0]][keys[1]] : (config as any)[keys[0]];
                  return (
                    <label key={item.key} className="flex items-start gap-3 p-3 rounded-lg bg-[#0a0e1a] border border-[#1e2436] cursor-pointer hover:border-[#d4a017]/20 transition-colors">
                      <input
                        type="checkbox"
                        checked={val}
                        onChange={() => updateConfig(item.key, !val)}
                        className="mt-0.5 accent-[#d4a017]"
                      />
                      <div>
                        <p className="text-sm text-white font-medium">{item.label}</p>
                        <p className="text-xs text-gray-500 mt-0.5">{item.desc}</p>
                      </div>
                    </label>
                  );
                })}
              </div>
              <div className="flex items-center gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1.5">Max file size (MB)</label>
                  <input
                    type="number"
                    value={config.safety.max_file_size_mb}
                    onChange={e => updateConfig('safety.max_file_size_mb', parseInt(e.target.value) || 100)}
                    className="w-24 bg-[#0a0e1a] border border-[#1e2436] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#d4a017]/50"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1.5">Output retention (days)</label>
                  <input
                    type="number"
                    value={config.output_retention_days}
                    onChange={e => updateConfig('output_retention_days', parseInt(e.target.value) || 30)}
                    className="w-24 bg-[#0a0e1a] border border-[#1e2436] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#d4a017]/50"
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Outlook Configuration */}
      {config && (
        <div className="space-y-2">
          <SectionHeader icon={Mail} title="Outlook Settings" subtitle="Email mode, send permissions, recipient restrictions" expanded={expandedSections.outlook} onToggle={() => toggleSection('outlook')} />
          {expandedSections.outlook && (
            <div className="rounded-xl border border-[#1e2436] bg-[#0f1422]/60 p-5 space-y-4 animate-in slide-in-from-top-2 duration-300">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-2">Outlook Mode</label>
                <div className="flex gap-3">
                  {[
                    { value: 'draft_only', label: 'Draft Only', desc: 'Create drafts, never send' },
                    { value: 'confirmed_send', label: 'Confirmed Send', desc: 'Send with approval' },
                    { value: 'approved_recipient_send', label: 'Approved Recipients', desc: 'Auto-send to allowlist' },
                  ].map(mode => (
                    <button
                      key={mode.value}
                      onClick={() => updateConfig('outlook.mode', mode.value)}
                      className={`flex-1 p-3 rounded-lg border text-left transition-all ${
                        config.outlook.mode === mode.value
                          ? 'border-[#d4a017]/50 bg-[#d4a017]/10'
                          : 'border-[#1e2436] bg-[#0a0e1a] hover:border-[#d4a017]/20'
                      }`}
                    >
                      <p className={`text-sm font-medium ${config.outlook.mode === mode.value ? 'text-[#d4a017]' : 'text-white'}`}>{mode.label}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{mode.desc}</p>
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <label className="flex items-start gap-3 p-3 rounded-lg bg-[#0a0e1a] border border-[#1e2436] cursor-pointer hover:border-[#d4a017]/20 transition-colors">
                  <input type="checkbox" checked={config.outlook.require_confirmation} onChange={() => updateConfig('outlook.require_confirmation', !config.outlook.require_confirmation)} className="mt-0.5 accent-[#d4a017]" />
                  <div>
                    <p className="text-sm text-white font-medium">Require confirmation</p>
                    <p className="text-xs text-gray-500 mt-0.5">Human must approve before sending</p>
                  </div>
                </label>
                <label className="flex items-start gap-3 p-3 rounded-lg bg-[#0a0e1a] border border-[#1e2436] cursor-pointer hover:border-[#d4a017]/20 transition-colors">
                  <input type="checkbox" checked={config.outlook.allow_external_recipients} onChange={() => updateConfig('outlook.allow_external_recipients', !config.outlook.allow_external_recipients)} className="mt-0.5 accent-[#d4a017]" />
                  <div>
                    <p className="text-sm text-white font-medium">Allow external recipients</p>
                    <p className="text-xs text-gray-500 mt-0.5">Send to domains outside the allowlist</p>
                  </div>
                </label>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Quick Actions */}
      <div className="flex items-center gap-3 pt-2">
        <button
          onClick={() => handleCleanup('temp')}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium text-gray-400 bg-[#151b2e] hover:bg-[#1e2436] border border-[#1e2436] hover:border-[#d4a017]/30 transition-all"
        >
          <Trash2 className="w-3.5 h-3.5" />
          Clean temp folder
        </button>
        <button
          onClick={() => handleCleanup('outputs')}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium text-gray-400 bg-[#151b2e] hover:bg-[#1e2436] border border-[#1e2436] hover:border-[#d4a017]/30 transition-all"
        >
          <Trash2 className="w-3.5 h-3.5" />
          Purge expired outputs
        </button>
      </div>
    </div>
  );
}
