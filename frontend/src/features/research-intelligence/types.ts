/**
 * Research Intelligence Feature Types
 * 
 * Shared types for the Research Intelligence UI components.
 */

import type {
  EvidenceAnalysisResponse,
  GapIntelligenceResponse,
  OpportunityRankingResponse,
  QuestionGenerationResponse,
  HypothesisChallengeResponse,
  CitationVerificationResponse,
  KnowledgeGraphEnhancementResponse,
} from '../../api/researchIntelligence';

// ============================================================================
// PIPELINE STAGE STATUS
// ============================================================================

export type PipelineStage = 'evidence' | 'gaps' | 'opportunities' | 'questions' | 'challenge' | 'citations' | 'graph';

export type StageStatus = 'idle' | 'loading' | 'success' | 'error';

export type PipelineState = {
  [key in PipelineStage]: {
    status: StageStatus;
    resultCount?: number;
    error?: string;
  };
};

// ============================================================================
// RESEARCH INTELLIGENCE STATE
// ============================================================================

export interface ResearchIntelligenceState {
  workspaceId: number | null;
  topic: string;
  paperIds: number[];
  pipeline: PipelineState;
  
  // Results
  evidence: EvidenceAnalysisResponse | null;
  gaps: GapIntelligenceResponse | null;
  opportunities: OpportunityRankingResponse | null;
  questions: QuestionGenerationResponse | null;
  challenge: HypothesisChallengeResponse | null;
  citations: CitationVerificationResponse | null;
  graph: KnowledgeGraphEnhancementResponse | null;
  
  // UI State
  selectedGapId: string | null;
  selectedOpportunityId: string | null;
  selectedQuestionId: string | null;
  hypothesisInput: string;
  showEvidenceTrace: boolean;
  evidenceTraceData: EvidenceTraceData | null;
}

// ============================================================================
// EVIDENCE TRACE
// ============================================================================

export interface EvidenceTraceData {
  insight: string;
  insightType: 'gap' | 'opportunity' | 'question' | 'challenge';
  papers: Array<{
    id: number;
    title: string;
    authors: string;
    passage?: string;
    relevanceScore?: number;
  }>;
  unavailable: boolean;
}

// ============================================================================
// SCORECARD
// ============================================================================

export interface ScorecardData {
  evidenceStrength: number;
  novelty: number;
  impact: number;
  feasibility: number;
  recency: number;
  overall: number;
  confidence: 'high' | 'medium' | 'low';
  explanation: string;
}

// ============================================================================
// UI COMPONENT PROPS
// ============================================================================

export interface IntelligenceCardProps {
  title: string;
  status: StageStatus;
  resultCount?: number;
  error?: string;
  onRetry?: () => void;
  children?: React.ReactNode;
}

export interface ScoreDisplayProps {
  value: number;
  max?: number;
  label: string;
  explanation?: string;
  size?: 'sm' | 'md' | 'lg';
}
