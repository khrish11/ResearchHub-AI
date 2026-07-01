import React, { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
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
  pageTitle?: string;
}

const MobileLayout: React.FC<MobileLayoutProps> = ({
  children,
  userEmail,
  userInitials,
  canAccessAnalytics = false,
  isDeveloper = false,
  pageTitle = 'ResearchHub AI',
}) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const sidebarRef = useRef<HTMLDivElement | null>(null);
  const lastActiveElementRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (sidebarOpen && !target.closest('.mobile-sidebar') && !target.closest('.mobile-menu-btn')) {
        setSidebarOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [sidebarOpen]);

  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!sidebarOpen) {
      return undefined;
    }

    lastActiveElementRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const frameId = window.requestAnimationFrame(() => {
      const focusTarget = sidebarRef.current?.querySelector<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      focusTarget?.focus();
    });

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setSidebarOpen(false);
      }
    };

    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      window.cancelAnimationFrame(frameId);
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
      lastActiveElementRef.current?.focus();
    };
  }, [sidebarOpen]);

  return (
    <div className="min-h-screen overflow-x-hidden bg-slate-50 dark:bg-slate-900">
      {/* Mobile Header */}
      <header className="md:hidden sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 px-3 py-3 backdrop-blur dark:border-slate-700 dark:bg-slate-800/90">
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
                {pageTitle}
              </h1>
            </div>
          </div>

          <div className="flex flex-shrink-0 items-center gap-1.5">
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
          <div
            ref={sidebarRef}
            role="dialog"
            aria-modal="true"
            aria-label="Navigation menu"
            className="mobile-sidebar absolute left-0 top-0 h-full w-[min(20rem,calc(100vw-0.75rem))] bg-white dark:bg-slate-800 shadow-xl transform transition-transform duration-300 ease-in-out"
          >
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
      <div className="flex min-w-0">
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
        <main className="min-h-screen min-w-0 flex-1 overflow-x-hidden">
          <div className="container mx-auto max-w-7xl px-3 py-5 sm:px-4 md:px-6 md:py-6 lg:px-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

export default MobileLayout;
