import React, { useEffect, useState } from 'react';
import { Bell, LayoutGrid, Sparkles, Workflow } from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';
import { apiErrorMessage } from '../utils/apiError';

const SETTINGS_KEY = 'researchhub_settings';

interface AppSettings {
  emailNotifications: boolean;
  compactSidebar: boolean;
  autoOpenLastWorkspace: boolean;
}

interface AiModelsResponse {
  configured: boolean;
  enabled: boolean;
  error?: string | null;
  available_models: string[];
  active_model: string;
  active_longform_model: string;
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
  const [aiModels, setAiModels] = useState<AiModelsResponse | null>(null);
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedLongformModel, setSelectedLongformModel] = useState('');
  const [applyToAll, setApplyToAll] = useState(true);
  const [modelSaving, setModelSaving] = useState(false);
  const [modelMsg, setModelMsg] = useState<string | null>(null);
  const [modelErr, setModelErr] = useState<string | null>(null);

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

  useEffect(() => {
    api
      .get<AiModelsResponse>('/ai/models')
      .then((res) => {
        setAiModels(res.data);
        setSelectedModel(res.data.active_model || '');
        setSelectedLongformModel(res.data.active_longform_model || res.data.active_model || '');
      })
      .catch((err: unknown) => {
        setModelErr(apiErrorMessage(err, 'Failed to load AI model settings.'));
      });
  }, []);

  const updateSetting = (key: keyof AppSettings, value: boolean) => {
    const next = { ...settings, [key]: value };
    setSettings(next);
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(next));
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1500);
  };

  const saveAiModelSelection = async () => {
    if (!selectedModel) {
      setModelErr('Select a base model first.');
      return;
    }
    if (!applyToAll && !selectedLongformModel) {
      setModelErr('Select a longform model.');
      return;
    }

    setModelSaving(true);
    setModelErr(null);
    setModelMsg(null);
    try {
      const response = await api.post<AiModelsResponse & { message: string }>('/ai/models/select', {
        model: selectedModel,
        longform_model: applyToAll ? selectedModel : selectedLongformModel,
        apply_to_all: applyToAll,
      });
      setAiModels(response.data);
      setSelectedModel(response.data.active_model || selectedModel);
      setSelectedLongformModel(response.data.active_longform_model || selectedLongformModel);
      setModelMsg(response.data.message || 'AI model updated.');
    } catch (err: unknown) {
      setModelErr(apiErrorMessage(err, 'Failed to update AI model.'));
    } finally {
      setModelSaving(false);
    }
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
          <article className="setting-item mb-3">
            <div className="flex items-start gap-3">
              <div className="studio-icon-chip bg-indigo-100 text-indigo-600">
                <Sparkles className="h-4.5 w-4.5" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-900">AI Model Selection</p>
                <p className="text-xs text-slate-500 mt-0.5 max-w-[520px]">
                  Select which Groq model powers all AI actions across summaries, chat, research agent,
                  reviews, and longform synthesis.
                </p>
                {aiModels && (
                  <p className="text-xs mt-1 text-slate-500">
                    Active: <span className="font-semibold">{aiModels.active_model}</span> | Longform:{' '}
                    <span className="font-semibold">{aiModels.active_longform_model}</span>
                  </p>
                )}
              </div>
            </div>
            <div className="w-full md:w-[520px] space-y-2">
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">Select base model</option>
                {(aiModels?.available_models || []).map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>

              <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={applyToAll}
                  onChange={(e) => setApplyToAll(e.target.checked)}
                />
                Use same model for longform tasks
              </label>

              {!applyToAll && (
                <select
                  value={selectedLongformModel}
                  onChange={(e) => setSelectedLongformModel(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">Select longform model</option>
                  {(aiModels?.available_models || []).map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              )}

              <button
                type="button"
                onClick={() => void saveAiModelSelection()}
                disabled={modelSaving || !selectedModel}
                className="hero-btn-primary disabled:opacity-60"
              >
                {modelSaving ? 'Saving...' : 'Save AI Model'}
              </button>

              {modelErr && <p className="text-xs text-rose-600">{modelErr}</p>}
              {modelMsg && <p className="text-xs text-emerald-600">{modelMsg}</p>}
            </div>
          </article>

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
