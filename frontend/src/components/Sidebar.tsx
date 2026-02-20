import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Home, LayoutDashboard, Search, Brain, Upload, FileText, LogOut } from 'lucide-react';

interface SidebarProps {
  userEmail?: string;
  userInitials?: string;
}

const Sidebar: React.FC<SidebarProps> = ({ userEmail, userInitials = 'U' }) => {
  const location = useLocation();

  const menuItems = [
    { path: '/home', label: 'Home', icon: Home },
    { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/search', label: 'Search Papers', icon: Search },
    { path: '/ai-tools', label: 'AI Tools', icon: Brain },
    { path: '/upload', label: 'Upload PDF', icon: Upload },
    { path: '/docs', label: 'DocSpace', icon: FileText },
  ];

  const isActive = (path: string) => {
    if (path === '/home') {
      return location.pathname === '/home' || (location.pathname === '/' && localStorage.getItem('token'));
    }
    return location.pathname.startsWith(path);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    window.location.href = '/login';
  };

  return (
    <div className="w-64 bg-white border-r border-slate-200 min-h-screen flex flex-col">
      <div className="p-6 border-b border-slate-200">
        <h1 className="text-xl font-bold text-indigo-600">ResearchHub AI</h1>
      </div>
      <nav className="flex-1 p-4 space-y-2">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.path);
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                active
                  ? 'bg-indigo-50 text-indigo-600 font-medium'
                  : 'text-slate-700 hover:bg-slate-50'
              }`}
            >
              <Icon className="h-5 w-5" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="p-4 border-t border-slate-200">
        {userEmail && (
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center text-sm font-semibold">{userInitials}</div>
            <div className="text-sm text-slate-700 truncate">{userEmail}</div>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 px-4 py-3 rounded-lg text-slate-700 hover:bg-slate-50 w-full"
        >
          <LogOut className="h-5 w-5" />
          <span>Logout</span>
        </button>
      </div>
    </div>
  );
};

export default Sidebar;
