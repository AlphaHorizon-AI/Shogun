import { useEffect, useState } from 'react';
import axios from 'axios';
import { FolderOpen, FolderPlus, RefreshCw, Save, CheckCircle2, AlertCircle, Folder, FileText } from 'lucide-react';
import { apiErrorMessage } from '../lib/apiError';

interface TreeEntry {
  name: string;
  path: string;
  type: 'directory' | 'file';
  size?: number;
  children?: TreeEntry[];
}

export const WorkspaceSetup = () => {
  const [workspacePath, setWorkspacePath] = useState('');
  const [savedPath, setSavedPath] = useState('');
  const [stats, setStats] = useState<{ total_files: number; total_directories: number; total_size_mb: number } | null>(null);
  const [tree, setTree] = useState<TreeEntry[]>([]);
  const [newFolderName, setNewFolderName] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [status, setStatus] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [cfgRes, infoRes, treeRes] = await Promise.all([
        axios.get('/api/v1/workspace/config'),
        axios.get('/api/v1/workspace/info'),
        axios.get('/api/v1/workspace/tree'),
      ]);
      const current = cfgRes.data?.data?.workspace_path || '';
      setWorkspacePath(current);
      setSavedPath(current);
      setStats(infoRes.data?.data || null);
      setTree(treeRes.data?.data?.tree || []);
    } catch (err) {
      setStatus({ type: 'error', text: apiErrorMessage(err, 'Failed to load local folder settings.') });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const handleSavePath = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!workspacePath.trim()) return;
    setSaving(true);
    setStatus(null);
    try {
      const res = await axios.put('/api/v1/workspace/config', { workspace_path: workspacePath.trim() });
      const updated = res.data?.data?.workspace_path || workspacePath.trim();
      setSavedPath(updated);
      setWorkspacePath(updated);
      setStatus({
        type: 'success',
        text: `Local folder set to ${updated}. Default 'input/' and 'output/' subfolders are ready.`,
      });
      await loadAll();
    } catch (err) {
      setStatus({ type: 'error', text: apiErrorMessage(err, 'Could not update local folder path.') });
    } finally {
      setSaving(false);
    }
  };

  const handleCreateSubfolder = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleaned = newFolderName.trim().replace(/^[/\\]+/, '');
    if (!cleaned) return;
    setCreatingFolder(true);
    setStatus(null);
    try {
      await axios.post('/api/v1/workspace/mkdir', { path: cleaned });
      setNewFolderName('');
      setStatus({ type: 'success', text: `Folder '${cleaned}' created inside workspace.` });
      await loadAll();
    } catch (err) {
      setStatus({ type: 'error', text: apiErrorMessage(err, 'Could not create subfolder.') });
    } finally {
      setCreatingFolder(false);
    }
  };

  const renderTree = (entries: TreeEntry[], depth = 0) =>
    entries.map((entry) => (
      <div key={entry.path}>
        <div
          className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-[#0f1426] text-xs"
          style={{ paddingLeft: `${depth * 18 + 8}px` }}
        >
          <div className="flex items-center gap-2 min-w-0">
            {entry.type === 'directory' ? (
              <Folder className="w-3.5 h-3.5 text-shogun-gold shrink-0" />
            ) : (
              <FileText className="w-3.5 h-3.5 text-shogun-subdued shrink-0" />
            )}
            <span className="font-mono text-shogun-text truncate">{entry.name}</span>
          </div>
          <span className="text-[10px] font-mono text-shogun-subdued shrink-0 ml-3">
            {entry.type === 'directory' ? `${entry.children?.length ?? 0} items` : `${entry.size ?? 0} B`}
          </span>
        </div>
        {entry.type === 'directory' && entry.children && entry.children.length > 0 && renderTree(entry.children, depth + 1)}
      </div>
    ));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-shogun-text tracking-tight flex items-center gap-2.5">
            <FolderOpen className="w-6 h-6 text-shogun-gold" />
            Local Folder Setup
          </h2>
          <p className="text-xs text-shogun-subdued mt-1">
            Configure the local filesystem directory used by AgentFlow Input, Workspace, and Output nodes.
          </p>
        </div>
        <button
          type="button"
          onClick={loadAll}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 rounded-lg border border-shogun-border text-xs font-semibold text-shogun-subdued hover:text-shogun-text hover:border-shogun-blue/40 transition-colors cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {status && (
        <div
          className={`flex items-center gap-2.5 p-3.5 rounded-xl border text-xs ${
            status.type === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-red-500/10 border-red-500/30 text-red-300'
          }`}
        >
          {status.type === 'success' ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
          <span>{status.text}</span>
        </div>
      )}

      {/* Root path configuration */}
      <form onSubmit={handleSavePath} className="shogun-card space-y-4">
        <div>
          <h3 className="text-sm font-bold text-shogun-text">AgentFlow Workspace Root</h3>
          <p className="text-xs text-shogun-subdued mt-1">
            All Workspace node paths and saved Output reports are strictly sandboxed inside this folder.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            value={workspacePath}
            onChange={(e) => setWorkspacePath(e.target.value)}
            placeholder="e.g. D:\AgentFlowData"
            className="flex-1 bg-[#050508] border border-shogun-border rounded-lg px-3.5 py-2.5 text-sm font-mono text-shogun-text focus:border-shogun-gold outline-none"
          />
          <button
            type="submit"
            disabled={saving || !workspacePath.trim()}
            className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-shogun-gold text-black font-bold text-xs uppercase tracking-wider hover:bg-shogun-gold/90 disabled:opacity-50 transition-all cursor-pointer"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : 'Set Local Folder'}
          </button>
        </div>

        {stats && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
            <div className="rounded-lg bg-[#050508] border border-shogun-border p-3">
              <div className="text-[10px] uppercase tracking-wider text-shogun-subdued font-bold">Active Path</div>
              <div className="text-xs font-mono text-shogun-gold truncate mt-1" title={savedPath}>{savedPath}</div>
            </div>
            <div className="rounded-lg bg-[#050508] border border-shogun-border p-3">
              <div className="text-[10px] uppercase tracking-wider text-shogun-subdued font-bold">Folders / Files</div>
              <div className="text-xs font-mono text-shogun-text mt-1">
                {stats.total_directories} folders · {stats.total_files} files
              </div>
            </div>
            <div className="rounded-lg bg-[#050508] border border-shogun-border p-3">
              <div className="text-[10px] uppercase tracking-wider text-shogun-subdued font-bold">Total Size</div>
              <div className="text-xs font-mono text-shogun-text mt-1">{stats.total_size_mb} MB</div>
            </div>
          </div>
        )}
      </form>

      {/* Subfolder setup + tree */}
      <div className="shogun-card space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-shogun-text">Workspace Folders</h3>
            <p className="text-xs text-shogun-subdued mt-0.5">
              Create subfolders (e.g. <code className="text-shogun-gold">input/reports</code>) and verify relative paths for your flows.
            </p>
          </div>
          <form onSubmit={handleCreateSubfolder} className="flex gap-2">
            <input
              type="text"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              placeholder="subfolder/name"
              className="bg-[#050508] border border-shogun-border rounded-lg px-3 py-1.5 text-xs font-mono text-shogun-text focus:border-shogun-blue outline-none"
            />
            <button
              type="submit"
              disabled={creatingFolder || !newFolderName.trim()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-shogun-blue/40 bg-shogun-blue/10 text-shogun-blue text-xs font-bold hover:bg-shogun-blue/20 disabled:opacity-50 cursor-pointer"
            >
              <FolderPlus className="w-3.5 h-3.5" />
              Create Folder
            </button>
          </form>
        </div>

        <div className="rounded-lg bg-[#050508] border border-shogun-border p-3 max-h-[380px] overflow-y-auto">
          {loading ? (
            <p className="text-xs text-shogun-subdued py-6 text-center">Loading folder structure...</p>
          ) : tree.length === 0 ? (
            <p className="text-xs text-shogun-subdued py-6 text-center">Workspace folder is empty.</p>
          ) : (
            renderTree(tree)
          )}
        </div>
      </div>
    </div>
  );
};
