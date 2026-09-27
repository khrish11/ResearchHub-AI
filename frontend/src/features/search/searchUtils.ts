import type { CitationStyle } from '../../utils/researchArtifacts';
import type { Paper, SavedQuery, SearchMode, SourceCatalogEntry, ResearchSearchContext } from './types';

export const GLOBAL_SEARCH_ENDPOINT = '/papers/search-global';
export const SEARCH_MIN_RESULTS = 20;
export const SEARCH_MAX_RESULTS = 200;
export const SEARCH_DEFAULT_RESULTS = 80;
export const SAVED_QUERIES_KEY = 'researchhub.saved_queries.v2';
export const RESEARCH_CONTEXT_KEY = 'soyog.research_context.v1';
export const RESEARCH_CONTEXT_MAX_AGE_MS = 24 * 60 * 60 * 1000; // 24 hours
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
  title: String(paper.title || '').trim(),
  authors: Array.isArray(paper.authors) && paper.authors.length > 0
    ? paper.authors.map((author) => String(author || '').trim()).filter(Boolean)
    : ['Unknown Author'],
  published: String(paper.published || '').trim() || 'n.d.',
  publication_name: String(paper.publication_name || paper.publication_title || '').trim(),
  publication_title: String(paper.publication_title || paper.publication_name || '').trim(),
  journal: String(paper.publication_name || paper.publication_title || '').trim(),
  publisher: String(paper.source || '').trim(),
  source: String(paper.source || '').trim(),
  doi: String(paper.doi || '').trim(),
  url: String(paper.url || '').trim(),
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

export const saveResearchContext = (context: ResearchSearchContext): void => {
  try {
    sessionStorage.setItem(RESEARCH_CONTEXT_KEY, JSON.stringify(context));
  } catch {
    // Silently fail if sessionStorage is unavailable
  }
};

export const loadResearchContext = (): ResearchSearchContext | null => {
  try {
    const raw = sessionStorage.getItem(RESEARCH_CONTEXT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    
    // Validate structure
    if (!parsed || typeof parsed !== 'object') return null;
    if (typeof parsed.query !== 'string' || !parsed.query.trim()) return null;
    if (typeof parsed.created_at !== 'number') return null;
    
    // Check age
    const age = Date.now() - parsed.created_at;
    if (age > RESEARCH_CONTEXT_MAX_AGE_MS) {
      clearResearchContext();
      return null;
    }
    
    // Validate optional fields
    const validContext: ResearchSearchContext = {
      query: parsed.query,
      intent: parsed.intent && typeof parsed.intent === 'string' ? parsed.intent : null,
      focus: parsed.focus && typeof parsed.focus === 'string' ? parsed.focus : null,
      research_type: parsed.research_type && typeof parsed.research_type === 'string' ? parsed.research_type : null,
      research_intent: parsed.research_intent && typeof parsed.research_intent === 'string' ? parsed.research_intent : null,
      suggested_scope: parsed.suggested_scope && typeof parsed.suggested_scope === 'string' ? parsed.suggested_scope : null,
      created_at: parsed.created_at,
    };
    
    return validContext;
  } catch {
    return null;
  }
};

export const clearResearchContext = (): void => {
  try {
    sessionStorage.removeItem(RESEARCH_CONTEXT_KEY);
  } catch {
    // Silently fail if sessionStorage is unavailable
  }
};

export const isResearchContextValid = (context: ResearchSearchContext | null, currentQuery: string): boolean => {
  if (!context) return false;
  if (!context.query || !context.query.trim()) return false;
  // Context must match current query (case-insensitive, trimmed)
  return context.query.trim().toLowerCase() === currentQuery.trim().toLowerCase();
};

// Intent-based search strategy mapping
export interface SearchStrategy {
  recommended_mode: 'fast' | 'balanced' | 'deep';
  description: string;
  recency_bias: 'low' | 'medium' | 'high';
}

export const INTENT_STRATEGY_MAP: Record<string, SearchStrategy> = {
  topic_exploration: {
    recommended_mode: 'balanced',
    description: 'Broad discovery across sources',
    recency_bias: 'medium',
  },
  research_question: {
    recommended_mode: 'balanced',
    description: 'Comprehensive coverage for specific questions',
    recency_bias: 'medium',
  },
  problem_investigation: {
    recommended_mode: 'deep',
    description: 'Extensive search for problem-solving',
    recency_bias: 'medium',
  },
  literature_review: {
    recommended_mode: 'deep',
    description: 'Deep search for comprehensive literature review',
    recency_bias: 'medium',
  },
  comparison: {
    recommended_mode: 'balanced',
    description: 'Broad multi-source comparison',
    recency_bias: 'medium',
  },
  methodology: {
    recommended_mode: 'deep',
    description: 'Deep search for methodological literature',
    recency_bias: 'low',
  },
  trend_analysis: {
    recommended_mode: 'deep',
    description: 'Recent-focused search for trend analysis',
    recency_bias: 'high',
  },
  ambiguous: {
    recommended_mode: 'balanced',
    description: 'Balanced search for exploration',
    recency_bias: 'medium',
  },
};

export const getSearchStrategy = (intent: string | null | undefined): SearchStrategy | null => {
  if (!intent) return null;
  const normalizedIntent = intent.toLowerCase().trim();
  return INTENT_STRATEGY_MAP[normalizedIntent] || null;
};

export const isValidIntent = (intent: string | null | undefined): boolean => {
  if (!intent) return false;
  const normalizedIntent = intent.toLowerCase().trim();
  return normalizedIntent in INTENT_STRATEGY_MAP;
};

// Research-aware query enhancement (deterministic, no LLM)
// Terminology mappings for query enhancement
const TERMINOLOGY_MAP: Record<string, string[]> = {
  'ai': ['artificial intelligence'],
  'ml': ['machine learning'],
  'dl': ['deep learning'],
  'nlp': ['natural language processing'],
  'cv': ['computer vision'],
  'llm': ['large language model', 'language model'],
  'transformer': ['attention mechanism', 'self-attention'],
  'cnn': ['convolutional neural network'],
  'rnn': ['recurrent neural network'],
  'gan': ['generative adversarial network'],
  'gpt': ['generative pretrained transformer'],
  'bert': ['bidirectional encoder representations'],
  'education': ['educational technology', 'learning technology'],
  'healthcare': ['medical', 'health'],
  'segmentation': ['image segmentation', 'semantic segmentation'],
  'classification': ['image classification', 'pattern recognition'],
  'detection': ['object detection', 'anomaly detection'],
};

export interface ResearchEnhancedQuery {
  original: string;
  enhanced: string;
  wasEnhanced: boolean;
  intent: string | null;
}

/**
 * Build a single research-enhanced query from the original query and research context.
 * This function combines the original query with relevant research context (intent, focus)
 * to create a more targeted search query, while preserving the original query meaning.
 */
export const buildResearchEnhancedQuery = (
  query: string,
  intent: string | null | undefined,
  focus: string | null | undefined
): ResearchEnhancedQuery => {
  const trimmedQuery = query.trim();
  if (!trimmedQuery) {
    return { original: '', enhanced: '', wasEnhanced: false, intent: null };
  }

  const normalizedIntent = intent?.toLowerCase().trim() || null;
  const trimmedFocus = focus?.trim() || '';

  // Ambiguous intent: no enhancement
  if (normalizedIntent === 'ambiguous') {
    return { original: trimmedQuery, enhanced: trimmedQuery, wasEnhanced: false, intent: normalizedIntent };
  }

  const lowerQuery = trimmedQuery.toLowerCase();
  let enhancedQuery = trimmedQuery;
  let wasEnhanced = false;

  // Step 1: Apply terminology expansion (only if it improves the query)
  // Only expand acronyms that are likely to benefit from expansion
  for (const [term, variants] of Object.entries(TERMINOLOGY_MAP)) {
    if (lowerQuery.includes(term) && !lowerQuery.includes(variants[0].toLowerCase())) {
      // Only expand if the term is a standalone acronym (not part of a larger word)
      const wordBoundaryRegex = new RegExp(`\\b${term}\\b`, 'i');
      if (wordBoundaryRegex.test(trimmedQuery)) {
        enhancedQuery = enhancedQuery.replace(wordBoundaryRegex, variants[0]);
        wasEnhanced = true;
        break; // Only expand one term to avoid over-complication
      }
    }
  }

  // Step 2: Add research focus if it adds meaningful context
  if (trimmedFocus && trimmedFocus.length > 3 && trimmedFocus.length < 100) {
    const lowerFocus = trimmedFocus.toLowerCase();
    // Only add focus if it's not already in the query
    if (!lowerQuery.includes(lowerFocus)) {
      // Check if focus naturally fits at the end or beginning
      if (lowerQuery.endsWith('for') || lowerQuery.endsWith('in') || lowerQuery.endsWith('on')) {
        enhancedQuery = `${enhancedQuery} ${trimmedFocus}`;
        wasEnhanced = true;
      } else if (lowerQuery.startsWith('how') || lowerQuery.startsWith('what') || lowerQuery.startsWith('why')) {
        enhancedQuery = `${trimmedFocus} ${enhancedQuery}`;
        wasEnhanced = true;
      } else {
        // Default: append focus with appropriate connector
        enhancedQuery = `${enhancedQuery} ${trimmedFocus}`;
        wasEnhanced = true;
      }
    }
  }

  // Step 3: Apply intent-specific enhancements (conservative)
  if (normalizedIntent === 'literature_review') {
    // Add "review" only if not already present and query is not already review-oriented
    const reviewTerms = ['review', 'survey', 'systematic review', 'meta-analysis'];
    const hasReviewTerm = reviewTerms.some(term => lowerQuery.includes(term));
    if (!hasReviewTerm && !lowerQuery.includes('literature')) {
      enhancedQuery = `${enhancedQuery} review`;
      wasEnhanced = true;
    }
  } else if (normalizedIntent === 'methodology') {
    // Add "methods" or "methodology" only if not already present and not awkward
    const methodTerms = ['method', 'methods', 'methodology', 'approach', 'technique', 'algorithm'];
    const hasMethodTerm = methodTerms.some(term => lowerQuery.includes(term));
    if (!hasMethodTerm) {
      // Check if adding "methods" would be awkward (e.g., "evaluation methods for LLM hallucination methods")
      if (!lowerQuery.includes('evaluation') && !lowerQuery.includes('assessment')) {
        enhancedQuery = `${enhancedQuery} methods`;
        wasEnhanced = true;
      }
    }
  } else if (normalizedIntent === 'trend_analysis') {
    // Add "recent" only if not already present
    if (!lowerQuery.includes('recent') && !lowerQuery.includes('latest') && !lowerQuery.includes('state of the art')) {
      enhancedQuery = `recent ${enhancedQuery}`;
      wasEnhanced = true;
    }
  } else if (normalizedIntent === 'comparison') {
    // Preserve comparison structure, don't add extra terms that could confuse the comparison
    // Only enhance if focus is relevant
    if (trimmedFocus && !lowerQuery.includes(trimmedFocus.toLowerCase())) {
      enhancedQuery = `${enhancedQuery} ${trimmedFocus}`;
      wasEnhanced = true;
    }
  }

  // Step 4: Clean up the enhanced query
  enhancedQuery = enhancedQuery
    .replace(/\s+/g, ' ') // Remove extra spaces
    .trim();

  // Step 5: Validate the enhanced query
  if (!validateQuery(enhancedQuery)) {
    // If validation fails, fall back to original
    return { original: trimmedQuery, enhanced: trimmedQuery, wasEnhanced: false, intent: normalizedIntent };
  }

  // Step 6: Check if enhancement is actually different and better
  if (enhancedQuery.toLowerCase() === trimmedQuery.toLowerCase()) {
    wasEnhanced = false;
  }

  // Step 7: Check for awkward repetitions
  const words = enhancedQuery.toLowerCase().split(/\s+/);
  const wordCounts = new Map<string, number>();
  for (const word of words) {
    wordCounts.set(word, (wordCounts.get(word) || 0) + 1);
  }
  // If any word appears more than twice, it's likely awkward
  for (const [word, count] of wordCounts) {
    if (count > 2 && word.length > 3) {
      // Fall back to original
      return { original: trimmedQuery, enhanced: trimmedQuery, wasEnhanced: false, intent: normalizedIntent };
    }
  }

  // Step 8: Ensure query length is reasonable
  if (enhancedQuery.length > 300) {
    // If too long, fall back to original
    return { original: trimmedQuery, enhanced: trimmedQuery, wasEnhanced: false, intent: normalizedIntent };
  }

  return {
    original: trimmedQuery,
    enhanced: enhancedQuery,
    wasEnhanced,
    intent: normalizedIntent,
  };
};

export const validateQuery = (query: string): boolean => {
  const trimmed = query.trim();
  if (!trimmed) return false;
  if (trimmed.length > 500) return false;
  if (!/^[a-zA-Z0-9\s\-_.,:;()]+$/.test(trimmed)) return false;
  return true;
};
