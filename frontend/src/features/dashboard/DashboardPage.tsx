import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  ArrowRight,
  AlertTriangle,
  Folder,
  FileText,
  Plus,
  Trash2,
  X,
  Check,
  Loader2,
  Database,
  BrainCircuit,
  Download,
  ArrowUpRight,
  Sparkles,
  Bot,
  Search,
  TrendingUp,
  BookMarked,
  Compass,
  Upload,
  Workflow,
  CheckCheck,
  BellRing,
  CheckCircle2,
  Circle,
  PlayCircle,
  XCircle,
  Lightbulb,
  WandSparkles,
} from 'lucide-react';
import Layout from '../../components/Layout';
import UnifiedCopilotPanel from '../../components/UnifiedCopilotPanel';
import api from '../../api';
import { useLocalStorage } from '../../hooks/useLocalStorage';
import { apiErrorMessage } from '../../utils/apiError';
import { useWorkspaceSummary } from './hooks/useWorkspaceSummary';
import type {
  DemoModeStateResponse,
  OnboardingStatusResponse,
  WorkspaceFeedItem,
  WorkspaceFeedResponse,
  WorkspaceInsightItem,
  WorkspaceInsightSource,
  WorkspaceInsightsPayload,
  WorkspaceInsightsResponse,
  WorkspaceTemplate,
} from './types';

const Dashboard = () => {
  const location = useLocation();
  const { workspaces, loading, totalPapers, totalChars, fetchWorkspaces, isUserCreatedWorkspace } = useWorkspaceSummary();

  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [creating, setCreating] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [activeInsightsWorkspaceId, setActiveInsightsWorkspaceId] = useState<number | null>(null);
  const [insights, setInsights] = useState<WorkspaceInsightsResponse | null>(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insightsRefreshing, setInsightsRefreshing] = useState(false);
  const [insightsError, setInsightsError] = useState<string | null>(null);
  const [feedItems, setFeedItems] = useState<WorkspaceFeedItem[]>([]);
  const [feedCursor, setFeedCursor] = useState<string | null>(null);
  const [feedHasMore, setFeedHasMore] = useState(false);
  const [feedSort, setFeedSort] = useState<'importance' | 'recent'>('importance');
  const [feedLoading, setFeedLoading] = useState(false);
  const [feedLoadingMore, setFeedLoadingMore] = useState(false);
  const [feedRefreshing, setFeedRefreshing] = useState(false);
  const [feedError, setFeedError] = useState<string | null>(null);
  const [feedUnreadCount, setFeedUnreadCount] = useState(0);
  const [feedDisclaimer, setFeedDisclaimer] = useState(
    'Feed items are AI-assisted signals from your workspace evidence. Always validate by opening linked source papers.'
  );
  const [onboarding, setOnboarding] = useState<OnboardingStatusResponse | null>(null);
  const [onboardingLoading, setOnboardingLoading] = useState(false);
  const [onboardingError, setOnboardingError] = useState<string | null>(null);
  const [demoBootstrapping, setDemoBootstrapping] = useState(false);
  const [demoState, setDemoState] = useState<DemoModeStateResponse | null>(null);
  const [demoStateLoading, setDemoStateLoading] = useState(false);
  const [demoStepUpdating, setDemoStepUpdating] = useState(false);
  const [demoExiting, setDemoExiting] = useState(false);
  const [demoError, setDemoError] = useState<string | null>(null);
  const [demoGuideDismissed, setDemoGuideDismissed] = useLocalStorage<boolean>('soyog.demo.guide.dismissed', false);
  const [hasExportedCitations, setHasExportedCitations] = useState(false);
  const feedSentinelRef = useRef<HTMLDivElement | null>(null);
  const demoAutoStartRef = useRef(false);

  const workspaceTemplates: WorkspaceTemplate[] = [
    {
      name: 'Literature Review Sprint',
      description: 'Track papers, notes, and synthesis for a structured literature review.',
    },
    {
      name: 'Model Benchmarking',
      description: 'Collect papers, datasets, and evaluation notes for comparing approaches.',
    },
    {
      name: 'Grant Discovery',
      description: 'Capture prior work, evidence gaps, and promising angles for proposal building.',
    },
  ];

  const quickLaunches = [
    {
      title: 'Search papers',
      desc: 'Probe the search fabric and start a fresh evidence trail.',
      to: '/search',
      icon: Search,
      tone: 'from-indigo-500 to-cyan-500',
    },
    {
      title: 'Research agent',
      desc: 'Use AI when you already know the question but need synthesis fast.',
      to: '/research-agent',
      icon: Bot,
      tone: 'from-sky-500 to-blue-600',
    },
    {
      title: 'Upload PDF',
      desc: 'Bring private documents into the same project context.',
      to: '/upload',
      icon: Upload,
      tone: 'from-emerald-500 to-teal-600',
    },
    {
      title: 'Mindmap review',
      desc: 'Convert imported evidence into a navigable review structure.',
      to: '/mindmap',
      icon: Workflow,
      tone: 'from-fuchsia-500 to-violet-600',
    },
  ];

  const parseApiError = useCallback((err: unknown, fallback: string) => {
    return apiErrorMessage(err, fallback);
  }, []);

  const fetchOnboardingStatus = useCallback(
    async (workspaceId?: number | null) => {
      setOnboardingLoading(true);
      setOnboardingError(null);
      try {
        const response = await api.get<OnboardingStatusResponse>('/onboarding/status', {
          params: workspaceId ? { workspace_id: workspaceId } : undefined,
        });
        setOnboarding(response.data);
      } catch (err) {
        setOnboardingError(parseApiError(err, 'Failed to load onboarding state.'));
      } finally {
        setOnboardingLoading(false);
      }
    },
    [parseApiError]
  );

  const fetchDemoState = useCallback(
    async (workspaceId?: number | null) => {
      setDemoStateLoading(true);
      setDemoError(null);
      try {
        const response = await api.get<DemoModeStateResponse>('/demo/state', {
          params: workspaceId ? { workspace_id: workspaceId } : undefined,
        });
        setDemoState(response.data);
      } catch (err) {
        setDemoError(parseApiError(err, 'Failed to load demo mode state.'));
      } finally {
        setDemoStateLoading(false);
      }
    },
    [parseApiError]
  );

  const fetchWorkspaceInsights = useCallback(async (workspaceId: number, refresh = false) => {
    if (!workspaceId) {
      setInsights(null);
      return;
    }
    if (refresh) {
      setInsightsRefreshing(true);
    } else {
      setInsightsLoading(true);
    }
    setInsightsError(null);
    try {
      const response = refresh
        ? await api.post<WorkspaceInsightsResponse>(`/workspace-insights/${workspaceId}/refresh?run_inline=false`)
        : await api.get<WorkspaceInsightsResponse>(`/workspace-insights/${workspaceId}?run_inline=false`);
      const payload = response.data;
      setInsights(payload);
      if (
        String(payload.status || '').toLowerCase() === 'failed' &&
        !payload.payload?.key_themes?.length &&
        !payload.payload?.important_findings?.length
      ) {
        setInsightsError(payload.error || 'Insights are temporarily unavailable. Please retry in a moment.');
      }
    } catch (err) {
      setInsightsError(parseApiError(err, 'Failed to load workspace insights.'));
    } finally {
      if (refresh) {
        setInsightsRefreshing(false);
      } else {
        setInsightsLoading(false);
      }
    }
  }, [parseApiError]);

  const fetchWorkspaceFeed = useCallback(
    async (
      workspaceId: number,
      options: { refresh?: boolean; append?: boolean; cursor?: string | null } = {}
    ) => {
      if (!workspaceId) {
        setFeedItems([]);
        setFeedCursor(null);
        setFeedHasMore(false);
        return;
      }
      const refresh = Boolean(options.refresh);
      const append = Boolean(options.append);
      const cursor = options.cursor ?? null;
      if (refresh) {
        setFeedRefreshing(true);
      } else if (append) {
        setFeedLoadingMore(true);
      } else {
        setFeedLoading(true);
      }
      setFeedError(null);
      try {
        const response = refresh
          ? await api.post<WorkspaceFeedResponse>(`/workspace-feed/${workspaceId}/refresh`, null, {
              params: {
                sort: feedSort,
                limit: 12,
                cursor,
                include_read: true,
                run_inline: false,
              },
            })
          : await api.get<WorkspaceFeedResponse>(`/workspace-feed/${workspaceId}`, {
              params: {
                sort: feedSort,
                limit: 12,
                cursor,
                include_read: true,
                run_inline: false,
              },
            });
        const payload = response.data;
        setFeedDisclaimer(
          payload.disclaimer ||
            'Feed items are AI-assisted signals from your workspace evidence. Always validate by opening linked source papers.'
        );
        setFeedUnreadCount(Number(payload.unread_count || 0));
        setFeedCursor(payload.next_cursor || null);
        setFeedHasMore(Boolean(payload.next_cursor));
        setFeedItems((prev) => {
          if (!append) {
            return payload.items || [];
          }
          const existing = new Map(prev.map((item) => [item.feed_item_id, item]));
          for (const item of payload.items || []) {
            existing.set(item.feed_item_id, item);
          }
          return Array.from(existing.values());
        });
        if (
          String(payload.status || '').toLowerCase() === 'failed' &&
          !(payload.items || []).length &&
          !append
        ) {
          setFeedError(payload.error || 'Feed is temporarily unavailable. Please retry in a moment.');
        }
      } catch (err) {
        setFeedError(parseApiError(err, 'Failed to load workspace feed.'));
      } finally {
        if (refresh) {
          setFeedRefreshing(false);
        } else if (append) {
          setFeedLoadingMore(false);
        } else {
          setFeedLoading(false);
        }
      }
    },
    [feedSort, parseApiError]
  );

  const handleFeedRefresh = useCallback(async () => {
    if (!activeInsightsWorkspaceId) return;
    await fetchWorkspaceFeed(activeInsightsWorkspaceId, { refresh: true, append: false, cursor: null });
  }, [activeInsightsWorkspaceId, fetchWorkspaceFeed]);

  const handleMarkFeedRead = useCallback(
    async (item: WorkspaceFeedItem, read: boolean) => {
      if (!activeInsightsWorkspaceId) return;
      try {
        const response = await api.post<WorkspaceFeedItem>(
          `/workspace-feed/${activeInsightsWorkspaceId}/items/${item.feed_item_id}/read`,
          { read }
        );
        const updated = response.data;
        setFeedItems((prev) => prev.map((current) => (current.feed_item_id === updated.feed_item_id ? updated : current)));
        setFeedUnreadCount((prev) => Math.max(0, prev + (updated.read ? -1 : 1)));
      } catch (err) {
        setFeedError(parseApiError(err, 'Failed to update feed item state.'));
      }
    },
    [activeInsightsWorkspaceId, parseApiError]
  );

  const handleDemoBootstrap = useCallback(async () => {
    const targetWorkspaceId = onboarding?.workspace_id || activeInsightsWorkspaceId || workspaces[0]?.id || null;
    setDemoBootstrapping(true);
    setDemoError(null);
    try {
      const response = await api.post<DemoModeStateResponse>('/demo/start', {
        workspace_id: targetWorkspaceId || undefined,
      });
      const payload = response.data;
      setDemoState(payload);
      setDemoGuideDismissed(false);
      if (payload.workspace_id) {
        setActiveInsightsWorkspaceId(payload.workspace_id);
        await fetchOnboardingStatus(payload.workspace_id);
        await fetchWorkspaceInsights(payload.workspace_id, true);
        await fetchWorkspaceFeed(payload.workspace_id, { refresh: true, append: false, cursor: null });
      }
      await fetchWorkspaces();
    } catch (err) {
      setDemoError(parseApiError(err, 'Failed to start demo mode.'));
    } finally {
      setDemoBootstrapping(false);
    }
  }, [
    activeInsightsWorkspaceId,
    fetchOnboardingStatus,
    fetchWorkspaceFeed,
    onboarding?.workspace_id,
    setDemoGuideDismissed,
    workspaces,
    fetchWorkspaceInsights,
    fetchWorkspaces,
    parseApiError,
  ]);

  const handleDemoStepComplete = useCallback(
    async (stepId?: string | null) => {
      const targetWorkspaceId = demoState?.workspace_id || onboarding?.workspace_id || activeInsightsWorkspaceId || workspaces[0]?.id || null;
      const cleanStepId = String(stepId || '').trim();
      if (!targetWorkspaceId || !cleanStepId) return;
      setDemoStepUpdating(true);
      setDemoError(null);
      try {
        const response = await api.post<DemoModeStateResponse>('/demo/steps/complete', {
          workspace_id: targetWorkspaceId,
          step_id: cleanStepId,
        });
        setDemoState(response.data);
      } catch (err) {
        setDemoError(parseApiError(err, 'Failed to update demo step.'));
      } finally {
        setDemoStepUpdating(false);
      }
    },
    [activeInsightsWorkspaceId, demoState?.workspace_id, onboarding?.workspace_id, parseApiError, workspaces]
  );

  const handleDemoStepAdvance = useCallback(async () => {
    const targetWorkspaceId = demoState?.workspace_id || onboarding?.workspace_id || activeInsightsWorkspaceId || workspaces[0]?.id || null;
    if (!targetWorkspaceId) return;
    setDemoStepUpdating(true);
    setDemoError(null);
    try {
      const response = await api.post<DemoModeStateResponse>('/demo/steps/next', {
        workspace_id: targetWorkspaceId,
      });
      setDemoState(response.data);
    } catch (err) {
      setDemoError(parseApiError(err, 'Failed to advance demo step.'));
    } finally {
      setDemoStepUpdating(false);
    }
  }, [activeInsightsWorkspaceId, demoState?.workspace_id, onboarding?.workspace_id, parseApiError, workspaces]);

  const handleExitDemoMode = useCallback(async () => {
    const targetWorkspaceId = demoState?.workspace_id || onboarding?.workspace_id || activeInsightsWorkspaceId || workspaces[0]?.id || null;
    setDemoExiting(true);
    setDemoError(null);
    try {
      const response = await api.post<DemoModeStateResponse>('/demo/exit', {
        workspace_id: targetWorkspaceId || undefined,
      });
      setDemoState(response.data);
      setDemoGuideDismissed(true);
      await fetchOnboardingStatus(response.data.workspace_id || targetWorkspaceId);
    } catch (err) {
      setDemoError(parseApiError(err, 'Failed to exit demo mode.'));
    } finally {
      setDemoExiting(false);
    }
  }, [
    activeInsightsWorkspaceId,
    demoState?.workspace_id,
    fetchOnboardingStatus,
    onboarding?.workspace_id,
    parseApiError,
    setDemoGuideDismissed,
    workspaces,
  ]);

  useEffect(() => {
    void fetchWorkspaces();
  }, [fetchWorkspaces]);

  useEffect(() => {
    if (workspaces.length === 0) {
      setActiveInsightsWorkspaceId(null);
      setInsights(null);
      return;
    }
    setActiveInsightsWorkspaceId((prev) => {
      if (prev && workspaces.some((workspace) => workspace.id === prev)) {
        return prev;
      }
      return workspaces[0].id;
    });
  }, [workspaces]);

  useEffect(() => {
    if (workspaces.length === 0) {
      return;
    }
    const workspaceIdParam = Number(new URLSearchParams(location.search).get('workspace_id') || 0);
    if (!workspaceIdParam || !workspaces.some((workspace) => workspace.id === workspaceIdParam)) {
      return;
    }
    setActiveInsightsWorkspaceId(workspaceIdParam);
  }, [location.search, workspaces]);

  useEffect(() => {
    if (!activeInsightsWorkspaceId) {
      setInsights(null);
      return;
    }
    void fetchWorkspaceInsights(activeInsightsWorkspaceId, false);
  }, [activeInsightsWorkspaceId, fetchWorkspaceInsights]);

  useEffect(() => {
    if (loading) {
      return;
    }
    const targetWorkspaceId = activeInsightsWorkspaceId || workspaces[0]?.id || null;
    void fetchOnboardingStatus(targetWorkspaceId);
  }, [activeInsightsWorkspaceId, fetchOnboardingStatus, loading, workspaces]);

  useEffect(() => {
    if (loading) {
      return;
    }
    const targetWorkspaceId = activeInsightsWorkspaceId || workspaces[0]?.id || null;
    void fetchDemoState(targetWorkspaceId);
  }, [activeInsightsWorkspaceId, fetchDemoState, loading, workspaces]);

  useEffect(() => {
    if (loading || demoBootstrapping) {
      return;
    }
    const queryParams = new URLSearchParams(location.search);
    const demoRequested = queryParams.get('demo') === '1';
    if (!demoRequested || demoAutoStartRef.current || demoState?.is_demo_mode) {
      return;
    }
    demoAutoStartRef.current = true;
    void handleDemoBootstrap();
  }, [demoBootstrapping, demoState?.is_demo_mode, handleDemoBootstrap, loading, location.search]);

  useEffect(() => {
    if (!activeInsightsWorkspaceId) {
      setFeedItems([]);
      setFeedCursor(null);
      setFeedHasMore(false);
      return;
    }
    void fetchWorkspaceFeed(activeInsightsWorkspaceId, {
      refresh: false,
      append: false,
      cursor: null,
    });
  }, [activeInsightsWorkspaceId, feedSort, fetchWorkspaceFeed]);

  useEffect(() => {
    if (!feedHasMore || feedLoading || feedLoadingMore || feedRefreshing) {
      return;
    }
    const target = feedSentinelRef.current;
    if (!target || !activeInsightsWorkspaceId) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        if (!entry.isIntersecting) {
          return;
        }
        if (!feedCursor || feedLoadingMore) {
          return;
        }
        void fetchWorkspaceFeed(activeInsightsWorkspaceId, {
          append: true,
          cursor: feedCursor,
        });
      },
      { rootMargin: '220px' }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [
    activeInsightsWorkspaceId,
    feedCursor,
    feedHasMore,
    feedLoading,
    feedLoadingMore,
    feedRefreshing,
    fetchWorkspaceFeed,
  ]);

  const insightSourceMap = useMemo(() => {
    const map = new Map<number, WorkspaceInsightSource>();
    (insights?.sources || []).forEach((source) => {
      if (source.source_index > 0) {
        map.set(source.source_index, source);
      }
    });
    return map;
  }, [insights]);

  const insightSections: Array<{
    key: keyof WorkspaceInsightsPayload;
    title: string;
    icon: typeof BrainCircuit;
    accent: string;
    empty: string;
  }> = [
    {
      key: 'key_themes',
      title: 'Key Themes',
      icon: BrainCircuit,
      accent: 'text-indigo-700 bg-indigo-50 border-indigo-100',
      empty: 'Add more summaries and reports to strengthen thematic signal.',
    },
    {
      key: 'emerging_trends',
      title: 'Trends',
      icon: TrendingUp,
      accent: 'text-cyan-700 bg-cyan-50 border-cyan-100',
      empty: 'Not enough trend momentum yet across the indexed corpus.',
    },
    {
      key: 'contradictions',
      title: 'Contradictions',
      icon: AlertTriangle,
      accent: 'text-amber-700 bg-amber-50 border-amber-100',
      empty: 'No strong contradiction detected in current evidence set.',
    },
    {
      key: 'research_gaps',
      title: 'Gaps',
      icon: BookMarked,
      accent: 'text-rose-700 bg-rose-50 border-rose-100',
      empty: 'Current evidence does not expose clear research gaps yet.',
    },
    {
      key: 'recommended_next_steps',
      title: 'Suggestions',
      icon: Compass,
      accent: 'text-emerald-700 bg-emerald-50 border-emerald-100',
      empty: 'No high-confidence recommendation available yet.',
    },
  ];

  const handleInsightsRefresh = async () => {
    if (!activeInsightsWorkspaceId) return;
    await fetchWorkspaceInsights(activeInsightsWorkspaceId, true);
  };

  const feedBadgeClass = (feedType: string): string => {
    if (feedType === 'contradiction') {
      return 'border-amber-200 bg-amber-50 text-amber-800';
    }
    if (feedType === 'trend') {
      return 'border-cyan-200 bg-cyan-50 text-cyan-800';
    }
    return 'border-emerald-200 bg-emerald-50 text-emerald-800';
  };

  const feedActionHref = (item: WorkspaceFeedItem): string => {
    if (!activeInsightsWorkspaceId) {
      return '/dashboard';
    }
    if ((item.related_papers || []).length >= 2) {
      return `/compare?ids=${item.related_papers.slice(0, 5).join(',')}&workspace_id=${activeInsightsWorkspaceId}`;
    }
    return `/workspace/${activeInsightsWorkspaceId}`;
  };

  const feedActionLabel = (item: WorkspaceFeedItem): string => {
    if ((item.related_papers || []).length >= 2) {
      return 'Compare papers';
    }
    return 'Open workspace';
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await api.post('/workspaces/', { name: newName.trim(), description: newDesc.trim() });
      setNewName('');
      setNewDesc('');
      setShowCreate(false);
      await fetchWorkspaces();
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/workspaces/${id}`);
      setDeleteId(null);
      await fetchWorkspaces();
    } catch {
      // keep silent on delete failure
    }
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-';
    try {
      return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return '-';
    }
  };

  const formatNum = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));

  const stats = [
    {
      label: 'Workspaces',
      value: workspaces.length,
      icon: Folder,
      iconClass: 'bg-indigo-100/70 text-indigo-600',
    },
    {
      label: 'Papers Imported',
      value: totalPapers,
      icon: FileText,
      iconClass: 'bg-sky-100/70 text-sky-600',
    },
    {
      label: 'Indexed Characters',
      value: formatNum(totalChars),
      icon: Database,
      iconClass: 'bg-violet-100/70 text-violet-600',
    },
    {
      label: 'AI Context',
      value: 'Ready',
      icon: BrainCircuit,
      iconClass: 'bg-teal-100/70 text-teal-700',
    },
  ];

  const onboardingPrompts = (onboarding?.copilot_prompts || []).slice(0, 6);
  const demoFeedPreview = onboarding?.demo?.sample_feed_items || [];
  const hasCompletedSearch = Boolean(workspaces.length > 0 || totalPapers > 0);
  const hasUploadedPaper = Boolean(totalPapers > 0 || onboarding?.completed_steps?.includes('upload_paper'));
  const hasCompletedPaperCheck = Boolean(
    onboarding?.completed_steps?.some((step) => ['explain_paper', 'compare_papers', 'generate_report'].includes(step)) || totalPapers > 0
  );
  const gettingStartedItems = [
    {
      key: 'createWorkspace',
      label: 'Create Workspace',
      completed: isUserCreatedWorkspace,
      actionLabel: 'Create Workspace',
      action: (
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-1 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100"
        >
          Create Workspace
          <ArrowRight className="h-3.5 w-3.5" />
        </button>
      ),
    },
    {
      key: 'searchPapers',
      label: 'Search Papers',
      completed: hasCompletedSearch,
      actionLabel: 'Search Papers',
      to: '/search',
    },
    {
      key: 'uploadPdf',
      label: 'Upload PDF',
      completed: hasUploadedPaper,
      actionLabel: 'Upload PDF',
      to: '/upload',
    },
    {
      key: 'runPaperCheck',
      label: 'Run Paper Check',
      completed: hasCompletedPaperCheck,
      actionLabel: 'Run Paper Check',
      to: '/upload',
    },
    {
      key: 'exportCitations',
      label: 'Export Citations',
      completed: hasExportedCitations,
      actionLabel: 'Export Citations',
      to: activeInsightsWorkspaceId ? `/workspace/${activeInsightsWorkspaceId}` : '/dashboard#workspaces',
    },
  ];
  const gettingStartedCompletedCount = gettingStartedItems.filter((item) => item.completed).length;
  const demoRequestedFromUrl = useMemo(() => new URLSearchParams(location.search).get('demo') === '1', [location.search]);
  const currentDemoStep = useMemo(() => {
    if (!demoState?.steps?.length) return null;
    return (
      demoState.steps.find((step) => step.active) ||
      demoState.steps.find((step) => step.id === demoState.current_step) ||
      demoState.steps.find((step) => !step.completed) ||
      demoState.steps[0]
    );
  }, [demoState]);
  const isDemoMode = Boolean(demoState?.is_demo_mode);
  const demoProgressPct = Math.round(Math.max(0, Math.min(1, Number(demoState?.progress || 0))) * 100);
  const demoTargetKey = currentDemoStep?.target_key || '';
  const showDemoGuide =
    Boolean(demoState?.steps?.length) && (isDemoMode || demoRequestedFromUrl || !demoGuideDismissed);
  const highlightForDemoTarget = (targetKey: string): string =>
    isDemoMode && demoTargetKey === targetKey
      ? 'ring-2 ring-indigo-300 ring-offset-2 ring-offset-slate-100'
      : '';
  const demoTooltipTextForTarget = (targetKey: string): string =>
    isDemoMode && demoTargetKey === targetKey ? currentDemoStep?.tooltip || '' : '';

  const handleExportWorkspace = async (id: number, name: string, format: 'bibtex' | 'csv') => {
    try {
      const res = await api.get(`/workspaces/${id}/export?format=${format}`, { responseType: 'blob' });
      const blob = new Blob([res.data], { type: format === 'csv' ? 'text/csv' : 'application/x-bibtex' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = format === 'csv' ? 'csv' : 'bib';
      a.download = `${name.replace(/\s+/g, '_')}.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      setHasExportedCitations(true);
    } catch {
      // keep silent on export failure
    }
  };

  return (
    <Layout>
      <section className="dashboard-hero mb-6">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-cyan-200 mb-2 flex items-center gap-2">
            <Sparkles className="h-3.5 w-3.5" /> Control Plane
          </p>
          <h2 className="text-3xl md:text-4xl font-bold text-white">Workspace Intelligence Dashboard</h2>
          <p className="text-cyan-100/90 mt-2 text-sm md:text-base">
            Create project spaces, orchestrate imports, and monitor research throughput in one place.
          </p>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2 md:mt-0">
          <button
            onClick={() => {
              if (isDemoMode) {
                void handleExitDemoMode();
              } else {
                void handleDemoBootstrap();
              }
            }}
            disabled={demoBootstrapping || demoExiting}
            className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-200 bg-white/10 px-3 py-2 text-xs font-semibold text-cyan-50 hover:bg-white/20 disabled:opacity-60"
          >
            {isDemoMode ? <XCircle className="h-3.5 w-3.5" /> : <PlayCircle className="h-3.5 w-3.5" />}
            {isDemoMode ? (demoExiting ? 'Exiting demo...' : 'Exit demo') : demoBootstrapping ? 'Starting demo...' : 'Try demo'}
          </button>
          <button onClick={() => setShowCreate(true)} className="hero-btn-primary">
            <Plus className="h-4 w-4" /> New Workspace
          </button>
        </div>
      </section>

      {showDemoGuide ? (
        <section className={`mb-4 rounded-2xl border border-indigo-200 bg-gradient-to-br from-indigo-50 via-cyan-50 to-white p-4 ${highlightForDemoTarget('demo_panel')}`}>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-700">Demo Story</p>
              <h3 className="mt-1 text-xl font-bold text-slate-900">
                {demoState?.scenario_title || 'Guided Product Narrative'}
              </h3>
              <p className="mt-1 text-sm text-slate-700">
                {demoState?.story_intro ||
                  'Walk through explain, compare, report, insights, and copilot in one connected scenario.'}
              </p>
              {currentDemoStep ? (
                <div className="mt-3 rounded-xl border border-indigo-100 bg-white/80 px-3 py-2.5">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Current Step</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">
                    {currentDemoStep.index}. {currentDemoStep.title}
                  </p>
                  <p className="mt-1 text-sm text-slate-700">{currentDemoStep.what_happening}</p>
                  <p className="mt-1 text-xs text-slate-600">Why it matters: {currentDemoStep.why_matters}</p>
                </div>
              ) : null}
            </div>
            <div className="w-full max-w-sm rounded-xl border border-indigo-100 bg-white/90 p-3">
              <div className="flex items-center justify-between gap-2 text-xs">
                <span className="font-semibold uppercase tracking-[0.16em] text-slate-500">Progress</span>
                <span className="font-semibold text-slate-700">{demoProgressPct}%</span>
              </div>
              <progress
                className="mt-2 h-2 w-full overflow-hidden rounded-full"
                max={100}
                value={demoProgressPct}
                aria-label="Demo progress"
              />
              <div className="mt-3 grid grid-cols-5 gap-1.5">
                {(demoState?.steps || []).map((step) => (
                  <button
                    key={`demo-step-${step.id}`}
                    type="button"
                    title={`${step.index}. ${step.title}`}
                    onClick={() => {
                      void handleDemoStepComplete(step.id);
                    }}
                    disabled={demoStepUpdating || !isDemoMode}
                    className={`inline-flex h-8 items-center justify-center rounded-lg border text-xs font-semibold transition-colors ${
                      step.completed
                        ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                        : step.active
                        ? 'border-indigo-300 bg-indigo-50 text-indigo-700'
                        : 'border-slate-200 bg-white text-slate-500'
                    }`}
                  >
                    {step.completed ? <Check className="h-3.5 w-3.5" /> : step.index}
                  </button>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {isDemoMode && currentDemoStep ? (
                  <Link
                    to={currentDemoStep.action_path || '/dashboard'}
                    className={`inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 ${
                      highlightForDemoTarget(currentDemoStep.target_key || '')
                    }`}
                  >
                    <WandSparkles className="h-3.5 w-3.5" />
                    {currentDemoStep.action_label || 'Open step'}
                  </Link>
                ) : (
                  <button
                    type="button"
                    onClick={() => {
                      void handleDemoBootstrap();
                    }}
                    disabled={demoBootstrapping}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
                  >
                    {demoBootstrapping ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <PlayCircle className="h-3.5 w-3.5" />}
                    {demoBootstrapping ? 'Starting demo...' : 'Start guided demo'}
                  </button>
                )}
                {isDemoMode ? (
                  <>
                    <button
                      type="button"
                      onClick={() => {
                        void handleDemoStepComplete(currentDemoStep?.id);
                      }}
                      disabled={demoStepUpdating || !currentDemoStep}
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                    >
                      {demoStepUpdating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                      Mark done
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        void handleDemoStepAdvance();
                      }}
                      disabled={demoStepUpdating}
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                    >
                      <ArrowRight className="h-3.5 w-3.5" />
                      Next step
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        void handleExitDemoMode();
                      }}
                      disabled={demoExiting}
                      className="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-60"
                    >
                      {demoExiting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <XCircle className="h-3.5 w-3.5" />}
                      Exit demo
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    onClick={() => setDemoGuideDismissed(true)}
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    Hide guide
                  </button>
                )}
              </div>
            </div>
          </div>
        </section>
      ) : null}

      {onboardingError ? (
        <section className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {onboardingError}
        </section>
      ) : null}

      {demoError ? (
        <section className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {demoError}
        </section>
      ) : null}

      {demoStateLoading ? (
        <section className="mb-4 flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading demo state...
        </section>
      ) : null}

      {onboardingLoading ? (
        <section className="mb-4 flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading onboarding guide...
        </section>
      ) : null}

      <section className="mb-6 feature-surface">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">ResearchHub Getting Started</p>
            <h3 className="mt-1 text-xl font-bold text-slate-900">First research workflow</h3>
            <p className="mt-1 text-sm text-slate-600">Complete these actions to learn the core platform flow.</p>
          </div>
          <span className="inline-flex w-fit items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-700">
            Completed {gettingStartedCompletedCount} / {gettingStartedItems.length}
          </span>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
          {gettingStartedItems.map((item) => (
            <article key={item.key} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between gap-2">
                <div
                  className={`inline-flex h-7 w-7 items-center justify-center rounded-full border ${
                    item.completed ? 'border-emerald-200 bg-emerald-50' : 'border-slate-200 bg-slate-50'
                  }`}
                >
                  {item.completed ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <Circle className="h-4 w-4 text-slate-400" />
                  )}
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                    item.completed
                      ? 'border border-emerald-200 bg-emerald-50 text-emerald-700'
                      : 'border border-slate-200 bg-slate-50 text-slate-600'
                  }`}
                >
                  {item.completed ? 'Done' : 'Next'}
                </span>
              </div>
              <h4 className="mt-3 text-sm font-semibold text-slate-900">{item.label}</h4>
              {!item.completed && (
                <div className="mt-3">
                  {item.action || (
                    <Link
                      to={item.to || '/dashboard'}
                      className="inline-flex items-center gap-1 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100"
                    >
                      {item.actionLabel}
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  )}
                </div>
              )}
            </article>
          ))}
        </div>
      </section>


      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 mb-6 md:mb-7">
        {stats.map((s) => {
          const Icon = s.icon;
          return (
            <div key={s.label} className="stat-tile">
              <div className={`stat-icon ${s.iconClass}`}>
                <Icon className="h-4 w-4 md:h-5 md:w-5" />
              </div>
              <p className="stat-label">{s.label}</p>
              <p className="stat-value">{loading ? '-' : s.value}</p>
            </div>
          );
        })}
      </section>

      <section id="copilot" className={`mb-6 rounded-2xl ${highlightForDemoTarget('copilot')}`}>
        {demoTooltipTextForTarget('copilot') ? (
          <div className="mb-2 inline-flex items-center gap-1 rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-[11px] font-semibold text-indigo-700">
            <Lightbulb className="h-3.5 w-3.5" /> {demoTooltipTextForTarget('copilot')}
          </div>
        ) : null}
        <UnifiedCopilotPanel
          workspaceId={activeInsightsWorkspaceId ?? workspaces[0]?.id ?? null}
          initialQuery="What are the main trends in my workspace?"
          heading="AI Copilot"
          subheading="Single entrypoint for explain, compare, report, insights, and grounded workspace answers."
          suggestedPrompts={onboardingPrompts}
        />
      </section>

      <section className="mb-6 grid grid-cols-1 gap-4 xl:grid-cols-[0.95fr,1.05fr]">
        <div className="feature-surface">
          <p className="mb-1 text-xs uppercase tracking-[0.2em] text-slate-500">Workspace operating model</p>
          <h3 className="text-xl font-bold text-slate-900">Keep each project as a contained evidence loop</h3>
          <div className="mt-4 grid gap-3">
            {[
              'Start with one workspace per real research question, not one workspace per paper.',
              'Import only the sources you are willing to cite or synthesize in downstream AI steps.',
              'Use exports and mindmaps after the workspace has enough high-signal material to justify synthesis.',
            ].map((item, index) => (
              <div key={item} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-indigo-600">Rule {index + 1}</p>
                <p className="mt-1 text-sm leading-relaxed text-slate-600">{item}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {quickLaunches.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.title}
                to={item.to}
                className="group rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition-transform duration-150 hover:-translate-y-1 hover:shadow-lg"
              >
                <div className={`inline-flex rounded-2xl bg-gradient-to-br ${item.tone} p-2.5 text-white shadow-md`}>
                  <Icon className="h-5 w-5" />
                </div>
                <h4 className="mt-4 text-base font-semibold text-slate-900">{item.title}</h4>
                <p className="mt-1 text-sm leading-relaxed text-slate-600">{item.desc}</p>
                <span className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-slate-700">
                  Open <ArrowRight className="h-3.5 w-3.5 transition-transform duration-150 group-hover:translate-x-0.5" />
                </span>
              </Link>
            );
          })}
        </div>
      </section>

      <section id="insights" className={`mb-6 feature-surface ${highlightForDemoTarget('insights')}`}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Auto Insights</p>
            <h3 className="text-xl font-bold text-slate-900">Workspace signal feed</h3>
            <p className="mt-1 text-sm text-slate-600">
              Proactive themes, contradictions, gaps, and suggested next moves powered by your indexed workspace context.
            </p>
            {demoTooltipTextForTarget('insights') ? (
              <p className="mt-2 inline-flex items-center gap-1 rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-[11px] font-semibold text-indigo-700">
                <Lightbulb className="h-3.5 w-3.5" /> {demoTooltipTextForTarget('insights')}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {workspaces.length > 1 && (
              <select
                aria-label="Insights workspace"
                title="Insights workspace"
                value={activeInsightsWorkspaceId ?? ''}
                onChange={(event) => setActiveInsightsWorkspaceId(Number(event.target.value) || null)}
                className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
              >
                {workspaces.map((workspace) => (
                  <option key={workspace.id} value={workspace.id}>
                    {workspace.name}
                  </option>
                ))}
              </select>
            )}
            <button
              onClick={handleInsightsRefresh}
              disabled={!activeInsightsWorkspaceId || insightsRefreshing}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              {insightsRefreshing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ArrowUpRight className="h-3.5 w-3.5" />} Refresh
            </button>
          </div>
        </div>

        {insightsLoading ? (
          <div className="mt-4 flex items-center gap-2 text-sm text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" /> Building workspace insights...
          </div>
        ) : insightsError ? (
          <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{insightsError}</div>
        ) : !activeInsightsWorkspaceId ? (
          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            Select a workspace to generate insights.
          </div>
        ) : (
          <>
            <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
              {insightSections.map((section) => {
                const Icon = section.icon;
                const items = (insights?.payload?.[section.key] || []) as WorkspaceInsightItem[];
                return (
                  <article key={section.key} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                    <div className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${section.accent}`}>
                      <Icon className="h-3.5 w-3.5" /> {section.title}
                    </div>
                    {items.length === 0 ? (
                      <p className="mt-3 text-sm text-slate-500">{section.empty}</p>
                    ) : (
                      <div className="mt-3 space-y-3">
                        {items.map((item, index) => (
                          <div key={`${section.key}-${index}`} className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5">
                            <p className="text-sm leading-relaxed text-slate-700">{item.text}</p>
                            {item.source_refs.length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-2">
                                {item.source_refs.map((sourceRef) => {
                                  const source = insightSourceMap.get(sourceRef);
                                  const sourceLabel = source?.title || `Source ${sourceRef}`;
                                  const clipped = sourceLabel.length > 46 ? `${sourceLabel.slice(0, 46)}...` : sourceLabel;
                                  return (
                                    <Link
                                      key={`${section.key}-${index}-${sourceRef}`}
                                      to={activeInsightsWorkspaceId ? `/workspace/${activeInsightsWorkspaceId}` : '#'}
                                      className="inline-flex items-center rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700 hover:bg-indigo-100"
                                      title={source ? `${source.title} (${source.source_type})` : `Source ${sourceRef}`}
                                    >
                                      S{sourceRef}: {clipped}
                                    </Link>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>

            <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Safety</p>
              <p className="mt-1 text-sm text-slate-600">
                {insights?.disclaimer || 'Insights are advisory and should be validated against source papers.'}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-500">
                <span>Confidence: {((insights?.confidence || 0) * 100).toFixed(1)}%</span>
                <span>Generated: {formatDate(insights?.generated_at || undefined)}</span>
                {insights?.job_status ? <span>Job: {insights.job_status}</span> : null}
              </div>
            </div>
          </>
        )}
      </section>

      <section className="mb-6 feature-surface">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Daily Intelligence Feed</p>
            <h3 className="text-xl font-bold text-slate-900">Your Research Feed</h3>
            <p className="mt-1 text-sm text-slate-600">
              Fresh trends, contradictions, recommendations, and alerts generated from your evolving workspace evidence.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-semibold text-slate-600">
              <BellRing className="h-3.5 w-3.5" /> {feedUnreadCount} unread
            </span>
            <select
              aria-label="Feed sort order"
              title="Feed sort order"
              value={feedSort}
              onChange={(event) => setFeedSort(event.target.value as 'importance' | 'recent')}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700"
            >
              <option value="importance">Sort: Importance</option>
              <option value="recent">Sort: Recent</option>
            </select>
            <button
              onClick={() => {
                void handleFeedRefresh();
              }}
              disabled={!activeInsightsWorkspaceId || feedRefreshing}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              {feedRefreshing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ArrowUpRight className="h-3.5 w-3.5" />} Refresh
            </button>
          </div>
        </div>

        {feedLoading ? (
          <div className="mt-4 flex items-center gap-2 text-sm text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" /> Building your daily feed...
          </div>
        ) : feedError ? (
          <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{feedError}</div>
        ) : feedItems.length === 0 ? (
          demoFeedPreview.length > 0 && Number(onboarding?.paper_count || 0) === 0 ? (
            <div className="mt-4 space-y-3">
              {demoFeedPreview.map((item) => (
                <article key={item.title} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${feedBadgeClass(item.type)}`}>
                      Demo {item.type}
                    </span>
                    <span className="text-[11px] font-semibold text-slate-500">
                      Importance {(Math.max(0, Math.min(1, item.importance_score || 0)) * 100).toFixed(0)}%
                    </span>
                  </div>
                  <h4 className="mt-1 text-base font-semibold text-slate-900">{item.title}</h4>
                  <p className="mt-2 text-sm text-slate-700">{item.description}</p>
                </article>
              ))}
              <div className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-800">
                Demo feed preview is shown because this workspace has no papers yet. Load demo mode or upload a paper to switch to live intelligence.
              </div>
            </div>
          ) : (
            <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              No feed items yet. Add more papers or refresh to generate new intelligence.
            </div>
          )
        ) : (
          <>
            <div className="mt-4 space-y-3">
              {feedItems.map((item) => (
                <article key={item.feed_item_id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${feedBadgeClass(item.type)}`}>
                          {item.type}
                        </span>
                        {!item.read ? (
                          <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">
                            New
                          </span>
                        ) : null}
                        <span className="text-[11px] font-semibold text-slate-500">
                          Importance {(Math.max(0, Math.min(1, item.importance_score || 0)) * 100).toFixed(0)}%
                        </span>
                      </div>
                      <h4 className="mt-1 text-base font-semibold text-slate-900">{item.title}</h4>
                    </div>
                    <button
                      onClick={() => {
                        void handleMarkFeedRead(item, !item.read);
                      }}
                      className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold text-slate-700 hover:bg-slate-100"
                    >
                      <CheckCheck className="h-3.5 w-3.5" />
                      {item.read ? 'Mark unread' : 'Mark read'}
                    </button>
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-slate-700">{item.description}</p>

                  {item.related_papers.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {item.related_papers.slice(0, 4).map((paperId) => (
                        <Link
                          key={`${item.feed_item_id}-paper-${paperId}`}
                          to={activeInsightsWorkspaceId ? `/workspace/${activeInsightsWorkspaceId}` : '#'}
                          className="inline-flex items-center rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-0.5 text-[11px] font-semibold text-indigo-700 hover:bg-indigo-100"
                        >
                          Paper {paperId}
                        </Link>
                      ))}
                    </div>
                  )}

                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    {item.sources.slice(0, 3).map((source) => {
                      const sourceUrl = source.url || (source.doi ? `https://doi.org/${source.doi}` : '');
                      return sourceUrl ? (
                        <a
                          key={`${item.feed_item_id}-source-${source.source_index}`}
                          href={sourceUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center rounded-full border border-cyan-200 bg-cyan-50 px-2.5 py-0.5 text-[11px] font-semibold text-cyan-700 hover:bg-cyan-100"
                        >
                          Source {source.source_index}
                        </a>
                      ) : (
                        <span
                          key={`${item.feed_item_id}-source-${source.source_index}`}
                          className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-[11px] font-semibold text-slate-600"
                        >
                          Source {source.source_index}
                        </span>
                      );
                    })}
                    <Link
                      to={feedActionHref(item)}
                      className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                    >
                      {feedActionLabel(item)}
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                </article>
              ))}
            </div>

            <div className="mt-4 flex items-center justify-center">
              <div ref={feedSentinelRef} className="h-8 w-full" />
              {feedLoadingMore ? (
                <div className="inline-flex items-center gap-2 text-xs text-slate-500">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading more feed items...
                </div>
              ) : null}
            </div>

            <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Safety</p>
              <p className="mt-1 text-sm text-slate-600">{feedDisclaimer}</p>
            </div>
          </>
        )}
      </section>

      <div id="workspaces" className={`flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 ${highlightForDemoTarget('workspaces')}`}>
        <h3 className="text-lg md:text-xl font-bold text-slate-900">Your Workspaces</h3>
        <Link
          to="/search"
          className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition-colors"
        >
          <span className="hidden sm:inline">Search Papers</span>
          <span className="sm:hidden">Search</span>
          <ArrowUpRight className="h-3.5 w-3.5" />
        </Link>
      </div>
      {demoTooltipTextForTarget('workspaces') ? (
        <div className="mb-3 inline-flex items-center gap-1 rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-[11px] font-semibold text-indigo-700">
          <Lightbulb className="h-3.5 w-3.5" /> {demoTooltipTextForTarget('workspaces')}
        </div>
      ) : null}

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 px-3">
          <div className="bg-white rounded-2xl p-6 w-full max-w-lg shadow-2xl border border-slate-100">
            <div className="flex items-center justify-between mb-5">
              <h4 className="text-lg font-bold text-slate-900">Create Workspace</h4>
              <button
                onClick={() => setShowCreate(false)}
                aria-label="Close create workspace dialog"
                title="Close"
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <p className="mb-2 text-sm font-medium text-slate-700">Start from a template</p>
                <div className="flex flex-wrap gap-2">
                  {workspaceTemplates.map((template) => (
                    <button
                      key={template.name}
                      type="button"
                      onClick={() => {
                        setNewName(template.name);
                        setNewDesc(template.description);
                      }}
                      className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-600 transition-colors hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700"
                    >
                      {template.name}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Name *</label>
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Multi-agent RAG Study"
                  className="w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
                <textarea
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="Project context, target area, key notes..."
                  rows={4}
                  className="w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm text-slate-900 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowCreate(false)}
                className="flex-1 py-2.5 rounded-xl border border-slate-200 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !newName.trim()}
                className="flex-1 py-2.5 rounded-xl bg-[linear-gradient(120deg,#4f46e5,#0284c7)] text-sm font-semibold text-white flex items-center justify-center gap-2 transition-opacity disabled:opacity-50"
              >
                {creating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" /> Creating...
                  </>
                ) : (
                  <>
                    <Check className="h-4 w-4" /> Create
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-slate-500 py-8">
          <Loader2 className="h-5 w-5 animate-spin" /> Loading workspaces...
        </div>
      ) : workspaces.length === 0 ? (
        <div className="feature-surface text-center py-12">
          <div className="w-14 h-14 rounded-2xl bg-indigo-50 flex items-center justify-center mx-auto mb-4">
            <Folder className="h-7 w-7 text-indigo-500" />
          </div>
          <h4 className="text-slate-800 font-semibold mb-1">No workspaces yet</h4>
          <p className="text-slate-500 text-sm mb-4">Create a workspace to start structuring your research program.</p>
          <button onClick={() => setShowCreate(true)} className="hero-btn-primary">
            <Plus className="h-4 w-4" /> Create first workspace
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {workspaces.map((ws) => (
            <div key={ws.id} className="feature-surface workspace-card">
              <div className="flex items-start justify-between mb-3">
                <div className="p-2 rounded-xl bg-indigo-50">
                  <Folder className="h-5 w-5 text-indigo-500" />
                </div>
                {deleteId === ws.id ? (
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleDelete(ws.id)}
                      className="text-xs px-2.5 py-1 rounded-lg bg-red-100 text-red-700 font-medium hover:bg-red-200"
                    >
                      Delete
                    </button>
                    <button
                      onClick={() => setDeleteId(null)}
                      className="text-xs px-2.5 py-1 rounded-lg bg-slate-100 text-slate-600 font-medium hover:bg-slate-200"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setDeleteId(ws.id)}
                    aria-label={`Delete workspace ${ws.name}`}
                    title="Delete workspace"
                    className="text-slate-300 hover:text-red-500 transition-colors"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>

              <h4 className="font-semibold text-slate-900 mb-1 truncate">{ws.name}</h4>
              <p className="text-sm text-slate-500 mb-4 line-clamp-2">{ws.description || 'No description provided.'}</p>

              <div className="mb-4 flex flex-wrap gap-2">
                <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold text-slate-600">
                  {ws.paperCount ?? 0} curated papers
                </span>
                <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
                  AI ready
                </span>
              </div>

              <div className="flex items-center justify-between gap-3">
                <span className="text-xs text-slate-500 bg-slate-100 px-2.5 py-1 rounded-full">
                  {ws.paperCount ?? 0} paper{ws.paperCount !== 1 ? 's' : ''} - {formatDate(ws.created_at)}
                </span>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => handleExportWorkspace(ws.id, ws.name, 'bibtex')}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-slate-600 hover:text-slate-900"
                  >
                    <Download className="h-3.5 w-3.5" /> Export
                  </button>
                  <Link to={`/workspace/${ws.id}`} className="text-xs font-semibold text-indigo-600 hover:text-indigo-800">
                    Open {'->'}
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
};

export default Dashboard;

