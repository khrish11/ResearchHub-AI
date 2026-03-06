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
  institutional_url?: string;
  full_text_url?: string;
  full_text_available?: boolean;
  access_type?: string;
  access_label?: string;
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

interface SourceStatusMeta {
  status?: string;
  count?: number;
  detail?: string;
}

interface SearchResponse {
  papers: Paper[];
  returned?: number;
  next_offset?: number;
  has_more?: boolean;
  cache_hit?: boolean;
  duration_ms?: number;
  search_mode?: string;
  source_counts?: Record<string, number>;
  source_status?: Record<string, SourceStatusMeta>;
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

interface SessionStatePayload {
  workspace_id?: number | null;
  last_query?: string | null;
  extra?: Record<string, unknown> | null;
}

interface SourceCatalogEntry {
  key: string;
  label: string;
  family: string;
  setup: string;
  note: string;
}

type YearFilter = 'any' | '2026' | '2024' | '2020' | '2015' | '2010';
type SortMode = 'relevance' | 'newest' | 'oldest' | 'title';
type CitationStyle = 'apa' | 'mla' | 'ieee';
type SearchMode = 'fast' | 'balanced' | 'deep';

const GLOBAL_SEARCH_ENDPOINT = '/papers/search-global';
const SEARCH_MIN_RESULTS = 20;
const SEARCH_MAX_RESULTS = 200;
const SEARCH_DEFAULT_RESULTS = 80;
const SAVED_QUERIES_KEY = 'researchhub.saved_queries.v2';
const LOAD_MORE_MAX_RESULTS = 60;
const INITIAL_RENDER_BATCH = 40;
const RENDER_BATCH_SIZE = 40;

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

const SEARCH_MODE_COPY: Record<SearchMode, string> = {
  fast: 'Front-load the highest-yield sources and return quickly.',
  balanced: 'Blend broad metadata coverage with usable speed.',
  deep: 'Spend more time across the long-tail source network.',
};

const SOURCE_LABELS: Record<string, string> = {
  arxiv: 'ArXiv',
  semantic: 'Semantic Scholar',
  semantic_scholar: 'Semantic Scholar',
  semantic_scholar_fallback_arxiv: 'Semantic Scholar',
  openalex: 'OpenAlex',
  econbiz: 'EconBiz',
  jstage: 'J-STAGE',
  orkg: 'ORKG',
  openaire: 'OpenAIRE',
  figshare: 'Figshare',
  osf: 'OSF Preprints',
  dryad: 'Dryad',
  inspire: 'INSPIRE-HEP',
  dblp: 'DBLP',
  zenodo: 'Zenodo',
  europepmc: 'Europe PMC',
  europe_pmc: 'Europe PMC',
  pmc: 'PMC',
  doaj: 'DOAJ',
  hal: 'HAL',
  biorxiv: 'bioRxiv',
  medrxiv: 'medRxiv',
  plos: 'PLOS',
  elife: 'eLife',
  pubmed: 'PubMed',
  springer: 'Springer',
  crossref: 'Crossref',
  nasa: 'NASA ADS',
  nasa_ads: 'NASA ADS',
  datacite: 'DataCite',
  eric: 'ERIC',
  osti: 'OSTI',
};

const SOURCE_CATALOG: SourceCatalogEntry[] = [
  { key: 'openalex', label: 'OpenAlex', family: 'Scholarly graph', setup: 'Optional mailto', note: 'Broad metadata and citation graph coverage.' },
  { key: 'econbiz', label: 'EconBiz', family: 'Economics', setup: 'Public', note: 'Economics and business literature via official public API.' },
  { key: 'jstage', label: 'J-STAGE', family: 'Japanese journals', setup: 'Public + attribution', note: 'Japanese journal discovery via official J-STAGE WebAPI.' },
  { key: 'orkg', label: 'ORKG', family: 'Knowledge graph', setup: 'Public', note: 'Open Research Knowledge Graph paper entries and linked metadata.' },
  { key: 'semantic', label: 'Semantic Scholar', family: 'Scholarly graph', setup: 'Optional API key', note: 'High-signal ranking and metadata enrichment.' },
  { key: 'arxiv', label: 'ArXiv', family: 'Preprints', setup: 'Public', note: 'Fast open preprint search for technical fields.' },
  { key: 'crossref', label: 'Crossref', family: 'DOI registry', setup: 'Optional mailto', note: 'Cross-publisher DOI metadata and venue coverage.' },
  { key: 'openaire', label: 'OpenAIRE', family: 'Repositories', setup: 'Public', note: 'European repositories and publications.' },
  { key: 'hal', label: 'HAL', family: 'Repositories', setup: 'Public', note: 'French open archive for papers and preprints.' },
  { key: 'zenodo', label: 'Zenodo', family: 'Repositories', setup: 'Public', note: 'Research outputs with strong OA links.' },
  { key: 'figshare', label: 'Figshare', family: 'Repositories', setup: 'Public', note: 'Article and artifact discovery with direct assets.' },
  { key: 'osf', label: 'OSF Preprints', family: 'Preprints', setup: 'Public', note: 'Open preprints and affiliated providers.' },
  { key: 'dryad', label: 'Dryad', family: 'Repositories', setup: 'Public', note: 'Dataset-backed research outputs.' },
  { key: 'datacite', label: 'DataCite', family: 'DOI registry', setup: 'Public', note: 'Research works and persistent identifier metadata.' },
  { key: 'dblp', label: 'DBLP', family: 'Computer science', setup: 'Public', note: 'Computer science publication index.' },
  { key: 'inspire', label: 'INSPIRE-HEP', family: 'Physics', setup: 'Public', note: 'Physics and high-energy literature.' },
  { key: 'nasa', label: 'NASA ADS', family: 'Astronomy', setup: 'Optional token', note: 'Astrophysics and space-science coverage.' },
  { key: 'springer', label: 'Springer', family: 'Publishers', setup: 'Optional API key', note: 'Publisher catalog expansion where keys are available.' },
  { key: 'pubmed', label: 'PubMed', family: 'Biomedical', setup: 'Optional API key', note: 'NCBI biomedical index with strong recall.' },
  { key: 'europepmc', label: 'Europe PMC', family: 'Biomedical', setup: 'Public', note: 'Open biomedical full text and metadata.' },
  { key: 'pmc', label: 'PMC', family: 'Biomedical', setup: 'Public', note: 'PubMed Central full-text archive.' },
  { key: 'doaj', label: 'DOAJ', family: 'Open access', setup: 'Public', note: 'Directory of open access journal articles.' },
  { key: 'plos', label: 'PLOS', family: 'Open access', setup: 'Public', note: 'Open publisher search for life sciences.' },
  { key: 'elife', label: 'eLife', family: 'Open access', setup: 'Public', note: 'Open life-science journal coverage.' },
  { key: 'biorxiv', label: 'bioRxiv', family: 'Preprints', setup: 'Public', note: 'Biology preprints.' },
  { key: 'medrxiv', label: 'medRxiv', family: 'Preprints', setup: 'Public', note: 'Medical preprints.' },
  { key: 'eric', label: 'ERIC', family: 'Education', setup: 'Public', note: 'Education research and policy literature.' },
  { key: 'osti', label: 'OSTI', family: 'Energy / DOE', setup: 'Public', note: 'DOE publications and technical reports.' },
];

const OPERATOR_CHECKLIST = [
  {
    title: 'Set OPENALEX_MAILTO, CROSSREF_MAILTO, and UNPAYWALL_MAILTO',
    impact: 'Moves you into polite pools and improves full-text resolution quality.',
    level: 'Recommended',
  },
  {
    title: 'Add SEMANTIC_SCHOLAR_API_KEY',
    impact: 'Improves Semantic Scholar throughput for heavier usage.',
    level: 'Optional',
  },
  {
    title: 'Add NCBI_API_KEY',
    impact: 'Raises PubMed quota ceiling for biomedical-heavy teams.',
    level: 'Optional',
  },
  {
    title: 'Add NASA_ADS_TOKEN and SPRINGER_META_KEY',
    impact: 'Unlocks astronomy and Springer catalog breadth.',
    level: 'Optional',
  },
  {
    title: 'Add J-STAGE attribution in your deployed source credits',
    impact: 'Their API terms require visible J-STAGE credit when you display their content.',
    level: 'Required',
  },
  {
    title: 'Run scripts/install-git-hooks.ps1 on every workstation',
    impact: 'Keeps the local main-branch push guard enforced on free private GitHub.',
    level: 'Required',
  },
];

const OPEN_ACCESS_SOURCES = new Set([
  'arxiv',
  'europepmc',
  'europe_pmc',
  'pmc',
  'doaj',
  'hal',
  'biorxiv',
  'medrxiv',
  'plos',
  'elife',
  'openalex',
  'pubmed',
  'openaire',
  'figshare',
  'osf',
  'dryad',
  'zenodo',
]);

const SOURCE_ALIASES: Record<string, string> = {
  semantic_scholar: 'semantic',
  semantic_scholar_fallback_arxiv: 'semantic',
  europe_pmc: 'europepmc',
  nasa_ads: 'nasa',
};

const canonicalSourceKey = (value: string): string => {
  const key = String(value || '').trim().toLowerCase();
  return SOURCE_ALIASES[key] || key;
};

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
  if (String(paper.access_type || '').toLowerCase() === 'open_access') {
    return true;
  }
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
  const [statusText, setStatusText] = useState(`Ready. Search across ${SOURCE_CATALOG.length} connected sources.`);

  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<number | null>(null);
  const [importingTitle, setImportingTitle] = useState<string | null>(null);
  const [importedSet, setImportedSet] = useState<Set<string>>(new Set());

  const [maxResults, setMaxResults] = useState(SEARCH_DEFAULT_RESULTS);
  const [searchMode, setSearchMode] = useState<SearchMode>('balanced');
  const [oaOnly, setOaOnly] = useState(false);
  const [pdfOnly, setPdfOnly] = useState(false);
  const [fullTextOnly, setFullTextOnly] = useState(false);
  const [yearFilter, setYearFilter] = useState<YearFilter>('any');
  const [sortMode, setSortMode] = useState<SortMode>('relevance');
  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [citationStyle, setCitationStyle] = useState<CitationStyle>('apa');
  const [bulkImporting, setBulkImporting] = useState(false);
  const [visibleCount, setVisibleCount] = useState(INITIAL_RENDER_BATCH);

  const [nextOffset, setNextOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [sourceStatus, setSourceStatus] = useState<Record<string, SourceStatusMeta>>({});
  const [sourceCounts, setSourceCounts] = useState<Record<string, number>>({});
  const [lastDurationMs, setLastDurationMs] = useState<number | null>(null);
  const [lastCacheHit, setLastCacheHit] = useState(false);

  const [savedQueries, setSavedQueries] = useState<SavedQuery[]>(() => loadSavedQueries());
  const [showSavedQueries, setShowSavedQueries] = useState(false);
  const [searchHistory, setSearchHistory] = useState<SearchHistoryItem[]>([]);
  const [showSearchHistory, setShowSearchHistory] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [loadingImported, setLoadingImported] = useState(false);
  const [resumeQuery, setResumeQuery] = useState<string | null>(null);
  const [institutionalRaw, setInstitutionalRaw] = useState('');
  const [institutionalImporting, setInstitutionalImporting] = useState(false);
  const [showInstitutionalImport, setShowInstitutionalImport] = useState(false);
  const [resolvingAccess, setResolvingAccess] = useState<Record<string, boolean>>({});

  const inputRef = useRef<HTMLInputElement | null>(null);
  const activeControllerRef = useRef<AbortController | null>(null);
  const runIdRef = useRef(0);
  const resultsRef = useRef<Paper[]>([]);

  useEffect(() => {
    resultsRef.current = results;
  }, [results]);

  useEffect(() => {
    let mounted = true;
    const boot = async () => {
      try {
        const [workspaceRes, sessionRes] = await Promise.all([
          api.get<Workspace[]>('/workspaces/'),
          api.get('/workspaces/session-state').catch(() => ({ data: null })),
        ]);
        const list = workspaceRes.data || [];
        const session = (sessionRes?.data || null) as SessionStatePayload | null;
        const preferredWorkspaceId = Number(session?.workspace_id || 0);
        const preferredQuery = String(session?.last_query || '').trim();
        const extra = session?.extra && typeof session.extra === 'object' ? session.extra : {};

        const restoredMax = Number((extra as Record<string, unknown>).maxResults);
        if (Number.isFinite(restoredMax)) {
          setMaxResults(
            Math.min(SEARCH_MAX_RESULTS, Math.max(SEARCH_MIN_RESULTS, Math.round(restoredMax / 10) * 10))
          );
        }
        const restoredMode = String((extra as Record<string, unknown>).searchMode || '').toLowerCase();
        if (restoredMode === 'fast' || restoredMode === 'balanced' || restoredMode === 'deep') {
          setSearchMode(restoredMode);
        }
        const restoredOaOnly = (extra as Record<string, unknown>).oaOnly;
        if (typeof restoredOaOnly === 'boolean') {
          setOaOnly(restoredOaOnly);
        }
        const restoredPdfOnly = (extra as Record<string, unknown>).pdfOnly;
        if (typeof restoredPdfOnly === 'boolean') {
          setPdfOnly(restoredPdfOnly);
        }
        const restoredFullTextOnly = (extra as Record<string, unknown>).fullTextOnly;
        if (typeof restoredFullTextOnly === 'boolean') {
          setFullTextOnly(restoredFullTextOnly);
        }
        const restoredYear = String((extra as Record<string, unknown>).yearFilter || '');
        if (['any', '2026', '2024', '2020', '2015', '2010'].includes(restoredYear)) {
          setYearFilter(restoredYear as YearFilter);
        }
        const restoredSort = String((extra as Record<string, unknown>).sortMode || '');
        if (['relevance', 'newest', 'oldest', 'title'].includes(restoredSort)) {
          setSortMode(restoredSort as SortMode);
        }
        const restoredSourceFilter = canonicalSourceKey(
          String((extra as Record<string, unknown>).sourceFilter || 'all')
        );
        setSourceFilter(restoredSourceFilter || 'all');

        if (list.length > 0) {
          if (!mounted) return;
          setWorkspaces(list);
          const validPreferred = list.some((workspace) => workspace.id === preferredWorkspaceId);
          setActiveWorkspaceId(validPreferred ? preferredWorkspaceId : list[0].id);
          if (preferredQuery) {
            setQuery(preferredQuery);
            setResumeQuery(preferredQuery);
          }
          return;
        }

        const created = await api.post<Workspace>('/workspaces/default', {});
        if (!mounted) return;
        setWorkspaces([created.data]);
        setActiveWorkspaceId(created.data.id);
        if (preferredQuery) {
          setQuery(preferredQuery);
          setResumeQuery(preferredQuery);
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
          searchMode,
          oaOnly,
          pdfOnly,
          fullTextOnly,
          yearFilter,
          sortMode,
          sourceFilter,
        },
      });
    },
    [activeWorkspaceId, fullTextOnly, maxResults, oaOnly, pdfOnly, searchMode, sortMode, sourceFilter, yearFilter],
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
        resultsRef.current = [];
        setVisibleCount(INITIAL_RENDER_BATCH);
        setNextOffset(0);
        setHasMore(false);
        setSourceStatus({});
        setSourceCounts({});
        setLastDurationMs(null);
        setLastCacheHit(false);
      }
      setError(null);
      setStatusText(append ? 'Loading more papers...' : 'Searching all connected sources...');

      try {
        const offset = append ? nextOffset : 0;
        const response = await api.get<SearchResponse>(GLOBAL_SEARCH_ENDPOINT, {
          params: {
            query: finalQuery,
            max_results: append ? Math.min(maxResults, LOAD_MORE_MAX_RESULTS) : maxResults,
            offset,
            search_mode: searchMode,
            track_history: append ? false : true,
          },
          signal: controller.signal,
        });

        if (runId !== runIdRef.current) {
          return;
        }

        const payload = response.data;
        const incoming = payload.papers || [];
        const incomingStatus = payload.source_status || {};
        const incomingCounts = payload.source_counts || {};
        const statusValues = Object.values(incomingStatus);
        const healthySources = statusValues.filter((item) => {
          const status = String(item?.status || '');
          return status === 'ok' || status === 'warning';
        }).length;
        const totalSources = statusValues.length || Object.keys(incomingCounts).length;

        setHasMore(Boolean(payload.has_more));
        setSourceStatus(incomingStatus);
        setSourceCounts(incomingCounts);
        setLastCacheHit(Boolean(payload.cache_hit));
        setLastDurationMs(
          Number.isFinite(Number(payload.duration_ms))
            ? Number(payload.duration_ms)
            : null
        );

        const computedNextOffset =
          typeof payload.next_offset === 'number' ? payload.next_offset : offset + incoming.length;
        setNextOffset(computedNextOffset);

        const base = append ? resultsRef.current : [];
        const merged = mergeUnique(base, incoming);
        setResults(merged);
        resultsRef.current = merged;

        const shownCount = merged.length;
        const cachedTag = payload.cache_hit ? 'cache hit' : 'live';
        const sourceTag = totalSources > 0 ? ` | ${healthySources}/${totalSources} sources` : '';
        const durationTag = Number.isFinite(Number(payload.duration_ms))
          ? ` | ${Number(payload.duration_ms)}ms`
          : '';
        setStatusText(`${cachedTag} | ${shownCount} papers${sourceTag}${durationTag}`);
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
    [fetchSearchHistory, maxResults, mergeUnique, nextOffset, persistSessionState, query, searchMode],
  );

  useEffect(() => {
    if (!resumeQuery || !activeWorkspaceId) {
      return;
    }
    if (loading || loadingMore) {
      return;
    }
    void runSearch(false, resumeQuery);
    setResumeQuery(null);
  }, [activeWorkspaceId, loading, loadingMore, resumeQuery, runSearch]);

  const filteredResults = useMemo(() => {
    let filtered = [...results];

    if (sourceFilter !== 'all') {
      filtered = filtered.filter(
        (paper) => canonicalSourceKey(String(paper.source || '')) === sourceFilter
      );
    }

    if (oaOnly) {
      filtered = filtered.filter((paper) => isLikelyOpenAccess(paper));
    }

    if (pdfOnly) {
      filtered = filtered.filter((paper) => hasPdfLink(paper));
    }

    if (fullTextOnly) {
      filtered = filtered.filter(
        (paper) =>
          Boolean(paper.full_text_available) ||
          Boolean(paper.full_text_url) ||
          hasPdfLink(paper)
      );
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
  }, [fullTextOnly, oaOnly, pdfOnly, results, sortMode, sourceFilter, yearFilter]);

  const sourceStatusEntries = useMemo(() => {
    const entries = Object.entries(sourceStatus);
    if (entries.length > 0) {
      return entries.sort((a, b) => Number(b[1]?.count || 0) - Number(a[1]?.count || 0));
    }
    return Object.entries(sourceCounts)
      .map(([name, count]) => [name, { status: 'ok', count }] as const)
      .sort((a, b) => Number(b[1]?.count || 0) - Number(a[1]?.count || 0));
  }, [sourceCounts, sourceStatus]);

  const sourceFilterOptions = useMemo(() => {
    const seen = new Set<string>();
    return sourceStatusEntries
      .map(([name, meta]) => {
        const canonical = canonicalSourceKey(name);
        if (!canonical || canonical === 'all' || seen.has(canonical)) {
          return null;
        }
        seen.add(canonical);
        return {
          value: canonical,
          label: SOURCE_LABELS[canonical] || SOURCE_LABELS[name] || name,
          count: Number(meta?.count || 0),
        };
      })
      .filter((item): item is { value: string; label: string; count: number } => Boolean(item))
      .sort((a, b) => b.count - a.count);
  }, [sourceStatusEntries]);

  const sourceStatusByCanonical = useMemo(() => {
    const mapped: Record<string, SourceStatusMeta> = {};
    Object.entries(sourceStatus).forEach(([name, meta]) => {
      const key = canonicalSourceKey(name);
      if (!key) return;
      const count = Number(meta?.count || 0);
      const existing = mapped[key];
      if (!existing || count >= Number(existing.count || 0)) {
        mapped[key] = {
          status: meta?.status,
          count,
          detail: meta?.detail,
        };
      }
    });
    return mapped;
  }, [sourceStatus]);

  const sourceCountsByCanonical = useMemo(() => {
    const mapped: Record<string, number> = {};
    Object.entries(sourceCounts).forEach(([name, count]) => {
      const key = canonicalSourceKey(name);
      if (!key) return;
      mapped[key] = Math.max(mapped[key] || 0, Number(count || 0));
    });
    Object.entries(sourceStatusByCanonical).forEach(([name, meta]) => {
      mapped[name] = Math.max(mapped[name] || 0, Number(meta?.count || 0));
    });
    return mapped;
  }, [sourceCounts, sourceStatusByCanonical]);

  const sourceAtlasCards = useMemo(
    () =>
      SOURCE_CATALOG.map((entry) => {
        const meta = sourceStatusByCanonical[entry.key];
        const count = Number(sourceCountsByCanonical[entry.key] || 0);
        return {
          ...entry,
          count,
          status: String(meta?.status || (count > 0 ? 'ok' : 'idle')).toLowerCase(),
          detail: String(meta?.detail || entry.note),
        };
      }),
    [sourceCountsByCanonical, sourceStatusByCanonical],
  );

  useEffect(() => {
    if (sourceFilter === 'all') {
      return;
    }
    if (!sourceFilterOptions.some((item) => item.value === sourceFilter)) {
      setSourceFilter('all');
    }
  }, [sourceFilter, sourceFilterOptions]);

  const renderedResults = useMemo(
    () => filteredResults.slice(0, Math.max(INITIAL_RENDER_BATCH, visibleCount)),
    [filteredResults, visibleCount],
  );
  const canRenderMore = renderedResults.length < filteredResults.length;
  const knownSourceCount = SOURCE_CATALOG.length;
  const respondingSourceCount = sourceAtlasCards.filter((item) => ['ok', 'warning'].includes(item.status)).length;
  const activeResultSourceCount = sourceAtlasCards.filter((item) => item.count > 0).length;
  const openAccessCount = filteredResults.filter((paper) => isLikelyOpenAccess(paper)).length;
  const fullTextCount = filteredResults.filter(
    (paper) => Boolean(paper.full_text_available) || Boolean(paper.full_text_url) || hasPdfLink(paper),
  ).length;
  const recentResultCount = filteredResults.filter((paper) => parseYear(paper.published) >= 2024).length;
  const importReadyCount = renderedResults.filter((paper) => !importedSet.has(normalizeKey(paper))).length;
  const highlightedAtlasCards = sourceAtlasCards.filter((item) => item.count > 0).slice(0, 6);

  const maxResultsCap = useMemo(() => {
    if (searchMode === 'fast') return 100;
    if (searchMode === 'deep') return 200;
    return 140;
  }, [searchMode]);

  useEffect(() => {
    setMaxResults((prev) => Math.min(prev, maxResultsCap));
  }, [maxResultsCap]);

  useEffect(() => {
    setVisibleCount(INITIAL_RENDER_BATCH);
  }, [oaOnly, pdfOnly, fullTextOnly, yearFilter, sortMode, sourceFilter]);

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

  const buildImportPayload = useCallback(
    (paper: Paper, workspaceId: number) => ({
      title: paper.title,
      authors: paper.authors || [],
      abstract: paper.abstract || '',
      url: paper.url || '',
      doi: paper.doi || '',
      bibcode: paper.bibcode || '',
      source: paper.source || 'global_merged',
      pdf_url: paper.pdf_url || paper.full_text_url || '',
      institutional_url: paper.institutional_url || '',
      access_type: paper.access_type || '',
      full_text_available: Boolean(paper.full_text_available || paper.full_text_url || paper.pdf_url),
      workspace_id: workspaceId,
    }),
    []
  );

  const importPaper = async (paper: Paper) => {
    if (!activeWorkspaceId) {
      toastError('Select a workspace before importing papers.');
      return;
    }

    setImportingTitle(paper.title);
    try {
      await api.post('/papers/import', buildImportPayload(paper, activeWorkspaceId));
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

  const importTopVisible = async (limit: number) => {
    if (!activeWorkspaceId) {
      toastError('Select a workspace before importing papers.');
      return;
    }
    if (bulkImporting) return;

    const candidates = renderedResults
      .filter((paper) => !importedSet.has(normalizeKey(paper)))
      .slice(0, Math.max(1, limit));

    if (candidates.length === 0) {
      toastError('No new visible papers to import.');
      return;
    }

    setBulkImporting(true);
    const queue = [...candidates];
    const importedKeys: string[] = [];
    let created = 0;
    let updated = 0;
    let failed = 0;
    const workerCount = Math.min(5, queue.length);

    const workers = Array.from({ length: workerCount }, async () => {
      while (queue.length > 0) {
        const next = queue.shift();
        if (!next) break;
        try {
          const response = await api.post('/papers/import', buildImportPayload(next, activeWorkspaceId));
          const updatedRow = Boolean(response.data?.updated);
          if (updatedRow) updated += 1;
          else created += 1;
          importedKeys.push(normalizeKey(next));
        } catch {
          failed += 1;
        }
      }
    });

    await Promise.all(workers);
    if (importedKeys.length > 0) {
      setImportedSet((prev) => {
        const next = new Set(prev);
        for (const key of importedKeys) next.add(key);
        return next;
      });
      await api
        .put('/workspaces/session-state', {
          page_path: '/search',
          workspace_id: activeWorkspaceId,
          last_query: query.trim(),
        })
        .catch(() => undefined);
    }
    setBulkImporting(false);

    if (failed > 0) {
      toastError(`Imported ${created} new, updated ${updated}, failed ${failed}`);
      return;
    }
    toastSuccess(`Imported ${created} new papers, updated ${updated}`);
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

  const resolvePaperAccess = async (paper: Paper) => {
    const key = normalizeKey(paper);
    setResolvingAccess((prev) => ({ ...prev, [key]: true }));
    try {
      const response = await api.post('/papers/resolve-access', {
        source: paper.source || 'global_merged',
        title: paper.title,
        doi: paper.doi || undefined,
        url: paper.url || undefined,
        pdf_url: paper.pdf_url || undefined,
        institutional_url: paper.institutional_url || undefined,
      });
      const resolved = response.data?.resolved || {};
      setResults((prev) =>
        prev.map((item) => {
          if (normalizeKey(item) !== key) return item;
          return {
            ...item,
            doi: resolved.doi || item.doi,
            pdf_url: resolved.pdf_url || item.pdf_url,
            institutional_url: resolved.institutional_url || item.institutional_url,
            full_text_url: resolved.full_text_url || item.full_text_url || resolved.pdf_url || item.pdf_url,
            full_text_available:
              typeof resolved.full_text_available === 'boolean'
                ? resolved.full_text_available
                : item.full_text_available,
            access_type: resolved.access_type || item.access_type,
            access_label: resolved.access_label || item.access_label,
          };
        })
      );
      toastSuccess('Access status refreshed');
    } catch (err: unknown) {
      toastError(apiErrorMessage(err, 'Failed to resolve paper access.'));
    } finally {
      setResolvingAccess((prev) => ({ ...prev, [key]: false }));
    }
  };

  const importInstitutionalList = async () => {
    if (!activeWorkspaceId) {
      toastError('Select a workspace first.');
      return;
    }
    if (!institutionalRaw.trim()) {
      toastError('Paste at least one institutional paper entry.');
      return;
    }

    setInstitutionalImporting(true);
    try {
      const response = await api.post('/papers/import-institutional', {
        workspace_id: activeWorkspaceId,
        source_name: 'institutional_portal',
        raw_text: institutionalRaw,
      });
      const imported = Number(response.data?.imported || 0);
      const updated = Number(response.data?.updated || 0);
      toastSuccess(`Institutional import complete: ${imported} new, ${updated} updated`);
      setInstitutionalRaw('');

      const wsRes = await api.get(`/workspaces/${activeWorkspaceId}`);
      const existingPapers: Array<{
        title: string;
        doi?: string;
        url?: string;
        abstract?: string;
      }> = wsRes.data?.papers || [];
      const next = new Set<string>();
      existingPapers.forEach((entry) => {
        const token = normalizeKey({
          title: String(entry.title || ''),
          authors: [],
          abstract: String(entry.abstract || ''),
          url: String(entry.url || ''),
          doi: String(entry.doi || ''),
          published: '',
          categories: [],
        });
        next.add(token);
      });
      setImportedSet(next);
    } catch (err: unknown) {
      toastError(apiErrorMessage(err, 'Institutional import failed.'));
    } finally {
      setInstitutionalImporting(false);
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
      <section className="space-y-6 pb-8">
        <div className="overflow-hidden rounded-[32px] border border-slate-200 bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.16),_transparent_30%),radial-gradient(circle_at_bottom_right,_rgba(34,197,94,0.14),_transparent_28%),linear-gradient(135deg,_rgba(255,255,255,0.98),_rgba(248,250,252,0.94))] shadow-[0_28px_90px_-48px_rgba(15,23,42,0.45)]">
          <div className="grid gap-6 p-6 md:p-8 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
            <div className="space-y-5">
              <div>
                <p className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.28em] text-slate-500">
                  <Sparkles className="h-3.5 w-3.5 text-sky-600" />
                  Unified Multi-Source Search
                </p>
                <h2 className="max-w-3xl text-3xl font-semibold tracking-tight text-slate-950 md:text-4xl">
                  Search across the strongest public research paper rails in one place.
                </h2>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600" role="status" aria-live="polite">
                  {statusText}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
                <span className="rounded-full border border-slate-200 bg-white/80 px-3 py-1">
                  Mode: <span className="font-semibold text-slate-900">{searchMode}</span>
                </span>
                <span className="rounded-full border border-slate-200 bg-white/80 px-3 py-1">
                  {SEARCH_MODE_COPY[searchMode]}
                </span>
                <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-emerald-700">
                  New public additions live: ERIC + OSTI + PMC + EconBiz + J-STAGE + ORKG
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => exportCitations('txt')}
                  className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-slate-700 hover:bg-white"
                >
                  <Download className="h-4 w-4" />
                  Export TXT
                </button>
                <button
                  type="button"
                  onClick={() => exportCitations('csv')}
                  className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-slate-700 hover:bg-white"
                >
                  <FileText className="h-4 w-4" />
                  Export CSV
                </button>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-3xl border border-white/70 bg-white/80 p-4 shadow-sm">
                <p className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Source Rails</p>
                <p className="mt-2 text-3xl font-semibold text-slate-950">{knownSourceCount}</p>
                <p className="mt-1 text-sm text-slate-600">Canonical paper sources wired into search.</p>
              </div>
              <div className="rounded-3xl border border-white/70 bg-white/80 p-4 shadow-sm">
                <p className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Responding Now</p>
                <p className="mt-2 text-3xl font-semibold text-slate-950">
                  {respondingSourceCount}
                  <span className="ml-1 text-lg text-slate-400">/ {knownSourceCount}</span>
                </p>
                <p className="mt-1 text-sm text-slate-600">Sources with live or warning state in the current run.</p>
              </div>
              <div className="rounded-3xl border border-white/70 bg-white/80 p-4 shadow-sm">
                <p className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Open Access In View</p>
                <p className="mt-2 text-3xl font-semibold text-slate-950">{openAccessCount}</p>
                <p className="mt-1 text-sm text-slate-600">Filtered results that look openly accessible.</p>
              </div>
              <div className="rounded-3xl border border-white/70 bg-white/80 p-4 shadow-sm">
                <p className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Full Text Ready</p>
                <p className="mt-2 text-3xl font-semibold text-slate-950">{fullTextCount}</p>
                <p className="mt-1 text-sm text-slate-600">Records with full text or direct PDF paths.</p>
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(330px,0.85fr)]">
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-[0_20px_70px_-45px_rgba(15,23,42,0.45)] space-y-5">
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
                aria-label="Search papers by topic"
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

            <div className="rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3 text-sm text-slate-600">
              Use <span className="font-semibold text-slate-900">Fast</span> for quick scouting,{' '}
              <span className="font-semibold text-slate-900">Balanced</span> for daily work, and{' '}
              <span className="font-semibold text-slate-900">Deep</span> when you want wider recall across the long tail.
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
              max={maxResultsCap}
              step={10}
              value={maxResults}
              onChange={(event) => setMaxResults(Number(event.target.value))}
              className="w-44"
            />
            <span className="text-sm font-semibold text-slate-700 w-10">{maxResults}</span>

            <label className="text-sm text-slate-500 ml-2">Mode</label>
            <select
              value={searchMode}
              onChange={(event) => setSearchMode(event.target.value as SearchMode)}
              className="h-10 rounded-xl border border-slate-200 px-3 text-sm text-slate-700"
            >
              <option value="fast">Fast</option>
              <option value="balanced">Balanced</option>
              <option value="deep">Deep (more papers)</option>
            </select>

            <label className="inline-flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={oaOnly} onChange={(event) => setOaOnly(event.target.checked)} />
              OA only
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={pdfOnly} onChange={(event) => setPdfOnly(event.target.checked)} />
              PDF only
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={fullTextOnly} onChange={(event) => setFullTextOnly(event.target.checked)} />
              Full text only
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
              value={sourceFilter}
              onChange={(event) => setSourceFilter(canonicalSourceKey(event.target.value) || 'all')}
              className="h-10 rounded-xl border border-slate-200 px-3 text-sm text-slate-700"
            >
              <option value="all">Source: All</option>
              {sourceFilterOptions.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label} ({item.count})
                </option>
              ))}
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
              onClick={() => setShowInstitutionalImport((prev) => !prev)}
              className="text-sm font-medium text-slate-700 inline-flex items-center gap-2"
            >
              <Download className="h-4 w-4" />
              Institutional Import Connector
            </button>

            {showInstitutionalImport && (
              <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs text-slate-600 mb-2">
                  Paste one entry per line in this format: <code>Title | URL | DOI | Author1; Author2</code>
                </p>
                <textarea
                  value={institutionalRaw}
                  onChange={(event) => setInstitutionalRaw(event.target.value)}
                  placeholder="Example: Secure IoT Intrusion Detection | https://publisher.com/paper/123 | 10.1000/example.doi"
                  className="w-full min-h-[120px] rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <div className="mt-2 flex items-center justify-between gap-2">
                  <span className="text-xs text-slate-500">{institutionalRaw.split('\n').filter((line) => line.trim()).length} lines</span>
                  <button
                    type="button"
                    onClick={() => void importInstitutionalList()}
                    disabled={institutionalImporting || !institutionalRaw.trim()}
                    className="inline-flex items-center gap-2 rounded-xl bg-slate-700 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-55"
                  >
                    {institutionalImporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                    Import Institutional Papers
                  </button>
                </div>
              </div>
            )}
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
                      aria-label={`Remove saved query ${item.query}`}
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
                          aria-label={`Remove history query ${item.query}`}
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
          <aside className="space-y-5">
            <div className="rounded-3xl border border-slate-200 bg-slate-950 p-5 text-white shadow-[0_24px_70px_-40px_rgba(15,23,42,0.75)]">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.24em] text-slate-400">From Your Side</p>
                  <h3 className="mt-2 text-xl font-semibold">Operator checklist</h3>
                </div>
                <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-300">
                  Public sources need no key
                </span>
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                The zero-cost additions are already live. Only the optional keyed sources below still depend on your setup.
              </p>
              <div className="mt-4 space-y-3">
                {OPERATOR_CHECKLIST.map((item) => (
                  <div key={item.title} className="rounded-2xl border border-white/10 bg-white/5 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm font-medium text-white">{item.title}</p>
                      <span
                        className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] uppercase tracking-[0.16em] ${
                          item.level === 'Required'
                            ? 'bg-rose-500/15 text-rose-200'
                            : item.level === 'Recommended'
                            ? 'bg-sky-500/15 text-sky-200'
                            : 'bg-slate-700 text-slate-200'
                        }`}
                      >
                        {item.level}
                      </span>
                    </div>
                    <p className="mt-2 text-xs leading-5 text-slate-300">{item.impact}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-[0_18px_60px_-45px_rgba(15,23,42,0.45)]">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Coverage Atlas</p>
                  <h3 className="mt-2 text-xl font-semibold text-slate-900">Source network</h3>
                </div>
                <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600">
                  {activeResultSourceCount} contributing
                </span>
              </div>
              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                {(highlightedAtlasCards.length > 0 ? highlightedAtlasCards : sourceAtlasCards.slice(0, 6)).map((item) => {
                  const isActive = sourceFilter !== 'all' && sourceFilter === item.key;
                  const toneClass =
                    item.status === 'ok'
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                      : item.status === 'warning'
                      ? 'border-amber-200 bg-amber-50 text-amber-800'
                      : item.status === 'timeout' || item.status === 'error'
                      ? 'border-rose-200 bg-rose-50 text-rose-800'
                      : 'border-slate-200 bg-slate-50 text-slate-700';
                  return (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => setSourceFilter(isActive ? 'all' : item.key)}
                      className={`rounded-2xl border p-3 text-left transition hover:-translate-y-0.5 ${toneClass} ${
                        isActive ? 'ring-2 ring-slate-300' : ''
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold">{item.label}</p>
                          <p className="mt-1 text-[11px] uppercase tracking-[0.14em] opacity-75">{item.family}</p>
                        </div>
                        <span className="text-lg font-semibold">{item.count}</span>
                      </div>
                      <p className="mt-2 text-xs leading-5 opacity-85">{item.detail}</p>
                    </button>
                  );
                })}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {SOURCE_CATALOG.map((item) => (
                  <span
                    key={item.key}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] text-slate-600"
                    title={item.note}
                  >
                    {item.label} | {item.setup}
                  </span>
                ))}
              </div>
              <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs leading-5 text-slate-600">
                Includes J-STAGE metadata where available.
                {' '}
                <a
                  href="https://www.jstage.jst.go.jp/"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 font-medium text-slate-900 underline underline-offset-2"
                >
                  Powered by J-STAGE
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>
          </aside>
        </div>

        {error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 inline-flex items-center gap-2" role="alert">
            <AlertCircle className="h-4 w-4" />
            {error}
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
            <span>
              Showing {renderedResults.length} of {filteredResults.length} filtered ({results.length} merged)
            </span>
            {lastDurationMs !== null && (
              <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-500">
                {lastCacheHit ? 'cache' : 'live'} | {lastDurationMs} ms
              </span>
            )}
            <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-500">
              2024+ results: {recentResultCount}
            </span>
            <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-500">
              Ready to import: {importReadyCount}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void importTopVisible(10)}
              disabled={bulkImporting || renderedResults.length === 0 || !activeWorkspaceId}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-55"
            >
              {bulkImporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
              Import Top 10
            </button>
            <button
              type="button"
              onClick={() => void importTopVisible(30)}
              disabled={bulkImporting || renderedResults.length === 0 || !activeWorkspaceId}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-55"
            >
              {bulkImporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
              Import Top 30
            </button>
          </div>
        </div>

        {sourceStatusEntries.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {sourceStatusEntries.map(([name, meta]) => {
              const canonical = canonicalSourceKey(name);
              const sourceName = SOURCE_LABELS[canonical] || SOURCE_LABELS[name] || name;
              const status = String(meta?.status || 'ok').toLowerCase();
              const toneClass =
                status === 'ok'
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : status === 'warning'
                  ? 'bg-amber-50 text-amber-700 border-amber-200'
                  : status === 'timeout' || status === 'error'
                  ? 'bg-rose-50 text-rose-700 border-rose-200'
                  : 'bg-slate-100 text-slate-600 border-slate-200';
              const isActiveSource = sourceFilter !== 'all' && canonical === sourceFilter;
              return (
                <button
                  key={name}
                  type="button"
                  onClick={() => setSourceFilter(isActiveSource ? 'all' : canonical)}
                  className={`rounded-full border px-2.5 py-1 text-[11px] transition ${toneClass} ${
                    isActiveSource ? 'ring-2 ring-slate-300' : ''
                  }`}
                  title={sourceName}
                >
                  {sourceName}: {Number(meta?.count || 0)}
                </button>
              );
            })}
          </div>
        )}

        <div className="space-y-4">
          {loading && (
            <div className="rounded-3xl border border-slate-200 bg-white p-8 text-center text-slate-600" role="status" aria-live="polite">
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
            renderedResults.map((paper) => {
              const importKey = normalizeKey(paper);
              const imported = importedSet.has(importKey);
              const sourceKey = canonicalSourceKey(String(paper.source || '').toLowerCase());
              const sourceLabel = SOURCE_LABELS[sourceKey] || paper.source || 'Merged source';
              const citation = buildCitation(paper, citationStyle);
              const fullTextLink = String(
                paper.full_text_url || paper.pdf_url || paper.institutional_url || (hasPdfLink(paper) ? paper.url : '')
              ).trim();
              const hasFullText = Boolean(paper.full_text_available) || Boolean(fullTextLink);
              const accessType = String(paper.access_type || '').toLowerCase();
              const accessLabel =
                String(paper.access_label || '').trim() ||
                (hasFullText
                  ? accessType === 'institutional'
                    ? 'Institutional Full Text'
                    : 'Full Text Available'
                  : paper.doi
                  ? 'DOI Available'
                  : 'Metadata Only');

              return (
                <article
                  key={importKey}
                  className="rounded-[28px] border border-slate-200 bg-white/95 p-6 shadow-[0_22px_70px_-48px_rgba(15,23,42,0.45)] transition hover:-translate-y-0.5"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <h3 className="text-2xl font-semibold text-slate-900 leading-tight mb-2">
                        {paper.title || 'Untitled'}
                      </h3>
                      <p className="text-sm text-slate-600 mb-2">{(paper.authors || []).join(', ') || 'Unknown authors'}</p>
                      <p className="text-slate-700 leading-relaxed line-clamp-4">{paper.abstract || 'No abstract available.'}</p>
                    </div>

                    <div className="flex flex-col items-end gap-2 shrink-0">
                      <span className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700">
                        {sourceLabel}
                      </span>
                      <button
                        type="button"
                        onClick={() => copyCitation(paper)}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
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
                    <span
                      className={`rounded-full px-2.5 py-1 ${
                        hasFullText
                          ? 'bg-emerald-50 text-emerald-700'
                          : accessType === 'doi_only'
                          ? 'bg-amber-50 text-amber-700'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {accessLabel}
                    </span>
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

                    {fullTextLink && (
                      <a
                        href={fullTextLink}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 hover:bg-emerald-100"
                      >
                        <FileText className="h-4 w-4" />
                        Open Full Text
                      </a>
                    )}

                    <button
                      type="button"
                      onClick={() => void resolvePaperAccess(paper)}
                      disabled={Boolean(resolvingAccess[importKey])}
                      className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-55"
                    >
                      {resolvingAccess[importKey] ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                      Resolve Access
                    </button>

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

        {canRenderMore && !loading && (
          <div className="flex justify-center pt-1">
            <button
              type="button"
              onClick={() => setVisibleCount((prev) => prev + RENDER_BATCH_SIZE)}
              className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-2.5 text-slate-700 hover:bg-slate-50"
            >
              Show {Math.min(RENDER_BATCH_SIZE, filteredResults.length - renderedResults.length)} more loaded results
            </button>
          </div>
        )}

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
