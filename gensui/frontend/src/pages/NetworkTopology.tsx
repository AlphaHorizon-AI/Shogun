import { useEffect, useState, useRef, useCallback } from 'react';
import { useNavigate } from '../lib/routerCompat';
import { Network, Radar, AlertTriangle, HelpCircle, Loader2, Shield, Maximize2, ZoomIn, ZoomOut, Globe } from 'lucide-react';
import api from '../lib/api';
import { useTranslation } from '../i18n';

interface MemberNode {
  id: string;
  instance_name: string;
  hostname: string | null;
  status: string;
  harakiri_state: string;
  samurai_count: number;
  environment: string;
  nexus_peers: string[];
  external_agents: ExternalAgent[];
  x: number;
  y: number;
}

interface ExternalAgent {
  id: string;
  name: string;
  platform: string;
  direction: string;
  has_endpoint: boolean;
  host_shogun_id: string;
  host_shogun_name: string;
  x: number;
  y: number;
}

interface DiscoveredHost {
  ip: string;
  port: number;
  hostname: string | null;
  is_shogun: boolean;
  is_self: boolean;
  version: string | null;
  instance_name: string | null;
  shogun_id: string | null;
  classification: 'enrolled' | 'unenrolled' | 'unknown';
  all_ips?: string[];
  interface_count?: number;
  x: number;
  y: number;
}

interface ScanResult {
  hosts: DiscoveredHost[];
  enrolled: DiscoveredHost[];
  unenrolled: DiscoveredHost[];
  unknown: DiscoveredHost[];
  subnets_scanned: string[];
  total_ips_probed: number;
  scan_duration_ms: number;
  error?: string;
}

const STATUS_COLORS: Record<string, { fill: string; stroke: string; glow: string }> = {
  online: { fill: '#34d399', stroke: '#10b981', glow: 'rgba(52, 211, 153, 0.3)' },
  offline: { fill: '#64748b', stroke: '#475569', glow: 'rgba(100, 116, 139, 0.15)' },
  harakiri: { fill: '#fb7185', stroke: '#e11d48', glow: 'rgba(251, 113, 133, 0.3)' },
};

const HUB_COLOR = { fill: '#160f20', stroke: '#c084fc', glow: 'rgba(192, 132, 252, 0.45)' };
const ROGUE_COLOR = { fill: '#1e1025', stroke: '#ef4444', glow: 'rgba(239, 68, 68, 0.3)' };
const UNKNOWN_COLOR = { fill: '#1a1a2e', stroke: '#6b7280', glow: 'rgba(107, 114, 128, 0.2)' };

const PLATFORM_COLORS: Record<string, { fill: string; stroke: string; glow: string }> = {
  microsoft_365: { fill: '#0c1e3a', stroke: '#2b88d8', glow: 'rgba(0, 120, 212, 0.5)' },
  salesforce:    { fill: '#0c1e30', stroke: '#00bcd4', glow: 'rgba(0, 188, 212, 0.45)' },
  google:        { fill: '#142210', stroke: '#4caf50', glow: 'rgba(76, 175, 80, 0.4)' },
  servicenow:    { fill: '#1e1e0a', stroke: '#9ccc65', glow: 'rgba(156, 204, 101, 0.4)' },
  custom:        { fill: '#1e0c28', stroke: '#ba68c8', glow: 'rgba(186, 104, 200, 0.4)' },
};
const getAgentColor = (platform: string) => PLATFORM_COLORS[platform] || PLATFORM_COLORS.custom;
const AGENT_R = 22;

export default function NetworkTopology() {
  const { t } = useTranslation();
  const [members, setMembers] = useState<MemberNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; member?: MemberNode; host?: DiscoveredHost; agent?: ExternalAgent } | null>(null);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const navigate = useNavigate();

  const fetchMembers = useCallback(async () => {
    try {
      const { data } = await api.get('/members');
      const raw = data.members || [];
      setMembers(raw.map((m: any) => ({
        id: m.id,
        instance_name: m.instance_name,
        hostname: m.hostname,
        status: m.harakiri_state !== 'none' ? 'harakiri' : m.status,
        harakiri_state: m.harakiri_state,
        samurai_count: m.samurai_count || 0,
        environment: m.environment,
        nexus_peers: m.metadata?.nexus_peers || [],
        external_agents: (m.metadata?.external_agents || []).map((a: any) => ({
          ...a,
          host_shogun_id: m.id,
          host_shogun_name: m.instance_name,
          x: 0,
          y: 0,
        })),
        x: 0,
        y: 0,
      })));
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchMembers();
    const i = setInterval(fetchMembers, 15000);
    return () => clearInterval(i);
  }, [fetchMembers]);

  const handleScan = useCallback(async () => {
    setScanning(true);
    setScanError(null);
    try {
      const { data } = await api.post('/monitoring/network-scan', {});
      setScanResult(data);
      if (data.error) setScanError(data.error);
    } catch (err: any) {
      setScanError(err.response?.data?.detail || 'Network scan failed');
    } finally {
      setScanning(false);
    }
  }, []);

  // Discover local and LAN Shoguns once when the topology opens. The button
  // remains available for an immediate rescan after another node starts.
  useEffect(() => {
    void handleScan();
  }, [handleScan]);

  // ── Pan & Zoom state ────────────────────────────────────
  const W = 1200, H = 680;
  const defaultVB = { x: 0, y: 0, w: W, h: H };
  const [vb, setVb] = useState(defaultVB);
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef({ x: 0, y: 0, vbX: 0, vbY: 0 });

  const zoomLevel = Math.round((W / vb.w) * 100);

  const handleWheel = useCallback((e: React.WheelEvent<SVGSVGElement>) => {
    e.preventDefault();
    const svg = svgRef.current;
    if (!svg) return;

    const factor = e.deltaY > 0 ? 1.1 : 0.9;
    const rect = svg.getBoundingClientRect();

    // Mouse position as fraction of SVG viewport
    const mx = (e.clientX - rect.left) / rect.width;
    const my = (e.clientY - rect.top) / rect.height;

    setVb(prev => {
      const newW = Math.max(200, Math.min(W * 4, prev.w * factor));
      const newH = Math.max(150, Math.min(H * 4, prev.h * factor));
      return {
        x: prev.x + (prev.w - newW) * mx,
        y: prev.y + (prev.h - newH) * my,
        w: newW,
        h: newH,
      };
    });
  }, [W, H]);

  const handleMouseDown = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (e.button !== 0) return; // left click only
    setIsPanning(true);
    panStart.current = { x: e.clientX, y: e.clientY, vbX: vb.x, vbY: vb.y };
  }, [vb.x, vb.y]);

  const handleMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (!isPanning) return;
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const scaleX = vb.w / rect.width;
    const scaleY = vb.h / rect.height;
    const dx = (e.clientX - panStart.current.x) * scaleX;
    const dy = (e.clientY - panStart.current.y) * scaleY;
    setVb(prev => ({ ...prev, x: panStart.current.vbX - dx, y: panStart.current.vbY - dy }));
  }, [isPanning, vb.w, vb.h]);

  const handleMouseUp = useCallback(() => setIsPanning(false), []);

  const resetView = () => setVb(defaultVB);
  const zoomIn = () => setVb(prev => {
    const f = 0.8;
    const nw = prev.w * f, nh = prev.h * f;
    return { x: prev.x + (prev.w - nw) / 2, y: prev.y + (prev.h - nh) / 2, w: nw, h: nh };
  });
  const zoomOut = () => setVb(prev => {
    const f = 1.25;
    const nw = Math.min(W * 4, prev.w * f), nh = Math.min(H * 4, prev.h * f);
    return { x: prev.x + (prev.w - nw) / 2, y: prev.y + (prev.h - nh) / 2, w: nw, h: nh };
  });
  const CX = W / 2, CY = H / 2;
  const INNER_RADIUS = Math.min(W, H) * 0.28;
  const AGENT_RING_RADIUS = Math.min(W, H) * 0.18;
  const OUTER_RADIUS = Math.min(W, H) * 0.46;
  const NODE_R = 24;
  const HUB_R = 42;
  const ROGUE_R = 18;

  // Position enrolled members in inner circle
  const positioned = members.map((m, i) => {
    const angle = (2 * Math.PI * i) / Math.max(members.length, 1) - Math.PI / 2;
    return { ...m, x: CX + INNER_RADIUS * Math.cos(angle), y: CY + INNER_RADIUS * Math.sin(angle) };
  });

  // Collect and position external agents — orbit around their host Shogun
  const allExternalAgents: ExternalAgent[] = [];
  positioned.forEach(host => {
    host.external_agents.forEach((agent, i) => {
      const count = host.external_agents.length;
      const baseAngle = Math.atan2(host.y - CY, host.x - CX);
      const spread = Math.PI * 0.8;
      const agentAngle = baseAngle - spread / 2 + (spread * i) / Math.max(count - 1, 1);
      const r = AGENT_RING_RADIUS * 0.75;
      allExternalAgents.push({
        ...agent,
        x: host.x + r * Math.cos(count === 1 ? baseAngle + Math.PI : agentAngle),
        y: host.y + r * Math.sin(count === 1 ? baseAngle + Math.PI : agentAngle),
      });
    });
  });

  // Inject demo external agents when none exist, so the topology showcases the feature
  if (allExternalAgents.length === 0 && positioned.length > 0) {
    const demoHost = positioned[0];
    const demoAgents: Omit<ExternalAgent, 'x' | 'y'>[] = [
      { id: 'demo-sf-1', name: 'Salesforce Agentforce', platform: 'salesforce', direction: 'bidirectional', has_endpoint: true, host_shogun_id: demoHost.id, host_shogun_name: demoHost.instance_name },
      { id: 'demo-m365-1', name: 'M365 Copilot', platform: 'microsoft_365', direction: 'inbound', has_endpoint: false, host_shogun_id: demoHost.id, host_shogun_name: demoHost.instance_name },
    ];
    const baseAngle = Math.atan2(demoHost.y - CY, demoHost.x - CX);
    const spread = Math.PI * 0.8;
    const r = AGENT_RING_RADIUS * 0.75;
    demoAgents.forEach((agent, i) => {
      const agentAngle = baseAngle - spread / 2 + (spread * i) / Math.max(demoAgents.length - 1, 1);
      allExternalAgents.push({
        ...agent,
        x: demoHost.x + r * Math.cos(agentAngle),
        y: demoHost.y + r * Math.sin(agentAngle),
      });
    });
  }

  // Position discovered hosts (unenrolled + unknown) in outer ring
  const rogueHosts = scanResult ? [...scanResult.unenrolled, ...scanResult.unknown] : [];
  const positionedRogue = rogueHosts.map((h, i) => {
    const angle = (2 * Math.PI * i) / Math.max(rogueHosts.length, 1) - Math.PI / 4;
    return { ...h, x: CX + OUTER_RADIUS * Math.cos(angle), y: CY + OUTER_RADIUS * Math.sin(angle) };
  });

  // Nexus peer edges
  const peerEdges: { from: MemberNode; to: MemberNode }[] = [];
  const idMap = new Map(positioned.map(m => [m.id, m]));
  positioned.forEach(m => {
    m.nexus_peers.forEach(peerId => {
      const peer = idMap.get(peerId);
      if (peer && m.id < peerId) {
        peerEdges.push({ from: m, to: peer });
      }
    });
  });

  const getColor = (status: string) => STATUS_COLORS[status] || STATUS_COLORS.offline;

  const handleNodeClick = (id: string) => navigate(`/fleet/${id}`);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-10 h-10 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gensui-50 flex items-center gap-3">
            <Network size={24} className="text-cyan-400" />
            {t('nav.topology', 'Network Topology')}
          </h1>
          <p className="text-sm text-gensui-400 mt-1">
            {members.length} enrolled instance{members.length !== 1 ? 's' : ''}
            {scanResult && (scanResult.unenrolled.length > 0 || scanResult.unknown.length > 0) && (
              <span className="text-red-400 ml-2 font-semibold">
                · {scanResult.unenrolled.length} unenrolled · {scanResult.unknown.length} unknown
              </span>
            )}
          </p>
        </div>
        <button
          onClick={handleScan}
          disabled={scanning}
          className="flex items-center gap-2 px-4 py-2 bg-cyan-600/20 hover:bg-cyan-600/30 border border-cyan-500/30 hover:border-cyan-500/50 text-cyan-300 rounded-xl text-sm font-semibold transition-all disabled:opacity-50 cursor-pointer"
        >
          {scanning ? <Loader2 size={16} className="animate-spin" /> : <Radar size={16} />}
          {scanning ? t('common.scanning', 'Scanning...') : t('common.scan_network', 'Scan Network')}
        </button>
      </div>

      {/* Scan info bar */}
      {scanResult && !scanError && (
        <div className="glass-card-sm px-4 py-2 flex items-center gap-4 text-xs text-gensui-400">
          <span>Scanned: <b className="text-gensui-200">{scanResult.subnets_scanned.join(', ')}*</b></span>
          <span>Probed: <b className="text-gensui-200">{scanResult.total_ips_probed}</b> IPs</span>
          <span>Duration: <b className="text-gensui-200">{scanResult.scan_duration_ms}ms</b></span>
          <span>Found: <b className="text-emerald-400">{scanResult.enrolled.length}</b> enrolled, <b className="text-red-400">{scanResult.unenrolled.length}</b> unenrolled, <b className="text-gensui-400">{scanResult.unknown.length}</b> unknown</span>
        </div>
      )}
      {scanError && (
        <div className="glass-card-sm px-4 py-2 flex items-center gap-2 text-sm text-red-400">
          <AlertTriangle size={14} />
          <span>{scanError}</span>
        </div>
      )}

      <div className="glass-card overflow-hidden relative">
        {/* Legend */}
        <div className="absolute top-4 right-4 glass-card-sm p-3 space-y-2 z-10">
          <p className="text-[10px] font-bold text-gensui-400 uppercase tracking-widest">Status</p>
          {[
            { label: 'Online', color: STATUS_COLORS.online.fill },
            { label: 'Offline', color: STATUS_COLORS.offline.fill },
            { label: 'Harakiri', color: STATUS_COLORS.harakiri.fill },
            { label: 'Gensui Hub', color: HUB_COLOR.stroke },
          ].map(item => (
            <div key={item.label} className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ background: item.color }} />
              <span className="text-[10px] text-gensui-300">{item.label}</span>
            </div>
          ))}
          {scanResult && (
            <>
              <div className="border-t border-gensui-700/50 pt-2 mt-2">
                <p className="text-[10px] font-bold text-gensui-400 uppercase tracking-widest mb-1">Discovery</p>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full border-2 border-dashed border-red-500 bg-red-900/30" />
                <span className="text-[10px] text-red-300">Unenrolled (Rogue)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full border-2 border-dotted border-gray-500 bg-gray-800/30" />
                <span className="text-[10px] text-gensui-400">Unknown (Port Open)</span>
              </div>
            </>
          )}
          {allExternalAgents.length > 0 && (
            <>
              <div className="border-t border-gensui-700/50 pt-2 mt-2">
                <p className="text-[10px] font-bold text-gensui-400 uppercase tracking-widest mb-1">External Agents</p>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rotate-45 border border-purple-400 bg-purple-900/30" style={{ borderRadius: 2 }} />
                <span className="text-[10px] text-purple-300">Enterprise Agent</span>
              </div>
            </>
          )}
          <div className="border-t border-gensui-700/50 pt-2 mt-2">
            <p className="text-[10px] font-bold text-gensui-400 uppercase tracking-widest mb-1">Connections</p>
            <div className="flex items-center gap-2">
              <div className="w-6 h-px bg-cyan-500/50" />
              <span className="text-[10px] text-gensui-300">Gensui Link</span>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <div className="w-6 h-px bg-amber-400/50" style={{ borderTop: '2px dashed' }} />
              <span className="text-[10px] text-gensui-300">Nexus Peer</span>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <div className="w-6 h-px bg-purple-400/50" style={{ borderTop: '2px dotted' }} />
              <span className="text-[10px] text-gensui-300">Nexus Gateway</span>
            </div>
          </div>
        </div>

        {members.length === 0 && positionedRogue.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-gensui-500">
            <Network size={48} className="mb-4 opacity-20" />
            <p className="text-sm">No Shogun instances enrolled</p>
            <p className="text-xs mt-1">Enroll a Shogun or scan the network to discover instances</p>
          </div>
        ) : (
          <svg
            ref={svgRef}
            viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
            className="w-full select-none"
            style={{ minHeight: '540px', cursor: isPanning ? 'grabbing' : 'grab' }}
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          >
            <defs>
              {/* Glow filters */}
              <filter id="glow-hub" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="8" result="blur" />
                <feFlood floodColor={HUB_COLOR.glow} result="color" />
                <feComposite in="color" in2="blur" operator="in" result="glow" />
                <feMerge>
                  <feMergeNode in="glow" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <filter id="glow-node" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="4" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <filter id="glow-rogue" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="6" result="blur" />
                <feFlood floodColor={ROGUE_COLOR.glow} result="color" />
                <feComposite in="color" in2="blur" operator="in" result="glow" />
                <feMerge>
                  <feMergeNode in="glow" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/* Outer trust boundary ring (dashed) — only when scan results exist */}
            {positionedRogue.length > 0 && (
              <circle
                cx={CX} cy={CY} r={INNER_RADIUS + 40}
                fill="none" stroke="rgba(239, 68, 68, 0.12)"
                strokeWidth="1" strokeDasharray="8 6"
              />
            )}

            {/* Hub-to-node connections */}
            {positioned.map(m => (
              <line
                key={`edge-${m.id}`}
                x1={CX} y1={CY}
                x2={m.x} y2={m.y}
                stroke="rgba(6, 182, 212, 0.15)"
                strokeWidth="1.5"
              />
            ))}

            {/* Nexus peer edges */}
            {peerEdges.map((edge, i) => (
              <line
                key={`nexus-${i}`}
                x1={edge.from.x} y1={edge.from.y}
                x2={edge.to.x} y2={edge.to.y}
                stroke="rgba(251, 191, 36, 0.4)"
                strokeWidth="2"
                strokeDasharray="6 4"
              />
            ))}

            {/* External agent edges — from host Shogun to agent node */}
            {allExternalAgents.map((agent, i) => {
              const host = positioned.find(m => m.id === agent.host_shogun_id);
              if (!host) return null;
              const ac = getAgentColor(agent.platform);
              return (
                <line
                  key={`ext-edge-${i}`}
                  x1={host.x} y1={host.y}
                  x2={agent.x} y2={agent.y}
                  stroke={ac.stroke}
                  strokeWidth="2"
                  strokeDasharray="6 4"
                  opacity={0.7}
                />
              );
            })}

            {/* External agent nodes — diamond shape */}
            {allExternalAgents.map((agent, i) => {
              const ac = getAgentColor(agent.platform);
              const sz = AGENT_R;
              // Diamond path
              const d = `M ${agent.x} ${agent.y - sz} L ${agent.x + sz} ${agent.y} L ${agent.x} ${agent.y + sz} L ${agent.x - sz} ${agent.y} Z`;
              return (
                <g
                  key={`ext-node-${i}`}
                  className="cursor-default"
                  onMouseEnter={(e) => setTooltip({ x: e.clientX, y: e.clientY, agent })}
                  onMouseLeave={() => setTooltip(null)}
                >
                  {/* Outer glow pulse */}
                  <path d={`M ${agent.x} ${agent.y - sz - 4} L ${agent.x + sz + 4} ${agent.y} L ${agent.x} ${agent.y + sz + 4} L ${agent.x - sz - 4} ${agent.y} Z`} fill="none" stroke={ac.glow} strokeWidth="2">
                    <animate attributeName="opacity" from="0.8" to="0" dur="2.5s" repeatCount="indefinite" />
                  </path>
                  {/* Main diamond */}
                  <path d={d} fill={ac.fill} stroke={ac.stroke} strokeWidth="2.5" />
                  {/* Direction arrows */}
                  <text x={agent.x} y={agent.y + 1} textAnchor="middle" dominantBaseline="central" fill={ac.stroke} fontSize="13" fontWeight="800">
                    {agent.direction === 'bidirectional' ? '⇄' : agent.direction === 'outbound' ? '→' : '←'}
                  </text>
                  {/* Name below */}
                  <text x={agent.x} y={agent.y + sz + 14} textAnchor="middle" fill={ac.stroke} fontSize="9" fontWeight="700">
                    {agent.name.length > 20 ? agent.name.slice(0, 18) + '…' : agent.name}
                  </text>
                  <text x={agent.x} y={agent.y + sz + 25} textAnchor="middle" fill="#6b7280" fontSize="7" fontWeight="600" letterSpacing="1">
                    {agent.platform.replace('_', ' ').toUpperCase()}
                  </text>
                </g>
              );
            })}

            {/* Animated pulse rings for hub */}
            <circle cx={CX} cy={CY} r={HUB_R + 4} fill="none" stroke={HUB_COLOR.glow} strokeWidth="1" opacity="0.5">
              <animate attributeName="r" from={HUB_R + 4} to={HUB_R + 20} dur="3s" repeatCount="indefinite" />
              <animate attributeName="opacity" from="0.5" to="0" dur="3s" repeatCount="indefinite" />
            </circle>

            {/* Hub node (Gensui) — Shogun AFM Logo */}
            <g filter="url(#glow-hub)">
              <defs>
                <clipPath id="hub-clip">
                  <circle cx={CX} cy={CY} r={HUB_R - 2} />
                </clipPath>
              </defs>
              <circle cx={CX} cy={CY} r={HUB_R} fill={HUB_COLOR.fill} stroke={HUB_COLOR.stroke} strokeWidth="2.5" />
              <image
                href="/gensui-purple-logo.png"
                x={CX - HUB_R + 2}
                y={CY - HUB_R + 2}
                width={(HUB_R - 2) * 2}
                height={(HUB_R - 2) * 2}
                clipPath="url(#hub-clip)"
                preserveAspectRatio="xMidYMid slice"
              />
              {/* Label below hub */}
              <text x={CX} y={CY + HUB_R + 16} textAnchor="middle" fill={HUB_COLOR.stroke} fontSize="10" fontWeight="800" letterSpacing="2">GENSUI</text>
              <text x={CX} y={CY + HUB_R + 27} textAnchor="middle" fill="#94a3b8" fontSize="7" fontWeight="600">COMMAND HUB</text>
            </g>

            {/* Enrolled member nodes */}
            {positioned.map(m => {
              const c = getColor(m.status);
              return (
                <g
                  key={m.id}
                  className="cursor-pointer"
                  onClick={() => handleNodeClick(m.id)}
                  onMouseEnter={(e) => setTooltip({ x: e.clientX, y: e.clientY, member: m })}
                  onMouseLeave={() => setTooltip(null)}
                  filter="url(#glow-node)"
                >
                  {/* Pulse for online */}
                  {m.status === 'online' && (
                    <circle cx={m.x} cy={m.y} r={NODE_R} fill="none" stroke={c.glow} strokeWidth="1">
                      <animate attributeName="r" from={NODE_R} to={NODE_R + 12} dur="2.5s" repeatCount="indefinite" />
                      <animate attributeName="opacity" from="0.6" to="0" dur="2.5s" repeatCount="indefinite" />
                    </circle>
                  )}
                  <circle cx={m.x} cy={m.y} r={NODE_R} fill={c.fill} stroke={c.stroke} strokeWidth="2" />
                  {/* Enrolled shield badge */}
                  <circle cx={m.x + NODE_R * 0.65} cy={m.y - NODE_R * 0.65} r="6" fill="#0a0e17" stroke="#10b981" strokeWidth="1" />
                  <text x={m.x + NODE_R * 0.65} y={m.y - NODE_R * 0.65 + 1} textAnchor="middle" dominantBaseline="central" fill="#10b981" fontSize="7" fontWeight="900">✓</text>
                  {/* First letter */}
                  <text x={m.x} y={m.y + 1} textAnchor="middle" dominantBaseline="central" fill="#0a0e17" fontSize="14" fontWeight="800">
                    {m.instance_name.charAt(0).toUpperCase()}
                  </text>
                  {/* Name below */}
                  <text x={m.x} y={m.y + NODE_R + 14} textAnchor="middle" fill="#94a3b8" fontSize="9" fontWeight="500">
                    {m.instance_name.length > 16 ? m.instance_name.slice(0, 14) + '…' : m.instance_name}
                  </text>
                </g>
              );
            })}

            {/* Unenrolled / Unknown (rogue) nodes — outer ring */}
            {positionedRogue.map((h, i) => {
              const isRogue = h.classification === 'unenrolled';
              const color = isRogue ? ROGUE_COLOR : UNKNOWN_COLOR;
              return (
                <g
                  key={`rogue-${i}`}
                  className="cursor-default"
                  onMouseEnter={(e) => setTooltip({ x: e.clientX, y: e.clientY, host: h })}
                  onMouseLeave={() => setTooltip(null)}
                  filter={isRogue ? "url(#glow-rogue)" : undefined}
                >
                  {/* Danger pulse for rogue */}
                  {isRogue && (
                    <circle cx={h.x} cy={h.y} r={ROGUE_R} fill="none" stroke="rgba(239, 68, 68, 0.4)" strokeWidth="1">
                      <animate attributeName="r" from={ROGUE_R} to={ROGUE_R + 14} dur="2s" repeatCount="indefinite" />
                      <animate attributeName="opacity" from="0.5" to="0" dur="2s" repeatCount="indefinite" />
                    </circle>
                  )}
                  {/* Dashed/dotted border */}
                  <circle
                    cx={h.x} cy={h.y} r={ROGUE_R}
                    fill={color.fill}
                    stroke={color.stroke}
                    strokeWidth="2"
                    strokeDasharray={isRogue ? '5 3' : '3 3'}
                  />
                  {/* Icon */}
                  <text x={h.x} y={h.y + 1} textAnchor="middle" dominantBaseline="central" fill={isRogue ? '#ef4444' : '#6b7280'} fontSize="14" fontWeight="800">
                    {isRogue ? '⚠' : '?'}
                  </text>
                  {/* Label below */}
                  <text x={h.x} y={h.y + ROGUE_R + 12} textAnchor="middle" fill={isRogue ? '#f87171' : '#6b7280'} fontSize="8" fontWeight="600">
                    {h.instance_name || h.ip}
                  </text>
                  <text x={h.x} y={h.y + ROGUE_R + 22} textAnchor="middle" fill="#555" fontSize="7">
                    {isRogue ? 'UNENROLLED' : 'UNKNOWN'}
                  </text>
                </g>
              );
            })}
          </svg>
        )}

        {/* Zoom Controls — bottom left */}
        {(members.length > 0 || positionedRogue.length > 0) && (
          <div className="absolute bottom-4 left-4 flex items-center gap-1 z-10">
            <button onClick={zoomIn} className="p-1.5 glass-card-sm hover:bg-gensui-700/40 rounded-lg text-gensui-400 hover:text-gensui-200 transition-colors" title="Zoom in">
              <ZoomIn size={14} />
            </button>
            <span className="text-[10px] text-gensui-500 font-mono w-8 text-center">{zoomLevel}%</span>
            <button onClick={zoomOut} className="p-1.5 glass-card-sm hover:bg-gensui-700/40 rounded-lg text-gensui-400 hover:text-gensui-200 transition-colors" title="Zoom out">
              <ZoomOut size={14} />
            </button>
            <button onClick={resetView} className="p-1.5 glass-card-sm hover:bg-gensui-700/40 rounded-lg text-gensui-400 hover:text-gensui-200 transition-colors ml-1" title="Reset view">
              <Maximize2 size={14} />
            </button>
          </div>
        )}
        {/* Tooltip overlay */}
        {tooltip && (() => {
          const tooltipW = 240;
          const tooltipH = 200;
          const flipX = tooltip.x + tooltipW + 20 > window.innerWidth;
          const flipY = tooltip.y + tooltipH + 20 > window.innerHeight;
          return (
          <div
            className="fixed glass-card-sm p-3 pointer-events-none z-50 space-y-1.5"
            style={{
              left: flipX ? tooltip.x - tooltipW - 12 : tooltip.x + 12,
              top: flipY ? tooltip.y - tooltipH : tooltip.y - 10,
              minWidth: 200,
              maxWidth: tooltipW,
            }}
          >
            {tooltip.member && (
              <>
                <p className="text-sm font-bold text-gensui-50">{tooltip.member.instance_name}</p>
                <div className="text-xs space-y-1 text-gensui-300">
                  <div className="flex justify-between"><span className="text-gensui-500">Host</span><span>{tooltip.member.hostname || '—'}</span></div>
                  <div className="flex justify-between"><span className="text-gensui-500">Status</span><span className={tooltip.member.status === 'online' ? 'text-emerald-400' : tooltip.member.status === 'harakiri' ? 'text-red-400' : 'text-gensui-400'}>{tooltip.member.status}</span></div>
                  <div className="flex justify-between"><span className="text-gensui-500">Samurai</span><span>{tooltip.member.samurai_count}</span></div>
                  <div className="flex justify-between"><span className="text-gensui-500">Environment</span><span>{tooltip.member.environment}</span></div>
                  <div className="flex justify-between"><span className="text-gensui-500">Enrollment</span><span className="text-emerald-400 flex items-center gap-1"><Shield size={10} /> Enrolled</span></div>
                  {tooltip.member.nexus_peers.length > 0 && (
                    <div className="flex justify-between"><span className="text-gensui-500">Nexus Peers</span><span className="text-amber-400">{tooltip.member.nexus_peers.length}</span></div>
                  )}
                </div>
                <p className="text-[10px] text-gensui-600 pt-1 border-t border-gensui-700/30">Click to deep dive →</p>
              </>
            )}
            {tooltip.host && (
              <>
                <div className="flex items-center gap-2">
                  {tooltip.host.classification === 'unenrolled' ? (
                    <AlertTriangle size={14} className="text-red-400" />
                  ) : (
                    <HelpCircle size={14} className="text-gray-400" />
                  )}
                  <p className="text-sm font-bold text-gensui-50">
                    {tooltip.host.instance_name || tooltip.host.ip}
                  </p>
                  {tooltip.host.is_self && (
                    <span className="text-[9px] bg-cyan-800/40 text-cyan-300 px-1.5 py-0.5 rounded-full font-bold">THIS MACHINE</span>
                  )}
                </div>
                <div className="text-xs space-y-1 text-gensui-300">
                  <div className="flex justify-between gap-4">
                    <span className="text-gensui-500">IP</span>
                    <span className="font-mono text-right">
                      {tooltip.host.all_ips && tooltip.host.all_ips.length > 1
                        ? tooltip.host.all_ips.map((ip, i) => <span key={i} className="block">{ip}:{tooltip.host!.port}</span>)
                        : <span>{tooltip.host.ip}:{tooltip.host.port}</span>
                      }
                    </span>
                  </div>
                  {tooltip.host.interface_count && tooltip.host.interface_count > 1 && (
                    <div className="flex justify-between"><span className="text-gensui-500">Interfaces</span><span className="text-cyan-400">{tooltip.host.interface_count} network interfaces</span></div>
                  )}
                  {tooltip.host.hostname && (
                    <div className="flex justify-between"><span className="text-gensui-500">Hostname</span><span>{tooltip.host.hostname}</span></div>
                  )}
                  {tooltip.host.version && (
                    <div className="flex justify-between"><span className="text-gensui-500">Version</span><span>{tooltip.host.version}</span></div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-gensui-500">Status</span>
                    <span className={tooltip.host.classification === 'unenrolled' ? 'text-red-400 font-bold' : 'text-gray-400'}>
                      {tooltip.host.classification === 'unenrolled' ? '⚠ NOT ENROLLED' : 'Unknown Service'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gensui-500">Is Shogun?</span>
                    <span className={tooltip.host.is_shogun ? 'text-amber-400' : 'text-gensui-500'}>
                      {tooltip.host.is_shogun ? 'Yes' : 'Unknown'}
                    </span>
                  </div>
                </div>
                {tooltip.host.classification === 'unenrolled' && (
                  <p className="text-[10px] text-red-400/70 pt-1 border-t border-red-900/30">
                    {tooltip.host.is_self
                      ? '⚠ This is your own Shogun — enroll it to clear this warning'
                      : '⚠ This Shogun instance is not enrolled in Gensui'
                    }
                  </p>
                )}
              </>
            )}
            {tooltip.agent && (
              <>
                <div className="flex items-center gap-2">
                  <Globe size={14} className="text-purple-400" />
                  <p className="text-sm font-bold text-gensui-50">{tooltip.agent.name}</p>
                </div>
                <div className="text-xs space-y-1 text-gensui-300">
                  <div className="flex justify-between"><span className="text-gensui-500">Platform</span><span className="text-purple-300">{tooltip.agent.platform.replace('_', ' ')}</span></div>
                  <div className="flex justify-between"><span className="text-gensui-500">Direction</span><span>{tooltip.agent.direction === 'bidirectional' ? '⇄ Bidirectional' : tooltip.agent.direction === 'outbound' ? '→ Outbound (Shogun → Agent)' : '← Inbound (Agent → Shogun)'}</span></div>
                  <div className="flex justify-between"><span className="text-gensui-500">Endpoint</span><span className={tooltip.agent.has_endpoint ? 'text-emerald-400' : 'text-gensui-500'}>{tooltip.agent.has_endpoint ? 'Configured' : 'None'}</span></div>
                  <div className="flex justify-between"><span className="text-gensui-500">Host Shogun</span><span className="text-cyan-400">{tooltip.agent.host_shogun_name}</span></div>
                </div>
                <p className="text-[10px] text-purple-400/60 pt-1 border-t border-purple-900/30">
                  Connected via Nexus External Gateway
                </p>
              </>
            )}
          </div>
        );})()}
      </div>
    </div>
  );
}
