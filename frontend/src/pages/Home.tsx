import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, MessageSquare, FileText, BookOpen, Sparkles, Orbit, BrainCircuit, Layers3, ArrowRight, RefreshCw, Bot, Upload, Workflow } from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';

interface Workspace {
  id: number;
  name: string;
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
  const [resumeState, setResumeState] = useState<SessionState | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationPaper[]>([]);
  const [recommendationLoading, setRecommendationLoading] = useState(false);
  const [recommendationError, setRecommendationError] = useState<string | null>(null);
  const [seedKeywords, setSeedKeywords] = useState<string[]>([]);
  const [realtimeKeywords, setRealtimeKeywords] = useState<string[]>([]);
  const [historySeeds, setHistorySeeds] = useState<string[]>([]);
  const [sourceMix, setSourceMix] = useState<Array<{ source: string; count: number }>>([]);
  const [recommendationUpdatedAt, setRecommendationUpdatedAt] = useState<string | null>(null);

  const loadHomeData = useCallback(async (forceLive = false) => {
    setRecommendationLoading(true);
    setRecommendationError(null);
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
      const workspaces = workspaceRes.data || [];

      let recs: RecommendationPaper[] = [];
      let recKeywords: string[] = [];
      let recSourceMix: Array<{ source: string; count: number }> = [];

      if (workspaces.length > 0) {
        const preferredWorkspaceId =
          session.workspace_id && workspaces.some((workspace) => workspace.id === session.workspace_id)
            ? Number(session.workspace_id)
            : workspaces[0].id;
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

      if (recs.length === 0) {
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
    } catch {
      setRecommendationError('Unable to fetch live recommendations yet.');
    } finally {
      setRecommendationLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHomeData(false);
  }, [loadHomeData]);

  const featureCards = [
    {
      title: 'Signal Search',
      desc: 'Probe multi-source paper indexes with richer relevance and live source diagnostics.',
      icon: Search,
      color: '#4f46e5',
      to: '/search',
      cta: 'Open Search',
    },
    {
      title: 'Context Chat',
      desc: 'Ask long-horizon research questions and keep context pinned to your workspace.',
      icon: MessageSquare,
      color: '#0284c7',
      to: '/ai-tools',
      cta: 'Open AI Tools',
    },
    {
      title: 'Doc Studio',
      desc: 'Draft, refine, and structure manuscripts with AI-guided editing workflows.',
      icon: FileText,
      color: '#0f766e',
      to: '/docs',
      cta: 'Open DocSpace',
    },
    {
      title: 'Review Engine',
      desc: 'Synthesize connected literature clusters instead of isolated single-paper summaries.',
      icon: BookOpen,
      color: '#9333ea',
      to: '/mindmap',
      cta: 'Open Mindmap',
    },
  ];

  const quickActionCards = [
    {
      title: 'Discover literature',
      desc: 'Run global search across 28+ source rails with live ranking and source diversity.',
      icon: Search,
      to: '/search',
      tone: 'from-indigo-500 to-cyan-500',
    },
    {
      title: 'Ask the research agent',
      desc: 'Move from search results to guided exploration when you need deeper synthesis.',
      icon: Bot,
      to: '/research-agent',
      tone: 'from-sky-500 to-blue-600',
    },
    {
      title: 'Ingest private PDFs',
      desc: 'Bring your own documents into the same workspace and keep the evidence layer unified.',
      icon: Upload,
      to: '/upload',
      tone: 'from-emerald-500 to-teal-600',
    },
    {
      title: 'Map the review',
      desc: 'Turn clusters of papers into a mindmap before writing or drafting structured review output.',
      icon: Workflow,
      to: '/mindmap',
      tone: 'from-fuchsia-500 to-violet-600',
    },
  ];

  const runwaySteps = [
    {
      label: '1. Scout',
      title: 'Search broad, then narrow fast',
      copy: 'Start in multi-source search, save one useful query, and identify the source mix before importing.',
    },
    {
      label: '2. Capture',
      title: 'Import only the evidence you need',
      copy: 'Move selected papers into a workspace so AI tools and exports stay tied to one clear project context.',
    },
    {
      label: '3. Synthesize',
      title: 'Let the AI operate on context, not fragments',
      copy: 'Use AI Tools, Research Chat, or Mindmap once the workspace contains enough strong material.',
    },
  ];

  return (
    <Layout>
      <section className="home-hero mb-6">
        <div className="home-hero-content">
          <p className="text-xs uppercase tracking-[0.2em] text-cyan-200 mb-2 flex items-center gap-2">
            <Sparkles className="h-3.5 w-3.5" /> Research Intelligence Layer
          </p>
          <h2 className="text-4xl md:text-5xl font-bold text-white leading-tight max-w-3xl">
            Design Breakthrough Research Pipelines, Not Just Paper Lists
          </h2>
          <p className="text-cyan-100/90 mt-4 max-w-2xl text-sm md:text-base">
            ResearchHub AI now blends deep search, live source verification, and AI-native writing flow in one command surface.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/search" className="hero-btn-primary">
              Launch Search Matrix <ArrowRight className="h-4 w-4" />
            </Link>
            <Link to="/dashboard" className="hero-btn-secondary">
              Open Dashboard
            </Link>
          </div>
        </div>

        <div className="hero-3d">
          <div className="hero-prism" />
          <div className="hero-ring ring-one" />
          <div className="hero-ring ring-two" />
          <div className="hero-ring ring-three" />
        </div>
      </section>

      {resumeState?.page_path && resumeState.page_path !== '/home' && (
        <section className="mb-5 rounded-2xl border border-indigo-200 bg-indigo-50/70 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-indigo-700 mb-1">Continue Session</p>
              <p className="text-sm text-indigo-900 font-semibold">Resume from: {resumeState.page_path}</p>
              {resumeState.last_query && (
                <p className="text-xs text-indigo-700 mt-1">Last query: {resumeState.last_query}</p>
              )}
            </div>
            <Link to={resumeState.page_path} className="hero-btn-primary">
              Continue where you left off <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </section>
      )}

      <section className="mb-6 grid grid-cols-1 gap-4 xl:grid-cols-[1.1fr,0.9fr]">
        <div className="feature-surface">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="mb-1 text-xs uppercase tracking-[0.2em] text-slate-500">Research runway</p>
              <h3 className="text-xl font-bold text-slate-900">Your next three high-leverage moves</h3>
            </div>
            <Link to="/dashboard" className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600">
              Open workspace ops <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          <div className="mt-4 grid gap-3">
            {runwaySteps.map((step) => (
              <article key={step.label} className="rounded-2xl border border-slate-200 bg-slate-50/90 px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-indigo-600">{step.label}</p>
                <h4 className="mt-1 text-base font-semibold text-slate-900">{step.title}</h4>
                <p className="mt-1 text-sm leading-relaxed text-slate-600">{step.copy}</p>
              </article>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {quickActionCards.map((card) => {
            const Icon = card.icon;
            return (
              <Link
                key={card.title}
                to={card.to}
                className="group rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition-transform duration-150 hover:-translate-y-1 hover:shadow-lg"
              >
                <div className={`inline-flex rounded-2xl bg-gradient-to-br ${card.tone} p-2.5 text-white shadow-md`}>
                  <Icon className="h-5 w-5" />
                </div>
                <h4 className="mt-4 text-base font-semibold text-slate-900">{card.title}</h4>
                <p className="mt-1 text-sm leading-relaxed text-slate-600">{card.desc}</p>
                <span className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-slate-700">
                  Jump in <ArrowRight className="h-3.5 w-3.5 transition-transform duration-150 group-hover:translate-x-0.5" />
                </span>
              </Link>
            );
          })}
        </div>
      </section>

      <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500 mb-1">Trending Research Feed</p>
            <h3 className="text-xl font-bold text-slate-900">Personalized Real-Time Recommendations</h3>
            {recommendationUpdatedAt && (
              <p className="text-xs text-slate-500 mt-1">
                Updated {new Date(recommendationUpdatedAt).toLocaleTimeString()}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void loadHomeData(true)}
              disabled={recommendationLoading}
              className="hero-btn-secondary disabled:opacity-60"
            >
              <RefreshCw className={`h-4 w-4 ${recommendationLoading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <Link to="/research-agent" className="hero-btn-secondary">
              Open Research Agent
            </Link>
          </div>
        </div>

        {seedKeywords.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {seedKeywords.map((keyword) => (
              <span key={keyword} className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
                {keyword}
              </span>
            ))}
          </div>
        )}
        {realtimeKeywords.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {realtimeKeywords.map((keyword) => (
              <span key={`rt-${keyword}`} className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs text-emerald-700">
                realtime: {keyword}
              </span>
            ))}
          </div>
        )}
        {sourceMix.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {sourceMix.map((item) => (
              <span key={`src-${item.source}`} className="rounded-full border border-cyan-200 bg-cyan-50 px-2.5 py-1 text-xs text-cyan-700">
                {item.source}: {item.count}
              </span>
            ))}
          </div>
        )}
        {historySeeds.length > 0 && (
          <p className="text-xs text-slate-500 mb-3">
            Personalized from recent searches: {historySeeds.join(' | ')}
          </p>
        )}

        {recommendationLoading && (
          <p className="text-sm text-slate-500">Loading recommendations...</p>
        )}
        {!recommendationLoading && recommendationError && (
          <p className="text-sm text-amber-700">{recommendationError}</p>
        )}
        {!recommendationLoading && !recommendationError && recommendations.length === 0 && (
          <p className="text-sm text-slate-500">
            Add papers to a workspace to unlock live topic-based recommendations.
          </p>
        )}
        {!recommendationLoading && recommendations.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {recommendations.map((paper, index) => {
              const link = paper.url || (paper.doi ? `https://doi.org/${paper.doi}` : '');
              return (
                <article key={`${paper.title}-${index}`} className="rounded-2xl border border-slate-200 bg-slate-50/90 p-3.5 shadow-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                      {paper.source || 'multi-source'}
                    </span>
                    {paper.year && (
                      <span className="rounded-full border border-cyan-200 bg-cyan-50 px-2.5 py-1 text-[11px] font-semibold text-cyan-700">
                        {paper.year}
                      </span>
                    )}
                  </div>
                  <p className="mt-3 text-sm font-semibold text-slate-900 line-clamp-2">{paper.title}</p>
                  {(paper.ranking_score || paper.score) && (
                    <p className="mt-2 text-[11px] text-slate-500">
                      relevance score: {(paper.ranking_score || paper.score || 0).toFixed(2)}
                    </p>
                  )}
                  {paper.reason && (
                    <p className="mt-2 rounded-xl border border-indigo-100 bg-indigo-50 px-2.5 py-2 text-[11px] text-indigo-700">
                      {paper.reason}
                    </p>
                  )}
                  {link && (
                    <a href={link} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-indigo-700">
                      Open paper <ArrowRight className="h-3.5 w-3.5" />
                    </a>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-7">
        <div className="stat-tile">
          <div className="stat-icon" style={{ background: 'rgba(79, 70, 229, 0.12)', color: '#4f46e5' }}>
            <Orbit className="h-5 w-5" />
          </div>
          <p className="stat-label">Search Fabric</p>
          <p className="stat-value">28+ Source Rails</p>
        </div>
        <div className="stat-tile">
          <div className="stat-icon" style={{ background: 'rgba(2, 132, 199, 0.12)', color: '#0284c7' }}>
            <BrainCircuit className="h-5 w-5" />
          </div>
          <p className="stat-label">AI Core</p>
          <p className="stat-value">Context Aware</p>
        </div>
        <div className="stat-tile">
          <div className="stat-icon" style={{ background: 'rgba(147, 51, 234, 0.12)', color: '#9333ea' }}>
            <Layers3 className="h-5 w-5" />
          </div>
          <p className="stat-label">Workspace Stack</p>
          <p className="stat-value">Import + Export + Synthesis</p>
        </div>
      </section>

      <section className="mb-4">
        <h3 className="text-2xl font-bold text-slate-900 mb-4">Core Systems</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {featureCards.map((card) => {
            const Icon = card.icon;
            return (
              <Link key={card.title} to={card.to} className="feature-surface group cursor-pointer">
                <div className="feature-icon" style={{ background: `${card.color}1f`, color: card.color }}>
                  <Icon className="h-5 w-5" />
                </div>
                <h4 className="text-base font-semibold text-slate-900 mt-3">{card.title}</h4>
                <p className="text-sm text-slate-600 mt-1 leading-relaxed">{card.desc}</p>
                <span className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold" style={{ color: card.color }}>
                  {card.cta} <ArrowRight className="h-3.5 w-3.5 transition-transform duration-150 group-hover:translate-x-0.5" />
                </span>
              </Link>
            );
          })}
        </div>
      </section>
    </Layout>
  );
};

export default Home;
