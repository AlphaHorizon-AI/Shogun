import { useState } from 'react';
import { 
  Activity, 
  RefreshCw, 
  Target, 
  BrainCircuit, 
  ShieldCheck, 
  TrendingUp, 
  Settings2, 
  Flame,
  Binary,
  Compass,
  Sparkles
} from "lucide-react";
import { cn } from '../lib/utils';

export function Bushido() {
  const [reflectionStrength, setReflectionStrength] = useState(70);
  
  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-6xl mx-auto pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            Bushido <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">Reflection Engine</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">Monitor and calibrate the autonomous feedback loops that optimize agent precision.</p>
        </div>
        
        <div className="flex items-center gap-3">
           <div className="px-4 py-2 bg-shogun-card border border-shogun-border rounded-lg flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.6)]" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-shogun-text">Engine Synchronized</span>
           </div>
           <button className="flex items-center gap-2 bg-shogun-blue hover:bg-shogun-blue/90 text-white font-bold py-2.5 px-6 rounded-lg transition-all shadow-shogun">
             <RefreshCw className="w-4 h-4" />
             FORCE REFLECTION
           </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
         {/* Stats Cards */}
         {[
           { label: 'Avg Fit Quality', value: '91.4%', icon: Target, color: 'text-shogun-gold' },
           { label: 'Active Cycles', value: '1,204', icon: Activity, color: 'text-shogun-blue' },
           { label: 'Optimization Delta', value: '+12.5%', icon: TrendingUp, color: 'text-green-500' },
           { label: 'Neural Load', value: '14%', icon: BrainCircuit, color: 'text-shogun-subdued' }
         ].map((stat, i) => (
           <div key={i} className="shogun-card border-b-2 border-transparent hover:border-shogun-blue transition-all group">
              <div className="flex items-center gap-2 mb-2">
                 <stat.icon className={cn("w-3.5 h-3.5", stat.color)} />
                 <span className="text-[9px] uppercase font-bold tracking-widest text-shogun-subdued">{stat.label}</span>
              </div>
              <div className="text-2xl font-bold text-shogun-text group-hover:scale-105 transition-transform origin-left">{stat.value}</div>
           </div>
         ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Tuning Controls */}
        <div className="lg:col-span-2 space-y-6">
           <div className="shogun-card space-y-8">
              <div className="flex items-center justify-between">
                 <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                    <Settings2 className="w-5 h-5 text-shogun-blue" /> Behavior Calibration
                 </h3>
                 <span className="text-[10px] text-shogun-subdued uppercase font-bold tracking-tighter italic">Deep Refinement Mode v4.1</span>
              </div>

              <div className="space-y-10 py-4">
                 <div className="space-y-4">
                    <div className="flex justify-between items-center">
                       <label className="text-xs font-bold text-shogun-text flex items-center gap-2 uppercase tracking-wide">
                          <Flame className="w-3.5 h-3.5 text-orange-500" /> Reflection Intensity
                       </label>
                       <span className="text-xs font-mono text-shogun-blue">{reflectionStrength}%</span>
                    </div>
                    <input 
                      type="range" 
                      min="0" 
                      max="100" 
                      value={reflectionStrength}
                      onChange={(e) => setReflectionStrength(parseInt(e.target.value))}
                      className="w-full h-1.5 bg-shogun-card rounded-lg appearance-none cursor-pointer accent-shogun-blue"
                    />
                    <p className="text-[10px] text-shogun-subdued">Higher intensity increases token consumption but provides far deeper logical validation.</p>
                 </div>

                 <div className="space-y-4">
                    <div className="flex justify-between items-center">
                       <label className="text-xs font-bold text-shogun-text flex items-center gap-2 uppercase tracking-wide">
                          <Binary className="w-3.5 h-3.5 text-shogun-gold" /> Memory Consolidation Rate
                       </label>
                       <span className="text-xs font-mono text-shogun-gold">0.05 / epoch</span>
                    </div>
                    <input 
                      type="range" 
                      min="0" 
                      max="100" 
                      defaultValue="45"
                      className="w-full h-1.5 bg-shogun-card rounded-lg appearance-none cursor-pointer accent-shogun-gold"
                    />
                    <p className="text-[10px] text-shogun-subdued">Frequency of episodic-to-semantic memory transformation cycles.</p>
                 </div>
                 
                 <div className="space-y-4">
                    <div className="flex justify-between items-center">
                       <label className="text-xs font-bold text-shogun-text flex items-center gap-2 uppercase tracking-wide">
                          <Compass className="w-3.5 h-3.5 text-green-500" /> Exploration Variance
                       </label>
                       <span className="text-xs font-mono text-green-500">0.24</span>
                    </div>
                    <input 
                      type="range" 
                      min="0" 
                      max="100" 
                      defaultValue="24"
                      className="w-full h-1.5 bg-shogun-card rounded-lg appearance-none cursor-pointer accent-green-500"
                    />
                 </div>
              </div>

              <div className="pt-6 border-t border-shogun-border flex gap-4">
                 <button className="flex-1 py-3 bg-shogun-card border border-shogun-border rounded-xl text-xs font-bold uppercase tracking-widest hover:text-shogun-gold hover:border-shogun-gold transition-all">
                    Reset To Baseline
                 </button>
                 <button className="flex-1 py-3 bg-[#1e293b] border border-shogun-blue/30 rounded-xl text-xs font-bold uppercase tracking-widest text-shogun-text hover:bg-shogun-blue transition-all shadow-[0_0_15px_rgba(74,140,199,0.1)]">
                    Save Calibration
                 </button>
              </div>
           </div>
        </div>

        {/* Sidebar Alerts/Info */}
        <div className="lg:col-span-1 space-y-6">
           <div className="shogun-card min-h-[300px]">
              <h3 className="text-sm font-bold flex items-center gap-2 text-shogun-gold mb-6 uppercase tracking-widest">
                 <Sparkles className="w-4 h-4" /> Insight Stream
              </h3>
              
              <div className="space-y-6">
                 {[
                   { msg: 'Agent "Ronin" optimized recursive depth from 5 to 3 due to cost variance.', time: '2m ago' },
                   { msg: 'Memory consolidation cycle cleared 124 redundant episodic records.', time: '14m ago' },
                   { msg: 'Policy violation detected in simulation; Kaizen rule engine corrected behavior.', time: '1h ago' }
                 ].map((insight, i) => (
                   <div key={i} className="flex gap-4 group">
                      <div className="w-1.5 h-1.5 rounded-full bg-shogun-blue mt-1.5 shrink-0 group-hover:scale-150 transition-transform" />
                      <div>
                         <p className="text-[11px] text-shogun-text leading-relaxed">{insight.msg}</p>
                         <span className="text-[9px] text-shogun-subdued block mt-2 font-bold uppercase">{insight.time}</span>
                      </div>
                   </div>
                 ))}
              </div>
           </div>

           <div className="shogun-card bg-shogun-blue/5 border-shogun-blue/20">
              <div className="flex items-center gap-3 mb-3 text-shogun-blue">
                 <ShieldCheck className="w-4 h-4" />
                 <h4 className="text-[10px] font-bold uppercase tracking-widest">Formal Verification</h4>
              </div>
              <p className="text-[10px] text-shogun-subdued leading-relaxed">
                 The Bushido engine uses formal verification loops to ensure that all behavioral optimizations remain strictly within the bounds defined in the Kaizen constitution.
              </p>
           </div>
        </div>
      </div>
    </div>
  );
}
