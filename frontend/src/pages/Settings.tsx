import React, { useEffect, useState } from 'react';
import { Bell, LayoutGrid, Sparkles, Workflow } from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';
import { apiErrorMessage } from '../utils/apiError';
import { hasOptionalTelemetryConsent } from '../utils/consent';
import { requestPushNotifications } from '../utils/firebaseClient';
import { firebaseAuthAvailable } from '../utils/firebaseAuth';

const SETTINGS_KEY = 'researchhub_settings';
const TASK_MODEL_ORDER = ['chat', 'upload_summary', 'mindmap', 'pipeline'];

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
  active_task_models: Record<string, string>;
  task_model_labels: Record<string, string>;
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
    copy: 'Receive email updates about workspace activity, research agent completions, and paper imports.',
    icon: <Bell className="h-4.5 w-4.5" />,
  },
  compactSidebar: {
    title: 'Compact sidebar',
    copy: 'Reduce navigation width and label spacing.',
    icon: <LayoutGrid className="h-4.5 w-4.5" />,
  },
  autoOpenLastWorkspace: {
    title: 'Auto-open last workspace',
    copy: 'Return directly to your most recent workspace after login.',
    icon: <Workflow className="h-4.5 w-4.5" />,
  },
};

const taskModelsMatchDefaults = (payload: AiModelsResponse) => {
  const taskModels = payload.active_task_models || {};
  return TASK_MODEL_ORDER.every((task) => {
    const selected = taskModels[task] || '';
    const expected =
      task === 'mindmap' || task === 'pipeline'
        ? payload.active_longform_model || payload.active_model
        : payload.active_model;
    return selected === expected;
  });
};

const Settings: React.FC = () => {
  const [settings, setSettings] = useState<AppSettings>(defaultSettings);
  const [saved, setSaved] = useState(false);
  const [aiModels, setAiModels] = useState<AiModelsResponse | null>(null);
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedLongformModel, setSelectedLongformModel] = useState('');
  const [selectedTaskModels, setSelectedTaskModels] = useState<Record<string, string>>({});
  const [applyToAll, setApplyToAll] = useState(true);
  const [modelSaving, setModelSaving] = useState(false);
  const [modelMsg, setModelMsg] = useState<string | null>(null);
  const [modelErr, setModelErr] = useState<string | null>(null);
  const [pushStatus, setPushStatus] = useState<NotificationPermission | 'unsupported'>(
    typeof Notification === 'undefined' ? 'unsupported' : Notification.permission,
  );
  const [pushBusy, setPushBusy] = useState(false);

  useEffect(() => {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return;
    try {
      setSettings({ ...defaultSettings, ...JSON.parse(raw) });
    } catch {
      setSettings(defaultSettings);
    }
  }, []);

  useEffect(() => {
    api
      .get<AiModelsResponse>('/ai/models')
      .then((res) => {
        const payload = res.data;
        setAiModels(payload);
        setSelectedModel(payload.active_model || '');
        setSelectedLongformModel(payload.active_longform_model || payload.active_model || '');
        setSelectedTaskModels(payload.active_task_models || {});
        setApplyToAll(taskModelsMatchDefaults(payload));
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

  const updateTaskModel = (task: string, value: string) => {
    setSelectedTaskModels((current) => ({ ...current, [task]: value }));
  };

  const availableModels = aiModels?.available_models || [];
  const taskLabels = aiModels?.task_model_labels || {};
  const visibleTaskKeys = TASK_MODEL_ORDER.filter((task) => taskLabels[task] || selectedTaskModels[task]);
  const optionalTelemetryEnabled = hasOptionalTelemetryConsent();
  const firebaseAuthEnabled = firebaseAuthAvailable();

  const saveAiModelSelection = async () => {
    if (!selectedModel) {
      setModelErr('Select a base model first.');
      return;
    }
    if (!selectedLongformModel) {
      setModelErr('Select a longform model.');
      return;
    }
    if (!applyToAll && visibleTaskKeys.some((task) => !selectedTaskModels[task])) {
      setModelErr('Select a model for each feature slot.');
      return;
    }

    setModelSaving(true);
    setModelErr(null);
    setModelMsg(null);
    try {
      const response = await api.post<AiModelsResponse & { message: string }>('/ai/models/select', {
        model: selectedModel,
        longform_model: selectedLongformModel,
        apply_to_all: applyToAll,
        task_models: applyToAll ? undefined : selectedTaskModels,
      });
      const payload = response.data;
      setAiModels(payload);
      setSelectedModel(payload.active_model || selectedModel);
      setSelectedLongformModel(payload.active_longform_model || selectedLongformModel);
      setSelectedTaskModels(payload.active_task_models || selectedTaskModels);
      setApplyToAll(taskModelsMatchDefaults(payload));
      setModelMsg(payload.message || 'AI model routing updated.');
    } catch (err: unknown) {
      setModelErr(apiErrorMessage(err, 'Failed to update AI model routing.'));
    } finally {
      setModelSaving(false);
    }
  };

  const enableBrowserNotifications = async () => {
    setPushBusy(true);
    setModelErr(null);
    try {
      const result = await requestPushNotifications();
      setPushStatus(result.permission);
      if (result.token) {
        setModelMsg('Browser notifications enabled.');
      } else if (result.permission === 'granted') {
        setModelMsg('Browser notifications are enabled, but FCM token generation still needs VAPID key configuration.');
      } else {
        setModelMsg('Browser notifications were not enabled.');
      }
    } catch (err: unknown) {
      setModelErr(apiErrorMessage(err, 'Failed to enable browser notifications.'));
    } finally {
      setPushBusy(false);
    }
  };

  return (
    <Layout>
      <div className="page-enter max-w-4xl space-y-5">
        <header className="space-y-2">
          <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">
            <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
            Settings
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950">Application settings</h1>
          <p className="max-w-2xl text-sm leading-6 text-slate-600">
            Keep preferences lean. Use the base model for general actions and assign stronger models only where they improve results.
          </p>
        </header>

        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
            <div>
              <h2 className="text-base font-semibold text-slate-900">AI model routing</h2>
              <p className="mt-1 max-w-2xl text-sm text-slate-500">
                Route different features to different models. Mindmap and pipeline can stay on a heavier model without forcing the same choice everywhere.
              </p>
            </div>
            {aiModels && (
              <div className="text-right text-xs text-slate-500">
                <p>Base: <span className="font-semibold text-slate-700">{aiModels.active_model}</span></p>
                <p>Longform: <span className="font-semibold text-slate-700">{aiModels.active_longform_model}</span></p>
              </div>
            )}
          </div>

          {!aiModels?.enabled && (
            <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              {aiModels?.error || modelErr || 'AI is not configured. Set GROQ_API_KEY in backend/.env first.'}
            </div>
          )}

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <label className="block text-sm text-slate-500">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Base model</span>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700"
              >
                <option value="">Select base model</option>
                {availableModels.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-sm text-slate-500">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Longform model</span>
              <select
                value={selectedLongformModel}
                onChange={(e) => setSelectedLongformModel(e.target.value)}
                className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700"
              >
                <option value="">Select longform model</option>
                {availableModels.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="mt-4 inline-flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={applyToAll}
              onChange={(e) => setApplyToAll(e.target.checked)}
            />
            Use base and longform defaults for every feature
          </label>

          {!applyToAll && (
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {visibleTaskKeys.map((task) => (
                <label key={task} className="block text-sm text-slate-500">
                  <span className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                    {taskLabels[task] || task}
                  </span>
                  <select
                    value={selectedTaskModels[task] || ''}
                    onChange={(e) => updateTaskModel(task, e.target.value)}
                    className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700"
                  >
                    <option value="">Select feature model</option>
                    {availableModels.map((model) => (
                      <option key={`${task}-${model}`} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => void saveAiModelSelection()}
              disabled={modelSaving || !selectedModel || !selectedLongformModel}
              className="hero-btn-primary disabled:opacity-60"
            >
              {modelSaving ? 'Saving...' : 'Save AI routing'}
            </button>
            {modelErr && <p className="text-xs text-rose-600">{modelErr}</p>}
            {modelMsg && <p className="text-xs text-emerald-600">{modelMsg}</p>}
          </div>
        </section>

        <section className="grid gap-3 md:grid-cols-2">
          {(Object.keys(settingMeta) as (keyof AppSettings)[]).map((key) => (
            <article key={key} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="studio-icon-chip bg-indigo-100 text-indigo-600">{settingMeta[key].icon}</div>
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{settingMeta[key].title}</p>
                    <p className="mt-0.5 max-w-[320px] text-xs leading-5 text-slate-500">{settingMeta[key].copy}</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => updateSetting(key, !settings[key])}
                  className={`switch ${settings[key] ? 'active' : ''}`}
                  aria-label={`Toggle ${settingMeta[key].title}`}
                />
              </div>
            </article>
          ))}
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-slate-900">Google services</p>
              <p className="mt-0.5 text-xs leading-5 text-slate-500">
                Firebase Auth is {firebaseAuthEnabled ? 'enabled' : 'disabled'}, optional telemetry is {optionalTelemetryEnabled ? 'allowed' : 'blocked'}, and browser notifications are {pushStatus}.
              </p>
            </div>
            <button
              type="button"
              onClick={() => void enableBrowserNotifications()}
              disabled={pushBusy || pushStatus === 'unsupported'}
              className="hero-btn-secondary disabled:opacity-60"
            >
              {pushBusy ? 'Enabling...' : 'Enable notifications'}
            </button>
          </div>
        </section>

        {saved && <p className="text-sm font-medium text-emerald-700">Settings saved.</p>}
      </div>
    </Layout>
  );
};

export default Settings;
