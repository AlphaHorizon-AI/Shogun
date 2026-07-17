import React, { useState } from 'react';
import { Activity, Beaker, GitCommit, GitMerge, FileDiff, CheckCircle, XCircle, ArrowRight, Play, Loader2, RefreshCw, Cpu, Star } from 'lucide-react';
import { cn } from '../../lib/utils';
import { useTranslation } from '../../i18n';

// Mock data interfaces
interface Skill {
  id: string;
  name: string;
  description: string;
  status: 'optimized' | 'needs_opt' | 'optimizing';
  lastRun: string;
}

interface OptRun {
  id: string;
  skillId: string;
  status: 'running' | 'completed' | 'failed';
  improvementScore?: number;
  timeStarted: string;
}

const mockSkills: Skill[] = [
  { id: '1', name: 'WebSearchOpt', description: 'Optimized web scraping logic', status: 'optimized', lastRun: '2026-07-17 10:00' },
  { id: '2', name: 'DataParser', description: 'JSON and CSV data extraction', status: 'needs_opt', lastRun: '2026-07-16 14:30' },
  { id: '3', name: 'TextSummarizer', description: 'NLP summarization routines', status: 'optimizing', lastRun: '2026-07-17 15:45' },
];

export function SkillOptTab() {
  const { t } = useTranslation();
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
  const [isPromoting, setIsPromoting] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);

  const handlePromote = () => {
    setIsPromoting(true);
    setTimeout(() => setIsPromoting(false), 1500);
  };

  const handleReject = () => {
    setIsRejecting(true);
    setTimeout(() => setIsRejecting(false), 1500);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-shogun-text flex items-center gap-2">
            <Cpu className="w-6 h-6 text-shogun-gold" />
            {t('skillopt.title', 'Skill Optimization Matrix')}
          </h2>
          <p className="text-sm text-shogun-subdued mt-1">
            {t('skillopt.subtitle', 'Monitor, evaluate, and promote AI-generated skill improvements.')}
          </p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-shogun-card border border-shogun-border hover:border-shogun-blue/50 rounded-lg text-sm font-medium transition-all">
          <RefreshCw className="w-4 h-4 text-shogun-blue" />
          {t('skillopt.refresh', 'Refresh Status')}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Available Skills Panel */}
        <div className="lg:col-span-1 space-y-4">
          <div className="shogun-card">
            <h3 className="text-sm font-bold text-shogun-text uppercase tracking-widest mb-4 flex items-center gap-2">
              <Beaker className="w-4 h-4 text-shogun-blue" />
              {t('skillopt.available_skills', 'Available Skills')}
            </h3>
            <div className="space-y-3">
              {mockSkills.map(skill => (
                <button
                  key={skill.id}
                  onClick={() => setSelectedSkill(skill.id)}
                  className={cn(
                    "w-full text-left p-4 rounded-xl border transition-all duration-300",
                    selectedSkill === skill.id
                      ? "bg-shogun-blue/10 border-shogun-blue shadow-[0_0_15px_rgba(74,140,199,0.15)]"
                      : "bg-[#050508] border-shogun-border hover:border-shogun-blue/30"
                  )}
                >
                  <div className="flex justify-between items-start mb-1">
                    <span className="font-semibold text-shogun-text">{skill.name}</span>
                    {skill.status === 'optimized' && <CheckCircle className="w-4 h-4 text-green-400" />}
                    {skill.status === 'optimizing' && <Loader2 className="w-4 h-4 text-amber-400 animate-spin" />}
                    {skill.status === 'needs_opt' && <Play className="w-4 h-4 text-shogun-blue" />}
                  </div>
                  <p className="text-xs text-shogun-subdued line-clamp-1">{skill.description}</p>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Dashboard / Candidate Diffs Panel */}
        <div className="lg:col-span-2 space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="shogun-card bg-gradient-to-br from-[#050508] to-shogun-card hover:border-shogun-blue/30 transition-colors">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-shogun-blue/10 rounded-lg">
                  <Activity className="w-5 h-5 text-shogun-blue" />
                </div>
                <h4 className="text-sm font-bold text-shogun-text">{t('skillopt.active_runs', 'Active Runs')}</h4>
              </div>
              <p className="text-3xl font-bold text-shogun-text mt-2">1</p>
              <p className="text-xs text-shogun-subdued mt-1">{t('skillopt.currently_optimizing', 'Currently optimizing')}</p>
            </div>
            <div className="shogun-card bg-gradient-to-br from-[#050508] to-shogun-card hover:border-green-500/30 transition-colors">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-green-500/10 rounded-lg">
                  <Star className="w-5 h-5 text-green-400" />
                </div>
                <h4 className="text-sm font-bold text-shogun-text">{t('skillopt.avg_improvement', 'Avg Improvement')}</h4>
              </div>
              <p className="text-3xl font-bold text-shogun-text mt-2">+24%</p>
              <p className="text-xs text-shogun-subdued mt-1">{t('skillopt.across_promoted', 'Across all promoted runs')}</p>
            </div>
          </div>

          <div className="shogun-card min-h-[400px] flex flex-col">
            <h3 className="text-sm font-bold text-shogun-text uppercase tracking-widest mb-4 flex items-center gap-2">
              <FileDiff className="w-4 h-4 text-shogun-gold" />
              {t('skillopt.candidate_diffs', 'Candidate Diffs & Promotion')}
            </h3>
            
            {selectedSkill ? (
              <div className="flex-1 flex flex-col animate-in fade-in duration-300">
                <div className="flex-1 bg-[#050508] border border-shogun-border rounded-lg p-4 font-mono text-xs overflow-auto relative">
                  <div className="absolute top-2 right-2 flex gap-2">
                    <span className="px-2 py-1 bg-red-500/10 text-red-400 rounded border border-red-500/20">- 3 lines</span>
                    <span className="px-2 py-1 bg-green-500/10 text-green-400 rounded border border-green-500/20">+ 4 lines</span>
                  </div>
                  <div className="text-shogun-subdued mt-6">
                    <span className="text-red-400 block">- def process_data(data):</span>
                    <span className="text-red-400 block">-     # old implementation</span>
                    <span className="text-red-400 block">-     return data.split(",")</span>
                    <span className="text-green-400 block mt-2">+ def process_data(data):</span>
                    <span className="text-green-400 block">+     """AI optimized implementation for speed"""</span>
                    <span className="text-green-400 block">+     import re</span>
                    <span className="text-green-400 block">+     return re.split(r",\s*", data)</span>
                  </div>
                </div>

                <div className="mt-6 flex items-center justify-end gap-3 pt-4 border-t border-shogun-border">
                  <button 
                    onClick={handleReject}
                    disabled={isRejecting || isPromoting}
                    className="flex items-center gap-2 px-4 py-2 bg-[#050508] hover:bg-red-500/10 text-shogun-subdued hover:text-red-400 border border-shogun-border hover:border-red-500/50 rounded-lg text-sm font-medium transition-all"
                  >
                    {isRejecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
                    {t('skillopt.reject', 'Reject Candidate')}
                  </button>
                  <button 
                    onClick={handlePromote}
                    disabled={isPromoting || isRejecting}
                    className="flex items-center gap-2 px-5 py-2 bg-shogun-gold hover:bg-[#e6b422] text-black rounded-lg text-sm font-bold shadow-[0_0_15px_rgba(212,160,23,0.3)] transition-all"
                  >
                    {isPromoting ? <Loader2 className="w-4 h-4 animate-spin" /> : <GitMerge className="w-4 h-4" />}
                    {t('skillopt.promote', 'Promote to Prod')}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-shogun-subdued flex-col gap-3">
                <GitCommit className="w-10 h-10 opacity-20" />
                <p>{t('skillopt.select_skill', 'Select a skill to view optimization candidates')}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
