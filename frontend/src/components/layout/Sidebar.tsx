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
  Download,
  HardDrive,
  ShieldCheck,
  LockKeyhole,
  Radio,
  Info,
} from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { useNavigate } from '../../lib/routerCompat';
import { cn } from '../../lib/utils';
import { useState, useEffect } from 'react';
import { useTranslation } from '../../i18n';

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
      "w-full flex items-start gap-3 p-2.5 rounded-lg transition-all duration-200 group relative",
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
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const { t } = useTranslation();

  const openSamurai = () => {
    if (location.pathname === '/samurai') {
      window.location.reload();
      return;
    }
    window.location.href = '/samurai';
  };

  // Check for updates on mount (non-blocking)
  useEffect(() => {
    fetch('/api/v1/updates/check')
      .then(r => r.json())
      .then(data => {
        if (data.update_available) setUpdateAvailable(true);
      })
      .catch(() => {}); // Silently fail if offline
  }, []);

  const [activeRuns, setActiveRuns] = useState(0);
  useEffect(() => {
    const fetchActiveRuns = async () => {
      try {
        const resp = await fetch('/api/v1/agent-flows/active-runs');
        const data = await resp.json();
        setActiveRuns(data?.data?.active_runs || 0);
      } catch {
        // ignore
      }
    };
    fetchActiveRuns();
    const interval = setInterval(fetchActiveRuns, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <aside className="w-64 h-full bg-[#050508] border-r border-shogun-border p-4 flex flex-col gap-6 overflow-y-auto scrollbar-hide relative z-20">
      <div>
        <h3 className="text-[10px] font-bold text-shogun-gold tracking-[0.2em] mb-3 pl-3 uppercase">{t('nav.navigation', 'Navigation')}</h3>
        <nav className="flex flex-col gap-1">
          <NavItem 
            icon={LayoutDashboard} 
            label={t('nav.overview', 'Overview')} 
            subLabel={t('nav.overview_sub', 'Command Center')} 
            active={location.pathname === '/'} 
            onClick={() => navigate('/')}
          />
          <NavItem 
            icon={User} 
            label={t('nav.shogun', 'Shogun')} 
            subLabel={t('nav.shogun_sub', 'My Agent')} 
            active={location.pathname === '/shogun'}
            onClick={() => navigate('/shogun')}
          />
          <NavItem 
            icon={Users} 
            label={t('nav.samurai', 'Samurai')} 
            subLabel={t('nav.samurai_sub', 'Sub-Agents')} 
            active={location.pathname === '/samurai'}
            badge={activeRuns > 0 ? `${activeRuns} RUNNING` : null}
            onClick={openSamurai}
          />
          <NavItem 
            icon={MessageSquare} 
            label={t('nav.comms', 'Comms')} 
            subLabel={t('nav.comms_sub', 'Chat · Mail · Files · Supermode')}
            active={location.pathname === '/chat'}
            onClick={() => navigate('/chat')}
          />
        </nav>
      </div>

      <div>
        <h3 className="text-[10px] font-bold text-shogun-blue tracking-[0.2em] mb-3 pl-3 uppercase">{t('nav.systems_governance', 'Systems & Governance')}</h3>
        <nav className="flex flex-col gap-1">
          <NavItem 
            icon={Sword} 
            label={t('nav.katana', 'The Katana')} 
            subLabel={t('nav.katana_sub', 'Models & Tools')} 
            active={location.pathname === '/katana'}
            onClick={() => navigate('/katana')}
          />
          <NavItem
            icon={Shield} 
            label={t('nav.torii', 'The Torii')} 
            subLabel={t('nav.torii_sub', 'Security Gateway')} 
            active={location.pathname === '/torii'}
            onClick={() => navigate('/torii')}
          />
          <NavItem
            icon={LockKeyhole}
            label={t('nav.toolgate', 'ToolGate')}
            subLabel={t('nav.toolgate_sub', 'Runtime Permissions')}
            active={location.pathname === '/toolgate'}
            onClick={() => navigate('/toolgate')}
          />
          <NavItem 
            icon={ScrollText} 
            label={t('nav.kaizen', 'Kaizen')} 
            subLabel={t('nav.kaizen_sub', 'Constitution')} 
            active={location.pathname === '/kaizen'}
            onClick={() => navigate('/kaizen')}
          />
          <NavItem 
            icon={Hand} 
            label={t('nav.bushido', 'Bushido')} 
            subLabel={t('nav.bushido_sub', 'Heartbeat')} 
            active={location.pathname === '/bushido'}
            onClick={() => navigate('/bushido')}
          />
        </nav>
      </div>

      <div>
        <h3 className="text-[10px] font-bold text-shogun-subdued tracking-[0.2em] mb-3 pl-3 uppercase">{t('nav.operations', 'Operations')}</h3>
        <nav className="flex flex-col gap-1">
          <NavItem 
            icon={Database} 
            label={t('nav.archives', 'Archives')} 
            subLabel={t('nav.archives_sub', 'Agent Memory')} 
            active={location.pathname === '/archives'}
            onClick={() => navigate('/archives')}
          />
          <NavItem 
            icon={BookOpen} 
            label={t('nav.dojo', 'Dojo')} 
            subLabel={t('nav.dojo_sub', 'Skill Registry')} 
            active={location.pathname === '/dojo'}
            onClick={() => navigate('/dojo')}
          />
          <NavItem 
            icon={History} 
            label={t('nav.logs', 'Logs')} 
            subLabel={t('nav.logs_sub', 'Audit Trail')} 
            active={location.pathname === '/logs'}
            onClick={() => navigate('/logs')}
          />
        </nav>
      </div>

      <div>
        <h3 className="text-[10px] font-bold tracking-[0.2em] mb-3 pl-3 uppercase" style={{color: 'rgb(129,140,248)'}}>{t('nav.alliance', 'Alliance')}</h3>
        <nav className="flex flex-col gap-1">
          <NavItem 
            icon={Network} 
            label={t('nav.nexus', 'Nexus')} 
            subLabel={t('nav.nexus_sub', 'A2A Workspaces')} 
            active={location.pathname === '/nexus'}
            onClick={() => navigate('/nexus')}
          />
          <NavItem 
            icon={ShieldCheck} 
            label={t('nav.gensui', 'Gensui')} 
            subLabel={t('nav.gensui_sub', 'Fleet Command')} 
            active={location.pathname === '/gensui'}
            onClick={() => navigate('/gensui')}
          />
        </nav>
      </div>

      {/* ── System Maintenance ──────────────────────── */}
      <div className="mt-auto pt-4 border-t border-shogun-border/40">
        <h3 className="text-[10px] font-bold text-shogun-subdued/60 tracking-[0.2em] mb-3 pl-3 uppercase">{t('nav.maintenance', 'Maintenance')}</h3>
        <nav className="flex flex-col gap-1">
          <NavItem 
            icon={HardDrive} 
            label={t('nav.backups', 'Backups')} 
            subLabel={t('nav.backups_sub', 'Data Protection')} 
            active={location.pathname === '/backups'}
            onClick={() => navigate('/backups')}
          />
          <NavItem
            icon={Radio}
            label={t('nav.privacy_telemetry', 'Privacy & Telemetry')}
            subLabel={t('nav.privacy_telemetry_sub', 'Optional Statistics')}
            active={location.pathname === '/privacy-telemetry'}
            onClick={() => navigate('/privacy-telemetry')}
          />
          <NavItem 
            icon={Download} 
            label={t('nav.updates', 'Updates')} 
            subLabel={t('nav.updates_sub', 'Platform Version')} 
            active={location.pathname === '/updates'}
            badge={updateAvailable ? t('nav.update_available', 'UPDATE') : null}
            onClick={() => navigate('/updates')}
          />
          <NavItem
            icon={Info}
            label={t('nav.about', 'About')}
            subLabel={t('nav.about_sub', 'System Information')}
            active={location.pathname === '/about'}
            onClick={() => navigate('/about')}
          />
          <NavItem 
            icon={HelpCircle} 
            label={t('nav.guide', 'Guide')} 
            subLabel={t('nav.guide_sub', 'Documentation')} 
            active={location.pathname === '/guide'}
            onClick={() => navigate('/guide')}
          />
        </nav>
      </div>
    </aside>
  );
};
