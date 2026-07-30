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
  Settings,
  Layers3,
  Network,
  BookmarkPlus,
  Power,
  Code2,
  Square,
  CheckSquare2,
} from 'lucide-react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { cn } from '../lib/utils';
import { logSamuraiDiagnostic } from '../lib/samuraiDiagnostics';
import { useTemplateCatalog } from '../i18n/templateCatalog';


// ═══════════════════════════════════════════════════════════════
// TYPE DEFINITIONS
// ═══════════════════════════════════════════════════════════════

export interface AgentFlowData {
  id: string;
  name: string;
  description: string | null;
  status: string;
  trigger_type: string;
  schedule_config: Record<string, any>;
  viewport: { x: number; y: number; zoom: number };
  version: number;
  flow_type: string;
  risk_tier: string;
  allow_as_subflow: boolean;
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

interface OutputMemoryInfusionConfig {
  enabled?: boolean;
  memory_type?: string;
  importance?: number;
  decay_type?: string;
  tags?: string[];
  title_template?: string;
  content_fields?: string[];
  redact_sensitive?: boolean;
  on_missing_field?: string;
  max_content_length?: number;
  store_on?: string;
  deduplication?: {
    mode?: string;
    semantic_threshold?: number;
  };
}

export interface FlowListItem {
  id: string;
  name: string;
  description: string | null;
  status: string;
  trigger_type: string;
  version: number;
  flow_type: string;
  risk_tier: string;
  allow_as_subflow: boolean;
  created_at: string;
  updated_at: string;
}

interface StackStepRunData {
  id: string;
  step_id: string;
  name: string;
  status: string;
  model_used: string | null;
  retry_count: number;
  max_retries: number;
  verification_status: string;
  flow_run_id: string | null;
  error_json: Record<string, any>;
}

interface StackRunData {
  id: string;
  stack_id: string | null;
  mode: string;
  status: string;
  objective: string;
  posture: string;
  model_profile: string;
  current_step_id: string | null;
  completed_steps: string[];
  pending_steps: string[];
  failed_steps: string[];
  approval_events: any[];
  output_publication: string;
  final_summary: Record<string, any>;
  published_output: Record<string, any>;
  created_at: string;
  steps: StackStepRunData[];
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
  { type: 'email_read',      label: 'Email Read',       icon: Mail,      color: '#f472b6', desc: 'Fetch governed inbox summaries' },
  { type: 'calendar_read',   label: 'Calendar Read',    icon: Calendar,  color: '#818cf8', desc: 'Fetch governed calendar events' },
  { type: 'coding',          label: 'Coding',           icon: Code2,     color: '#14b8a6', desc: 'Governed IDE and programming memory' },
  { type: 'shogun_approval', label: 'Shogun Approval',  icon: Shield,    color: '#4a8cc7', desc: 'Approval gate' },
  { type: 'logic',           label: 'Logic / Decision', icon: GitBranch, color: '#a78bfa', desc: 'Branching logic' },
  { type: 'input',           label: 'Input',            icon: LogIn,     color: '#22c55e', desc: 'Workflow start point' },
  { type: 'output',          label: 'Output',           icon: LogOut,    color: '#f97316', desc: 'Final delivery' },
  { type: 'mado_browser',    label: 'Mado Browser',     icon: Globe,     color: '#06b6d4', desc: 'Browser automation' },
  { type: 'email_send',      label: 'Email Send',       icon: Mail,      color: '#e879a8', desc: 'Send email via SMTP' },
  { type: 'channel_send',    label: 'Telegram / Teams', icon: MessageSquare, color: '#38bdf8', desc: 'Send an operator message' },
  { type: 'workspace',       label: 'Workspace',        icon: FolderOpen, color: '#f59e0b', desc: 'File operations' },
  { type: 'office',          label: 'Office',           icon: FileSpreadsheet, color: '#10b981', desc: 'Office documents' },
  { type: 'subflow',         label: 'Subflow',          icon: Layers3, color: '#8b5cf6', desc: 'Run a reusable child flow' },
  { type: 'stack_orchestrator', label: 'Stack Orchestrator', icon: Network, color: '#c084fc', desc: 'Supervise long-running Agent Stacks' },
] as const;


// ═══════════════════════════════════════════════════════════════
// CUSTOM NODES
// ═══════════════════════════════════════════════════════════════

const nodeColors: Record<string, string> = {
  samurai: '#d4a017',
  email_read: '#f472b6',
  calendar_read: '#818cf8',
  coding: '#14b8a6',
  shogun_approval: '#4a8cc7',
  logic: '#a78bfa',
  input: '#22c55e',
  output: '#f97316',
  mado_browser: '#06b6d4',
  email_send: '#e879a8',
  channel_send: '#38bdf8',
  workspace: '#f59e0b',
  office: '#10b981',
  subflow: '#8b5cf6',
  stack_orchestrator: '#c084fc',
};

const nodeIcons: Record<string, React.ElementType> = {
  samurai: Users,
  email_read: Mail,
  calendar_read: Calendar,
  coding: Code2,
  shogun_approval: Shield,
  logic: GitBranch,
  input: LogIn,
  output: LogOut,
  mado_browser: Globe,
  email_send: Mail,
  channel_send: MessageSquare,
  workspace: FolderOpen,
  office: FileSpreadsheet,
  subflow: Layers3,
  stack_orchestrator: Network,
};

function isInspectorInteractiveTarget(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && Boolean(
    target.closest('button, input, textarea, select, a, [role="button"], .nodrag, .nowheel')
  );
}

function ExecutionTreeNode({ node }: { node: any }) {
  const statusColor = node.status === 'completed' ? '#22c55e'
    : node.status === 'failed' ? '#ef4444'
    : node.status === 'running' ? '#4a8cc7'
    : node.status === 'cancelled' ? '#7a8899'
    : '#d4a017';
  return (
    <div className="relative pl-4">
      {node.run_depth > 0 && <div className="absolute left-0 top-0 h-4 w-3 border-b border-l border-[#2a3060] rounded-bl" />}
      <div className="rounded-lg border border-[#1a2040] bg-[#0e1225] p-2.5">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: statusColor }} />
            <span className="truncate text-[10px] font-bold text-[#c8d0d8]">{node.flow_name}</span>
            <span className="text-[8px] text-[#7a8899]">v{node.flow_version}</span>
          </div>
          <span className="text-[8px] font-bold uppercase" style={{ color: statusColor }}>{node.status}</span>
        </div>
        <div className="mt-1 flex gap-3 text-[8px] text-[#7a8899]">
          <span>Depth {node.run_depth}</span>
          {node.started_at && node.completed_at && (
            <span>{((parseRunTimestamp(node.completed_at).getTime() - parseRunTimestamp(node.started_at).getTime()) / 1000).toFixed(1)}s</span>
          )}
          <span className="ml-auto font-mono">{String(node.run_id).slice(0, 8)}</span>
        </div>
      </div>
      {node.children?.length > 0 && (
        <div className="mt-2 space-y-2 border-l border-[#1a2040] pl-2">
          {node.children.map((child: any) => <ExecutionTreeNode key={child.run_id} node={child} />)}
        </div>
      )}
    </div>
  );
}

function FlowNode({ id, data, selected, type }: { id: string; data: Record<string, any>; selected: boolean; type: string }) {
  const navigate = useNavigate();
  const color = nodeColors[type] || '#d4a017';
  const Icon = nodeIcons[type] || Users;
  const config: Record<string, any> = data.config || {};
  const resultContext = useContext(OutputResultViewerContext);
  const authoritativeState = resultContext?.nodeStates?.[id];
  const executionStatus = authoritativeState?.status || data.execution_status;
  const executionOutput = authoritativeState?.output ?? data.execution_output ?? '';
  const executionRunId = resultContext?.runId || data.execution_run_id || null;
  const isRunning = executionStatus === 'running';
  const openFailureLog = (event: React.SyntheticEvent) => {
    event.preventDefault();
    event.stopPropagation();
    const params = new URLSearchParams({
      event_type: 'agent_flow.node.failed',
      node_id: id,
    });
    if (authoritativeState?.failure_event_id) {
      params.set('event_id', authoritativeState.failure_event_id);
    }
    if (executionRunId) {
      params.set('trace_id', executionRunId);
    }
    navigate(`/logs?${params.toString()}`);
  };

  return (
    <div
      className={cn(
        "relative min-w-[200px] max-w-[260px] rounded-lg border transition-all duration-200",
        selected
          ? "ring-2 ring-offset-1 ring-offset-[#0a0e1a] shadow-lg"
          : "shadow-md hover:shadow-lg"
      )}
      onClick={(event) => {
        if (isInspectorInteractiveTarget(event.target)) return;
        logSamuraiDiagnostic('agent_flow.node.click', {
          nodeId: id,
          type,
          label: data.label,
          selected,
        });
        data.onOpenInspector?.(id);
      }}
      onPointerUp={(event) => {
        if (isInspectorInteractiveTarget(event.target)) return;
        logSamuraiDiagnostic('agent_flow.node.pointer_up', {
          nodeId: id,
          type,
          label: data.label,
          selected,
        });
        data.onOpenInspector?.(id);
      }}
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
        <button
          type="button"
          title="Node Properties"
          aria-label={`Open properties for ${data.label || 'node'}`}
          className="nodrag nopan shrink-0 w-6 h-6 rounded border border-[#1a2040] bg-[#0a0e1a] text-[#7a8899] hover:text-[#d4a017] hover:border-[#d4a017]/50 flex items-center justify-center transition-colors"
          onPointerDown={(event) => {
            event.preventDefault();
            event.stopPropagation();
          }}
          onPointerUp={(event) => {
            event.preventDefault();
            event.stopPropagation();
            logSamuraiDiagnostic('agent_flow.node.properties_button.pointer_up', {
              nodeId: id,
              type,
              label: data.label,
            });
            data.onOpenInspector?.(id);
          }}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            logSamuraiDiagnostic('agent_flow.node.properties_button.click', {
              nodeId: id,
              type,
              label: data.label,
            });
            data.onOpenInspector?.(id);
          }}
        >
          <Settings className="w-3 h-3" />
        </button>
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
        {type === 'email_read' && (
          <>
            <div className="flex items-center gap-1">
              <Mail className="w-2.5 h-2.5 text-[#f472b6]/70" />
              <span className="text-[8px] font-bold text-[#f472b6]/80 uppercase">
                {config.unread_only !== false ? 'Unread' : 'Recent'} · {config.folder || 'INBOX'}
              </span>
            </div>
            <p className="text-[9px] text-[#7a8899]">Up to {config.per_page || 10} message summaries</p>
          </>
        )}
        {type === 'calendar_read' && (
          <>
            <div className="flex items-center gap-1">
              <Calendar className="w-2.5 h-2.5 text-[#818cf8]/70" />
              <span className="text-[8px] font-bold text-[#818cf8]/80 uppercase">
                {config.start_date && config.end_date ? 'Explicit range' : `${config.days_ahead || 1} day window`}
              </span>
            </div>
            <p className="text-[9px] text-[#7a8899]">Structured event summaries</p>
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
        {type === 'coding' && (
          <>
            <div className="flex items-center gap-1">
              <Code2 className="w-2.5 h-2.5 text-[#14b8a6]/70" />
              <span className="text-[8px] font-bold text-[#14b8a6]/80 uppercase">
                {config.action || 'analyze'}
              </span>
            </div>
            <p className="text-[9px] text-[#7a8899] line-clamp-2">
              {config.task_description || config.command || 'Configure coding task...'}
            </p>
            {config.recall_memory !== false && (
              <span className="text-[8px] text-[#14b8a6]/60">Programming memory enabled</span>
            )}
          </>
        )}
        {type === 'subflow' && (
          <>
            <div className="flex items-center gap-1">
              <Layers3 className="w-2.5 h-2.5 text-[#8b5cf6]/70" />
              <span className="text-[8px] font-bold text-[#8b5cf6]/80 uppercase">
                {config.child_flow_name || 'Select child flow'}
              </span>
            </div>
            <p className="text-[8px] text-[#7a8899]">
              {config.child_flow_version_mode || 'locked'}
              {config.child_flow_version ? ` · v${config.child_flow_version}` : ''}
              {' · '}{config.on_failure || 'fail_parent'}
            </p>
          </>
        )}
        {type === 'stack_orchestrator' && (
          <>
            <div className="flex items-center gap-1">
              <Network className="w-2.5 h-2.5 text-[#c084fc]/80" />
              <span className="text-[8px] font-bold text-[#c084fc] uppercase">
                {config.mode || 'selected_stack'}
              </span>
            </div>
            <p className="text-[9px] text-[#7a8899] line-clamp-2">
              {config.objective || 'Configure a governed long-running objective'}
            </p>
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
            <button
              type="button"
              title="Open exact failure log"
              aria-label={`Open failure log for ${data.label || 'node'}`}
              className="nodrag nopan w-5 h-5 rounded-full bg-[#ef4444] hover:bg-[#dc2626] flex items-center justify-center shadow-[0_0_8px_rgba(239,68,68,0.4)] focus:outline-none focus:ring-2 focus:ring-white/70"
              onPointerDown={(event) => event.stopPropagation()}
              onPointerUp={openFailureLog}
              onClick={(event) => {
                // Keyboard activation has no preceding pointer event.
                if (event.detail === 0) openFailureLog(event);
              }}
            >
              <XCircle className="w-3 h-3 text-white" />
            </button>
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
  email_read: FlowNode,
  calendar_read: FlowNode,
  coding: FlowNode,
  shogun_approval: FlowNode,
  logic: FlowNode,
  input: FlowNode,
  output: FlowNode,
  mado_browser: FlowNode,
  email_send: FlowNode,
  channel_send: FlowNode,
  workspace: FlowNode,
  office: FlowNode,
  subflow: FlowNode,
  stack_orchestrator: FlowNode,
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
    : 'Select the destination folder; the filename is configured below';
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

      {!isReadAction && (
        <div className="space-y-1.5">
          <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Output Filename</label>
          <input
            type="text"
            value={config.output_filename || ''}
            onChange={(e) => updateConfig('output_filename', e.target.value)}
            className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#10b981] transition-colors outline-none"
            placeholder={action.startsWith('excel') ? 'output.xlsx' : action.startsWith('word') ? 'output.docx' : 'output.pptx'}
          />
          <p className="text-[8px] text-[#7a8899]/60">A matching extension is added automatically if omitted.</p>
        </div>
      )}

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

function JsonConfigEditor({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: Record<string, any>;
  onChange: (value: Record<string, any>) => void;
  placeholder: string;
}) {
  const [draft, setDraft] = useState(JSON.stringify(value || {}, null, 2));
  const [error, setError] = useState('');

  useEffect(() => setDraft(JSON.stringify(value || {}, null, 2)), [value]);

  const commit = () => {
    try {
      const parsed = JSON.parse(draft || '{}');
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error('Use a JSON object');
      onChange(parsed);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid JSON');
    }
  };

  return (
    <div className="space-y-1.5">
      <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">{label}</label>
      <textarea
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        rows={5}
        spellCheck={false}
        placeholder={placeholder}
        className={cn(
          "w-full bg-[#0a0e1a] border rounded-lg p-2 text-[10px] font-mono text-[#c8d0d8] outline-none resize-y",
          error ? "border-[#ef4444]" : "border-[#1a2040] focus:border-[#8b5cf6]",
        )}
      />
      {error && <p className="text-[8px] text-[#ef4444]">{error}</p>}
    </div>
  );
}


function NodeInspector({
  node,
  onUpdate,
  onClose,
  agents,
  routingProfiles,
  flowId,
  flows,
}: {
  node: Node;
  onUpdate: (id: string, data: any) => void;
  onClose: () => void;
  agents: any[];
  routingProfiles: any[];
  flowId: string;
  flows: FlowListItem[];
}) {
  const nodeType = node.type || 'samurai';
  const color = nodeColors[nodeType] || '#d4a017';
  const Icon = nodeIcons[nodeType] || Users;
  const config: Record<string, any> = (node.data as Record<string, any>)?.config || {};
  const samuraiToolContract = [
    config.task_description,
    ...(Array.isArray(config.required_tools) ? config.required_tools : []),
    ...(Array.isArray(config.allowed_tools) ? config.allowed_tools : []),
  ].join(' ');
  const governedSamuraiReadTools = ['fetch_inbox', 'list_calendar_events'].filter((tool) =>
    new RegExp(`\\b${tool}\\b`, 'i').test(samuraiToolContract),
  );
  const memoryInfusion = (config.memory_infusion || {}) as OutputMemoryInfusionConfig;
  const [subflowValidation, setSubflowValidation] = useState<{valid: boolean; warnings: string[]; errors: string[]} | null>(null);
  const [validatingSubflow, setValidatingSubflow] = useState(false);

  const updateConfig = (key: string, value: any) => {
    onUpdate(node.id, {
      ...node.data,
      config: { ...config, [key]: value },
    });
  };

  const updateLabel = (label: string) => {
    onUpdate(node.id, { ...node.data, label });
  };

  const updateMemoryInfusion = (key: keyof OutputMemoryInfusionConfig, value: unknown) => {
    updateConfig('memory_infusion', { ...memoryInfusion, [key]: value });
  };

  const validateSelectedSubflow = async () => {
    if (!config.child_flow_id) return;
    setValidatingSubflow(true);
    try {
      const response = await axios.post(`/api/v1/agent-flows/${flowId}/validate-subflow`, {
        child_flow_id: config.child_flow_id,
        child_flow_version_mode: config.child_flow_version_mode || 'locked',
        child_flow_version: config.child_flow_version || null,
      });
      setSubflowValidation(response.data?.data || null);
    } catch (err) {
      setSubflowValidation({
        valid: false,
        warnings: [],
        errors: [axios.isAxiosError(err) ? err.response?.data?.detail || err.message : 'Validation failed'],
      });
    } finally {
      setValidatingSubflow(false);
    }
  };

  return (
    <div className="w-full bg-[#050508] border-l border-[#1a2040] h-full flex flex-col overflow-hidden">
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

            {governedSamuraiReadTools.length > 0 && (
              <div className="rounded-lg border border-[#22c55e]/30 bg-[#22c55e]/10 p-2.5">
                <p className="text-[9px] font-bold text-[#22c55e]">Governed read access enabled.</p>
                <p className="mt-1 text-[8px] leading-relaxed text-[#86efac]">
                  The flow runtime will fetch the requested email/calendar data under ToolGate policy and pass it to this Samurai for compilation.
                </p>
              </div>
            )}

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
                    <strong>Note:</strong> Saving a scheduled trigger activates the flow and registers it with the job scheduler.
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
            <div className="rounded-lg border border-[#f97316]/25 bg-[#f97316]/5 p-3 space-y-3">
              <label className="flex items-center justify-between gap-3 cursor-pointer">
                <span>
                  <span className="block text-[9px] font-bold text-[#f97316] uppercase tracking-widest">Memory Infusion</span>
                  <span className="block text-[8px] text-[#7a8899] mt-1">Store this output mechanically in Archives</span>
                </span>
                <input
                  type="checkbox"
                  checked={memoryInfusion.enabled === true}
                  onChange={(event) => updateConfig('memory_infusion', {
                    memory_type: 'episodic', importance: 0.8, decay_type: 'sticky',
                    tags: ['auto-stored', 'flow-output'],
                    title_template: '{flow_name} - {timestamp}',
                    content_fields: ['result', 'summary'], redact_sensitive: true,
                    on_missing_field: 'store_available', max_content_length: 12000,
                    store_on: 'success',
                    deduplication: { mode: 'exact', semantic_threshold: 0.92 },
                    ...memoryInfusion, enabled: event.target.checked,
                  })}
                  className="accent-[#f97316]"
                />
              </label>

              {memoryInfusion.enabled === true && (
                <div className="space-y-3 border-t border-[#f97316]/15 pt-3">
                  <div className="grid grid-cols-2 gap-2">
                    <label className="space-y-1 text-[8px] uppercase text-[#7a8899]">Memory type
                      <select value={memoryInfusion.memory_type || 'episodic'} onChange={(event) => updateMemoryInfusion('memory_type', event.target.value)} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded p-2 text-[10px] text-[#c8d0d8] outline-none">
                        {['episodic', 'semantic', 'procedural', 'persona'].map((value) => <option key={value}>{value}</option>)}
                      </select>
                    </label>
                    <label className="space-y-1 text-[8px] uppercase text-[#7a8899]">Decay
                      <select value={memoryInfusion.decay_type || 'sticky'} onChange={(event) => updateMemoryInfusion('decay_type', event.target.value)} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded p-2 text-[10px] text-[#c8d0d8] outline-none">
                        {['fast', 'medium', 'slow', 'sticky', 'pinned'].map((value) => <option key={value}>{value}</option>)}
                      </select>
                    </label>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <label className="space-y-1 text-[8px] uppercase text-[#7a8899]">Importance
                      <input type="number" min={0} max={1} step={0.05} value={memoryInfusion.importance ?? 0.8} onChange={(event) => updateMemoryInfusion('importance', Number(event.target.value))} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded p-2 text-[10px] text-[#c8d0d8] outline-none" />
                    </label>
                    <label className="space-y-1 text-[8px] uppercase text-[#7a8899]">Store on
                      <select value={memoryInfusion.store_on || 'success'} onChange={(event) => updateMemoryInfusion('store_on', event.target.value)} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded p-2 text-[10px] text-[#c8d0d8] outline-none">
                        <option value="success">Success</option><option value="partial">Partial</option><option value="always">Always</option>
                      </select>
                    </label>
                  </div>
                  <label className="block space-y-1 text-[8px] uppercase text-[#7a8899]">Title template
                    <input value={memoryInfusion.title_template || '{flow_name} - {timestamp}'} onChange={(event) => updateMemoryInfusion('title_template', event.target.value)} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded p-2 text-[10px] normal-case text-[#c8d0d8] outline-none" />
                  </label>
                  <label className="block space-y-1 text-[8px] uppercase text-[#7a8899]">Content fields
                    <input value={(memoryInfusion.content_fields || ['result', 'summary']).join(', ')} onChange={(event) => updateMemoryInfusion('content_fields', event.target.value.split(',').map((value) => value.trim()).filter(Boolean))} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded p-2 text-[10px] normal-case text-[#c8d0d8] outline-none" />
                  </label>
                  <label className="block space-y-1 text-[8px] uppercase text-[#7a8899]">Tags
                    <input value={(memoryInfusion.tags || ['auto-stored', 'flow-output']).join(', ')} onChange={(event) => updateMemoryInfusion('tags', event.target.value.split(',').map((value) => value.trim()).filter(Boolean))} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded p-2 text-[10px] normal-case text-[#c8d0d8] outline-none" />
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    <label className="space-y-1 text-[8px] uppercase text-[#7a8899]">Missing fields
                      <select value={memoryInfusion.on_missing_field || 'store_available'} onChange={(event) => updateMemoryInfusion('on_missing_field', event.target.value)} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded p-2 text-[10px] text-[#c8d0d8] outline-none">
                        <option value="store_available">Store available</option><option value="skip">Skip memory</option><option value="fail">Fail node</option>
                      </select>
                    </label>
                    <label className="space-y-1 text-[8px] uppercase text-[#7a8899]">Max characters
                      <input type="number" min={256} max={100000} value={memoryInfusion.max_content_length || 12000} onChange={(event) => updateMemoryInfusion('max_content_length', Number(event.target.value))} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded p-2 text-[10px] text-[#c8d0d8] outline-none" />
                    </label>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <label className="space-y-1 text-[8px] uppercase text-[#7a8899]">Deduplication
                      <select value={memoryInfusion.deduplication?.mode || 'exact'} onChange={(event) => updateMemoryInfusion('deduplication', { semantic_threshold: 0.92, ...memoryInfusion.deduplication, mode: event.target.value })} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded p-2 text-[10px] text-[#c8d0d8] outline-none">
                        <option value="none">None</option><option value="exact">Exact hash</option><option value="semantic">Semantic</option>
                      </select>
                    </label>
                    {memoryInfusion.deduplication?.mode === 'semantic' && (
                      <label className="space-y-1 text-[8px] uppercase text-[#7a8899]">Similarity
                        <input type="number" min={0.5} max={1} step={0.01} value={memoryInfusion.deduplication?.semantic_threshold ?? 0.92} onChange={(event) => updateMemoryInfusion('deduplication', { ...memoryInfusion.deduplication, mode: 'semantic', semantic_threshold: Number(event.target.value) })} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded p-2 text-[10px] text-[#c8d0d8] outline-none" />
                      </label>
                    )}
                  </div>
                  <label className="flex items-center gap-2 text-[9px] text-[#c8d0d8] cursor-pointer">
                    <input type="checkbox" checked={memoryInfusion.redact_sensitive !== false} onChange={(event) => updateMemoryInfusion('redact_sensitive', event.target.checked)} className="accent-[#f97316]" />
                    Redact credentials and secrets before storage
                  </label>
                </div>
              )}
            </div>
          </>
        )}

        {/* Coding node fields */}
        {nodeType === 'coding' && (
          <>
            <div className="rounded-lg border border-[#14b8a6]/20 bg-[#14b8a6]/5 p-2.5 text-[9px] leading-relaxed text-[#8adbd1]">
              Coding nodes use governed IDE Mode. Workspace actions require Campaign or Ronin posture,
              an approved workspace, and the matching IDE permissions.
            </div>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Action</label>
              <select
                value={config.action || 'analyze'}
                onChange={(e) => updateConfig('action', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#14b8a6] outline-none"
              >
                <option value="analyze">Analyze / Plan</option>
                <option value="list_files">List Repository Files</option>
                <option value="search">Search Code</option>
                <option value="read_file">Read File</option>
                <option value="apply_patch">Write / Replace File</option>
                <option value="run_task">Run Test / Build Task</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Task Description</label>
              <textarea
                value={config.task_description || ''}
                onChange={(e) => updateConfig('task_description', e.target.value)}
                rows={3}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#14b8a6] outline-none resize-y"
                placeholder="Describe the coding objective and acceptance criteria..."
              />
            </div>
            {config.action !== 'analyze' && (
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Approved Workspace ID</label>
                <input
                  value={config.workspace_id || ''}
                  onChange={(e) => updateConfig('workspace_id', e.target.value)}
                  className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#14b8a6] outline-none"
                  placeholder="VS Code workspace UUID"
                />
              </div>
            )}
            {(config.action === 'read_file' || config.action === 'apply_patch') && (
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Workspace-relative Path</label>
                <input
                  value={config.path || ''}
                  onChange={(e) => updateConfig('path', e.target.value)}
                  className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#14b8a6] outline-none font-mono"
                  placeholder="src/module.py"
                />
              </div>
            )}
            {config.action === 'search' && (
              <div className="grid grid-cols-2 gap-2">
                <input value={config.query || ''} onChange={(e) => updateConfig('query', e.target.value)}
                  className="bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] outline-none" placeholder="Search text" />
                <input value={config.file_glob || '*'} onChange={(e) => updateConfig('file_glob', e.target.value)}
                  className="bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] outline-none" placeholder="*.py" />
              </div>
            )}
            {config.action === 'apply_patch' && (
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Complete File Content</label>
                <textarea value={config.content_template || ''} onChange={(e) => updateConfig('content_template', e.target.value)}
                  rows={7} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-[10px] text-[#c8d0d8] font-mono outline-none"
                  placeholder="Use {{context}} to insert predecessor output." />
              </div>
            )}
            {config.action === 'run_task' && (
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Allowlisted Command</label>
                <input value={config.command || ''} onChange={(e) => updateConfig('command', e.target.value)}
                  className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] font-mono outline-none"
                  placeholder="pytest tests/test_feature.py" />
              </div>
            )}
            <label className="flex items-center justify-between rounded-lg border border-[#1a2040] bg-[#0a0e1a] p-2.5 text-[10px] text-[#c8d0d8]">
              Recall project programming memory
              <input type="checkbox" checked={config.recall_memory !== false}
                onChange={(e) => updateConfig('recall_memory', e.target.checked)} />
            </label>
            {config.action === 'run_task' && (
              <label className="flex items-center justify-between rounded-lg border border-[#1a2040] bg-[#0a0e1a] p-2.5 text-[10px] text-[#c8d0d8]">
                Remember successful verified result
                <input type="checkbox" checked={Boolean(config.remember_on_success)}
                  onChange={(e) => updateConfig('remember_on_success', e.target.checked)} />
              </label>
            )}
          </>
        )}

        {/* Flow Stacking / Subflow fields */}
        {nodeType === 'subflow' && (
          <>
            <div className="rounded-lg border border-[#8b5cf6]/25 bg-[#8b5cf6]/5 p-3">
              <p className="text-[9px] font-bold uppercase tracking-widest text-[#8b5cf6]">Governed child execution</p>
              <p className="mt-1 text-[9px] leading-relaxed text-[#7a8899]">
                The child inherits this run's posture, permission ceiling, audit context, and cancellation state.
              </p>
            </div>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Child Flow</label>
              <select
                value={config.child_flow_id || ''}
                onChange={(event) => {
                  const child = flows.find((item) => item.id === event.target.value);
                  onUpdate(node.id, {
                    ...node.data,
                    config: {
                      ...config,
                      child_flow_id: child?.id || '',
                      child_flow_name: child?.name || '',
                      child_flow_version: child?.version || null,
                      child_flow_version_mode: config.child_flow_version_mode || 'locked',
                      execution_mode: 'sequential',
                      timeout_seconds: config.timeout_seconds || 600,
                      on_failure: config.on_failure || 'fail_parent',
                    },
                  });
                  setSubflowValidation(null);
                }}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#8b5cf6] outline-none"
              >
                <option value="">Select a reusable flow...</option>
                {flows.filter((item) => item.id !== flowId).map((item) => (
                  <option key={item.id} value={item.id} disabled={!item.allow_as_subflow}>
                    {item.name} · v{item.version} · {item.risk_tier}{!item.allow_as_subflow ? ' · blocked' : ''}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Version</label>
                <select
                  value={config.child_flow_version_mode || 'locked'}
                  onChange={(event) => updateConfig('child_flow_version_mode', event.target.value)}
                  className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#8b5cf6] outline-none"
                >
                  <option value="locked">Locked</option>
                  <option value="latest">Latest</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Timeout</label>
                <input
                  type="number"
                  min={1}
                  max={86400}
                  value={config.timeout_seconds || 600}
                  onChange={(event) => updateConfig('timeout_seconds', Number(event.target.value))}
                  className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#8b5cf6] outline-none"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Failure Policy</label>
              <select
                value={config.on_failure || 'fail_parent'}
                onChange={(event) => updateConfig('on_failure', event.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#8b5cf6] outline-none"
              >
                <option value="fail_parent">Fail parent</option>
                <option value="continue_with_error">Continue with error</option>
                <option value="route_to_error">Route error downstream</option>
              </select>
            </div>
            <JsonConfigEditor
              label="Input Mapping"
              value={config.input_mapping || {}}
              onChange={(value) => updateConfig('input_mapping', value)}
              placeholder={'{"topic": "{{input.topic}}"}'}
            />
            <JsonConfigEditor
              label="Output Mapping"
              value={config.output_mapping || {}}
              onChange={(value) => updateConfig('output_mapping', value)}
              placeholder={'{"summary": "{{output.summary}}"}'}
            />
            <button
              type="button"
              disabled={!config.child_flow_id || validatingSubflow}
              onClick={validateSelectedSubflow}
              className="w-full flex items-center justify-center gap-2 rounded-lg border border-[#8b5cf6]/30 bg-[#8b5cf6]/10 px-3 py-2 text-[9px] font-bold uppercase tracking-widest text-[#a78bfa] disabled:opacity-40"
            >
              {validatingSubflow ? <Loader2 className="w-3 h-3 animate-spin" /> : <Shield className="w-3 h-3" />}
              Validate safety & governance
            </button>
            {subflowValidation && (
              <div className={cn(
                "rounded-lg border p-2.5 text-[9px]",
                subflowValidation.valid
                  ? "border-[#22c55e]/25 bg-[#22c55e]/5 text-[#22c55e]"
                  : "border-[#ef4444]/25 bg-[#ef4444]/5 text-[#ef4444]",
              )}>
                <p className="font-bold uppercase tracking-wider">
                  {subflowValidation.valid ? 'Reference is safe' : 'Reference is blocked'}
                </p>
                {[...subflowValidation.warnings, ...subflowValidation.errors].map((message, index) => (
                  <p key={index} className="mt-1 opacity-80">{message}</p>
                ))}
              </div>
            )}
          </>
        )}

        {/* Stack Orchestrator control-node fields */}
        {nodeType === 'stack_orchestrator' && (
          <>
            <div className="rounded-lg border border-[#c084fc]/25 bg-[#c084fc]/5 p-3">
              <p className="text-[9px] font-bold uppercase tracking-widest text-[#c084fc]">Runtime control layer</p>
              <p className="mt-1 text-[9px] leading-relaxed text-[#7a8899]">
                Supervises Agent Stacks through persistent state, checkpoints, verification, retries and inherited posture permissions. Concrete work remains in Agent Flow.
              </p>
            </div>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Execution Mode</label>
              <select value={config.mode || 'selected_stack'} onChange={(event) => updateConfig('mode', event.target.value)} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#c084fc] outline-none">
                <option value="selected_stack">Selected Agent Stack</option>
                <option value="template">Stack Template</option>
                <option value="goal_driven">Goal-driven plan</option>
              </select>
            </div>
            {(config.mode || 'selected_stack') === 'selected_stack' && (
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Agent Stack</label>
                <select value={config.selected_stack_id || ''} onChange={(event) => updateConfig('selected_stack_id', event.target.value)} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#c084fc] outline-none">
                  <option value="">Select an Agent Stack...</option>
                  {flows.filter((item) => item.id !== flowId).map((item) => (
                    <option key={item.id} value={item.id}>{item.name} · {item.flow_type} · {item.risk_tier}</option>
                  ))}
                </select>
              </div>
            )}
            {config.mode === 'template' && (
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Stack Template ID</label>
                <input value={config.stack_template_id || ''} onChange={(event) => updateConfig('stack_template_id', event.target.value)} placeholder="bug-fix-stack" className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#c084fc] outline-none" />
              </div>
            )}
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Objective</label>
              <textarea value={config.objective || ''} onChange={(event) => updateConfig('objective', event.target.value)} rows={3} placeholder="Describe the long-running outcome..." className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#c084fc] outline-none resize-y" />
            </div>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Success Criteria</label>
              <textarea value={(config.success_criteria || []).join('\n')} onChange={(event) => updateConfig('success_criteria', event.target.value.split('\n').map((item) => item.trim()).filter(Boolean))} rows={3} placeholder={'One criterion per line\nTests pass\nArtifacts verified'} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#c084fc] outline-none resize-y" />
            </div>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Allowed Tools</label>
              <input value={(config.allowed_tools || []).join(', ')} onChange={(event) => updateConfig('allowed_tools', event.target.value.split(',').map((item) => item.trim()).filter(Boolean))} placeholder="workspace, ide, mado" className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#c084fc] outline-none" />
              <p className="text-[8px] text-[#555]">This list can only narrow the active posture. IDE and Ronin permissions must also be explicitly enabled.</p>
            </div>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Model Routing Profile</label>
              <select value={config.model_routing_profile || 'balanced'} onChange={(event) => updateConfig('model_routing_profile', event.target.value)} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#c084fc] outline-none">
                <option value="balanced">Balanced</option>
                {routingProfiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Max Runtime (min)</label>
                <input type="number" min={1} max={1440} value={config.max_runtime_minutes || 60} onChange={(event) => updateConfig('max_runtime_minutes', Number(event.target.value))} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] outline-none" />
              </div>
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Max Iterations</label>
                <input type="number" min={1} max={500} value={config.max_iterations || 50} onChange={(event) => updateConfig('max_iterations', Number(event.target.value))} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] outline-none" />
              </div>
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Retries / Step</label>
                <input type="number" min={0} max={10} value={config.max_retry_attempts_per_step ?? 2} onChange={(event) => updateConfig('max_retry_attempts_per_step', Number(event.target.value))} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] outline-none" />
              </div>
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Checkpoint</label>
                <select value={config.checkpoint_frequency || 'after_each_step'} onChange={(event) => updateConfig('checkpoint_frequency', event.target.value)} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] outline-none">
                  <option value="after_each_step">Each step</option><option value="after_each_subflow">Each subflow</option><option value="timed">Timed</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <label className="flex items-center gap-2 rounded-lg border border-[#1a2040] p-2 text-[9px] text-[#c8d0d8]"><input type="checkbox" checked={config.context_compaction !== false} onChange={(event) => updateConfig('context_compaction', event.target.checked)} /> Context compaction</label>
              <label className="flex items-center gap-2 rounded-lg border border-[#1a2040] p-2 text-[9px] text-[#c8d0d8]"><input type="checkbox" checked={config.verification_required !== false} onChange={(event) => updateConfig('verification_required', event.target.checked)} /> Verification required</label>
            </div>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Approval Policy</label>
              <select value={config.approval_policy || 'inherited'} onChange={(event) => updateConfig('approval_policy', event.target.value)} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] outline-none">
                <option value="inherited">Inherited</option><option value="step_based">Step based</option><option value="always_required_for_high_risk">Always for high risk</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5"><label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Failure Policy</label><select value={config.failure_policy || 'pause'} onChange={(event) => updateConfig('failure_policy', event.target.value)} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] outline-none"><option value="pause">Pause</option><option value="retry">Retry</option><option value="continue_with_error">Continue with error</option><option value="fail_stack">Fail stack</option></select></div>
              <div className="space-y-1.5"><label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Artifacts</label><select value={config.artifact_policy || 'retain_all'} onChange={(event) => updateConfig('artifact_policy', event.target.value)} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] outline-none"><option value="retain_all">Retain all</option><option value="retain_final_only">Final only</option><option value="retain_selected">Selected</option></select></div>
            </div>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Published Output</label>
              <select value={config.output_publication || 'summary_and_final'} onChange={(event) => updateConfig('output_publication', event.target.value)} className="w-full bg-[#0a0e1a] border border-[#c084fc]/30 rounded-lg p-2 text-xs text-[#c8d0d8] outline-none">
                <option value="summary_and_final">Orchestrator summary + final Flow</option><option value="summary_only">Orchestrator summary only</option><option value="final_only">Final Flow only</option><option value="all_steps">All Flow outputs (legacy)</option>
              </select>
              <p className="text-[8px] normal-case leading-relaxed text-[#7a8899]">Intermediate results remain internal handovers and are still retained for checkpoints, verification, and audit.</p>
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

        {/* Email Read fields */}
        {nodeType === 'email_read' && (
          <>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Mail Folder</label>
              <input
                type="text"
                value={config.folder || 'INBOX'}
                onChange={(e) => updateConfig('folder', e.target.value)}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#f472b6] transition-colors outline-none"
                placeholder="INBOX"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Page</label>
                <input type="number" min={1} value={config.page || 1} onChange={(e) => updateConfig('page', Number(e.target.value))} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#f472b6] outline-none" />
              </div>
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Messages</label>
                <input type="number" min={1} max={50} value={config.per_page || 10} onChange={(e) => updateConfig('per_page', Number(e.target.value))} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#f472b6] outline-none" />
              </div>
            </div>
            <label className="flex items-center justify-between gap-3 rounded-lg border border-[#1a2040] bg-[#0a0e1a] p-2.5">
              <span className="text-[9px] font-bold uppercase tracking-widest text-[#c8d0d8]">Unread only</span>
              <input type="checkbox" checked={config.unread_only !== false} onChange={(e) => updateConfig('unread_only', e.target.checked)} className="accent-[#f472b6]" />
            </label>
            <div className="rounded-lg border border-[#f472b6]/20 bg-[#f472b6]/5 p-2.5 text-[8px] text-[#f472b6]/80">
              Read-only and governed by Torii posture plus ToolGate. Outputs structured message summaries to successor nodes.
            </div>
          </>
        )}

        {/* Calendar Read fields */}
        {nodeType === 'calendar_read' && (
          <>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Dynamic Window (days)</label>
              <input
                type="number"
                min={1}
                max={31}
                value={config.days_ahead || 1}
                onChange={(e) => updateConfig('days_ahead', Number(e.target.value))}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#818cf8] outline-none"
              />
              <p className="text-[8px] text-[#7a8899]">One day means today. Leave the explicit range empty for scheduled flows.</p>
            </div>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Explicit Start (optional)</label>
              <input type="datetime-local" value={config.start_date || ''} onChange={(e) => updateConfig('start_date', e.target.value || null)} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#818cf8] outline-none" />
            </div>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Explicit End (optional)</label>
              <input type="datetime-local" value={config.end_date || ''} onChange={(e) => updateConfig('end_date', e.target.value || null)} className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#818cf8] outline-none" />
            </div>
            <div className="rounded-lg border border-[#818cf8]/20 bg-[#818cf8]/5 p-2.5 text-[8px] text-[#818cf8]/80">
              Read-only and governed by Torii posture plus ToolGate. Outputs structured event summaries to successor nodes.
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
                Requires Mail writes to be enabled in ToolGate &gt; Comms.
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
              <label className="text-[9px] font-bold text-[#7a8899] uppercase tracking-widest">Telegram Topic Thread ID (optional)</label>
              <input
                type="number"
                min="1"
                step="1"
                value={config.message_thread_id ?? ''}
                onChange={(e) => updateConfig('message_thread_id', e.target.value === '' ? null : Number(e.target.value))}
                className="w-full bg-[#0a0e1a] border border-[#1a2040] rounded-lg p-2 text-xs text-[#c8d0d8] focus:border-[#38bdf8] transition-colors outline-none"
                placeholder="For example, 22 for the News topic"
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

export function AgentFlowCanvas({
  flow,
  onBack,
  onFlowUpdate,
  agents,
  routingProfiles,
  availableFlows,
}: {
  flow: AgentFlowData;
  onBack: () => void;
  onFlowUpdate: () => void;
  agents: any[];
  routingProfiles: any[];
  availableFlows: FlowListItem[];
}) {
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
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [flowName, setFlowName] = useState(flow.name);
  const [editingName, setEditingName] = useState(false);
  const [flowStatus, setFlowStatus] = useState(flow.status);
  const [changingStatus, setChangingStatus] = useState(false);

  useEffect(() => setFlowStatus(flow.status), [flow.id, flow.status]);

  useEffect(() => {
    logSamuraiDiagnostic('agent_flow.canvas.mount', {
      flowId: flow.id,
      flowName: flow.name,
      nodes: flow.nodes?.length || 0,
      edges: flow.edges?.length || 0,
      agents: agents.length,
      routingProfiles: routingProfiles.length,
    });
  }, [flow.id]);

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
  const [selectedRunTree, setSelectedRunTree] = useState<any | null>(null);
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
      const [resp, treeResp] = await Promise.all([
        axios.get(`/api/v1/agent-flows/runs/${runId}`),
        axios.get(`/api/v1/agent-flows/runs/${runId}/tree`),
      ]);
      const run = resp.data?.data || null;
      setSelectedRunDetails(run);
      setSelectedRunTree(treeResp.data?.data || null);
      return run;
    } catch (err) {
      console.error(err);
      setSelectedRunDetails(fallback ? {
        status: 'completed',
        trigger_type: 'manual',
        result_summary: { [fallback.label]: fallback.content },
      } : null);
      setSelectedRunTree(null);
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
    setSelectedRunTree(null);
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

  const openNodeInspector = useCallback((nodeId: string) => {
    const node = nodes.find((item) => item.id === nodeId);
    logSamuraiDiagnostic('agent_flow.inspector.open_request', {
      nodeId,
      foundNode: Boolean(node),
      type: node?.type,
      label: node?.data?.label,
      totalNodes: nodes.length,
    });
    setSelectedNodeId(nodeId);
  }, [nodes]);

  const renderedNodes = useMemo(
    () => nodes.map((node) => ({
      ...node,
      data: {
        ...node.data,
        onOpenInspector: openNodeInspector,
      },
    })),
    [nodes, openNodeInspector]
  );

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
    logSamuraiDiagnostic('agent_flow.reactflow.on_node_click', {
      nodeId: node.id,
      type: node.type,
      label: node.data?.label,
    });
    openNodeInspector(node.id);
  }, [openNodeInspector]);

  const onPaneClick = useCallback((event: React.MouseEvent) => {
    const target = event.target;
    const clickedNode = target instanceof HTMLElement
      ? target.closest('.react-flow__node, [title="Node Properties"], [aria-label^="Open properties"]')
      : null;
    logSamuraiDiagnostic('agent_flow.reactflow.on_pane_click', {
      selectedNodeId,
      ignoredBecauseNodeClick: Boolean(clickedNode),
    });
    if (clickedNode) return;
    setSelectedNodeId(null);
  }, [selectedNodeId]);

  const onSelectionChange = useCallback(({ nodes: selectedNodes }: { nodes: Node[] }) => {
    if (selectedNodes[0]) {
      logSamuraiDiagnostic('agent_flow.reactflow.selection_change', {
        nodeId: selectedNodes[0].id,
        type: selectedNodes[0].type,
        label: selectedNodes[0].data?.label,
      });
      setSelectedNodeId(selectedNodes[0].id);
    }
  }, []);

  // Update node data from inspector
  const onNodeDataUpdate = useCallback((nodeId: string, newData: any) => {
    setNodes((nds) =>
      nds.map((n) => (n.id === nodeId ? { ...n, data: newData } : n))
    );
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
      const initialConfig = nodeType === 'stack_orchestrator' ? {
        mode: 'selected_stack',
        objective: '',
        success_criteria: [],
        allowed_tools: [],
        model_routing_profile: 'balanced',
        max_runtime_minutes: 60,
        max_iterations: 50,
        max_retry_attempts_per_step: 2,
        checkpoint_frequency: 'after_each_step',
        context_compaction: true,
        verification_required: true,
        approval_policy: 'inherited',
        artifact_policy: 'retain_all',
        output_publication: 'summary_and_final',
        failure_policy: 'pause',
      } : nodeType === 'email_read' ? {
        folder: 'INBOX',
        page: 1,
        per_page: 10,
        unread_only: true,
      } : nodeType === 'calendar_read' ? {
        days_ahead: 1,
        start_date: null,
        end_date: null,
      } : {};
      const newNode: Node = {
        id: crypto.randomUUID(),
        type: nodeType,
        position,
        data: {
          label: paletteItem?.label || 'New Node',
          config: initialConfig,
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
    setSelectedNodeId(null);
  }, [setNodes, setEdges]);

  // Save flow
  const handleSave = useCallback(async (): Promise<boolean> => {
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

      // The graph endpoint derives trigger metadata from the Input node and
      // synchronizes the live scheduler in the same save operation.
      await axios.put(`/api/v1/agent-flows/${flow.id}/graph`, graphPayload);

      setDirty(false);
      return true;
    } catch (err: any) {
      console.error('Failed to save flow:', err);
      window.alert(err?.response?.data?.detail || 'Could not save this AgentFlow.');
      return false;
    } finally {
      setSaving(false);
    }
  }, [flow.id, flow.name, flowName, nodes, edges, reactFlowInstance]);

  const handleToggleStatus = useCallback(async () => {
    if (changingStatus) return;
    if (dirty && !(await handleSave())) return;
    const nextStatus = flowStatus === 'active' ? 'paused' : 'active';
    setChangingStatus(true);
    try {
      const resp = await axios.post(`/api/v1/agent-flows/${flow.id}/${nextStatus === 'active' ? 'activate' : 'pause'}`);
      setFlowStatus(resp.data?.data?.status || nextStatus);
      onFlowUpdate();
    } catch (err: any) {
      window.alert(err?.response?.data?.detail || `Could not set this AgentFlow to ${nextStatus}.`);
    } finally {
      setChangingStatus(false);
    }
  }, [changingStatus, dirty, flow.id, flowStatus, handleSave, onFlowUpdate]);

  const handleSaveAsTemplate = useCallback(async () => {
    if (dirty && !(await handleSave())) return;
    const templateName = window.prompt('Template name', flowName);
    if (!templateName) return;
    const category = window.prompt('Template category', 'My Templates') || 'My Templates';
    try {
      await axios.post(`/api/v1/agent-flows/${flow.id}/save-as-template`, {
        name: templateName,
        category,
      });
      window.alert(`Reusable template “${templateName}” saved.`);
    } catch (err: any) {
      window.alert(err?.response?.data?.detail || 'Could not save this template.');
    }
  }, [dirty, flow.id, flowName, handleSave]);

  // ── Trigger run ──────────────────────────────────────────
  const handleRun = useCallback(async () => {
    if (executing) return;
    // Auto-save before running
    if (dirty && !(await handleSave())) return;
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
        setSelectedRunTree(null);
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
  const inspectorNode = selectedNodeId ? nodes.find((n) => n.id === selectedNodeId) || null : null;

  useEffect(() => {
    logSamuraiDiagnostic('agent_flow.inspector.state', {
      selectedNodeId,
      inspectorVisible: Boolean(inspectorNode),
      nodeType: inspectorNode?.type,
      nodeLabel: inspectorNode?.data?.label,
      totalNodes: nodes.length,
    });
  }, [selectedNodeId, inspectorNode, nodes.length]);

  return (
    <div data-testid="agent-flow-editor" data-flow-id={flow.id} className="relative flex h-[calc(100vh-120px)] rounded-lg overflow-hidden border border-[#1a2040] min-w-0">
      {/* Canvas */}
      <div className="flex-1 min-w-0 flex flex-col bg-[#060810]">
        {/* Toolbar */}
        <div className="flex flex-col gap-2 px-3 py-2 bg-[#0a0e1a] border-b border-[#1a2040] shrink-0">
          <div className="flex min-w-0 items-center gap-3">
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
                className="max-w-[min(28rem,60vw)] truncate text-sm font-bold text-[#d4a017] hover:text-[#d4a017]/80 transition-colors"
              >
                {flowName}
              </button>
            )}

            <span className={cn(
              "text-[8px] font-bold uppercase tracking-widest px-2 py-0.5 rounded border",
              flowStatus === 'active'
                ? "text-green-400 bg-green-500/10 border-green-500/20"
                : flowStatus === 'paused'
                  ? "text-[#4a8cc7] bg-[#4a8cc7]/10 border-[#4a8cc7]/20"
                  : "text-[#7a8899] bg-[#7a8899]/10 border-[#7a8899]/20"
            )}>
              {flowStatus}
            </span>

            {dirty && (
              <span className="text-[8px] text-[#d4a017]/60 font-bold uppercase tracking-widest animate-pulse">
                Unsaved
              </span>
            )}
          </div>

          <div className="flex w-full min-w-0 flex-wrap items-center gap-2">
            {/* Node palette (inline drag buttons) */}
            <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1 mr-2">
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
                    className="flex shrink-0 items-center gap-1.5 px-2 py-1.5 bg-[#0e1225] border border-[#1a2040] rounded-md cursor-grab active:cursor-grabbing hover:border-[#2a3060] transition-colors group"
                    title={`Drag to add ${item.label}`}
                  >
                    <PIcon className="w-3 h-3" style={{ color: item.color }} />
                    <span className="hidden text-[9px] font-bold text-[#7a8899] group-hover:text-[#c8d0d8] lg:inline">
                      {item.label}
                    </span>
                  </div>
                );
              })}
            </div>

            <div className="h-5 w-px bg-[#1a2040]" />

            <button
              type="button"
              role="switch"
              aria-checked={flowStatus === 'active'}
              onClick={handleToggleStatus}
              disabled={changingStatus || saving}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider border transition-all",
                flowStatus === 'active'
                  ? "bg-green-500/15 text-green-400 border-green-500/30 hover:bg-green-500/25"
                  : "bg-[#0e1225] text-[#7a8899] border-[#2a3060] hover:text-[#c8d0d8]",
                (changingStatus || saving) && "opacity-60 cursor-wait",
              )}
              title={flowStatus === 'active' ? 'Pause this AgentFlow and disable its schedule' : 'Activate this AgentFlow'}
            >
              {changingStatus ? <Loader2 className="w-3 h-3 animate-spin" /> : <Power className="w-3 h-3" />}
              {flowStatus === 'active' ? 'Active' : 'Activate'}
            </button>

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
            <button
              onClick={handleSaveAsTemplate}
              disabled={saving}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider bg-[#8b5cf6]/15 text-[#c084fc] border border-[#8b5cf6]/30 hover:bg-[#8b5cf6]/25 transition-all"
              title="Save this AgentFlow for future reuse"
            >
              <BookmarkPlus className="w-3 h-3" /> Template
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
        <div ref={reactFlowWrapper} className="flex-1 min-w-0">
          <OutputResultViewerContext.Provider value={outputResultContext}>
            <ReactFlow
              nodes={renderedNodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={onNodeClick}
              onNodeDoubleClick={onNodeClick}
              onPaneClick={onPaneClick}
              onSelectionChange={onSelectionChange}
              onDrop={onDrop}
              onDragOver={onDragOver}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              defaultViewport={flow.viewport}
              fitView={!flow.nodes?.length ? false : true}
              snapToGrid
              snapGrid={[16, 16]}
              nodeDragThreshold={5}
              selectNodesOnDrag={false}
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
        <div className="absolute top-0 right-0 bottom-0 z-[60] w-[min(420px,calc(100vw-320px))] min-w-[320px] max-w-[420px] shadow-[-20px_0_40px_rgba(0,0,0,0.35)]">
          <NodeInspector
            node={inspectorNode}
            onUpdate={onNodeDataUpdate}
            onClose={() => setSelectedNodeId(null)}
            agents={agents}
            routingProfiles={routingProfiles}
            flowId={flow.id}
            flows={availableFlows}
          />
        </div>
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
                        <span className="bg-[#1a2040] px-2.5 py-1 rounded">Depth: {selectedRunDetails.run_depth || 0}</span>
                        {selectedRunDetails.flow_version && <span className="bg-[#1a2040] px-2.5 py-1 rounded">Flow v{selectedRunDetails.flow_version}</span>}
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

                      {selectedRunTree && (
                        <div className="space-y-3">
                          <div className="flex items-center gap-2 border-b border-[#1a2040] pb-2">
                            <Network className="w-4 h-4 text-[#8b5cf6]" />
                            <h3 className="text-xs font-bold text-[#c8d0d8] uppercase tracking-wider">Flow Stacking Execution Tree</h3>
                          </div>
                          <ExecutionTreeNode node={selectedRunTree} />
                        </div>
                      )}

                      {selectedRunDetails.governance_context && Object.keys(selectedRunDetails.governance_context).length > 0 && (
                        <details className="rounded-lg border border-[#1a2040] bg-[#0e1225] p-3">
                          <summary className="cursor-pointer text-[10px] font-bold uppercase tracking-wider text-[#7a8899]">Inherited governance context</summary>
                          <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-[9px] text-[#c8d0d8]">{JSON.stringify(selectedRunDetails.governance_context, null, 2)}</pre>
                        </details>
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
  onBulkDelete,
  onDuplicate,
  onRefresh,
}: {
  flows: FlowListItem[];
  loading: boolean;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
  onBulkDelete: (ids: string[]) => Promise<void>;
  onDuplicate: (id: string) => void;
  onRefresh: () => void;
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deletingSelection, setDeletingSelection] = useState(false);
  const [bulkError, setBulkError] = useState('');

  const filtered = flows.filter((f) =>
    f.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  useEffect(() => {
    const visibleIds = new Set(flows.map((flow) => flow.id));
    setSelectedIds((current) => new Set([...current].filter((id) => visibleIds.has(id))));
  }, [flows]);

  const toggleSelection = (flowId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(flowId)) next.delete(flowId);
      else next.add(flowId);
      return next;
    });
    setBulkError('');
  };

  const exitSelectionMode = () => {
    setSelectionMode(false);
    setSelectedIds(new Set());
    setBulkError('');
  };

  const deleteSelection = async () => {
    if (selectedIds.size === 0 || deletingSelection) return;
    const selectedNames = flows.filter((flow) => selectedIds.has(flow.id)).map((flow) => flow.name);
    const preview = selectedNames.slice(0, 5).join(', ');
    const suffix = selectedNames.length > 5 ? ` and ${selectedNames.length - 5} more` : '';
    if (!window.confirm(`Delete ${selectedIds.size} Agent Flows?\n\n${preview}${suffix}\n\nThis removes the selected workflows from the overview.`)) return;
    setDeletingSelection(true);
    setBulkError('');
    try {
      await onBulkDelete([...selectedIds]);
      exitSelectionMode();
    } catch (error) {
      const message = axios.isAxiosError(error)
        ? error.response?.data?.detail?.message || error.response?.data?.detail || error.message
        : 'Bulk deletion failed.';
      setBulkError(String(message));
    } finally {
      setDeletingSelection(false);
    }
  };

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
          onClick={() => selectionMode ? exitSelectionMode() : setSelectionMode(true)}
          className={cn(
            "flex items-center gap-2 border font-bold py-2.5 px-4 rounded-lg transition-all text-xs",
            selectionMode
              ? "border-[#d4a017]/50 bg-[#d4a017]/10 text-[#d4a017]"
              : "border-[#1a2040] bg-[#0e1225] text-[#7a8899] hover:text-[#c8d0d8]"
          )}
        >
          {selectionMode ? <CheckSquare2 className="w-4 h-4" /> : <Square className="w-4 h-4" />}
          {selectionMode ? 'CANCEL' : 'SELECT'}
        </button>
        <button
          onClick={onCreate}
          className="flex items-center gap-2 bg-[#4a8cc7] hover:bg-[#4a8cc7]/90 text-white font-bold py-2.5 px-5 rounded-lg transition-all shadow-[0_0_20px_rgba(74,140,199,0.15)] text-xs"
        >
          <Plus className="w-4 h-4" /> NEW FLOW
        </button>
      </div>

      {selectionMode && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-[#d4a017]/25 bg-[#d4a017]/5 px-4 py-3">
          <span className="text-xs font-bold text-[#c8d0d8]">{selectedIds.size} selected</span>
          <button
            onClick={() => setSelectedIds(new Set(filtered.map((flow) => flow.id)))}
            disabled={filtered.length === 0}
            className="text-[10px] font-bold uppercase tracking-wider text-[#4a8cc7] hover:text-[#6aa6dc] disabled:opacity-40"
          >
            Select all {searchTerm ? 'filtered' : ''}
          </button>
          <button
            onClick={() => setSelectedIds(new Set())}
            disabled={selectedIds.size === 0}
            className="text-[10px] font-bold uppercase tracking-wider text-[#7a8899] hover:text-[#c8d0d8] disabled:opacity-40"
          >
            Clear
          </button>
          <button
            onClick={() => void deleteSelection()}
            disabled={selectedIds.size === 0 || deletingSelection}
            className="ml-auto flex items-center gap-2 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-2 text-xs font-bold text-red-400 transition-colors hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {deletingSelection ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
            DELETE {selectedIds.size || ''}
          </button>
          {bulkError && <p className="w-full text-[10px] text-red-400">{bulkError}</p>}
        </div>
      )}

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
            <div
              key={flow.id}
              role="button"
              tabIndex={0}
              aria-pressed={selectionMode ? selectedIds.has(flow.id) : undefined}
              onClick={() => selectionMode ? toggleSelection(flow.id) : onSelect(flow.id)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  selectionMode ? toggleSelection(flow.id) : onSelect(flow.id);
                }
              }}
              className={cn(
                "shogun-card !p-0 text-left hover:border-[#4a8cc7]/40 transition-all group relative overflow-hidden cursor-pointer",
                selectionMode && selectedIds.has(flow.id) && "border-[#d4a017]/70 bg-[#d4a017]/5 ring-1 ring-[#d4a017]/30"
              )}
            >
              {/* Top accent */}
              <div className="h-0.5" style={{ background: statusColors[flow.status] || '#7a8899' }} />

              {selectionMode && (
                <button
                  type="button"
                  aria-label={`${selectedIds.has(flow.id) ? 'Deselect' : 'Select'} ${flow.name}`}
                  onClick={(event) => { event.stopPropagation(); toggleSelection(flow.id); }}
                  className={cn(
                    "absolute right-4 top-4 z-10 rounded-md border p-1.5 transition-colors",
                    selectedIds.has(flow.id)
                      ? "border-[#d4a017]/60 bg-[#d4a017]/20 text-[#d4a017]"
                      : "border-[#2a3060] bg-[#0e1225] text-[#7a8899] hover:text-[#c8d0d8]"
                  )}
                >
                  {selectedIds.has(flow.id) ? <CheckSquare2 className="w-4 h-4" /> : <Square className="w-4 h-4" />}
                </button>
              )}

              <div className={cn("p-5", selectionMode && "pr-14")}>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <h4 className="text-sm font-bold text-[#c8d0d8] group-hover:text-[#d4a017] transition-colors truncate">
                      {flow.name}
                    </h4>
                    <p className="text-[10px] text-[#7a8899] mt-1 line-clamp-2">
                      {flow.description || 'No description'}
                    </p>
                  </div>
                  {!selectionMode && <div className="relative">
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
                  </div>}
                </div>

                <div className="flex items-center gap-3 mt-4">
                  {flow.flow_type === 'stack' && (
                    <span className="text-[8px] font-bold uppercase tracking-widest px-2 py-0.5 rounded border text-[#a78bfa] bg-[#8b5cf6]/10 border-[#8b5cf6]/30">
                      Flow Stack
                    </span>
                  )}
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
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════
export function StackOrchestratorConsole({ flows, onClose }: { flows: FlowListItem[]; onClose: () => void }) {
  const [runs, setRuns] = useState<StackRunData[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selected, setSelected] = useState<StackRunData | null>(null);
  const [checkpoints, setCheckpoints] = useState<any[]>([]);
  const [artifacts, setArtifacts] = useState<any[]>([]);
  const [verifications, setVerifications] = useState<any[]>([]);
  const [mode, setMode] = useState<'selected_stack' | 'goal_driven' | 'template'>('selected_stack');
  const [objective, setObjective] = useState('');
  const [selectedStackId, setSelectedStackId] = useState('');
  const [templateId, setTemplateId] = useState('');
  const [modelProfile, setModelProfile] = useState('balanced');
  const [outputPublication, setOutputPublication] = useState('summary_and_final');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    try {
      const listResponse = await axios.get('/api/v1/stacks/orchestrator');
      const list = listResponse.data?.data || [];
      setRuns(list);
      if (selectedId) {
        const [runResponse, checkpointResponse, artifactResponse, verificationResponse] = await Promise.all([
          axios.get(`/api/v1/stacks/orchestrator/${selectedId}`),
          axios.get(`/api/v1/stacks/orchestrator/${selectedId}/checkpoints`),
          axios.get(`/api/v1/stacks/orchestrator/${selectedId}/artifacts`),
          axios.get(`/api/v1/stacks/orchestrator/${selectedId}/verifications`),
        ]);
        setSelected(runResponse.data?.data || null);
        setCheckpoints(checkpointResponse.data?.data || []);
        setArtifacts(artifactResponse.data?.data || []);
        setVerifications(verificationResponse.data?.data || []);
      }
    } catch (err) {
      setError(axios.isAxiosError(err) ? err.response?.data?.detail || err.message : 'Could not load Stack Orchestrator state');
    }
  }, [selectedId]);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 2000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const createRun = async () => {
    setBusy(true);
    setError('');
    try {
      const response = await axios.post('/api/v1/stacks/orchestrator/create', {
        mode,
        objective,
        selected_stack_id: mode === 'selected_stack' ? selectedStackId || null : null,
        stack_template_id: mode === 'template' ? templateId || null : null,
        success_criteria: [],
        allowed_tools: [],
        model_routing_profile: modelProfile,
        max_runtime_minutes: 60,
        max_iterations: 50,
        max_retry_attempts_per_step: 2,
        checkpoint_frequency: 'after_each_step',
        context_compaction: 'enabled',
        verification_required: true,
        approval_policy: 'inherited',
        artifact_policy: 'retain_all',
        output_publication: outputPublication,
        failure_policy: 'pause',
      });
      const run = response.data?.data;
      if (run) {
        setSelectedId(run.id);
        setSelected(run);
        setObjective('');
        await refresh();
      }
    } catch (err) {
      setError(axios.isAxiosError(err) ? err.response?.data?.detail || err.message : 'Could not create Stack Orchestrator run');
    } finally {
      setBusy(false);
    }
  };

  const transition = async (action: 'start' | 'pause' | 'resume' | 'cancel') => {
    if (!selectedId) return;
    setBusy(true);
    setError('');
    try {
      await axios.post(`/api/v1/stacks/orchestrator/${selectedId}/${action}`);
      await refresh();
    } catch (err) {
      setError(axios.isAxiosError(err) ? err.response?.data?.detail || err.message : `Could not ${action} stack`);
    } finally {
      setBusy(false);
    }
  };

  const approvePlan = async () => {
    if (!selectedId || !selectedStackId) return;
    setBusy(true);
    try {
      await axios.post(`/api/v1/stacks/orchestrator/${selectedId}/plan-decision`, {
        approved: true,
        selected_stack_id: selectedStackId,
        reason: 'Reviewed and attached in Katana',
      });
      await refresh();
    } catch (err) {
      setError(axios.isAxiosError(err) ? err.response?.data?.detail || err.message : 'Could not approve plan');
    } finally {
      setBusy(false);
    }
  };

  const statusColor = (status: string) => status === 'completed' || status === 'verified' ? '#22c55e'
    : status === 'failed' || status === 'blocked' ? '#ef4444'
    : status === 'running' || status === 'retrying' ? '#4a8cc7'
    : status === 'waiting_approval' ? '#f59e0b'
    : '#7a8899';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="flex h-[88vh] w-full max-w-7xl overflow-hidden rounded-xl border border-[#c084fc]/30 bg-[#080b18] shadow-2xl">
        <aside className="w-72 shrink-0 border-r border-[#1a2040] bg-[#070914] flex flex-col">
          <div className="border-b border-[#1a2040] p-4">
            <h3 className="flex items-center gap-2 text-sm font-bold text-[#c084fc]"><Network className="w-4 h-4" />Stack Orchestrator</h3>
            <p className="mt-1 text-[8px] uppercase tracking-widest text-[#7a8899]">Long-horizon runtime control</p>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {runs.map((run) => (
              <button key={run.id} onClick={() => setSelectedId(run.id)} className={cn("w-full rounded-lg border p-3 text-left transition-colors", selectedId === run.id ? "border-[#c084fc]/40 bg-[#c084fc]/10" : "border-transparent hover:bg-[#10152a]")}>
                <p className="line-clamp-2 text-[10px] font-bold text-[#c8d0d8]">{run.objective}</p>
                <div className="mt-2 flex items-center justify-between"><span className="text-[8px] uppercase text-[#7a8899]">{run.mode.replace('_', ' ')}</span><span className="text-[8px] font-bold uppercase" style={{ color: statusColor(run.status) }}>{run.status.replace('_', ' ')}</span></div>
              </button>
            ))}
            {runs.length === 0 && <p className="p-5 text-center text-[9px] text-[#7a8899]">No orchestrated runs yet.</p>}
          </div>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center justify-between border-b border-[#1a2040] bg-[#0e1225] px-5 py-3">
            <div><h2 className="text-sm font-bold text-[#c8d0d8]">Runtime Command View</h2><p className="text-[9px] text-[#7a8899]">State · checkpoints · verification · recovery</p></div>
            <div className="flex items-center gap-2"><button onClick={refresh} className="p-2 text-[#7a8899] hover:text-[#c084fc]"><RefreshCw className="w-4 h-4" /></button><button onClick={onClose} className="p-2 text-[#7a8899] hover:text-white"><X className="w-4 h-4" /></button></div>
          </div>

          <div className="flex-1 overflow-y-auto p-5">
            {error && <div className="mb-4 rounded-lg border border-[#ef4444]/30 bg-[#ef4444]/5 p-3 text-[10px] text-[#ef4444]">{error}</div>}
            {!selected ? (
              <div className="mx-auto max-w-2xl space-y-4 rounded-xl border border-[#1a2040] bg-[#0e1225] p-5">
                <div><h3 className="text-sm font-bold text-[#c8d0d8]">Create Stack Run</h3><p className="mt-1 text-[9px] text-[#7a8899]">Select a reusable stack, instantiate a template, or generate a reviewable goal plan.</p></div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5"><label className="text-[8px] font-bold uppercase tracking-widest text-[#7a8899]">Mode</label><select value={mode} onChange={(event) => setMode(event.target.value as typeof mode)} className="w-full rounded-lg border border-[#1a2040] bg-[#050508] p-2.5 text-xs text-[#c8d0d8]"><option value="selected_stack">Selected stack</option><option value="goal_driven">Goal-driven</option><option value="template">Template</option></select></div>
                  <div className="space-y-1.5"><label className="text-[8px] font-bold uppercase tracking-widest text-[#7a8899]">Model Profile</label><input value={modelProfile} onChange={(event) => setModelProfile(event.target.value)} className="w-full rounded-lg border border-[#1a2040] bg-[#050508] p-2.5 text-xs text-[#c8d0d8]" /></div>
                </div>
                {mode !== 'template' && <div className="space-y-1.5"><label className="text-[8px] font-bold uppercase tracking-widest text-[#7a8899]">{mode === 'goal_driven' ? 'Attach after review' : 'Agent Stack'}</label><select value={selectedStackId} onChange={(event) => setSelectedStackId(event.target.value)} className="w-full rounded-lg border border-[#1a2040] bg-[#050508] p-2.5 text-xs text-[#c8d0d8]"><option value="">Select stack...</option>{flows.map((flow) => <option key={flow.id} value={flow.id}>{flow.name} · {flow.flow_type}</option>)}</select></div>}
                {mode === 'template' && <div className="space-y-1.5"><label className="text-[8px] font-bold uppercase tracking-widest text-[#7a8899]">Template ID</label><input value={templateId} onChange={(event) => setTemplateId(event.target.value)} placeholder="bug-fix-stack" className="w-full rounded-lg border border-[#1a2040] bg-[#050508] p-2.5 text-xs text-[#c8d0d8]" /></div>}
                <div className="space-y-1.5"><label className="text-[8px] font-bold uppercase tracking-widest text-[#7a8899]">Objective</label><textarea value={objective} onChange={(event) => setObjective(event.target.value)} rows={4} placeholder="What should this Agent Stack accomplish?" className="w-full rounded-lg border border-[#1a2040] bg-[#050508] p-3 text-xs text-[#c8d0d8] outline-none focus:border-[#c084fc]" /></div>
                <div className="space-y-1.5"><label className="text-[8px] font-bold uppercase tracking-widest text-[#7a8899]">Published Output</label><select value={outputPublication} onChange={(event) => setOutputPublication(event.target.value)} className="w-full rounded-lg border border-[#c084fc]/30 bg-[#050508] p-2.5 text-xs text-[#c8d0d8]"><option value="summary_and_final">Orchestrator summary + final Flow</option><option value="summary_only">Orchestrator summary only</option><option value="final_only">Final Flow only</option><option value="all_steps">All Flow outputs (legacy)</option></select><p className="text-[8px] leading-relaxed text-[#7a8899]">Every intermediate result is handed to the next Flow without being published.</p></div>
                <button disabled={busy || !objective || (mode === 'selected_stack' && !selectedStackId) || (mode === 'template' && !templateId)} onClick={createRun} className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#c084fc] px-4 py-3 text-xs font-bold text-[#090b15] disabled:opacity-40">{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Network className="w-4 h-4" />}Create Runtime Plan</button>
              </div>
            ) : (
              <div className="space-y-5">
                <div className="rounded-xl border border-[#1a2040] bg-[#0e1225] p-5">
                  <div className="flex flex-wrap items-start justify-between gap-4"><div><div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: statusColor(selected.status) }} /><span className="text-[9px] font-bold uppercase tracking-widest" style={{ color: statusColor(selected.status) }}>{selected.status.replace('_', ' ')}</span></div><h3 className="mt-2 max-w-3xl text-lg font-bold text-[#c8d0d8]">{selected.objective}</h3><p className="mt-1 text-[9px] uppercase tracking-widest text-[#7a8899]">{selected.posture} posture · {selected.model_profile} · {selected.mode.replace('_', ' ')}</p></div><div className="flex gap-2">{selected.status === 'created' && <button onClick={() => transition('start')} className="rounded-lg bg-[#22c55e]/15 px-3 py-2 text-[9px] font-bold uppercase text-[#22c55e]">Start</button>}{selected.status === 'running' && <button onClick={() => transition('pause')} className="rounded-lg bg-[#f59e0b]/15 px-3 py-2 text-[9px] font-bold uppercase text-[#f59e0b]">Pause</button>}{selected.status === 'paused' && <button onClick={() => transition('resume')} className="rounded-lg bg-[#4a8cc7]/15 px-3 py-2 text-[9px] font-bold uppercase text-[#4a8cc7]">Resume checkpoint</button>}{!['completed', 'failed', 'cancelled'].includes(selected.status) && <button onClick={() => transition('cancel')} className="rounded-lg bg-[#ef4444]/10 px-3 py-2 text-[9px] font-bold uppercase text-[#ef4444]">Cancel</button>}</div></div>
                  {selected.status === 'waiting_approval' && <div className="mt-4 flex items-center gap-3 rounded-lg border border-[#f59e0b]/25 bg-[#f59e0b]/5 p-3"><AlertTriangle className="w-4 h-4 text-[#f59e0b]" /><p className="flex-1 text-[10px] text-[#c8d0d8]">Generated or supervised plan requires review. Choose the concrete Agent Stack in the creation panel selection, then approve.</p><button disabled={!selectedStackId || busy} onClick={approvePlan} className="rounded bg-[#f59e0b] px-3 py-2 text-[9px] font-bold uppercase text-black disabled:opacity-40">Approve Plan</button></div>}
                </div>

                <div className="grid gap-5 xl:grid-cols-[1.4fr_1fr]">
                  <section className="rounded-xl border border-[#1a2040] bg-[#0e1225] p-4"><h4 className="mb-3 flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-[#c8d0d8]"><Network className="w-3.5 h-3.5 text-[#c084fc]" />Execution Tree</h4><div className="space-y-2">{selected.steps.map((step, index) => <div key={step.id} className="relative flex items-center gap-3 rounded-lg border border-[#1a2040] bg-[#090d1d] p-3"><div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[9px] font-bold" style={{ borderColor: statusColor(step.status), color: statusColor(step.status) }}>{index + 1}</div><div className="min-w-0 flex-1"><div className="flex items-center justify-between gap-2"><p className="truncate text-[10px] font-bold text-[#c8d0d8]">{step.name}</p><span className="text-[8px] font-bold uppercase" style={{ color: statusColor(step.status) }}>{step.status.replace('_', ' ')}</span></div><div className="mt-1 flex flex-wrap gap-3 text-[8px] text-[#7a8899]"><span>{step.model_used || 'model pending'}</span><span>{step.retry_count}/{step.max_retries} retries</span><span>verification: {step.verification_status}</span>{step.flow_run_id && <span>run {step.flow_run_id.slice(0, 8)}</span>}</div>{step.error_json?.message && <p className="mt-1 text-[8px] text-[#ef4444]">{step.error_json.message}</p>}</div></div>)}</div></section>
                  <div className="space-y-5"><section className="rounded-xl border border-[#1a2040] bg-[#0e1225] p-4"><h4 className="mb-3 text-[10px] font-bold uppercase tracking-widest text-[#c8d0d8]">Checkpoints</h4><div className="max-h-56 space-y-2 overflow-y-auto">{checkpoints.map((checkpoint) => <div key={checkpoint.id} className="rounded-lg border border-[#1a2040] p-3"><div className="flex justify-between gap-2"><span className="text-[9px] font-bold text-[#c8d0d8]">{checkpoint.summary}</span><span className="text-[8px] text-[#7a8899]">{formatRunTimestamp(checkpoint.created_at)}</span></div><p className="mt-1 line-clamp-3 text-[8px] text-[#7a8899]">{checkpoint.context_summary}</p><p className="mt-1 text-[8px] text-[#c084fc]">{checkpoint.resume_instruction}</p></div>)}{checkpoints.length === 0 && <p className="text-[9px] text-[#7a8899]">No checkpoints yet.</p>}</div></section><section className="rounded-xl border border-[#1a2040] bg-[#0e1225] p-4"><h4 className="mb-3 text-[10px] font-bold uppercase tracking-widest text-[#c8d0d8]">Evidence</h4><div className="grid grid-cols-2 gap-2"><div className="rounded-lg bg-[#090d1d] p-3"><p className="text-xl font-bold text-[#c084fc]">{artifacts.length}</p><span className="text-[8px] uppercase text-[#7a8899]">Artifacts</span></div><div className="rounded-lg bg-[#090d1d] p-3"><p className="text-xl font-bold text-[#22c55e]">{verifications.filter((item) => item.status === 'passed').length}/{verifications.length}</p><span className="text-[8px] uppercase text-[#7a8899]">Verified</span></div></div></section></div>
                </div>
                {Object.keys(selected.published_output || {}).length > 0 && <section className="rounded-xl border border-[#22c55e]/25 bg-[#22c55e]/5 p-4"><div className="mb-3 flex items-center justify-between gap-3"><h4 className="text-[10px] font-bold uppercase tracking-widest text-[#22c55e]">Published Stack Output</h4><span className="rounded bg-[#22c55e]/10 px-2 py-1 text-[8px] uppercase text-[#22c55e]">{selected.output_publication.replaceAll('_', ' ')}</span></div><pre className="max-h-96 overflow-auto whitespace-pre-wrap text-[9px] leading-relaxed text-[#c8d0d8]">{JSON.stringify(selected.published_output, null, 2)}</pre></section>}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}


export function FlowStackModal({
  flows,
  onClose,
  onCreate,
}: {
  flows: FlowListItem[];
  onClose: () => void;
  onCreate: (name: string, flowIds: string[], versionMode: string) => Promise<void>;
}) {
  const [name, setName] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [versionMode, setVersionMode] = useState('locked');
  const [creating, setCreating] = useState(false);
  const available = flows.filter((flow) => flow.allow_as_subflow);

  const move = (index: number, direction: -1 | 1) => {
    const next = [...selected];
    const target = index + direction;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    setSelected(next);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="w-full max-w-2xl overflow-hidden rounded-xl border border-[#8b5cf6]/30 bg-[#0a0e1a] shadow-2xl">
        <div className="flex items-center justify-between border-b border-[#1a2040] bg-[#0e1225] p-5">
          <div>
            <h3 className="flex items-center gap-2 text-lg font-bold text-[#a78bfa]"><Layers3 className="w-5 h-5" />Create Flow Stack</h3>
            <p className="mt-1 text-[10px] font-bold uppercase tracking-widest text-[#7a8899]">Each child output becomes the next child input</p>
          </div>
          <button onClick={onClose} className="p-2 text-[#7a8899] hover:text-[#c8d0d8]"><X className="w-4 h-4" /></button>
        </div>
        <div className="grid grid-cols-2 gap-5 p-5">
          <div className="space-y-3">
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold uppercase tracking-widest text-[#7a8899]">Stack Name</label>
              <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Board Report Orchestration" className="w-full rounded-lg border border-[#1a2040] bg-[#050508] p-2.5 text-xs text-[#c8d0d8] outline-none focus:border-[#8b5cf6]" />
            </div>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold uppercase tracking-widest text-[#7a8899]">Version Policy</label>
              <select value={versionMode} onChange={(event) => setVersionMode(event.target.value)} className="w-full rounded-lg border border-[#1a2040] bg-[#050508] p-2.5 text-xs text-[#c8d0d8] outline-none">
                <option value="locked">Lock current versions</option>
                <option value="latest">Use latest at run time</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold uppercase tracking-widest text-[#7a8899]">Add Reusable Flow</label>
              <div className="max-h-52 space-y-1 overflow-y-auto rounded-lg border border-[#1a2040] p-1.5">
                {available.map((flow) => (
                  <button key={flow.id} type="button" onClick={() => setSelected((items) => [...items, flow.id])} className="w-full rounded p-2 text-left hover:bg-[#8b5cf6]/10">
                    <div className="flex items-center justify-between gap-2"><span className="truncate text-[10px] font-bold text-[#c8d0d8]">{flow.name}</span><Plus className="w-3 h-3 text-[#8b5cf6]" /></div>
                    <span className="text-[8px] uppercase text-[#7a8899]">v{flow.version} · {flow.risk_tier}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div>
            <label className="text-[9px] font-bold uppercase tracking-widest text-[#7a8899]">Execution Order ({selected.length})</label>
            <div className="mt-2 min-h-64 space-y-2 rounded-lg border border-dashed border-[#8b5cf6]/25 p-2">
              {selected.length === 0 && <p className="py-20 text-center text-[10px] text-[#7a8899]">Add at least two flows</p>}
              {selected.map((id, index) => {
                const flow = available.find((item) => item.id === id);
                return (
                  <div key={`${id}-${index}`} className="flex items-center gap-2 rounded-lg border border-[#1a2040] bg-[#0e1225] p-2">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#8b5cf6]/15 text-[9px] font-bold text-[#a78bfa]">{index + 1}</span>
                    <span className="min-w-0 flex-1 truncate text-[10px] font-bold text-[#c8d0d8]">{flow?.name || id}</span>
                    <button onClick={() => move(index, -1)} disabled={index === 0} className="text-[10px] text-[#7a8899] disabled:opacity-20">↑</button>
                    <button onClick={() => move(index, 1)} disabled={index === selected.length - 1} className="text-[10px] text-[#7a8899] disabled:opacity-20">↓</button>
                    <button onClick={() => setSelected((items) => items.filter((_, itemIndex) => itemIndex !== index))}><X className="w-3 h-3 text-[#ef4444]" /></button>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-3 border-t border-[#1a2040] p-4">
          <button onClick={onClose} className="rounded-lg border border-[#1a2040] px-4 py-2 text-xs font-bold text-[#7a8899]">Cancel</button>
          <button
            disabled={!name.trim() || selected.length < 2 || creating}
            onClick={async () => { setCreating(true); try { await onCreate(name, selected, versionMode); } finally { setCreating(false); } }}
            className="flex items-center gap-2 rounded-lg bg-[#8b5cf6] px-4 py-2 text-xs font-bold text-white disabled:opacity-40"
          >
            {creating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Layers3 className="w-3.5 h-3.5" />} Create Stack
          </button>
        </div>
      </div>
    </div>
  );
}


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
  source?: string;
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
  const {
    ui: templateUi,
    category: translateCategory,
    difficulty: translateDifficulty,
    agentFlow: translateTemplate,
  } = useTemplateCatalog();
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
    const localized = list.map((template) => translateTemplate(template));
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return localized.filter(
        (t) =>
          t.name.toLowerCase().includes(q) ||
          t.description.toLowerCase().includes(q) ||
          t.category.toLowerCase().includes(q)
      );
    }
    return localized;
  }, [templates, selectedCategory, searchQuery, translateTemplate]);

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
              {templateUi('create_agent_flow', 'Create Agent Flow')}
            </h3>
            <p className="text-[10px] text-[#7a8899] uppercase tracking-widest font-bold mt-1">
              {templateUi('choose_template', 'Choose a template or start from scratch')}
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
            {templateUi('templates', 'Templates')}
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
            {templateUi('blank_flow', 'Blank Flow')}
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
                {templateUi('all_templates', 'All Templates')}
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
                  <span className="flex-1 truncate">{translateCategory(cat.name)}</span>
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
                    placeholder={templateUi('search_templates', 'Search templates...')}
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
                    <p className="text-sm text-amber-300 font-semibold">{templateUi('templates_unavailable', 'Templates unavailable')}</p>
                    <p className="text-xs text-[#7a8899] mt-2">{loadError}</p>
                  </div>
                ) : filteredTemplates.length === 0 ? (
                  <div className="text-center py-16">
                    <Search className="w-8 h-8 text-[#7a8899]/40 mx-auto mb-3" />
                    <p className="text-sm text-[#7a8899]">{templateUi('no_templates', 'No templates match your search')}</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-2.5">
                    {filteredTemplates.map((t) => {
                      const sourceCategory = templates.find((item) => item.id === t.id)?.category || t.category;
                      const catColor = CATEGORY_COLORS[sourceCategory] || '#7a8899';
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
                                  {translateDifficulty(t.difficulty || 'beginner') || diff.label}
                                </span>
                                <span className="text-[8px] text-[#7a8899]/60 ml-auto">
                                  {t.node_count} {templateUi('nodes', 'nodes')}
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

  useEffect(() => {
    logSamuraiDiagnostic('agent_flow.mount', {
      path: window.location.pathname,
      href: window.location.href,
    });
  }, []);

  // Fetch flows list
  const fetchFlows = useCallback(async () => {
    setLoading(true);
    logSamuraiDiagnostic('agent_flow.fetch_flows.start');
    try {
      const res = await axios.get('/api/v1/agent-flows');
      if (res.data.data) {
        setFlows(res.data.data);
        logSamuraiDiagnostic('agent_flow.fetch_flows.success', {
          count: res.data.data.length,
          ids: res.data.data.slice(0, 10).map((flow: FlowListItem) => flow.id),
        });
      } else {
        logSamuraiDiagnostic('agent_flow.fetch_flows.empty_response', { response: res.data });
      }
    } catch (err) {
      console.error('Failed to fetch flows:', err);
      logSamuraiDiagnostic('agent_flow.fetch_flows.error', { error: err });
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch supporting data
  const fetchSupportData = useCallback(async () => {
    logSamuraiDiagnostic('agent_flow.fetch_support.start');
    try {
      const [agentRes, routingRes] = await Promise.all([
        axios.get('/api/v1/agents?agent_type=samurai'),
        axios.get('/api/v1/model-routing-profiles'),
      ]);
      if (agentRes.data.data) setAgents(agentRes.data.data);
      if (routingRes.data.data) setRoutingProfiles(routingRes.data.data);
      logSamuraiDiagnostic('agent_flow.fetch_support.success', {
        agents: agentRes.data?.data?.length || 0,
        routingProfiles: routingRes.data?.data?.length || 0,
      });
    } catch (err) {
      console.error('Failed to fetch support data:', err);
      logSamuraiDiagnostic('agent_flow.fetch_support.error', { error: err });
    }
  }, []);

  useEffect(() => {
    fetchFlows();
    fetchSupportData();
  }, [fetchFlows, fetchSupportData]);

  // Load a specific flow
  const loadFlow = useCallback(async (flowId: string) => {
    logSamuraiDiagnostic('agent_flow.load_flow.start', { flowId });
    try {
      const res = await axios.get(`/api/v1/agent-flows/${flowId}`);
      if (res.data.data) {
        logSamuraiDiagnostic('agent_flow.load_flow.success', {
          flowId,
          nodes: res.data.data.nodes?.length || 0,
          edges: res.data.data.edges?.length || 0,
        });
        setActiveFlow(res.data.data);
      } else {
        logSamuraiDiagnostic('agent_flow.load_flow.empty_response', { flowId, response: res.data });
      }
    } catch (err) {
      console.error('Failed to load flow:', err);
      logSamuraiDiagnostic('agent_flow.load_flow.error', { flowId, error: err });
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

  const handleBulkDelete = useCallback(async (flowIds: string[]) => {
    await axios.delete('/api/v1/agent-flows/bulk', { data: { flow_ids: flowIds } });
    await fetchFlows();
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
          availableFlows={flows}
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
        onBulkDelete={handleBulkDelete}
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
