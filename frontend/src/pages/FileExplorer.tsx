import { useState, useEffect, useCallback, useRef } from 'react';
import {
  FolderOpen, File, Folder, Trash2, Edit3, Save, X, RefreshCw,
  ChevronRight, ChevronDown, FileText, FileCode, FileSpreadsheet,
  Image, Archive, FolderPlus, FilePlus, HardDrive,
  AlertTriangle, Check, Search, Upload, Download
} from 'lucide-react';
import axios from 'axios';
import { cn } from '../lib/utils';
import { downloadAuthenticatedFile, extractBlobErrorMessage } from '../lib/fileDownload';

// ── Types ───────────────────────────────────────────────────────────

interface TreeNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  extension?: string;
  created_at?: string;
  modified_at?: string;
  children?: TreeNode[];
}

interface WorkspaceInfo {
  path: string;
  enabled: boolean;
  total_files: number;
  total_directories: number;
  total_size_bytes: number;
  total_size_mb: number;
}

// ── Helpers ─────────────────────────────────────────────────────────

function getFileIcon(ext: string) {
  const codeExts = ['ts', 'tsx', 'js', 'jsx', 'py', 'go', 'rs', 'java', 'c', 'cpp', 'h', 'cs', 'rb', 'php', 'sh', 'bat', 'ps1', 'yaml', 'yml', 'toml', 'ini', 'cfg'];
  const spreadExts = ['csv', 'xlsx', 'xls'];
  const imageExts = ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'bmp', 'ico'];
  const archiveExts = ['zip', 'tar', 'gz', 'rar', '7z', 'bz2'];
  const textExts = ['txt', 'md', 'log', 'json', 'xml', 'html', 'css'];

  if (codeExts.includes(ext)) return FileCode;
  if (spreadExts.includes(ext)) return FileSpreadsheet;
  if (imageExts.includes(ext)) return Image;
  if (archiveExts.includes(ext)) return Archive;
  if (textExts.includes(ext)) return FileText;
  return File;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTimestamp(value?: string): string {
  if (!value) return 'Date unavailable';
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value));
}

// ── Tree Item Component ─────────────────────────────────────────────

function TreeItem({
  node, depth, selectedPath, expandedPaths, onSelect, onToggle
}: {
  node: TreeNode;
  depth: number;
  selectedPath: string | null;
  expandedPaths: Set<string>;
  onSelect: (node: TreeNode) => void;
  onToggle: (path: string) => void;
}) {
  const isDir = node.type === 'directory';
  const isExpanded = expandedPaths.has(node.path);
  const isSelected = selectedPath === node.path;
  const Icon = isDir ? (isExpanded ? FolderOpen : Folder) : getFileIcon(node.extension || '');

  return (
    <div>
      <button
        onClick={() => { onSelect(node); if (isDir) onToggle(node.path); }}
        className={cn(
          "w-full flex items-center gap-1.5 px-2 py-1 text-sm rounded-md transition-all group",
          isSelected
            ? "bg-shogun-blue/15 text-shogun-blue"
            : "text-shogun-text hover:bg-shogun-card"
        )}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {isDir ? (
          <span className="w-3 h-3 flex items-center justify-center flex-shrink-0 text-shogun-subdued">
            {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          </span>
        ) : (
          <span className="w-3 h-3 flex-shrink-0" />
        )}
        <Icon className={cn("w-4 h-4 flex-shrink-0", isDir ? "text-shogun-gold" : "text-shogun-subdued")} />
        <span className="min-w-0 flex-1 text-left">
          <span className="block truncate">{node.name}</span>
          {!isDir && (
            <span
              className="block truncate text-[9px] leading-3 text-shogun-subdued/60 font-mono"
              title={`Created ${formatTimestamp(node.created_at)}`}
            >
              Created {formatTimestamp(node.created_at)}
            </span>
          )}
        </span>
        {!isDir && node.size !== undefined && (
          <span className="text-[10px] text-shogun-subdued/60 font-mono flex-shrink-0">{formatSize(node.size)}</span>
        )}
      </button>
      {isDir && isExpanded && node.children && (
        <div>
          {node.children.map(child => (
            <TreeItem
              key={child.path}
              node={child}
              depth={depth + 1}
              selectedPath={selectedPath}
              expandedPaths={expandedPaths}
              onSelect={onSelect}
              onToggle={onToggle}
            />
          ))}
          {node.children.length === 0 && (
            <div className="text-[11px] text-shogun-subdued/40 italic pl-4 py-1" style={{ paddingLeft: `${(depth + 1) * 16 + 20}px` }}>
              Empty folder
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main FileExplorer Component ─────────────────────────────────────

export const FileExplorer = () => {
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [info, setInfo] = useState<WorkspaceInfo | null>(null);
  const [selectedNode, setSelectedNode] = useState<TreeNode | null>(null);
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set(['']));
  const [fileContent, setFileContent] = useState<string>('');
  const [editContent, setEditContent] = useState<string>('');
  const [isEditing, setIsEditing] = useState(false);
  const [isBinary, setIsBinary] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [showNewDialog, setShowNewDialog] = useState<'file' | 'folder' | null>(null);
  const [newName, setNewName] = useState('');
  const [showRenameDialog, setShowRenameDialog] = useState(false);
  const [renameName, setRenameName] = useState('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const dragCounter = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Flash message ─────────────────────────────────────────────
  const flash = useCallback((type: 'success' | 'error', text: string) => {
    setStatusMsg({ type, text });
    setTimeout(() => setStatusMsg(null), 3000);
  }, []);

  const handleDownloadFile = async (node: TreeNode) => {
    setDownloading(true);
    try {
      const url = `/api/v1/workspace/download?path=${encodeURIComponent(node.path)}`;
      await downloadAuthenticatedFile(url, node.name);
    } catch (err: any) {
      const message = await extractBlobErrorMessage(err, 'Failed to download workspace file.');
      flash('error', message);
    } finally {
      setDownloading(false);
    }
  };

  // ── Fetch tree & info ─────────────────────────────────────────
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [treeRes, infoRes] = await Promise.all([
        axios.get('/api/v1/workspace/tree'),
        axios.get('/api/v1/workspace/info'),
      ]);
      if (treeRes.data?.success) setTree(treeRes.data.data.tree);
      if (infoRes.data?.success) setInfo(infoRes.data.data);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err.message;
      setError(detail);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // ── Select node and load content ──────────────────────────────
  const handleSelect = async (node: TreeNode) => {
    setSelectedNode(node);
    setIsEditing(false);
    setIsBinary(false);
    setShowDeleteConfirm(false);
    setShowRenameDialog(false);

    if (node.type === 'file') {
      try {
        const res = await axios.get('/api/v1/workspace/read', { params: { path: node.path } });
        if (res.data?.success) {
          setFileContent(res.data.data.content);
          setEditContent(res.data.data.content);
        }
      } catch (err: any) {
        const detail = err?.response?.data?.detail || 'Failed to read file';
        if (detail.toLowerCase().includes('binary')) {
          setIsBinary(true);
          setFileContent('');
        } else {
          setFileContent(`[Error] ${detail}`);
        }
        setEditContent('');
      }
    } else {
      setFileContent('');
      setEditContent('');
    }
  };

  // ── Toggle expand ─────────────────────────────────────────────
  const handleToggle = (path: string) => {
    setExpandedPaths(prev => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  // ── Save file ─────────────────────────────────────────────────
  const handleSave = async () => {
    if (!selectedNode || selectedNode.type !== 'file') return;
    setSaving(true);
    try {
      const res = await axios.post('/api/v1/workspace/write', {
        path: selectedNode.path,
        content: editContent,
      });
      if (res.data?.success) {
        setFileContent(editContent);
        setIsEditing(false);
        flash('success', `Saved ${selectedNode.name}`);
        fetchData();
      }
    } catch (err: any) {
      flash('error', err?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  // ── Create file/folder ────────────────────────────────────────
  const handleCreate = async () => {
    if (!newName.trim()) return;
    const basePath = selectedNode?.type === 'directory' ? selectedNode.path : '';
    const fullPath = basePath ? `${basePath}/${newName.trim()}` : newName.trim();

    try {
      if (showNewDialog === 'folder') {
        await axios.post('/api/v1/workspace/mkdir', { path: fullPath });
        flash('success', `Created folder: ${newName.trim()}`);
      } else {
        await axios.post('/api/v1/workspace/write', { path: fullPath, content: '' });
        flash('success', `Created file: ${newName.trim()}`);
      }
      setShowNewDialog(null);
      setNewName('');
      // Expand parent
      if (basePath) {
        setExpandedPaths(prev => new Set([...prev, basePath]));
      }
      fetchData();
    } catch (err: any) {
      flash('error', err?.response?.data?.detail || 'Creation failed');
    }
  };

  // ── Delete ────────────────────────────────────────────────────
  const handleDelete = async () => {
    if (!selectedNode) return;
    try {
      await axios.delete('/api/v1/workspace/delete', { params: { path: selectedNode.path } });
      flash('success', `Deleted: ${selectedNode.name}`);
      setSelectedNode(null);
      setFileContent('');
      setShowDeleteConfirm(false);
      fetchData();
    } catch (err: any) {
      flash('error', err?.response?.data?.detail || 'Delete failed');
    }
  };

  // ── Rename ────────────────────────────────────────────────────
  const handleRename = async () => {
    if (!selectedNode || !renameName.trim()) return;
    const parts = selectedNode.path.split('/');
    parts[parts.length - 1] = renameName.trim();
    const newPath = parts.join('/');

    try {
      await axios.post('/api/v1/workspace/rename', {
        old_path: selectedNode.path,
        new_path: newPath,
      });
      flash('success', `Renamed to: ${renameName.trim()}`);
      setShowRenameDialog(false);
      setSelectedNode(null);
      fetchData();
    } catch (err: any) {
      flash('error', err?.response?.data?.detail || 'Rename failed');
    }
  };

  // ── File Upload (drag & drop + button) ────────────────────────
  const handleUpload = async (files: FileList | File[]) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    const targetPath = selectedNode?.type === 'directory' ? selectedNode.path : '';

    try {
      const formData = new FormData();
      Array.from(files).forEach(f => formData.append('files', f));
      formData.append('path', targetPath);

      const res = await axios.post('/api/v1/workspace/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      if (res.data?.success) {
        const count = res.data.data.uploaded;
        flash('success', `Uploaded ${count} file${count !== 1 ? 's' : ''}`);
        if (targetPath) {
          setExpandedPaths(prev => new Set([...prev, targetPath]));
        }
        fetchData();
      }
    } catch (err: any) {
      flash('error', err?.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  // ── Drag & Drop handlers ──────────────────────────────────────
  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current += 1;
    if (e.dataTransfer.types.includes('Files')) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current -= 1;
    if (dragCounter.current === 0) {
      setIsDragging(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    dragCounter.current = 0;
    if (e.dataTransfer.files?.length) {
      handleUpload(e.dataTransfer.files);
    }
  };

  // ── Filter tree ───────────────────────────────────────────────
  const filterTree = (nodes: TreeNode[], query: string): TreeNode[] => {
    if (!query) return nodes;
    const q = query.toLowerCase();
    return nodes.reduce<TreeNode[]>((acc, node) => {
      if (node.name.toLowerCase().includes(q)) {
        acc.push(node);
      } else if (node.type === 'directory' && node.children) {
        const filtered = filterTree(node.children, query);
        if (filtered.length > 0) {
          acc.push({ ...node, children: filtered });
        }
      }
      return acc;
    }, []);
  };

  const displayTree = filterTree(tree, searchQuery);
  const workspaceRootNode: TreeNode = {
    name: 'Workspace',
    path: '',
    type: 'directory',
    children: displayTree,
  };

  // ── Error state ───────────────────────────────────────────────
  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-3">
          <AlertTriangle className="w-10 h-10 text-red-400 mx-auto" />
          <h3 className="text-lg font-bold text-shogun-text">Workspace Unavailable</h3>
          <p className="text-sm text-shogun-subdued max-w-md">{error}</p>
          <button onClick={fetchData}
            className="px-4 py-2 bg-shogun-blue/20 text-shogun-blue rounded-lg text-sm hover:bg-shogun-blue/30 transition-colors">
            <RefreshCw className="w-4 h-4 inline mr-1" /> Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className="h-full flex flex-col relative"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* Hidden file input for upload button */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={e => { if (e.target.files) { handleUpload(e.target.files); e.target.value = ''; } }}
      />

      {/* Drag overlay */}
      {isDragging && (
        <div className="absolute inset-0 z-50 bg-shogun-bg/90 backdrop-blur-sm flex items-center justify-center border-2 border-dashed border-shogun-blue rounded-xl transition-all">
          <div className="text-center space-y-3 animate-pulse">
            <Upload className="w-12 h-12 text-shogun-blue mx-auto" />
            <h3 className="text-lg font-bold text-shogun-blue">Drop files here</h3>
            <p className="text-sm text-shogun-subdued">
              {selectedNode?.type === 'directory'
                ? <>Upload into <span className="font-mono text-shogun-blue">{selectedNode.path}/</span></>
                : 'Upload to workspace root'
              }
            </p>
          </div>
        </div>
      )}
      {/* Status bar */}
      {statusMsg && (
        <div className={cn(
          "px-4 py-2 text-xs font-medium flex items-center gap-2 shrink-0 transition-all",
          statusMsg.type === 'success' ? "bg-emerald-500/10 text-emerald-400 border-b border-emerald-500/20" : "bg-red-500/10 text-red-400 border-b border-red-500/20"
        )}>
          {statusMsg.type === 'success' ? <Check className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
          {statusMsg.text}
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        {/* ── Sidebar: Tree ──────────────────────────────────── */}
        <div className="w-72 border-r border-shogun-border flex flex-col bg-shogun-bg/50 shrink-0">
          {/* Toolbar */}
          <div className="p-2 border-b border-shogun-border flex items-center gap-1 shrink-0">
            <button onClick={() => setShowNewDialog('file')} title="New File"
              className="p-1.5 rounded hover:bg-shogun-card text-shogun-subdued hover:text-shogun-blue transition-colors">
              <FilePlus className="w-4 h-4" />
            </button>
            <button onClick={() => setShowNewDialog('folder')} title="New Folder"
              className="p-1.5 rounded hover:bg-shogun-card text-shogun-subdued hover:text-shogun-gold transition-colors">
              <FolderPlus className="w-4 h-4" />
            </button>
            <button onClick={() => fileInputRef.current?.click()} title="Upload Files" disabled={uploading}
              className="p-1.5 rounded hover:bg-shogun-card text-shogun-subdued hover:text-emerald-400 transition-colors">
              <Upload className={cn("w-4 h-4", uploading && "animate-bounce")} />
            </button>
            {selectedNode && selectedNode.path !== '' && (
              <>
                <button onClick={() => { setRenameName(selectedNode.name); setShowRenameDialog(true); }} title="Rename"
                  className="p-1.5 rounded hover:bg-shogun-card text-shogun-subdued hover:text-shogun-text transition-colors">
                  <Edit3 className="w-4 h-4" />
                </button>
                <button onClick={() => setShowDeleteConfirm(true)} title="Delete"
                  className="p-1.5 rounded hover:bg-shogun-card text-shogun-subdued hover:text-red-400 transition-colors">
                  <Trash2 className="w-4 h-4" />
                </button>
              </>
            )}
            <div className="flex-1" />
            <button onClick={fetchData} title="Refresh"
              className="p-1.5 rounded hover:bg-shogun-card text-shogun-subdued hover:text-shogun-text transition-colors">
              <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
            </button>
          </div>

          {/* Search */}
          <div className="px-2 pt-2 shrink-0">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-shogun-subdued" />
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Search files..."
                className="w-full bg-shogun-card border border-shogun-border rounded-md pl-8 pr-3 py-1.5 text-xs text-shogun-text placeholder-shogun-subdued/40 focus:outline-none focus:border-shogun-blue/50"
              />
            </div>
          </div>

          {/* Tree */}
          <div className="flex-1 overflow-y-auto p-1 mt-1">
            {loading ? (
              <div className="flex items-center justify-center h-20">
                <RefreshCw className="w-5 h-5 animate-spin text-shogun-subdued" />
              </div>
            ) : (
              <TreeItem
                node={workspaceRootNode}
                depth={0}
                selectedPath={selectedNode?.path ?? null}
                expandedPaths={expandedPaths}
                onSelect={handleSelect}
                onToggle={handleToggle}
              />
            )}
          </div>

          {/* Workspace info footer */}
          {info && (
            <div className="p-2 border-t border-shogun-border text-[10px] text-shogun-subdued/60 space-y-0.5 shrink-0">
              <div className="flex items-center gap-1"><HardDrive className="w-3 h-3" /> {info.total_files} files · {info.total_directories} dirs · {info.total_size_mb} MB</div>
              <div className="font-mono truncate" title={info.path}>{info.path}</div>
            </div>
          )}
        </div>

        {/* ── Main: Content Area ─────────────────────────────── */}
        <div className="flex-1 flex flex-col min-w-0">
          {selectedNode ? (
            <>
              {/* File header */}
              <div className="px-4 py-2.5 border-b border-shogun-border flex items-center gap-3 shrink-0 bg-shogun-bg/30">
                {selectedNode.type === 'file' ? (
                  <>
                    {(() => { const Icon = getFileIcon(selectedNode.extension || ''); return <Icon className="w-4 h-4 text-shogun-subdued" />; })()}
                    <span className="text-sm font-medium text-shogun-text truncate">{selectedNode.path}</span>
                    {selectedNode.size !== undefined && (
                      <span className="text-[10px] text-shogun-subdued font-mono">{formatSize(selectedNode.size)}</span>
                    )}
                    <span
                      className="text-[10px] text-shogun-subdued font-mono"
                      title={selectedNode.modified_at
                        ? `Modified ${formatTimestamp(selectedNode.modified_at)}`
                        : undefined}
                    >
                      Created {formatTimestamp(selectedNode.created_at)}
                    </span>
                    <div className="flex-1" />
                    {!isBinary && (
                      isEditing ? (
                        <div className="flex items-center gap-1">
                          <button onClick={handleSave} disabled={saving}
                            className="px-3 py-1 bg-emerald-500/20 text-emerald-400 rounded text-xs font-medium hover:bg-emerald-500/30 transition-colors flex items-center gap-1">
                            <Save className="w-3 h-3" /> {saving ? 'Saving...' : 'Save'}
                          </button>
                          <button onClick={() => { setIsEditing(false); setEditContent(fileContent); }}
                            className="px-3 py-1 bg-shogun-card text-shogun-subdued rounded text-xs hover:text-shogun-text transition-colors">
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      ) : (
                        <button onClick={() => setIsEditing(true)}
                          className="px-3 py-1 bg-shogun-blue/10 text-shogun-blue rounded text-xs font-medium hover:bg-shogun-blue/20 transition-colors flex items-center gap-1">
                          <Edit3 className="w-3 h-3" /> Edit
                        </button>
                      )
                    )}
                    {isBinary && (
                      <button
                        type="button"
                        disabled={downloading}
                        onClick={() => handleDownloadFile(selectedNode)}
                        className="px-3 py-1 bg-shogun-blue/10 text-shogun-blue rounded text-xs font-medium hover:bg-shogun-blue/20 transition-colors flex items-center gap-1 disabled:opacity-50 cursor-pointer">
                        <Download className={cn("w-3 h-3", downloading && "animate-spin")} /> {downloading ? 'Downloading…' : 'Download'}
                      </button>
                    )}
                  </>
                ) : (
                  <>
                    <FolderOpen className="w-4 h-4 text-shogun-gold" />
                    <span className="text-sm font-medium text-shogun-text truncate">{selectedNode.path || 'Workspace'}/</span>
                    <span className="text-[10px] text-shogun-subdued">{selectedNode.children?.length || 0} items</span>
                  </>
                )}
              </div>

              {/* Content */}
              <div className="flex-1 overflow-auto">
                {selectedNode.type === 'file' ? (
                  isBinary ? (
                    /* Binary file info card */
                    <div className="flex-1 flex items-center justify-center p-8">
                      <div className="text-center space-y-4 max-w-sm">
                        {(() => { const Icon = getFileIcon(selectedNode.extension || ''); return <Icon className="w-16 h-16 text-shogun-subdued/30 mx-auto" />; })()}
                        <h3 className="text-lg font-bold text-shogun-text">{selectedNode.name}</h3>
                        <div className="space-y-2">
                          <div className="flex items-center justify-center gap-4 text-xs text-shogun-subdued">
                            <span className="bg-shogun-card px-2 py-1 rounded font-mono">.{selectedNode.extension}</span>
                            {selectedNode.size !== undefined && <span>{formatSize(selectedNode.size)}</span>}
                          </div>
                          <p className="text-xs text-shogun-subdued/60">Binary file — cannot be displayed as text.</p>
                        </div>
                        <button
                          type="button"
                          disabled={downloading}
                          onClick={() => handleDownloadFile(selectedNode)}
                          className="inline-flex items-center gap-2 px-4 py-2 bg-shogun-blue/15 text-shogun-blue rounded-lg text-sm font-medium hover:bg-shogun-blue/25 transition-colors disabled:opacity-50 cursor-pointer">
                          <Download className={cn("w-4 h-4", downloading && "animate-spin")} /> {downloading ? 'Downloading…' : 'Download File'}
                        </button>
                      </div>
                    </div>
                  ) : isEditing ? (
                    <textarea
                      value={editContent}
                      onChange={e => setEditContent(e.target.value)}
                      className="w-full h-full bg-transparent text-shogun-text text-sm font-mono p-4 resize-none focus:outline-none leading-relaxed"
                      spellCheck={false}
                    />
                  ) : (
                    <pre className="text-sm font-mono text-shogun-text p-4 whitespace-pre-wrap break-words leading-relaxed">
                      {fileContent || <span className="text-shogun-subdued italic">Empty file</span>}
                    </pre>
                  )
                ) : (
                  <div className="p-4 space-y-2">
                    <h3 className="text-sm font-bold text-shogun-text mb-3">Contents of {selectedNode.path ? selectedNode.name : 'Workspace'}/</h3>
                    {selectedNode.children && selectedNode.children.length > 0 ? (
                      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                        {selectedNode.children.map(child => {
                          const Icon = child.type === 'directory' ? Folder : getFileIcon(child.extension || '');
                          return (
                            <button
                              key={child.path}
                              onClick={() => handleSelect(child)}
                              className="flex items-start gap-2 p-3 rounded-lg bg-shogun-card hover:bg-shogun-card/80 border border-shogun-border hover:border-shogun-blue/30 transition-all text-left group"
                            >
                              <Icon className={cn("w-5 h-5 mt-0.5 flex-shrink-0", child.type === 'directory' ? "text-shogun-gold" : "text-shogun-subdued")} />
                              <div className="min-w-0 flex-1">
                                <div className="text-xs font-medium text-shogun-text truncate group-hover:text-shogun-blue transition-colors">{child.name}</div>
                                {child.type === 'file' && child.size !== undefined && (
                                  <div className="text-[10px] text-shogun-subdued">{formatSize(child.size)}</div>
                                )}
                                <div
                                  className="mt-1 text-[9px] leading-3 text-shogun-subdued/60 font-mono truncate"
                                  title={`Created ${formatTimestamp(child.created_at)}`}
                                >
                                  Created {formatTimestamp(child.created_at)}
                                </div>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="text-sm text-shogun-subdued italic">This folder is empty</p>
                    )}
                  </div>
                )}
              </div>
            </>
          ) : (
            /* Empty state */
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center space-y-3">
                <FolderOpen className="w-12 h-12 text-shogun-gold/30 mx-auto" />
                <h3 className="text-lg font-bold text-shogun-text">Agent Workspace</h3>
                <p className="text-sm text-shogun-subdued max-w-sm">
                  Select a file or folder from the tree to view or edit it.
                  This is the shared workspace used by the Shogun and all Samurai agents.
                </p>
                {info && (
                  <div className="text-xs text-shogun-subdued font-mono bg-shogun-card px-3 py-1.5 rounded-lg inline-block">
                    {info.path}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Dialogs ────────────────────────────────────────────── */}

      {/* New file/folder dialog */}
      {showNewDialog && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 backdrop-blur-sm">
          <div className="bg-shogun-bg border border-shogun-border rounded-xl p-5 w-96 shadow-2xl space-y-4">
            <h3 className="text-sm font-bold text-shogun-text flex items-center gap-2">
              {showNewDialog === 'folder' ? <FolderPlus className="w-4 h-4 text-shogun-gold" /> : <FilePlus className="w-4 h-4 text-shogun-blue" />}
              New {showNewDialog === 'folder' ? 'Folder' : 'File'}
            </h3>
            {selectedNode?.type === 'directory' && (
              <p className="text-[11px] text-shogun-subdued">Inside: <span className="font-mono text-shogun-text">{selectedNode.path}/</span></p>
            )}
            <input
              autoFocus
              type="text"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleCreate()}
              placeholder={showNewDialog === 'folder' ? 'Folder name' : 'filename.txt'}
              className="w-full bg-shogun-card border border-shogun-border rounded-lg px-3 py-2 text-sm text-shogun-text placeholder-shogun-subdued/40 focus:outline-none focus:border-shogun-blue/50"
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => { setShowNewDialog(null); setNewName(''); }}
                className="px-4 py-1.5 text-xs text-shogun-subdued hover:text-shogun-text transition-colors">Cancel</button>
              <button onClick={handleCreate} disabled={!newName.trim()}
                className="px-4 py-1.5 bg-shogun-blue/20 text-shogun-blue rounded-lg text-xs font-medium hover:bg-shogun-blue/30 transition-colors disabled:opacity-40">
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rename dialog */}
      {showRenameDialog && selectedNode && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 backdrop-blur-sm">
          <div className="bg-shogun-bg border border-shogun-border rounded-xl p-5 w-96 shadow-2xl space-y-4">
            <h3 className="text-sm font-bold text-shogun-text flex items-center gap-2">
              <Edit3 className="w-4 h-4 text-shogun-gold" /> Rename
            </h3>
            <p className="text-[11px] text-shogun-subdued font-mono">{selectedNode.path}</p>
            <input
              autoFocus
              type="text"
              value={renameName}
              onChange={e => setRenameName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleRename()}
              className="w-full bg-shogun-card border border-shogun-border rounded-lg px-3 py-2 text-sm text-shogun-text focus:outline-none focus:border-shogun-blue/50"
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowRenameDialog(false)}
                className="px-4 py-1.5 text-xs text-shogun-subdued hover:text-shogun-text transition-colors">Cancel</button>
              <button onClick={handleRename} disabled={!renameName.trim() || renameName === selectedNode.name}
                className="px-4 py-1.5 bg-shogun-gold/20 text-shogun-gold rounded-lg text-xs font-medium hover:bg-shogun-gold/30 transition-colors disabled:opacity-40">
                Rename
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirmation */}
      {showDeleteConfirm && selectedNode && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 backdrop-blur-sm">
          <div className="bg-shogun-bg border border-red-500/30 rounded-xl p-5 w-96 shadow-2xl space-y-4">
            <h3 className="text-sm font-bold text-red-400 flex items-center gap-2">
              <Trash2 className="w-4 h-4" /> Delete {selectedNode.type === 'directory' ? 'Folder' : 'File'}
            </h3>
            <p className="text-sm text-shogun-text">
              Are you sure you want to delete <span className="font-mono text-red-400">{selectedNode.name}</span>?
              {selectedNode.type === 'directory' && <span className="block text-xs text-shogun-subdued mt-1">This will delete the folder and all its contents.</span>}
            </p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowDeleteConfirm(false)}
                className="px-4 py-1.5 text-xs text-shogun-subdued hover:text-shogun-text transition-colors">Cancel</button>
              <button onClick={handleDelete}
                className="px-4 py-1.5 bg-red-500/20 text-red-400 rounded-lg text-xs font-medium hover:bg-red-500/30 transition-colors">
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
