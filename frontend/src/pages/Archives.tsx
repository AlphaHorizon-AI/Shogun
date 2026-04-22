import { useState, useEffect, useCallback } from 'react';
import { 
  Database, 
  Search, 
  Filter, 
  Brain, 
  Book, 
  Calendar, 
  Star, 
  Trash2, 
  RefreshCw,
  ChevronRight,
  Clock,
  Pin,
  PinOff,
  Archive,
  X,
  Shield,
  Layers,
  Sparkles,
  Plus,
  ArrowUpDown,
  BarChart3,
  Network,
  Users,
  Info,
  Zap
} from "lucide-react";
import axios from 'axios';
import { cn } from '../lib/utils';
import { useTranslation } from '../i18n';

const API = 'http://localhost:8000/api/v1/memory';
const AGENTS_API = 'http://localhost:8000/api/v1/agents';

type MemoryCategory = 'all' | 'episodic' | 'semantic' | 'procedural' | 'persona' | 'skills';

interface MemoryRecord {
  id: string;
  memory_type: string;
  agent_id: string;
  title: string;
  content: string;
  summary: string | null;
  relevance_score: number;
  importance_score: number;
  confidence_score: number;
  decay_class: string;
  is_pinned: boolean;
  access_count: number;
  successful_use_count: number;
  recall_count: number;
  last_accessed_at: string | null;
  last_confirmed_at: string | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

interface ScoredMemory extends MemoryRecord {
  scores: {
    semantic_similarity: number;
    relevance_score: number;
    importance_score: number;
    confidence_score: number;
    recency_boost: number;
    final: number;
  };
}

interface MemoryStats {
  total_active: number;
  total_archived: number;
  retention_rate: number;
  type_counts: Record<string, number>;
  pinned_count: number;
  avg_relevance: number;
  avg_importance: number;
  qdrant?: {
    points_count?: number;
    status?: string;
    error?: string;
  };
}

interface Agent {
  id: string;
  name: string;
  agent_type: string;
}

export function Archives() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [memories, setMemories] = useState<MemoryRecord[]>([]);
  const [searchResults, setSearchResults] = useState<ScoredMemory[]>([]);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeCategory, setActiveCategory] = useState<MemoryCategory>('all');
  const [selectedAgentId, setSelectedAgentId] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'created_at' | 'relevance' | 'importance'>('created_at');
  const [selectedMemory, setSelectedMemory] = useState<MemoryRecord | ScoredMemory | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // ── Manual Memory Form State ─────────────────────────────
  const [newMemory, setNewMemory] = useState({
    title: '',
    content: '',
    memory_type: 'semantic',
    importance_score: 0.5,
    decay_class: 'medium',
    agent_id: ''
  });

  // ── Fetch Initial Data ─────────────────────────────────────
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const agentsRes = await axios.get(AGENTS_API);
      setAgents(agentsRes.data.data || []);
      
      const statsRes = await axios.get(`${API}/stats`);
      setStats(statsRes.data.data);
      
      // Initial memories
      const params = new URLSearchParams();
      if (activeCategory !== 'all') params.set('memory_type', activeCategory);
      if (selectedAgentId !== 'all') params.set('agent_id', selectedAgentId);
      params.set('sort_by', sortBy);
      
      const memoriesRes = await axios.get(`${API}?${params}`);
      setMemories(memoriesRes.data.data || []);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  }, [activeCategory, selectedAgentId, sortBy]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ── Semantic Search ────────────────────────────────────────
  useEffect(() => {
    const delayDebounceFn = setTimeout(async () => {
      if (searchTerm.trim().length > 2) {
        setSearching(true);
        try {
          const res = await axios.post(`${API}/search`, {
            query: searchTerm,
            agent_id: selectedAgentId === 'all' ? null : selectedAgentId,
            memory_types: activeCategory === 'all' ? null : [activeCategory],
            limit: 20
          });
          setSearchResults(res.data.data || []);
        } catch (error) {
          console.error('Search error:', error);
        } finally {
          setSearching(false);
        }
      } else {
        setSearchResults([]);
      }
    }, 500);

    return () => clearTimeout(delayDebounceFn);
  }, [searchTerm, selectedAgentId, activeCategory]);

  // ── Actions ────────────────────────────────────────────────
  const forgetMemory = async (id: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      await axios.post(`${API}/${id}/forget`);
      setMemories(prev => prev.filter(m => m.id !== id));
      setSearchResults(prev => prev.filter(m => m.id !== id));
      if (selectedMemory?.id === id) setSelectedMemory(null);
      setStatusMsg({ type: 'success', text: 'Memory archived.' });
      fetchStats();
    } catch {
      setStatusMsg({ type: 'error', text: 'Failed to archive memory.' });
    }
    setTimeout(() => setStatusMsg(null), 3000);
  };

  const togglePin = async (id: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      const res = await axios.post(`${API}/${id}/pin`);
      const updated = res.data.data;
      setMemories(prev => prev.map(m => m.id === id ? updated : m));
      setSearchResults(prev => prev.map(m => m.id === id ? { ...m, is_pinned: updated.is_pinned } : m));
      if (selectedMemory?.id === id) setSelectedMemory(prev => prev ? { ...prev, is_pinned: updated.is_pinned } : null);
      setStatusMsg({ type: 'success', text: updated.is_pinned ? 'Memory pinned.' : 'Memory unpinned.' });
      fetchStats();
    } catch {
      setStatusMsg({ type: 'error', text: 'Failed to toggle pin.' });
    }
    setTimeout(() => setStatusMsg(null), 3000);
  };

  const createMemory = async () => {
    if (!newMemory.title || !newMemory.content || !newMemory.agent_id) {
      setStatusMsg({ type: 'error', text: 'Please fill required fields.' });
      return;
    }
    try {
      const res = await axios.post(API, newMemory);
      setMemories(prev => [res.data.data, ...prev]);
      setIsCreateModalOpen(false);
      setNewMemory({ ...newMemory, title: '', content: '' });
      setStatusMsg({ type: 'success', text: 'Memory inscribed successfully.' });
      fetchStats();
    } catch {
      setStatusMsg({ type: 'error', text: 'Failed to inscribe memory.' });
    }
    setTimeout(() => setStatusMsg(null), 3000);
  };

  const reindexVectors = async () => {
    try {
      setLoading(true);
      await axios.post(`${API}/reindex`);
      setStatusMsg({ type: 'success', text: 'Vector index rebuilt.' });
      fetchData();
    } catch {
      setStatusMsg({ type: 'error', text: 'Reindexing failed.' });
      setLoading(false);
    }
    setTimeout(() => setStatusMsg(null), 3000);
  };

  const fetchStats = async () => {
    try {
      const res = await axios.get(`${API}/stats`);
      setStats(res.data.data);
    } catch { /* silent */ }
  };

  // ── Helpers ────────────────────────────────────────────────
  const getCategoryIcon = (cat: string) => {
    switch(cat.toLowerCase()) {
      case 'episodic': return <Calendar className="w-4 h-4" />;
      case 'semantic': return <Book className="w-4 h-4" />;
      case 'procedural': return <Brain className="w-4 h-4" />;
      case 'persona': return <Shield className="w-4 h-4" />;
      case 'skills': return <Zap className="w-4 h-4" />;
      default: return <Database className="w-4 h-4" />;
    }
  };

  const getCategoryColor = (cat: string) => {
    switch(cat.toLowerCase()) {
      case 'episodic': return 'text-purple-400';
      case 'semantic': return 'text-shogun-blue';
      case 'procedural': return 'text-green-400';
      case 'persona': return 'text-shogun-gold';
      case 'skills': return 'text-orange-400';
      default: return 'text-shogun-subdued';
    }
  };

  const timeAgo = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  };

  const categories: MemoryCategory[] = ['all', 'episodic', 'semantic', 'procedural', 'persona', 'skills'];

  const displayedMemories = searchTerm.trim().length > 2 ? searchResults : memories;

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            {t('archives.title', 'Archives')} <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">Memory Core</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">{t('archives.subtitle', 'SOTA semantic retrieval and salience-weighted persistent knowledge store.')}</p>
        </div>
        
        <div className="flex items-center gap-3">
          <button 
            onClick={() => setIsCreateModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-shogun-gold/10 text-shogun-gold border border-shogun-gold/20 rounded-lg text-sm font-bold uppercase tracking-widest hover:bg-shogun-gold/20 transition-all"
          >
            <Plus className="w-4 h-4" /> {t('archives.inscribe', 'Inscribe Memory')}
          </button>
          <button 
            onClick={reindexVectors}
            title="Rebuild Vector Index"
            className="p-2.5 bg-shogun-card border border-shogun-border rounded-lg text-shogun-subdued hover:text-shogun-blue transition-colors"
          >
            <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
          </button>
        </div>
      </div>

      {/* Status Message */}
      {statusMsg && (
        <div className={cn(
          "p-3 rounded-lg flex items-center gap-3 animate-in slide-in-from-top-2 text-sm font-bold uppercase tracking-widest",
          statusMsg.type === 'success' ? "bg-green-500/10 text-green-500 border border-green-500/20" : "bg-red-500/10 text-red-500 border border-red-500/20"
        )}>
          {statusMsg.type === 'success' ? <Sparkles className="w-4 h-4" /> : <Info className="w-4 h-4" />}
          {statusMsg.text}
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Stats & Filter Sidebar */}
        <div className="lg:col-span-3 space-y-6">
          
          {/* Filters Panel */}
          <div className="shogun-card space-y-6">
            <div>
              <h3 className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest mb-3 flex items-center gap-2">
                <Filter className="w-3 h-3" /> Agent Context
              </h3>
              <select 
                value={selectedAgentId}
                onChange={(e) => setSelectedAgentId(e.target.value)}
                className="w-full bg-shogun-bg border border-shogun-border rounded-lg px-3 py-2 text-xs text-shogun-text focus:border-shogun-blue outline-none"
              >
                <option value="all">Global / All Agents</option>
                {agents.map(a => (
                  <option key={a.id} value={a.id}>{a.name} ({a.agent_type})</option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <h3 className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest mb-2 flex items-center gap-2">
                <Network className="w-3 h-3" /> Categorization
              </h3>
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  className={cn(
                    "w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-all",
                    activeCategory === cat 
                      ? "bg-shogun-blue/10 text-shogun-blue border border-shogun-blue/30 font-bold" 
                      : "text-shogun-subdued hover:bg-shogun-bg hover:text-shogun-text"
                  )}
                >
                  <div className="flex items-center gap-3 capitalize">
                    {getCategoryIcon(cat)}
                    {cat}
                  </div>
                  <span className="text-[9px] font-mono opacity-50">
                    {cat === 'all' ? stats?.total_active : stats?.type_counts?.[cat] || 0}
                  </span>
                </button>
              ))}
            </div>

            <div>
              <h3 className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest mb-3 flex items-center gap-2">
                <ArrowUpDown className="w-3 h-3" /> Sort Ordinance
              </h3>
              <div className="grid grid-cols-1 gap-2">
                {[
                  { id: 'created_at', label: 'Chronological' },
                  { id: 'relevance', label: 'Salience' },
                  { id: 'importance', label: 'Importance' }
                ].map(s => (
                  <button
                    key={s.id}
                    onClick={() => setSortBy(s.id as any)}
                    className={cn(
                      "px-3 py-2 rounded-lg text-left text-[10px] uppercase font-bold tracking-widest transition-all",
                      sortBy === s.id ? "bg-shogun-gold/10 text-shogun-gold border border-shogun-gold/30" : "text-shogun-subdued hover:bg-shogun-bg border border-transparent"
                    )}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Salience Metrics Card */}
          <div className="shogun-card !bg-gradient-to-br from-shogun-card to-[#0a0e1a]">
             <h3 className="text-[10px] font-bold text-shogun-gold uppercase tracking-widest flex items-center gap-2 mb-4">
               <Star className="w-3 h-3" /> Salience Metrics
             </h3>
             <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 bg-shogun-bg/50 border border-shogun-border rounded-xl">
                    <span className="text-[9px] text-shogun-subdued uppercase block mb-1">Retention</span>
                    <span className="text-sm font-bold text-green-500">{stats?.retention_rate}%</span>
                  </div>
                  <div className="p-3 bg-shogun-bg/50 border border-shogun-border rounded-xl">
                    <span className="text-[9px] text-shogun-subdued uppercase block mb-1">{t('archives.pinned', 'Pinned')}</span>
                    <span className="text-sm font-bold text-shogun-gold">{stats?.pinned_count}</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between items-center text-[10px] uppercase font-bold">
                    <span className="text-shogun-subdued">Avg Relevance</span>
                    <span className="text-shogun-blue">{(stats?.avg_relevance || 0).toFixed(3)}</span>
                  </div>
                  <div className="h-1.5 bg-shogun-bg border border-shogun-border rounded-full overflow-hidden">
                    <div className="h-full bg-shogun-blue" style={{ width: `${(stats?.avg_relevance || 0) * 100}%` }} />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between items-center text-[10px] uppercase font-bold">
                    <span className="text-shogun-subdued">Avg Importance</span>
                    <span className="text-shogun-gold">{(stats?.avg_importance || 0).toFixed(3)}</span>
                  </div>
                  <div className="h-1.5 bg-shogun-bg border border-shogun-border rounded-full overflow-hidden">
                    <div className="h-full bg-shogun-gold" style={{ width: `${(stats?.avg_importance || 0) * 100}%` }} />
                  </div>
                </div>

                {stats?.qdrant && (
                  <div className="pt-2 border-t border-shogun-border/50">
                    <div className="flex items-center gap-2 text-[9px] text-shogun-subdued mb-1 uppercase tracking-tighter">
                      <Layers className="w-3 h-3 text-shogun-blue" /> Vector Index: {stats.qdrant.status}
                    </div>
                    {stats.qdrant.error && <p className="text-[8px] text-red-500/70 italic leading-tight">{stats.qdrant.error}</p>}
                  </div>
                )}
             </div>
          </div>
        </div>

        {/* Center / Right Content Area */}
        <div className="lg:col-span-9 space-y-6">
          
          {/* Search Header */}
          <div className="shogun-card !p-0 overflow-hidden border-shogun-blue/20">
             <div className="p-4 bg-shogun-blue/5 border-b border-shogun-border flex items-center gap-4 relative">
                <div className="relative flex-1">
                  <Search className={cn(
                    "absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 transition-colors",
                    searching ? "text-shogun-blue animate-pulse" : "text-shogun-subdued"
                  )} />
                  <input 
                    type="text"
                    placeholder={t('archives.search_placeholder', 'Enter semantic query or keyword segment...')}
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full bg-shogun-bg border border-shogun-border rounded-xl pl-12 pr-4 py-3 text-sm focus:border-shogun-blue outline-none transition-all shadow-inner placeholder:text-shogun-subdued/50"
                  />
                  {searchTerm.length > 0 && (
                    <button 
                      onClick={() => setSearchTerm('')}
                      className="absolute right-4 top-1/2 -translate-y-1/2 p-1 hover:bg-shogun-card rounded-md"
                    >
                      <X className="w-3 h-3 text-shogun-subdued" />
                    </button>
                  )}
                </div>
                {searchTerm.trim().length > 2 && (
                   <div className="flex items-center gap-2 text-[10px] font-bold text-shogun-blue uppercase tracking-widest whitespace-nowrap">
                     <Sparkles className="w-3 h-3" /> Semantic Rank Active
                   </div>
                )}
             </div>

             {/* Results Pane */}
             <div className="min-h-[500px] max-h-[800px] overflow-y-auto custom-scrollbar divide-y divide-shogun-border/50 bg-[#050508]/30">
               {loading && displayedMemories.length === 0 ? (
                 <div className="h-[500px] flex flex-col items-center justify-center opacity-50 gap-4">
                    <RefreshCw className="w-10 h-10 animate-spin text-shogun-blue" />
                    <span className="text-[10px] font-bold uppercase tracking-[0.3em] shogun-title">Synchronizing Memory...</span>
                 </div>
               ) : displayedMemories.length === 0 ? (
                 <div className="h-[500px] flex flex-col items-center justify-center text-shogun-subdued gap-6">
                   <div className="w-16 h-16 rounded-full bg-shogun-card border border-shogun-border flex items-center justify-center animate-pulse">
                      <Database className="w-8 h-8 opacity-20" />
                   </div>
                   <div className="text-center">
                     <p className="text-sm font-bold shogun-title mb-2">No Fragments Discovered</p>
                     <p className="text-xs max-w-md px-12 leading-relaxed opacity-60">
                       The persistent knowledge stream contains no fragments matching your criteria. 
                       Try adjusting filters or entering a more descriptive semantic query.
                     </p>
                   </div>
                 </div>
               ) : (
                 <div className="divide-y divide-shogun-border/50">
                    {displayedMemories.map((m) => {
                      const isScored = 'scores' in m;
                      const memory = m as any;
                      return (
                        <div 
                          key={memory.id} 
                          onClick={() => setSelectedMemory(memory)}
                          className="p-5 hover:bg-shogun-blue/[0.03] transition-all cursor-pointer group flex items-start gap-6 relative overflow-hidden"
                        >
                          {/* Rank/Score Indicator (Semantic Search only) */}
                          {isScored && (
                            <div className="absolute left-0 top-0 bottom-0 w-1 bg-shogun-blue opacity-30 group-hover:opacity-100 transition-opacity" />
                          )}

                          {/* Icon Column */}
                          <div className={cn(
                            "w-12 h-12 rounded-2xl bg-shogun-card border border-shogun-border flex flex-col items-center justify-center gap-0.5 shrink-0 transition-all",
                            getCategoryColor(memory.memory_type),
                            "group-hover:border-shogun-blue/30 group-hover:shadow-[0_0_15px_rgba(74,140,199,0.1)]"
                          )}>
                             {getCategoryIcon(memory.memory_type)}
                             <span className="text-[7px] font-bold uppercase opacity-60">
                               {memory.importance_score > 0.8 ? 'Vital' : 'Rec'}
                             </span>
                          </div>

                          {/* Content Column */}
                          <div className="flex-1 min-w-0 space-y-2">
                             <div className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-3 overflow-hidden">
                                   <span className={cn("text-[10px] font-bold uppercase tracking-wider", getCategoryColor(memory.memory_type))}>
                                     {memory.memory_type}
                                   </span>
                                   {memory.is_pinned && <Pin className="w-3 h-3 text-shogun-gold" />}
                                   <span className="text-[10px] text-shogun-subdued flex items-center gap-1.5 border-l border-shogun-border pl-3">
                                      <Clock className="w-3.5 h-3.5" /> {timeAgo(memory.created_at)}
                                   </span>
                                   {isScored && (
                                     <span className="text-[10px] bg-shogun-blue/10 text-shogun-blue px-2 py-0.5 rounded-full font-bold flex items-center gap-1">
                                       <Sparkles className="w-2.5 h-2.5" /> Final: {memory.scores.final.toFixed(3)}
                                     </span>
                                   )}
                                </div>
                                
                                <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 translate-x-2 group-hover:translate-x-0 transition-all">
                                   <button 
                                      onClick={(e) => togglePin(memory.id, e)}
                                      className="p-1.5 hover:bg-shogun-bg border border-transparent hover:border-shogun-border rounded-lg text-shogun-subdued hover:text-shogun-gold transition-all"
                                   >
                                      {memory.is_pinned ? <PinOff className="w-4 h-4" /> : <Pin className="w-4 h-4" />}
                                   </button>
                                   <button 
                                      onClick={(e) => forgetMemory(memory.id, e)}
                                      className="p-1.5 hover:bg-shogun-bg border border-transparent hover:border-shogun-border rounded-lg text-shogun-subdued hover:text-red-500 transition-all"
                                   >
                                      <Trash2 className="w-4 h-4" />
                                   </button>
                                </div>
                             </div>

                             <h4 className="text-sm font-bold text-shogun-text group-hover:text-shogun-blue transition-colors line-clamp-1">{memory.title}</h4>
                             <p className="text-xs text-shogun-subdued/80 leading-relaxed line-clamp-2 italic">
                               {memory.summary || memory.content.slice(0, 200) + '...'}
                             </p>

                             {/* Multi-Score Bar Display */}
                             <div className="grid grid-cols-4 gap-4 items-center pt-2">
                                <div className="space-y-1.5">
                                   <div className="flex justify-between text-[8px] uppercase font-bold text-shogun-subdued">
                                      <span>Similarity</span>
                                      <span className="text-shogun-text font-mono">
                                        {isScored ? (memory.scores.semantic_similarity * 100).toFixed(0) : '—'}%
                                      </span>
                                   </div>
                                   <div className="h-1 bg-shogun-bg rounded-full overflow-hidden">
                                      <div className="h-full bg-white opacity-20" style={{ width: `${(isScored ? memory.scores.semantic_similarity : 0) * 100}%` }} />
                                   </div>
                                </div>
                                <div className="space-y-1.5">
                                   <div className="flex justify-between text-[8px] uppercase font-bold text-shogun-subdued">
                                      <span>Salience</span>
                                      <span className="text-shogun-blue font-mono">
                                         {((isScored ? memory.scores.relevance_score : memory.relevance_score) * 100).toFixed(0)}%
                                      </span>
                                   </div>
                                   <div className="h-1 bg-shogun-bg rounded-full overflow-hidden">
                                      <div 
                                         className="h-full bg-shogun-blue" 
                                         style={{ width: `${(isScored ? memory.scores.relevance_score : memory.relevance_score) * 100}%` }} 
                                      />
                                   </div>
                                </div>
                                <div className="space-y-1.5">
                                   <div className="flex justify-between text-[8px] uppercase font-bold text-shogun-subdued">
                                      <span>Importance</span>
                                      <span className="text-shogun-gold font-mono">
                                         {((isScored ? memory.scores.importance_score : memory.importance_score) * 100).toFixed(0)}%
                                      </span>
                                   </div>
                                   <div className="h-1 bg-shogun-bg rounded-full overflow-hidden">
                                      <div 
                                         className="h-full bg-shogun-gold" 
                                         style={{ width: `${(isScored ? memory.scores.importance_score : memory.importance_score) * 100}%` }} 
                                      />
                                   </div>
                                </div>
                                <div className="flex flex-col items-end">
                                   <span className={cn(
                                     "text-[8px] font-bold uppercase px-2 py-0.5 rounded-md tracking-tighter",
                                     memory.decay_class === 'pinned' ? 'bg-purple-500/10 text-purple-400' : 
                                     memory.decay_class === 'sticky' ? 'bg-shogun-blue/10 text-shogun-blue' :
                                     'bg-shogun-card border border-shogun-border text-shogun-subdued'
                                   )}>
                                     {memory.decay_class}
                                   </span>
                                </div>
                             </div>
                          </div>
                          <ChevronRight className="w-5 h-5 text-shogun-border self-center transition-all group-hover:translate-x-1 group-hover:text-shogun-blue opacity-50" />
                        </div>
                      );
                    })}
                 </div>
               )}
             </div>
          </div>
        </div>
      </div>

      {/* ── MANUALLY INSCRIBE MODAL ────────────────────────────── */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/90 backdrop-blur-md animate-in fade-in duration-300">
           <div className="bg-shogun-bg border border-shogun-border w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden">
              <div className="p-6 border-b border-shogun-border bg-shogun-card flex justify-between items-center">
                 <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-shogun-gold/10 border border-shogun-gold/20 flex items-center justify-center text-shogun-gold">
                       <Plus className="w-6 h-6" />
                    </div>
                    <div>
                       <h3 className="text-xl font-bold shogun-title">Inscribe Memory</h3>
                       <p className="text-xs text-shogun-subdued uppercase tracking-widest font-bold">Manual Fragment Injection</p>
                    </div>
                 </div>
                 <button onClick={() => setIsCreateModalOpen(false)} className="p-2 hover:bg-[#0a0e1a] rounded-lg transition-colors">
                    <X className="w-6 h-6 text-shogun-subdued" />
                 </button>
              </div>

              <div className="p-8 space-y-6">
                 <div className="grid grid-cols-2 gap-6">
                    <div className="space-y-2">
                       <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest block">Memory Type</label>
                       <select 
                         value={newMemory.memory_type}
                         onChange={(e) => setNewMemory({...newMemory, memory_type: e.target.value})}
                         className="w-full bg-shogun-card border border-shogun-border rounded-xl px-4 py-3 text-sm text-shogun-text outline-none focus:border-shogun-blue transition-all"
                       >
                         {categories.filter(c => c !== 'all').map(c => (
                           <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                         ))}
                       </select>
                    </div>
                    <div className="space-y-2">
                       <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest block">Agent Attribution</label>
                       <select 
                         value={newMemory.agent_id}
                         onChange={(e) => setNewMemory({...newMemory, agent_id: e.target.value})}
                         className="w-full bg-shogun-card border border-shogun-border rounded-xl px-4 py-3 text-sm text-shogun-text outline-none focus:border-shogun-blue transition-all"
                       >
                         <option value="">Select Agent...</option>
                         {agents.map(a => (
                           <option key={a.id} value={a.id}>{a.name} ({a.agent_type})</option>
                         ))}
                       </select>
                    </div>
                 </div>

                 <div className="space-y-2">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest block">Memory Title</label>
                    <input 
                      type="text"
                      placeholder="E.g. Operational Guidelines for Project Alpha"
                      value={newMemory.title}
                      onChange={(e) => setNewMemory({...newMemory, title: e.target.value})}
                      className="w-full bg-shogun-card border border-shogun-border rounded-xl px-4 py-3 text-sm text-shogun-text outline-none focus:border-shogun-blue transition-all"
                    />
                 </div>

                 <div className="space-y-2">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest block">Content Payload</label>
                    <textarea 
                      rows={5}
                      placeholder="Paste fragment content here..."
                      value={newMemory.content}
                      onChange={(e) => setNewMemory({...newMemory, content: e.target.value})}
                      className="w-full bg-shogun-card border border-shogun-border rounded-xl px-4 py-3 text-sm text-shogun-text outline-none focus:border-shogun-blue transition-all resize-none font-mono"
                    />
                 </div>

                 <div className="grid grid-cols-2 gap-6 items-center">
                    <div className="space-y-3">
                       <div className="flex justify-between text-[10px] font-bold uppercase tracking-widest">
                         <span className="text-shogun-subdued">Intrinsic Importance</span>
                         <span className="text-shogun-gold">{Math.round(newMemory.importance_score * 100)}%</span>
                       </div>
                       <input 
                         type="range" min="0" max="1" step="0.05"
                         value={newMemory.importance_score}
                         onChange={(e) => setNewMemory({...newMemory, importance_score: parseFloat(e.target.value)})}
                         className="w-full h-2 bg-shogun-card rounded-lg appearance-none cursor-pointer accent-shogun-gold"
                       />
                    </div>
                    <div className="space-y-2">
                       <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest block">Decay Class</label>
                       <div className="flex gap-2">
                         {['fast', 'medium', 'slow', 'sticky', 'pinned'].map(d => (
                           <button 
                             key={d}
                             onClick={() => setNewMemory({...newMemory, decay_class: d})}
                             className={cn(
                               "px-2 py-1 rounded border text-[8px] font-bold uppercase transition-all flex-1",
                               newMemory.decay_class === d ? "bg-shogun-blue/20 border-shogun-blue text-shogun-blue" : "border-shogun-border text-shogun-subdued hover:border-shogun-subdued"
                             )}
                           >
                             {d}
                           </button>
                         ))}
                       </div>
                    </div>
                 </div>
              </div>

              <div className="p-6 bg-shogun-card border-t border-shogun-border mt-auto flex justify-end gap-3">
                 <button onClick={() => setIsCreateModalOpen(false)} className="px-6 py-2.5 rounded-xl border border-shogun-border text-sm font-bold text-shogun-subdued hover:bg-shogun-bg transition-all">Cancel</button>
                 <button onClick={createMemory} className="px-8 py-2.5 rounded-xl bg-shogun-blue text-white text-sm font-bold uppercase tracking-widest hover:brightness-110 transition-all shadow-[0_0_20px_rgba(74,140,199,0.3)]">Create Fragment</button>
              </div>
           </div>
        </div>
      )}

      {/* ── MEMORY DETAIL VIEW ───────────────────────────────── */}
      {selectedMemory && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/90 backdrop-blur-md animate-in fade-in duration-300"
          onClick={() => setSelectedMemory(null)}
        >
           <div 
             className="bg-shogun-bg border border-shogun-border w-full max-w-4xl rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300"
             onClick={e => e.stopPropagation()}
           >
              {/* Header */}
              <div className="p-8 border-b border-shogun-border bg-shogun-card flex justify-between items-start">
                 <div className="flex items-start gap-5">
                    <div className={cn(
                      "w-14 h-14 rounded-2xl bg-[#050508] border border-shogun-border flex items-center justify-center",
                      getCategoryColor(selectedMemory.memory_type)
                    )}>
                       {getCategoryIcon(selectedMemory.memory_type)}
                    </div>
                    <div>
                       <h3 className="text-2xl font-bold shogun-title mb-1">{selectedMemory.title}</h3>
                       <div className="flex items-center gap-4 text-xs font-bold uppercase tracking-widest mt-1">
                         <span className={cn(getCategoryColor(selectedMemory.memory_type))}>{selectedMemory.memory_type}</span>
                         <span className="text-shogun-subdued opacity-30">/</span>
                         <span className="text-shogun-subdued">GUID: {selectedMemory.id}</span>
                         {selectedMemory.is_pinned && <span className="flex items-center gap-1.5 text-shogun-gold bg-shogun-gold/10 px-2.5 py-1 rounded-full"><Pin className="w-3 h-3" /> Pinned</span>}
                       </div>
                    </div>
                 </div>
                 <button onClick={() => setSelectedMemory(null)} className="p-2 hover:bg-[#0a0e1a] rounded-xl transition-colors">
                    <X className="w-8 h-8 text-shogun-subdued hover:text-shogun-text" />
                 </button>
              </div>

              {/* Grid Body */}
              <div className="grid grid-cols-12 max-h-[75vh] overflow-y-auto">
                 {/* Left Content (8 cols) */}
                 <div className="col-span-8 p-8 border-r border-shogun-border space-y-8 bg-[#050508]/20">
                    <div className="space-y-4">
                       <h4 className="text-[10px] font-bold text-shogun-blue uppercase tracking-[0.2em] flex items-center gap-2">
                         <Layers className="w-3.5 h-3.5" /> Intelligence Payload
                       </h4>
                       <div className="bg-shogun-bg border border-shogun-border p-6 rounded-2xl text-[13px] leading-relaxed text-shogun-text font-mono whitespace-pre-wrap shadow-inner min-h-[300px]">
                          {selectedMemory.content || '(Fragment empty)'}
                       </div>
                    </div>
                    
                    {'scores' in selectedMemory && (
                       <div className="space-y-4">
                          <h4 className="text-[10px] font-bold text-shogun-gold uppercase tracking-[0.2em] flex items-center gap-2">
                             <BarChart3 className="w-3.5 h-3.5" /> Semantic Score Analysis
                          </h4>
                          <div className="grid grid-cols-5 gap-3">
                             {[
                               { label: 'Similarity', val: selectedMemory.scores.semantic_similarity, color: 'shogun-blue' },
                               { label: 'Salience', val: selectedMemory.scores.relevance_score, color: 'shogun-blue' },
                               { label: 'Importance', val: selectedMemory.scores.importance_score, color: 'shogun-gold' },
                               { label: 'Confidence', val: selectedMemory.scores.confidence_score, color: 'green-500' },
                               { label: 'Recency', val: selectedMemory.scores.recency_boost, color: 'purple-400' },
                             ].map(s => (
                               <div key={s.label} className="shogun-card !p-3 text-center transition-transform hover:scale-105">
                                 <span className="text-[8px] text-shogun-subdued uppercase font-bold block mb-2">{s.label}</span>
                                 <div className={cn("text-xl font-bold font-mono tracking-tighter text-" + s.color)}>
                                   {Math.round(s.val * 100)}%
                                 </div>
                               </div>
                             ))}
                          </div>
                       </div>
                    )}
                 </div>

                 {/* Right Metadata (4 cols) */}
                 <div className="col-span-4 p-8 bg-shogun-card/50 space-y-8">
                    <div className="space-y-5">
                       <h4 className="text-[10px] font-bold text-shogun-subdued uppercase tracking-[0.2em]">Operational Health</h4>
                       <div className="space-y-4">
                          <div className="flex justify-between items-center bg-shogun-bg/50 p-3 border border-shogun-border rounded-xl">
                             <span className="text-[10px] text-shogun-subdued uppercase font-bold">Decay State</span>
                             <span className={cn(
                               "text-[9px] font-bold uppercase px-2 py-1 rounded-md",
                               selectedMemory.decay_class === 'pinned' ? 'bg-purple-500/10 text-purple-400' : 'bg-shogun-blue/10 text-shogun-blue'
                             )}>
                                {selectedMemory.decay_class}
                             </span>
                          </div>
                          <div className="space-y-1">
                             <div className="flex justify-between text-[10px] text-shogun-subdued uppercase font-bold px-1">
                                <span>Utilization Pattern</span>
                                <span className="text-shogun-text font-mono truncate max-w-[100px]">
                                   {selectedMemory.successful_use_count} of {selectedMemory.access_count}
                                </span>
                             </div>
                             <div className="h-2 bg-shogun-bg border border-shogun-border rounded-full overflow-hidden">
                                <div 
                                  className="h-full bg-green-500 transition-all" 
                                  style={{ width: `${(selectedMemory.successful_use_count / Math.max(1, selectedMemory.access_count)) * 100}%` }} 
                                />
                             </div>
                          </div>
                       </div>
                    </div>

                    <div className="space-y-5">
                       <h4 className="text-[10px] font-bold text-shogun-subdued uppercase tracking-[0.2em]">Provenance Detail</h4>
                       <div className="space-y-3">
                          <div className="flex items-center gap-3 text-xs">
                             <Clock className="w-4 h-4 text-shogun-blue" />
                             <div>
                                <p className="text-shogun-subdued text-[9px] uppercase font-bold">Inscribed At</p>
                                <p className="text-shogun-text font-bold">
                                   {selectedMemory.created_at ? new Date(selectedMemory.created_at).toLocaleString() : 'Just now'}
                                </p>
                             </div>
                          </div>
                          <div className="flex items-center gap-3 text-xs">
                             <Users className="w-4 h-4 text-shogun-gold" />
                             <div>
                                <p className="text-shogun-subdued text-[9px] uppercase font-bold">Attributed Agent</p>
                                <p className="text-shogun-text font-bold">
                                   {agents.find(a => a.id === selectedMemory.agent_id)?.name || 'System Initializer'}
                                </p>
                             </div>
                          </div>
                          <div className="flex items-center gap-3 text-xs opacity-50">
                             <RefreshCw className="w-4 h-4 text-shogun-subdued" />
                             <div>
                                <p className="text-shogun-subdued text-[9px] uppercase font-bold">Last Reinforcement</p>
                                <p className="text-shogun-text font-bold">{timeAgo(selectedMemory.last_confirmed_at)}</p>
                             </div>
                          </div>
                       </div>
                    </div>

                    <div className="pt-8 space-y-3">
                       <button 
                         onClick={() => togglePin(selectedMemory.id)}
                         className="w-full py-3 bg-shogun-bg border border-shogun-border rounded-xl text-xs font-bold uppercase tracking-widest hover:text-shogun-gold hover:border-shogun-gold transition-all flex items-center justify-center gap-3 group"
                       >
                         {selectedMemory.is_pinned ? <><PinOff className="w-4 h-4 group-hover:scale-110" /> Unpin Fragment</> : <><Pin className="w-4 h-4 group-hover:scale-110" /> Pin for Retrieval</>}
                       </button>
                       <button 
                         onClick={() => forgetMemory(selectedMemory.id)}
                         className="w-full py-3 bg-shogun-bg border border-shogun-border rounded-xl text-xs font-bold uppercase tracking-widest hover:text-red-500 hover:border-red-500 transition-all flex items-center justify-center gap-3 group"
                       >
                         <Archive className="w-4 h-4 group-hover:scale-110" /> Move to Archive
                       </button>
                    </div>
                 </div>
              </div>
           </div>
        </div>
      )}

      {/* ── STYLING OVERRIDES (SCROLLBAR) ── */}
      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #1a2235; border-radius: 10px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #4a8cc7; }
      `}</style>
    </div>
  );
}
