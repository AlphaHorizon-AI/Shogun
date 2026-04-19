import { 
  LayoutDashboard, 
  User, 
  Users, 
  MessageSquare, 
  Shield, 
  Hand, 
  HelpCircle,
  Database,
  ScrollText,
  History,
  Sword,
  BookOpen,
  Network,
} from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { cn } from '../../lib/utils';

interface NavItemProps {
  icon: React.ElementType;
  label: string;
  subLabel?: string;
  active?: boolean;
  onClick?: () => void;
}

const NavItem = ({ icon: Icon, label, subLabel, active, onClick }: NavItemProps) => (
  <button
    onClick={onClick}
    className={cn(
      "w-full flex items-start gap-3 p-2.5 rounded-lg transition-all duration-200 group",
      active 
        ? "bg-shogun-card border border-shogun-border text-shogun-gold shadow-shogun" 
        : "text-shogun-subdued hover:bg-shogun-card/50 hover:text-shogun-text"
    )}
  >
    <Icon className={cn("w-4 h-4 mt-0.5", active ? "text-shogun-gold" : "group-hover:text-shogun-blue")} />
    <div className="flex flex-col items-start leading-tight">
      <span className="font-semibold text-[12px]">{label}</span>
      {subLabel && <span className="text-[9px] text-shogun-subdued uppercase tracking-wider">{subLabel}</span>}
    </div>
  </button>
);

export const Sidebar = () => {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <aside className="w-64 h-full bg-[#050508] border-r border-shogun-border p-4 flex flex-col gap-6 overflow-y-auto scrollbar-hide relative z-20">
      <div>
        <h3 className="text-[10px] font-bold text-shogun-gold tracking-[0.2em] mb-3 pl-3 uppercase">Navigation</h3>
        <nav className="flex flex-col gap-1">
          <NavItem 
            icon={LayoutDashboard} 
            label="Overview" 
            subLabel="Command Center" 
            active={location.pathname === '/'} 
            onClick={() => navigate('/')}
          />
          <NavItem 
            icon={User} 
            label="Shogun" 
            subLabel="My Agent" 
            active={location.pathname === '/shogun'}
            onClick={() => navigate('/shogun')}
          />
          <NavItem 
            icon={Users} 
            label="Samurai" 
            subLabel="Sub-Agents" 
            active={location.pathname === '/samurai'}
            onClick={() => navigate('/samurai')}
          />
          <NavItem 
            icon={MessageSquare} 
            label="Comms" 
            subLabel="Chat Console" 
            active={location.pathname === '/chat'}
            onClick={() => navigate('/chat')}
          />
        </nav>
      </div>

      <div>
        <h3 className="text-[10px] font-bold text-shogun-blue tracking-[0.2em] mb-3 pl-3 uppercase">Systems & Governance</h3>
        <nav className="flex flex-col gap-1">
          <NavItem 
            icon={Sword} 
            label="The Katana" 
            subLabel="Models & Tools" 
            active={location.pathname === '/katana'}
            onClick={() => navigate('/katana')}
          />
          <NavItem 
            icon={Shield} 
            label="The Torii" 
            subLabel="Security Gateway" 
            active={location.pathname === '/torii'}
            onClick={() => navigate('/torii')}
          />
          <NavItem 
            icon={ScrollText} 
            label="Kaizen" 
            subLabel="Constitution" 
            active={location.pathname === '/kaizen'}
            onClick={() => navigate('/kaizen')}
          />
          <NavItem 
            icon={Hand} 
            label="Bushido" 
            subLabel="Heartbeat" 
            active={location.pathname === '/bushido'}
            onClick={() => navigate('/bushido')}
          />
        </nav>
      </div>

      <div>
        <h3 className="text-[10px] font-bold text-shogun-subdued tracking-[0.2em] mb-3 pl-3 uppercase">Operations</h3>
        <nav className="flex flex-col gap-1">
          <NavItem 
            icon={Database} 
            label="Archives" 
            subLabel="Agent Memory" 
            active={location.pathname === '/archives'}
            onClick={() => navigate('/archives')}
          />
          <NavItem 
            icon={BookOpen} 
            label="Dojo" 
            subLabel="Skill Registry" 
            active={location.pathname === '/dojo'}
            onClick={() => navigate('/dojo')}
          />
          <NavItem 
            icon={History} 
            label="Logs" 
            subLabel="Audit Trail" 
            active={location.pathname === '/logs'}
            onClick={() => navigate('/logs')}
          />
          <NavItem 
            icon={HelpCircle} 
            label="Guide" 
            subLabel="Documentation" 
            active={location.pathname === '/guide'}
            onClick={() => navigate('/guide')}
          />
        </nav>
      </div>

      <div>
        <h3 className="text-[10px] font-bold tracking-[0.2em] mb-3 pl-3 uppercase" style={{color: 'rgb(129,140,248)'}}>Alliance</h3>
        <nav className="flex flex-col gap-1">
          <NavItem 
            icon={Network} 
            label="Nexus" 
            subLabel="A2A Workspaces" 
            active={location.pathname === '/nexus'}
            onClick={() => navigate('/nexus')}
          />
        </nav>
      </div>
    </aside>
  );
};

