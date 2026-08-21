/**
 * Research Intelligence API Client
 * 
 * API clients for the 7 research intelligence endpoints:
 * - Evidence Analysis
 * - Gap Detection (upgraded)
 * - Opportunity Ranking
 * - Research Question Generation
 * - Hypothesis Challenge
 * - Citation Verification
 * - Knowledge Graph Enhancement
 */

import api from '../api';

// ============================================================================
// TYPES
// ============================================================================

export interface WorkspaceScopedRequest {
  workspace_id: number;
  topic?: string;
  paper_ids?: number[];
}

// ============================================================================
// EVIDENCE ANALYSIS
// ============================================================================

export interface EvidenceAnalysisRequest extends WorkspaceScopedRequest {
  claim: string;
  topic?: string;
}

export interface EvidencePaper {
  id: number;
  title: string;
  authors: string;
}

export interface EvidenceClassification {
  supporting_count: number;
  contradicting_count: number;
  neutral_count: number;
  insufficient_evidence: boolean;
  supporting_papers: EvidencePaper[];
  contradicting_papers: EvidencePaper[];
}

export interface EvidenceStrength {
  support_count: number;
  contradiction_count: number;
  neutral_count: number;
  source_quality_score: number;
  recency_score: number;
  replication_signal: number;
  overall_strength: number;
  confidence: 'high' | 'medium' | 'low';
  explanation: string;
}

export interface EvidencePassage {
  paper_id: number;
  paper_title: string;
  passage_text: string;
  relevance_score: number;
  evidence_type: 'supporting' | 'contradicting' | 'neutral';
}

export interface EvidenceAnalysisResponse {
  workspace: { id: number; name: string };
  claim: string;
  classification: EvidenceClassification;
  strength: EvidenceStrength;
  passages: EvidencePassage[];
  evidence_type: 'observed' | 'inferred' | 'ai_generated';
  generated_at: string;
}

// ============================================================================
// GAP INTELLIGENCE
// ============================================================================

export type GapDetectionRequest = WorkspaceScopedRequest;

export interface StructuredGap {
  category: string;
  description: string;
  confidence: number;
  evidence_count: number;
  novelty_potential: number;
  research_impact: number;
  feasibility: number;
  recency: number;
  supporting_papers: number[];
  counter_evidence: string[];
  affected_papers: number[];
  explanation: string;
}

export interface GapScores {
  overall_confidence: number;
  novelty_potential: number;
  research_impact: number;
  feasibility: number;
  recency: number;
}

export interface GapIntelligenceResponse {
  workspace: { id: number; name: string };
  topic: string;
  paper_count: number;
  gaps_by_category: Record<string, StructuredGap[]>;
  scores: GapScores;
  summary: string;
  generated_at: string;
}

// ============================================================================
// OPPORTUNITY RANKING
// ============================================================================

export type OpportunityRankingRequest = WorkspaceScopedRequest;

export interface ResearchOpportunity {
  gap_id: string;
  gap_description: string;
  category: string;
  evidence_strength: number;
  novelty: number;
  impact: number;
  feasibility: number;
  recency: number;
  overall_score: number;
  rank: number;
  explanation: string;
  supporting_papers: number[];
  affected_papers: number[];
}

export interface OpportunityComparison {
  opportunity_1: string;
  opportunity_2: string;
  comparison: string;
  recommendation: string;
}

export interface TopOpportunity {
  gap_id: string;
  gap_description: string;
  category: string;
  overall_score: number;
  rank: number;
  explanation: string;
}

export interface OpportunityRankingResponse {
  workspace: { id: number; name: string };
  topic: string;
  paper_count: number;
  opportunities: ResearchOpportunity[];
  total_opportunities: number;
  top_opportunity: TopOpportunity | null;
  comparison_matrix: OpportunityComparison[];
  summary: string;
  generated_at: string;
}

// ============================================================================
// RESEARCH QUESTION GENERATION
// ============================================================================

export interface QuestionGenerationRequest extends WorkspaceScopedRequest {
  max_questions?: number;
}

export interface ResearchQuestion {
  id: string;
  question: string;
  category: 'exploratory' | 'confirmatory' | 'comparative' | 'causal';
  complexity: number;
  confidence: 'high' | 'medium' | 'low';
  novelty: number;
  feasibility: number;
  impact: number;
  source_gap_id: string;
  source_gap_description: string;
  supporting_papers: number[];
  rationale: string;
}

export interface QuestionGenerationResponse {
  workspace: { id: number; name: string };
  topic: string;
  paper_count: number;
  questions: ResearchQuestion[];
  total_questions: number;
  top_questions: ResearchQuestion[];
  summary: string;
  generated_at: string;
}

// ============================================================================
// HYPOTHESIS CHALLENGER
// ============================================================================

export interface HypothesisChallengeRequest extends WorkspaceScopedRequest {
  hypothesis: string;
}

export interface Challenge {
  id: string;
  hypothesis: string;
  challenge_type: string;
  challenge_text: string;
  counter_evidence: string[];
  strength: number;
  confidence: number;
  supporting_papers: number[];
  rationale: string;
}

export interface StrongestChallenge {
  id: string;
  challenge_type: string;
  challenge_text: string;
  strength: number;
  confidence: number;
  rationale: string;
}

export interface HypothesisChallengeResponse {
  workspace: { id: number; name: string };
  hypothesis: string;
  challenges: Challenge[];
  total_challenges: number;
  strongest_challenge: StrongestChallenge | null;
  overall_vulnerability: number;
  summary: string;
  generated_at: string;
}

// ============================================================================
// CITATION VERIFICATION
// ============================================================================

export type CitationVerificationRequest = WorkspaceScopedRequest;

export interface CitationIssue {
  type: string;
  description: string;
  severity: 'low' | 'medium' | 'high';
  recommendation: string;
}

export interface CitationVerification {
  paper_id: number;
  paper_title: string;
  source: string;
  doi: string;
  url: string;
  quality_score: number;
  accessibility_score: number;
  consistency_score: number;
  overall_confidence: number;
  issues: CitationIssue[];
  recommendations: string[];
}

export interface CitationVerificationResponse {
  workspace: { id: number; name: string };
  total_papers: number;
  verifications: CitationVerification[];
  average_quality: number;
  average_accessibility: number;
  average_consistency: number;
  overall_confidence: number;
  critical_issues: number;
  summary: string;
  generated_at: string;
}

// ============================================================================
// KNOWLEDGE GRAPH ENHANCEMENT
// ============================================================================

export interface KnowledgeGraphEnhancementRequest extends WorkspaceScopedRequest {
  layers?: ('gap' | 'evidence' | 'opportunity' | 'citation')[];
}

export interface IntelligenceLayer {
  layer_type: string;
  enabled: boolean;
  data: Record<string, unknown>;
  summary: string;
}

export interface EnhancedKnowledgeGraph {
  base_graph: {
    nodes: Array<{ id: string; label: string; type: string; metadata?: Record<string, unknown> }>;
    edges: Array<{ source: string; target: string; relation?: string; type?: string; weight?: number }>;
  };
  intelligence_layers: IntelligenceLayer[];
  total_layers: number;
  enhanced_nodes: number;
  enhanced_edges: number;
  summary: string;
  generated_at: string;
}

export interface KnowledgeGraphEnhancementResponse {
  workspace: { id: number; name: string };
  topic: string;
  paper_count: number;
  base_graph: {
    nodes: Array<{ id: string; label: string; type: string; metadata?: Record<string, unknown> }>;
    edges: Array<{ source: string; target: string; relation?: string; type?: string; weight?: number }>;
  };
  intelligence_layers: IntelligenceLayer[];
  total_layers: number;
  enhanced_nodes: number;
  enhanced_edges: number;
  summary: string;
  generated_at: string;
}

// ============================================================================
// RESEARCH INTELLIGENCE ARTIFACTS
// ============================================================================

export interface ResearchIntelligenceArtifactRequest {
  workspace_id: number;
  topic: string;
  paper_ids: number[];
  pipeline_version?: string;
}

export interface ResearchIntelligenceArtifact {
  id: string;
  workspace_id: number;
  user_id: number;
  topic: string;
  paper_ids: number[];
  paper_count: number;
  status: 'running' | 'completed' | 'partial' | 'failed';
  pipeline_version: string;
  created_at: string;
  updated_at: string;
  evidence_analysis?: Record<string, unknown>;
  gap_analysis?: Record<string, unknown>;
  opportunity_ranking?: Record<string, unknown>;
  research_questions?: Record<string, unknown>;
  hypothesis_challenges?: Record<string, unknown>;
  citation_verification?: Record<string, unknown>;
  knowledge_graph?: Record<string, unknown>;
  overall_score?: number;
  summary?: string;
  stage_errors?: Record<string, string>;
}

export interface ListArtifactsResponse {
  artifacts: ResearchIntelligenceArtifact[];
}

// ============================================================================
// API CLIENT FUNCTIONS
// ============================================================================

/**
 * Evidence Analysis
 * POST /research/evidence-analysis
 */
export async function analyzeEvidence(request: EvidenceAnalysisRequest): Promise<EvidenceAnalysisResponse> {
  const response = await api.post<EvidenceAnalysisResponse>('/research/evidence-analysis', request);
  return response.data;
}

/**
 * Gap Detection (upgraded with Gap Intelligence)
 * POST /research/gap-detection
 */
export async function detectGaps(request: GapDetectionRequest): Promise<GapIntelligenceResponse> {
  const response = await api.post<GapIntelligenceResponse>('/research/gap-detection', request);
  return response.data;
}

/**
 * Opportunity Ranking
 * POST /research/opportunity-ranking
 */
export async function rankOpportunities(request: OpportunityRankingRequest): Promise<OpportunityRankingResponse> {
  const response = await api.post<OpportunityRankingResponse>('/research/opportunity-ranking', request);
  return response.data;
}

/**
 * Research Question Generation
 * POST /research/question-generation
 */
export async function generateQuestions(request: QuestionGenerationRequest): Promise<QuestionGenerationResponse> {
  const response = await api.post<QuestionGenerationResponse>('/research/question-generation', request);
  return response.data;
}

/**
 * Hypothesis Challenge
 * POST /research/hypothesis-challenge
 */
export async function challengeHypothesis(request: HypothesisChallengeRequest): Promise<HypothesisChallengeResponse> {
  const response = await api.post<HypothesisChallengeResponse>('/research/hypothesis-challenge', request);
  return response.data;
}

/**
 * Citation Verification
 * POST /research/citation-verification
 */
export async function verifyCitations(request: CitationVerificationRequest): Promise<CitationVerificationResponse> {
  const response = await api.post<CitationVerificationResponse>('/research/citation-verification', request);
  return response.data;
}

/**
 * Knowledge Graph Enhancement
 * POST /research/knowledge-graph-enhancement
 */
export async function enhanceKnowledgeGraph(request: KnowledgeGraphEnhancementRequest): Promise<KnowledgeGraphEnhancementResponse> {
  const response = await api.post<KnowledgeGraphEnhancementResponse>('/research/knowledge-graph-enhancement', request);
  return response.data;
}

/**
 * Create Research Intelligence Artifact
 * POST /research/intelligence
 */
export async function createResearchIntelligenceArtifact(request: ResearchIntelligenceArtifactRequest): Promise<ResearchIntelligenceArtifact> {
  const response = await api.post<ResearchIntelligenceArtifact>('/research/intelligence', request);
  return response.data;
}

/**
 * Get Research Intelligence Artifact
 * GET /research/intelligence/{artifact_id}
 */
export async function getResearchIntelligenceArtifact(artifactId: string): Promise<ResearchIntelligenceArtifact> {
  const response = await api.get<ResearchIntelligenceArtifact>(`/research/intelligence/${artifactId}`);
  return response.data;
}

/**
 * List Workspace Research Intelligence Artifacts
 * GET /workspaces/{workspace_id}/research-intelligence
 */
export async function listWorkspaceResearchIntelligenceArtifacts(workspaceId: number): Promise<ListArtifactsResponse> {
  const response = await api.get<ListArtifactsResponse>(`/workspaces/${workspaceId}/research-intelligence`);
  return response.data;
}

/**
 * Delete Research Intelligence Artifact
 * DELETE /research/intelligence/{artifact_id}
 */
export async function deleteResearchIntelligenceArtifact(artifactId: string): Promise<{ success: boolean }> {
  const response = await api.delete<{ success: boolean }>(`/research/intelligence/${artifactId}`);
  return response.data;
}

// ============================================================================
// SAVED RESEARCH QUESTIONS
// ============================================================================

export interface SavedResearchQuestion {
  id: string;
  workspace_id: number;
  user_id: number;
  question: string;
  category: string;
  complexity: string;
  confidence: number;
  novelty: number;
  feasibility: number;
  impact: number;
  source_gap_id?: string;
  source_gap_description?: string;
  supporting_papers: number[];
  rationale?: string;
  source_artifact_id?: string;
  created_at: string;
}

export interface SaveResearchQuestionRequest {
  workspace_id: number;
  question: string;
  category: string;
  complexity: string;
  confidence: number;
  novelty: number;
  feasibility: number;
  impact: number;
  source_gap_id?: string;
  source_gap_description?: string;
  supporting_papers?: number[];
  rationale?: string;
  source_artifact_id?: string;
}

export interface ListSavedQuestionsResponse {
  questions: SavedResearchQuestion[];
}

/**
 * Save Research Question
 * POST /research/questions
 */
export async function saveResearchQuestion(request: SaveResearchQuestionRequest): Promise<SavedResearchQuestion> {
  const response = await api.post<SavedResearchQuestion>('/research/questions', request);
  return response.data;
}

/**
 * List Saved Research Questions for Workspace
 * GET /research/workspaces/{workspace_id}/questions
 */
export async function listSavedResearchQuestions(workspaceId: number): Promise<ListSavedQuestionsResponse> {
  const response = await api.get<ListSavedQuestionsResponse>(`/research/workspaces/${workspaceId}/questions`);
  return response.data;
}

/**
 * Get Saved Research Question
 * GET /research/questions/{question_id}
 */
export async function getSavedResearchQuestion(questionId: string): Promise<SavedResearchQuestion> {
  const response = await api.get<SavedResearchQuestion>(`/research/questions/${questionId}`);
  return response.data;
}

/**
 * Delete Saved Research Question
 * DELETE /research/questions/{question_id}
 */
export async function deleteSavedResearchQuestion(questionId: string): Promise<{ success: boolean }> {
  const response = await api.delete<{ success: boolean }>(`/research/questions/${questionId}`);
  return response.data;
}

// ============================================================================
// RESEARCH PLAN
// ============================================================================

export interface ResearcherDecision {
  field_name: string;
  ai_suggestion: string;
  researcher_decision: 'ACCEPT' | 'MODIFY' | 'REJECT';
  final_value: string;
  decision_timestamp: string;
  evidence_references: string[];
}

export interface ResearchPlan {
  id: string;
  workspace_id: number;
  user_id: number;
  artifact_id: string;
  opportunity_id: string;
  opportunity_description: string;
  title: string;
  research_problem: string;
  research_question: string;
  hypothesis: string;
  objectives: string;
  proposed_methodology: string;
  alternative_methodology: string;
  datasets: string;
  variables: string;
  baselines: string;
  evaluation_metrics: string;
  expected_contribution: string;
  risks: string;
  limitations: string;
  reproducibility_requirements: string;
  supporting_papers: number[];
  evidence_references: string[];
  researcher_decisions: ResearcherDecision[];
  status: 'draft' | 'review' | 'final' | 'archived';
  created_at: string;
  updated_at: string;
}

export interface CreateResearchPlanRequest extends WorkspaceScopedRequest {
  artifact_id: string;
  opportunity_id: string;
  opportunity_description: string;
  title: string;
  research_problem: string;
  research_question: string;
  hypothesis: string;
  objectives: string;
  proposed_methodology: string;
  alternative_methodology: string;
  datasets: string;
  variables: string;
  baselines: string;
  evaluation_metrics: string;
  expected_contribution: string;
  risks: string;
  limitations: string;
  reproducibility_requirements: string;
  supporting_papers?: number[];
  evidence_references?: string[];
  status?: string;
}

export interface UpdateResearchPlanRequest {
  title?: string;
  research_problem?: string;
  research_question?: string;
  hypothesis?: string;
  objectives?: string;
  proposed_methodology?: string;
  alternative_methodology?: string;
  datasets?: string;
  variables?: string;
  baselines?: string;
  evaluation_metrics?: string;
  expected_contribution?: string;
  risks?: string;
  limitations?: string;
  reproducibility_requirements?: string;
  supporting_papers?: number[];
  evidence_references?: string[];
  researcher_decisions?: ResearcherDecision[];
  status?: string;
}

export interface GeneratePlanSuggestionsRequest {
  artifact_id: string;
  opportunity_id: string;
  gap_description: string;
  category: string;
  evidence_strength: number;
  novelty: number;
  impact: number;
  feasibility: number;
  recency: number;
  overall_score: number;
  explanation: string;
  supporting_papers: number[];
  affected_papers: number[];
}

export interface ListResearchPlansResponse {
  plans: ResearchPlan[];
}

/**
 * Generate Research Plan Suggestions
 * POST /research/plans/generate
 */
export interface PlanSuggestions {
  title: string;
  research_problem: string;
  research_question: string;
  hypothesis: string;
  objectives: string;
  proposed_methodology: string;
  alternative_methodology: string;
  datasets: string;
  variables: string;
  baselines: string;
  evaluation_metrics: string;
  expected_contribution: string;
  risks: string;
  limitations: string;
  reproducibility_requirements: string;
  evidence_references?: string[];
  opportunity_id?: string;
  opportunity_description?: string;
  supporting_papers?: number[];
}

export async function generatePlanSuggestions(request: GeneratePlanSuggestionsRequest): Promise<PlanSuggestions> {
  const response = await api.post<PlanSuggestions>('/research/plans/generate', request);
  return response.data;
}

/**
 * Create Research Plan
 * POST /research/plans
 */
export async function createResearchPlan(request: CreateResearchPlanRequest): Promise<ResearchPlan> {
  const response = await api.post<ResearchPlan>('/research/plans', request);
  return response.data;
}

/**
 * Get Research Plan
 * GET /research/plans/{plan_id}
 */
export async function getResearchPlan(planId: string): Promise<ResearchPlan> {
  const response = await api.get<ResearchPlan>(`/research/plans/${planId}`);
  return response.data;
}

/**
 * List Research Plans for Workspace
 * GET /research/workspaces/{workspace_id}/plans
 */
export async function listResearchPlans(workspaceId: number): Promise<ListResearchPlansResponse> {
  const response = await api.get<ListResearchPlansResponse>(`/research/workspaces/${workspaceId}/plans`);
  return response.data;
}

/**
 * Update Research Plan
 * PUT /research/plans/{plan_id}
 */
export async function updateResearchPlan(planId: string, request: UpdateResearchPlanRequest): Promise<ResearchPlan> {
  const response = await api.put<ResearchPlan>(`/research/plans/${planId}`, request);
  return response.data;
}

/**
 * Delete Research Plan
 * DELETE /research/plans/{plan_id}
 */
export async function deleteResearchPlan(planId: string): Promise<{ success: boolean }> {
  const response = await api.delete<{ success: boolean }>(`/research/plans/${planId}`);
  return response.data;
}

/**
 * Export Research Plan to DocSpace
 * POST /research/plans/{plan_id}/export
 */
export async function exportResearchPlanToDocspace(planId: string): Promise<ResearchPlan> {
  const response = await api.post<ResearchPlan>(`/research/plans/${planId}/export`);
  return response.data;
}
