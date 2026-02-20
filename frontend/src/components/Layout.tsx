import React from 'react';
import Sidebar from './Sidebar';
import Header from './Header';

interface LayoutProps {
  children: React.ReactNode;
  userEmail?: string;
  userInitials?: string;
}

const Layout: React.FC<LayoutProps> = ({ children, userEmail, userInitials }) => {
  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar userEmail={userEmail} userInitials={userInitials} />
      <div className="flex-1 flex flex-col">
        <Header userEmail={userEmail} userInitials={userInitials} />
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
};

export default Layout;
