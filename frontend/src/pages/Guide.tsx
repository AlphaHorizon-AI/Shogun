import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  BookOpen,
  Terminal,
  ShieldCheck,
  Zap,
  Layout,
  Cpu,
  Database,
  MessageSquare,
  FileText,
  Search,
  Key,
  Download,
  RefreshCw,
  AlertCircle,
  Network,
  Users,
  Compass,
  Lock,
  Flame,
  Binary,
  GitBranch,
  CheckCircle2,
  Package,
  Activity,
  Archive,
  HardDrive,
  Globe,
  Star,
  Layers,
  Sparkles,
  Link2,
  FileKey,
  Shield,
  Trash2,
  AppWindow,
  Mail,
  CalendarDays,
  Play,
  ExternalLink,
  Workflow,
  Camera,
  ShieldAlert,
  Sword,
  HelpCircle,
  Info,
  Crosshair,
  Monitor as MonitorIcon,
  FileSpreadsheet,
  FolderOpen as FolderOpenIcon,
  Power,
  List,
  Clock,
  Route as RouteIcon,
  Target,

  BrainCircuit,
  Eye,
  GitMerge,
  Printer,
  SlidersHorizontal,

} from "lucide-react";
import { cn } from '../lib/utils';
import { useTranslation } from '../i18n';
import { useLocation } from 'react-router-dom';
import {
  requestedGuideSection,
  requestedGuideTab,
  type GuideTab,
} from '../lib/guideNavigation';

type DocTab = GuideTab;
type GuideCatalog = Record<string, string>;

const guideCatalogModules = import.meta.glob('../i18n/guide/*.json', { eager: false }) as Record<
  string,
  () => Promise<{ default: GuideCatalog }>
>;
const guideCatalogCache: Record<string, GuideCatalog> = {};
const guideOriginalText = new WeakMap<Text, string>();

async function loadGuideCatalog(language: string): Promise<GuideCatalog> {
  if (guideCatalogCache[language]) return guideCatalogCache[language];

  const loader = guideCatalogModules[`../i18n/guide/${language}.json`];
  if (!loader) return {};

  try {
    const catalog = (await loader()).default;
    guideCatalogCache[language] = catalog;
    return catalog;
  } catch (error) {
    console.error(`[guide-i18n] Failed to load the ${language} Guide catalog`, error);
    return {};
  }
}

function applyGuideCatalog(root: HTMLElement, catalog: GuideCatalog) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode() as Text | null;

  while (node) {
    const isTechnicalContent = Boolean(node.parentElement?.closest('code, pre, script, style, svg'));
    if (!isTechnicalContent) {
      const current = node.nodeValue ?? '';
      const remembered = guideOriginalText.get(node);
      const candidate = remembered ?? current;
      const source = candidate.trim();

      if (source && (remembered !== undefined || Object.prototype.hasOwnProperty.call(catalog, source))) {
        if (remembered === undefined) guideOriginalText.set(node, candidate);
        const leading = candidate.match(/^\s*/)?.[0] ?? '';
        const trailing = candidate.match(/\s*$/)?.[0] ?? '';
        node.nodeValue = `${leading}${catalog[source] ?? source}${trailing}`;
      }
    }
    node = walker.nextNode() as Text | null;
  }
}

export function Guide() {
  const { t, language } = useTranslation();
  const location = useLocation();
  const [activeTab, setActiveTab] = useState<DocTab>(
    () => requestedGuideTab(window.location.search) ?? 'onboarding'
  );
  const [activeSection, setActiveSection] = useState<string>('ref-tenshu');
  const guideRootRef = useRef<HTMLDivElement>(null);
  const refContentRef = useRef<HTMLDivElement>(null);

  const REFERENCE_SECTIONS = useMemo(() => [
    { id: 'ref-tenshu', label: 'Tenshu', icon: Layout, color: 'text-shogun-blue' },
    { id: 'ref-server', label: 'Server Mode', icon: Package, color: 'text-emerald-400' },
    { id: 'ref-profile', label: 'Shogun Profile', icon: Cpu, color: 'text-shogun-gold' },
    { id: 'ref-samurai', label: 'Samurai Network', icon: Users, color: 'text-shogun-gold' },
    { id: 'ref-comms', label: 'Comms', icon: MessageSquare, color: 'text-shogun-blue' },
    { id: 'ref-supermode', label: 'Supermode Canvas', icon: Target, color: 'text-violet-400' },
    { id: 'ref-workspace', label: 'Workspace', icon: FolderOpenIcon, color: 'text-amber-400' },
    { id: 'ref-katana', label: 'Katana', icon: Sword, color: 'text-shogun-blue' },
    { id: 'ref-telegram', label: 'Telegram Setup', icon: MessageSquare, color: 'text-sky-400' },
    { id: 'ref-model-router', label: 'Model Router', icon: RouteIcon, color: 'text-blue-400' },
    { id: 'ref-visual-intake', label: 'Visual Intake', icon: Eye, color: 'text-cyan-400' },
    { id: 'ref-active-skills', label: 'Active Skills', icon: Sparkles, color: 'text-amber-400' },
    { id: 'ref-office', label: 'Office', icon: FileSpreadsheet, color: 'text-green-400' },
    { id: 'ref-ide-mode', label: 'IDE Mode', icon: MonitorIcon, color: 'text-emerald-400' },
    { id: 'ref-mado', label: 'Mado', icon: AppWindow, color: 'text-cyan-400' },
    { id: 'ref-ronin', label: 'Ronin', icon: Crosshair, color: 'text-orange-400' },
    { id: 'ref-skillopt', label: 'SkillOpt', icon: BrainCircuit, color: 'text-fuchsia-400' },
    { id: 'ref-torii', label: 'Torii', icon: Lock, color: 'text-red-400' },
    { id: 'ref-toolgate', label: 'ToolGate', icon: Shield, color: 'text-orange-400' },
    { id: 'ref-kaizen', label: 'Kaizen', icon: ShieldCheck, color: 'text-shogun-gold' },
    { id: 'ref-bushido', label: 'Bushido', icon: RefreshCw, color: 'text-shogun-blue' },
    { id: 'ref-archives', label: 'Archives', icon: Database, color: 'text-shogun-gold' },
    { id: 'ref-dojo', label: 'Dojo', icon: Flame, color: 'text-shogun-gold' },
    { id: 'ref-maintenance', label: 'Maintenance', icon: HardDrive, color: 'text-shogun-gold' },
    { id: 'ref-roles-responsibilities', label: 'Roles & Responsibilities', icon: Users, color: 'text-cyan-400' },
    { id: 'ref-modified-installations', label: 'Modified Installations', icon: GitBranch, color: 'text-amber-400' },
    { id: 'ref-incident-reporting', label: 'Incident Reporting', icon: ShieldAlert, color: 'text-red-400' },
  ], []);

  const scrollToSection = useCallback((sectionId: string) => {
    const el = document.getElementById(sectionId);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setActiveSection(sectionId);
    }
  }, []);

  useEffect(() => {
    const requested = requestedGuideTab(location.search);
    if (!requested) return;
    const timer = window.setTimeout(() => setActiveTab(requested), 0);
    return () => window.clearTimeout(timer);
  }, [location.search]);

  useEffect(() => {
    if (activeTab !== 'reference' || !location.hash) return;
    const sectionId = requestedGuideSection(
      location.hash,
      REFERENCE_SECTIONS.map(section => section.id),
    );
    if (!sectionId) return;
    const timer = window.setTimeout(() => scrollToSection(sectionId), 0);
    return () => window.clearTimeout(timer);
  }, [activeTab, location.hash, REFERENCE_SECTIONS, scrollToSection]);

  const printGrandReference = useCallback(() => {
    const content = refContentRef.current;
    if (!content) return;

    const printWindow = window.open('', '_blank', 'width=1100,height=800');
    if (!printWindow) {
      window.alert('Please allow pop-ups to print the Grand Reference.');
      return;
    }
    printWindow.opener = null;

    const title = content.querySelector('h3')?.textContent?.trim() || 'The Grand Reference';
    const printDocument = printWindow.document;
    printDocument.documentElement.lang = language;
    printDocument.title = title;
    printDocument.head.replaceChildren();
    for (const node of document.querySelectorAll('link[rel="stylesheet"], style')) {
      printDocument.head.append(node.cloneNode(true));
    }
    const printStyle = printDocument.createElement('style');
    printStyle.textContent = `
            @page { size: A4; margin: 14mm; }
            html, body { background: white !important; color: #111827 !important; }
            body { font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
            .grand-reference-print { max-width: none !important; }
            .grand-reference-print * { color: #111827 !important; border-color: #d1d5db !important; }
            .grand-reference-print section { break-inside: auto; }
            .grand-reference-print .shogun-card { break-inside: avoid; background: white !important; box-shadow: none !important; }
            .grand-reference-print h3, .grand-reference-print h4 { break-after: avoid; }
            .grand-reference-print pre, .grand-reference-print code { white-space: pre-wrap; overflow-wrap: anywhere; }
            .print-hide { display: none !important; }
          `;
    printDocument.head.append(printStyle);
    const main = printDocument.createElement('main');
    main.className = 'grand-reference-print';
    main.append(content.cloneNode(true));
    printDocument.body.replaceChildren(main);

    const printWhenReady = () => {
      printWindow.focus();
      printWindow.print();
    };
    if (printWindow.document.readyState === 'complete') {
      window.setTimeout(printWhenReady, 250);
    } else {
      printWindow.addEventListener('load', () => window.setTimeout(printWhenReady, 250), { once: true });
    }
  }, [language]);

  useEffect(() => {
    if (activeTab !== 'reference') return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        }
      },
      { rootMargin: '-80px 0px -60% 0px', threshold: 0.1 }
    );
    const timer = setTimeout(() => {
      REFERENCE_SECTIONS.forEach(({ id }) => {
        const el = document.getElementById(id);
        if (el) observer.observe(el);
      });
    }, 100);
    return () => { clearTimeout(timer); observer.disconnect(); };
  }, [activeTab, REFERENCE_SECTIONS]);

  useEffect(() => {
    let cancelled = false;
    loadGuideCatalog(language).then((catalog) => {
      if (!cancelled && guideRootRef.current) {
        applyGuideCatalog(guideRootRef.current, catalog);
      }
    });
    return () => { cancelled = true; };
  }, [activeTab, language]);

  return (
    <div ref={guideRootRef} className="max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500 pb-20">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h2 className="text-4xl font-bold shogun-title flex items-center gap-4">
            {t('guide.title', 'Framework Guide')}
            <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-1 rounded border border-shogun-border tracking-[0.3em] uppercase">{t('guide.badge', 'Knowledge Base')}</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">{t('guide.subtitle', 'Master the Shogun architecture, operations, and system maintenance.')}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap items-center gap-2 p-1 bg-shogun-card border border-shogun-border rounded-xl w-fit">
        {[
          { id: 'onboarding', label: t('guide.tab_onboarding', 'Onboarding'), icon: Compass },
          { id: 'reference', label: t('guide.tab_reference', 'Reference Manual'), icon: BookOpen },
          { id: 'architecture', label: t('guide.tab_architecture', 'Architecture'), icon: Cpu },
          { id: 'safety', label: t('guide.tab_safety', 'Safety Protocols'), icon: ShieldCheck },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as DocTab)}
            className={cn(
              "flex items-center gap-2 px-6 py-2.5 rounded-lg text-xs font-bold uppercase tracking-widest transition-all",
              activeTab === tab.id
                ? "bg-shogun-blue text-white shadow-lg"
                : "text-shogun-subdued hover:text-shogun-text hover:bg-shogun-bg"
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content Rendering */}
      <div className="grid grid-cols-1 gap-8">

        {/* Onboarding */}
        {activeTab === 'onboarding' && (
          <div className="space-y-8 animate-in slide-in-from-bottom-4">

             {/* Welcome Hero */}
             <section className="shogun-card border-l-4 border-shogun-blue">
                <h3 className="text-xl font-bold text-shogun-text mb-4 flex items-center gap-3">
                  <Zap className="w-6 h-6 text-shogun-blue" />
                  Your Journey Begins
                </h3>
                <p className="text-shogun-subdued leading-relaxed mb-6">
                  Welcome to Shogun. You are not just running a tool; you are commanding a distributed cognitive lattice.
                  This system is designed for high-stakes automation and deep research.
                  This guide will walk you through everything you need to go from zero to fully operational.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                   <div className="p-4 bg-shogun-bg border border-shogun-border rounded-xl">
                      <div className="text-shogun-blue font-bold text-lg mb-1">1. Connect Brains</div>
                      <p className="text-xs text-shogun-subdued">Head to <strong>Katana</strong> to connect an organisation-selected cloud provider or local model. Shogun supplies the orchestration layer; it does not bundle an AI model.</p>
                   </div>
                   <div className="p-4 bg-shogun-bg border border-shogun-border rounded-xl">
                      <div className="text-shogun-gold font-bold text-lg mb-1">2. Train Skills</div>
                      <p className="text-xs text-shogun-subdued">Visit the <strong>Dojo</strong> to browse 4,000+ specialized skills. Certify your agents for specific task categories.</p>
                   </div>
                   <div className="p-4 bg-shogun-bg border border-shogun-border rounded-xl">
                      <div className="text-green-500 font-bold text-lg mb-1">3. Start Chatting</div>
                      <p className="text-xs text-shogun-subdued">Open <strong>Tenshu</strong> or the global chat. Your Shogun is now ready to assist, research, and execute.</p>
                   </div>
                </div>

                <div id="ref-telegram" className="shogun-card space-y-6 scroll-mt-6 border-sky-400/20">
                   <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                      <div>
                         <div className="font-bold text-shogun-text flex items-center gap-2 text-base">
                            <MessageSquare className="w-5 h-5 text-sky-400" /> Telegram — Complete Beginner Setup
                         </div>
                         <p className="text-xs text-shogun-subdued mt-1">Use Telegram on your phone or computer to talk directly to your Shogun.</p>
                      </div>
                      <span className="text-[9px] font-bold uppercase tracking-widest text-sky-400 bg-sky-400/10 border border-sky-400/20 px-2.5 py-1 rounded-full w-fit">About 10–15 minutes</span>
                   </div>

                   <div className="p-4 rounded-lg border border-sky-400/20 bg-sky-400/5">
                      <p className="text-xs text-shogun-text font-bold">The easiest supported choice</p>
                      <p className="text-xs text-shogun-subdued leading-relaxed mt-1">
                         Choose <strong>Polling</strong>. It works while Shogun is running and does not require a public website or router changes.
                         Although the screen also shows a Webhook option, the listener in this release operates by polling. Use Webhook only if an administrator has supplied a separate compatible webhook receiver.
                      </p>
                   </div>

                   <div>
                      <h5 className="text-sm font-bold text-shogun-text mb-3">Before you begin</h5>
                      <div className="grid sm:grid-cols-3 gap-3">
                         {[
                            ['Telegram account', 'Install Telegram and sign in on your phone or computer.'],
                            ['Running Shogun', 'Shogun must remain open and have internet access to receive messages.'],
                            ['Private test first', 'Connect a private one-to-one chat before trying a Telegram group.'],
                         ].map(([title, text]) => (
                            <div key={title} className="p-3 rounded-lg bg-shogun-bg border border-shogun-border">
                               <p className="text-xs font-bold text-shogun-text">{title}</p>
                               <p className="text-[11px] text-shogun-subdued leading-relaxed mt-1">{text}</p>
                            </div>
                         ))}
                      </div>
                   </div>

                   <div className="space-y-4">
                      <h5 className="text-sm font-bold text-shogun-text">Part A — Create your Telegram bot</h5>
                      <ol className="text-xs text-shogun-subdued space-y-3 ml-5 list-decimal leading-relaxed">
                         <li>
                            Open the official <a href="https://t.me/BotFather" target="_blank" rel="noreferrer" className="text-sky-400 hover:underline font-bold">@BotFather</a> chat.
                            Check the username carefully: it must be exactly <code>@BotFather</code> and should show Telegram's verification mark.
                         </li>
                         <li>Press <strong>Start</strong>, or type <code>/start</code>. Then type <code>/newbot</code>.</li>
                         <li>BotFather asks for a display name. This is the friendly name people see, for example <code>My Shogun</code>.</li>
                         <li>
                            Choose a unique username. Telegram requires 5–32 Latin letters, numbers, or underscores, and the username must end in <code>bot</code>,
                            for example <code>northwind_shogun_bot</code>.
                         </li>
                         <li>
                            BotFather returns a long token containing numbers, a colon, and letters. Copy the entire token. Treat it exactly like a password:
                            anyone who has it can control the bot. Never paste it into email, screenshots, tickets, or chat messages.
                         </li>
                      </ol>
                      <a href="https://core.telegram.org/bots/features#botfather" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[11px] text-sky-400 hover:underline">
                         <ExternalLink className="w-3 h-3" /> Official Telegram BotFather instructions
                      </a>
                   </div>

                   <div className="space-y-4">
                      <h5 className="text-sm font-bold text-shogun-text">Part B — Connect the bot to Shogun</h5>
                      <ol className="text-xs text-shogun-subdued space-y-3 ml-5 list-decimal leading-relaxed">
                         <li>In Shogun, open <strong>The Katana → Telegram</strong>.</li>
                         <li>Paste the token into <strong>Bot Token</strong>. Leave the eye icon closed unless you need to check what you pasted.</li>
                         <li>Select <strong>Polling</strong>.</li>
                         <li>
                            For this first connection, leave <strong>Allowed Chat IDs</strong> empty. This temporary step lets Shogun discover your ID.
                            Do not leave it empty permanently, because an empty list allows every Telegram chat that can reach the bot.
                         </li>
                         <li>Click <strong>Connect Bot</strong>. Success is shown as a green <strong>Connected</strong> badge and the bot's username.</li>
                      </ol>
                   </div>

                   <div className="space-y-4">
                      <h5 className="text-sm font-bold text-shogun-text">Part C — Find and save your Chat ID safely</h5>
                      <ol className="text-xs text-shogun-subdued space-y-3 ml-5 list-decimal leading-relaxed">
                         <li>Return to Telegram and open the new bot using the link from BotFather or by searching for its username.</li>
                         <li>Press <strong>Start</strong> and send a simple message such as <code>Hello</code>. A bot cannot begin a private conversation until you contact it first.</li>
                         <li>Return to <strong>Katana → Telegram</strong> and click <strong>Auto-detect Chat ID</strong>. Your personal Chat ID should appear in both the test field and the Allowed Chat IDs field.</li>
                         <li>
                            <strong>Important:</strong> auto-detect fills the form but does not save the whitelist by itself. Paste the same bot token into <strong>Bot Token</strong> again,
                            confirm Polling is selected, and click <strong>Update Connection</strong>. This second save makes the whitelist permanent.
                         </li>
                         <li>Enter the detected ID under <strong>Test Connection</strong> and click <strong>Send Test</strong>. Telegram should receive “Shogun Test Message.”</li>
                         <li>Send <code>Hello Shogun</code> to the bot. A normal AI reply confirms that both incoming and outgoing communication work.</li>
                      </ol>
                   </div>

                   <div className="grid md:grid-cols-2 gap-4">
                      <div className="p-4 rounded-lg bg-shogun-bg border border-shogun-border space-y-3">
                         <h5 className="text-xs font-bold text-shogun-text">Optional: use the bot in a group</h5>
                         <ol className="text-[11px] text-shogun-subdued space-y-2 ml-4 list-decimal leading-relaxed">
                            <li>Add the bot to the Telegram group.</li>
                            <li>Send a command addressed to it, such as <code>/start@your_bot_name</code>, or reply directly to one of its messages.</li>
                            <li>Click <strong>Auto-detect Chat ID</strong> again. Group IDs are normally negative numbers.</li>
                            <li>Add that negative ID to Allowed Chat IDs, paste the token again, and click <strong>Update Connection</strong>.</li>
                         </ol>
                         <p className="text-[10px] text-shogun-subdued leading-relaxed">
                            Telegram Privacy Mode is enabled for group bots by default. The bot normally sees commands, direct mentions, and replies—not every group message.
                            This is the safer default. If an administrator disables Privacy Mode in BotFather, remove and re-add the bot to the group afterward.
                         </p>
                      </div>
                      <div className="p-4 rounded-lg bg-shogun-bg border border-shogun-border space-y-3">
                         <h5 className="text-xs font-bold text-shogun-text">Security checklist</h5>
                         <ul className="text-[11px] text-shogun-subdued space-y-2 ml-4 list-disc leading-relaxed">
                            <li>Keep at least one Allowed Chat ID saved.</li>
                            <li>Use a separate bot for testing and production.</li>
                            <li>Only run one Shogun instance with a given token; two pollers can compete for the same messages.</li>
                            <li>If the token is exposed, regenerate or revoke it in BotFather, then reconnect Shogun with the replacement.</li>
                            <li>Disconnect the bot in Katana when remote access is no longer needed.</li>
                         </ul>
                      </div>
                   </div>

                   <div className="space-y-3">
                      <h5 className="text-sm font-bold text-shogun-text">Telegram troubleshooting</h5>
                      <div className="overflow-x-auto rounded-lg border border-shogun-border">
                         <table className="w-full text-[11px]">
                            <thead><tr className="text-left bg-shogun-bg text-shogun-subdued"><th className="p-3">What you see</th><th className="p-3">What to do</th></tr></thead>
                            <tbody className="divide-y divide-shogun-border text-shogun-subdued">
                               <tr><td className="p-3 font-bold text-shogun-text">Invalid token or HTTP 401</td><td className="p-3">Copy the complete token from BotFather again. A revoked token automatically disconnects the listener.</td></tr>
                               <tr><td className="p-3 font-bold text-shogun-text">Auto-detect finds nothing</td><td className="p-3">Send a fresh message directly to the bot, wait a few seconds, then retry. Confirm no other application is consuming updates for the same token.</td></tr>
                               <tr><td className="p-3 font-bold text-shogun-text">Test works, but your messages are ignored</td><td className="p-3">Check that your exact Chat ID is in Allowed Chat IDs and that you completed the second Update Connection save.</td></tr>
                               <tr><td className="p-3 font-bold text-shogun-text">Group messages are ignored</td><td className="p-3">Mention the bot, use a command, or reply to it. Check the negative group ID and Telegram Privacy Mode.</td></tr>
                               <tr><td className="p-3 font-bold text-shogun-text">Replies stop when the computer sleeps</td><td className="p-3">Keep Shogun running on an awake, internet-connected computer or server. Polling is performed by Shogun itself.</td></tr>
                            </tbody>
                         </table>
                      </div>
                   </div>
                </div>
             </section>

             {/* YouTube Video Guides */}
             <section className="shogun-card bg-red-500/[0.04] border-red-500/20 border-l-4 border-l-red-500">
                <div className="flex flex-col md:flex-row md:items-center gap-4">
                   <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 shrink-0 w-fit">
                      <Play className="w-8 h-8 text-red-500" />
                   </div>
                   <div className="space-y-2 flex-1">
                      <h3 className="text-lg font-bold text-shogun-text flex items-center gap-2">
                         Complete Video Guide
                         <span className="text-[9px] font-bold text-red-400 bg-red-500/10 px-2 py-0.5 rounded-full uppercase tracking-widest">YouTube</span>
                      </h3>
                      <p className="text-xs text-shogun-subdued leading-relaxed">
                         Prefer video? Watch the full Shogun walkthrough series — from installation to advanced workflows, agent configuration, and security setup.
                      </p>
                      <a
                         href="https://www.youtube.com/@ShogunAIAgents"
                         target="_blank"
                         rel="noopener noreferrer"
                         className="inline-flex items-center gap-2 px-4 py-2 bg-red-500 hover:bg-red-600 text-white text-xs font-bold rounded-lg transition-all duration-200 shadow-lg hover:shadow-red-500/25 mt-1"
                      >
                         <Play className="w-3.5 h-3.5" />
                         Watch on YouTube
                         <ExternalLink className="w-3 h-3 opacity-60" />
                      </a>
                   </div>
                </div>
             </section>

             {/* Prerequisites */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-blue/40 pb-3">
                   <CheckCircle2 className="w-6 h-6 text-shogun-blue" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Prerequisites</h4>
                      <p className="text-xs text-shogun-subdued">What you need before you begin.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Key className="w-4 h-4 text-shogun-blue" /> At Least One API Key</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">For cloud inference, you need an API key from at least one AI provider — OpenAI, Anthropic, Google Gemini, or Perplexity. These are obtained from the provider&apos;s developer portal. Alternatively, connect a supported local model. Without a configured model, Shogun cannot perform model-backed tasks.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><HardDrive className="w-4 h-4 text-shogun-blue" /> Or a Local Model (Optional)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">If you prefer to run AI entirely on your own machine (no internet required), install <strong>Ollama</strong> and pull a model like <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">llama3</code>. Shogun will auto-detect it on the Katana → Local Models tab.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Globe className="w-4 h-4 text-shogun-blue" /> A Modern Browser</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Shogun's UI is designed for modern browsers — Chrome, Edge, Firefox, or Safari. Ensure JavaScript is enabled. The interface is fully responsive and works on tablets and phones as well.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Terminal className="w-4 h-4 text-shogun-blue" /> Shogun Backend Running</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The backend server must be running on <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">localhost:8000</code>. If you installed via Docker, it starts automatically. Otherwise, run <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">python -m shogun</code> from the project root.</p>
                   </div>
                </div>
             </section>

             {/* Step-by-Step First Launch */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-gold/40 pb-3">
                   <Compass className="w-6 h-6 text-shogun-gold" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">First Launch — Step by Step</h4>
                      <p className="text-xs text-shogun-subdued">Follow these steps in order for the smoothest setup experience.</p>
                   </div>
                </div>
                <div className="space-y-4">
                   {[
                     { step: 1, title: 'Add Your First AI Provider', color: 'text-shogun-blue', icon: Key, desc: 'Navigate to Katana → Cloud Providers. Click "Add Provider." Choose the provider type (e.g., OpenAI), paste your API key, and save. Within seconds, all available models from that provider will appear as options throughout Shogun.' },
                     { step: 2, title: 'Choose a Routing Profile', color: 'text-shogun-blue', icon: Cpu, desc: 'Go to Katana → Model Routing. Choose a routing profile, or use Custom to select an ordered primary and fallback model list from your connected providers.' },
                     { step: 3, title: 'Review Your Security Posture', color: 'text-red-400', icon: Lock, desc: 'Visit Torii (Security). The default posture is TACTICAL — a balanced setting that gives the AI enough freedom for productive work while keeping dangerous operations locked down. Read the tier descriptions and choose the level that matches your risk comfort.' },
                     { step: 4, title: 'Write Your Constitution (Optional)', color: 'text-shogun-gold', icon: FileText, desc: 'Open Kaizen → Constitution tab. This is the AI\'s "rule book." The default constitution covers essential safety rules. You can add your own rules here — for example, "Never send emails without my approval" or "Always respond in formal English." Click "Publish Edicts" when done.' },
                     { step: 5, title: 'Deploy Your First Samurai (Optional)', color: 'text-shogun-gold', icon: Users, desc: 'Head to Samurai Network. Click "Deploy Samurai," choose a role (e.g., Researcher, Analyst), give it a name, and deploy. Your first sub-agent is now ready to receive delegated tasks from the main Shogun.' },
                     { step: 6, title: 'Start a Conversation', color: 'text-green-500', icon: MessageSquare, desc: 'Click "Enter Command" on the dashboard (or navigate to Comms). Type your first message. The Shogun will respond using the primary model you selected. Congratulations — you are operational!' },
                   ].map((item) => (
                     <div key={item.step} className="shogun-card flex gap-5 items-start">
                        <div className="flex flex-col items-center gap-2 shrink-0">
                           <div className={`w-10 h-10 rounded-xl bg-shogun-bg border border-shogun-border flex items-center justify-center font-bold text-lg ${item.color}`}>
                              {item.step}
                           </div>
                        </div>
                        <div className="space-y-1 min-w-0">
                           <div className={`font-bold text-shogun-text flex items-center gap-2`}>
                              <item.icon className={`w-4 h-4 ${item.color}`} />
                              {item.title}
                           </div>
                           <p className="text-xs text-shogun-subdued leading-relaxed">{item.desc}</p>
                        </div>
                     </div>
                   ))}
                </div>
             </section>

             {/* Core Concepts Glossary */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-blue/40 pb-3">
                   <BookOpen className="w-6 h-6 text-shogun-blue" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Core Concepts</h4>
                      <p className="text-xs text-shogun-subdued">Key terms you'll encounter throughout the platform.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                   {[
                     { term: 'Shogun', def: 'The main AI agent — your primary assistant. It coordinates everything, delegates to Samurai, and answers your questions directly.', icon: Cpu, color: 'text-shogun-gold' },
                     { term: 'Samurai', def: 'Specialized sub-agents that handle specific tasks. Think of them as employees — each one has a role, a name, and a current assignment.', icon: Users, color: 'text-shogun-gold' },
                     { term: 'Lattice', def: 'The network of all connected agents (Shogun + Samurai). The lattice distributes work intelligently and ensures no single agent is overwhelmed.', icon: Network, color: 'text-shogun-blue' },
                     { term: 'Constitution', def: 'A set of inviolable rules written in YAML that govern what all agents are allowed to do. Managed in the Kaizen page.', icon: FileText, color: 'text-shogun-gold' },
                     { term: 'Security Posture', def: 'The built-in tier or custom policy selected in Torii. ToolGate turns that selection into capability boundaries and runtime ALLOW, CONFIRM, or BLOCK decisions.', icon: Lock, color: 'text-red-400' },
                     { term: 'Harakiri', def: 'The emergency kill switch. Requests cancellation of supported active agent work and locks the system to the most restrictive built-in posture (SHRINE).', icon: ShieldCheck, color: 'text-red-400' },
                     { term: 'Routing Profile', def: 'A set of rules that decides which AI model handles which type of task. For example: code → GPT-4, research → Perplexity.', icon: GitBranch, color: 'text-shogun-blue' },
                     { term: 'Salience', def: 'A memory importance score (0.0–1.0). High-salience memories are retrieved first. The system auto-adjusts salience over time.', icon: Star, color: 'text-shogun-gold' },
                     { term: 'Reflection Cycle', def: 'An automated self-improvement loop where the AI analyzes its own performance and generates optimization insights. Run from Bushido.', icon: RefreshCw, color: 'text-shogun-blue' },
                     { term: 'Ronin (Desktop)', def: 'The desktop control capability. Allows agents to interact with OS desktops — mouse, keyboard, screenshots, and native apps. Torii selects its policy; ToolGate governs its capability boundary and runtime decisions alongside Posture Guard, App Trust, and Komainu.', icon: Crosshair, color: 'text-orange-400' },
                     { term: 'Komainu (Guardian)', def: 'The physical override system for Ronin. A three-tier safety mechanism: Level 1 (Pause), Level 2 (Terminate), Level 3 (Harakiri). Detects human mouse/keyboard input and stops the AI. Named after Japanese shrine guardians.', icon: ShieldAlert, color: 'text-red-400' },
                   ].map((item) => (
                     <div key={item.term} className="shogun-card space-y-2">
                        <div className={`font-bold text-shogun-text flex items-center gap-2`}>
                           <item.icon className={`w-4 h-4 ${item.color}`} />
                           {item.term}
                        </div>
                        <p className="text-xs text-shogun-subdued leading-relaxed">{item.def}</p>
                     </div>
                   ))}
                </div>
             </section>

             {/* Navigation Map */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-gold/40 pb-3">
                   <Layout className="w-6 h-6 text-shogun-gold" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Navigation Map</h4>
                      <p className="text-xs text-shogun-subdued">Every page in Shogun at a glance — what it does and when to use it.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   {[
                     { name: 'Tenshu (Dashboard)', purpose: 'Your home screen. See stat cards, active agents, recent events, quick actions, and the Harakiri button. The first thing you see when you open Shogun.', icon: Layout, color: 'text-shogun-blue' },
                     { name: 'Shogun Profile', purpose: 'Configure your AI\'s identity, personality, behavioral directives, and scheduled jobs. Model selection lives in Katana; security configuration lives in Torii and ToolGate.', icon: Cpu, color: 'text-shogun-gold' },
                     { name: 'Samurai Network', purpose: 'Deploy and manage permanent specialized sub-agents. Give each Samurai a role, routing profile, spawn policy, and selected skills from the Shogun\'s validated active skillset.', icon: Users, color: 'text-shogun-gold' },
                     { name: 'Agent Flow', purpose: 'Build reusable multi-step workflows from the Samurai page. Connect governed nodes, execute them, inspect failures, and collect artifacts.', icon: Workflow, color: 'text-violet-400' },
                     { name: 'Comms', purpose: 'The communication hub with five tabs in this order: Chat, Mail, Calendar, Files, and Supermode Canvas.', icon: MessageSquare, color: 'text-shogun-blue' },
                     { name: 'Mail (Email Client)', purpose: 'Browse IMAP mail, read and compose messages, and manage folders. Shogun can use the same account through governed native tools.', icon: Mail, color: 'text-sky-400' },
                     { name: 'Calendar', purpose: 'View and create CalDAV events with times, locations, and descriptions. Shogun can query and create events through governed native tools.', icon: CalendarDays, color: 'text-emerald-400' },
                     { name: 'Supermode Canvas', purpose: 'Run durable multi-agent missions. The Shogun plans workstreams, routes Fleet Samurai or spawned specialists, chooses task-level routing logic, checkpoints work, requests approvals, and records learning and artifacts.', icon: Target, color: 'text-violet-400' },
                     { name: 'Katana (System Forge)', purpose: 'Install and connect AI providers, models, tools, file formats, channels, and account-specific scopes. Configure model routing and eligibility here; ToolGate governs whether capabilities may execute.', icon: Sword, color: 'text-shogun-blue' },
                     { name: 'Mado (Browser)', purpose: 'Browser automation powered by Playwright, governed by the active posture and ToolGate browser and network boundaries.', icon: AppWindow, color: 'text-cyan-400' },
                     { name: 'Ronin (Desktop Control)', purpose: 'Optional governed mouse, keyboard, screenshot, and native-app control. It requires the Ronin posture and separate operator enablement.', icon: Crosshair, color: 'text-orange-400' },
                     { name: 'Torii (Security)', purpose: 'Select the active built-in tier or custom posture and access Harakiri. Custom posture creation and detailed editing belong to ToolGate.', icon: Lock, color: 'text-red-400' },
                     { name: 'ToolGate (Runtime Permissions)', purpose: 'Edit runtime security, create custom postures, configure capability boundaries, and inspect effective ALLOW, CONFIRM, or BLOCK decisions.', icon: Shield, color: 'text-orange-400' },
                     { name: 'Kaizen (Governance)', purpose: 'Write the Constitution and Mandate, validate changes, and maintain revision history for the laws and objectives governing every agent.', icon: ShieldCheck, color: 'text-shogun-gold' },
                     { name: 'Bushido (Reflection)', purpose: 'Calibrate self-improvement behavior, tune reflection and consolidation, and review generated insights.', icon: RefreshCw, color: 'text-shogun-blue' },
                     { name: 'Archives (Memory)', purpose: 'Search, browse, create, connect, and manage durable memory with semantic retrieval, provenance, salience, and memory-type filtering.', icon: Database, color: 'text-shogun-gold' },
                     { name: 'Dojo (Training Hall)', purpose: 'Browse skills, study training material, take certification exams, and track validated achievements that may participate in governed runtime skill activation.', icon: Flame, color: 'text-shogun-gold' },
                     { name: 'Backups', purpose: 'Schedule backups, manage retention, export or import data, create Complete Backups, and perform safe restore or PC migration workflows.', icon: HardDrive, color: 'text-shogun-gold' },
                     { name: 'Privacy & Telemetry', purpose: 'Review optional statistics, preview exactly what may be sent, give or withdraw consent, and delete the pseudonymous installation record.', icon: ShieldCheck, color: 'text-violet-400' },
                     { name: 'Updates', purpose: 'Check the current build against the release manifest and install an available update while preserving application data and configuration.', icon: Download, color: 'text-emerald-400' },
                     { name: 'About', purpose: 'See the installed version, build, system information, project references, and licence information.', icon: Info, color: 'text-cyan-400' },
                     { name: 'Guide (Documentation)', purpose: 'Open onboarding, concepts, the Grand Manual, architecture, and safety material; print or save the complete manual for offline use.', icon: HelpCircle, color: 'text-shogun-subdued' },
                   ].map((item) => (
                     <div key={item.name} className="shogun-card flex gap-4 items-start">
                        <div className={`p-2 rounded-lg bg-shogun-bg border border-shogun-border shrink-0`}>
                           <item.icon className={`w-5 h-5 ${item.color}`} />
                        </div>
                        <div className="space-y-1 min-w-0">
                           <div className="font-bold text-shogun-text text-sm">{item.name}</div>
                           <p className="text-xs text-shogun-subdued leading-relaxed">{item.purpose}</p>
                        </div>
                     </div>
                   ))}
                </div>
             </section>

             {/* Tips & Best Practices */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-green-500/40 pb-3">
                   <Sparkles className="w-6 h-6 text-green-500" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Tips & Best Practices</h4>
                      <p className="text-xs text-shogun-subdued">Recommendations from experienced operators.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2 border-l-2 border-green-500/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-green-500" /> Start with TACTICAL Posture</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The default "TACTICAL" security tier is recommended for most users. It gives the AI enough autonomy to be useful while keeping dangerous operations (like shell access and auto-spawning) locked down. Only move to CAMPAIGN or RONIN when you fully understand the risks.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-green-500/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Database className="w-4 h-4 text-green-500" /> Add Fallback Models</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Don't rely on a single AI provider. In Katana → Model Routing, edit Custom routing and add at least one fallback model from a different provider. If the primary goes down, the router tries the next eligible model.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-green-500/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Star className="w-4 h-4 text-green-500" /> Pin Important Memories</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">If there's a fact the AI must never forget — a company policy, a key contact, a critical instruction — create it as a memory in Archives and pin it. Pinned memories always have maximum salience and are always loaded into context.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-green-500/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Download className="w-4 h-4 text-green-500" /> Enable Automatic Backups</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Your Shogun accumulates valuable knowledge over time. Go to <strong>Backups</strong> in the sidebar → enable automatic backups on a schedule. You can also manually export a "Safe JSON Bundle" from the Data Management tab. This protects you from data loss due to hardware failure.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-green-500/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-green-500" /> Write a Clear Mandate</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The Mandate (Kaizen → Mandate tab) is injected into every conversation. Use it to set the AI's overall purpose, tone, and special instructions. For example: "You are a senior financial analyst. Always cite sources. Respond in English."</p>
                   </div>
                </div>
             </section>

          </div>
        )}

        {/* Reference Manual (Comprehensive Function List) */}
        {activeTab === 'reference' && (
          <div className="flex gap-8 animate-in slide-in-from-bottom-4">
            {/* Sticky Sidebar Navigation */}
            <nav className="hidden lg:block w-56 shrink-0">
              <div className="sticky top-6 space-y-1 p-3 bg-shogun-card border border-shogun-border rounded-xl max-h-[calc(100vh-120px)] overflow-y-auto">
                <div className="flex items-center gap-2 px-2 pb-2 mb-2 border-b border-shogun-border">
                  <List className="w-4 h-4 text-shogun-blue" />
                  <span className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Sections</span>
                </div>
                {REFERENCE_SECTIONS.map((sec) => (
                  <button
                    key={sec.id}
                    onClick={() => scrollToSection(sec.id)}
                    className={cn(
                      "w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[11px] font-medium transition-all duration-200 text-left",
                      activeSection === sec.id
                        ? "bg-shogun-blue/10 text-shogun-blue border border-shogun-blue/20 shadow-sm"
                        : "text-shogun-subdued hover:text-shogun-text hover:bg-shogun-bg border border-transparent"
                    )}
                  >
                    <sec.icon className={cn("w-3.5 h-3.5 shrink-0", activeSection === sec.id ? 'text-shogun-blue' : sec.color)} />
                    {sec.label}
                  </button>
                ))}
              </div>
            </nav>
            {/* Main Content */}
            <div className="flex-1 min-w-0 space-y-16" ref={refContentRef}>
             {/* Introduction */}
             <div className="text-center max-w-3xl mx-auto space-y-4">
                <div className="flex flex-wrap items-center justify-center gap-3">
                  <h3 className="text-3xl font-bold shogun-title">The Grand Reference</h3>
                  <button
                    type="button"
                    onClick={printGrandReference}
                    className="print-hide inline-flex items-center gap-2 rounded-lg border border-shogun-blue/30 bg-shogun-blue/10 px-3 py-2 text-xs font-bold text-shogun-blue transition-colors hover:bg-shogun-blue/20"
                  >
                    <Printer className="h-4 w-4" />
                    Print Guide
                  </button>
                </div>
                <p className="text-shogun-subdued leading-relaxed">A deep-dive, page-by-page, tab-by-tab, button-by-button manual of every single capability within the Shogun platform. Written in plain language so anyone can understand it — no technical jargon required.</p>
             </div>

             {/* ═══════════════════════════════════════════════════════════════ */}
             {/* 1. TENSHU (DASHBOARD) */}
             {/* ═══════════════════════════════════════════════════════════════ */}
             <section id="ref-tenshu" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-blue/40 pb-3">
                   <Layout className="w-6 h-6 text-shogun-blue" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Tenshu — The Command Center</h4>
                      <p className="text-xs text-shogun-subdued">Your home screen. The first thing you see when you open Shogun.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-shogun-blue" /> Stat Cards (Top Row)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Four large cards at the top of the page. Each one is a "quick look" at a different part of the system. They are clickable — clicking one takes you to the related page.</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Neural Engine:</strong> Shows the name of your primary AI and whether it is currently running. Click to go to the Shogun Profile page.</li>
                         <li><strong>Active Lattice:</strong> How many sub-agents (Samurai) are currently deployed. Click to go to the Samurai Network page.</li>
                         <li><strong>Knowledge Volume:</strong> The total number of memories stored in the Archives. Also indicates whether the search index is healthy or has errors.</li>
                         <li><strong>Security Tier:</strong> Shows your current protection level (e.g., "GUARDED" or "TACTICAL"). Click to go to Torii.</li>
                      </ul>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Users className="w-4 h-4 text-shogun-blue" /> Active Deployment Registry</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">A table below the stat cards that lists every Samurai (sub-agent) currently running. For each one you can see:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Designation:</strong> The agent's name and its first-letter icon.</li>
                         <li><strong>Current Task:</strong> What the agent is working on right now.</li>
                         <li><strong>Engagement Bar:</strong> A progress bar showing how busy it is.</li>
                         <li><strong>Status:</strong> A green "active" or blue "suspended" badge.</li>
                      </ul>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Zap className="w-4 h-4 text-shogun-blue" /> Quick Actions Panel</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Two large shortcut buttons below the deployment registry:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>New Samurai:</strong> Opens the Samurai Network page to deploy a new sub-agent.</li>
                         <li><strong>Model Setup:</strong> Opens the Katana page to configure AI models.</li>
                      </ul>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-red-400" /> Emergency Stop (Harakiri)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">A red button on the dashboard. Pressing it opens a two-step confirmation modal. Once confirmed, the kill switch blocks new governed operations and requests cancellation of supported active Telegram, Agent Flow, approval, and Ronin work. Cancellation is best-effort; verify external processes and side effects separately. The security posture locks to "SHRINE" (maximum protection). A pulsing red banner appears until you press "Reset Harakiri".</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-shogun-gold" /> Telemetry Feed (Right Sidebar)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">A timeline of recent system events displayed on the right side. Each event has a colored icon (red for security, gold for agent, blue for system) and a timestamp. At the bottom, a "System Load" bar shows current CPU usage.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><MessageSquare className="w-4 h-4 text-shogun-blue" /> "Enter Command" Button</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The blue button in the top right. Clicking it takes you straight to the Comms (Chat) page where you can start talking to your Shogun.</p>
                   </div>
                </div>
             </section>

             {/* ═══════════════════════════════════════════════════════════════ */}
             {/* SHOGUN SERVER MODE (DOCKER) */}
             <section id="ref-server" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-emerald-400/40 pb-3">
                   <Package className="w-6 h-6 text-emerald-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Shogun Server Mode — Container Installation</h4>
                      <p className="text-xs text-shogun-subdued">Run Shogun and The Tenshu continuously with Docker, PostgreSQL, and Qdrant.</p>
                   </div>
                </div>

                <div className="shogun-card border-l-4 border-l-red-500 space-y-3">
                   <div className="font-bold text-red-400 flex items-center gap-2"><AlertCircle className="w-4 h-4" /> Ronin Does Not Work in Server Mode</div>
                   <p className="text-xs text-shogun-subdued leading-relaxed">
                      A container cannot safely access the server's physical desktop. Ronin screenshots, mouse and keyboard control,
                      native application control, and host-desktop sessions are disabled and rejected by the server. Selecting the Torii
                      posture named <strong>RONIN</strong> does not override this container boundary. Install Shogun directly on a desktop
                      computer when Ronin Desktop Control is required.
                   </p>
                   <p className="text-xs text-shogun-subdued leading-relaxed">
                      <strong className="text-emerald-400">Still available:</strong> Mado browser automation runs Chromium inside the
                      container. Agent Flows, Telegram, memory, ToolGate, HARAKIRI, and external
                      local-model servers such as Ollama continue to work.
                   </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-3">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Download className="w-4 h-4 text-emerald-400" /> Before You Install</div>
                      <ul className="text-xs text-shogun-subdued space-y-1.5 ml-4 list-disc leading-relaxed">
                         <li><strong>Windows or macOS:</strong> Install Docker Desktop and start it.</li>
                         <li><strong>Linux:</strong> Install Docker Engine and the Docker Compose plugin.</li>
                         <li>Allow outbound internet access while the image and service images are downloaded.</li>
                         <li>Plan remote administration through a VPN, SSH tunnel, or authenticated HTTPS reverse proxy.</li>
                      </ul>
                   </div>
                   <div className="shogun-card space-y-3">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Play className="w-4 h-4 text-emerald-400" /> One-Click Installation</div>
                      <ol className="text-xs text-shogun-subdued space-y-1.5 ml-4 list-decimal leading-relaxed">
                         <li>Open the latest Shogun GitHub Release.</li>
                         <li>Download <code>Shogun-Server-Install.bat</code> on Windows, or <code>Shogun-Server-Install.sh</code> on Linux/macOS.</li>
                         <li>Run the installer. It generates secrets, builds the image, and starts all services.</li>
                         <li>Open <code>http://127.0.0.1:8000/setup</code> and complete the Setup Wizard as the Primary Admin.</li>
                      </ol>
                      <a href="https://github.com/AlphaHorizon-AI/Shogun/releases/latest" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-400 hover:underline">
                         <ExternalLink className="w-3 h-3" /> Open the latest Shogun Release
                      </a>
                   </div>
                   <div className="shogun-card space-y-3">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Network className="w-4 h-4 text-emerald-400" /> What the Stack Runs</div>
                      <ul className="text-xs text-shogun-subdued space-y-1.5 ml-4 list-disc leading-relaxed">
                         <li><strong>Shogun + The Tenshu:</strong> A non-root application container exposed on port 8000.</li>
                         <li><strong>PostgreSQL:</strong> Structured application, configuration, and audit data.</li>
                         <li><strong>Qdrant:</strong> Vector memory and semantic retrieval.</li>
                         <li><strong>Internal network:</strong> PostgreSQL and Qdrant are not published to the host.</li>
                         <li><strong>Health and restart controls:</strong> Failed services are detected and restarted automatically.</li>
                      </ul>
                   </div>
                   <div className="shogun-card space-y-3">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Database className="w-4 h-4 text-emerald-400" /> Persistence and Upgrades</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Named Docker volumes preserve application data, memories, vault content, configuration, logs, PostgreSQL, and Qdrant. The installer also preserves <code>.env.server</code> when updating the source.</p>
                      <p className="text-xs text-red-400 leading-relaxed"><strong>Never use</strong> <code>docker compose down -v</code> unless you intentionally want to delete all Server-mode data.</p>
                   </div>
                   <div className="shogun-card space-y-3">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Lock className="w-4 h-4 text-emerald-400" /> Network Security</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The Tenshu binds to <code>127.0.0.1</code> by default and is therefore reachable only from the server itself. Do not expose it on a public or shared network without an authenticated HTTPS reverse proxy. A VPN or SSH tunnel is the preferred way to administer it remotely.</p>
                   </div>
                </div>

                <div className="shogun-card space-y-3">
                   <div className="font-bold text-shogun-text flex items-center gap-2"><Terminal className="w-4 h-4 text-emerald-400" /> Essential Server Commands</div>
                   <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <div className="bg-shogun-bg rounded-lg border border-shogun-border p-3"><p className="text-[10px] font-bold uppercase tracking-widest text-shogun-subdued mb-2">Status</p><code className="text-[10px] text-emerald-400 break-all">docker compose --env-file .env.server -f docker-compose.server.yml ps</code></div>
                      <div className="bg-shogun-bg rounded-lg border border-shogun-border p-3"><p className="text-[10px] font-bold uppercase tracking-widest text-shogun-subdued mb-2">Live Logs</p><code className="text-[10px] text-emerald-400 break-all">docker compose --env-file .env.server -f docker-compose.server.yml logs -f shogun</code></div>
                      <div className="bg-shogun-bg rounded-lg border border-shogun-border p-3"><p className="text-[10px] font-bold uppercase tracking-widest text-shogun-subdued mb-2">Safe Stop</p><code className="text-[10px] text-emerald-400 break-all">docker compose --env-file .env.server -f docker-compose.server.yml down</code></div>
                   </div>
                </div>
             </section>

             {/* ═══════════════════════════════════════════════════════════════ */}
             {/* 3. SHOGUN PROFILE */}
             {/* ═══════════════════════════════════════════════════════════════ */}
             <section id="ref-profile" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-gold/40 pb-3">
                   <Cpu className="w-6 h-6 text-shogun-gold" />
                   <div>
                       <h4 className="text-xl font-bold uppercase tracking-widest">Shogun Profile — Agent Identity &amp; Behaviour</h4>
                       <p className="text-xs text-shogun-subdued">Configure the orchestration persona, behaviour, and scheduled operations of your main Shogun agent. These settings do not alter the selected model&apos;s training or intrinsic behaviour. Has 3 tabs; security configuration is owned by ToolGate.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Cpu className="w-4 h-4 text-shogun-gold" /> General Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Set the Shogun's name, choose an active "Persona" (a pre-built personality template), and write a description. On the right side, adjust the <strong>Autonomy Level</strong> slider (how much freedom the AI gets), <strong>Tone</strong> (e.g., Analytical, Direct), <strong>Risk Tolerance</strong>, <strong>Verbosity</strong> (how detailed responses are), <strong>Planning Depth</strong>, <strong>Tool Usage</strong>, <strong>Security Bias</strong>, and <strong>Memory Style</strong>. Click the avatar image to upload a custom picture.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Database className="w-4 h-4 text-shogun-gold" /> Model Selection</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Model selection is configured centrally in <strong>Katana → Model Routing</strong>, where providers, routing profiles, capability requirements, primary models, and fallback order share one source of truth.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-shogun-gold" /> Behavior Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">A full-screen YAML text editor showing the Shogun's core behavioral directives — its priorities, operational constraints, and delegation rules. Think of this as the AI's "rule book." You can edit it directly, and the badge in the top-right confirms it is in "YAML Mode."</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Shield className="w-4 h-4 text-orange-400" /> Security Summary</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The General tab shows the active policy, inherited base tier, and capability risk as a compact summary. Use <strong>Open ToolGate</strong> to inspect or change security behavior. The former Permissions tab now redirects to ToolGate so there is only one runtime-permission control surface.</p>
                   </div>
                   <div className="shogun-card space-y-2 md:col-span-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><RefreshCw className="w-4 h-4 text-shogun-gold" /> Operations Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">View and manage scheduled background jobs. Preset jobs include <strong>Memory Consolidation</strong> (summarizes and compresses old memories), <strong>Knowledge Refresh</strong> (updates outdated knowledge), and <strong>Security Audit</strong>. Each can be enabled/disabled with a toggle. Below the presets, you can <strong>create custom jobs</strong> with a name, schedule (nightly, weekly, monthly, or one-time), priority, and instructions.</p>
                   </div>
                </div>
             </section>

             {/* ═══════════════════════════════════════════════════════════════ */}
             {/* 4. SAMURAI NETWORK */}
             {/* ═══════════════════════════════════════════════════════════════ */}
             <section id="ref-samurai" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-gold/40 pb-3">
                   <Users className="w-6 h-6 text-shogun-gold" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Samurai Network — The Fleet</h4>
                      <p className="text-xs text-shogun-subdued">Deploy, manage, and monitor specialized sub-agents.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Users className="w-4 h-4 text-shogun-gold" /> Fleet Stats (Top)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Four stat cards: <strong>Total Fleet</strong> (all agents), <strong>Active</strong> (currently working), <strong>Suspended</strong> (paused), and <strong>Signal Range</strong> (network reach).</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Search className="w-4 h-4 text-shogun-gold" /> Agent Table & Search</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">A large table listing every Samurai. Use the search bar to filter by name. Each row shows: the agent's <strong>name and role badge</strong>, <strong>status</strong> (green dot = active), <strong>current task</strong> (with a live progress bar if running), <strong>role/slug</strong>, <strong>routing profile</strong>, and <strong>deployment date</strong>. Hover over a row to reveal action buttons.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Zap className="w-4 h-4 text-shogun-gold" /> Row Action Buttons</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Three buttons appear when you hover over a Samurai row:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Pause/Play:</strong> Suspend a running agent or resume a suspended one.</li>
                         <li><strong>Trash:</strong> Permanently delete the agent (asks for confirmation first).</li>
                         <li><strong>Configure (⋮):</strong> Opens a modal where you can change the agent's name, role, routing profile, spawn policy, and description.</li>
                      </ul>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Package className="w-4 h-4 text-shogun-blue" /> "Deploy Samurai" Button</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The blue button in the top right. Opens a form where you choose a <strong>Role</strong> from the pre-defined Samurai roles list, give it a <strong>custom name</strong>, choose a <strong>Spawn Policy</strong> (Manual, Auto, or Scheduled), optionally assign a <strong>Routing Profile</strong>, and write a description. Click "Deploy Samurai" to create it.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Sparkles className="w-4 h-4 text-cyan-400" /> Assign Shogun Skills</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Open a Samurai&apos;s <strong>Configure</strong> panel and use the <strong>Shogun skills</strong> selector to search the Shogun&apos;s validated active skillset. Select only the skills that should form this Samurai&apos;s specialist signature. The selected skills are shown on the fleet row and are considered when Supermode decides who should receive a workstream.</p>
                      <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Important:</strong> a skill supplies governed instructions and expertise. It does not grant a tool, widen filesystem or network access, or bypass Torii, ToolGate, exam, or approval requirements.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><RouteIcon className="w-4 h-4 text-emerald-400" /> How Supermode Uses the Fleet</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">For each planned mission role, the Shogun first looks for a suitable active permanent Fleet Samurai. It compares the workstream with the Samurai&apos;s role, description, assigned skills, routing profile, and current availability. A strong match is reserved for the mission and keeps its Fleet identity and operator-selected skills. If no suitable Samurai is available, the Shogun creates a temporary mission-scoped specialist instead. The Inspector records which path was used and why.</p>
                   </div>
                </div>

                {/* Agent Flow sub-section */}
                <div className="mt-8 space-y-4">
                   <div className="text-xs font-bold text-shogun-subdued uppercase tracking-widest pl-1 border-l-2 border-shogun-gold/40 ml-1">Samurai Orchestration</div>
                   <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="shogun-card space-y-2 border-l-2 border-violet-400/40">
                         <div className="font-bold text-shogun-text flex items-center gap-2"><Workflow className="w-4 h-4 text-violet-400" /> Agent Flow — Workflow Builder</div>
                         <p className="text-xs text-shogun-subdued leading-relaxed">A visual drag-and-drop canvas for designing multi-step AI pipelines. Build workflows by chaining 15 node types, including governed native reads and the memory-aware Coding node:</p>
                         <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                            <li><strong>Input:</strong> The entry point — accepts user text, data, or triggers.</li>
                            <li><strong>Samurai:</strong> Delegates a task to a specific sub-agent.</li>
                            <li><strong>Shogun Approval:</strong> Pauses the flow for human confirmation.</li>
                            <li><strong>Logic:</strong> A conditional gate — routes based on a condition.</li>
                            <li><strong>Mado Browser:</strong> Automates a web browsing action.</li>
                            <li><strong>Email Read / Calendar Read:</strong> Fetches governed, structured inbox summaries or calendar events for successor nodes.</li>
                            <li><strong>Email Send / Telegram:</strong> Delivers results through configured channels.</li>
                            <li><strong>Workspace / Office:</strong> Performs governed file operations or works with Office documents.</li>
                            <li><strong>Subflow:</strong> Runs a reusable child Agent Flow.</li>
                            <li><strong>Output:</strong> Collects and presents the final result, with optional memory infusion.</li>
                         </ul>
                         <p className="text-xs text-shogun-subdued leading-relaxed mt-2"><strong>Samurai governed reads:</strong> Samurai nodes can request fetch_inbox and list_calendar_events directly. The flow runtime executes those read-only tools under the active security posture and ToolGate policy, then hands the structured results to the Samurai for compilation. Dedicated Email Read and Calendar Read nodes remain available when you prefer an explicit multi-node pipeline.</p>
                      </div>
                      <div className="shogun-card space-y-2 border-l-2 border-violet-400/40">
                         <div className="font-bold text-shogun-text flex items-center gap-2"><GitBranch className="w-4 h-4 text-violet-400" /> Canvas, Execution & AI Creation</div>
                         <p className="text-xs text-shogun-subdued leading-relaxed">Position nodes freely on the visual canvas and draw directed edges between them. Edges define execution order — data flows from source to target. The canvas supports pan, zoom, and node reordering. Workflows are saved to the database.</p>
                         <p className="text-xs text-shogun-subdued leading-relaxed mt-2">Click <strong>Execute</strong> to run a workflow. Nodes process in topological order, passing outputs as inputs to the next. Shogun Approval nodes pause until you confirm.</p>
                         <p className="text-xs text-shogun-subdued leading-relaxed mt-2">Shogun can manage workflows natively: <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">list_agent_flows</code> discovers flows and stacks, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">get_agent_flow</code> reads a complete graph, and <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">patch_agent_flow</code> safely changes selected nodes or edges. It can also create, replace, and delete flows. The agent is instructed to inspect a flow before editing it.</p>
                      </div>
                      <div className="shogun-card space-y-2 border-l-2 border-violet-400/40">
                         <div className="font-bold text-shogun-text flex items-center gap-2"><Package className="w-4 h-4 text-violet-400" /> Template Gallery</div>
                         <p className="text-xs text-shogun-subdued leading-relaxed">Click <strong>New Flow</strong> to browse 173 pre-built workflow templates across 11 different categories, including 33 distinct Coding templates. Templates range in difficulty from <strong>Beginner</strong> to <strong>Advanced</strong>.</p>
                         <p className="text-xs text-shogun-subdued leading-relaxed mt-2">When you select a template, the canvas is automatically populated. Samurai nodes inside templates use <strong>Ephemeral (Ad-Hoc)</strong> agents by default to keep your Fleet clean, but can be manually linked to a permanent Fleet Samurai via the node properties panel.</p>
                      </div>
                      <div className="shogun-card space-y-2 border-l-2 border-orange-400/40 md:col-span-2">
                         <div className="font-bold text-shogun-text flex items-center gap-2"><Database className="w-4 h-4 text-orange-400" /> Output Memory Infusion</div>
                         <p className="text-xs text-shogun-subdued leading-relaxed">An Output node can opt into <strong>Memory Infusion</strong>. When its configured completion state is reached, the flow engine—not the model—stores selected output fields in Archives. Configure the memory type, importance, decay, tags, title template, content fields, maximum length, sensitive-data redaction, and behavior when fields are missing.</p>
                         <p className="text-xs text-shogun-subdued leading-relaxed">Storage can run on success, partial completion, or always. Exact-hash or semantic deduplication prevents repeated memories and reinforces an existing match. Every stored, skipped, or deduplicated result carries flow/run/node provenance and an audit event. Memory Infusion is disabled by default and must be enabled per Output node.</p>
                      </div>
                   </div>
                   <div className="shogun-card space-y-2 mt-4">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Search className="w-4 h-4 text-violet-400" /> Agent Inspection &amp; Editing</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">For a standard Agent Flow, Shogun uses <code className="text-violet-400">get_agent_flow</code> and prefers <code className="text-violet-400">patch_agent_flow</code> for targeted graph changes that preserve untouched nodes and edges. A direct operator instruction to edit a flow authorizes that targeted patch for the current turn; Shogun still has to inspect first, remain at Tactical posture or above, and obey the separate create, activate, execute, template, and delete permissions.</p>
                   </div>
                </div>
             </section>

             {/* 2. COMMS (CHAT) */}
             {/* ═══════════════════════════════════════════════════════════════ */}
             <section id="ref-comms" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-blue/40 pb-3">
                   <MessageSquare className="w-6 h-6 text-shogun-blue" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Comms — The Conversation</h4>
                      <p className="text-xs text-shogun-subdued">Your direct line to the Shogun AI. Five tabs in interface order: Chat, Mail, Calendar, Files, and Supermode Canvas.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><MessageSquare className="w-4 h-4 text-shogun-blue" /> Chat Window</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The main area showing your conversation. Your messages appear on the right (blue icon), and the Shogun's replies appear on the left (gold icon). While the AI is thinking, three bouncing dots are shown. Responses stream in token by token so you can watch the answer being written in real time.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Globe className="w-4 h-4 text-shogun-blue" /> Model & Search Tags</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Below each Shogun reply you will see a small tag. If the reply used a <strong>Web Search</strong> (via Perplexity), a blue "Web Search" badge appears. Otherwise, the name of the AI model used is shown (e.g., "gpt-4o").</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Search className="w-4 h-4 text-shogun-gold" /> Input Bar & Sending</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Type your message at the bottom and press <strong>Enter</strong> (or click the blue send arrow) to send. While the AI is responding, the input field is locked and shows "Transmitting directive..." to prevent double-sending.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Compass className="w-4 h-4 text-shogun-gold" /> Session History</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Below the input bar, click <strong>"View History"</strong> to open a right-hand drawer showing all your previous chat sessions. Each session shows a preview of the first message and the number of messages. Click <strong>"Restore"</strong> to reload an old conversation. Click <strong>"Clear All History"</strong> at the bottom to permanently erase all archived sessions.</p>
                   </div>
                   <div className="shogun-card space-y-2 md:col-span-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-red-400" /> Clear Button (Trash Icon)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The trash icon in the top right <strong>archives</strong> the current session to history and starts a fresh conversation. Your old messages are not lost — they are kept in the History drawer and can be restored at any time.</p>
                   </div>
                </div>

                {/* Mail & Calendar */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                   <div className="shogun-card space-y-2 border-l-2 border-sky-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Mail className="w-4 h-4 text-sky-400" /> Mail — Email Client</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">A full IMAP/SMTP email client built into Comms. Browse your inbox with sender, subject, date, and preview. Click any message to read the full content. <strong>Compose</strong> new emails with To, CC, BCC, subject, and body. Reply to existing messages with quoted context. Navigate between folders (Inbox, Sent, Drafts). Configure your email account in the system settings. The Shogun can also manage email via native skills: <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">fetch_inbox</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">read_email</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">send_email</code>.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-emerald-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><CalendarDays className="w-4 h-4 text-emerald-400" /> Calendar — Event Management</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">CalDAV calendar integration. View your upcoming events on a timeline with titles, times, locations, and descriptions. Create new events by specifying a title, start/end time, location, and optional description. Supports all-day events. Connect a CalDAV server in the system settings. The Shogun can query and create events via native skills: <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">list_calendar_events</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">create_calendar_event</code>.</p>
                   </div>
                </div>

                 {/* Files Tab (Workspace File Explorer) */}
                 <div className="shogun-card space-y-3 border-l-2 border-amber-400/40 mt-4">
                    <div className="font-bold text-shogun-text flex items-center gap-2"><FolderOpenIcon className="w-4 h-4 text-amber-400" /> Files — Workspace File Explorer</div>
                    <p className="text-xs text-shogun-subdued leading-relaxed">A full visual file manager for the Agent Workspace — the dedicated folder shared between the Shogun, all Samurai agents, and the user. The Files tab provides everything you need to browse, create, edit, upload, and delete files without leaving the Comms page.</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
                       <div className="bg-shogun-bg rounded-lg p-3 space-y-1.5">
                          <div className="text-xs font-bold text-amber-400">Tree Sidebar (Left)</div>
                          <ul className="text-[11px] text-shogun-subdued space-y-1 ml-3 list-disc">
                             <li>Expandable directory tree with file-type icons (code, spreadsheet, image, archive, text).</li>
                             <li>File sizes shown in human-readable format (KB, MB).</li>
                             <li>Real-time search filter to find files instantly.</li>
                             <li>Workspace info footer: total files, directories, and disk usage.</li>
                          </ul>
                       </div>
                       <div className="bg-shogun-bg rounded-lg p-3 space-y-1.5">
                          <div className="text-xs font-bold text-amber-400">Content Panel (Right)</div>
                          <ul className="text-[11px] text-shogun-subdued space-y-1 ml-3 list-disc">
                             <li>Click a file to view its contents in a monospace reader.</li>
                             <li>Click <strong>Edit</strong> to modify any text file inline, then <strong>Save</strong> to write back to disk.</li>
                             <li>Click a folder to see its contents as a clickable card grid with icons and sizes.</li>
                             <li>Empty state shows workspace path and usage instructions.</li>
                          </ul>
                       </div>
                       <div className="bg-shogun-bg rounded-lg p-3 space-y-1.5">
                          <div className="text-xs font-bold text-amber-400">Toolbar Actions</div>
                          <ul className="text-[11px] text-shogun-subdued space-y-1 ml-3 list-disc">
                             <li><strong>New File</strong> (file+ icon): Creates a file inside the selected folder or workspace root.</li>
                             <li><strong>New Folder</strong> (folder+ icon): Creates a directory. Nested paths auto-created.</li>
                             <li><strong>Upload</strong> (upload icon): Opens a file picker to upload one or more files.</li>
                             <li><strong>Rename</strong> (edit icon): Renames the selected file or folder.</li>
                             <li><strong>Delete</strong> (trash icon): Deletes with confirmation. Directories deleted recursively.</li>
                             <li><strong>Refresh</strong> (refresh icon): Reloads the tree from disk.</li>
                          </ul>
                       </div>
                       <div className="bg-shogun-bg rounded-lg p-3 space-y-1.5">
                          <div className="text-xs font-bold text-amber-400">Drag &amp; Drop Upload</div>
                          <ul className="text-[11px] text-shogun-subdued space-y-1 ml-3 list-disc">
                             <li>Drag files from your desktop or file manager and drop them anywhere on the File Explorer.</li>
                             <li>A blue overlay appears showing where files will land.</li>
                             <li>Files are uploaded into the currently selected folder, or workspace root if none is selected.</li>
                             <li>Multiple files can be dropped at once. All file types are supported.</li>
                             <li>Filenames are sanitized on the server. Path traversal is blocked.</li>
                          </ul>
                       </div>
                    </div>
                 </div>
             </section>

             {/* SUPERMODE CANVAS */}
             <section id="ref-supermode" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-violet-400/40 pb-3">
                   <Target className="w-6 h-6 text-violet-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Supermode Canvas — Durable Multi-Agent Missions</h4>
                      <p className="text-xs text-shogun-subdued">The fifth Comms tab. Use it when one outcome needs planning, several specialists, governed tools, checkpoints, recovery, and a traceable result.</p>
                   </div>
                </div>

                <div className="rounded-xl border border-violet-400/30 bg-violet-500/10 p-4 space-y-2">
                   <div className="font-bold text-violet-300 flex items-center gap-2"><ShieldCheck className="w-4 h-4" /> Before you start</div>
                   <p className="text-xs text-shogun-subdued leading-relaxed">Supermode requires an active <strong>Campaign</strong> or <strong>Ronin</strong> posture. It remains governed: ToolGate capability boundaries, model eligibility, approvals, budgets, the kill switch, and live posture changes still apply. If the posture is lowered while a mission is running, the mission pauses rather than silently continuing with permissions it no longer has.</p>
                   <p className="text-xs text-shogun-subdued leading-relaxed">Use ordinary Chat for a quick answer. Choose Supermode when the work benefits from decomposition, parallel workstreams, evidence, review, synthesis, or a durable record that can survive a restart.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2 border-l-2 border-violet-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Play className="w-4 h-4 text-violet-400" /> Start a Mission from Chat</div>
                      <ol className="text-xs text-shogun-subdued space-y-1.5 ml-4 list-decimal leading-relaxed">
                         <li>Open <strong>Comms → Chat</strong>.</li>
                         <li>Select <strong>Supermode</strong> below the conversation.</li>
                         <li>Describe the outcome you want, not merely a topic.</li>
                         <li>Attach any source files needed for the work.</li>
                         <li>Send the prompt. Shogun creates a durable mission and returns a mission card.</li>
                         <li>Choose <strong>Open Supermode Canvas</strong>, or open the fifth Comms tab later.</li>
                      </ol>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-violet-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-violet-400" /> Write a Useful Mission Objective</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">A strong objective states the <strong>deliverable</strong>, <strong>scope</strong>, <strong>quality bar</strong>, <strong>constraints</strong>, and <strong>evidence expectations</strong>. For example: “Compare these three vendors, verify current pricing from primary sources, explain uncertainty, and create a decision memo in the workspace.”</p>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Avoid vague requests such as “research this.” The Shogun can plan from them, but it cannot infer every business constraint. Include deadlines, forbidden actions, required formats, preferred sources, and what a successful result must contain.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-shogun-gold/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><GitBranch className="w-4 h-4 text-shogun-gold" /> What the Shogun Does</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The Shogun turns the objective into a versioned plan containing bounded workstreams and dependencies. Independent tasks may run in parallel; dependent tasks wait for their predecessors. Specialists checkpoint concise results back into the mission so later tasks can continue without relying on an open chat window.</p>
                      <p className="text-xs text-shogun-subdued leading-relaxed">A failed attempt may be retried within its task budget. If a required predecessor ultimately fails, dependent work is blocked and the mission reports the unrecovered failure instead of pretending the result is complete.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-amber-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Clock className="w-4 h-4 text-amber-400" /> Fast Path and Runtime Limits</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">For an ordinary bounded objective, the Shogun uses two parallel analysis workstreams followed by one combined independent review and synthesis. Security, medical, legal, regulated, financial-advice, safety-critical, software, and other high-stakes work keeps a separate review gate. This shortens routine commercial and research missions without removing the final challenge of unsupported claims.</p>
                      <p className="text-xs text-shogun-subdued leading-relaxed">A research model may use at most eight governed tool calls across four tool rounds before it must answer from the evidence already gathered. One model attempt has a three-minute ceiling, and one task execution attempt has a seven-minute ceiling. If a model cannot complete in time, the Shogun moves to the configured fallback instead of replaying the same full research loop on that model. A task may still retry once when its durable retry budget permits.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-emerald-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Users className="w-4 h-4 text-emerald-400" /> Fleet Samurai or Spawned Specialist?</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The Shogun checks the permanent Samurai Fleet before spawning anyone. It scores active Samurai against the requested role, task description, assigned Shogun skills, routing profile, and availability. A good match is routed into the mission as a <strong>Fleet Samurai</strong>. If no appropriate match exists, the Shogun creates a temporary <strong>Spawned specialist</strong> limited to that mission.</p>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Click the agent box to see its source, mission role, routing explanation, inherited skills, available tools, latest handoff, and model-call usage. Operator-selected Fleet skills are used exactly as assigned; spawned specialists may retrieve governed skills from the Shogun&apos;s active skillset.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-blue-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><RouteIcon className="w-4 h-4 text-blue-400" /> Task-Level Routing Logic</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Every workstream can use a different Katana routing profile. The Shogun compares the task objective, instructions, task type, and Samurai role with each profile&apos;s description. A Fleet Samurai&apos;s assigned profile is preferred, but a clearly better task match may be selected.</p>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The chosen routing profile, reason, actual model, provider, and any fallback are stored on the task and timeline. A fallback is used only when an earlier profile cannot provide an enabled model with the required capabilities and runtime limits.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-cyan-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Workflow className="w-4 h-4 text-cyan-400" /> Read the Canvas</div>
                      <ul className="text-xs text-shogun-subdued space-y-1.5 ml-4 list-disc leading-relaxed">
                         <li><strong>Shogun:</strong> The gold top box shows mission state and current plan version.</li>
                         <li><strong>Agent boxes:</strong> Show the specialist role, Fleet/spawned source, state, and model-call count.</li>
                         <li><strong>Task boxes:</strong> Show the work item, state, and selected routing profile or model.</li>
                         <li><strong>Solid lines:</strong> Connect the Shogun to agents and agents to assigned tasks.</li>
                         <li><strong>Dashed “depends” lines:</strong> Show which task must finish before another can proceed.</li>
                         <li><strong>Agents, Tasks, Dependencies:</strong> Toggle each layer when the canvas becomes crowded. Use zoom, fit-view, and pan controls to navigate.</li>
                      </ul>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-cyan-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Search className="w-4 h-4 text-cyan-400" /> Drill Down with the Inspector</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Click <strong>Shogun</strong>, any agent box, or any task box to open its record in the right-hand Inspector. Click a Timeline entry to inspect the event type, timestamp, related task or agent, and structured event data. Click empty canvas space or the Inspector close button to return to the mission summary.</p>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Use this drilldown when a task is waiting or failed. The visible reason distinguishes routing problems, missing model capabilities, governance blocks, exhausted retry budgets, dependency failures, and operator pauses.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-indigo-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><List className="w-4 h-4 text-indigo-400" /> Timeline, Plans, Approvals, Learning &amp; Artifacts</div>
                      <ul className="text-xs text-shogun-subdued space-y-1.5 ml-4 list-disc leading-relaxed">
                         <li><strong>Timeline:</strong> A chronological, clickable explanation of planning, routing, execution, retries, pauses, and completion.</li>
                         <li><strong>Plans:</strong> Every plan version, its reason, status, and number of workstreams.</li>
                         <li><strong>Approvals:</strong> Durable requests that need a human decision. Read the reason, then approve or deny.</li>
                         <li><strong>Learning:</strong> Candidate lessons and procedures captured from meaningful checkpoints, with confidence.</li>
                         <li><strong>Artifacts:</strong> Generated files together with their description or workspace provenance.</li>
                      </ul>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-amber-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><SlidersHorizontal className="w-4 h-4 text-amber-400" /> Pause, Resume, Stop, Steer and Re-plan</div>
                      <ul className="text-xs text-shogun-subdued space-y-1.5 ml-4 list-disc leading-relaxed">
                         <li><strong>Pause:</strong> Prevents new work from starting. In-flight work stops at its current durable checkpoint, so the button is not an instant process kill.</li>
                         <li><strong>Resume:</strong> Continues from persisted mission state after the posture and budgets are eligible again.</li>
                         <li><strong>Stop:</strong> Cancels the mission after confirmation. No new work starts, and a late worker result cannot revive cancelled records.</li>
                         <li><strong>Message Shogun:</strong> Adds a constraint, redirects priorities, or changes emphasis without starting a new run.</li>
                         <li><strong>Re-plan:</strong> Creates a new plan version for a running mission while preserving history.</li>
                         <li><strong>Specialist:</strong> Requests an additional role and objective. The Shogun may route a matching Fleet Samurai or create a mission-scoped specialist.</li>
                      </ul>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-red-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Trash2 className="w-4 h-4 text-red-400" /> Mission List and Deletion</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The left column lists every run with its state and progress. Click a run to reopen it. The trash button deletes only a <strong>completed, failed, or stopped</strong> run; active work must be stopped first. Deleting removes the mission&apos;s run history from Supermode but deliberately keeps generated workspace files.</p>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Use <strong>Stop</strong> when you need execution to end but still want to inspect the run. Use <strong>Delete</strong> only when the retained mission record is no longer useful.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-red-400/40 md:col-span-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><AlertCircle className="w-4 h-4 text-red-400" /> Understand Common Pauses and Failures</div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs text-shogun-subdued leading-relaxed">
                         <ul className="space-y-1.5 ml-4 list-disc">
                            <li><strong>Requires Campaign or Ronin:</strong> Raise the posture in Torii, then resume. ToolGate may still narrow individual capabilities.</li>
                            <li><strong>Paused by Harakiri:</strong> Confirm the environment is safe, reset Harakiri, restore an eligible posture, and resume.</li>
                            <li><strong>Budget reached:</strong> The model-call, token, cost, agent, plan-revision, or deadline boundary stopped additional work. Review the mission before increasing limits.</li>
                         </ul>
                         <ul className="space-y-1.5 ml-4 list-disc">
                            <li><strong>No eligible model:</strong> In Katana, verify that the chosen custom profile contains an enabled model and that the model&apos;s registry capabilities include what the task requires. Also verify context and output limits.</li>
                            <li><strong>Exhausted retry budget:</strong> Open the failed task and its Timeline events. Fix the underlying model, tool, data, or governance problem before re-planning.</li>
                            <li><strong>Blocked by dependency:</strong> A required predecessor failed or was cancelled. Repair or replace that earlier workstream; the dependent task cannot safely run on missing input.</li>
                         </ul>
                      </div>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-emerald-400/40 md:col-span-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Sparkles className="w-4 h-4 text-emerald-400" /> Completion, Learning and Reuse</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">After successful workstreams are synthesized, the Shogun consolidates distinct learning candidates into durable memory with mission provenance. When the completed plan represents a reusable process, the Inspector shows <strong>Reusable process detected</strong>. Choose <strong>Create draft AgentFlow</strong> to open an editable draft that preserves the mission&apos;s task order and parallel dependencies. Review the draft before activating or running it.</p>
                   </div>
                </div>

                <div className="shogun-card space-y-3">
                   <div className="font-bold text-shogun-text flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-violet-400" /> Recommended Operating Sequence</div>
                   <ol className="text-xs text-shogun-subdued space-y-1.5 ml-4 list-decimal leading-relaxed">
                      <li>Confirm Campaign or Ronin in Torii and review the active custom policy in ToolGate.</li>
                      <li>Confirm Katana has eligible enabled models and sensible custom-profile descriptions and fallbacks.</li>
                      <li>Assign validated skills and routing profiles to permanent Fleet Samurai where you want fine-grained control.</li>
                      <li>Write a concrete outcome, attach the inputs, and start Supermode from Chat.</li>
                      <li>Inspect the first plan, agent sources, task-level routing choices, and dependency lines.</li>
                      <li>Resolve approvals and use Message Shogun or Re-plan when requirements change.</li>
                      <li>Investigate failures through the clickable task and Timeline records before retrying.</li>
                      <li>Review artifacts and learning, then convert a stable successful mission into a draft AgentFlow if it should be repeated.</li>
                      <li>Stop unwanted active runs before deleting their retained run history.</li>
                   </ol>
                </div>
             </section>

             {/* ═══════════════════════════════════════════════════════════════ */}
             {/* WORKSPACE (FILE EXPLORER) */}
             {/* ═══════════════════════════════════════════════════════════════ */}
              <section id="ref-workspace" className="space-y-6 scroll-mt-6">
                 <div className="flex items-center gap-3 border-b-2 border-amber-400/40 pb-3">
                    <FolderOpenIcon className="w-6 h-6 text-amber-400" />
                    <div>
                       <h4 className="text-xl font-bold uppercase tracking-widest">Workspace &mdash; Agent File System</h4>
                       <p className="text-xs text-shogun-subdued">A dedicated folder where the Shogun and all Samurai agents have persistent read/write access.</p>
                    </div>
                 </div>

                 <div className="shogun-card space-y-3">
                    <div className="font-bold text-shogun-text flex items-center gap-2"><Sparkles className="w-4 h-4 text-amber-400" /> Overview</div>
                    <p className="text-xs text-shogun-subdued leading-relaxed">{"The Workspace is a single, dedicated directory where the Shogun and all Samurai agents can read, write, and manage files. It serves as the agent\u2019s persistent \u201Cdesk\u201D \u2014 a safe location to store outputs, share data between agents, and create working documents. Availability and access mode follow the active policy's filesystem and workspace boundaries in ToolGate; the built-in Shrine policy disables it."}</p>
                    <p className="text-xs text-shogun-subdued leading-relaxed">{"Default location: data/workspace/ inside the Shogun project directory. The path is configurable via environment variable WORKSPACE_PATH."}</p>
                 </div>

                 <div className="shogun-card bg-amber-500/10 border-amber-500/30 border-l-4 border-l-amber-500 space-y-3">
                    <h5 className="text-sm font-bold text-amber-400 flex items-center gap-2"><CheckCircle2 className="w-5 h-5" /> Getting Started</h5>
                    <ol className="text-xs text-shogun-subdued space-y-2 ml-4 list-decimal">
                       <li>{"Navigate to Comms (sidebar) and click the Files tab."}</li>
                       <li>{"The File Explorer shows the workspace tree on the left and a content viewer/editor on the right."}</li>
                       <li>{"Use the toolbar buttons to create new files, new folders, rename, or delete items."}</li>
                       <li>{"Click any file to view its content. Click Edit to modify it inline, then Save."}</li>
                       <li>{"In Mission Mode chat, ask the Shogun to use workspace tools \u2014 it can read, write, list, and manage files directly."}</li>
                       <li>{"The workspace folder is automatically created on first startup at data/workspace/."}</li>
                    </ol>
                 </div>

                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><FolderOpenIcon className="w-4 h-4 text-amber-400" /> File Explorer (Comms &rarr; Files Tab)</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">{"The File Explorer is a tab inside the Comms page, alongside Chat, Mail, and Calendar. It provides a visual interface for managing workspace files:"}</p>
                       <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                          <li><strong>Tree sidebar:</strong> Expandable directory tree with file-type icons (code, spreadsheet, image, archive, text), size labels, and real-time search filter.</li>
                          <li><strong>Content viewer:</strong> Displays file contents with monospace formatting. Shows file path, extension, and size in the header bar.</li>
                          <li><strong>Inline editor:</strong> Click Edit to modify any text file directly in the browser. Click Save to write changes back to disk.</li>
                          <li><strong>Create File:</strong> Click the file+ icon in the toolbar. Enter a filename. The file is created inside the currently selected folder (or workspace root).</li>
                          <li><strong>Create Folder:</strong> Click the folder+ icon. Enter a folder name. Nested paths are created automatically.</li>
                          <li><strong>Rename:</strong> Select an item, click the edit icon. Enter the new name and confirm.</li>
                          <li><strong>Delete:</strong> Select an item, click the trash icon. A confirmation dialog appears. Directories are deleted recursively including all contents.</li>
                          <li><strong>Grid view:</strong> When a directory is selected, its contents are displayed as a clickable card grid with icons and sizes.</li>
                          <li><strong>Info footer:</strong> Shows the full workspace path, total file count, directory count, and disk usage in MB.</li>
                          <li><strong>Drag &amp; drop upload:</strong> Drag files from your desktop onto the File Explorer to upload them. A blue overlay indicates the drop target. Multiple files supported simultaneously.</li>
                          <li><strong>Upload button:</strong> Click the upload icon in the toolbar to open a native file picker for selecting files to upload into the current folder.</li>
                       </ul>
                    </div>
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Terminal className="w-4 h-4 text-amber-400" /> 6 Agent Native Tools</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">{"In Mission Mode, the Shogun and all Samurai agents have 6 workspace tools injected as native functions. The agent sees the workspace path in its system prompt and can use these tools autonomously:"}</p>
                       <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                          <li><strong>workspace_info</strong> <span className="text-green-400">(low risk)</span> \u2014 Returns workspace path, whether access is enabled, total files, total directories, and total size in MB.</li>
                          <li><strong>workspace_list</strong> <span className="text-green-400">(low risk)</span> \u2014 Lists files and directories at a given relative path. Returns name, type, size (for files), and child count (for dirs).</li>
                          <li><strong>workspace_read</strong> <span className="text-green-400">(low risk)</span> \u2014 Reads a text file\u2019s content (capped at 5 MB). Returns content, size, and path. Binary files return an error.</li>
                          <li><strong>workspace_write</strong> <span className="text-yellow-400">(medium risk)</span> \u2014 Creates or overwrites a text file. Parent directories are auto-created. Returns action (created/overwritten) and size.</li>
                          <li><strong>workspace_mkdir</strong> <span className="text-green-400">(low risk)</span> \u2014 Creates a subdirectory with parents. Returns action (created/already_exists).</li>
                          <li><strong>workspace_delete</strong> <span className="text-red-400">(high risk)</span> \u2014 Deletes a single file. Cannot delete directories (safety constraint via agent tools; the UI can delete dirs).</li>
                       </ul>
                    </div>
                 </div>

                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Shield className="w-4 h-4 text-amber-400" /> Path Validation &amp; Security</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">{"All workspace operations \u2014 both the File Explorer UI and agent native tools \u2014 enforce strict path validation at every level:"}</p>
                       <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                          <li><strong>Boundary enforcement:</strong> Every path is resolved to its absolute form and checked that it remains inside the workspace root. Any escape attempt is blocked.</li>
                          <li><strong>Traversal blocking:</strong> Paths containing <code className="bg-shogun-card px-1 rounded">..</code> are rejected immediately, before any filesystem operation.</li>
                          <li><strong>Absolute path blocking:</strong> Only relative paths (from workspace root) are accepted. Paths starting with <code className="bg-shogun-card px-1 rounded">/</code> or <code className="bg-shogun-card px-1 rounded">\</code> are rejected.</li>
                          <li><strong>UNC path blocking:</strong> Network paths are rejected to prevent lateral movement.</li>
                          <li><strong>Size guard:</strong> File reads are capped at 5 MB (agent tools) or 10 MB (File Explorer UI) to prevent memory exhaustion.</li>
                          <li><strong>Root protection:</strong> The workspace root directory itself cannot be deleted.</li>
                       </ul>
                    </div>
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Lock className="w-4 h-4 text-amber-400" /> Security Posture Matrix</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">{"The workspace is a binary gate: either fully available or completely locked."}</p>
                       <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                          <li><strong>SHRINE:</strong> \u274C Workspace completely disabled. No read, no write, no listing. All 6 tools return errors. File Explorer shows an error state with retry button.</li>
                          <li><strong>GUARDED:</strong> \u2705 Full read/write access. All 6 agent tools available. File Explorer fully functional.</li>
                          <li><strong>TACTICAL:</strong> \u2705 Full read/write access. All 6 agent tools available.</li>
                          <li><strong>CAMPAIGN:</strong> \u2705 Full read/write access. All 6 agent tools available.</li>
                          <li><strong>RONIN:</strong> \u2705 Full read/write access. All 6 agent tools available.</li>
                       </ul>
                    </div>
                 </div>

                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Link2 className="w-4 h-4 text-amber-400" /> Office App Mode Alignment</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">{"The Workspace and Office App Mode share the same folder concept. The four \u201CApproved Folders\u201D in the Katana\u2019s Office tab (input, output, templates, temp) can be left empty to auto-map to the workspace root directory. This means Office file operations and agent workspace tools operate in the same directory by default. Configure custom paths in the Katana \u2192 Office tab if you need separate boundaries for Office automation."}</p>
                    </div>
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Globe className="w-4 h-4 text-amber-400" /> REST API Endpoints</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">{"The File Explorer UI uses a dedicated REST API under /api/v1/workspace/. These endpoints are also available for external integrations and custom tooling:"}</p>
                       <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                          <li><code className="bg-shogun-card px-1 rounded">GET /api/v1/workspace/info</code> \u2014 Metadata, path, and disk usage</li>
                          <li><code className="bg-shogun-card px-1 rounded">GET /api/v1/workspace/tree</code> \u2014 Full recursive directory tree (JSON)</li>
                          <li><code className="bg-shogun-card px-1 rounded">GET /api/v1/workspace/read?path=</code> \u2014 Read file content as text</li>
                          <li><code className="bg-shogun-card px-1 rounded">POST /api/v1/workspace/write</code> \u2014 Create or update file (JSON body: path, content)</li>
                          <li><code className="bg-shogun-card px-1 rounded">POST /api/v1/workspace/mkdir</code> \u2014 Create directory (JSON body: path)</li>
                          <li><code className="bg-shogun-card px-1 rounded">DELETE /api/v1/workspace/delete?path=</code> \u2014 Delete file or directory</li>
                          <li><code className="bg-shogun-card px-1 rounded">POST /api/v1/workspace/rename</code> \u2014 Rename/move (JSON body: old_path, new_path)</li>
                       </ul>
                    </div>
                 </div>

                 <div className="shogun-card space-y-2">
                    <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-amber-400" /> System Prompt Integration</div>
                    <p className="text-xs text-shogun-subdued leading-relaxed">{"When workspace is enabled, the Shogun\u2019s system prompt includes the workspace path and available tools in two places: the ACTIVE SECURITY POSTURE block (\u201CWorkspace: ENABLED \u2014 /path/to/workspace\u201D) and the YOUR CAPABILITIES block (listing all 6 tools by name). This ensures the agent knows where to save files and which tools it can call. At SHRINE, the prompt shows \u201CWorkspace: DISABLED (SHRINE posture)\u201D."}</p>
                 </div>
              </section>

             {/* ═══════════════════════════════════════════════════════════════ */}
             {/* 5. KATANA (THE FORGE) */}
             {/* ═══════════════════════════════════════════════════════════════ */}
             <section id="ref-katana" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-blue/40 pb-3">
                   <Cpu className="w-6 h-6 text-shogun-blue" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Katana — The System Forge</h4>
                      <p className="text-xs text-shogun-subdued">Where you install and connect models, tools, formats, channels, account integrations, and operational capability providers. Shows 11 tabs normally and 12 when IDE Mode is available in Campaign or Ronin posture. Katana exposes capabilities; it does not decide whether a capability may run.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Key className="w-4 h-4 text-shogun-blue" /> AI Model Provider Tab</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Lists every cloud or local AI service the deploying organisation has connected (OpenAI, Anthropic, Google Gemini, Perplexity, Ollama, etc.). Each provider card shows its <strong>name</strong>, <strong>type</strong>, <strong>status</strong>, and available <strong>models</strong>. The deploying organisation selects and assesses providers and models for its use cases; third-party providers remain responsible for their services under their terms and applicable law. Add, edit, enable, disable, or delete provider connections here; credentials are stored through the backend rather than displayed after saving.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-shogun-blue" /> File Formats Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Controls the file-format registry used by governed tools. Review recognized extensions, MIME types, capability categories, safety classifications, size limits, and which operations are available for each format.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Binary className="w-4 h-4 text-shogun-blue" /> Routing Profiles Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Open <strong>Model Routing</strong> to choose a built-in automatic profile or create a custom profile. A custom profile has a name and a plain-language description, an exact ordered list of enabled models, and a temperature for each model. The first model is Primary; the rest are attempted as fallbacks in the displayed order. The description matters because Supermode compares it with each workstream and can choose a different routing logic for different tasks.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Network className="w-4 h-4 text-shogun-blue" /> Toolbox Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Lists the external tools installed or connected to Shogun — web search, file access, database connections, code execution, and more. Each tool shows its <strong>name</strong>, <strong>type</strong>, and availability status. You can <strong>register new tools</strong> and connect or disconnect existing ones. These controls determine whether a capability exists; <strong>ToolGate</strong> determines whether, when, and with what confirmation it may execute.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Sparkles className="w-4 h-4 text-shogun-blue" /> Skills · Active Usage Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Shows which Dojo skills are actually retrieved and injected during agent runs, along with usage outcomes, trajectory evidence, and improvement candidates. See <strong>Active Skills &amp; Trajectory Capture</strong> below for the complete runtime lifecycle.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileSpreadsheet className="w-4 h-4 text-shogun-blue" /> Office App Mode Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Controls the <strong>Office App Mode</strong> — Shogun's ability to read, create, and modify Microsoft Office documents (<code>.xlsx</code>, <code>.docx</code>, <code>.pptx</code>). The tab has a master <strong>enable/disable</strong> toggle at the top. Below it are four sections:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Approved Folders:</strong> Four directory paths (Input, Output, Templates, Temp) that define the allowed file boundaries. When left empty, they automatically use the <strong>workspace root</strong> folder. All file operations are jailed to these directories — any path outside them is rejected.</li>
                         <li><strong>Per-Application Settings:</strong> Individual cards for <strong>Excel</strong>, <strong>Word</strong>, <strong>PowerPoint</strong>, and <strong>Outlook</strong> — each with its own enable toggle, macro policy (allow/block), overwrite protection, and timeout. Excel also has an external links toggle; Outlook has draft-only vs. send mode and domain allowlists.</li>
                         <li><strong>Safety Rules:</strong> Global policies including path traversal blocking, Windows shortcut (<code>.lnk</code>) blocking, UNC/network path blocking, output versioning, and a maximum file size cap (default 100 MB).</li>
                         <li><strong>Security Posture Gate:</strong> Office operations require at least <strong>Guarded</strong> posture. In <strong>Shrine</strong> mode, all Office tools are disabled. The minimum posture can be raised (e.g., to Tactical) for stricter environments.</li>
                      </ul>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Mail className="w-4 h-4 text-shogun-blue" /> Mail &amp; Calendar Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Connect your email account for AI-powered mail capabilities. Configure an <strong>IMAP/SMTP</strong> account by entering server addresses, port numbers, and credentials. Once connected, the Shogun can:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Read emails:</strong> Fetch and analyze incoming mail from the inbox.</li>
                         <li><strong>Send emails:</strong> Compose and send messages when Mail writes are enabled in ToolGate &gt; Comms.</li>
                         <li><strong>Calendar events:</strong> Create and manage calendar entries (when supported by the provider).</li>
                      </ul>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The tab shows <strong>connection status</strong>, account details, and <strong>Account Scopes</strong> for read, send, and calendar access. These scopes describe what the connected account exposes; ToolGate remains the runtime authority and can further restrict or require confirmation for every action. Recorded mail activity is submitted to the HMAC-chained audit store.</p>
                   </div>
                   <div id="ref-telegram" className="shogun-card space-y-5 md:col-span-2 scroll-mt-6 border-sky-400/20">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Globe className="w-4 h-4 text-shogun-blue" /> Telegram Integration</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Connect a private Telegram bot so you can talk to Shogun from your phone. A first-time personal setup normally takes 10–15 minutes.</p>
                      <div className="p-3 rounded-lg border border-sky-400/20 bg-sky-400/5 text-xs text-shogun-subdued leading-relaxed">
                         <strong className="text-shogun-text">Choose Polling.</strong> It is the working listener in this release and needs no public URL.
                         Keep Webhook for administrator-managed custom deployments.
                      </div>
                      <ol className="text-xs text-shogun-subdued space-y-2 ml-5 list-decimal leading-relaxed">
                         <li>In Telegram, open the verified <a href="https://t.me/BotFather" target="_blank" rel="noreferrer" className="text-sky-400 hover:underline">@BotFather</a> account and send <code>/newbot</code>.</li>
                         <li>Choose a display name, then a unique username ending in <code>bot</code>. Copy the token BotFather returns and protect it like a password.</li>
                         <li>Open <strong>Katana → Telegram</strong>, paste the token, select Polling, temporarily leave Allowed Chat IDs empty, and click <strong>Connect Bot</strong>.</li>
                         <li>Open your new bot in Telegram, press Start, and send <code>Hello</code>. Bots cannot initiate private conversations.</li>
                         <li>Back in Katana, click <strong>Auto-detect Chat ID</strong>. The detected ID is placed in the test and whitelist fields.</li>
                         <li>
                            Paste the token again and click <strong>Update Connection</strong>. This second save is essential: auto-detect changes the form,
                            but the Allowed Chat IDs whitelist is not permanent until the connection is updated.
                         </li>
                         <li>Click <strong>Send Test</strong>, then send <code>Hello Shogun</code> from Telegram. Receiving both replies completes the private-chat setup.</li>
                      </ol>
                      <div className="grid md:grid-cols-2 gap-4">
                         <div className="p-3 rounded-lg bg-shogun-bg border border-shogun-border">
                            <p className="text-xs font-bold text-shogun-text mb-2">Adding a group</p>
                            <p className="text-[11px] text-shogun-subdued leading-relaxed">
                               Add the bot, send a direct command or mention, then auto-detect again. A group ID is normally negative.
                               Add it to Allowed Chat IDs, paste the token again, and Update Connection. Telegram Privacy Mode normally limits the bot to commands, mentions, and replies.
                            </p>
                         </div>
                         <div className="p-3 rounded-lg bg-shogun-bg border border-shogun-border">
                            <p className="text-xs font-bold text-shogun-text mb-2">Safety rules</p>
                            <ul className="text-[11px] text-shogun-subdued ml-4 list-disc space-y-1">
                               <li>Never leave Allowed Chat IDs empty after discovery.</li>
                               <li>Run only one Shogun poller per token.</li>
                               <li>Regenerate an exposed token in BotFather immediately.</li>
                               <li>Shogun must stay awake, running, and online.</li>
                            </ul>
                         </div>
                      </div>
                      <p className="text-[11px] text-shogun-subdued leading-relaxed">
                         <strong className="text-shogun-text">If auto-detect finds nothing:</strong> send a fresh direct message to the bot, wait a few seconds, and retry.
                         If Send Test works but normal messages are ignored, verify the exact Chat ID and repeat the second Update Connection save.
                         See the expanded Telegram setup and troubleshooting walkthrough in the Onboarding tab.
                      </p>
                      <a href="https://core.telegram.org/bots/features" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[11px] text-sky-400 hover:underline">
                         <ExternalLink className="w-3 h-3" /> Official Telegram bot and Privacy Mode reference
                      </a>
                   </div>
                </div>

             </section>

              {/* ─── MODEL ROUTER ─── */}
              <section id="ref-model-router" className="space-y-6 scroll-mt-6">
                 <div className="flex items-center gap-3 border-b-2 border-blue-400/40 pb-3">
                    <RouteIcon className="w-6 h-6 text-blue-400" />
                    <div>
                       <h4 className="text-xl font-bold uppercase tracking-widest">Model Router — Intelligent Model Selection</h4>
                       <p className="text-xs text-shogun-subdued">Provider-agnostic, task-aware model selection with routing profiles, registry, and usage telemetry.</p>
                    </div>
                 </div>

                  <div className="shogun-card space-y-3">
                     <div className="font-bold text-shogun-text flex items-center gap-2"><Compass className="w-4 h-4 text-blue-400" /> How It Works</div>
                     <p className="text-xs text-shogun-subdued leading-relaxed">Instead of hardcoding which configured model handles each request, the Model Router evaluates the <strong>task type</strong>, <strong>complexity</strong>, and your <strong>active routing profile</strong> to select a matching model automatically. Navigate to <strong>Katana → Model Routing</strong> to configure profiles and view the model registry. Registry metadata and routing scores are orchestration aids, not Alpha Horizon certification that a model is suitable or legally compliant for a particular use case.</p>
                  </div>

                  <div className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 p-4 space-y-2">
                     <div className="font-bold text-cyan-300 flex items-center gap-2"><ShieldCheck className="w-4 h-4" /> Model responsibility boundary</div>
                     <p className="text-xs text-shogun-subdued leading-relaxed">Shogun does not bundle, train, or supply a proprietary LLM or foundation model. It orchestrates local or cloud-hosted models selected and configured by the deploying organisation. Alpha Horizon remains responsible for official Shogun orchestration code, defaults, connectors, and documentation to the extent required by applicable law; the deploying organisation remains responsible for its provider selection, configuration, data, use case, oversight, and output validation; and each third-party provider remains responsible for its own model or service under its terms and applicable law.</p>
                  </div>

                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="shogun-card space-y-2 border-l-2 border-blue-400/40">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Layers className="w-4 h-4 text-blue-400" /> 5 Routing Profiles</div>
                       <div className="bg-shogun-bg rounded-lg p-3 space-y-2">
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-green-400 bg-green-400/10 px-2 py-0.5 rounded">ULTRA ECONOMY</span><span className="text-xs text-shogun-subdued">Strongly prefers local models, minimizes API calls.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded">ECONOMY</span><span className="text-xs text-shogun-subdued">Low-cost daily work, escalates only for complex tasks.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-blue-400 bg-blue-400/10 px-2 py-0.5 rounded">BALANCED</span><span className="text-xs text-shogun-subdued">Recommended balance of quality and cost. Default profile.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded">HIGH CAPABILITY</span><span className="text-xs text-shogun-subdued">Uses stronger models earlier in the complexity curve.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-red-400 bg-red-400/10 px-2 py-0.5 rounded">PREMIUM</span><span className="text-xs text-shogun-subdued">Maximum quality, always picks the best available model.</span></div>
                       </div>
                    </div>
                    <div className="shogun-card space-y-2 border-l-2 border-blue-400/40">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-blue-400" /> Task Classification</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Every request is classified into one of 20+ task types across 5 complexity tiers:</p>
                       <div className="bg-shogun-bg rounded-lg p-3 space-y-1.5 text-xs text-shogun-subdued">
                          <p><strong className="text-green-400">Simple:</strong> simple_chat, classification, extraction, memory_write</p>
                          <p><strong className="text-emerald-400">Moderate:</strong> summarization, browser_task, skill_selection</p>
                          <p><strong className="text-blue-400">Complex:</strong> planning, coding_plan, coding_edit, stack_planning</p>
                          <p><strong className="text-amber-400">Critical:</strong> complex_reasoning, test_failure_analysis, self_verification</p>
                          <p><strong className="text-cyan-400">Vision:</strong> visual_understanding, screenshot_analysis, photo_understanding</p>
                       </div>
                    </div>
                    <div className="shogun-card space-y-2 border-l-2 border-violet-400/40">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><RouteIcon className="w-4 h-4 text-violet-400" /> Supermode Task-Level Routing</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Supermode can choose a different routing profile for each workstream. It compares the task objective, instructions, task type, and Samurai role with every configured profile description. A Samurai&apos;s assigned profile remains the preference unless another description is a clearly stronger fit. The chosen profile and explanation are recorded on the task and timeline; if it cannot satisfy the required capabilities, Shogun falls back to the assigned profile, active profile, and then Balanced.</p>
                    </div>
                    <div className="shogun-card space-y-2 border-l-2 border-blue-400/40">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Database className="w-4 h-4 text-blue-400" /> Model Registry</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Every discovered model is registered with its provider, enabled state, supported task capabilities, quality/cost/latency tiers, context limits, native tool-calling support, and role tags. This metadata determines whether the router considers the model eligible; incorrectly disabling a model or removing a required capability can produce a “No eligible model” task failure.</p>
                       <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Editing rule:</strong> select a <strong>custom profile</strong> to enable registry editing. You can then enable or disable models, click capability chips, change quality/cost/latency, choose automatic or manually overridden context limits, test a model, and verify tool support. Built-in automatic profiles intentionally show the registry as read-only because their eligibility rules are fixed. Save the profile after changing its model order.</p>
                    </div>
                    <div className="shogun-card space-y-2 border-l-2 border-blue-400/40">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-blue-400" /> Decision & Usage Logs</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Every routing decision is persisted: which task type, complexity score, selected model, fallback model, and reason. Usage telemetry tracks input/output tokens, cost estimates, and latency. View usage summaries.</p>
                    </div>
                    <div className="shogun-card space-y-2 border-l-2 border-cyan-400/40">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-cyan-400" /> OpenClaw College Ecosystem Intelligence</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">OpenClaw College ecosystem intelligence is <strong>disabled by default</strong>. No event is queued or sent until a local administrator explicitly opts in under <strong>Privacy &amp; Telemetry</strong> after reviewing the purpose, exact destination, and fields. When enabled, Shogun sends only <code>eventId</code>, <code>schemaVersion</code>, <code>eventType</code>, <code>occurredAt</code>, <code>installationHash</code>, <code>shogunVersion</code>, <code>country</code>, <code>model</code>, <code>provider</code>, <code>taskType</code>, <code>locality</code>, <code>success</code>, <code>inputTokens</code>, <code>outputTokens</code>, <code>latency</code>, and <code>cost</code> to <code>https://www.openclawcollege.com/api/v1/intelligence/events</code>. The configured model, provider, and task identifiers are sent as text, truncated to 120, 80, and 80 characters respectively; token, latency, and cost values are bucketed, <code>occurredAt</code> is rounded to the UTC hour, <code>country</code> is derived from OS/locale settings, and <code>installationHash</code> is a weekly rotating pseudonymous identifier. The security and incident-reporting acknowledgement is separate and is never sent.</p>
                       <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Before opting in:</strong> do not enable College sharing if a configured model, provider, or task identifier contains a tenant, customer, project, person, filename, prompt fragment, credential, secret, or other sensitive value. Prompts, outputs, files, error contents, agent names, credentials, and exact IP addresses are not dedicated application-payload fields, but configured identifiers are transmitted verbatim within the stated length limits. HTTPS delivery necessarily exposes network connection metadata to the recipient and network providers; review the recipient&apos;s current privacy terms before opting in. Shogun does not assert or control the recipient&apos;s retention or publication practices.</p>
                    </div>
                 </div>
              </section>

              {/* ─── VISUAL INTAKE ─── */}
              <section id="ref-visual-intake" className="space-y-6 scroll-mt-6">
                 <div className="flex items-center gap-3 border-b-2 border-cyan-400/40 pb-3">
                    <Eye className="w-6 h-6 text-cyan-400" />
                    <div>
                       <h4 className="text-xl font-bold uppercase tracking-widest">Visual Intake — Image Analysis</h4>
                       <p className="text-xs text-shogun-subdued">Secure, source-neutral image upload, processing, and AI-powered vision analysis with full governance.</p>
                    </div>
                 </div>

                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="shogun-card space-y-2 border-l-2 border-cyan-400/40">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Camera className="w-4 h-4 text-cyan-400" /> Upload & Process</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Upload images from chat, Telegram, email, or browser. Shogun normalizes them to WebP, generates 640×640 thumbnails, strips all EXIF metadata (GPS, camera info, timestamps) for privacy, and deduplicates via SHA-256 hashing. Supported formats: JPEG, PNG, WebP, static GIF (max 20 MB).</p>
                    </div>
                    <div className="shogun-card space-y-2 border-l-2 border-cyan-400/40">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Sparkles className="w-4 h-4 text-cyan-400" /> AI Vision</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Describe:</strong> Generate natural language descriptions. <strong>Inspect:</strong> Deep inspection with custom prompts — ask specific questions about content. <strong>OCR:</strong> Extract text from screenshots, documents, and photos. <strong>Compare:</strong> Side-by-side comparison of two images with AI analysis.</p>
                    </div>
                    <div className="shogun-card space-y-2 border-l-2 border-cyan-400/40">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Shield className="w-4 h-4 text-cyan-400" /> 6 Permission Flags</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed"><code className="text-cyan-400">allow_image_intake</code> (on), <code className="text-cyan-400">allow_local_vision</code> (on), <code className="text-cyan-400">allow_cloud_vision</code> (off — privacy-sensitive), <code className="text-cyan-400">allow_ocr</code> (on), <code className="text-cyan-400">allow_auto_memory</code> (off — privacy-sensitive), and <code className="text-cyan-400">allow_delete</code> (on). These are policy-scoped capability boundaries in <strong>ToolGate</strong>; there is no separate Visual Intake permission tab in Katana.</p>
                    </div>
                    <div className="shogun-card space-y-2 border-l-2 border-cyan-400/40">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Link2 className="w-4 h-4 text-cyan-400" /> Retention &amp; Context</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Pin important images to prevent retention expiry (default: 30 days). Images can be linked to chat sessions and messages for context tracking.</p>
                    </div>
                 </div>
              </section>

              {/* ─── ACTIVE SKILLS & TRAJECTORY ─── */}
              <section id="ref-active-skills" className="space-y-6 scroll-mt-6">
                 <div className="flex items-center gap-3 border-b-2 border-amber-400/40 pb-3">
                    <Sparkles className="w-6 h-6 text-amber-400" />
                    <div>
                       <h4 className="text-xl font-bold uppercase tracking-widest">Active Skills & Trajectory Capture</h4>
                       <p className="text-xs text-shogun-subdued">Runtime skill retrieval from the Dojo — automatic selection, context injection, outcome tracking, and improvement candidates.</p>
                    </div>
                 </div>

                 <div className="shogun-card space-y-3">
                    <div className="font-bold text-shogun-text flex items-center gap-2"><Flame className="w-4 h-4 text-amber-400" /> How Active Skills Work</div>
                    <p className="text-xs text-shogun-subdued leading-relaxed">When a Shogun agent processes a request, the Active Skill system automatically <strong>retrieves</strong> relevant skills from the Dojo, <strong>gates</strong> them against the active ToolGate capability boundaries and exam requirements, <strong>injects</strong> skill content into the LLM context (advisory or context_block mode), and <strong>tracks</strong> the outcome (success, partial, failed, not_used, blocked). Torii selects the governing tier or custom policy; ToolGate applies its runtime rules. Skills are live during execution — not just catalog entries.</p>
                 </div>

                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="shogun-card space-y-2 border-l-2 border-amber-400/40">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Shield className="w-4 h-4 text-amber-400" /> Configuration</div>
                       <div className="bg-shogun-bg rounded-lg p-3 space-y-1.5 text-xs text-shogun-subdued">
                          <p><code className="text-amber-400">active_skill_max_per_run</code>: 5 — max skills per execution run</p>
                          <p><code className="text-amber-400">active_skill_max_per_step</code>: 3 — max skills per step</p>
                          <p><code className="text-amber-400">active_skill_max_total_context_tokens</code>: 2,500 — token budget</p>
                          <p><code className="text-amber-400">active_skill_require_exam_pass</code>: true — only use passed skills</p>
                          <p><code className="text-amber-400">active_skill_preserve_during_compaction</code>: true — keep during context compaction</p>
                       </div>
                    </div>
                    <div className="shogun-card space-y-2 border-l-2 border-amber-400/40">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><GitMerge className="w-4 h-4 text-amber-400" /> Trajectory Capture</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Every skill invocation generates a structured evidence trail: <strong>Candidate Retrievals</strong> (which skills were considered), <strong>Episodes</strong> (full lifecycle), <strong>Trajectories</strong> (outcome scoring), <strong>Tool Links</strong> (tools called during usage), <strong>Verification Links</strong> (how outcomes were verified), <strong>Outcome Scores</strong> (deterministic scoring), and <strong>Improvement Candidates</strong> (suggested fixes). All data is secret-redacted automatically.</p>
                    </div>
                 </div>
              </section>


              {/* OFFICE APP MODE */}
              <section id="ref-office" className="space-y-6 scroll-mt-6">
                 <div className="flex items-center gap-3 border-b-2 border-green-400/40 pb-3">
                    <FileSpreadsheet className="w-6 h-6 text-green-400" />
                    <div>
                       <h4 className="text-xl font-bold uppercase tracking-widest">Office App Mode</h4>
                       <p className="text-xs text-shogun-subdued">Controlled Microsoft Office automation &mdash; Excel, Word, PowerPoint, Outlook.</p>
                    </div>
                 </div>
                 <div className="shogun-card space-y-3">
                    <div className="font-bold text-shogun-text flex items-center gap-2"><Sparkles className="w-4 h-4 text-green-400" /> Overview</div>
                    <p className="text-xs text-shogun-subdued leading-relaxed">{"Office App Mode (codename Katana) lets the AI agent read, modify, and create Excel workbooks, Word documents, PowerPoint presentations, and Outlook emails \u2014 all within strict security boundaries. It uses a hybrid architecture: pure Python libraries handle most operations cross-platform. COM automation is only used for PDF export, formula calculation, and Outlook."}</p>
                 </div>
                 <div className="shogun-card bg-green-500/10 border-green-500/30 border-l-4 border-l-green-500 space-y-3">
                    <h5 className="text-sm font-bold text-green-400 flex items-center gap-2"><CheckCircle2 className="w-5 h-5" /> Getting Started</h5>
                    <ol className="text-xs text-shogun-subdued space-y-2 ml-4 list-decimal">
                          <li>{"Navigate to Katana → Office."}</li>
                       <li>{"Enable Office App Mode with the master toggle."}</li>
                       <li>{"Configure all four folders \u2014 input, output, templates, and temp."}</li>
                       <li>{"Toggle individual apps \u2014 enable only what you need."}</li>
                       <li>{"Save your configuration."}</li>
                       <li>{"The 27 Office tools are now available to the agent in chat."}</li>
                    </ol>
                 </div>
                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Shield className="w-4 h-4 text-green-400" /> Approved Folders</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">{"Every file operation is validated against four folder boundaries (input, output, templates, temp). Files outside are rejected. Path traversal, UNC paths, and .lnk shortcuts are blocked."}</p>
                    </div>
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Layers className="w-4 h-4 text-green-400" /> Output Versioning</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">{"The agent never overwrites originals. Every save creates a timestamped copy (e.g. report_20260630_094500.xlsx). Old outputs are cleaned after the retention period (default: 30 days)."}</p>
                    </div>
                 </div>
                 <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><FileSpreadsheet className="w-4 h-4 text-green-400" /> Excel (8 tools)</div>
                       <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc"><li>Open workbook</li><li>Read range / all cells</li><li>Write range</li><li>List sheets</li><li>Save as (versioned)</li><li>Export PDF (COM)</li><li>Recalculate (COM)</li><li>Get metadata</li></ul>
                    </div>
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-blue-400" /> Word (6 tools)</div>
                       <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc"><li>Open document</li><li>Replace placeholders</li><li>Insert table</li><li>Save as (versioned)</li><li>Export PDF (COM)</li><li>Get metadata</li></ul>
                    </div>
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Layers className="w-4 h-4 text-orange-400" /> PowerPoint (7 tools)</div>
                       <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc"><li>Open presentation</li><li>Replace placeholders</li><li>Insert table</li><li>Insert image</li><li>Save as (versioned)</li><li>Export PDF (COM)</li><li>Get metadata</li></ul>
                    </div>
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Mail className="w-4 h-4 text-cyan-400" /> Outlook (4 tools)</div>
                       <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc"><li>Create draft</li><li>Attach file</li><li>Save + review</li><li>Send (high-risk)</li></ul>
                    </div>
                 </div>
                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Mail className="w-4 h-4 text-cyan-400" /> Outlook Modes</div>
                       <div className="bg-shogun-bg rounded-lg p-3 space-y-2">
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-green-400 bg-green-400/10 px-2 py-0.5 rounded">DRAFT ONLY</span><span className="text-xs text-shogun-subdued">Create and save drafts. Never sends.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-yellow-400 bg-yellow-400/10 px-2 py-0.5 rounded">CONFIRMED SEND</span><span className="text-xs text-shogun-subdued">Can send with human approval.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-red-400 bg-red-400/10 px-2 py-0.5 rounded">APPROVED RECIPIENTS</span><span className="text-xs text-shogun-subdued">Auto-send to allowlisted domains.</span></div>
                       </div>
                    </div>
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Lock className="w-4 h-4 text-green-400" /> Security Per Posture</div>
                       <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                          <li><strong>SHRINE:</strong> Office completely disabled.</li>
                          <li><strong>GUARDED:</strong> Read, write, save-as. No overwrite, no macros, no send.</li>
                          <li><strong>TACTICAL:</strong> + Delete (approval). + Send (approval).</li>
                          <li><strong>CAMPAIGN:</strong> + Delete (allowed). + Send (approval).</li>
                          <li><strong>RONIN:</strong> + Overwrite originals. Send still requires approval.</li>
                       </ul>
                    </div>
                 </div>
                 <div className="shogun-card space-y-2">
                    <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-green-400" /> Audit Trail</div>
                    <p className="text-xs text-shogun-subdued leading-relaxed">{"Every Office operation emits an office.* event into the dual-write audit chain. Events include application, action, file paths, duration, and status."}</p>
                 </div>
              </section>

              {/* ─── IDE MODE ─── */}
              <section id="ref-ide-mode" className="space-y-6 scroll-mt-6">
                 <div className="flex items-center gap-3 border-b-2 border-emerald-400/40 pb-3">
                    <MonitorIcon className="w-6 h-6 text-emerald-400" />
                    <div>
                       <h4 className="text-xl font-bold uppercase tracking-widest">IDE Mode — VS Code Integration</h4>
                       <p className="text-xs text-shogun-subdued">Connect your VS Code editor via a governed WebSocket bridge for AI-assisted development.</p>
                    </div>
                 </div>

                 <div className="shogun-card bg-amber-500/10 border-amber-500/30 border-l-4 border-l-amber-500">
                    <h5 className="text-sm font-bold text-amber-400 flex items-center gap-2 mb-3">
                       <ShieldAlert className="w-5 h-5" />
                       Requires Campaign or Ronin Posture
                    </h5>
                    <p className="text-xs text-shogun-subdued leading-relaxed">IDE Mode is exposed by Katana only when the active policy is based on Campaign or Ronin and its ToolGate capability boundary enables <code className="text-amber-400">ide_enabled</code>. The WebSocket bridge only accepts connections from localhost (<code className="text-amber-400">127.0.0.1</code> / <code className="text-amber-400">::1</code>) — remote connections are rejected.</p>
                 </div>

                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="shogun-card space-y-2 border-l-2 border-emerald-400/40">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-emerald-400" /> File Operations</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Read, create, list, search, and apply patches within approved workspaces. Before an IDE write, Shogun keeps an in-memory content restore point for the lifetime of the running process; this is not a durable SHA-256 backup. A supported interrupted workflow may resume from its last valid checkpoint, but operators must verify external side effects. <strong>Protected files</strong> (<code className="text-emerald-400">.env</code>, <code className="text-emerald-400">*.pem</code>, <code className="text-emerald-400">*.key</code>, <code className="text-emerald-400">id_rsa*</code>, <code className="text-emerald-400">credentials*</code>) require explicit approval and are not added to model context automatically; credential directories remain blocked.</p>
                    </div>
                    <div className="shogun-card space-y-2 border-l-2 border-emerald-400/40">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Terminal className="w-4 h-4 text-emerald-400" /> Terminal & Git</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Run approved commands (allowlisted per posture: <code className="text-emerald-400">pytest</code>, <code className="text-emerald-400">python</code>, <code className="text-emerald-400">npm</code>, <code className="text-emerald-400">ruff</code>, <code className="text-emerald-400">mypy</code>, <code className="text-emerald-400">tsc</code>, <code className="text-emerald-400">cargo</code>, <code className="text-emerald-400">go</code>). Git operations: status, diff, branch, create-branch, commit. <strong>Push is disabled by default</strong>; git mutations require Ronin + explicit approval.</p>
                    </div>
                    <div className="shogun-card space-y-2 border-l-2 border-emerald-400/40">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Key className="w-4 h-4 text-emerald-400" /> Pairing System</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Pairing uses one-time <code className="text-emerald-400">SHG-</code> prefixed tokens with SHA-256 digest comparison and 10-minute expiry. Generate a token in the Katana IDE tab, enter it in VS Code, and the bridge connects. Revoke all pairings instantly from the dashboard.</p>
                    </div>
                    <div className="shogun-card space-y-2 border-l-2 border-emerald-400/40">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Zap className="w-4 h-4 text-emerald-400" /> Workspace Boundaries</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">All file operations are restricted to approved workspace paths. Path traversal is blocked. Symlinks that escape boundaries are rejected. Denied directories: <code className="text-emerald-400">.ssh</code>, <code className="text-emerald-400">.aws</code>, <code className="text-emerald-400">.azure</code>, <code className="text-emerald-400">.gnupg</code>, <code className="text-emerald-400">.kube</code>. Emergency <strong>Kill Switch</strong> endpoint terminates all IDE connections instantly.</p>
                    </div>
                 </div>

                 <div className="shogun-card space-y-2">
                    <div className="font-bold text-shogun-text flex items-center gap-2"><Download className="w-4 h-4 text-emerald-400" /> VS Code Extension</div>
                    <p className="text-xs text-shogun-subdued leading-relaxed">Install the <strong>shogun-ide-bridge</strong> extension from <code className="text-emerald-400">bridge/vscode/</code>. Configure <code className="text-emerald-400">shogun.bridgeUrl</code> (default: <code className="text-emerald-400">ws://127.0.0.1:8000/api/v1/ide/bridge</code>). Commands: <strong>Shogun: Connect</strong>, <strong>Shogun: Disconnect</strong>, <strong>Shogun: Open Dashboard</strong>.</p>
                 </div>
              </section>

             {/* ═══════════════════════════════════════════════════════════════ */}
             {/* MADO (BROWSER AUTOMATION) */}
             {/* ═══════════════════════════════════════════════════════════════ */}
             <section id="ref-mado" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-cyan-400/40 pb-3">
                   <AppWindow className="w-6 h-6 text-cyan-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Mado — The Browser Layer</h4>
                      <p className="text-xs text-shogun-subdued">Secure browser automation. Your AI can browse the web, extract content, and take screenshots.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Globe className="w-4 h-4 text-cyan-400" /> Browse Web</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The Shogun can navigate to any URL using the <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">browse_web</code> native skill. It loads the full page via Playwright (a real browser engine), then extracts the content as readable text or raw HTML. You can optionally pass a CSS selector to target a specific element on the page.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Camera className="w-4 h-4 text-cyan-400" /> Screenshots</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">After navigating to a page, the Shogun can take a screenshot using <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">take_screenshot</code>. Choose between viewport-only or full-page capture. Screenshots are saved locally and can be used in mission reports or sent via Telegram.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Lock className="w-4 h-4 text-cyan-400" /> Security Integration</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Mado respects the active Torii tier or custom policy as enforced by ToolGate. Browser automation must be enabled in that policy's capability boundaries. In <strong>SHRINE</strong> tier, Mado is disabled entirely. In <strong>GUARDED</strong>, it's limited to 1 session with no downloads or uploads. In <strong>TACTICAL</strong> and above, broader Mado features can be available.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-cyan-400" /> Session Management</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Browser sessions are managed automatically. When Shogun shuts down, all active Playwright browser instances are cleanly closed. The Katana → Mado Browser tab shows the current session status and lets you manually manage active browser contexts.</p>
                   </div>
                   <div className="shogun-card space-y-2 md:col-span-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldAlert className="w-4 h-4 text-cyan-400" /> One Permission Authority</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Torii selects the governing tier or custom policy; ToolGate is the runtime permission authority for Mado. The active policy controls browser access, headless or visible mode, autonomous browsing, uploads, downloads, and session limits. Mado remains an operational console for runtime health, screenshots, resets, and diagnostics—it does not maintain a second permission system.</p>
                   </div>
                </div>

                {/* ── MADO PRACTICAL GUIDE ───────────────────────── */}
                <div className="mt-8 space-y-4">
                   <div className="text-xs font-bold text-cyan-400 uppercase tracking-widest pl-1 border-l-2 border-cyan-400/40 ml-1">Practical How-To Guide — Using Mado Step by Step</div>

                   {/* Step 1: Setup */}
                   <div className="shogun-card space-y-3 border-l-2 border-cyan-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><span className="text-cyan-400 font-mono text-sm">01</span> First-Time Setup — Install Chromium</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Before Mado can work, you need the browser engine. This is a <strong>one-time setup</strong>:</p>
                      <ol className="text-xs text-shogun-subdued space-y-1 ml-4 list-decimal">
                         <li>Navigate to <strong>Katana → Mado Browser</strong>.</li>
                         <li>If Chromium is not installed, you'll see a <strong>"Install Chromium"</strong> button in the top-right corner.</li>
                         <li>Click it. The system will download and install Playwright + Chromium (1–2 minutes depending on connection).</li>
                         <li>Once complete, the badge changes to a green <strong>"Chromium Ready"</strong> indicator with the version number.</li>
                      </ol>
                      <p className="text-xs text-shogun-subdued leading-relaxed mt-1"><strong>Security Note:</strong> Mado must be enabled in the active policy's browser capability boundary in <strong>ToolGate</strong>. The built-in <strong>SHRINE</strong> policy disables Mado. <strong>GUARDED</strong> allows one session with no downloads or uploads. <strong>TACTICAL</strong> and higher tiers can expose broader features, subject to the active policy's ToolGate rules.</p>
                   </div>

                   {/* Step 2: Automatic Session */}
                   <div className="shogun-card space-y-3 border-l-2 border-cyan-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><span className="text-cyan-400 font-mono text-sm">02</span> Let Shogun Manage the Browser</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">You do not need to create browser sessions manually. Shogun creates its managed browser profile automatically the first time a governed task calls <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">browse_web</code>.</p>
                      <ol className="text-xs text-shogun-subdued space-y-1 ml-4 list-decimal">
                         <li>Select the tier or custom policy in <strong>Torii</strong>, then review browser permissions in <strong>ToolGate</strong>.</li>
                         <li>Ask Shogun to browse, or run an AgentFlow containing a Mado Browser node.</li>
                         <li>Use <strong>Mado → Overview</strong> to inspect the managed session.</li>
                         <li>Use <strong>Reset</strong> only when the browser needs a clean profile.</li>
                      </ol>
                      <p className="text-xs text-shogun-subdued leading-relaxed mt-1"><strong>Advanced diagnostics</strong> lists runtime sessions and storage paths without adding another security configuration layer.</p>
                   </div>

                   {/* Scenario A: Chat-Driven Browsing */}
                   <div className="shogun-card space-y-3 border-l-2 border-emerald-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><span className="text-emerald-400 font-mono text-sm">A</span> Scenario: Browse the Web via Chat</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The easiest way to use Mado — just ask your Shogun in the chat. Behind the scenes, it uses the <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">browse_web</code> native skill.</p>
                      <div className="bg-shogun-bg rounded-lg p-3 space-y-2">
                         <p className="text-[10px] text-cyan-400/80 font-bold uppercase tracking-widest">Example Chat Prompts</p>
                         <div className="space-y-1">
                            <p className="text-xs text-shogun-text font-mono">"Browse https://news.ycombinator.com and give me the top 5 stories"</p>
                            <p className="text-xs text-shogun-text font-mono">"Go to https://example.com/pricing and extract the pricing table"</p>
                            <p className="text-xs text-shogun-text font-mono">"Visit https://github.com/trending and summarize what's popular today"</p>
                            <p className="text-xs text-shogun-text font-mono">"Browse https://weather.com and tell me the forecast for Copenhagen"</p>
                         </div>
                      </div>
                      <p className="text-xs text-shogun-subdued leading-relaxed"><strong>What happens:</strong> The Shogun launches a headless browser session (if not already running), navigates to the URL, auto-accepts cookie consent walls (Google/YouTube), extracts the page content as text, and returns it in the chat — up to 20,000 characters.</p>
                      <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Targeting specific content:</strong> Add a CSS selector to extract only what you need:</p>
                      <p className="text-xs text-shogun-text font-mono bg-shogun-bg rounded px-2 py-1">"Browse https://en.wikipedia.org/wiki/Shogun and extract the text from the #mw-content-text selector"</p>
                   </div>

                   {/* Scenario B: Take a Screenshot */}
                   <div className="shogun-card space-y-3 border-l-2 border-emerald-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><span className="text-emerald-400 font-mono text-sm">B</span> Scenario: Screenshot a Web Page</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">After browsing to a page, you can ask the Shogun to take a screenshot:</p>
                      <div className="bg-shogun-bg rounded-lg p-3 space-y-2">
                         <p className="text-[10px] text-cyan-400/80 font-bold uppercase tracking-widest">Example Chat Sequence</p>
                         <div className="space-y-1">
                            <p className="text-xs text-shogun-text font-mono">1. "Browse https://my-dashboard.example.com/analytics"</p>
                            <p className="text-xs text-shogun-text font-mono">2. "Now take a screenshot of this page"</p>
                            <p className="text-xs text-shogun-text font-mono">3. "Take a full-page screenshot" <span className="text-shogun-subdued">(captures entire scrollable page)</span></p>
                         </div>
                      </div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Screenshots are saved to the <strong>Mado → Screenshots</strong> tab with a timestamp. You can view all captured images there. Files are stored at <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">data/mado/screenshots/</code>.</p>
                   </div>

                   {/* Scenario C: Operational Console */}
                   <div className="shogun-card space-y-3 border-l-2 border-violet-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><span className="text-violet-400 font-mono text-sm">C</span> Scenario: Inspecting Browser Operations</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Use the Mado console to inspect browser work while ToolGate remains responsible for runtime permissions:</p>
                      <ol className="text-xs text-shogun-subdued space-y-1 ml-4 list-decimal">
                         <li><strong>Overview:</strong> Check Chromium, agent-browser health, and session count.</li>
                         <li><strong>Screenshots:</strong> Review evidence captured by chat and AgentFlow tasks.</li>
                         <li><strong>Advanced:</strong> Inspect runtime sessions and storage paths, or remove stale sessions.</li>
                         <li><strong>Torii:</strong> Select the tier or custom policy. <strong>ToolGate:</strong> Inspect or change its browser capability boundaries and runtime rules.</li>
                      </ol>
                      <p className="text-xs text-shogun-subdued leading-relaxed mt-1"><strong>Design principle:</strong> Torii selects the policy, ToolGate governs runtime permission, and Mado shows browser operations.</p>
                   </div>

                   {/* Scenario D: Agent Flow with Mado */}
                   <div className="shogun-card space-y-3 border-l-2 border-violet-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><span className="text-violet-400 font-mono text-sm">D</span> Scenario: Multi-Step Automation with Agent Flow</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">For complex workflows, combine Mado with Agent Flow — the visual workflow builder:</p>
                      <div className="bg-shogun-bg rounded-lg p-3 space-y-3">
                         <p className="text-[10px] text-cyan-400/80 font-bold uppercase tracking-widest">Example: Daily Competitor Price Check</p>
                         <div className="space-y-1 text-xs text-shogun-subdued">
                            <p><strong>Input Node →</strong> "Check competitor prices"</p>
                            <p><strong>Mado Browser Node →</strong> Navigate to competitor's pricing page</p>
                            <p><strong>Samurai Node →</strong> "Analyze the pricing data and compare to our current prices"</p>
                            <p><strong>Logic Node →</strong> If prices changed → proceed, else → skip</p>
                            <p><strong>Samurai Node →</strong> "Draft a summary email of pricing changes"</p>
                            <p><strong>Output Node →</strong> Final report</p>
                         </div>
                      </div>
                      <p className="text-xs text-shogun-subdued leading-relaxed mt-2">The <strong>Mado Browser node</strong> in Agent Flow supports: navigate to a URL, extract content (text/HTML), and take screenshots. Chain it with Samurai nodes for AI analysis and Logic nodes for conditional routing.</p>
                   </div>

                   {/* Scenario E: Form Filling */}
                   <div className="shogun-card space-y-3 border-l-2 border-amber-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><span className="text-amber-400 font-mono text-sm">E</span> Scenario: Filling Forms &amp; Clicking Elements</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Mado supports full interaction with web pages — not just reading them. Via the API, you can:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Fill forms:</strong> Provide a list of <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">{'{'}selector, value, type{'}'}</code> objects. Supports text inputs, dropdowns (<code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">select</code>), and checkboxes.</li>
                         <li><strong>Click elements:</strong> Click any element by CSS selector — buttons, links, menu items.</li>
                         <li><strong>Wait for elements:</strong> Pause until a specific CSS selector appears on the page (with configurable timeout).</li>
                         <li><strong>Execute JavaScript:</strong> Run custom JS scripts on the page for advanced extraction or interaction.</li>
                         <li><strong>Upload files:</strong> Upload a local file to a file input element (requires TACTICAL tier or higher).</li>
                         <li><strong>Download files:</strong> Capture a triggered download and save it locally (requires TACTICAL tier or higher).</li>
                      </ul>
                      <p className="text-xs text-shogun-subdued leading-relaxed mt-1">These actions are available through the REST API at <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">/api/v1/mado/sessions/{'{'}session_id{'}'}/fill-form</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">/click</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">/wait</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">/execute-js</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">/upload</code>, and <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">/download</code>.</p>
                   </div>

                   {/* Scenario F: PDF Generation */}
                   <div className="shogun-card space-y-3 border-l-2 border-amber-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><span className="text-amber-400 font-mono text-sm">F</span> Scenario: Generating PDFs from Web Pages</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Mado can convert any web page to a PDF document — useful for archiving, reports, or compliance evidence:</p>
                      <ol className="text-xs text-shogun-subdued space-y-1 ml-4 list-decimal">
                         <li>Navigate to the page you want to convert (via chat, AgentFlow, or API).</li>
                         <li>Call the PDF endpoint: <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">POST /api/v1/mado/sessions/{'{'}session_id{'}'}/pdf</code></li>
                         <li>The PDF is generated in A4 format with background colors and saved to <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">data/mado/downloads/</code>.</li>
                      </ol>
                      <p className="text-xs text-shogun-subdued leading-relaxed mt-1"><strong>Note:</strong> PDF generation only works in <strong>headless</strong> mode (Chromium limitation).</p>
                   </div>

                   {/* Profiles & Persistence */}
                   <div className="shogun-card space-y-3 border-l-2 border-cyan-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><span className="text-cyan-400 font-mono text-sm">💡</span> Understanding Browser Profiles</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Each session has a <strong>profile</strong> — a persistent directory on disk that stores cookies, local storage, cache, and login sessions. This means:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Logins persist:</strong> If you log into a website in session "research_agent", next time you use that profile, you're still logged in.</li>
                         <li><strong>Isolation:</strong> Different profiles don't share cookies or data — like using separate Chrome profiles.</li>
                         <li><strong>Cleanup:</strong> Delete a session to close the browser. The profile data stays on disk until you manually delete it from <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">data/mado/profiles/</code>.</li>
                      </ul>
                      <p className="text-xs text-shogun-subdued leading-relaxed mt-1"><strong>Storage paths</strong> are visible under <strong>Mado → Advanced</strong>. The agent-managed profile is created automatically and can be reset from Overview.</p>
                   </div>

                   {/* ToolGate Permissions */}
                   <div className="shogun-card space-y-3 border-l-2 border-red-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldAlert className="w-4 h-4 text-red-400" /> Configuring Mado Permissions</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Select the tier or custom policy in <strong>Torii</strong>, then configure its Mado boundaries in <strong>ToolGate</strong>. These rules apply consistently to chat, Telegram, the Mado API, and AgentFlow browser nodes.</p>
                      <div className="bg-shogun-bg rounded-lg p-3 space-y-2">
                         <p className="text-[10px] text-red-400/80 font-bold uppercase tracking-widest">ToolGate Capability Boundaries</p>
                         <ul className="text-xs text-shogun-subdued space-y-1 ml-2 list-disc">
                            <li><strong>Mado enabled:</strong> Allows or blocks browser automation entirely.</li>
                            <li><strong>Headless only:</strong> Prevents visible browser windows at restricted postures.</li>
                            <li><strong>Maximum sessions:</strong> Applies to API, agent-managed, and AgentFlow sessions.</li>
                            <li><strong>Autonomous browsing:</strong> Controls unattended browser work.</li>
                            <li><strong>Downloads and uploads:</strong> Governs file transfer through Mado.</li>
                         </ul>
                      </div>
                   </div>

                   {/* Troubleshooting */}
                   <div className="shogun-card space-y-3 border-l-2 border-red-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><span className="text-red-400 font-mono text-sm">⚠</span> Troubleshooting</div>
                      <ul className="text-xs text-shogun-subdued space-y-2 ml-4 list-disc">
                         <li><strong>"Browser automation is disabled"</strong> — The active policy's ToolGate boundary does not allow Mado. Use <strong>Torii</strong> to select an appropriate tier or custom policy, then inspect <strong>ToolGate → Capability Boundaries</strong>. The built-in GUARDED tier allows one restricted session; TACTICAL and higher can expose broader features.</li>
                         <li><strong>"No active browser session"</strong> — For chat skills (<code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">take_screenshot</code>), you must first use <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">browse_web</code> to navigate to a page.</li>
                         <li><strong>Chromium not installed</strong> — Click "Install Chromium" on the Mado page. Requires internet access for the initial download (~200 MB).</li>
                         <li><strong>Session shows "idle" forever</strong> — The browser launches lazily. It only starts when you perform an action (navigate, screenshot, etc.). This is normal.</li>
                         <li><strong>Visible mode blocked</strong> — The active policy's Mado boundary may enforce headless-only browsing. Campaign- or Ronin-based policies can permit visible sessions when ToolGate enables them.</li>
                      </ul>
                   </div>
                </div>
             </section>


             {/* ═══════════════════════════════════════════════════════════════ */}

              {/* ═══════════════════════════════════════════════════════════════ */}
              {/* RONIN (DESKTOP CONTROL) */}
              {/* ═══════════════════════════════════════════════════════════════ */}
              <section id="ref-ronin" className="space-y-6 scroll-mt-6">
                 <div className="flex items-center gap-3 border-b-2 border-orange-400/40 pb-3">
                    <Crosshair className="w-6 h-6 text-orange-400" />
                    <div>
                       <h4 className="text-xl font-bold uppercase tracking-widest">Ronin - Desktop Control Layer</h4>
                       <p className="text-xs text-shogun-subdued">Governed desktop automation: mouse, keyboard, screenshots, native apps, and OS interaction.</p>
                    </div>
                 </div>

                 <div className="shogun-card bg-red-500/10 border-red-500/30 border-l-4 border-l-red-500">
                    <h5 className="text-sm font-bold text-red-500 flex items-center gap-2 mb-3">
                       <ShieldAlert className="w-5 h-5" />
                       CRITICAL: Understand the Repercussions Before Enabling
                    </h5>
                    <div className="space-y-3 text-xs text-shogun-subdued leading-relaxed">
                       <p><strong className="text-red-400">Ronin can give an AI agent direct desktop input control.</strong> This is not a sandbox boundary. When separately enabled under the RONIN tier, registered capabilities can move the mouse, press keys, capture the screen, and interact with permitted native applications. The built-in Ronin action registry does not provide a general shell-command capability, and all actions remain subject to runtime policy. This differs from browser automation (Mado), which operates through a controlled Chromium session.</p>
                       <div className="bg-[#050508] rounded-lg p-3 border border-red-500/20 space-y-2">
                          <p className="text-red-400 font-bold text-[10px] uppercase tracking-widest">What can go wrong:</p>
                          <ul className="ml-4 list-disc space-y-1.5">
                          <li><strong className="text-red-400">Data Loss:</strong> Approved desktop actions or in-application clicks can still overwrite or remove data. Explicitly classified deletion and mutating raw GUI primitives require approval under the built-in policy, but raw coordinates cannot prove the semantic effect of a click and approval does not guarantee that the intended target is correct.</li>
                          <li><strong className="text-red-400">Credential Exposure:</strong> Explicit credential-entry operations and applications classified as forbidden remain blocked by the built-in policy; raw typing is treated as high risk and requires approval. The runtime cannot understand every field solely from coordinates, so do not place secrets on screen or approve typing without verifying the focused control.</li>
                          <li><strong className="text-red-400">Financial Damage:</strong> Critical actions are blocked and sensitive applications require approval under the built-in policy, but approved interactions can still be irreversible. Independently verify every transaction before authorising it.</li>
                          <li><strong className="text-red-400">Software Installation:</strong> Explicitly classified software installation remains approval-required. Review the source, signature, arguments, requested privileges, and destination before approving any launcher or raw GUI action that could install software.</li>
                          <li><strong className="text-red-400">Admin Escalation:</strong> Explicit administrative escalation is disabled by the built-in policy. Do not weaken this control or approve a raw GUI action near an elevation prompt without an independent security review.</li>
                          <li><strong className="text-red-400">External Data Upload:</strong> Explicitly classified external uploads remain approval-required. Browser and Office automation have separate approval controls; raw GUI coordinates cannot identify every destination, so verify the focused application, destination, and data before approving.</li>
                          </ul>
                       </div>
                       <p className="text-red-400 font-bold">Rule of thumb: If you would not give a stranger supervised access to the current desktop and data, do not enable Ronin Desktop Control on that machine. Prefer a disposable, isolated environment.</p>
                    </div>
                 </div>

                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Shield className="w-4 h-4 text-orange-400" /> Posture Levels</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Ronin&apos;s policy schema defines six desktop capability states. The standard activation path is narrower: every built-in tier leaves desktop automation disabled, and only the RONIN tier permits an operator to enable <code>desktop_full</code> through a separate warning confirmation.</p>
                       <div className="bg-shogun-bg rounded-lg p-3 space-y-2">
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-[#7a8899] bg-[#7a8899]/10 px-2 py-0.5 rounded">DISABLED</span><span className="text-xs text-shogun-subdued">The built-in default for SHRINE, GUARDED, TACTICAL, CAMPAIGN, and RONIN until separate desktop enablement.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-shogun-blue bg-shogun-blue/10 px-2 py-0.5 rounded">OBSERVE ONLY</span><span className="text-xs text-shogun-subdued">Screenshots and window listing only. Read-only.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-green-400 bg-green-400/10 px-2 py-0.5 rounded">BROWSER ONLY</span><span className="text-xs text-shogun-subdued">Playwright/Mado browser control only. No desktop.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-orange-400 bg-orange-400/10 px-2 py-0.5 rounded">DESKTOP LIMITED</span><span className="text-xs text-shogun-subdued">A policy-schema state for scoped mouse, keyboard, and screenshots; it is not automatically activated by TACTICAL.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-red-400 bg-red-400/10 px-2 py-0.5 rounded">DESKTOP FULL</span><span className="text-xs text-shogun-subdued">Broad registered native-app, mouse, keyboard, and screen capabilities after separate operator enablement under RONIN. General shell execution and administrative escalation remain disabled; protected applications, verification, approval, and critical-action gates remain enforced. <strong className="text-red-400">HIGH RISK.</strong></span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-purple-400 bg-purple-400/10 px-2 py-0.5 rounded">ADMIN APPROVAL REQUIRED</span><span className="text-xs text-shogun-subdued">An internal schema state; it does not override the built-in <code>ronin_admin_escalation: false</code> control.</span></div>
                       </div>
                    </div>
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Crosshair className="w-4 h-4 text-orange-400" /> Where to Configure</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Torii selects the governing tier or custom policy. Its inherited desktop ceiling and explicit Ronin boundaries are shown and governed in ToolGate; Ronin cannot widen them from its operational console.</p>
                       <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                          <li><strong>SHRINE / GUARDED / TACTICAL / CAMPAIGN:</strong> Ronin Desktop Control is disabled by the built-in tier constraints.</li>
                          <li><strong>RONIN:</strong> The tier makes the desktop_full posture eligible, but desktop control remains off until separately enabled with an explicit confirmation. The built-in policy keeps credential entry and administrative escalation blocked; file deletion, external uploads, and software installation require approval; high-risk verification and critical-action gates remain active.</li>
                       </ul>
                       <p className="text-xs text-shogun-subdued leading-relaxed">After selecting a tier, the Ronin constraints appear in the Current Constraints card on the left side of Torii (Ronin Desktop, Ronin Sessions, Mouse/Keyboard).</p>
                    </div>
                 </div>

                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Lock className="w-4 h-4 text-orange-400" /> Application Trust Levels</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Known applications in the registry are assigned one of four trust levels; an unknown process defaults to RESTRICTED rather than being treated as trusted. Posture Guard combines the active policy, registered capability, application trust, and detected environment when evaluating a request.</p>
                       <div className="bg-shogun-bg rounded-lg p-3 space-y-2">
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-green-400 bg-green-400/10 px-2 py-0.5 rounded">TRUSTED</span><span className="text-xs text-shogun-subdued">VS Code, Notepad, Calculator, Shogun. Safe to interact.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-yellow-400 bg-yellow-400/10 px-2 py-0.5 rounded">RESTRICTED</span><span className="text-xs text-shogun-subdued">Chrome, Excel, PowerPoint. Some caution required.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-orange-400 bg-orange-400/10 px-2 py-0.5 rounded">SENSITIVE</span><span className="text-xs text-shogun-subdued">Outlook, SAP, Salesforce, CRM. Requires elevated posture.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-red-400 bg-red-400/10 px-2 py-0.5 rounded">FORBIDDEN</span><span className="text-xs text-shogun-subdued">Password managers, banking apps, and crypto wallets are examples. A process classified FORBIDDEN is denied by Posture Guard; registry coverage and foreground detection must still be verified.</span></div>
                       </div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">The trust registry comes pre-populated with 50+ applications. View and filter them on the App Trust tab in Ronin.</p>
                    </div>
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldAlert className="w-4 h-4 text-red-400" /> Komainu Guardian (Physical Override)</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Komainu is a software input listener. While it is running and receiving operating-system mouse or keyboard events, it can request a pause, termination, or Harakiri response according to the configured level. It is not a hardware interlock and may be unavailable or interrupted.</p>
                       <div className="bg-shogun-bg rounded-lg p-3 space-y-2">
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-yellow-400 bg-yellow-400/10 px-2 py-0.5 rounded">LEVEL 1: PAUSE</span><span className="text-xs text-shogun-subdued">Any human input pauses the active Ronin session. Resume manually.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-orange-400 bg-orange-400/10 px-2 py-0.5 rounded">LEVEL 2: TERMINATE</span><span className="text-xs text-shogun-subdued">Any human input kills the active session immediately.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-red-400 bg-red-400/10 px-2 py-0.5 rounded">LEVEL 3: HARAKIRI</span><span className="text-xs text-shogun-subdued">Any human input activates the global kill switch and requests cancellation of supported active work.</span></div>
                       </div>
                       <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Triple-Escape:</strong> while the Komainu listener is running and receiving keyboard events, pressing Escape three times within 1.5 seconds requests Harakiri. Ronin/Komainu is unavailable in Server mode; verify the listener and kill switch before relying on this control.</p>
                    </div>
                 </div>

                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Zap className="w-4 h-4 text-orange-400" /> Capabilities Registry</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">20+ registered actions organized by category. Each has a risk level, minimum posture requirement, and an approval flag. View them on the Capabilities tab in Ronin.</p>
                       <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                          <li><strong>Desktop:</strong> screenshot, click, move_mouse, type, hotkey, locate_image, read_screen</li>
                          <li><strong>Browser:</strong> open, click, type, extract, screenshot (bridges to Mado)</li>
                          <li><strong>OS:</strong> list_windows, focus_window, get_foreground_app</li>
                       </ul>
                    </div>
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><MonitorIcon className="w-4 h-4 text-orange-400" /> Environment Detection</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Ronin automatically detects the environment type at startup. This affects which posture policies are allowed.</p>
                       <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                          <li><strong>Physical Machine:</strong> Your real hardware. Highest risk surface.</li>
                          <li><strong>VM:</strong> VirtualBox, VMware, Hyper-V. Recommended for full desktop posture.</li>
                          <li><strong>Sandbox:</strong> Windows Sandbox, Docker. Safe for testing.</li>
                          <li><strong>Remote Desktop:</strong> RDP sessions. Higher latency, lower risk.</li>
                          <li><strong>Citrix / Cloud Workspace:</strong> Enterprise environments.</li>
                       </ul>
                    </div>
                 </div>

                 <div className="shogun-card space-y-3 border-l-4 border-l-red-500">
                    <div className="font-bold text-shogun-text flex items-center gap-2"><AlertCircle className="w-4 h-4 text-red-400" /> Tier-by-Tier Ronin Repercussions</div>
                    <p className="text-xs text-shogun-subdued leading-relaxed">This table shows exactly what the AI can do at each security tier. <strong className="text-red-400">Read this carefully before changing your posture.</strong></p>
                    <div className="bg-shogun-bg rounded-lg overflow-hidden border border-shogun-border">
                       <table className="w-full text-xs">
                          <thead>
                             <tr className="border-b border-shogun-border">
                                <th className="text-left p-2.5 text-shogun-subdued font-bold uppercase tracking-widest text-[10px]">Dangerous Action</th>
                                <th className="text-center p-2.5 text-shogun-blue font-bold uppercase tracking-widest text-[10px]">Tactical</th>
                                <th className="text-center p-2.5 text-orange-400 font-bold uppercase tracking-widest text-[10px]">Campaign</th>
                                <th className="text-center p-2.5 text-red-400 font-bold uppercase tracking-widest text-[10px]">Ronin</th>
                             </tr>
                          </thead>
                          <tbody className="text-shogun-subdued">
                             <tr className="border-b border-shogun-border/50"><td className="p-2.5">Credential Entry</td><td className="text-center p-2.5 text-red-400">Blocked</td><td className="text-center p-2.5 text-red-400">Blocked</td><td className="text-center p-2.5 text-red-400">Blocked</td></tr>
                             <tr className="border-b border-shogun-border/50"><td className="p-2.5">File Deletion</td><td className="text-center p-2.5 text-red-400">Blocked</td><td className="text-center p-2.5 text-yellow-400">Approval</td><td className="text-center p-2.5 text-yellow-400">Approval</td></tr>
                             <tr className="border-b border-shogun-border/50"><td className="p-2.5">External Uploads</td><td className="text-center p-2.5 text-red-400">Blocked</td><td className="text-center p-2.5 text-yellow-400">Approval</td><td className="text-center p-2.5 text-yellow-400">Approval</td></tr>
                             <tr className="border-b border-shogun-border/50"><td className="p-2.5">Software Install</td><td className="text-center p-2.5 text-red-400">Blocked</td><td className="text-center p-2.5 text-yellow-400">Approval</td><td className="text-center p-2.5 text-yellow-400">Approval</td></tr>
                             <tr className="border-b border-shogun-border/50"><td className="p-2.5">Native App Interaction</td><td className="text-center p-2.5 text-red-400">Blocked</td><td className="text-center p-2.5 text-green-400">Allowed</td><td className="text-center p-2.5 text-green-400">Allowed</td></tr>
                             <tr className="border-b border-shogun-border/50"><td className="p-2.5">Shell Commands</td><td className="text-center p-2.5 text-red-400">Blocked</td><td className="text-center p-2.5 text-green-400">Allowed</td><td className="text-center p-2.5 text-green-400">Allowed</td></tr>
                             <tr><td className="p-2.5 font-bold text-red-400">Admin Escalation (UAC)</td><td className="text-center p-2.5 text-red-400">Blocked</td><td className="text-center p-2.5 text-red-400">Blocked</td><td className="text-center p-2.5 text-red-400">Blocked</td></tr>
                          </tbody>
                       </table>
                    </div>
                    <p className="text-xs text-red-400 font-bold leading-relaxed">RONIN is the highest-autonomy built-in tier, not a removal of safety controls. Desktop control requires separate enablement; credential entry and administrative escalation remain blocked; deletion, uploads, installation, Office send, macros, and external Office actions retain approval gates. Use RONIN only in a controlled, preferably isolated test environment and verify the effective policy before relying on it.</p>
                 </div>

                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Crosshair className="w-4 h-4 text-orange-400" /> Dashboard Tabs</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">The Ronin page has 5 tabs:</p>
                       <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                          <li><strong>Control:</strong> Status cards, environment detection panel, and a Quick Action executor for manual desktop commands.</li>
                          <li><strong>Sessions:</strong> Create and manage desktop sessions. Choose posture level and Komainu guardian level per session.</li>
                          <li><strong>App Trust:</strong> View the pre-classified trust registry. Filter by trust level.</li>
                          <li><strong>Capabilities:</strong> View all registered desktop actions with risk levels and posture requirements.</li>
                          <li><strong>Audit Trail:</strong> Chronological feed of all Ronin events with severity coloring.</li>
                       </ul>
                    </div>
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Power className="w-4 h-4 text-red-400" /> Emergency Controls</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Multiple layers of emergency shutdown:</p>
                       <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                          <li><strong className="text-red-400">STOP Button:</strong> The red skull button in the Ronin header. Triggers Harakiri.</li>
                          <li><strong className="text-red-400">Triple-Escape:</strong> While the Komainu listener is running and receiving keyboard events, three Escapes within 1.5 seconds request Harakiri. Verify the listener before relying on it.</li>
                          <li><strong className="text-yellow-400">Komainu Override:</strong> Any human mouse or keyboard input triggers the configured level.</li>
                          <li><strong className="text-red-400">Torii Harakiri:</strong> The global kill switch on the Torii page. Blocks new governed operations and requests best-effort cancellation of supported active work.</li>
                       </ul>
                    </div>
                 </div>
              </section>

              {/* ─── SKILLOPT ─── */}
              <section id="ref-skillopt" className="space-y-6 scroll-mt-6">
                 <div className="flex items-center gap-3 border-b-2 border-fuchsia-400/40 pb-3">
                    <BrainCircuit className="w-6 h-6 text-fuchsia-400" />
                    <div>
                       <h4 className="text-xl font-bold uppercase tracking-widest">SkillOpt — Automated Skill Optimization</h4>
                       <p className="text-xs text-shogun-subdued">Data-driven skill improvement pipeline — version management, training runs, candidate generation, validation, and promotion.</p>
                    </div>
                 </div>

                 <div className="shogun-card space-y-3">
                    <div className="font-bold text-shogun-text flex items-center gap-2"><GitMerge className="w-4 h-4 text-fuchsia-400" /> The Optimization Pipeline</div>
                    <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Usage Events</strong> are captured from Active Skill runs. A <strong>Training Run</strong> uses these to generate optimized <strong>Candidates</strong>. Each candidate is <strong>Validated</strong> against held-out tasks with safety checks and scoring. Successful candidates are <strong>Promoted</strong> to become the new active version; failing ones are <strong>Rejected</strong> with a reason.</p>
                 </div>

                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="shogun-card space-y-2 border-l-2 border-fuchsia-400/40">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Layers className="w-4 h-4 text-fuchsia-400" /> Version Management</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Every skill change creates a versioned snapshot with a version number, content hash, validation score, and status (<code className="text-fuchsia-400">candidate</code> → <code className="text-fuchsia-400">active</code> → <code className="text-fuchsia-400">retired</code>). Browse retained versions for any skill from the SkillOpt tab in <strong>Katana</strong>. Compare candidate versus baseline content with the interactive diff viewer.</p>
                    </div>
                    <div className="shogun-card space-y-2 border-l-2 border-fuchsia-400/40">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-fuchsia-400" /> Katana Dashboard</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">The SkillOpt tab in <strong>Katana</strong> provides real-time tracking of optimization runs, interactive diff viewer for candidates vs baseline, one-click promote/reject controls, and metrics for average improvement scores. Start training runs, view all skill versions, and monitor usage events.</p>
                    </div>
                 </div>
              </section>

             {/* 10. TORII (SECURITY) */}
             {/* ═══════════════════════════════════════════════════════════════ */}
             <section id="ref-torii" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-red-400/40 pb-3">
                   <Lock className="w-6 h-6 text-red-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Torii — Security Portal</h4>
                      <p className="text-xs text-shogun-subdued">Select the active built-in tier or custom posture. Custom postures are created, edited, and deleted in ToolGate, then become available here immediately.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-red-400" /> Security Posture (Left Column)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Five clickable tiers, from safest to most dangerous:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>SHRINE (MAX):</strong> Zero-trust. Local only. No external tools. Maximum safety.</li>
                         <li><strong>GUARDED:</strong> Restricted network. Only approved tools. Everything needs human approval.</li>
                         <li><strong>TACTICAL (DEFAULT):</strong> Balanced autonomy. The AI has scoped file access and can use approved tools on its own.</li>
                         <li><strong>CAMPAIGN:</strong> High autonomy. Broad internet access. Agents can auto-spawn without asking.</li>
                         <li><strong>RONIN (HIGH RISK):</strong> Highest governed autonomy. Critical blocks, approvals, verification, and separate Ronin Desktop enablement remain; prefer an isolated test environment.</li>
                      </ul>
                      <p className="text-xs text-shogun-subdued leading-relaxed mt-2">Click a built-in tier or custom posture to activate it. Built-in tiers are protected presets. Use <strong>Manage custom postures in ToolGate</strong> to create or maintain reusable postures. If you edit an active built-in tier directly in ToolGate, Shogun automatically creates and activates a custom copy.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Lock className="w-4 h-4 text-red-400" /> Unified Posture Selector</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Built-in tiers and every custom posture from ToolGate appear in the same selection grid. The active marker reflects the policy actually enforced at runtime. Selecting a built-in tier clears any previous custom assignment; selecting a custom posture activates that policy together with its inherited base tier.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-red-400" /> Current Constraints</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The constraints panel summarizes the effective filesystem, network, shell, skills, delegation, communications, browser, and desktop limits. For a custom posture these values come from its base tier and ToolGate capability boundaries—not from whichever posture happened to be selected previously.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-red-500" /> Harakiri Button</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The red button in the top right of the Torii page. Same as the one on the Dashboard — activates the global kill switch. It requires two-step confirmation, blocks new governed operations, requests best-effort cancellation of supported active work, and locks the posture to SHRINE. Verify external processes separately. Press "Reset Harakiri" to restore normal operation.</p>
                   </div>
                </div>
             </section>

             {/* ═══════════════════════════════════════════════════════════════ */}
             {/* TOOLGATE (RUNTIME PERMISSIONS) */}
             {/* ══════════════════════════════════════════════════════════════ */}
             <section id="ref-toolgate" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-orange-400/40 pb-3">
                   <Shield className="w-6 h-6 text-orange-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">ToolGate — Runtime Permissions</h4>
                      <p className="text-xs text-shogun-subdued">The single place to edit runtime security. Every setting is locally editable.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2 md:col-span-2 border-l-2 border-orange-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Layers className="w-4 h-4 text-orange-400" /> Ownership Model</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Torii</strong> selects the active built-in tier or custom posture. <strong>ToolGate</strong> owns custom posture creation, editing, deletion, capability ceilings, and per-call runtime authorization. Saving a change while a protected built-in tier is active automatically creates and activates a custom copy, so the built-in preset stays intact. <strong>Katana</strong> manages installed or connected capabilities, model providers and routing, and account-specific scopes. <strong>Shogun Profile</strong> owns identity, behavior, and operations—not security configuration.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Lock className="w-4 h-4 text-orange-400" /> Custom Posture Library</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Create, edit, and delete reusable custom postures in ToolGate. Each posture has a name, description, inherited base tier, kill-switch and dry-run flags, and detailed capability boundaries. Newly created postures appear immediately in Torii. Directly editing an active built-in tier is the exception: ToolGate automatically creates and activates its custom copy before saving the change. Deleting an active custom posture safely returns Torii to its base tier.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-orange-400" /> Policy-Scoped Rules</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">ToolGate always follows the currently active policy. A built-in tier uses its own scope. A custom policy uses a stable policy-specific scope and inherits its base tier's default risk mode. Switching tiers or custom policies loads that scope's own capability boundaries, tool overrides, and advanced content rules.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-orange-400" /> Capability Boundaries &amp; Risk</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The capability panel explains the policy ceiling for filesystem, network, shell, skills, subagents, memory, communications, workflows, browser, visual intake, IDE, and related features. The <strong>Capability Risk Index</strong> summarizes exposure from 0–100. Built-in presets remain protected, but their displayed settings are editable in standalone Tenshu because the first save automatically creates and activates a custom copy.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldAlert className="w-4 h-4 text-orange-400" /> Effective Tool Policy</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Every registered tool shows its effective <strong>ALLOW</strong>, <strong>CONFIRM</strong>, or <strong>BLOCK</strong> verdict, risk class, source, and reason. Local overrides may narrow a policy. They cannot widen an enclosing capability boundary.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Zap className="w-4 h-4 text-orange-400" /> Simulator, Approvals &amp; Audit</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Use the simulator to preview a tool call with its actual parameters before running it. Calls that require confirmation enter the approval queue and fail closed on denial or timeout. Instrumented decisions preserve their policy source in governance event records.</p>
                   </div>
                   <div className="shogun-card space-y-2 md:col-span-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><SlidersHorizontal className="w-4 h-4 text-orange-400" /> Advanced Content Controls</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Turn on <strong>Advanced mode</strong> to flag specific words or phrases inside nested tool arguments. Each rule can match a phrase anywhere or as a whole word, be case-sensitive or case-insensitive, apply to every tool or one selected tool, and return <strong>CONFIRM</strong> or <strong>BLOCK</strong>. Advanced rules are scoped to the active tier or custom policy and can only tighten the final verdict.</p>
                   </div>
                </div>
             </section>

             {/* ═══════════════════════════════════════════════════════════════ */}
             {/* 8. KAIZEN (GOVERNANCE) */}
             {/* ═══════════════════════════════════════════════════════════════ */}
             <section id="ref-kaizen" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-blue/40 pb-3">
                   <ShieldCheck className="w-6 h-6 text-shogun-gold" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Kaizen — The Constitutional Layer</h4>
                      <p className="text-xs text-shogun-subdued">Define the fundamental laws and ethical boundaries for all agents. Has 2 tabs.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-shogun-gold" /> Constitution Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">A full-screen YAML code editor where you write the "Constitution" — the AI's core laws. The system validates the YAML in real time (green dot = correct syntax, red = error with details). On the right sidebar, <strong>Active Principles</strong> are extracted from the YAML and shown as colored cards: red (Critical), orange (High), gold (Balanced), blue (Medium), green (Low). Click <strong>"Publish Edicts"</strong> to save your changes — a new revision is created automatically.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-shogun-gold" /> The Mandate Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">A Markdown editor for writing the Shogun's "Mission Statement." This is a free-form document defining objectives and operating principles. Use the <strong>Edit/Preview</strong> toggle to switch between writing mode and rendered mode. Key sections of this document are automatically injected into the AI's system prompt on every interaction, so if you write "Always respond in Danish" here, the AI will obey.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><RefreshCw className="w-4 h-4 text-shogun-gold" /> Revision History</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">On the right sidebar (both tabs). Shows a timeline of every saved version of the Constitution or Mandate. Each entry shows the version number, change summary, and date. The most recent version is highlighted.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Download className="w-4 h-4 text-shogun-gold" /> Download Audit Log</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">At the bottom of the sidebar. Downloads available governance-change records as JSON for review. Export contents depend on captured and retained events and do not prove a complete change history.</p>
                   </div>
                </div>
             </section>

             {/* ═══════════════════════════════════════════════════════════════ */}
             {/* 9. BUSHIDO (REFLECTION ENGINE) */}
             {/* ═══════════════════════════════════════════════════════════════ */}
             <section id="ref-bushido" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-blue/40 pb-3">
                   <RefreshCw className="w-6 h-6 text-shogun-blue" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Bushido — The Reflection Engine</h4>
                      <p className="text-xs text-shogun-subdued">Automated self-improvement cycles where the AI analyzes its own performance.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-shogun-blue" /> Calibration Controls</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Three dials that control the Shogun's self-improvement behavior: <strong>Reflection Frequency</strong> (how often the system thinks about its own performance), <strong>Consolidation Threshold</strong> (when to compress old memories), and <strong>Exploration Budget</strong> (how willing the system is to try new approaches). Each has a slider and a plain-English description.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Sparkles className="w-4 h-4 text-shogun-blue" /> Insight Stream</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">A live feed of AI-generated suggestions. The system autonomously analyzes its own behavior and posts insights like "Model X is 2x faster for code tasks" or "Memory #412 hasn't been used in 30 days — consider archiving." Each insight has a severity badge and a timestamp.</p>
                   </div>
                   <div className="shogun-card space-y-2 md:col-span-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><RefreshCw className="w-4 h-4 text-shogun-blue" /> Reflection Trigger</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">A button to manually trigger a reflection cycle. The system will analyze recent interactions, evaluate model performance, check memory health, and produce a set of actionable insights. Results appear in the Insight Stream.</p>
                   </div>
                </div>
             </section>

             {/* ═══════════════════════════════════════════════════════════════ */}
             {/* 6. ARCHIVES (MEMORY) */}
             {/* ═══════════════════════════════════════════════════════════════ */}
             <section id="ref-archives" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-gold/40 pb-3">
                   <Database className="w-6 h-6 text-shogun-gold" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Archives — The Memory Vault</h4>
                      <p className="text-xs text-shogun-subdued">Everything the Shogun has ever learned, remembered, or been told.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Search className="w-4 h-4 text-shogun-gold" /> Semantic Search Bar</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Type a question or topic and the system finds matching memories using AI-powered "meaning" search — not just keyword matching. For example, searching "customer complaints" can also return memories about "user feedback" or "product issues." Results are ranked by relevance.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Layers className="w-4 h-4 text-shogun-gold" /> Memory Types</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Memories are categorized into types:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Semantic:</strong> Facts and knowledge (e.g., "The capital of France is Paris").</li>
                         <li><strong>Episodic:</strong> Experiences and events (e.g., "User asked about pricing on April 15").</li>
                         <li><strong>Procedural:</strong> How-to instructions and workflows.</li>
                         <li><strong>Persona:</strong> Durable identity, relationship, and communication context.</li>
                         <li><strong>Skills:</strong> Canonical achieved-skill content synchronized from the Dojo.</li>
                         <li><strong>Programming:</strong> Reusable coding solutions with evidence, validation, files, languages, and sources.</li>
                      </ul>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Star className="w-4 h-4 text-shogun-gold" /> Salience Score</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Each memory has relevance and importance signals that influence retrieval. Frequently reused memories can be reinforced, while decay policies control retention: <strong>fast</strong>, <strong>medium</strong>, <strong>slow</strong>, <strong>sticky</strong>, or <strong>pinned</strong>. Pin critical memories to keep them at maximum priority.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Sparkles className="w-4 h-4 text-shogun-gold" /> Inscribe Memory (+ Button)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Click the "+" button to manually add a new memory. You choose the <strong>type</strong> (semantic, episodic, etc.), write the <strong>content</strong>, and optionally set the <strong>salience</strong>. This is useful for injecting facts, rules, or context that the AI should always know about.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-shogun-gold" /> Browse, Filter &amp; Lifecycle</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Filter by memory type, decay policy, or agent, then sort chronologically or by salience/importance. Each card exposes its content, provenance, scores, dates, and tags. Normal memories move to the archive instead of being hard-deleted; Programming memories use an explicit permanent-delete action.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Download className="w-4 h-4 text-shogun-gold" /> Import &amp; Export</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Import Memories</strong> accepts OpenClaw exports, Shogun exports, and generic Markdown from files, ZIP archives, or folders. It parses input as inert data, validates a preview, reports duplicates/conflicts, supports embedding retries and rollback, and blocks ZIP path traversal.</p>
                      <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Export Memory</strong> creates an OpenClaw-compatible Markdown bundle. Scope and filter by agent, project, memory type, date, and minimum importance; optionally include archived, private, sticky, analysis, raw, or secret-bearing content. Sensitive exports require confirmation and remain available in export history.</p>
                   </div>
                   <div className="shogun-card space-y-2 md:col-span-2 border-l-2 border-shogun-gold/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><BrainCircuit className="w-4 h-4 text-shogun-gold" /> Self-Reinforced Learning</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">In Mission Mode, Shogun is instructed to proactively retain durable guidance when you explicitly correct it, tool use reveals verified information likely to help future work, or you confirm a reusable decision, preference, or idea. It must avoid transient, speculative, duplicated, sensitive, or task-local material and record source and confidence where applicable.</p>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Two cases also have dedicated automatic capture: explicit operator corrections become durable semantic memories, and completed Mado web research becomes a sourced procedural memory. Existing matches are reused or reinforced instead of blindly duplicated. Governed Chat mechanically captures explicit corrections but cannot browse or use Mission tools.</p>
                   </div>
                   <div className="shogun-card space-y-4 md:col-span-2 border-l-2 border-shogun-blue/50">
                      <div>
                         <div className="font-bold text-shogun-text flex items-center gap-2"><Network className="w-4 h-4 text-shogun-blue" /> How the New Memory System Works</div>
                         <p className="mt-2 text-xs text-shogun-subdued leading-relaxed">Shogun now uses three cooperating layers. Your existing Archive memories stay in place; the graph adds connections and safer retrieval around them.</p>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                         <div className="rounded border border-shogun-border bg-shogun-bg/40 p-3 space-y-1">
                            <div className="text-xs font-bold text-shogun-gold">Phase 1 — Scoped Recall</div>
                            <p className="text-xs text-shogun-subdued leading-relaxed">First, Shogun limits the search to memories the current user and agent are allowed to access within the relevant workspace, project, workflow, conversation, and topic.</p>
                         </div>
                         <div className="rounded border border-shogun-border bg-shogun-bg/40 p-3 space-y-1">
                            <div className="text-xs font-bold text-shogun-gold">Phase 2 — MemoryGraph</div>
                            <p className="text-xs text-shogun-subdued leading-relaxed">Next, Kiroku connects related memories to the people, agents, projects, workflows, conversations, and topics they belong to. It can also track when one memory supersedes or conflicts with another.</p>
                         </div>
                         <div className="rounded border border-shogun-border bg-shogun-bg/40 p-3 space-y-1">
                            <div className="text-xs font-bold text-shogun-gold">Phase 3 — Governed Retrieval</div>
                            <p className="text-xs text-shogun-subdued leading-relaxed">Finally, Shogun starts with the best meaning-based matches, follows only approved graph connections, removes stale or conflicting material, applies ToolGate policy checks, and builds a small, auditable context pack for the answer.</p>
                         </div>
                      </div>
                      <div className="rounded border border-emerald-500/30 bg-emerald-500/5 p-3 space-y-1">
                         <div className="text-xs font-bold text-emerald-400 flex items-center gap-2"><ShieldCheck className="w-4 h-4" /> Safe Migration</div>
                         <p className="text-xs text-shogun-subdued leading-relaxed">No existing Archive memory is replaced or discarded. The graph is built alongside the current memory store and can run in shadow mode before it becomes active. Graph relationships never override access rules, and cross-agent memory sharing stays off unless an operator explicitly enables it.</p>
                      </div>
                      <div className="rounded border border-shogun-border bg-shogun-bg/40 p-3 space-y-1">
                         <div className="text-xs font-bold text-shogun-text flex items-center gap-2"><GitMerge className="w-4 h-4 text-shogun-blue" /> Recommended Rollout</div>
                         <p className="text-xs text-shogun-subdued leading-relaxed">Upgrade the database first, backfill the graph from existing memories, enable dual writing, observe graph retrieval in shadow mode, and switch it to active only after the results have been verified. This makes the migration gradual and reversible.</p>
                      </div>
                   </div>
                </div>
             </section>

             {/* ═══════════════════════════════════════════════════════════════ */}
             {/* 7. DOJO (TRAINING HALL) */}
             {/* ═══════════════════════════════════════════════════════════════ */}
             <section id="ref-dojo" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-gold/40 pb-3">
                   <Flame className="w-6 h-6 text-shogun-gold" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Dojo — The Training Hall</h4>
                      <p className="text-xs text-shogun-subdued">Browse, study, and certify your agents on 4,000+ skills. Has 4 tabs.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Search className="w-4 h-4 text-shogun-gold" /> Catalog Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The default tab. Shows every available skill from the OpenClaw College database. Each skill shows its <strong>name</strong>, <strong>risk tier</strong> (Low, Medium, High, Critical), and faculty category. A sidebar shows faculty categories in a collapsible tree — click a category to filter skills. Use the search bar to find specific skills by name. Click any skill to see its full training literature.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Package className="w-4 h-4 text-shogun-gold" /> Bundles Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Skills grouped into themed bundles (e.g., "Web Security Fundamentals," "Data Analysis Pack"). Each bundle card shows the bundle name, number of skills included, average difficulty, and a description. Click a bundle to expand it and see all the skills it contains.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Layers className="w-4 h-4 text-shogun-gold" /> Specializations Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Higher-level groupings that combine multiple bundles into a career-path style progression. Think of these as "majors" — completing a specialization means your agent is deeply trained in an entire domain.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-shogun-gold" /> Achieved Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Shows all the certifications your agents have already passed. Each entry shows the skill name, exam score, pass/fail status, and date achieved. Achieved skills are synchronized into the Archives <strong>Skills</strong> memory layer so their canonical instructions can participate in runtime retrieval.</p>
                   </div>
                   <div className="shogun-card space-y-2 md:col-span-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-shogun-gold" /> Skill Detail & Exams</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">When you click a skill, its detail pane shows canonical training content, source material, and risk tier plus a <strong>Take Exam</strong> action. Canonical skill content is structured as an operational instruction foundation: purpose, use conditions, inputs, workflow, decision rules, outputs, safety constraints, failure handling, examples, and success criteria. Exams contain 30–50 multiple-choice questions; passing certifies the agent and records the achievement.</p>
                   </div>
                </div>
             </section>

             {/* ═══════════════════════════════════════════════════════════════ */}
             {/* MAINTENANCE — BACKUPS, PRIVACY, DATA & UPDATES */}
             <section id="ref-maintenance" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-subdued/40 pb-3">
                   <HardDrive className="w-6 h-6 text-shogun-subdued" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Maintenance — Backups, Privacy, Updates, About &amp; Guide</h4>
                      <p className="text-xs text-shogun-subdued">Presented in the same order as the <strong>Maintenance</strong> section at the bottom of the sidebar.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2 border-l-2 border-shogun-gold/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-shogun-gold" /> Scheduled Backups</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Navigate to <strong>Backups</strong> in the sidebar. Enable automatic backups with a configurable schedule (hourly to weekly). Set how many old backups to keep — older ones are automatically deleted. Backups include your database, configs, governance documents, and environment settings.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-shogun-blue/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Database className="w-4 h-4 text-shogun-blue" /> Data Management Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">On the <strong>Backups</strong> page, switch to the <strong>Data Management</strong> tab. Here you'll find a live System Snapshot (row counts per table, DB size), one-click export as a <strong>Safe JSON Bundle</strong> or <strong>Raw Database Swap</strong>, and an Import area to restore from a previous export.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-shogun-gold/60">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Archive className="w-4 h-4 text-shogun-gold" /> Complete Backup &amp; Total Restore</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">For PC migration, <strong>Complete Backup</strong> discovers all configured storage roots and archives every contained file, including SQLite, embedded Qdrant, chats, settings, archives, workspaces, vault data, and logs. <strong>Total Restore</strong> validates every file checksum, creates a safety backup, and applies the package before startup so the old and new states are never mixed. The package contains credentials and other secrets and must be protected accordingly.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-amber-500/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-amber-400" /> Restore &amp; Recovery</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Every scheduled backup in the list has a <strong>Restore</strong> button for database and configuration rollback. Use <strong>Total Restore</strong> with a Complete Backup when recreating the whole Shogun state on another machine. Both workflows require a restart.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-violet-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-violet-400" /> Privacy &amp; Telemetry</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Navigate to Privacy &amp; Telemetry in the sidebar to review or control Shogun's optional, pseudonymous installation statistics. Telemetry is disabled by default and requires explicit consent. The page shows the exact fields that may be shared, everything that is never shared, and a preview of the next weekly heartbeat payload. You can send a test event, disable sharing, reveal the installation identifier, or delete your telemetry data. Server installations require administrator authorization.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-emerald-500/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Download className="w-4 h-4 text-emerald-400" /> System Updates</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Navigate to <strong>Updates</strong> in the sidebar. The automatic checker reads the repository's <code>version.json</code> manifest, compares its numeric build with the installed build, and caches the result for 6 hours. <strong>Check for Updates</strong> forces a fresh check; an available release displays an <strong>UPDATE</strong> badge in the sidebar.</p>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Click <strong>Install Update</strong> to download the current <code>main</code> branch, replace application code, and rebuild the frontend while preserving your database, configurations, environment, and virtual environment. Restart Shogun when installation completes. Private repositories can use a locally encrypted GitHub token configured on the Updates page.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-cyan-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Info className="w-4 h-4 text-cyan-400" /> About</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Open <strong>About</strong> to identify the installed Shogun version and build, review system information, and find the project and licence references associated with this installation. Record the version and build when reporting a defect so the report can be matched to the correct release.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-shogun-subdued/60">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><HelpCircle className="w-4 h-4 text-shogun-subdued" /> Guide</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The Guide contains onboarding, concepts, this page-by-page Grand Manual, architecture, and safety material. The Grand Manual follows the application&apos;s Navigation, Systems &amp; Governance, Operations, and Maintenance order. Use its left index to jump to a section and <strong>Print / Save PDF</strong> to create an offline reference.</p>
                   </div>
                </div>
             </section>

             {/* ROLES & RESPONSIBILITIES */}
             <section id="ref-roles-responsibilities" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-cyan-400/40 pb-3">
                   <Users className="w-6 h-6 text-cyan-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Roles &amp; Responsibilities</h4>
                      <p className="text-xs text-shogun-subdued">Responsibility follows each party&apos;s actual role in developing, providing, configuring, modifying, and operating the system.</p>
                   </div>
                </div>

                <div className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 p-4 space-y-2">
                   <div className="font-bold text-cyan-300 flex items-center gap-2"><Cpu className="w-4 h-4" /> Shogun is an orchestration framework—not an AI model</div>
                   <p className="text-xs text-shogun-subdued leading-relaxed">
                       Shogun does not bundle, train, or supply a proprietary LLM or foundation model. Shogun is not itself an LLM, foundation model, or general-purpose AI (GPAI) model. It is model-agnostic software that connects agents and workflows to AI models selected by the deploying organisation. Models may be cloud-hosted by third parties or hosted locally by the organisation. Alpha Horizon does not own or operate those selected models as part of the locally deployed Shogun product.
                   </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-3 border-l-2 border-shogun-gold/50">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-shogun-gold" /> Alpha Horizon responsibilities</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">An official release is a version and build published by Alpha Horizon through its official release channel and identified in <code>version.json</code>. For those releases, Alpha Horizon is responsible for:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1.5 ml-4 list-disc leading-relaxed">
                         <li>Maintaining the official source repository and release history.</li>
                         <li>Providing public and confidential mechanisms for reporting suspected security vulnerabilities.</li>
                         <li>Reviewing security reports that affect official, unmodified Shogun release code.</li>
                         <li>Publishing security advisories, mitigations, or fixes when Alpha Horizon determines this is appropriate or legally required.</li>
                          <li>Maintaining reasonable security controls around the official development and release process.</li>
                          <li>Maintaining the incident-handling and regulatory-escalation process described in Incident Reporting.</li>
                          <li>Official Shogun orchestration code, defaults, connectors, and documentation to the extent required by applicable law.</li>
                      </ul>
                   </div>

                   <div className="shogun-card space-y-3 border-l-2 border-shogun-blue/50">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><HardDrive className="w-4 h-4 text-shogun-blue" /> Deploying organisation responsibilities</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The organisation deploying Shogun remains responsible for assessing and controlling its particular implementation and use, including:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1.5 ml-4 list-disc leading-relaxed">
                         <li>Model and provider selection, including cloud-versus-local hosting and suitability for each use case.</li>
                         <li>API credentials, authentication, users, agent permissions, tools, and connected systems.</li>
                         <li>Data processed through Shogun and applicable GDPR or other data-protection duties.</li>
                         <li>Use-case assessment under applicable AI regulation, human oversight, and validation of AI-generated outputs, actions, and decisions.</li>
                         <li>Production infrastructure, network configuration, integrations, backups, disaster recovery, and environment monitoring.</li>
                         <li>The security, functionality, regulatory impact, and operational consequences of its configuration and any source-code modifications.</li>
                      </ul>
                       <p className="text-[10px] text-shogun-subdued leading-relaxed">A deploying organisation must complete its own security, legal, regulatory, and operational assessment before using Shogun for production workloads and confirm that its intended use is permitted by the Shogun AFM Free Use License or a separate written agreement. These operational responsibilities do not transfer Alpha Horizon&apos;s non-excludable duties for official releases or Alpha Horizon-controlled processing.</p>
                   </div>

                   <div className="shogun-card space-y-3 border-l-2 border-violet-400/50">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Network className="w-4 h-4 text-violet-400" /> Third-party model and service providers</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">
                          Third-party providers remain responsible for their respective models and services under their terms and applicable law. Alpha Horizon does not own or control their training data, provider infrastructure, intrinsic model behaviour, availability, or service-level performance. The deploying organisation remains responsible for provider due diligence and for deciding whether a selected model or service is appropriate for its intended use. This does not exclude responsibility for Shogun&apos;s own orchestration, integration code, defaults, or instructions.
                      </p>
                   </div>

                   <div className="shogun-card space-y-3 border-l-2 border-emerald-400/50">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Shield className="w-4 h-4 text-emerald-400" /> Regulatory roles follow the facts</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">
                          Shogun&apos;s model-agnostic architecture does not by itself determine the parties&apos; roles under the EU AI Act. Depending on the facts, Alpha Horizon may have obligations as a provider or downstream provider of an AI system; the deploying organisation may be a deployer and, in circumstances such as those described in Article 25 for high-risk AI systems, may acquire provider obligations; and a model supplier may have obligations as a model provider. Each party must assess and fulfil the duties attached to its actual role.
                      </p>
                      <a href="https://eur-lex.europa.eu/eli/reg/2024/1689/oj" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[10px] text-emerald-300 hover:underline"><ExternalLink className="w-3 h-3" /> EU AI Act role definitions</a>
                   </div>
                </div>

                <div className="rounded-xl border border-shogun-border bg-shogun-bg p-4 space-y-2">
                   <div className="font-bold text-shogun-text">Product and service boundary</div>
                   <p className="text-xs text-shogun-subdued leading-relaxed">
                       Shogun AFM is free to use for permitted purposes, source-available, locally deployable, and model-agnostic. It is provided “as is” under the Shogun AFM Free Use License. The official free-use distribution documented here is not a hosted SaaS service and includes no helpdesk, service-level agreement, managed integration, or other general support commitment unless Alpha Horizon agrees to one separately and in writing. This allocation does not override the licence or a separate written agreement. Nothing in this documentation excludes statutory rights or responsibilities that cannot legally be limited.
                   </p>
                </div>
             </section>

             {/* MODIFIED SHOGUN INSTALLATIONS */}
             <section id="ref-modified-installations" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-amber-400/40 pb-3">
                   <GitBranch className="w-6 h-6 text-amber-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Modified Shogun Installations</h4>
                      <p className="text-xs text-shogun-subdued">Internal modification is permitted only within the boundaries of the Shogun AFM Free Use License.</p>
                   </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-3 border-l-2 border-amber-400/50">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-amber-400" /> Licence boundary</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">
                         Shogun is source-available—not open source—and may be modified internally for permitted purposes under its licence. The existing restrictions on sale, resale, rebranding, hosted or managed-service use, and public redistribution remain unchanged. Modified versions may not be published or represented as official Shogun AFM releases without Alpha Horizon&apos;s written permission.
                      </p>
                      <a href="https://github.com/AlphaHorizon-AI/Shogun/blob/main/LICENSE.md" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[10px] text-amber-300 hover:underline"><ExternalLink className="w-3 h-3" /> Shogun AFM Free Use License</a>
                   </div>

                   <div className="shogun-card space-y-3 border-l-2 border-red-400/50">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><AlertCircle className="w-4 h-4 text-red-400" /> Responsibility for modifications</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">
                          A user-modified installation is not an official Shogun release unless Alpha Horizon expressly accepts the changes and publishes them through its official release process. Unless separately agreed in writing, Alpha Horizon does not test, validate, certify, or warrant third-party modifications and, to the extent permitted by law, does not assume responsibility for defects, vulnerabilities, behaviour, or consequences introduced by those modifications.
                      </p>
                      <p className="text-xs text-shogun-subdued leading-relaxed">
                          The modifying organisation is responsible for assessing the modification&apos;s security, functionality, data-protection impact, AI-regulatory role, integration behaviour, update path, and operational consequences. It must track its changes and revalidate them when adopting an official update.
                       </p>
                       <p className="text-xs text-shogun-subdued leading-relaxed">
                          A party that substantially modifies Shogun and makes that modified product available on the market may acquire manufacturer obligations under the CRA. For a high-risk AI system, rebranding, substantial modification, or a qualifying change of intended purpose can also alter provider responsibilities under the EU AI Act.
                       </p>
                   </div>
                </div>

                <div className="rounded-xl border border-shogun-border bg-shogun-bg p-4">
                   <p className="text-[10px] text-shogun-subdued leading-relaxed">
                       Reports from modified installations remain welcome so Alpha Horizon can determine whether an official release is also affected. This allocation does not limit responsibility that Alpha Horizon cannot legally exclude for a defect attributable to an official Alpha Horizon release, and it does not override any statutory rights. Attribution must be assessed from the actual defect, modification, configuration, and supply chain—not merely from the presence of a modified installation.
                   </p>
                </div>
             </section>

             {/* INCIDENT REPORTING — SECURITY & VULNERABILITY DISCLOSURE */}
             <section id="ref-incident-reporting" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-red-400/40 pb-3">
                   <ShieldAlert className="w-6 h-6 text-red-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Incident Reporting</h4>
                      <p className="text-xs text-shogun-subdued">Report suspected vulnerabilities, security defects, privacy incidents, and unexpected security behavior promptly.</p>
                   </div>
                </div>

                <div className="rounded-xl border border-red-400/30 bg-red-500/10 p-4 space-y-2">
                   <div className="font-bold text-red-300 flex items-center gap-2"><AlertCircle className="w-4 h-4" /> If there may be an active compromise</div>
                   <p className="text-xs text-shogun-subdued leading-relaxed">
                      Stop the affected workflow, activate <strong>Harakiri</strong> when appropriate, and isolate the affected Shogun instance from untrusted networks.
                      Preserve audit records and timestamps; do not erase evidence. From a trusted device, revoke or rotate credentials that may have been exposed.
                      These containment steps do not replace reporting the incident.
                   </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-3 border-l-2 border-shogun-blue/50">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><MessageSquare className="w-4 h-4 text-shogun-blue" /> Public, non-sensitive reports</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">
                         We encourage every user and security researcher to report suspected security issues. Use the public issue tracker only when the report is safe to disclose publicly and contains no secrets, personal data, customer data, or exploit-enabling details.
                      </p>
                      <a
                        href="https://github.com/AlphaHorizon-AI/Shogun/issues/new"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 rounded-lg bg-shogun-blue px-4 py-2.5 text-xs font-bold text-white transition-colors hover:bg-shogun-blue/80"
                      >
                         <ExternalLink className="w-4 h-4" /> Open a GitHub incident report
                      </a>
                   </div>

                   <div className="shogun-card space-y-3 border-l-2 border-red-400/50">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Lock className="w-4 h-4 text-red-400" /> Confidential vulnerability reports</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">
                         Do <strong>not</strong> publish exploit code, unpatched reproduction details, credentials or tokens, personal data, prompt content, production telemetry identifiers, installation identifiers, or unredacted logs in a public issue.
                      </p>
                      <div className="flex flex-wrap gap-2">
                         <a
                           href="https://github.com/AlphaHorizon-AI/Shogun/security/advisories/new"
                           target="_blank"
                           rel="noopener noreferrer"
                           className="inline-flex items-center gap-2 rounded-lg border border-red-400/40 bg-red-500/10 px-3 py-2 text-xs font-bold text-red-300 transition-colors hover:bg-red-500/20"
                         >
                            <FileKey className="w-4 h-4" /> Report privately
                         </a>
                         <a
                           href="mailto:contact@alphahorizon.io?subject=Shogun%20Security%20Report"
                           className="inline-flex items-center gap-2 rounded-lg border border-shogun-border bg-shogun-bg px-3 py-2 text-xs font-bold text-shogun-text transition-colors hover:border-red-400/40"
                         >
                            <Mail className="w-4 h-4" /> contact@alphahorizon.io
                         </a>
                      </div>
                      <p className="text-[10px] text-shogun-subdued leading-relaxed">
                         Prefer the private advisory for sensitive material. Email is a human-routed initial-contact channel and may not be end-to-end encrypted; do not email secrets or exploit details until a secure exchange method is agreed. The coordinated vulnerability disclosure process is documented in the{' '}
                         <a href="https://github.com/AlphaHorizon-AI/Shogun/blob/main/SECURITY.md" target="_blank" rel="noopener noreferrer" className="text-red-300 hover:underline">Security Policy</a>.
                      </p>
                   </div>

                   <div className="shogun-card space-y-3 border-l-2 border-amber-400/50">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-amber-400" /> What to include</div>
                      <ul className="text-xs text-shogun-subdued space-y-1.5 ml-4 list-disc leading-relaxed">
                         <li>Shogun version and build, operating system, and desktop or server deployment type.</li>
                         <li>Affected component, what you expected, what happened, and the security or privacy impact.</li>
                         <li>UTC timestamps, relevant trace or run IDs, and safe reproduction steps.</li>
                         <li>Sanitized logs and mitigations already attempted. Remove credentials, personal data, customer data, prompts, and proprietary content.</li>
                         <li>A secure way to contact you for follow-up and whether you believe exploitation is active.</li>
                      </ul>
                   </div>

                   <div className="shogun-card space-y-3 border-l-2 border-violet-400/50">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-violet-400" /> Coordinated handling</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">
                         Alpha Horizon aims to acknowledge and triage security reports promptly. Its coordinated process may validate affected versions and may publish corrective, mitigating, or advisory material where Alpha Horizon determines this appropriate or where required by applicable law. This does not promise a patch for every report or a customer-support response time. Please coordinate public disclosure until affected users have had a reasonable opportunity to apply any available measure.
                      </p>
                      <p className="text-xs text-shogun-subdued leading-relaxed">
                         Preserve relevant audit exports and follow any report or advisory for remediation guidance. When a verified security update or mitigation is made available, review and apply it promptly, then confirm the affected behavior.
                      </p>
                   </div>

                   <div className="shogun-card space-y-3 border-l-2 border-emerald-400/50">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><RefreshCw className="w-4 h-4 text-emerald-400" /> Product identity, vulnerability handling, and updates</div>
                      <ul className="text-xs text-shogun-subdued space-y-1.5 ml-4 list-disc leading-relaxed">
                         <li><strong>Product:</strong> Shogun AFM, release family 1.x. The unique version and build are shown on the Updates page and in <code>version.json</code>.</li>
                         <li><strong>Manufacturer and digital contact:</strong> Alpha Horizon — <a href="https://www.alphahorizon.io/" target="_blank" rel="noopener noreferrer" className="text-emerald-300 hover:underline">alphahorizon.io</a> — <a href="mailto:contact@alphahorizon.io" className="text-emerald-300 hover:underline">contact@alphahorizon.io</a>.</li>
                          <li><strong>Applicable vulnerability handling:</strong> Alpha Horizon handles security vulnerabilities affecting official, unmodified Shogun releases in accordance with applicable legal obligations and any support or vulnerability-handling period required under applicable law. A release-specific end date is determined and published when applicable law requires it.</li>
                          <li><strong>Support boundary:</strong> Shogun has no standard maintenance agreement, helpdesk, SLA, or commitment to ongoing feature development, compatibility or integration maintenance, or LLM/provider compatibility work. Security vulnerability handling is separate from general customer support and is performed where Alpha Horizon elects to provide it or where required by applicable law. Broader support exists only under a separate written agreement.</li>
                          <li><strong>Security updates:</strong> Alpha Horizon may publish corrective or mitigating measures through <a href="https://github.com/AlphaHorizon-AI/Shogun/releases" target="_blank" rel="noopener noreferrer" className="text-emerald-300 hover:underline">official releases</a>, <a href="https://github.com/AlphaHorizon-AI/Shogun/security/advisories" target="_blank" rel="noopener noreferrer" className="text-emerald-300 hover:underline">security advisories</a>, or the Shogun Updates channel where it determines this appropriate or where required by applicable law. This does not promise a patch for every report. Any applicable legal obligation to provide an update without charge is preserved. Installation requires an operator action.</li>
                          <li><strong>Modified installations:</strong> Customer or third-party modifications are not validated, certified, or maintained by Alpha Horizon. Reports remain welcome so Alpha Horizon can assess whether an issue is also attributable to an official release; Alpha Horizon does not undertake to patch defects introduced by those modifications.</li>
                         <li><strong>Secure decommissioning:</strong> Export records that must be retained, disconnect integrations, revoke credentials and tokens, remove local profiles and workspace data, and securely erase Shogun databases and backups before transferring or disposing of a device.</li>
                      </ul>
                   </div>

                   <div className="shogun-card space-y-3 border-l-2 border-orange-400/50">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Clock className="w-4 h-4 text-orange-400" /> CRA regulatory escalation</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">
                          Opening a GitHub report notifies Alpha Horizon; it does not itself complete any statutory notification. From <strong>11 September 2026</strong>, when Alpha Horizon has applicable manufacturer or other economic-operator duties under the EU Cyber Resilience Act, an actively exploited vulnerability or severe security incident is escalated through the ENISA Single Reporting Platform.
                      </p>
                      <ul className="text-xs text-shogun-subdued space-y-1.5 ml-4 list-disc leading-relaxed">
                         <li>Early warning: without undue delay and no later than 24 hours after awareness.</li>
                         <li>Substantive notification and initial assessment: no later than 72 hours after awareness.</li>
                         <li>Final vulnerability report: no later than 14 days after a corrective or mitigating measure is available.</li>
                         <li>Final severe-incident report: within one month after the 72-hour notification.</li>
                      </ul>
                      <div className="flex flex-wrap gap-3 text-[10px]">
                         <a href="https://www.enisa.europa.eu/topics/product-security/single-reporting-platform-srp" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-orange-300 hover:underline"><ExternalLink className="w-3 h-3" /> ENISA reporting platform</a>
                         <a href="https://digital-strategy.ec.europa.eu/en/policies/cra-reporting" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-orange-300 hover:underline"><ExternalLink className="w-3 h-3" /> European Commission guidance</a>
                      </div>
                   </div>
                </div>

                <div className="rounded-xl border border-shogun-border bg-shogun-bg p-4">
                   <p className="text-[10px] text-shogun-subdued leading-relaxed">
                      This section supports secure use and CRA readiness; it is not legal advice and does not by itself establish conformity. Product classification, technical documentation, cybersecurity risk assessment, conformity assessment, EU declaration of conformity, manufacturer postal details, and any national-law obligations must be completed and validated for the way Shogun is placed on the EU market.
                   </p>
                </div>
             </section>



            </div>
          </div>
        )}

        {/* Architecture */}
        {activeTab === 'architecture' && (
          <div className="space-y-16 animate-in slide-in-from-bottom-4">

             {/* Introduction */}
             <div className="text-center max-w-3xl mx-auto space-y-4">
                <h3 className="text-3xl font-bold shogun-title">System Architecture</h3>
                <p className="text-shogun-subdued leading-relaxed">A deep-dive into how Shogun is built — the layers, protocols, and subsystems that make it work. Understanding the architecture helps you make better decisions about configuration, security, and scaling.</p>
             </div>

             {/* 1. High-Level Overview */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-blue/40 pb-3">
                   <Layers className="w-6 h-6 text-shogun-blue" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">System Topology</h4>
                      <p className="text-xs text-shogun-subdued">The big picture — how all the pieces fit together.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Layout className="w-4 h-4 text-shogun-blue" /> Three-Tier Design</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Shogun is built in three tiers: <strong>Presentation</strong> (the React-based UI you're looking at), <strong>Application</strong> (a FastAPI backend handling all business logic, routing, and orchestration), and <strong>Persistence</strong> (SQLite in desktop mode or PostgreSQL in Server mode, plus Qdrant for vector memory). Each tier is independent and communicates through governed APIs.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Network className="w-4 h-4 text-shogun-blue" /> Lattice Architecture</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Instead of one monolithic AI, Shogun uses a "Lattice" — a network of specialized sub-agents (Samurai) coordinated by a central Shogun agent. Work is distributed across the lattice based on agent roles and routing profiles. This makes the system resilient, parallelizable, and scalable.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Globe className="w-4 h-4 text-shogun-blue" /> External Integrations</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">The system connects outward to cloud AI providers (OpenAI, Anthropic, Gemini, Perplexity, OpenRouter) and local model servers (Ollama) selected and configured by the deploying organisation. Shogun orchestrates those connections; it does not supply the selected model. It also integrates with Telegram for mobile messaging, automates web browsing via Mado (Playwright), connects to email servers (IMAP/SMTP), and syncs with calendar servers (CalDAV).</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Cpu className="w-4 h-4 text-shogun-blue" /> Desktop and Server Deployment</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Desktop mode runs Shogun, The Tenshu, SQLite, and local Qdrant directly on one computer. Server mode runs the application, PostgreSQL, and Qdrant as isolated Docker services with persistent volumes and automatic restarts. Both stay on hardware you control; Server mode is intended for continuous operation.</p>
                   </div>
                </div>
             </section>

             {/* 2. Agent Hierarchy */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-gold/40 pb-3">
                   <Users className="w-6 h-6 text-shogun-gold" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Agent Hierarchy</h4>
                      <p className="text-xs text-shogun-subdued">How intelligence is distributed across the network.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                   <div className="shogun-card space-y-3 border-t-2 border-shogun-gold">
                      <div className="font-bold text-shogun-gold text-lg flex items-center gap-2"><Cpu className="w-5 h-5" /> The Shogun</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The central coordinator. Receives user queries, decides how to respond, and can delegate sub-tasks to Samurai agents. Has its own personality, behavioral directives, and primary model. Think of the Shogun as the CEO — it makes strategic decisions and assigns work.</p>
                      <div className="text-[9px] text-shogun-subdued uppercase font-bold tracking-widest bg-shogun-bg p-2 rounded border border-shogun-border">Configured in: Shogun Profile</div>
                   </div>
                   <div className="shogun-card space-y-3 border-t-2 border-shogun-blue">
                      <div className="font-bold text-shogun-blue text-lg flex items-center gap-2"><Users className="w-5 h-5" /> Samurai Agents</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Specialized sub-agents, each with a defined role (Researcher, Analyst, Developer, etc.). Samurai can run independently or be orchestrated by the Shogun. Each has its own routing profile, spawn policy, and task queue. Think of them as department heads — experts in their domain.</p>
                      <div className="text-[9px] text-shogun-subdued uppercase font-bold tracking-widest bg-shogun-bg p-2 rounded border border-shogun-border">Managed in: Samurai Network</div>
                   </div>
                </div>
             </section>

             {/* 3. Memory Tier */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-gold/40 pb-3">
                   <Database className="w-6 h-6 text-shogun-gold" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">The Memory Tier</h4>
                      <p className="text-xs text-shogun-subdued">How the system stores, retrieves, and manages knowledge.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Search className="w-4 h-4 text-shogun-gold" /> Vector Memory (Qdrant)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Memories are converted into numerical vectors (embeddings) and stored in a Qdrant vector database. This enables <strong>semantic search</strong> — you can search by meaning, not just keywords. When the AI responds to a query, it automatically retrieves the most relevant memories from this layer and includes them in context.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Database className="w-4 h-4 text-shogun-gold" /> Structured Storage</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Agents, providers, routing profiles, governance documents, chat history, certifications, and security policies use SQLite (<code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">shogun.db</code>) in desktop mode and PostgreSQL in Server mode. This database is the source of truth for everything except vector embeddings.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Layers className="w-4 h-4 text-shogun-gold" /> Memory Types</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Memories are categorized into five types: <strong>Semantic</strong> (facts and knowledge), <strong>Episodic</strong> (events and experiences), <strong>Procedural</strong> (instructions and workflows), <strong>Persona</strong> (identity, preferences, and personal information), and <strong>Skills</strong> (learned capabilities from the Dojo). Each type has different retrieval priorities and consolidation rules. The type influences how aggressively the memory fades over time.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Star className="w-4 h-4 text-shogun-gold" /> Salience & Decay</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Every memory has a salience score (0.0–1.0). Frequently accessed memories rise in salience; unused ones decay naturally. The Bushido reflection engine periodically reviews memories and consolidates low-salience ones. You can <strong>pin</strong> critical memories to prevent decay entirely.</p>
                   </div>
                </div>
             </section>

             {/* 4. Communication Protocol */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-blue/40 pb-3">
                   <MessageSquare className="w-6 h-6 text-shogun-blue" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Communication Protocol</h4>
                      <p className="text-xs text-shogun-subdued">How agents talk to each other and to you.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><MessageSquare className="w-4 h-4 text-shogun-blue" /> User → Shogun (REST + SSE)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">When you type a message in Comms, it is sent as an HTTP POST to the backend. The response is streamed back via <strong>Server-Sent Events (SSE)</strong> — the tokens appear one at a time in real-time. This is what creates the "typing" effect you see as the AI responds.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Users className="w-4 h-4 text-shogun-blue" /> Shogun → Samurai (Internal Dispatch)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The Shogun delegates tasks to Samurai agents via an internal dispatch queue. Each delegation includes the task description, priority level, and context from the conversation. The Samurai processes the task independently and reports results back.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Zap className="w-4 h-4 text-shogun-blue" /> Shogun → AI Providers (LLM Calls)</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">The routing engine selects a configured model based on the active routing profile (or uses the default primary model). The request is sent to the deploying organisation&apos;s selected third-party provider API or local model service with the assembled prompt (user message + system prompt + memory context + constitution). Shogun relays streaming responses but does not control the selected model&apos;s training data, intrinsic behaviour, availability, or output quality.</p>
                   </div>
                </div>
             </section>

             {/* 5. Security Layer */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-red-400/40 pb-3">
                   <Lock className="w-6 h-6 text-red-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Security Layer</h4>
                      <p className="text-xs text-shogun-subdued">Defense-in-depth controls for governed agent and tool actions.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-red-400" /> Tiered Posture System</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Five built-in security tiers (SHRINE → GUARDED → TACTICAL → CAMPAIGN → RONIN), plus custom policies based on those tiers, define the capability ceiling. Torii selects the active tier or policy; ToolGate displays and enforces its filesystem, network, shell, tools, workflow, memory, and delegation rules.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-red-400" /> Kaizen Constitution Validator</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Covered operations routed through the Kaizen constitutional validator are evaluated server-side against enabled rules, in priority order. A detected violation can block the covered action before dispatch. This is one enforcement layer, not proof that every action or external side effect passes through Kaizen; keep privileges narrow and test the controls used by your deployment.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><AlertCircle className="w-4 h-4 text-red-400" /> Harakiri Kill Switch</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">An application-level emergency mechanism. When activated, it blocks new governed operations, requests best-effort cancellation of supported active work, locks posture to SHRINE, and displays a prominent red banner. External processes and systems may continue; use host-level containment when required. Activation requires two-step confirmation and recovery requires a deliberate reset.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Key className="w-4 h-4 text-red-400" /> Credential Protection</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Protected provider-credential APIs store supported credentials encrypted and return masked metadata to the frontend. Environment variables, legacy configuration, plugins, and custom integrations are separate secret paths that require deployment review.</p>
                   </div>
                </div>
             </section>

             {/* 6. Intelligence Pipeline */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-blue/40 pb-3">
                   <Cpu className="w-6 h-6 text-shogun-blue" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Intelligence Pipeline</h4>
                      <p className="text-xs text-shogun-subdued">The journey of a message from input to output.</p>
                   </div>
                </div>
                <div className="space-y-4">
                   {[
                     { step: 1, title: 'User Input', desc: 'You type a message in the Comms chat interface. The message is sent to the backend via HTTP POST.', color: 'text-shogun-blue', icon: MessageSquare },
                     { step: 2, title: 'Routing Decision', desc: 'The routing engine checks the active routing profile for matching task rules. If a rule matches (e.g., "research" → Perplexity), that model is used. Otherwise, the primary model is selected.', color: 'text-shogun-blue', icon: GitBranch },
                     { step: 3, title: 'Context Assembly', desc: 'The system assembles the full prompt: system instructions + Mandate (from Kaizen) + relevant memories (from Archives, via semantic search) + current conversation history + constitutional rules.', color: 'text-shogun-gold', icon: Layers },
                     { step: 4, title: 'Security Validation', desc: 'The assembled request is checked against the active ToolGate policy and constitutional rules. Capability boundaries, tool verdicts, parameters, and advanced content rules can require confirmation or block execution.', color: 'text-red-400', icon: ShieldCheck },
                      { step: 5, title: 'Model Invocation', desc: 'The validated prompt is sent to the organisation-selected third-party provider API or local model service. Shogun relays the response via SSE; the selected provider or local operator supplies the model.', color: 'text-shogun-blue', icon: Cpu },
                     { step: 6, title: 'Memory Inscription', desc: 'After the response completes, key information from the exchange may be automatically stored as new memories in the Archives, increasing the AI\'s knowledge for future queries.', color: 'text-shogun-gold', icon: Database },
                   ].map((item) => (
                     <div key={item.step} className="shogun-card flex gap-5 items-start">
                        <div className="flex flex-col items-center gap-2 shrink-0">
                           <div className={`w-10 h-10 rounded-xl bg-shogun-bg border border-shogun-border flex items-center justify-center font-bold text-lg ${item.color}`}>
                              {item.step}
                           </div>
                        </div>
                        <div className="space-y-1 min-w-0">
                           <div className="font-bold text-shogun-text flex items-center gap-2">
                              <item.icon className={`w-4 h-4 ${item.color}`} />
                              {item.title}
                           </div>
                           <p className="text-xs text-shogun-subdued leading-relaxed">{item.desc}</p>
                        </div>
                     </div>
                   ))}
                </div>
             </section>

             {/* 7. Self-Improvement Loop */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-gold/40 pb-3">
                   <RefreshCw className="w-6 h-6 text-shogun-gold" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Self-Improvement Loop (Bushido)</h4>
                      <p className="text-xs text-shogun-subdued">How the system continuously optimizes itself.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-shogun-gold" /> Reflection Cycles</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The Bushido engine periodically analyzes recent interactions to evaluate model performance, memory utilization, and agent effectiveness. It looks for patterns — which models are faster, which memories are frequently retrieved, which agents are underperforming — and generates actionable insights.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Binary className="w-4 h-4 text-shogun-gold" /> Memory Consolidation</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Low-salience episodic memories are periodically transformed into compact semantic summaries. This prevents the memory store from growing indefinitely while preserving the knowledge within. The consolidation rate is configurable via the Bushido calibration controls.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Compass className="w-4 h-4 text-shogun-gold" /> Exploration vs. Exploitation</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The "Exploration Variance" parameter controls how much the system deviates from proven strategies. Low variance means the AI sticks to what works; high variance means it experiments with new approaches. This is the classic explore-exploit tradeoff, tunable in Bushido.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-shogun-gold" /> Formal Verification</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Bushido proposals routed through the configured Kaizen validation path are checked against enabled rules before application. Review proposed and applied changes and retain independent change controls; this validator is a governance layer, not a guarantee that every optimization or side effect is classified or prevented.</p>
                   </div>
                </div>
             </section>

          </div>
        )}

        {/* Safety Protocols */}
        {activeTab === 'safety' && (
          <div className="space-y-16 animate-in slide-in-from-bottom-4">

             {/* Introduction */}
             <div className="text-center max-w-3xl mx-auto space-y-4">
                <h3 className="text-3xl font-bold shogun-title">Safety & Security Protocols</h3>
                <p className="text-shogun-subdued leading-relaxed">Shogun uses multiple security layers intended to reduce the likelihood and impact of a single control failure. Common-mode failures, configuration errors, uninstrumented paths, and host compromise remain possible. This page explains the implemented application controls and their limits.</p>
             </div>

             {/* 1. Security Philosophy */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-red-400/40 pb-3">
                   <ShieldCheck className="w-6 h-6 text-red-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Security Philosophy</h4>
                      <p className="text-xs text-shogun-subdued">The principles that govern every safety decision in Shogun.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                   <div className="shogun-card space-y-2 border-t-2 border-red-400">
                      <div className="font-bold text-shogun-text text-lg">Defense in Depth</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">No single layer should be relied on alone. Torii posture and policy, ToolGate, Kaizen validation, and action-specific checks cover different governed paths. Their coverage can overlap, but they may share dependencies or omit custom paths; test each boundary and combine them with host, identity, network, and monitoring controls.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-t-2 border-orange-400">
                      <div className="font-bold text-shogun-text text-lg">Least Privilege</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Agents receive only the minimum permissions needed for their tasks. Filesystem access, shell execution, delegation, and other capabilities must fit inside the active ToolGate boundary; per-tool and advanced content rules may further tighten execution but cannot widen that ceiling.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-t-2 border-shogun-gold">
                      <div className="font-bold text-shogun-text text-lg">Fail Closed</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">At implemented governance boundaries, unknown executable capabilities and missing or malformed explicit permission-gate values are denied. An agent without a saved posture override inherits the built-in TACTICAL default; a posture-read failure stops the affected request instead of being treated as permission. Harakiri provides a fail-closed gate for new governed operations and best-effort cancellation of supported active work; it is not a guarantee that every external process stops immediately.</p>
                   </div>
                </div>
             </section>

             {/* 2. Security Tiers */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-red-400/40 pb-3">
                   <Lock className="w-6 h-6 text-red-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">The Five Security Tiers</h4>
                      <p className="text-xs text-shogun-subdued">Each tier represents a different balance between safety and autonomy. Choose based on your environment and risk tolerance.</p>
                   </div>
                </div>
                <div className="space-y-4">
                   {[
                     { tier: 'SHRINE', subtitle: 'Maximum Protection', color: 'border-green-500 bg-green-500/5', badge: 'text-green-500 bg-green-500/10 border-green-500/30', desc: 'The most restrictive built-in policy for governed agent operations. It denies governed filesystem, network, shell, delegation, mail, calendar, cron, and Mado Browser capabilities and routes any remaining governed exception through approval. SHRINE is not a host or container network firewall and does not automatically disable separate update checks or explicitly opted-in telemetry services. Use it when you suspect a breach, while auditing, or for highly sensitive operations, together with host-level containment.', perms: ['Filesystem: Denied for governed tools', 'Network: Denied for governed tools', 'Shell: Blocked', 'Sub-agents: Blocked', 'Tools: Disabled by policy', 'Mail: Disabled', 'Calendar: Disabled', 'Cron: Disabled', 'Mado Browser: Disabled', 'Host/network isolation: Separate control'] },
                     { tier: 'GUARDED', subtitle: 'Restricted Operations', color: 'border-blue-500 bg-blue-500/5', badge: 'text-blue-500 bg-blue-500/10 border-blue-500/30', desc: 'A restricted built-in capability ceiling. For registered native tools that reach ToolGate in standard mode, low- and medium-risk calls are allowed by the risk default, high-risk calls require confirmation, and critical calls are blocked; parameter rules, capability boundaries, and overrides may tighten that result. Validate coverage and endpoint allowlists for the deployment.', perms: ['Filesystem: Allowlist ceiling', 'Network: Endpoint ceiling', 'Shell: Blocked', 'Sub-agents: Max 2 (manual)', 'Tools: Low/medium allow by default', 'High risk: Human confirmation', 'Critical risk: Blocked', 'Mail: Read-only ceiling', 'Calendar: Read-only ceiling', 'Coverage: Instrumented paths'] },
                     { tier: 'TACTICAL', subtitle: 'Balanced (Default)', color: 'border-shogun-gold bg-shogun-gold/5', badge: 'text-shogun-gold bg-shogun-gold/10 border-shogun-gold/30', desc: 'The recommended default. Agents have scoped file access (read and write within designated directories), can use approved tools autonomously, and have filtered network access. Shell commands are still blocked. Up to 5 sub-agents can be spawned. A good balance between productivity and safety.', perms: ['Filesystem: Scoped read/write', 'Network: Filtered (allowlist)', 'Shell: Blocked', 'Sub-agents: Max 5 (manual)', 'Tools: Approved auto-allowed', 'Mail: Read & Send', 'Calendar: Full access', 'Cron: Full access', 'Mado Browser: Headless only', 'Human approval: Dangerous only'] },
                     { tier: 'CAMPAIGN', subtitle: 'High Autonomy', color: 'border-orange-500 bg-orange-500/5', badge: 'text-orange-500 bg-orange-500/10 border-orange-500/30', desc: 'Extended autonomy for advanced users. On registered native paths in campaign mode, the risk default allows low-, medium-, and high-risk calls and blocks critical calls; capability boundaries, parameter checks, campaign presets, and explicit overrides may tighten the result. Use only in controlled environments with monitoring and independently validated model, connector, and custom-plugin behavior.', perms: ['Filesystem: Broad policy ceiling', 'Network: Broad policy ceiling', 'Shell: Policy-controlled', 'Sub-agents: Policy-controlled', 'Low/medium/high: Allowed by risk default', 'Critical risk: Blocked', 'Overrides: May tighten', 'Mail: Governed access', 'Mado Browser: Policy-controlled', 'Coverage: Instrumented paths'] },
                     { tier: 'RONIN', subtitle: '⚠ Highest Autonomy', color: 'border-red-500 bg-red-500/5', badge: 'text-red-500 bg-red-500/10 border-red-500/30', desc: 'The broadest built-in capability tier for governed operations, intended for controlled testing. It permits full filesystem/network policy and shell/tool use, but does not remove safety controls. Ronin desktop control must be enabled separately; forbidden applications and critical actions remain blocked, credential entry and administrative escalation remain disabled, and defined high-risk actions retain approval and verification gates.', perms: ['Filesystem: Full policy', 'Network: Full policy', 'Shell: Enabled', 'Sub-agents: Max 50', 'Tools: Broad access', 'Mail: Governed access', 'Calendar: Governed access', 'Cron: Governed access', 'Mado Browser: Autonomous', 'Human approval: High-risk gates'] },
                   ].map((item) => (
                     <div key={item.tier} className={`shogun-card border-l-4 ${item.color}`}>
                        <div className="flex flex-col md:flex-row md:items-start gap-4">
                           <div className="md:w-1/3 space-y-2">
                              <div className="flex items-center gap-3">
                                 <span className={`text-xs font-bold uppercase px-2 py-1 rounded border ${item.badge}`}>{item.tier}</span>
                                 <span className="text-sm font-bold text-shogun-text">{item.subtitle}</span>
                              </div>
                              <p className="text-xs text-shogun-subdued leading-relaxed">{item.desc}</p>
                           </div>
                           <div className="md:w-2/3 grid grid-cols-2 md:grid-cols-5 gap-2">
                              {item.perms.map((perm, i) => {
                                const [label, value] = perm.split(': ');
                                return (
                                  <div key={i} className="bg-shogun-bg border border-shogun-border rounded-lg p-2">
                                     <div className="text-[9px] text-shogun-subdued uppercase font-bold tracking-widest">{label}</div>
                                     <div className="text-[10px] text-shogun-text font-bold mt-0.5">{value}</div>
                                  </div>
                                );
                              })}
                           </div>
                        </div>
                     </div>
                   ))}
                </div>
             </section>

             {/* 3. Constitutional Guardrails */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-gold/40 pb-3">
                   <FileText className="w-6 h-6 text-shogun-gold" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Constitutional Guardrails</h4>
                      <p className="text-xs text-shogun-subdued">The AI's inviolable laws — written by you, enforced by the system.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-shogun-gold" /> How It Works</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The Constitution is a YAML document written in the Kaizen page. Each rule has a <strong>name</strong>, <strong>description</strong>, <strong>priority level</strong> (critical, high, balanced, medium, low), and <strong>enforcement mode</strong>. Covered operations submitted to the validator are checked against enabled applicable rules in priority order, with critical rules evaluated first. Custom or external paths require separate coverage review.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-shogun-gold" /> Enforcement Modes</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Rules can be set to different enforcement modes: <strong>Block</strong> (action is stopped entirely), <strong>Warn</strong> (action proceeds but a warning is logged), or <strong>Audit</strong> (action proceeds silently, logged for later review). Critical safety rules should always use "Block" mode.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><RefreshCw className="w-4 h-4 text-shogun-gold" /> Revision History</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Every time you publish the Constitution, a new revision snapshot is saved. You can review retained versions in the Kaizen sidebar to support change review, compliance assessment, and debugging of unexpected behaviour. Protect the underlying database and backups under your organisation&apos;s access-control and retention policy.</p>
                   </div>
                <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Zap className="w-4 h-4 text-shogun-gold" /> The Mandate</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">In addition to the Constitution&apos;s configured validation rules, the Mandate (Kaizen → Mandate tab) supplies soft directives to covered AI conversations. Configured server-side gates can block covered actions; the Mandate shapes behaviour such as tone, language, priorities, and focus. Neither layer guarantees that every external side effect is classified or captured.</p>
                   </div>
                </div>
              </section>

             {/* 4. ToolGate — Runtime Enforcement */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-orange-400/40 pb-3">
                   <Shield className="w-6 h-6 text-orange-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">ToolGate — Runtime Tool Enforcement</h4>
                      <p className="text-xs text-shogun-subdued">The policy-aware control surface and enforcement engine for capability ceilings, risk, confirmations, overrides, and parameter-sensitive runtime decisions.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Shield className="w-4 h-4 text-orange-400" /> How It Works</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Torii</strong> selects the built-in tier or custom policy. On registered and instrumented native-tool paths, <strong>ToolGate</strong> loads that policy&apos;s stable scope, displays its capability ceiling, and evaluates a call before execution. It combines the inherited risk mode, capability boundary, parameter analysis, per-tool override, and advanced content rules into one effective <strong>ALLOW</strong>, <strong>CONFIRM</strong>, or <strong>BLOCK</strong> verdict. Custom plugins and uninstrumented execution paths require separate coverage verification.</p>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Katana controls whether a tool is installed or connected, while PostureGuard controls which tools are visible to the agent. ToolGate remains the final runtime authorization layer even for visible, connected tools. A connected email tool can therefore be available in Katana but still require confirmation or be blocked by ToolGate.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><AlertCircle className="w-4 h-4 text-red-400" /> Risk Classification</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Every native tool is classified with a <strong>risk score</strong> from 0.0 (harmless) to 1.0 (critical). The classification is based on four risk dimensions:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Data exfiltration:</strong> Can this tool send data outside the system? (send_email, external API calls)</li>
                         <li><strong>Destructive mutation:</strong> Can this tool permanently alter or delete data? (file write, database operations)</li>
                         <li><strong>Autonomy escalation:</strong> Can this tool spawn new processes or grant itself more power? (spawn_samurai, create_cron_job)</li>
                         <li><strong>Physical world impact:</strong> Can this tool affect the real world? (desktop_click, desktop_type, send_email)</li>
                      </ul>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Lock className="w-4 h-4 text-shogun-gold" /> Tier-Based Thresholds</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Each built-in tier defines the baseline thresholds for its ToolGate scope. A custom policy inherits the default risk mode of its base tier while keeping its own capability boundaries, tool overrides, and advanced rules:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Confirm threshold:</strong> Tools with risk scores above this require human confirmation before executing.</li>
                         <li><strong>Block threshold:</strong> Tools with risk scores above this are blocked entirely — no amount of confirmation can override.</li>
                      </ul>
                      <p className="text-xs text-shogun-subdued leading-relaxed">A policy override or parameter/content rule may tighten that baseline, but it cannot widen a blocked capability boundary.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Zap className="w-4 h-4 text-shogun-gold" /> Parameter-Aware Analysis</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">ToolGate doesn't just check the tool name — it inspects the actual parameters. The <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">check_tool_access</code> function analyzes:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Target paths:</strong> File operations targeting system directories get elevated risk.</li>
                         <li><strong>Email recipients:</strong> External domains may trigger higher scrutiny than internal ones.</li>
                         <li><strong>Cron schedules:</strong> Very frequent schedules (every minute) are flagged as higher risk.</li>
                         <li><strong>Shell commands:</strong> Commands containing <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">rm</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">sudo</code>, or pipe chains get elevated risk.</li>
                      </ul>
                   </div>
                   <div className="shogun-card space-y-2 md:col-span-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-shogun-blue" /> Dual-Path Enforcement</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">ToolGate enforces on <strong>both</strong> tool execution paths in the system:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Structured mode:</strong> When the AI uses JSON-formatted tool calls (standard mode), ToolGate intercepts in the structured execution pipeline before <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">execute_native_tool</code> is called.</li>
                         <li><strong>Text mode:</strong> When the AI uses text-based tool invocation (fallback mode), ToolGate intercepts in the text-mode extraction pipeline before the tool function is dispatched.</li>
                      </ul>
                      <p className="text-xs text-shogun-subdued leading-relaxed">These built-in structured and text execution paths invoke ToolGate independently of the model&apos;s response format. Custom plugins, integrations, and future execution paths must preserve the same gate; verify coverage for every executable path in your deployment.</p>
                   </div>
                   <div className="shogun-card space-y-2 md:col-span-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-shogun-blue" /> Audit Trail</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Recorded ToolGate decisions include provenance such as tool name, parameters, computed risk, active policy scope and base tier, decision, source, reason, and any matching advanced content rule. These entries are dual-written to Layer 1 (operational) and Layer 2 (separate application-level HMAC-chained records); the deploying organisation controls and verifies retention. Framework tags attached to events do not determine legal applicability or compliance. Event correlation supports partial workflow reconstruction; missing events or a missing trace are not proof that an action did or did not occur.</p>
                   </div>
                </div>
             </section>

             {/* 5. Harakiri Emergency Protocol */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-red-500/40 pb-3">
                   <AlertCircle className="w-6 h-6 text-red-500" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Harakiri — Emergency Protocol</h4>
                      <p className="text-xs text-shogun-subdued">A last-resort application control that blocks new governed work and requests bounded cancellation.</p>
                   </div>
                </div>
                <div className="shogun-card border-l-4 border-red-500 bg-red-500/[0.02] space-y-6">
                   <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-3">
                         <div className="font-bold text-red-400 flex items-center gap-2"><Zap className="w-4 h-4" /> What Happens When Activated</div>
                         <ul className="text-xs text-shogun-subdued space-y-2 ml-4 list-disc leading-relaxed">
                            <li><strong>Cancellation is requested for supported active agent work.</strong> Instrumented tasks are interrupted where the runtime supports cancellation, and the restrictive posture blocks supported new work.</li>
                            <li><strong>Security posture locks to SHRINE.</strong> Governed filesystem, network, shell, and tool capabilities are restricted by that policy; this does not revoke host permissions already held by separate processes.</li>
                            <li><strong>A pulsing red banner appears</strong> at the top of every page in the system, alerting all users that the kill switch is active.</li>
                            <li><strong>A critical log entry is created</strong> with the timestamp and reason for activation.</li>
                            <li><strong>Supported instrumented connectors receive the emergency state.</strong> This is not a network-isolation guarantee: separately running connectors, peers, provider calls, and host processes must be checked and contained through deployment controls.</li>
                         </ul>
                      </div>
                      <div className="space-y-3">
                         <div className="font-bold text-shogun-text flex items-center gap-2"><Lock className="w-4 h-4 text-red-400" /> Activation & Recovery</div>
                         <ul className="text-xs text-shogun-subdued space-y-2 ml-4 list-disc leading-relaxed">
                            <li><strong>Two-step confirmation:</strong> You must click the Harakiri button, then confirm in a modal dialog. This prevents accidental activation.</li>
                            <li><strong>Available from two locations:</strong> The Dashboard (Tenshu) and the Security Portal (Torii). Both trigger the same global mechanism.</li>
                            <li><strong>To recover:</strong> Click "Reset Harakiri" on the banner or from the Torii page. The posture returns to TACTICAL (the safe default). You must then manually re-enable any higher postures if desired.</li>
                            <li><strong>Harakiri does not intentionally delete stored data or configuration.</strong> Interrupted work and external systems may still have partial side effects, so inspect state before resuming.</li>
                         </ul>
                      </div>
                   </div>
                   <div className="bg-[#0a0505] border border-red-500/20 p-4 rounded-xl">
                      <p className="text-[10px] text-red-500 font-bold uppercase tracking-widest mb-2">When to Use Harakiri</p>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Use the kill switch when: you observe unexpected or harmful agent behavior, you suspect your API keys have been compromised, an agent is consuming excessive resources, or you need to perform a security audit. When in doubt, press the button — it's always better to freeze and investigate than to let a problem escalate.</p>
                   </div>
                </div>
             </section>

             {/* 5. Operational Security Best Practices */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-blue/40 pb-3">
                   <Lock className="w-6 h-6 text-shogun-blue" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Operational Security Best Practices</h4>
                      <p className="text-xs text-shogun-subdued">Recommended practices for maintaining a secure Shogun deployment.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2 border-l-2 border-shogun-blue/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Key className="w-4 h-4 text-shogun-blue" /> Rotate API Keys Regularly</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">API keys for AI providers should be rotated periodically. If you suspect a key has been exposed, revoke it immediately from the provider's dashboard and update it in Katana → Cloud Providers.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-shogun-blue/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-shogun-blue" /> Test Posture Changes in SHRINE</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Before upgrading to a higher security posture (e.g., TACTICAL → CAMPAIGN), test your constitutional rules in SHRINE mode first. This ensures your guardrails are properly configured before giving agents more freedom.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-shogun-blue/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Network className="w-4 h-4 text-shogun-blue" /> Isolate RONIN Environments</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">If you need the RONIN high-autonomy tier for testing, prefer an isolated machine or VM with no production data, credential stores, or unnecessary external access. Confirm that the built-in blocked, approval-required, verification, and critical-action controls remain effective, and add host-level containment appropriate to your risk.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-shogun-blue/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Download className="w-4 h-4 text-shogun-blue" /> Backup Before Major Changes</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Before changing the security posture, modifying the Constitution, or deploying new agents, export a backup via the Data Management tab. This gives you a restore point if something goes wrong.</p>
                   </div>
                </div>
             </section>

             {/* 6. ToolGate — Runtime Tool Enforcement */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-amber-500/40 pb-3">
                   <ShieldAlert className="w-6 h-6 text-amber-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">ToolGate — Runtime Tool Enforcement</h4>
                      <p className="text-xs text-shogun-subdued">The runtime behavior of the ToolGate policy selected in Torii, including local and centrally managed operation.</p>
                   </div>
                </div>
                <div className="shogun-card space-y-4">
                   <p className="text-xs text-shogun-subdued leading-relaxed">ToolGate sits between PostureGuard (which determines <em>which tools are visible</em>) and the executor that runs them. It provides policy-scoped, per-call enforcement based on capability boundaries, risk mode, tool overrides, parameter analysis, and advanced word or phrase rules. In Tenshu it is editable locally.</p>
                   <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-lg p-3 space-y-1">
                         <div className="text-xs font-bold text-emerald-400 uppercase tracking-wider">ALLOW</div>
                         <p className="text-[11px] text-shogun-subdued">Low-risk tools (browse, fetch, list) execute immediately with no interruption.</p>
                      </div>
                      <div className="bg-amber-500/5 border border-amber-500/20 rounded-lg p-3 space-y-1">
                         <div className="text-xs font-bold text-amber-400 uppercase tracking-wider">CONFIRM</div>
                         <p className="text-[11px] text-shogun-subdued">High-risk tools (send email, desktop control) pause and show a confirmation card in the chat. You must click Approve or Deny before execution proceeds.</p>
                      </div>
                      <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3 space-y-1">
                         <div className="text-xs font-bold text-red-400 uppercase tracking-wider">BLOCK</div>
                         <p className="text-[11px] text-shogun-subdued">Critical-risk or destructive patterns are blocked outright. The tool receives a "blocked" response, and the AI must find an alternative approach.</p>
                      </div>
                   </div>
                   <div className="space-y-3">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><AlertCircle className="w-4 h-4 text-amber-400" /> Risk Classification</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Every tool in the registry is assigned a risk level: <strong className="text-emerald-400">LOW</strong> (read-only, no side effects), <strong className="text-amber-400">MEDIUM</strong> (creates/modifies internal state), <strong className="text-orange-400">HIGH</strong> (external side effects or control actions), or <strong className="text-red-400">CRITICAL</strong> (destructive or irreversible). The Mode × Risk threshold matrix determines the default action for each combination.</p>
                   </div>
                   <div className="space-y-3">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldAlert className="w-4 h-4 text-amber-400" /> Parameter-Aware Checks</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Beyond the static risk level, ToolGate recursively inspects nested arguments. Built-in analysis detects destructive commands, sensitive paths, recursive deletion, mass operations, credential-like input, and force flags. <strong>Advanced mode</strong> adds operator-defined words or phrases with whole-word or substring matching, optional case sensitivity, global or tool-specific scope, and a CONFIRM or BLOCK outcome. These checks can only tighten the final decision.</p>
                   </div>
                   <div className="space-y-3">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Clock className="w-4 h-4 text-amber-400" /> Confirmation Timeout</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">When a confirmation card appears, you have <strong>60 seconds</strong> to respond. If the timer expires, the tool is <strong>auto-denied</strong> for safety. The AI receives a "denied by operator" result and can adapt its approach.</p>
                   </div>
                </div>
             </section>

             {/* 7. Quarantine — Shogun Trash */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-purple-500/40 pb-3">
                   <Trash2 className="w-6 h-6 text-purple-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Quarantine — Shogun Trash</h4>
                      <p className="text-xs text-shogun-subdued">Recoverable soft-delete for file operations.</p>
                   </div>
                </div>
                <div className="shogun-card space-y-4">
                   <p className="text-xs text-shogun-subdued leading-relaxed">When Shogun deletes a file (via Ronin desktop automation or future file tools), the file is not permanently removed. Instead, it is moved to a <code className="text-amber-400 bg-black/30 px-1.5 py-0.5 rounded">.shogun_trash/</code> directory at the project root. This acts as a safety net against accidental or AI-initiated data loss.</p>
                   <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div className="bg-shogun-card border border-shogun-border rounded-lg p-3 space-y-2">
                         <div className="text-xs font-bold text-shogun-text">Quarantine</div>
                         <p className="text-[11px] text-shogun-subdued">Files are timestamped and moved to trash. A manifest.json tracks the original path, deletion reason, file size, and timestamp.</p>
                      </div>
                      <div className="bg-shogun-card border border-shogun-border rounded-lg p-3 space-y-2">
                         <div className="text-xs font-bold text-shogun-text">Recover</div>
                         <p className="text-[11px] text-shogun-subdued">Any quarantined file can be restored to its original location via the recovery function. No data is permanently lost until explicitly purged.</p>
                      </div>
                      <div className="bg-shogun-card border border-shogun-border rounded-lg p-3 space-y-2">
                         <div className="text-xs font-bold text-shogun-text">Auto-Purge</div>
                         <p className="text-[11px] text-shogun-subdued">Files older than 30 days are eligible for automatic permanent deletion. This prevents unbounded disk growth while preserving recent safety net coverage.</p>
                      </div>
                      <div className="bg-shogun-card border border-shogun-border rounded-lg p-3 space-y-2">
                         <div className="text-xs font-bold text-shogun-text">Audit Trail</div>
                         <p className="text-[11px] text-shogun-subdued">Instrumented quarantine and recovery actions can create manifest entries. The manifest lists available records of what was moved or restored, when, and why; it is not a guaranteed complete deletion history.</p>
                      </div>
                   </div>
                </div>
             </section>

             {/* 8. Threat Model */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-red-400/40 pb-3">
                   <AlertCircle className="w-6 h-6 text-red-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Threat Model</h4>
                      <p className="text-xs text-shogun-subdued">Known risk categories and how Shogun mitigates them.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-red-400 flex items-center gap-2"><AlertCircle className="w-4 h-4" /> Prompt Injection</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Risk:</strong> Malicious input that attempts to redirect the model or misuse a tool. <strong>Mitigation:</strong> Configured server-side policy and tool gates evaluate covered operations independently of model text and can deny them. This is defense in depth, not a guarantee that prompt injection or every external side effect is prevented; minimise privileges, validate outputs, and supervise high-impact actions.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-red-400 flex items-center gap-2"><AlertCircle className="w-4 h-4" /> Credential Exposure</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Risk:</strong> API keys or secrets leaking through agent responses, logs, configuration, or integrations. <strong>Mitigation:</strong> Use Shogun&apos;s protected provider-credential storage where available; those API paths return masked metadata and are designed to keep stored secrets out of model context. Environment variables, legacy configuration, plugins, logs, manually pasted prompts, and third-party integrations are separate secret paths—review and restrict them, rotate exposed credentials, and never paste secrets into a prompt.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-red-400 flex items-center gap-2"><AlertCircle className="w-4 h-4" /> Runaway Agent</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Risk:</strong> An agent entering a loop, spawning unlimited sub-agents, or consuming excessive API credits. <strong>Mitigation:</strong> Spawn policies limit auto-spawning. Harakiri blocks new governed operations and requests best-effort cancellation of supported active work; operators must verify external processes. Resource monitoring in Bushido flags anomalies.</p>
                   </div>
                </div>
             </section>

          </div>
        )}

      {/* Legal Disclaimer */}
      <div className="mt-16 pt-8 border-t border-shogun-border/40">
        <div className="shogun-card bg-orange-500/5 border-orange-500/20">
          <div className="flex items-start gap-4">
            <AlertCircle className="w-6 h-6 text-orange-400 shrink-0 mt-1" />
            <div className="space-y-4">
              <h4 className="text-sm font-bold text-shogun-text uppercase tracking-widest flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-orange-400" />
                {t('guide.disclaimer_title', 'Legal Disclaimer')}
              </h4>
              <p className="text-xs text-shogun-subdued leading-relaxed">
                {t('guide.disclaimer_body', 'Shogun is a source-available AI-agent orchestration framework that is free to use for permitted purposes under the Shogun AFM Free Use License and provided “as is.” It does not guarantee accuracy, completeness, reliability, or suitability for a particular purpose; use remains at the operator’s risk to the extent permitted by law. The deploying organisation is responsible for the configuration, selected models and providers, data, permissions, infrastructure, use cases, oversight, and output validation it controls. Alpha Horizon remains responsible for duties that applicable law assigns to official Alpha Horizon releases, and third-party providers remain responsible for their respective models and services under their terms and applicable law. No disclaimer limits rights or responsibilities that cannot legally be excluded.')}
              </p>
              <div className="p-3 bg-shogun-bg border border-shogun-border rounded-lg border-l-4 border-l-orange-400">
                <p className="text-xs font-bold text-shogun-text">
                  {t('guide.disclaimer_oversight', 'Human oversight required: Shogun may generate inaccurate, incomplete, or inappropriate outputs. It must not be relied upon without appropriate human review, especially in legal, financial, compliance, security, or other high-impact contexts.')}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  );
}
