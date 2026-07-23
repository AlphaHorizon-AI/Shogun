import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Shield, Users, Layers, Activity,
  FileSearch, Bell, UserPlus, Skull, LogOut, ChevronLeft, ChevronRight,
  Network, Settings, BookOpen, BarChart3, Key, Globe, LockKeyhole
} from 'lucide-react';
import { clearAuth, getAdmin } from '../../lib/auth';
import { useTranslation } from '../../i18n';

const NAV_ITEMS = [
  { path: '/', i18nKey: 'nav.dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/fleet', i18nKey: 'nav.fleet', label: 'Fleet', icon: Users },
  { path: '/network', i18nKey: 'nav.network', label: 'Network', icon: Network },
  { path: '/groups', i18nKey: 'nav.groups', label: 'Groups', icon: Layers },
  { path: '/postures', i18nKey: 'nav.postures', label: 'Postures', icon: Shield },
  { path: '/toolgate', i18nKey: 'nav.toolgate', label: 'ToolGate', icon: LockKeyhole },
  { path: '/harakiri', i18nKey: 'nav.harakiri', label: 'Harakiri', icon: Skull },
  { path: '/activity', i18nKey: 'nav.activity', label: 'Activity', icon: Activity },
  { path: '/audit', i18nKey: 'nav.audit', label: 'Audit Log', icon: FileSearch },
  { path: '/fleet-audit', i18nKey: 'nav.fleet_audit', label: 'Fleet Audit', icon: BarChart3 },
  { path: '/alerts', i18nKey: 'nav.alerts', label: 'Alerts', icon: Bell },
  { path: '/enrollment', i18nKey: 'nav.enrollment', label: 'Enrollment', icon: UserPlus },
  { path: '/identity', i18nKey: 'nav.identity', label: 'Identity', icon: Key },
  { path: '/settings', i18nKey: 'nav.settings', label: 'Settings', icon: Settings },
  { path: '/guide', i18nKey: 'nav.guide', label: 'Reference', icon: BookOpen },
];

export default function Sidebar() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const admin = getAdmin();
  const { t, language, setLanguage, languages } = useTranslation();
  const [showLangPicker, setShowLangPicker] = useState(false);
  const currentLang = languages.find(l => l.code === language);

  return (
    <aside className={`flex flex-col h-screen bg-gensui-800/40 border-r border-gensui-700/30 transition-all duration-300 ${collapsed ? 'w-16' : 'w-64'}`}>
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-gensui-700/30">
        <img
          src="/gensui-logo.png"
          alt="Gensui"
          className="w-9 h-9 rounded-lg object-cover"
        />
        {!collapsed && (
          <div>
            <h1 className="text-sm font-bold text-gensui-50 tracking-wide">GENSUI</h1>
            <p className="text-[10px] text-gensui-500 uppercase tracking-widest">Command Center</p>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map(({ path, i18nKey, label, icon: Icon }) => {
          const active = location.pathname === path || (path !== '/' && location.pathname.startsWith(path));
          const displayLabel = t(i18nKey, label);
          return (
            <Link
              key={path}
              to={path}
              className={`sidebar-item ${active ? 'active' : ''}`}
              title={collapsed ? displayLabel : undefined}
            >
              <Icon size={18} />
              {!collapsed && <span>{displayLabel}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Language Selector */}
      {!collapsed && (
        <div className="relative px-2 mb-2">
          <button
            onClick={() => setShowLangPicker(!showLangPicker)}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-gensui-400 hover:text-gensui-200 hover:bg-gensui-700/30 transition-colors"
          >
            <Globe size={14} />
            <span>{currentLang?.flag} {currentLang?.name}</span>
          </button>
          {showLangPicker && (
            <div className="absolute bottom-full left-0 right-0 mx-2 mb-1 bg-gensui-800 border border-gensui-700/50 rounded-lg shadow-xl max-h-60 overflow-y-auto z-50">
              {languages.map(lang => (
                <button
                  key={lang.code}
                  onClick={() => { setLanguage(lang.code); setShowLangPicker(false); }}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-gensui-700/40 transition-colors ${
                    lang.code === language ? 'text-cyan-400 bg-cyan-500/5' : 'text-gensui-300'
                  }`}
                >
                  <span>{lang.flag}</span>
                  <span>{lang.name}</span>
                  <span className="text-gensui-600 ml-auto">{lang.englishName}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Collapse Toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-center p-2 mx-2 mb-2 rounded-lg text-gensui-500 hover:text-gensui-300 hover:bg-gensui-700/30 transition-colors"
      >
        {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      </button>

      {/* Admin Profile */}
      <div className="border-t border-gensui-700/30 p-3">
        {!collapsed && admin && (
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gensui-600 flex items-center justify-center text-xs font-bold text-gensui-200">
              {(admin.display_name || admin.email)?.[0]?.toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-gensui-200 truncate">{admin.display_name || admin.email}</p>
              <p className="text-[10px] text-gensui-500 uppercase">{admin.role}</p>
            </div>
            <button
              onClick={() => { clearAuth(); window.location.href = '/login'; }}
              className="p-1.5 text-gensui-500 hover:text-crimson-400 transition-colors"
              title="Logout"
            >
              <LogOut size={14} />
            </button>
          </div>
        )}
        {collapsed && (
          <button
            onClick={() => { clearAuth(); window.location.href = '/login'; }}
            className="w-full flex justify-center p-2 text-gensui-500 hover:text-crimson-400 transition-colors"
            title="Logout"
          >
            <LogOut size={16} />
          </button>
        )}
      </div>
    </aside>
  );
}
