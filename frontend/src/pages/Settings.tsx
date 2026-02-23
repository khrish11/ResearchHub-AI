import React, { useEffect, useState } from 'react';
import { Bell, LayoutGrid, Sparkles, Workflow } from 'lucide-react';
import Layout from '../components/Layout';

const SETTINGS_KEY = 'researchhub_settings';

interface AppSettings {
  emailNotifications: boolean;
  compactSidebar: boolean;
  autoOpenLastWorkspace: boolean;
}

const defaultSettings: AppSettings = {
  emailNotifications: true,
  compactSidebar: false,
  autoOpenLastWorkspace: true,
};

const settingMeta: Record<
  keyof AppSettings,
  { title: string; copy: string; icon: React.ReactNode }
> = {
  emailNotifications: {
    title: 'Email notifications',
    copy: 'Receive alerts for imports, source checks, and workspace activity updates.',
    icon: <Bell className="h-4.5 w-4.5" />,
  },
  compactSidebar: {
    title: 'Compact sidebar',
    copy: 'Use tighter spacing and smaller labels in navigation for denser workspace view.',
    icon: <LayoutGrid className="h-4.5 w-4.5" />,
  },
  autoOpenLastWorkspace: {
    title: 'Auto-open last workspace',
    copy: 'Jump directly back into your previous workspace after authentication.',
    icon: <Workflow className="h-4.5 w-4.5" />,
  },
};

const Settings: React.FC = () => {
  const [settings, setSettings] = useState<AppSettings>(defaultSettings);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) {
      return;
    }
    try {
      const parsed = JSON.parse(raw);
      setSettings({ ...defaultSettings, ...parsed });
    } catch {
      setSettings(defaultSettings);
    }
  }, []);

  const updateSetting = (key: keyof AppSettings, value: boolean) => {
    const next = { ...settings, [key]: value };
    setSettings(next);
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(next));
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1500);
  };

  return (
    <Layout>
      <div className="page-enter max-w-4xl">
        <section className="studio-hero mb-5">
          <span className="studio-kicker">
            <Sparkles className="h-3.5 w-3.5" />
            Preference center
          </span>
          <h2>Application Settings</h2>
          <p>
            Tune your workspace behavior, alerts, and navigation defaults for a smoother research flow.
          </p>
          <div className="studio-chip-row">
            <span className="studio-chip">
              {Object.values(settings).filter(Boolean).length} enabled preferences
            </span>
          </div>
          <div className="studio-orb" aria-hidden="true" />
        </section>

        <section className="studio-surface p-4">
          <div className="settings-grid">
            {(Object.keys(settingMeta) as (keyof AppSettings)[]).map((key) => (
              <article key={key} className="setting-item">
                <div className="flex items-start gap-3">
                  <div className="studio-icon-chip bg-indigo-100 text-indigo-600">{settingMeta[key].icon}</div>
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{settingMeta[key].title}</p>
                    <p className="text-xs text-slate-500 mt-0.5 max-w-[340px]">{settingMeta[key].copy}</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => updateSetting(key, !settings[key])}
                  className={`switch ${settings[key] ? 'active' : ''}`}
                  aria-label={`Toggle ${settingMeta[key].title}`}
                />
              </article>
            ))}
          </div>

          {saved && (
            <p className="text-sm text-emerald-700 mt-3 font-semibold">Settings saved.</p>
          )}
        </section>
      </div>
    </Layout>
  );
};

export default Settings;
