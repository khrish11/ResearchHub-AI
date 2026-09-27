import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Search, ArrowRight, FileText, BookOpen, RefreshCw, Plus, Upload, BrainCircuit } from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';

interface Workspace {
  id: number;
  name: string;
  description?: string;
  papers_count?: number;
  chats_count?: number;
  updated_at?: string;
}

interface SessionState {
  page_path: string;
  workspace_id?: number | null;
  last_query?: string | null;
  updated_at?: string | null;
}

interface RecommendationPaper {
  title: string;
  source?: string;
  year?: number;
  url?: string;
  doi?: string;
  score?: number;
  ranking_score?: number;
  freshness_score?: number;
  reason?: string;
}

interface PersonalizedFeedResponse {
  trending_papers: RecommendationPaper[];
  seed_keywords?: string[];
  relevance_context?: {
    realtime_keywords?: string[];
    history_queries?: string[];
    source_mix?: Record<string, number>;
  };
}

interface SearchHistoryInsights {
  top_queries: Array<{ query: string; display_query?: string; count: number; weight: number }>;
}

interface SearchGlobalFallbackResponse {
  papers: Array<{
    title: string;
    source?: string;
    published?: string;
    url?: string;
    doi?: string;
  }>;
}

const HOME_RECENT_RECOMMENDATIONS_KEY = 'researchhub.home_recent_recommendations.v1';

const parseYearFromPublished = (value?: string): number | undefined => {
  const match = String(value || '').match(/(19|20)\d{2}/);
  return match ? Number(match[0]) : undefined;
};

const formatRelevanceScore = (value: unknown): string | null => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return null;
  }
  return numeric.toFixed(2);
};

const parseResearchContext = (description?: string | null): {
  researchQuestion?: string;
  focus?: string;
  intent?: string;
  isResearchContext: boolean;
} => {
  if (!description) {
    return { isResearchContext: false };
  }

  const lines = description.split('\n').map(line => line.trim()).filter(Boolean);
  if (lines.length === 0 || !lines[0].startsWith('Research:')) {
    return { isResearchContext: false };
  }

  const result: {
    researchQuestion?: string;
    focus?: string;
    intent?: string;
    isResearchContext: boolean;
  } = { isResearchContext: true };

  for (const line of lines) {
    if (line.startsWith('Research:')) {
      result.researchQuestion = line.replace('Research:', '').trim();
    } else if (line.startsWith('Focus:')) {
      result.focus = line.replace('Focus:', '').trim();
    } else if (line.startsWith('Intent:')) {
      result.intent = line.replace('Intent:', '').trim();
    }
  }

  return result;
};

const normalizeRecKey = (item: RecommendationPaper): string => {
  const doi = String(item.doi || '').trim().toLowerCase();
  if (doi) return `doi:${doi}`;
  const url = String(item.url || '').trim().toLowerCase();
  if (url) return `url:${url}`;
  return `title:${String(item.title || '').trim().toLowerCase()}`;
};

const loadRecentRecommendationKeys = (): string[] => {
  try {
    const raw = localStorage.getItem(HOME_RECENT_RECOMMENDATIONS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.map((item) => String(item).trim()).filter(Boolean).slice(-80);
  } catch {
    return [];
  }
};

const saveRecentRecommendationKeys = (keys: string[]) => {
  localStorage.setItem(HOME_RECENT_RECOMMENDATIONS_KEY, JSON.stringify(keys.slice(-80)));
};

const diversifyRecommendations = (
  input: RecommendationPaper[],
  maxItems: number,
  refreshSeed: number
): RecommendationPaper[] => {
  if (!Array.isArray(input) || input.length === 0 || maxItems <= 0) return [];

  const groups = new Map<string, RecommendationPaper[]>();
  input.forEach((paper) => {
    const source = String(paper.source || 'multi-source').trim().toLowerCase() || 'multi-source';
    const bucket = groups.get(source) || [];
    bucket.push(paper);
    groups.set(source, bucket);
  });

  let sources = Array.from(groups.keys());
  if (sources.length > 1) {
    const shift = Math.abs(Math.floor(refreshSeed || 0)) % sources.length;
    if (shift > 0) {
      sources = [...sources.slice(shift), ...sources.slice(0, shift)];
    }
  }

  const output: RecommendationPaper[] = [];
  while (output.length < maxItems) {
    let addedThisRound = 0;
    for (const source of sources) {
      const bucket = groups.get(source) || [];
      if (bucket.length === 0) continue;
      output.push(bucket.shift() as RecommendationPaper);
      addedThisRound += 1;
      if (output.length >= maxItems) break;
    }
    if (addedThisRound === 0) break;
  }

  return output.slice(0, maxItems);
};

const Home = () => {
  const navigate = useNavigate();
  const [researchQuery, setResearchQuery] = useState('');
  const [queryError, setQueryError] = useState('');
  
  const [resumeState, setResumeState] = useState<SessionState | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspacesLoading, setWorkspacesLoading] = useState(false);
  const [workspacesError, setWorkspacesError] = useState<string | null>(null);
  
  const [recommendations, setRecommendations] = useState<RecommendationPaper[]>([]);
  const [recommendationLoading, setRecommendationLoading] = useState(false);
  const [recommendationError, setRecommendationError] = useState<string | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_seedKeywords, setSeedKeywords] = useState<string[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_realtimeKeywords, setRealtimeKeywords] = useState<string[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_historySeeds, setHistorySeeds] = useState<string[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_sourceMix, setSourceMix] = useState<Array<{ source: string; count: number }>>([]);
  const [recommendationUpdatedAt, setRecommendationUpdatedAt] = useState<string | null>(null);

  const loadHomeData = useCallback(async (forceLive = false) => {
    setWorkspacesLoading(true);
    setRecommendationLoading(true);
    setRecommendationError(null);
    setWorkspacesError(null);
    setSourceMix([]);
    
    try {
      const [sessionRes, workspaceRes, historyRes] = await Promise.all([
        api.get<SessionState>('/workspaces/session-state').catch(() => ({ data: { page_path: '/home' } as SessionState })),
        api.get<Workspace[]>('/workspaces/').catch(() => ({ data: [] as Workspace[] })),
        api.get<SearchHistoryInsights>('/papers/search-history/insights').catch(() => ({ data: { top_queries: [] } as SearchHistoryInsights })),
      ]);

      const session = sessionRes.data || { page_path: '/home' };
      setResumeState(session);

      const historySeedQueries = (historyRes.data?.top_queries || [])
        .map((item) => item.display_query || item.query)
        .filter(Boolean)
        .slice(0, 4);
      setHistorySeeds(historySeedQueries);
      
      // Normalize workspace response to ensure it's always an array
      let wsList: Workspace[] = [];
      if (Array.isArray(workspaceRes.data)) {
        wsList = workspaceRes.data;
      } else if (typeof workspaceRes.data === 'string') {
        // API returned HTML or error string instead of JSON
        console.error('Workspaces API returned non-JSON response:', workspaceRes.data);
        wsList = [];
      } else if (workspaceRes.data && typeof workspaceRes.data === 'object' && 'workspaces' in workspaceRes.data && Array.isArray((workspaceRes.data as { workspaces?: unknown }).workspaces)) {
        // Handle wrapped response format
        wsList = (workspaceRes.data as { workspaces: Workspace[] }).workspaces;
      } else {
        console.error('Unexpected workspaces response format:', workspaceRes.data);
        wsList = [];
      }
      
      setWorkspaces(wsList.slice(0, 4));
      setWorkspacesLoading(false);

      let recs: RecommendationPaper[] = [];
      let recKeywords: string[] = [];
      let recSourceMix: Array<{ source: string; count: number }> = [];

      if (wsList.length > 0) {
        const preferredWorkspaceId =
          session.workspace_id && wsList.some((workspace) => workspace.id === session.workspace_id)
            ? Number(session.workspace_id)
            : wsList[0].id;
        try {
          const feedRes = await api.post<PersonalizedFeedResponse>('/research/personalized-feed', {
            workspace_id: preferredWorkspaceId,
            max_suggestions: 8,
            force_live: forceLive,
            refresh_seed: forceLive ? `${Date.now()}` : undefined,
          });
          recs = Array.isArray(feedRes.data?.trending_papers) ? feedRes.data.trending_papers : [];
          const realtime = Array.isArray(feedRes.data?.relevance_context?.realtime_keywords)
            ? (feedRes.data?.relevance_context?.realtime_keywords as string[])
            : [];
          const history = Array.isArray(feedRes.data?.relevance_context?.history_queries)
            ? (feedRes.data?.relevance_context?.history_queries as string[])
            : [];
          const sourceMixMap =
            feedRes.data?.relevance_context?.source_mix &&
            typeof feedRes.data.relevance_context.source_mix === 'object'
              ? (feedRes.data.relevance_context.source_mix as Record<string, number>)
              : {};
          recSourceMix = Object.entries(sourceMixMap)
            .map(([source, count]) => ({ source, count: Number(count || 0) }))
            .filter((item) => item.count > 0)
            .sort((a, b) => b.count - a.count)
            .slice(0, 5);
          recKeywords = Array.isArray(feedRes.data?.seed_keywords) ? feedRes.data.seed_keywords.slice(0, 8) : [];
          setRealtimeKeywords(realtime.slice(0, 8));
          setHistorySeeds(history.slice(0, 4));
        } catch {
          recs = [];
        }
      }

      if (recs.length === 0 && (wsList.length > 0 || historySeedQueries.length > 0)) {
        const fallbackQueries = [...historySeedQueries, 'graph neural networks', 'federated learning security', 'renewable energy storage'];
        const dedup = new Map<string, RecommendationPaper>();
        for (const query of fallbackQueries) {
          if (!query || dedup.size >= 8) continue;
          try {
            const fallbackRes = await api.get<SearchGlobalFallbackResponse>('/papers/search-global', {
              params: {
                query,
                max_results: 6,
                offset: forceLive ? Math.abs((Date.now() + query.length) % 24) : 0,
                track_history: false,
              },
            });
            for (const paper of fallbackRes.data?.papers || []) {
              const item: RecommendationPaper = {
                title: paper.title,
                source: paper.source,
                year: parseYearFromPublished(paper.published),
                url: paper.url,
                doi: paper.doi,
                reason: `Trending around "${query}"`,
              };
              const key = normalizeRecKey(item);
              if (!dedup.has(key)) dedup.set(key, item);
              if (dedup.size >= 8) break;
            }
          } catch {
            // Continue fallback attempts.
          }
        }
        recs = Array.from(dedup.values());
        if (recKeywords.length === 0) {
          recKeywords = historySeedQueries.slice(0, 8);
        }
      }

      const recentKeys = loadRecentRecommendationKeys();
      const unseenRecs = recs.filter((paper) => !recentKeys.includes(normalizeRecKey(paper)));
      const basePool = unseenRecs.length >= Math.min(4, recs.length) ? unseenRecs : recs;
      const diversified = diversifyRecommendations(
        basePool,
        8,
        forceLive ? Date.now() : Date.now() / 60000
      );
      const nextRecommendations = diversified.slice(0, 8);
      if (recSourceMix.length === 0 && nextRecommendations.length > 0) {
        const localMix = new Map<string, number>();
        nextRecommendations.forEach((paper) => {
          const source = String(paper.source || 'multi-source').trim().toLowerCase();
          localMix.set(source, (localMix.get(source) || 0) + 1);
        });
        recSourceMix = Array.from(localMix.entries())
          .map(([source, count]) => ({ source, count }))
          .sort((a, b) => b.count - a.count)
          .slice(0, 5);
      }

      if (nextRecommendations.length > 0) {
        const nextKeys = [
          ...recentKeys,
          ...nextRecommendations.map((paper) => normalizeRecKey(paper)),
        ];
        saveRecentRecommendationKeys(nextKeys);
      }

      setRecommendations(nextRecommendations);
      setSourceMix(recSourceMix);
      setSeedKeywords(recKeywords);
      if (nextRecommendations.length === 0) {
        setRealtimeKeywords([]);
        setSourceMix([]);
      }
      setRecommendationUpdatedAt(new Date().toISOString());
      if (nextRecommendations.length === 0) {
        setRecommendationError('No recommendations available yet. Add papers or run a few searches.');
      }
    } catch (err) {
      console.error('Failed to load home data:', err);
      setRecommendationError('Unable to fetch live recommendations yet.');
      setWorkspacesError('Failed to load workspaces. Backend service may be unavailable.');
    } finally {
      setRecommendationLoading(false);
      setWorkspacesLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHomeData(false);
  }, [loadHomeData]);

  const handleStartResearch = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedQuery = researchQuery.trim();
    
    if (!trimmedQuery) {
      setQueryError('Please enter a research topic or question');
      return;
    }
    
    setQueryError('');
    navigate(`/research?q=${encodeURIComponent(trimmedQuery)}`);
  };

  const handleCreateWorkspace = () => {
    navigate('/workspaces');
  };

  const handleUploadPapers = () => {
    navigate('/research');
  };

  const formatLastActivity = (dateString?: string | null): string => {
    if (!dateString) return 'No recent activity';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    return date.toLocaleDateString();
  };

  return (
    <Layout>
      <div className="mx-auto max-w-5xl px-4 py-8">
        {/* Header */}
        <header className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            {resumeState?.page_path && resumeState.page_path !== '/home' 
              ? 'Continue your research' 
              : 'What are you researching today?'}
          </h1>
        </header>

        {/* Primary Research Entry */}
        <section className="mb-10">
          <form onSubmit={handleStartResearch} className="max-w-3xl">
            <div className="relative">
              <label htmlFor="research-query" className="sr-only">
                What are you researching?
              </label>
              <input
                id="research-query"
                type="text"
                value={researchQuery}
                onChange={(e) => {
                  setResearchQuery(e.target.value);
                  setQueryError('');
                }}
                placeholder="What are you researching?"
                className="w-full rounded-2xl border-2 border-slate-300 px-6 py-4 text-lg placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-4 focus:ring-indigo-500/20 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:border-indigo-400"
                aria-describedby={queryError ? 'query-error' : undefined}
              />
              {queryError && (
                <p id="query-error" className="mt-2 text-sm text-red-600" role="alert">
                  {queryError}
                </p>
              )}
            </div>
            <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">
              Enter a topic, research question, or problem you want to investigate.
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="submit"
                className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-6 py-3 text-base font-semibold text-white hover:bg-indigo-700 transition shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
              >
                <Search className="h-5 w-5" />
                START RESEARCH
              </button>
              <button
                type="button"
                onClick={handleCreateWorkspace}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-6 py-3 text-base font-semibold text-slate-700 hover:bg-slate-50 transition dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2"
              >
                <Plus className="h-5 w-5" />
                CREATE WORKSPACE
              </button>
              <button
                type="button"
                onClick={handleUploadPapers}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-6 py-3 text-base font-semibold text-slate-700 hover:bg-slate-50 transition dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2"
              >
                <Upload className="h-5 w-5" />
                UPLOAD PAPERS
              </button>
            </div>
          </form>
        </section>

        {/* Continue Research */}
        {resumeState?.page_path && resumeState.page_path !== '/home' && (
          <section className="mb-10 rounded-2xl border border-indigo-200 bg-indigo-50/70 p-6 dark:border-indigo-800 dark:bg-indigo-950/30">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Continue Research</h2>
                {resumeState.last_query && (
                  <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                    Last query: {resumeState.last_query}
                  </p>
                )}
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-500">
                  Last activity: {formatLastActivity(resumeState.updated_at)}
                </p>
              </div>
              <Link
                to={resumeState.page_path}
                className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 transition focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
              >
                CONTINUE
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </section>
        )}

        {/* What am I researching? */}
        {(() => {
          const activeWorkspace = resumeState?.workspace_id 
            ? workspaces.find(w => w.id === resumeState.workspace_id)
            : workspaces[0];
          
          if (!activeWorkspace || !activeWorkspace.description) {
            return null;
          }

          const researchContext = parseResearchContext(activeWorkspace.description);
          if (!researchContext.isResearchContext) {
            return null;
          }

          return (
            <section className="mb-10 rounded-2xl border border-emerald-200 bg-emerald-50/70 p-6 dark:border-emerald-800 dark:bg-emerald-950/30">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">What am I researching?</h2>
                  <div className="mt-3 space-y-2">
                    <div>
                      <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Research Question:</span>
                      <p className="text-base text-slate-900 dark:text-slate-100">{researchContext.researchQuestion}</p>
                    </div>
                    {researchContext.focus && (
                      <div>
                        <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Focus:</span>
                        <p className="text-sm text-slate-700 dark:text-slate-300">{researchContext.focus}</p>
                      </div>
                    )}
                    {researchContext.intent && (
                      <div>
                        <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Intent:</span>
                        <p className="text-sm text-slate-700 dark:text-slate-300">{researchContext.intent}</p>
                      </div>
                    )}
                  </div>
                  <p className="mt-3 text-xs text-slate-500 dark:text-slate-500">
                    Workspace: {activeWorkspace.name} • {activeWorkspace.papers_count || 0} papers
                  </p>
                </div>
                <Link
                  to={`/workspace/${activeWorkspace.id}`}
                  className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 transition focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
                >
                  OPEN WORKSPACE
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </section>
          );
        })()}

        {/* Recent Workspaces */}
        <section className="mb-10">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Recent Workspaces</h2>
            <Link
              to="/workspaces"
              className="inline-flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300"
            >
              View all workspaces
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          
          {workspacesLoading ? (
            <p className="text-sm text-slate-500 dark:text-slate-400">Loading workspaces...</p>
          ) : workspacesError ? (
            <p className="text-sm text-red-600">{workspacesError}</p>
          ) : workspaces.length === 0 ? (
            <p className="text-sm text-slate-500 dark:text-slate-400">No workspaces yet. Create your first workspace to get started.</p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {workspaces.map((workspace) => (
                <Link
                  key={workspace.id}
                  to={`/workspace/${workspace.id}`}
                  className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:shadow-md hover:border-indigo-300 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-indigo-600"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100 line-clamp-1">
                        {workspace.name}
                      </h3>
                      {workspace.description && (
                        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400 line-clamp-2">
                          {workspace.description}
                        </p>
                      )}
                    </div>
                    <div className="ml-3 flex flex-col gap-1 text-xs text-slate-500 dark:text-slate-400">
                      <div className="flex items-center gap-1">
                        <FileText className="h-3 w-3" />
                        {workspace.papers_count || 0}
                      </div>
                      <div className="flex items-center gap-1">
                        <BookOpen className="h-3 w-3" />
                        {workspace.chats_count || 0}
                      </div>
                    </div>
                  </div>
                  <div className="mt-4 flex items-center justify-between">
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {formatLastActivity(workspace.updated_at)}
                    </p>
                    <span className="inline-flex items-center gap-1 text-sm font-medium text-indigo-600 group-hover:underline dark:text-indigo-400">
                      OPEN
                      <ArrowRight className="h-3.5 w-3.5" />
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </section>

        {/* Recommended Papers */}
        <section className="mb-10">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Recommended for your research</h2>
              {recommendationUpdatedAt && (
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  Updated {new Date(recommendationUpdatedAt).toLocaleTimeString()}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void loadHomeData(true)}
                disabled={recommendationLoading}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition disabled:opacity-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${recommendationLoading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
              <Link
                to="/search"
                className="inline-flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300"
              >
                Explore papers
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>

          {recommendationLoading && (
            <p className="text-sm text-slate-500 dark:text-slate-400">Loading recommendations...</p>
          )}
          {!recommendationLoading && recommendationError && (
            <p className="text-sm text-amber-700 dark:text-amber-400">{recommendationError}</p>
          )}
          {!recommendationLoading && !recommendationError && recommendations.length === 0 && (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Add papers to a workspace to unlock live topic-based recommendations.
            </p>
          )}
          {!recommendationLoading && recommendations.length > 0 && (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {recommendations.map((paper, index) => {
                const link = paper.url || (paper.doi ? `https://doi.org/${paper.doi}` : '');
                const scoreText = formatRelevanceScore(paper.ranking_score ?? paper.score);
                return (
                  <article key={`${paper.title}-${index}`} className="rounded-2xl border border-slate-200 bg-slate-50/90 p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
                    <div className="flex flex-wrap items-center gap-2 mb-3">
                      <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-400">
                        {paper.source || 'multi-source'}
                      </span>
                      {paper.year && (
                        <span className="rounded-full border border-cyan-200 bg-cyan-50 px-2.5 py-1 text-[11px] font-semibold text-cyan-700 dark:border-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300">
                          {paper.year}
                        </span>
                      )}
                    </div>
                    <p className="text-sm font-semibold text-slate-900 dark:text-slate-100 line-clamp-2 mb-2">
                      {paper.title}
                    </p>
                    {scoreText && (
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 mb-2">
                        relevance score: {scoreText}
                      </p>
                    )}
                    {paper.reason && (
                      <p className="mb-3 rounded-xl border border-indigo-100 bg-indigo-50 px-2.5 py-2 text-[11px] text-indigo-700 dark:border-indigo-800 dark:bg-indigo-950/30 dark:text-indigo-300">
                        {paper.reason}
                      </p>
                    )}
                    {link && (
                      <a
                        href={link}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-700 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300"
                      >
                        Open paper
                        <ArrowRight className="h-3.5 w-3.5" />
                      </a>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </section>

        {/* Bottom Quick Actions */}
        <section className="grid gap-4 md:grid-cols-3">
          <Link
            to="/search"
            className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:shadow-md hover:border-indigo-300 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-indigo-600"
          >
            <div className="mb-3 inline-flex rounded-xl bg-indigo-100 p-3 text-indigo-600 dark:bg-indigo-900 dark:text-indigo-300">
              <Search className="h-6 w-6" />
            </div>
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Search Papers</h3>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
              Search across 28+ academic sources to find relevant papers.
            </p>
            <span className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-indigo-600 group-hover:underline dark:text-indigo-400">
              Start searching
              <ArrowRight className="h-4 w-4" />
            </span>
          </Link>

          <Link
            to="/research-agent"
            className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:shadow-md hover:border-indigo-300 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-indigo-600"
          >
            <div className="mb-3 inline-flex rounded-xl bg-fuchsia-100 p-3 text-fuchsia-600 dark:bg-fuchsia-900 dark:text-fuchsia-300">
              <BrainCircuit className="h-6 w-6" />
            </div>
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Deep Research</h3>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
              Let AI autonomously explore literature and generate insights.
            </p>
            <span className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-fuchsia-600 group-hover:underline dark:text-fuchsia-400">
              Start deep research
              <ArrowRight className="h-4 w-4" />
            </span>
          </Link>

          <Link
            to="/library"
            className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:shadow-md hover:border-indigo-300 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-indigo-600"
          >
            <div className="mb-3 inline-flex rounded-xl bg-emerald-100 p-3 text-emerald-600 dark:bg-emerald-900 dark:text-emerald-300">
              <BookOpen className="h-6 w-6" />
            </div>
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Open Library</h3>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
              Access your papers, saved questions, and research artifacts.
            </p>
            <span className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-emerald-600 group-hover:underline dark:text-emerald-400">
              Open library
              <ArrowRight className="h-4 w-4" />
            </span>
          </Link>
        </section>
      </div>
    </Layout>
  );
};

export default Home;
