import ChatGPTOAuthPanel, { type ChatGPTSignIn } from './katana/ChatGPTOAuthPanel';
import { useState, useEffect } from 'react';
import {
  Cpu,
  Plus,
  Save,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
  Zap,
  Trash2,
  RefreshCw,
  Link2,
  Search,
  ChevronDown,
  ChevronUp,
  Download,
  Folder,
  Edit2,
  Cloud,
  Monitor,
} from 'lucide-react';
import axios from 'axios';
import { cn } from '../lib/utils';
import { useTranslation } from '../i18n';


// ── Documentation links for cloud providers ─────────────────────
const PROVIDER_DOCS: Record<string, { label: string; url: string }> = {
  google:     { label: 'Gemini Model Reference',   url: 'https://ai.google.dev/gemini-api/docs/models' },
  openai:     { label: 'OpenAI Model Reference',    url: 'https://platform.openai.com/docs/models' },
  anthropic:  { label: 'Claude Model Overview',     url: 'https://platform.claude.com/docs/en/about-claude/models/overview' },
  openrouter: { label: 'OpenRouter Model Catalog',  url: 'https://openrouter.ai/models' },
};

const PROVIDER_BASE_URLS: Record<string, string> = {
  openai:     'https://api.openai.com/v1',
  google:     'https://generativelanguage.googleapis.com/v1beta/openai',
  anthropic:  'https://api.anthropic.com/v1',
  openrouter: 'https://openrouter.ai/api/v1',
  ollama:     'http://127.0.0.1:11434',
  lmstudio:   'http://localhost:1234/v1',
  local:      'http://localhost:1234/v1',
  custom:     '',
};

const PROVIDER_DISPLAY_NAMES: Record<string, string> = {
  openai: 'OpenAI',
  google: 'Google Gemini',
  anthropic: 'Anthropic Claude',
  openrouter: 'OpenRouter',
};

const PROVIDER_MODEL_PRESETS: Record<string, string[]> = {
  openai: ['gpt-5'],
  anthropic: ['claude-sonnet-5'],
  google: ['gemini-3.5-flash'],
  openrouter: ['z-ai/glm-5.2', 'google/gemini-3.5-flash', 'anthropic/claude-sonnet-5'],
  ollama: ['llama3.2', 'qwen2.5-coder', 'deepseek-r1:8b', 'mistral'],
};

const LOCAL_PROVIDERS = ['ollama', 'lmstudio', 'local'];
const isLocalProvider = (type: string) => LOCAL_PROVIDERS.includes(type);

const PROVIDER_SECRET_KEYS = new Set(['api_key', 'api-key', 'access_token', 'refresh_token', 'token', 'password', 'secret', 'client_secret', 'oauth_client_secret']);

type ReasoningControl = {
  type: 'effort_enum';
  supported_efforts: string[];
  provider_default?: string | null;
  catalog_version: number;
};
const hasProviderSecret = (value: unknown): boolean => {
  if (!value || typeof value !== 'object') return false;
  if (Array.isArray(value)) return value.some(hasProviderSecret);
  return Object.entries(value as Record<string, unknown>).some(
    ([key, item]) => (PROVIDER_SECRET_KEYS.has(key.toLowerCase()) && typeof item === 'string' && !!item) || hasProviderSecret(item),
  );
};
const withoutProviderSecrets = (value: unknown): unknown => {
  if (Array.isArray(value)) return value.map(withoutProviderSecrets);
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>)
      .filter(([key]) => !PROVIDER_SECRET_KEYS.has(key.toLowerCase()))
      .map(([key, item]) => [key, withoutProviderSecrets(item)]),
  );
};

// ── Ollama live search result type ───────────────────────────────
interface OllamaSearchResult {
  id: string; name: string; description: string;
  sizes: string[]; capabilities: string[];
  pulls: string; tag_count: number; updated: string;
}


const toSlug = (name: string) =>
  name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

export function Katana() {
  const { t } = useTranslation();

  const [loading, setLoading]     = useState(true);
  const [saving, setSaving]       = useState(false);

  const [providers, setProviders]   = useState<any[]>([]);
  const [localModels, setLocalModels] = useState<string[]>([]);
  const [localProviderType, setLocalProviderType] = useState<string>('ollama');
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null);

  // ── New Provider form state ──────────────────────────────────
  const [newProvider, setNewProvider] = useState({
    name: '',
    provider_type: 'openai',
    auth_type: 'api_key',
    api_key: '',
    base_url: PROVIDER_BASE_URLS['openai'],
    is_active: true
  });
  const [configuredModels, setConfiguredModels] = useState<string[]>([]);
  const [configuredReasoning, setConfiguredReasoning] = useState<Record<string, string>>({});
  const [reasoningCapabilities, setReasoningCapabilities] = useState<Record<string, ReasoningControl | null>>({});
  const [oauthClientSecret, setOauthClientSecret] = useState('');
  const [chatGPTSignIn, setChatGPTSignIn] = useState<ChatGPTSignIn | null>(null);
  const [testingOAuthProviderId, setTestingOAuthProviderId] = useState<string | null>(null);
  const [customModelInput, setCustomModelInput] = useState('');
  const [discoveredModels, setDiscoveredModels] = useState<string[]>([]);
  const [discoveringModels, setDiscoveringModels] = useState(false);
  const [hasStoredProviderCredential, setHasStoredProviderCredential] = useState(false);
  const [providerConfigBase, setProviderConfigBase] = useState<Record<string, any>>({});
  const [baseUrlOverride, setBaseUrlOverride] = useState(false);
  const [localModelPath, setLocalModelPath]   = useState('');
  const [scanningModels, setScanningModels]   = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!configuredModels.length) {
      setReasoningCapabilities({});
      return () => { cancelled = true; };
    }
    axios.post('/api/v1/model-providers/reasoning-capabilities', {
      provider_type: newProvider.provider_type,
      model_ids: configuredModels,
    }).then(response => {
      if (!cancelled) setReasoningCapabilities(response.data?.data || {});
    }).catch(() => {
      if (!cancelled) setReasoningCapabilities({});
    });
    return () => { cancelled = true; };
  }, [newProvider.provider_type, configuredModels]);

  useEffect(() => {
    setConfiguredReasoning(current => Object.fromEntries(
      Object.entries(current).filter(([modelId]) => configuredModels.includes(modelId)),
    ));
  }, [configuredModels]);

  useEffect(() => {
    const receiveOAuthResult = (event: MessageEvent) => {
      if (event.data?.type !== 'shogun.provider-oauth') return;
      const success = event.data.status === 'success';
      setStatusMessage({ type: success ? 'success' : 'error', text: event.data.message || (success ? 'OAuth connection completed.' : 'OAuth connection failed.') });
      if (success) fetchData();
    };
    window.addEventListener('message', receiveOAuthResult);
    return () => window.removeEventListener('message', receiveOAuthResult);
  }, []);

  // ── Pull-model state ─────────────────────────────────────────
  const [showPullPanel, setShowPullPanel]         = useState(false);
  
  useEffect(() => {
    const activeLocal = providers.find(p => p.status === 'connected' && isLocalProvider(p.provider_type));
    const isLocal = isLocalProvider(newProvider.provider_type);
    
    if (isLocal) {
      fetchLocalModels(newProvider.provider_type, newProvider.base_url);
      // Set a sensible default path when switching to a local provider
      if (!localModelPath) {
        if (newProvider.provider_type === 'ollama') {
          // Windows default; user can override
          setLocalModelPath('%USERPROFILE%\\.ollama\\models');
        } else {
          setLocalModelPath('');
        }
      }
    } else if (activeLocal) {
      fetchLocalModels(activeLocal.provider_type, activeLocal.base_url);
    } else {
      setLocalModels([]);
      setLocalModelPath('');
    }
  }, [newProvider.provider_type, newProvider.base_url, providers]);

  const [pullCatalogFilter, setPullCatalogFilter] = useState<string>('all');
  const [pullingModel, setPullingModel]           = useState<string | null>(null);
  const [pullStatus, setPullStatus]               = useState<{ status: string; percent: number } | null>(null);
  const [customPullTag, setCustomPullTag]         = useState('');

  // ── Live Ollama search state ──────────────────────────────────
  const [ollamaQuery, setOllamaQuery]             = useState('');
  const [ollamaResults, setOllamaResults]         = useState<OllamaSearchResult[]>([]);
  const [ollamaLoading, setOllamaLoading]         = useState(false);
  const [ollamaPage, setOllamaPage]               = useState(1);
  const [ollamaHasMore, setOllamaHasMore]         = useState(false);
  const [ollamaLoadingMore, setOllamaLoadingMore] = useState(false);
  const [ollamaSearchError, setOllamaSearchError] = useState('');

  const searchOllamaModels = async (query: string, page: number, append: boolean = false) => {
    if (page === 1) setOllamaLoading(true);
    else setOllamaLoadingMore(true);
    setOllamaSearchError('');
    try {
      const params: Record<string, string> = {};
      if (query.trim()) params.q = query.trim();
      if (page > 1) params.p = String(page);
      if (pullCatalogFilter !== 'all') params.c = pullCatalogFilter;
      const res = await axios.get('/api/v1/system/ollama-search', { params });
      if (res.data?.success) {
        const data = res.data.data;
        setOllamaResults(prev => append ? [...prev, ...data.models] : data.models);
        setOllamaHasMore(data.has_more);
        setOllamaPage(data.page);
      } else {
        if (!append) setOllamaResults([]);
        setOllamaSearchError(res.data?.meta?.error || 'Ollama model search is unavailable.');
      }
    } catch (error: any) {
      if (!append) setOllamaResults([]);
      setOllamaSearchError(error?.response?.data?.detail || 'Could not reach the Ollama model catalog.');
    } finally {
      setOllamaLoading(false);
      setOllamaLoadingMore(false);
    }
  };

  // Debounced search when query or filter changes
  useEffect(() => {
    if (!showPullPanel) return;
    const timer = setTimeout(() => {
      searchOllamaModels(ollamaQuery, 1, false);
    }, 300);
    return () => clearTimeout(timer);
  }, [ollamaQuery, pullCatalogFilter, showPullPanel]);

  // Initial load when panel opens
  useEffect(() => {
    if (showPullPanel && ollamaResults.length === 0) {
      searchOllamaModels('', 1, false);
    }
  }, [showPullPanel]);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const provRes = await axios.get('/api/v1/model-providers');
      setProviders(provRes.data.data || []);
    } catch (error) {
      console.error('Error fetching AI providers:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchLocalModels = async (providerType: string, customBaseUrl?: string) => {
    setLocalProviderType(providerType);
    try {
      const baseUrl = customBaseUrl || 
        (newProvider.provider_type === providerType ? newProvider.base_url : null) || 
        (providerType === 'ollama' ? 'http://127.0.0.1:11434' : 'http://localhost:1234/v1');

      const res = await axios.get('/api/v1/system/local-models', {
        params: {
          provider_type: providerType,
          base_url: baseUrl,
        }
      });
      if (res.data?.success) {
        setLocalModels(res.data.data || []);
      } else {
        setLocalModels([]);
        setStatusMessage({
          type: 'error',
          text: res.data?.meta?.error || `Could not connect to ${providerType} at ${baseUrl}.`,
        });
      }
    } catch (error: any) {
      setLocalModels([]);
      setStatusMessage({
        type: 'error',
        text: error?.response?.data?.detail || `Could not scan ${providerType}. Check that it is running and the base URL is correct.`,
      });
    }
  };

  const addConfiguredModel = (modelId: string) => {
    const normalized = modelId.trim();
    if (!normalized) return;
    setConfiguredModels(current => current.includes(normalized) ? current : [...current, normalized]);
    if (!isLocalProvider(newProvider.provider_type) && !newProvider.name.trim()) {
      setNewProvider(current => ({
        ...current,
        name: PROVIDER_DISPLAY_NAMES[current.provider_type] || current.provider_type,
      }));
    }
  };

  const handleDiscoverProviderModels = async () => {
    setDiscoveringModels(true);
    setDiscoveredModels([]);
    try {
      const res = await axios.post('/api/v1/model-providers/discover-models', {
        provider_type: newProvider.provider_type,
        base_url: newProvider.base_url || null,
        api_key: newProvider.api_key || null,
        provider_id: editingProviderId,
      });
      const found: string[] = res.data?.data || [];
      setDiscoveredModels(found);
      setStatusMessage({
        type: 'success',
        text: `Found ${found.length} model${found.length === 1 ? '' : 's'}. Click any model to add it.`,
      });
    } catch (error: any) {
      setStatusMessage({
        type: 'error',
        text: error?.response?.data?.detail || 'Could not retrieve this provider’s model catalog.',
      });
    } finally {
      setDiscoveringModels(false);
    }
  };

  // Scan the filesystem path via the backend endpoint
  const handleScanLocalModels = async () => {
    const rawPath = localModelPath.trim();
    if (!rawPath) return;
    setScanningModels(true);
    try {
      const res = await axios.get('/api/v1/system/scan-local-models', {
        params: { path: rawPath },
      });
      const found: string[] = res.data?.data || [];
      if (res.data?.success === false) {
        setStatusMessage({ type: 'error', text: res.data?.meta?.error || 'The model directory could not be accessed.' });
      } else if (found.length > 0) {
        setLocalModels(found);
        setStatusMessage({ type: 'success', text: `Found ${found.length} model${found.length !== 1 ? 's' : ''} in directory.` });
      } else {
        setStatusMessage({ type: 'error', text: 'No models found at that path. Check the directory and try again.' });
      }
    } catch (error: any) {
      setStatusMessage({ type: 'error', text: error?.response?.data?.detail || 'Could not scan directory. Ensure the backend can access the path.' });
    } finally {
      setScanningModels(false);
      setTimeout(() => setStatusMessage(null), 4000);
    }
  };

  // Stream an Ollama model pull via SSE backend proxy
  const handlePullModel = async (modelId: string) => {
    const baseUrl = (newProvider.provider_type === 'ollama' ? newProvider.base_url : null) || 'http://127.0.0.1:11434';
    setPullingModel(modelId);
    setPullStatus({ status: 'Connecting to Ollama…', percent: 0 });
    try {
      const params = new URLSearchParams({ model: modelId, base_url: baseUrl });
      const response = await fetch(`/api/v1/system/pull-model?${params}`);
      if (!response.body) throw new Error('No response body');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.status === 'error') {
              setStatusMessage({ type: 'error', text: data.error || `Failed to pull ${modelId}` });
              setTimeout(() => setStatusMessage(null), 6000);
              return;
            }
            if (data.status === 'done' || data.status === 'success') {
              setPullStatus({ status: '✓ Complete!', percent: 100 });
              setStatusMessage({ type: 'success', text: `${modelId} pulled successfully — ready to use.` });
              setLocalModels(prev => prev.includes(modelId) ? prev : [modelId, ...prev]);
              setTimeout(() => setStatusMessage(null), 5000);
              break;
            }
            const percent = data.total && data.completed
              ? Math.round((data.completed / data.total) * 100)
              : 0;
            const gbDone = data.completed ? (data.completed / 1e9).toFixed(2) : null;
            const gbTotal = data.total ? (data.total / 1e9).toFixed(2) : null;
            const sizeStr = gbDone && gbTotal ? ` — ${gbDone} / ${gbTotal} GB` : '';
            setPullStatus({ status: `${data.status}${sizeStr}`, percent });
          } catch { /* malformed line, skip */ }
        }
      }
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: err?.message || `Failed to pull ${modelId}. Is Ollama running at ${baseUrl}?` });
      setTimeout(() => setStatusMessage(null), 6000);
    } finally {
      setPullingModel(null);
      setPullStatus(null);
    }
  };

  // ── Delete local model ──────────────────────────────────────────
  const [deletingModel, setDeletingModel] = useState<string | null>(null);

  const handleDeleteOllamaModel = async (modelId: string) => {
    if (!confirm(`Delete model "${modelId}" from Ollama? This will free disk space but the model will need to be re-pulled to use again.`)) return;
    const activeOllama = providers.find(p => p.provider_type === 'ollama' && p.base_url);
    const baseUrl = activeOllama?.base_url || 
      (newProvider.provider_type === 'ollama' ? newProvider.base_url : null) || 
      'http://127.0.0.1:11434';
    setDeletingModel(modelId);
    try {
      const params = new URLSearchParams({ model: modelId, base_url: baseUrl });
      const resp = await fetch(`/api/v1/system/delete-model?${params}`, { method: 'DELETE' });
      const data = await resp.json();
      if (data.success) {
        setLocalModels(prev => prev.filter(m => m !== modelId));
        setStatusMessage({ type: 'success', text: `${modelId} deleted successfully.` });
      } else {
        setStatusMessage({ type: 'error', text: data.message || `Failed to delete ${modelId}` });
      }
      setTimeout(() => setStatusMessage(null), 5000);
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: err?.message || `Failed to delete ${modelId}` });
      setTimeout(() => setStatusMessage(null), 6000);
    } finally {
      setDeletingModel(null);
    }
  };

  // ── Provider handlers ────────────────────────────────────────
  const pollProviderOAuth = async (providerId: string, flowId: string) => {
    const deadline = Date.now() + 10 * 60 * 1000;
    while (Date.now() < deadline) {
      await new Promise(resolve => window.setTimeout(resolve, 1000));
      try {
        const response = await axios.get(`/api/v1/model-providers/${providerId}/oauth/status`, {
          params: { flow_id: flowId },
        });
        const result = response.data?.data;
        if (result?.status === 'pending') continue;
        if (result?.status === 'success') {
          setStatusMessage({ type: 'success', text: result.message || 'OAuth connection completed.' });
          await fetchData();
          return;
        }
        setStatusMessage({ type: 'error', text: result?.message || 'OAuth connection failed.' });
        return;
      } catch {
        // A transient local API restart should not cancel the provider authorization window.
      }
    }
    setStatusMessage({ type: 'error', text: 'OAuth authorization timed out. Start the connection again.' });
  };

  const openBrowserFallback = (url: string): boolean => {
    const page = window.open(url, '_blank');
    if (page) page.opener = null;
    return Boolean(page);
  };

  const beginProviderOAuth = async (providerId: string) => {
    const response = await axios.post(`/api/v1/model-providers/${providerId}/oauth/start`, {
      return_origin: window.location.origin,
    });
    const result = response.data?.data || {};
    if (result.manual_recovery === 'paste_callback_url') {
      setChatGPTSignIn({ ...result, providerId });
      if (!result.browser_opened) openBrowserFallback(result.authorization_url);
      return;
    }
    if (!result.browser_opened && !openBrowserFallback(result.authorization_url)) {
      throw new Error('The default browser could not be opened. Allow Shogun to open browser windows and try again.');
    }
    setStatusMessage({ type: 'success', text: 'Default browser opened. Complete provider authorization there; Shogun will detect it automatically.' });
    void pollProviderOAuth(providerId, result.flow_id);
  };

  const pollCodexLogin = async (providerId: string, flowId: string) => {
    const deadline = Date.now() + 10 * 60 * 1000;
    while (Date.now() < deadline) {
      await new Promise(resolve => window.setTimeout(resolve, 1000));
      try {
        const response = await axios.get(`/api/v1/model-providers/${providerId}/codex/status`, {
          params: { flow_id: flowId },
        });
        const result = response.data?.data;
        if (result?.status === 'pending') continue;
        if (result?.status === 'success') {
          setStatusMessage({ type: 'success', text: result.message || 'ChatGPT/Codex subscription connected.' });
          await fetchData();
          return;
        }
        setStatusMessage({ type: 'error', text: result?.message || 'ChatGPT/Codex sign-in failed.' });
        return;
      } catch {
        // A brief local API interruption should not close the official sign-in page.
      }
    }
    setStatusMessage({ type: 'error', text: 'ChatGPT/Codex sign-in timed out. Start the connection again.' });
  };

  const beginCodexLogin = async (providerId: string) => {
    const response = await axios.post(`/api/v1/model-providers/${providerId}/codex/start`);
    const result = response.data?.data || {};
    if (result.already_connected || result.status === 'success') {
      setStatusMessage({ type: 'success', text: 'ChatGPT/Codex subscription is connected.' });
      await fetchData();
      return;
    }
    if (!result.browser_opened && !openBrowserFallback(result.authorization_url)) {
      throw new Error('The ChatGPT sign-in page could not be opened. Allow Shogun to open browser windows and try again.');
    }
    setStatusMessage({ type: 'success', text: 'ChatGPT sign-in opened in your default browser. Shogun will detect completion automatically.' });
    void pollCodexLogin(providerId, result.flow_id);
  };

  const handleOpenProviderSetup = async (providerType: string, authType: string) => {
    try {
      const response = await axios.post(
        `/api/v1/model-providers/credential-setup/${encodeURIComponent(providerType)}/open`,
        null,
        { params: { auth_type: authType } },
      );
      const result = response.data?.data || {};
      if (!result.browser_opened && !openBrowserFallback(result.url)) {
        throw new Error('The default browser could not be opened.');
      }
      setStatusMessage({ type: 'success', text: 'Official provider setup page opened in your default browser.' });
    } catch (error: any) {
      setStatusMessage({ type: 'error', text: error?.response?.data?.detail || error?.message || 'Could not open the provider setup page.' });
    }
  };

  const handleCreateProvider = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const slug = toSlug(newProvider.name);
      const credential = newProvider.api_key.trim();
      const payload: Record<string, any> = {
        name:          newProvider.name,
        provider_type: newProvider.provider_type,
        slug,
        base_url:      newProvider.base_url || null,
        is_local:      isLocalProvider(newProvider.provider_type),
        auth_type:     isLocalProvider(newProvider.provider_type) ? 'none' : newProvider.auth_type,
        config:        {
          ...providerConfigBase,
          ...(newProvider.auth_type === 'api_key' && credential ? { api_key: credential } : {}),
          ...(newProvider.auth_type === 'token' && credential ? { token: credential } : {}),
          ...(newProvider.auth_type === 'oauth' && oauthClientSecret.trim() ? { oauth_client_secret: oauthClientSecret.trim() } : {}),
          models: configuredModels,
          model_reasoning: configuredReasoning,
        },
      };

      let response;
      if (editingProviderId) {
        response = await axios.patch(`/api/v1/model-providers/${editingProviderId}`, payload);
        setStatusMessage({ type: 'success', text: 'Model provider updated successfully.' });
      } else {
        response = await axios.post('/api/v1/model-providers', payload);
        setStatusMessage({ type: 'success', text: 'Model provider added successfully.' });
      }

      if (newProvider.auth_type === 'oauth') {
        const providerId = response.data?.data?.id;
        await beginProviderOAuth(providerId);
      } else if (newProvider.auth_type === 'chatgpt') {
        const providerId = response.data?.data?.id;
        await beginCodexLogin(providerId);
      }

      setNewProvider({ name: '', provider_type: 'openai', auth_type: 'api_key', api_key: '', base_url: PROVIDER_BASE_URLS['openai'], is_active: true });
      setConfiguredModels([]);
      setConfiguredReasoning({});
      setOauthClientSecret('');
      setCustomModelInput('');
      setDiscoveredModels([]);
      setHasStoredProviderCredential(false);
      setProviderConfigBase({});
      setEditingProviderId(null);
      setBaseUrlOverride(false);
      fetchData();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail
        : Array.isArray(detail) ? detail.map((d: any) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join(', ')
        : err?.message || 'Failed to save provider.';
      setStatusMessage({ type: 'error', text: msg });
    } finally {
      setSaving(false);
      setTimeout(() => setStatusMessage(null), 5000);
    }
  };

  const handleStartEdit = (p: any) => {
    setEditingProviderId(p.id);
    setNewProvider({
      name: p.name,
      provider_type: p.provider_type,
      auth_type: p.auth_type || 'api_key',
      api_key: '',
      base_url: p.base_url || PROVIDER_BASE_URLS[p.provider_type] || '',
      is_active: p.status === 'connected'
    });
    const configured: string[] = Array.isArray(p.config?.models)
      ? p.config.models.filter((value: unknown): value is string => typeof value === 'string' && !!value.trim())
      : [p.config?.model_id, p.config?.model].filter((value: unknown): value is string => typeof value === 'string' && !!value.trim());
    const genericName = (PROVIDER_DISPLAY_NAMES[p.provider_type] || p.provider_type || '').toLowerCase();
    const legacyModel = typeof p.name === 'string' && p.name.trim() && p.name.trim().toLowerCase() !== genericName
      ? p.name.trim()
      : '';
    const models = configured.length > 0 ? configured : legacyModel ? [legacyModel] : [];
    setConfiguredModels([...new Set(models.map((value: string) => value.trim()))]);
    setConfiguredReasoning({ ...(p.config?.model_reasoning || {}) });
    setOauthClientSecret('');
    setCustomModelInput('');
    setDiscoveredModels([]);
    setHasStoredProviderCredential(hasProviderSecret(p.config));
    setProviderConfigBase(withoutProviderSecrets(p.config || {}) as Record<string, any>);
    setBaseUrlOverride(!!p.base_url);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleCancelEdit = () => {
    setEditingProviderId(null);
    setNewProvider({
      name: '',
      provider_type: 'openai',
      auth_type: 'api_key',
      api_key: '',
      base_url: PROVIDER_BASE_URLS['openai'],
      is_active: true
    });
    setConfiguredModels([]);
    setConfiguredReasoning({});
    setOauthClientSecret('');
    setCustomModelInput('');
    setDiscoveredModels([]);
    setHasStoredProviderCredential(false);
    setProviderConfigBase({});
    setBaseUrlOverride(false);
  };

  const handleToggleProvider = async (id: string, currentStatus: string) => {
    const newStatus = currentStatus === 'connected' ? 'disabled' : 'connected';
    try {
      await axios.patch(`/api/v1/model-providers/${id}`, { status: newStatus });
      fetchData();
    } catch (error) {
      console.error('Error toggling provider:', error);
    }
  };

  const handleConnectOAuth = async (providerId: string) => {
    try {
      await beginProviderOAuth(providerId);
    } catch (error: any) {
      setStatusMessage({ type: 'error', text: error?.response?.data?.detail || error?.message || 'Could not start OAuth.' });
    }
  };

  const handleDisconnectOAuth = async (providerId: string) => {
    try {
      await axios.post(`/api/v1/model-providers/${providerId}/oauth/disconnect`);
      setStatusMessage({ type: 'success', text: 'OAuth tokens removed from Shogun.' });
      fetchData();
    } catch (error: any) {
      setStatusMessage({ type: 'error', text: error?.response?.data?.detail || 'Could not disconnect OAuth.' });
    }
  };

  const handleConnectCodex = async (providerId: string) => {
    try {
      await beginCodexLogin(providerId);
    } catch (error: any) {
      setStatusMessage({ type: 'error', text: error?.response?.data?.detail || error?.message || 'Could not start ChatGPT/Codex sign-in.' });
    }
  };

  const handleDisconnectCodex = async (providerId: string) => {
    try {
      await axios.post(`/api/v1/model-providers/${providerId}/codex/disconnect`);
      setStatusMessage({ type: 'success', text: 'ChatGPT/Codex subscription disconnected. Codex removed the local sign-in.' });
      await fetchData();
    } catch (error: any) {
      setStatusMessage({ type: 'error', text: error?.response?.data?.detail || 'Could not disconnect ChatGPT/Codex.' });
    }
  };

  const handleDeleteProvider = async (id: string, name: string) => {
    if (!confirm(`Remove provider "${name}" from the grid? This cannot be undone.`)) return;
    try {
      await axios.delete(`/api/v1/model-providers/${id}`);
      setStatusMessage({ type: 'success', text: `Provider "${name}" removed.` });
      fetchData();
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to delete provider.' });
    } finally {
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };

  // ── Provider helpers ─────────────────────────────────────────
  const getProviderColor = (type: string) => {
    switch (type) {
      case 'openai':     return { bg: 'bg-green-500/10',         text: 'text-green-500' };
      case 'anthropic':  return { bg: 'bg-shogun-gold/10',        text: 'text-shogun-gold' };
      case 'google':     return { bg: 'bg-blue-400/10',           text: 'text-blue-400' };
      case 'openrouter': return { bg: 'bg-purple-400/10',         text: 'text-purple-400' };
      case 'ollama':     return { bg: 'bg-cyan-400/10',           text: 'text-cyan-400' };
      case 'lmstudio':   return { bg: 'bg-orange-400/10',         text: 'text-orange-400' };
      default:           return { bg: 'bg-shogun-blue/10',        text: 'text-shogun-blue' };
    }
  };

  const getProviderDisplayType = (type: string) => {
    const map: Record<string, string> = {
      openai: 'OpenAI', anthropic: 'Anthropic', google: 'Google Gemini',
      openrouter: 'OpenRouter', ollama: 'Ollama', lmstudio: 'LM Studio',
      local: 'Local', custom: 'Custom',
    };
    return map[type] || type;
  };

  const currentDocLink = newProvider.auth_type === 'chatgpt'
    ? { label: 'Official Codex App Server guide', url: 'https://learn.chatgpt.com/docs/app-server' }
    : PROVIDER_DOCS[newProvider.provider_type];
  const isLocal        = isLocalProvider(newProvider.provider_type);

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-6xl mx-auto pb-12">
      <div>
        <h2 className="text-2xl font-bold text-shogun-text tracking-tight flex items-center gap-2.5">
          <Cpu className="w-6 h-6 text-shogun-gold" />
          AI Providers
        </h2>
        <p className="text-shogun-subdued text-xs mt-1">
          Configure cloud API keys, ChatGPT/OAuth connections, and local Ollama / LM Studio models for AgentFlow.
        </p>
      </div>

      {chatGPTSignIn && <ChatGPTOAuthPanel key={chatGPTSignIn.flow_id} flow={chatGPTSignIn}
        onComplete={message => { setChatGPTSignIn(null); setStatusMessage({ type: 'success', text: message }); void fetchData(); }}
        onCancel={() => { setChatGPTSignIn(null); void fetchData(); }} />}
      {statusMessage && (
        <div className={cn(
          "p-3 rounded-lg flex items-center gap-3",
          statusMessage.type === 'success'
            ? "bg-green-500/10 text-green-500 border border-green-500/20"
            : "bg-red-500/10 text-red-500 border border-red-500/20"
        )}>
          {statusMessage.type === 'success' ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
          <span className="text-sm font-medium">{statusMessage.text}</span>
        </div>
      )}

      <div className="mt-4">

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Add Provider form */}
            <div className="lg:col-span-1">
              <div className="shogun-card space-y-6 sticky top-6">
                <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                  {editingProviderId ? (
                    <><Edit2 className="w-5 h-5 text-shogun-gold" /> {t('common.edit', 'Edit Provider')}</>
                  ) : (
                    <><Plus className="w-5 h-5 text-shogun-blue" /> {t('katana.add_provider', 'Add Provider')}</>
                  )}
                </h3>
                <form onSubmit={handleCreateProvider} className="space-y-4">
                  {/* Provider selector */}
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.provider', 'Provider')}</label>
                    <select
                      value={newProvider.provider_type}
                      onChange={(e) => {
                        const type = e.target.value;
                        setNewProvider({
                          ...newProvider,
                          provider_type: type,
                          auth_type: 'api_key',
                          api_key: '',
                          name: '',
                          base_url: PROVIDER_BASE_URLS[type] || '',
                        });
                        setConfiguredModels([]);
                        setConfiguredReasoning({});
                        setOauthClientSecret('');
                        setCustomModelInput('');
                        setDiscoveredModels([]);
                        setHasStoredProviderCredential(false);
                        setProviderConfigBase({});
                        setBaseUrlOverride(false);
                      }}
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                    >
                      <optgroup label={t('katana.ai_model_providers')}>
                        <option value="openai">OpenAI</option>
                        <option value="google">Google (Gemini)</option>
                        <option value="anthropic">Anthropic</option>
                        <option value="openrouter">OpenRouter</option>
                        <option value="custom">Custom OpenAI-compatible</option>
                      </optgroup>
                      <optgroup label={t('katana.local_providers')}>
                        <option value="ollama">Ollama (Local)</option>
                        <option value="lmstudio">LM Studio (Local)</option>
                      </optgroup>
                    </select>
                  </div>

                  {/* Doc link */}
                  {currentDocLink && (
                    <a
                      href={currentDocLink.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 p-2.5 rounded-lg bg-shogun-blue/5 border border-shogun-blue/15 text-shogun-blue hover:bg-shogun-blue/10 hover:border-shogun-blue/30 transition-all group"
                    >
                      <Link2 className="w-3.5 h-3.5 shrink-0" />
                      <span className="text-[11px] font-semibold truncate">{currentDocLink.label}</span>
                      <ExternalLink className="w-3 h-3 ml-auto opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                    </a>
                  )}

                  {/* Display Name / Local model picker */}
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">
                      {isLocal ? t('katana.available_models') : t('katana.display_name')}
                    </label>
                    {isLocal && localModels.length > 0 ? (
                      <select
                        required
                        value={newProvider.name}
                        onChange={(e) => {
                          const modelId = e.target.value;
                          setNewProvider({...newProvider, name: modelId});
                          addConfiguredModel(modelId);
                        }}
                        className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                      >
                        <option value="" disabled>{t('katana.select_pulled_model')}</option>
                        {localModels.map((m) => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type="text"
                        required
                        placeholder={isLocal ? "e.g. llama3:8b (or connect to fetch)" : "e.g. Primary OpenAI"}
                        value={newProvider.name}
                        onChange={(e) => setNewProvider({...newProvider, name: e.target.value})}
                        className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                      />
                    )}
                    {isLocal && localModels.length === 0 && (
                      <div className="flex items-center gap-2 mt-1">
                        <button
                          type="button"
                          onClick={() => fetchLocalModels(newProvider.provider_type)}
                          className="text-[9px] font-bold text-shogun-blue hover:text-shogun-gold uppercase tracking-widest transition-colors flex items-center gap-1"
                        >
                          <RefreshCw className="w-2.5 h-2.5" /> {t('katana.scan_for_local_models')}
                        </button>
                        <span className="text-[9px] text-shogun-subdued">• Ensure {newProvider.provider_type === 'ollama' ? 'Ollama' : 'LM Studio'} is running</span>
                      </div>
                    )}
                  </div>

                  <div className="space-y-2.5 pt-2 border-t border-shogun-border/40">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center justify-between">
                      <span>Active Models ({configuredModels.length})</span>
                      <span className="text-[8px] text-purple-400 font-semibold normal-case">Router candidates</span>
                    </label>
                    <div className="space-y-1.5 min-h-[36px] p-2 bg-[#050508] border border-shogun-border rounded-lg">
                      {configuredModels.map((modelId) => {
                        const reasoning = reasoningCapabilities[modelId];
                        return (
                        <div key={modelId} className="flex items-center gap-2 text-[10px] px-2 py-1.5 rounded bg-purple-500/10 border border-purple-500/25 text-purple-300 font-semibold">
                          <span className="min-w-0 flex-1 truncate font-mono">{modelId}</span>
                          {reasoning && (
                            <label className="flex items-center gap-1 text-[8px] font-sans uppercase text-shogun-subdued">
                              Reasoning
                              <select
                                value={configuredReasoning[modelId] || ''}
                                onChange={event => setConfiguredReasoning(current => {
                                  const next = { ...current };
                                  if (event.target.value) next[modelId] = event.target.value;
                                  else delete next[modelId];
                                  return next;
                                })}
                                className="rounded border border-purple-400/30 bg-[#050508] px-1.5 py-1 text-[9px] normal-case text-purple-200 outline-none"
                              >
                                <option value="">Provider default{reasoning.provider_default ? ` (${reasoning.provider_default})` : ''}</option>
                                {reasoning.supported_efforts.map(effort => <option key={effort} value={effort}>{effort}</option>)}
                              </select>
                            </label>
                          )}
                          <button
                            type="button"
                            onClick={() => setConfiguredModels(current => current.filter(item => item !== modelId))}
                            className="text-purple-400 hover:text-red-400 font-bold ml-0.5"
                            aria-label={`Remove ${modelId}`}
                          >
                            ×
                          </button>
                        </div>
                      );})}
                      {configuredModels.length === 0 && (
                        <span className="text-[10px] text-shogun-subdued italic py-0.5">No models selected. This provider will not be used for routing.</span>
                      )}
                    </div>

                    {!!PROVIDER_MODEL_PRESETS[newProvider.provider_type]?.length && (
                      <div className="space-y-1">
                        <span className="text-[9px] text-shogun-subdued font-medium">Quick add:</span>
                        <div className="flex flex-wrap gap-1">
                          {PROVIDER_MODEL_PRESETS[newProvider.provider_type].map((preset) => {
                            const selected = configuredModels.includes(preset);
                            return (
                              <button
                                key={preset}
                                type="button"
                                onClick={() => setConfiguredModels(current => selected
                                  ? current.filter(modelId => modelId !== preset)
                                  : [...current, preset])}
                                className={cn(
                                  "text-[9px] font-mono px-2 py-0.5 rounded border transition-all",
                                  selected
                                    ? "bg-purple-500/20 border-purple-400 text-purple-300 font-bold"
                                    : "bg-[#050508] border-shogun-border text-shogun-subdued hover:border-purple-400/40 hover:text-shogun-text"
                                )}
                              >
                                {selected ? `✓ ${preset}` : `+ ${preset}`}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {newProvider.auth_type !== 'chatgpt' && <div className="flex gap-1.5 pt-1">
                      <input
                        type="text"
                        placeholder="Exact model ID"
                        value={customModelInput}
                        onChange={(event) => setCustomModelInput(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key !== 'Enter' || !customModelInput.trim()) return;
                          event.preventDefault();
                          const modelId = customModelInput.trim();
                          setConfiguredModels(current => current.includes(modelId) ? current : [...current, modelId]);
                          setCustomModelInput('');
                        }}
                        className="flex-1 bg-[#050508] border border-shogun-border rounded-lg px-2.5 py-1.5 text-xs font-mono focus:border-purple-400 outline-none"
                      />
                      <button
                        type="button"
                        disabled={!customModelInput.trim()}
                        onClick={() => {
                          const modelId = customModelInput.trim();
                          if (modelId) setConfiguredModels(current => current.includes(modelId) ? current : [...current, modelId]);
                          setCustomModelInput('');
                        }}
                        className="px-3 py-1.5 bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/40 text-purple-300 text-[10px] font-bold uppercase rounded-lg disabled:opacity-40"
                      >
                        Add
                      </button>
                    </div>}
                  </div>

                  {/* Auth Configuration (cloud only) */}
                  {!isLocal && (
                    <>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.auth_type', 'Auth Type')}</label>
                        <select
                          value={newProvider.auth_type}
                          onChange={(e) => {
                            const authType = e.target.value;
                            setNewProvider(current => ({
                              ...current,
                              auth_type: authType,
                              api_key: '',
                              base_url: authType === 'chatgpt'
                                ? ''
                                : current.base_url || PROVIDER_BASE_URLS[current.provider_type] || '',
                            }));
                            setBaseUrlOverride(false);
                          }}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                        >
                          <option value="api_key">{t('katana.api_key_option')}</option>
                          {newProvider.provider_type === 'openai' && <option value="token">Workload identity bearer token</option>}
                          {newProvider.provider_type === 'openai' && <option value="chatgpt">ChatGPT/Codex subscription (browser sign-in)</option>}
                          {newProvider.provider_type === 'openai' && <option value="oauth">Connect with ChatGPT (direct OAuth + PKCE)</option>}
                          {(newProvider.provider_type === 'google' || newProvider.provider_type === 'custom') && <option value="oauth">Connect account in browser (OAuth 2.0 + PKCE)</option>}
                        </select>
                        {newProvider.provider_type === 'openai' && (
                          <p className="text-[9px] leading-relaxed text-shogun-subdued">Choose an OpenAI Platform API credential, or sign in with a supported ChatGPT plan through the official local Codex app-server. Platform API usage and ChatGPT/Codex subscription usage are separate methods.</p>
                        )}
                        {newProvider.provider_type === 'anthropic' && (
                          <p className="text-[9px] leading-relaxed text-shogun-subdued">Anthropic model API access uses an API key or a separately configured workload identity. Shogun can open the official key page in your default browser; Anthropic's browser login is not a registered third-party app OAuth flow.</p>
                        )}
                      </div>
                      {newProvider.auth_type === 'chatgpt' ? (
                        <div className="space-y-3 rounded-lg border border-green-400/25 bg-green-400/5 p-3">
                          <div>
                            <p className="text-[10px] font-bold uppercase tracking-widest text-green-300">Official ChatGPT/Codex sign-in</p>
                            <p className="mt-1 text-[9px] leading-relaxed text-shogun-subdued">Save this provider and Shogun will open the official ChatGPT sign-in in your default browser. The local Codex app-server owns the callback, encrypted credential storage, refresh, and available model list; Shogun never reads or stores your ChatGPT token.</p>
                          </div>
                          <div className="rounded border border-shogun-border bg-[#050508] px-3 py-2 text-[9px] leading-relaxed text-shogun-subdued">
                            Uses your Codex subscription limits and requires the official Codex desktop app or CLI on this computer. It does not use OpenAI Platform API credits.
                          </div>
                          {editingProviderId && (
                            <button
                              type="button"
                              onClick={() => handleConnectCodex(editingProviderId)}
                              className="inline-flex items-center gap-1.5 rounded-lg border border-green-400/30 bg-green-400/5 px-3 py-2 text-[9px] font-bold uppercase tracking-wider text-green-300 hover:bg-green-400/10"
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                              Open ChatGPT sign-in
                            </button>
                          )}
                        </div>
                      ) : newProvider.auth_type === 'oauth' && newProvider.provider_type === 'openai' ? (
                        <div className="space-y-3 rounded-lg border border-cyan-400/25 p-3">
                          <p className="text-xs text-shogun-subdued">Connect your ChatGPT subscription directly in the browser. Shogun encrypts and refreshes the credentials. API keys and Codex app-server connections remain separate options.</p>
                          <label className="block text-xs text-shogun-subdued">Public OAuth client ID (optional override)
                            <input value={providerConfigBase.oauth_client_id || ''} onChange={event => setProviderConfigBase(current => ({ ...current, oauth_client_id: event.target.value }))}
                              placeholder="Use installation default" className="mt-1 block w-full rounded border border-shogun-border bg-shogun-bg p-2" />
                          </label>
                          <p className="text-xs text-shogun-subdued">Save to connect or reconnect. Selected models and routing stay under your control. Subscription model access and limits depend on your account.</p>
                        </div>
                      ) : newProvider.auth_type !== 'oauth' ? <div className="space-y-1.5 mt-3">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">
                          {newProvider.auth_type === 'token' ? 'Bearer token' : t('katana.api_key_label')}
                        </label>
                        <input
                          type="password"
                          placeholder={hasStoredProviderCredential
                            ? 'Stored credential unchanged — enter a replacement'
                            : newProvider.auth_type === 'token' ? 'eyJ...' : 'sk-...'}
                          value={newProvider.api_key}
                          onChange={(e) => setNewProvider({...newProvider, api_key: e.target.value})}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                        />
                        {hasStoredProviderCredential && !newProvider.api_key && (
                          <p className="text-[9px] text-green-400">✓ A protected credential is stored. Leave this blank to keep it.</p>
                        )}
                        {hasStoredProviderCredential && newProvider.api_key && (
                          <p className="text-[9px] text-shogun-gold">The stored credential will be replaced when you save.</p>
                        )}
                        {newProvider.auth_type === 'api_key' && ['openai', 'google', 'anthropic'].includes(newProvider.provider_type) && (
                          <button
                            type="button"
                            onClick={() => handleOpenProviderSetup(newProvider.provider_type, 'api_key')}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-shogun-blue/30 bg-shogun-blue/5 px-3 py-2 text-[9px] font-bold uppercase tracking-wider text-shogun-blue hover:bg-shogun-blue/10"
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                            Open {PROVIDER_DISPLAY_NAMES[newProvider.provider_type] || newProvider.provider_type} API key page
                          </button>
                        )}
                      </div> : (
                        <div className="space-y-3 rounded-lg border border-cyan-400/25 bg-cyan-400/5 p-3">
                          <div>
                            <p className="text-[10px] font-bold uppercase tracking-widest text-cyan-300">Real OAuth connection</p>
                            <p className="mt-1 text-[9px] leading-relaxed text-shogun-subdued">Shogun opens the provider consent page in your default browser, validates state, uses PKCE, stores tokens encrypted, and detects completion automatically.</p>
                          </div>
                          {newProvider.provider_type === 'google' && (
                            <button
                              type="button"
                              onClick={() => handleOpenProviderSetup('google', 'oauth')}
                              className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-400/30 bg-cyan-400/5 px-3 py-2 text-[9px] font-bold uppercase tracking-wider text-cyan-300 hover:bg-cyan-400/10"
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                              Open Google OAuth client setup
                            </button>
                          )}
                          <label className="block text-[9px] uppercase text-shogun-subdued">OAuth client ID
                            <input required value={providerConfigBase.oauth_client_id || ''} onChange={event => setProviderConfigBase(current => ({ ...current, oauth_client_id: event.target.value }))} className="mt-1 block w-full rounded-lg border border-shogun-border bg-[#050508] p-2 text-xs normal-case outline-none focus:border-cyan-400" />
                          </label>
                          <label className="block text-[9px] uppercase text-shogun-subdued">OAuth client secret
                            <input type="password" value={oauthClientSecret} placeholder={hasStoredProviderCredential ? 'Stored secret unchanged' : 'Optional for public PKCE clients'} onChange={event => setOauthClientSecret(event.target.value)} className="mt-1 block w-full rounded-lg border border-shogun-border bg-[#050508] p-2 text-xs normal-case outline-none focus:border-cyan-400" />
                          </label>
                          {newProvider.provider_type === 'google' ? (
                            <label className="block text-[9px] uppercase text-shogun-subdued">Google Cloud project ID
                              <input value={providerConfigBase.oauth_project_id || ''} onChange={event => setProviderConfigBase(current => ({ ...current, oauth_project_id: event.target.value }))} placeholder="my-google-cloud-project" className="mt-1 block w-full rounded-lg border border-shogun-border bg-[#050508] p-2 text-xs normal-case outline-none focus:border-cyan-400" />
                            </label>
                          ) : <>
                            <label className="block text-[9px] uppercase text-shogun-subdued">Authorization URL
                              <input required type="url" value={providerConfigBase.oauth_authorization_url || ''} onChange={event => setProviderConfigBase(current => ({ ...current, oauth_authorization_url: event.target.value }))} placeholder="https://provider.example/oauth/authorize" className="mt-1 block w-full rounded-lg border border-shogun-border bg-[#050508] p-2 text-xs normal-case outline-none focus:border-cyan-400" />
                            </label>
                            <label className="block text-[9px] uppercase text-shogun-subdued">Token URL
                              <input required type="url" value={providerConfigBase.oauth_token_url || ''} onChange={event => setProviderConfigBase(current => ({ ...current, oauth_token_url: event.target.value }))} placeholder="https://provider.example/oauth/token" className="mt-1 block w-full rounded-lg border border-shogun-border bg-[#050508] p-2 text-xs normal-case outline-none focus:border-cyan-400" />
                            </label>
                          </>}
                          <label className="block text-[9px] uppercase text-shogun-subdued">Scopes
                            <input value={providerConfigBase.oauth_scopes || ''} onChange={event => setProviderConfigBase(current => ({ ...current, oauth_scopes: event.target.value }))} placeholder={newProvider.provider_type === 'google' ? 'Leave blank for Shogun defaults' : 'models.read chat.write'} className="mt-1 block w-full rounded-lg border border-shogun-border bg-[#050508] p-2 text-xs normal-case outline-none focus:border-cyan-400" />
                          </label>
                          <label className="block text-[9px] uppercase text-shogun-subdued">Redirect URI override
                            <input type="url" value={providerConfigBase.oauth_redirect_uri || ''} onChange={event => setProviderConfigBase(current => ({ ...current, oauth_redirect_uri: event.target.value }))} placeholder="Leave blank for this Shogun API address" className="mt-1 block w-full rounded-lg border border-shogun-border bg-[#050508] p-2 text-xs normal-case outline-none focus:border-cyan-400" />
                          </label>
                        </div>
                      )}
                    </>
                  )}

                  {/* Base URL — pre-filled, editable on override */}
                  {newProvider.auth_type === 'oauth' && newProvider.provider_type === 'openai' ? (
                    <p className="text-xs text-shogun-subdued">Model transport: ChatGPT subscription Responses. Add exact subscription model IDs below; Platform model discovery is unavailable.</p>
                  ) : newProvider.auth_type === 'chatgpt' ? (
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Model transport</label>
                      <div className="rounded-lg border border-green-400/20 bg-green-400/5 p-3 text-xs text-green-300">
                        Managed locally by the official Codex app-server
                      </div>
                    </div>
                  ) : <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">
                        {t('katana.base_url_label')} {isLocal ? '' : t('katana.auto')}
                      </label>
                      <button
                        type="button"
                        onClick={() => setBaseUrlOverride(v => !v)}
                        className={cn(
                          "text-[9px] font-bold uppercase tracking-widest transition-colors",
                          baseUrlOverride ? "text-shogun-gold" : "text-shogun-blue hover:text-shogun-gold"
                        )}
                      >
                        {baseUrlOverride ? t('katana.reset') : t('katana.override')}
                      </button>
                    </div>
                    <div className="relative">
                      <input
                        type="text"
                        readOnly={!baseUrlOverride}
                        placeholder={PROVIDER_BASE_URLS[newProvider.provider_type] || 'https://...'}
                        value={newProvider.base_url}
                        onChange={(e) => setNewProvider({...newProvider, base_url: e.target.value})}
                        className={cn(
                          "w-full bg-[#050508] border rounded-lg p-3 text-sm outline-none font-mono text-xs transition-all",
                          baseUrlOverride
                            ? "border-shogun-gold text-shogun-gold focus:ring-1 focus:ring-shogun-gold/20 cursor-text"
                            : "border-shogun-border text-shogun-subdued cursor-default select-none"
                        )}
                      />
                      {!baseUrlOverride && (
                        <div className="absolute right-3 top-1/2 -translate-y-1/2">
                          <span className="text-[8px] text-green-400 font-bold uppercase border border-green-400/20 bg-green-400/5 px-1.5 py-0.5 rounded">
                            {t('katana.default')}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>}

                  {!isLocal && (
                    <div className="space-y-2 rounded-lg border border-shogun-blue/20 bg-shogun-blue/5 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-[10px] font-bold uppercase tracking-widest text-shogun-text">Provider model catalog</p>
                          <p className="text-[9px] text-shogun-subdued mt-0.5">Scan the provider and click models to add them as router candidates.</p>
                        </div>
                        <button
                          type="button"
                          onClick={handleDiscoverProviderModels}
                          disabled={discoveringModels || (newProvider.auth_type === 'oauth' && newProvider.provider_type === 'openai') || (newProvider.auth_type === 'chatgpt' ? !editingProviderId : !newProvider.base_url)}
                          className="shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-lg border border-shogun-blue/30 bg-shogun-blue/10 hover:bg-shogun-blue/20 disabled:opacity-40 text-shogun-blue text-[9px] font-bold uppercase tracking-wider"
                        >
                          <RefreshCw className={cn("w-3 h-3", discoveringModels && "animate-spin")} />
                          {discoveringModels ? 'Scanning…' : 'Scan models'}
                        </button>
                      </div>
                      {discoveredModels.length > 0 && (
                        <div className="max-h-44 overflow-y-auto grid grid-cols-1 gap-1 pt-1">
                          {discoveredModels.map(modelId => {
                            const selected = configuredModels.includes(modelId);
                            return (
                              <button
                                key={modelId}
                                type="button"
                                onClick={() => addConfiguredModel(modelId)}
                                disabled={selected}
                                className={cn(
                                  "flex items-center justify-between gap-2 rounded border px-2.5 py-1.5 text-left text-[10px] font-mono transition-all",
                                  selected
                                    ? "border-green-500/30 bg-green-500/10 text-green-300"
                                    : "border-shogun-border bg-[#050508] text-shogun-text hover:border-purple-400/50 hover:text-purple-300",
                                )}
                              >
                                <span className="truncate">{modelId}</span>
                                <span className="shrink-0 text-[9px] font-sans font-bold">{selected ? '✓ Added' : '+ Add'}</span>
                              </button>
                            );
                          })}
                        </div>
                      )}
                      {newProvider.auth_type === 'chatgpt' && !editingProviderId && (
                        <p className="text-[9px] text-shogun-subdued">Save and complete ChatGPT sign-in first. Codex will then supply the exact model catalog available to this subscription.</p>
                      )}
                    </div>
                  )}

                  {/* Model Location — local providers only */}
                  {isLocal && (
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-1.5">
                        <Folder className="w-3 h-3" /> {t('katana.model_location')}
                        <span className="text-shogun-subdued/50 normal-case font-normal tracking-normal text-[9px]">({t('katana.filesystem_path')})</span>
                      </label>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          placeholder={
                            newProvider.provider_type === 'ollama'
                              ? 'C:\\Users\\you\\.ollama\\models'
                              : 'C:\\Users\\you\\AppData\\Local\\LM Studio\\models'
                          }
                          value={localModelPath}
                          onChange={(e) => setLocalModelPath(e.target.value)}
                          className="flex-1 bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue outline-none font-mono text-xs"
                        />
                        <button
                          type="button"
                          disabled={scanningModels || !localModelPath.trim()}
                          onClick={handleScanLocalModels}
                          className="flex items-center gap-1.5 px-3 py-2 bg-shogun-blue/10 hover:bg-shogun-blue/20 border border-shogun-blue/30 hover:border-shogun-blue/60 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-shogun-blue text-[10px] font-bold uppercase tracking-widest transition-all whitespace-nowrap"
                        >
                          {scanningModels
                            ? <RefreshCw className="w-3 h-3 animate-spin" />
                            : <Search className="w-3 h-3" />}
                          Scan
                        </button>
                      </div>
                      <p className="text-[9px] text-shogun-subdued leading-relaxed">
                        Paste the path shown in your {newProvider.provider_type === 'ollama' ? 'Ollama' : 'LM Studio'} settings.
                        The backend will walk the directory and return every pulled model.
                      </p>
                    </div>
                  )}

                  {/* {t('katana.pull_model')} — Ollama only */}
                  {newProvider.provider_type === 'ollama' && (
                    <div className="border border-shogun-border rounded-xl overflow-hidden">
                      <button
                        type="button"
                        onClick={() => setShowPullPanel(p => !p)}
                        className="w-full flex items-center justify-between px-4 py-3 bg-[#050508] hover:bg-[#0a0e1a] transition-colors"
                      >
                        <span className="flex items-center gap-2 text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">
                          <Download className="w-3.5 h-3.5 text-cyan-400" />
                          Pull a Model
                          <span className="text-cyan-400/60 normal-case font-normal tracking-normal">
                            — {t('katana.download_to_ollama')}
                          </span>
                        </span>
                        {showPullPanel
                          ? <ChevronUp className="w-3.5 h-3.5 text-shogun-subdued" />
                          : <ChevronDown className="w-3.5 h-3.5 text-shogun-subdued" />}
                      </button>

                      {showPullPanel && (
                        <div className="p-4 space-y-4 border-t border-shogun-border bg-[#02040a]">
                          {/* Live progress bar */}
                          {pullingModel && pullStatus && (
                            <div className="p-3 rounded-xl bg-cyan-500/5 border border-cyan-500/20 space-y-2">
                              <div className="flex items-center justify-between">
                                <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-widest truncate">
                                  ↓ {pullingModel}
                                </span>
                                <span className="text-[10px] font-mono text-cyan-400/70 ml-2 shrink-0">
                                  {pullStatus.percent}%
                                </span>
                              </div>
                              <div className="w-full h-1.5 bg-[#0a0e1a] rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-gradient-to-r from-cyan-500 to-shogun-blue rounded-full transition-all duration-300"
                                  style={{ width: `${pullStatus.percent}%` }}
                                />
                              </div>
                              <p className="text-[9px] text-cyan-400/60 font-mono truncate">{pullStatus.status}</p>
                            </div>
                          )}

                          {/* Search input */}
                          <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-shogun-subdued/50" />
                            <input
                              type="text"
                              value={ollamaQuery}
                              onChange={e => setOllamaQuery(e.target.value)}
                              placeholder="Search all Ollama models..."
                              className="w-full bg-[#050508] border border-shogun-border rounded-lg pl-9 pr-3 py-2 text-xs focus:border-cyan-500/60 outline-none placeholder:text-shogun-subdued/40"
                            />
                            {ollamaLoading && (
                              <RefreshCw className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-cyan-400 animate-spin" />
                            )}
                          </div>

                          {/* Category filter */}
                          <div className="flex gap-1 flex-wrap">
                            {(['all', 'vision', 'tools', 'thinking', 'embedding', 'cloud'] as const).map(f => (
                              <button
                                key={f}
                                type="button"
                                onClick={() => setPullCatalogFilter(f)}
                                className={cn(
                                  "px-2.5 py-1 rounded text-[9px] font-bold uppercase tracking-widest border transition-all",
                                  pullCatalogFilter === f
                                    ? "bg-cyan-500/15 border-cyan-500/40 text-cyan-400"
                                    : "bg-transparent border-shogun-border text-shogun-subdued hover:border-shogun-subdued"
                                )}
                              >
                                {f}
                              </button>
                            ))}
                          </div>

                          {/* Model results */}
                          <div className="grid grid-cols-1 gap-2 max-h-80 overflow-y-auto pr-1 scrollbar-thin">
                            {ollamaLoading && ollamaResults.length === 0 ? (
                              <div className="flex items-center justify-center py-8 text-shogun-subdued/50">
                                <RefreshCw className="w-4 h-4 animate-spin mr-2" />
                                <span className="text-[10px]">Searching ollama.com...</span>
                              </div>
                            ) : ollamaSearchError ? (
                              <div className="flex flex-col items-center justify-center py-8 text-red-400/70 text-center">
                                <span className="text-[10px]">{ollamaSearchError}</span>
                                <button type="button" onClick={() => searchOllamaModels(ollamaQuery, 1, false)} className="text-[9px] mt-2 text-cyan-400 hover:text-cyan-300">Retry search</button>
                              </div>
                            ) : ollamaResults.length === 0 ? (
                              <div className="flex flex-col items-center justify-center py-8 text-shogun-subdued/50">
                                <span className="text-[10px]">No models found</span>
                                <span className="text-[9px] mt-1">Try a different search or use a custom tag below</span>
                              </div>
                            ) : (
                              ollamaResults.map(m => {
                                const isThis = pullingModel === m.id;
                                const matchingLocalModel = localModels.find(model => {
                                  const normModel = model.toLowerCase();
                                  const normId = m.id.toLowerCase();
                                  if (normModel === normId) return true;
                                  if (normModel.startsWith(normId + ':')) return true;
                                  return false;
                                });
                                const alreadyHave = !!matchingLocalModel;
                                return (
                                  <div
                                    key={m.id}
                                    className={cn(
                                      "flex items-center justify-between p-2.5 rounded-lg border transition-all",
                                      isThis
                                        ? "border-cyan-500/40 bg-cyan-500/5"
                                        : alreadyHave
                                          ? "border-green-500/20 bg-green-500/5"
                                          : "border-shogun-border hover:border-shogun-subdued bg-[#050508]"
                                    )}
                                  >
                                    <div className="min-w-0">
                                      <div className="flex items-center gap-2 flex-wrap">
                                        <span className="text-[10px] font-bold text-shogun-text truncate">{m.name}</span>
                                        {m.sizes.map(s => (
                                          <span key={s} className="text-[7px] px-1 py-0.5 rounded bg-blue-500/10 border border-blue-500/20 text-blue-400 font-bold shrink-0">{s}</span>
                                        ))}
                                        {alreadyHave && <span className="text-[8px] text-green-400 font-bold shrink-0">✓ local</span>}
                                      </div>
                                      <p className="text-[8px] text-shogun-subdued/70 truncate mt-0.5">{m.description}</p>
                                      <div className="flex items-center gap-2 mt-0.5">
                                        {m.capabilities.map(cap => (
                                          <span key={cap} className="text-[7px] px-1 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 font-medium">{cap}</span>
                                        ))}
                                        <span className="text-[7px] text-shogun-subdued/50 font-mono">↓{m.pulls}</span>
                                        {m.tag_count > 0 && <span className="text-[7px] text-shogun-subdued/50 font-mono">{m.tag_count} tags</span>}
                                        {m.updated && <span className="text-[7px] text-shogun-subdued/40">{m.updated}</span>}
                                      </div>
                                    </div>
                                    <div className="ml-3 shrink-0 flex items-center gap-1">
                                      <button
                                        type="button"
                                        disabled={!!pullingModel}
                                        onClick={() => handlePullModel(m.id)}
                                        className={cn(
                                          "flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[9px] font-bold uppercase transition-all border",
                                          isThis
                                            ? "border-cyan-500/40 text-cyan-400 bg-cyan-500/10 animate-pulse"
                                            : alreadyHave
                                              ? "border-green-500/20 text-green-400 bg-green-500/5 hover:bg-green-500/10"
                                              : "border-shogun-border text-shogun-subdued hover:border-cyan-500/50 hover:text-cyan-400 hover:bg-cyan-500/5 disabled:opacity-30 disabled:cursor-not-allowed"
                                        )}
                                      >
                                        {isThis
                                          ? <><RefreshCw className="w-2.5 h-2.5 animate-spin" /> {t('katana.pulling')}</>
                                          : alreadyHave
                                            ? <><RefreshCw className="w-2.5 h-2.5" /> {t('katana.repull')}</>
                                            : <><Download className="w-2.5 h-2.5" /> {t('katana.pull')}</>}
                                      </button>
                                      {alreadyHave && matchingLocalModel && localProviderType === 'ollama' && (
                                        <button
                                          type="button"
                                          disabled={!!pullingModel || deletingModel === matchingLocalModel}
                                          onClick={(e) => { e.stopPropagation(); handleDeleteOllamaModel(matchingLocalModel); }}
                                          className={cn(
                                            "p-1.5 rounded-lg transition-all border",
                                            deletingModel === matchingLocalModel
                                              ? "border-red-500/40 text-red-400 bg-red-500/10 animate-pulse"
                                              : "border-shogun-border text-red-500/40 hover:border-red-500/50 hover:text-red-500 hover:bg-red-500/5 disabled:opacity-30 disabled:cursor-not-allowed"
                                          )}
                                          title={t('katana.delete_local_model', 'Delete from Ollama')}
                                        >
                                          <Trash2 className="w-3 h-3" />
                                        </button>
                                      )}
                                    </div>
                                  </div>
                                );
                              })
                            )}

                            {/* Load More */}
                            {ollamaHasMore && !ollamaLoading && (
                              <button
                                type="button"
                                onClick={() => searchOllamaModels(ollamaQuery, ollamaPage + 1, true)}
                                disabled={ollamaLoadingMore}
                                className="w-full py-2 rounded-lg border border-shogun-border text-[9px] font-bold uppercase tracking-widest text-shogun-subdued hover:border-cyan-500/40 hover:text-cyan-400 transition-all disabled:opacity-50"
                              >
                                {ollamaLoadingMore
                                  ? <><RefreshCw className="w-3 h-3 animate-spin inline mr-1" /> Loading...</>
                                  : 'Load More Models'}
                              </button>
                            )}
                          </div>

                          {/* Custom model tag */}
                          <div className="pt-2 border-t border-shogun-border/50 space-y-1.5">
                            <label className="text-[9px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.custom_model_tag', 'Custom Model Tag')}</label>
                            <div className="flex gap-2">
                              <input
                                type="text"
                                value={customPullTag}
                                onChange={e => setCustomPullTag(e.target.value)}
                                onKeyDown={e => { if (e.key === 'Enter' && customPullTag.trim()) { e.preventDefault(); handlePullModel(customPullTag.trim()); setCustomPullTag(''); }}}
                                placeholder="e.g. llama3.2:latest or mistral:7b-instruct"
                                className="flex-1 bg-[#050508] border border-shogun-border rounded-lg px-3 py-2 text-xs font-mono focus:border-cyan-500/60 outline-none placeholder:text-shogun-subdued/40"
                              />
                              <button
                                type="button"
                                disabled={!!pullingModel || !customPullTag.trim()}
                                onClick={() => { handlePullModel(customPullTag.trim()); setCustomPullTag(''); }}
                                className="px-3 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 hover:border-cyan-500/60 disabled:opacity-30 disabled:cursor-not-allowed rounded-lg text-cyan-400 text-[10px] font-bold uppercase tracking-widest transition-all whitespace-nowrap flex items-center gap-1"
                              >
                                <Download className="w-3 h-3" /> {t('katana.pull')}
                              </button>
                            </div>
                            <p className="text-[9px] text-shogun-subdued/60">Any valid Ollama model tag from <a href="https://ollama.com/search" target="_blank" rel="noopener noreferrer" className="text-cyan-400/70 font-mono hover:text-cyan-400 transition-colors">ollama.com/search</a></p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* ── Manage Local Models ─────────────────────── */}
                  {isLocal && localModels.length > 0 && (
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-2">
                        <Monitor className="w-3.5 h-3.5" />
                        {t('katana.manage_local_models', 'Manage Local Models')}
                        <span className="text-[8px] px-1.5 py-0.5 rounded bg-[#050508] border border-shogun-border text-shogun-subdued font-bold">{localModels.length}</span>
                      </label>
                      <div className="grid grid-cols-1 gap-1.5 max-h-48 overflow-y-auto pr-1 scrollbar-thin">
                        {localModels.map(m => (
                          <div
                            key={m}
                            className="flex items-center justify-between p-2 rounded-lg border border-shogun-border bg-[#050508] hover:border-shogun-subdued transition-all"
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="w-1.5 h-1.5 rounded-full bg-green-500 shrink-0" />
                              <span className="text-[10px] font-mono text-shogun-text truncate">{m}</span>
                            </div>
                            <button
                              type="button"
                              disabled={configuredModels.includes(m)}
                              onClick={() => addConfiguredModel(m)}
                              className="ml-auto shrink-0 px-2 py-1 rounded-lg border border-purple-500/30 text-purple-300 hover:bg-purple-500/10 disabled:border-green-500/30 disabled:text-green-400 text-[9px] font-bold uppercase"
                            >
                              {configuredModels.includes(m) ? 'Added' : '+ Add'}
                            </button>
                            {localProviderType === 'ollama' && (
                              <button
                                type="button"
                                disabled={deletingModel === m}
                                onClick={() => handleDeleteOllamaModel(m)}
                                className={cn(
                                  "shrink-0 flex items-center gap-1 px-2 py-1 rounded-lg text-[9px] font-bold uppercase transition-all border",
                                  deletingModel === m
                                    ? "border-red-500/40 text-red-400 bg-red-500/10 animate-pulse"
                                    : "border-shogun-border text-red-500/50 hover:border-red-500/50 hover:text-red-500 hover:bg-red-500/5"
                                )}
                                title={t('katana.delete_local_model', 'Delete from Ollama')}
                              >
                                <Trash2 className="w-3 h-3" />
                                <span>{t('katana.delete', 'Delete')}</span>
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex gap-2">
                    <button
                      type="submit"
                      disabled={saving || !newProvider.name}
                      className="flex-1 py-3 bg-shogun-blue hover:bg-shogun-blue/90 text-white font-bold rounded-lg shadow-shogun transition-all flex items-center justify-center gap-2"
                    >
                      {saving ? (
                        <RefreshCw className="w-4 h-4 animate-spin" />
                      ) : (
                        editingProviderId ? <CheckCircle2 className="w-4 h-4" /> : <Save className="w-4 h-4" />
                      )}
                      {editingProviderId ? t('katana.update_provider') : t('katana.initiate_provider')}
                    </button>
                    {editingProviderId && (
                      <button
                        type="button"
                        onClick={handleCancelEdit}
                        className="px-4 py-2 bg-shogun-subdued/10 hover:bg-shogun-subdued/20 border border-shogun-border rounded-lg text-shogun-subdued text-xs font-bold uppercase transition-all"
                      >
                        {t('common.cancel')}
                      </button>
                    )}
                  </div>
                </form>
              </div>
            </div>

            {/* Active Providers grid */}
            <div className="lg:col-span-2 space-y-6">
              <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                <Cpu className="w-5 h-5 text-shogun-blue" /> {t('katana.active_providers')}
              </h3>

              {loading ? (
                <div className="p-12 text-center shogun-card opacity-50">
                  <RefreshCw className="w-8 h-8 animate-spin mx-auto text-shogun-blue mb-4" />
                  <p className="text-xs uppercase tracking-widest font-bold">{t('katana.querying_model_grid')}</p>
                </div>
              ) : providers.length === 0 ? (
                <div className="p-12 text-center shogun-card border-dashed">
                  <p className="text-shogun-subdued italic">{t('katana.no_providers')}</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-4">
                  {providers.map((p) => {
                    const color   = getProviderColor(p.provider_type);
                    const docLink = p.auth_type === 'chatgpt'
                      ? { label: 'Official Codex App Server guide', url: 'https://learn.chatgpt.com/docs/app-server' }
                      : PROVIDER_DOCS[p.provider_type];
                    const isActive = p.status === 'connected';
                    const isLocalProv = isLocalProvider(p.provider_type);
                    return (
                      <div key={p.id} className="shogun-card group hover:border-shogun-blue/50 transition-all">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center", color.bg, color.text)}>
                              {isLocalProv
                                ? <Monitor className="w-6 h-6" />
                                : <Cloud className="w-6 h-6" />
                              }
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <h4 className="font-bold text-shogun-text">{p.name}</h4>
                                {isActive
                                  ? <span className="text-[8px] bg-green-500/10 text-green-500 px-1.5 py-0.5 rounded border border-green-500/20 font-bold uppercase">{t('katana.active')}</span>
                                  : <span className="text-[8px] bg-shogun-subdued/10 text-shogun-subdued px-1.5 py-0.5 rounded border border-shogun-border font-bold uppercase">{p.status ?? t('katana.not_configured')}</span>
                                }
                              </div>
                              <div className="flex items-center gap-2 mt-1">
                                <span className="text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded bg-[#050508] border border-shogun-border text-shogun-subdued">
                                  {getProviderDisplayType(p.provider_type)}
                                </span>
                                <span className="text-xs text-shogun-subdued">
                                  {p.auth_type === 'chatgpt'
                                    ? `Codex subscription${p.config?.codex_plan_type ? ` · ${p.config.codex_plan_type}` : ''}`
                                    : p.base_url || t('katana.default_endpoint')}
                                </span>
                              </div>
                              {Array.isArray(p.config?.models) && p.config.models.length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-2">
                                  {p.config.models.map((modelId: string) => (
                                    <span key={modelId} className="text-[9px] font-mono px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/25 text-purple-300 font-semibold">
                                      {modelId}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {p.auth_type === 'oauth' && p.provider_type === 'openai' && (
                              <button type="button" disabled={testingOAuthProviderId !== null} onClick={async () => {
                                setTestingOAuthProviderId(p.id);
                                try {
                                  const response = await axios.post(`/api/v1/model-providers/${p.id}/test`);
                                  const result = response.data.data;
                                  setStatusMessage({ type: result.status === 'ok' ? 'success' : 'error', text: result.note });
                                } catch { setStatusMessage({ type: 'error', text: 'Connection check failed. Try again.' }); }
                                finally { setTestingOAuthProviderId(null); }
                              }} className="rounded-lg border border-shogun-border px-2 py-1.5 text-xs text-shogun-text disabled:opacity-50">
                                {testingOAuthProviderId === p.id ? 'Checking…' : 'Test connection'}
                              </button>
                            )}
                            {p.auth_type === 'oauth' && (
                              <button
                                onClick={() => isActive ? handleDisconnectOAuth(p.id) : handleConnectOAuth(p.id)}
                                className="px-2 py-1.5 rounded-lg border border-cyan-400/30 bg-cyan-400/5 text-[9px] font-bold uppercase text-cyan-300 hover:bg-cyan-400/10"
                                title={isActive ? 'Remove stored OAuth grants' : 'Open provider authorization'}
                              >
                                {isActive ? 'Disconnect OAuth' : 'Connect OAuth'}
                              </button>
                            )}
                            {p.auth_type === 'chatgpt' && (
                              <button
                                onClick={() => isActive ? handleDisconnectCodex(p.id) : handleConnectCodex(p.id)}
                                className="px-2 py-1.5 rounded-lg border border-green-400/30 bg-green-400/5 text-[9px] font-bold uppercase text-green-300 hover:bg-green-400/10"
                                title={isActive ? 'Sign out and remove the local Codex credential' : 'Open official ChatGPT sign-in'}
                              >
                                {isActive ? 'Disconnect ChatGPT' : 'Connect ChatGPT'}
                              </button>
                            )}
                            {docLink && (
                              <a
                                href={docLink.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="p-2 hover:bg-shogun-blue/10 text-shogun-subdued hover:text-shogun-blue rounded-lg transition-colors"
                                title={docLink.label}
                              >
                                <ExternalLink className="w-4 h-4" />
                              </a>
                            )}
                            <button
                              onClick={() => handleStartEdit(p)}
                              className="p-2 hover:bg-shogun-card rounded-lg transition-colors text-shogun-subdued hover:text-shogun-gold"
                              title={t('katana.edit_provider')}
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            {!['oauth', 'chatgpt'].includes(p.auth_type) && <button
                                onClick={() => handleToggleProvider(p.id, p.status)}
                                className="p-2 hover:bg-shogun-card rounded-lg transition-colors text-shogun-subdued hover:text-shogun-text"
                                title={isActive ? t('katana.disable') : t('katana.enable')}
                              >
                                {isActive ? <Zap className="w-4 h-4" /> : <ShieldCheck className="w-4 h-4" />}
                              </button>}
                            <button
                              onClick={() => handleDeleteProvider(p.id, p.name)}
                              className="p-2 hover:bg-red-500/10 text-red-500/50 hover:text-red-500 rounded-lg transition-colors"
                              title={t('katana.delete_provider')}
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Local Models Manager */}
              {localModels.length > 0 && (
                <div className="shogun-card space-y-4 border border-shogun-border bg-[#02040a]/40 backdrop-blur-md rounded-xl p-5 mt-6">
                  <div className="flex items-center justify-between border-b border-shogun-border/40 pb-3">
                    <div className="flex items-center gap-2">
                      <Monitor className="w-5 h-5 text-green-400" />
                      <div>
                        <h4 className="font-bold text-shogun-text text-sm">Local Models Manager</h4>
                        <p className="text-[10px] text-shogun-subdued mt-0.5">Manage models pulled on your local machines</p>
                      </div>
                    </div>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#050508] border border-shogun-border text-green-400 font-mono font-bold">
                      {localModels.length} models
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-80 overflow-y-auto pr-1 scrollbar-thin">
                    {localModels.map(m => {
                      return (
                        <div
                          key={m}
                          className="flex items-center justify-between p-3 rounded-lg border border-shogun-border bg-[#050508]/60 hover:border-shogun-subdued transition-all group"
                        >
                          <div className="flex flex-col min-w-0 mr-3">
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="w-2 h-2 rounded-full bg-green-500 shrink-0 shadow-[0_0_8px_#22c55e]" />
                              <span className="text-xs font-mono text-shogun-text truncate font-semibold" title={m}>{m}</span>
                            </div>
                          </div>
                          <button
                            type="button"
                            disabled={configuredModels.includes(m)}
                            onClick={() => addConfiguredModel(m)}
                            className="ml-auto mr-2 shrink-0 px-2.5 py-1.5 rounded-lg border border-purple-500/30 text-purple-300 hover:bg-purple-500/10 disabled:border-green-500/30 disabled:text-green-400 text-[9px] font-bold uppercase"
                          >
                            {configuredModels.includes(m) ? 'Added' : '+ Add'}
                          </button>
                          {localProviderType === 'ollama' && (
                            <button
                              type="button"
                              disabled={deletingModel === m}
                              onClick={() => handleDeleteOllamaModel(m)}
                              className={cn(
                                "shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[9px] font-bold uppercase transition-all border",
                                deletingModel === m
                                  ? "border-red-500/40 text-red-400 bg-red-500/10 animate-pulse"
                                  : "border-shogun-border text-red-500/60 hover:border-red-500 hover:text-red-500 hover:bg-red-500/10"
                              )}
                              title={t('katana.delete_local_model', 'Delete from Ollama')}
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                              <span>{deletingModel === m ? t('katana.deleting', 'Deleting') : t('katana.delete', 'Delete')}</span>
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>

      </div>
    </div>
  );
}
