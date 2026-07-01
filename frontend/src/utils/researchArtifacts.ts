import api from '../api';
import { apiErrorMessage } from './apiError';

export type CitationStyle = 'apa' | 'mla' | 'ieee' | 'chicago' | 'bibtex';

export interface CitationMetadata {
  title?: string;
  authors?: string[];
  year?: string | number | null;
  venue?: string | null;
  journal?: string | null;
  publisher?: string | null;
  doi?: string | null;
  url?: string | null;
  pages?: string | null;
  issue?: string | null;
  volume?: string | null;
  published?: string | null;
  publication_name?: string | null;
  publication_title?: string | null;
  source?: string | null;
}

export interface CitationResponse {
  citation: string;
  style: string;
  completeness_score: number;
  missing_fields: string[];
  warnings: string[];
  metadata: {
    title?: string;
    authors?: string[];
    year?: string | null;
    venue?: string | null;
    doi?: string | null;
    url?: string | null;
    pages?: string | null;
    issue?: string | null;
    volume?: string | null;
    source?: string | null;
  };
}

export interface PaperClaim {
  claim?: string;
  support_level?: string;
  evidence?: string;
}

export interface PaperCheckAnalysis {
  snapshot?: {
    title?: string;
    paper_type?: string;
    core_problem?: string;
    summary?: string;
  };
  claims?: PaperClaim[];
  methods?: {
    approach?: string;
    datasets?: string[];
    metrics?: string[];
    notes?: string[];
  };
  evidence_strength?: {
    score?: number;
    summary?: string;
    signals?: string[];
  };
  reproducibility?: {
    score?: number;
    summary?: string;
    checklist?: string[];
  };
  citation_quality?: {
    score?: number;
    summary?: string;
    issues?: string[];
  };
  limitations?: string[];
  red_flags?: string[];
  confidence_notes?: string[];
}

export interface AIWritingSegment {
  segment_id: string;
  start_offset?: number;
  end_offset?: number;
  text_excerpt: string;
  likelihood_score: number;
  likelihood_band: 'low' | 'medium' | 'high';
  reasons: string[];
  explanation: string;
  heuristic_score?: number;
}

export interface PaperCheckPayload {
  paper_id?: number;
  raw_text?: string;
  workspace_id?: number;
  prefer_async?: boolean;
}

export interface CompletedPaperCheckResult {
  status: 'completed';
  job_id?: string | null;
  paper_analysis: PaperCheckAnalysis;
  ai_writing_likelihood: {
    segments: AIWritingSegment[];
    disclaimer?: string;
    detection_error?: string | null;
  };
  metadata: {
    processed_at?: string;
    model_used?: string | null;
    version?: string;
    source?: string;
    segment_count?: number;
    suspicious_segment_count?: number;
    cache_hit?: boolean;
    cache_layer?: string | null;
  };
}

export interface PaperExplanationSource {
  source_id: string;
  source_type: string;
  title: string;
  url?: string;
  doi?: string;
  similarity_score?: number;
}

export interface PaperExplanationResponse {
  paper_id: number;
  workspace_id: number;
  status: 'cached' | 'reused' | 'generated' | 'fallback';
  cached: boolean;
  generated_at?: string | null;
  expires_at?: string | null;
  disclaimer: string;
  simple_explanation: string;
  key_points: string[];
  methodology: string;
  strengths: string[];
  weaknesses: string[];
  evidence_quality: string;
  ai_likelihood: string;
  significance: string;
  sources: PaperExplanationSource[];
  error?: string | null;
}

interface QueuedPaperCheckResponse {
  status: 'pending' | 'queued';
  job_id: string;
  metadata?: {
    processed_at?: string;
    version?: string;
  };
}

interface StructuredErrorResponse {
  error?: {
    code?: string;
    message?: string;
    retryable?: boolean;
  };
}

interface LatestPaperCheckResponse extends StructuredErrorResponse {
  job_id?: string | null;
  status?: string;
  result?: Partial<CompletedPaperCheckResult> | null;
  created_at?: string | null;
  updated_at?: string | null;
}

type InitialPaperCheckResponse =
  | CompletedPaperCheckResult
  | QueuedPaperCheckResponse
  | StructuredErrorResponse;

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

const parseYear = (value: string | number | null | undefined): string | null => {
  const match = String(value || '').match(/(19|20)\d{2}/);
  return match ? match[0] : null;
};

export const citationMissingFieldLabel = (value: string): string => {
  if (value === 'pages_or_issue') return 'pages, issue, or volume';
  return value.replace(/_/g, ' ');
};

export const extractPaperTitleFromFilename = (filename: string): string =>
  String(filename || '')
    .replace(/\.pdf$/i, '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

export const buildCitationPayload = (metadata: CitationMetadata, style: CitationStyle) => ({
  title: String(metadata.title || '').trim(),
  authors: Array.isArray(metadata.authors) ? metadata.authors.filter(Boolean) : [],
  year: parseYear(metadata.year ?? metadata.published),
  venue: String(
    metadata.venue || metadata.journal || metadata.publication_name || metadata.publication_title || metadata.source || ''
  ).trim() || null,
  journal: String(metadata.journal || metadata.publication_name || metadata.publication_title || '').trim() || null,
  publisher: String(metadata.publisher || metadata.source || '').trim() || null,
  doi: String(metadata.doi || '').trim() || null,
  url: String(metadata.url || '').trim() || null,
  pages: String(metadata.pages || '').trim() || null,
  issue: String(metadata.issue || '').trim() || null,
  volume: String(metadata.volume || '').trim() || null,
  style,
});

export const fallbackCitation = (metadata: CitationMetadata, style: CitationStyle): string => {
  const payload = buildCitationPayload(metadata, style);
  const authors = payload.authors.length > 0 ? payload.authors : ['Unknown author'];
  const year = payload.year || 'n.d.';
  const title = payload.title || 'Untitled';
  const venue = payload.venue || 'Unknown venue';
  const link = payload.doi ? `https://doi.org/${payload.doi}` : payload.url || '';

  if (style === 'bibtex') {
    const authorToken = String(authors[0] || 'paper').split(' ').slice(-1)[0].toLowerCase() || 'paper';
    const titleToken = String(title.split(' ')[0] || 'paper').replace(/[^a-zA-Z0-9]+/g, '').toLowerCase() || 'paper';
    return [
      `@misc{${authorToken}${String(year).replace(/\D+/g, '') || 'nd'}${titleToken},`,
      `  title = {${title}},`,
      `  author = {${authors.join(' and ')}},`,
      payload.year ? `  year = {${payload.year}},` : '',
      payload.venue ? `  journal = {${payload.venue}},` : '',
      payload.doi ? `  doi = {${payload.doi}},` : '',
      link ? `  url = {${link}},` : '',
      '}',
    ].filter(Boolean).join('\n');
  }
  if (style === 'ieee') {
    return `${authors.join(', ')}, "${title}," ${venue}, ${year}.${link ? ` ${link}` : ''}`.trim();
  }
  if (style === 'mla') {
    return `${authors[0]}${authors.length > 1 ? ', et al.' : '.'} "${title}." ${venue}, ${year}.${link ? ` ${link}` : ''}`.trim();
  }
  if (style === 'chicago') {
    return `${authors.join(', ')}. "${title}." ${venue}${payload.year ? ` (${payload.year})` : ''}.${link ? ` ${link}` : ''}`.trim();
  }
  return `${authors.join(', ')} (${year}). ${title}. ${venue}.${link ? ` ${link}` : ''}`.trim();
};

export const fetchCitation = async (metadata: CitationMetadata, style: CitationStyle): Promise<CitationResponse> => {
  const response = await api.post<CitationResponse | StructuredErrorResponse>('/papers/citation', buildCitationPayload(metadata, style));
  const data = response.data as CitationResponse & StructuredErrorResponse;
  if (data?.error?.message) {
    throw new Error(data.error.message);
  }
  return data as CitationResponse;
};

export const fetchPaperCitation = async (paperId: number, style: CitationStyle): Promise<CitationResponse> => {
  const response = await api.get<CitationResponse | StructuredErrorResponse>(`/papers/${paperId}/citation`, {
    params: { style },
  });
  const data = response.data as CitationResponse & StructuredErrorResponse;
  if (data?.error?.message) {
    throw new Error(data.error.message);
  }
  return data as CitationResponse;
};

export const fetchPaperExplanation = async (
  paperId: number,
  options: { refresh?: boolean; includeRag?: boolean } = {}
): Promise<PaperExplanationResponse> => {
  const response = await api.get<PaperExplanationResponse>(`/papers/${paperId}/explain`, {
    params: {
      refresh: Boolean(options.refresh),
      include_rag: Boolean(options.includeRag),
    },
  });
  return response.data;
};

const normalizeCompletedPaperCheck = (
  payload: Partial<CompletedPaperCheckResult>,
  jobId?: string | null
): CompletedPaperCheckResult => ({
  status: 'completed',
  job_id: jobId ?? payload.job_id ?? null,
  paper_analysis: payload.paper_analysis || {},
  ai_writing_likelihood: {
    segments: Array.isArray(payload.ai_writing_likelihood?.segments) ? payload.ai_writing_likelihood.segments : [],
    disclaimer: payload.ai_writing_likelihood?.disclaimer,
    detection_error: payload.ai_writing_likelihood?.detection_error || null,
  },
  metadata: payload.metadata || {},
});

export const runPaperCheck = async (
  payload: PaperCheckPayload,
  options: { pollIntervalMs?: number; maxWaitMs?: number } = {}
): Promise<CompletedPaperCheckResult> => {
  const pollIntervalMs = Math.max(1000, Number(options.pollIntervalMs || 1800));
  const maxWaitMs = Math.max(10000, Number(options.maxWaitMs || 90000));
  const start = Date.now();

  const response = await api.post<InitialPaperCheckResponse>(
    '/research/paper-check',
    payload
  );
  const initial = response.data;
  if ('error' in initial && initial?.error?.message) {
    throw new Error(initial.error.message);
  }
  if ('status' in initial && initial.status === 'completed') {
    return normalizeCompletedPaperCheck(initial);
  }
  if (!('status' in initial) || !['pending', 'queued'].includes(initial.status) || !('job_id' in initial) || !initial.job_id) {
    throw new Error('Paper check returned an unexpected response.');
  }

  while (Date.now() - start < maxWaitMs) {
    await sleep(pollIntervalMs);
    const poll = await api.get(`/research/paper-check/${initial.job_id}`);
    const data = poll.data as {
      status?: string;
      result?: Partial<CompletedPaperCheckResult>;
      error?: { message?: string; retryable?: boolean };
    };
    if (data?.status === 'completed' && data.result) {
      return normalizeCompletedPaperCheck(data.result, initial.job_id);
    }
    if (data?.status === 'failed') {
      throw new Error(String(data.error?.message || 'Paper check failed.'));
    }
  }

  throw new Error(`Paper check exceeded ${Math.round(maxWaitMs / 1000)}s. Try again.`);
};

export const getLatestPaperCheck = async (
  paperId: number,
  workspaceId?: number
): Promise<CompletedPaperCheckResult | null> => {
  if (!paperId || !workspaceId) {
    return null;
  }
  try {
    const response = await api.get<LatestPaperCheckResponse>('/research/paper-check/latest', {
      params: {
        paper_id: paperId,
        workspace_id: workspaceId,
      },
    });
    const data = response.data;
    if (data?.status !== 'completed' || !data.result) {
      return null;
    }
    const result = normalizeCompletedPaperCheck(data.result, data.job_id ?? null);
    const completedAt = result.metadata.processed_at || data.updated_at || data.created_at || undefined;
    return {
      ...result,
      metadata: {
        ...result.metadata,
        processed_at: completedAt,
      },
    };
  } catch (err: unknown) {
    if ((err as { response?: { status?: number } })?.response?.status === 404) {
      return null;
    }
    throw err;
  }
};

export const researchFeatureError = (error: unknown, fallback: string): string =>
  apiErrorMessage(error, fallback);
