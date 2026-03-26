import React, { useState, useEffect } from 'react';
import { Command, Menu, X } from 'lucide-react';
import Sidebar from './Sidebar';
import ThemeToggle from './ThemeToggle';
import { openCommandPalette } from '../utils/commandPalette';

interface MobileLayoutProps {
  children: React.ReactNode;
  userEmail?: string;
  userInitials?: string;
  canAccessAnalytics?: boolean;
  isDeveloper?: boolean;
}

const MobileLayout: React.FC<MobileLayoutProps> = ({
  children,
  userEmail,
  userInitials,
  canAccessAnalytics = false,
  isDeveloper = false,
}) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Close sidebar on route change or when clicking outside
  useEffect(() => {
    const handleRouteChange = () => setSidebarOpen(false);
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (sidebarOpen && !target.closest('.mobile-sidebar') && !target.closest('.mobile-menu-btn')) {
        setSidebarOpen(false);
      }
    };

    window.addEventListener('popstate', handleRouteChange);
    document.addEventListener('mousedown', handleClickOutside);

    return () => {
      window.removeEventListener('popstate', handleRouteChange);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [sidebarOpen]);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      {/* Mobile Header */}
      <header className="md:hidden sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 px-4 py-3 backdrop-blur dark:border-slate-700 dark:bg-slate-800/90">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <button
              onClick={() => setSidebarOpen(true)}
              className="mobile-menu-btn p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5 text-slate-600 dark:text-slate-300" />
            </button>

            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-indigo-600 dark:text-indigo-300">
                Research shell
              </p>
              <h1 className="truncate text-base font-semibold text-slate-900 dark:text-slate-100">
                Soyog AI
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={openCommandPalette}
              className="inline-flex items-center justify-center rounded-lg border border-slate-200 bg-white p-2 text-slate-600 shadow-sm transition-colors hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
              aria-label="Open command palette"
            >
              <Command className="h-4 w-4" />
            </button>
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/50" onClick={() => setSidebarOpen(false)} />
          <div className="mobile-sidebar absolute left-0 top-0 h-full w-80 bg-white dark:bg-slate-800 shadow-xl transform transition-transform duration-300 ease-in-out">
            <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                Menu
              </h2>
              <button
                onClick={() => setSidebarOpen(false)}
                className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                aria-label="Close menu"
              >
                <X className="h-5 w-5 text-slate-600 dark:text-slate-300" />
              </button>
            </div>
            <div className="overflow-y-auto h-full pb-20">
              <Sidebar
                mobile
                userEmail={userEmail}
                userInitials={userInitials}
                canAccessAnalytics={canAccessAnalytics}
                isDeveloper={isDeveloper}
              />
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="flex">
        {/* Desktop Sidebar */}
        <div className="hidden md:block">
          <Sidebar
            userEmail={userEmail}
            userInitials={userInitials}
            canAccessAnalytics={canAccessAnalytics}
            isDeveloper={isDeveloper}
          />
        </div>

        {/* Page Content */}
        <main className="flex-1 min-h-screen overflow-x-auto">
          <div className="container mx-auto px-4 py-6 md:px-6 lg:px-8 max-w-7xl">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

export default MobileLayout;
