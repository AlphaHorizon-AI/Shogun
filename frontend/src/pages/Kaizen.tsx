import { useState, useEffect, useCallback, useMemo } from 'react';
import yaml from 'js-yaml';
import axios from 'axios';
import {
  Save,
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  BookOpen,
  Scale,
  Zap,
  History,
  FileCode,
  Lock,
  Download,
  ScrollText,
  FileText,
  Eye
} from "lucide-react";
import { cn } from '../lib/utils';

const API = 'http://localhost:8888/api/v1/kaizen';

// ── Simple markdown-to-HTML renderer (no deps) ───────────────
function renderMarkdown(md: string): string {
  return md
    .replace(/^### (.+)$/gm, '<h3 class="text-sm font-bold text-shogun-gold mt-4 mb-1">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-base font-bold text-shogun-gold mt-5 mb-2">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="text-lg font-bold text-shogun-gold mt-6 mb-2">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-shogun-text">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^- (.+)$/gm, '<li class="ml-4 text-sm text-[#c0c0c0] list-disc">$1</li>')
    .replace(/^---$/gm, '<hr class="border-shogun-border my-3" />')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>');
}

// ── Severity badge colors ────────────────────────────────────
const severityColors: Record<string, string> = {
  CRITICAL: 'text-red-400 bg-red-500/10 border-red-500/30',
  HIGH: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
  BALANCED: 'text-shogun-gold bg-shogun-gold/10 border-shogun-gold/30',
  MEDIUM: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  LOW: 'text-green-400 bg-green-500/10 border-green-500/30',
};
const severityIcons: Record<string, typeof ShieldCheck> = {
  CRITICAL: ShieldCheck,
  HIGH: BookOpen,
  BALANCED: Zap,
  MEDIUM: Scale,
  LOW: CheckCircle2,
};

type Tab = 'constitution' | 'mandate';

interface Revision {
  id: string;
  document_type: string;
  version: number;
  change_summary: string;
  created_at: string | null;
}

interface Directive {
  id: string;
  rule: string;
  severity: string;
}

export function Kaizen() {
  const [activeTab, setActiveTab] = useState<Tab>('constitution');

  // ── Constitution state ─────────────────────────────
  const [constitution, setConstitution] = useState('');
  const [constitutionLoaded, setConstitutionLoaded] = useState(false);
  const [constitutionDirty, setConstitutionDirty] = useState(false);

  // ── Mandate state ──────────────────────────────────
  const [mandate, setMandate] = useState('');
  const [mandateLoaded, setMandateLoaded] = useState(false);
  const [mandateDirty, setMandateDirty] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  // ── Shared state ───────────────────────────────────
  const [saving, setSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [revisions, setRevisions] = useState<Revision[]>([]);

  // ── YAML validation ────────────────────────────────
  const yamlStatus = useMemo(() => {
    if (!constitution.trim()) return { valid: true, error: null };
    try {
      yaml.load(constitution);
      return { valid: true, error: null };
    } catch (e: any) {
      return { valid: false, error: e.message || 'Invalid YAML' };
    }
  }, [constitution]);

  // ── Parse active directives from YAML ──────────────
  const directives: Directive[] = useMemo(() => {
    try {
      const data = yaml.load(constitution) as any;
      if (!data || !data.core_directives) return [];
      return (data.core_directives as any[])
        .filter((d: any) => d && typeof d === 'object')
        .map((d: any) => ({
          id: d.id || 'unknown',
          rule: d.rule || '',
          severity: (d.severity || 'MEDIUM').toUpperCase(),
        }));
    } catch {
      return [];
    }
  }, [constitution]);

  // ── Load constitution ──────────────────────────────
  const loadConstitution = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/constitution`);
      setConstitution(res.data.data.content);
      setConstitutionLoaded(true);
      setConstitutionDirty(false);
    } catch (err) {
      console.error('Failed to load constitution', err);
      setConstitutionLoaded(true);
    }
  }, []);

  // ── Load mandate ───────────────────────────────────
  const loadMandate = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/mandate`);
      setMandate(res.data.data.content);
      setMandateLoaded(true);
      setMandateDirty(false);
    } catch (err) {
      console.error('Failed to load mandate', err);
      setMandateLoaded(true);
    }
  }, []);

  // ── Load revisions ────────────────────────────────
  const loadRevisions = useCallback(async (type?: string) => {
    try {
      const url = type ? `${API}/revisions?document_type=${type}` : `${API}/revisions`;
      const res = await axios.get(url);
      setRevisions(res.data.data || []);
    } catch {
      setRevisions([]);
    }
  }, []);

  // ── Initial load ──────────────────────────────────
  useEffect(() => {
    loadConstitution();
    loadMandate();
    loadRevisions();
  }, [loadConstitution, loadMandate, loadRevisions]);

  // ── Reload revisions on tab switch ────────────────
  useEffect(() => {
    loadRevisions(activeTab);
  }, [activeTab, loadRevisions]);

  // ── Save handlers ─────────────────────────────────
  const handlePublishConstitution = async () => {
    if (!yamlStatus.valid) {
      setStatusMessage({ type: 'error', text: 'Cannot publish: YAML syntax is invalid.' });
      setTimeout(() => setStatusMessage(null), 4000);
      return;
    }
    setSaving(true);
    try {
      const res = await axios.put(`${API}/constitution`, {
        content: constitution,
        change_summary: 'Updated via Kaizen UI',
      });
      setStatusMessage({ type: 'success', text: res.data.data.message || 'Edicts published.' });
      setConstitutionDirty(false);
      loadRevisions('constitution');
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to publish edicts.';
      setStatusMessage({ type: 'error', text: detail });
    } finally {
      setSaving(false);
      setTimeout(() => setStatusMessage(null), 4000);
    }
  };

  const handlePublishMandate = async () => {
    setSaving(true);
    try {
      const res = await axios.put(`${API}/mandate`, {
        content: mandate,
        change_summary: 'Updated via Kaizen UI',
      });
      setStatusMessage({ type: 'success', text: res.data.data.message || 'Mandate updated.' });
      setMandateDirty(false);
      loadRevisions('mandate');
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to update mandate.';
      setStatusMessage({ type: 'error', text: detail });
    } finally {
      setSaving(false);
      setTimeout(() => setStatusMessage(null), 4000);
    }
  };

  // ── Download audit log ────────────────────────────
  const handleDownloadAuditLog = async () => {
    try {
      const res = await axios.get(`${API}/audit-log`, { responseType: 'blob' });
      const blob = new Blob([res.data], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'kaizen_audit_log.json';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to download audit log.' });
      setTimeout(() => setStatusMessage(null), 4000);
    }
  };

  const isConstitutionTab = activeTab === 'constitution';

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-6xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            Kaizen <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">Constitutional Layer</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">Define the fundamental laws and behavioral constraints for the entire Samurai Network.</p>
        </div>

        <button
          onClick={isConstitutionTab ? handlePublishConstitution : handlePublishMandate}
          disabled={saving || (isConstitutionTab && !yamlStatus.valid)}
          className="flex items-center gap-2 bg-shogun-gold hover:bg-shogun-gold/90 text-black font-bold py-2.5 px-6 rounded-lg transition-all shadow-shogun disabled:opacity-50"
        >
          {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {isConstitutionTab ? 'PUBLISH EDICTS' : 'SEAL MANDATE'}
        </button>
      </div>

      {/* Status Message */}
      {statusMessage && (
        <div className={cn(
          "p-4 rounded-lg flex items-center gap-3 animate-in slide-in-from-top-2",
          statusMessage.type === 'success' ? "bg-green-500/10 text-green-500 border border-green-500/20" : "bg-red-500/10 text-red-500 border border-red-500/20"
        )}>
          {statusMessage.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          <span className="text-sm font-bold uppercase tracking-widest">{statusMessage.text}</span>
        </div>
      )}

      {/* Tab Switcher */}
      <div className="flex gap-1 bg-[#050508] p-1 rounded-xl border border-shogun-border w-fit">
        <button
          onClick={() => setActiveTab('constitution')}
          className={cn(
            "flex items-center gap-2 px-5 py-2 rounded-lg text-xs font-bold uppercase tracking-widest transition-all",
            activeTab === 'constitution'
              ? "bg-shogun-gold/15 text-shogun-gold border border-shogun-gold/30"
              : "text-shogun-subdued hover:text-shogun-text"
          )}
        >
          <FileCode className="w-3.5 h-3.5" /> Constitution
        </button>
        <button
          onClick={() => setActiveTab('mandate')}
          className={cn(
            "flex items-center gap-2 px-5 py-2 rounded-lg text-xs font-bold uppercase tracking-widest transition-all",
            activeTab === 'mandate'
              ? "bg-shogun-gold/15 text-shogun-gold border border-shogun-gold/30"
              : "text-shogun-subdued hover:text-shogun-text"
          )}
        >
          <ScrollText className="w-3.5 h-3.5" /> The Mandate
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* ── Editor (left 2/3) ──────────────────────── */}
        <div className="lg:col-span-2 space-y-4">
          {activeTab === 'constitution' ? (
            /* Constitution YAML Editor */
            <div className="shogun-card !p-0 overflow-hidden border-shogun-gold/20 flex flex-col min-h-[600px]">
              <div className="p-4 border-b border-shogun-border bg-[#050508]/80 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <FileCode className="w-4 h-4 text-shogun-gold" />
                  <span className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">constitution.yaml</span>
                  {constitutionDirty && (
                    <span className="text-[9px] text-orange-400 bg-orange-500/10 px-2 py-0.5 rounded border border-orange-500/20 font-bold uppercase">unsaved</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <div className={cn("w-2 h-2 rounded-full", yamlStatus.valid ? "bg-green-500 animate-pulse" : "bg-red-500")} />
                  <span className={cn("text-[9px] tracking-tighter uppercase font-bold", yamlStatus.valid ? "text-shogun-subdued" : "text-red-400")}>
                    {yamlStatus.valid ? 'Valid Syntax' : 'Invalid Syntax'}
                  </span>
                </div>
              </div>
              <textarea
                value={constitution}
                onChange={(e) => { setConstitution(e.target.value); setConstitutionDirty(true); }}
                className="flex-1 w-full bg-[#02040a] p-6 font-mono text-sm text-[#d1d1d1] outline-none resize-none selection:bg-shogun-gold/20"
                spellCheck={false}
                placeholder={constitutionLoaded ? '' : 'Loading...'}
              />
              {!yamlStatus.valid && yamlStatus.error && (
                <div className="p-3 bg-red-500/5 border-t border-red-500/20 text-[10px] text-red-400 font-mono">
                  ⚠ {yamlStatus.error}
                </div>
              )}
              <div className="p-3 bg-shogun-card/50 border-t border-shogun-border flex justify-between items-center text-[9px] text-shogun-subdued">
                <span>{constitution.split('\n').length} lines</span>
                <span className="flex items-center gap-1"><Lock className="w-3 h-3" /> System Restricted Mode</span>
              </div>
            </div>
          ) : (
            /* Mandate Markdown Editor */
            <div className="shogun-card !p-0 overflow-hidden border-shogun-gold/20 flex flex-col min-h-[600px]">
              <div className="p-4 border-b border-shogun-border bg-[#050508]/80 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <ScrollText className="w-4 h-4 text-shogun-gold" />
                  <span className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">mandate.md</span>
                  {mandateDirty && (
                    <span className="text-[9px] text-orange-400 bg-orange-500/10 px-2 py-0.5 rounded border border-orange-500/20 font-bold uppercase">unsaved</span>
                  )}
                </div>
                <button
                  onClick={() => setShowPreview(!showPreview)}
                  className={cn(
                    "flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest px-3 py-1 rounded-md border transition-all",
                    showPreview
                      ? "text-shogun-gold bg-shogun-gold/10 border-shogun-gold/30"
                      : "text-shogun-subdued hover:text-shogun-text border-shogun-border hover:border-shogun-gold/30"
                  )}
                >
                  {showPreview ? <FileText className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                  {showPreview ? 'Edit' : 'Preview'}
                </button>
              </div>
              {showPreview ? (
                <div
                  className="flex-1 w-full bg-[#02040a] p-6 text-sm text-[#c0c0c0] overflow-auto prose-invert"
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(mandate) }}
                />
              ) : (
                <textarea
                  value={mandate}
                  onChange={(e) => { setMandate(e.target.value); setMandateDirty(true); }}
                  className="flex-1 w-full bg-[#02040a] p-6 font-mono text-sm text-[#d1d1d1] outline-none resize-none selection:bg-shogun-gold/20"
                  spellCheck={false}
                  placeholder={mandateLoaded ? '' : 'Loading...'}
                />
              )}
              <div className="p-3 bg-shogun-card/50 border-t border-shogun-border flex justify-between items-center text-[9px] text-shogun-subdued">
                <span>{mandate.split('\n').length} lines</span>
                <span className="flex items-center gap-1"><ScrollText className="w-3 h-3" /> Governance Document</span>
              </div>
            </div>
          )}
        </div>

        {/* ── Sidebar (right 1/3) ────────────────────── */}
        <div className="lg:col-span-1 space-y-6">
          {/* Active Principles (only on constitution tab) */}
          {activeTab === 'constitution' && (
            <div className="shogun-card space-y-6">
              <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                <Scale className="w-5 h-5 text-shogun-gold" /> Active Principles
                <span className="text-[9px] text-shogun-subdued bg-shogun-card px-1.5 py-0.5 rounded border border-shogun-border ml-auto">{directives.length}</span>
              </h3>
              <div className="space-y-3">
                {directives.length === 0 && (
                  <div className="text-[10px] text-shogun-subdued text-center py-4">
                    {yamlStatus.valid ? 'No core_directives found in YAML.' : 'Fix YAML syntax to see directives.'}
                  </div>
                )}
                {directives.map((rule) => {
                  const Icon = severityIcons[rule.severity] || Scale;
                  const colorClass = severityColors[rule.severity] || severityColors.MEDIUM;
                  return (
                    <div key={rule.id} className="p-4 bg-[#050508] border border-shogun-border rounded-xl flex items-start gap-3 group hover:border-shogun-gold/50 transition-all">
                      <Icon className={cn("w-4 h-4 mt-0.5 shrink-0", colorClass.split(' ')[0])} />
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-bold text-shogun-text capitalize">{rule.id.replace(/_/g, ' ')}</div>
                        <div className="text-[10px] text-shogun-subdued mt-0.5 leading-relaxed">{rule.rule}</div>
                        <span className={cn("inline-block text-[8px] font-bold uppercase tracking-widest mt-1 px-1.5 py-0.5 rounded border", colorClass)}>
                          {rule.severity}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Mandate summary (only on mandate tab) */}
          {activeTab === 'mandate' && (
            <div className="shogun-card space-y-4">
              <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                <ScrollText className="w-5 h-5 text-shogun-gold" /> About The Mandate
              </h3>
              <p className="text-[11px] text-shogun-subdued leading-relaxed">
                The Mandate is the Shogun's mission document. It defines the primary objectives, areas of responsibility,
                and operating principles that guide all decisions. Changes are injected into the Shogun's system prompt.
              </p>
              <div className="p-3 bg-shogun-gold/5 border border-shogun-gold/20 rounded-lg">
                <div className="text-[9px] text-shogun-gold font-bold uppercase tracking-widest mb-1">⚡ System Integration</div>
                <div className="text-[10px] text-shogun-subdued">
                  Key sections of this mandate are automatically injected into the Shogun's AI context on every interaction.
                </div>
              </div>
            </div>
          )}

          {/* Revision History */}
          <div className="shogun-card bg-shogun-gold/5 border-shogun-gold/20">
            <h4 className="text-xs font-bold text-shogun-gold flex items-center gap-2 mb-3">
              <History className="w-4 h-4" /> REVISION HISTORY
            </h4>
            <div className="space-y-3 max-h-[300px] overflow-y-auto">
              {revisions.length === 0 && (
                <div className="text-[10px] text-shogun-subdued text-center py-2">No revisions yet. Publish to create the first.</div>
              )}
              {revisions.map((rev, i) => (
                <div key={rev.id} className={cn("flex items-start gap-4", i > 2 && "opacity-50")}>
                  <div className={cn("w-1.5 h-1.5 rounded-full mt-1.5", i === 0 ? "bg-shogun-gold" : "bg-shogun-subdued")} />
                  <div>
                    <div className="text-[10px] text-shogun-text font-bold">
                      {rev.document_type === 'constitution' ? 'Constitution' : 'Mandate'} v{rev.version}
                    </div>
                    <div className="text-[9px] text-shogun-subdued">{rev.change_summary}</div>
                    {rev.created_at && (
                      <div className="text-[8px] text-shogun-subdued mt-0.5">
                        {new Date(rev.created_at).toLocaleDateString()} {new Date(rev.created_at).toLocaleTimeString()}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Download Audit Log */}
          <div className="p-4 text-center">
            <button
              onClick={handleDownloadAuditLog}
              className="flex items-center gap-2 mx-auto text-[10px] font-bold text-shogun-gold hover:text-shogun-text uppercase tracking-widest transition-all"
            >
              <Download className="w-3.5 h-3.5" />
              Download Audit Log (.JSON)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
