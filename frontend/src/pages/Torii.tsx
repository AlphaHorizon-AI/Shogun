import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  AppWindow,
  Calendar,
  CheckCircle2,
  Clock,
  Crosshair,
  Globe,
  HardDrive,
  Mail,
  Monitor,
  MousePointer2,
  Power,
  RefreshCw,
  Settings2,
  Shield,
  ShieldAlert,
  Sparkles,
  Terminal,
  Users,
  Zap,
} from 'lucide-react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { HarakiriModal } from '../components/HarakiriModal';
import { useTranslation } from '../i18n';
import { cn } from '../lib/utils';

type TierType = 'shrine' | 'guarded' | 'tactical' | 'campaign' | 'ronin';

interface Posture {
  active_tier: TierType;
  active_policy_id: string | null;
  active_policy_name: string | null;
  active_policy_tier: TierType | null;
  filesystem_mode: string;
  network_mode: string;
  shell_enabled: boolean;
  skill_auto_install: boolean;
  max_active_subagents: number;
  kill_switch_active: boolean;
  comms_read_email: boolean;
  comms_send_email: boolean;
  comms_read_calendar: boolean;
  comms_create_events: boolean;
  comms_list_cron: boolean;
  comms_manage_cron: boolean;
  mado_enabled: boolean;
  mado_headless_only: boolean;
  mado_autonomous_browsing: boolean;
  ronin_enabled: boolean;
  ronin_posture: string;
  ronin_max_sessions: number;
  ronin_mouse_enabled: boolean;
  ronin_keyboard_enabled: boolean;
}

interface Policy {
  id: string;
  name: string;
  tier: TierType;
  description: string | null;
  is_builtin: boolean;
}

const TIER_DEFS: Array<{
  id: TierType;
  label: string;
  color: string;
  bg: string;
  border: string;
}> = [
  { id: 'shrine', label: 'SHRINE', color: 'text-shogun-gold', bg: 'bg-shogun-gold/5', border: 'border-shogun-gold/40' },
  { id: 'guarded', label: 'GUARDED', color: 'text-green-400', bg: 'bg-green-400/5', border: 'border-green-400/40' },
  { id: 'tactical', label: 'TACTICAL', color: 'text-shogun-blue', bg: 'bg-shogun-blue/5', border: 'border-shogun-blue/40' },
  { id: 'campaign', label: 'CAMPAIGN', color: 'text-orange-400', bg: 'bg-orange-400/5', border: 'border-orange-400/40' },
  { id: 'ronin', label: 'RONIN', color: 'text-red-500', bg: 'bg-red-500/5', border: 'border-red-500/40' },
];

export function Torii() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [posture, setPosture] = useState<Posture | null>(null);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [showHarakiri, setShowHarakiri] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const tiers = useMemo(() => [
    { ...TIER_DEFS[0], badge: t('torii.badge_max'), description: t('torii.tier_shrine_desc') },
    { ...TIER_DEFS[1], badge: '', description: t('torii.tier_guarded_desc') },
    { ...TIER_DEFS[2], badge: t('torii.badge_default'), description: t('torii.tier_tactical_desc') },
    { ...TIER_DEFS[3], badge: '', description: t('torii.tier_campaign_desc') },
    { ...TIER_DEFS[4], badge: t('torii.badge_unsafe'), description: t('torii.tier_ronin_desc') },
  ], [t]);

  const customPolicies = useMemo(
    () => policies.filter(policy => !policy.is_builtin),
    [policies],
  );

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [postureResponse, policiesResponse] = await Promise.all([
        axios.get('/api/v1/security/posture'),
        axios.get('/api/v1/security/policies'),
      ]);
      setPosture(postureResponse.data.data);
      setPolicies(policiesResponse.data.data || []);
    } catch {
      setStatusMessage({ type: 'error', text: t('torii.posture_failed') });
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const flash = (type: 'success' | 'error', text: string) => {
    setStatusMessage({ type, text });
    window.setTimeout(() => setStatusMessage(null), 3500);
  };

  const selectPosture = async (selection: { tier: TierType } | { policy_id: string }, label: string) => {
    if (saving) return;
    setSaving(true);
    try {
      const response = await axios.put('/api/v1/security/posture/active', selection);
      setPosture(response.data.data);
      flash('success', `${t('torii.posture_updated')} ${label}`);
    } catch (error: unknown) {
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : null;
      flash('error', detail || t('torii.posture_failed'));
    } finally {
      setSaving(false);
    }
  };

  const handleKillSwitch = async () => {
    if (posture?.kill_switch_active) {
      if (!confirm(t('torii.reset_confirm'))) return;
      try {
        const response = await axios.delete('/api/v1/security/kill-switch');
        setPosture(response.data.data);
        flash('success', t('torii.reset_success'));
      } catch {
        flash('error', t('torii.reset_failed'));
      }
      return;
    }
    setShowHarakiri(true);
  };

  const confirmHarakiri = async () => {
    setShowHarakiri(false);
    try {
      const response = await axios.post('/api/v1/security/kill-switch');
      setPosture(response.data.data);
      flash('error', t('torii.harakiri_initiated'));
    } catch {
      flash('error', t('torii.harakiri_failed'));
    }
  };

  const activeLabel = posture?.active_policy_name || posture?.active_tier.toUpperCase();

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-12 animate-in fade-in duration-500">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <h2 className="shogun-title flex items-center gap-3 text-3xl font-bold">
            {t('torii.title', 'The Torii')}
            <span className="rounded border border-shogun-border bg-shogun-card px-2 py-0.5 text-[10px] font-normal uppercase tracking-[0.2em] text-shogun-subdued">
              {t('torii.badge')}
            </span>
          </h2>
          <p className="mt-1 text-sm text-shogun-subdued">
            Choose which security posture is active. Custom posture design belongs to ToolGate.
          </p>
        </div>
        <button
          onClick={handleKillSwitch}
          className={cn(
            'flex items-center gap-3 rounded-lg px-5 py-2.5 font-bold shadow-lg transition-all active:scale-95',
            posture?.kill_switch_active
              ? 'animate-pulse bg-red-500 text-white'
              : 'border border-red-500/50 bg-shogun-card text-red-500 hover:bg-red-500 hover:text-white',
          )}
        >
          <Power className="h-4 w-4" />
          <span className="text-sm">
            {posture?.kill_switch_active ? t('torii.reset_harakiri') : t('torii.harakiri')}
          </span>
        </button>
      </div>

      {statusMessage && (
        <div className={cn(
          'flex items-center gap-3 rounded-lg border p-4',
          statusMessage.type === 'success'
            ? 'border-green-500/20 bg-green-500/10 text-green-400'
            : 'border-red-500/20 bg-red-500/10 text-red-400',
        )}>
          {statusMessage.type === 'success'
            ? <CheckCircle2 className="h-5 w-5" />
            : <ShieldAlert className="h-5 w-5" />}
          <span className="text-sm font-bold">{statusMessage.text}</span>
        </div>
      )}

      <div className="shogun-card">
        <div className="flex flex-col justify-between gap-3 border-b border-shogun-border pb-5 md:flex-row md:items-center">
          <div>
            <h3 className="flex items-center gap-2 text-lg font-bold text-shogun-text">
              <Shield className="h-5 w-5 text-shogun-gold" />
              {t('torii.security_posture', 'Security Posture')}
            </h3>
            <p className="mt-1 text-xs text-shogun-subdued">
              Active: <span className="font-bold text-shogun-text">{activeLabel || t('common.loading')}</span>
              {saving && <span className="ml-2 animate-pulse">{t('common.saving')}</span>}
            </p>
          </div>
          <button
            onClick={() => navigate('/toolgate')}
            className="flex items-center gap-2 self-start rounded-lg border border-shogun-gold/30 bg-shogun-gold/5 px-3 py-2 text-xs font-bold text-shogun-gold hover:bg-shogun-gold/10"
          >
            <Settings2 className="h-4 w-4" /> Manage custom postures in ToolGate
          </button>
        </div>

        {loading ? (
          <div className="flex h-48 items-center justify-center">
            <RefreshCw className="h-7 w-7 animate-spin text-shogun-blue" />
          </div>
        ) : (
          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {tiers.map(tier => {
              const active = !posture?.active_policy_id && posture?.active_tier === tier.id;
              return (
                <button
                  key={tier.id}
                  onClick={() => selectPosture({ tier: tier.id }, tier.label)}
                  disabled={saving || active}
                  className={cn(
                    'rounded-xl border p-4 text-left transition-all disabled:cursor-default',
                    active ? `${tier.bg} ${tier.border}` : 'border-shogun-border hover:border-shogun-subdued hover:bg-[#0a0e1a]',
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className={cn('text-xs font-bold tracking-widest', tier.color)}>{tier.label}</span>
                    {active ? <CheckCircle2 className={cn('h-4 w-4', tier.color)} /> : <span className="h-4 w-4 rounded-full border border-shogun-border" />}
                  </div>
                  <p className="mt-2 text-[10px] leading-relaxed text-shogun-subdued">{tier.description}</p>
                  {tier.badge && <span className={cn('mt-3 inline-flex rounded border px-1.5 py-0.5 text-[8px] font-bold uppercase', tier.color, tier.border)}>{tier.badge}</span>}
                </button>
              );
            })}

            {customPolicies.map(policy => {
              const tier = TIER_DEFS.find(item => item.id === policy.tier) || TIER_DEFS[2];
              const active = posture?.active_policy_id === policy.id;
              return (
                <button
                  key={policy.id}
                  onClick={() => selectPosture({ policy_id: policy.id }, policy.name)}
                  disabled={saving || active}
                  className={cn(
                    'rounded-xl border p-4 text-left transition-all disabled:cursor-default',
                    active ? 'border-violet-400/50 bg-violet-500/[0.08]' : 'border-shogun-border hover:border-violet-400/40 hover:bg-violet-500/[0.04]',
                  )}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-2">
                      <Sparkles className="h-4 w-4 shrink-0 text-violet-300" />
                      <span className="truncate text-xs font-bold text-shogun-text">{policy.name}</span>
                    </div>
                    {active ? <CheckCircle2 className="h-4 w-4 shrink-0 text-violet-300" /> : <span className="h-4 w-4 shrink-0 rounded-full border border-shogun-border" />}
                  </div>
                  <p className="mt-2 line-clamp-2 min-h-8 text-[10px] leading-relaxed text-shogun-subdued">
                    {policy.description || 'Custom ToolGate posture'}
                  </p>
                  <span className={cn('mt-3 inline-flex rounded border px-1.5 py-0.5 text-[8px] font-bold uppercase', tier.color, tier.border, tier.bg)}>
                    Custom · Base {policy.tier}
                  </span>
                </button>
              );
            })}

            {customPolicies.length === 0 && (
              <button
                onClick={() => navigate('/toolgate')}
                className="flex min-h-32 flex-col items-center justify-center rounded-xl border border-dashed border-violet-400/25 p-4 text-center hover:bg-violet-500/[0.04]"
              >
                <Sparkles className="h-5 w-5 text-violet-300" />
                <span className="mt-2 text-xs font-bold text-violet-200">Create a custom posture</span>
                <span className="mt-1 text-[10px] text-shogun-subdued">Configure it in ToolGate, then activate it here.</span>
              </button>
            )}
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {posture && (
          <div className="shogun-card space-y-3 lg:col-span-2">
            <h4 className="text-xs font-bold uppercase tracking-widest text-shogun-subdued">{t('torii.current_constraints')}</h4>
            <div className="grid gap-x-8 gap-y-3 md:grid-cols-2">
              {[
                { icon: HardDrive, label: t('torii.filesystem'), value: posture.filesystem_mode },
                { icon: Globe, label: t('torii.network'), value: posture.network_mode },
                { icon: Terminal, label: t('torii.shell'), value: posture.shell_enabled ? t('torii.enabled') : t('torii.disabled') },
                { icon: Zap, label: t('torii.auto_skills'), value: posture.skill_auto_install ? t('torii.allowed') : t('torii.off') },
                { icon: Users, label: t('torii.max_agents'), value: String(posture.max_active_subagents) },
                { icon: Mail, label: t('torii.mail_access'), value: !posture.comms_read_email ? t('torii.disabled') : posture.comms_send_email ? t('torii.read_send') : t('torii.read_only') },
                { icon: Calendar, label: t('torii.calendar_access'), value: !posture.comms_read_calendar ? t('torii.disabled') : posture.comms_create_events ? t('torii.full_access') : t('torii.read_only') },
                { icon: Clock, label: t('torii.cron_access'), value: !posture.comms_list_cron ? t('torii.disabled') : posture.comms_manage_cron ? t('torii.full_access') : t('torii.read_only') },
                { icon: AppWindow, label: 'Mado Browser', value: !posture.mado_enabled ? t('torii.disabled') : posture.mado_headless_only ? 'Headless' : posture.mado_autonomous_browsing ? 'Autonomous' : 'Enabled' },
                { icon: Crosshair, label: 'Ronin Desktop', value: !posture.ronin_enabled ? t('torii.disabled') : posture.ronin_posture.replace('_', ' ') },
                { icon: Monitor, label: 'Ronin Sessions', value: !posture.ronin_enabled ? '—' : String(posture.ronin_max_sessions) },
                { icon: MousePointer2, label: 'Mouse/Keyboard', value: !posture.ronin_enabled ? '—' : posture.ronin_mouse_enabled && posture.ronin_keyboard_enabled ? 'Enabled' : posture.ronin_mouse_enabled ? 'Mouse Only' : posture.ronin_keyboard_enabled ? 'Keyboard Only' : t('torii.disabled') },
              ].map(({ icon: Icon, label, value }) => (
                <div key={label} className="flex items-center justify-between text-xs">
                  <span className="flex items-center gap-1.5 text-shogun-subdued"><Icon className="h-3 w-3" /> {label}</span>
                  <span className="font-mono font-bold text-shogun-text">{value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="shogun-card border-red-500/20 bg-red-500/5">
          <h4 className="mb-2 flex items-center gap-2 text-xs font-bold text-red-500">
            <AlertTriangle className="h-4 w-4" /> {t('torii.emergency_protocols')}
          </h4>
          <p className="text-[10px] leading-relaxed text-shogun-subdued">{t('torii.emergency_desc')}</p>
        </div>
      </div>

      {showHarakiri && (
        <HarakiriModal onConfirm={confirmHarakiri} onCancel={() => setShowHarakiri(false)} />
      )}
    </div>
  );
}
