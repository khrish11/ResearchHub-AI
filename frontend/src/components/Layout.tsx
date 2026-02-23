import React from 'react';
import Sidebar from './Sidebar';
import Header from './Header';
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

  return (
    <div className="app-shell min-h-screen">
      <div className="app-shell-bg" aria-hidden="true">
        <div className="nebula nebula-a" />
        <div className="nebula nebula-b" />
        <div className="nebula nebula-c" />
      </div>
      <div className="flex min-h-screen relative z-10">
        <Sidebar userEmail={email} userInitials={initials} />
        <div className="flex-1 flex flex-col min-w-0">
          <Header userEmail={email} userInitials={initials} />
          <main className="flex-1 p-4 md:p-6 lg:p-7 overflow-x-hidden">
            <div className="mx-auto w-full max-w-[1440px]">{children}</div>
          </main>
        </div>
      </div>
    </div>
  );
};

export default Layout;
