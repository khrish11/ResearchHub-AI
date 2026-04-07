export interface Workspace {
  id: number;
  name: string;
}

export interface Paper {
  id: number;
  title: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  metadata?: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation?: string;
  type?: string;
  weight?: number;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  summary?: {
    papers?: number;
    concepts?: number;
    authors?: number;
    years?: number;
    total_edges?: number;
    top_concepts?: Array<{ label: string; frequency: number }>;
    top_authors?: Array<{ label: string; paper_count: number }>;
    top_years?: Array<{ year: number; count: number }>;
  };
}

export interface AiStatusResponse {
  enabled: boolean;
  model?: string | null;
  error?: string | null;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
}

export type JsonRecord = Record<string, unknown>;

export interface FullPipelineResult {
  results?: Record<string, unknown>;
  steps_completed?: unknown[];
  planned_steps?: unknown[];
}

export interface ChatbotResult {
  reply?: string;
}

export type AgentPanel = 'overview' | 'analysis' | 'graph' | 'generation' | 'advanced';
