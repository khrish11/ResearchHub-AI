import React from 'react';
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

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { user } = useUser();
  const email = user?.email;
  const initials = user?.initials ?? '?';
  const canAccessAnalytics = Boolean(user?.canAccessAnalytics);
  const isDeveloper = Boolean(user?.isDeveloper);

  return (
    <MobileLayout
      userEmail={email}
      userInitials={initials}
      canAccessAnalytics={canAccessAnalytics}
      isDeveloper={isDeveloper}
    >
      <div className="space-y-6">
        <Header userEmail={email} userInitials={initials} />
        <div className="max-w-none">
          {children}
        </div>
      </div>
    </MobileLayout>
  );
};

export default Layout;
