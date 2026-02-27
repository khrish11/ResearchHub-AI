import React, { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { BrainCircuit, House, Search, LayoutDashboard, Sparkles } from 'lucide-react';
import api from '../api';
import { toAppPath } from '../utils/routing';

interface HeaderProps {
  userEmail?: string;
  userInitials?: string;
}

interface AiStatusResponse {
  enabled: boolean;
  model?: string | null;
}

const Header: React.FC<HeaderProps> = ({ userEmail, userInitials = 'U' }) => {
  const [aiEnabled, setAiEnabled] = useState<boolean | null>(null);
  const [aiModel, setAiModel] = useState<string | null>(null);
  const location = useLocation();

  useEffect(() => {
    let mounted = true;
    api
      .get<AiStatusResponse>('/ai/status')
      .then((res) => {
        if (!mounted) return;
        setAiEnabled(!!res.data.enabled);
        setAiModel(res.data.model || null);
      })
      .catch(() => {
        if (!mounted) return;
        setAiEnabled(false);
        setAiModel(null);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const shortModel = aiModel
    ? aiModel.replace('llama-', 'Llama ').replace('-versatile', '').replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : null;

  const pageTitle = useMemo(() => {
    const path = location.pathname;
    if (path.startsWith('/search')) return 'Paper Search';
    if (path.startsWith('/dashboard')) return 'Dashboard';
    if (path.startsWith('/mindmap')) return 'Mindmap Studio';
    if (path.startsWith('/workspace')) return 'Workspace';
    if (path.startsWith('/ai-tools')) return 'AI Tools';
    if (path.startsWith('/research-chat') || path.startsWith('/writing-chat')) return 'Research Chatbot';
    if (path.startsWith('/upload')) return 'Upload Center';
    if (path.startsWith('/docs')) return 'DocSpace';
    if (path.startsWith('/account')) return 'Account';
    if (path.startsWith('/settings')) return 'Settings';
    if (path.startsWith('/developer')) return 'Developer Console';
    return 'Research Command';
  }, [location.pathname]);

  const mobileLinks = [
    { to: '/home', icon: House, label: 'Home' },
    { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/search', icon: Search, label: 'Search' },
  ];

  return (
    <header className="sticky top-0 z-20 px-3 md:px-6 pt-3 pb-2">
      <div className="topbar-shell">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500 mb-1 flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
              Neural Interface
            </p>
            <h1 className="text-lg md:text-xl font-bold text-slate-900 truncate">{pageTitle}</h1>
          </div>

          <div className="flex items-center gap-2.5 md:gap-3">
            {aiEnabled !== null && (
              <div
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${
                  aiEnabled
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : 'bg-rose-50 text-rose-700 border-rose-200'
                }`}
              >
                <BrainCircuit className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{aiEnabled ? `AI ${shortModel || 'Online'}` : 'AI Offline'}</span>
                <span className="sm:hidden">{aiEnabled ? 'AI On' : 'AI Off'}</span>
              </div>
            )}

            {userEmail && (
              <div className="flex items-center gap-2 pl-2.5 border-l border-slate-200">
                <div className="topbar-avatar">{userInitials}</div>
                <div className="hidden lg:block">
                  <p className="text-sm font-semibold text-slate-800 leading-tight">{userEmail}</p>
                  <p className="text-xs text-slate-400">Research Operator</p>
                </div>
                <button
                  type="button"
                  aria-label="Log out"
                  onClick={() => {
                    localStorage.removeItem('token');
                    window.location.href = toAppPath('/login');
                  }}
                  className="ml-1 px-2.5 py-1 text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Logout
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="mt-3 flex lg:hidden gap-1.5">
          {mobileLinks.map((item) => {
            const Icon = item.icon;
            const active = location.pathname.startsWith(item.to);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${
                  active
                    ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
                    : 'bg-white text-slate-600 border-slate-200'
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {item.label}
              </Link>
            );
          })}
        </div>
      </div>
    </header>
  );
};

export default Header;
