import { useState, useEffect, useMemo } from 'react';
import {
  Shield, Lock, AlertTriangle, Power, ShieldAlert,
  CheckCircle2, RefreshCw, Search, Eye, X, Plus, Save,
  Trash2, Copy, Check, Activity,
  Globe, HardDrive, Terminal, Zap, Users,
} from 'lucide-react';
import axios from 'axios';
import { cn } from '../lib/utils';
import { HarakiriModal } from '../components/HarakiriModal';
import { useTranslation } from '../i18n';

type TierType = 'shrine' | 'guarded' | 'tactical' | 'campaign' | 'ronin';

interface Posture {
  active_tier: TierType;
  filesystem_mode: string;
  network_mode: string;
  shell_enabled: boolean;
  skill_auto_install: boolean;
  max_active_subagents: number;
  kill_switch_enabled: boolean;
  kill_switch_active: boolean;
}

interface Policy {
  id: string;
  name: string;
  tier: TierType;
  description: string | null;
  permissions: {
    filesystem?: { mode?: string; allowed_paths?: string[]; allow_home_access?: boolean };
    network?: { mode?: string; allowed_domains?: string[]; allow_arbitrary_requests?: boolean };
    shell?: { enabled?: boolean; allowed_binaries?: string[] };
    skills?: { allow_auto_install?: boolean; require_approval?: boolean };
    subagents?: { allow_spawn?: boolean; max_active?: number; allow_auto_spawn?: boolean };
    memory?: { allow_write?: boolean; allow_bulk_delete?: boolean };
  };
  kill_switch_enabled: boolean;
  dry_run_supported: boolean;
  is_builtin: boolean;
  created_at: string;
}

const TIER_DEFS: { id: TierType; color: string; bg: string; border: string }[] = [
  { id: 'shrine',   color: 'text-shogun-gold',  bg: 'bg-shogun-gold/5',   border: 'border-shogun-gold/40' },
  { id: 'guarded',  color: 'text-green-400',    bg: 'bg-green-400/5',     border: 'border-green-400/40' },
  { id: 'tactical', color: 'text-shogun-blue',  bg: 'bg-shogun-blue/5',   border: 'border-shogun-blue/40' },
  { id: 'campaign', color: 'text-orange-400',   bg: 'bg-orange-400/5',    border: 'border-orange-400/40' },
  { id: 'ronin',    color: 'text-red-500',      bg: 'bg-red-500/5',       border: 'border-red-500/40' },
];


export function Torii() {
  const { t } = useTranslation();

  const TIERS = useMemo(() => [
    { ...TIER_DEFS[0], label: 'SHRINE',   badge: t('torii.badge_max'),     description: t('torii.tier_shrine_desc') },
    { ...TIER_DEFS[1], label: 'GUARDED',  badge: '',                       description: t('torii.tier_guarded_desc') },
    { ...TIER_DEFS[2], label: 'TACTICAL', badge: t('torii.badge_default'), description: t('torii.tier_tactical_desc') },
    { ...TIER_DEFS[3], label: 'CAMPAIGN', badge: '',                       description: t('torii.tier_campaign_desc') },
    { ...TIER_DEFS[4], label: 'RONIN',    badge: t('torii.badge_unsafe'),  description: t('torii.tier_ronin_desc') },
  ], [t]);

  const [loading, setLoading]       = useState(true);
  const [posture, setPosture]       = useState<Posture | null>(null);
  const [policies, setPolicies]     = useState<Policy[]>([]);
  const [saving, setSaving]         = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [showHarakiri, setShowHarakiri] = useState(false);

  // Search / filter
  const [search, setSearch] = useState('');
  const filteredPolicies = useMemo(() => {
    if (!search.trim()) return policies;
    const q = search.toLowerCase();
    return policies.filter(p =>
      p.name.toLowerCase().includes(q) ||
      p.tier.toLowerCase().includes(q) ||
      (p.description || '').toLowerCase().includes(q)
    );
  }, [policies, search]);

  // Modal: view policy
  const [viewPolicy, setViewPolicy] = useState<Policy | null>(null);

  // Modal: create policy
  const [showCreate, setShowCreate] = useState(false);
  const [newPolicy, setNewPolicy]   = useState({
    name: '', tier: 'tactical' as TierType, description: '',
    kill_switch_enabled: true, dry_run_supported: true,
  });

  // Copied confirmation
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [postureRes, policiesRes] = await Promise.all([
        axios.get('/api/v1/security/posture'),
        axios.get('/api/v1/security/policies'),
      ]);
      setPosture(postureRes.data.data);
      setPolicies(policiesRes.data.data || []);
    } catch (err) {
      console.error('Error fetching security data:', err);
    } finally {
      setLoading(false);
    }
  };

  const flash = (type: 'success' | 'error', text: string) => {
    setStatusMessage({ type, text });
    setTimeout(() => setStatusMessage(null), 3500);
  };

  // ── Posture change ──────────────────────────────────────────────
  const handlePostureChange = async (tier: TierType) => {
    if (saving || posture?.active_tier === tier) return;
    setSaving(true);
    try {
      const res = await axios.patch('/api/v1/security/posture', { active_tier: tier });
      setPosture(res.data.data);
      flash('success', t('torii.posture_updated') + ' ' + tier.toUpperCase());
    } catch {
      flash('error', t('torii.posture_failed'));
    } finally {
      setSaving(false);
    }
  };

  // ── Kill switch ─────────────────────────────────────────────────
  const handleKillSwitch = async () => {
    if (posture?.kill_switch_active) {
      // Reset — single confirm is fine for the safe direction
      if (!confirm(t('torii.reset_confirm'))) return;
      try {
        const res = await axios.delete('/api/v1/security/kill-switch');
        setPosture(res.data.data);
        flash('success', t('torii.reset_success'));
      } catch {
        flash('error', t('torii.reset_failed'));
      }
      return;
    }
    // Activate — open the two-step Harakiri modal
    setShowHarakiri(true);
  };

  const confirmHarakiri = async () => {
    setShowHarakiri(false);
    try {
      const res = await axios.post('/api/v1/security/kill-switch');
      setPosture(res.data.data);
      flash('error', t('torii.harakiri_initiated'));
    } catch {
      flash('error', t('torii.harakiri_failed'));
    }
  };

  // ── Create policy ───────────────────────────────────────────────
  const handleCreatePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await axios.post('/api/v1/security/policies', {
        name: newPolicy.name,
        tier: newPolicy.tier,
        description: newPolicy.description || null,
        kill_switch_enabled: newPolicy.kill_switch_enabled,
        dry_run_supported: newPolicy.dry_run_supported,
        permissions: {},
      });
      flash('success', t('torii.policy_created'));
      setShowCreate(false);
      setNewPolicy({ name: '', tier: 'tactical', description: '', kill_switch_enabled: true, dry_run_supported: true });
      fetchData();
    } catch {
      flash('error', t('torii.policy_create_failed'));
    } finally {
      setSaving(false);
    }
  };

  // ── Delete policy ───────────────────────────────────────────────
  const handleDeletePolicy = async (id: string, _name: string) => {
    if (!confirm(t('torii.policy_delete_confirm'))) return;
    try {
      await axios.delete(`/api/v1/security/policies/${id}`);
      flash('success', t('torii.policy_deleted'));
      if (viewPolicy?.id === id) setViewPolicy(null);
      fetchData();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || t('torii.policy_delete_failed');
      flash('error', detail);
    }
  };

  // ── Encrypt/Copy policy JSON ────────────────────────────────────
  const handleCopyPolicy = (policy: Policy) => {
    const exportable = {
      name: policy.name,
      tier: policy.tier,
      description: policy.description,
      permissions: policy.permissions,
      kill_switch_enabled: policy.kill_switch_enabled,
      dry_run_supported: policy.dry_run_supported,
    };
    navigator.clipboard.writeText(JSON.stringify(exportable, null, 2));
    setCopiedId(policy.id);
    setTimeout(() => setCopiedId(null), 2000);
  };


  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-6xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            {t('torii.title', 'The Torii')}{' '}
            <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">
              {t('torii.badge')}
            </span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">
            {t('torii.subtitle', 'Define the moral and technical boundaries of the Samurai Network.')}
          </p>
        </div>

        <button
          onClick={handleKillSwitch}
          className={cn(
            'flex items-center gap-3 font-bold py-2.5 px-5 rounded-lg transition-all shadow-lg active:scale-95',
            posture?.kill_switch_active
              ? 'bg-red-500 text-white animate-pulse'
              : 'bg-shogun-card border border-red-500/50 text-red-500 hover:bg-red-500 hover:text-white'
          )}
        >
          <Power className="w-4 h-4 shrink-0" />
          <div className="flex flex-col items-start">
            <span className="text-sm leading-tight">
              {posture?.kill_switch_active ? t('torii.reset_harakiri') : t('torii.harakiri')}
            </span>
            <span className="text-[9px] font-normal opacity-70 tracking-widest leading-tight">[{t('torii.kill_switch', 'Kill Switch')}]</span>
          </div>
        </button>
      </div>

      {/* Status banner */}
      {statusMessage && (
        <div className={cn(
          'p-4 rounded-lg flex items-center gap-3 animate-in slide-in-from-top-2',
          statusMessage.type === 'success'
            ? 'bg-green-500/10 text-green-500 border border-green-500/20'
            : 'bg-red-500/10 text-red-500 border border-red-500/20 shadow-[0_0_20px_rgba(239,68,68,0.2)]'
        )}>
          {statusMessage.type === 'success'
            ? <CheckCircle2 className="w-5 h-5 shrink-0" />
            : <ShieldAlert className="w-5 h-5 shrink-0" />
          }
          <span className="text-sm font-bold uppercase tracking-wider">{statusMessage.text}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* ── Left: Posture selector ── */}
        <div className="lg:col-span-1 space-y-5">
          <div className="shogun-card">
            <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text mb-1">
              <Shield className="w-5 h-5 text-shogun-gold" /> {t('torii.security_posture', 'Security Posture')}
            </h3>
            <p className="text-[10px] text-shogun-subdued mb-5 uppercase tracking-widest">
              {posture ? t('torii.active_label') + ': ' + posture.active_tier.toUpperCase() : t('common.loading')}
              {saving && <span className="ml-2 animate-pulse">{t('common.saving')}</span>}
            </p>

            <div className="space-y-2.5">
              {TIERS.map(tier => {
                const isActive = posture?.active_tier === tier.id;
                return (
                  <div
                    key={tier.id}
                    onClick={() => handlePostureChange(tier.id)}
                    className={cn(
                      'p-3.5 rounded-xl border cursor-pointer transition-all',
                      isActive
                        ? `${tier.bg} ${tier.border} shadow-sm`
                        : 'border-shogun-border hover:border-shogun-subdued hover:bg-[#0a0e1a]',
                      saving && 'pointer-events-none opacity-60'
                    )}
                  >
                    <div className="flex items-center justify-between mb-0.5">
                      <div className="flex items-center gap-2">
                        <span className={cn('text-xs font-bold tracking-widest', tier.color)}>
                          {tier.label}
                        </span>
                        {tier.badge && (
                          <span className={cn('text-[8px] border px-1.5 py-0.5 rounded font-bold uppercase', tier.color, tier.border)}>
                            {tier.badge}
                          </span>
                        )}
                      </div>
                      {isActive
                        ? <CheckCircle2 className={cn('w-3.5 h-3.5', tier.color)} />
                        : <div className="w-3.5 h-3.5 rounded-full border border-shogun-border" />
                      }
                    </div>
                    <p className="text-[10px] text-shogun-subdued leading-tight">{tier.description}</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Posture detail card */}
          {posture && (
            <div className="shogun-card space-y-3">
              <h4 className="text-xs font-bold text-shogun-subdued uppercase tracking-widest">{t('torii.current_constraints')}</h4>
              {[
                { icon: HardDrive, label: t('torii.filesystem'), value: posture.filesystem_mode },
                { icon: Globe,     label: t('torii.network'),    value: posture.network_mode },
                { icon: Terminal,  label: t('torii.shell'),      value: posture.shell_enabled ? t('torii.enabled') : t('torii.disabled') },
                { icon: Zap,       label: t('torii.auto_skills'), value: posture.skill_auto_install ? t('torii.allowed') : t('torii.off') },
                { icon: Users,     label: t('torii.max_agents'), value: String(posture.max_active_subagents) },
              ].map(({ icon: Icon, label, value }) => (
                <div key={label} className="flex items-center justify-between text-xs">
                  <span className="flex items-center gap-1.5 text-shogun-subdued">
                    <Icon className="w-3 h-3" /> {label}
                  </span>
                  <span className="font-mono font-bold text-shogun-text">{value}</span>
                </div>
              ))}
            </div>
          )}

          <div className="shogun-card bg-red-500/5 border-red-500/20">
            <h4 className="text-xs font-bold text-red-500 flex items-center gap-2 mb-2">
              <AlertTriangle className="w-4 h-4" /> {t('torii.emergency_protocols')}
            </h4>
            <p className="text-[10px] text-shogun-subdued leading-relaxed">
              {t('torii.emergency_desc')}
            </p>
          </div>
        </div>

        {/* ── Right: Policy Registry ── */}
        <div className="lg:col-span-2 space-y-5">
          <div className="shogun-card flex flex-col">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                <Lock className="w-5 h-5 text-shogun-blue" /> {t('torii.policy_registry')}
              </h3>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-shogun-subdued" />
                <input
                  type="text"
                  placeholder={t('torii.filter_policies')}
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="bg-[#050508] border border-shogun-border rounded-lg pl-8 pr-3 py-1.5 text-xs outline-none focus:border-shogun-blue"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto min-h-[300px]">
              {loading ? (
                <div className="flex flex-col items-center justify-center h-48 opacity-50">
                  <RefreshCw className="w-8 h-8 animate-spin text-shogun-blue mb-2" />
                  <span className="text-[10px] uppercase tracking-widest font-bold">{t('torii.auditing_shields')}</span>
                </div>
              ) : filteredPolicies.length === 0 ? (
                <div className="text-center py-16 text-shogun-subdued italic text-sm">
                  {search
                    ? t('torii.no_match')
                    : t('torii.no_policies')
                  }
                </div>
              ) : (
                <div className="space-y-3">
                  {filteredPolicies.map(policy => {
                    const tier = TIERS.find(t => t.id === policy.tier);
                    const ruleCount = Object.keys(policy.permissions || {}).length;
                    return (
                      <div
                        key={policy.id}
                        className="p-4 bg-[#050508] border border-shogun-border rounded-xl flex items-center justify-between group hover:border-shogun-blue/40 transition-all"
                      >
                        <div className="flex items-center gap-4 min-w-0">
                          <div className={cn(
                            'w-10 h-10 rounded-lg border flex items-center justify-center shrink-0',
                            tier?.bg, tier?.border, tier?.color
                          )}>
                            <Shield className="w-5 h-5" />
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <h4 className="text-sm font-bold text-shogun-text truncate">{policy.name}</h4>
                              {policy.is_builtin && (
                                <span className="text-[8px] border border-shogun-subdued/30 text-shogun-subdued px-1.5 py-0.5 rounded uppercase">{t('torii.built_in')}</span>
                              )}
                            </div>
                            <div className="flex items-center gap-2 mt-1 flex-wrap">
                              <span className={cn('text-[8px] border px-2 py-0.5 rounded font-bold uppercase', tier?.color, tier?.border, tier?.bg)}>
                                {policy.tier}
                              </span>
                              <span className="text-[10px] text-shogun-subdued flex items-center gap-1">
                                <Activity className="w-3 h-3" />
                                {ruleCount} {ruleCount === 1 ? t('torii.permission_block') : t('torii.permission_blocks')}
                              </span>
                              {policy.kill_switch_enabled && (
                                <span className="text-[9px] text-green-400 flex items-center gap-0.5">
                                  <CheckCircle2 className="w-2.5 h-2.5" /> {t('torii.kill_switch_label')}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 ml-3">
                          <button
                            onClick={() => setViewPolicy(policy)}
                            className="p-2 hover:bg-shogun-card rounded-lg text-shogun-subdued hover:text-shogun-text transition-colors"
                            title={t('torii.view_policy')}
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleCopyPolicy(policy)}
                            className="p-2 hover:bg-shogun-card rounded-lg text-shogun-subdued hover:text-shogun-gold transition-colors"
                            title={t('torii.export_json')}
                          >
                            {copiedId === policy.id
                              ? <Check className="w-4 h-4 text-green-400" />
                              : <Copy className="w-4 h-4" />
                            }
                          </button>
                          {!policy.is_builtin && (
                            <button
                              onClick={() => handleDeletePolicy(policy.id, policy.name)}
                              className="p-2 hover:bg-red-500/10 rounded-lg text-shogun-subdued hover:text-red-400 transition-colors"
                              title={t('torii.delete_policy_tooltip')}
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="mt-6 pt-5 border-t border-shogun-border flex items-center justify-between">
              <div className="flex items-center gap-2 text-[10px] text-shogun-subdued uppercase tracking-widest font-bold">
                <Lock className="w-3 h-3 text-shogun-gold" />
                {policies.length} {policies.length === 1 ? t('torii.policy_singular') : t('torii.policy_plural')} {t('torii.in_registry')}
              </div>
              <button
                onClick={() => setShowCreate(v => !v)}
                className="flex items-center gap-1.5 text-[10px] font-bold text-shogun-blue hover:text-shogun-gold uppercase tracking-widest transition-all"
              >
                {showCreate ? <X className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
                {showCreate ? t('common.cancel') : t('torii.create_tactical_policy')}
              </button>
            </div>

            {/* ── Create Policy form ───────────────────────────── */}
            {showCreate && (
              <form
                onSubmit={handleCreatePolicy}
                className="mt-5 pt-5 border-t border-shogun-border space-y-4 animate-in slide-in-from-bottom-2 duration-200"
              >
                <h4 className="text-sm font-bold text-shogun-text flex items-center gap-2">
                  <Plus className="w-4 h-4 text-shogun-blue" /> {t('torii.new_tactical_policy')}
                </h4>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t("torii.policy_name", "Policy Name *")}</label>
                    <input
                      required
                      type="text"
                      placeholder="e.g. Research Samurai Policy"
                      value={newPolicy.name}
                      onChange={e => setNewPolicy({ ...newPolicy, name: e.target.value })}
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t("torii.security_tier", "Security Tier *")}</label>
                    <select
                      value={newPolicy.tier}
                      onChange={e => setNewPolicy({ ...newPolicy, tier: e.target.value as TierType })}
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                    >
                      {TIERS.map(t => (
                        <option key={t.id} value={t.id}>
                          {t.label}{t.badge ? ` (${t.badge})` : ''}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-1.5 md:col-span-2">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t("torii.description", "Description")}</label>
                    <textarea
                      rows={2}
                      placeholder="What does this policy govern?"
                      value={newPolicy.description}
                      onChange={e => setNewPolicy({ ...newPolicy, description: e.target.value })}
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none resize-none"
                    />
                  </div>

                  <div className="flex items-center gap-4 md:col-span-2">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={newPolicy.kill_switch_enabled}
                        onChange={e => setNewPolicy({ ...newPolicy, kill_switch_enabled: e.target.checked })}
                        className="accent-shogun-blue"
                      />
                      <span className="text-xs text-shogun-subdued">{t('torii.kill_switch_enabled')}</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={newPolicy.dry_run_supported}
                        onChange={e => setNewPolicy({ ...newPolicy, dry_run_supported: e.target.checked })}
                        className="accent-shogun-blue"
                      />
                      <span className="text-xs text-shogun-subdued">{t('torii.dry_run_supported')}</span>
                    </label>
                  </div>
                </div>

                <div className="flex gap-3 pt-1">
                  <button
                    type="submit"
                    disabled={saving}
                    className="flex items-center gap-2 px-5 py-2.5 bg-shogun-blue hover:bg-shogun-blue/90 disabled:opacity-50 text-white font-bold rounded-lg text-sm transition-all"
                  >
                    {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    {t('torii.save_policy')}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowCreate(false)}
                    className="px-4 py-2.5 text-sm text-shogun-subdued hover:text-shogun-text transition-colors"
                  >
                    {t('common.cancel')}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      </div>

      {/* ── View Policy Modal ──────────────────────────────────────── */}
      {viewPolicy && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setViewPolicy(null)} />
          <div className="relative bg-shogun-bg border border-shogun-border rounded-2xl shadow-2xl w-full max-w-2xl mx-4 max-h-[85vh] flex flex-col">
            {/* Modal header */}
            <div className="flex items-center justify-between p-6 border-b border-shogun-border shrink-0">
              <div>
                <h3 className="font-bold text-shogun-text text-lg">{viewPolicy.name}</h3>
                <div className="flex items-center gap-2 mt-1">
                  {(() => { const t = TIERS.find(x => x.id === viewPolicy.tier); return t ? (
                    <span className={cn('text-[9px] border px-2 py-0.5 rounded font-bold uppercase', t.color, t.border, t.bg)}>
                      {t.label}
                    </span>
                  ) : null; })()}
                  {viewPolicy.is_builtin && (
                    <span className="text-[8px] border border-shogun-subdued/30 text-shogun-subdued px-1.5 py-0.5 rounded uppercase">{t('torii.built_in')}</span>
                  )}
                  <span className="text-[10px] text-shogun-subdued">
                    {t('torii.created')} {new Date(viewPolicy.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleCopyPolicy(viewPolicy)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-shogun-blue border border-shogun-blue/30 rounded-lg hover:bg-shogun-blue/10 transition-all"
                >
                  {copiedId === viewPolicy.id ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                  {copiedId === viewPolicy.id ? t('torii.copied') : t('torii.export_json_btn')}
                </button>
                <button onClick={() => setViewPolicy(null)} className="p-2 text-shogun-subdued hover:text-shogun-text rounded-lg hover:bg-shogun-card transition-all">
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Modal body */}
            <div className="overflow-y-auto flex-1 p-6 space-y-5">
              {viewPolicy.description && (
                <p className="text-sm text-shogun-subdued leading-relaxed">{viewPolicy.description}</p>
              )}

              {/* Flags */}
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: t('torii.kill_switch_label'), value: viewPolicy.kill_switch_enabled },
                  { label: t('torii.dry_run_label'), value: viewPolicy.dry_run_supported },
                ].map(({ label, value }) => (
                  <div key={label} className="flex items-center gap-2 p-3 bg-[#050508] border border-shogun-border rounded-lg">
                    {value ? <CheckCircle2 className="w-4 h-4 text-green-400" /> : <X className="w-4 h-4 text-red-400" />}
                    <span className="text-xs text-shogun-subdued">{label}</span>
                    <span className="text-xs font-bold text-shogun-text ml-auto">{value ? t('common.yes') : t('common.no')}</span>
                  </div>
                ))}
              </div>

              {/* Permissions JSON */}
              <div className="space-y-2">
                <h4 className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('torii.permission_blocks_title')}</h4>
                {Object.keys(viewPolicy.permissions).length === 0 ? (
                  <p className="text-xs text-shogun-subdued italic">{t('torii.no_permissions')}</p>
                ) : (
                  Object.entries(viewPolicy.permissions).map(([category, perms]) => (
                    <div key={category} className="bg-[#050508] border border-shogun-border rounded-lg overflow-hidden">
                      <div className="px-4 py-2 bg-shogun-card border-b border-shogun-border">
                        <span className="text-[10px] font-bold text-shogun-blue uppercase tracking-widest">{category}</span>
                      </div>
                      <pre className="p-4 text-[11px] text-shogun-text font-mono overflow-x-auto leading-relaxed">
                        {JSON.stringify(perms, null, 2)}
                      </pre>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Modal footer */}
            {!viewPolicy.is_builtin && (
              <div className="p-4 border-t border-shogun-border shrink-0">
                <button
                  onClick={() => handleDeletePolicy(viewPolicy.id, viewPolicy.name)}
                  className="flex items-center gap-2 text-xs text-red-400/60 hover:text-red-400 transition-colors px-3 py-2 border border-red-400/10 hover:border-red-400/30 rounded-lg"
                >
                  <Trash2 className="w-3 h-3" /> {t('torii.delete_this_policy')}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Harakiri two-step confirmation modal */}
      {showHarakiri && (
        <HarakiriModal
          onConfirm={confirmHarakiri}
          onCancel={() => setShowHarakiri(false)}
        />
      )}
    </div>
  );
}
