import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Search,
  ExternalLink,
  Loader2,
  Plus,
  CheckCircle,
  AlertCircle,
  BookmarkPlus,
  Copy,
  Download,
  Calendar,
  FileText,
  RefreshCw,
  Sparkles,
  History,
  Trash2,
} from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';
import { apiErrorMessage } from '../utils/apiError';
import { useToast } from '../contexts/ToastContext';

interface Paper {
  title: string;
  authors: string[];
  abstract: string;
  url: string;
  pdf_url?: string;
  published: string;
  categories: string[];
  source?: string;
  doi?: string;
  bibcode?: string;
  publication_title?: string;
  publication_name?: string;
}

interface Workspace {
  id: number;
  name: string;
}

interface SearchResponse {
  papers: Paper[];
  returned?: number;
  next_offset?: number;
  has_more?: boolean;
}

interface SavedQuery {
  id: string;
  query: string;
  savedAt: string;
}

interface SearchHistoryItem {
  id: number;
  query: string;
  source: string;
  result_count: number;
  created_at: string;
  filters?: Record<string, unknown>;
}

type YearFilter = 'any' | '2026' | '2024' | '2020' | '2015' | '2010';
type SortMode = 'relevance' | 'newest' | 'oldest' | 'title';
type CitationStyle = 'apa' | 'mla' | 'ieee';

const GLOBAL_SEARCH_ENDPOINT = '/papers/search-global';
const SEARCH_MIN_RESULTS = 20;
const SEARCH_MAX_RESULTS = 120;
const SEARCH_DEFAULT_RESULTS = 60;
const SAVED_QUERIES_KEY = 'researchhub.saved_queries.v2';

const QUICK_QUERIES = [
  'graph neural networks for molecules',
  'multimodal llm reasoning benchmark',
  'battery degradation prediction transformers',
  'exoplanet atmospheric retrieval',
  'robust control for quadrotors',
  'finite element analysis composites',
  'power electronics wide bandgap devices',
  'nanophotonics metasurface design',
];

const SOURCE_LABELS: Record<string, string> = {
  arxiv: 'ArXiv',
  semantic: 'Semantic Scholar',
  semantic_scholar: 'Semantic Scholar',
  semantic_scholar_fallback_arxiv: 'Semantic Scholar',
  openalex: 'OpenAlex',
  europepmc: 'Europe PMC',
  europe_pmc: 'Europe PMC',
  doaj: 'DOAJ',
  hal: 'HAL',
  biorxiv: 'bioRxiv',
  medrxiv: 'medRxiv',
  plos: 'PLOS',
  elife: 'eLife',
  pubmed: 'PubMed',
  springer: 'Springer',
  nasa: 'NASA ADS',
  nasa_ads: 'NASA ADS',
  datacite: 'DataCite',
};

const OPEN_ACCESS_SOURCES = new Set([
  'arxiv',
  'europepmc',
  'europe_pmc',
  'doaj',
  'hal',
  'biorxiv',
  'medrxiv',
  'plos',
  'elife',
]);

const normalizeKey = (paper: Paper): string => {
  const doi = (paper.doi || '').trim().toLowerCase();
  if (doi) {
    return `doi:${doi.replace('https://doi.org/', '').replace('http://doi.org/', '')}`;
  }
  const url = (paper.url || '').trim().toLowerCase();
  if (url) {
    return `url:${url}`;
  }
  return `title:${(paper.title || '').trim().toLowerCase()}`;
};

const parseYear = (published: string): number => {
  const match = String(published || '').match(/(19|20)\d{2}/);
  return match ? Number(match[0]) : 0;
};

const hasPdfLink = (paper: Paper): boolean => {
  const url = String(paper.url || '').toLowerCase();
  const pdfUrl = String(paper.pdf_url || '').toLowerCase();
  return pdfUrl.length > 0 || url.endsWith('.pdf') || pdfUrl.endsWith('.pdf');
};

const isLikelyOpenAccess = (paper: Paper): boolean => {
  const source = String(paper.source || '').toLowerCase();
  if (OPEN_ACCESS_SOURCES.has(source)) {
    return true;
  }
  const url = String(paper.url || '').toLowerCase();
  return url.includes('pmc') || url.includes('/pdf') || url.includes('arxiv.org');
};

const loadSavedQueries = (): SavedQuery[] => {
  try {
    const raw = localStorage.getItem(SAVED_QUERIES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item) => item && typeof item.id === 'string' && typeof item.query === 'string')
      .map((item) => ({
        id: String(item.id),
        query: String(item.query).trim(),
        savedAt: typeof item.savedAt === 'string' ? item.savedAt : '',
      }))
      .filter((item) => item.query.length > 0)
      .slice(0, 20);
  } catch {
    return [];
  }
};

const buildCitation = (paper: Paper, style: CitationStyle): string => {
  const year = parseYear(paper.published);
  const authors = paper.authors && paper.authors.length > 0 ? paper.authors : ['Unknown author'];
  const title = (paper.title || 'Untitled').trim();
  const venue = (paper.publication_name || paper.publication_title || paper.source || 'Unknown venue').trim();
  const url = (paper.url || '').trim();

  if (style === 'ieee') {
    return `${authors.join(', ')}, "${title}," ${venue}, ${year || 'n.d.'}. ${url ? `Available: ${url}` : ''}`.trim();
  }
  if (style === 'mla') {
    const first = authors[0] || 'Unknown author';
    return `${first}${authors.length > 1 ? ', et al.' : '.'} "${title}." ${venue}, ${year || 'n.d.'}. ${url}`.trim();
  }
  return `${authors.join(', ')} (${year || 'n.d.'}). ${title}. ${venue}.${url ? ` ${url}` : ''}`.trim();
};

const formatHistoryTime = (value: string): string => {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return 'recent';
  const diffMs = Date.now() - timestamp;
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.round(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.round(diffHours / 24);
  return `${diffDays}d ago`;
};

const SearchPapers: React.FC = () => {
  const { success: toastSuccess, error: toastError } = useToast();

  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusText, setStatusText] = useState('Ready. Search across connected sources.');

  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<number | null>(null);
  const [importingTitle, setImportingTitle] = useState<string | null>(null);
  const [importedSet, setImportedSet] = useState<Set<string>>(new Set());

  const [maxResults, setMaxResults] = useState(SEARCH_DEFAULT_RESULTS);
  const [oaOnly, setOaOnly] = useState(false);
  const [pdfOnly, setPdfOnly] = useState(false);
  const [yearFilter, setYearFilter] = useState<YearFilter>('any');
  const [sortMode, setSortMode] = useState<SortMode>('relevance');
  const [citationStyle, setCitationStyle] = useState<CitationStyle>('apa');

  const [nextOffset, setNextOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  const [savedQueries, setSavedQueries] = useState<SavedQuery[]>(() => loadSavedQueries());
  const [showSavedQueries, setShowSavedQueries] = useState(false);
  const [searchHistory, setSearchHistory] = useState<SearchHistoryItem[]>([]);
  const [showSearchHistory, setShowSearchHistory] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [loadingImported, setLoadingImported] = useState(false);

  const inputRef = useRef<HTMLInputElement | null>(null);
  const activeControllerRef = useRef<AbortController | null>(null);
  const runIdRef = useRef(0);

  useEffect(() => {
    let mounted = true;
    const boot = async () => {
      try {
        const [workspaceRes, sessionRes] = await Promise.all([
          api.get<Workspace[]>('/workspaces/'),
          api.get('/workspaces/session-state').catch(() => ({ data: null })),
        ]);
        const list = workspaceRes.data || [];
        const preferredWorkspaceId = Number(sessionRes?.data?.workspace_id || 0);
        const preferredQuery = String(sessionRes?.data?.last_query || '').trim();

        if (list.length > 0) {
          if (!mounted) return;
          setWorkspaces(list);
          const validPreferred = list.some((workspace) => workspace.id === preferredWorkspaceId);
          setActiveWorkspaceId(validPreferred ? preferredWorkspaceId : list[0].id);
          if (preferredQuery) {
            setQuery(preferredQuery);
          }
          return;
        }

        const created = await api.post<Workspace>('/workspaces/default', {});
        if (!mounted) return;
        setWorkspaces([created.data]);
        setActiveWorkspaceId(created.data.id);
        if (preferredQuery) {
          setQuery(preferredQuery);
        }
      } catch {
        if (!mounted) return;
        setWorkspaces([]);
        setActiveWorkspaceId(null);
        setImportedSet(new Set());
      }
    };

    void boot();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!activeWorkspaceId) {
      setImportedSet(new Set());
      return;
    }
    let mounted = true;
    setLoadingImported(true);
    api
      .get(`/workspaces/${activeWorkspaceId}`)
      .then((res) => {
        if (!mounted) return;
        const existingPapers: Array<{
          title: string;
          doi?: string;
          url?: string;
          authors?: string;
          abstract?: string;
        }> = res.data?.papers || [];
        const next = new Set<string>();
        existingPapers.forEach((paper) => {
          const key = normalizeKey({
            title: String(paper.title || ''),
            authors: [],
            abstract: String(paper.abstract || ''),
            url: String(paper.url || ''),
            doi: String(paper.doi || ''),
            published: '',
            categories: [],
          });
          next.add(key);
        });
        setImportedSet(next);
      })
      .catch(() => {
        if (!mounted) return;
        setImportedSet(new Set());
      })
      .finally(() => {
        if (mounted) setLoadingImported(false);
      });

    return () => {
      mounted = false;
    };
  }, [activeWorkspaceId]);

  const fetchSearchHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const response = await api.get<{ items: SearchHistoryItem[] }>('/papers/search-history', {
        params: { limit: 30 },
      });
      setSearchHistory(response.data?.items || []);
    } catch {
      setSearchHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchSearchHistory();
  }, [fetchSearchHistory]);

  useEffect(() => {
    try {
      localStorage.setItem(SAVED_QUERIES_KEY, JSON.stringify(savedQueries));
    } catch {
      // Storage failures are non-blocking.
    }
  }, [savedQueries]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const editable =
        !!target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable);

      if (!editable && event.key === '/' && !event.ctrlKey && !event.metaKey && !event.altKey) {
        event.preventDefault();
        inputRef.current?.focus();
      }

      if (event.key === 'Escape' && activeControllerRef.current) {
        runIdRef.current += 1;
        activeControllerRef.current.abort();
        activeControllerRef.current = null;
        setLoading(false);
        setLoadingMore(false);
        setStatusText('Search canceled.');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      activeControllerRef.current?.abort();
      activeControllerRef.current = null;
    };
  }, []);

  const mergeUnique = useCallback((current: Paper[], incoming: Paper[]): Paper[] => {
    const out: Paper[] = [];
    const seen = new Set<string>();

    for (const paper of [...current, ...incoming]) {
      const key = normalizeKey(paper);
      if (seen.has(key)) {
        continue;
      }
      seen.add(key);
      out.push(paper);
    }

    return out;
  }, []);

  const persistSessionState = useCallback(
    async (finalQuery: string) => {
      await api.put('/workspaces/session-state', {
        page_path: '/search',
        workspace_id: activeWorkspaceId,
        last_query: finalQuery.slice(0, 300),
        extra: {
          maxResults,
          oaOnly,
          pdfOnly,
          yearFilter,
          sortMode,
        },
      });
    },
    [activeWorkspaceId, maxResults, oaOnly, pdfOnly, sortMode, yearFilter],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const trimmed = query.trim();
      if (!trimmed && !activeWorkspaceId) return;
      void persistSessionState(trimmed).catch(() => undefined);
    }, 900);
    return () => window.clearTimeout(timer);
  }, [activeWorkspaceId, persistSessionState, query]);

  const runSearch = useCallback(
    async (append: boolean, forcedQuery?: string) => {
      const finalQuery = (forcedQuery ?? query).trim();
      if (!finalQuery) {
        setError('Enter a search query.');
        return;
      }

      runIdRef.current += 1;
      const runId = runIdRef.current;

      activeControllerRef.current?.abort();
      const controller = new AbortController();
      activeControllerRef.current = controller;

      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
        setResults([]);
        setNextOffset(0);
        setHasMore(false);
      }
      setError(null);
      setStatusText(append ? 'Loading more papers...' : 'Searching all connected sources...');

      try {
        const offset = append ? nextOffset : 0;
        const response = await api.get<SearchResponse>(GLOBAL_SEARCH_ENDPOINT, {
          params: {
            query: finalQuery,
            max_results: maxResults,
            offset,
          },
          signal: controller.signal,
        });

        if (runId !== runIdRef.current) {
          return;
        }

        const payload = response.data;
        const incoming = payload.papers || [];

        setHasMore(Boolean(payload.has_more));

        const computedNextOffset =
          typeof payload.next_offset === 'number' ? payload.next_offset : offset + incoming.length;
        setNextOffset(computedNextOffset);

        setResults((prev) => (append ? mergeUnique(prev, incoming) : mergeUnique([], incoming)));

        const shownCount = append
          ? mergeUnique(results, incoming).length
          : incoming.length;
        setStatusText(`Showing ${shownCount} merged papers from connected sources.`);
        void fetchSearchHistory();
        void persistSessionState(finalQuery).catch(() => undefined);
      } catch (err: unknown) {
        if (controller.signal.aborted) {
          return;
        }
        const message = apiErrorMessage(err, 'Search request failed.');
        setError(message);
        setStatusText('Search failed. Retry with fewer words or another topic phrase.');
        void persistSessionState(finalQuery).catch(() => undefined);
      } finally {
        if (runId === runIdRef.current) {
          setLoading(false);
          setLoadingMore(false);
          activeControllerRef.current = null;
        }
      }
    },
    [fetchSearchHistory, maxResults, mergeUnique, nextOffset, persistSessionState, query, results],
  );

  const filteredResults = useMemo(() => {
    let filtered = [...results];

    if (oaOnly) {
      filtered = filtered.filter((paper) => isLikelyOpenAccess(paper));
    }

    if (pdfOnly) {
      filtered = filtered.filter((paper) => hasPdfLink(paper));
    }

    if (yearFilter !== 'any') {
      const minYear = Number(yearFilter);
      filtered = filtered.filter((paper) => parseYear(paper.published) >= minYear);
    }

    if (sortMode === 'newest') {
      filtered.sort((a, b) => parseYear(b.published) - parseYear(a.published));
    } else if (sortMode === 'oldest') {
      filtered.sort((a, b) => parseYear(a.published) - parseYear(b.published));
    } else if (sortMode === 'title') {
      filtered.sort((a, b) => a.title.localeCompare(b.title));
    }

    return filtered;
  }, [oaOnly, pdfOnly, results, sortMode, yearFilter]);

  const saveCurrentQuery = () => {
    const trimmed = query.trim();
    if (!trimmed) {
      return;
    }

    const existing = savedQueries.find((item) => item.query.toLowerCase() === trimmed.toLowerCase());
    if (existing) {
      toastSuccess('Query already saved');
      return;
    }

    const entry: SavedQuery = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      query: trimmed,
      savedAt: new Date().toISOString(),
    };

    setSavedQueries((prev) => [entry, ...prev].slice(0, 20));
    toastSuccess('Search query saved');
  };

  const removeSavedQuery = (id: string) => {
    setSavedQueries((prev) => prev.filter((item) => item.id !== id));
  };

  const clearSearchHistory = async () => {
    try {
      await api.delete('/papers/search-history');
      setSearchHistory([]);
      toastSuccess('Search history cleared');
    } catch {
      toastError('Failed to clear search history');
    }
  };

  const removeSearchHistoryItem = async (id: number) => {
    try {
      await api.delete('/papers/search-history', { params: { item_id: id } });
      setSearchHistory((prev) => prev.filter((item) => item.id !== id));
    } catch {
      toastError('Failed to remove search history entry');
    }
  };

  const importPaper = async (paper: Paper) => {
    if (!activeWorkspaceId) {
      toastError('Select a workspace before importing papers.');
      return;
    }

    setImportingTitle(paper.title);
    try {
      await api.post('/papers/import', {
        title: paper.title,
        authors: paper.authors || [],
        abstract: paper.abstract || '',
        url: paper.url || '',
        doi: paper.doi || '',
        bibcode: paper.bibcode || '',
        workspace_id: activeWorkspaceId,
      });
      await api.put('/workspaces/session-state', {
        page_path: '/search',
        workspace_id: activeWorkspaceId,
        last_query: query.trim(),
      });
      setImportedSet((prev) => {
        const next = new Set(prev);
        next.add(normalizeKey(paper));
        return next;
      });
      toastSuccess('Paper imported');
    } catch (err: unknown) {
      toastError(apiErrorMessage(err, 'Failed to import paper.'));
    } finally {
      setImportingTitle(null);
    }
  };

  const copyCitation = async (paper: Paper) => {
    const text = buildCitation(paper, citationStyle);
    try {
      await navigator.clipboard.writeText(text);
      toastSuccess('Citation copied');
    } catch {
      toastError('Failed to copy citation');
    }
  };

  const exportCitations = (format: 'txt' | 'csv') => {
    if (filteredResults.length === 0) {
      toastError('No results to export');
      return;
    }

    let content = '';
    let mime = 'text/plain;charset=utf-8';
    let ext = 'txt';

    if (format === 'csv') {
      const rows = [
        ['Title', 'Authors', 'Year', 'Source', 'DOI', 'URL', 'Citation'],
        ...filteredResults.map((paper) => [
          paper.title,
          (paper.authors || []).join('; '),
          String(parseYear(paper.published) || ''),
          SOURCE_LABELS[String(paper.source || '').toLowerCase()] || paper.source || 'Unknown',
          paper.doi || '',
          paper.url || '',
          buildCitation(paper, citationStyle),
        ]),
      ];

      content = rows
        .map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(','))
        .join('\n');
      mime = 'text/csv;charset=utf-8';
      ext = 'csv';
    } else {
      content = filteredResults
        .map((paper, index) => `${index + 1}. ${buildCitation(paper, citationStyle)}`)
        .join('\n\n');
    }

    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `researchhub-citations.${ext}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <Layout>
      <section className="space-y-6">
        <div className="rounded-3xl border border-slate-200 bg-white/90 p-6 shadow-sm">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500 mb-1 flex items-center gap-2">
                <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
                Unified Multi-Source Search
              </p>
              <h2 className="text-2xl font-bold text-slate-900">Search Papers</h2>
              <p className="text-sm text-slate-500 mt-1">{statusText}</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => exportCitations('txt')}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50"
              >
                <Download className="h-4 w-4" />
                Export TXT
              </button>
              <button
                type="button"
                onClick={() => exportCitations('csv')}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50"
              >
                <FileText className="h-4 w-4" />
                Export CSV
              </button>
            </div>
          </div>

        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm space-y-5">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
              <input
                ref={inputRef}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    void runSearch(false);
                  }
                }}
                placeholder="Search any research topic"
                className="w-full h-12 rounded-2xl border border-slate-200 bg-white pl-12 pr-4 text-base text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
              />
            </div>
            <button
              type="button"
              onClick={() => void runSearch(false)}
              disabled={loading}
              className="h-12 px-5 rounded-2xl bg-slate-700 hover:bg-slate-800 disabled:bg-slate-400 text-white font-semibold inline-flex items-center gap-2"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              Search
            </button>
            <button
              type="button"
              onClick={saveCurrentQuery}
              className="h-12 px-5 rounded-2xl border border-slate-200 text-slate-700 hover:bg-slate-50 inline-flex items-center gap-2"
            >
              <BookmarkPlus className="h-4 w-4" />
              Save
            </button>
          </div>

          <div className="flex flex-wrap gap-3 items-center">
            <label className="text-sm text-slate-500">Import to</label>
            <select
              value={activeWorkspaceId ?? ''}
              onChange={(event) => setActiveWorkspaceId(event.target.value ? Number(event.target.value) : null)}
              className="h-10 rounded-xl border border-slate-200 px-3 text-sm text-slate-700"
            >
              {workspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name}
                </option>
              ))}
            </select>

            <label className="text-sm text-slate-500 ml-2">Results per page</label>
            <input
              type="range"
              min={SEARCH_MIN_RESULTS}
              max={SEARCH_MAX_RESULTS}
              step={10}
              value={maxResults}
              onChange={(event) => setMaxResults(Number(event.target.value))}
              className="w-44"
            />
            <span className="text-sm font-semibold text-slate-700 w-10">{maxResults}</span>

            <label className="inline-flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={oaOnly} onChange={(event) => setOaOnly(event.target.checked)} />
              OA only
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={pdfOnly} onChange={(event) => setPdfOnly(event.target.checked)} />
              PDF only
            </label>

            <select
              value={yearFilter}
              onChange={(event) => setYearFilter(event.target.value as YearFilter)}
              className="h-10 rounded-xl border border-slate-200 px-3 text-sm text-slate-700"
            >
              <option value="any">Any year</option>
              <option value="2026">2026+</option>
              <option value="2024">2024+</option>
              <option value="2020">2020+</option>
              <option value="2015">2015+</option>
              <option value="2010">2010+</option>
            </select>

            <select
              value={sortMode}
              onChange={(event) => setSortMode(event.target.value as SortMode)}
              className="h-10 rounded-xl border border-slate-200 px-3 text-sm text-slate-700"
            >
              <option value="relevance">Sort: Relevance</option>
              <option value="newest">Sort: Newest</option>
              <option value="oldest">Sort: Oldest</option>
              <option value="title">Sort: Title</option>
            </select>

            <select
              value={citationStyle}
              onChange={(event) => setCitationStyle(event.target.value as CitationStyle)}
              className="h-10 rounded-xl border border-slate-200 px-3 text-sm text-slate-700"
            >
              <option value="apa">Cite: APA</option>
              <option value="mla">Cite: MLA</option>
              <option value="ieee">Cite: IEEE</option>
            </select>
          </div>

          <div className="flex flex-wrap gap-2">
            {QUICK_QUERIES.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => {
                  setQuery(item);
                  void runSearch(false, item);
                }}
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100"
              >
                {item}
              </button>
            ))}
          </div>

          <div className="border-t border-slate-100 pt-3">
            <button
              type="button"
              onClick={() => setShowSavedQueries((prev) => !prev)}
              className="text-sm font-medium text-slate-700 inline-flex items-center gap-2"
            >
              <BookmarkPlus className="h-4 w-4" />
              Saved queries ({savedQueries.length})
            </button>

            {showSavedQueries && (
              <div className="mt-3 flex flex-wrap gap-2">
                {savedQueries.length === 0 && <span className="text-xs text-slate-500">No saved queries yet.</span>}
                {savedQueries.map((item) => (
                  <div key={item.id} className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1">
                    <button
                      type="button"
                      onClick={() => {
                        setQuery(item.query);
                        void runSearch(false, item.query);
                      }}
                      className="text-xs text-slate-700 hover:text-slate-900"
                    >
                      {item.query}
                    </button>
                    <button
                      type="button"
                      onClick={() => removeSavedQuery(item.id)}
                      className="text-xs text-slate-400 hover:text-red-500"
                    >
                      x
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="border-t border-slate-100 pt-3">
            <div className="flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => setShowSearchHistory((prev) => !prev)}
                className="text-sm font-medium text-slate-700 inline-flex items-center gap-2"
              >
                <History className="h-4 w-4" />
                Search history ({searchHistory.length})
              </button>
              {searchHistory.length > 0 && (
                <button
                  type="button"
                  onClick={() => void clearSearchHistory()}
                  className="text-xs text-slate-500 hover:text-red-600 inline-flex items-center gap-1"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Clear
                </button>
              )}
            </div>

            {showSearchHistory && (
              <div className="mt-3 space-y-2">
                {historyLoading && <span className="text-xs text-slate-500">Loading history...</span>}
                {!historyLoading && searchHistory.length === 0 && (
                  <span className="text-xs text-slate-500">No search history yet.</span>
                )}
                {!historyLoading &&
                  searchHistory.map((item) => (
                    <div key={item.id} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                      <div className="flex items-center justify-between gap-3">
                        <button
                          type="button"
                          onClick={() => {
                            setQuery(item.query);
                            void runSearch(false, item.query);
                          }}
                          className="text-sm text-slate-800 hover:text-slate-900 text-left"
                        >
                          {item.query}
                        </button>
                        <button
                          type="button"
                          onClick={() => void removeSearchHistoryItem(item.id)}
                          className="text-xs text-slate-400 hover:text-red-500"
                        >
                          Remove
                        </button>
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                        <span>{formatHistoryTime(item.created_at)}</span>
                        <span>|</span>
                        <span>{item.result_count} results</span>
                        {item.filters && typeof item.filters.max_results === 'number' && (
                          <>
                            <span>|</span>
                            <span>limit {item.filters.max_results}</span>
                          </>
                        )}
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>

        {error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 inline-flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            {error}
          </div>
        )}

        <div className="text-sm text-slate-600">
          Showing {filteredResults.length} of {results.length} merged results
        </div>

        <div className="space-y-4">
          {loading && (
            <div className="rounded-3xl border border-slate-200 bg-white p-8 text-center text-slate-600">
              <Loader2 className="h-6 w-6 animate-spin mx-auto mb-3" />
              Searching connected sources...
            </div>
          )}

          {!loading && filteredResults.length === 0 && (
            <div className="rounded-3xl border border-slate-200 bg-white p-10 text-center text-slate-500">
              No results found. Try broader keywords or loosen filters.
            </div>
          )}

          {!loading &&
            filteredResults.map((paper) => {
              const importKey = normalizeKey(paper);
              const imported = importedSet.has(importKey);
              const sourceKey = String(paper.source || '').toLowerCase();
              const sourceLabel = SOURCE_LABELS[sourceKey] || paper.source || 'Merged source';
              const citation = buildCitation(paper, citationStyle);

              return (
                <article key={importKey} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <h3 className="text-2xl font-semibold text-slate-900 leading-tight mb-2">
                        {paper.title || 'Untitled'}
                      </h3>
                      <p className="text-sm text-slate-600 mb-2">{(paper.authors || []).join(', ') || 'Unknown authors'}</p>
                      <p className="text-slate-700 leading-relaxed line-clamp-4">{paper.abstract || 'No abstract available.'}</p>
                    </div>

                    <div className="flex flex-col items-end gap-2 shrink-0">
                      <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700">{sourceLabel}</span>
                      <button
                        type="button"
                        onClick={() => copyCitation(paper)}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
                      >
                        <Copy className="h-3.5 w-3.5" />
                        Copy Citation
                      </button>
                    </div>
                  </div>

                  <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
                    {paper.published && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                        <Calendar className="h-3.5 w-3.5" />
                        {paper.published}
                      </span>
                    )}
                    {paper.doi && (
                      <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">DOI: {paper.doi}</span>
                    )}
                    {hasPdfLink(paper) && (
                      <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">PDF</span>
                    )}
                    {isLikelyOpenAccess(paper) && (
                      <span className="rounded-full bg-teal-50 px-2.5 py-1 text-teal-700">Open Access</span>
                    )}
                  </div>

                  <p className="mt-3 text-xs text-slate-500 line-clamp-2">{citation}</p>

                  <div className="mt-5 flex flex-wrap gap-2">
                    <a
                      href={paper.url || '#'}
                      target="_blank"
                      rel="noreferrer"
                      className={`inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium ${
                        paper.url
                          ? 'bg-slate-700 text-white hover:bg-slate-800'
                          : 'bg-slate-200 text-slate-500 pointer-events-none'
                      }`}
                    >
                      <ExternalLink className="h-4 w-4" />
                      View Paper
                    </a>

                    {paper.pdf_url && (
                      <a
                        href={paper.pdf_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                      >
                        <FileText className="h-4 w-4" />
                        Open PDF
                      </a>
                    )}

                    <button
                      type="button"
                      onClick={() => void importPaper(paper)}
                      disabled={imported || importingTitle === paper.title || !activeWorkspaceId || loadingImported}
                      className={`inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium ${
                        imported
                          ? 'bg-emerald-100 text-emerald-700'
                          : 'bg-indigo-100 text-indigo-700 hover:bg-indigo-200 disabled:opacity-60'
                      }`}
                    >
                      {importingTitle === paper.title ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : imported ? (
                        <CheckCircle className="h-4 w-4" />
                      ) : (
                        <Plus className="h-4 w-4" />
                      )}
                      {imported ? 'Imported' : 'Import'}
                    </button>
                  </div>
                </article>
              );
            })}
        </div>

        {hasMore && !loading && (
          <div className="flex justify-center pt-2">
            <button
              type="button"
              onClick={() => void runSearch(true)}
              disabled={loadingMore}
              className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-2.5 text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            >
              {loadingMore ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              {loadingMore ? 'Loading...' : 'Load more'}
            </button>
          </div>
        )}
      </section>
    </Layout>
  );
};

export default SearchPapers;
