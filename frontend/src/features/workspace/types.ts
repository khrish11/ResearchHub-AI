export interface Paper {
  id: number;
  title: string;
  authors: string;
  abstract: string;
  url?: string;
  doi?: string;
  bibcode?: string;
  source?: string;
  pdf_url?: string;
  institutional_url?: string;
  access_type?: string;
  full_text_available?: boolean;
}

export interface ChatItem {
  id: number;
  message: string;
  response: string;
}

export interface WorkspaceDetail {
  id: number;
  name: string;
  description?: string;
  papers: Paper[];
  chats: ChatItem[];
}

export interface FaultResult {
  fault_count: number;
  risk_score?: number;
  quality_score?: number;
  quality_tier?: string;
  severity_breakdown?: {
    high: number;
    medium: number;
    low: number;
  };
  verification_checklist?: string[];
  faults: Array<{
    severity: string;
    fault_type: string;
    evidence: string;
    recommendation: string;
  }>;
  analysis: string;
}

export type WorkspaceTab = 'papers' | 'chat' | 'review' | 'ops';
