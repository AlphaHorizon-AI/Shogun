import { useState } from 'react';
import { 
  Book, 
  Shield, 
  Cpu, 
  Zap, 
  Search, 
  ChevronRight, 
  ExternalLink,
  Info,
  Layers,
  Flag,
  Rocket,
  RefreshCw,
  Lock
} from "lucide-react";
import { cn } from '../lib/utils';

type DocTab = 'onboarding' | 'architecture' | 'modules' | 'safety';

export function Guide() {
  const [activeTab, setActiveTab] = useState<DocTab>('onboarding');
  const [searchTerm, setSearchTerm] = useState('');

  const sections = {
    onboarding: [
      { title: 'The Way of the Shogun', content: 'Shogun is an autonomous orchestration framework designed to bridge high-level intent with multi-agent execution. Your role as the Daimyo is to define objectives; Shogun handle the tactics.', icon: Flag },
      { title: 'First Deployment', content: 'Begin at the Katana to link your LLM providers. Without a provider, the system heart remains cold. OpenAI, Anthropic, and local Ollama instances are supported.', icon: Rocket },
      { title: 'Establishing the Shrine', content: 'Visit the Torii to set your initial security posture. We recommend Starting in "Guarded" mode for initial configuration.', icon: Shield },
    ],
    architecture: [
       { title: 'The Tenshu (Dashboard)', content: 'The control center for all system-wide operations. React + FastAPI + PostgreSQL/Redis.', icon: Layers },
       { title: 'Samurai Lattice', content: 'A flat network of sub-agents spawned by the Shogun. Each Samurai manages its own episodic memory and toolset.', icon: Cpu },
       { title: 'Memory Tiers', content: 'Archives provide three levels of persistence: Episodic (Session), Semantic (Knowledge), and Procedural (Skills).', icon: Book },
    ],
    modules: [
       { title: 'Katana (Systems)', content: 'Manage model providers, API credentials, and tool routing maps.', icon: Zap },
       { title: 'Dojo (Skills)', content: 'Install autonomous capabilities (Python, Web Search, Filesystem) from the OpenClaw College.', icon: Book },
       { title: 'Bushido (Reflection)', content: 'The continuous self-correction loop that monitors agent precision and performance.', icon: RefreshCw },
    ],
    safety: [
       { title: 'Torii Security', content: 'Global kill-switches and role-based permissions for every agent in the network.', icon: Shield },
       { title: 'Kaizen Constitution', content: 'The behavioral bounds defined in YAML that agents are strictly forbidden from crossing.', icon: Lock },
    ]
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-5xl mx-auto pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            Framework Guide <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">Knowledge Base</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">Mastering the arts of autonomous orchestration and system governance.</p>
        </div>
        
        <div className="relative max-w-xs w-full">
           <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-shogun-subdued" />
           <input 
             type="text" 
             placeholder="Search docs..."
             value={searchTerm}
             onChange={(e) => setSearchTerm(e.target.value)}
             className="w-full bg-shogun-card border border-shogun-border rounded-lg pl-10 pr-4 py-2 text-xs focus:border-shogun-blue outline-none transition-all"
           />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8 mt-8">
        {/* Nav Sidebar */}
        <div className="lg:col-span-1 space-y-2">
          {(['onboarding', 'architecture', 'modules', 'safety'] as DocTab[]).map((tab) => (
             <button
               key={tab}
               onClick={() => setActiveTab(tab)}
               className={cn(
                 "w-full flex items-center justify-between px-4 py-3 rounded-xl text-sm font-bold uppercase tracking-widest transition-all border",
                 activeTab === tab 
                   ? "bg-shogun-blue/10 text-shogun-blue border-shogun-blue/30 shadow-[0_0_15px_rgba(74,140,199,0.1)]" 
                   : "text-shogun-subdued border-transparent hover:bg-shogun-card hover:text-shogun-text"
               )}
             >
                {tab}
                <ChevronRight className={cn("w-4 h-4 transition-transform", activeTab === tab ? "rotate-90" : "")} />
             </button>
          ))}
          
          <div className="mt-8 pt-6 border-t border-shogun-border space-y-4">
             <div className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest px-4">Community Resources</div>
             <a href="#" className="flex items-center justify-between px-4 py-2 text-xs text-shogun-blue hover:text-shogun-gold transition-colors font-medium group">
                Github Repository <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
             </a>
             <a href="#" className="flex items-center justify-between px-4 py-2 text-xs text-shogun-blue hover:text-shogun-gold transition-colors font-medium group">
                OpenClaw College <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
             </a>
             <a href="#" className="flex items-center justify-between px-4 py-2 text-xs text-shogun-blue hover:text-shogun-gold transition-colors font-medium group">
                Discord Operations <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
             </a>
          </div>
        </div>

        {/* Content Area */}
        <div className="lg:col-span-3 space-y-6">
           <div className="shogun-card !p-8">
              <div className="flex items-center gap-4 mb-8">
                 <div className="w-12 h-12 rounded-2xl bg-shogun-blue/10 flex items-center justify-center text-shogun-blue shadow-[0_0_20px_rgba(74,140,199,0.1)]">
                    <Book className="w-6 h-6" />
                 </div>
                 <div>
                    <h3 className="text-2xl font-bold text-shogun-text capitalize">{activeTab} Manual</h3>
                    <p className="text-xs text-shogun-subdued mt-1 uppercase tracking-widest font-bold">Version 2.0.4 Stable</p>
                 </div>
              </div>

              <div className="space-y-12">
                 {sections[activeTab].map((section, i) => (
                   <div key={i} className="space-y-4 group">
                      <div className="flex items-center gap-3">
                         <div className="w-8 h-8 rounded-lg bg-[#050508] border border-shogun-border flex items-center justify-center text-shogun-gold group-hover:bg-shogun-gold group-hover:text-black transition-all">
                            <section.icon className="w-4 h-4" />
                         </div>
                         <h4 className="text-lg font-bold text-shogun-text group-hover:text-shogun-gold transition-colors">{section.title}</h4>
                      </div>
                      <p className="text-sm text-shogun-subdued leading-relaxed pl-11">
                         {section.content}
                      </p>
                   </div>
                 ))}
              </div>

              <div className="mt-16 p-6 bg-[#050508] border border-shogun-border rounded-2xl flex items-start gap-4">
                 <div className="p-2 bg-shogun-gold/10 rounded-lg shrink-0">
                    <Info className="w-5 h-5 text-shogun-gold" />
                 </div>
                 <div>
                    <h5 className="text-sm font-bold text-shogun-text mb-1 uppercase tracking-wide">Operator Note</h5>
                    <p className="text-xs text-shogun-subdued leading-relaxed">
                       This guide is dynamically generated from system capabilities. If you install new specializations in the Dojo, check back here for updated module instructions.
                    </p>
                 </div>
              </div>
           </div>
        </div>
      </div>
    </div>
  );
}
