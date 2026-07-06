import { createContext, useState, useEffect, useCallback, useContext, useRef, useMemo } from 'react';
import { createPortal } from 'react-dom';
import type { DragEvent } from 'react';
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  addEdge,
  Panel,
  Handle,
  Position,
  MarkerType,
  useReactFlow,
  ReactFlowProvider,
  BaseEdge,
  getSmoothStepPath,
  EdgeLabelRenderer,
} from '@xyflow/react';
import type {
  Connection,
  Node,
  Edge,
  NodeTypes,
  EdgeTypes,
  EdgeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Save,
  Plus,
  Trash2,
  Copy,
  Play,
  ChevronLeft,
  X,
  Users,
  Shield,
  GitBranch,
  LogIn,
  LogOut,
  Loader2,
  Zap,
  Clock,
  RefreshCw,
  Search,
  MoreVertical,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  History,
  StopCircle,
  Globe,
  Mail,
  Upload,
  FileText,
  Link,
  Calendar,
  Radio,
  Clipboard,
  FolderOpen,
  FileSpreadsheet,
  Sparkles,
  LayoutGrid,
  MessageSquare,
} from 'lucide-react';
import axios from 'axios';
import { cn } from '../lib/utils';


// ═══════════════════════════════════════════════════════════════
// TYPE DEFINITIONS
// ═══════════════════════════════════════════════════════════════

interface AgentFlowData {
  id: string;
  name: string;
  description: string | null;
  status: string;
  trigger_type: string;
  schedule_config: Record<string, any>;
  viewport: { x: number; y: number; zoom: number };
  nodes: FlowNodeData[];
  edges: FlowEdgeData[];
  created_at: string;
  updated_at: string;
}

interface FlowNodeData {
  id: string;
  flow_id: string;
  node_type: string;
  label: string;
  position_x: number;
  position_y: number;
  config: Record<string, any>;
}

interface FlowEdgeData {
  id: string;
  flow_id: string;
  source_node_id: string;
  target_node_id: string;
  source_handle: string | null;
  target_handle: string | null;
  label: string | null;
  edge_type: string;
  config: Record<string, any>;
}

interface FlowListItem {
  id: string;
  name: string;
  description: string | null;
  status: string;
  trigger_type: string;
  created_at: string;
  updated_at: string;
}

interface OutputResultRequest {
  runId: string | null;
  label: string;
  content: string;
}

interface OutputResultContextValue {
  view: (request: OutputResultRequest) => void;
  runId: string | null;
  nodeStates: Record<string, any>;
}

const OutputResultViewerContext = createContext<OutputResultContextValue | null>(null);

function parseRunTimestamp(value: string): Date {
  // SQLite returns UTC datetimes without a timezone suffix. JavaScript treats
  // those values as local time unless UTC is made explicit.
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
  return new Date(hasTimezone ? value : `${value}Z`);
}

function formatRunTimestamp(value?: string | null): string {
  return value ? parseRunTimestamp(value).toLocaleString() : '-';
}


// ═══════════════════════════════════════════════════════════════
// NODE PALETTE — card types available for dragging
// ═══════════════════════════════════════════════════════════════

const NODE_PALETTE = [
  { type: 'samurai',         label: 'Samurai',          icon: Users,     color: '#d4a017', desc: 'Task worker / sub-agent' },
  { type: 'shogun_approval', label: 'Shogun Approval',  icon: Shield,    color: '#4a8cc7', desc: 'Approval gate' },
  { type: 'logic',           label: 'Logic / Decision', icon: GitBranch, color: '#a78bfa', desc: 'Branching logic' },
  { type: 'input',           label: 'Input',            icon: LogIn,     color: '#22c55e', desc: 'Workflow start point' },
  { type: 'output',          label: 'Output',           icon: LogOut,    color: '#f97316', desc: 'Final delivery' },
  { type: 'mado_browser',    label: 'Mado Browser',     icon: Globe,     color: '#06b6d4', desc: 'Browser automation' },
  { type: 'email_send',      label: 'Email Send',       icon: Mail,      color: '#e879a8', desc: 'Send email via SMTP' },
  { type: 'channel_send',    label: 'Telegram / Teams', icon: MessageSquare, color: '#38bdf8', desc: 'Send an operator message' },
  { type: 'workspace',       label: 'Workspace',        icon: FolderOpen, color: '#f59e0b', desc: 'File operations' },
  { type: 'office',          label: 'Office',           icon: FileSpreadsheet, color: '#10b981', desc: 'Office documents' },
] as const;


// ═══════════════════════════════════════════════════════════════
// CUSTOM NODES
// ═══════════════════════════════════════════════════════════════

const nodeColors: Record<string, string> = {
  samurai: '#d4a017',
  shogun_approval: '#4a8cc7',
  logic: '#a78bfa',
  input: '#22c55e',
  output: '#f97316',
  mado_browser: '#06b6d4',
  email_send: '#e879a8',
  channel_send: '#38bdf8',
  workspace: '#f59e0b',
  office: '#10b981',
};

const nodeIcons: Record<string, React.ElementType> = {
  samurai: Users,
  shogun_approval: Shield,
  logic: GitBranch,
  input: LogIn,
  output: LogOut,
  mado_browser: Globe,
  email_send: Mail,
  channel_send: MessageSquare,
  workspace: FolderOpen,
  office: FileSpreadsheet,
};

function FlowNode({ id, data, selected, type }: { id: string; data: Record<string, any>; selected: boolean; type: string }) {
  const color = nodeColors[type] || '#d4a017';
  const Icon = nodeIcons[type] || Users;
  const config: Record<string, any> = data.config || {};
  const resultContext = useContext(OutputResultViewerContext);
  const authoritativeState = resultContext?.nodeStates?.[id];
  const executionStatus = authoritativeState?.status || data.execution_status;
  const executionOutput = authoritativeState?.output ?? data.execution_output ?? '';
  const executionRunId = resultContext?.runId || data.execution_run_id || null;
  const isRunning = executionStatus === 'running';

  return (
    <div
      className={cn(
        "relative min-w-[200px] max-w-[260px] rounded-lg border transition-all duration-200",
        selected
          ? "ring-2 ring-offset-1 ring-offset-[#0a0e1a] shadow-lg"
          : "shadow-md hover:shadow-lg"
      )}
      style={{
        background: isRunning
          ? `linear-gradient(135deg, ${color}0a 0%, #0e1225 42%, ${color}06 100%)`
          : '#0e1225',
        borderColor: isRunning ? color : selected ? color : '#1a2040',
        boxShadow: isRunning
          ? `inset 0 0 20px ${color}2e, 0 0 0 3px ${color}, 0 0 14px 5px ${color}f2, 0 0 38px 14px ${color}b8, 0 0 82px 28px ${color}73, 0 0 128px 42px ${color}3d`
          : selected
            ? `0 0 0 1px ${color}b3, 0 0 20px ${color}55`
            : undefined,
        filter: isRunning ? `saturate(1.08) brightness(1.03)` : undefined,
      }}
    >
      {/* Top accent bar */}
      <div
        className={cn("rounded-t-lg transition-all duration-300", isRunning ? "h-1.5" : "h-1")}
        style={{
          background: color,
          boxShadow: isRunning
            ? `0 0 10px 3px ${color}, 0 0 28px 10px ${color}d9, 0 0 52px 18px ${color}80`
            : undefined,
        }}
      />

      {/* Header */}
      <div className="px-3 py-2 flex items-center gap-2 border-b" style={{ borderColor: '#1a204060' }}>
        <div
          className="w-6 h-6 rounded flex items-center justify-center shrink-0"
          style={{ background: `${color}15`, border: `1px solid ${color}30` }}
        >
          <Icon className="w-3.5 h-3.5" style={{ color }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[11px] font-bold text-[#c8d0d8] truncate">{data.label}</div>
          <div className="text-[8px] font-bold uppercase tracking-widest" style={{ color: `${color}90` }}>
            {type.replace('_', ' ')}
          </div>
        </div>
      </div>

      {/* Body — type-specific preview */}
      <div className="px-3 py-2 space-y-1">
        {type === 'samurai' && (
          <>
            {config.task_description && (
              <p className="text-[9px] text-[#7a8899] line-clamp-2">{config.task_description}</p>
            )}
            {config.routing_profile_name && (
              <div className="flex items-center gap-1">
                <Zap className="w-2.5 h-2.5 text-[#d4a017]/70" />
                <span className="text-[8px] font-bold text-[#d4a017]/80">{config.routing_profile_name}</span>
              </div>
            )}
            {!config.task_description && !config.routing_profile_name && (
              <p className="text-[9px] text-[#7a8899]/50 italic">Configure task...</p>
            )}
          </>
        )}
        {type === 'shogun_approval' && (
          <>
            <div className="flex items-center gap-1">
              <Shield className="w-2.5 h-2.5 text-[#4a8cc7]/70" />
              <span className="text-[8px] font-bold text-[#4a8cc7]/80 uppercase">
                {config.approval_mode || 'manual'} approval
              </span>
            </div>
            {config.confidence_threshold && (
              <span className="text-[8px] text-[#7a8899]">
                Threshold: {config.confidence_threshold}%
              </span>
            )}
          </>
        )}
        {type === 'logic' && (
          <p className="text-[9px] text-[#a78bfa]/80 font-mono">
            {config.condition_expression || 'IF condition → ...'}
          </p>
        )}
        {type === 'input' && (
          <div className="flex items-center gap-1">
            <span className="text-[8px] font-bold text-[#22c55e]/80 uppercase">
              {config.input_type || 'manual'} trigger
            </span>
          </div>
        )}
        {type === 'output' && (
          <div className="flex flex-col gap-1.5 w-full">
            <div className="flex items-center gap-1">
              <span className="text-[8px] font-bold text-[#f97316]/80 uppercase">
                {config.output_type || 'artifact'}
              </span>
            </div>
            {executionStatus === 'completed' && (
              <button
                data-testid="view-output-result"
                onPointerDown={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                }}
                onPointerUp={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  resultContext?.view({
                    runId: executionRunId,
                    label: data.label || 'Output',
                    content: executionOutput,
                  });
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  // Keyboard-triggered clicks do not have a pointer event.
                  if (e.detail === 0) {
                    resultContext?.view({
                      runId: executionRunId,
                      label: data.label || 'Output',
                      content: executionOutput,
                    });
                  }
                }}
                type="button"
                className="nodrag nopan mt-1 w-full flex items-center justify-center gap-1.5 px-2 py-1 bg-[#22c55e]/10 hover:bg-[#22c55e]/20 text-[#22c55e] border border-[#22c55e]/20 rounded text-[9px] font-bold uppercase transition-colors"
              >
                <Search className="w-3 h-3" />
                View Result
              </button>
            )}
          </div>
        )}
        {type === 'mado_browser' && (
          <>
            <div className="flex items-center gap-1">
              <Globe className="w-2.5 h-2.5 text-[#06b6d4]/70" />
              <span className="text-[8px] font-bold text-[#06b6d4]/80 uppercase">
                {config.action || 'navigate'}
              </span>
            </div>
            {config.url && (
              <p className="text-[9px] text-[#7a8899] truncate">{config.url}</p>
            )}
          </>
        )}
        {type === 'email_send' && (
          <>
            <div className="flex items-center gap-1">
              <Mail className="w-2.5 h-2.5 text-[#e879a8]/70" />
              <span className="text-[8px] font-bold text-[#e879a8]/80 truncate">
                {config.to_address || 'No recipient'}
              </span>
            </div>
            {config.subject && (
              <p className="text-[9px] text-[#7a8899] truncate">{config.subject}</p>
            )}
          </>
        )}
        {type === 'channel_send' && (
          <>
            <div className="flex items-center gap-1">
              <MessageSquare className="w-2.5 h-2.5 text-[#38bdf8]/70" />
              <span className="text-[8px] font-bold text-[#38bdf8]/80 uppercase">
                {config.channel || 'both'}
              </span>
            </div>
            <p className="text-[9px] text-[#7a8899] line-clamp-2">
              {config.message_template || 'Uses predecessor output'}
            </p>
          </>
        )}
        {type === 'workspace' && (
          <>
            <div className="flex items-center gap-1">
              <FolderOpen className="w-2.5 h-2.5 text-[#f59e0b]/70" />
              <span className="text-[8px] font-bold text-[#f59e0b]/80 uppercase">
                {config.action || 'read_file'}
              </span>
            </div>
            {config.path && (
              <p className="text-[9px] text-[#7a8899] truncate">{config.path}</p>
            )}
          </>
        )}
        {type === 'office' && (
          <>
            <div className="flex items-center gap-1">
              <FileSpreadsheet className="w-2.5 h-2.5 text-[#10b981]/70" />
              <span className="text-[8px] font-bold text-[#10b981]/80 uppercase">
                {config.action || 'word_read'}
              </span>
            </div>
            {config.input_path && (
              <p className="text-[9px] text-[#7a8899] truncate">{config.input_path}</p>
            )}
          </>
        )}
      </div>

      {/* Handles */}
      {type !== 'input' && (
        <Handle
          type="target"
          position={Position.Left}
          className="!w-2.5 !h-2.5 !border-2 !rounded-full !bg-[#0a0e1a]"
          style={{ borderColor: color }}
        />
      )}
      {type !== 'output' && (
        <Handle
          type="source"
          position={Position.Right}
          className="!w-2.5 !h-2.5 !border-2 !rounded-full !bg-[#0a0e1a]"
          style={{ borderColor: color }}
        />
      )}
      {/* Logic nodes get extra handles for branches */}
      {type === 'logic' && (
        <>
          <Handle
            type="source"
            position={Position.Bottom}
            id="false"
            className="!w-2.5 !h-2.5 !border-2 !rounded-full !bg-[#0a0e1a]"
            style={{ borderColor: '#ef4444' }}
          />
        </>
      )}

      {/* Execution status overlay */}
      {executionStatus && executionStatus !== 'pending' && (
        <div className="absolute -top-1 -right-1 z-10">
          {executionStatus === 'running' && (
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center animate-pulse"
              style={{
                background: color,
                boxShadow: `0 0 10px ${color}, 0 0 22px ${color}cc`,
              }}
            >
              <Loader2 className="w-3 h-3 text-white animate-spin" />
            </div>
          )}
          {executionStatus === 'completed' && (
            <div className="w-5 h-5 rounded-full bg-[#22c55e] flex items-center justify-center shadow-[0_0_8px_rgba(34,197,94,0.4)]">
              <CheckCircle2 className="w-3 h-3 text-white" />
            </div>
          )}
          {executionStatus === 'failed' && (
            <div className="w-5 h-5 rounded-full bg-[#ef4444] flex items-center justify-center shadow-[0_0_8px_rgba(239,68,68,0.4)]">
              <XCircle className="w-3 h-3 text-white" />
            </div>
          )}
          {executionStatus === 'skipped' && (
            <div className="w-5 h-5 rounded-full bg-[#7a8899] flex items-center justify-center">
              <AlertTriangle className="w-3 h-3 text-white" />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Register custom node types
const nodeTypes: NodeTypes = {
  samurai: FlowNode,
  shogun_approval: FlowNode,
  logic: FlowNode,
  input: FlowNode,
  output: FlowNode,
  mado_browser: FlowNode,
  email_send: FlowNode,
  channel_send: FlowNode,
  workspace: FlowNode,
  office: FlowNode,
};


// ═══════════════════════════════════════════════════════════════
// CUSTOM EDGE
// ═══════════════════════════════════════════════════════════════

function CustomEdge({
  id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition,
  data, markerEnd, style, selected,
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX, sourceY, sourcePosition,
    targetX, targetY, targetPosition,
    borderRadius: 12,
  });

  const edgeColor = data?.edge_type === 'success' ? '#22c55e'
    : data?.edge_type === 'failure' ? '#ef4444'
    : data?.edge_type === 'conditional' ? '#a78bfa'
    : '#4a8cc7';

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          ...style,
          stroke: selected ? '#d4a017' : edgeColor,
          strokeWidth: selected ? 2.5 : 1.5,
          opacity: selected ? 1 : 0.7,
        }}
      />
      {data?.label && (
        <EdgeLabelRenderer>
          <div
            className="absolute text-[8px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border pointer-events-all"
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              background: '#0e1225',
              borderColor: edgeColor + '40',
              color: edgeColor,
            }}
          >
            {data.label as string}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const edgeTypes: EdgeTypes = {
  custom: CustomEdge,
};


// ═══════════════════════════════════════════════════════════════
// OFFICE NODE FIELDS — with folder picker
// ═══════════════════════════════════════════════════════════════

const READ_ACTIONS = ['excel_read', 'word_read', 'pptx_read'];

function OfficeNodeFields({ config, updateConfig }: { config: Record<string, any>; updateConfig: (k: string, v: any) => void }) {
  const [showPicker, setShowPicker] = useState(false);
  const [treeData, setTreeData] = useState<any[]>([]);
  const [loadingTree, setLoadingTree] = useState(false);
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());

  const action = config.action || 'word_read';
  const isReadAction = READ_ACTIONS.includes(action);
  const pathKey = isReadAction ? 'input_path' : 'output_path';
  const pickerLabel = isReadAction ? 'Source File' : 'Destination Folder';
  const fieldHint = isReadAction
    ? 'Select the file to read'
    : 'Where to save the output file';
  const fieldPlaceholder = isReadAction ? 'Input/document.docx' : 'Output/';

  // File extensions relevant to the current action
  const relevantExtensions = useMemo(() => {
    if (action.startsWith('excel')) return ['xlsx', 'xls', 'csv'];
    if (action.startsWith('word')) return ['docx', 'doc'];
    if (action.startsWith('pptx')) return ['pptx', 'ppt'];
    return [];
  }, [action]);

  const openPicker = async () => {
    setShowPicker(true);
    setLoadingTree(true);
    try {
      const res = await axios.get('/api/v1/workspace/tree');
      const tree = res.data?.data?.tree || res.data?.data || [];
      setTreeData(tree);
    } catch {
      setTreeData([]);
    }
    setLoadingTree(false);
  };

  const selectFile = (filePath: string) => {
    updateConfig(pathKey, filePath);
    setShowPicker(false);
  };

  const selectFolder = (folderPath: string) => {
    updateConfig(pathKey, folderPath + '/');
    setShowPicker(false);
  };

  const toggleDir = (path: string) => {
    setExpandedDirs(prev => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  // Get the icon color for a file based on whether it matches the action's extensions
  const getFileColor = (ext: string) => {
    if (relevantExtensions.includes(ext.toLowerCase())) return 'text-[#10b981]';
    return 'text-[#7a8899]/50';
  };

  // Recursive tree renderer
  const renderTreeNode = (node: any, depth: number = 0) => {
    if (node.type === 'directory') {
      const isExpanded = expandedDirs.has(node.path);
      const children = node.children || [];
      // Check if this directory contains any relevant files (recursively)
      const hasRelevantFiles = isReadAction ? _hasMatchingFiles(children, relevantExtensions) : true;

      return (
        <div key={node.path}>
          <button
            onClick={() => isReadAction ? toggleDir(node.path) : selectFolder(node.path)}
            className={cn(
              'w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-left transition-colors group',
              'hover:bg-[#10b981]/10',
              !hasRelevantFiles && isReadAction && 'opacity-40'
            )}
            style={{ paddingLeft: `${12 + depth * 16}px` }}
          >
            <FolderOpen className={cn('w-3.5 h-3.5', isExpanded ? 'text-[#10b981]' : 'text-[#f59e0b]/70')} />
            <span className="text-xs text-[#c8d0d8] flex-1 truncate">{node.name}</span>
            {isReadAction ? (
              <span className="text-[8px] text-[#7a8899] opacity-0 group-hover:opacity-100 transition-opacity">
                {isExpanded ? '▼' : '▶'}
              </span>
            ) : (
              <span className="ml-auto text-[9px] text-[#10b981] opacity-0 group-hover:opacity-100 transition-opacity">Select</span>
            )}
          </button>
          {isReadAction && isExpanded && children.map((child: any) => renderTreeNode(child, depth + 1))}
        </div>
      );
    }

    // File node — only show in read mode
    if (!isReadAction) return null;

    const ext = node.extension || '';
    const isRelevant = relevantExtensions.includes(ext.toLowerCase());
    const sizeStr = node.size ? `${(node.size / 1024).toFixed(1)} KB` : '';

    return (
      <button
        key={node.path}
        onClick={() => isRelevant ? selectFile(node.path) : undefined}
        className={cn(
          'w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-left transition-colors group',
          isRelevant ? 'hover:bg-[#10b981]/10 cursor-pointer' : 'opacity-30 cursor-default'
        )}
        style={{ paddingLeft: `${12 + depth * 16}px` }}
        disabled={!isRelevant}
      >
        <FileText className={cn('w-3.5 h-3.5', getFileColor(ext))} />
        <span className={cn('text-xs flex-1 truncate', isRelevant ? 'text-[#c8d0d8]' : 'text-[#7a8899]/60')}>
          {node.name}
        </span>
        {sizeStr && <span className="text-[8px] text-[#7a8899]/50 shrink-0">{sizeStr}</span>}
        {isRelevant && (
          <span className="text-[9px] text-[#10b981] opacity-0 group-hover:opacity-100 transition-opacity shrink-0">Select</span>
        )}
      </button>
    );
  };

  return (
    <>
      {/* Action dropdown */}
      <div className="space-y-1.5">
        <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Action</label>
        <select
          value={action}
          onChange={(e) => updateConfig('action', e.target.value)}
          className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#10b981] transition-colors outline-none"
        >
          <optgroup label="Excel">
            <option value="excel_read">Excel &mdash; Read</option>
            <option value="excel_create">Excel &mdash; Create</option>
            <option value="excel_write">Excel &mdash; Write</option>
          </optgroup>
          <optgroup label="Word">
            <option value="word_read">Word &mdash; Read</option>
            <option value="word_create">Word &mdash; Create</option>
            <option value="word_replace">Word &mdash; Replace Placeholders</option>
          </optgroup>
          <optgroup label="PowerPoint">
            <option value="pptx_read">PowerPoint &mdash; Read</option>
            <option value="pptx_replace">PowerPoint &mdash; Replace Placeholders</option>
          </optgroup>
        </select>
      </div>

      {/* Smart path field with picker */}
      <div className="space-y-1.5">
        <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest flex items-center gap-1">
          {isReadAction ? <FileText className="w-3 h-3 text-[#10b981]/60" /> : <FolderOpen className="w-3 h-3 text-[#10b981]/60" />}
          {pickerLabel}
        </label>
        <div className="flex gap-1.5">
          <input
            type="text"
            value={config[pathKey] || ''}
            onChange={(e) => updateConfig(pathKey, e.target.value)}
            className="flex-1 bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#10b981] transition-colors outline-none"
            placeholder={fieldPlaceholder}
          />
          <button
            onClick={openPicker}
            className="px-2.5 bg-[#10b981]/10 border border-[#10b981]/30 rounded-lg text-[#10b981] hover:bg-[#10b981]/20 transition-colors"
            title={isReadAction ? 'Browse workspace files' : 'Browse workspace folders'}
          >
            {isReadAction ? <FileText className="w-3.5 h-3.5" /> : <FolderOpen className="w-3.5 h-3.5" />}
          </button>
        </div>
        <p className="text-[8px] text-[#7a8899]/60">{fieldHint}</p>
      </div>

      {/* Excel sheet name */}
      {['excel_read', 'excel_create', 'excel_write'].includes(action) && (
        <div className="space-y-1.5">
          <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Sheet Name</label>
          <input
            type="text"
            value={config.sheet_name || ''}
            onChange={(e) => updateConfig('sheet_name', e.target.value)}
            className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#10b981] transition-colors outline-none"
            placeholder="Sheet1"
          />
        </div>
      )}

      {/* Word content template */}
      {action === 'word_create' && (
        <div className="space-y-1.5">
          <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Content Template</label>
          <textarea
            value={config.content_template || ''}
            onChange={(e) => updateConfig('content_template', e.target.value)}
            rows={3}
            className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#10b981] transition-colors outline-none resize-none"
            placeholder={'Use {{context}} for predecessor data.'}
          />
        </div>
      )}

      <div className="p-2.5 bg-[#10b981]/5 border border-[#10b981]/20 rounded-lg">
        <p className="text-[8px] text-[#10b981]/80">
          <strong>Office</strong> &mdash; All paths are relative to the workspace root.
          Requires Office App Mode enabled in the Katana.
        </p>
      </div>

      {/* File/Folder Picker Modal */}
      {showPicker && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 backdrop-blur-sm">
          <div className="bg-[#0a0e1a] border border-[#1a2040] rounded-xl p-5 w-[28rem] max-h-[70vh] shadow-2xl flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-[#c8d0d8] flex items-center gap-2">
                {isReadAction ? <FileText className="w-4 h-4 text-[#10b981]" /> : <FolderOpen className="w-4 h-4 text-[#10b981]" />}
                {isReadAction ? 'Select Source File' : 'Select Destination Folder'}
              </h3>
              <button
                onClick={() => setShowPicker(false)}
                className="p-1 hover:bg-[#1a2040] text-[#7a8899] hover:text-[#c8d0d8] rounded-lg transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {isReadAction && (
              <p className="text-[9px] text-[#7a8899] mb-3">
                Expand folders to find your file. Only <strong className="text-[#10b981]">{relevantExtensions.join(', ')}</strong> files are selectable.
              </p>
            )}

            <div className="flex-1 overflow-y-auto space-y-0.5 min-h-[200px]">
              {loadingTree ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-5 h-5 text-[#10b981] animate-spin" />
                </div>
              ) : treeData.length === 0 ? (
                <p className="text-xs text-[#7a8899] text-center py-8">No files found in workspace</p>
              ) : (
                <>
                  {!isReadAction && (
                    <button
                      onClick={() => selectFolder('')}
                      className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left hover:bg-[#10b981]/10 transition-colors group"
                    >
                      <FolderOpen className="w-4 h-4 text-[#10b981]" />
                      <span className="text-xs text-[#c8d0d8] font-medium">/ (workspace root)</span>
                      <span className="ml-auto text-[9px] text-[#10b981] opacity-0 group-hover:opacity-100 transition-opacity">Select</span>
                    </button>
                  )}
                  {treeData.map((node) => renderTreeNode(node, 0))}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

/** Check if a tree branch contains any files with matching extensions. */
function _hasMatchingFiles(children: any[], extensions: string[]): boolean {
  for (const child of children) {
    if (child.type === 'file' && extensions.includes((child.extension || '').toLowerCase())) {
      return true;
    }
    if (child.type === 'directory' && child.children && _hasMatchingFiles(child.children, extensions)) {
      return true;
    }
  }
  return false;
}


// ═══════════════════════════════════════════════════════════════
// NODE INSPECTOR PANEL
// ═══════════════════════════════════════════════════════════════

function NodeInspector({
  node,
  onUpdate,
  onClose,
  agents,
  routingProfiles,
  flowId,
}: {
  node: Node;
  onUpdate: (id: string, data: any) => void;
  onClose: () => void;
  agents: any[];
  routingProfiles: any[];
  flowId: string;
}) {
  const nodeType = node.type || 'samurai';
  const color = nodeColors[nodeType] || '#d4a017';
  const Icon = nodeIcons[nodeType] || Users;
  const config: Record<string, any> = (node.data as Record<string, any>)?.config || {};

  const updateConfig = (key: string, value: any) => {
    onUpdate(node.id, {
      ...node.data,
      config: { ...config, [key]: value },
    });
  };

  const updateLabel = (label: string) => {
    onUpdate(node.id, { ...node.data, label });
  };

  return (
    <div className="w-[420px] bg-[#050508] border-l border-[#1a2040] h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-[#1a2040] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{ background: `${color}15`, border: `1px solid ${color}30` }}
          >
            <Icon className="w-4 h-4" style={{ color }} />
          </div>
          <div>
            <h3 className="text-xs font-bold text-[#c8d0d8]">Node Properties</h3>
            <span className="text-[8px] font-bold uppercase tracking-widest" style={{ color }}>
              {nodeType.replace('_', ' ')}
            </span>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 hover:bg-[#1a2040] text-[#7a8899] hover:text-[#c8d0d8] rounded-lg transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Form */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Label */}
        <div className="space-y-1.5">
          <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Label</label>
          <input
            type="text"
            value={((node.data as Record<string, any>)?.label as string) || ''}
            onChange={(e) => updateLabel(e.target.value)}
            className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#4a8cc7] transition-colors outline-none"
          />
        </div>

        {/* Samurai-specific fields */}
        {nodeType === 'samurai' && (
          <>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest flex items-center gap-1">
                Linked Fleet Samurai <span className="text-[#d4a017]/70 font-normal normal-case tracking-normal">(Optional)</span>
              </label>
              <select
                value={config.agent_id || ''}
                onChange={(e) => updateConfig('agent_id', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#d4a017] transition-colors outline-none cursor-pointer"
              >
                <option value="">Use Ephemeral / Ad-Hoc Samurai</option>
                {agents.map((a: any) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
              <p className="text-[10px] text-[#7a8899] leading-tight">
                Leave unlinked to spawn a temporary Samurai that won't clutter your Fleet.
              </p>
            </div>

            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Task Description</label>
              <textarea
                value={config.task_description || ''}
                onChange={(e) => updateConfig('task_description', e.target.value)}
                rows={3}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#d4a017] transition-colors outline-none resize-y min-h-[60px]"
                placeholder="Describe what this Samurai should do..."
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Expected Output</label>
              <input
                type="text"
                value={config.expected_output || ''}
                onChange={(e) => updateConfig('expected_output', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#d4a017] transition-colors outline-none"
                placeholder="e.g., JSON report, markdown summary..."
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest flex items-center gap-1">
                <Zap className="w-3 h-3 text-[#d4a017]/70" /> Routing Profile
              </label>
              <select
                value={config.routing_profile_id || ''}
                onChange={(e) => updateConfig('routing_profile_id', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#d4a017] transition-colors outline-none cursor-pointer"
              >
                <option value="">System default</option>
                {routingProfiles.map((p: any) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Timeout (s)</label>
                <input
                  type="number"
                  value={config.timeout || 300}
                  onChange={(e) => updateConfig('timeout', parseInt(e.target.value))}
                  className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#d4a017] transition-colors outline-none"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Retries</label>
                <input
                  type="number"
                  value={config.retry_count || 0}
                  onChange={(e) => updateConfig('retry_count', parseInt(e.target.value))}
                  min={0}
                  max={5}
                  className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#d4a017] transition-colors outline-none"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">On Failure</label>
              <select
                value={config.failure_action || 'stop'}
                onChange={(e) => updateConfig('failure_action', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#d4a017] transition-colors outline-none cursor-pointer"
              >
                <option value="stop">Stop workflow</option>
                <option value="retry">Retry</option>
                <option value="skip">Skip and continue</option>
                <option value="escalate">Escalate to Shogun</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Context Injection</label>
              <textarea
                value={config.context_injection || ''}
                onChange={(e) => updateConfig('context_injection', e.target.value)}
                rows={2}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#d4a017] transition-colors outline-none resize-none"
                placeholder="Additional context to inject..."
              />
            </div>
          </>
        )}

        {/* Shogun Approval fields */}
        {nodeType === 'shogun_approval' && (
          <>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Approval Mode</label>
              <select
                value={config.approval_mode || 'manual'}
                onChange={(e) => updateConfig('approval_mode', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#4a8cc7] transition-colors outline-none cursor-pointer"
              >
                <option value="manual">Manual Human Approval</option>
                <option value="ai_assisted">AI-Assisted Approval</option>
                <option value="policy_based">Policy-Based Approval</option>
                <option value="confidence_threshold">Confidence Threshold</option>
              </select>
            </div>

            {config.approval_mode === 'confidence_threshold' && (
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">
                  Confidence Threshold (%)
                </label>
                <input
                  type="number"
                  value={config.confidence_threshold || 85}
                  onChange={(e) => updateConfig('confidence_threshold', parseInt(e.target.value))}
                  min={0}
                  max={100}
                  className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#4a8cc7] transition-colors outline-none"
                />
              </div>
            )}

            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Escalation Action</label>
              <select
                value={config.escalation_action || 'notify'}
                onChange={(e) => updateConfig('escalation_action', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#4a8cc7] transition-colors outline-none cursor-pointer"
              >
                <option value="notify">Notify operator</option>
                <option value="block">Block until manual review</option>
                <option value="reroute">Reroute for revision</option>
                <option value="stop">Stop workflow</option>
              </select>
            </div>
          </>
        )}

        {/* Logic/Decision fields */}
        {nodeType === 'logic' && (
          <>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Condition Expression</label>
              <textarea
                value={config.condition_expression || ''}
                onChange={(e) => updateConfig('condition_expression', e.target.value)}
                rows={3}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-[10px] text-[#a78bfa] font-mono focus:border-[#a78bfa] transition-colors outline-none resize-none"
                placeholder="e.g., confidence > 85%"
              />
            </div>
            <div className="p-2.5 bg-[#a78bfa]/5 border border-[#a78bfa]/20 rounded-lg">
              <p className="text-[8px] text-[#a78bfa]/80">
                <strong>Right handle →</strong> TRUE branch<br />
                <strong>Bottom handle ↓</strong> FALSE branch
              </p>
            </div>
          </>
        )}

        {/* Input fields */}
        {nodeType === 'input' && (
          <>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Input Type</label>
              <select
                value={config.input_type || 'manual'}
                onChange={(e) => updateConfig('input_type', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#22c55e] transition-colors outline-none cursor-pointer"
              >
                <option value="manual">Manual Input</option>
                <option value="document">Document Upload</option>
                <option value="api">API Trigger</option>
                <option value="scheduled">Scheduled Trigger</option>
                <option value="event">Event-Based Trigger</option>
                <option value="nexus">Nexus Task</option>
              </select>
            </div>

            {/* ── Scheduled Trigger ──────────────────────── */}
            {config.input_type === 'scheduled' && (
              <>
                <div className="space-y-1.5">
                  <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest flex items-center gap-1">
                    <Calendar className="w-3 h-3" /> Frequency
                  </label>
                  <select
                    value={config.schedule_frequency || 'nightly'}
                    onChange={(e) => updateConfig('schedule_frequency', e.target.value)}
                    className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#22c55e] transition-colors outline-none cursor-pointer"
                  >
                    <option value="hourly">Hourly</option>
                    <option value="nightly">Daily (Nightly)</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>

                {config.schedule_frequency !== 'hourly' && (
                  <div className="space-y-1.5">
                    <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest flex items-center gap-1">
                      <Clock className="w-3 h-3" /> Run Time
                    </label>
                    <input
                      type="time"
                      value={config.schedule_time || '07:00'}
                      onChange={(e) => updateConfig('schedule_time', e.target.value)}
                      className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#22c55e] transition-colors outline-none"
                    />
                  </div>
                )}

                {config.schedule_frequency === 'hourly' && (
                  <div className="space-y-1.5">
                    <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Minute Offset</label>
                    <input
                      type="number"
                      min={0}
                      max={59}
                      value={config.schedule_minute_offset ?? 0}
                      onChange={(e) => updateConfig('schedule_minute_offset', parseInt(e.target.value) || 0)}
                      className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#22c55e] transition-colors outline-none"
                      placeholder="0"
                    />
                    <p className="text-[8px] text-[#555]">Runs at this minute past every hour (0–59)</p>
                  </div>
                )}

                {config.schedule_frequency === 'weekly' && (
                  <div className="space-y-1.5">
                    <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Days of Week</label>
                    <div className="flex flex-wrap gap-1">
                      {['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'].map((day) => {
                        const days: string[] = config.schedule_days || ['mon', 'tue', 'wed', 'thu', 'fri'];
                        const active = days.includes(day);
                        return (
                          <button
                            key={day}
                            type="button"
                            onClick={() => {
                              const next = active ? days.filter((d: string) => d !== day) : [...days, day];
                              updateConfig('schedule_days', next.length ? next : [day]);
                            }}
                            className={cn(
                              "px-2 py-1 rounded text-[9px] font-bold uppercase tracking-wider transition-all cursor-pointer border",
                              active
                                ? "bg-[#22c55e]/15 border-[#22c55e]/40 text-[#22c55e]"
                                : "bg-[#0a0e1a] border-[#1a2040] text-[#555] hover:border-[#2a3060]"
                            )}
                          >
                            {day}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {config.schedule_frequency === 'monthly' && (
                  <div className="space-y-1.5">
                    <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Day of Month</label>
                    <input
                      type="number"
                      min={1}
                      max={28}
                      value={config.schedule_day || 1}
                      onChange={(e) => updateConfig('schedule_day', parseInt(e.target.value) || 1)}
                      className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#22c55e] transition-colors outline-none"
                    />
                    <p className="text-[8px] text-[#555]">Day 1–28 (avoids month-length issues)</p>
                  </div>
                )}

                <div className="bg-[#22c55e]/5 border border-[#22c55e]/20 rounded-lg p-2.5">
                  <p className="text-[9px] text-[#22c55e]/80 leading-relaxed">
                    <strong>Note:</strong> The flow must be <strong>Activated</strong> for the schedule to register with the job scheduler. Save → then Activate from the flow list.
                  </p>
                </div>
              </>
            )}

            {/* ── Document Upload ────────────────────────── */}
            {config.input_type === 'document' && (
              <>
                <div className="space-y-1.5">
                  <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest flex items-center gap-1">
                    <Upload className="w-3 h-3" /> Upload Document
                  </label>
                  <div
                    className={cn(
                      "border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition-all duration-200",
                      "hover:border-[#22c55e]/50 hover:bg-[#22c55e]/5",
                      config.uploaded_file
                        ? "border-[#22c55e]/30 bg-[#22c55e]/5"
                        : "border-[#1a2040] bg-[#0a0e1a]"
                    )}
                    onClick={() => {
                      const input = document.createElement('input');
                      input.type = 'file';
                      input.accept = '.pdf,.txt,.csv,.json,.md,.docx,.xlsx';
                      input.onchange = async (e: any) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        const formData = new FormData();
                        formData.append('file', file);
                        try {
                          const res = await axios.post(`/api/v1/agent-flows/${flowId}/upload`, formData);
                          const data = res.data?.data;
                          updateConfig('uploaded_file', {
                            filename: data?.filename || file.name,
                            size: file.size,
                            path: data?.path || '',
                          });
                        } catch {
                          updateConfig('uploaded_file', {
                            filename: file.name,
                            size: file.size,
                            path: '',
                            error: 'Upload failed',
                          });
                        }
                      };
                      input.click();
                    }}
                    onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
                    onDrop={async (e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      const file = e.dataTransfer.files?.[0];
                      if (!file) return;
                      const formData = new FormData();
                      formData.append('file', file);
                      try {
                        const res = await axios.post(`/api/v1/agent-flows/${flowId}/upload`, formData);
                        const data = res.data?.data;
                        updateConfig('uploaded_file', {
                          filename: data?.filename || file.name,
                          size: file.size,
                          path: data?.path || '',
                        });
                      } catch {
                        updateConfig('uploaded_file', {
                          filename: file.name,
                          size: file.size,
                          path: '',
                          error: 'Upload failed',
                        });
                      }
                    }}
                  >
                    {config.uploaded_file ? (
                      <div className="space-y-1">
                        <FileText className="w-6 h-6 mx-auto text-[#22c55e]" />
                        <p className="text-[10px] font-bold text-[#c8d0d8] truncate">{config.uploaded_file.filename}</p>
                        <p className="text-[8px] text-[#555]">
                          {(config.uploaded_file.size / 1024).toFixed(1)} KB
                        </p>
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); updateConfig('uploaded_file', null); }}
                          className="text-[8px] text-[#ef4444] hover:text-[#ef4444]/80 font-bold uppercase tracking-wider cursor-pointer"
                        >
                          Remove
                        </button>
                      </div>
                    ) : (
                      <div className="space-y-1.5 py-2">
                        <Upload className="w-6 h-6 mx-auto text-[#555]" />
                        <p className="text-[10px] text-[#7a8899] font-bold">
                          Drag & drop or click to upload
                        </p>
                        <p className="text-[8px] text-[#555]">
                          PDF, TXT, CSV, JSON, MD, DOCX, XLSX
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}

            {/* ── Manual Input ──────────────────────────── */}
            {(!config.input_type || config.input_type === 'manual') && (
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Initial Context</label>
                <textarea
                  value={config.manual_input || ''}
                  onChange={(e) => updateConfig('manual_input', e.target.value)}
                  rows={3}
                  className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#22c55e] transition-colors outline-none resize-y min-h-[60px]"
                  placeholder="Enter initial context or instructions for the flow..."
                />
                <p className="text-[8px] text-[#555]">This text is passed as input when the flow runs</p>
              </div>
            )}

            {/* ── API Trigger ───────────────────────────── */}
            {config.input_type === 'api' && (() => {
              const [toolsLoading, setToolsLoading] = useState(false);
              const [tools, setTools] = useState<{id: string; name: string; slug: string; base_url: string | null; connector_type: string; status: string}[]>([]);

              useEffect(() => {
                let cancelled = false;
                setToolsLoading(true);
                axios.get('/api/v1/tools').then((res) => {
                  if (!cancelled) setTools(res.data?.data || []);
                }).catch(() => {}).finally(() => { if (!cancelled) setToolsLoading(false); });
                return () => { cancelled = true; };
              }, []);

              const selectedTool = tools.find((t) => t.id === config.api_tool_id);

              return (
                <>
                  <div className="space-y-1.5">
                    <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest flex items-center gap-1">
                      <Zap className="w-3 h-3" /> API Source
                    </label>
                    <select
                      value={config.api_tool_id || ''}
                      onChange={(e) => {
                        const tool = tools.find((t) => t.id === e.target.value);
                        updateConfig('api_tool_id', e.target.value || null);
                        updateConfig('api_tool_name', tool?.name || null);
                        updateConfig('api_base_url', tool?.base_url || null);
                      }}
                      className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#22c55e] transition-colors outline-none cursor-pointer"
                    >
                      <option value="">— Webhook (direct POST) —</option>
                      {toolsLoading && <option disabled>Loading connectors...</option>}
                      {tools.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name} ({t.connector_type}){t.base_url ? ` · ${t.base_url}` : ''}
                        </option>
                      ))}
                    </select>
                    <p className="text-[8px] text-[#555]">
                      {config.api_tool_id
                        ? 'This flow triggers via the selected API connector'
                        : 'Select a connector or use the direct webhook URL below'}
                    </p>
                  </div>

                  {selectedTool && (
                    <div className="bg-[#06b6d4]/5 border border-[#06b6d4]/20 rounded-lg p-2.5 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] font-bold text-[#06b6d4]">{selectedTool.name}</span>
                        <span className={cn(
                          "text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded",
                          selectedTool.status === 'active' ? "text-green-400 bg-green-500/10" : "text-[#555] bg-[#0a0e1a]"
                        )}>{selectedTool.status}</span>
                      </div>
                      {selectedTool.base_url && (
                        <p className="text-[8px] text-[#555] font-mono truncate">{selectedTool.base_url}</p>
                      )}
                    </div>
                  )}

                  <div className="space-y-1.5">
                    <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest flex items-center gap-1">
                      <Link className="w-3 h-3" /> Webhook URL
                    </label>
                    <div className="flex gap-1">
                      <input
                        type="text"
                        readOnly
                        value={`${window.location.origin}/api/v1/agent-flows/${flowId}/runs`}
                        className="flex-1 bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-[10px] text-[#7a8899] font-mono outline-none select-all"
                      />
                      <button
                        type="button"
                        onClick={() => {
                          navigator.clipboard.writeText(`${window.location.origin}/api/v1/agent-flows/${flowId}/runs`);
                        }}
                        className="p-2 bg-[#0a0e1a] border border-[#1a2040] rounded-lg hover:border-[#22c55e]/40 transition-colors cursor-pointer"
                        title="Copy URL"
                      >
                        <Clipboard className="w-3 h-3 text-[#7a8899]" />
                      </button>
                    </div>
                  </div>
                  <div className="bg-[#22c55e]/5 border border-[#22c55e]/20 rounded-lg p-2.5 space-y-1.5">
                    <p className="text-[9px] text-[#22c55e]/80 leading-relaxed">
                      <strong>Usage:</strong> Send a <code className="bg-[#0a0e1a] px-1 py-0.5 rounded text-[8px]">POST</code> request with a JSON body to trigger this flow.
                    </p>
                    <pre className="text-[8px] text-[#555] font-mono bg-[#0a0e1a] p-2 rounded overflow-x-auto">
{`POST /api/v1/agent-flows/${flowId}/runs
Content-Type: application/json

{ "trigger_type": "api" }`}
                    </pre>
                  </div>
                </>
              );
            })()}

            {/* ── Event-Based Trigger ───────────────────── */}
            {config.input_type === 'event' && (
              <>
                <div className="space-y-1.5">
                  <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest flex items-center gap-1">
                    <Radio className="w-3 h-3" /> Event Source
                  </label>
                  <select
                    value={config.event_source || 'email'}
                    onChange={(e) => updateConfig('event_source', e.target.value)}
                    className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#22c55e] transition-colors outline-none cursor-pointer"
                  >
                    <option value="email">Email Received</option>
                    <option value="bushido">Bushido Schedule</option>
                    <option value="system">System Event</option>
                    <option value="custom">Custom Event</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Event Filter</label>
                  <input
                    type="text"
                    value={config.event_filter || ''}
                    onChange={(e) => updateConfig('event_filter', e.target.value)}
                    className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#22c55e] transition-colors outline-none"
                    placeholder={
                      config.event_source === 'email' ? 'from:*@client.com' :
                      config.event_source === 'system' ? 'event_type:agent.deployed' :
                      'filter expression...'
                    }
                  />
                  <p className="text-[8px] text-[#555]">Optional filter to narrow which events trigger this flow</p>
                </div>
                <div className="bg-[#22c55e]/5 border border-[#22c55e]/20 rounded-lg p-2.5 space-y-1">
                  <p className="text-[9px] text-[#22c55e]/80 leading-relaxed">
                    <strong>How it works:</strong> When a matching event is captured by the Shogun Event Logger, this flow will be triggered automatically.
                  </p>
                  <p className="text-[8px] text-[#555] leading-relaxed">
                    Events are emitted by all subsystems — email sync, agent actions, Bushido schedules, browser automation, and system heartbeats.
                  </p>
                </div>
              </>
            )}

            {/* ── Nexus Task ────────────────────────────── */}
            {config.input_type === 'nexus' && (() => {
              // Load workspaces on mount if not cached
              const [wsLoading, setWsLoading] = useState(false);
              const [workspaces, setWorkspaces] = useState<{id: string; name: string; topic: string | null}[]>([]);

              useEffect(() => {
                let cancelled = false;
                setWsLoading(true);
                axios.get('/api/v1/workspaces').then((res) => {
                  if (!cancelled) setWorkspaces(res.data?.data || []);
                }).catch(() => {}).finally(() => { if (!cancelled) setWsLoading(false); });
                return () => { cancelled = true; };
              }, []);

              return (
                <>
                  <div className="space-y-1.5">
                    <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest flex items-center gap-1">
                      <Zap className="w-3 h-3" /> Nexus Workspace
                    </label>
                    <select
                      value={config.nexus_workspace_id || ''}
                      onChange={(e) => updateConfig('nexus_workspace_id', e.target.value)}
                      className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#22c55e] transition-colors outline-none cursor-pointer"
                    >
                      <option value="">— Select workspace —</option>
                      {wsLoading && <option disabled>Loading...</option>}
                      {workspaces.map((ws) => (
                        <option key={ws.id} value={ws.id}>
                          {ws.name}{ws.topic ? ` (${ws.topic})` : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Trigger on Message Type</label>
                    <select
                      value={config.nexus_message_type || 'task'}
                      onChange={(e) => updateConfig('nexus_message_type', e.target.value)}
                      className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#22c55e] transition-colors outline-none cursor-pointer"
                    >
                      <option value="task">Task messages</option>
                      <option value="proposal">Proposals</option>
                      <option value="signal">Signals / Alerts</option>
                      <option value="any">Any message</option>
                    </select>
                    <p className="text-[8px] text-[#555]">This flow triggers when a matching message arrives in the workspace</p>
                  </div>
                  <div className="bg-[#22c55e]/5 border border-[#22c55e]/20 rounded-lg p-2.5 space-y-1">
                    <p className="text-[9px] text-[#22c55e]/80 leading-relaxed">
                      <strong>How it works:</strong> When a <code className="bg-[#0a0e1a] px-1 py-0.5 rounded text-[8px]">{config.nexus_message_type || 'task'}</code> message arrives in the linked workspace, the message content is passed as input to this flow.
                    </p>
                  </div>
                </>
              );
            })()}

            {/* Description — always shown */}
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Description</label>
              <textarea
                value={config.description || ''}
                onChange={(e) => updateConfig('description', e.target.value)}
                rows={2}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#22c55e] transition-colors outline-none resize-y min-h-[44px]"
                placeholder="Describe the input..."
              />
            </div>
          </>
        )}

        {/* Output fields */}
        {nodeType === 'output' && (
          <>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Output Type</label>
              <select
                value={config.output_type || 'artifact'}
                onChange={(e) => updateConfig('output_type', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#f97316] transition-colors outline-none cursor-pointer"
              >
                <option value="artifact">Artifact / Report</option>
                <option value="export">Export File</option>
                <option value="api">API Response</option>
                <option value="notification">Notification</option>
                <option value="memory">Store in Memory</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Format</label>
              <select
                value={config.format || 'markdown'}
                onChange={(e) => updateConfig('format', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#f97316] transition-colors outline-none cursor-pointer"
              >
                <option value="markdown">Markdown</option>
                <option value="json">JSON</option>
                <option value="html">HTML</option>
                <option value="plain">Plain Text</option>
              </select>
            </div>
          </>
        )}

        {/* Mado Browser fields */}
        {nodeType === 'mado_browser' && (
          <>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Action</label>
              <select
                value={config.action || 'navigate'}
                onChange={(e) => updateConfig('action', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#06b6d4] transition-colors outline-none cursor-pointer"
              >
                <option value="navigate">Navigate to URL</option>
                <option value="extract_content">Extract Content</option>
                <option value="screenshot">Take Screenshot</option>
                <option value="fill_form">Fill Form</option>
                <option value="click">Click Element</option>
                <option value="execute_js">Execute JavaScript</option>
                <option value="wait_for">Wait for Element</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">URL</label>
              <input
                type="text"
                value={config.url || ''}
                onChange={(e) => updateConfig('url', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#06b6d4] transition-colors outline-none"
                placeholder="https://example.com"
              />
            </div>

            {/* Smart selector — presets + natural language + advanced raw */}
            {(() => {
              const EXTRACT_PRESETS: { value: string; label: string; selector: string; desc: string }[] = [
                { value: 'headlines',    label: '📰 All Headlines',       selector: 'h1, h2, h3, h4, article h2, article h3',         desc: 'Grabs all headline text from the page' },
                { value: 'links',        label: '🔗 All Links',           selector: 'a[href]',                                        desc: 'Extracts every link on the page with its URL' },
                { value: 'article',      label: '📄 Article Content',     selector: 'article, [role="article"], .post-content, .entry-content, .article-body, main', desc: 'Main article text and body content' },
                { value: 'news_cards',   label: '🗞️ News Cards',          selector: 'article a, [data-n-tid] a, c-wiz article, [jslog] h3, [jslog] h4', desc: 'News feed cards (Google News, news aggregators)' },
                { value: 'tables',       label: '📊 Tables & Data',       selector: 'table, [role="table"], .data-table',             desc: 'Structured tables and data grids' },
                { value: 'images',       label: '🖼️ Images',              selector: 'img[src], picture source',                       desc: 'All images with their source URLs' },
                { value: 'lists',        label: '📋 Lists',               selector: 'ul, ol, dl, [role="list"]',                      desc: 'Bullet points, numbered lists, and definition lists' },
                { value: 'prices',       label: '💰 Prices & Products',   selector: '[class*="price"], [data-price], .product-card, .product-title', desc: 'Product names, prices, and e-commerce data' },
                { value: 'full_page',    label: '📜 Full Page Text',      selector: 'body',                                           desc: 'Everything visible on the page' },
                { value: 'custom',       label: '⚙️ Custom Selector',     selector: '',                                               desc: 'Write your own CSS selector' },
              ];

              // Use config.selector_preset to track selection; fall back to matching
              const presetValue = config.selector_preset || EXTRACT_PRESETS.find(p => p.selector === config.selector)?.value || (config.selector ? 'custom' : '');
              const showAdvanced = config.show_advanced_selector || presetValue === 'custom';
              const currentPreset = EXTRACT_PRESETS.find(p => p.value === presetValue);

              // Batched config update — sets multiple keys in one call
              const updateMultiConfig = (updates: Record<string, any>) => {
                onUpdate(node.id, {
                  ...node.data,
                  config: { ...config, ...updates },
                });
              };

              return (
                <>
                  <div className="space-y-1.5">
                    <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">What to Extract</label>
                    <select
                      value={presetValue}
                      onChange={(e) => {
                        const preset = EXTRACT_PRESETS.find(p => p.value === e.target.value);
                        if (preset && preset.value !== 'custom') {
                          updateMultiConfig({
                            selector: preset.selector,
                            selector_preset: preset.value,
                            show_advanced_selector: false,
                          });
                        } else {
                          updateMultiConfig({
                            selector_preset: 'custom',
                            show_advanced_selector: true,
                          });
                        }
                      }}
                      className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#06b6d4] transition-colors outline-none cursor-pointer"
                    >
                      <option value="">— Choose what to extract —</option>
                      {EXTRACT_PRESETS.map(p => (
                        <option key={p.value} value={p.value}>{p.label}</option>
                      ))}
                    </select>
                    {currentPreset && presetValue !== 'custom' && (
                      <p className="text-[8px] text-[#06b6d4]/70">{currentPreset.desc}</p>
                    )}
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Describe What You Need</label>
                    <textarea
                      value={config.extract_hint || ''}
                      onChange={(e) => updateConfig('extract_hint', e.target.value)}
                      rows={2}
                      className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#06b6d4] transition-colors outline-none resize-y min-h-[40px]"
                      placeholder='e.g. "Get all article titles and their links" or "Find product prices"'
                    />
                    <p className="text-[8px] text-[#555]">Optional — helps the AI understand what to look for in the extracted content</p>
                  </div>

                  {/* Advanced toggle */}
                  <button
                    type="button"
                    onClick={() => updateConfig('show_advanced_selector', !showAdvanced)}
                    className="flex items-center gap-1.5 text-[8px] font-bold text-[#555] hover:text-[#7a8899] uppercase tracking-widest transition-colors cursor-pointer"
                  >
                    <span className="transition-transform" style={{ transform: showAdvanced ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
                    Advanced: CSS Selector
                  </button>

                  {showAdvanced && (
                    <div className="space-y-1.5">
                      <input
                        type="text"
                        value={config.selector || ''}
                        onChange={(e) => {
                          updateMultiConfig({
                            selector: e.target.value,
                            selector_preset: 'custom',
                          });
                        }}
                        className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-[10px] text-[#06b6d4] font-mono focus:border-[#06b6d4] transition-colors outline-none"
                        placeholder="e.g., .main-content, #article, table"
                      />
                      <p className="text-[8px] text-[#555]">Raw CSS selector — for power users who know the page structure</p>
                    </div>
                  )}
                </>
              );
            })()}

            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Session Name</label>
              <input
                type="text"
                value={config.session_name || 'flow_browser'}
                onChange={(e) => updateConfig('session_name', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#06b6d4] transition-colors outline-none"
                placeholder="flow_browser"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Browser Mode</label>
              <select
                value={config.browser_mode || 'headless'}
                onChange={(e) => updateConfig('browser_mode', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#06b6d4] transition-colors outline-none cursor-pointer"
              >
                <option value="headless">Headless</option>
                <option value="visible">Visible</option>
              </select>
            </div>

            {config.action === 'extract_content' && (
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Extract Type</label>
                <select
                  value={config.extract_type || 'text'}
                  onChange={(e) => updateConfig('extract_type', e.target.value)}
                  className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#06b6d4] transition-colors outline-none cursor-pointer"
                >
                  <option value="text">Text</option>
                  <option value="html">HTML</option>
                  <option value="inner_text">Inner Text</option>
                </select>
              </div>
            )}

            {config.action === 'execute_js' && (
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">JavaScript</label>
                <textarea
                  value={config.script || ''}
                  onChange={(e) => updateConfig('script', e.target.value)}
                  rows={4}
                  className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-[10px] text-[#06b6d4] font-mono focus:border-[#06b6d4] transition-colors outline-none resize-none"
                  placeholder="document.title"
                />
              </div>
            )}

            {config.action === 'wait_for' && (
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Timeout (ms)</label>
                <input
                  type="number"
                  value={config.timeout || 10000}
                  onChange={(e) => updateConfig('timeout', parseInt(e.target.value))}
                  className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#06b6d4] transition-colors outline-none"
                />
              </div>
            )}

            <div className="p-2.5 bg-[#06b6d4]/5 border border-[#06b6d4]/20 rounded-lg">
              <p className="text-[8px] text-[#06b6d4]/80">
                <strong>Mado 窓</strong> — Browser actions are governed by the Torii security posture.
                Domain allowlists and session limits apply.
              </p>
            </div>
          </>
        )}

        {/* Email Send fields */}
        {nodeType === 'email_send' && (
          <>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">To Address</label>
              <input
                type="text"
                value={config.to_address || ''}
                onChange={(e) => updateConfig('to_address', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#e879a8] transition-colors outline-none"
                placeholder="recipient@example.com"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">CC Address</label>
              <input
                type="text"
                value={config.cc_address || ''}
                onChange={(e) => updateConfig('cc_address', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#e879a8] transition-colors outline-none"
                placeholder="cc@example.com"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">BCC Address</label>
              <input
                type="text"
                value={config.bcc_address || ''}
                onChange={(e) => updateConfig('bcc_address', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#e879a8] transition-colors outline-none"
                placeholder="bcc@example.com"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Subject</label>
              <input
                type="text"
                value={config.subject || ''}
                onChange={(e) => updateConfig('subject', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#e879a8] transition-colors outline-none"
                placeholder="Email subject line..."
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Body Template</label>
              <textarea
                value={config.body_template || ''}
                onChange={(e) => updateConfig('body_template', e.target.value)}
                rows={4}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#e879a8] transition-colors outline-none resize-none"
                placeholder="Leave empty to use predecessor output as body. Use {{context}} to inject predecessor output into a template."
              />
            </div>

            <div className="p-2.5 bg-[#e879a8]/5 border border-[#e879a8]/20 rounded-lg">
              <p className="text-[8px] text-[#e879a8]/80">
                <strong>Mail ✉</strong> — Sends via the SMTP account configured in the Mail page.
                Requires <code className="text-[#e879a8]">perm_send_mail</code> to be enabled.
              </p>
            </div>
          </>
        )}

        {/* Workspace fields */}
        {nodeType === 'channel_send' && (
          <>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Channel</label>
              <select
                value={config.channel || 'both'}
                onChange={(e) => updateConfig('channel', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#38bdf8] transition-colors outline-none"
              >
                <option value="both">Telegram and Teams</option>
                <option value="telegram">Telegram</option>
                <option value="teams">Microsoft Teams</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Message Template</label>
              <textarea
                value={config.message_template || ''}
                onChange={(e) => updateConfig('message_template', e.target.value)}
                rows={4}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#38bdf8] transition-colors outline-none resize-none"
                placeholder="Leave empty to send the predecessor output, or use {{context}} inside a message."
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Telegram Chat IDs (optional)</label>
              <input
                type="text"
                value={(config.telegram_chat_ids || []).join(', ')}
                onChange={(e) => updateConfig('telegram_chat_ids', e.target.value.split(',').map(v => v.trim()).filter(Boolean))}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#38bdf8] transition-colors outline-none"
                placeholder="Uses configured allowed chats when empty"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Teams Conversation IDs (optional)</label>
              <input
                type="text"
                value={(config.teams_conversation_ids || []).join(', ')}
                onChange={(e) => updateConfig('teams_conversation_ids', e.target.value.split(',').map(v => v.trim()).filter(Boolean))}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#38bdf8] transition-colors outline-none"
                placeholder="Uses notification routes or known conversations when empty"
              />
            </div>
          </>
        )}

        {/* Workspace fields */}
        {nodeType === 'workspace' && (
          <>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Action</label>
              <select
                value={config.action || 'read_file'}
                onChange={(e) => updateConfig('action', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#f59e0b] transition-colors outline-none"
              >
                <option value="read_file">Read File</option>
                <option value="write_file">Write File</option>
                <option value="list_files">List Files</option>
                <option value="mkdir">Create Directory</option>
                <option value="delete">Delete</option>
                <option value="copy">Copy</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Path</label>
              <input
                type="text"
                value={config.path || ''}
                onChange={(e) => updateConfig('path', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#f59e0b] transition-colors outline-none"
                placeholder="Input/myfile.txt (relative to workspace)"
              />
            </div>

            {config.action === 'copy' && (
              <>
                <div className="space-y-1.5">
                  <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Source Path</label>
                  <input
                    type="text"
                    value={config.source_path || ''}
                    onChange={(e) => updateConfig('source_path', e.target.value)}
                    className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#f59e0b] transition-colors outline-none"
                    placeholder="Input/source.txt"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Destination Path</label>
                  <input
                    type="text"
                    value={config.dest_path || ''}
                    onChange={(e) => updateConfig('dest_path', e.target.value)}
                    className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#f59e0b] transition-colors outline-none"
                    placeholder="Output/dest.txt"
                  />
                </div>
              </>
            )}

            {config.action === 'write_file' && (
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Content Template</label>
                <textarea
                  value={config.content_template || ''}
                  onChange={(e) => updateConfig('content_template', e.target.value)}
                  rows={3}
                  className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#f59e0b] transition-colors outline-none resize-none"
                  placeholder='Leave empty to write predecessor output. Use {{context}} for predecessor data.'
                />
              </div>
            )}

            <div className="p-2.5 bg-[#f59e0b]/5 border border-[#f59e0b]/20 rounded-lg">
              <p className="text-[8px] text-[#f59e0b]/80">
                <strong>Workspace</strong> &mdash; All paths are relative to the agent workspace folder.
                Governed by the Torii security posture.
              </p>
            </div>
          </>
        )}

        {/* Office fields */}
        {nodeType === 'office' && (
          <OfficeNodeFields config={config} updateConfig={updateConfig} />
        )}
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════
// MAIN CANVAS COMPONENT (wrapped in ReactFlowProvider externally)
// ═══════════════════════════════════════════════════════════════

function AgentFlowCanvas({
  flow,
  onBack,
  onFlowUpdate: _onFlowUpdate,
  agents,
  routingProfiles,
}: {
  flow: AgentFlowData;
  onBack: () => void;
  onFlowUpdate: () => void;
  agents: any[];
  routingProfiles: any[];
}) {
  void _onFlowUpdate; // reserved for Phase 2 execution engine
  const reactFlowInstance = useReactFlow();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  // Convert backend data to React Flow format
  const initialNodes: Node[] = useMemo(() =>
    (flow.nodes || []).map((n) => ({
      id: n.id,
      type: n.node_type,
      position: { x: n.position_x, y: n.position_y },
      data: { label: n.label, config: n.config },
    })),
    [flow.id]
  );

  const initialEdges: Edge[] = useMemo(() =>
    (flow.edges || []).map((e) => ({
      id: e.id,
      source: e.source_node_id,
      target: e.target_node_id,
      sourceHandle: e.source_handle,
      targetHandle: e.target_handle,
      type: 'custom',
      data: { label: e.label, edge_type: e.edge_type },
      markerEnd: { type: MarkerType.ArrowClosed, color: '#4a8cc7', width: 16, height: 16 },
    })),
    [flow.id]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [flowName, setFlowName] = useState(flow.name);
  const [editingName, setEditingName] = useState(false);

  // ── Execution state ──────────────────────────────────────
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState<string | null>(null);
  const [nodeStates, setNodeStates] = useState<Record<string, any>>({});
  const [displayedRunId, setDisplayedRunId] = useState<string | null>(null);
  const [executing, setExecuting] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [runHistory, setRunHistory] = useState<any[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRunDetails, setSelectedRunDetails] = useState<any | null>(null);
  const [loadingRunDetails, setLoadingRunDetails] = useState(false);
  const [deletingRunId, setDeletingRunId] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadRunResult = useCallback(async (
    runId: string,
    fallback?: { label: string; content: string },
  ) => {
    setSelectedRunId(runId);
    setLoadingRunDetails(true);
    try {
      const resp = await axios.get(`/api/v1/agent-flows/runs/${runId}`);
      const run = resp.data?.data || null;
      setSelectedRunDetails(run);
      return run;
    } catch (err) {
      console.error(err);
      setSelectedRunDetails(fallback ? {
        status: 'completed',
        trigger_type: 'manual',
        result_summary: { [fallback.label]: fallback.content },
      } : null);
      return null;
    } finally {
      setLoadingRunDetails(false);
    }
  }, []);

  const handleViewOutputResult = useCallback((request: OutputResultRequest) => {
    if (request.runId) {
      void loadRunResult(request.runId, {
        label: request.label,
        content: request.content,
      });
      return;
    }
    setSelectedRunId('node-output');
    setSelectedRunDetails({
      status: 'completed',
      trigger_type: 'manual',
      result_summary: { [request.label]: request.content },
    });
  }, [loadRunResult]);

  const outputResultContext = useMemo<OutputResultContextValue>(() => ({
    view: handleViewOutputResult,
    runId: displayedRunId,
    nodeStates,
  }), [displayedRunId, handleViewOutputResult, nodeStates]);

  const fetchHistory = useCallback(async () => {
    try {
      const resp = await axios.get(`/api/v1/agent-flows/${flow.id}/runs?limit=20`);
      setRunHistory(resp.data?.data || []);
    } catch {
      // ignore
    }
  }, [flow.id]);

  const hydrateRunState = useCallback((run: any) => {
    const normalizedStates = { ...(run.node_states || {}) };
    if (run.status === 'completed') {
      (flow.nodes || []).forEach((node) => {
        if (node.node_type !== 'output') return;
        const label = node.label || '';
        const summaryOutput = run.result_summary?.[label];
        const state = normalizedStates[node.id] || {};
        normalizedStates[node.id] = {
          ...state,
          // A completed flow has finalized its output. Older runs could leave
          // this state pending even though result_summary was committed.
          status: 'completed',
          output: state.output ?? summaryOutput ??
            'The run completed, but no output text was returned.',
        };
      });
    }
    setRunStatus(run.status);
    setNodeStates(normalizedStates);
    setDisplayedRunId(run.id || null);
    setNodes((nds) =>
      nds.map((n) => {
        const nodeState = normalizedStates[n.id];
        const nodeLabel = typeof n.data?.label === 'string' ? n.data.label : '';
        const summaryOutput = n.type === 'output'
          ? run.result_summary?.[nodeLabel]
          : undefined;
        const output = nodeState?.output ?? summaryOutput ?? null;
        return {
          ...n,
          className: nodeState?.status === 'running'
            ? 'agent-flow-node-running'
            : undefined,
          style: {
            ...(n.style || {}),
            '--agent-flow-active-color': nodeColors[n.type || ''] || '#d4a017',
            '--agent-flow-glow-strong': `${nodeColors[n.type || ''] || '#d4a017'}66`,
            '--agent-flow-glow-medium': `${nodeColors[n.type || ''] || '#d4a017'}3d`,
            '--agent-flow-glow-soft': `${nodeColors[n.type || ''] || '#d4a017'}1a`,
            '--agent-flow-glow-faint': `${nodeColors[n.type || ''] || '#d4a017'}12`,
          } as React.CSSProperties,
          data: {
            ...n.data,
            execution_status: nodeState?.status || null,
            execution_output: output,
            execution_run_id: run.id || null,
          },
        };
      })
    );
  }, [flow.nodes, setNodes]);

  // Restore latest run state on mount
  useEffect(() => {
    const initLatestRun = async () => {
      try {
        const resp = await axios.get(`/api/v1/agent-flows/${flow.id}/runs?limit=1`);
        const latest = resp.data?.data?.[0];
        if (latest) {
          const detailResp = await axios.get(`/api/v1/agent-flows/runs/${latest.id}`);
          const latestRun = detailResp.data?.data;
          if (latestRun) hydrateRunState(latestRun);
          if (latest.status === 'pending' || latest.status === 'running') {
            setActiveRunId(latest.id);
            setExecuting(true);
          }
        }
      } catch {
        // ignore
      }
    };
    initLatestRun();
  }, [flow.id, hydrateRunState]);

  // Track changes
  useEffect(() => { setDirty(true); }, [nodes, edges]);

  // ── Poll active run status ───────────────────────────────
  useEffect(() => {
    if (!activeRunId) return;
    const poll = async () => {
      try {
        const resp = await axios.get(`/api/v1/agent-flows/runs/${activeRunId}`);
        const run = resp.data?.data;
        if (run) {
          hydrateRunState(run);
          if (['completed', 'failed', 'cancelled'].includes(run.status)) {
            setActiveRunId(null);
            setExecuting(false);
            void fetchHistory();
            if (pollRef.current) clearInterval(pollRef.current);
          }
        }
      } catch {
        // ignore polling errors
      }
    };
    poll(); // Immediate first poll
    pollRef.current = setInterval(poll, 1500);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [activeRunId, fetchHistory, hydrateRunState]);


  // Handle new connections
  const onConnect = useCallback((params: Connection) => {
    setEdges((eds) => addEdge({
      ...params,
      type: 'custom',
      data: { label: null, edge_type: 'default' },
      markerEnd: { type: MarkerType.ArrowClosed, color: '#4a8cc7', width: 16, height: 16 },
    }, eds));
  }, [setEdges]);

  // Handle node selection
  const onNodeClick = useCallback((_: any, node: Node) => {
    setSelectedNode(node);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  // Update node data from inspector
  const onNodeDataUpdate = useCallback((nodeId: string, newData: any) => {
    setNodes((nds) =>
      nds.map((n) => (n.id === nodeId ? { ...n, data: newData } : n))
    );
    setSelectedNode((prev) => prev && prev.id === nodeId ? { ...prev, data: newData } : prev);
  }, [setNodes]);

  // Drag-and-drop from palette
  const onDragOver = useCallback((event: DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault();
      const nodeType = event.dataTransfer.getData('application/agentflow-node-type');
      if (!nodeType) return;

      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const paletteItem = NODE_PALETTE.find((p) => p.type === nodeType);
      const newNode: Node = {
        id: crypto.randomUUID(),
        type: nodeType,
        position,
        data: {
          label: paletteItem?.label || 'New Node',
          config: {},
        },
      };

      setNodes((nds) => [...nds, newNode]);
    },
    [reactFlowInstance, setNodes]
  );

  // Delete selected nodes/edges
  const onDeleteSelected = useCallback(() => {
    setNodes((nds) => nds.filter((n) => !n.selected));
    setEdges((eds) => eds.filter((e) => !e.selected));
    setSelectedNode(null);
  }, [setNodes, setEdges]);

  // Save flow
  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      // Update flow name if changed
      if (flowName !== flow.name) {
        await axios.patch(`/api/v1/agent-flows/${flow.id}`, { name: flowName });
      }

      // Build graph payload
      const viewport = reactFlowInstance.getViewport();
      const graphPayload = {
        viewport: { x: viewport.x, y: viewport.y, zoom: viewport.zoom },
        nodes: nodes.map((n) => ({
          id: n.id,
          node_type: n.type || 'samurai',
          label: n.data?.label || 'Untitled',
          position_x: n.position.x,
          position_y: n.position.y,
          config: n.data?.config || {},
        })),
        edges: edges.map((e) => ({
          id: e.id,
          source_node_id: e.source,
          target_node_id: e.target,
          source_handle: e.sourceHandle || null,
          target_handle: e.targetHandle || null,
          label: e.data?.label || null,
          edge_type: e.data?.edge_type || 'default',
          config: e.data?.config || {},
        })),
      };

      await axios.put(`/api/v1/agent-flows/${flow.id}/graph`, graphPayload);

      // ── Sync schedule_config from input nodes ────────────
      const inputNode = nodes.find((n) => n.type === 'input');
      if (inputNode) {
        const cfg = (inputNode.data as any)?.config || {};
        const inputType = cfg.input_type || 'manual';
        const patch: Record<string, any> = {};

        if (inputType === 'scheduled') {
          patch.trigger_type = 'scheduled';
          patch.schedule_config = {
            frequency: cfg.schedule_frequency || 'nightly',
            schedule_time: cfg.schedule_time || '07:00',
            ...(cfg.schedule_frequency === 'weekly' && { schedule_days: cfg.schedule_days || ['mon', 'tue', 'wed', 'thu', 'fri'] }),
            ...(cfg.schedule_frequency === 'monthly' && { schedule_day: cfg.schedule_day || 1 }),
            ...(cfg.schedule_frequency === 'hourly' && { minute_offset: cfg.schedule_minute_offset || 0 }),
          };
        } else if (inputType === 'api') {
          patch.trigger_type = 'api';
        } else if (inputType === 'event') {
          patch.trigger_type = 'event';
        } else {
          patch.trigger_type = 'manual';
        }

        // Only PATCH if trigger_type differs from current
        if (patch.trigger_type !== flow.trigger_type || patch.schedule_config) {
          await axios.patch(`/api/v1/agent-flows/${flow.id}`, patch);
        }
      }

      setDirty(false);
    } catch (err) {
      console.error('Failed to save flow:', err);
    } finally {
      setSaving(false);
    }
  }, [flow.id, flow.name, flow.trigger_type, flowName, nodes, edges, reactFlowInstance]);

  // ── Trigger run ──────────────────────────────────────────
  const handleRun = useCallback(async () => {
    if (executing) return;
    // Auto-save before running
    if (dirty) await handleSave();
    setExecuting(true);
    setRunStatus('pending');
    setDisplayedRunId(null);
    // Clear previous execution overlays
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        className: undefined,
        data: {
          ...n.data,
          execution_status: null,
          execution_output: null,
          execution_run_id: null,
        },
      }))
    );
    try {
      const resp = await axios.post(`/api/v1/agent-flows/${flow.id}/run`);
      const runId = resp.data?.data?.run_id;
      if (runId) {
        setActiveRunId(runId);
      }
    } catch (err) {
      console.error('Failed to start flow run:', err);
      setExecuting(false);
      setRunStatus(null);
    }
  }, [executing, dirty, handleSave, flow.id, setNodes]);

  // ── Cancel run ───────────────────────────────────────────
  const handleCancel = useCallback(async () => {
    if (!activeRunId) return;
    try {
      await axios.post(`/api/v1/agent-flows/runs/${activeRunId}/cancel`);
      setActiveRunId(null);
      setExecuting(false);
      setRunStatus('cancelled');
    } catch {
      // ignore
    }
  }, [activeRunId]);

  // ── Fetch run history ────────────────────────────────────
  useEffect(() => {
    if (!showHistory) return;
    void fetchHistory();
    const refreshTimer = window.setInterval(() => {
      void fetchHistory();
    }, 3000);
    return () => window.clearInterval(refreshTimer);
  }, [fetchHistory, showHistory]);

  const deleteRun = useCallback(async (id: string) => {
    if (!window.confirm('Delete this run and its generated Output file?')) return;
    setDeletingRunId(id);
    try {
      await axios.delete(`/api/v1/agent-flows/runs/${id}`);
      setRunHistory((runs) => runs.filter((run) => run.id !== id));
      if (displayedRunId === id || nodes.some((node) => node.data?.execution_run_id === id)) {
        setRunStatus(null);
        setNodeStates({});
        setDisplayedRunId(null);
        setNodes((currentNodes) => currentNodes.map((node) => ({
          ...node,
          className: undefined,
          data: {
            ...node.data,
            execution_status: null,
            execution_output: null,
            execution_run_id: null,
          },
        })));
      }
      if (selectedRunId === id) {
        setSelectedRunId(null);
        setSelectedRunDetails(null);
      }
    } catch (err) {
      console.error('Failed to delete flow run:', err);
    } finally {
      setDeletingRunId(null);
    }
  }, [displayedRunId, nodes, selectedRunId, setNodes]);

  const viewRunDetails = useCallback(async (id: string) => {
    const run = await loadRunResult(id);
    if (run) hydrateRunState(run);
  }, [hydrateRunState, loadRunResult]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA' || document.activeElement?.tagName === 'SELECT') return;
        onDeleteSelected();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleSave, onDeleteSelected]);

  // Find the actual selected node object for inspector
  const inspectorNode = selectedNode ? nodes.find((n) => n.id === selectedNode.id) || selectedNode : null;

  return (
    <div className="relative flex h-[calc(100vh-120px)] rounded-lg overflow-hidden border border-[#1a2040]">
      {/* Canvas */}
      <div className="flex-1 flex flex-col bg-[#060810]">
        {/* Toolbar */}
        <div className="flex items-center justify-between px-3 py-2 bg-[#0a0e1a] border-b border-[#1a2040]">
          <div className="flex items-center gap-3">
            <button
              onClick={onBack}
              className="p-1.5 hover:bg-[#1a2040] text-[#7a8899] hover:text-[#c8d0d8] rounded-lg transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            <div className="h-5 w-px bg-[#1a2040]" />

            {editingName ? (
              <input
                autoFocus
                type="text"
                value={flowName}
                onChange={(e) => setFlowName(e.target.value)}
                onBlur={() => setEditingName(false)}
                onKeyDown={(e) => e.key === 'Enter' && setEditingName(false)}
                className="bg-[#0e1225] border border-[#d4a017]/40 rounded px-2 py-1 text-sm font-bold text-[#d4a017] outline-none"
              />
            ) : (
              <button
                onClick={() => setEditingName(true)}
                className="text-sm font-bold text-[#d4a017] hover:text-[#d4a017]/80 transition-colors"
              >
                {flowName}
              </button>
            )}

            <span className={cn(
              "text-[8px] font-bold uppercase tracking-widest px-2 py-0.5 rounded border",
              flow.status === 'active'
                ? "text-green-400 bg-green-500/10 border-green-500/20"
                : flow.status === 'paused'
                  ? "text-[#4a8cc7] bg-[#4a8cc7]/10 border-[#4a8cc7]/20"
                  : "text-[#7a8899] bg-[#7a8899]/10 border-[#7a8899]/20"
            )}>
              {flow.status}
            </span>

            {dirty && (
              <span className="text-[8px] text-[#d4a017]/60 font-bold uppercase tracking-widest animate-pulse">
                Unsaved
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* Node palette (inline drag buttons) */}
            <div className="flex items-center gap-1 mr-2">
              {NODE_PALETTE.map((item) => {
                const PIcon = item.icon;
                return (
                  <div
                    key={item.type}
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData('application/agentflow-node-type', item.type);
                      e.dataTransfer.effectAllowed = 'move';
                    }}
                    className="flex items-center gap-1.5 px-2 py-1.5 bg-[#0e1225] border border-[#1a2040] rounded-md cursor-grab active:cursor-grabbing hover:border-[#2a3060] transition-colors group"
                    title={`Drag to add ${item.label}`}
                  >
                    <PIcon className="w-3 h-3" style={{ color: item.color }} />
                    <span className="text-[9px] font-bold text-[#7a8899] group-hover:text-[#c8d0d8] hidden xl:inline">
                      {item.label}
                    </span>
                  </div>
                );
              })}
            </div>

            <div className="h-5 w-px bg-[#1a2040]" />

            <button
              onClick={handleSave}
              disabled={saving}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all",
                saving
                  ? "bg-[#7a8899]/20 text-[#7a8899] cursor-wait"
                  : dirty
                    ? "bg-[#d4a017] text-black hover:bg-[#d4a017]/90 shadow-[0_0_12px_rgba(212,160,23,0.2)]"
                    : "bg-[#0e1225] text-[#7a8899] border border-[#1a2040] hover:border-[#2a3060]"
              )}
            >
              {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
              {saving ? 'Saving...' : 'Save'}
            </button>

            <div className="h-5 w-px bg-[#1a2040]" />

            {/* Run / Cancel button */}
            {executing ? (
              <button
                onClick={handleCancel}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider bg-[#ef4444]/20 text-[#ef4444] border border-[#ef4444]/30 hover:bg-[#ef4444]/30 transition-all"
              >
                <StopCircle className="w-3 h-3" />
                Cancel
              </button>
            ) : (
              <button
                onClick={handleRun}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider bg-[#22c55e]/20 text-[#22c55e] border border-[#22c55e]/30 hover:bg-[#22c55e]/30 transition-all shadow-[0_0_10px_rgba(34,197,94,0.1)]"
              >
                <Play className="w-3 h-3" />
                Run
              </button>
            )}

            {/* History button */}
            <button
              onClick={() => { setShowHistory(!showHistory); if (!showHistory) fetchHistory(); }}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all border",
                showHistory
                  ? "bg-[#4a8cc7]/20 text-[#4a8cc7] border-[#4a8cc7]/30"
                  : "bg-[#0e1225] text-[#7a8899] border-[#1a2040] hover:border-[#2a3060]"
              )}
            >
              <History className="w-3 h-3" />
              History
            </button>
          </div>
        </div>

        {/* Execution Status Bar */}
        {runStatus && (
          <div className={cn(
            "flex items-center justify-between px-4 py-2 border-b text-[10px] font-bold uppercase tracking-wider",
            runStatus === 'running' ? "bg-[#4a8cc7]/10 border-[#4a8cc7]/20 text-[#4a8cc7]" :
            runStatus === 'completed' ? "bg-[#22c55e]/10 border-[#22c55e]/20 text-[#22c55e]" :
            runStatus === 'failed' ? "bg-[#ef4444]/10 border-[#ef4444]/20 text-[#ef4444]" :
            runStatus === 'cancelled' ? "bg-[#7a8899]/10 border-[#7a8899]/20 text-[#7a8899]" :
            "bg-[#d4a017]/10 border-[#d4a017]/20 text-[#d4a017]"
          )}>
            <div className="flex items-center gap-2">
              {runStatus === 'running' && <Loader2 className="w-3 h-3 animate-spin" />}
              {runStatus === 'completed' && <CheckCircle2 className="w-3 h-3" />}
              {runStatus === 'failed' && <XCircle className="w-3 h-3" />}
              {runStatus === 'pending' && <Clock className="w-3 h-3" />}
              <span>Flow {runStatus}</span>
            </div>
            <div className="flex items-center gap-2">
              {Object.values(nodeStates).length > 0 && (
                <span className="text-[9px] opacity-70">
                  {Object.values(nodeStates).filter((s: any) => s.status === 'completed').length}/{Object.values(nodeStates).length} nodes completed
                </span>
              )}
              {runStatus !== 'running' && (
                <button
                  onClick={() => { setRunStatus(null); setNodeStates({}); setDisplayedRunId(null); setNodes((nds) => nds.map((n) => ({ ...n, className: undefined, data: { ...n.data, execution_status: null, execution_output: null, execution_run_id: null } }))); }}
                  className="text-current opacity-50 hover:opacity-100 transition-opacity"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>
        )}

        {/* React Flow Canvas */}
        <div ref={reactFlowWrapper} className="flex-1">
          <OutputResultViewerContext.Provider value={outputResultContext}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={onNodeClick}
              onPaneClick={onPaneClick}
              onDrop={onDrop}
              onDragOver={onDragOver}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              defaultViewport={flow.viewport}
              fitView={!flow.nodes?.length ? false : true}
              snapToGrid
              snapGrid={[16, 16]}
              deleteKeyCode={null}
              proOptions={{ hideAttribution: true }}
              style={{ background: '#060810' }}
            >
            <Controls
              position="bottom-left"
              style={{ display: 'flex', gap: 2 }}
              className="!bg-[#0e1225] !border !border-[#1a2040] !rounded-lg !shadow-lg [&>button]:!bg-[#0a0e1a] [&>button]:!border-[#1a2040] [&>button]:!text-[#7a8899] [&>button:hover]:!text-[#d4a017] [&>button]:!rounded [&>button]:!w-7 [&>button]:!h-7"
            />
            <MiniMap
              position="bottom-right"
              nodeColor={(n) => nodeColors[n.type || 'samurai'] || '#d4a017'}
              maskColor="rgba(6, 8, 16, 0.85)"
              className="!bg-[#0a0e1a] !border !border-[#1a2040] !rounded-lg"
              style={{ width: 160, height: 100 }}
            />
            <Background
              variant={BackgroundVariant.Dots}
              gap={20}
              size={1}
              color="#1a204040"
            />

            {/* Empty state */}
            {nodes.length === 0 && (
              <Panel position="top-center" className="mt-24">
                <div className="text-center space-y-3 animate-in fade-in duration-700">
                  <div className="w-16 h-16 rounded-2xl bg-[#0e1225] border border-[#1a2040] flex items-center justify-center mx-auto">
                    <GitBranch className="w-7 h-7 text-[#4a8cc7]/40" />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-[#7a8899]">Empty Canvas</p>
                    <p className="text-[10px] text-[#7a8899]/60 mt-1">
                      Drag cards from the toolbar above to build your workflow
                    </p>
                  </div>
                </div>
              </Panel>
            )}
            </ReactFlow>
          </OutputResultViewerContext.Provider>
        </div>
      </div>

      {/* Inspector Panel */}
      {inspectorNode && (
        <NodeInspector
          node={inspectorNode}
          onUpdate={onNodeDataUpdate}
          onClose={() => setSelectedNode(null)}
          agents={agents}
          routingProfiles={routingProfiles}
          flowId={flow.id}
        />
      )}

      {/* Run History Panel — rendered into #portal-root (outside React #root) */}
      {createPortal(
        <>
          {showHistory && (
            <>
          {/* Backdrop — click to close */}
          <div
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 99998,
              backgroundColor: 'rgba(0,0,0,0.2)',
              pointerEvents: 'auto',
            }}
            onClick={() => setShowHistory(false)}
          />
          {/* Panel */}
          <div
            style={{
              position: 'fixed',
              top: 0,
              right: 0,
              width: 320,
              height: '100vh',
              zIndex: 99999,
              backgroundColor: '#0a0e1a',
              borderLeft: '1px solid #1a2040',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '-8px 0 32px rgba(0,0,0,0.5)',
              pointerEvents: 'auto',
            }}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-[#1a2040] shrink-0">
              <div className="flex items-center gap-2 min-w-0">
                <History className="w-4 h-4 text-[#4a8cc7] shrink-0" />
                <h3 className="text-xs font-bold text-[#c8d0d8] uppercase tracking-wider">Run History</h3>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={fetchHistory}
                  className="p-1.5 hover:bg-[#1a2040] text-[#7a8899] hover:text-[#c8d0d8] rounded-lg transition-colors"
                  title="Refresh history"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setShowHistory(false)}
                  className="p-1.5 hover:bg-[#ef4444]/20 text-[#7a8899] hover:text-[#ef4444] rounded-lg transition-colors"
                  title="Close history"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
              {runHistory.length === 0 && (
                <div className="text-center py-8">
                  <Clock className="w-8 h-8 text-[#7a8899]/30 mx-auto mb-2" />
                  <p className="text-[10px] text-[#7a8899]/50">No runs yet</p>
                </div>
              )}
              {runHistory.map((run: any) => (
                <div
                  key={run.id}
                  onClick={() => viewRunDetails(run.id)}
                  className="p-3 bg-[#0e1225] border border-[#1a2040] rounded-lg hover:border-[#2a3060] transition-colors overflow-hidden cursor-pointer"
                >
                  <div className="flex items-center justify-between mb-2 gap-2">
                    <div className="flex items-center gap-1.5 min-w-0">
                      {run.status === 'completed' && <CheckCircle2 className="w-3.5 h-3.5 text-[#22c55e] shrink-0" />}
                      {run.status === 'failed' && <XCircle className="w-3.5 h-3.5 text-[#ef4444] shrink-0" />}
                      {run.status === 'running' && <Loader2 className="w-3.5 h-3.5 text-[#4a8cc7] animate-spin shrink-0" />}
                      {run.status === 'cancelled' && <StopCircle className="w-3.5 h-3.5 text-[#7a8899] shrink-0" />}
                      {run.status === 'pending' && <Clock className="w-3.5 h-3.5 text-[#d4a017] shrink-0" />}
                      <span className={cn(
                        "text-[10px] font-bold uppercase",
                        run.status === 'completed' ? "text-[#22c55e]" :
                        run.status === 'failed' ? "text-[#ef4444]" :
                        run.status === 'running' ? "text-[#4a8cc7]" :
                        "text-[#7a8899]"
                      )}>
                        {run.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <span className="text-[8px] font-bold uppercase tracking-widest text-[#7a8899]/60 bg-[#7a8899]/10 px-1.5 py-0.5 rounded truncate max-w-[80px]">
                        {run.trigger_type}
                      </span>
                      <button
                        type="button"
                        title="Delete run and Output file"
                        disabled={deletingRunId === run.id || run.status === 'running' || run.status === 'pending'}
                        onClick={(e) => {
                          e.stopPropagation();
                          void deleteRun(run.id);
                        }}
                        className="p-1 rounded text-[#7a8899]/60 hover:text-[#ef4444] hover:bg-[#ef4444]/10 disabled:opacity-30 disabled:pointer-events-none transition-colors"
                      >
                        {deletingRunId === run.id
                          ? <Loader2 className="w-3 h-3 animate-spin" />
                          : <Trash2 className="w-3 h-3" />}
                      </button>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-[9px] text-[#7a8899]">
                    <span>{formatRunTimestamp(run.created_at)}</span>
                    {run.started_at && run.completed_at && (
                      <span className="text-[#d4a017]/70">
                        {((parseRunTimestamp(run.completed_at).getTime() - parseRunTimestamp(run.started_at).getTime()) / 1000).toFixed(1)}s
                      </span>
                    )}
                  </div>
                  {run.error_message && (
                    <p className="mt-1.5 text-[9px] text-[#ef4444]/80 line-clamp-2 bg-[#ef4444]/5 rounded p-1.5">
                      {run.error_message}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>

            </>
          )}

          {/* Run Details Modal */}
          {selectedRunId && (
            <div className="fixed inset-0 flex items-center justify-center p-4 pointer-events-auto" style={{ zIndex: 100000 }}>
              <div 
                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                onClick={() => setSelectedRunId(null)}
              />
              <div className="relative w-full max-w-4xl max-h-[85vh] bg-[#0a0e1a] border border-[#1a2040] rounded-xl shadow-2xl flex flex-col overflow-hidden">
                <div className="flex items-center justify-between px-6 py-4 border-b border-[#1a2040] bg-[#0e1225]">
                  <div className="flex items-center gap-3">
                    <h2 className="text-sm font-bold text-[#c8d0d8] uppercase tracking-wider">Run Details</h2>
                    {loadingRunDetails && <Loader2 className="w-4 h-4 text-[#4a8cc7] animate-spin" />}
                  </div>
                  <button 
                    onClick={() => setSelectedRunId(null)}
                    className="p-2 hover:bg-[#1a2040] text-[#7a8899] hover:text-[#c8d0d8] rounded-lg transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
                
                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                  {selectedRunDetails ? (
                    <>
                      <div className="flex flex-wrap gap-4 text-[11px] font-bold uppercase tracking-wider text-[#7a8899]">
                        <span className="bg-[#1a2040] px-2.5 py-1 rounded">Status: <span className={cn(
                          selectedRunDetails.status === 'completed' ? "text-[#22c55e]" :
                          selectedRunDetails.status === 'failed' ? "text-[#ef4444]" : "text-[#4a8cc7]"
                        )}>{selectedRunDetails.status}</span></span>
                        <span className="bg-[#1a2040] px-2.5 py-1 rounded">Trigger: {selectedRunDetails.trigger_type}</span>
                        {selectedRunDetails.started_at && selectedRunDetails.completed_at && (
                          <span className="bg-[#1a2040] px-2.5 py-1 rounded">
                            Duration: {((parseRunTimestamp(selectedRunDetails.completed_at).getTime() - parseRunTimestamp(selectedRunDetails.started_at).getTime()) / 1000).toFixed(2)}s
                          </span>
                        )}
                      </div>

                      {selectedRunDetails.error_message && (
                        <div className="p-4 rounded-lg border border-[#ef4444]/20 bg-[#ef4444]/5">
                          <h3 className="text-xs font-bold text-[#ef4444] uppercase tracking-wider mb-2">Error Details</h3>
                          <p className="text-sm text-[#ef4444]/90 whitespace-pre-wrap font-mono">{selectedRunDetails.error_message}</p>
                        </div>
                      )}

                      {selectedRunDetails.result_summary && Object.keys(selectedRunDetails.result_summary).length > 0 ? (
                        <div className="space-y-4">
                          <h3 className="text-xs font-bold text-[#c8d0d8] uppercase tracking-wider border-b border-[#1a2040] pb-2">Output Artifacts & Reports</h3>
                          {Object.entries(selectedRunDetails.result_summary).map(([label, content]) => (
                            <div key={label} className="rounded-lg border border-[#2a3060] bg-[#0e1225] overflow-hidden">
                              <div className="px-4 py-2 bg-[#1a2040]/50 border-b border-[#2a3060]">
                                <span className="text-xs font-bold text-[#4a8cc7]">{label}</span>
                              </div>
                              <div className="p-4 text-sm text-[#c8d0d8] leading-relaxed whitespace-pre-wrap overflow-x-auto">
                                {String(content)}
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="py-8 text-center border border-dashed border-[#1a2040] rounded-lg">
                          <p className="text-sm text-[#7a8899]">No output artifacts generated for this run.</p>
                        </div>
                      )}
                    </>
                  ) : (
                    !loadingRunDetails && (
                      <div className="py-12 text-center">
                        <p className="text-sm text-[#7a8899]">Could not load run details.</p>
                      </div>
                    )
                  )}
                </div>
              </div>
            </div>
          )}
        </>,
        document.getElementById('portal-root')!
      )}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════
// FLOW LIST VIEW
// ═══════════════════════════════════════════════════════════════

function FlowListView({
  flows,
  loading,
  onSelect,
  onCreate,
  onDelete,
  onDuplicate,
  onRefresh,
}: {
  flows: FlowListItem[];
  loading: boolean;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
  onDuplicate: (id: string) => void;
  onRefresh: () => void;
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [menuOpen, setMenuOpen] = useState<string | null>(null);

  const filtered = flows.filter((f) =>
    f.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const statusColors: Record<string, string> = {
    draft: '#7a8899',
    active: '#22c55e',
    paused: '#4a8cc7',
    archived: '#7a8899',
  };

  return (
    <div className="space-y-5 animate-in fade-in duration-500">
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Flows', value: flows.length, color: '#d4a017' },
          { label: 'Active', value: flows.filter((f) => f.status === 'active').length, color: '#22c55e' },
          { label: 'Draft', value: flows.filter((f) => f.status === 'draft').length, color: '#7a8899' },
          { label: 'Paused', value: flows.filter((f) => f.status === 'paused').length, color: '#4a8cc7' },
        ].map((stat, i) => (
          <div key={i} className="shogun-card !p-4 border-l-2" style={{ borderLeftColor: stat.color }}>
            <span className="text-[9px] uppercase tracking-widest font-bold text-[#7a8899]">{stat.label}</span>
            <div className="text-2xl font-bold text-[#c8d0d8] mt-1">{stat.value}</div>
          </div>
        ))}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#7a8899]" />
          <input
            type="text"
            placeholder="Filter workflows..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-[#0e1225] border border-[#1a2040] rounded-lg pl-10 pr-4 py-2 text-sm text-[#c8d0d8] focus:border-[#4a8cc7] transition-colors outline-none"
          />
        </div>
        <button
          onClick={onRefresh}
          className="p-2.5 bg-[#0e1225] border border-[#1a2040] rounded-lg text-[#7a8899] hover:text-[#d4a017] transition-colors"
        >
          <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
        </button>
        <button
          onClick={onCreate}
          className="flex items-center gap-2 bg-[#4a8cc7] hover:bg-[#4a8cc7]/90 text-white font-bold py-2.5 px-5 rounded-lg transition-all shadow-[0_0_20px_rgba(74,140,199,0.15)] text-xs"
        >
          <Plus className="w-4 h-4" /> NEW FLOW
        </button>
      </div>

      {/* Flow Cards Grid */}
      {loading ? (
        <div className="flex flex-col items-center gap-3 py-16">
          <Loader2 className="w-6 h-6 text-[#d4a017] animate-spin" />
          <span className="text-[10px] text-[#7a8899] uppercase tracking-widest">Loading workflows...</span>
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16">
          <GitBranch className="w-10 h-10 text-[#1a2040] mx-auto mb-3" />
          <p className="text-sm text-[#7a8899]">
            {flows.length === 0 ? 'No Agent Flows created yet' : 'No flows match your search'}
          </p>
          {flows.length === 0 && (
            <p className="text-[10px] text-[#7a8899]/60 mt-1">
              Create your first workflow to orchestrate Samurai agents visually
            </p>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((flow) => (
            <button
              key={flow.id}
              onClick={() => onSelect(flow.id)}
              className="shogun-card !p-0 text-left hover:border-[#4a8cc7]/40 transition-all group relative overflow-hidden"
            >
              {/* Top accent */}
              <div className="h-0.5" style={{ background: statusColors[flow.status] || '#7a8899' }} />

              <div className="p-5">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <h4 className="text-sm font-bold text-[#c8d0d8] group-hover:text-[#d4a017] transition-colors truncate">
                      {flow.name}
                    </h4>
                    <p className="text-[10px] text-[#7a8899] mt-1 line-clamp-2">
                      {flow.description || 'No description'}
                    </p>
                  </div>
                  <div className="relative">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setMenuOpen(menuOpen === flow.id ? null : flow.id);
                      }}
                      className="p-1.5 hover:bg-[#1a2040] rounded-lg text-[#7a8899] hover:text-[#c8d0d8] transition-colors opacity-0 group-hover:opacity-100"
                    >
                      <MoreVertical className="w-3.5 h-3.5" />
                    </button>
                    {menuOpen === flow.id && (
                      <div className="absolute right-0 top-8 z-10 w-36 bg-[#0e1225] border border-[#1a2040] rounded-lg shadow-xl overflow-hidden">
                        <button
                          onClick={(e) => { e.stopPropagation(); onDuplicate(flow.id); setMenuOpen(null); }}
                          className="w-full flex items-center gap-2 px-3 py-2 text-[10px] font-bold text-[#7a8899] hover:bg-[#1a2040] hover:text-[#c8d0d8] transition-colors"
                        >
                          <Copy className="w-3 h-3" /> Duplicate
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); onDelete(flow.id); setMenuOpen(null); }}
                          className="w-full flex items-center gap-2 px-3 py-2 text-[10px] font-bold text-red-400 hover:bg-red-500/10 transition-colors"
                        >
                          <Trash2 className="w-3 h-3" /> Delete
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-3 mt-4">
                  <span
                    className="text-[8px] font-bold uppercase tracking-widest px-2 py-0.5 rounded border"
                    style={{
                      color: statusColors[flow.status],
                      background: `${statusColors[flow.status]}10`,
                      borderColor: `${statusColors[flow.status]}30`,
                    }}
                  >
                    {flow.status}
                  </span>
                  <span className="text-[8px] text-[#7a8899] flex items-center gap-1">
                    <Clock className="w-2.5 h-2.5" />
                    {flow.trigger_type}
                  </span>
                  <span className="text-[8px] text-[#7a8899]/60 ml-auto">
                    {new Date(flow.updated_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════
// TEMPLATE GALLERY MODAL
// ═══════════════════════════════════════════════════════════════

interface TemplateItem {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  difficulty: string;
  trigger_type: string;
  node_count: number;
}

interface TemplateCategoryInfo {
  name: string;
  count: number;
}

const CATEGORY_COLORS: Record<string, string> = {
  'Document Processing': '#10b981',
  'Data Analysis': '#3b82f6',
  'Content Creation': '#f59e0b',
  'Email Automation': '#8b5cf6',
  'Research & Intelligence': '#ef4444',
  'Business Operations': '#06b6d4',
  'Marketing': '#ec4899',
  'Human Resources': '#14b8a6',
  'Legal & Compliance': '#6366f1',
  'Education & Training': '#f97316',
};

const DIFFICULTY_BADGES: Record<string, { label: string; color: string }> = {
  beginner: { label: 'Beginner', color: '#10b981' },
  intermediate: { label: 'Intermediate', color: '#f59e0b' },
  advanced: { label: 'Advanced', color: '#ef4444' },
};

function CreateFlowModal({
  onClose,
  onCreate,
  onCreateFromTemplate,
}: {
  onClose: () => void;
  onCreate: (name: string, description: string, triggerType: string) => void;
  onCreateFromTemplate: (templateId: string) => void;
}) {
  const [activeTab, setActiveTab] = useState<'templates' | 'blank'>('templates');
  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [categories, setCategories] = useState<TemplateCategoryInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [creating, setCreating] = useState<string | null>(null);

  // Blank flow state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [triggerType, setTriggerType] = useState('manual');

  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        const res = await axios.get('/api/v1/agent-flows/templates');
        const data = res.data?.data;
        if (data) {
          setTemplates(data.templates || []);
          setCategories(data.categories || []);
        }
      } catch (err) {
        console.error('Failed to load templates:', err);
        const detail = axios.isAxiosError(err) ? err.response?.data?.detail : '';
        setLoadError(detail || 'AgentFlow templates could not be loaded. Run Shogun Repair/Update and restart Shogun.');
      } finally {
        setLoading(false);
      }
    };
    fetchTemplates();
  }, []);

  const filteredTemplates = useMemo(() => {
    let list = templates;
    if (selectedCategory) {
      list = list.filter((t) => t.category === selectedCategory);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (t) =>
          t.name.toLowerCase().includes(q) ||
          t.description.toLowerCase().includes(q) ||
          t.category.toLowerCase().includes(q)
      );
    }
    return list;
  }, [templates, selectedCategory, searchQuery]);

  const handleUseTemplate = async (templateId: string) => {
    setCreating(templateId);
    try {
      onCreateFromTemplate(templateId);
    } catch {
      setCreating(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-[#0a0e1a] border border-[#1a2040] rounded-xl w-full max-w-5xl h-[85vh] shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 flex flex-col">
        {/* Header */}
        <div className="bg-[#0e1225] border-b border-[#1a2040] p-5 flex items-center justify-between shrink-0">
          <div>
            <h3 className="text-lg font-bold text-[#d4a017] flex items-center gap-2">
              <Sparkles className="w-5 h-5" />
              Create Agent Flow
            </h3>
            <p className="text-[10px] text-[#7a8899] uppercase tracking-widest font-bold mt-1">
              Choose a template or start from scratch
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-[#d4a017]/10 text-[#7a8899] hover:text-[#d4a017] rounded-lg transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="border-b border-[#1a2040] flex gap-0 shrink-0">
          <button
            onClick={() => setActiveTab('templates')}
            className={cn(
              'px-6 py-3 text-sm font-bold transition-all flex items-center gap-2',
              activeTab === 'templates'
                ? 'text-[#d4a017] border-b-2 border-[#d4a017] bg-[#d4a017]/5'
                : 'text-[#7a8899] hover:text-[#c8d0d8] hover:bg-[#1a2040]/50'
            )}
          >
            <LayoutGrid className="w-4 h-4" />
            Templates
            <span className="text-[9px] bg-[#d4a017]/20 text-[#d4a017] px-1.5 py-0.5 rounded-full font-bold">
              {templates.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('blank')}
            className={cn(
              'px-6 py-3 text-sm font-bold transition-all flex items-center gap-2',
              activeTab === 'blank'
                ? 'text-[#d4a017] border-b-2 border-[#d4a017] bg-[#d4a017]/5'
                : 'text-[#7a8899] hover:text-[#c8d0d8] hover:bg-[#1a2040]/50'
            )}
          >
            <Plus className="w-4 h-4" />
            Blank Flow
          </button>
        </div>

        {/* Content */}
        {activeTab === 'templates' ? (
          <div className="flex flex-1 overflow-hidden">
            {/* Category sidebar */}
            <div className="w-56 border-r border-[#1a2040] overflow-y-auto shrink-0 p-3 space-y-0.5">
              <button
                onClick={() => setSelectedCategory(null)}
                className={cn(
                  'w-full text-left px-3 py-2 rounded-lg text-xs font-medium transition-colors',
                  !selectedCategory
                    ? 'bg-[#d4a017]/10 text-[#d4a017]'
                    : 'text-[#7a8899] hover:text-[#c8d0d8] hover:bg-[#1a2040]/50'
                )}
              >
                All Templates
                <span className="float-right text-[9px] opacity-60">{templates.length}</span>
              </button>
              {categories.map((cat) => (
                <button
                  key={cat.name}
                  onClick={() => setSelectedCategory(cat.name === selectedCategory ? null : cat.name)}
                  className={cn(
                    'w-full text-left px-3 py-2 rounded-lg text-xs font-medium transition-colors flex items-center gap-2',
                    selectedCategory === cat.name
                      ? 'bg-[#d4a017]/10 text-[#d4a017]'
                      : 'text-[#7a8899] hover:text-[#c8d0d8] hover:bg-[#1a2040]/50'
                  )}
                >
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ background: CATEGORY_COLORS[cat.name] || '#7a8899' }}
                  />
                  <span className="flex-1 truncate">{cat.name}</span>
                  <span className="text-[9px] opacity-60">{cat.count}</span>
                </button>
              ))}
            </div>

            {/* Template grid */}
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* Search */}
              <div className="p-3 border-b border-[#1a2040] shrink-0">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#7a8899]" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full bg-[#050508] border border-[#1a2040] rounded-lg pl-9 pr-3 py-2 text-xs text-[#c8d0d8] focus:border-[#d4a017] transition-colors outline-none"
                    placeholder="Search templates..."
                  />
                </div>
              </div>

              {/* Grid */}
              <div className="flex-1 overflow-y-auto p-3">
                {loading ? (
                  <div className="flex items-center justify-center py-16">
                    <Loader2 className="w-6 h-6 text-[#d4a017] animate-spin" />
                  </div>
                ) : loadError ? (
                  <div className="text-center py-16 px-8">
                    <AlertTriangle className="w-8 h-8 text-amber-400 mx-auto mb-3" />
                    <p className="text-sm text-amber-300 font-semibold">Templates unavailable</p>
                    <p className="text-xs text-[#7a8899] mt-2">{loadError}</p>
                  </div>
                ) : filteredTemplates.length === 0 ? (
                  <div className="text-center py-16">
                    <Search className="w-8 h-8 text-[#7a8899]/40 mx-auto mb-3" />
                    <p className="text-sm text-[#7a8899]">No templates match your search</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-2.5">
                    {filteredTemplates.map((t) => {
                      const catColor = CATEGORY_COLORS[t.category] || '#7a8899';
                      const diff = DIFFICULTY_BADGES[t.difficulty] || DIFFICULTY_BADGES.beginner;
                      return (
                        <button
                          key={t.id}
                          onClick={() => handleUseTemplate(t.id)}
                          disabled={!!creating}
                          className={cn(
                            'text-left p-3.5 rounded-xl border transition-all group',
                            'bg-[#0e1225] border-[#1a2040] hover:border-[#d4a017]/50 hover:bg-[#0e1225]/80',
                            'hover:shadow-[0_0_20px_rgba(212,160,23,0.08)]',
                            creating === t.id && 'opacity-70 pointer-events-none'
                          )}
                        >
                          <div className="flex items-start gap-2.5">
                            <span className="text-xl leading-none mt-0.5">{t.icon}</span>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <h4 className="text-xs font-bold text-[#c8d0d8] truncate flex-1 group-hover:text-[#d4a017] transition-colors">
                                  {t.name}
                                </h4>
                                {creating === t.id && <Loader2 className="w-3 h-3 text-[#d4a017] animate-spin shrink-0" />}
                              </div>
                              <p className="text-[10px] text-[#7a8899] line-clamp-2 leading-relaxed mb-2">
                                {t.description}
                              </p>
                              <div className="flex items-center gap-2 flex-wrap">
                                <span
                                  className="text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded"
                                  style={{ color: catColor, background: `${catColor}15` }}
                                >
                                  {t.category}
                                </span>
                                <span
                                  className="text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded"
                                  style={{ color: diff.color, background: `${diff.color}15` }}
                                >
                                  {diff.label}
                                </span>
                                <span className="text-[8px] text-[#7a8899]/60 ml-auto">
                                  {t.node_count} nodes
                                </span>
                              </div>
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          /* Blank Flow Tab */
          <div className="p-6 space-y-5 overflow-y-auto">
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-[#7a8899] uppercase tracking-widest">Flow Name</label>
              <input
                type="text"
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-[#050508] border border-[#1a2040] rounded-lg p-2.5 text-sm text-[#c8d0d8] focus:border-[#d4a017] transition-colors outline-none"
                placeholder="e.g., Research Pipeline, Weekly Report..."
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-[#7a8899] uppercase tracking-widest">Trigger Type</label>
              <select
                value={triggerType}
                onChange={(e) => setTriggerType(e.target.value)}
                className="w-full bg-[#050508] border border-[#1a2040] rounded-lg p-2.5 text-sm text-[#c8d0d8] focus:border-[#d4a017] transition-colors outline-none cursor-pointer"
              >
                <option value="manual">Manual Execution</option>
                <option value="scheduled">Scheduled / Cron</option>
                <option value="event">Event-Based Trigger</option>
                <option value="api">API Trigger</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-[#7a8899] uppercase tracking-widest">Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                className="w-full bg-[#050508] border border-[#1a2040] rounded-lg p-3 text-xs text-[#c8d0d8] focus:border-[#d4a017] transition-colors outline-none resize-none"
                placeholder="Describe the purpose of this workflow..."
              />
            </div>

            <div className="flex gap-3 pt-2">
              <button
                onClick={onClose}
                className="flex-1 bg-[#0e1225] hover:bg-[#1a2040] text-[#7a8899] font-bold py-2.5 rounded-lg transition-all border border-[#1a2040] text-sm"
              >
                Cancel
              </button>
              <button
                onClick={() => onCreate(name, description, triggerType)}
                disabled={!name.trim()}
                className={cn(
                  "flex-1 font-bold py-2.5 rounded-lg transition-all text-sm flex items-center justify-center gap-2",
                  !name.trim()
                    ? "bg-[#7a8899]/20 text-[#7a8899] cursor-not-allowed"
                    : "bg-[#4a8cc7] hover:bg-[#4a8cc7]/90 text-white shadow-[0_0_20px_rgba(74,140,199,0.15)]"
                )}
              >
                <Plus className="w-3.5 h-3.5" />
                Create Blank Flow
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════
// MAIN EXPORT — AGENT FLOW TAB COMPONENT
// ═══════════════════════════════════════════════════════════════

export const AgentFlow = () => {
  const [flows, setFlows] = useState<FlowListItem[]>([]);
  const [activeFlow, setActiveFlow] = useState<AgentFlowData | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [agents, setAgents] = useState<any[]>([]);
  const [routingProfiles, setRoutingProfiles] = useState<any[]>([]);

  // Fetch flows list
  const fetchFlows = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get('/api/v1/agent-flows');
      if (res.data.data) setFlows(res.data.data);
    } catch (err) {
      console.error('Failed to fetch flows:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch supporting data
  const fetchSupportData = useCallback(async () => {
    try {
      const [agentRes, routingRes] = await Promise.all([
        axios.get('/api/v1/agents?agent_type=samurai'),
        axios.get('/api/v1/model-routing-profiles'),
      ]);
      if (agentRes.data.data) setAgents(agentRes.data.data);
      if (routingRes.data.data) setRoutingProfiles(routingRes.data.data);
    } catch (err) {
      console.error('Failed to fetch support data:', err);
    }
  }, []);

  useEffect(() => {
    fetchFlows();
    fetchSupportData();
  }, [fetchFlows, fetchSupportData]);

  // Load a specific flow
  const loadFlow = useCallback(async (flowId: string) => {
    try {
      const res = await axios.get(`/api/v1/agent-flows/${flowId}`);
      if (res.data.data) setActiveFlow(res.data.data);
    } catch (err) {
      console.error('Failed to load flow:', err);
    }
  }, []);

  // Create new flow
  const handleCreate = useCallback(async (name: string, description: string, triggerType: string) => {
    try {
      const res = await axios.post('/api/v1/agent-flows', { name, description, trigger_type: triggerType });
      if (res.data.data) {
        setShowCreateModal(false);
        setActiveFlow(res.data.data);
        fetchFlows();
      }
    } catch (err) {
      console.error('Failed to create flow:', err);
    }
  }, [fetchFlows]);

  // Create from template
  const handleCreateFromTemplate = useCallback(async (templateId: string) => {
    try {
      const res = await axios.post('/api/v1/agent-flows/from-template', { template_id: templateId });
      if (res.data.data) {
        setShowCreateModal(false);
        // Re-fetch the full flow to get nodes/edges (the create response doesn't include them)
        const flowId = res.data.data.id;
        const fullRes = await axios.get(`/api/v1/agent-flows/${flowId}`);
        if (fullRes.data.data) {
          setActiveFlow(fullRes.data.data);
        } else {
          setActiveFlow(res.data.data);
        }
        fetchFlows();
      }
    } catch (err) {
      console.error('Failed to create flow from template:', err);
    }
  }, [fetchFlows]);

  // Delete flow
  const handleDelete = useCallback(async (flowId: string) => {
    if (!confirm('Delete this Agent Flow?')) return;
    try {
      await axios.delete(`/api/v1/agent-flows/${flowId}`);
      fetchFlows();
    } catch (err) {
      console.error('Failed to delete flow:', err);
    }
  }, [fetchFlows]);

  // Duplicate flow
  const handleDuplicate = useCallback(async (flowId: string) => {
    try {
      await axios.post(`/api/v1/agent-flows/${flowId}/duplicate`);
      fetchFlows();
    } catch (err) {
      console.error('Failed to duplicate flow:', err);
    }
  }, [fetchFlows]);

  // Canvas view
  if (activeFlow) {
    return (
      <ReactFlowProvider>
        <AgentFlowCanvas
          key={activeFlow.id}
          flow={activeFlow}
          onBack={() => { setActiveFlow(null); fetchFlows(); }}
          onFlowUpdate={fetchFlows}
          agents={agents}
          routingProfiles={routingProfiles}
        />
      </ReactFlowProvider>
    );
  }

  // List view
  return (
    <>
      <FlowListView
        flows={flows}
        loading={loading}
        onSelect={loadFlow}
        onCreate={() => setShowCreateModal(true)}
        onDelete={handleDelete}
        onDuplicate={handleDuplicate}
        onRefresh={fetchFlows}
      />

      {showCreateModal && (
        <CreateFlowModal
          onClose={() => setShowCreateModal(false)}
          onCreate={handleCreate}
          onCreateFromTemplate={handleCreateFromTemplate}
        />
      )}
    </>
  );
};
