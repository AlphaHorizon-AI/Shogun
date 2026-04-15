import { useState, useEffect } from 'react';
import { 
  Search, 
  Plus, 
  Book, 
  ShieldCheck, 
  Zap, 
  RefreshCw,
  Trophy,
  Globe,
  Lock,
  Sparkles,
  AlertCircle,
  CheckCircle2
} from "lucide-react";
import axios from 'axios';
import { cn } from '../lib/utils';

type DojoTab = 'catalog' | 'bundles' | 'specialties';

export function Dojo() {
  const [activeTab, setActiveTab] = useState<DojoTab>('catalog');
  const [loading, setLoading] = useState(true);
  const [skills, setSkills] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSkill, setSelectedSkill] = useState<any>(null);

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [statsRes, skillsRes] = await Promise.all([
        axios.get('/api/v1/dojo/openclaw/stats'),
        axios.get('/api/v1/dojo/openclaw/skills')
      ]);
      setStats(statsRes.data.data);
      setSkills(skillsRes.data.data || []);
    } catch (error) {
      console.error('Error fetching Dojo data:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredSkills = skills.filter(s => 
    s.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
    s.description?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-7xl mx-auto pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            The Dojo <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">OpenClaw Hub</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">Discover and install specialized skills from the global OpenClaw College registry.</p>
        </div>
        
        <div className="flex items-center gap-3">
           <div className="hidden lg:flex items-center gap-6 px-6 border-r border-shogun-border">
              <div className="flex flex-col">
                 <span className="text-[10px] text-shogun-subdued uppercase font-bold tracking-widest leading-none">Catalog</span>
                 <span className="text-xl font-bold text-shogun-gold">{stats?.skills || '...'} <span className="text-[10px] font-normal">Skills</span></span>
              </div>
              <div className="flex flex-col">
                 <span className="text-[10px] text-shogun-subdued uppercase font-bold tracking-widest leading-none">Community</span>
                 <span className="text-xl font-bold text-shogun-blue">{stats?.agents || '...'} <span className="text-[10px] font-normal">Labs</span></span>
              </div>
           </div>
           <button 
             onClick={fetchData}
             className="p-2.5 bg-shogun-card border border-shogun-border rounded-lg text-shogun-subdued hover:text-shogun-gold transition-colors"
           >
             <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
           </button>
        </div>
      </div>

      <div className="flex border-b border-shogun-border">
        {(['catalog', 'bundles', 'specialties'] as DojoTab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              "px-6 py-3 text-sm font-bold uppercase tracking-widest transition-all relative",
              activeTab === tab ? "text-shogun-gold" : "text-shogun-subdued hover:text-shogun-text"
            )}
          >
            {tab === 'catalog' && 'Skill Catalog'}
            {tab === 'bundles' && 'Ready Bundles'}
            {tab === 'specialties' && 'Specializations'}
            {activeTab === tab && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-shogun-gold shadow-[0_0_10px_rgba(212,160,23,0.5)]" />
            )}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8 mt-6">
        {/* Search and Sidebar */}
        <div className="lg:col-span-1 space-y-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-shogun-subdued" />
            <input 
              type="text" 
              placeholder="Filter Dojo..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-[#050508] border border-shogun-border rounded-xl pl-10 pr-4 py-3 text-sm focus:border-shogun-gold outline-none transition-all shadow-inner"
            />
          </div>

          <div className="shogun-card space-y-4">
             <h3 className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest border-b border-shogun-border pb-2 mb-4">Trending Tags</h3>
             <div className="flex flex-wrap gap-2">
                {['Research', 'Coding', 'Web', 'Analysis', 'Creative', 'DevOps'].map(tag => (
                   <span key={tag} className="text-[10px] px-2 py-1 bg-[#050508] border border-shogun-border rounded hover:border-shogun-gold hover:text-shogun-gold transition-colors cursor-pointer">{tag}</span>
                ))}
             </div>
          </div>

          <div className="shogun-card bg-shogun-blue/5 border-shogun-blue/20">
             <div className="flex items-center gap-3 mb-3">
               <Trophy className="w-5 h-5 text-shogun-gold" />
               <h4 className="text-sm font-bold text-shogun-text">OpenClaw Certified</h4>
             </div>
             <p className="text-[10px] text-shogun-subdued leading-relaxed">
               All skills in the Dojo have undergone automated safety auditing by the OpenClaw College board. Verified skills display the "Zen" mark of stability.
             </p>
          </div>
        </div>

        {/* Content */}
        <div className="lg:col-span-3">
           {loading ? (
             <div className="p-20 text-center shogun-card bg-[#050508]/20 flex flex-col items-center gap-4 border-dashed">
                <div className="relative">
                   <RefreshCw className="w-10 h-10 animate-spin text-shogun-gold" />
                   <Sparkles className="absolute -top-1 -right-1 w-4 h-4 text-shogun-blue animate-pulse" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-shogun-subdued">Syncing with OpenClaw College...</span>
             </div>
           ) : (
             <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {filteredSkills.map((skill) => (
                  <div 
                    key={skill.id} 
                    onClick={() => setSelectedSkill(skill)}
                    className="shogun-card group hover:border-shogun-gold/50 cursor-pointer transition-all flex flex-col"
                  >
                    <div className="flex justify-between items-start mb-4">
                       <div className="w-12 h-12 bg-[#050508] border border-shogun-border rounded-xl flex items-center justify-center text-shogun-gold group-hover:bg-shogun-gold/10 transition-colors">
                          <Book className="w-6 h-6" />
                       </div>
                       <div className="flex flex-col items-end">
                          <code className="text-[9px] bg-shogun-card px-1.5 py-0.5 rounded border border-shogun-border text-shogun-subdued">v{skill.version}</code>
                          <span className={cn(
                            "text-[8px] font-bold uppercase tracking-widest mt-1",
                            skill.risk_tier === 'shrine' ? 'text-shogun-gold' : skill.risk_tier === 'tactical' ? 'text-shogun-blue' : 'text-red-500'
                          )}>{skill.risk_tier}</span>
                       </div>
                    </div>
                    
                    <h4 className="text-lg font-bold text-shogun-text group-hover:text-shogun-gold transition-colors">{skill.name}</h4>
                    <p className="text-xs text-shogun-subdued mt-2 line-clamp-3 leading-relaxed flex-1">
                      {skill.description}
                    </p>
                    
                    <div className="mt-6 pt-4 border-t border-shogun-border flex items-center justify-between">
                       <div className="flex gap-2">
                          {skill.permissions?.network && <Globe className="w-3 h-3 text-shogun-blue" />}
                          {skill.permissions?.shell && <Zap className="w-3 h-3 text-red-500" />}
                          {skill.permissions?.filesystem_write && <ShieldCheck className="w-3 h-3 text-green-500" />}
                       </div>
                       <div className="flex items-center gap-1 text-[10px] font-mono text-shogun-subdued">
                          <Plus className="w-3 h-3" /> Install
                       </div>
                    </div>
                  </div>
                ))}
             </div>
           )}
        </div>
      </div>

      {/* Skill Detail Modal */}
      {selectedSkill && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-300">
           <div className="bg-shogun-bg border border-shogun-border w-full max-w-3xl rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300">
              <div className="p-6 border-b border-shogun-border bg-shogun-card flex justify-between items-center">
                 <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-[#050508] border border-shogun-border flex items-center justify-center text-shogun-gold">
                       <Zap className="w-5 h-5" />
                    </div>
                    <div>
                       <h3 className="text-lg font-bold text-shogun-text">{selectedSkill.name}</h3>
                       <p className="text-[10px] text-shogun-subdued uppercase tracking-widest font-bold">Faculty: {selectedSkill.faculty}</p>
                    </div>
                 </div>
                 <button onClick={() => setSelectedSkill(null)} className="p-2 hover:bg-[#0a0e1a] rounded-lg transition-colors">
                    <AlertCircle className="w-6 h-6 text-shogun-subdued rotate-45" />
                 </button>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2">
                 <div className="p-8 space-y-6 border-r border-shogun-border">
                    <div className="space-y-3">
                       <h4 className="text-[10px] font-bold text-shogun-blue uppercase tracking-widest">Description</h4>
                       <p className="text-sm text-shogun-text leading-relaxed">
                          {selectedSkill.description}
                       </p>
                    </div>

                    <div className="space-y-3">
                       <h4 className="text-[10px] font-bold text-shogun-blue uppercase tracking-widest">Capabilities</h4>
                       <div className="flex flex-wrap gap-2">
                          {(selectedSkill.capabilities || []).map((cap: string) => (
                             <span key={cap} className="text-[10px] px-2 py-1 bg-shogun-card border border-shogun-border rounded text-shogun-subdued">{cap}</span>
                          ))}
                       </div>
                    </div>
                 </div>

                 <div className="p-8 space-y-6 bg-[#050508]/30">
                    <div className="space-y-4">
                       <h4 className="text-[10px] font-bold text-shogun-gold uppercase tracking-widest flex items-center gap-2">
                          <Lock className="w-3 h-3" /> Permission Audit
                       </h4>
                       <div className="space-y-2">
                          {Object.entries(selectedSkill.permissions || {}).map(([key, val]: [string, any]) => (
                             <div key={key} className="flex items-center justify-between p-3 bg-shogun-bg border border-shogun-border rounded-lg">
                                <span className="text-xs text-shogun-text font-bold capitalize">{key.replace('_', ' ')}</span>
                                {val ? <CheckCircle2 className="w-4 h-4 text-green-500" /> : <XCircle className="w-4 h-4 text-shogun-subdued" />}
                             </div>
                          ))}
                       </div>
                    </div>

                    <div className="pt-4">
                       <button className="w-full py-4 bg-shogun-gold hover:bg-shogun-gold/90 text-black font-bold text-xs uppercase tracking-[0.2em] rounded-xl shadow-shogun transition-all flex items-center justify-center gap-3">
                          <Plus className="w-5 h-5" />
                          Install to Shogun Prime
                       </button>
                       <p className="text-[9px] text-shogun-subdued mt-3 text-center italic">
                          Installing this skill adds new capabilities to the primary agent's task-routing matrix.
                       </p>
                    </div>
                 </div>
              </div>
           </div>
        </div>
      )}
    </div>
  );
}

const XCircle = ({ className, ...props }: any) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    {...props}
  >
    <circle cx="12" cy="12" r="10" />
    <path d="m15 9-6 6" />
    <path d="m9 9 6 6" />
  </svg>
);
