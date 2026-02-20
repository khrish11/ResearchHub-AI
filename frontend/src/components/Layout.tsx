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
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar userEmail={email} userInitials={initials} />
      <div className="flex-1 flex flex-col">
        <Header userEmail={email} userInitials={initials} />
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
};

export default Layout;
