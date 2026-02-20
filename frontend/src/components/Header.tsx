import { useEffect, useState } from 'react';
import api from '../api';

interface HeaderProps {
  userEmail?: string;
  userInitials?: string;
}

const Header: React.FC<HeaderProps> = ({ userEmail, userInitials = 'U' }) => {
  const [aiEnabled, setAiEnabled] = useState<boolean | null>(null);
  const [aiModel, setAiModel] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    api.get('/ai/status')
      .then((res: any) => {
        if (!mounted) return;
        setAiEnabled(!!res.data.enabled);
        setAiModel(res.data.model || null);
      })
      .catch(() => {
        if (!mounted) return;
        setAiEnabled(false);
        setAiModel(null);
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <header className="bg-white border-b border-slate-200 px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          {/* Search bar can go here if needed */}
        </div>
        <div className="flex items-center gap-4">
          {aiEnabled !== null && (
            <div className={`px-2 py-1 rounded-full text-xs font-semibold ${aiEnabled ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>
              AI: {aiEnabled ? `Enabled${aiModel ? ` (${aiModel})` : ''}` : 'Disabled'}
            </div>
          )}

          {userEmail && (
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-full bg-indigo-600 flex items-center justify-center text-white text-sm font-medium">
                {userInitials}
              </div>
              <span className="text-sm text-slate-700">{userEmail}</span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;
