import React from 'react';
import { useLocation } from 'react-router-dom';
import Header from './Header';
import MobileLayout from './MobileLayout';
import { useUser } from '../hooks/useUser';

interface LayoutProps {
  children: React.ReactNode;
  // Props kept for backwards compat but no longer used by consumers —
  // Layout now fetches user data itself via useUser.
  userEmail?: string;
  userInitials?: string;
}

const routeTitles: Array<{ match: RegExp; title: string }> = [
  { match: /^\/dashboard/, title: 'Dashboard' },
  { match: /^\/search/, title: 'Search Papers' },
  { match: /^\/workspace(\/|$)/, title: 'Workspace' },
  { match: /^\/compare/, title: 'Compare Papers' },
  { match: /^\/research-report/, title: 'Research Report' },
  { match: /^\/research-agent/, title: 'Research Agent' },
  { match: /^\/upload/, title: 'Upload PDF' },
  { match: /^\/settings/, title: 'Settings' },
  { match: /^\/privacy/, title: 'Privacy' },
  { match: /^\/terms/, title: 'Terms' },
  { match: /^\/cookies/, title: 'Cookies' },
  { match: /^\/data-rights/, title: 'Data Rights' },
  { match: /^\/verify-email/, title: 'Verify Email' },
  { match: /^\/forgot-password/, title: 'Forgot Password' },
  { match: /^\/reset-password/, title: 'Reset Password' },
  { match: /^\/home/, title: 'Home' },
  { match: /^\/ai-tools/, title: 'AI Tools' },
  { match: /^\/research-chat/, title: 'Research Chat' },
  { match: /^\/ask-workspace/, title: 'Ask Workspace' },
  { match: /^\/docs/, title: 'DocSpace' },
  { match: /^\/mindmap/, title: 'Mindmap' },
  { match: /^\/account/, title: 'Account' },
  { match: /^\/analytics/, title: 'AI Analytics' },
  { match: /^\/developer/, title: 'Admin Console' },
];

const getPageTitle = (pathname: string) =>
  routeTitles.find((route) => route.match.test(pathname))?.title || 'ResearchHub AI';

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation();
  const { user } = useUser();
  const email = user?.email;
  const initials = user?.initials ?? '?';
  const canAccessAnalytics = Boolean(user?.canAccessAnalytics);
  const isDeveloper = Boolean(user?.isDeveloper);
  const pageTitle = getPageTitle(location.pathname);

  return (
    <MobileLayout
      userEmail={email}
      userInitials={initials}
      canAccessAnalytics={canAccessAnalytics}
      isDeveloper={isDeveloper}
      pageTitle={pageTitle}
    >
      <div className="space-y-6">
        <Header userEmail={email} userInitials={initials} />
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm md:px-5">
          <h1 className="text-lg font-semibold text-slate-900 md:text-xl">{pageTitle}</h1>
        </div>
        <div className="max-w-none">
          {children}
        </div>
      </div>
    </MobileLayout>
  );
};

export default Layout;
