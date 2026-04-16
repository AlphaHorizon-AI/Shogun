import { useState } from 'react';
import { Skull, AlertTriangle, ShieldAlert, X } from 'lucide-react';

interface HarakiriModalProps {
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Two-step harakiri confirmation modal.
 * Step 1 — ominous warning.
 * Step 2 — final irreversible commit screen.
 */
export function HarakiriModal({ onConfirm, onCancel }: HarakiriModalProps) {
  const [step, setStep] = useState<1 | 2>(1);

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={onCancel}
      />

      {/* Step 1 — Warning */}
      {step === 1 && (
        <div className="relative w-full max-w-md mx-4 animate-in zoom-in-95 duration-200">
          <div className="bg-shogun-bg border border-orange-500/50 rounded-2xl shadow-[0_0_60px_rgba(249,115,22,0.2)] overflow-hidden">
            {/* Header stripe */}
            <div className="bg-orange-500/10 border-b border-orange-500/30 px-6 py-4 flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-orange-400 shrink-0" />
              <span className="text-orange-400 font-bold uppercase tracking-widest text-sm">
                Warning — Step 1 of 2
              </span>
              <button onClick={onCancel} className="ml-auto text-shogun-subdued hover:text-shogun-text">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-6 space-y-5">
              <div className="text-center space-y-2">
                <p className="text-shogun-text font-bold text-base leading-relaxed">
                  You are about to initiate <span className="text-orange-400">Harakiri</span>.
                </p>
                <p className="text-shogun-subdued text-sm leading-relaxed">
                  This will immediately set posture to <strong className="text-orange-300">SHRINE</strong> and
                  suspend <strong className="text-orange-300">all</strong> autonomous agent activity on this system.
                </p>
              </div>

              <div className="bg-orange-500/5 border border-orange-500/20 rounded-xl p-4 text-xs text-orange-300/80 space-y-1">
                <p>⚠ All Samurai agents will be halted</p>
                <p>⚠ Shell and skill execution will be disabled</p>
                <p>⚠ Network access will be locked to allowlist</p>
                <p>⚠ This state persists across restarts until manually reset</p>
              </div>
            </div>

            <div className="px-6 pb-6 flex gap-3">
              <button
                onClick={onCancel}
                className="flex-1 py-2.5 rounded-lg border border-shogun-border text-shogun-subdued hover:text-shogun-text text-sm font-bold transition-all"
              >
                Cancel
              </button>
              <button
                onClick={() => setStep(2)}
                className="flex-1 py-2.5 rounded-lg bg-orange-500/20 border border-orange-500/50 text-orange-400 hover:bg-orange-500/30 text-sm font-bold transition-all"
              >
                I Understand — Proceed
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Step 2 — Final Commit */}
      {step === 2 && (
        <div className="relative w-full max-w-md mx-4 animate-in zoom-in-95 duration-200">
          <div className="bg-shogun-bg border border-red-500/60 rounded-2xl shadow-[0_0_80px_rgba(239,68,68,0.3)] overflow-hidden">
            {/* Header stripe */}
            <div className="bg-red-500/15 border-b border-red-500/40 px-6 py-4 flex items-center gap-3">
              <ShieldAlert className="w-5 h-5 text-red-400 shrink-0" />
              <span className="text-red-400 font-bold uppercase tracking-widest text-sm">
                Final Confirmation — Step 2 of 2
              </span>
              <button onClick={onCancel} className="ml-auto text-shogun-subdued hover:text-shogun-text">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-6 space-y-5">
              {/* Skull icon */}
              <div className="flex justify-center">
                <div className="w-16 h-16 rounded-full bg-red-500/10 border-2 border-red-500/40 flex items-center justify-center">
                  <Skull className="w-8 h-8 text-red-400" />
                </div>
              </div>

              <div className="text-center space-y-2">
                <p className="text-red-400 font-bold text-lg uppercase tracking-widest">
                  This is not reversible
                </p>
                <p className="text-shogun-subdued text-sm leading-relaxed">
                  You are committing to a <strong className="text-red-300">global system lockdown</strong>.
                  All agents will be frozen immediately and the system will not
                  resume autonomously.
                </p>
              </div>

              <p className="text-center text-[10px] text-shogun-subdued/60 uppercase tracking-widest">
                Click "INITIATE HARAKIRI" to proceed — there is no automatic undo.
              </p>
            </div>

            <div className="px-6 pb-6 flex gap-3">
              <button
                onClick={onCancel}
                className="flex-1 py-2.5 rounded-lg border border-shogun-border text-shogun-subdued hover:text-shogun-text text-sm font-bold transition-all"
              >
                Abort
              </button>
              <button
                onClick={() => { onConfirm(); }}
                className="flex-1 py-2.5 rounded-lg bg-red-500 hover:bg-red-600 active:scale-95 text-white text-sm font-bold transition-all shadow-[0_0_20px_rgba(239,68,68,0.4)] uppercase tracking-widest"
              >
                ☠ Initiate Harakiri
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
