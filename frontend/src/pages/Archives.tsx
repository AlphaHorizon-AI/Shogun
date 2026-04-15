import { useState, useEffect } from 'react';
import { 
  Database, 
  Search, 
  Filter, 
  Brain, 
  History, 
  Book, 
  Calendar, 
  Star, 
  Trash2, 
  RefreshCw,
  MoreVertical,
  ChevronRight,
  TrendingUp,
  Clock
} from "lucide-react";
import axios from 'axios';
import { cn } from '../lib/utils';

type MemoryCategory = 'all' | 'episodic' | 'semantic' | 'procedural';

export function Archives() {
  const [loading, setLoading] = useState(true);
  const [memories, setMemories] = useState<any[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeCategory, setActiveCategory] = useState<MemoryCategory>('all');
  const [selectedMemory, setSelectedMemory] = useState<any>(null);

  useEffect(() => {
    fetchMemories();
  }, [activeCategory]);

  const fetchMemories = async () => {
    setLoading(true);
    try {
      const url = activeCategory === 'all' 
        ? '/api/v1/memory' 
        : `/api/v1/memory?category=${activeCategory}`;
      const res = await axios.get(url);
      setMemories(res.data.data || []);
    } catch (error) {
      console.error('Error fetching memories:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredMemories = memories.filter(m => 
    m.content.toLowerCase().includes(searchTerm.toLowerCase()) || 
    m.summary?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getCategoryIcon = (cat: string) => {
    switch(cat.toLowerCase()) {
      case 'episodic': return <Calendar className="w-3.5 h-3.5" />;
      case 'semantic': return <Book className="w-3.5 h-3.5" />;
      case 'procedural': return <Brain className="w-3.5 h-3.5" />;
      default: return <Database className="w-3.5 h-3.5" />;
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-6xl mx-auto pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            Archives <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">Memory Core</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">Deep search and audit the persistent knowledge stream of all active agents.</p>
        </div>
        
        <div className="flex items-center gap-3">
          <button 
            onClick={fetchMemories}
            className="p-2.5 bg-shogun-card border border-shogun-border rounded-lg text-shogun-subdued hover:text-shogun-gold transition-colors"
          >
            <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar Filters */}
        <div className="lg:col-span-1 space-y-4">
          <div className="shogun-card !p-2 space-y-1">
            <h3 className="px-3 py-2 text-[10px] font-bold text-shogun-subdued uppercase tracking-widest mb-1 flex items-center gap-2">
              <Filter className="w-3 h-3" /> Categories
            </h3>
            {(['all', 'episodic', 'semantic', 'procedural'] as MemoryCategory[]).map((cat) => (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                className={cn(
                  "w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all",
                  activeCategory === cat 
                    ? "bg-shogun-blue/10 text-shogun-blue border border-shogun-blue/20 font-bold" 
                    : "text-shogun-subdued hover:bg-shogun-card hover:text-shogun-text"
                )}
              >
                <div className="flex items-center gap-3 capitalize">
                  {getCategoryIcon(cat)}
                  {cat}
                </div>
                {activeCategory === cat && <div className="w-1.5 h-1.5 rounded-full bg-shogun-blue shadow-[0_0_8px_rgba(74,140,199,0.8)]" />}
              </button>
            ))}
          </div>

          <div className="shogun-card space-y-4">
             <h3 className="text-[10px] font-bold text-shogun-gold uppercase tracking-widest flex items-center gap-2">
               <Star className="w-3 h-3" /> Memory Salience
             </h3>
             <div className="space-y-3">
                <div className="flex items-center justify-between">
                   <span className="text-xs text-shogun-subdued">Retention Rate</span>
                   <span className="text-xs font-bold text-shogun-text flex items-center gap-1"><TrendingUp className="w-3 h-3 text-green-500" /> 94%</span>
                </div>
                <div className="flex items-center justify-between">
                   <span className="text-xs text-shogun-subdued">Total Records</span>
                   <span className="text-xs font-bold text-shogun-text">{memories.length}</span>
                </div>
             </div>
          </div>
        </div>

        {/* Memory Stream */}
        <div className="lg:col-span-3 space-y-6">
          <div className="shogun-card !p-0 overflow-hidden">
             <div className="p-4 border-b border-shogun-border bg-[#050508]/50 relative">
                <Search className="absolute left-7 top-1/2 -translate-y-1/2 w-4 h-4 text-shogun-subdued" />
                <input 
                  type="text"
                  placeholder="Query memory archives (content, tags, or concepts)..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full bg-shogun-card border border-shogun-border rounded-xl pl-12 pr-4 py-3 text-sm focus:border-shogun-blue outline-none transition-all shadow-inner"
                />
             </div>

             <div className="max-h-[600px] overflow-y-auto scrollbar-hide divide-y divide-shogun-border">
               {loading ? (
                 <div className="p-20 text-center opacity-50 flex flex-col items-center gap-3">
                    <RefreshCw className="w-8 h-8 animate-spin text-shogun-blue" />
                    <span className="text-[10px] font-bold uppercase tracking-widest">Accessing Bi-Temporal Hub...</span>
                 </div>
               ) : filteredMemories.length === 0 ? (
                 <div className="p-20 text-center text-shogun-subdued italic">
                   No relevant memories found in this knowledge sector.
                 </div>
               ) : filteredMemories.map((memory) => (
                 <div 
                   key={memory.id} 
                   onClick={() => setSelectedMemory(memory)}
                   className="p-5 hover:bg-shogun-gold/5 transition-all cursor-pointer group flex items-start gap-5"
                 >
                   <div className="flex flex-col items-center gap-1 min-w-[50px] pt-1">
                      <div className="w-10 h-10 rounded-xl bg-[#050508] border border-shogun-border flex items-center justify-center text-shogun-blue group-hover:bg-shogun-blue/10 transition-colors">
                        {getCategoryIcon(memory.category)}
                      </div>
                      <span className="text-[8px] font-bold uppercase text-shogun-subdued group-hover:text-shogun-blue">{memory.importance > 7 ? 'Vital' : 'Routine'}</span>
                   </div>
                   
                   <div className="flex-1 space-y-2">
                      <div className="flex items-center justify-between">
                         <div className="flex items-center gap-3">
                            <span className="text-xs font-bold text-shogun-text capitalize">{memory.category} Record</span>
                            <span className="text-[10px] text-shogun-subdued flex items-center gap-1"><Clock className="w-3 h-3" /> {new Date(memory.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} • {new Date(memory.created_at).toLocaleDateString()}</span>
                         </div>
                         <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button className="p-1.5 hover:bg-shogun-card rounded text-shogun-subdued hover:text-red-500 transition-colors"><Trash2 className="w-3.5 h-3.5" /></button>
                            <button className="p-1.5 hover:bg-shogun-card rounded text-shogun-subdued hover:text-shogun-gold transition-colors"><MoreVertical className="w-3.5 h-3.5" /></button>
                         </div>
                      </div>
                      <p className="text-sm text-shogun-text leading-relaxed font-medium line-clamp-2">
                        {memory.summary || memory.content}
                      </p>
                      {memory.importance && (
                        <div className="flex items-center gap-2 pt-1">
                           <div className="h-1 flex-1 bg-shogun-border rounded-full overflow-hidden">
                              <div className="h-full bg-shogun-blue" style={{ width: `${memory.importance * 10}%` }} />
                           </div>
                           <span className="text-[9px] font-bold text-shogun-blue">{memory.importance}/10 Salience</span>
                        </div>
                      )}
                   </div>
                   <ChevronRight className="w-4 h-4 text-shogun-border mt-6 opacity-0 group-hover:opacity-100 transition-all group-hover:translate-x-1" />
                 </div>
               ))}
             </div>
          </div>
        </div>
      </div>
      
      {/* Memory Detail Overlay (Simplified) */}
      {selectedMemory && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-300">
           <div className="bg-shogun-bg border border-shogun-border w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300">
              <div className="p-6 border-b border-shogun-border bg-shogun-card flex justify-between items-center">
                 <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-[#050508] border border-shogun-border flex items-center justify-center text-shogun-gold">
                       <History className="w-5 h-5" />
                    </div>
                    <div>
                       <h3 className="text-lg font-bold text-shogun-text">Memory Detailed Audit</h3>
                       <p className="text-[10px] text-shogun-subdued uppercase tracking-widest font-bold">UID: {selectedMemory.id}</p>
                    </div>
                 </div>
                 <button onClick={() => setSelectedMemory(null)} className="p-2 hover:bg-[#0a0e1a] rounded-lg transition-colors">
                    <XCircle className="w-6 h-6 text-shogun-subdued hover:text-shogun-text" />
                 </button>
              </div>
              <div className="p-8 space-y-6">
                 <div className="space-y-4">
                    <h4 className="text-[10px] font-bold text-shogun-blue uppercase tracking-widest">Content Payload</h4>
                    <div className="bg-[#050508] border border-shogun-border p-6 rounded-xl text-sm leading-relaxed text-shogun-text max-h-[300px] overflow-y-auto font-mono">
                       {selectedMemory.content}
                    </div>
                 </div>
                 
                 <div className="grid grid-cols-2 gap-4">
                    <div className="shogun-card">
                       <h4 className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest mb-2">Metadata</h4>
                       <div className="space-y-2">
                          <div className="flex justify-between text-xs">
                             <span className="text-shogun-subdued">Agent</span>
                             <span className="text-shogun-text font-bold">Shogun-Prime</span>
                          </div>
                          <div className="flex justify-between text-xs">
                             <span className="text-shogun-subdued">Retrieved</span>
                             <span className="text-shogun-text font-bold">14 times</span>
                          </div>
                       </div>
                    </div>
                    <div className="shogun-card">
                       <h4 className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest mb-2">Operations</h4>
                       <div className="flex gap-2">
                          <button className="flex-1 py-2 bg-shogun-card border border-shogun-border rounded text-[10px] font-bold uppercase tracking-widest hover:text-shogun-gold hover:border-shogun-gold transition-all">Refactor</button>
                          <button className="flex-1 py-2 bg-shogun-card border border-shogun-border rounded text-[10px] font-bold uppercase tracking-widest hover:text-red-500 hover:border-red-500 transition-all">Archive</button>
                       </div>
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
