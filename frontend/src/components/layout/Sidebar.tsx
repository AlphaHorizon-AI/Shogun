import { GitBranch, Cpu, Route, FolderOpen } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { useNavigate } from '../../lib/routerCompat';
import { cn } from '../../lib/utils';
import { useState, useEffect } from 'react';

interface NavItemProps {
  icon: React.ElementType;
  label: string;
  subLabel?: string;
  active?: boolean;
  badge?: string | null;
  onClick?: () => void;
}

const NavItem = ({ icon: Icon, label, subLabel, active, badge, onClick }: NavItemProps) => (
  <button
    onClick={onClick}
    className={cn(
      'w-full flex items-start gap-3 p-2.5 rounded-lg transition-all duration-200 group relative cursor-pointer',
      active
        ? 'bg-shogun-card border border-shogun-border text-shogun-gold shadow-shogun'
        : 'text-shogun-subdued hover:bg-shogun-card/50 hover:text-shogun-text',
    )}
  >
    <Icon className={cn('w-4 h-4 mt-0.5', active ? 'text-shogun-gold' : 'group-hover:text-shogun-blue')} />
    <div className="flex flex-col items-start leading-tight">
      <span className="font-semibold text-[12px]">{label}</span>
      {subLabel && <span className="text-[9px] text-shogun-subdued uppercase tracking-wider">{subLabel}</span>}
    </div>
    {badge && (
      <span className="absolute right-2 top-1/2 -translate-y-1/2 bg-emerald-500 text-[8px] text-white font-bold px-1.5 py-0.5 rounded-full animate-pulse">
        {badge}
      </span>
    )}
  </button>
);

export const Sidebar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [activeRuns, setActiveRuns] = useState(0);

  useEffect(() => {
    const fetchActiveRuns = async () => {
      try {
        const resp = await fetch('/api/v1/agent-flows/active-runs');
        if (!resp.ok) return;
        const data = await resp.json();
        setActiveRuns(data?.data?.active_runs || 0);
      } catch {
        // Ignore transient failures
      }
    };
    fetchActiveRuns();
    const interval = setInterval(fetchActiveRuns, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <aside className="w-60 h-full bg-[#050508] border-r border-shogun-border p-4 flex flex-col gap-6 overflow-y-auto relative z-20">
      <div>
        <h3 className="text-[10px] font-bold text-shogun-gold tracking-[0.2em] mb-3 pl-3 uppercase">
          Workflows
        </h3>
        <nav className="flex flex-col gap-1">
          <NavItem
            icon={GitBranch}
            label="AgentFlow"
            subLabel="Visual Flows & Ad-Hoc Agents"
            active={location.pathname === '/'}
            badge={activeRuns > 0 ? `${activeRuns} RUN` : null}
            onClick={() => navigate('/')}
          />
        </nav>
      </div>

      <div>
        <h3 className="text-[10px] font-bold text-shogun-blue tracking-[0.2em] mb-3 pl-3 uppercase">
          Configuration
        </h3>
        <nav className="flex flex-col gap-1">
          <NavItem
            icon={Cpu}
            label="AI Providers"
            subLabel="Cloud & Local Models"
            active={location.pathname === '/providers'}
            onClick={() => navigate('/providers')}
          />
          <NavItem
            icon={Route}
            label="Routing Profiles"
            subLabel="Selection & Fallbacks"
            active={location.pathname === '/routing'}
            onClick={() => navigate('/routing')}
          />
          <NavItem
            icon={FolderOpen}
            label="Local Folder"
            subLabel="File System Setup"
            active={location.pathname === '/workspace'}
            onClick={() => navigate('/workspace')}
          />
        </nav>
      </div>
    </aside>
  );
};
