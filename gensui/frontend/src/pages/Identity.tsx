import { useEffect, useState, useCallback } from 'react';
import {
  Key, Shield, Plus, Trash2, RefreshCw, Copy, Eye, EyeOff,
  CheckCircle, XCircle, RotateCw, Globe, Lock, Users
} from 'lucide-react';
import api from '../lib/api';
import { useTranslation } from '../i18n';

type Tab = 'service-accounts' | 'sso-providers';

interface ServiceAccount {
  id: string; name: string; description: string | null;
  api_key_prefix: string; role: string; scopes: Record<string, boolean> | null;
  rate_limit_rpm: number; is_active: boolean; expires_at: string | null;
  last_used_at: string | null; last_used_ip: string | null; usage_count: number;
  created_by: string | null; created_at: string | null;
  authentication_available?: boolean; configuration_only?: boolean;
}

interface SSOProvider {
  id: string; name: string; provider_type: string;
  issuer_url: string | null; client_id: string | null; has_client_secret: boolean;
  discovery_url: string | null; scopes: string; audience: string | null;
  claim_mapping: Record<string, string> | null;
  default_role: string; role_mapping: Record<string, string> | null;
  auto_create_users: boolean; auto_activate_users: boolean;
  allowed_domains: string | null; is_active: boolean; is_primary: boolean;
  created_by: string | null; created_at: string | null;
  authentication_available?: boolean; configuration_only?: boolean;
}

const ROLES = ['readonly', 'auditor', 'operator', 'admin'];
const PROVIDER_TYPES = [
  { value: 'oidc', label: 'OpenID Connect (stored configuration only)' },
  { value: 'saml', label: 'SAML 2.0 (not implemented)' },
  { value: 'spiffe', label: 'SPIFFE/SPIRE (not implemented)' },
];

export default function Identity() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>('service-accounts');
  const [accounts, setAccounts] = useState<ServiceAccount[]>([]);
  const [providers, setProviders] = useState<SSOProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newKey, setNewKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [copied, setCopied] = useState(false);

  // Create form state
  const [formName, setFormName] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formRole, setFormRole] = useState('readonly');
  const [formRateLimit, setFormRateLimit] = useState(60);

  // SSO form state
  const [showSSOCreate, setShowSSOCreate] = useState(false);
  const [ssoName, setSsoName] = useState('');
  const [ssoType, setSsoType] = useState('oidc');
  const [ssoIssuer, setSsoIssuer] = useState('');
  const [ssoClientId, setSsoClientId] = useState('');
  const [ssoClientSecret, setSsoClientSecret] = useState('');
  const [ssoScopes, setSsoScopes] = useState('openid profile email');
  const [ssoDefaultRole, setSsoDefaultRole] = useState('readonly');
  const [ssoAutoCreate, setSsoAutoCreate] = useState(false);
  const [ssoPrimary, setSsoPrimary] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (tab === 'service-accounts') {
        const r = await api.get('/identity/service-accounts');
        setAccounts(r.data.accounts || []);
      } else {
        const r = await api.get('/identity/sso-providers');
        setProviders(r.data.providers || []);
      }
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [tab]);

  useEffect(() => { load(); }, [load]);

  const createAccount = async () => {
    try {
      const r = await api.post('/identity/service-accounts', {
        name: formName, description: formDesc || null,
        role: formRole, rate_limit_rpm: formRateLimit,
      });
      setNewKey(r.data.api_key);
      setShowCreate(false);
      setFormName(''); setFormDesc(''); setFormRole('readonly'); setFormRateLimit(60);
      load();
    } catch (e) { console.error(e); }
  };

  const revokeAccount = async (id: string) => {
    if (!confirm('Revoke this service account? This will invalidate its API key.')) return;
    try { await api.post(`/identity/service-accounts/${id}/revoke`); load(); } catch (e) { console.error(e); }
  };

  const rotateKey = async (id: string) => {
    if (!confirm('Rotate API key? The current key will be invalidated.')) return;
    try {
      const r = await api.post(`/identity/service-accounts/${id}/rotate`);
      setNewKey(r.data.api_key);
      load();
    } catch (e) { console.error(e); }
  };

  const copyKey = () => {
    navigator.clipboard.writeText(newKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const createSSO = async () => {
    try {
      await api.post('/identity/sso-providers', {
        name: ssoName, provider_type: ssoType,
        issuer_url: ssoIssuer || null, client_id: ssoClientId || null,
        client_secret: ssoClientSecret || null, scopes: ssoScopes,
        default_role: ssoDefaultRole, auto_create_users: ssoAutoCreate,
        is_primary: ssoPrimary,
      });
      setShowSSOCreate(false);
      setSsoName(''); setSsoType('oidc'); setSsoIssuer(''); setSsoClientId('');
      setSsoClientSecret(''); setSsoScopes('openid profile email');
      setSsoDefaultRole('readonly'); setSsoAutoCreate(false); setSsoPrimary(false);
      load();
    } catch (e) { console.error(e); }
  };

  const deleteSSO = async (id: string) => {
    if (!confirm('Delete this stored provider configuration? No login path currently uses it.')) return;
    try { await api.delete(`/identity/sso-providers/${id}`); load(); } catch (e) { console.error(e); }
  };

  return (
    <div className="space-y-6 max-w-7xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gensui-50">{t('identity.title', 'Enterprise Identity')}</h1>
        <p className="text-sm text-gensui-400 mt-1">{t('identity.subtitle', 'Reserved identity configuration; service-account and SSO authentication are not available in this release')}</p>
      </div>

      <div className="glass-card p-4 border-l-4 border-l-amber-500 text-xs text-gensui-300 leading-relaxed">
        <strong className="text-amber-400">Authentication unavailable:</strong>{' '}
        This page can store reserved service-account and provider configuration, but Gensui APIs do not accept
        service-account keys and no OIDC, SAML, or SPIFFE login verifier is implemented in this release. Do not rely
        on these records for access control.
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gensui-800/40 p-1 rounded-lg border border-gensui-700/30">
        <button
          onClick={() => setTab('service-accounts')}
          className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs font-medium transition-all ${
            tab === 'service-accounts' ? 'bg-gensui-600/40 text-gensui-50 border border-gensui-500/30' : 'text-gensui-400 hover:text-gensui-200'
          }`}
        >
          <Key size={14} /> {t('identity.service_accounts', 'Service Accounts')}
        </button>
        <button
          onClick={() => setTab('sso-providers')}
          className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs font-medium transition-all ${
            tab === 'sso-providers' ? 'bg-gensui-600/40 text-gensui-50 border border-gensui-500/30' : 'text-gensui-400 hover:text-gensui-200'
          }`}
        >
          <Globe size={14} /> {t('identity.sso_providers', 'SSO / OIDC Providers')}
        </button>
      </div>

      {/* New API Key Banner */}
      {newKey && (
        <div className="glass-card p-4 border-l-4 border-l-amber-500 space-y-2">
          <div className="flex items-center gap-2 text-amber-400 text-sm font-bold">
            <Key size={16} /> Reserved Credential Generated — Not Accepted by Gensui APIs
          </div>
          <p className="text-xs text-gensui-400">This value is shown once for configuration staging. It does not authenticate any Gensui API endpoint in this release.</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-gensui-900 border border-gensui-700 rounded px-3 py-2 text-xs text-gensui-200 font-mono">
              {showKey ? newKey : '•'.repeat(newKey.length)}
            </code>
            <button onClick={() => setShowKey(!showKey)} className="p-2 text-gensui-400 hover:text-gensui-200">
              {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
            <button onClick={copyKey} className="gensui-btn-primary text-xs flex items-center gap-1">
              {copied ? <><CheckCircle size={14} /> Copied!</> : <><Copy size={14} /> Copy</>}
            </button>
          </div>
          <button onClick={() => { setNewKey(''); setShowKey(false); }} className="text-xs text-gensui-500 hover:text-gensui-300">
            Dismiss
          </button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <RefreshCw className="animate-spin text-gensui-500" size={24} />
        </div>
      ) : (
        <>
          {/* ── Service Accounts ── */}
          {tab === 'service-accounts' && (
            <div className="space-y-4">
              <div className="flex justify-end">
                <button onClick={() => setShowCreate(!showCreate)} className="gensui-btn-primary flex items-center gap-2 text-xs">
                  <Plus size={14} /> Create Reserved Credential Record
                </button>
              </div>

              {/* Create Form */}
              {showCreate && (
                <div className="glass-card p-5 space-y-4 border-l-4 border-l-cyan-500">
                  <h3 className="text-sm font-bold text-gensui-100">New Service Account</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs text-gensui-400 block mb-1">Name</label>
                      <input className="gensui-input w-full" value={formName} onChange={e => setFormName(e.target.value)} placeholder="CI/CD Pipeline" />
                    </div>
                    <div>
                      <label className="text-xs text-gensui-400 block mb-1">Role</label>
                      <select className="gensui-input w-full" value={formRole} onChange={e => setFormRole(e.target.value)}>
                        {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-gensui-400 block mb-1">Description</label>
                      <input className="gensui-input w-full" value={formDesc} onChange={e => setFormDesc(e.target.value)} placeholder="Optional description" />
                    </div>
                    <div>
                      <label className="text-xs text-gensui-400 block mb-1">Rate Limit (req/min)</label>
                      <input className="gensui-input w-full" type="number" value={formRateLimit} onChange={e => setFormRateLimit(Number(e.target.value))} />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={createAccount} disabled={!formName} className="gensui-btn-primary text-xs">Create</button>
                    <button onClick={() => setShowCreate(false)} className="gensui-btn-secondary text-xs">Cancel</button>
                  </div>
                </div>
              )}

              {/* Account List */}
              <div className="glass-card overflow-hidden">
                <table className="gensui-table">
                  <thead>
                    <tr><th>Name</th><th>Key Prefix</th><th>Role</th><th>Status</th><th>Usage</th><th>Last Used</th><th>Actions</th></tr>
                  </thead>
                  <tbody>
                    {accounts.map(sa => (
                      <tr key={sa.id}>
                        <td>
                          <div>
                            <div className="text-sm text-gensui-200 font-medium">{sa.name}</div>
                            {sa.description && <div className="text-xs text-gensui-500">{sa.description}</div>}
                          </div>
                        </td>
                        <td className="font-mono text-xs text-gensui-400">{sa.api_key_prefix}…</td>
                        <td>
                          <span className="text-xs px-2 py-0.5 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-400">
                            {sa.role}
                          </span>
                        </td>
                        <td>
                          {sa.is_active
                            ? <span className="flex items-center gap-1 text-xs text-amber-400"><XCircle size={12} /> Stored — auth unavailable</span>
                            : <span className="flex items-center gap-1 text-xs text-red-400"><XCircle size={12} /> Revoked</span>
                          }
                        </td>
                        <td className="text-sm text-gensui-300">{sa.usage_count.toLocaleString()}</td>
                        <td className="text-xs text-gensui-500">{sa.last_used_at ? new Date(sa.last_used_at).toLocaleString() : 'Never'}</td>
                        <td>
                          <div className="flex gap-1">
                            {sa.is_active && (
                              <>
                                <button onClick={() => rotateKey(sa.id)} className="p-1.5 text-gensui-400 hover:text-amber-400 transition-colors" title="Rotate key">
                                  <RotateCw size={14} />
                                </button>
                                <button onClick={() => revokeAccount(sa.id)} className="p-1.5 text-gensui-400 hover:text-red-400 transition-colors" title="Revoke">
                                  <XCircle size={14} />
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                    {accounts.length === 0 && (
                      <tr><td colSpan={7} className="text-center py-8 text-gensui-500">No service accounts</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── SSO Providers ── */}
          {tab === 'sso-providers' && (
            <div className="space-y-4">
              <div className="flex justify-end">
                <button onClick={() => setShowSSOCreate(!showSSOCreate)} className="gensui-btn-primary flex items-center gap-2 text-xs">
                  <Plus size={14} /> Store Provider Configuration
                </button>
              </div>

              {/* Create SSO Form */}
              {showSSOCreate && (
                <div className="glass-card p-5 space-y-4 border-l-4 border-l-purple-500">
                  <h3 className="text-sm font-bold text-gensui-100">Store Inactive SSO/OIDC Configuration</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs text-gensui-400 block mb-1">Provider Name</label>
                      <input className="gensui-input w-full" value={ssoName} onChange={e => setSsoName(e.target.value)} placeholder="Keycloak Production" />
                    </div>
                    <div>
                      <label className="text-xs text-gensui-400 block mb-1">Type</label>
                      <select className="gensui-input w-full" value={ssoType} onChange={e => setSsoType(e.target.value)}>
                        {PROVIDER_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-gensui-400 block mb-1">Issuer URL</label>
                      <input className="gensui-input w-full" value={ssoIssuer} onChange={e => setSsoIssuer(e.target.value)} placeholder="https://auth.example.com/realms/main" />
                    </div>
                    <div>
                      <label className="text-xs text-gensui-400 block mb-1">Client ID</label>
                      <input className="gensui-input w-full" value={ssoClientId} onChange={e => setSsoClientId(e.target.value)} placeholder="gensui-client" />
                    </div>
                    <div>
                      <label className="text-xs text-gensui-400 block mb-1">Client Secret</label>
                      <input className="gensui-input w-full" type="password" value={ssoClientSecret} onChange={e => setSsoClientSecret(e.target.value)} placeholder="••••••••" />
                    </div>
                    <div>
                      <label className="text-xs text-gensui-400 block mb-1">Scopes</label>
                      <input className="gensui-input w-full" value={ssoScopes} onChange={e => setSsoScopes(e.target.value)} />
                    </div>
                    <div>
                      <label className="text-xs text-gensui-400 block mb-1">Default Role</label>
                      <select className="gensui-input w-full" value={ssoDefaultRole} onChange={e => setSsoDefaultRole(e.target.value)}>
                        {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                      </select>
                    </div>
                    <div className="flex items-end gap-4">
                      <label className="flex items-center gap-2 text-xs text-gensui-300 cursor-pointer">
                        <input type="checkbox" checked={false} disabled className="rounded" />
                        Auto-create users (unavailable)
                      </label>
                      <label className="flex items-center gap-2 text-xs text-gensui-300 cursor-pointer">
                        <input type="checkbox" checked={false} disabled className="rounded" />
                        Primary login (unavailable)
                      </label>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={createSSO} disabled={!ssoName} className="gensui-btn-primary text-xs">Store Inactive Configuration</button>
                    <button onClick={() => setShowSSOCreate(false)} className="gensui-btn-secondary text-xs">Cancel</button>
                  </div>
                </div>
              )}

              {/* Provider List */}
              <div className="grid grid-cols-1 gap-4">
                {providers.map(p => (
                  <div key={p.id} className={`glass-card p-4 border-l-4 ${p.is_active ? 'border-l-purple-500' : 'border-l-gensui-600'}`}>
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <Globe size={20} className="text-purple-400" />
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="text-sm font-bold text-gensui-100">{p.name}</h3>
                            <span className="text-[10px] px-2 py-0.5 rounded-full border border-purple-500/30 bg-purple-500/10 text-purple-400 uppercase">
                              {p.provider_type}
                            </span>
                            <span className="text-[10px] px-2 py-0.5 rounded-full border border-amber-500/30 bg-amber-500/10 text-amber-400">
                              AUTH UNAVAILABLE
                            </span>
                            {p.is_primary && (
                              <span className="text-[10px] px-2 py-0.5 rounded-full border border-amber-500/30 bg-amber-500/10 text-amber-400">
                                PRIMARY
                              </span>
                            )}
                            {!p.is_active && (
                              <span className="text-[10px] px-2 py-0.5 rounded-full border border-red-500/30 bg-red-500/10 text-red-400">
                                DISABLED
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-gensui-500 mt-1">{p.issuer_url || 'No issuer URL'}</p>
                        </div>
                      </div>
                      <button onClick={() => deleteSSO(p.id)} className="p-1.5 text-gensui-500 hover:text-red-400 transition-colors" title="Delete provider">
                        <Trash2 size={14} />
                      </button>
                    </div>
                    <div className="grid grid-cols-3 gap-3 mt-3">
                      <div className="text-xs">
                        <span className="text-gensui-500">Client ID: </span>
                        <span className="text-gensui-300 font-mono">{p.client_id || '—'}</span>
                      </div>
                      <div className="text-xs">
                        <span className="text-gensui-500">Secret: </span>
                        <span className={p.has_client_secret ? 'text-emerald-400' : 'text-red-400'}>
                          {p.has_client_secret ? '✓ Configured' : '✗ Not set'}
                        </span>
                      </div>
                      <div className="text-xs">
                        <span className="text-gensui-500">Default role: </span>
                        <span className="text-cyan-400">{p.default_role}</span>
                      </div>
                      <div className="text-xs">
                        <span className="text-gensui-500">Scopes: </span>
                        <span className="text-gensui-300">{p.scopes}</span>
                      </div>
                      <div className="text-xs">
                        <span className="text-gensui-500">Auto-create: </span>
                        <span className={p.auto_create_users ? 'text-emerald-400' : 'text-gensui-500'}>
                          {p.auto_create_users ? 'Yes' : 'No'}
                        </span>
                      </div>
                      <div className="text-xs text-gensui-500">
                        Created: {p.created_at ? new Date(p.created_at).toLocaleDateString() : '—'}
                      </div>
                    </div>
                  </div>
                ))}
                {providers.length === 0 && (
                  <div className="glass-card p-8 text-center text-gensui-500">
                    <Globe size={32} className="mx-auto mb-3 opacity-30" />
                    <p className="text-sm">No SSO providers configured</p>
                    <p className="text-xs mt-1">Provider configuration can be staged, but single sign-on is not implemented in this release.</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
