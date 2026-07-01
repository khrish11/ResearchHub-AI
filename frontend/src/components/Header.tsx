import React, { useMemo } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  ArrowUpRight,
  Binary,
  Bot,
  BrainCircuit,
  Command,
  FileSearch,
  Files,
  House,
  LayoutDashboard,
  Search,
  Sparkles,
  Workflow,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { toAppPath } from '../utils/routing';
import { openCommandPalette } from '../utils/commandPalette';
import { clearAuthSession } from '../utils/authSession';

interface HeaderProps {
  userEmail?: string;
  userInitials?: string;
}



interface HeaderMeta {
  title: string;
  eyebrow: string;
  description: string;
  action: {
    label: string;
    to: string;
    icon: LucideIcon;
  };
}

const Header: React.FC<HeaderProps> = ({ userEmail, userInitials = 'U' }) => {
  const location = useLocation();

  const headerMeta = useMemo<HeaderMeta>(() => {
    const path = location.pathname;

    if (path.startsWith('/search')) {
      return {
        title: 'Paper Search',
        eyebrow: 'Discovery',
        description: 'Scan cross-source literature, compare signals, and move only the strongest papers into workspace flow.',
        action: { label: 'Open Research Agent', to: '/research-agent', icon: Bot },
      };
    }
    if (path.startsWith('/dashboard')) {
      return {
        title: 'Dashboard',
        eyebrow: 'Operations',
        description: 'Create workspaces, monitor research throughput, and move from raw paper intake to active project execution.',
        action: { label: 'Search papers', to: '/search', icon: Search },
      };
    }
    if (path.startsWith('/mindmap')) {
      return {
        title: 'Mindmap Studio',
        eyebrow: 'Synthesis',
        description: 'Turn clusters of papers into thematic maps, narrative structure, and review-ready mental models.',
        action: { label: 'Open DocSpace', to: '/docs', icon: Files },
      };
    }
    if (path.startsWith('/workspace')) {
      return {
        title: 'Workspace',
        eyebrow: 'Project Context',
        description: 'Stay inside one project surface for imported papers, notes, exports, and context-preserving follow-up work.',
        action: { label: 'Open AI Tools', to: '/ai-tools', icon: BrainCircuit },
      };
    }
    if (path.startsWith('/ai-tools')) {
      return {
        title: 'AI Tools',
        eyebrow: 'Inference',
        description: 'Draft synthesis, probe hypotheses, and keep answers grounded in the papers already loaded into your project.',
        action: { label: 'Open Research Chat', to: '/research-chat', icon: Bot },
      };
    }
    if (path.startsWith('/research-agent')) {
      return {
        title: 'Research Agent',
        eyebrow: 'Autonomy',
        description: 'Run deeper question-answer loops across recent search context and workspace evidence without leaving the product.',
        action: { label: 'Search papers', to: '/search', icon: FileSearch },
      };
    }
    if (path.startsWith('/research-chat') || path.startsWith('/writing-chat')) {
      return {
        title: 'Research Chatbot',
        eyebrow: 'Conversation',
        description: 'Keep the writing loop active while your workspace context, imported papers, and live queries stay within reach.',
        action: { label: 'Go to dashboard', to: '/dashboard', icon: LayoutDashboard },
      };
    }
    if (path.startsWith('/upload')) {
      return {
        title: 'Upload Center',
        eyebrow: 'Ingestion',
        description: 'Bring local PDFs into the system, preserve metadata, and expand research context beyond public-source discovery.',
        action: { label: 'Open DocSpace', to: '/docs', icon: Files },
      };
    }
    if (path.startsWith('/docs')) {
      return {
        title: 'DocSpace',
        eyebrow: 'Reading Layer',
        description: 'Review imported material, inspect metadata, and navigate source evidence without leaving the research shell.',
        action: { label: 'Open Mindmap', to: '/mindmap', icon: Workflow },
      };
    }
    if (path.startsWith('/account')) {
      return {
        title: 'Account',
        eyebrow: 'Identity',
        description: 'Manage your profile, session context, and the access surface tied to this research workspace.',
        action: { label: 'Go to settings', to: '/settings', icon: Binary },
      };
    }
    if (path.startsWith('/settings')) {
      return {
        title: 'Settings',
        eyebrow: 'Preferences',
        description: 'Tune the environment, activation behavior, and the guardrails that keep the workspace stable.',
        action: { label: 'Go to home', to: '/home', icon: House },
      };
    }
    if (path.startsWith('/developer')) {
      return {
        title: 'Developer Console',
        eyebrow: 'Diagnostics',
        description: 'Inspect lower-level platform state and validate the operational health behind the user-facing workflows.',
        action: { label: 'Go to dashboard', to: '/dashboard', icon: LayoutDashboard },
      };
    }

    return {
      title: 'Research Command',
      eyebrow: 'Workspace',
      description: 'Resume the most important research task quickly and keep every next action one click away.',
      action: { label: 'Launch search', to: '/search', icon: Search },
    };
  }, [location.pathname]);

  const mobileLinks = [
    { to: '/home', icon: House, label: 'Home' },
    { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/search', icon: Search, label: 'Search' },
    { to: '/research-agent', icon: Bot, label: 'Agent' },
  ];

  const HeaderActionIcon = headerMeta.action.icon;

  return (
    <header className="sticky top-0 z-20 px-3 md:px-6 pt-3 pb-2">
      <div className="topbar-shell">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0 flex-1">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <p className="m-0 flex items-center gap-1.5 text-[11px] uppercase tracking-[0.2em] text-slate-500">
                <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
                {headerMeta.eyebrow}
              </p>
              <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-500">
                <Command className="h-3 w-3" />
                Ctrl K
              </span>
              <span className="inline-flex items-center gap-1 rounded-full border border-cyan-200 bg-cyan-50 px-2.5 py-1 text-[11px] font-semibold text-cyan-700">
                28+ source rails
              </span>
            </div>
            <p className="mb-1 flex items-center gap-1.5 text-[11px] uppercase tracking-[0.2em] text-slate-500">
              <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
              Neural Interface
            </p>
            <h1 className="truncate text-lg font-bold text-slate-900 md:text-xl">{headerMeta.title}</h1>
            <p className="mt-1 max-w-3xl text-sm leading-relaxed text-slate-600">{headerMeta.description}</p>
          </div>

          <div className="flex flex-col gap-2.5 xl:items-end">
            <div className="flex flex-wrap items-center gap-2.5 md:gap-3 xl:justify-end">
              <button
                type="button"
                onClick={openCommandPalette}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
              >
                <Command className="h-3.5 w-3.5" />
                Command menu
              </button>

              <Link to={headerMeta.action.to} className="hero-btn-primary">
                <HeaderActionIcon className="h-4 w-4" />
                {headerMeta.action.label}
              </Link>


            </div>

            {userEmail && (
              <div className="flex items-center gap-2 rounded-2xl border border-slate-200/80 bg-white/80 px-2.5 py-2 shadow-sm">
                <div className="topbar-avatar">{userInitials}</div>
                <div className="hidden lg:block">
                  <p className="text-sm font-semibold leading-tight text-slate-800">{userEmail}</p>
                  <p className="text-xs text-slate-400">Research Operator</p>
                </div>
                <button
                  type="button"
                  aria-label="Log out"
                  onClick={() => {
                    void clearAuthSession().finally(() => {
                      window.location.href = toAppPath('/login');
                    });
                  }}
                  className="ml-1 inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
                >
                  Logout
                  <ArrowUpRight className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold text-slate-600">
            Active surface
          </span>
          <span className="inline-flex items-center gap-1 rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-[11px] font-semibold text-indigo-700">
            {headerMeta.title}
          </span>
          <span className="hidden rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-500 md:inline-flex md:items-center md:gap-1">
            Ctrl/Cmd + K to jump anywhere
          </span>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-1.5 lg:hidden">
          {mobileLinks.map((item) => {
            const Icon = item.icon;
            const active = location.pathname.startsWith(item.to);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`inline-flex min-w-0 items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold transition-colors ${
                  active
                    ? 'border-indigo-200 bg-indigo-50 text-indigo-700'
                    : 'border-slate-200 bg-white text-slate-600'
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
