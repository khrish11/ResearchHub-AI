import React, { useEffect, useMemo, useRef, useState } from 'react';
import api from '../api';
import {
  Search,
  ExternalLink,
  Plus,
  CheckCircle,
  AlertCircle,
  Loader2,
  Tag,
  Calendar,
  Telescope,
  BookOpen,
  Globe2,
  Layers,
  Rocket,
  Sparkles,
  Database,
  ArrowRight,
  Download,
  Copy,
  BookmarkPlus,
  Clock3,
  X,
  Bell,
} from 'lucide-react';
import Layout from '../components/Layout';
import { apiErrorMessage } from '../utils/apiError';
import { useLocation } from 'react-router-dom';

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
  total?: number | null;
  returned?: number;
  offset?: number;
  next_offset?: number;
  has_more?: boolean;
  source?: string;
  notice?: string;
  source_status?: Record<string, { status: string; count?: number; detail?: string }>;
  cache_hit?: boolean;
}

interface SourceCfg {
  label: string;
  icon: React.ReactNode;
  color: string;
  bg: string;
}

type YearFilter = 'any' | '2026' | '2024' | '2020' | '2015';
type CitationStyle = 'apa' | 'mla' | 'ieee';
type SortMode = 'relevance' | 'newest' | 'oldest' | 'title';

interface SavedQuery {
  id: string;
  query: string;
  savedAt: string;
  watchEnabled?: boolean;
  lastTotal?: number | null;
  lastCheckedAt?: string;
  lastDelta?: number;
}

type PaperSource =
  | 'arxiv'
  | 'semantic_scholar'
  | 'semantic_scholar_fallback_arxiv'
  | 'openalex'
  | 'europe_pmc'
  | 'biorxiv'
  | 'medrxiv'
  | 'plos'
  | 'elife'
  | 'pubmed'
  | 'doaj'
  | 'datacite'
  | 'hal'
  | 'springer'
  | 'nasa_ads'
  | 'unknown';

const SOURCE_META: Record<PaperSource, SourceCfg> = {
  arxiv: {
    label: 'ArXiv',
    icon: <Telescope style={{ width: 14, height: 14 }} />,
    color: '#6366f1',
    bg: 'rgba(99,102,241,0.12)',
  },
  semantic_scholar: {
    label: 'Semantic Scholar',
    icon: <BookOpen style={{ width: 14, height: 14 }} />,
    color: '#059669',
    bg: 'rgba(5,150,105,0.12)',
  },
  semantic_scholar_fallback_arxiv: {
    label: 'Semantic Scholar',
    icon: <BookOpen style={{ width: 14, height: 14 }} />,
    color: '#059669',
    bg: 'rgba(5,150,105,0.12)',
  },
  openalex: {
    label: 'OpenAlex',
    icon: <BookOpen style={{ width: 14, height: 14 }} />,
    color: '#10b981',
    bg: 'rgba(16,185,129,0.12)',
  },
  europe_pmc: {
    label: 'Europe PMC',
    icon: <Globe2 style={{ width: 14, height: 14 }} />,
    color: '#f59e0b',
    bg: 'rgba(245,158,11,0.12)',
  },
  biorxiv: {
    label: 'bioRxiv',
    icon: <BookOpen style={{ width: 14, height: 14 }} />,
    color: '#84cc16',
    bg: 'rgba(132,204,22,0.12)',
  },
  medrxiv: {
    label: 'medRxiv',
    icon: <BookOpen style={{ width: 14, height: 14 }} />,
    color: '#22c55e',
    bg: 'rgba(34,197,94,0.12)',
  },
  plos: {
    label: 'PLOS',
    icon: <Globe2 style={{ width: 14, height: 14 }} />,
    color: '#f97316',
    bg: 'rgba(249,115,22,0.12)',
  },
  elife: {
    label: 'eLife',
    icon: <Globe2 style={{ width: 14, height: 14 }} />,
    color: '#14b8a6',
    bg: 'rgba(20,184,166,0.12)',
  },
  pubmed: {
    label: 'PubMed',
    icon: <BookOpen style={{ width: 14, height: 14 }} />,
    color: '#0ea5e9',
    bg: 'rgba(14,165,233,0.12)',
  },
  doaj: {
    label: 'DOAJ',
    icon: <Globe2 style={{ width: 14, height: 14 }} />,
    color: '#f97316',
    bg: 'rgba(249,115,22,0.12)',
  },
  datacite: {
    label: 'DataCite',
    icon: <Layers style={{ width: 14, height: 14 }} />,
    color: '#06b6d4',
    bg: 'rgba(6,182,212,0.12)',
  },
  hal: {
    label: 'HAL',
    icon: <Globe2 style={{ width: 14, height: 14 }} />,
    color: '#9333ea',
    bg: 'rgba(147,51,234,0.12)',
  },
  springer: {
    label: 'Springer Nature',
    icon: <Layers style={{ width: 14, height: 14 }} />,
    color: '#ec4899',
    bg: 'rgba(236,72,153,0.12)',
  },
  nasa_ads: {
    label: 'NASA ADS',
    icon: <Rocket style={{ width: 14, height: 14 }} />,
    color: '#0ea5e9',
    bg: 'rgba(14,165,233,0.12)',
  },
  unknown: {
    label: 'Merged Source',
    icon: <Globe2 style={{ width: 14, height: 14 }} />,
    color: '#475569',
    bg: 'rgba(71,85,105,0.12)',
  },
};

const GLOBAL_SEARCH_ENDPOINT = '/papers/search-global';
const SEARCH_DEFAULT_RESULTS = 60;
const SEARCH_MAX_RESULTS = 120;
const SEARCH_MIN_RESULTS = 20;
const SAVED_QUERIES_STORAGE_KEY = 'researchhub.saved_queries.v1';
const MAX_SAVED_QUERIES = 12;

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

const OPEN_ACCESS_SOURCES = new Set([
  'arxiv',
  'europe_pmc',
  'doaj',
  'hal',
  'biorxiv',
  'medrxiv',
  'plos',
  'elife',
]);

const loadSavedQueries = (): SavedQuery[] => {
  try {
    const raw = localStorage.getItem(SAVED_QUERIES_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item) => item && typeof item.query === 'string' && typeof item.id === 'string')
      .map((item) => ({
        id: String(item.id),
        query: String(item.query).trim(),
        savedAt: typeof item.savedAt === 'string' ? item.savedAt : '',
        watchEnabled: Boolean(item.watchEnabled),
        lastTotal: typeof item.lastTotal === 'number' ? item.lastTotal : null,
        lastCheckedAt: typeof item.lastCheckedAt === 'string' ? item.lastCheckedAt : '',
        lastDelta: typeof item.lastDelta === 'number' ? item.lastDelta : 0,
      }))
      .filter((item) => item.query.length > 0)
      .slice(0, MAX_SAVED_QUERIES);
  } catch {
    return [];
  }
};

const SearchPapers: React.FC = () => {
  const location = useLocation();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<number | null>(null);

  const [maxResults, setMaxResults] = useState(SEARCH_DEFAULT_RESULTS);

  const [totalResults, setTotalResults] = useState<number | null>(null);
  const [nextOffset, setNextOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [pdfOnly, setPdfOnly] = useState(false);
  const [oaOnly, setOaOnly] = useState(false);
  const [yearFilter, setYearFilter] = useState<YearFilter>('any');
  const [sourceStatus, setSourceStatus] = useState<SearchResponse['source_status']>({});
  const [cacheHit, setCacheHit] = useState(false);
  const [copyState, setCopyState] = useState<string | null>(null);
  const [citationStyle, setCitationStyle] = useState<CitationStyle>('apa');
  const [sortMode, setSortMode] = useState<SortMode>('relevance');
  const [savedQueries, setSavedQueries] = useState<SavedQuery[]>(() => loadSavedQueries());
  const [liveMessage, setLiveMessage] = useState('Ready. Search across all connected sources.');
  const [watchScanLoading, setWatchScanLoading] = useState(false);

  const [importedSet, setImportedSet] = useState<Set<string>>(new Set());
  const [importingTitle, setImportingTitle] = useState<string | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const activeControllerRef = useRef<AbortController | null>(null);
  const autoRunKeyRef = useRef<string>('');

  const globalSrc = SOURCE_META.unknown;

  useEffect(() => {
    api
      .get('/workspaces/')
      .then(async (res) => {
        const wsList: Workspace[] = res.data;
        setWorkspaces(wsList);
        if (wsList.length > 0) {
          setActiveWorkspaceId(wsList[0].id);
          return;
        }
        const defaultWs = await api.post('/workspaces/', {
          name: 'My Research Workspace',
          description: 'Default workspace for organizing research papers',
        });
        setWorkspaces([defaultWs.data]);
        setActiveWorkspaceId(defaultWs.data.id);
      })
      .catch(() => {
        setWorkspaces([]);
      });
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(SAVED_QUERIES_STORAGE_KEY, JSON.stringify(savedQueries));
    } catch {
      // Ignore storage failures (private mode/quota); feature remains non-blocking.
    }
  }, [savedQueries]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const inEditable =
        !!target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable);

      if (!inEditable && event.key === '/' && !event.metaKey && !event.ctrlKey && !event.altKey) {
        event.preventDefault();
        searchInputRef.current?.focus();
      }

      if (event.key === 'Escape' && activeControllerRef.current) {
        activeControllerRef.current.abort();
        setLiveMessage('Search canceled.');
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      activeControllerRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const qParam = (params.get('q') || '').trim();
    const autoRun = params.get('autorun') === '1';
    const key = `${qParam}|${autoRun ? '1' : '0'}`;
    if (!qParam) {
      return;
    }
    if (query !== qParam) {
      setQuery(qParam);
    }
    if (autoRun && autoRunKeyRef.current !== key) {
      autoRunKeyRef.current = key;
      void runSearch(0, false, qParam);
    }
  }, [location.search]);

  const formatTotal = useMemo(() => {
    if (typeof totalResults !== 'number') {
      return `${results.length}`;
    }
    return totalResults.toLocaleString();
  }, [results.length, totalResults]);

  const sourceHealthSummary = useMemo(() => {
    const entries = Object.values(sourceStatus || {});
    if (!entries.length) {
      return null;
    }
    const contributing = entries.filter((item) => Number(item?.count || 0) > 0).length;
    return {
      contributing,
      total: entries.length,
    };
  }, [sourceStatus]);

  const paperYear = (paper: Paper): number | null => {
    const m = String(paper.published || '').match(/(19|20)\d{2}/);
    if (!m) return null;
    const year = Number(m[0]);
    return Number.isFinite(year) ? year : null;
  };

  const hasPdf = (paper: Paper): boolean =>
    Boolean(paper.pdf_url) || Boolean(paper.url && paper.url.toLowerCase().endsWith('.pdf'));

  const isOpenAccess = (paper: Paper): boolean => {
    if (hasPdf(paper)) return true;
    const src = String(paper.source || '').toLowerCase();
    if (OPEN_ACCESS_SOURCES.has(src)) return true;
    const url = String(paper.url || '').toLowerCase();
    return url.includes('arxiv.org') || url.includes('pmc') || url.includes('doi.org/10.1101/');
  };

  const visibleResults = useMemo(() => {
    const filtered = results.filter((paper) => {
      if (pdfOnly && !hasPdf(paper)) return false;
      if (oaOnly && !isOpenAccess(paper)) return false;
      if (yearFilter !== 'any') {
        const y = paperYear(paper);
        if (!y || y < Number(yearFilter)) return false;
      }
      return true;
    });

    if (sortMode === 'relevance') {
      return filtered;
    }

    const sorted = [...filtered];
    if (sortMode === 'newest') {
      sorted.sort((a, b) => (paperYear(b) || 0) - (paperYear(a) || 0));
      return sorted;
    }
    if (sortMode === 'oldest') {
      sorted.sort((a, b) => (paperYear(a) || 0) - (paperYear(b) || 0));
      return sorted;
    }
    sorted.sort((a, b) => String(a.title || '').localeCompare(String(b.title || '')));
    return sorted;
  }, [results, pdfOnly, oaOnly, yearFilter, sortMode]);

  const hasActiveFilters = pdfOnly || oaOnly || yearFilter !== 'any';
  const watchedQueries = useMemo(
    () => savedQueries.filter((item) => Boolean(item.watchEnabled)),
    [savedQueries]
  );

  const formatRelativeTime = (isoTime?: string) => {
    if (!isoTime) return 'Never';
    const parsed = Date.parse(isoTime);
    if (!Number.isFinite(parsed)) return 'Never';
    const seconds = Math.max(0, Math.floor((Date.now() - parsed) / 1000));
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  const getPaperSourceMeta = (paper: Paper): SourceCfg => {
    const src = (paper.source || '').toLowerCase();
    if (src === 'arxiv') {
      return SOURCE_META.arxiv;
    }
    if (src === 'semantic_scholar' || src === 'semantic_scholar_fallback_arxiv') {
      return SOURCE_META.semantic_scholar;
    }
    if (src === 'openalex') {
      return SOURCE_META.openalex;
    }
    if (src === 'europe_pmc') {
      return SOURCE_META.europe_pmc;
    }
    if (src === 'biorxiv') {
      return SOURCE_META.biorxiv;
    }
    if (src === 'medrxiv') {
      return SOURCE_META.medrxiv;
    }
    if (src === 'plos') {
      return SOURCE_META.plos;
    }
    if (src === 'elife') {
      return SOURCE_META.elife;
    }
    if (src === 'pubmed') {
      return SOURCE_META.pubmed;
    }
    if (src === 'doaj') {
      return SOURCE_META.doaj;
    }
    if (src === 'datacite') {
      return SOURCE_META.datacite;
    }
    if (src === 'hal') {
      return SOURCE_META.hal;
    }
    if (src === 'springer') {
      return SOURCE_META.springer;
    }
    if (src === 'nasa_ads') {
      return SOURCE_META.nasa_ads;
    }
    return SOURCE_META.unknown;
  };

  const buildSearchParams = (searchText: string, offset: number) => {
    const params = new URLSearchParams({
      query: searchText.trim(),
      max_results: String(maxResults),
      offset: String(offset),
    });
    return params;
  };

  const setSearchUrlState = (searchText: string, autoRun = false) => {
    const next = new URLSearchParams(window.location.search);
    if (searchText.trim()) {
      next.set('q', searchText.trim());
      if (autoRun) {
        next.set('autorun', '1');
      } else {
        next.delete('autorun');
      }
    } else {
      next.delete('q');
      next.delete('autorun');
    }
    const queryString = next.toString();
    const nextUrl = `${window.location.pathname}${queryString ? `?${queryString}` : ''}`;
    window.history.replaceState({}, document.title, nextUrl);
  };

  const runSearch = async (offset: number, append: boolean, searchText = query) => {
    const normalizedQuery = searchText.trim();
    if (!normalizedQuery) {
      return;
    }

    if (activeControllerRef.current) {
      activeControllerRef.current.abort();
    }
    const controller = new AbortController();
    activeControllerRef.current = controller;

    if (append) {
      setLoadingMore(true);
    } else {
      setLoading(true);
      setResults([]);
      setImportedSet(new Set());
      setTotalResults(null);
      setNextOffset(0);
      setHasMore(false);
    }
    setError(null);
    setNotice(null);
    setLiveMessage(`Searching all connected sources for "${normalizedQuery}"...`);

    try {
      const params = buildSearchParams(normalizedQuery, offset);
      const res = await api.get<SearchResponse>(`${GLOBAL_SEARCH_ENDPOINT}?${params.toString()}`, {
        signal: controller.signal,
      });
      const papers = res.data?.papers || [];
      const returned = typeof res.data?.returned === 'number' ? res.data.returned : papers.length;
      const responseNextOffset =
        typeof res.data?.next_offset === 'number' ? res.data.next_offset : offset + returned;
      const responseHasMore =
        typeof res.data?.has_more === 'boolean' ? res.data.has_more : returned >= maxResults;

      setResults((prev) => {
        const merged = append ? [...prev, ...papers] : papers;
        const seen = new Set<string>();
        return merged.filter((paper) => {
          const key = `${paper.title}|${paper.url}`;
          if (seen.has(key)) {
            return false;
          }
          seen.add(key);
          return true;
        });
      });
      setTotalResults(typeof res.data?.total === 'number' ? res.data.total : null);
      setNextOffset(responseNextOffset);
      setHasMore(responseHasMore && papers.length > 0);
      setNotice(res.data?.notice || null);
      setSourceStatus(res.data?.source_status || {});
      setCacheHit(!!res.data?.cache_hit);
      setLiveMessage(
        `Loaded ${papers.length} papers${res.data?.cache_hit ? ' from cache' : ''} for "${normalizedQuery}".`
      );
    } catch (err: unknown) {
      const canceled =
        typeof err === 'object' &&
        err !== null &&
        'code' in err &&
        String((err as { code?: string }).code) === 'ERR_CANCELED';
      if (canceled) {
        if (activeControllerRef.current === controller || !activeControllerRef.current) {
          setLiveMessage('Search canceled.');
        }
        return;
      }
      setError(apiErrorMessage(err, 'Search failed. Please try again.'));
      setLiveMessage('Search failed. Retry with a narrower query.');
    } finally {
      if (activeControllerRef.current === controller) {
        activeControllerRef.current = null;
      }
      if (append) {
        setLoadingMore(false);
      } else {
        setLoading(false);
      }
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setSearchUrlState(query, false);
    await runSearch(0, false);
  };

  const handleLoadMore = async () => {
    if (loadingMore || loading || !hasMore) {
      return;
    }
    await runSearch(nextOffset, true, query);
  };

  const handleImport = async (paper: Paper) => {
    if (!activeWorkspaceId) {
      return;
    }
    setImportingTitle(paper.title);
    try {
      await api.post('/papers/import', {
        title: paper.title,
        authors: paper.authors,
        abstract: paper.abstract,
        url: paper.url,
        doi: paper.doi,
        bibcode: paper.bibcode,
        workspace_id: activeWorkspaceId,
      });
      setImportedSet((prev) => new Set(prev).add(paper.title));
    } finally {
      setImportingTitle(null);
    }
  };

  const clearFilters = () => {
    setPdfOnly(false);
    setOaOnly(false);
    setYearFilter('any');
  };

  const saveCurrentQuery = () => {
    const normalized = query.trim();
    if (!normalized) {
      setCopyState('Type a query to save');
      window.setTimeout(() => setCopyState(null), 1400);
      return;
    }
    setSavedQueries((prev) => {
      const withoutDuplicates = prev.filter(
        (item) => item.query.toLowerCase() !== normalized.toLowerCase()
      );
      const next: SavedQuery[] = [
        {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          query: normalized,
          savedAt: new Date().toISOString(),
          watchEnabled: false,
          lastTotal: null,
          lastCheckedAt: '',
          lastDelta: 0,
        },
        ...withoutDuplicates,
      ].slice(0, MAX_SAVED_QUERIES);
      return next;
    });
    setCopyState('Search saved');
    window.setTimeout(() => setCopyState(null), 1400);
  };

  const runSavedSearch = async (savedQuery: string) => {
    setQuery(savedQuery);
    setSearchUrlState(savedQuery, false);
    await runSearch(0, false, savedQuery);
  };

  const removeSavedSearch = (id: string) => {
    setSavedQueries((prev) => prev.filter((item) => item.id !== id));
  };

  const clearSavedSearches = () => {
    setSavedQueries([]);
  };

  const toggleWatchQuery = (id: string) => {
    setSavedQueries((prev) =>
      prev.map((item) =>
        item.id === id
          ? {
              ...item,
              watchEnabled: !item.watchEnabled,
              lastDelta: 0,
            }
          : item
      )
    );
  };

  const scanWatchlistItems = async (items: SavedQuery[]) => {
    if (items.length === 0) {
      setCopyState('No watchlist queries');
      window.setTimeout(() => setCopyState(null), 1600);
      return;
    }

    setWatchScanLoading(true);
    setLiveMessage(`Scanning ${items.length} watchlist quer${items.length === 1 ? 'y' : 'ies'}...`);
    let changedCount = 0;

    try {
      const checks = await Promise.all(
        items.map(async (item) => {
          try {
            const params = buildSearchParams(item.query, 0);
            params.set('max_results', '20');
            const res = await api.get<SearchResponse>(`${GLOBAL_SEARCH_ENDPOINT}?${params.toString()}`);
            const currentTotal =
              typeof res.data?.total === 'number' ? res.data.total : (res.data?.papers || []).length;
            return {
              id: item.id,
              ok: true,
              total: Math.max(0, Number(currentTotal || 0)),
            };
          } catch {
            return {
              id: item.id,
              ok: false,
              total: null as number | null,
            };
          }
        })
      );

      setSavedQueries((prev) =>
        prev.map((entry) => {
          const match = checks.find((item) => item.id === entry.id);
          if (!match || !match.ok || match.total === null) {
            return entry;
          }
          const previousTotal = typeof entry.lastTotal === 'number' ? entry.lastTotal : null;
          const delta = previousTotal === null ? 0 : match.total - previousTotal;
          if (delta > 0) {
            changedCount += 1;
          }
          return {
            ...entry,
            lastTotal: match.total,
            lastCheckedAt: new Date().toISOString(),
            lastDelta: delta,
          };
        })
      );

      setCopyState(
        changedCount > 0
          ? `${changedCount} watchlist quer${changedCount === 1 ? 'y has' : 'ies have'} new papers`
          : 'Watchlist scan complete'
      );
      window.setTimeout(() => setCopyState(null), 2200);
      setLiveMessage('Watchlist scan complete.');
    } finally {
      setWatchScanLoading(false);
    }
  };

  const runWatchlistScan = async () => {
    await scanWatchlistItems(watchedQueries);
  };

  const checkSingleWatch = async (item: SavedQuery) => {
    await scanWatchlistItems([item]);
  };

  const cancelActiveSearch = () => {
    if (activeControllerRef.current) {
      activeControllerRef.current.abort();
      activeControllerRef.current = null;
    }
    setLoading(false);
    setLoadingMore(false);
    setLiveMessage('Search canceled.');
  };

  const citationText = (paper: Paper) => {
    const authorsList = (paper.authors || []).filter(Boolean);
    const authors = authorsList.length ? authorsList.join(', ') : 'Unknown authors';
    const year = paperYear(paper) || 'n.d.';
    const title = paper.title || 'Untitled';
    const venue = paper.publication_title || paper.publication_name || '';
    const link = paper.url || paper.pdf_url || '';

    if (citationStyle === 'mla') {
      const venuePart = venue ? ` ${venue},` : '';
      const yearPart = year ? ` ${year},` : '';
      const linkPart = link ? ` ${link}` : '';
      return `${authors}. "${title}."${venuePart}${yearPart}${linkPart}`.trim();
    }

    if (citationStyle === 'ieee') {
      const venuePart = venue ? `, ${venue}` : '';
      const yearPart = year ? `, ${year}` : '';
      const linkPart = link ? ` [Online]. Available: ${link}` : '';
      return `${authors}, "${title}"${venuePart}${yearPart}.${linkPart}`.trim();
    }

    const core = `${authors} (${year}). ${title}.`;
    const venuePart = venue ? ` ${venue}.` : '';
    const linkPart = link ? ` ${link}` : '';
    return `${core}${venuePart}${linkPart}`.trim();
  };

  const bibtexEntry = (paper: Paper, idx: number) => {
    const firstAuthor = (paper.authors?.[0] || 'author').split(' ').slice(-1)[0].toLowerCase().replace(/[^a-z0-9]/g, '');
    const year = paperYear(paper) || 'nodate';
    const key = `${firstAuthor}${year}${idx + 1}`;
    const title = (paper.title || '').replace(/[{}]/g, '');
    const authors = (paper.authors || []).join(' and ').replace(/[{}]/g, '');
    const venue = (paper.publication_title || paper.publication_name || '').replace(/[{}]/g, '');
    const doi = (paper.doi || '').trim();
    const url = (paper.url || paper.pdf_url || '').trim();
    return [
      `@article{${key},`,
      `  title = {${title}},`,
      `  author = {${authors || 'Unknown'}},`,
      `  year = {${year}},`,
      venue ? `  journal = {${venue}},` : '',
      doi ? `  doi = {${doi}},` : '',
      url ? `  url = {${url}},` : '',
      `}`,
    ]
      .filter(Boolean)
      .join('\n');
  };

  const downloadText = (filename: string, content: string, mime: string) => {
    const blob = new Blob([content], { type: mime });
    const href = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = href;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(href);
  };

  const csvEscape = (value: string) => `"${(value || '').replace(/"/g, '""')}"`;

  const exportCsv = () => {
    const rows = visibleResults.map((paper) => [
      paper.title || '',
      (paper.authors || []).join('; '),
      paper.published || '',
      paper.source || '',
      paper.doi || '',
      paper.pdf_url || '',
      paper.url || '',
      paper.abstract || '',
    ]);
    const header = ['title', 'authors', 'published', 'source', 'doi', 'pdf_url', 'url', 'abstract'];
    const csv = [header, ...rows].map((row) => row.map((cell) => csvEscape(String(cell))).join(',')).join('\n');
    downloadText('research-results.csv', csv, 'text/csv;charset=utf-8');
  };

  const exportBibtex = () => {
    const bib = visibleResults.map((paper, idx) => bibtexEntry(paper, idx)).join('\n\n');
    downloadText('research-results.bib', bib, 'text/plain;charset=utf-8');
  };

  const copyToClipboard = async (text: string, successLabel: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopyState(successLabel);
      window.setTimeout(() => setCopyState(null), 1800);
    } catch {
      setCopyState('Copy failed');
      window.setTimeout(() => setCopyState(null), 1800);
    }
  };

  const copyAllCitations = async () => {
    const text = visibleResults.map((paper) => citationText(paper)).join('\n');
    await copyToClipboard(text, `${citationStyle.toUpperCase()} citations copied`);
  };

  return (
    <Layout>
      <div className="page-enter">
        <div className="search-hero mb-6">
          <div className="search-hero-content">
            <p className="text-xs uppercase tracking-[0.2em] text-indigo-200 mb-2 flex items-center gap-2">
              <Sparkles className="h-3.5 w-3.5" /> Discovery Engine
            </p>
            <h1 className="text-3xl md:text-4xl font-bold text-white leading-tight">
              Search Research Papers at Scale
            </h1>
            <p className="text-indigo-100 mt-2 max-w-2xl">
              Unified search across fourteen live indexes, faster imports, and paged results so you can access
              significantly more papers per query.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="hero-pill">
                <Database className="h-3.5 w-3.5" /> 14 Live Sources
              </span>
              <span className="hero-pill">Up to 120 per page</span>
              <span className="hero-pill">Infinite paging support</span>
              <span className="hero-pill">Press `/` to focus search</span>
            </div>
          </div>
          <div className="orbital-scene" aria-hidden="true">
            <div className="orbital-core" />
            <div className="orbital-ring orbital-ring-a" />
            <div className="orbital-ring orbital-ring-b" />
            <div className="orbital-ring orbital-ring-c" />
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-slate-100 p-5 mb-6" style={{ boxShadow: '0 1px 8px rgba(0,0,0,0.04)' }}>
          <form onSubmit={handleSearch} className="flex flex-col gap-3">
            <div className="flex flex-wrap md:flex-nowrap gap-3">
              <div className="relative flex-grow">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
                  <Search style={{ width: 17, height: 17 }} className="text-slate-400" />
                </div>
                <input
                  ref={searchInputRef}
                  type="text"
                  aria-label="Search research papers"
                  className="block w-full rounded-xl border border-slate-200 py-3 pl-10 pr-4 text-slate-900 placeholder:text-slate-400 focus:outline-none text-sm"
                  style={{ boxShadow: `0 0 0 0px ${globalSrc.color}` }}
                  onFocus={(e) => (e.target.style.boxShadow = `0 0 0 2px ${globalSrc.color}55`)}
                  onBlur={(e) => (e.target.style.boxShadow = '')}
                  placeholder="Try: retrieval augmented generation, exoplanet habitability, battery degradation"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="rounded-xl px-6 py-3 text-sm font-semibold text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 min-w-[120px]"
                style={{ background: `linear-gradient(135deg, ${globalSrc.color}, ${globalSrc.color}bb)` }}
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                Search
              </button>
              <button
                type="button"
                onClick={saveCurrentQuery}
                disabled={!query.trim()}
                className="rounded-xl px-4 py-3 text-sm font-semibold text-slate-700 border border-slate-200 hover:bg-slate-50 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 min-w-[120px]"
              >
                <BookmarkPlus className="h-4 w-4" />
                Save query
              </button>
              {(loading || loadingMore) && (
                <button
                  type="button"
                  onClick={cancelActiveSearch}
                  className="rounded-xl px-4 py-3 text-sm font-semibold text-slate-700 border border-slate-200 hover:bg-slate-50 transition-all flex items-center justify-center gap-2 min-w-[96px]"
                >
                  <X className="h-4 w-4" />
                  Cancel
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 pt-2">
              <div className="flex items-center gap-3">
                <label className="text-sm text-slate-500">Import to:</label>
                <select
                  value={activeWorkspaceId ?? ''}
                  onChange={(e) => setActiveWorkspaceId(e.target.value ? Number(e.target.value) : null)}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 focus:outline-none min-w-[200px]"
                >
                  <option value="">- select workspace -</option>
                  {workspaces.map((workspace) => (
                    <option key={workspace.id} value={workspace.id}>
                      {workspace.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="lg:col-span-2 flex flex-wrap items-center gap-3">
                <label className="text-sm text-slate-500 whitespace-nowrap">Results per page:</label>
                <input
                  type="range"
                  min={SEARCH_MIN_RESULTS}
                  max={SEARCH_MAX_RESULTS}
                  step={5}
                  value={maxResults}
                  onChange={(e) => setMaxResults(Number(e.target.value))}
                  className="w-full"
                />
                <span className="text-sm font-semibold text-slate-700 w-12 text-right">{maxResults}</span>
                <label className="flex items-center gap-2 text-sm text-slate-600 md:ml-2">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-slate-300 text-indigo-600"
                    checked={oaOnly}
                    onChange={(e) => setOaOnly(e.target.checked)}
                  />
                  OA only
                </label>
                <label className="flex items-center gap-2 text-sm text-slate-600 md:ml-4">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-slate-300 text-indigo-600"
                    checked={pdfOnly}
                    onChange={(e) => setPdfOnly(e.target.checked)}
                  />
                  Only show with PDF
                </label>
                <select
                  value={yearFilter}
                  onChange={(e) => setYearFilter(e.target.value as YearFilter)}
                  className="rounded-lg border border-slate-200 px-2 py-1.5 text-sm text-slate-700 focus:outline-none"
                  title="Minimum publication year"
                >
                  <option value="any">Any year</option>
                  <option value="2026">2026+</option>
                  <option value="2024">2024+</option>
                  <option value="2020">2020+</option>
                  <option value="2015">2015+</option>
                </select>
                <select
                  value={sortMode}
                  onChange={(e) => setSortMode(e.target.value as SortMode)}
                  className="rounded-lg border border-slate-200 px-2 py-1.5 text-sm text-slate-700 focus:outline-none"
                  title="Result ordering"
                >
                  <option value="relevance">Sort: Relevance</option>
                  <option value="newest">Sort: Newest</option>
                  <option value="oldest">Sort: Oldest</option>
                  <option value="title">Sort: Title A-Z</option>
                </select>
                <select
                  value={citationStyle}
                  onChange={(e) => setCitationStyle(e.target.value as CitationStyle)}
                  className="rounded-lg border border-slate-200 px-2 py-1.5 text-sm text-slate-700 focus:outline-none"
                  title="Citation style"
                >
                  <option value="apa">Cite: APA</option>
                  <option value="mla">Cite: MLA</option>
                  <option value="ieee">Cite: IEEE</option>
                </select>
                {hasActiveFilters && (
                  <button
                    type="button"
                    onClick={clearFilters}
                    className="text-xs font-semibold text-slate-600 border border-slate-200 rounded-lg px-2 py-1.5 hover:bg-slate-50"
                  >
                    Clear filters
                  </button>
                )}
              </div>
            </div>

            <div className="pt-2 flex flex-wrap gap-2">
              {QUICK_QUERIES.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => setQuery(q)}
                  className="text-xs px-2.5 py-1.5 rounded-full bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
            {savedQueries.length > 0 && (
              <div className="pt-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-500 flex items-center gap-1.5">
                    <Clock3 className="h-3.5 w-3.5" /> Saved searches
                  </p>
                  <button
                    type="button"
                    onClick={clearSavedSearches}
                    className="text-xs font-semibold text-slate-500 hover:text-slate-700"
                  >
                    Clear all
                  </button>
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {savedQueries.map((item) => (
                    <div key={item.id} className="inline-flex items-center rounded-full border border-slate-200 bg-white pl-3 pr-1 py-1 gap-1">
                      <button
                        type="button"
                        onClick={() => {
                          void runSavedSearch(item.query);
                        }}
                        className="text-xs font-medium text-slate-600 hover:text-slate-800"
                      >
                        {item.query}
                      </button>
                      <button
                        type="button"
                        aria-label={`${item.watchEnabled ? 'Disable' : 'Enable'} watch for ${item.query}`}
                        onClick={() => toggleWatchQuery(item.id)}
                        className={`rounded-full p-1 border ${
                          item.watchEnabled
                            ? 'text-indigo-700 bg-indigo-50 border-indigo-200'
                            : 'text-slate-400 border-transparent hover:text-slate-700 hover:border-slate-200'
                        }`}
                      >
                        <Bell className="h-3 w-3" />
                      </button>
                      <button
                        type="button"
                        aria-label={`Remove saved query ${item.query}`}
                        onClick={() => removeSavedSearch(item.id)}
                        className="text-slate-400 hover:text-slate-700 rounded-full p-1"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {watchedQueries.length > 0 && (
              <div className="pt-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-500 flex items-center gap-1.5">
                    <Bell className="h-3.5 w-3.5" /> Watchlists
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      void runWatchlistScan();
                    }}
                    disabled={watchScanLoading}
                    className="text-xs font-semibold text-slate-700 border border-slate-200 rounded-lg px-2.5 py-1.5 hover:bg-slate-50 disabled:opacity-50"
                  >
                    {watchScanLoading ? 'Scanning...' : 'Run watchlist scan'}
                  </button>
                </div>
                <div className="mt-2 space-y-2">
                  {watchedQueries.map((item) => (
                    <div
                      key={`watch-${item.id}`}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-slate-700 truncate">{item.query}</p>
                        <p className="text-xs text-slate-500">
                          Last check: {formatRelativeTime(item.lastCheckedAt)} · Total:{' '}
                          {typeof item.lastTotal === 'number' ? item.lastTotal : '--'}
                          {typeof item.lastDelta === 'number' && item.lastDelta > 0 ? ` · +${item.lastDelta} new` : ''}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            void runSavedSearch(item.query);
                          }}
                          className="text-xs font-semibold text-slate-700 border border-slate-200 rounded-lg px-2 py-1 hover:bg-white"
                        >
                          Open
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            void checkSingleWatch(item);
                          }}
                          className="text-xs font-semibold text-slate-700 border border-slate-200 rounded-lg px-2 py-1 hover:bg-white"
                        >
                          Check now
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="text-xs text-slate-500 pt-1">Status: {liveMessage}</div>
          </form>
        </div>

        {error && (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 border border-red-100">
            <span className="inline-flex items-center gap-2">
              <AlertCircle className="h-4 w-4 flex-shrink-0" /> {error}
            </span>
            <button
              type="button"
              onClick={() => {
                void runSearch(0, false, query);
              }}
              disabled={!query.trim()}
              className="text-xs font-semibold text-red-700 border border-red-200 rounded-lg px-2 py-1 hover:bg-red-100 disabled:opacity-50"
            >
              Retry
            </button>
          </div>
        )}

        {notice && (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800 border border-amber-200">
            <span className="inline-flex items-center gap-2">
              <AlertCircle className="h-4 w-4 flex-shrink-0" /> {notice}
            </span>
            <button
              type="button"
              onClick={() => setNotice(null)}
              className="text-xs font-semibold text-amber-800 border border-amber-300 rounded-lg px-2 py-1 hover:bg-amber-100"
            >
              Dismiss
            </button>
          </div>
        )}

        <p className="sr-only" aria-live="polite">
          {liveMessage}
        </p>

        {!loading && visibleResults.length > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
            <p className="text-sm text-slate-500 font-medium">
              Showing <span className="font-semibold text-slate-700">{visibleResults.length}</span> of{' '}
              <span className="font-semibold" style={{ color: globalSrc.color }}>
                {formatTotal}
              </span>{' '}
              merged results across all connected sources {pdfOnly ? '(PDF only)' : ''}
              {cacheHit ? ' (cached)' : ''} {sortMode !== 'relevance' ? ` - sorted by ${sortMode}` : ''}
              {sourceHealthSummary ? ` - sources contributing: ${sourceHealthSummary.contributing}/${sourceHealthSummary.total}` : ''}
            </p>
            <span
              className="text-xs font-semibold px-3 py-1.5 rounded-full"
              style={{ background: globalSrc.bg, color: globalSrc.color }}
            >
              Unified multi-source search
            </span>
          </div>
        )}

        {!loading && visibleResults.length > 0 && (
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={exportCsv}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50"
            >
              <Download className="h-3.5 w-3.5" /> Export CSV
            </button>
            <button
              type="button"
              onClick={exportBibtex}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50"
            >
              <Download className="h-3.5 w-3.5" /> Export BibTeX
            </button>
            <button
              type="button"
              onClick={copyAllCitations}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50"
            >
              <Copy className="h-3.5 w-3.5" /> Copy {citationStyle.toUpperCase()} citations
            </button>
            {copyState && (
              <span className="text-xs font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-lg px-2.5 py-1.5">
                {copyState}
              </span>
            )}
          </div>
        )}

        {loading && (
          <div className="mb-4 space-y-3">
            <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3">
              <div className="flex items-center text-slate-500 gap-2">
                <Loader2 className="h-4.5 w-4.5 animate-spin" style={{ color: globalSrc.color }} />
                <span className="text-sm">Searching all sources...</span>
              </div>
              <button
                type="button"
                onClick={cancelActiveSearch}
                className="text-xs font-semibold text-slate-600 border border-slate-200 rounded-lg px-2 py-1 hover:bg-slate-50"
              >
                Cancel
              </button>
            </div>
            {[0, 1, 2].map((index) => (
              <div
                key={index}
                className="bg-white rounded-2xl border border-slate-100 p-6 animate-pulse"
                style={{ boxShadow: '0 1px 8px rgba(0,0,0,0.04)' }}
              >
                <div className="h-5 w-2/3 bg-slate-200 rounded mb-4" />
                <div className="h-3.5 w-1/3 bg-slate-200 rounded mb-2" />
                <div className="h-3.5 w-full bg-slate-100 rounded mb-2" />
                <div className="h-3.5 w-5/6 bg-slate-100 rounded mb-4" />
                <div className="flex gap-2">
                  <div className="h-6 w-20 bg-slate-100 rounded-lg" />
                  <div className="h-6 w-24 bg-slate-100 rounded-lg" />
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="space-y-4">
          {visibleResults.map((paper, idx) => {
            const paperSrc = getPaperSourceMeta(paper);
            const imported = importedSet.has(paper.title);
            const isImporting = importingTitle === paper.title;
            return (
              <div
                key={`${paper.title}-${idx}`}
                className="paper-card-3d bg-white rounded-2xl border border-slate-100 p-6 transition-all duration-200"
              >
                <div className="flex items-start justify-between gap-3 mb-2">
                  <h3 className="text-base font-semibold text-slate-900 leading-snug flex-1">{paper.title}</h3>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() =>
                        copyToClipboard(citationText(paper), `${citationStyle.toUpperCase()} citation copied`)
                      }
                      className="flex-shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs font-semibold transition-all border border-slate-200 text-slate-600 hover:bg-slate-50"
                    >
                      <Copy className="h-3.5 w-3.5" /> Cite
                    </button>
                    <button
                      onClick={() => handleImport(paper)}
                      disabled={imported || isImporting || !activeWorkspaceId}
                      className={`flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all border ${
                        imported
                          ? 'bg-emerald-50 text-emerald-600 border-emerald-100 cursor-default'
                          : 'bg-indigo-50 text-indigo-600 border-indigo-100 hover:bg-indigo-100'
                      } disabled:opacity-50`}
                    >
                      {imported ? (
                        <>
                          <CheckCircle className="h-3.5 w-3.5" /> Saved
                        </>
                      ) : isImporting ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Saving...
                        </>
                      ) : (
                        <>
                          <Plus className="h-3.5 w-3.5" /> Import
                        </>
                      )}
                    </button>
                  </div>
                </div>

                <p className="text-sm text-slate-500 mb-2">
                  {paper.authors.slice(0, 4).join(', ')}
                  {paper.authors.length > 4 ? ' et al.' : ''}
                </p>
                <p className="text-sm text-slate-600 line-clamp-3 leading-relaxed">{paper.abstract}</p>

                <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
                  {paper.published && (
                    <span className="flex items-center gap-1 bg-slate-50 text-slate-500 px-2 py-1 rounded-lg">
                      <Calendar className="h-3.5 w-3.5" />
                      {paper.published}
                    </span>
                  )}
                  <span
                    className="flex items-center gap-1 px-2 py-1 rounded-lg font-medium"
                    style={{ background: paperSrc.bg, color: paperSrc.color }}
                  >
                    {paperSrc.icon} {paperSrc.label}
                  </span>
                  {paper.categories.slice(0, 2).map((cat) => (
                    <span key={cat} className="flex items-center gap-1 bg-slate-50 text-slate-500 px-2 py-1 rounded-lg">
                      <Tag className="h-3 w-3" />
                      {cat}
                    </span>
                  ))}

                  {(paper.publication_title || paper.publication_name) && (
                    <span className="flex items-center gap-1 bg-slate-50 text-slate-500 px-2 py-1 rounded-lg text-xs font-medium ml-auto">
                      {paper.publication_title || paper.publication_name}
                    </span>
                  )}

                  {paper.doi && (
                    <a
                      href={`https://doi.org/${paper.doi}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs font-medium ml-2 px-2 py-1 rounded-lg bg-emerald-50 text-emerald-700 hover:underline"
                    >
                      DOI: {paper.doi}
                    </a>
                  )}
                  {paper.bibcode && (
                    <a
                      href={`https://ui.adsabs.harvard.edu/abs/${paper.bibcode}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs font-medium ml-2 px-2 py-1 rounded-lg bg-emerald-50 text-emerald-700 hover:underline"
                    >
                      Bibcode: {paper.bibcode}
                    </a>
                  )}

                  {paper.pdf_url && (
                    <a
                      href={paper.pdf_url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-1 font-medium ml-2 hover:underline text-emerald-700"
                    >
                      PDF <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  )}
                  {paper.url && (
                    <a
                      href={paper.url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-1 font-medium ml-2 hover:underline"
                      style={{ color: paperSrc.color }}
                    >
                      View Paper <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {!loading && !error && hasMore && (
          <div className="mt-6 flex justify-center">
            <button
              onClick={handleLoadMore}
              disabled={loadingMore}
              className="rounded-xl px-5 py-2.5 text-sm font-semibold text-white transition-all disabled:opacity-60 inline-flex items-center gap-2"
              style={{ background: `linear-gradient(135deg, ${globalSrc.color}, ${globalSrc.color}bb)` }}
            >
              {loadingMore ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Loading...
                </>
              ) : (
                <>
                  Load More <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        )}

        {!loading && visibleResults.length === 0 && query && !error && (
          <div className="text-center py-16">
            {results.length > 0 && hasActiveFilters ? (
              <div className="inline-flex flex-col items-center gap-3">
                <p className="text-slate-500">Results exist for "{query}", but none match current filters.</p>
                <button
                  type="button"
                  onClick={clearFilters}
                  className="text-sm font-semibold text-slate-700 border border-slate-200 rounded-lg px-3 py-2 hover:bg-slate-50"
                >
                  Clear filters
                </button>
              </div>
            ) : (
              <div className="inline-flex flex-col items-center gap-2">
                <p className="text-slate-500">No results for "{query}".</p>
                <p className="text-slate-400 text-sm">Try broader keywords, fewer words, or newer/older year ranges.</p>
              </div>
            )}
          </div>
        )}
        {!loading && !query && (
          <div className="text-center py-20">
            <div className="w-16 h-16 mx-auto rounded-2xl flex items-center justify-center mb-4" style={{ background: globalSrc.bg }}>
              <Search style={{ width: 28, height: 28, color: globalSrc.color }} />
            </div>
            <p className="text-slate-500 text-base font-medium">Global Paper Search</p>
            <p className="text-slate-400 text-sm mt-1">One query across ArXiv, Semantic Scholar, OpenAlex, Europe PMC, PubMed, DOAJ, DataCite, HAL, bioRxiv, medRxiv, PLOS, eLife, Springer, and NASA ADS.</p>
            <p className="text-slate-400 text-xs mt-2">Shortcut: press "/" to jump to search.</p>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default SearchPapers;
