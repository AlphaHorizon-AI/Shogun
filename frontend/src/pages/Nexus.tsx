import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Network,
  Plus,
  Send,
  RefreshCw,
  Users,
  MessageSquare,
  FileText,
  Loader2,
  X,
  Copy,
  Check,
  Wifi,
  ChevronRight,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  GitBranch,
  Zap,
  BookOpen,
  ArrowLeft,
  Edit3,
  Save,
  Trash2,
  UserPlus,
} from 'lucide-react';
import axios from 'axios';
import { cn } from '../lib/utils';

// ── Types ──────────────────────────────────────────────────────

type MessageType = 'proposal' | 'task' | 'reply' | 'update' | 'plan_revision' | 'approval' | 'signal' | 'system' | 'invitation';

interface Peer {
  id: string;
  peer_name: string;
  peer_url: string;
  role: string;
  status: string;
  last_seen_at: string | null;
}

interface WorkspaceMessage {
  id: string;
  from_name: string;
  from_peer_url: string | null;
  from_agent_id: string | null;
  message_type: MessageType;
  content: string;
  parent_message_id: string | null;
  delivery_status: string;
  created_at: string;
}

interface Workspace {
  id: string;
  name: string;
  description: string | null;
  topic: string | null;
  status: string;
  scope: string;
  shared_document: string | null;
  document_version: number;
  tags: string[];
  peer_count: number;
  message_count: number;
  peers: Peer[];
  messages: WorkspaceMessage[];
  created_at: string;
}

interface Identity {
  name: string;
  agent_id: string | null;
  inbound_url: string;
  platform: string;
  version: string;
}

// ── Constants ──────────────────────────────────────────────────

const MSG_TYPE_CONFIG: Record<MessageType | string, { color: string; label: string; icon: any }> = {
  proposal:      { color: 'text-purple-400 bg-purple-500/10 border-purple-500/30', label: 'Proposal',     icon: Sparkles },
  task:          { color: 'text-shogun-blue bg-shogun-blue/10 border-shogun-blue/30', label: 'Task',      icon: Zap },
  reply:         { color: 'text-shogun-subdued bg-shogun-card border-shogun-border', label: 'Reply',       icon: MessageSquare },
  update:        { color: 'text-green-400 bg-green-500/10 border-green-500/30', label: 'Update',          icon: GitBranch },
  plan_revision: { color: 'text-shogun-gold bg-shogun-gold/10 border-shogun-gold/30', label: 'Plan Rev.', icon: Edit3 },
  approval:      { color: 'text-green-400 bg-green-500/10 border-green-500/30', label: 'Approval',        icon: CheckCircle2 },
  signal:        { color: 'text-orange-400 bg-orange-500/10 border-orange-500/30', label: 'Signal',       icon: AlertCircle },
  invitation:    { color: 'text-purple-400 bg-purple-500/10 border-purple-500/30', label: 'Invitation',   icon: UserPlus },
  system:        { color: 'text-shogun-subdued/60 bg-transparent border-transparent', label: 'System',    icon: Network },
};

const PEER_STATUS_COLOR: Record<string, string> = {
  active:  'bg-green-500',
  pending: 'bg-yellow-500',
  offline: 'bg-shogun-subdued',
  declined:'bg-red-500',
};

// ── Helper ─────────────────────────────────────────────────────

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch { return ''; }
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' });
  } catch { return ''; }
}

// ── Main Component ─────────────────────────────────────────────

export function Nexus() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selected, setSelected] = useState<Workspace | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  // Create workspace modal
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newTopic, setNewTopic] = useState('');
  const [creating, setCreating] = useState(false);

  // Invite peer modal
  const [showInvite, setShowInvite] = useState(false);
  const [inviteUrl, setInviteUrl] = useState('');
  const [inviteName, setInviteName] = useState('');
  const [inviting, setInviting] = useState(false);
  const [inviteMsg, setInviteMsg] = useState<{type: 'success'|'error', text: string}|null>(null);

  // Message composer
  const [msgContent, setMsgContent] = useState('');
  const [msgType, setMsgType] = useState<MessageType>('update');
  const [sending, setSending] = useState(false);

  // Document editor
  const [editingDoc, setEditingDoc] = useState(false);
  const [docContent, setDocContent] = useState('');
  const [savingDoc, setSavingDoc] = useState(false);

  // Delete workspace
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  // Polling
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const threadEndRef = useRef<HTMLDivElement>(null);

  // ── Fetch ─────────────────────────────────────────────────

  const fetchAll = useCallback(async () => {
    try {
      const [wsRes, idRes] = await Promise.all([
        axios.get('/api/v1/workspaces'),
        axios.get('/api/v1/a2a/identity'),
      ]);
      setWorkspaces(wsRes.data.data || []);
      setIdentity(idRes.data.data);
    } catch (err) {
      console.error('Nexus fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshSelected = useCallback(async () => {
    if (!selected) return;
    try {
      const res = await axios.get(`/api/v1/workspaces/${selected.id}`);
      const fresh = res.data.data as Workspace;
      setSelected(fresh);
      setWorkspaces(prev => prev.map(w => w.id === fresh.id ? fresh : w));
    } catch (err) {
      console.error('Workspace refresh error:', err);
    }
  }, [selected]);

  useEffect(() => {
    fetchAll();
  }, []);

  // Poll every 8s when a workspace is open
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (selected) {
      pollRef.current = setInterval(refreshSelected, 8000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [selected?.id]);

  // Auto-scroll thread
  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [selected?.messages?.length]);

  // ── Actions ───────────────────────────────────────────────

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const res = await axios.post('/api/v1/workspaces', {
        name: newName,
        description: newDesc || null,
        topic: newTopic || null,
      });
      const ws = res.data.data as Workspace;
      setWorkspaces(prev => [ws, ...prev]);
      setSelected(ws);
      setShowCreate(false);
      setNewName(''); setNewDesc(''); setNewTopic('');
    } catch (err) { console.error(err); }
    finally { setCreating(false); }
  };

  const handleInvite = async () => {
    if (!inviteUrl.trim() || !selected) return;
    setInviting(true);
    setInviteMsg(null);
    try {
      await axios.post(`/api/v1/workspaces/${selected.id}/peers`, {
        peer_url: inviteUrl,
        peer_name: inviteName || 'Remote Shogun',
      });
      setInviteMsg({ type: 'success', text: 'Invitation sent. Peer is now pending.' });
      setInviteUrl(''); setInviteName('');
      await refreshSelected();
    } catch (err: any) {
      setInviteMsg({ type: 'error', text: err.response?.data?.detail || 'Invite failed' });
    } finally { setInviting(false); }
  };

  const handleSend = async () => {
    if (!msgContent.trim() || !selected) return;
    setSending(true);
    try {
      await axios.post(`/api/v1/workspaces/${selected.id}/messages`, {
        content: msgContent,
        message_type: msgType,
      });
      setMsgContent('');
      await refreshSelected();
    } catch (err) { console.error(err); }
    finally { setSending(false); }
  };

  const handleSaveDoc = async () => {
    if (!selected) return;
    setSavingDoc(true);
    try {
      await axios.patch(`/api/v1/workspaces/${selected.id}/document`, { content: docContent });
      setEditingDoc(false);
      await refreshSelected();
    } catch (err) { console.error(err); }
    finally { setSavingDoc(false); }
  };

  const handleRemovePeer = async (peerId: string) => {
    if (!selected) return;
    try {
      await axios.delete(`/api/v1/workspaces/${selected.id}/peers/${peerId}`);
      await refreshSelected();
    } catch (err) { console.error(err); }
  };

  const handleDeleteWorkspace = async (wsId: string) => {
    setDeletingId(wsId);
    try {
      await axios.delete(`/api/v1/workspaces/${wsId}`);
      setWorkspaces(prev => prev.filter(w => w.id !== wsId));
      if (selected?.id === wsId) setSelected(null);
    } catch (err) { console.error(err); }
    finally { setDeletingId(null); setConfirmDeleteId(null); }
  };

  const copyEndpoint = () => {
    if (identity?.inbound_url) {
      navigator.clipboard.writeText(identity.inbound_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // ── Render: Workspace List ────────────────────────────────

  if (!selected) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500 max-w-7xl mx-auto pb-12">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
              Nexus
              <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">A2A Protocol</span>
            </h2>
            <p className="text-shogun-subdued text-sm mt-1">Agent-to-Agent workspaces — plan, communicate, and collaborate with remote Shogun instances.</p>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={fetchAll} className="p-2.5 bg-shogun-card border border-shogun-border rounded-lg text-shogun-subdued hover:text-shogun-gold transition-colors">
              <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
            </button>
            <button
              onClick={() => setShowCreate(true)}
              className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs uppercase tracking-[0.15em] rounded-xl shadow-lg transition-all flex items-center gap-2"
            >
              <Plus className="w-4 h-4" /> New Workspace
            </button>
          </div>
        </div>

        {/* Identity Card */}
        {identity && (
          <div className="shogun-card bg-indigo-500/5 border-indigo-500/20 flex items-center gap-6">
            <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center flex-shrink-0">
              <Network className="w-6 h-6 text-indigo-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[10px] font-bold text-indigo-400 uppercase tracking-widest">My A2A Endpoint</p>
              <p className="text-sm font-bold text-shogun-text mt-0.5">{identity.name}</p>
              <code className="text-[10px] text-shogun-subdued font-mono truncate block">{identity.inbound_url}</code>
            </div>
            <button
              onClick={copyEndpoint}
              className="flex-shrink-0 px-4 py-2 bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 rounded-lg text-xs font-bold uppercase tracking-widest hover:bg-indigo-500/20 transition-colors flex items-center gap-2"
            >
              {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? 'Copied' : 'Copy URL'}
            </button>
          </div>
        )}

        {/* Workspace Grid */}
        {loading ? (
          <div className="p-20 text-center shogun-card border-dashed flex flex-col items-center gap-4">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-shogun-subdued">Loading workspaces...</p>
          </div>
        ) : workspaces.length === 0 ? (
          <div className="p-20 text-center shogun-card border-dashed border-2 border-indigo-500/20 flex flex-col items-center gap-6">
            <div className="relative">
              <div className="w-20 h-20 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                <Network className="w-10 h-10 text-indigo-400" />
              </div>
              <Sparkles className="absolute -top-1 -right-1 w-5 h-5 text-shogun-gold animate-pulse" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-shogun-text mb-2">No Workspaces Yet</h3>
              <p className="text-sm text-shogun-subdued max-w-md">Create a workspace to start collaborating with other Shogun instances using the A2A protocol.</p>
            </div>
            <button onClick={() => setShowCreate(true)} className="px-8 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs uppercase tracking-[0.2em] rounded-xl shadow-lg transition-all flex items-center gap-2">
              <Plus className="w-4 h-4" /> Create First Workspace
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {workspaces.map(ws => (
              <div key={ws.id} className="relative shogun-card group hover:border-indigo-500/50 transition-all flex flex-col">
                {/* Delete button — appears on hover */}
                <button
                  onClick={e => { e.stopPropagation(); setConfirmDeleteId(ws.id); }}
                  className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 p-1.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition-all z-10"
                  title="Delete workspace"
                >
                  {deletingId === ws.id
                    ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    : <Trash2 className="w-3.5 h-3.5" />}
                </button>

                <button
                  onClick={() => { setSelected(ws); setDocContent(ws.shared_document || ''); }}
                  className="text-left flex flex-col flex-1"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center group-hover:bg-indigo-500/20 transition-colors flex-shrink-0">
                      <GitBranch className="w-6 h-6 text-indigo-400" />
                    </div>
                    <div className="flex flex-col items-end gap-1 pr-8">
                      <span className={cn(
                        'text-[8px] font-bold uppercase tracking-widest px-2 py-0.5 rounded border',
                        ws.scope === 'federated'
                          ? 'text-indigo-400 bg-indigo-500/10 border-indigo-500/30'
                          : 'text-shogun-subdued bg-shogun-card border-shogun-border'
                      )}>{ws.scope}</span>
                      <span className={cn(
                        'text-[8px] font-bold uppercase tracking-widest px-2 py-0.5 rounded',
                        ws.status === 'active' ? 'text-green-400' : 'text-shogun-subdued'
                      )}>{ws.status}</span>
                    </div>
                  </div>

                  <h3 className="text-lg font-bold text-shogun-text group-hover:text-indigo-400 transition-colors">{ws.name}</h3>
                  {ws.topic && <p className="text-[10px] text-indigo-400/70 font-bold uppercase tracking-widest mt-1">{ws.topic}</p>}
                  {ws.description && <p className="text-xs text-shogun-subdued mt-2 line-clamp-2 leading-relaxed flex-1">{ws.description}</p>}

                  <div className="mt-6 pt-4 border-t border-shogun-border flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1.5 text-[10px] text-shogun-subdued">
                        <Users className="w-3 h-3" /> {ws.peer_count} peer{ws.peer_count !== 1 ? 's' : ''}
                      </div>
                      <div className="flex items-center gap-1.5 text-[10px] text-shogun-subdued">
                        <MessageSquare className="w-3 h-3" /> {ws.message_count} msg{ws.message_count !== 1 ? 's' : ''}
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-shogun-subdued group-hover:text-indigo-400 transition-colors" />
                  </div>
                </button>
              </div>
            ))}
          </div>

        )}

        {/* Delete Confirmation Modal — rendered outside ternary */}
        {confirmDeleteId && (() => {
          const ws = workspaces.find(w => w.id === confirmDeleteId);
          return ws ? (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
              <div className="bg-shogun-bg border border-red-500/30 w-full max-w-sm rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
                <div className="p-6 border-b border-red-500/20 bg-red-500/5 flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
                    <Trash2 className="w-5 h-5 text-red-400" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-shogun-text">Delete Workspace</h3>
                    <p className="text-[10px] text-red-400 uppercase tracking-widest font-bold">Permanent — cannot be undone</p>
                  </div>
                </div>
                <div className="p-6 space-y-4">
                  <p className="text-sm text-shogun-subdued">
                    Delete <strong className="text-shogun-text">{ws.name}</strong>? This will remove all {ws.message_count} messages and {ws.peer_count} peer connections permanently.
                  </p>
                  <div className="flex gap-3">
                    <button
                      onClick={() => setConfirmDeleteId(null)}
                      className="flex-1 py-3 bg-shogun-card border border-shogun-border text-shogun-subdued font-bold text-xs uppercase tracking-widest rounded-xl hover:border-shogun-text transition-colors"
                    >Cancel</button>
                    <button
                      onClick={() => handleDeleteWorkspace(ws.id)}
                      disabled={deletingId === ws.id}
                      className="flex-1 py-3 bg-red-600 hover:bg-red-500 text-white font-bold text-xs uppercase tracking-widest rounded-xl transition-all disabled:opacity-40 flex items-center justify-center gap-2"
                    >
                      {deletingId === ws.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ) : null;
        })()}

        {/* Create Modal */}
        {showCreate && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-shogun-bg border border-shogun-border w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
              <div className="p-6 border-b border-shogun-border bg-shogun-card flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                    <GitBranch className="w-5 h-5 text-indigo-400" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-shogun-text">New Workspace</h3>
                    <p className="text-[10px] text-shogun-subdued uppercase tracking-widest">A2A Collaboration</p>
                  </div>
                </div>
                <button onClick={() => setShowCreate(false)} className="p-2 hover:bg-[#0a0e1a] rounded-lg transition-colors">
                  <X className="w-5 h-5 text-shogun-subdued" />
                </button>
              </div>
              <div className="p-8 space-y-5">
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Name *</label>
                  <input
                    autoFocus
                    value={newName}
                    onChange={e => setNewName(e.target.value)}
                    placeholder="Project Alpha..."
                    className="w-full bg-[#050508] border border-shogun-border rounded-xl px-4 py-3 text-sm focus:border-indigo-500 outline-none transition-all"
                    onKeyDown={e => e.key === 'Enter' && handleCreate()}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Topic</label>
                  <input
                    value={newTopic}
                    onChange={e => setNewTopic(e.target.value)}
                    placeholder="e.g. Market analysis, Code review..."
                    className="w-full bg-[#050508] border border-shogun-border rounded-xl px-4 py-3 text-sm focus:border-indigo-500 outline-none transition-all"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Description</label>
                  <textarea
                    value={newDesc}
                    onChange={e => setNewDesc(e.target.value)}
                    placeholder="What will this workspace be used for?"
                    rows={3}
                    className="w-full bg-[#050508] border border-shogun-border rounded-xl px-4 py-3 text-sm focus:border-indigo-500 outline-none transition-all resize-none"
                  />
                </div>
                <div className="flex gap-3 pt-2">
                  <button onClick={() => setShowCreate(false)} className="flex-1 py-3 bg-shogun-card border border-shogun-border text-shogun-subdued font-bold text-xs uppercase tracking-widest rounded-xl hover:border-shogun-text transition-colors">Cancel</button>
                  <button onClick={handleCreate} disabled={creating || !newName.trim()} className="flex-1 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs uppercase tracking-[0.15em] rounded-xl shadow-lg transition-all disabled:opacity-40 flex items-center justify-center gap-2">
                    {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                    {creating ? 'Creating...' : 'Create Workspace'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── Render: Workspace Detail ──────────────────────────────

  const localUrl = identity?.inbound_url || '';

  return (
    <div className="flex flex-col h-[calc(100vh-80px)] animate-in fade-in duration-300">
      {/* Detail Header */}
      <div className="flex items-center justify-between p-4 border-b border-shogun-border bg-shogun-card flex-shrink-0">
        <div className="flex items-center gap-4">
          <button
            onClick={() => { setSelected(null); setEditingDoc(false); fetchAll(); }}
            className="p-2 hover:bg-[#0a0e1a] rounded-lg transition-colors text-shogun-subdued hover:text-shogun-text"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="w-9 h-9 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
            <GitBranch className="w-4 h-4 text-indigo-400" />
          </div>
          <div>
            <h2 className="text-base font-bold text-shogun-text">{selected.name}</h2>
            {selected.topic && <p className="text-[10px] text-indigo-400/70 font-bold uppercase tracking-widest">{selected.topic}</p>}
          </div>
          <span className="text-[8px] font-bold uppercase tracking-widest px-2 py-0.5 rounded border text-green-400 bg-green-500/10 border-green-500/20">
            {selected.status}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={refreshSelected} className="p-2 text-shogun-subdued hover:text-indigo-400 transition-colors">
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={() => { setShowInvite(true); setInviteMsg(null); }}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs uppercase tracking-widest rounded-lg transition-all flex items-center gap-2"
          >
            <UserPlus className="w-3.5 h-3.5" /> Invite Peer
          </button>
          <button
            onClick={() => setConfirmDeleteId(selected.id)}
            className="p-2 text-shogun-subdued hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all border border-transparent hover:border-red-500/20"
            title="Delete workspace"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 3-Column Layout: Peers | Thread | Document */}
      <div className="flex-1 overflow-hidden grid grid-cols-[220px_1fr_320px]">

        {/* Left: Peer Roster */}
        <div className="border-r border-shogun-border overflow-y-auto bg-[#050508] p-4 space-y-4">
          <p className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-2">
            <Users className="w-3 h-3" /> Peers ({selected.peers.length})
          </p>

          {/* Local agent (self) */}
          <div className="p-3 rounded-xl border border-indigo-500/20 bg-indigo-500/5">
            <div className="flex items-center gap-2 mb-1">
              <span className="w-2 h-2 rounded-full bg-indigo-400 flex-shrink-0" />
              <p className="text-xs font-bold text-indigo-400 truncate">{identity?.name || 'Me'}</p>
            </div>
            <p className="text-[9px] text-shogun-subdued font-bold uppercase tracking-wider">Owner · This Instance</p>
          </div>

          {selected.peers.length === 0 ? (
            <div className="p-4 border border-dashed border-shogun-border rounded-xl text-center">
              <Wifi className="w-5 h-5 text-shogun-subdued mx-auto mb-2 opacity-30" />
              <p className="text-[10px] text-shogun-subdued">No peers yet. Invite a remote Shogun.</p>
            </div>
          ) : (
            selected.peers.map(peer => (
              <div key={peer.id} className="p-3 rounded-xl border border-shogun-border bg-shogun-card group">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={cn('w-2 h-2 rounded-full flex-shrink-0', PEER_STATUS_COLOR[peer.status] || 'bg-shogun-subdued')} />
                    <p className="text-xs font-bold text-shogun-text truncate">{peer.peer_name}</p>
                  </div>
                  <button
                    onClick={() => handleRemovePeer(peer.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-shogun-subdued hover:text-red-400 transition-all"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
                <p className="text-[8px] text-shogun-subdued font-bold uppercase tracking-wider mt-1">{peer.role} · {peer.status}</p>
                <p className="text-[8px] text-shogun-subdued/60 font-mono truncate mt-1">{peer.peer_url}</p>
                {peer.last_seen_at && (
                  <p className="text-[8px] text-shogun-subdued/50 mt-1">seen {formatDate(peer.last_seen_at)}</p>
                )}
              </div>
            ))
          )}
        </div>

        {/* Center: Message Thread */}
        <div className="flex flex-col overflow-hidden border-r border-shogun-border">
          {/* Thread */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {selected.messages.length === 0 && (
              <div className="p-8 text-center text-shogun-subdued text-xs">No messages yet. Post the first one.</div>
            )}
            {selected.messages.map(msg => {
              const cfg = MSG_TYPE_CONFIG[msg.message_type] || MSG_TYPE_CONFIG.update;
              const isLocal = msg.from_peer_url === localUrl || msg.from_agent_id === 'system';
              const isSystem = msg.message_type === 'system';

              if (isSystem) {
                return (
                  <div key={msg.id} className="flex items-center gap-3 py-1">
                    <div className="flex-1 h-px bg-shogun-border" />
                    <p className="text-[9px] text-shogun-subdued/60 whitespace-nowrap px-2 font-mono italic"
                      dangerouslySetInnerHTML={{ __html: msg.content.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`(.+?)`/g, '<code class="font-mono bg-shogun-card px-1 rounded">$1</code>') }}
                    />
                    <div className="flex-1 h-px bg-shogun-border" />
                  </div>
                );
              }

              return (
                <div key={msg.id} className={cn('flex gap-3', isLocal ? 'flex-row-reverse' : 'flex-row')}>
                  {/* Avatar */}
                  <div className={cn(
                    'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold',
                    isLocal ? 'bg-indigo-500/20 text-indigo-400' : 'bg-shogun-card border border-shogun-border text-shogun-subdued'
                  )}>
                    {(msg.from_name || '?').charAt(0).toUpperCase()}
                  </div>

                  <div className={cn('max-w-[75%] space-y-1', isLocal ? 'items-end' : 'items-start', 'flex flex-col')}>
                    {/* Meta */}
                    <div className={cn('flex items-center gap-2', isLocal ? 'flex-row-reverse' : 'flex-row')}>
                      <span className="text-[10px] font-bold text-shogun-text">{msg.from_name}</span>
                      <span className={cn('text-[8px] font-bold px-1.5 py-0.5 rounded border uppercase tracking-widest', cfg.color)}>
                        {cfg.label}
                      </span>
                      <span className="text-[9px] text-shogun-subdued/60 font-mono">{formatTime(msg.created_at)}</span>
                    </div>

                    {/* Bubble */}
                    <div className={cn(
                      'px-4 py-2.5 rounded-2xl text-sm leading-relaxed',
                      isLocal
                        ? 'bg-indigo-600 text-white rounded-tr-sm'
                        : 'bg-shogun-card border border-shogun-border text-shogun-text rounded-tl-sm'
                    )}>
                      <span dangerouslySetInnerHTML={{ __html: msg.content.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`(.+?)`/g, '<code class="font-mono bg-black/20 px-1 rounded text-xs">$1</code>') }} />
                    </div>

                    {/* Delivery */}
                    {isLocal && msg.delivery_status !== 'local' && (
                      <span className={cn('text-[8px] font-mono', msg.delivery_status === 'delivered' ? 'text-green-400' : msg.delivery_status === 'failed' ? 'text-red-400' : 'text-shogun-subdued')}>
                        {msg.delivery_status}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
            <div ref={threadEndRef} />
          </div>

          {/* Composer */}
          <div className="p-4 border-t border-shogun-border bg-shogun-card space-y-3 flex-shrink-0">
            {/* Type selector */}
            <div className="flex flex-wrap gap-1.5">
              {(['update', 'proposal', 'task', 'plan_revision', 'approval', 'signal'] as MessageType[]).map(t => {
                const cfg = MSG_TYPE_CONFIG[t];
                return (
                  <button
                    key={t}
                    onClick={() => setMsgType(t)}
                    className={cn(
                      'text-[9px] px-2.5 py-1 rounded border font-bold uppercase tracking-widest transition-all',
                      msgType === t ? cfg.color : 'text-shogun-subdued border-shogun-border hover:border-shogun-text'
                    )}
                  >
                    {cfg.label}
                  </button>
                );
              })}
            </div>
            {/* Input row */}
            <div className="flex gap-2">
              <textarea
                value={msgContent}
                onChange={e => setMsgContent(e.target.value)}
                placeholder={`Post a ${MSG_TYPE_CONFIG[msgType]?.label || 'message'}...`}
                rows={2}
                className="flex-1 bg-[#050508] border border-shogun-border rounded-xl px-4 py-2.5 text-sm focus:border-indigo-500 outline-none transition-all resize-none"
                onKeyDown={e => { if (e.key === 'Enter' && e.ctrlKey) handleSend(); }}
              />
              <button
                onClick={handleSend}
                disabled={sending || !msgContent.trim()}
                className="px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl transition-all disabled:opacity-40 flex items-center gap-2"
              >
                {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-[9px] text-shogun-subdued/50">Ctrl+Enter to send · Messages are fanned out to all active peers</p>
          </div>
        </div>

        {/* Right: Shared Document */}
        <div className="overflow-y-auto flex flex-col">
          <div className="p-4 border-b border-shogun-border flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-shogun-gold" />
              <p className="text-[10px] font-bold text-shogun-text uppercase tracking-widest">Shared Document</p>
              {selected.document_version > 0 && (
                <span className="text-[8px] font-mono text-shogun-subdued/60">v{selected.document_version}</span>
              )}
            </div>
            {!editingDoc ? (
              <button
                onClick={() => { setEditingDoc(true); setDocContent(selected.shared_document || ''); }}
                className="p-1.5 text-shogun-subdued hover:text-shogun-gold transition-colors rounded-lg hover:bg-shogun-card"
              >
                <Edit3 className="w-3.5 h-3.5" />
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <button onClick={() => setEditingDoc(false)} className="p-1.5 text-shogun-subdued hover:text-shogun-text transition-colors">
                  <X className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={handleSaveDoc}
                  disabled={savingDoc}
                  className="px-3 py-1.5 bg-shogun-gold hover:bg-shogun-gold/90 text-black text-[10px] font-bold uppercase tracking-widest rounded-lg transition-all flex items-center gap-1.5"
                >
                  {savingDoc ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                  Save
                </button>
              </div>
            )}
          </div>

          {editingDoc ? (
            <textarea
              value={docContent}
              onChange={e => setDocContent(e.target.value)}
              className="flex-1 bg-[#050508] text-sm text-shogun-text font-mono p-4 outline-none resize-none border-none"
              placeholder="# Document Title&#10;&#10;Write your shared plan here..."
            />
          ) : (
            <div className="flex-1 p-4 overflow-y-auto">
              {selected.shared_document ? (
                <div
                  className="prose prose-invert prose-sm max-w-none text-shogun-text text-sm leading-relaxed space-y-3"
                  dangerouslySetInnerHTML={{
                    __html: selected.shared_document
                      .replace(/^# (.+)$/gm, '<h1 class="text-lg font-bold text-shogun-text mt-4 first:mt-0">$1</h1>')
                      .replace(/^## (.+)$/gm, '<h2 class="text-sm font-bold text-indigo-400 uppercase tracking-widest mt-4 first:mt-0">$2</h2>')
                      .replace(/\*\*(.+?)\*\*/g, '<strong class="text-shogun-text">$1</strong>')
                      .replace(/`(.+?)`/g, '<code class="font-mono bg-shogun-card px-1.5 py-0.5 rounded text-xs text-shogun-gold">$1</code>')
                      .replace(/\n/g, '<br>')
                  }}
                />
              ) : (
                <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
                  <BookOpen className="w-8 h-8 text-shogun-subdued opacity-30" />
                  <p className="text-xs text-shogun-subdued">No document yet.<br />Click the edit icon to start writing.</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Invite Modal */}
      {showInvite && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-shogun-bg border border-shogun-border w-full max-w-md rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-6 border-b border-shogun-border bg-shogun-card flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                  <UserPlus className="w-5 h-5 text-indigo-400" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-shogun-text">Invite Peer</h3>
                  <p className="text-[10px] text-shogun-subdued uppercase tracking-widest">Remote Shogun A2A URL</p>
                </div>
              </div>
              <button onClick={() => setShowInvite(false)} className="p-2 hover:bg-[#0a0e1a] rounded-lg transition-colors">
                <X className="w-5 h-5 text-shogun-subdued" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div className="space-y-2">
                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Peer Endpoint URL *</label>
                <input
                  autoFocus
                  value={inviteUrl}
                  onChange={e => setInviteUrl(e.target.value)}
                  placeholder="http://remote-shogun:8000/api/v1/a2a/inbound"
                  className="w-full bg-[#050508] border border-shogun-border rounded-xl px-4 py-3 text-sm focus:border-indigo-500 outline-none transition-all font-mono"
                />
              </div>
              <div className="space-y-2">
                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Display Name (optional)</label>
                <input
                  value={inviteName}
                  onChange={e => setInviteName(e.target.value)}
                  placeholder="Their Shogun's name..."
                  className="w-full bg-[#050508] border border-shogun-border rounded-xl px-4 py-3 text-sm focus:border-indigo-500 outline-none transition-all"
                />
              </div>
              {inviteMsg && (
                <div className={cn('p-3 rounded-lg border text-xs', inviteMsg.type === 'success' ? 'bg-green-500/10 border-green-500/30 text-green-400' : 'bg-red-500/10 border-red-500/30 text-red-400')}>
                  {inviteMsg.text}
                </div>
              )}
              <div className="p-3 bg-indigo-500/5 border border-indigo-500/20 rounded-xl text-[10px] text-shogun-subdued space-y-1">
                <p className="font-bold text-indigo-400">How it works:</p>
                <p>• We ping their endpoint to verify it's reachable</p>
                <p>• A signed invitation is sent using HMAC-SHA256</p>
                <p>• They can then post messages back to this workspace</p>
              </div>
              <div className="flex gap-3">
                <button onClick={() => setShowInvite(false)} className="flex-1 py-3 bg-shogun-card border border-shogun-border text-shogun-subdued font-bold text-xs uppercase tracking-widest rounded-xl hover:border-shogun-text transition-colors">Cancel</button>
                <button
                  onClick={handleInvite}
                  disabled={inviting || !inviteUrl.trim()}
                  className="flex-1 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs uppercase tracking-widest rounded-xl transition-all disabled:opacity-40 flex items-center justify-center gap-2"
                >
                  {inviting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  {inviting ? 'Sending...' : 'Send Invitation'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
