import React, { useState, useEffect } from 'react';
import { Menu, X } from 'lucide-react';
import Sidebar from './Sidebar';
import ThemeToggle from './ThemeToggle';

interface MobileLayoutProps {
  children: React.ReactNode;
  userEmail?: string;
  userInitials?: string;
}

const MobileLayout: React.FC<MobileLayoutProps> = ({
  children,
  userEmail,
  userInitials,
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
      <header className="md:hidden bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-4 py-3 flex items-center justify-between">
        <button
          onClick={() => setSidebarOpen(true)}
          className="mobile-menu-btn p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5 text-slate-600 dark:text-slate-300" />
        </button>

        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            ResearchHub AI
          </h1>
        </div>

        <div className="flex items-center gap-2">
          <ThemeToggle />
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
              <Sidebar mobile userEmail={userEmail} userInitials={userInitials} />
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="flex">
        {/* Desktop Sidebar */}
        <div className="hidden md:block">
          <Sidebar userEmail={userEmail} userInitials={userInitials} />
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
