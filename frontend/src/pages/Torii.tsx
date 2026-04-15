import { useState, useEffect } from 'react';
import { 
  Shield, 
  Lock, 
  Unlock, 
  AlertTriangle, 
  Power, 
  ShieldAlert, 
  CheckCircle2, 
  RefreshCw,
  Search,
  Eye,
  Activity
} from "lucide-react";
import axios from 'axios';
import { cn } from '../lib/utils';

type TierType = 'shrine' | 'guarded' | 'tactical' | 'campaign' | 'ronin';

export function Torii() {
  const [loading, setLoading] = useState(true);
  const [posture, setPosture] = useState<any>(null);
  const [policies, setPolicies] = useState<any[]>([]);
  const [killSwitchActive, setKillSwitchActive] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [postureRes, policiesRes] = await Promise.all([
        axios.get('/api/v1/security/posture'),
        axios.get('/api/v1/security/policies')
      ]);
      setPosture(postureRes.data.data);
      setPolicies(policiesRes.data.data || []);
    } catch (error) {
      console.error('Error fetching security data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handlePostureChange = async (tier: TierType) => {
    try {
      // In a real implementation, this might call POST /security/posture or similar
      // For now we'll simulate the update
      setPosture({ ...posture, active_tier: tier });
      setStatusMessage({ type: 'success', text: `Security posture updated to ${tier.toUpperCase()}.` });
      setTimeout(() => setStatusMessage(null), 3000);
    } catch (error) {
      setStatusMessage({ type: 'error', text: 'Failed to update posture.' });
    }
  };

  const handleKillSwitch = async () => {
    if (!confirm('WARNING: Activating the Kill Switch will immediately suspend ALL agent activities. Proceed?')) return;
    
    try {
      await axios.post('/api/v1/security/kill-switch');
      setKillSwitchActive(true);
      setStatusMessage({ type: 'error', text: 'GLOBAL KILL-SWITCH ACTIVATED. ALL SYSTEMS SUSPENDED.' });
    } catch (error) {
      console.error('Error activating kill switch:', error);
    }
  };

  const tiers: { id: TierType, label: string, color: string, description: string }[] = [
    { id: 'shrine', label: 'SHRINE (MAX)', color: 'text-shogun-gold', description: 'Zero-trust. Local only. No external tool execution.' },
    { id: 'guarded', label: 'GUARDED', color: 'text-green-500', description: 'Restricted network. Allowlist tools. Human-in-the-loop.' },
    { id: 'tactical', label: 'TACTICAL (DEF)', color: 'text-shogun-blue', description: 'Balanced autonomy. Scoped filesystem access.' },
    { id: 'campaign', label: 'CAMPAIGN', color: 'text-orange-500', description: 'High autonomy. Broad network access. Automated spawns.' },
    { id: 'ronin', label: 'RONIN (UNSAFE)', color: 'text-red-500', description: 'Unrestricted execution. Warning: Recommended for sandbox only.' },
  ];

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-6xl mx-auto pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            The Torii <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">Security Portal</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">Define the moral and technical boundaries of the Samurai Network.</p>
        </div>
        
        <button 
          onClick={handleKillSwitch}
          className={cn(
            "flex items-center gap-2 font-bold py-2.5 px-6 rounded-lg transition-all shadow-lg active:scale-95",
            killSwitchActive 
              ? "bg-red-500 text-white animate-pulse" 
              : "bg-shogun-card border border-red-500/50 text-red-500 hover:bg-red-500 hover:text-white"
          )}
        >
          <Power className="w-4 h-4" />
          {killSwitchActive ? 'SYSTEMS OFFLINE' : 'KILL SWITCH'}
        </button>
      </div>

      {statusMessage && (
        <div className={cn(
          "p-4 rounded-lg flex items-center gap-3 animate-in slide-in-from-top-2",
          statusMessage.type === 'success' ? "bg-green-500/10 text-green-500 border border-green-500/20" : "bg-red-500/10 text-red-500 border border-red-500/20 shadow-[0_0_20px_rgba(239,68,68,0.2)]"
        )}>
          {statusMessage.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <ShieldAlert className="w-5 h-5" />}
          <span className="text-sm font-bold uppercase tracking-wider">{statusMessage.text}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Tier Selection */}
        <div className="lg:col-span-1 space-y-6">
          <div className="shogun-card">
            <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text mb-6">
              <Shield className="w-5 h-5 text-shogun-gold" /> Security Posture
            </h3>
            
            <div className="space-y-3">
              {tiers.map((tier) => (
                <div 
                  key={tier.id}
                  onClick={() => handlePostureChange(tier.id)}
                  className={cn(
                    "p-4 rounded-xl border cursor-pointer transition-all hover:bg-[#0a0e1a]",
                    posture?.active_tier === tier.id 
                      ? "border-shogun-gold bg-shogun-gold/5 shadow-[0_0_15px_rgba(212,160,23,0.1)]" 
                      : "border-shogun-border hover:border-shogun-subdued"
                  )}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className={cn("text-xs font-bold tracking-widest", tier.color)}>{tier.label}</span>
                    {posture?.active_tier === tier.id ? <CheckCircle2 className="w-3 h-3 text-shogun-gold" /> : <div className="w-3 h-3 rounded-full border border-shogun-border" />}
                  </div>
                  <p className="text-[10px] text-shogun-subdued leading-tight">{tier.description}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="shogun-card bg-red-500/5 border-red-500/20">
             <h4 className="text-xs font-bold text-red-500 flex items-center gap-2 mb-3">
               <AlertTriangle className="w-4 h-4" /> EMERGENCY PROTOCOLS
             </h4>
             <p className="text-[10px] text-shogun-subdued leading-relaxed">
               Activating RONIN mode or disabling the network allowlist removes critical safety gates. Use this only for local research purposes in a completely isolated environment.
             </p>
          </div>
        </div>

        {/* Policy Registry */}
        <div className="lg:col-span-2 space-y-6">
          <div className="shogun-card flex flex-col h-full">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                <Lock className="w-5 h-5 text-shogun-blue" /> Policy Registry
              </h3>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-shogun-subdued" />
                <input 
                  type="text" 
                  placeholder="Filter policies..."
                  className="bg-[#050508] border border-shogun-border rounded-lg pl-8 pr-3 py-1.5 text-xs outline-none focus:border-shogun-blue"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto min-h-[400px]">
               {loading ? (
                 <div className="flex flex-col items-center justify-center h-full opacity-50">
                    <RefreshCw className="w-8 h-8 animate-spin text-shogun-blue mb-2" />
                    <span className="text-[10px] uppercase tracking-widest font-bold">Auditing Shields...</span>
                 </div>
               ) : policies.length === 0 ? (
                 <div className="text-center py-20 text-shogun-subdued italic text-sm">
                   No specific security policies defined. System is falling back to default posture.
                 </div>
               ) : (
                 <div className="space-y-4">
                   {policies.map((policy) => (
                     <div key={policy.id} className="p-4 bg-[#050508] border border-shogun-border rounded-xl flex items-center justify-between group hover:border-shogun-blue/50 transition-all">
                       <div className="flex items-center gap-4">
                         <div className="w-10 h-10 rounded-lg bg-shogun-card border border-shogun-border flex items-center justify-center text-shogun-blue">
                           <Shield className="w-5 h-5" />
                         </div>
                         <div>
                            <h4 className="text-sm font-bold text-shogun-text">{policy.name}</h4>
                            <div className="flex items-center gap-3 mt-1">
                               <span className="text-[8px] bg-shogun-blue/10 text-shogun-blue px-2 py-0.5 rounded border border-shogun-blue/20 font-bold uppercase">
                                 {Object.keys(policy.permissions || {}).length} rules
                               </span>
                               <span className="text-[10px] text-shogun-subdued flex items-center gap-1">
                                 <Activity className="w-3 h-3" /> Active Engagement
                               </span>
                            </div>
                         </div>
                       </div>
                       <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                         <button className="p-2 hover:bg-shogun-card rounded-lg text-shogun-subdued hover:text-shogun-text transition-colors">
                           <Eye className="w-4 h-4" />
                         </button>
                         <button className="p-2 hover:bg-shogun-card rounded-lg text-shogun-subdued hover:text-shogun-gold transition-colors">
                           <Unlock className="w-4 h-4" />
                         </button>
                       </div>
                     </div>
                   ))}
                 </div>
               )}
            </div>
            
            <div className="mt-6 pt-6 border-t border-shogun-border flex items-center justify-between">
               <div className="flex items-center gap-2 text-[10px] text-shogun-subdued uppercase tracking-widest font-bold">
                 <Lock className="w-3 h-3 text-shogun-gold" /> All communications encrypted
               </div>
               <button className="text-[10px] font-bold text-shogun-blue hover:text-shogun-gold uppercase tracking-widest transition-all">
                 + Create Tactical Policy
               </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
