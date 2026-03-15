import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Brain,
  Bot,
  FileText,
  Home,
  LayoutDashboard,
  Search,
  Settings,
  Upload,
  UserCog,
  LogOut,
  CornerDownLeft,
  Clock3,
  Bell,
  MessageSquareCode,
} from 'lucide-react';
import { toAppPath } from '../utils/routing';
import { OPEN_COMMAND_PALETTE_EVENT } from '../utils/commandPalette';
import { clearAuthSession } from '../utils/authSession';

const SAVED_QUERIES_STORAGE_KEY = 'researchhub.saved_queries.v1';

interface SavedQueryRecord {
  id: string;
  query: string;
  watchEnabled?: boolean;
}

interface CommandItem {
  id: string;
  title: string;
  subtitle?: string;
  group: string;
  icon: React.ReactNode;
  keywords: string[];
  onSelect: () => void;
}

const loadSavedQueries = (): SavedQueryRecord[] => {
  try {
    const raw = localStorage.getItem(SAVED_QUERIES_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item) => item && typeof item.id === 'string' && typeof item.query === 'string')
      .map((item) => ({
        id: String(item.id),
        query: String(item.query).trim(),
        watchEnabled: Boolean(item.watchEnabled),
      }))
      .filter((item) => item.query.length > 0)
      .slice(0, 12);
  } catch {
    return [];
  }
};

const CommandPalette: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const [savedQueries, setSavedQueries] = useState<SavedQueryRecord[]>([]);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const onGlobalKeyDown = (event: KeyboardEvent) => {
      const openHotkey = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k';
      if (!openHotkey) return;
      event.preventDefault();
      setOpen((prev) => !prev);
    };

    const onOpenEvent = () => {
      setOpen(true);
    };

    window.addEventListener('keydown', onGlobalKeyDown);
    window.addEventListener(OPEN_COMMAND_PALETTE_EVENT, onOpenEvent);
    return () => {
      window.removeEventListener('keydown', onGlobalKeyDown);
      window.removeEventListener(OPEN_COMMAND_PALETTE_EVENT, onOpenEvent);
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    setSavedQueries(loadSavedQueries());
    setQuery('');
    setActiveIndex(0);
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }, [open]);

  const go = useCallback((path: string) => {
    navigate(path);
    setOpen(false);
  }, [navigate]);

  const baseCommands = useMemo<CommandItem[]>(
    () => [
      {
        id: 'go-home',
        title: 'Go to Home',
        subtitle: '/home',
        group: 'Navigation',
        icon: <Home className="h-4 w-4" />,
        keywords: ['home', 'landing'],
        onSelect: () => go('/home'),
      },
      {
        id: 'go-dashboard',
        title: 'Go to Dashboard',
        subtitle: '/dashboard',
        group: 'Navigation',
        icon: <LayoutDashboard className="h-4 w-4" />,
        keywords: ['dashboard', 'overview'],
        onSelect: () => go('/dashboard'),
      },
      {
        id: 'go-search',
        title: 'Go to Search Papers',
        subtitle: '/search',
        group: 'Navigation',
        icon: <Search className="h-4 w-4" />,
        keywords: ['search', 'papers', 'discover'],
        onSelect: () => go('/search'),
      },
      {
        id: 'go-ai-tools',
        title: 'Go to AI Tools',
        subtitle: '/ai-tools',
        group: 'Navigation',
        icon: <Brain className="h-4 w-4" />,
        keywords: ['ai', 'tools'],
        onSelect: () => go('/ai-tools'),
      },
      {
        id: 'go-research-chat',
        title: 'Go to Research Chat',
        subtitle: '/research-chat',
        group: 'Navigation',
        icon: <MessageSquareCode className="h-4 w-4" />,
        keywords: ['research', 'chat', 'copilot', 'assistant', 'papers'],
        onSelect: () => go('/research-chat'),
      },
      {
        id: 'go-research-agent',
        title: 'Go to Research Agent',
        subtitle: '/research-agent',
        group: 'Navigation',
        icon: <Bot className="h-4 w-4" />,
        keywords: ['research', 'agent', 'automation', 'assistant'],
        onSelect: () => go('/research-agent'),
      },
      {
        id: 'go-upload',
        title: 'Go to Upload PDF',
        subtitle: '/upload',
        group: 'Navigation',
        icon: <Upload className="h-4 w-4" />,
        keywords: ['upload', 'pdf'],
        onSelect: () => go('/upload'),
      },
      {
        id: 'go-docs',
        title: 'Go to DocSpace',
        subtitle: '/docs',
        group: 'Navigation',
        icon: <FileText className="h-4 w-4" />,
        keywords: ['docs', 'docspace'],
        onSelect: () => go('/docs'),
      },
      {
        id: 'go-account',
        title: 'Go to Account',
        subtitle: '/account',
        group: 'Navigation',
        icon: <UserCog className="h-4 w-4" />,
        keywords: ['account', 'profile'],
        onSelect: () => go('/account'),
      },
      {
        id: 'go-settings',
        title: 'Go to Settings',
        subtitle: '/settings',
        group: 'Navigation',
        icon: <Settings className="h-4 w-4" />,
        keywords: ['settings', 'preferences'],
        onSelect: () => go('/settings'),
      },
      {
        id: 'logout',
        title: 'Log out',
        subtitle: 'End session and return to login',
        group: 'Account',
        icon: <LogOut className="h-4 w-4" />,
        keywords: ['logout', 'sign out'],
        onSelect: () => {
          void clearAuthSession().finally(() => {
            window.location.href = toAppPath('/login');
          });
        },
      },
    ],
    [go]
  );

  const savedQueryCommands = useMemo<CommandItem[]>(
    () =>
      savedQueries.map((saved) => ({
        id: `saved-${saved.id}`,
        title: saved.query,
        subtitle: 'Run saved search',
        group: 'Saved Searches',
        icon: <Clock3 className="h-4 w-4" />,
        keywords: ['saved', 'query', saved.query],
        onSelect: () => {
          navigate(`/search?q=${encodeURIComponent(saved.query)}&autorun=1`);
          setOpen(false);
        },
      })),
    [savedQueries, navigate]
  );

  const watchlistCommands = useMemo<CommandItem[]>(
    () =>
      savedQueries
        .filter((saved) => saved.watchEnabled)
        .map((saved) => ({
          id: `watch-${saved.id}`,
          title: saved.query,
          subtitle: 'Open watchlist query',
          group: 'Watchlists',
          icon: <Bell className="h-4 w-4" />,
          keywords: ['watchlist', 'watch', saved.query],
          onSelect: () => {
            navigate(`/search?q=${encodeURIComponent(saved.query)}&autorun=1`);
            setOpen(false);
          },
        })),
    [savedQueries, navigate]
  );

  const allCommands = useMemo(
    () => [...baseCommands, ...savedQueryCommands, ...watchlistCommands],
    [baseCommands, savedQueryCommands, watchlistCommands]
  );

  const filteredCommands = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return allCommands;
    return allCommands.filter((item) =>
      [item.title, item.subtitle || '', item.group, ...item.keywords]
        .join(' ')
        .toLowerCase()
        .includes(normalized)
    );
  }, [allCommands, query]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setOpen(false);
        return;
      }
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        setActiveIndex((prev) => {
          if (filteredCommands.length === 0) return 0;
          return (prev + 1) % filteredCommands.length;
        });
        return;
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        setActiveIndex((prev) => {
          if (filteredCommands.length === 0) return 0;
          return prev <= 0 ? filteredCommands.length - 1 : prev - 1;
        });
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [open, filteredCommands.length]);

  useEffect(() => {
    setActiveIndex((prev) => {
      if (filteredCommands.length === 0) return 0;
      return Math.min(prev, filteredCommands.length - 1);
    });
  }, [filteredCommands.length]);

  useEffect(() => {
    if (!open) return;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = '';
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    setOpen(false);
  }, [location.pathname, open]);

  if (!open) {
    return null;
  }

  const runActiveCommand = () => {
    const target = filteredCommands[activeIndex];
    if (!target) return;
    target.onSelect();
  };

  return (
    <div className="fixed inset-0 z-50">
      <button
        type="button"
        aria-label="Close command palette"
        className="absolute inset-0 bg-slate-900/35 backdrop-blur-[2px]"
        onClick={() => setOpen(false)}
      />

      <div className="absolute inset-x-0 top-[8vh] mx-auto w-[min(760px,92vw)] rounded-2xl border border-slate-200 bg-white shadow-2xl overflow-hidden">
        <div className="border-b border-slate-200 px-4 py-3">
          <div className="flex items-center gap-3">
            <Search className="h-4 w-4 text-slate-400" />
            <input
              ref={inputRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  runActiveCommand();
                }
              }}
              placeholder="Type a command, page, or saved search..."
              className="w-full bg-transparent text-sm text-slate-800 placeholder:text-slate-400 outline-none"
            />
            <span className="hidden sm:inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-[11px] text-slate-500">
              <CornerDownLeft className="h-3 w-3" /> run
            </span>
          </div>
        </div>

        <div className="max-h-[55vh] overflow-y-auto p-2">
          {filteredCommands.length === 0 ? (
            <div className="px-3 py-8 text-center text-sm text-slate-500">No commands found.</div>
          ) : (
            filteredCommands.map((item, index) => {
              const active = index === activeIndex;
              return (
                <button
                  key={item.id}
                  type="button"
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => item.onSelect()}
                  className={`w-full text-left px-3 py-2.5 rounded-xl transition-colors ${
                    active ? 'bg-indigo-50 border border-indigo-200' : 'hover:bg-slate-50 border border-transparent'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-slate-800 truncate flex items-center gap-2">
                        <span className="text-slate-500">{item.icon}</span>
                        {item.title}
                      </p>
                      {item.subtitle && <p className="text-xs text-slate-500 truncate mt-0.5">{item.subtitle}</p>}
                    </div>
                    <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                      {item.group}
                    </span>
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};

export default CommandPalette;
