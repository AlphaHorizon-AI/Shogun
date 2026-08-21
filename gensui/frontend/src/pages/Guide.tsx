import { useState, useEffect, useRef, useCallback } from 'react';
import {
  LayoutDashboard, Shield, Users, Layers, Activity,
  FileSearch, Bell, UserPlus, Skull, Network, Settings,
  BookOpen, List, Server, AlertTriangle, Zap, Lock,
  Monitor, Globe, Tag, Copy, Search, Eye, Trash2,
  Check, X, Key, Info, ShieldAlert, Clock, BarChart3
} from 'lucide-react';
import { useTranslation } from '../i18n';

export default function Guide() {
  const { t } = useTranslation();
  const [activeSection, setActiveSection] = useState('ref-dashboard');

  const SECTIONS = [
    { id: 'ref-dashboard', label: t('guide.sidebar_dashboard', 'Dashboard'), icon: LayoutDashboard, color: 'text-cyan-400' },
    { id: 'ref-fleet', label: t('guide.sidebar_fleet', 'Fleet'), icon: Users, color: 'text-emerald-400' },
    { id: 'ref-detail', label: t('guide.sidebar_detail', 'Shogun Detail'), icon: Server, color: 'text-cyan-400' },
    { id: 'ref-network', label: t('guide.sidebar_network', 'Network Topology'), icon: Network, color: 'text-cyan-400' },
    { id: 'ref-groups', label: t('guide.sidebar_groups', 'Groups'), icon: Layers, color: 'text-purple-400' },
    { id: 'ref-postures', label: t('guide.sidebar_postures', 'Postures'), icon: Shield, color: 'text-amber-400' },
    { id: 'ref-harakiri', label: t('guide.sidebar_harakiri', 'Harakiri Control'), icon: Skull, color: 'text-red-400' },
    { id: 'ref-activity', label: t('guide.sidebar_activity', 'Activity Monitor'), icon: Activity, color: 'text-cyan-400' },
    { id: 'ref-audit', label: t('guide.sidebar_audit', 'Audit Log'), icon: FileSearch, color: 'text-gensui-400' },
    { id: 'ref-alerts', label: t('guide.sidebar_alerts', 'Alerts'), icon: Bell, color: 'text-amber-400' },
    { id: 'ref-enrollment', label: t('guide.sidebar_enrollment', 'Enrollment'), icon: UserPlus, color: 'text-amber-400' },
    { id: 'ref-settings', label: t('guide.sidebar_settings', 'Settings'), icon: Settings, color: 'text-cyan-400' },
    { id: 'ref-security', label: t('guide.sidebar_security', 'Security Protocols'), icon: ShieldAlert, color: 'text-red-400' },
    { id: 'ref-fleet-audit', label: t('guide.sidebar_fleet_audit', 'Fleet Audit'), icon: BarChart3, color: 'text-cyan-400' },
    { id: 'ref-identity', label: t('guide.sidebar_identity', 'Enterprise Identity'), icon: Key, color: 'text-purple-400' },
  ];

  const scrollToSection = useCallback((id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setActiveSection(id);
    }
  }, []);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActiveSection(entry.target.id);
        }
      },
      { rootMargin: '-80px 0px -60% 0px', threshold: 0.1 }
    );
    const timer = setTimeout(() => {
      SECTIONS.forEach(({ id }) => {
        const el = document.getElementById(id);
        if (el) observer.observe(el);
      });
    }, 100);
    return () => { clearTimeout(timer); observer.disconnect(); };
  }, []);

  const cn = (...classes: (string | boolean | undefined)[]) => classes.filter(Boolean).join(' ');

  /* ── Helpers for translated card blocks ─────────────────── */
  const Card = ({ icon: Icon, iconColor, title, children, span2 }: { icon: any; iconColor: string; title: string; children: React.ReactNode; span2?: boolean }) => (
    <div className={`glass-card p-4 space-y-2 ${span2 ? 'md:col-span-2' : ''}`}>
      <div className="font-semibold text-gensui-100 flex items-center gap-2 text-sm"><Icon size={14} className={iconColor} /> {title}</div>
      {children}
    </div>
  );
  const P = ({ children }: { children: React.ReactNode }) => <p className="text-xs text-gensui-400 leading-relaxed">{children}</p>;

  return (
    <div className="space-y-6 max-w-7xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gensui-50 flex items-center gap-3">
          <BookOpen size={24} className="text-cyan-400" />
          {t('guide.title', 'Reference Manual')}
          <span className="text-[10px] font-normal text-gensui-500 bg-gensui-800/60 px-2 py-0.5 rounded border border-gensui-700/30 tracking-[0.3em] uppercase">{t('nav.guide', 'Guide')}</span>
        </h1>
        <p className="text-sm text-gensui-400 mt-1">{t('guide.subtitle', 'A comprehensive, page-by-page, button-by-button manual of every capability within Gensui Command Center.')}</p>
      </div>

      {/* Two-column layout: sidebar + content */}
      <div className="flex gap-8">
        {/* Sticky Sidebar Navigation */}
        <nav className="hidden lg:block w-52 shrink-0">
          <div className="sticky top-6 space-y-1 p-3 bg-gensui-800/40 border border-gensui-700/30 rounded-xl max-h-[calc(100vh-120px)] overflow-y-auto">
            <div className="flex items-center gap-2 px-2 pb-2 mb-2 border-b border-gensui-700/30">
              <List size={14} className="text-cyan-400" />
              <span className="text-[10px] font-bold text-gensui-500 uppercase tracking-widest">{t('guide.sections', 'Sections')}</span>
            </div>
            {SECTIONS.map((sec) => (
              <button
                key={sec.id}
                onClick={() => scrollToSection(sec.id)}
                className={cn(
                  "w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[11px] font-medium transition-all duration-200 text-left",
                  activeSection === sec.id
                    ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 shadow-sm"
                    : "text-gensui-400 hover:text-gensui-200 hover:bg-gensui-700/30 border border-transparent"
                )}
              >
                <sec.icon size={14} className={cn("shrink-0", activeSection === sec.id ? 'text-cyan-400' : sec.color)} />
                {sec.label}
              </button>
            ))}
          </div>
        </nav>

        {/* Main Content */}
        <div className="flex-1 min-w-0 space-y-14">

          {/* ═══════════════════════════════════════════════════════ */}
          {/* 1. DASHBOARD */}
          {/* ═══════════════════════════════════════════════════════ */}
          <section id="ref-dashboard" className="space-y-4 scroll-mt-6">
            <div className="flex items-center gap-3 border-b border-gensui-700/30 pb-3">
              <LayoutDashboard size={20} className="text-cyan-400" />
              <div>
                <h2 className="text-lg font-bold text-gensui-100 uppercase tracking-widest">{t('guide.sec_dashboard_title', 'Dashboard &mdash; Command Overview')}</h2>
                <p className="text-xs text-gensui-400">{t('guide.sec_dashboard_desc', 'Real-time fleet monitoring and security status at a glance.')}</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Card icon={Users} iconColor="text-emerald-400" title={t('guide.card_fleet_stats', 'Fleet Stats Grid (Top Row)')}>
                <P>{t('guide.card_fleet_stats_desc', 'Four metric cards at the top. Each shows a count and optional total:')}</P>
                <ul className="text-xs text-gensui-400 space-y-1 ml-4 list-disc">
                  <li><strong className="text-gensui-200">{t('guide.card_members_online', 'Members Online:')}</strong> {t('guide.card_members_online_desc', 'Shows how many Shogun instances are currently connected vs. total enrolled.')}</li>
                  <li><strong className="text-gensui-200">{t('guide.card_active_samurai', 'Active Samurai:')}</strong> {t('guide.card_active_samurai_desc', 'Total sub-agents running across all fleet members.')}</li>
                  <li><strong className="text-gensui-200">{t('guide.card_active_workflows', 'Active Workflows:')}</strong> {t('guide.card_active_workflows_desc', 'Running Agent Flow pipelines fleet-wide.')}</li>
                  <li><strong className="text-gensui-200">{t('guide.card_mado_sessions', 'Mado Sessions:')}</strong> {t('guide.card_mado_sessions_desc', 'Active browser automation sessions across all Shoguns.')}</li>
                </ul>
              </Card>
              <Card icon={AlertTriangle} iconColor="text-red-400" title={t('guide.card_alert_row', 'Alert & Status Row')}>
                <P>{t('guide.card_alert_row_desc', 'Three clickable cards below the stats grid:')}</P>
                <ul className="text-xs text-gensui-400 space-y-1 ml-4 list-disc">
                  <li><strong className="text-gensui-200">{t('guide.card_active_alerts', 'Active Alerts:')}</strong> {t('guide.card_active_alerts_desc', 'Number of unresolved alerts. Turns red when critical alerts exist. Click to navigate to the Alerts page.')}</li>
                  <li><strong className="text-gensui-200">{t('guide.card_harakiri_active', 'Harakiri Active:')}</strong> {t('guide.card_harakiri_active_desc', 'Shows "None" (green) or the count of active Harakiri events (red pulsing). Click to go to Harakiri Control.')}</li>
                  <li><strong className="text-gensui-200">{t('guide.card_pending_enrollment', 'Pending Enrollment:')}</strong> {t('guide.card_pending_enrollment_desc', 'Number of Shogun instances awaiting approval. Click to go to Enrollment Management.')}</li>
                </ul>
              </Card>
              <Card icon={Shield} iconColor="text-red-400" title={t('guide.card_posture_banner', 'Global Posture Override Banner')} span2>
                <P>{t('guide.card_posture_banner_desc', 'When a Global Posture Override is active (see Postures), a red danger-glowing banner appears showing the posture name, who activated it, and the reason. This means all fleet members are currently locked to a specific security posture regardless of their individual settings.')}</P>
              </Card>
              <Card icon={Activity} iconColor="text-cyan-400" title={t('guide.card_auto_refresh', 'Auto-Refresh')} span2>
                <P>{t('guide.card_auto_refresh_desc', 'All dashboard data auto-refreshes every 10 seconds. No manual reload needed.')}</P>
              </Card>
            </div>
          </section>

          {/* ═══════════════════════════════════════════════════════ */}
          {/* 2. FLEET */}
          {/* ═══════════════════════════════════════════════════════ */}
          <section id="ref-fleet" className="space-y-4 scroll-mt-6">
            <div className="flex items-center gap-3 border-b border-gensui-700/30 pb-3">
              <Users size={20} className="text-emerald-400" />
              <div>
                <h2 className="text-lg font-bold text-gensui-100 uppercase tracking-widest">{t('guide.sec_fleet_title', 'Fleet Management')}</h2>
                <p className="text-xs text-gensui-400">{t('guide.sec_fleet_desc', 'View, search, and filter all enrolled Shogun instances.')}</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Card icon={Search} iconColor="text-cyan-400" title={t('guide.card_search_bar', 'Search & Filter Bar')}>
                <P>{t('guide.card_search_bar_desc', 'A text search field and a status dropdown at the top. Search by instance name or hostname. Filter by status: All, Online, or Offline.')}</P>
              </Card>
              <Card icon={Eye} iconColor="text-cyan-400" title={t('guide.card_fleet_table', 'Fleet Table')}>
                <P>{t('guide.card_fleet_table_desc', 'A sortable table with columns: Instance (name + hostname, clickable to detail), Status (online/offline badge with pulse), Environment, Harakiri (active state or "—"), Samurai count, Workflows count, Last Seen timestamp. Data auto-refreshes every 10 seconds.')}</P>
              </Card>
              <Card icon={Server} iconColor="text-cyan-400" title={t('guide.card_click_instance', 'Clicking an Instance')} span2>
                <P>{t('guide.card_click_instance_desc', 'Click any instance name in the table to navigate to its Shogun Detail page (see next section). This is the deep-dive view for a single fleet member.')}</P>
              </Card>
            </div>
          </section>

          {/* ═══════════════════════════════════════════════════════ */}
          {/* 3. SHOGUN DETAIL */}
          {/* ═══════════════════════════════════════════════════════ */}
          <section id="ref-detail" className="space-y-4 scroll-mt-6">
            <div className="flex items-center gap-3 border-b border-gensui-700/30 pb-3">
              <Server size={20} className="text-cyan-400" />
              <div>
                <h2 className="text-lg font-bold text-gensui-100 uppercase tracking-widest">{t('guide.sec_detail_title', 'Shogun Detail &mdash; Instance Deep Dive')}</h2>
                <p className="text-xs text-gensui-400">{t('guide.sec_detail_desc', 'Full operational profile for a single Shogun instance.')}</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Card icon={Tag} iconColor="text-cyan-400" title={t('guide.card_header_badges', 'Header & Status Badges')}>
                <P>{t('guide.card_header_badges_desc', 'Shows the instance name, online/offline badge, and a pulsing red Harakiri badge if active. Below: hostname, environment, and enrollment date. A back arrow returns to the Fleet page.')}</P>
              </Card>
              <Card icon={Activity} iconColor="text-cyan-400" title={t('guide.card_stats_row', 'Stats Row')}>
                <P>{t('guide.card_stats_row_desc', 'Five metric cards: Samurai count, Workflows running, Mado Sessions, Last Seen time, and Enrollment status. Each has a colored icon.')}</P>
              </Card>
              <Card icon={Info} iconColor="text-cyan-400" title={t('guide.card_identity_card', 'Identity Card (Left Column)')}>
                <P>{t('guide.card_identity_card_desc', 'Displays: Version, Build hash (first 12 chars), OS, Deploy Type, Organization, Owner, and Disconnect Behavior. All read from the Shogun\'s heartbeat telemetry.')}</P>
              </Card>
              <Card icon={Shield} iconColor="text-amber-400" title={t('guide.card_security_posture', 'Security Posture Card')}>
                <P>{t('guide.card_security_posture_desc', 'Shows the effective posture currently applied to this Shogun: posture name, source (individual, group, or global), and level number. If no posture is assigned, shows "No posture assigned."')}</P>
              </Card>
              <Card icon={Layers} iconColor="text-purple-400" title={t('guide.card_groups_card', 'Groups Card')}>
                <P>{t('guide.card_groups_card_desc', 'Lists all groups this Shogun belongs to as purple tag badges. Groups are managed from the Groups page and allow collective posture/policy application.')}</P>
              </Card>
              <Card icon={AlertTriangle} iconColor="text-red-400" title={t('guide.card_actions', 'Actions Card')}>
                <P>{t('guide.card_actions_desc', 'Three action buttons for this specific instance:')}</P>
                <ul className="text-xs text-gensui-400 space-y-1 ml-4 list-disc">
                  <li><strong className="text-amber-400">{t('guide.card_soft_freeze', 'Soft Freeze:')}</strong> {t('guide.card_soft_freeze_desc', 'Persists the governed-operation gate and requests best-effort cancellation of supported active work.')}</li>
                  <li><strong className="text-red-400">{t('guide.card_hard_stop', 'Hard Stop:')}</strong> {t('guide.card_hard_stop_desc', 'Requests urgent cancellation on supported instrumented paths; it does not guarantee that every host or external process stops immediately.')}</li>
                  <li><strong className="text-red-400">{t('guide.card_disable_instance', 'Disable Instance:')}</strong> {t('guide.card_disable_instance_desc', 'Revokes enrollment. The Shogun is disconnected from the fleet permanently until re-enrolled.')}</li>
                </ul>
              </Card>
              <Card icon={Activity} iconColor="text-cyan-400" title={t('guide.card_activity_timeline', 'Activity Timeline (Right Column)')} span2>
                <P>{t('guide.card_activity_timeline_desc', 'A scrollable timeline of telemetry events from this specific Shogun. Each event shows: severity dot (red/amber/cyan/gray), event type, category, payload message, and timestamp. Limited to the 50 most recent events. Auto-refreshes every 15 seconds.')}</P>
              </Card>
            </div>
          </section>

          {/* ═══════════════════════════════════════════════════════ */}
          {/* 4. NETWORK TOPOLOGY */}
          {/* ═══════════════════════════════════════════════════════ */}
          <section id="ref-network" className="space-y-4 scroll-mt-6">
            <div className="flex items-center gap-3 border-b border-gensui-700/30 pb-3">
              <Network size={20} className="text-cyan-400" />
              <div>
                <h2 className="text-lg font-bold text-gensui-100 uppercase tracking-widest">{t('guide.sec_network_title', 'Network Topology &mdash; Visual Map')}</h2>
                <p className="text-xs text-gensui-400">{t('guide.sec_network_desc', 'Interactive SVG graph showing all fleet members, their connections, and discovered hosts.')}</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Card icon={Globe} iconColor="text-cyan-400" title={t('guide.card_topology_graph', 'Topology Graph')}>
                <P>{t('guide.card_topology_graph_desc', 'A full-width interactive SVG canvas. At the center: the Gensui Hub (gold border, logo). Around it in a circle: all enrolled Shogun instances as colored nodes. Lines connect each node to the hub (cyan). Dashed amber lines show Nexus peer-to-peer connections between Shoguns.')}</P>
              </Card>
              <Card icon={Eye} iconColor="text-emerald-400" title={t('guide.card_node_colors', 'Node Colors & Status')}>
                <P>{t('guide.card_node_colors_desc', 'Each node has a color indicating status:')}</P>
                <ul className="text-xs text-gensui-400 space-y-1 ml-4 list-disc">
                  <li><strong className="text-emerald-400">{t('guide.card_green_online', 'Green (Online):')}</strong> {t('guide.card_green_online_desc', 'Connected and reporting heartbeats. Has a pulsing animation ring.')}</li>
                  <li><strong className="text-gensui-400">{t('guide.card_gray_offline', 'Gray (Offline):')}</strong> {t('guide.card_gray_offline_desc', 'Not responding. No pulse.')}</li>
                  <li><strong className="text-red-400">{t('guide.card_red_harakiri', 'Red (Harakiri):')}</strong> {t('guide.card_red_harakiri_desc', 'Emergency shutdown is active on this instance.')}</li>
                </ul>
              </Card>
              <Card icon={Search} iconColor="text-cyan-400" title={t('guide.card_network_scan', 'Network Scan')}>
                <P>{t('guide.card_network_scan_desc', 'Click "Scan Network" to probe your local subnet for other Shogun instances. The scan probes all IPs on port 8000, identifies Shogun instances (by checking /health), and classifies them as enrolled, unenrolled (rogue), or unknown. Results appear as dashed-border nodes in an outer ring.')}</P>
              </Card>
              <Card icon={Monitor} iconColor="text-cyan-400" title={t('guide.card_pan_zoom', 'Pan & Zoom Controls')}>
                <P>{t('guide.card_pan_zoom_desc', 'Scroll wheel to zoom in/out. Click and drag to pan. Use the zoom controls in the bottom-left: zoom in (+), zoom out (−), reset view. Hover over any node to see a detailed tooltip with hostname, status, samurai count, and enrollment info. Click an enrolled node to navigate to its detail page.')}</P>
              </Card>
              <Card icon={AlertTriangle} iconColor="text-red-400" title={t('guide.card_rogue_detection', 'Rogue Detection')} span2>
                <P>{t('guide.card_rogue_detection_desc', 'After a network scan, unenrolled Shogun instances appear as red dashed-border nodes with a warning icon. These are Shogun instances on your network that are not enrolled in Gensui — potential security risks. Unknown hosts (port 8000 open but not Shogun) appear as gray dotted nodes. A red trust boundary ring separates enrolled nodes from external ones.')}</P>
              </Card>
              <Card icon={Globe} iconColor="text-purple-400" title={t('guide.card_external_agents', 'External Enterprise Agents')} span2>
                <P>{t('guide.card_external_agents_desc', 'When Shogun instances have external agents registered via the Nexus External Gateway, they appear on the topology as diamond-shaped nodes connected to their host Shogun with dashed purple lines.')}</P>
              </Card>
            </div>
          </section>

          {/* ═══════════════════════════════════════════════════════ */}
          {/* 5. GROUPS */}
          {/* ═══════════════════════════════════════════════════════ */}
          <section id="ref-groups" className="space-y-4 scroll-mt-6">
            <div className="flex items-center gap-3 border-b border-gensui-700/30 pb-3">
              <Layers size={20} className="text-purple-400" />
              <div>
                <h2 className="text-lg font-bold text-gensui-100 uppercase tracking-widest">{t('guide.sec_groups_title', 'Groups &mdash; Collective Management')}</h2>
                <p className="text-xs text-gensui-400">{t('guide.sec_groups_desc', 'Organize Shogun instances into groups for collective policy management.')}</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Card icon={Zap} iconColor="text-purple-400" title={t('guide.card_create_group', 'Create Group')}>
                <P>{t('guide.card_create_group_desc', 'Enter a group name in the text field and click "Create Group". Groups let you apply postures, trigger Harakiri, and manage policies for multiple Shoguns at once instead of one by one.')}</P>
              </Card>
              <Card icon={Trash2} iconColor="text-red-400" title={t('guide.card_group_cards', 'Group Cards')}>
                <P>{t('guide.card_group_cards_desc', 'Each group appears as a card showing the group name, member count, and optional description. Click the trash icon on a card to delete the group (with confirmation). Deleting a group does not delete its member Shoguns — they simply become ungrouped.')}</P>
              </Card>
            </div>
          </section>

          {/* ═══════════════════════════════════════════════════════ */}
          {/* 6. POSTURES */}
          {/* ═══════════════════════════════════════════════════════ */}
          <section id="ref-postures" className="space-y-4 scroll-mt-6">
            <div className="flex items-center gap-3 border-b border-gensui-700/30 pb-3">
              <Shield size={20} className="text-amber-400" />
              <div>
                <h2 className="text-lg font-bold text-gensui-100 uppercase tracking-widest">{t('guide.sec_postures_title', 'Security Postures')}</h2>
                <p className="text-xs text-gensui-400">{t('guide.sec_postures_desc', 'Define what Shogun instances are allowed to do. Each posture is a permission template.')}</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Card icon={Shield} iconColor="text-amber-400" title={t('guide.card_posture_cards', 'Posture Cards')} span2>
                <P>{t('guide.card_posture_cards_desc', 'Each posture card shows the name, level number (0–100, higher = more restrictive), and description. A "Built-in" tag appears on system-defined postures.')}</P>
              </Card>
              <Card icon={Zap} iconColor="text-emerald-400" title={t('guide.card_create_posture', 'Create Posture')}>
                <P>{t('guide.card_create_posture_desc', 'Click "Create Posture" in the top right to open the creation modal. Fill in a name, description, level (0–100), and toggle each of the 14 permission flags.')}</P>
              </Card>
              <Card icon={Eye} iconColor="text-cyan-400" title={t('guide.card_edit_posture', 'Edit Posture')}>
                <P>{t('guide.card_edit_posture_desc', 'Hover over any posture card and click the pencil icon to open the edit modal. You can change the description, level, all 14 permission flags, and tool overrides. Built-in posture names cannot be changed.')}</P>
              </Card>
              <Card icon={Trash2} iconColor="text-red-400" title={t('guide.card_delete_posture', 'Delete Posture')}>
                <P>{t('guide.card_delete_posture_desc', 'Custom postures can be deleted by clicking the trash icon on the card. Deleting a posture automatically unassigns it from any members or groups. Built-in postures cannot be deleted.')}</P>
              </Card>
              <Card icon={Settings} iconColor="text-purple-400" title={t('guide.card_tool_overrides', 'Tool Overrides')}>
                <P>{t('guide.card_tool_overrides_desc', 'In the create/edit modal, expand the "Tool Overrides" section to define per-tool rules. Select a tool from the dropdown, then set it to Allow, Confirm (requires human approval), or Block (tool call is rejected).')}</P>
              </Card>
              <Card icon={Lock} iconColor="text-amber-400" title={t('guide.card_permission_cats', 'Permission Categories (14 Total)')} span2>
                <P>{t('guide.card_permission_cats_desc', 'Each posture controls these 14 permission flags:')}</P>
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {[
                    'external models', 'local models', 'tool execution', 'mado (browser)',
                    'memory write', 'memory read', 'agent flow', 'nexus',
                    'samurai delegation', 'scheduled triggers', 'autonomous loops',
                    'external web', 'file write', 'external api',
                  ].map(p => (
                    <span key={p} className="text-[10px] px-2 py-0.5 rounded-full bg-gensui-700/40 text-gensui-300 border border-gensui-600/30">{p}</span>
                  ))}
                </div>
              </Card>
            </div>
          </section>

          {/* ═══════════════════════════════════════════════════════ */}
          {/* 7. HARAKIRI CONTROL */}
          {/* ═══════════════════════════════════════════════════════ */}
          <section id="ref-harakiri" className="space-y-4 scroll-mt-6">
            <div className="flex items-center gap-3 border-b border-red-800/40 pb-3">
              <Skull size={20} className="text-red-400" />
              <div>
                <h2 className="text-lg font-bold text-gensui-100 uppercase tracking-widest">{t('guide.sec_harakiri_title', 'Harakiri Control Center')}</h2>
                <p className="text-xs text-red-400">{t('guide.sec_harakiri_desc', 'Emergency shutdown and containment. Use with extreme caution.')}</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Card icon={Zap} iconColor="text-red-400" title={t('guide.card_harakiri_panel', 'Initiate Harakiri Panel')} span2>
                <P>{t('guide.card_harakiri_panel_desc', 'The main trigger panel. Configure and execute emergency shutdowns:')}</P>
                <ul className="text-xs text-gensui-400 space-y-1.5 ml-4 list-disc">
                  <li><strong className="text-gensui-200">{t('guide.card_scope', 'Scope:')}</strong> {t('guide.card_scope_desc', 'Choose Individual (one Shogun) or Global (ALL Shoguns in the fleet simultaneously).')}</li>
                  <li><strong className="text-gensui-200">{t('guide.card_mode', 'Mode:')}</strong> {t('guide.card_mode_desc', 'Four escalation levels: Soft Freeze, Hard Stop, Network Isolate, Full Terminate.')}</li>
                  <li><strong className="text-gensui-200">{t('guide.card_target', 'Target Shogun:')}</strong> {t('guide.card_target_desc', '(Individual mode only) Select which instance to target from a dropdown.')}</li>
                  <li><strong className="text-gensui-200">{t('guide.card_reason', 'Reason:')}</strong> {t('guide.card_reason_desc', 'A text field for documenting why the Harakiri is being triggered. Logged in the audit trail.')}</li>
                </ul>
              </Card>
              <Card icon={Lock} iconColor="text-red-400" title={t('guide.card_two_step', 'Two-Step Confirmation')}>
                <P>{t('guide.card_two_step_desc', 'After clicking "Initiate Harakiri," a red confirmation box appears. You must type "CONFIRM HARAKIRI" (or "CONFIRM GLOBAL HARAKIRI" for global scope) exactly to enable the Execute button. This prevents accidental activation.')}</P>
              </Card>
              <Card icon={Activity} iconColor="text-cyan-400" title={t('guide.card_event_history', 'Event History Table')}>
                <P>{t('guide.card_event_history_desc', 'Below the trigger panel, a table of all past Harakiri events: Scope, Mode, Status, Affected count, Acknowledged count, Timestamp, and a Release button to lift an active Harakiri.')}</P>
              </Card>
            </div>
          </section>

          {/* ═══════════════════════════════════════════════════════ */}
          {/* 8. ACTIVITY MONITOR */}
          {/* ═══════════════════════════════════════════════════════ */}
          <section id="ref-activity" className="space-y-4 scroll-mt-6">
            <div className="flex items-center gap-3 border-b border-gensui-700/30 pb-3">
              <Activity size={20} className="text-cyan-400" />
              <div>
                <h2 className="text-lg font-bold text-gensui-100 uppercase tracking-widest">{t('guide.sec_activity_title', 'Activity Monitor')}</h2>
                <p className="text-xs text-gensui-400">{t('guide.sec_activity_desc', 'Real-time telemetry event stream from all fleet members.')}</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Card icon={Search} iconColor="text-cyan-400" title={t('guide.card_category_filter', 'Category Filter')}>
                <P>{t('guide.card_category_filter_desc', 'A dropdown filter in the top-right lets you filter events by category: System, Security, Agent, Tool, Model, or All Categories.')}</P>
              </Card>
              <Card icon={Eye} iconColor="text-cyan-400" title={t('guide.card_event_table', 'Event Table')}>
                <P>{t('guide.card_event_table_desc', 'Columns: Time, Severity (colored badge), Type (monospace event identifier), Category, Shogun (first 8 chars of ID). Shows the latest 100 events. Auto-refreshes every 5 seconds.')}</P>
              </Card>
            </div>
          </section>

          {/* ═══════════════════════════════════════════════════════ */}
          {/* 9. AUDIT LOG */}
          {/* ═══════════════════════════════════════════════════════ */}
          <section id="ref-audit" className="space-y-4 scroll-mt-6">
            <div className="flex items-center gap-3 border-b border-gensui-700/30 pb-3">
              <FileSearch size={20} className="text-gensui-400" />
              <div>
                <h2 className="text-lg font-bold text-gensui-100 uppercase tracking-widest">{t('guide.sec_audit_title', 'Audit Log &mdash; HMAC-Chained')}</h2>
                <p className="text-xs text-gensui-400">{t('guide.sec_audit_desc', 'HMAC-chained records for instrumented administrative actions, with consistency checks for covered fields.')}</p>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3">
              <Card icon={FileSearch} iconColor="text-gensui-300" title={t('guide.card_audit_table', 'Audit Table')}>
                <P>{t('guide.card_audit_table_desc', 'Columns: Time, Actor (who performed the action), Action (monospace identifier), Target (type + first 8 chars of target ID), Reason. Filter by action using the text input. The subtitle shows "HMAC-chained" confirming these entries are cryptographically linked for tamper detection.')}</P>
              </Card>
            </div>
          </section>

          {/* ═══════════════════════════════════════════════════════ */}
          {/* 10. ALERTS */}
          {/* ═══════════════════════════════════════════════════════ */}
          <section id="ref-alerts" className="space-y-4 scroll-mt-6">
            <div className="flex items-center gap-3 border-b border-gensui-700/30 pb-3">
              <Bell size={20} className="text-amber-400" />
              <div>
                <h2 className="text-lg font-bold text-gensui-100 uppercase tracking-widest">{t('guide.sec_alerts_title', 'Alerts')}</h2>
                <p className="text-xs text-gensui-400">{t('guide.sec_alerts_desc', 'Security and system alerts from across the fleet.')}</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Card icon={Bell} iconColor="text-amber-400" title={t('guide.card_alerts_table', 'Alerts Table')}>
                <P>{t('guide.card_alerts_table_desc', 'Columns: Time, Severity (CRITICAL/HIGH/MEDIUM/LOW), Type, Description, Status (active/resolved), Actions.')}</P>
              </Card>
              <Card icon={Check} iconColor="text-emerald-400" title={t('guide.card_resolving', 'Resolving Alerts')}>
                <P>{t('guide.card_resolving_desc', 'Active alerts show a "Resolve" button in the Actions column. Clicking it marks the alert as resolved and logs the resolution in the audit trail.')}</P>
              </Card>
            </div>
          </section>

          {/* ═══════════════════════════════════════════════════════ */}
          {/* 11. ENROLLMENT */}
          {/* ═══════════════════════════════════════════════════════ */}
          <section id="ref-enrollment" className="space-y-4 scroll-mt-6">
            <div className="flex items-center gap-3 border-b border-gensui-700/30 pb-3">
              <UserPlus size={20} className="text-amber-400" />
              <div>
                <h2 className="text-lg font-bold text-gensui-100 uppercase tracking-widest">{t('guide.sec_enrollment_title', 'Enrollment Management')}</h2>
                <p className="text-xs text-gensui-400">{t('guide.sec_enrollment_desc', 'Approve new Shogun instances and manage enrollment tokens.')}</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Card icon={UserPlus} iconColor="text-amber-400" title={t('guide.card_pending_table', 'Pending Enrollments Table')} span2>
                <P>{t('guide.card_pending_table_desc', 'When a Shogun instance connects to Gensui for the first time, it appears here as a pending enrollment. The table shows: Instance name, Hostname, Environment, OS, Requested timestamp, and Actions (Approve/Reject).')}</P>
              </Card>
              <Card icon={Key} iconColor="text-cyan-400" title={t('guide.card_enrollment_tokens', 'Enrollment Tokens')}>
                <P>{t('guide.card_enrollment_tokens_desc', 'Pre-generate tokens that Shogun instances can use to auto-enroll. Enter a label and click "Generate Token". Each token shows: label, first 30 characters, use count vs. max uses.')}</P>
              </Card>
              <Card icon={Copy} iconColor="text-cyan-400" title={t('guide.card_copy_token', 'Copy Token')}>
                <P>{t('guide.card_copy_token_desc', 'Click the copy icon next to any token to copy it to your clipboard. Send this token to the Shogun operator — they paste it into their Gensui connection form.')}</P>
              </Card>
              <Card icon={X} iconColor="text-red-400" title={t('guide.card_revoke_token', 'Revoke Token')} span2>
                <P>{t('guide.card_revoke_token_desc', 'Click the ban icon next to any active token to revoke it. Once revoked, the token can never be used again for enrollment. The token remains visible with a red "Revoked" badge for audit purposes. This action is logged in the HMAC-chained audit trail.')}</P>
              </Card>
            </div>
          </section>

          {/* ═══════════════════════════════════════════════════════ */}
          {/* 12. SETTINGS */}
          {/* ═══════════════════════════════════════════════════════ */}
          <section id="ref-settings" className="space-y-4 scroll-mt-6">
            <div className="flex items-center gap-3 border-b border-gensui-700/30 pb-3">
              <Settings size={20} className="text-cyan-400" />
              <div>
                <h2 className="text-lg font-bold text-gensui-100 uppercase tracking-widest">{t('guide.sec_settings_title', 'Settings')}</h2>
                <p className="text-xs text-gensui-400">{t('guide.sec_settings_desc', 'Manage your admin profile, password, and view server configuration.')}</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Card icon={Users} iconColor="text-cyan-400" title={t('guide.card_profile', 'Profile Section')}>
                <P>{t('guide.card_profile_desc', 'View your email (read-only), role (read-only), and edit your display name. Click "Save Profile" to persist changes.')}</P>
              </Card>
              <Card icon={Lock} iconColor="text-amber-400" title={t('guide.card_change_pw', 'Change Password')}>
                <P>{t('guide.card_change_pw_desc', 'Enter your current password, new password (minimum 6 characters), and confirm the new password. Passwords must match.')}</P>
              </Card>
              <Card icon={Server} iconColor="text-purple-400" title={t('guide.card_server_config', 'Server Configuration')}>
                <P>{t('guide.card_server_config_desc', 'Read-only display of server settings: JWT Token Expiry, Heartbeat Timeout, Enrollment Approval mode, Default Posture. These are configured via the .env file.')}</P>
              </Card>
              <Card icon={Info} iconColor="text-gensui-400" title={t('guide.card_about', 'About')}>
                <P>{t('guide.card_about_desc', 'Displays the Gensui version number and confirms it is part of the Shogun AFM (Agent Fleet Management) platform.')}</P>
              </Card>
            </div>
          </section>

          {/* Security Protocols — First section (Governance overview) */}
          <section id="ref-security" className="space-y-6">
            <div className="flex items-center gap-3 border-b border-gensui-700 pb-3">
              <ShieldAlert size={28} className="text-red-400" />
              <div>
                <h2 className="text-2xl font-bold text-gensui-50">{t('guide.sec_security_title', 'Safety & Security Protocols')}</h2>
                <p className="text-xs text-gensui-400">{t('guide.sec_security_governance_desc', 'Gensui\'s defense-in-depth security model for centrally governing Shogun instances.')}</p>
              </div>
            </div>

            {/* ToolGate Governance */}
            <div className="glass-card p-5 space-y-4">
              <div className="flex items-center gap-2">
                <ShieldAlert size={18} className="text-amber-400" />
                <h3 className="text-lg font-bold text-gensui-100">{t('guide.card_toolgate_governance', 'ToolGate — Centralized Tool Enforcement')}</h3>
              </div>
              <P>{t('guide.card_toolgate_governance_desc', 'ToolGate is the runtime safety gate that sits between the AI model and tool execution on every Shogun instance. From Gensui, capability boundaries, tool-level verdicts, and advanced content rules are stored on each posture and pushed to assigned instances through policy sync.')}</P>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-lg p-3 space-y-1">
                  <div className="text-xs font-bold text-emerald-400 uppercase tracking-wider">ALLOW</div>
                  <p className="text-[11px] text-gensui-400">{t('guide.toolgate_allow', 'Tool executes immediately with no interruption. Used for low-risk, read-only operations.')}</p>
                </div>
                <div className="bg-amber-500/5 border border-amber-500/20 rounded-lg p-3 space-y-1">
                  <div className="text-xs font-bold text-amber-400 uppercase tracking-wider">CONFIRM</div>
                  <p className="text-[11px] text-gensui-400">{t('guide.toolgate_confirm', 'Tool pauses and shows a confirmation card to the local operator. They must approve or deny before execution. 60-second auto-deny timeout.')}</p>
                </div>
                <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3 space-y-1">
                  <div className="text-xs font-bold text-red-400 uppercase tracking-wider">BLOCK</div>
                  <p className="text-[11px] text-gensui-400">{t('guide.toolgate_block', 'Tool is blocked outright. The AI receives a "blocked" response and must find an alternative.')}</p>
                </div>
              </div>
              <div className="bg-orange-500/5 border border-orange-500/20 rounded-lg p-3 space-y-1">
                <div className="text-xs font-bold text-orange-300 uppercase tracking-wider">{t('guide.toolgate_advanced', 'Advanced Content Controls')}</div>
                <p className="text-[11px] text-gensui-400">{t('guide.toolgate_advanced_desc', 'Advanced mode flags configured words or phrases inside nested tool arguments. Rules support contains or whole-word matching, optional case sensitivity, global or tool-specific targeting, and confirm or block verdicts. They can only tighten policy and remain active from the cached posture during an outage.')}</p>
              </div>
              <div className="bg-gensui-800 border border-gensui-700 p-3 rounded-lg">
                <p className="text-xs text-gensui-400 leading-relaxed"><strong className="text-gensui-200">{t('guide.toolgate_priority', 'Monotonic Policy Resolution:')}</strong> {t('guide.toolgate_priority_desc', 'Capability boundaries, parameter safety, advanced content rules, Campaign rules, local rules, and Gensui rules are resolved to the most restrictive verdict. No lower layer can relax a block or confirmation requirement imposed above it.')}</p>
              </div>
            </div>

            {/* Posture Push */}
            <div className="glass-card p-5 space-y-4">
              <div className="flex items-center gap-2">
                <Shield size={18} className="text-cyan-400" />
                <h3 className="text-lg font-bold text-gensui-100">{t('guide.card_posture_push_governance', 'Posture Push — Policy Sync')}</h3>
              </div>
              <P>{t('guide.card_posture_push_governance_desc', 'Every Shogun instance periodically (every 30 seconds by default) fetches its effective posture from Gensui. This includes:')}</P>
              <ul className="text-xs text-gensui-400 space-y-2 ml-4 list-disc leading-relaxed">
                <li><strong className="text-gensui-200">{t('guide.posture_rules', 'Posture Rules:')}</strong> {t('guide.posture_rules_desc', 'allow/deny flags for external models, tool execution, Mado browser, memory access, Nexus, sub-agents, scheduled triggers, autonomous loops, file writes, and external APIs.')}</li>
                <li><strong className="text-gensui-200">{t('guide.tool_overrides_sync', 'Tool Overrides:')}</strong> {t('guide.tool_overrides_sync_desc', 'Per-tool allow/confirm/block overrides configured in the posture\'s tool_overrides field.')}</li>
                <li><strong className="text-gensui-200">{t('guide.advanced_controls_sync', 'Advanced Controls:')}</strong> {t('guide.advanced_controls_sync_desc', 'Content-aware word and phrase rules, matching behavior, target tools, and confirm/block verdicts configured in Gensui ToolGate.')}</li>
                <li><strong className="text-gensui-200">{t('guide.global_posture_sync', 'Global Posture:')}</strong> {t('guide.global_posture_sync_desc', 'If a global posture override is active, it takes precedence over individual or group assignments.')}</li>
                <li><strong className="text-gensui-200">{t('guide.harakiri_state_sync', 'Harakiri State:')}</strong> {t('guide.harakiri_state_sync_desc', 'If Harakiri is triggered from Gensui, the posture is forced to the most restrictive level.')}</li>
              </ul>
            </div>

            {/* Quarantine */}
            <div className="glass-card p-5 space-y-4">
              <div className="flex items-center gap-2">
                <Trash2 size={18} className="text-purple-400" />
                <h3 className="text-lg font-bold text-gensui-100">{t('guide.card_quarantine_governance', 'Quarantine — Shogun Trash')}</h3>
              </div>
              <P>{t('guide.card_quarantine_governance_desc', 'Each Shogun instance includes a quarantine system (.shogun_trash/) that moves deleted files to a recoverable trash folder instead of permanently deleting them. Files can be recovered within 30 days. This protects against accidental or AI-initiated data loss.')}</P>
            </div>

            {/* Prompt Injection */}
            <div className="glass-card p-5 space-y-4">
              <div className="flex items-center gap-2">
                <Lock size={18} className="text-red-400" />
                <h3 className="text-lg font-bold text-gensui-100">{t('guide.card_injection_governance', 'Prompt Injection Containment')}</h3>
              </div>
              <P>{t('guide.card_injection_governance_desc', 'When Shogun agents fetch external content (web pages, emails, calendar events), the content is wrapped with [UNTRUSTED EXTERNAL DATA] boundary markers. The markers help the model treat embedded instructions as untrusted, but do not replace ToolGate policy, least privilege, output review, or other prompt-injection controls.')}</P>
            </div>

            {/* Audit & Compliance */}
            <div className="glass-card p-5 space-y-4">
              <div className="flex items-center gap-2">
                <FileSearch size={18} className="text-gensui-400" />
                <h3 className="text-lg font-bold text-gensui-100">{t('guide.card_audit_compliance', 'Audit & Compliance')}</h3>
              </div>
              <P>{t('guide.card_audit_compliance_desc', 'Instrumented security decisions — including ToolGate verdicts, posture changes, harakiri activations, and token revocations — are recorded in an append-only HMAC-chained audit log. Chain checks and exports can support investigation and NIS2, SOC 2, or EU AI Act assessments; they do not prove completeness or establish compliance.')}</P>
            </div>
          </section>

          {/* Fleet Audit Dashboard */}
          <section id="ref-fleet-audit" className="space-y-6">
            <div className="flex items-center gap-3 border-b border-gensui-700 pb-3">
              <BarChart3 size={28} className="text-cyan-400" />
              <div>
                <h2 className="text-2xl font-bold text-gensui-50">{t('guide.sec_fleet_audit_title', 'Fleet Audit Dashboard')}</h2>
                <p className="text-xs text-gensui-400">{t('guide.sec_fleet_audit_desc', 'Multi-instance audit analytics, governance-evidence summaries, and chain-link checks.')}</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Card icon={BarChart3} iconColor="text-cyan-400" title={t('guide.card_overview_tab', 'Overview Tab')}>
                <P>{t('guide.card_overview_tab_desc', 'Fleet-wide statistics: total audit events, last 24h/7d counts, security-critical events, HMAC chain integrity verification, action breakdown, and actor type distribution.')}</P>
              </Card>
              <Card icon={Users} iconColor="text-emerald-400" title={t('guide.card_per_member_tab', 'Per Member Tab')}>
                <P>{t('guide.card_per_member_tab_desc', 'Audit and telemetry event counts per fleet member. Shows instance name, enrollment status, total events, critical event count, and last event timestamp.')}</P>
              </Card>
              <Card icon={Activity} iconColor="text-amber-400" title={t('guide.card_telemetry_tab', 'Telemetry Analytics Tab')}>
                <P>{t('guide.card_telemetry_tab_desc', 'Aggregated telemetry breakdown by severity, category, event type (top 20), and per-member distribution. Filterable by date range.')}</P>
              </Card>
              <Card icon={Shield} iconColor="text-cyan-400" title={t('guide.card_compliance_tab', 'Compliance Tab')}>
                <P>{t('guide.card_compliance_tab_desc', 'Governance-evidence summary with references relevant to NIS2, SOC 2, and the EU AI Act. It shows fleet size, harakiri activations, posture changes, enrollment events, token revocations, and chain-link checks, but does not determine compliance.')}</P>
              </Card>
              <Card icon={FileSearch} iconColor="text-gensui-400" title={t('guide.card_raw_log_tab', 'Raw Log Tab')}>
                <P>{t('guide.card_raw_log_tab_desc', 'Available audit records with action filtering. Displayed fields depend on captured events.')}</P>
              </Card>
              <Card icon={Copy} iconColor="text-purple-400" title={t('guide.card_csv_export', 'CSV Export')}>
                <P>{t('guide.card_csv_export_desc', 'Export up to 50,000 available audit records as CSV for offline analysis, governance review, or SIEM integration. The export does not prove record completeness.')}</P>
              </Card>
            </div>
          </section>

          {/* Enterprise Identity */}
          <section id="ref-identity" className="space-y-6">
            <div className="flex items-center gap-3 border-b border-gensui-700 pb-3">
              <Key size={28} className="text-purple-400" />
              <div>
                <h2 className="text-2xl font-bold text-gensui-50">{t('guide.sec_identity_title', 'Enterprise Identity')}</h2>
                <p className="text-xs text-gensui-400">{t('guide.sec_identity_desc', 'Reserved service-account and SSO provider configuration. These records are not accepted for authentication in this release.')}</p>
              </div>
            </div>

            {/* Service Accounts */}
            <div className="glass-card p-5 space-y-4">
              <div className="flex items-center gap-2">
                <Key size={18} className="text-amber-400" />
                <h3 className="text-lg font-bold text-gensui-100">{t('guide.card_service_accounts', 'Service Accounts & API Keys')}</h3>
              </div>
              <P>{t('guide.card_service_accounts_desc', 'Gensui can create and store reserved service-account credential records, but no Gensui API endpoint accepts those keys for authentication in this release. Do not use them as an access-control boundary.')}</P>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="bg-gensui-800 border border-gensui-700 rounded-lg p-3 space-y-1">
                  <div className="text-xs font-bold text-gensui-200">{t('guide.api_key_format', 'API Key Format')}</div>
                  <p className="text-[11px] text-gensui-400">{t('guide.api_key_format_desc', 'gsk_ prefix + 48 random characters. HMAC-SHA256 hashed at rest. Key prefix stored for display identification.')}</p>
                </div>
                <div className="bg-gensui-800 border border-gensui-700 rounded-lg p-3 space-y-1">
                  <div className="text-xs font-bold text-gensui-200">{t('guide.key_lifecycle', 'Key Lifecycle')}</div>
                  <p className="text-[11px] text-gensui-400">{t('guide.key_lifecycle_desc', 'Reserved keys can be created, rotated, and revoked as configuration records and the raw value is shown once. They remain unusable for API authentication until an endpoint explicitly wires and enforces the service-account dependency.')}</p>
                </div>
              </div>
            </div>

            {/* SSO / OIDC */}
            <div className="glass-card p-5 space-y-4">
              <div className="flex items-center gap-2">
                <Globe size={18} className="text-purple-400" />
                <h3 className="text-lg font-bold text-gensui-100">{t('guide.sec_sso_oidc', 'SSO / OIDC Providers')}</h3>
              </div>
              <P>{t('guide.sec_sso_oidc_desc', 'Provider records may be stored for future integration, but SSO login is unavailable in this release. Signed OIDC-token verification is not implemented; SAML 2.0 and SPIFFE/SPIRE authentication are also not implemented. Stored providers remain inactive and cannot be primary login providers.')}</P>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="bg-gensui-800 border border-gensui-700 rounded-lg p-3 space-y-1">
                  <div className="text-xs font-bold text-gensui-200">{t('guide.oidc_config', 'OIDC Configuration')}</div>
                  <p className="text-[11px] text-gensui-400">{t('guide.oidc_config_desc', 'Set issuer URL, client ID, client secret (encrypted at rest), scopes, and audience.')}</p>
                </div>
                <div className="bg-gensui-800 border border-gensui-700 rounded-lg p-3 space-y-1">
                  <div className="text-xs font-bold text-gensui-200">{t('guide.role_mapping', 'Role Mapping')}</div>
                  <p className="text-[11px] text-gensui-400">{t('guide.role_mapping_desc', 'Role and claim-mapping values are stored as configuration only. No login verifier currently applies them to an authenticated user.')}</p>
                </div>
                <div className="bg-gensui-800 border border-gensui-700 rounded-lg p-3 space-y-1">
                  <div className="text-xs font-bold text-gensui-200">{t('guide.auto_provisioning', 'Auto-Provisioning')}</div>
                  <p className="text-[11px] text-gensui-400">{t('guide.auto_provisioning_desc', 'Automatic user provisioning and primary-provider login are forced off until a complete signed-token validation and login flow is implemented.')}</p>
                </div>
                <div className="bg-gensui-800 border border-gensui-700 rounded-lg p-3 space-y-1">
                  <div className="text-xs font-bold text-gensui-200">{t('guide.sso_security', 'Security')}</div>
                  <p className="text-[11px] text-gensui-400">{t('guide.sso_security_desc', 'Stored client secrets are encrypted at rest and instrumented configuration changes may emit audit records. No OIDC signature, issuer, audience, expiry, SAML, or SPIFFE authentication decision is performed in this release.')}</p>
                </div>
              </div>
            </div>
          </section>

          {/* ═══════════════════════════════════════════════════════════════
              SAFETY & SECURITY PROTOCOLS (Detailed)
              ═══════════════════════════════════════════════════════════════ */}
          <section id="ref-security" className="space-y-6">
            <div className="flex items-center gap-3 border-b border-gensui-700 pb-3">
              <ShieldAlert size={28} className="text-red-400" />
              <div>
                <h2 className="text-2xl font-bold text-gensui-50">{t('guide.sec_security_title', 'Safety & Security Protocols')}</h2>
                <p className="text-xs text-gensui-400">{t('guide.sec_security_desc', 'Runtime security controls available to connected Shogun instances in the operator-managed fleet.')}</p>
              </div>
            </div>

            {/* Architecture Overview */}
            <div className="glass-card p-5 space-y-4">
              <h3 className="text-lg font-bold text-gensui-100 flex items-center gap-2"><Shield size={18} className="text-amber-400" /> {t('guide.security_architecture', 'Architecture Overview')}</h3>
              <P>{t('guide.security_architecture_desc', 'Shogun exposes six layers of security controls, with fleet policy distributed by Gensui and runtime enforcement performed by each connected instance. These controls and their records can support risk management and regulatory assessment, but do not by themselves establish NIS2, SOC 2, or EU AI Act conformity.')}</P>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {[
                  { phase: '1', title: t('guide.phase1_title', 'ToolGate'), desc: t('guide.phase1_desc', 'Runtime tool enforcement engine'), color: 'text-red-400' },
                  { phase: '2', title: t('guide.phase2_title', 'Quarantine'), desc: t('guide.phase2_desc', 'Soft-delete trash recovery'), color: 'text-amber-400' },
                  { phase: '3', title: t('guide.phase3_title', 'Prompt Injection'), desc: t('guide.phase3_desc', 'Untrusted content wrapping'), color: 'text-purple-400' },
                  { phase: '4', title: t('guide.phase4_title', 'Posture Push'), desc: t('guide.phase4_desc', 'Fleet-wide policy sync'), color: 'text-cyan-400' },
                  { phase: '5', title: t('guide.phase5_title', 'Fleet Audit'), desc: t('guide.phase5_desc', 'Multi-instance dashboards'), color: 'text-emerald-400' },
                  { phase: '6', title: t('guide.phase6_title', 'Enterprise Identity'), desc: t('guide.phase6_desc', 'Inactive configuration staging; authentication unavailable'), color: 'text-blue-400' },
                ].map(p => (
                  <div key={p.phase} className="bg-gensui-800/60 border border-gensui-700/30 rounded-lg p-3">
                    <div className={`text-xs font-bold ${p.color}`}>{t('guide.phase_label', 'Phase')} {p.phase}: {p.title}</div>
                    <p className="text-[10px] text-gensui-500 mt-1">{p.desc}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Phase 1: ToolGate */}
            <div className="glass-card p-5 space-y-4">
              <h3 className="text-lg font-bold text-gensui-100 flex items-center gap-2"><Lock size={18} className="text-red-400" /> {t('guide.security_toolgate', 'Phase 1: ToolGate — Runtime Tool Enforcement')}</h3>
              <P>{t('guide.security_toolgate_full_desc', 'ToolGate evaluates instrumented Shogun tool-execution paths against the active security posture and returns allow, confirm (human-in-the-loop), or block. Custom plugins and execution paths require separate coverage verification.')}</P>
              <div className="space-y-3">
                <div className="bg-gensui-800 border border-gensui-700 rounded-lg p-3">
                  <div className="text-xs font-bold text-gensui-200 mb-1">{t('guide.security_toolgate_eval', 'How ToolGate Evaluates a Call')}</div>
                  <ol className="text-[11px] text-gensui-400 leading-relaxed list-decimal pl-4 space-y-1">
                    <li><strong>{t('guide.eval_step1', 'Tool Override Check')}</strong> — {t('guide.eval_step1_desc', 'If the posture has a specific tool override, that verdict is returned immediately.')}</li>
                    <li><strong>{t('guide.eval_step2', 'Permission Flag Check')}</strong> — {t('guide.eval_step2_desc', 'The tool is mapped to a permission category. If that flag is false, the call is blocked.')}</li>
                    <li><strong>{t('guide.eval_step3', 'Parameter & Advanced Rule Check')}</strong> — {t('guide.eval_step3_desc', 'Built-in destructive checks and administrator-defined word or phrase rules can escalate the call to confirm or block.')}</li>
                    <li><strong>{t('guide.eval_step4', 'Mode and Risk Default')}</strong> — {t('guide.eval_step4_desc', 'If no stricter rule matches, the active mode and tool risk classification determine the default verdict.')}</li>
                  </ol>
                </div>
                <div className="bg-gensui-800 border border-gensui-700 rounded-lg p-3">
                  <div className="text-xs font-bold text-gensui-200 mb-1">{t('guide.security_toolgate_confirm', 'Confirmation Modal (Human-in-the-Loop)')}</div>
                  <p className="text-[11px] text-gensui-400 leading-relaxed">{t('guide.security_toolgate_confirm_desc', 'When a tool override is set to confirm, Shogun pauses execution and presents a confirmation modal. The user must explicitly Approve or Deny before the tool executes. Instrumented denials are recorded in the append-only HMAC-chained audit log.')}</p>
                </div>
                <div className="bg-gensui-800 border border-gensui-700 rounded-lg p-3">
                  <div className="text-xs font-bold text-gensui-200 mb-1">{t('guide.security_toolgate_audit', 'Audit Logging')}</div>
                  <p className="text-[11px] text-gensui-400 leading-relaxed">{t('guide.security_toolgate_audit_desc', 'Instrumented ToolGate evaluations record the tool name, arguments, verdict, matched rule or flag, posture name, and timestamp. Layer 2 is append-only through the application service and HMAC-chained so covered-field mismatches can be detected.')}</p>
                </div>
              </div>
            </div>

            {/* Phase 2: Quarantine */}
            <div className="glass-card p-5 space-y-4">
              <h3 className="text-lg font-bold text-gensui-100 flex items-center gap-2"><Trash2 size={18} className="text-amber-400" /> {t('guide.security_quarantine', 'Phase 2: Quarantine — Soft-Delete Recovery')}</h3>
              <P>{t('guide.security_quarantine_full_desc', 'The Quarantine system replaces hard deletes with recoverable soft deletes. When a file deletion is requested, the file is moved to .shogun_trash/ instead of being permanently removed.')}</P>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="bg-gensui-800 border border-gensui-700 rounded-lg p-3 space-y-1">
                  <div className="text-xs font-bold text-gensui-200">{t('guide.security_quarantine_storage', 'Trash Storage')}</div>
                  <p className="text-[11px] text-gensui-400">{t('guide.security_quarantine_storage_desc', 'Files retain their original path structure. Each entry stores: original_path, deleted_at, deleted_by, size_bytes, and reason.')}</p>
                </div>
                <div className="bg-gensui-800 border border-gensui-700 rounded-lg p-3 space-y-1">
                  <div className="text-xs font-bold text-gensui-200">{t('guide.security_quarantine_recovery', 'Recovery & Purge')}</div>
                  <p className="text-[11px] text-gensui-400">{t('guide.security_quarantine_recovery_desc', 'Administrators can restore files to their original location or permanently purge them. Auto-purge policies can be configured by age (e.g., 30 days).')}</p>
                </div>
              </div>
            </div>

            {/* Phase 3: Prompt Injection */}
            <div className="glass-card p-5 space-y-4">
              <h3 className="text-lg font-bold text-gensui-100 flex items-center gap-2"><AlertTriangle size={18} className="text-purple-400" /> {t('guide.security_injection', 'Phase 3: Prompt Injection Containment')}</h3>
              <P>{t('guide.security_injection_full_desc', 'External content can contain adversarial instructions. Supported ingestion paths mark designated untrusted content with boundary metadata to help policy and model layers distinguish it; verify connector coverage because marking does not eliminate prompt-injection risk.')}</P>
            </div>

            {/* Phase 4: Posture Push */}
            <div className="glass-card p-5 space-y-4">
              <h3 className="text-lg font-bold text-gensui-100 flex items-center gap-2"><Zap size={18} className="text-cyan-400" /> {t('guide.security_posture_push', 'Phase 4: Gensui → Shogun Posture Push')}</h3>
              <P>{t('guide.security_posture_push_full_desc', 'Gensui can deliver updated posture configuration to connected Shogun instances through heartbeat responses. Offline, disconnected, failed, or delayed instances may retain a cached posture; verify acknowledgement and effective state before relying on fleet consistency.')}</P>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="bg-gensui-800 border border-gensui-700 rounded-lg p-3 space-y-1">
                  <div className="text-xs font-bold text-gensui-200">{t('guide.security_posture_push_mechanism', 'Push Mechanism')}</div>
                  <p className="text-[11px] text-gensui-400">{t('guide.security_posture_push_mechanism_desc', 'Posture changes are delivered via the existing heartbeat response. No additional ports or protocols required.')}</p>
                </div>
                <div className="bg-gensui-800 border border-gensui-700 rounded-lg p-3 space-y-1">
                  <div className="text-xs font-bold text-gensui-200">{t('guide.security_posture_push_scope', 'Scope Hierarchy')}</div>
                  <p className="text-[11px] text-gensui-400">{t('guide.security_posture_push_scope_desc', 'Individual posture overrides take priority over Group posture, which overrides the Default fleet posture.')}</p>
                </div>
              </div>
            </div>

            {/* Phase 5: Fleet Audit */}
            <div className="glass-card p-5 space-y-4">
              <h3 className="text-lg font-bold text-gensui-100 flex items-center gap-2"><BarChart3 size={18} className="text-emerald-400" /> {t('guide.security_fleet_audit', 'Phase 5: Fleet Audit Views')}</h3>
              <P>{t('guide.security_fleet_audit_full_desc', 'Multi-instance audit dashboard providing operator-visible security events, governance evidence, and chain-link checks. It does not determine regulatory or certification status.')}</P>
            </div>

            {/* Phase 6: Enterprise Identity */}
            <div className="glass-card p-5 space-y-4">
              <h3 className="text-lg font-bold text-gensui-100 flex items-center gap-2"><Key size={18} className="text-blue-400" /> {t('guide.security_enterprise_id', 'Phase 6: Enterprise Identity')}</h3>
              <P>{t('guide.security_enterprise_id_full_desc', 'Gensui stores reserved service-account and provider configuration, but does not accept service-account keys or implement OIDC, SAML, or SPIFFE authentication in this release.')}</P>
            </div>

            {/* Append-only Audit Chain */}
            <div className="glass-card p-5 space-y-4">
              <h3 className="text-lg font-bold text-gensui-100 flex items-center gap-2"><FileSearch size={18} className="text-gensui-400" /> {t('guide.security_immutable_chain', 'Append-only HMAC Audit Chain (HMAC-SHA256)')}</h3>
              <P>{t('guide.security_immutable_chain_full_desc', 'Instrumented security events are dual-written to an operational store and a separate HMAC-chained store. The application service exposes append operations rather than update or delete operations; administrators with host or database access must still protect the underlying storage. Chain checks can reveal covered-field or link mismatches, but do not prove that every event was captured or establish compliance.')}</P>
            </div>

            {/* Security Postures Detail */}
            <div className="glass-card p-5 space-y-4">
              <h3 className="text-lg font-bold text-gensui-100 flex items-center gap-2"><Shield size={18} className="text-amber-400" /> {t('guide.security_postures_detail', 'Security Postures')}</h3>
              <P>{t('guide.security_postures_detail_full_desc', 'Security postures configure 14 instrumented Shogun capability flags, a severity level, and optional per-tool overrides. They are not a complete host, network, or custom-plugin security boundary; verify coverage for every deployed execution path.')}</P>
              <div className="bg-gensui-800 border border-gensui-700 rounded-lg p-3">
                <div className="text-xs font-bold text-gensui-200 mb-2">{t('guide.security_posture_levels', 'Built-in Posture Levels')}</div>
                <div className="space-y-1 text-[11px] text-gensui-400">
                  <div className="flex justify-between"><span className="text-emerald-400 font-bold">OPEN (L0)</span><span>{t('guide.posture_open', 'All 14 instrumented flags enabled; intended for trusted local development')}</span></div>
                  <div className="flex justify-between"><span className="text-sky-400 font-bold">OBSERVE_ONLY (L5)</span><span>{t('guide.posture_observe_only', 'Same enabled flags while Gensui monitors; not an enforcement guarantee')}</span></div>
                  <div className="flex justify-between"><span className="text-cyan-400 font-bold">STANDARD (L10)</span><span>{t('guide.posture_standard', 'Default operational configuration; validate it for the deployed use case')}</span></div>
                  <div className="flex justify-between"><span className="text-amber-400 font-bold">RESTRICTED (L30)</span><span>{t('guide.posture_restricted', 'Blocks Mado, autonomous scheduling, external web/API, and file writes; external models, tools, and Nexus remain enabled')}</span></div>
                  <div className="flex justify-between"><span className="text-violet-400 font-bold">LOCAL_ONLY (L40)</span><span>{t('guide.posture_local_only', 'Blocks external models, web, and APIs while retaining configured local-model and local-tool paths')}</span></div>
                  <div className="flex justify-between"><span className="text-red-400 font-bold">LOCKDOWN (L90)</span><span>{t('guide.posture_lockdown', 'Disables most instrumented capabilities; memory read and policy/heartbeat operations remain')}</span></div>
                </div>
              </div>
            </div>
          </section>

        </div>
      </div>
    </div>
  );
}
