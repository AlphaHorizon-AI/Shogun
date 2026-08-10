import { Component, createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { DragEvent, ErrorInfo, ReactNode } from 'react';
import axios from 'axios';
import {
  ReactFlow, ReactFlowProvider, Background, BackgroundVariant, Controls, MiniMap,
  addEdge, reconnectEdge, useEdgesState, useNodesState, useNodesInitialized, useReactFlow, Handle, Position,
} from '@xyflow/react';
import type { Connection, Edge, Node } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Layers3, Search, Save, BookmarkPlus, Play, RefreshCw, Boxes, Route,
  ShieldCheck, Sparkles, Trash2, CircleStop, Pause, RotateCcw, Loader2, X, Eye,
  ChevronDown, ChevronUp, Info, Power, LocateFixed,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { AgentFlowCanvas } from './AgentFlow';
import type { AgentFlowData, FlowListItem } from './AgentFlow';
import { useTemplateCatalog } from '../i18n/templateCatalog';

type CatalogTemplate = {
  id: string; name: string; description: string; category: string;
  icon?: string; node_count?: number; flow_count?: number; source?: string;
  difficulty?: string; duration_label?: string;
  orchestrator_config?: Record<string, any>;
  flow_template_ids?: string[];
  builder_nodes?: Array<{ id: string; label: string; flow_id?: string; template_id?: string; position_x: number; position_y: number }>;
  builder_edges?: Array<{ source: string; target: string }>;
};

type SavedFlow = { id: string; name: string; status: string; flow_type: string };

const StackActionsContext = createContext<{
  openEditor: (nodeId: string) => void;
  deleteNode: (nodeId: string) => void;
}>({ openEditor: () => undefined, deleteNode: () => undefined });

function StackFlowCard({ id, data, selected }: { id: string; data: Record<string, any>; selected: boolean }) {
  const { openEditor, deleteNode } = useContext(StackActionsContext);
  return <div onClick={() => openEditor(id)} className={cn(
    'relative w-[230px] rounded-xl border bg-[#0e1225] text-[#c8d0d8] shadow-lg transition-all',
    selected ? 'border-purple-400 ring-2 ring-purple-400/25' : 'border-[#28325d] hover:border-[#4a8cc7]',
  )}>
    <Handle type="target" position={Position.Left} className="!h-3 !w-3 !border-2 !border-[#080b16] !bg-[#4a8cc7]" />
    <div className="flex items-start gap-2 p-3">
      <Layers3 className="mt-0.5 h-4 w-4 shrink-0 text-purple-400" />
      <button type="button" onPointerDown={(event) => event.stopPropagation()} onClick={() => openEditor(id)} className="nodrag nopan min-w-0 flex-1 text-left">
        <div className="truncate text-[11px] font-bold">{String(data.label || 'AgentFlow')}</div>
        <div className="mt-1 text-[8px] font-bold uppercase tracking-wider text-[#7a8899]">{String(data.category || 'AgentFlow')} · drag to reorder</div>
      </button>
      <div className="flex shrink-0 gap-1">
        <button type="button" title="Edit AgentFlow" onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); openEditor(id); }} className="nodrag nopan rounded border border-[#28325d] p-1 text-[#7a8899] hover:text-[#4a8cc7]"><Eye className="h-3 w-3" /></button>
        <button type="button" title="Delete from stack" onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); deleteNode(id); }} className="nodrag nopan rounded border border-red-500/20 p-1 text-red-400/70 hover:bg-red-500/10 hover:text-red-300"><Trash2 className="h-3 w-3" /></button>
      </div>
    </div>
    <Handle type="source" position={Position.Right} className="!h-3 !w-3 !border-2 !border-[#080b16] !bg-[#8b5cf6]" />
  </div>;
}

const stackNodeTypes = { stackFlow: StackFlowCard };

type TemplateDetail = Omit<CatalogTemplate, 'category'> & {
  category?: string;
  trigger_type?: string;
  nodes: Array<{ id: string; node_type: string; label: string; position_x: number; position_y: number; config?: Record<string, any> }>;
  edges: Array<{ id?: string; source_node_id: string; target_node_id: string; label?: string | null }>;
};

const previewColors: Record<string, string> = {
  input: '#22c55e', output: '#d4a017', samurai: '#4a8cc7', office: '#14b8a6',
  logic: '#f59e0b', approval: '#ef4444', subflow: '#8b5cf6', notification: '#ec4899',
};

export function AgentFlowTemplatePreview({ reference, onClose }: { reference: string; onClose: () => void }) {
  const [detail, setDetail] = useState<TemplateDetail | null>(null);
  const [selected, setSelected] = useState<any | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    setDetail(null); setSelected(null); setError('');
    const isFlow = reference.startsWith('flow:');
    const identifier = reference.split(':').slice(1).join(':');
    const url = isFlow
      ? `/api/v1/agent-flows/${encodeURIComponent(identifier)}`
      : `/api/v1/agent-flows/templates/${encodeURIComponent(identifier)}`;
    axios.get(url)
      .then((response) => setDetail(response.data?.data))
      .catch((requestError) => setError(requestError?.response?.data?.detail || 'Could not open this AgentFlow template.'));
  }, [reference]);

  const previewNodes: Node[] = (detail?.nodes || []).map((node) => ({
    id: node.id,
    type: 'default',
    position: { x: node.position_x, y: node.position_y },
    data: { label: node.label, nodeType: node.node_type, config: node.config || {} },
    style: {
      width: 190, border: `1px solid ${previewColors[node.node_type] || '#4a8cc7'}`,
      borderRadius: 9, background: '#0e1225', color: '#c8d0d8', fontWeight: 700,
    },
  }));
  const previewEdges: Edge[] = (detail?.edges || []).map((edge, index) => ({
    id: edge.id || `preview-edge-${index}`, source: edge.source_node_id, target: edge.target_node_id,
    label: edge.label || undefined, animated: true, style: { stroke: '#4a8cc7', strokeWidth: 2 },
  }));

  return <div className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-6" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="w-full max-w-6xl h-[82vh] rounded-xl border border-shogun-border bg-[#080b16] shadow-2xl overflow-hidden flex flex-col">
      <header className="flex items-center justify-between px-5 py-4 border-b border-shogun-border">
        <div><div className="flex items-center gap-2"><Eye className="w-4 h-4 text-shogun-blue" /><h3 className="font-bold">{detail?.name || 'Opening AgentFlow…'}</h3></div>{detail && <p className="text-[10px] text-shogun-subdued mt-1">{detail.category || 'Saved AgentFlow'} · {detail.nodes.length} individual nodes · read-only preview</p>}</div>
        <button onClick={onClose} className="p-2 rounded border border-shogun-border text-shogun-subdued hover:text-white"><X className="w-4 h-4" /></button>
      </header>
      {error ? <div className="m-5 p-4 border border-red-500/30 text-red-300 rounded">{error}</div> : !detail ? <div className="flex-1 flex items-center justify-center text-sm text-shogun-subdued">Loading the AgentFlow nodes…</div> : <div className="grid grid-cols-[minmax(0,1fr)_280px] flex-1 min-h-0">
        <div className="bg-[#060913]">
          {/* The preview and builder are separate canvases and must not share a React Flow store. */}
          <ReactFlowProvider>
            <ReactFlow key={reference} nodes={previewNodes} edges={previewEdges} fitView fitViewOptions={{ padding: 0.18 }} nodesDraggable={false} nodesConnectable={false} elementsSelectable onNodeClick={(_, node) => setSelected(node.data)}>
              <Background variant={BackgroundVariant.Dots} color="#26305d" gap={22} /><Controls /><MiniMap />
            </ReactFlow>
          </ReactFlowProvider>
        </div>
        <aside className="border-l border-shogun-border p-4 overflow-y-auto">
          {selected ? <><div className="text-[9px] uppercase text-shogun-blue font-bold">{selected.nodeType} node</div><h4 className="font-bold text-sm mt-1">{selected.label}</h4><div className="text-[9px] uppercase text-shogun-subdued mt-5 mb-2">Configuration</div><pre className="text-[10px] whitespace-pre-wrap break-words p-3 rounded bg-[#050710] border border-shogun-border">{JSON.stringify(selected.config, null, 2)}</pre></> : <div className="text-xs text-shogun-subdued leading-relaxed">Select an individual node to inspect its type and configuration.</div>}
        </aside>
      </div>}
    </div>
  </div>;
}

class AgentFlowEditorBoundary extends Component<
  { children: ReactNode; onClose: () => void },
  { error: Error | null }
> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('The embedded AgentFlow editor could not be rendered.', error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return <div className="flex h-full items-center justify-center bg-[#050508] p-6">
      <div className="w-full max-w-lg rounded-xl border border-red-500/30 bg-[#0e1225] p-6 text-center shadow-2xl">
        <h2 className="text-base font-bold text-red-300">The AgentFlow editor could not open</h2>
        <p className="mt-2 text-xs leading-relaxed text-shogun-subdued">The Flow Stack is still safe. Close this view and try the AgentFlow again.</p>
        <p className="mt-3 rounded border border-red-500/20 bg-black/20 p-2 text-[10px] text-red-200">{this.state.error.message}</p>
        <button type="button" onClick={this.props.onClose} className="mt-5 rounded border border-shogun-border px-4 py-2 text-xs font-bold text-shogun-text hover:border-shogun-blue">BACK TO FLOW STACK</button>
      </div>
    </div>;
  }
}

function EmbeddedAgentFlowEditor({
  flow, onClose, agents, routingProfiles, availableFlows,
}: {
  flow: AgentFlowData;
  onClose: () => void;
  agents: any[];
  routingProfiles: any[];
  availableFlows: FlowListItem[];
}) {
  return <div className="fixed inset-0 z-[100] overflow-hidden bg-[#050508] p-3" data-testid="embedded-agent-flow-editor">
    <AgentFlowEditorBoundary onClose={onClose}>
      <ReactFlowProvider>
        <AgentFlowCanvas
          key={flow.id}
          flow={flow}
          onBack={onClose}
          onFlowUpdate={() => undefined}
          agents={agents}
          routingProfiles={routingProfiles}
          availableFlows={availableFlows}
        />
      </ReactFlowProvider>
    </AgentFlowEditorBoundary>
  </div>;
}

function FlowStackBuilder({ seed }: { seed: CatalogTemplate | null }) {
  const [templates, setTemplates] = useState<CatalogTemplate[]>([]);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
  const [selectedEdgeIds, setSelectedEdgeIds] = useState<string[]>([]);
  const [orchestratorOpen, setOrchestratorOpen] = useState(true);
  const [search, setSearch] = useState('');
  const [templateCategory, setTemplateCategory] = useState('All');
  const [stackCategory, setStackCategory] = useState('My Templates');
  const [name, setName] = useState('New Flow Stack');
  const [description, setDescription] = useState('');
  const [objective, setObjective] = useState('Complete the stack and verify every flow output.');
  const [modelProfile, setModelProfile] = useState('balanced');
  const [failurePolicy, setFailurePolicy] = useState('pause');
  const [maxRuntime, setMaxRuntime] = useState(1440);
  const [maxIterations, setMaxIterations] = useState(100);
  const [maxRetries, setMaxRetries] = useState(3);
  const [checkpointFrequency, setCheckpointFrequency] = useState('after_each_subflow');
  const [approvalPolicy, setApprovalPolicy] = useState('step_based');
  const [artifactPolicy, setArtifactPolicy] = useState('retain_all');
  const [outputPublication, setOutputPublication] = useState('summary_and_final');
  const [saving, setSaving] = useState(false);
  const [savedStackId, setSavedStackId] = useState('');
  const [stackStatus, setStackStatus] = useState<'draft' | 'active' | 'paused'>('draft');
  const [changingStatus, setChangingStatus] = useState(false);
  const [notice, setNotice] = useState('');
  const [editorFlow, setEditorFlow] = useState<AgentFlowData | null>(null);
  const [openingFlowId, setOpeningFlowId] = useState<string | null>(null);
  const openingFlowRef = useRef(false);
  const autoCenteredSeedRef = useRef<CatalogTemplate | null>(null);
  const [agents, setAgents] = useState<any[]>([]);
  const [routingProfiles, setRoutingProfiles] = useState<any[]>([]);
  const [availableFlows, setAvailableFlows] = useState<FlowListItem[]>([]);
  const reactFlow = useReactFlow();
  const nodesInitialized = useNodesInitialized();

  const centerStack = useCallback(() => {
    if (!nodes.length) {
      setNotice('Add an AgentFlow template before centering the canvas.');
      return;
    }
    const bounds = reactFlow.getNodesBounds(nodes);
    void (async () => {
      await reactFlow.fitView({ padding: 0.2, duration: 0, maxZoom: 1.15 });
      const viewport = reactFlow.getViewport();
      await reactFlow.setViewport({
        ...viewport,
        y: 72 - bounds.y * viewport.zoom,
      }, { duration: 450 });
    })();
  }, [nodes, reactFlow]);

  useEffect(() => {
    Promise.all([
      axios.get('/api/v1/agent-flows/templates'),
      axios.get('/api/v1/agents?agent_type=samurai'),
      axios.get('/api/v1/model-routing-profiles'),
      axios.get('/api/v1/agent-flows'),
    ]).then(([templateResponse, agentResponse, routingResponse, flowResponse]) => {
      setTemplates(templateResponse.data?.data?.templates || []);
      setAgents(agentResponse.data?.data || []);
      setRoutingProfiles(routingResponse.data?.data || []);
      setAvailableFlows(flowResponse.data?.data || []);
    });
  }, []);

  const openAgentFlowEditor = useCallback(async (stackNode: Node) => {
    if (openingFlowRef.current) return;
    const existingFlowId = stackNode.data.flowId ? String(stackNode.data.flowId) : '';
    const templateId = stackNode.data.templateId ? String(stackNode.data.templateId) : '';
    if (!existingFlowId && !templateId) {
      setNotice(`“${String(stackNode.data.label || 'This AgentFlow')}” is not linked to an AgentFlow template.`);
      return;
    }
    openingFlowRef.current = true;
    setOpeningFlowId(stackNode.id);
    setNotice('Opening the editable AgentFlow...');
    try {
      let resolvedFlowId = existingFlowId;
      if (!resolvedFlowId) {
        const created = await axios.post('/api/v1/agent-flows/from-template', { template_id: templateId }, { timeout: 15000 });
        resolvedFlowId = String(created.data?.data?.id || '');
        if (!resolvedFlowId) throw new Error('The AgentFlow template could not be instantiated.');
        setNodes((current) => current.map((node) => node.id === stackNode.id ? {
          ...node,
          data: { ...node.data, flowId: resolvedFlowId, templateId: undefined },
        } : node));
      }
      const [flowResponse, listResponse] = await Promise.all([
        axios.get(`/api/v1/agent-flows/${encodeURIComponent(resolvedFlowId)}`, { timeout: 15000 }),
        axios.get('/api/v1/agent-flows', { timeout: 15000 }),
      ]);
      setAvailableFlows(listResponse.data?.data || []);
      const editableFlow = flowResponse.data?.data;
      if (!editableFlow?.id || !Array.isArray(editableFlow.nodes) || !Array.isArray(editableFlow.edges)) {
        throw new Error('The server returned an incomplete AgentFlow.');
      }
      setEditorFlow(editableFlow);
      setNotice('');
    } catch (error: any) {
      setNotice(error?.response?.data?.detail || error?.message || 'Could not open this AgentFlow.');
    } finally {
      openingFlowRef.current = false;
      setOpeningFlowId(null);
    }
  }, [setNodes]);

  useEffect(() => {
    if (!seed || !templates.length) return;
    const seededNodes = seed.builder_nodes?.length
      ? seed.builder_nodes.map((item) => ({
          id: item.id, position: { x: item.position_x, y: item.position_y }, type: 'stackFlow',
          data: { label: item.label, templateId: item.template_id, flowId: item.flow_id, category: seed.category },
        } as Node))
      : (seed.flow_template_ids || []).map((templateId, index) => {
          const template = templates.find((item) => item.id === templateId);
          return {
            id: crypto.randomUUID(), position: { x: 340 + index * 300, y: 220 }, type: 'stackFlow',
            data: { label: template?.name || templateId, templateId, category: template?.category || seed.category },
          } as Node;
        });
    const seededEdges: Edge[] = seed.builder_edges?.length
      ? seed.builder_edges.map((edge, index) => ({ id: `seed-edge-${index}`, source: edge.source, target: edge.target, animated: true, style: { stroke: '#8b5cf6', strokeWidth: 2 } }))
      : seededNodes.slice(1).map((node, index) => ({ id: `seed-edge-${index}`, source: seededNodes[index].id, target: node.id, animated: true, style: { stroke: '#8b5cf6', strokeWidth: 2 } }));
    setNodes(seededNodes);
    setEdges(seededEdges);
    setName(seed.name);
    setDescription(seed.description);
    setStackCategory(seed.category || 'My Templates');
    setTemplateCategory('All');
    setSavedStackId('');
    setStackStatus('draft');
    if (seed.orchestrator_config) {
      setObjective((current) => seed.orchestrator_config?.objective || current);
      setModelProfile(seed.orchestrator_config.model_routing_profile || 'balanced');
      setFailurePolicy(seed.orchestrator_config.failure_policy || 'retry');
      setMaxRuntime(seed.orchestrator_config.max_runtime_minutes || 1440);
      setMaxIterations(seed.orchestrator_config.max_iterations || 100);
      setMaxRetries(seed.orchestrator_config.max_retry_attempts_per_step ?? 3);
      setCheckpointFrequency(seed.orchestrator_config.checkpoint_frequency || 'after_each_subflow');
      setApprovalPolicy(seed.orchestrator_config.approval_policy || 'step_based');
      setArtifactPolicy(seed.orchestrator_config.artifact_policy || 'retain_all');
      setOutputPublication(seed.orchestrator_config.output_publication || 'summary_and_final');
    }
    setNotice(`Opened “${seed.name}” in the Stack Builder. Click any AgentFlow block to inspect its internal nodes.`);
  }, [seed, templates, setEdges, setNodes]);

  useEffect(() => {
    if (!seed || !nodes.length || !nodesInitialized || autoCenteredSeedRef.current === seed) return;
    const frame = window.requestAnimationFrame(() => {
      centerStack();
      autoCenteredSeedRef.current = seed;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [centerStack, nodes.length, nodesInitialized, seed]);

  const categories = useMemo(() => ['All', ...Array.from(new Set(templates.map((item) => item.category))).sort()], [templates]);
  const visible = useMemo(() => templates.filter((item) =>
    (templateCategory === 'All' || item.category === templateCategory) &&
    `${item.name} ${item.description}`.toLowerCase().includes(search.toLowerCase())
  ), [templates, templateCategory, search]);

  const deleteStackNode = useCallback((nodeId: string) => {
    setNodes((current) => current.filter((node) => node.id !== nodeId));
    setEdges((current) => current.filter((edge) => edge.source !== nodeId && edge.target !== nodeId));
    setSelectedNodeIds((current) => current.filter((id) => id !== nodeId));
  }, [setEdges, setNodes]);

  const deleteSelected = useCallback(() => {
    if (!selectedNodeIds.length && !selectedEdgeIds.length) return;
    const removedNodes = new Set(selectedNodeIds);
    const removedEdges = new Set(selectedEdgeIds);
    setNodes((current) => current.filter((node) => !removedNodes.has(node.id)));
    setEdges((current) => current.filter((edge) =>
      !removedEdges.has(edge.id) && !removedNodes.has(edge.source) && !removedNodes.has(edge.target)
    ));
    setSelectedNodeIds([]);
    setSelectedEdgeIds([]);
  }, [selectedEdgeIds, selectedNodeIds, setEdges, setNodes]);

  const onSelectionChange = useCallback(({ nodes: selectedNodes, edges: selectedEdges }: { nodes: Node[]; edges: Edge[] }) => {
    const nextNodeIds = selectedNodes.map((node) => node.id);
    const nextEdgeIds = selectedEdges.map((edge) => edge.id);
    setSelectedNodeIds((current) => current.length === nextNodeIds.length && current.every((id, index) => id === nextNodeIds[index]) ? current : nextNodeIds);
    setSelectedEdgeIds((current) => current.length === nextEdgeIds.length && current.every((id, index) => id === nextEdgeIds[index]) ? current : nextEdgeIds);
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Delete' && event.key !== 'Backspace') return;
      const target = event.target;
      if (target instanceof HTMLElement && target.closest('input, textarea, select, [contenteditable="true"]')) return;
      event.preventDefault();
      deleteSelected();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [deleteSelected]);

  const stackActions = useMemo(() => ({
    openEditor: (nodeId: string) => {
      const node = nodes.find((item) => item.id === nodeId);
      if (node) void openAgentFlowEditor(node);
    },
    deleteNode: deleteStackNode,
  }), [deleteStackNode, nodes, openAgentFlowEditor]);

  const onStackNodeClick = useCallback((_: unknown, node: Node) => {
    void openAgentFlowEditor(node);
  }, [openAgentFlowEditor]);

  const onConnect = useCallback((connection: Connection) => {
    setEdges((current) => addEdge({ ...connection, animated: true, style: { stroke: '#8b5cf6', strokeWidth: 2 } }, current));
  }, [setEdges]);

  const onReconnect = useCallback((oldEdge: Edge, connection: Connection) => {
    setEdges((current) => reconnectEdge(oldEdge, connection, current));
  }, [setEdges]);

  const onDragOver = useCallback((event: DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
  }, []);

  const onDrop = useCallback((event: DragEvent) => {
    event.preventDefault();
    const raw = event.dataTransfer.getData('application/shogun-flow-template');
    if (!raw) return;
    const template = JSON.parse(raw) as CatalogTemplate;
    const position = reactFlow.screenToFlowPosition({ x: event.clientX, y: event.clientY });
    const id = crypto.randomUUID();
    setNodes((current) => [...current, {
      id, position, type: 'stackFlow',
      data: { label: template.name, templateId: template.id, category: template.category },
    }]);
  }, [reactFlow, setNodes]);

  const saveStack = async (saveAsTemplate: boolean) => {
    const flowNodes = nodes;
    if (!flowNodes.length) return setNotice('Drag at least one AgentFlow template onto the canvas.');
    if (flowNodes.length > 1 && !edges.length) return setNotice('Connect the AgentFlow templates before saving.');
    setSaving(true); setNotice('');
    try {
      const response = await axios.post('/api/v1/agent-flows/flow-stacks/compose', {
        name, description, category: stackCategory,
        nodes: flowNodes.map((node) => ({
          id: node.id, template_id: node.data.templateId || undefined,
          flow_id: node.data.flowId || undefined, label: node.data.label,
          position_x: node.position.x, position_y: node.position.y,
        })),
        edges: edges.map((edge) => ({ id: edge.id, source: edge.source, target: edge.target })),
        orchestrator_config: {
          objective, model_routing_profile: modelProfile, failure_policy: failurePolicy,
          checkpoint_frequency: checkpointFrequency, verification_required: true,
          max_runtime_minutes: maxRuntime, max_iterations: maxIterations,
          max_retry_attempts_per_step: maxRetries, context_compaction: 'enabled',
          approval_policy: approvalPolicy, artifact_policy: artifactPolicy,
          output_publication: outputPublication,
          timeout_seconds: Math.min(maxRuntime * 60, 86400),
        },
        save_as_template: saveAsTemplate,
      });
      setSavedStackId(String(response.data.data.id));
      setStackStatus(response.data.data.status === 'active' ? 'active' : response.data.data.status === 'paused' ? 'paused' : 'draft');
      setNotice(saveAsTemplate
        ? `Stack and reusable template saved: ${response.data.data.name}`
        : `Flow Stack saved: ${response.data.data.name}`);
    } catch (error: any) {
      setNotice(error?.response?.data?.detail || 'Could not save the Flow Stack.');
    } finally { setSaving(false); }
  };

  const changeStackStatus = async () => {
    if (!savedStackId) return setNotice('Save the Flow Stack before activating it.');
    const activate = stackStatus !== 'active';
    setChangingStatus(true);
    try {
      const response = await axios.post(`/api/v1/agent-flows/${encodeURIComponent(savedStackId)}/${activate ? 'activate' : 'pause'}`);
      setStackStatus(response.data?.data?.status === 'active' ? 'active' : 'paused');
      setNotice(activate ? 'Flow Stack activated and available for execution.' : 'Flow Stack deactivated. Existing history is preserved.');
    } catch (error: any) {
      setNotice(error?.response?.data?.detail || `Could not ${activate ? 'activate' : 'deactivate'} the Flow Stack.`);
    } finally { setChangingStatus(false); }
  };

  return (
    <div className="grid grid-cols-[300px_minmax(0,1fr)] gap-4 min-h-[690px]">
      <aside className="shogun-card !p-4 overflow-hidden flex flex-col">
        <div className="flex items-center gap-2 mb-3"><Boxes className="w-4 h-4 text-shogun-blue" /><b className="text-xs">AGENTFLOW TEMPLATES</b></div>
        <div className="relative mb-2"><Search className="absolute w-3.5 h-3.5 left-2.5 top-2.5 text-shogun-subdued" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search templates" className="w-full bg-[#080b16] border border-shogun-border rounded pl-8 pr-2 py-2 text-xs" /></div>
        <select value={templateCategory} onChange={(e) => setTemplateCategory(e.target.value)} className="bg-[#080b16] border border-shogun-border rounded p-2 text-xs mb-3">
          {categories.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <div className="space-y-2 overflow-y-auto pr-1 flex-1">
          {visible.map((template) => (
            <div key={template.id} draggable onDragStart={(event) => {
              event.dataTransfer.setData('application/shogun-flow-template', JSON.stringify(template));
              event.dataTransfer.effectAllowed = 'copy';
            }} className="p-3 rounded-lg border border-shogun-border bg-[#0a0e1a] hover:border-shogun-blue cursor-grab active:cursor-grabbing">
              <div className="text-xs font-bold text-shogun-text">{template.name}</div>
              <div className="flex items-center justify-between mt-1"><div className="text-[9px] text-shogun-blue uppercase">{template.category}</div><div className="text-[9px] text-shogun-subdued">DRAG TO STACK</div></div>
            </div>
          ))}
        </div>
      </aside>

      <section className="rounded-xl border border-shogun-border bg-[#060913] overflow-hidden relative">
        <div className="absolute z-20 top-3 left-3 flex items-center gap-2">
          <div className="px-3 py-2 rounded bg-[#0e1225]/95 border border-shogun-border text-[10px] text-shogun-subdued">
            Drag to reorder · connect handles · click a card to edit
          </div>
          <button
            type="button"
            onClick={centerStack}
            title="Fit the complete Flow Stack and move it to the top of the canvas"
            className="flex items-center gap-1.5 rounded border border-shogun-blue/40 bg-[#0e1225]/95 px-3 py-2 text-[10px] font-bold text-shogun-blue shadow-lg hover:border-shogun-blue hover:bg-shogun-blue/10"
          >
            <LocateFixed className="h-3.5 w-3.5" /> CENTER FLOW
          </button>
          {(selectedNodeIds.length > 0 || selectedEdgeIds.length > 0) && <button onClick={deleteSelected} className="flex items-center gap-1.5 rounded border border-red-500/30 bg-[#180b14]/95 px-3 py-2 text-[10px] font-bold text-red-300 hover:bg-red-500/15"><Trash2 className="h-3 w-3" />DELETE SELECTED ({selectedNodeIds.length + selectedEdgeIds.length})</button>}
        </div>
        <StackActionsContext.Provider value={stackActions}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={stackNodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onReconnect={onReconnect}
          onNodeClick={onStackNodeClick}
          onSelectionChange={onSelectionChange}
          onDrop={onDrop}
          onDragOver={onDragOver}
          edgesReconnectable
          deleteKeyCode={null}
          fitView
        >
          <Background variant={BackgroundVariant.Dots} color="#26305d" gap={22} />
          <Controls /><MiniMap nodeColor="#4a8cc7" />
        </ReactFlow>
        </StackActionsContext.Provider>

      <aside className={cn('absolute z-30 top-3 right-3 w-[360px] rounded-xl border border-purple-400/30 bg-[#0b0e1c]/95 shadow-2xl backdrop-blur transition-all', orchestratorOpen ? 'max-h-[calc(100%-24px)] overflow-y-auto p-4 space-y-4' : 'w-auto p-2')}>
        <div className="flex items-center justify-between gap-4"><div className="flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-purple-400" /><b className="text-xs">FLOW STACK SETTINGS</b></div><button type="button" onClick={() => setOrchestratorOpen((current) => !current)} title={orchestratorOpen ? 'Collapse settings' : 'Expand settings'} className="rounded border border-purple-400/20 p-1 text-purple-300 hover:bg-purple-500/10">{orchestratorOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}</button></div>
        {orchestratorOpen && <>
        <div className="group relative rounded-lg border border-purple-400/20 bg-purple-500/5 p-2.5 text-[9px] leading-relaxed text-shogun-subdued"><div className="flex items-center gap-1.5 font-bold uppercase tracking-wider text-purple-300"><Info className="h-3.5 w-3.5" /> How the Orchestrator works</div><p className="mt-1">It supervises the complete Stack: passing output between AgentFlows, saving checkpoints, retrying failures, compacting long-running context, and verifying results before completion.</p><div className="pointer-events-none absolute right-2 top-2 hidden w-64 rounded-lg border border-purple-400/30 bg-[#080b16] p-3 text-[9px] normal-case text-shogun-text shadow-2xl group-hover:block">Configure the goal and safety limits here. Activate the saved Stack when it is ready to run. Pausing a Stack prevents new executions without deleting it.</div></div>
        <label className="block text-[9px] uppercase text-shogun-subdued">Stack name<input value={name} onChange={(e) => setName(e.target.value)} className="mt-1 w-full bg-[#080b16] border border-shogun-border rounded p-2 text-xs text-shogun-text" /></label>
        <label className="block text-[9px] uppercase text-shogun-subdued">Stack category<select value={stackCategory} onChange={(e) => setStackCategory(e.target.value)} className="mt-1 w-full bg-[#080b16] border border-shogun-border rounded p-2 text-xs text-shogun-text">{Object.keys(STACK_CATEGORY_COLORS).map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label className="block text-[9px] uppercase text-shogun-subdued">Description<textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} className="mt-1 w-full bg-[#080b16] border border-shogun-border rounded p-2 text-xs text-shogun-text" /></label>
        <label className="block text-[9px] uppercase text-shogun-subdued">Objective<textarea value={objective} onChange={(e) => setObjective(e.target.value)} rows={4} className="mt-1 w-full bg-[#080b16] border border-purple-500/30 rounded p-2 text-xs text-shogun-text" /></label>
        <label className="block text-[9px] uppercase text-shogun-subdued">Model routing<select value={modelProfile} onChange={(e) => setModelProfile(e.target.value)} className="mt-1 w-full bg-[#080b16] border border-shogun-border rounded p-2 text-xs"><option>balanced</option><option>quality</option><option>speed</option><option>cost</option></select></label>
        <label className="block text-[9px] uppercase text-shogun-subdued">On failure<select value={failurePolicy} onChange={(e) => setFailurePolicy(e.target.value)} className="mt-1 w-full bg-[#080b16] border border-shogun-border rounded p-2 text-xs"><option>pause</option><option>retry</option><option>continue_with_error</option><option>fail_stack</option></select></label>
        <div className="grid grid-cols-2 gap-2"><label className="block text-[9px] uppercase text-shogun-subdued">Max runtime (min)<input type="number" min={1} max={1440} value={maxRuntime} onChange={(e) => setMaxRuntime(Number(e.target.value))} className="mt-1 w-full bg-[#080b16] border border-shogun-border rounded p-2 text-xs" /></label><label className="block text-[9px] uppercase text-shogun-subdued">Max iterations<input type="number" min={1} max={500} value={maxIterations} onChange={(e) => setMaxIterations(Number(e.target.value))} className="mt-1 w-full bg-[#080b16] border border-shogun-border rounded p-2 text-xs" /></label></div>
        <label className="block text-[9px] uppercase text-shogun-subdued">Checkpoints<select value={checkpointFrequency} onChange={(e) => setCheckpointFrequency(e.target.value)} className="mt-1 w-full bg-[#080b16] border border-shogun-border rounded p-2 text-xs"><option value="after_each_subflow">After every AgentFlow</option><option value="after_each_step">After every step</option><option value="timed">Timed</option></select></label>
        <div className="grid grid-cols-2 gap-2"><label className="block text-[9px] uppercase text-shogun-subdued">Retries<input type="number" min={0} max={10} value={maxRetries} onChange={(e) => setMaxRetries(Number(e.target.value))} className="mt-1 w-full bg-[#080b16] border border-shogun-border rounded p-2 text-xs" /></label><label className="block text-[9px] uppercase text-shogun-subdued">Approval<select value={approvalPolicy} onChange={(e) => setApprovalPolicy(e.target.value)} className="mt-1 w-full bg-[#080b16] border border-shogun-border rounded p-2 text-xs"><option value="step_based">Step based</option><option value="inherited">Inherited</option><option value="always_required_for_high_risk">High risk</option></select></label></div>
        <label className="block text-[9px] uppercase text-shogun-subdued">Artifacts<select value={artifactPolicy} onChange={(e) => setArtifactPolicy(e.target.value)} className="mt-1 w-full bg-[#080b16] border border-shogun-border rounded p-2 text-xs"><option value="retain_all">Retain all</option><option value="retain_final_only">Final only</option><option value="retain_selected">Selected</option></select></label>
        <label className="block text-[9px] uppercase text-shogun-subdued">Published output<select value={outputPublication} onChange={(e) => setOutputPublication(e.target.value)} className="mt-1 w-full bg-[#080b16] border border-purple-400/30 rounded p-2 text-xs"><option value="summary_and_final">Orchestrator summary + final Flow</option><option value="summary_only">Orchestrator summary only</option><option value="final_only">Final Flow only</option><option value="all_steps">All Flow outputs (legacy)</option></select><span className="mt-1 block normal-case leading-relaxed text-[8px] text-shogun-subdued">Intermediate results are always retained internally and handed to the next Flow. This setting only controls what is published at the end.</span></label>
        <div className="flex items-center justify-between text-[10px] text-shogun-subdued"><span>{nodes.length} flows</span><span>{edges.length} connections</span></div>
        <button disabled={!savedStackId || changingStatus} onClick={changeStackStatus} title={!savedStackId ? 'Save the Stack before activating it' : stackStatus === 'active' ? 'Deactivate this Stack' : 'Activate this Stack'} className={cn('w-full flex justify-center items-center gap-2 py-2 rounded text-xs font-bold border disabled:cursor-not-allowed disabled:opacity-40', stackStatus === 'active' ? 'border-green-400/40 bg-green-500/15 text-green-300' : 'border-shogun-border bg-[#080b16] text-shogun-subdued')}><Power className="w-3.5 h-3.5" />{changingStatus ? 'UPDATING...' : stackStatus === 'active' ? 'ACTIVE — CLICK TO DEACTIVATE' : savedStackId ? 'ACTIVATE STACK' : 'SAVE STACK TO ACTIVATE'}</button>
        <button onClick={() => { setNodes([]); setEdges([]); setSelectedNodeIds([]); setSelectedEdgeIds([]); }} className="w-full flex justify-center items-center gap-2 py-2 border border-red-500/25 text-red-400 rounded text-xs"><Trash2 className="w-3.5 h-3.5" /> CLEAR CANVAS</button>
        <button disabled={saving} onClick={() => saveStack(false)} className="w-full flex justify-center items-center gap-2 py-2 bg-shogun-blue rounded text-white font-bold text-xs"><Save className="w-3.5 h-3.5" /> SAVE STACK</button>
        <button disabled={saving} onClick={() => saveStack(true)} className="w-full flex justify-center items-center gap-2 py-2 bg-purple-500/20 border border-purple-400/40 text-purple-300 rounded font-bold text-xs"><BookmarkPlus className="w-3.5 h-3.5" /> SAVE AS TEMPLATE</button>
        {notice && <div className="p-2 rounded border border-shogun-border bg-[#080b16] text-[10px] text-shogun-text">{notice}</div>}
        </>}
      </aside>
      </section>
      {openingFlowId && <div role="status" className="fixed bottom-5 left-1/2 z-[90] -translate-x-1/2 rounded-lg border border-shogun-blue/30 bg-[#0e1225] px-4 py-3 shadow-2xl"><div className="flex items-center gap-3 text-sm text-shogun-text"><Loader2 className="w-5 h-5 animate-spin text-shogun-blue" /> Opening editable AgentFlow...</div></div>}
      {editorFlow && <EmbeddedAgentFlowEditor flow={editorFlow} onClose={() => setEditorFlow(null)} agents={agents} routingProfiles={routingProfiles} availableFlows={availableFlows} />}
    </div>
  );
}

const STACK_CATEGORY_COLORS: Record<string, string> = {
  'Continuous Intelligence': '#22c55e',
  'Strategy & Transformation': '#3b82f6',
  'Product & Innovation': '#f59e0b',
  'Growth & Brand': '#ec4899',
  'Customer Operations': '#06b6d4',
  'Data & Executive Operations': '#8b5cf6',
  'Risk & Compliance': '#ef4444',
  'People & Capability': '#14b8a6',
  'Incident & Resilience': '#f97316',
  'Knowledge & Publishing': '#6366f1',
  'My Templates': '#d4a017',
};

function StackTemplateGallery({ onOpen }: { onOpen: (template: CatalogTemplate) => void }) {
  const {
    ui: templateUi,
    category: translateCategory,
    flowStack: translateStackTemplate,
  } = useTemplateCatalog();
  const [templates, setTemplates] = useState<CatalogTemplate[]>([]);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('All');
  const [notice, setNotice] = useState('');
  const load = useCallback(() => axios.get('/api/v1/agent-flows/flow-stack-templates').then((response) => setTemplates(response.data?.data?.templates || [])), []);
  useEffect(() => { load(); }, [load]);
  const categories = ['All', ...Array.from(new Set(templates.map((item) => item.category))).sort()];
  const visible = templates
    .filter((item) => category === 'All' || item.category === category)
    .map((item) => translateStackTemplate(item))
    .filter((item) => `${item.name} ${item.description} ${item.category}`.toLowerCase().includes(search.toLowerCase()));
  const useTemplate = async (id: string) => {
    setNotice(templateUi('building_stack', 'Building your Flow Stack...'));
    try {
      const response = await axios.post('/api/v1/agent-flows/flow-stacks/from-template', { template_id: id });
      setNotice(`Created: ${response.data.data.name}`);
    } catch (error: any) { setNotice(error?.response?.data?.detail || templateUi('could_not_create_stack', 'Could not create this stack.')); }
  };
  void useTemplate;
  return <div className="space-y-4">
    <div className="flex gap-3"><div className="relative flex-1"><Search className="absolute w-4 h-4 left-3 top-3 text-shogun-subdued" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={templateUi('search_stack_templates', 'Search Flow Stack templates')} className="w-full bg-[#0e1225] border border-shogun-border rounded-lg pl-10 p-2.5 text-sm" /></div><select value={category} onChange={(e) => setCategory(e.target.value)} className="bg-[#0e1225] border border-shogun-border rounded-lg px-3 text-xs" style={{ color: category === 'All' ? '#c8d0d8' : STACK_CATEGORY_COLORS[category] || '#c8d0d8' }}>{categories.map((item) => <option key={item} value={item} style={{ color: item === 'All' ? '#c8d0d8' : STACK_CATEGORY_COLORS[item] || '#c8d0d8' }}>{item === 'All' ? templateUi('all_stack_categories', 'All Flow Stack Categories') : `● ${translateCategory(item)}`}</option>)}</select><button onClick={load} className="p-2.5 border border-shogun-border rounded-lg"><RefreshCw className="w-4 h-4" /></button></div>
    <div className="text-xs text-shogun-subdued">{templates.length} {templateUi('reusable_templates', 'reusable templates')} · {visible.length} {templateUi('shown', 'shown')}</div>
    {notice && <div className="p-3 border border-shogun-blue/30 bg-shogun-blue/10 rounded text-xs">{notice}</div>}
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">{visible.map((template) => {
      const sourceCategory = templates.find((item) => item.id === template.id)?.category || template.category;
      const color = STACK_CATEGORY_COLORS[sourceCategory] || '#7a8899';
      return <div key={template.id} onClick={() => onOpen(template)} className="shogun-card relative !p-4 flex flex-col min-h-[210px] cursor-pointer hover:border-purple-400/50 transition-colors overflow-hidden"><div className="absolute inset-x-0 top-0 h-0.5" style={{ backgroundColor: color }} /><div className="flex justify-between"><Layers3 className="w-5 h-5" style={{ color }} /><span className="text-[9px] uppercase rounded px-2 py-1 font-bold" style={{ color, backgroundColor: `${color}18` }}>{template.category}</span></div><h3 className="font-bold text-sm mt-3">{template.name}</h3><p className="text-[11px] text-shogun-subdued mt-2 flex-1">{template.description}</p><div className="flex gap-2 my-3"><span className="text-[9px] px-2 py-1 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20">{template.flow_count || 0} {templateUi('phases', 'phases').toUpperCase()}</span><span className="text-[9px] px-2 py-1 rounded bg-shogun-blue/10 text-shogun-blue border border-shogun-blue/20">{template.duration_label || templateUi('resumable', 'Resumable')}</span></div><button onClick={(event) => { event.stopPropagation(); onOpen(template); }} className="w-full px-3 py-2 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 text-[10px] font-bold">{templateUi('open_program', 'Open long-running program').toUpperCase()}</button></div>;
    })}</div>
  </div>;
}

function LegacyOrchestratorRuntime() {
  const [stacks, setStacks] = useState<SavedFlow[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [selected, setSelected] = useState('');
  const [objective, setObjective] = useState('Execute the selected Flow Stack and verify the final output.');
  const [notice, setNotice] = useState('');
  const refresh = useCallback(async () => {
    const [flowResponse, runResponse] = await Promise.all([axios.get('/api/v1/agent-flows'), axios.get('/api/v1/stacks/orchestrator')]);
    setStacks((flowResponse.data?.data || []).filter((item: SavedFlow) => item.flow_type === 'stack'));
    setRuns(runResponse.data?.data || []);
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  const createRun = async () => {
    if (!selected) return setNotice('Select a saved Flow Stack first.');
    try {
      const response = await axios.post('/api/v1/stacks/orchestrator/create', { mode: 'selected_stack', selected_stack_id: selected, objective, verification_required: true, checkpoint_frequency: 'after_each_subflow', failure_policy: 'pause' });
      await axios.post(`/api/v1/stacks/orchestrator/${response.data.data.id}/start`);
      setNotice('Flow Stack run started.'); await refresh();
    } catch (error: any) { setNotice(error?.response?.data?.detail || 'Could not start the run.'); }
  };
  const action = async (id: string, verb: string) => { await axios.post(`/api/v1/stacks/orchestrator/${id}/${verb}`); await refresh(); };
  return <div className="grid grid-cols-[360px_1fr] gap-4"><div className="shogun-card space-y-4"><div className="flex gap-2 items-center"><ShieldCheck className="w-5 h-5 text-purple-400" /><b>Flow Stack Runtime</b></div><select value={selected} onChange={(e) => setSelected(e.target.value)} className="w-full bg-[#080b16] border border-shogun-border rounded p-2 text-xs"><option value="">Select Flow Stack</option>{stacks.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select><textarea value={objective} onChange={(e) => setObjective(e.target.value)} rows={5} className="w-full bg-[#080b16] border border-shogun-border rounded p-2 text-xs" /><button onClick={createRun} className="w-full flex justify-center gap-2 items-center bg-purple-500/25 border border-purple-400/40 text-purple-200 py-2 rounded text-xs font-bold"><Play className="w-4 h-4" /> START FLOW STACK</button>{notice && <div className="text-xs text-shogun-subdued">{notice}</div>}</div><div className="space-y-3"><div className="flex justify-between"><b className="text-sm">FLOW STACK RUNS</b><button onClick={refresh}><RefreshCw className="w-4 h-4" /></button></div>{runs.length === 0 && <div className="shogun-card text-sm text-shogun-subdued">No stack runs yet.</div>}{runs.map((run) => <div key={run.id} className="shogun-card !p-4 flex justify-between items-center"><div><div className="font-bold text-sm">{run.objective}</div><div className="text-[10px] text-shogun-subdued uppercase mt-1">{run.status} · {run.posture || 'ready'}</div></div><div className="flex gap-2">{run.status === 'running' && <button onClick={() => action(run.id, 'pause')} title="Pause"><Pause className="w-4 h-4" /></button>}{run.status === 'paused' && <button onClick={() => action(run.id, 'resume')} title="Resume"><RotateCcw className="w-4 h-4" /></button>}{!['completed','cancelled','failed'].includes(run.status) && <button onClick={() => action(run.id, 'cancel')} title="Cancel"><CircleStop className="w-4 h-4 text-red-400" /></button>}</div></div>)}</div></div>;
}

void LegacyOrchestratorRuntime;

function OrchestratorRuntime() {
  const baseUrl = '/api/v1/stacks/orchestrator';
  const [stacks, setStacks] = useState<SavedFlow[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [selectedStack, setSelectedStack] = useState('');
  const [selectedRunId, setSelectedRunId] = useState('');
  const [selectedRun, setSelectedRun] = useState<any | null>(null);
  const [checkpoints, setCheckpoints] = useState<any[]>([]);
  const [artifacts, setArtifacts] = useState<any[]>([]);
  const [verifications, setVerifications] = useState<any[]>([]);
  const [objective, setObjective] = useState('Execute the selected Flow Stack and verify the final output.');
  const [criteria, setCriteria] = useState('Every AgentFlow produces a non-empty result\nAll required verification checks pass');
  const [notice, setNotice] = useState('');

  const refresh = useCallback(async () => {
    const [flowResponse, runResponse] = await Promise.all([axios.get('/api/v1/agent-flows'), axios.get(baseUrl)]);
    setStacks((flowResponse.data?.data || []).filter((item: SavedFlow) => item.flow_type === 'stack'));
    const nextRuns = runResponse.data?.data || [];
    setRuns(nextRuns);
    setSelectedRunId((current) => current || nextRuns[0]?.id || '');
  }, []);
  const loadRun = useCallback(async (runId: string) => {
    if (!runId) return;
    try {
      const [runResponse, checkpointResponse, artifactResponse, verificationResponse] = await Promise.all([
        axios.get(`${baseUrl}/${runId}`), axios.get(`${baseUrl}/${runId}/checkpoints`),
        axios.get(`${baseUrl}/${runId}/artifacts`), axios.get(`${baseUrl}/${runId}/verifications`),
      ]);
      setSelectedRun(runResponse.data?.data || null);
      setCheckpoints(checkpointResponse.data?.data || []);
      setArtifacts(artifactResponse.data?.data || []);
      setVerifications(verificationResponse.data?.data || []);
    } catch (error: any) { setNotice(error?.response?.data?.detail || 'Could not load the runtime trace.'); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    if (!selectedRunId) return;
    loadRun(selectedRunId);
    const timer = window.setInterval(() => { loadRun(selectedRunId); refresh(); }, 2000);
    return () => window.clearInterval(timer);
  }, [selectedRunId, loadRun, refresh]);

  const createRun = async () => {
    if (!selectedStack) return setNotice('Select a saved Flow Stack first.');
    try {
      const response = await axios.post(`${baseUrl}/create`, {
        mode: 'selected_stack', selected_stack_id: selectedStack, objective,
        success_criteria: criteria.split('\n').map((item) => item.trim()).filter(Boolean),
        verification_required: true, context_compaction: 'enabled',
        checkpoint_frequency: 'after_each_subflow', failure_policy: 'pause',
      });
      const runId = response.data.data.id;
      await axios.post(`${baseUrl}/${runId}/start`);
      setSelectedRunId(runId);
      setNotice('Run started with durable checkpoints and independent verification.');
      await refresh();
    } catch (error: any) { setNotice(error?.response?.data?.detail || 'Could not start the run.'); }
  };
  const action = async (id: string, verb: string) => {
    try { await axios.post(`${baseUrl}/${id}/${verb}`); await loadRun(id); await refresh(); }
    catch (error: any) { setNotice(error?.response?.data?.detail || `Could not ${verb} this run.`); }
  };
  const statusColor = (status: string) => ({
    completed: '#22c55e', passed: '#22c55e', running: '#38bdf8', retrying: '#f59e0b',
    paused: '#f59e0b', waiting_approval: '#c084fc', failed: '#ef4444', cancelled: '#7a8899',
    completed_with_errors: '#f97316',
  }[status] || '#7a8899');
  const terminal = ['completed', 'completed_with_errors', 'cancelled', 'failed'];

  return <div className="grid grid-cols-[340px_minmax(0,1fr)] gap-4">
    <div className="space-y-4">
      <div className="shogun-card space-y-3">
        <div className="flex gap-2 items-center"><ShieldCheck className="w-5 h-5 text-purple-400" /><b>Start governed run</b></div>
        <select value={selectedStack} onChange={(e) => setSelectedStack(e.target.value)} className="w-full bg-[#080b16] border border-shogun-border rounded p-2 text-xs"><option value="">Select Flow Stack</option>{stacks.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select>
        <label className="block text-[9px] uppercase text-shogun-subdued">Objective<textarea value={objective} onChange={(e) => setObjective(e.target.value)} rows={4} className="mt-1 w-full bg-[#080b16] border border-shogun-border rounded p-2 text-xs normal-case" /></label>
        <label className="block text-[9px] uppercase text-shogun-subdued">Success criteria — one per line<textarea value={criteria} onChange={(e) => setCriteria(e.target.value)} rows={3} className="mt-1 w-full bg-[#080b16] border border-shogun-border rounded p-2 text-xs normal-case" /></label>
        <button onClick={createRun} className="w-full flex justify-center gap-2 items-center bg-purple-500/25 border border-purple-400/40 text-purple-200 py-2 rounded text-xs font-bold"><Play className="w-4 h-4" /> START FLOW STACK</button>
        {notice && <div className="text-[10px] text-shogun-subdued">{notice}</div>}
      </div>
      <div className="space-y-2"><div className="flex justify-between"><b className="text-xs">CURRENT & RECENT RUNS</b><button onClick={refresh}><RefreshCw className="w-4 h-4" /></button></div>{runs.length === 0 && <div className="shogun-card text-xs text-shogun-subdued">No stack runs yet.</div>}{runs.map((run) => <button key={run.id} onClick={() => setSelectedRunId(run.id)} className={cn('shogun-card !p-3 w-full text-left border transition-colors', selectedRunId === run.id && 'border-purple-400/60')}><div className="font-bold text-xs line-clamp-2">{run.objective}</div><div className="flex items-center justify-between mt-2 text-[9px] uppercase"><span style={{ color: statusColor(run.status) }}>{run.status.replaceAll('_', ' ')}</span><span className="text-shogun-subdued">{run.posture || 'ready'}</span></div></button>)}</div>
    </div>
    <div className="space-y-4 min-w-0">
      {!selectedRun && <div className="shogun-card text-sm text-shogun-subdued">Select a run to inspect its live execution trace.</div>}
      {selectedRun && <>
        <div className="shogun-card !p-4"><div className="flex items-start justify-between gap-4"><div><div className="text-[9px] uppercase text-shogun-subdued">Runtime command view</div><h3 className="mt-1 font-bold">{selectedRun.objective}</h3><div className="mt-2 flex flex-wrap gap-2 text-[9px]"><span className="rounded border px-2 py-1 uppercase" style={{ color: statusColor(selectedRun.status), borderColor: `${statusColor(selectedRun.status)}55` }}>{selectedRun.status.replaceAll('_', ' ')}</span><span className="rounded border border-shogun-border px-2 py-1 text-shogun-subdued">{selectedRun.completed_steps?.length || 0}/{selectedRun.steps?.length || 0} steps</span><span className="rounded border border-shogun-border px-2 py-1 text-shogun-subdued">{selectedRun.model_profile}</span></div></div><div className="flex gap-2">{selectedRun.status === 'running' && <button onClick={() => action(selectedRun.id, 'pause')} title="Pause" className="rounded border border-amber-400/30 p-2 text-amber-300"><Pause className="w-4 h-4" /></button>}{selectedRun.status === 'paused' && <button onClick={() => action(selectedRun.id, 'resume')} title="Resume" className="rounded border border-green-400/30 p-2 text-green-300"><RotateCcw className="w-4 h-4" /></button>}{!terminal.includes(selectedRun.status) && <button onClick={() => action(selectedRun.id, 'cancel')} title="Cancel" className="rounded border border-red-400/30 p-2 text-red-300"><CircleStop className="w-4 h-4" /></button>}</div></div></div>
        <div className="grid grid-cols-[minmax(0,1.45fr)_minmax(280px,0.8fr)] gap-4">
          <section className="shogun-card !p-4">
            <h4 className="text-[10px] font-bold uppercase tracking-widest">Live execution tree</h4>
            <div className="mt-3 space-y-2">{(selectedRun.steps || []).map((step: any, index: number) => {
              const route = step.metadata_json?.routing_decision || {};
              return <div key={step.id} className="rounded-lg border border-shogun-border bg-[#080b16] p-3"><div className="flex gap-3"><div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[9px] font-bold" style={{ color: statusColor(step.status), borderColor: statusColor(step.status) }}>{index + 1}</div><div className="min-w-0 flex-1"><div className="flex justify-between gap-2"><b className="truncate text-[10px]">{step.name}</b><span className="text-[8px] uppercase" style={{ color: statusColor(step.status) }}>{step.status.replaceAll('_', ' ')}</span></div><div className="mt-1 flex flex-wrap gap-3 text-[8px] text-shogun-subdued"><span>{step.model_used || 'model pending'}</span><span>profile {route.active_profile || selectedRun.model_profile}</span><span>complexity {route.complexity_score ?? '—'}</span><span>cost tier {route.estimated_cost_tier ?? '—'}</span><span>escalation {route.escalation_level || 'none'}</span><span>retry {step.retry_count}/{step.max_retries}</span><span style={{ color: statusColor(step.verification_status) }}>verification {step.verification_status}</span></div>{route.reason && <p className="mt-1 text-[8px] text-purple-300">{route.reason}</p>}{step.error_json?.message && <p className="mt-2 text-[8px] text-red-400">{step.error_json.message}</p>}</div></div></div>;
            })}</div>
          </section>
          <div className="space-y-4">
            <section className="shogun-card !p-4"><h4 className="text-[10px] font-bold uppercase tracking-widest">Independent verification</h4><div className="mt-3 space-y-2 max-h-64 overflow-y-auto">{verifications.map((item) => <div key={item.id} className="rounded border border-shogun-border p-2"><div className="flex justify-between gap-2 text-[8px] uppercase"><b>{item.verification_type.replaceAll('_', ' ')}</b><span style={{ color: statusColor(item.status) }}>{item.status}</span></div><p className="mt-1 text-[8px] text-shogun-subdued">{item.observed_result}</p><div className="mt-1 text-[8px] text-purple-300">{item.metadata_json?.verifier_mode || 'evidence'} · score {item.metadata_json?.score ?? '—'}</div></div>)}{verifications.length === 0 && <p className="text-[9px] text-shogun-subdued">No verification evidence yet.</p>}</div></section>
            <section className="shogun-card !p-4"><h4 className="text-[10px] font-bold uppercase tracking-widest">Evidence & continuity</h4><div className="mt-3 grid grid-cols-3 gap-2 text-center"><div className="rounded bg-[#080b16] p-2"><b className="text-purple-300">{checkpoints.length}</b><div className="text-[7px] uppercase text-shogun-subdued">checkpoints</div></div><div className="rounded bg-[#080b16] p-2"><b className="text-blue-300">{artifacts.length}</b><div className="text-[7px] uppercase text-shogun-subdued">artifacts</div></div><div className="rounded bg-[#080b16] p-2"><b className="text-green-300">{verifications.filter((item) => item.status === 'passed').length}</b><div className="text-[7px] uppercase text-shogun-subdued">passed</div></div></div>{checkpoints[0] && <div className="mt-3 rounded border border-shogun-border p-2"><b className="text-[8px]">Latest durable checkpoint</b><p className="mt-1 line-clamp-4 whitespace-pre-wrap text-[8px] text-shogun-subdued">{checkpoints[0].context_summary}</p><p className="mt-1 text-[8px] text-purple-300">{checkpoints[0].resume_instruction}</p></div>}</section>
          </div>
        </div>
        {Object.keys(selectedRun.final_summary || {}).length > 0 && <section className="shogun-card !p-4"><h4 className="text-[10px] font-bold uppercase tracking-widest">Final verified summary</h4><div className="mt-3 grid grid-cols-2 gap-3 text-[9px]"><div><span className="text-shogun-subdued">Status</span><p style={{ color: statusColor(selectedRun.final_summary.final_status) }}>{selectedRun.final_summary.final_status?.replaceAll('_', ' ')}</p></div><div><span className="text-shogun-subdued">Files changed</span><p>{selectedRun.final_summary.files_changed?.length || 0}</p></div><div className="col-span-2"><span className="text-shogun-subdued">Known issues</span><pre className="mt-1 whitespace-pre-wrap text-[8px] text-amber-300">{JSON.stringify(selectedRun.final_summary.known_issues || [], null, 2)}</pre></div></div></section>}
      </>}
    </div>
  </div>;
}

export const FlowStack = () => {
  const { ui: templateUi } = useTemplateCatalog();
  const [tab, setTab] = useState<'builder' | 'templates' | 'runtime'>('builder');
  const [builderSeed, setBuilderSeed] = useState<{ template: CatalogTemplate; revision: number } | null>(null);
  const openStackTemplate = (template: CatalogTemplate) => {
    setBuilderSeed((current) => ({
      template: {
        ...template,
        builder_nodes: template.builder_nodes?.map((node) => ({ ...node })),
        builder_edges: template.builder_edges?.map((edge) => ({ ...edge })),
      },
      revision: (current?.revision || 0) + 1,
    }));
    setTab('builder');
  };
  return <div className="space-y-5 animate-in fade-in duration-500">
    <div className="flex items-center justify-between"><div><h2 className="text-2xl font-bold flex items-center gap-2"><Layers3 className="text-purple-400" /> {templateUi('flow_stacking', 'Flow Stacking')}</h2><p className="text-sm text-shogun-subdued mt-1">{templateUi('flow_stacking_subtitle', 'Compose AgentFlows into connected, orchestrated systems.')}</p></div><div className="text-[10px] px-3 py-1.5 border border-purple-500/30 bg-purple-500/10 text-purple-300 rounded-full">208 {templateUi('built_in_stacks', 'built-in stacks').toUpperCase()}</div></div>
    <div className="flex gap-2 border border-shogun-border bg-shogun-card p-1 rounded-lg w-fit">{[
      ['builder', Route, templateUi('stack_builder', 'Stack Builder').toUpperCase()], ['templates', Sparkles, templateUi('stack_templates', 'Stack Templates').toUpperCase()], ['runtime', ShieldCheck, templateUi('flow_stack_runs', 'Runs').toUpperCase()],
    ].map(([id, Icon, label]: any) => <button key={id} onClick={() => setTab(id)} className={cn('flex items-center gap-2 px-4 py-2 rounded text-xs font-bold', tab === id ? 'bg-purple-500/20 border border-purple-400/40 text-purple-200' : 'text-shogun-subdued border border-transparent')}><Icon className="w-4 h-4" />{label}</button>)}</div>
    {tab === 'builder' && <ReactFlowProvider key={`stack-builder-${builderSeed?.revision || 0}`}><FlowStackBuilder seed={builderSeed?.template || null} /></ReactFlowProvider>}
    {tab === 'templates' && <StackTemplateGallery onOpen={openStackTemplate} />}
    {tab === 'runtime' && <OrchestratorRuntime />}
  </div>;
};
