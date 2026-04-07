import type { CitationStyle } from '../../utils/researchArtifacts';
import type { Paper, SavedQuery, SearchMode, SourceCatalogEntry } from './types';

export const GLOBAL_SEARCH_ENDPOINT = '/papers/search-global';
export const SEARCH_MIN_RESULTS = 20;
export const SEARCH_MAX_RESULTS = 200;
export const SEARCH_DEFAULT_RESULTS = 80;
export const SAVED_QUERIES_KEY = 'researchhub.saved_queries.v2';
export const LOAD_MORE_MAX_RESULTS = 60;
export const INITIAL_RENDER_BATCH = 40;
export const RENDER_BATCH_SIZE = 40;

export const QUICK_QUERIES = [
  'graph neural networks for molecules',
  'multimodal llm reasoning benchmark',
  'battery degradation prediction transformers',
  'exoplanet atmospheric retrieval',
  'robust control for quadrotors',
  'finite element analysis composites',
  'power electronics wide bandgap devices',
  'nanophotonics metasurface design',
];

export const SEARCH_MODE_COPY: Record<SearchMode, string> = {
  fast: 'Front-load the highest-yield sources and return quickly.',
  balanced: 'Blend broad metadata coverage with usable speed.',
  deep: 'Spend more time across the long-tail source network.',
};

export const SOURCE_LABELS: Record<string, string> = {
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

export const SOURCE_CATALOG: SourceCatalogEntry[] = [
  { key: 'openalex', label: 'OpenAlex', note: 'Broad metadata and citation graph coverage.' },
  { key: 'econbiz', label: 'EconBiz', note: 'Economics and business literature via official public API.' },
  { key: 'jstage', label: 'J-STAGE', note: 'Japanese journal discovery via official J-STAGE WebAPI.' },
  { key: 'orkg', label: 'ORKG', note: 'Open Research Knowledge Graph paper entries and linked metadata.' },
  { key: 'semantic', label: 'Semantic Scholar', note: 'High-signal ranking and metadata enrichment.' },
  { key: 'arxiv', label: 'ArXiv', note: 'Fast open preprint search for technical fields.' },
  { key: 'crossref', label: 'Crossref', note: 'Cross-publisher DOI metadata and venue coverage.' },
  { key: 'openaire', label: 'OpenAIRE', note: 'European repositories and publications.' },
  { key: 'hal', label: 'HAL', note: 'French open archive for papers and preprints.' },
  { key: 'zenodo', label: 'Zenodo', note: 'Research outputs with strong OA links.' },
  { key: 'figshare', label: 'Figshare', note: 'Article and artifact discovery with direct assets.' },
  { key: 'osf', label: 'OSF Preprints', note: 'Open preprints and affiliated providers.' },
  { key: 'dryad', label: 'Dryad', note: 'Dataset-backed research outputs.' },
  { key: 'datacite', label: 'DataCite', note: 'Research works and persistent identifier metadata.' },
  { key: 'dblp', label: 'DBLP', note: 'Computer science publication index.' },
  { key: 'inspire', label: 'INSPIRE-HEP', note: 'Physics and high-energy literature.' },
  { key: 'nasa', label: 'NASA ADS', note: 'Astrophysics and space-science coverage.' },
  { key: 'springer', label: 'Springer', note: 'Publisher catalog expansion where keys are available.' },
  { key: 'pubmed', label: 'PubMed', note: 'NCBI biomedical index with strong recall.' },
  { key: 'europepmc', label: 'Europe PMC', note: 'Open biomedical full text and metadata.' },
  { key: 'pmc', label: 'PMC', note: 'PubMed Central full-text archive.' },
  { key: 'doaj', label: 'DOAJ', note: 'Directory of open access journal articles.' },
  { key: 'plos', label: 'PLOS', note: 'Open publisher search for life sciences.' },
  { key: 'elife', label: 'eLife', note: 'Open life-science journal coverage.' },
  { key: 'biorxiv', label: 'bioRxiv', note: 'Biology preprints.' },
  { key: 'medrxiv', label: 'medRxiv', note: 'Medical preprints.' },
  { key: 'eric', label: 'ERIC', note: 'Education research and policy literature.' },
  { key: 'osti', label: 'OSTI', note: 'DOE publications and technical reports.' },
];

export const OPEN_ACCESS_SOURCES = new Set([
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

export const SOURCE_ALIASES: Record<string, string> = {
  semantic_scholar: 'semantic',
  semantic_scholar_fallback_arxiv: 'semantic',
  europe_pmc: 'europepmc',
  nasa_ads: 'nasa',
};

export const canonicalSourceKey = (value: string): string => {
  const key = String(value || '').trim().toLowerCase();
  return SOURCE_ALIASES[key] || key;
};

export const normalizeKey = (paper: Paper): string => {
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

export const parseYear = (published: string): number => {
  const match = String(published || '').match(/(19|20)\d{2}/);
  return match ? Number(match[0]) : 0;
};

export const hasPdfLink = (paper: Paper): boolean => {
  const url = String(paper.url || '').toLowerCase();
  const pdfUrl = String(paper.pdf_url || '').toLowerCase();
  return pdfUrl.length > 0 || url.endsWith('.pdf') || pdfUrl.endsWith('.pdf');
};

export const isLikelyOpenAccess = (paper: Paper): boolean => {
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

export const loadSavedQueries = (): SavedQuery[] => {
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

export const getCitationMetadata = (paper: Paper) => ({
  title: paper.title,
  authors: paper.authors,
  published: paper.published,
  publication_name: paper.publication_name,
  publication_title: paper.publication_title,
  source: paper.source,
  doi: paper.doi,
  url: paper.url,
});

export const citationCacheKey = (paper: Paper, style: CitationStyle) => `${normalizeKey(paper)}::${style}`;

export const formatHistoryTime = (value: string): string => {
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
