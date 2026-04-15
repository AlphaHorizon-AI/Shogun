import { useState } from 'react';
import { 
  Save, 
  ShieldCheck, 
  AlertCircle, 
  CheckCircle2, 
  RefreshCw, 
  BookOpen, 
  Scale, 
  Zap, 
  History,
  FileCode,
  Lock
} from "lucide-react";
import { cn } from '../lib/utils';

export function Kaizen() {
  const [saving, setSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
  
  const [constitution, setConstitution] = useState(`# SHOGUN SYSTEM CONSTITUTION
# --- Global Behavioral Principles ---

core_directives:
  - id: zero_harm
    rule: "Operations must not compromise host system integrity."
    severity: CRITICAL
  
  - id: transparency
    rule: "All autonomous spawns must be logged to the Torii registry."
    severity: HIGH

autonomy_limits:
  max_recursion_depth: 3
  prohibited_tools:
    - shell_rm_root
    - network_sniffing
  approval_required: true

data_sovereignty:
  retention_policy: episodic_decay
  privacy_tier: maximal
`);

  const handleSave = async () => {
    setSaving(true);
    try {
      // Simulate API call to save configuration
      await new Promise(resolve => setTimeout(resolve, 1000));
      setStatusMessage({ type: 'success', text: 'Constitutional rules synchronized across the network.' });
      setTimeout(() => setStatusMessage(null), 3000);
    } catch (error) {
      setStatusMessage({ type: 'error', text: 'Failed to update behavioral laws.' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-6xl mx-auto pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            Kaizen <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">Constitutional Layer</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">Define the fundamental laws and behavioral constraints for the entire Samurai Network.</p>
        </div>
        
        <button 
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 bg-shogun-gold hover:bg-shogun-gold/90 text-black font-bold py-2.5 px-6 rounded-lg transition-all shadow-shogun disabled:opacity-50"
        >
          {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          PUBLISH EDICTS
        </button>
      </div>

      {statusMessage && (
        <div className={cn(
          "p-4 rounded-lg flex items-center gap-3 animate-in slide-in-from-top-2",
          statusMessage.type === 'success' ? "bg-green-500/10 text-green-500 border border-green-500/20" : "bg-red-500/10 text-red-500 border border-red-500/20"
        )}>
          {statusMessage.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          <span className="text-sm font-bold uppercase tracking-widest">{statusMessage.text}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Editor Side */}
        <div className="lg:col-span-2 space-y-4">
           <div className="shogun-card !p-0 overflow-hidden border-shogun-gold/20 flex flex-col min-h-[600px]">
              <div className="p-4 border-b border-shogun-border bg-[#050508]/80 flex items-center justify-between">
                 <div className="flex items-center gap-3">
                    <FileCode className="w-4 h-4 text-shogun-gold" />
                    <span className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">constitution.yaml</span>
                 </div>
                 <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                    <span className="text-[9px] text-shogun-subdued tracking-tighter uppercase font-bold">Valid Syntax</span>
                 </div>
              </div>
              <textarea 
                value={constitution}
                onChange={(e) => setConstitution(e.target.value)}
                className="flex-1 w-full bg-[#02040a] p-6 font-mono text-sm text-[#d1d1d1] outline-none resize-none selection:bg-shogun-gold/20"
                spellCheck={false}
              />
              <div className="p-3 bg-shogun-card/50 border-t border-shogun-border flex justify-between items-center text-[9px] text-shogun-subdued">
                 <span>Ln 24, Col 12</span>
                 <span className="flex items-center gap-1"><Lock className="w-3 h-3" /> System Restricted Mode</span>
              </div>
           </div>
        </div>

        {/* Info/Status Side */}
        <div className="lg:col-span-1 space-y-6">
           <div className="shogun-card space-y-6">
              <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                 <Scale className="w-5 h-5 text-shogun-gold" /> Active Principles
              </h3>
              
              <div className="space-y-4">
                 {[
                   { name: 'Zero Harm', level: 'CRITICAL', icon: ShieldCheck, color: 'text-green-500' },
                   { name: 'Full Audit', level: 'HIGH', icon: BookOpen, color: 'text-shogun-blue' },
                   { name: 'Human Oversight', level: 'BALANCED', icon: Zap, color: 'text-shogun-gold' }
                 ].map((rule) => (
                   <div key={rule.name} className="p-4 bg-[#050508] border border-shogun-border rounded-xl flex items-center justify-between group hover:border-shogun-gold/50 transition-all">
                      <div className="flex items-center gap-3">
                         <rule.icon className={cn("w-4 h-4", rule.color)} />
                         <div>
                            <div className="text-xs font-bold text-shogun-text">{rule.name}</div>
                            <div className="text-[9px] text-shogun-subdued uppercase font-bold tracking-tighter">{rule.level} Priority</div>
                         </div>
                      </div>
                      <ChevronRight className="w-3 h-3 text-shogun-subdued opacity-0 group-hover:opacity-100 transition-all" />
                   </div>
                 ))}
              </div>
           </div>

           <div className="shogun-card bg-shogun-gold/5 border-shogun-gold/20">
              <h4 className="text-xs font-bold text-shogun-gold flex items-center gap-2 mb-3">
                 <History className="w-4 h-4" /> REVISION HISTORY
              </h4>
              <div className="space-y-3">
                 <div className="flex items-start gap-4">
                    <div className="w-1.5 h-1.5 rounded-full bg-shogun-gold mt-1.5" />
                    <div>
                       <div className="text-[10px] text-shogun-text font-bold">Rule Update v2.4.1</div>
                       <div className="text-[9px] text-shogun-subdued">Added max_recursion_depth limit.</div>
                    </div>
                 </div>
                 <div className="flex items-start gap-4 opacity-50">
                    <div className="w-1.5 h-1.5 rounded-full bg-shogun-subdued mt-1.5" />
                    <div>
                       <div className="text-[10px] text-shogun-text font-bold">Initial Seeding</div>
                       <div className="text-[9px] text-shogun-subdued">Baseline behavioral directives established.</div>
                    </div>
                 </div>
              </div>
           </div>

           <div className="p-4 text-center">
              <button className="text-[10px] font-bold text-shogun-gold hover:text-shogun-text uppercase tracking-widest transition-all">
                 Download Audit Log (.JSON)
              </button>
           </div>
        </div>
      </div>
    </div>
  );
}

const ChevronRight = ({ className, ...props }: any) => (
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
    <path d="m9 18 6-6-6-6" />
  </svg>
);
