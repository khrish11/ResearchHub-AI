import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Home, LayoutDashboard, Search, Brain, Upload, FileText, LogOut, Microscope, Settings, UserCog, Workflow, Bot, MessageSquareCode } from 'lucide-react';
import ThemeToggle from './ThemeToggle';
import { toAppPath } from '../utils/routing';

interface SidebarProps {
  userEmail?: string;
  userInitials?: string;
  mobile?: boolean;
}

const Sidebar: React.FC<SidebarProps> = ({ userEmail, userInitials = 'U', mobile = false }) => {
  const location = useLocation();

  const menuItems = [
    { path: '/home', label: 'Home', icon: Home },
    { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/search', label: 'Search Papers', icon: Search },
    { path: '/ai-tools', label: 'AI Tools', icon: Brain },
    { path: '/research-agent', label: 'Research Agent', icon: Bot },
    { path: '/research-chat', label: 'Research Chat', icon: MessageSquareCode },
    { path: '/upload', label: 'Upload PDF', icon: Upload },
    { path: '/docs', label: 'DocSpace', icon: FileText },
    { path: '/mindmap', label: 'Mindmap', icon: Workflow },
    { path: '/account', label: 'Account', icon: UserCog },
    { path: '/settings', label: 'Settings', icon: Settings },
  ];

  const isActive = (path: string) => {
    if (path === '/home') {
      return location.pathname === '/home' || (location.pathname === '/' && localStorage.getItem('token'));
    }
    return location.pathname.startsWith(path);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    window.location.href = toAppPath('/login');
  };

  return (
    <aside className={`${mobile ? 'flex w-full' : 'hidden md:flex md:w-[260px] lg:w-[280px] xl:w-[300px]'} min-h-screen px-4 py-4`}>
      <div className="sidebar-shell w-full rounded-3xl p-4 flex flex-col">
        <div className="px-2 pt-2 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl sidebar-logo-chip">
              <Microscope className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="sidebar-brand">Soyog AI</p>
              <p className="text-[11px] text-indigo-200/70 tracking-wide uppercase">Neural Workspace</p>
            </div>
          </div>
        </div>
        <div className="h-px mx-1 mb-3 bg-indigo-200/10" />

        <nav className="flex-1 px-1 space-y-1.5" aria-label="Primary">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`sidebar-nav-item ${active ? 'sidebar-nav-active' : 'sidebar-nav-idle'}`}
              >
                <Icon className="h-4.5 w-4.5 flex-shrink-0" style={{ width: 18, height: 18 }} />
                <span className="tracking-wide">{item.label}</span>
                {active && <div className="ml-auto w-1.5 h-1.5 rounded-full bg-white/70" />}
              </Link>
            );
          })}
        </nav>

        <div className="p-3 mt-auto">
          <div className="px-2 pb-2">
            <div className="mb-3">
              <ThemeToggle className="w-full" />
            </div>
            {userEmail && (
              <div className="flex items-center gap-3 px-2 mb-3">
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white flex-shrink-0 sidebar-user-avatar"
                >
                  {userInitials}
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-medium truncate sidebar-user-email">{userEmail}</p>
                  <p className="text-xs sidebar-user-role">Researcher</p>
                </div>
              </div>
            )}
            <button type="button" onClick={handleLogout} className="sidebar-logout" aria-label="Log out">
              <LogOut style={{ width: 17, height: 17 }} />
              <span className="font-medium">Logout</span>
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
