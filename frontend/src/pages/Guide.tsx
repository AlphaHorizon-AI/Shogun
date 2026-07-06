import { useState, useEffect, useRef, useCallback } from 'react';
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
  HardDrive,
  Globe,
  Star,
  Layers,
  Sparkles,
  Filter,
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
  Crosshair,
  Monitor as MonitorIcon,
  FileSpreadsheet,
  FolderOpen as FolderOpenIcon,
  Power,
  List,
  Clock,
} from "lucide-react";
import { cn } from '../lib/utils';
import { useTranslation } from '../i18n';

type DocTab = 'onboarding' | 'architecture' | 'reference' | 'safety';

export function Guide() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<DocTab>('onboarding');
  const [activeSection, setActiveSection] = useState<string>('ref-tenshu');
  const refContentRef = useRef<HTMLDivElement>(null);

  const REFERENCE_SECTIONS = [
    { id: 'ref-tenshu', label: 'Tenshu', icon: Layout, color: 'text-shogun-blue' },
    { id: 'ref-comms', label: 'Comms', icon: MessageSquare, color: 'text-shogun-blue' },
    { id: 'ref-profile', label: 'Shogun Profile', icon: Cpu, color: 'text-shogun-gold' },
    { id: 'ref-samurai', label: 'Samurai Network', icon: Users, color: 'text-shogun-gold' },
    { id: 'ref-katana', label: 'Katana', icon: Sword, color: 'text-shogun-blue' },
    { id: 'ref-telegram', label: 'Telegram Setup', icon: MessageSquare, color: 'text-sky-400' },
    { id: 'ref-teams', label: 'Teams Setup', icon: Users, color: 'text-indigo-400' },
    { id: 'ref-archives', label: 'Archives', icon: Database, color: 'text-shogun-gold' },
    { id: 'ref-dojo', label: 'Dojo', icon: Flame, color: 'text-shogun-gold' },
    { id: 'ref-kaizen', label: 'Kaizen', icon: ShieldCheck, color: 'text-shogun-gold' },
    { id: 'ref-bushido', label: 'Bushido', icon: RefreshCw, color: 'text-shogun-blue' },
    { id: 'ref-mado', label: 'Mado', icon: AppWindow, color: 'text-cyan-400' },
    { id: 'ref-ronin', label: 'Ronin', icon: Crosshair, color: 'text-orange-400' },
    { id: 'ref-office', label: 'Office', icon: FileSpreadsheet, color: 'text-green-400' },
    { id: 'ref-workspace', label: 'Workspace', icon: FolderOpenIcon, color: 'text-amber-400' },
    { id: 'ref-torii', label: 'Torii', icon: Lock, color: 'text-red-400' },
    { id: 'ref-nexus', label: 'Nexus', icon: Globe, color: 'text-indigo-400' },
    { id: 'ref-nexus-gateway', label: 'Nexus Gateway', icon: Link2, color: 'text-indigo-400' },
    { id: 'ref-gensui', label: 'Gensui', icon: ShieldAlert, color: 'text-indigo-400' },
    { id: 'ref-logs', label: 'Logs', icon: Terminal, color: 'text-shogun-subdued' },
    { id: 'ref-maintenance', label: 'Maintenance', icon: HardDrive, color: 'text-shogun-gold' },
  ];

  const scrollToSection = useCallback((sectionId: string) => {
    const el = document.getElementById(sectionId);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setActiveSection(sectionId);
    }
  }, []);

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
  }, [activeTab]);

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500 pb-20">
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
                  This system is designed for high-stakes automation, deep research, and secure agent-to-agent collaboration.
                  This guide will walk you through everything you need to go from zero to fully operational.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                   <div className="p-4 bg-shogun-bg border border-shogun-border rounded-xl">
                      <div className="text-shogun-blue font-bold text-lg mb-1">1. Connect Brains</div>
                      <p className="text-xs text-shogun-subdued">Head to <strong>Katana</strong> to add your API keys or local models. This is where your AI's "intelligence" comes from.</p>
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
                      <p className="text-xs text-shogun-subdued leading-relaxed">You need an API key from at least one AI provider — OpenAI, Anthropic, Google Gemini, or Perplexity. These are obtained from the provider's developer portal. Without a key, the Shogun cannot think.</p>
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
                     { step: 2, title: 'Select a Primary Model', color: 'text-shogun-blue', icon: Cpu, desc: 'Go to Shogun Profile → Models tab. In the "Primary Model" dropdown, select which AI brain the Shogun will use by default. This is the model that answers every question and powers every decision unless a routing rule overrides it.' },
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
                     { term: 'Security Posture', def: 'A tiered system (SHRINE → RONIN) controlling how much autonomy and access agents have. Managed in Torii.', icon: Lock, color: 'text-red-400' },
                     { term: 'Harakiri', def: 'The emergency kill switch. Instantly freezes all agent activity and locks the system to maximum security (SHRINE).', icon: ShieldCheck, color: 'text-red-400' },
                     { term: 'Routing Profile', def: 'A set of rules that decides which AI model handles which type of task. For example: code → GPT-4, research → Perplexity.', icon: GitBranch, color: 'text-shogun-blue' },
                     { term: 'Salience', def: 'A memory importance score (0.0–1.0). High-salience memories are retrieved first. The system auto-adjusts salience over time.', icon: Star, color: 'text-shogun-gold' },
                     { term: 'Reflection Cycle', def: 'An automated self-improvement loop where the AI analyzes its own performance and generates optimization insights. Run from Bushido.', icon: RefreshCw, color: 'text-shogun-blue' },
                     { term: 'Ronin (Desktop)', def: 'The desktop control capability. Allows agents to interact with OS desktops — mouse, keyboard, screenshots, native apps. Governed by Posture Guard, App Trust, and Komainu. Requires explicit enabling in Torii.', icon: Crosshair, color: 'text-orange-400' },
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
                     { name: 'Comms (Chat)', purpose: 'Talk directly to your Shogun. Send questions or commands. Responses stream in real time. View chat history and restore old sessions. Also includes an integrated email client and calendar.', icon: MessageSquare, color: 'text-shogun-blue' },
                     { name: 'Shogun Profile', purpose: 'Configure your AI\'s identity — name, personality, primary model, fallback models, behavioral directives, permissions, and scheduled jobs.', icon: Cpu, color: 'text-shogun-gold' },
                     { name: 'Samurai Network', purpose: 'Deploy and manage specialized sub-agents. Each Samurai has a role, routing profile, and spawn policy. Monitor their tasks and status.', icon: Users, color: 'text-shogun-gold' },
                     { name: 'Katana (System Forge)', purpose: 'Plug in AI providers (cloud or local), create routing profiles, manage tools, and configure Telegram integration.', icon: Sword, color: 'text-shogun-blue' },
                     { name: 'Archives (Memory)', purpose: 'Search, browse, create, and manage the AI\'s memories. Supports semantic search, salience pinning, and memory type filtering.', icon: Database, color: 'text-shogun-gold' },
                     { name: 'Dojo (Training Hall)', purpose: 'Browse 4,000+ skills from the OpenClaw College. Study training material, take certification exams, and track achievements.', icon: Flame, color: 'text-shogun-gold' },
                     { name: 'Kaizen (Governance)', purpose: 'Write the Constitution (YAML rules) and the Mandate (Markdown mission statement). Manage revision history and audit trails.', icon: ShieldCheck, color: 'text-shogun-gold' },
                     { name: 'Bushido (Reflection)', purpose: 'Calibrate self-improvement behavior. Tune reflection intensity, consolidation rate, and exploration variance. View AI-generated insights.', icon: RefreshCw, color: 'text-shogun-blue' },
                     { name: 'Torii (Security)', purpose: 'Set the system\'s security posture (5 tiers from SHRINE to RONIN). Create and manage security policies. Access the Harakiri kill switch.', icon: Lock, color: 'text-red-400' },
                     { name: 'Mado (Browser)', purpose: 'Browser automation layer powered by Playwright. Your AI can navigate to URLs, extract page content, take screenshots, and interact with web pages — all controlled through the secure Torii permission system.', icon: AppWindow, color: 'text-cyan-400' },
                     { name: 'Ronin (Desktop Control)', purpose: 'Desktop automation layer. Allows governed mouse, keyboard, screenshot, and native app control. Protected by Posture Guard, App Trust (4 levels), Komainu physical override, and environment detection. Only available at TACTICAL tier or higher.', icon: Crosshair, color: 'text-orange-400' },
                     { name: 'Agent Flow (Workflows)', purpose: 'Visual drag-and-drop workflow builder. Design multi-step AI pipelines by chaining Input, Samurai, Shogun Approval, Logic Gate, Browser, and Output nodes. Execute complex orchestration flows.', icon: Workflow, color: 'text-violet-400' },
                     { name: 'Mail (Email Client)', purpose: 'Full IMAP/SMTP email integration. Browse your inbox, read and compose emails, reply with CC/BCC, navigate folders. Your Shogun can also read, send, and manage emails via native skills.', icon: Mail, color: 'text-sky-400' },
                     { name: 'Calendar', purpose: 'CalDAV calendar integration. View upcoming events, create new ones (with time, location, and description), and manage your schedule. Your Shogun can query and create events via native skills.', icon: CalendarDays, color: 'text-emerald-400' },
                     { name: 'Nexus (Collaboration)', purpose: 'Create Joint Workspaces. Invite other Shogun instances over the network. Exchange typed messages and co-edit a shared whiteboard.', icon: Globe, color: 'text-indigo-400' },
                     { name: 'Gensui (Fleet Command)', purpose: 'Connect this Shogun to a Gensui Central Command server for fleet-wide security posture management, remote policy enforcement, telemetry monitoring, and emergency Harakiri. Manage enrollment, view active posture, and monitor the fleet link.', icon: ShieldAlert, color: 'text-indigo-400' },
                     { name: 'Backups & Data', purpose: 'Scheduled and manual backups with configurable retention. Export/import your entire database. Manage backup settings and restore from any point.', icon: HardDrive, color: 'text-shogun-gold' },
                     { name: 'Updates', purpose: 'Auto-checks for new Shogun versions every 6 hours. One-click install to download and apply updates. Preserves your data, configs, and environment.', icon: Download, color: 'text-emerald-400' },
                     { name: 'Logs (Compliance Dashboard)', purpose: 'NIS2, SOC2, and EU AI Act-compliant event stream. Filter by 11 categories (Decision, Oversight, Risk, Model, Policy, Memory, Tools, Auth, Incident, System). Click trace IDs for full workflow reconstruction. Audit chain verifies tamper-proof integrity.', icon: Terminal, color: 'text-shogun-subdued' },
                     { name: 'Guide (Documentation)', purpose: 'This page — a comprehensive knowledge base covering onboarding, architecture, reference manual, and safety protocols. Located in the Maintenance section.', icon: HelpCircle, color: 'text-shogun-subdued' },
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
                      <p className="text-xs text-shogun-subdued leading-relaxed">Don't rely on a single AI provider. In Shogun Profile → Models, add at least one fallback model from a different provider. If your primary (e.g., OpenAI) goes down, the system automatically switches to the next available brain.</p>
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
                   <div className="shogun-card space-y-2 border-l-2 border-green-500/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-green-500" /> Monitor the Compliance Dashboard</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Check the Logs page regularly — it records every action with full NIS2/SOC2/EU AI Act provenance. Use the <strong>Decision</strong> tab to track AI reasoning influences. Click trace IDs to reconstruct full workflows. Verify the <strong>"Chain Intact"</strong> badge stays green — a broken chain indicates tampering. Export the audit log periodically for off-site compliance archival.</p>
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
                <h3 className="text-3xl font-bold shogun-title">The Grand Reference</h3>
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
                      <p className="text-xs text-shogun-subdued leading-relaxed">A red button on the dashboard. Pressing it opens a two-step confirmation modal. Once confirmed, <strong>all active agent operations are immediately stopped</strong>. The security posture locks to "SHRINE" (maximum protection). A pulsing red banner appears at the top of Every page until you press "Reset Harakiri".</p>
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
             {/* 2. COMMS (CHAT) */}
             {/* ═══════════════════════════════════════════════════════════════ */}
             <section id="ref-comms" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-blue/40 pb-3">
                   <MessageSquare className="w-6 h-6 text-shogun-blue" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Comms — The Conversation</h4>
                      <p className="text-xs text-shogun-subdued">Your direct line to the Shogun AI. Four tabs: Chat, Mail, Calendar, and Files.</p>
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

             {/* ═══════════════════════════════════════════════════════════════ */}
             {/* 3. SHOGUN PROFILE */}
             {/* ═══════════════════════════════════════════════════════════════ */}
             <section id="ref-profile" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-gold/40 pb-3">
                   <Cpu className="w-6 h-6 text-shogun-gold" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Shogun Profile — Your AI's Identity</h4>
                      <p className="text-xs text-shogun-subdued">Configure the personality, intelligence, and behavior of your main Shogun agent. Has 5 tabs.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Cpu className="w-4 h-4 text-shogun-gold" /> General Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Set the Shogun's name, choose an active "Persona" (a pre-built personality template), and write a description. On the right side, adjust the <strong>Autonomy Level</strong> slider (how much freedom the AI gets), <strong>Tone</strong> (e.g., Analytical, Direct), <strong>Risk Tolerance</strong>, <strong>Verbosity</strong> (how detailed responses are), <strong>Planning Depth</strong>, <strong>Tool Usage</strong>, <strong>Security Bias</strong>, and <strong>Memory Style</strong>. Click the avatar image to upload a custom picture.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Database className="w-4 h-4 text-shogun-gold" /> Models Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Choose exactly which AI brain the Shogun uses. Has two cards: <strong>Primary Model</strong> (the main brain used for every request) — select from a dropdown grouped by provider. <strong>Fallback Models</strong> — add backup brains in priority order. If the primary is unavailable, these are tried in order. Drag to reorder priorities. Also has a <strong>Routing Strategy</strong> dropdown to choose a routing profile.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-shogun-gold" /> Behavior Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">A full-screen YAML text editor showing the Shogun's core behavioral directives — its priorities, operational constraints, and delegation rules. Think of this as the AI's "rule book." You can edit it directly, and the badge in the top-right confirms it is in "YAML Mode."</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Lock className="w-4 h-4 text-shogun-gold" /> Permissions Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Displays the security rules inherited from the current Security Policy. Shows a <strong>Risk Score</strong> meter (0–100, where higher = more dangerous). Every permission category (Filesystem, Network, Shell, Skills, Subagents, Memory) is listed with plain-English tooltips explaining what each setting does. You can toggle individual settings to customize rules beyond the base policy.</p>
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
                </div>

                {/* Agent Flow sub-section */}
                <div className="mt-8 space-y-4">
                   <div className="text-xs font-bold text-shogun-subdued uppercase tracking-widest pl-1 border-l-2 border-shogun-gold/40 ml-1">Samurai Orchestration</div>
                   <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="shogun-card space-y-2 border-l-2 border-violet-400/40">
                         <div className="font-bold text-shogun-text flex items-center gap-2"><Workflow className="w-4 h-4 text-violet-400" /> Agent Flow — Workflow Builder</div>
                         <p className="text-xs text-shogun-subdued leading-relaxed">A visual drag-and-drop canvas for designing multi-step AI pipelines using your Samurai. Build workflows by chaining six node types:</p>
                         <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                            <li><strong>Input:</strong> The entry point — accepts user text, data, or triggers.</li>
                            <li><strong>Samurai:</strong> Delegates a task to a specific sub-agent.</li>
                            <li><strong>Shogun Approval:</strong> Pauses the flow for human confirmation.</li>
                            <li><strong>Logic:</strong> A conditional gate — routes based on a condition.</li>
                            <li><strong>Mado Browser:</strong> Automates a web browsing action.</li>
                            <li><strong>Output:</strong> Collects and presents the workflow's result.</li>
                         </ul>
                      </div>
                      <div className="shogun-card space-y-2 border-l-2 border-violet-400/40">
                         <div className="font-bold text-shogun-text flex items-center gap-2"><GitBranch className="w-4 h-4 text-violet-400" /> Canvas, Execution & AI Creation</div>
                         <p className="text-xs text-shogun-subdued leading-relaxed">Position nodes freely on the visual canvas and draw directed edges between them. Edges define execution order — data flows from source to target. The canvas supports pan, zoom, and node reordering. Workflows are saved to the database.</p>
                         <p className="text-xs text-shogun-subdued leading-relaxed mt-2">Click <strong>Execute</strong> to run a workflow. Nodes process in topological order, passing outputs as inputs to the next. Shogun Approval nodes pause until you confirm.</p>
                         <p className="text-xs text-shogun-subdued leading-relaxed mt-2">You can also ask the Shogun to <strong>build workflows for you</strong> via the <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">create_agent_flow</code> native skill.</p>
                      </div>
                      <div className="shogun-card space-y-2 border-l-2 border-violet-400/40">
                         <div className="font-bold text-shogun-text flex items-center gap-2"><Package className="w-4 h-4 text-violet-400" /> Template Gallery</div>
                         <p className="text-xs text-shogun-subdued leading-relaxed">Click <strong>New Flow</strong> to browse 137 pre-built workflow templates across 10 different categories (e.g., Data Analysis, Content Creation, Document Processing). Templates range in difficulty from <strong>Beginner</strong> to <strong>Advanced</strong>.</p>
                         <p className="text-xs text-shogun-subdued leading-relaxed mt-2">When you select a template, the canvas is automatically populated. Samurai nodes inside templates use <strong>Ephemeral (Ad-Hoc)</strong> agents by default to keep your Fleet clean, but can be manually linked to a permanent Fleet Samurai via the node properties panel.</p>
                      </div>
                   </div>
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
                      <p className="text-xs text-shogun-subdued">Where you plug in AI "brains", connect tools, and set up routing rules. Has nine tabs.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Key className="w-4 h-4 text-shogun-blue" /> Cloud Providers Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Lists every cloud AI service you have connected (OpenAI, Anthropic, Google Gemini, Perplexity, etc.). Each provider card shows its <strong>name</strong>, <strong>type</strong>, <strong>status</strong> (active/disabled), and which <strong>models</strong> it provides. You can <strong>add a new provider</strong> by clicking the button, entering a name, selecting the type, pasting your API key, and optionally listing specific model names. Each card has <strong>Edit</strong> and <strong>Delete</strong> buttons.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><HardDrive className="w-4 h-4 text-shogun-blue" /> Local Models Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">For AI models running on your own computer (via Ollama). Shows a list of <strong>discovered models</strong> on your machine, each with its size and format. You can <strong>pull new models</strong> from the Ollama library with a real-time download progress bar showing speed and percentage.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Binary className="w-4 h-4 text-shogun-blue" /> Routing Profiles Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Create "routing profiles" — sets of rules that decide which AI model handles which type of task. For example, you can create a "Balanced" profile where: code tasks go to GPT-4, research tasks go to Perplexity Sonar, and simple chat goes to a cheap model. Each profile has a <strong>name</strong>, optional <strong>default model</strong>, and a list of <strong>rules</strong> (task type → model pair). Profiles can be set as the system default.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Network className="w-4 h-4 text-shogun-blue" /> Toolbox Tab</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Lists all the external tools the Shogun can use — web search, file access, database connections, code execution, etc. Each tool shows its <strong>name</strong>, <strong>type</strong>, and <strong>status</strong> (enabled/disabled). You can <strong>register new tools</strong> and toggle existing ones on or off.</p>
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
                         <li><strong>Send emails:</strong> Compose and send messages (requires <code>perm_send_mail</code> to be enabled).</li>
                         <li><strong>Calendar events:</strong> Create and manage calendar entries (when supported by the provider).</li>
                      </ul>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The tab shows <strong>connection status</strong>, account details, and permission toggles for read, send, and calendar access. All mail activity is logged in the immutable audit chain.</p>
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
                   <div id="ref-teams" className="shogun-card space-y-2 md:col-span-2 scroll-mt-6">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><MessageSquare className="w-4 h-4 text-shogun-blue" /> Microsoft Teams Adapter</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Connect Microsoft Teams as an enterprise command and notification channel for Shogun. Teams is the communication surface; <strong>Katana</strong> manages the channel, while <strong>Gensui</strong> continues to enforce identity, authorization, approvals, policy, and audit. The adapter supports personal chats, group chats, and channel commands when the Shogun bot is directly mentioned.</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Overview:</strong> Shows adapter health, tenant and SSO status, recent activity, errors, and active approval requests.</li>
                         <li><strong>Setup Wizard:</strong> Configures the deployment mode, allowed Microsoft tenants, Bot/App ID, secret reference, public HTTPS messaging endpoint, valid domains, and downloadable Teams app package.</li>
                         <li><strong>Entra &amp; Roles:</strong> Maps verified Teams and Microsoft Entra identities to Shogun roles. New identities begin as <strong>Viewer</strong> until deliberately promoted.</li>
                         <li><strong>Security Policy:</strong> Controls available command groups, destructive-command approval flow, approval expiry, and dual approval for fleet shutdown.</li>
                         <li><strong>Audit &amp; Diagnostics:</strong> Records inbound commands, risk classification, authorization decisions, response outcomes, and correlation IDs. Built-in checks validate the Shogun backend, Microsoft Graph configuration, proactive messaging, and Teams manifest.</li>
                      </ul>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Commands such as <code>status</code>, <code>agents</code>, <code>run workflow</code>, <code>pause agent</code>, and <code>show pending approvals</code> are classified by risk before dispatch. Critical commands—including Harakiri—never execute directly from a casual Teams message and must pass through Gensui confirmation and the configured approval policy. Production use requires a Microsoft Entra/Azure Bot registration and a public HTTPS Teams Bridge endpoint.</p>
                   </div>
                </div>

                <div className="shogun-card space-y-6 border-indigo-400/20">
                   <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                      <div>
                         <div className="font-bold text-shogun-text flex items-center gap-2 text-base">
                            <Users className="w-5 h-5 text-indigo-400" /> Microsoft Teams — Step-by-Step Connection Guide
                         </div>
                         <p className="text-xs text-shogun-subdued mt-1">A complete path from an empty Microsoft tenant to a working Shogun personal chat and channel mention.</p>
                      </div>
                      <span className="text-[9px] font-bold uppercase tracking-widest text-indigo-400 bg-indigo-400/10 border border-indigo-400/20 px-2.5 py-1 rounded-full w-fit">Administrator-assisted setup</span>
                   </div>

                   <div className="p-4 rounded-lg border border-amber-400/20 bg-amber-400/5">
                      <p className="text-xs text-amber-300 font-bold flex items-center gap-2"><AlertCircle className="w-4 h-4" /> Non-technical reality check</p>
                      <p className="text-xs text-shogun-subdued leading-relaxed mt-2">
                         Teams is an enterprise deployment, not a one-token connection. Most organizations require a <strong>Microsoft 365/Teams administrator</strong>,
                         an <strong>Azure or Entra administrator</strong>, and the person who operates the Shogun server. The simplest safe pilot is
                         <strong> Single tenant + Customer-hosted Teams Bridge + personal chat</strong>. Leave SSO, Microsoft Graph, and proactive messaging off until basic chat works.
                      </p>
                   </div>

                   <div>
                      <h5 className="text-sm font-bold text-shogun-text mb-3">What must be ready</h5>
                      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
                         {[
                            ['Microsoft 365 tenant', 'A work or school tenant with Microsoft Teams.'],
                            ['Azure subscription', 'Permission to create an Entra app registration and Azure Bot resource.'],
                            ['Public HTTPS address', 'A stable internet address for the Teams Bridge, or a secure tunnel for a pilot.'],
                            ['Shogun server access', 'Permission to start the included bridge and set protected environment values.'],
                         ].map(([title, text]) => (
                            <div key={title} className="p-3 rounded-lg bg-shogun-bg border border-shogun-border">
                               <p className="text-xs font-bold text-shogun-text">{title}</p>
                               <p className="text-[11px] text-shogun-subdued leading-relaxed mt-1">{text}</p>
                            </div>
                         ))}
                      </div>
                   </div>

                   <div className="p-4 rounded-lg bg-indigo-400/5 border border-indigo-400/20">
                      <h5 className="text-xs font-bold text-shogun-text">Administrator handoff checklist</h5>
                      <p className="text-[11px] text-shogun-subdued mt-1">If someone else manages Microsoft 365, give that person this exact list:</p>
                      <ul className="text-[11px] text-shogun-subdued leading-relaxed mt-2 ml-4 list-disc space-y-1.5">
                         <li>Create a <strong>single-tenant Microsoft Entra app registration</strong> for Shogun.</li>
                         <li>Create an <strong>Azure Bot</strong> using that existing app registration and enable its Microsoft Teams channel.</li>
                         <li>Provide the <strong>Directory (tenant) ID</strong> and <strong>Application (client) ID</strong>.</li>
                         <li>Store the client secret or certificate in the approved secret store; do not send it by email or Teams chat.</li>
                         <li>Permit the Shogun custom Teams app for pilot users, or upload it to the organization's app catalog.</li>
                         <li>Provide a public HTTPS hostname that routes to the Shogun Teams Bridge on port <code>3978</code>.</li>
                      </ul>
                   </div>

                   <div className="space-y-4">
                      <h5 className="text-sm font-bold text-shogun-text">Part A — Register Shogun in Microsoft Entra</h5>
                      <ol className="text-xs text-shogun-subdued space-y-3 ml-5 list-decimal leading-relaxed">
                         <li>Sign in to the <a href="https://portal.azure.com" target="_blank" rel="noreferrer" className="text-indigo-400 hover:underline font-bold">Azure portal</a> with the administrator account.</li>
                         <li>Open <strong>Microsoft Entra ID → App registrations → New registration</strong>.</li>
                         <li>Enter a recognizable name such as <code>Shogun Teams Bot</code>.</li>
                         <li>Select <strong>Accounts in this organizational directory only</strong> for a single-tenant deployment, then select <strong>Register</strong>.</li>
                         <li>On Overview, copy <strong>Application (client) ID</strong> and <strong>Directory (tenant) ID</strong>. Keep the labels with the values so they are not confused.</li>
                         <li>
                            For a pilot using a client secret, open <strong>Certificates &amp; secrets → Client secrets → New client secret</strong>.
                            Copy the secret <strong>Value</strong> immediately; it is displayed only once. Store it in an approved secret manager.
                            For production, Microsoft recommends a managed identity, federated credential, or certificate instead of a long-lived client secret.
                         </li>
                      </ol>
                      <a href="https://learn.microsoft.com/en-us/microsoft-365/agents-sdk/azure-bot-authentication-for-javascript" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[11px] text-indigo-400 hover:underline">
                         <ExternalLink className="w-3 h-3" /> Official Microsoft authentication options
                      </a>
                   </div>

                   <div className="space-y-4">
                      <h5 className="text-sm font-bold text-shogun-text">Part B — Create and configure the Azure Bot</h5>
                      <ol className="text-xs text-shogun-subdued space-y-3 ml-5 list-decimal leading-relaxed">
                         <li>In the Azure portal, select <strong>Create a resource</strong>, search for <strong>Azure Bot</strong>, and select <strong>Create</strong>.</li>
                         <li>Choose the subscription and resource group, enter a unique bot handle, and select <strong>Single Tenant</strong>.</li>
                         <li>For Microsoft App ID, choose <strong>Use existing app registration</strong> and enter the Application (client) ID from Part A.</li>
                         <li>After deployment, open the Azure Bot resource. Under <strong>Settings → Configuration</strong>, set Messaging endpoint to <code>https://YOUR-BRIDGE-HOST/api/messages</code>, then apply the change.</li>
                         <li>Under <strong>Settings → Channels</strong>, add or enable the <strong>Microsoft Teams</strong> channel.</li>
                      </ol>
                      <a href="https://learn.microsoft.com/en-us/microsoftteams/platform/teams-sdk/teams/azure-configuration" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[11px] text-indigo-400 hover:underline">
                         <ExternalLink className="w-3 h-3" /> Official Azure Bot and Teams channel instructions
                      </a>
                   </div>

                   <div className="space-y-4">
                      <h5 className="text-sm font-bold text-shogun-text">Part C — Start the included Teams Bridge</h5>
                      <p className="text-xs text-shogun-subdued leading-relaxed">
                         The bridge is the Microsoft-facing service in <code>bridge/teams</code>. Teams sends messages to the bridge; the bridge validates and normalizes them,
                         then sends governed commands to Shogun. The bridge requires <strong>Node.js 22 or newer</strong>.
                      </p>
                      <div className="grid md:grid-cols-2 gap-4">
                         <div className="p-4 rounded-lg bg-[#050508] border border-shogun-border">
                            <p className="text-[10px] font-bold uppercase tracking-widest text-shogun-subdued mb-2">Bridge environment values</p>
                            <pre className="text-[10px] text-indigo-300 whitespace-pre-wrap overflow-x-auto">{`tenantId=<Directory tenant ID>
clientId=<Application client ID>
clientSecret=<secret Value for pilot only>
SHOGUN_INTERNAL_API_URL=http://<shogun-host>:8000
SHOGUN_INTERNAL_API_KEY=<one long random shared key>`}</pre>
                         </div>
                         <div className="p-4 rounded-lg bg-[#050508] border border-shogun-border">
                            <p className="text-[10px] font-bold uppercase tracking-widest text-shogun-subdued mb-2">Install and start</p>
                            <pre className="text-[10px] text-indigo-300 whitespace-pre-wrap overflow-x-auto">{`cd bridge/teams
npm install
npm run build
npm start`}</pre>
                         </div>
                      </div>
                      <ul className="text-xs text-shogun-subdued space-y-2 ml-4 list-disc leading-relaxed">
                         <li>Set the same <code>SHOGUN_INTERNAL_API_KEY</code> in the operating-system environment for both Shogun and the bridge, then restart both. Do not commit this key to source control.</li>
                         <li><code>SHOGUN_INTERNAL_API_URL</code> must be an address the bridge can reach. If both run on one computer, <code>http://127.0.0.1:8000</code> is normally correct.</li>
                         <li>The bridge listens on port <code>3978</code>. Put it behind a public HTTPS reverse proxy or a controlled development tunnel.</li>
                         <li>Open <code>https://YOUR-BRIDGE-HOST/api/teams/health</code>. A JSON response with status <code>ok</code> confirms the bridge is reachable.</li>
                      </ul>
                   </div>

                   <div className="space-y-4">
                      <h5 className="text-sm font-bold text-shogun-text">Part D — Complete Katana's Setup Wizard</h5>
                      <p className="text-xs text-shogun-subdued">Open <strong>The Katana → Microsoft Teams → Setup Wizard</strong> and use these values:</p>
                      <div className="overflow-x-auto rounded-lg border border-shogun-border">
                         <table className="w-full text-[11px]">
                            <thead><tr className="text-left bg-shogun-bg text-shogun-subdued"><th className="p-3">Katana field</th><th className="p-3">Recommended value</th></tr></thead>
                            <tbody className="divide-y divide-shogun-border text-shogun-subdued">
                               <tr><td className="p-3 font-bold text-shogun-text">Deployment mode</td><td className="p-3"><strong>Customer-hosted Teams Bridge</strong> for production; Local development + tunnel for a pilot.</td></tr>
                               <tr><td className="p-3 font-bold text-shogun-text">Tenant mode</td><td className="p-3"><strong>Single tenant</strong>.</td></tr>
                               <tr><td className="p-3 font-bold text-shogun-text">Allowed tenant IDs</td><td className="p-3">The Directory (tenant) ID from Entra. Enter one ID per line.</td></tr>
                               <tr><td className="p-3 font-bold text-shogun-text">Bot / App ID</td><td className="p-3">The Application (client) ID from Entra.</td></tr>
                               <tr><td className="p-3 font-bold text-shogun-text">Bot display name</td><td className="p-3">A friendly name such as <code>Shogun</code>.</td></tr>
                               <tr><td className="p-3 font-bold text-shogun-text">Secret reference</td><td className="p-3">A reference such as <code>vault://teams/bot-client-secret</code>, never the secret value. The actual credential is injected into the bridge runtime.</td></tr>
                               <tr><td className="p-3 font-bold text-shogun-text">Public messaging endpoint</td><td className="p-3"><code>https://YOUR-BRIDGE-HOST/api/messages</code> — exactly the same URL configured on the Azure Bot.</td></tr>
                               <tr><td className="p-3 font-bold text-shogun-text">Valid domains</td><td className="p-3">Hostname only, for example <code>teams-bridge.example.com</code>. Do not include <code>https://</code> or a path.</td></tr>
                            </tbody>
                         </table>
                      </div>
                      <ol className="text-xs text-shogun-subdued space-y-2 ml-5 list-decimal leading-relaxed">
                         <li>Click <strong>Save configuration</strong>.</li>
                         <li>Keep SSO, Microsoft Graph, and Proactive messaging disabled for the first test.</li>
                         <li>Under Security Policy, keep destructive commands disabled and dual approval enabled.</li>
                         <li>Click <strong>Enable adapter</strong>. Overview should become Production ready or show a specific missing item.</li>
                      </ol>
                   </div>

                   <div className="space-y-4">
                      <h5 className="text-sm font-bold text-shogun-text">Part E — Generate and install the Teams app</h5>
                      <ol className="text-xs text-shogun-subdued space-y-3 ml-5 list-decimal leading-relaxed">
                         <li>Click <strong>Generate Teams app package</strong>. Shogun downloads <code>shogun-teams-app.zip</code>. Do not unzip it.</li>
                         <li>For a personal pilot, open Teams and choose <strong>Apps → Manage your apps → Upload an app → Upload a custom app</strong>. Select the ZIP, then choose <strong>Add</strong> and <strong>Open</strong>.</li>
                         <li>
                            If Upload a custom app is missing, a Teams administrator must allow it or upload the ZIP centrally at
                            <a href="https://admin.teams.microsoft.com" target="_blank" rel="noreferrer" className="text-indigo-400 hover:underline"> Teams admin center</a> under <strong>Teams apps → Manage apps → Upload new app</strong>.
                         </li>
                         <li>For a team or channel, install the app in that team too. In channel messages, directly mention <code>@Shogun</code> before the command.</li>
                      </ol>
                      <div className="flex flex-wrap gap-4">
                         <a href="https://learn.microsoft.com/en-us/microsoftteams/platform/concepts/deploy-and-publish/apps-upload" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[11px] text-indigo-400 hover:underline">
                            <ExternalLink className="w-3 h-3" /> Upload a custom app in Teams
                         </a>
                         <a href="https://learn.microsoft.com/en-us/microsoftteams/teams-custom-app-policies-and-settings" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[11px] text-indigo-400 hover:underline">
                            <ExternalLink className="w-3 h-3" /> Teams administrator app policies
                         </a>
                      </div>
                   </div>

                   <div className="space-y-4">
                      <h5 className="text-sm font-bold text-shogun-text">Part F — Test in the right order</h5>
                      <ol className="text-xs text-shogun-subdued space-y-3 ml-5 list-decimal leading-relaxed">
                         <li>Open a personal chat with the installed Shogun app. The welcome message should say Shogun is connected.</li>
                         <li>Send <code>help</code>, then <code>status</code>. These are safe first commands for a new Viewer identity.</li>
                         <li>Open <strong>Katana → Microsoft Teams → Entra &amp; Roles</strong>. Your identity should appear after the first message.</li>
                         <li>Open <strong>Audit Log</strong>. The commands should have timestamps, authorization results, and correlation IDs.</li>
                         <li>Under <strong>Diagnostics</strong>, run Shogun backend and Teams manifest. Test Graph and proactive messaging only after configuring those features.</li>
                         <li>Finally test a channel with <code>@Shogun status</code>. A plain <code>status</code> without the mention may be ignored.</li>
                      </ol>
                   </div>

                   <div className="space-y-3">
                      <h5 className="text-sm font-bold text-shogun-text">Teams troubleshooting</h5>
                      <div className="overflow-x-auto rounded-lg border border-shogun-border">
                         <table className="w-full text-[11px]">
                            <thead><tr className="text-left bg-shogun-bg text-shogun-subdued"><th className="p-3">What you see</th><th className="p-3">What to check</th></tr></thead>
                            <tbody className="divide-y divide-shogun-border text-shogun-subdued">
                               <tr><td className="p-3 font-bold text-shogun-text">The app cannot be uploaded</td><td className="p-3">Ask the Teams administrator to enable custom app upload or upload the ZIP in Teams admin center. Regenerate the ZIP after changing App ID, valid domains, or SSO.</td></tr>
                               <tr><td className="p-3 font-bold text-shogun-text">Bot sends no reply</td><td className="p-3">Check bridge health, confirm Azure Bot uses the exact <code>/api/messages</code> HTTPS endpoint, and confirm the Teams channel is enabled.</td></tr>
                               <tr><td className="p-3 font-bold text-shogun-text">“Shogun is unreachable”</td><td className="p-3">The bridge is online but cannot reach Shogun. Check the internal API URL, network/firewall access, and that both processes use the same internal API key.</td></tr>
                               <tr><td className="p-3 font-bold text-shogun-text">Unauthorized or silent command</td><td className="p-3">Compare the tenant with Allowed tenant IDs. In a channel, mention the bot and ensure the app is installed in that team.</td></tr>
                               <tr><td className="p-3 font-bold text-shogun-text">Only safe commands work</td><td className="p-3">This is expected for new Viewer identities. An administrator must deliberately assign a higher Shogun role and command policy.</td></tr>
                               <tr><td className="p-3 font-bold text-shogun-text">Authentication stopped later</td><td className="p-3">The client secret may have expired. Replace it in the bridge's secret store, restart the bridge, and retire the old secret.</td></tr>
                               <tr><td className="p-3 font-bold text-shogun-text">Proactive messages disappear after restart</td><td className="p-3">The included bridge uses in-memory storage for development. Production needs Azure Blob or Cosmos-backed Agents SDK storage, and the user must contact the bot once first.</td></tr>
                            </tbody>
                         </table>
                      </div>
                   </div>

                   <div className="p-4 rounded-lg border border-green-400/20 bg-green-400/5">
                      <h5 className="text-xs font-bold text-green-400">Setup is complete when all six statements are true</h5>
                      <ul className="text-[11px] text-shogun-subdued mt-2 ml-4 list-disc space-y-1.5">
                         <li>The bridge health URL returns status <code>ok</code>.</li>
                         <li>Katana Overview reports the adapter as ready with the correct tenant.</li>
                         <li>The Teams app installs without a manifest error.</li>
                         <li><code>help</code> and <code>status</code> receive replies in a personal chat.</li>
                         <li>The user appears under Entra &amp; Roles and the command appears in Audit Log.</li>
                         <li><code>@Shogun status</code> works in every team/channel where the app was intentionally installed.</li>
                      </ul>
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
                      </ul>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Star className="w-4 h-4 text-shogun-gold" /> Salience Score</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Each memory has a "salience" score (0.0 to 1.0) that represents how important it is. High-salience memories are prioritized when the AI retrieves context. The system automatically adjusts salience over time — frequently used memories rise, rarely used ones fade. You can manually <strong>pin</strong> a memory to lock its salience at maximum.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Sparkles className="w-4 h-4 text-shogun-gold" /> Inscribe Memory (+ Button)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Click the "+" button to manually add a new memory. You choose the <strong>type</strong> (semantic, episodic, etc.), write the <strong>content</strong>, and optionally set the <strong>salience</strong>. This is useful for injecting facts, rules, or context that the AI should always know about.</p>
                   </div>
                   <div className="shogun-card space-y-2 md:col-span-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-shogun-gold" /> Memory Cards</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Each memory is shown as a card with: the content text, memory type badge, salience bar, creation date, and action buttons. You can <strong>delete</strong> individual memories via the trash icon. The total count and an "Export" option are available in the header.</p>
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
                      <p className="text-xs text-shogun-subdued leading-relaxed">Shows all the certifications your agents have already passed. Each entry shows the skill name, exam score, pass/fail status, and date achieved. This is your "trophy room" — proof that your AI has been tested and verified on specific capabilities.</p>
                   </div>
                   <div className="shogun-card space-y-2 md:col-span-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-shogun-gold" /> Skill Detail & Exams</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">When you click on any individual skill, you see its full detail pane: the training literature (textbooks and reference material), the risk tier, and a <strong>"Take Exam"</strong> button. Exams are 30–50 multiple-choice questions. The AI agent answers them automatically. A passing score certifies the agent on that skill and appears in the "Achieved" tab.</p>
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
                      <p className="text-xs text-shogun-subdued leading-relaxed">At the bottom of the sidebar. Downloads a JSON file containing the full audit history of all governance changes. Useful for compliance or reviewing what rules were changed and when.</p>
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
                      <p className="text-xs text-shogun-subdued leading-relaxed">Mado respects the Torii security posture. Browser automation must be explicitly enabled in the agent's permission set. In <strong>SHRINE</strong> tier, Mado is disabled entirely. In <strong>GUARDED</strong>, it's limited to 1 session with no downloads or uploads. In <strong>TACTICAL</strong> and above, full Mado features are available.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-cyan-400" /> Session Management</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Browser sessions are managed automatically. When Shogun shuts down, all active Playwright browser instances are cleanly closed. The Mado page in the sidebar shows the current session status and lets you manually manage active browser contexts.</p>
                   </div>
                   <div className="shogun-card space-y-2 md:col-span-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldAlert className="w-4 h-4 text-cyan-400" /> One Permission Authority</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Torii is the sole permission authority for Mado. The active posture controls browser access, headless or visible mode, autonomous browsing, uploads, downloads, and session limits. Mado is an operational console for runtime health, screenshots, resets, and diagnostics — it does not maintain a second permission system.</p>
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
                         <li>Navigate to <strong>Mado</strong> in the sidebar.</li>
                         <li>If Chromium is not installed, you'll see a <strong>"Install Chromium"</strong> button in the top-right corner.</li>
                         <li>Click it. The system will download and install Playwright + Chromium (1–2 minutes depending on connection).</li>
                         <li>Once complete, the badge changes to a green <strong>"Chromium Ready"</strong> indicator with the version number.</li>
                      </ol>
                      <p className="text-xs text-shogun-subdued leading-relaxed mt-1"><strong>Security Note:</strong> Mado must be enabled in your Torii security posture. At <strong>SHRINE</strong> tier, Mado is completely disabled. <strong>GUARDED</strong> allows 1 session with no downloads/uploads. You need at least <strong>TACTICAL</strong> (headless only) for full Mado features.</p>
                   </div>

                   {/* Step 2: Automatic Session */}
                   <div className="shogun-card space-y-3 border-l-2 border-cyan-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><span className="text-cyan-400 font-mono text-sm">02</span> Let Shogun Manage the Browser</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">You do not need to create browser sessions manually. Shogun creates its managed browser profile automatically the first time a governed task calls <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">browse_web</code>.</p>
                      <ol className="text-xs text-shogun-subdued space-y-1 ml-4 list-decimal">
                         <li>Set browser permissions in <strong>Torii</strong>.</li>
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
                      <p className="text-xs text-shogun-subdued leading-relaxed">Use the Mado console to inspect browser work while Torii remains responsible for permissions:</p>
                      <ol className="text-xs text-shogun-subdued space-y-1 ml-4 list-decimal">
                         <li><strong>Overview:</strong> Check Chromium, agent-browser health, and session count.</li>
                         <li><strong>Screenshots:</strong> Review evidence captured by chat and AgentFlow tasks.</li>
                         <li><strong>Advanced:</strong> Inspect runtime sessions and storage paths, or remove stale sessions.</li>
                         <li><strong>Torii:</strong> Change browser permissions and posture limits.</li>
                      </ol>
                      <p className="text-xs text-shogun-subdued leading-relaxed mt-1"><strong>Design principle:</strong> Mado shows browser operations; Torii governs them.</p>
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

                   {/* Torii Permissions */}
                   <div className="shogun-card space-y-3 border-l-2 border-red-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldAlert className="w-4 h-4 text-red-400" /> Configuring Mado Permissions</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Configure Mado once in <strong>Torii</strong>. These rules apply consistently to chat, Telegram, the Mado API, and AgentFlow browser nodes. Gensui remains an outer fleet-level authority when connected.</p>
                      <div className="bg-shogun-bg rounded-lg p-3 space-y-2">
                         <p className="text-[10px] text-red-400/80 font-bold uppercase tracking-widest">Torii Controls</p>
                         <ul className="text-xs text-shogun-subdued space-y-1 ml-2 list-disc">
                            <li><strong>Mado enabled:</strong> Allows or blocks browser automation entirely.</li>
                            <li><strong>Headless only:</strong> Prevents visible browser windows at restricted postures.</li>
                            <li><strong>Maximum sessions:</strong> Applies to API, agent-managed, and AgentFlow sessions.</li>
                            <li><strong>Autonomous browsing:</strong> Controls unattended browser work.</li>
                            <li><strong>Downloads and uploads:</strong> Governs file transfer through Mado.</li>
                         </ul>
                      </div>
                      <p className="text-xs text-shogun-subdued leading-relaxed mt-1"><strong>Priority:</strong> Gensui policy overrides local Torii when fleet governance is active. Mado itself does not override either authority.</p>
                   </div>

                   {/* Troubleshooting */}
                   <div className="shogun-card space-y-3 border-l-2 border-red-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><span className="text-red-400 font-mono text-sm">⚠</span> Troubleshooting</div>
                      <ul className="text-xs text-shogun-subdued space-y-2 ml-4 list-disc">
                         <li><strong>"Browser automation is disabled"</strong> — Your Torii security tier doesn't allow Mado. Go to <strong>Torii → Security Posture</strong> and switch to GUARDED or higher (GUARDED allows 1 session; TACTICAL+ enables full features).</li>
                         <li><strong>"No active browser session"</strong> — For chat skills (<code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">take_screenshot</code>), you must first use <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">browse_web</code> to navigate to a page.</li>
                         <li><strong>Chromium not installed</strong> — Click "Install Chromium" on the Mado page. Requires internet access for the initial download (~200 MB).</li>
                         <li><strong>Session shows "idle" forever</strong> — The browser launches lazily. It only starts when you perform an action (navigate, screenshot, etc.). This is normal.</li>
                         <li><strong>Visible mode blocked</strong> — The active Torii posture may enforce headless-only browsing. CAMPAIGN or RONIN can permit visible sessions.</li>
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
                       <p><strong className="text-red-400">Ronin gives the AI direct physical control of your computer.</strong> This is not a sandboxed operation. When enabled, Shogun can move your mouse, press keys, read your screen, interact with any application, and execute OS-level commands. This is fundamentally different from browser automation (Mado), which runs in an isolated Chromium sandbox.</p>
                       <div className="bg-[#050508] rounded-lg p-3 border border-red-500/20 space-y-2">
                          <p className="text-red-400 font-bold text-[10px] uppercase tracking-widest">What can go wrong:</p>
                          <ul className="ml-4 list-disc space-y-1.5">
                             <li><strong className="text-red-400">Data Loss:</strong> The AI can click Delete buttons, overwrite files, or drag items to trash. At CAMPAIGN/RONIN tier, file deletion is allowed or only requires approval but mistakes happen in milliseconds.</li>
                             <li><strong className="text-red-400">Credential Exposure:</strong> If the AI types into a password field, opens a password manager, or interacts with banking/crypto apps your credentials could be exposed, logged, or transmitted. At RONIN tier, credential entry is ALLOWED with no gate.</li>
                             <li><strong className="text-red-400">Financial Damage:</strong> The AI can click purchase buttons, submit orders, confirm transactions, or interact with trading platforms. There is no undo for financial actions.</li>
                             <li><strong className="text-red-400">Software Installation:</strong> At CAMPAIGN tier, software installation requires approval. At RONIN tier, the AI can download and install arbitrary software without asking.</li>
                             <li><strong className="text-red-400">Admin Escalation:</strong> At RONIN tier, admin escalation is enabled. The AI can accept UAC prompts, run as administrator, and modify system settings.</li>
                             <li><strong className="text-red-400">External Data Upload:</strong> The AI can open a browser, paste sensitive data, and upload it to external services. At RONIN tier, this is ALLOWED without approval.</li>
                          </ul>
                       </div>
                       <p className="text-red-400 font-bold">Rule of thumb: If you would not give a stranger unsupervised access to your desktop, do not enable CAMPAIGN or RONIN posture on that machine.</p>
                    </div>
                 </div>

                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Shield className="w-4 h-4 text-orange-400" /> Posture Levels</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">{"Ronin has four posture levels. The active posture is set in Torii \u2192 Security Posture and shown in the Ronin header."}</p>
                       <div className="bg-shogun-bg rounded-lg p-3 space-y-2">
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-[#7a8899] bg-[#7a8899]/10 px-2 py-0.5 rounded">DISABLED</span><span className="text-xs text-shogun-subdued">No desktop access at all. Shrine and Guarded tiers.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-shogun-blue bg-shogun-blue/10 px-2 py-0.5 rounded">OBSERVE ONLY</span><span className="text-xs text-shogun-subdued">Screenshots and window listing only. Read-only.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-green-400 bg-green-400/10 px-2 py-0.5 rounded">BROWSER ONLY</span><span className="text-xs text-shogun-subdued">Playwright/Mado browser control only. No desktop.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-orange-400 bg-orange-400/10 px-2 py-0.5 rounded">DESKTOP LIMITED</span><span className="text-xs text-shogun-subdued">Mouse, keyboard, screenshots. No native apps, no shell, no admin. Tactical tier.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-red-400 bg-red-400/10 px-2 py-0.5 rounded">DESKTOP FULL</span><span className="text-xs text-shogun-subdued">{"Full control: native apps, shell commands, admin escalation. Campaign/Ronin tier."} <strong className="text-red-400">DANGEROUS.</strong></span></div>
                       </div>
                    </div>
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Crosshair className="w-4 h-4 text-orange-400" /> Where to Configure</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Ronin posture is controlled by the Security Tier selected in Torii. You cannot enable Ronin independently. It follows the global posture.</p>
                       <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                          <li><strong>SHRINE / GUARDED:</strong> Ronin is disabled. No desktop control at all.</li>
                          <li><strong>TACTICAL:</strong> Ronin is desktop_limited. Mouse + keyboard + screenshots. 1 session max. Dangerous actions blocked.</li>
                          <li><strong>CAMPAIGN:</strong> Ronin is desktop_full. Native apps + shell. 5 sessions max. Dangerous actions require approval.</li>
                          <li><strong>RONIN:</strong> Ronin is desktop_full. Everything allowed. 10 sessions. Admin escalation enabled. <strong className="text-red-400">No safety gates. VM only recommended.</strong></li>
                       </ul>
                       <p className="text-xs text-shogun-subdued leading-relaxed">After selecting a tier, the Ronin constraints appear in the Current Constraints card on the left side of Torii (Ronin Desktop, Ronin Sessions, Mouse/Keyboard).</p>
                    </div>
                 </div>

                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><Lock className="w-4 h-4 text-orange-400" /> Application Trust Levels</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Every application on your OS is classified into one of four trust levels. The Posture Guard evaluates: Agent + Posture + App Trust + Environment = Decision.</p>
                       <div className="bg-shogun-bg rounded-lg p-3 space-y-2">
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-green-400 bg-green-400/10 px-2 py-0.5 rounded">TRUSTED</span><span className="text-xs text-shogun-subdued">VS Code, Notepad, Calculator, Shogun. Safe to interact.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-yellow-400 bg-yellow-400/10 px-2 py-0.5 rounded">RESTRICTED</span><span className="text-xs text-shogun-subdued">Chrome, Excel, PowerPoint. Some caution required.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-orange-400 bg-orange-400/10 px-2 py-0.5 rounded">SENSITIVE</span><span className="text-xs text-shogun-subdued">Outlook, SAP, Salesforce, CRM. Requires elevated posture.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-red-400 bg-red-400/10 px-2 py-0.5 rounded">FORBIDDEN</span><span className="text-xs text-shogun-subdued">Password managers, banking apps, crypto wallets. <strong className="text-red-400">Always blocked, no override.</strong></span></div>
                       </div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">The trust registry comes pre-populated with 50+ applications. View and filter them on the App Trust tab in Ronin.</p>
                    </div>
                    <div className="shogun-card space-y-2">
                       <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldAlert className="w-4 h-4 text-red-400" /> Komainu Guardian (Physical Override)</div>
                       <p className="text-xs text-shogun-subdued leading-relaxed">Komainu is a hardware-level safety mechanism. It monitors for human mouse and keyboard activity and can instantly override the AI. Three levels:</p>
                       <div className="bg-shogun-bg rounded-lg p-3 space-y-2">
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-yellow-400 bg-yellow-400/10 px-2 py-0.5 rounded">LEVEL 1: PAUSE</span><span className="text-xs text-shogun-subdued">Any human input pauses the active Ronin session. Resume manually.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-orange-400 bg-orange-400/10 px-2 py-0.5 rounded">LEVEL 2: TERMINATE</span><span className="text-xs text-shogun-subdued">Any human input kills the active session immediately.</span></div>
                          <div className="flex items-center gap-2"><span className="text-[10px] font-bold text-red-400 bg-red-400/10 px-2 py-0.5 rounded">LEVEL 3: HARAKIRI</span><span className="text-xs text-shogun-subdued">Any human input triggers full emergency stop for all sessions and agents.</span></div>
                       </div>
                       <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Triple-Escape</strong> (press Escape 3 times rapidly) is a hard-coded Level 3 trigger that cannot be disabled, overridden, or circumvented. It always triggers Harakiri.</p>
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
                          <li><strong>Citrix / Cloud Workspace:</strong> Enterprise environments. Policy may be enforced by Gensui.</li>
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
                             <tr className="border-b border-shogun-border/50"><td className="p-2.5">Credential Entry</td><td className="text-center p-2.5 text-red-400">Blocked</td><td className="text-center p-2.5 text-yellow-400">Approval</td><td className="text-center p-2.5 text-green-400">Allowed</td></tr>
                             <tr className="border-b border-shogun-border/50"><td className="p-2.5">File Deletion</td><td className="text-center p-2.5 text-red-400">Blocked</td><td className="text-center p-2.5 text-yellow-400">Approval</td><td className="text-center p-2.5 text-green-400">Allowed</td></tr>
                             <tr className="border-b border-shogun-border/50"><td className="p-2.5">External Uploads</td><td className="text-center p-2.5 text-red-400">Blocked</td><td className="text-center p-2.5 text-yellow-400">Approval</td><td className="text-center p-2.5 text-green-400">Allowed</td></tr>
                             <tr className="border-b border-shogun-border/50"><td className="p-2.5">Software Install</td><td className="text-center p-2.5 text-red-400">Blocked</td><td className="text-center p-2.5 text-yellow-400">Approval</td><td className="text-center p-2.5 text-green-400">Allowed</td></tr>
                             <tr className="border-b border-shogun-border/50"><td className="p-2.5">Native App Interaction</td><td className="text-center p-2.5 text-red-400">Blocked</td><td className="text-center p-2.5 text-green-400">Allowed</td><td className="text-center p-2.5 text-green-400">Allowed</td></tr>
                             <tr className="border-b border-shogun-border/50"><td className="p-2.5">Shell Commands</td><td className="text-center p-2.5 text-red-400">Blocked</td><td className="text-center p-2.5 text-green-400">Allowed</td><td className="text-center p-2.5 text-green-400">Allowed</td></tr>
                             <tr><td className="p-2.5 font-bold text-red-400">Admin Escalation (UAC)</td><td className="text-center p-2.5 text-red-400">Blocked</td><td className="text-center p-2.5 text-red-400">Blocked</td><td className="text-center p-2.5 text-green-400">Allowed</td></tr>
                          </tbody>
                       </table>
                    </div>
                    <p className="text-xs text-red-400 font-bold leading-relaxed">At RONIN tier, every dangerous action is allowed WITHOUT operator approval. This means the AI can delete files, enter credentials, install software, and escalate to admin autonomously. Only use RONIN tier in fully isolated, disposable environments (VMs, sandboxes).</p>
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
                          <li><strong className="text-red-400">Triple-Escape:</strong> Press Escape 3 times rapidly. Hard-coded, cannot be disabled.</li>
                          <li><strong className="text-yellow-400">Komainu Override:</strong> Any human mouse or keyboard input triggers the configured level.</li>
                          <li><strong className="text-red-400">Torii Harakiri:</strong> The global kill switch on the Torii page. Stops everything system-wide.</li>
                       </ul>
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
                       <li>{"Navigate to Sidebar \u2192 Office (under Capabilities)."}</li>
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
                    <p className="text-xs text-shogun-subdued leading-relaxed">{"Every Office operation emits an office.* event into the dual-write audit chain. Events include application, action, file paths, duration, and status. View them on the Logs page filtered by category: office."}</p>
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
                    <p className="text-xs text-shogun-subdued leading-relaxed">{"The Workspace is a single, dedicated directory where the Shogun and all Samurai agents can read, write, and manage files. It serves as the agent\u2019s persistent \u201Cdesk\u201D \u2014 a safe, always-available location to store outputs, share data between agents, and create working documents. The Workspace is disabled only at SHRINE security posture."}</p>
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

             {/* 10. TORII (SECURITY) */}
             {/* ═══════════════════════════════════════════════════════════════ */}
             <section id="ref-torii" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-red-400/40 pb-3">
                   <Lock className="w-6 h-6 text-red-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Torii — Security Portal</h4>
                      <p className="text-xs text-shogun-subdued">Control exactly what your agents are allowed to do, access, and reach.</p>
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
                         <li><strong>RONIN (UNSAFE):</strong> Unrestricted. Only use in completely isolated test environments.</li>
                      </ul>
                      <p className="text-xs text-shogun-subdued leading-relaxed mt-2">Click a tier to switch. Below the tiers, a <strong>Current Constraints</strong> card shows exactly what the active tier allows (Filesystem mode, Network mode, Shell access, etc.).</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Lock className="w-4 h-4 text-red-400" /> Policy Registry (Right Column)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">A list of all security policies defined in the system. Each policy card shows the name, tier badge, permission block count, and whether the kill-switch is enabled. Hover over a policy to reveal buttons:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Eye icon:</strong> Opens a full-screen modal showing every detail of the policy — all permission blocks as JSON.</li>
                         <li><strong>Copy icon:</strong> Exports the policy as JSON to your clipboard.</li>
                         <li><strong>Trash icon:</strong> Deletes the policy (only for user-created policies; built-in ones cannot be deleted).</li>
                      </ul>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-red-400" /> Create Tactical Policy</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Click "Create Tactical Policy" at the bottom of the registry. A form appears where you enter a <strong>name</strong>, choose a <strong>security tier</strong>, write a <strong>description</strong>, and toggle whether the <strong>kill-switch</strong> and <strong>dry-run</strong> are supported. Click "Save Policy" to create it.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-red-500" /> Harakiri Button</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The red button in the top right of the Torii page. Same as the one on the Dashboard — activates the global kill switch. Requires two-step confirmation. Once active, all agents are frozen and the posture locks to SHRINE. Press "Reset Harakiri" to restore normal operation.</p>
                   </div>
                </div>
             </section>

             {/* ═══════════════════════════════════════════════════════════════ */}
             {/* 11. NEXUS (COLLABORATION) */}
             {/* ═══════════════════════════════════════════════════════════════ */}
             <section id="ref-nexus" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-indigo-400/40 pb-3">
                   <Users className="w-6 h-6 text-indigo-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Nexus — The Alliance</h4>
                      <p className="text-xs text-shogun-subdued">Inter-agent collaboration. Work with other Shogun instances across the network.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Key className="w-4 h-4 text-indigo-400" /> Identity Card (Top)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Displays your Shogun's unique ID and public key. Other Shogun instances need this to verify your messages are authentic. Click the copy icon to put your agent ID on the clipboard for sharing.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><GitBranch className="w-4 h-4 text-indigo-400" /> Workspace List (Left Column)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">A list of all Joint Workspaces you have created or joined. Each card shows the workspace name, topic, and number of peer agents connected. Click a workspace to open it. Hover over a card to see the <strong>delete button</strong> (red X in the corner). Deleting a workspace permanently removes it and all its messages.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Package className="w-4 h-4 text-indigo-400" /> "Create Workspace" Button</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Opens a form where you enter a <strong>name</strong>, <strong>description</strong>, and <strong>topic</strong> for the new workspace. After creation, you can invite other Shogun agents by providing their network URL.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Users className="w-4 h-4 text-indigo-400" /> Invite Peers</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Inside a workspace detail view, click <strong>"Invite Peer"</strong>. Enter the <strong>endpoint URL</strong> of the other Shogun (e.g., http://192.168.1.50:8000) and optionally a display name. The system will contact the remote agent, exchange identity information, and add it to the workspace.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><MessageSquare className="w-4 h-4 text-indigo-400" /> A2A Message Thread</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Inside a workspace, the right panel shows all messages exchanged between agents. Messages can be typed in the compose box at the bottom. Choose a <strong>message type</strong> from the dropdown: "update" for status reports, "proposal" for suggestions, "approval" for sign-offs, or "task" for actionable assignments. Messages are automatically signed with your agent's identity.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-indigo-400" /> Shared Whiteboard</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Below the message thread, a full-width text editor where all agents in the workspace can collaboratively write plans, code, or reports. Click <strong>"Edit"</strong> to enter editing mode, make your changes, then click <strong>"Save"</strong> to publish them to all connected peers.</p>
                   </div>
                </div>
             </section>

             {/* 11a. NEXUS EXTERNAL GATEWAY */}
             <section id="ref-nexus-gateway" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-indigo-400/40 pb-3">
                   <Link2 className="w-6 h-6 text-indigo-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Nexus External Gateway</h4>
                      <p className="text-xs text-shogun-subdued">Bidirectional interoperability with Microsoft 365, Salesforce, Google, and ServiceNow agents. Send and receive tasks through governed A2A channels.</p>
                   </div>
                </div>
                <div className="shogun-card space-y-3 border-l-2 border-indigo-400/40">
                   <div className="font-bold text-shogun-text flex items-center gap-2"><Zap className="w-4 h-4 text-indigo-400" /> What Is the External Gateway?</div>
                   <p className="text-xs text-shogun-subdued leading-relaxed">The Nexus External Gateway enables <strong>bidirectional</strong> communication between Shogun and enterprise AI agents. <strong>Inbound:</strong> external platforms (Microsoft 365 Copilot, Salesforce Einstein/Agentforce, Google Vertex AI, ServiceNow) send tasks into Shogun for execution. <strong>Outbound:</strong> Shogun can dispatch tasks <em>to</em> external agents &mdash; e.g. ask Salesforce to update a CRM record, ask M365 to schedule a meeting, or trigger a ServiceNow workflow. Shogun acts as an independent execution and orchestration layer that works <em>alongside</em> enterprise agents, not as a replacement. No vendor SDKs, no platform lock-in. Just standard HTTP + Bearer tokens.</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                   <div className="shogun-card space-y-2 border-l-2 border-shogun-blue/40">
                      <div className="font-bold text-shogun-text text-sm">Standalone Mode</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Shogun runs independently with local agents, models, browser control, and memory. No external connectivity needed.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-indigo-400/40">
                      <div className="font-bold text-shogun-text text-sm">Enterprise-Connected Mode</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">External agents submit tasks via A2A, webhooks, or MCP. Shogun executes and returns results.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-red-400/40">
                      <div className="font-bold text-shogun-text text-sm">Governed Hybrid Mode</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Both modes combined, with Gensui enforcing postures, platform allowlists, and real-time policy checks on every task.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Key className="w-4 h-4 text-indigo-400" /> Register an External Agent</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed"><code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">POST /api/v1/nexus/external/register-agent</code> &mdash; Provide a <strong>name</strong>, <strong>platform</strong> (e.g. microsoft_365, salesforce), optional <strong>endpoint_url</strong> (for outbound dispatch), and optional <strong>direction</strong> (<code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">inbound</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">outbound</code>, or <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">bidirectional</code>). Shogun returns a unique API token. Set <strong>endpoint_url</strong> to enable Shogun to dispatch tasks <em>to</em> the external agent.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Search className="w-4 h-4 text-indigo-400" /> Discover Capabilities</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed"><code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">GET /api/v1/nexus/capabilities</code> &mdash; Returns the 9 default capabilities Shogun exposes (e.g. document.summarize, spreadsheet.analyze, email.draft) plus any custom-registered capabilities. External agents query this to know what they can ask for.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Zap className="w-4 h-4 text-indigo-400" /> Submit a Task (A2A)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed"><code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">POST /api/v1/nexus/external/a2a/task</code> &mdash; Send a JSON payload with the action, input context, source_agent_id, and source_platform. Shogun authenticates, policy-checks, routes to the best internal agent, executes via LLM, and returns the result.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-indigo-400" /> Task Status &amp; Callbacks</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed"><code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">GET /external/task/id</code> &mdash; Poll for task status (pending, executing, completed, blocked, failed). <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">POST /external/task/id/callback</code> &mdash; Receive async callback updates from remote systems.</p>
                   </div>
                </div>
                <div className="shogun-card space-y-3 border-l-2 border-red-400/40">
                   <div className="font-bold text-shogun-text flex items-center gap-2"><Shield className="w-4 h-4 text-red-400" /> Four-Layer Security Model</div>
                   <p className="text-xs text-shogun-subdued leading-relaxed">Every inbound task passes through four enforcement layers before execution:</p>
                   <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
                      <div className="p-3 bg-shogun-bg border border-shogun-border rounded-lg space-y-1">
                         <div className="text-xs font-bold text-shogun-text">Bearer Authentication</div>
                         <p className="text-[10px] text-shogun-subdued">Each registered agent has a unique token. Invalid tokens get an immediate 401.</p>
                      </div>
                      <div className="p-3 bg-shogun-bg border border-shogun-border rounded-lg space-y-1">
                         <div className="text-xs font-bold text-shogun-text">Hardcoded Blocks</div>
                         <p className="text-[10px] text-shogun-subdued">desktop.execute, ronin.stop, ronin.harakiri are permanently blocked for all external agents. No override possible.</p>
                      </div>
                      <div className="p-3 bg-shogun-bg border border-shogun-border rounded-lg space-y-1">
                         <div className="text-xs font-bold text-shogun-text">Platform Allowlists</div>
                         <p className="text-[10px] text-shogun-subdued">Per-platform rules control which capabilities each platform can use. M365 can summarize docs but not touch local files.</p>
                      </div>
                      <div className="p-3 bg-shogun-bg border border-shogun-border rounded-lg space-y-1">
                         <div className="text-xs font-bold text-shogun-text">Gensui Posture</div>
                         <p className="text-[10px] text-shogun-subdued">When Gensui is active, its real-time posture can disable all Nexus communication, block browser/desktop sessions, or restrict file writes fleet-wide.</p>
                      </div>
                   </div>
                </div>
                <div className="shogun-card space-y-2">
                   <div className="font-bold text-shogun-text flex items-center gap-2"><FileKey className="w-4 h-4 text-indigo-400" /> Audit Trail</div>
                   <p className="text-xs text-shogun-subdued leading-relaxed">Every gateway operation produces dual-logged audit events: <strong>Layer 1 (Operational)</strong> in the main SQLite database with 90-day retention, and <strong>Layer 2 (Immutable)</strong> in the HMAC-chained append-only database for NIS2/SOC2/EU AI Act compliance with 7-year retention.</p>
                </div>

                {/* Outbound Dispatch */}
                <div className="shogun-card space-y-3 border-l-2 border-purple-400/40">
                   <div className="font-bold text-shogun-text flex items-center gap-2"><ExternalLink className="w-4 h-4 text-purple-400" /> Outbound Dispatch (Shogun &rarr; External Agent)</div>
                   <p className="text-xs text-shogun-subdued leading-relaxed">Shogun can also <strong>send tasks to external agents</strong>. When an external agent has an <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">endpoint_url</code> configured and its direction is <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">outbound</code> or <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">bidirectional</code>, Shogun can dispatch tasks to it.</p>
                   <div className="bg-shogun-bg rounded-lg p-3 space-y-2">
                      <p className="text-[10px] text-purple-400/80 font-bold uppercase tracking-widest">API Endpoints</p>
                      <ul className="text-xs text-shogun-subdued space-y-1.5 ml-2 list-disc">
                         <li><code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">POST /api/v1/nexus/external/dispatch</code> &mdash; Send a task to an external agent. Provide the <strong>agent_id</strong>, <strong>action</strong> (e.g. <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">crm.update_contact</code>), and <strong>input_context</strong>. Shogun POSTs the payload to the agent's endpoint_url with the agent's token as a Bearer header.</li>
                         <li><code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">GET /api/v1/nexus/external/dispatchable-agents</code> &mdash; List all agents that can receive outbound tasks (direction is outbound or bidirectional AND endpoint_url is set).</li>
                      </ul>
                   </div>
                   <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Use cases:</strong> Ask Salesforce to update a CRM record, ask M365 to schedule a meeting, trigger a ServiceNow incident workflow, send processed data back to Google Cloud. The external agent receives a JSON payload with the action, input context, and a task_id for tracking.</p>
                   <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Direction field:</strong> <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">inbound</code> = agent can only send tasks to Shogun. <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">outbound</code> = Shogun can only send tasks to the agent. <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">bidirectional</code> = both directions.</p>
                </div>
             </section>

             {/* 11b. GENSUI (FLEET COMMAND) */}
             {/* ═══════════════════════════════════════════════════════════════ */}
             <section id="ref-gensui" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-indigo-400/40 pb-3">
                   <ShieldAlert className="w-6 h-6 text-indigo-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Gensui — Fleet Command</h4>
                      <p className="text-xs text-shogun-subdued">Connect your Shogun to a centralized Gensui server for fleet management and security coordination.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2 md:col-span-2 border-l-2 border-indigo-400/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Network className="w-4 h-4 text-indigo-400" /> What is Gensui?</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Gensui is a <strong>Central Command server</strong> that manages a fleet of Shogun instances. When your Shogun is connected to a Gensui server, it receives security posture policies, reports telemetry, responds to commands (including remote Harakiri), and participates in coordinated fleet operations. Think of Gensui as the "general" commanding multiple Shogun "officers."</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Link2 className="w-4 h-4 text-indigo-400" /> Connection Form (Not Connected)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">When not connected, the page shows a setup form with four fields:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Server URL:</strong> The address of the Gensui server (e.g., http://localhost:8787). Click "Test Connection" to verify reachability before connecting.</li>
                         <li><strong>Enrollment Token:</strong> A one-time token generated in the Gensui admin panel. Paste it here to auto-enroll this Shogun instance.</li>
                         <li><strong>Instance Name:</strong> A human-readable name for this Shogun (displayed in the Gensui fleet dashboard).</li>
                         <li><strong>Environment:</strong> Choose Development, Staging, or Production to tag this instance.</li>
                      </ul>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-green-400" /> Status Dashboard (Connected)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Once connected, the page transforms into a live status dashboard showing:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Connection status:</strong> Green badge when actively connected, amber when enrolled but offline.</li>
                         <li><strong>Shogun ID:</strong> The unique identifier assigned during enrollment.</li>
                         <li><strong>Last Sync:</strong> Timestamp of the most recent heartbeat or policy sync.</li>
                         <li><strong>Disconnect button:</strong> Severs the fleet link with a confirmation modal.</li>
                      </ul>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Shield className="w-4 h-4 text-indigo-400" /> Active Posture Card</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Displays the security posture pushed from Gensui. Shows 14 permission flags (External Models, Mado Browser, Memory Write, etc.) as green ✅ or red ❌ badges. These posture rules are enforced locally by the Torii and override local settings when Gensui is connected.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-indigo-400" /> Background Services</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">When connected, four background tasks run automatically:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Heartbeat:</strong> Reports status to Gensui every 15 seconds.</li>
                         <li><strong>Policy Sync:</strong> Fetches effective posture every 30 seconds.</li>
                         <li><strong>Command Polling:</strong> Checks for pending commands (e.g., Harakiri) every 5 seconds.</li>
                         <li><strong>Telemetry Push:</strong> Sends buffered events to Gensui every 10 seconds.</li>
                      </ul>
                   </div>
                </div>
             </section>

             {/* ═══════════════════════════════════════════════════════════════ */}
             {/* 12. LOGS (AUDIT TRAIL) */}
             {/* ═══════════════════════════════════════════════════════════════ */}
             <section id="ref-logs" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-subdued/40 pb-3">
                   <Terminal className="w-6 h-6 text-shogun-subdued" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Logs — The Compliance Dashboard</h4>
                      <p className="text-xs text-shogun-subdued">NIS2, SOC2, and EU AI Act-compliant event logging with full trace reconstruction and tamper-proof audit chain.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2 md:col-span-2 border-l-2 border-shogun-blue/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Layers className="w-4 h-4 text-shogun-blue" /> Dual-Layer Architecture</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Every event is written to <strong>two independent stores</strong>: (1) an <strong>operational SQLite log</strong> (fast, searchable, 90-day retention) for day-to-day monitoring, and (2) a <strong>tamper-resistant HMAC-chained audit database</strong> (append-only, 7-year retention) for regulatory evidence. If anyone modifies or deletes an entry in the audit chain, the cryptographic hash chain breaks — and the dashboard flags it immediately.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-shogun-subdued" /> Event Stream</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The main panel shows every event in chronological order. Each row displays: <strong>timestamp</strong>, <strong>category icon</strong>, <strong>severity badge</strong> (info/warn/error/critical), <strong>result status</strong> (green check for success, red X for denied), the <strong>action description</strong>, <strong>event type tag</strong> (e.g., DECISION.CONTEXT), the <strong>model used</strong>, <strong>tool invoked</strong>, and <strong>trace ID link</strong>. Click any event to expand its detail panel. Toggle between <strong>Live</strong> (auto-refresh every 5 seconds) and <strong>Paused</strong> modes.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Filter className="w-4 h-4 text-shogun-subdued" /> Category Tabs</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Eleven filterable categories across the top, each with a real-time event count badge:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Decision:</strong> AI decision provenance — context assembled, influences tracked (EU AI Act). Events: <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">decision.context</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">decision.influences</code>.</li>
                         <li><strong>Oversight:</strong> Human review — AI responses delivered for implicit oversight, emergency shutdowns. Events: <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">oversight.response_delivered</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">oversight.emergency_shutdown</code>.</li>
                         <li><strong>Risk:</strong> Security tier warnings, denied tools, high-autonomy alerts. Events: <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">risk.tools_denied</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">risk.high_autonomy_mode</code>.</li>
                         <li><strong>Model:</strong> Model selection, LLM responses, API errors, fallback activations. Events: <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">model.selected</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">model.response</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">model.error</code>.</li>
                         <li><strong>Policy:</strong> Torii policy evaluations — tools granted or denied with reasons. Events: <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">policy.evaluated</code>.</li>
                         <li><strong>Memory:</strong> Memory recall, search queries, write operations with retrieval provenance. Events: <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">memory.search</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">memory.write</code>.</li>
                         <li><strong>Tools:</strong> Tool/skill executions, arguments, and results. Events: <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">tool.executed</code>.</li>
                         <li><strong>Auth:</strong> Session tracking, security posture changes, API credential lifecycle, kill switch activations. Events: <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">auth.session</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">auth.posture_changed</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">auth.credential_added</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">auth.kill_switch_activated</code>.</li>
                         <li><strong>Incident:</strong> Critical security events — model API failures, kill switch emergency actions, audit chain integrity violations. Events: <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">incident.model_api_error</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">incident.kill_switch</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">incident.chain_broken</code>.</li>
                         <li><strong>System:</strong> Server lifecycle (startup/shutdown), governance configuration changes (Constitution/Mandate), backup and restore provenance. Events: <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">system.startup</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">system.shutdown</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">system.config_changed</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">system.backup_created</code>, <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">system.backup_restored</code>.</li>
                      </ul>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Link2 className="w-4 h-4 text-shogun-blue" /> Trace Reconstruction</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Every chat turn generates a <strong>trace_id</strong> (e.g., <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">trc_d5ae40fb</code>) that links all events in that workflow — from policy evaluation through memory recall, model selection, tool execution, and decision provenance. Click any trace ID link to open the <strong>Trace Reconstruction modal</strong>, which displays every event in the chain as a numbered timeline. This allows full <strong>workflow reconstruction</strong> for incident investigation.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileKey className="w-4 h-4 text-shogun-gold" /> Event Detail Panel</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Click any event to expand a detail panel showing the full NIS2/SOC2 + EU AI Act record:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>WHO/WHAT/WHEN:</strong> User ID, agent, event type, timestamp.</li>
                         <li><strong>MODEL/PROVIDER:</strong> Which AI model and cloud provider handled the request.</li>
                         <li><strong>POLICY:</strong> Security policy reference, decision (allowed/denied), and reason.</li>
                         <li><strong>RISK/TRACE:</strong> Risk score and correlated trace ID.</li>
                         <li><strong>AI Confidence bar:</strong> Color-coded indicator (green ≥ 70%, yellow 40–70%, red &lt; 40%).</li>
                         <li><strong>Framework badges:</strong> Shows which compliance frameworks apply (SOC2, NIS2, EU_AI_ACT).</li>
                         <li><strong>Governance flags:</strong> Human oversight required, evidence completeness, risk level.</li>
                         <li><strong>Detail payload:</strong> Full structured JSON of all event metadata.</li>
                      </ul>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Shield className="w-4 h-4 text-green-500" /> Audit Chain Integrity</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The top-right corner shows a real-time <strong>Chain Intact</strong> indicator (green) or <strong>Chain Broken</strong> alert (red, pulsing). This verifies the HMAC-SHA256 hash chain across all immutable audit records. If the chain is intact, no records have been tampered with. The status bar at the bottom also shows "AUDIT: INTACT" or "BROKEN."</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Download className="w-4 h-4 text-shogun-gold" /> Compliance Export</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Click the download icon to export the <strong>immutable audit log</strong> as a JSON file. This export pulls from the tamper-proof chain (not the operational log), making it suitable for regulatory auditors, compliance reviews, and incident investigations. The export includes all event metadata, governance flags, and chain hashes.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Trash2 className="w-4 h-4 text-red-400" /> Clear Operational Logs</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Click the trash icon to clear the <strong>operational log only</strong>. The immutable audit chain is <strong>never affected</strong> by this action — it is append-only and cannot be cleared. A confirmation dialog warns you before deletion. The clearing event itself is recorded in the immutable audit chain as evidence.</p>
                   </div>
                </div>
             </section>

             {/* 13. MAINTENANCE — BACKUPS, DATA & UPDATES */}
             <section id="ref-maintenance" className="space-y-6 scroll-mt-6">
                <div className="flex items-center gap-3 border-b-2 border-shogun-subdued/40 pb-3">
                   <HardDrive className="w-6 h-6 text-shogun-subdued" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Maintenance — Backups, Data & Updates</h4>
                      <p className="text-xs text-shogun-subdued">Found under the <strong>Maintenance</strong> section at the bottom of the sidebar.</p>
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
                   <div className="shogun-card space-y-2 border-l-2 border-emerald-500/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Download className="w-4 h-4 text-emerald-400" /> System Updates</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Navigate to <strong>Updates</strong> in the sidebar. The system automatically checks for new versions every 6 hours. When an update is available, a green <strong>NEW</strong> badge appears on the sidebar. Click <strong>Install Update</strong> to download, extract, and rebuild — your data, configs, and environment are always preserved.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-amber-500/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-amber-400" /> Restore & Recovery</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Every backup in the list has a <strong>Restore</strong> button. Clicking it overwrites your current database and config files with the backup's contents. A restart is required afterwards. Use this to roll back after a bad config change, recover from corruption, or migrate to a new machine.</p>
                   </div>
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
                      <p className="text-xs text-shogun-subdued leading-relaxed">Shogun is built in three tiers: <strong>Presentation</strong> (the React-based UI you're looking at), <strong>Application</strong> (a FastAPI backend handling all business logic, routing, and orchestration), and <strong>Persistence</strong> (SQLite for structured data, Qdrant for vector memory). Each tier is independent and communicates via REST APIs.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Network className="w-4 h-4 text-shogun-blue" /> Lattice Architecture</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Instead of one monolithic AI, Shogun uses a "Lattice" — a network of specialized sub-agents (Samurai) coordinated by a central Shogun agent. Work is distributed across the lattice based on agent roles and routing profiles. This makes the system resilient, parallelizable, and scalable.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Globe className="w-4 h-4 text-shogun-blue" /> External Integrations</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The system connects outward to cloud AI providers (OpenAI, Anthropic, Gemini, Perplexity, OpenRouter) and local model servers (Ollama). It integrates with Telegram for mobile messaging, supports the A2A (Agent-to-Agent) protocol for cross-network collaboration via Nexus, automates web browsing via Mado (Playwright), connects to email servers (IMAP/SMTP), and syncs with calendar servers (CalDAV).</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Cpu className="w-4 h-4 text-shogun-blue" /> Single-Server Deployment</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The entire Shogun stack runs on a single machine. The backend serves on port 8000, the frontend is a Vite-powered React SPA proxied or served separately, and SQLite/Qdrant run locally. No cloud infrastructure is required — everything stays on your hardware.</p>
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
                   <div className="shogun-card space-y-3 border-t-2 border-indigo-400">
                      <div className="font-bold text-indigo-400 text-lg flex items-center gap-2"><Globe className="w-5 h-5" /> Peer Shoguns</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Other Shogun instances running on different machines. Connected via the Nexus collaboration module using the A2A Protocol. Peers exchange messages, share whiteboard content, and can coordinate on complex multi-agent tasks across network boundaries.</p>
                      <div className="text-[9px] text-shogun-subdued uppercase font-bold tracking-widest bg-shogun-bg p-2 rounded border border-shogun-border">Connected via: Nexus</div>
                   </div>
                   <div className="shogun-card space-y-3 border-t-2 border-indigo-400 md:col-span-3">
                      <div className="font-bold text-indigo-400 text-lg flex items-center gap-2"><ShieldAlert className="w-5 h-5" /> Gensui (Fleet Command)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">An optional Central Command server that sits above multiple Shogun instances. When connected, Gensui pushes security postures, monitors telemetry, issues commands (including remote Harakiri), and coordinates fleet-wide policy. Think of Gensui as the "general" commanding an army of Shogun "officers." Each Shogun enrolls with Gensui and maintains a persistent background connection with heartbeats, policy sync, and command polling.</p>
                      <div className="text-[9px] text-shogun-subdued uppercase font-bold tracking-widest bg-shogun-bg p-2 rounded border border-shogun-border">Connected via: Alliance → Gensui</div>
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
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Database className="w-4 h-4 text-shogun-gold" /> Structured Storage (SQLite)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">All configuration data — agents, providers, routing profiles, governance documents, chat history, certifications, security policies — is stored in a local SQLite database (<code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">shogun.db</code>). This is the "source of truth" for everything except vector embeddings.</p>
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
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Globe className="w-4 h-4 text-indigo-400" /> Shogun → Peers (A2A Protocol)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Inter-Shogun communication uses the <strong>Agent-to-Agent (A2A)</strong> protocol over HTTP. Messages are typed (update, proposal, approval, task) and cryptographically signed with the sender's identity keys. Each peer validates signatures before accepting messages.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Zap className="w-4 h-4 text-shogun-blue" /> Shogun → AI Providers (LLM Calls)</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The routing engine selects a model based on the active routing profile (or uses the default primary model). The request is sent to the chosen provider's API (OpenAI, Anthropic, etc.) with the assembled prompt (user message + system prompt + memory context + constitution). Streaming responses are relayed back to the frontend.</p>
                   </div>
                </div>
             </section>

             {/* 5. Security Layer */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-red-400/40 pb-3">
                   <Lock className="w-6 h-6 text-red-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Security Layer</h4>
                      <p className="text-xs text-shogun-subdued">Defense-in-depth architecture that protects every agent action.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-red-400" /> Tiered Posture System</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Five security tiers (SHRINE → GUARDED → TACTICAL → CAMPAIGN → RONIN) control what agents can access. Each tier defines permissions for filesystem, network, shell, tools, and sub-agent spawning. The active tier applies globally to all agents. Managed in Torii.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><FileText className="w-4 h-4 text-red-400" /> Kaizen Constitution Validator</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Every proposed agent action is validated against the Constitution (written in Kaizen). If an action violates any constitutional rule, it is blocked before execution. The validation happens server-side, so agents cannot bypass it. Rules are evaluated by priority (critical rules are checked first).</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><AlertCircle className="w-4 h-4 text-red-400" /> Harakiri Kill Switch</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">A global emergency mechanism. When activated, <strong>all</strong> agent activity is instantly frozen, the posture locks to SHRINE (maximum protection), and a prominent red banner appears system-wide. Requires a two-step confirmation to activate and a deliberate reset to restore normal operations.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Key className="w-4 h-4 text-red-400" /> Identity & Signing</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Each Shogun instance has a unique ID and cryptographic key pair. All A2A messages are signed, ensuring peers can verify authenticity. API keys for external providers are stored encrypted in the database and never exposed in the frontend.</p>
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
                     { step: 4, title: 'Security Validation', desc: 'The assembled request is checked against the active security posture and constitutional rules. If any violations are found, the request is blocked or modified.', color: 'text-red-400', icon: ShieldCheck },
                     { step: 5, title: 'LLM Invocation', desc: 'The validated prompt is sent to the selected AI model\'s API. The response streams back token-by-token via SSE.', color: 'text-shogun-blue', icon: Cpu },
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
                      <p className="text-xs text-shogun-subdued leading-relaxed">All behavioral optimizations proposed by the Bushido engine are verified against the Kaizen constitution before being applied. This ensures that self-improvement never violates the fundamental laws defined by the operator. The system cannot "optimize its way" past your rules.</p>
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
                <p className="text-shogun-subdued leading-relaxed">Shogun is built with a defense-in-depth security model. Multiple independent layers work together to ensure that no single failure can compromise the system. This page explains every safety mechanism in detail.</p>
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
                      <p className="text-xs text-shogun-subdued leading-relaxed">No single layer is trusted alone. Security is enforced at the posture level (Torii), the constitutional level (Kaizen), the permission level (Shogun Profile), and the runtime level (action validation). An attacker would need to bypass all four layers simultaneously.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-t-2 border-orange-400">
                      <div className="font-bold text-shogun-text text-lg">Least Privilege</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Agents are given only the minimum permissions they need to complete their tasks. By default, agents cannot access the filesystem, execute shell commands, or spawn sub-agents unless explicitly granted by the active security posture and individual permission overrides.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-t-2 border-shogun-gold">
                      <div className="font-bold text-shogun-text text-lg">Fail Closed</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">When in doubt, the system blocks rather than allows. If a constitutional rule is ambiguous, the action is denied. If the security posture cannot be verified, the system defaults to SHRINE (maximum protection). The Harakiri kill switch ensures instant lockdown in emergencies.</p>
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
                     { tier: 'SHRINE', subtitle: 'Maximum Protection', color: 'border-green-500 bg-green-500/5', badge: 'text-green-500 bg-green-500/10 border-green-500/30', desc: 'Zero-trust mode. All external connections are blocked. Agents can only process information locally with no filesystem, network, or shell access. No sub-agent spawning. Every action requires explicit human approval. Use this when you suspect a breach, while auditing, or when running highly sensitive operations.', perms: ['Filesystem: None', 'Network: None (local only)', 'Shell: Blocked', 'Sub-agents: Blocked', 'Tools: Disabled', 'Mail: Disabled', 'Calendar: Disabled', 'Cron: Disabled', 'Mado Browser: Disabled', 'Human approval: Everything'] },
                     { tier: 'GUARDED', subtitle: 'Restricted Operations', color: 'border-blue-500 bg-blue-500/5', badge: 'text-blue-500 bg-blue-500/10 border-blue-500/30', desc: 'Highly restricted. Filesystem access limited to approved directories only. Network restricted to approved endpoints. All tool usage requires human confirmation. Sub-agents limited to 2 maximum. Suitable for production environments where safety takes priority over speed.', perms: ['Filesystem: Allowlist only', 'Network: Approved endpoints only', 'Shell: Blocked', 'Sub-agents: Max 2 (manual)', 'Tools: With approval', 'Mail: Read only', 'Calendar: Read only', 'Cron: View only', 'Mado Browser: Enabled (1 session)', 'Human approval: Most actions'] },
                     { tier: 'TACTICAL', subtitle: 'Balanced (Default)', color: 'border-shogun-gold bg-shogun-gold/5', badge: 'text-shogun-gold bg-shogun-gold/10 border-shogun-gold/30', desc: 'The recommended default. Agents have scoped file access (read and write within designated directories), can use approved tools autonomously, and have filtered network access. Shell commands are still blocked. Up to 5 sub-agents can be spawned. A good balance between productivity and safety.', perms: ['Filesystem: Scoped read/write', 'Network: Filtered (allowlist)', 'Shell: Blocked', 'Sub-agents: Max 5 (manual)', 'Tools: Approved auto-allowed', 'Mail: Read & Send', 'Calendar: Full access', 'Cron: Full access', 'Mado Browser: Headless only', 'Human approval: Dangerous only'] },
                     { tier: 'CAMPAIGN', subtitle: 'High Autonomy', color: 'border-orange-500 bg-orange-500/5', badge: 'text-orange-500 bg-orange-500/10 border-orange-500/30', desc: 'Extended autonomy for advanced users. Broad filesystem access. Full internet access. Shell commands allowed with logging. Sub-agents can auto-spawn based on policies. Only use this in controlled environments where you have monitoring in place and trust the AI models you are running.', perms: ['Filesystem: Broad access', 'Network: Full internet', 'Shell: Allowed (logged)', 'Sub-agents: Auto-spawn enabled', 'Tools: All enabled', 'Mail: Read & Send', 'Calendar: Full access', 'Cron: Full access', 'Mado Browser: Enabled', 'Human approval: Critical only'] },
                     { tier: 'RONIN', subtitle: '⚠ Unrestricted', color: 'border-red-500 bg-red-500/5', badge: 'text-red-500 bg-red-500/10 border-red-500/30', desc: 'No restrictions whatsoever. Full filesystem, network, shell, and tool access with zero oversight. ONLY use this in completely isolated sandbox/test environments with no access to production data, external services, or sensitive information. This tier exists for testing and development purposes only.', perms: ['Filesystem: Unrestricted', 'Network: Unrestricted', 'Shell: Unrestricted', 'Sub-agents: Unrestricted', 'Tools: All enabled', 'Mail: Unrestricted', 'Calendar: Unrestricted', 'Cron: Full access', 'Mado Browser: Autonomous', 'Human approval: None'] },
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
                      <p className="text-xs text-shogun-subdued leading-relaxed">The Constitution is a YAML document written in the Kaizen page. Each rule has a <strong>name</strong>, <strong>description</strong>, <strong>priority level</strong> (critical, high, balanced, medium, low), and <strong>enforcement mode</strong>. Before any agent action is executed, the system checks it against every constitutional rule in priority order. Critical rules are checked first.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-shogun-gold" /> Enforcement Modes</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Rules can be set to different enforcement modes: <strong>Block</strong> (action is stopped entirely), <strong>Warn</strong> (action proceeds but a warning is logged), or <strong>Audit</strong> (action proceeds silently, logged for later review). Critical safety rules should always use "Block" mode.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><RefreshCw className="w-4 h-4 text-shogun-gold" /> Revision History</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Every time you publish the Constitution, a new revision is saved. You can review all past versions in the Kaizen sidebar. This creates an immutable audit trail — you can always see who changed what and when. Useful for compliance and debugging unexpected behavior.</p>
                   </div>
                <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Zap className="w-4 h-4 text-shogun-gold" /> The Mandate</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">In addition to the Constitution (hard rules), the Mandate (Kaizen → Mandate tab) injects soft directives into every AI conversation. While the Constitution blocks actions, the Mandate shapes behavior — tone, language, priorities, and focus areas. Both work together to align the AI with your intentions.</p>
                   </div>
                </div>
              </section>

             {/* 4. ToolGate — Runtime Enforcement */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-orange-400/40 pb-3">
                   <Shield className="w-6 h-6 text-orange-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">ToolGate — Runtime Tool Enforcement</h4>
                      <p className="text-xs text-shogun-subdued">A real-time enforcement engine that inspects every tool call before execution and blocks dangerous operations based on risk analysis and the active security tier.</p>
                   </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Shield className="w-4 h-4 text-orange-400" /> How It Works</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Every time the AI attempts to execute a native tool (send email, create calendar event, browse the web, click the desktop, etc.), the ToolGate engine intercepts the call <strong>before it runs</strong>. It evaluates the tool's risk level against the current security tier's thresholds and either <strong>allows</strong>, <strong>requires confirmation</strong>, or <strong>blocks</strong> the call.</p>
                      <p className="text-xs text-shogun-subdued leading-relaxed">This is separate from PostureGuard (which controls tool <em>visibility</em>). ToolGate adds a second enforcement layer that checks even visible tools for dangerous parameters — for example, allowing the <code className="bg-shogun-bg px-1 py-0.5 rounded text-shogun-text">send_email</code> tool to be available but blocking it if the recipient is an external domain.</p>
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
                      <p className="text-xs text-shogun-subdued leading-relaxed">Each security tier defines two thresholds that control ToolGate's behavior:</p>
                      <ul className="text-xs text-shogun-subdued space-y-1 ml-4 list-disc">
                         <li><strong>Confirm threshold:</strong> Tools with risk scores above this require human confirmation before executing.</li>
                         <li><strong>Block threshold:</strong> Tools with risk scores above this are blocked entirely — no amount of confirmation can override.</li>
                      </ul>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Example: At TACTICAL tier, the confirm threshold is 0.5 and block threshold is 0.8. A tool with risk 0.6 (like send_email) will prompt for confirmation. A tool with risk 0.9 would be blocked outright.</p>
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
                      <p className="text-xs text-shogun-subdued leading-relaxed">This ensures no tool call can bypass ToolGate regardless of the AI model's response format.</p>
                   </div>
                   <div className="shogun-card space-y-2 md:col-span-2">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Activity className="w-4 h-4 text-shogun-blue" /> Audit Trail</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Every ToolGate decision is logged to the compliance dashboard with full provenance: tool name, parameters, computed risk score, the active tier, the decision (allow/confirm/block), and the threshold that triggered the decision. Blocked and confirmed events appear in the <strong>Risk</strong> tab of the Logs page. These entries are dual-written to both Layer 1 (operational, 90-day retention) and Layer 2 (immutable HMAC chain, 7-year retention).</p>
                   </div>
                </div>
             </section>

             {/* 5. Harakiri Emergency Protocol */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-red-500/40 pb-3">
                   <AlertCircle className="w-6 h-6 text-red-500" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">Harakiri — Emergency Protocol</h4>
                      <p className="text-xs text-shogun-subdued">The nuclear option. When everything else fails, this stops the world.</p>
                   </div>
                </div>
                <div className="shogun-card border-l-4 border-red-500 bg-red-500/[0.02] space-y-6">
                   <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-3">
                         <div className="font-bold text-red-400 flex items-center gap-2"><Zap className="w-4 h-4" /> What Happens When Activated</div>
                         <ul className="text-xs text-shogun-subdued space-y-2 ml-4 list-disc leading-relaxed">
                            <li><strong>All agent activity is immediately frozen.</strong> Running tasks are interrupted mid-execution. No new tasks can be started.</li>
                            <li><strong>Security posture locks to SHRINE</strong> (maximum protection). Filesystem, network, shell, and tool access are all revoked.</li>
                            <li><strong>A pulsing red banner appears</strong> at the top of every page in the system, alerting all users that the kill switch is active.</li>
                            <li><strong>A critical log entry is created</strong> with the timestamp and reason for activation.</li>
                            <li><strong>External connections are severed.</strong> Telegram bot, Nexus peers, and outgoing API calls are all paused.</li>
                         </ul>
                      </div>
                      <div className="space-y-3">
                         <div className="font-bold text-shogun-text flex items-center gap-2"><Lock className="w-4 h-4 text-red-400" /> Activation & Recovery</div>
                         <ul className="text-xs text-shogun-subdued space-y-2 ml-4 list-disc leading-relaxed">
                            <li><strong>Two-step confirmation:</strong> You must click the Harakiri button, then confirm in a modal dialog. This prevents accidental activation.</li>
                            <li><strong>Available from two locations:</strong> The Dashboard (Tenshu) and the Security Portal (Torii). Both trigger the same global mechanism.</li>
                            <li><strong>To recover:</strong> Click "Reset Harakiri" on the banner or from the Torii page. The posture returns to TACTICAL (the safe default). You must then manually re-enable any higher postures if desired.</li>
                            <li><strong>No data is lost.</strong> Harakiri only freezes operations — it does not delete or modify any data, memories, agents, or settings.</li>
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
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Terminal className="w-4 h-4 text-shogun-blue" /> Use the Compliance Dashboard</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">The Logs page is your compliance nerve center. Make it a habit to check the <strong>Decision</strong> tab to review AI reasoning provenance, the <strong>Risk</strong> tab for security tier warnings and denied tools, the <strong>Oversight</strong> tab for human review actions, the <strong>Incident</strong> tab for critical alerts (model API failures, kill switch activations, chain integrity violations), and the <strong>System</strong> tab for server lifecycle and governance config changes. Verify the audit chain stays intact. Export the immutable audit log regularly for off-site archival — this is your evidence for NIS2, SOC2, and EU AI Act compliance.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-shogun-blue/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-shogun-blue" /> Test Posture Changes in SHRINE</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Before upgrading to a higher security posture (e.g., TACTICAL → CAMPAIGN), test your constitutional rules in SHRINE mode first. This ensures your guardrails are properly configured before giving agents more freedom.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-shogun-blue/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Network className="w-4 h-4 text-shogun-blue" /> Isolate RONIN Environments</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">If you need RONIN (unrestricted) mode for testing, run it on an isolated machine or VM with no access to production data, credential stores, or external services. Never run RONIN on a machine connected to your main network.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-shogun-blue/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Download className="w-4 h-4 text-shogun-blue" /> Backup Before Major Changes</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Before changing the security posture, modifying the Constitution, or deploying new agents, export a backup via the Data Management tab. This gives you a restore point if something goes wrong.</p>
                   </div>
                   <div className="shogun-card space-y-2 border-l-2 border-shogun-blue/40">
                      <div className="font-bold text-shogun-text flex items-center gap-2"><Users className="w-4 h-4 text-shogun-blue" /> Limit Nexus Peer Access</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed">Only invite trusted Shogun instances as peers in Nexus. Every peer can send messages and propose tasks. Verify the identity of remote agents before accepting workspace invitations. Remove inactive or unknown peers promptly.</p>
                   </div>
                </div>
             </section>

             {/* 6. ToolGate — Runtime Tool Enforcement */}
             <section className="space-y-6">
                <div className="flex items-center gap-3 border-b-2 border-amber-500/40 pb-3">
                   <ShieldAlert className="w-6 h-6 text-amber-400" />
                   <div>
                      <h4 className="text-xl font-bold uppercase tracking-widest">ToolGate — Runtime Tool Enforcement</h4>
                      <p className="text-xs text-shogun-subdued">Per-invocation safety gating with risk scoring and human-in-the-loop confirmation.</p>
                   </div>
                </div>
                <div className="shogun-card space-y-4">
                   <p className="text-xs text-shogun-subdued leading-relaxed">ToolGate sits between PostureGuard (which determines <em>which tools are available</em>) and the tool executor (which <em>runs them</em>). It provides fine-grained, per-call enforcement based on tool risk levels and parameter analysis.</p>
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
                      <p className="text-xs text-shogun-subdued leading-relaxed">Beyond the static risk level, ToolGate inspects <em>how</em> a tool is called. It detects: destructive shell patterns (rm -rf, DROP TABLE, format C:), sensitive system paths (System32, /etc/), recursive delete flags, mass operations (10+ items), credential-like content in typed text, and force flags. These checks can escalate the action from ALLOW → CONFIRM or CONFIRM → BLOCK regardless of the tool's static risk.</p>
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
                         <p className="text-[11px] text-shogun-subdued">Every quarantine and recovery action is logged. The manifest provides a complete history of what was deleted, when, and why.</p>
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
                      <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Risk:</strong> Malicious input that tricks the AI into ignoring its rules. <strong>Mitigation:</strong> Constitutional rules are enforced server-side and cannot be overridden by prompt content. The security posture applies independently of the AI's decision-making.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-red-400 flex items-center gap-2"><AlertCircle className="w-4 h-4" /> Credential Exposure</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Risk:</strong> API keys or secrets leaking through agent responses or logs. <strong>Mitigation:</strong> Keys are stored encrypted in the database and never included in prompts or agent context. The frontend never receives raw key values — only masked previews.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-red-400 flex items-center gap-2"><AlertCircle className="w-4 h-4" /> Runaway Agent</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Risk:</strong> An agent entering a loop, spawning unlimited sub-agents, or consuming excessive API credits. <strong>Mitigation:</strong> Spawn policies limit auto-spawning. The Harakiri kill switch provides instant global shutdown. Resource monitoring in Bushido flags anomalies.</p>
                   </div>
                   <div className="shogun-card space-y-2">
                      <div className="font-bold text-red-400 flex items-center gap-2"><AlertCircle className="w-4 h-4" /> Unauthorized Peer Access</div>
                      <p className="text-xs text-shogun-subdued leading-relaxed"><strong>Risk:</strong> A malicious Shogun instance connecting as a peer and injecting harmful tasks. <strong>Mitigation:</strong> All A2A messages are cryptographically signed. Peers must be explicitly invited by URL. Workspace deletion removes all peer access immediately.</p>
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
                {t('guide.disclaimer_body', 'Shogun is provided for general informational, experimental, and operational use only. It is provided “as is” and “as available,” without warranties of any kind, express or implied, including but not limited to accuracy, fitness for a particular purpose, merchantability, availability, or non-infringement. Users are solely responsible for evaluating, validating, monitoring, and approving any outputs, actions, configurations, or decisions made with or through Shogun. Alpha Horizon disclaims liability for any direct, indirect, incidental, consequential, or special damages arising from the use of, or inability to use, Shogun, except where such limitation is not permitted by applicable law.')}
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
