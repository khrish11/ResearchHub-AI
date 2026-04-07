export interface Paper {
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

export interface Workspace {
  id: number;
  name: string;
}

export interface SourceStatusMeta {
  status?: string;
  count?: number;
  detail?: string;
}

export interface SearchResponse {
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

export interface SavedQuery {
  id: string;
  query: string;
  savedAt: string;
}

export interface SearchHistoryItem {
  id: number;
  query: string;
  source: string;
  result_count: number;
  created_at: string;
  filters?: Record<string, unknown>;
}

export interface SessionStatePayload {
  workspace_id?: number | null;
  last_query?: string | null;
  extra?: Record<string, unknown> | null;
}

export interface SourceCatalogEntry {
  key: string;
  label: string;
  note: string;
}

export type YearFilter = 'any' | '2026' | '2024' | '2020' | '2015' | '2010';
export type SortMode = 'relevance' | 'newest' | 'oldest' | 'title';
export type SearchMode = 'fast' | 'balanced' | 'deep';
export type ResultView = 'comfortable' | 'compact';
