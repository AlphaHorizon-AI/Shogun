import { useEffect, useState } from 'react';
import axios from 'axios';
import { AlertCircle, Loader2, MessageCircle, Plus, ShieldCheck, Trash2, Users } from 'lucide-react';
import { cn } from '../../lib/utils';
import { useTranslation } from '../../i18n';

type TeamMode = 'single' | 'team';
type MemberChannel = 'telegram' | 'microsoft_teams';

interface TeamMember {
  id: string;
  display_name: string;
  email?: string | null;
  role: 'admin' | 'member';
  is_primary: boolean;
  active: boolean;
  channel: 'web' | MemberChannel;
  telegram_user_id?: string | null;
  teams_aad_object_id?: string | null;
  teams_user_principal_name?: string | null;
}

interface TeamState { mode: TeamMode; members: TeamMember[]; }

const emptyForm = {
  display_name: '', email: '', channel: 'telegram' as MemberChannel,
  telegram_user_id: '', teams_aad_object_id: '', teams_user_principal_name: '',
};

function errorMessage(error: any): string {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(item => item.msg).filter(Boolean).join(' ');
  return error?.message || 'The team configuration could not be saved.';
}

export function TeamMembersPanel() {
  const { t } = useTranslation();
  const [state, setState] = useState<TeamState | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get('/api/v1/team');
      setState(response.data.data);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const switchMode = async (mode: TeamMode) => {
    if (!state || saving || state.mode === mode) return;
    setSaving(true);
    setError(null);
    try {
      const response = await axios.put('/api/v1/team/mode', { mode });
      setState(response.data.data);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setSaving(false);
    }
  };

  const addMember = async () => {
    if (!state || saving) return;
    setSaving(true);
    setError(null);
    try {
      await axios.post('/api/v1/team/members', {
        ...form,
        telegram_user_id: form.channel === 'telegram' ? form.telegram_user_id.trim() || null : null,
        teams_aad_object_id: form.channel === 'microsoft_teams' ? form.teams_aad_object_id.trim() || null : null,
        teams_user_principal_name: form.channel === 'microsoft_teams' ? form.teams_user_principal_name.trim() || null : null,
      });
      setForm(emptyForm);
      const response = await axios.get('/api/v1/team');
      setState(response.data.data);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setSaving(false);
    }
  };

  const removeMember = async (member: TeamMember) => {
    if (member.is_primary || !window.confirm(`${t('katana.team.delete_prefix', 'Delete')} ${member.display_name} ${t('katana.team.delete_suffix', 'from this Shogun team? Their channel access will be revoked immediately.')}`)) return;
    setDeletingId(member.id);
    setError(null);
    try {
      await axios.delete(`/api/v1/team/members/${member.id}`);
      setState(current => current ? {...current, members: current.members.filter(item => item.id !== member.id)} : current);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setDeletingId(null);
    }
  };

  if (loading) return <div className="shogun-card flex items-center gap-3 text-sm text-shogun-subdued"><Loader2 className="h-4 w-4 animate-spin" /> {t('katana.team.loading', 'Loading team configuration…')}</div>;
  if (!state) return <div className="shogun-card text-sm text-red-300">{t('katana.team.unavailable', 'Team configuration is unavailable.')}</div>;

  const ordinaryMembers = state.members.filter(member => !member.is_primary);

  return (
    <div className="space-y-6">
      <div className="shogun-card space-y-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h3 className="flex items-center gap-2 text-lg font-bold text-shogun-text"><Users className="h-5 w-5 text-shogun-blue" /> {t('katana.team.title', 'Team Mode')}</h3>
            <p className="mt-1 text-xs text-shogun-subdued">{t('katana.team.description', 'Only the Primary Admin uses Tenshu. Team Members communicate through Telegram or Microsoft Teams.')}</p>
          </div>
          <div className="inline-flex rounded-lg border border-shogun-border bg-shogun-bg p-1" role="group" aria-label="Installation mode">
            {(['single', 'team'] as TeamMode[]).map(mode => (
              <button key={mode} type="button" onClick={() => void switchMode(mode)} disabled={saving} className={cn('rounded-md px-4 py-2 text-[10px] font-bold uppercase tracking-widest transition-colors disabled:opacity-50', state.mode === mode ? 'bg-shogun-blue text-white' : 'text-shogun-subdued hover:text-shogun-text')}>
                {mode === 'single' ? t('katana.team.single_user', 'Single User') : t('katana.team.team_mode', 'Team Mode')}
              </button>
            ))}
          </div>
        </div>
        <div className={cn('rounded-lg border p-3 text-xs', state.mode === 'team' ? 'border-emerald-500/20 bg-emerald-500/5 text-emerald-300' : 'border-amber-500/20 bg-amber-500/5 text-amber-200')}>
          {state.mode === 'team'
            ? `${ordinaryMembers.length} ${ordinaryMembers.length === 1 ? t('katana.team.member_active_singular', 'Team Member can currently be recognized through the configured channel.') : t('katana.team.member_active_plural', 'Team Members can currently be recognized through their configured channels.')}`
            : t('katana.team.single_active', 'Single-user mode is active. Saved Team Members are retained, but all of their channel access is disabled.')}
        </div>
      </div>

      {error && <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300"><AlertCircle className="h-4 w-4" />{error}</div>}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(300px,0.7fr)]">
        <div className="space-y-3">
          {state.members.map(member => (
            <div key={member.id} className="shogun-card flex items-start justify-between gap-4">
              <div className="flex min-w-0 gap-3">
                <div className={cn('rounded-lg p-2', member.is_primary ? 'bg-amber-500/10 text-amber-300' : 'bg-blue-500/10 text-blue-300')}>
                  {member.is_primary ? <ShieldCheck className="h-5 w-5" /> : <MessageCircle className="h-5 w-5" />}
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-shogun-text">{member.display_name}</span>
                    <span className="rounded border border-shogun-border px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-shogun-subdued">{member.is_primary ? t('katana.team.primary_admin', 'Primary Admin') : member.channel === 'telegram' ? 'Telegram' : 'Microsoft Teams'}</span>
                    <span className={cn('h-2 w-2 rounded-full', member.active ? 'bg-emerald-400' : 'bg-shogun-subdued')} title={member.active ? t('katana.team.active', 'Active') : t('katana.team.disabled', 'Disabled')} />
                  </div>
                  {member.email && <p className="mt-1 truncate text-xs text-shogun-subdued">{member.email}</p>}
                  {!member.is_primary && <p className="mt-1 break-all font-mono text-[10px] text-shogun-subdued">{member.channel === 'telegram' ? `User ID: ${member.telegram_user_id}` : member.teams_user_principal_name || `Object ID: ${member.teams_aad_object_id}`}</p>}
                </div>
              </div>
              {!member.is_primary && (
                <button type="button" onClick={() => void removeMember(member)} disabled={deletingId === member.id} className="rounded-lg p-2 text-shogun-subdued transition-colors hover:bg-red-500/10 hover:text-red-400 disabled:opacity-50" title={t('katana.team.delete_member', 'Delete Team Member')}>
                  {deletingId === member.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                </button>
              )}
            </div>
          ))}
        </div>

        <div className={cn('shogun-card space-y-4 self-start', state.mode !== 'team' && 'opacity-60')}>
          <h3 className="flex items-center gap-2 font-bold text-shogun-text"><Plus className="h-4 w-4 text-shogun-blue" /> {t('katana.team.add_member', 'Add Team Member')}</h3>
          <input value={form.display_name} onChange={event => setForm({...form, display_name: event.target.value})} disabled={state.mode !== 'team'} placeholder={t('katana.team.full_name', 'Full name')} className="w-full rounded-lg border border-shogun-border bg-shogun-bg px-3 py-2 text-sm text-shogun-text outline-none focus:border-shogun-blue disabled:cursor-not-allowed" />
          <input value={form.email} onChange={event => setForm({...form, email: event.target.value})} disabled={state.mode !== 'team'} placeholder={t('katana.team.email_optional', 'Email (optional)')} className="w-full rounded-lg border border-shogun-border bg-shogun-bg px-3 py-2 text-sm text-shogun-text outline-none focus:border-shogun-blue disabled:cursor-not-allowed" />
          <select value={form.channel} onChange={event => setForm({...form, channel: event.target.value as MemberChannel})} disabled={state.mode !== 'team'} className="w-full rounded-lg border border-shogun-border bg-shogun-bg px-3 py-2 text-sm text-shogun-text outline-none focus:border-shogun-blue disabled:cursor-not-allowed">
            <option value="telegram">Telegram</option><option value="microsoft_teams">Microsoft Teams</option>
          </select>
          {form.channel === 'telegram' ? (
            <input value={form.telegram_user_id} onChange={event => setForm({...form, telegram_user_id: event.target.value})} disabled={state.mode !== 'team'} placeholder={t('katana.team.telegram_user_id', 'Telegram user ID')} className="w-full rounded-lg border border-shogun-border bg-shogun-bg px-3 py-2 font-mono text-sm text-shogun-text outline-none focus:border-shogun-blue disabled:cursor-not-allowed" />
          ) : (
            <><input value={form.teams_user_principal_name} onChange={event => setForm({...form, teams_user_principal_name: event.target.value})} disabled={state.mode !== 'team'} placeholder={t('katana.team.teams_email', 'Teams sign-in email')} className="w-full rounded-lg border border-shogun-border bg-shogun-bg px-3 py-2 font-mono text-sm text-shogun-text outline-none focus:border-shogun-blue disabled:cursor-not-allowed" /><input value={form.teams_aad_object_id} onChange={event => setForm({...form, teams_aad_object_id: event.target.value})} disabled={state.mode !== 'team'} placeholder={t('katana.team.entra_id', 'Entra Object ID (optional if email is set)')} className="w-full rounded-lg border border-shogun-border bg-shogun-bg px-3 py-2 font-mono text-sm text-shogun-text outline-none focus:border-shogun-blue disabled:cursor-not-allowed" /></>
          )}
          <button type="button" onClick={() => void addMember()} disabled={state.mode !== 'team' || saving || !form.display_name.trim() || (form.channel === 'telegram' ? !form.telegram_user_id.trim() : !(form.teams_user_principal_name.trim() || form.teams_aad_object_id.trim()))} className="flex w-full items-center justify-center gap-2 rounded-lg bg-shogun-blue px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-white transition-colors hover:bg-shogun-blue/80 disabled:cursor-not-allowed disabled:opacity-40">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} {t('katana.team.add_button', 'Add Member')}
          </button>
          <p className="text-[10px] leading-relaxed text-shogun-subdued">{t('katana.team.memory_notice', 'Each member receives a separate memory identity. Deleting a member revokes access and archives that member’s private memory slot.')}</p>
        </div>
      </div>
    </div>
  );
}
