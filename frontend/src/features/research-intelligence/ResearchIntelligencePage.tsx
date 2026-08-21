/**
 * Research Intelligence Page
 * 
 * Main page for the unified Research Intelligence experience.
 * Integrates all intelligence components into a cohesive workflow.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Loader2, AlertCircle } from 'lucide-react';
import Layout from '../../components/Layout';
import api from '../../api';
import { useToast } from '../../contexts/ToastContext';
import {
  analyzeEvidence,
  detectGaps,
  rankOpportunities,
  generateQuestions,
  challengeHypothesis,
  verifyCitations,
  enhanceKnowledgeGraph,
  createResearchIntelligenceArtifact,
  getResearchIntelligenceArtifact,
  listWorkspaceResearchIntelligenceArtifacts,
  deleteResearchIntelligenceArtifact,
  saveResearchQuestion,
  listSavedResearchQuestions,
  deleteSavedResearchQuestion,
  generatePlanSuggestions,
  createResearchPlan,
} from '../../api/researchIntelligence';
import type {
  ResearchQuestion,
  ResearchIntelligenceArtifact,
  SavedResearchQuestion,
  ResearchOpportunity,
  PlanSuggestions,
} from '../../api/researchIntelligence';
import type {
  PipelineStage,
  ResearchIntelligenceState,
  EvidenceTraceData,
  ScorecardData,
} from './types';
import { ResearchIntelligenceHeader } from './ResearchIntelligenceHeader';
import { IntelligencePipeline } from './IntelligencePipeline';
import { IntelligenceScorecard } from './IntelligenceScorecard';
import { EvidenceLandscape } from './EvidenceLandscape';
import { GapIntelligence } from './GapIntelligence';
import { OpportunityRanking } from './OpportunityRanking';
import { ResearchQuestionGenerator } from './ResearchQuestionGenerator';
import { HypothesisChallenger } from './HypothesisChallenger';
import { CitationIntegrity } from './CitationIntegrity';
import { EvidenceTrace } from './EvidenceTrace';
import { ResearchPlanBuilder } from './ResearchPlanBuilder';

const ResearchIntelligencePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { error: toastError, success: toastSuccess } = useToast();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Workspace data
  const [workspace, setWorkspace] = useState<{ id: number; name: string; papers: Array<{ id: number }> } | null>(null);
  const [topic, setTopic] = useState('');

  // Intelligence state
  const [state, setState] = useState<ResearchIntelligenceState>({
    workspaceId: null,
    topic: '',
    paperIds: [],
    pipeline: {
      evidence: { status: 'idle' },
      gaps: { status: 'idle' },
      opportunities: { status: 'idle' },
      questions: { status: 'idle' },
      challenge: { status: 'idle' },
      citations: { status: 'idle' },
      graph: { status: 'idle' },
    },
    evidence: null,
    gaps: null,
    opportunities: null,
    questions: null,
    challenge: null,
    citations: null,
    graph: null,
    selectedGapId: null,
    selectedOpportunityId: null,
    selectedQuestionId: null,
    hypothesisInput: '',
    showEvidenceTrace: false,
    evidenceTraceData: null,
  });

  // Artifact history state
  const [artifacts, setArtifacts] = useState<ResearchIntelligenceArtifact[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [viewMode, setViewMode] = useState<'current' | 'artifact'>('current');
  const [currentArtifact, setCurrentArtifact] = useState<ResearchIntelligenceArtifact | null>(null);

  // Saved research questions state
  const [savedQuestions, setSavedQuestions] = useState<SavedResearchQuestion[]>([]);

  // Research plan generation state
  const [isGeneratingPlan, setIsGeneratingPlan] = useState(false);
  const [planSuggestions, setPlanSuggestions] = useState<PlanSuggestions | null>(null);
  const [showPlanBuilder, setShowPlanBuilder] = useState(false);

  // Load workspace data
  useEffect(() => {
    if (!id) return;
    
    const loadWorkspace = async () => {
      try {
        const response = await api.get(`/workspaces/${id}`);
        setWorkspace(response.data);
        setTopic(response.data.name);
        setState(prev => ({
          ...prev,
          workspaceId: Number(id),
          topic: response.data.name,
          paperIds: response.data.papers.map((p: { id: number }) => p.id),
        }));
      } catch {
        setError('Failed to load workspace');
        toastError('Failed to load workspace');
      } finally {
        setLoading(false);
      }
    };

    void loadWorkspace();
  }, [id, toastError]);

  // Load artifact history
  useEffect(() => {
    if (!state.workspaceId) return;

    const loadArtifacts = async () => {
      try {
        const response = await listWorkspaceResearchIntelligenceArtifacts(state.workspaceId!);
        setArtifacts(response.artifacts);
      } catch {
        // Silently fail - artifact feature may not be enabled
      }
    };

    void loadArtifacts();
  }, [state.workspaceId]);

  // Load saved research questions
  useEffect(() => {
    if (!state.workspaceId) return;

    const loadSavedQuestions = async () => {
      try {
        const response = await listSavedResearchQuestions(state.workspaceId!);
        setSavedQuestions(response.questions);
      } catch {
        // Silently fail - saved questions feature may not be enabled
      }
    };

    void loadSavedQuestions();
  }, [state.workspaceId]);

  // Calculate scorecard from available data
  const scorecard: ScorecardData | null = React.useMemo(() => {
    if (!state.evidence || !state.gaps) return null;

    return {
      evidenceStrength: state.evidence.strength.overall_strength,
      novelty: state.gaps.scores.novelty_potential,
      impact: state.gaps.scores.research_impact,
      feasibility: state.gaps.scores.feasibility,
      recency: state.gaps.scores.recency,
      overall: Math.round(
        (state.evidence.strength.overall_strength +
         state.gaps.scores.novelty_potential +
         state.gaps.scores.research_impact +
         state.gaps.scores.feasibility +
         state.gaps.scores.recency) / 5
      ),
      confidence: state.evidence.strength.confidence,
      explanation: 'Based on evidence strength and gap analysis scores',
    };
  }, [state.evidence, state.gaps]);

  // Save current analysis as artifact
  const handleSaveArtifact = useCallback(async () => {
    if (!state.workspaceId || !state.topic || state.paperIds.length === 0) {
      toastError('Cannot save: missing workspace, topic, or papers');
      return;
    }

    // Check if there's any analysis to save
    const hasAnalysis = state.evidence || state.gaps || state.opportunities || 
                       state.questions || state.challenge || state.citations || state.graph;
    
    if (!hasAnalysis) {
      toastError('Run at least one intelligence analysis before saving');
      return;
    }

    try {
      await createResearchIntelligenceArtifact({
        workspace_id: state.workspaceId,
        topic: state.topic,
        paper_ids: state.paperIds,
      });
      toastSuccess('Analysis saved as artifact');
      // Refresh artifacts list
      const response = await listWorkspaceResearchIntelligenceArtifacts(state.workspaceId);
      setArtifacts(response.artifacts);
    } catch {
      toastError('Failed to save artifact');
    }
  }, [state.workspaceId, state.topic, state.paperIds, state.evidence, state.gaps, 
      state.opportunities, state.questions, state.challenge, state.citations, state.graph, 
      toastError, toastSuccess]);

  // Load artifact
  const handleLoadArtifact = useCallback(async (artifactId: string) => {
    try {
      const artifact = await getResearchIntelligenceArtifact(artifactId);
      setCurrentArtifact(artifact);
      setViewMode('artifact');
      setShowHistory(false);
      toastSuccess('Artifact loaded');
    } catch {
      toastError('Failed to load artifact');
    }
  }, [toastError, toastSuccess]);

  // Delete artifact
  const handleDeleteArtifact = useCallback(async (artifactId: string) => {
    if (!confirm('Are you sure you want to delete this artifact?')) return;

    try {
      await deleteResearchIntelligenceArtifact(artifactId);
      toastSuccess('Artifact deleted');
      // Refresh artifacts list
      if (state.workspaceId) {
        const response = await listWorkspaceResearchIntelligenceArtifacts(state.workspaceId);
        setArtifacts(response.artifacts);
      }
      // If viewing the deleted artifact, switch back to current view
      if (currentArtifact?.id === artifactId) {
        setCurrentArtifact(null);
        setViewMode('current');
      }
    } catch {
      toastError('Failed to delete artifact');
    }
  }, [state.workspaceId, currentArtifact, toastError, toastSuccess]);

  // Save a research question
  const handleSaveQuestion = useCallback(async (question: ResearchQuestion) => {
    if (!state.workspaceId) {
      toastError('Cannot save: missing workspace');
      return;
    }

    try {
      // Convert ResearchQuestion type to SaveResearchQuestionRequest format
      const complexityMap: Record<number, string> = {
        1: 'simple',
        2: 'moderate',
        3: 'complex',
      };
      const confidenceMap: Record<string, number> = {
        high: 85,
        medium: 60,
        low: 35,
      };

      await saveResearchQuestion({
        workspace_id: state.workspaceId,
        question: question.question,
        category: question.category,
        complexity: complexityMap[question.complexity] || 'moderate',
        confidence: confidenceMap[question.confidence] || 60,
        novelty: question.novelty,
        feasibility: question.feasibility,
        impact: question.impact,
        source_gap_id: question.source_gap_id,
        source_gap_description: question.source_gap_description,
        supporting_papers: question.supporting_papers,
        rationale: question.rationale,
        source_artifact_id: currentArtifact?.id,
      });
      toastSuccess('Question saved');
      // Refresh saved questions list
      const response = await listSavedResearchQuestions(state.workspaceId);
      setSavedQuestions(response.questions);
    } catch {
      toastError('Failed to save question');
    }
  }, [state.workspaceId, currentArtifact, toastError, toastSuccess]);

  // Delete a saved research question
  const handleDeleteSavedQuestion = useCallback(async (questionId: string) => {
    if (!confirm('Are you sure you want to delete this question?')) return;

    try {
      await deleteSavedResearchQuestion(questionId);
      toastSuccess('Question deleted');
      // Refresh saved questions list
      if (state.workspaceId) {
        const response = await listSavedResearchQuestions(state.workspaceId);
        setSavedQuestions(response.questions);
      }
    } catch {
      toastError('Failed to delete question');
    }
  }, [state.workspaceId, toastError, toastSuccess]);

  // Switch back to current analysis view
  const handleBackToCurrent = useCallback(() => {
    setCurrentArtifact(null);
    setViewMode('current');
  }, []);

  // Handle develop research plan from opportunity
  const handleDevelopPlan = useCallback(async (opportunity: ResearchOpportunity) => {
    if (!currentArtifact || !state.workspaceId) {
      toastError('Cannot generate plan: missing artifact or workspace');
      return;
    }

    setIsGeneratingPlan(true);
    try {
      // Generate plan suggestions
      const suggestions = await generatePlanSuggestions({
        artifact_id: currentArtifact.id,
        opportunity_id: opportunity.gap_id,
        gap_description: opportunity.gap_description,
        category: opportunity.category,
        evidence_strength: opportunity.evidence_strength,
        novelty: opportunity.novelty,
        impact: opportunity.impact,
        feasibility: opportunity.feasibility,
        recency: opportunity.recency,
        overall_score: opportunity.overall_score,
        explanation: opportunity.explanation,
        supporting_papers: opportunity.supporting_papers,
        affected_papers: opportunity.affected_papers,
      });

      setPlanSuggestions(suggestions);
      setShowPlanBuilder(true);
      toastSuccess('Plan suggestions generated');
    } catch {
      toastError('Failed to generate plan suggestions');
    } finally {
      setIsGeneratingPlan(false);
    }
  }, [currentArtifact, state.workspaceId, toastError, toastSuccess]);

  // Handle save research plan
  const handleSavePlan = useCallback(async (planData: PlanSuggestions) => {
    if (!state.workspaceId || !currentArtifact) {
      toastError('Cannot save plan: missing workspace or artifact');
      return;
    }

    try {
      await createResearchPlan({
        workspace_id: state.workspaceId,
        artifact_id: currentArtifact.id,
        opportunity_id: planSuggestions?.opportunity_id || '',
        opportunity_description: planSuggestions?.opportunity_description || '',
        title: planData.title,
        research_problem: planData.research_problem,
        research_question: planData.research_question,
        hypothesis: planData.hypothesis,
        objectives: planData.objectives,
        proposed_methodology: planData.proposed_methodology,
        alternative_methodology: planData.alternative_methodology,
        datasets: planData.datasets,
        variables: planData.variables,
        baselines: planData.baselines,
        evaluation_metrics: planData.evaluation_metrics,
        expected_contribution: planData.expected_contribution,
        risks: planData.risks,
        limitations: planData.limitations,
        reproducibility_requirements: planData.reproducibility_requirements,
        supporting_papers: planSuggestions?.supporting_papers || [],
        evidence_references: planSuggestions?.evidence_references || [],
        status: 'draft',
      });

      setShowPlanBuilder(false);
      setPlanSuggestions(null);
      toastSuccess('Research plan saved successfully');
    } catch {
      toastError('Failed to save research plan');
    }
  }, [state.workspaceId, currentArtifact, planSuggestions, toastError, toastSuccess]);

  // Handle cancel plan builder
  const handleCancelPlan = useCallback(() => {
    setShowPlanBuilder(false);
    setPlanSuggestions(null);
  }, []);

  // Generate research report from artifact
  const handleGenerateReport = useCallback(async () => {
    if (!currentArtifact || !state.workspaceId) return;

    try {
      const response = await api.post('/research/generate-report', {
        paper_ids: currentArtifact.paper_ids,
        topic: currentArtifact.topic,
        intelligence_artifact_id: currentArtifact.id,
      });

      // Navigate to report page with the generated report
      const reportData = response.data.result;
      // Store the report data in sessionStorage for the report page to retrieve
      sessionStorage.setItem('generatedReport', JSON.stringify(reportData));
      sessionStorage.setItem('reportArtifactId', currentArtifact.id);
      sessionStorage.setItem('reportWorkspaceId', state.workspaceId.toString());
      
      navigate(`/research-report?artifact_id=${currentArtifact.id}&workspace_id=${state.workspaceId}`);
      toastSuccess('Research report generated successfully');
    } catch (err) {
      toastError('Failed to generate research report');
      console.error(err);
    }
  }, [currentArtifact, state.workspaceId, navigate, toastError, toastSuccess]);

  // Run intelligence stage
  const runStage = useCallback(async (stage: PipelineStage) => {
    if (!state.workspaceId) return;

    setState(prev => ({
      ...prev,
      pipeline: {
        ...prev.pipeline,
        [stage]: { status: 'loading' },
      },
    }));

    try {
      const baseRequest = {
        workspace_id: state.workspaceId,
        topic: state.topic,
        paper_ids: state.paperIds.length > 0 ? state.paperIds : undefined,
      };

      switch (stage) {
        case 'evidence': {
          // Evidence analysis requires a claim - use topic as default claim
          const result = await analyzeEvidence({
            ...baseRequest,
            claim: state.topic || 'Analyze evidence for this research topic',
          });
          setState(prev => ({
            ...prev,
            evidence: result,
            pipeline: {
              ...prev.pipeline,
              evidence: { status: 'success', resultCount: result.classification.supporting_count + result.classification.contradicting_count },
            },
          }));
          toastSuccess('Evidence analysis complete');
          break;
        }
        case 'gaps': {
          const result = await detectGaps(baseRequest);
          setState(prev => ({
            ...prev,
            gaps: result,
            pipeline: {
              ...prev.pipeline,
              gaps: { status: 'success', resultCount: Object.values(result.gaps_by_category).flat().length },
            },
          }));
          toastSuccess('Gap detection complete');
          break;
        }
        case 'opportunities': {
          const result = await rankOpportunities(baseRequest);
          setState(prev => ({
            ...prev,
            opportunities: result,
            pipeline: {
              ...prev.pipeline,
              opportunities: { status: 'success', resultCount: result.opportunities.length },
            },
          }));
          toastSuccess('Opportunity ranking complete');
          break;
        }
        case 'questions': {
          const result = await generateQuestions({ ...baseRequest, max_questions: 10 });
          setState(prev => ({
            ...prev,
            questions: result,
            pipeline: {
              ...prev.pipeline,
              questions: { status: 'success', resultCount: result.questions.length },
            },
          }));
          toastSuccess('Question generation complete');
          break;
        }
        case 'citations': {
          const result = await verifyCitations(baseRequest);
          setState(prev => ({
            ...prev,
            citations: result,
            pipeline: {
              ...prev.pipeline,
              citations: { status: 'success', resultCount: result.verifications.length },
            },
          }));
          toastSuccess('Citation verification complete');
          break;
        }
        case 'graph': {
          const result = await enhanceKnowledgeGraph({ ...baseRequest, layers: ['gap', 'evidence', 'opportunity'] });
          setState(prev => ({
            ...prev,
            graph: result,
            pipeline: {
              ...prev.pipeline,
              graph: { status: 'success', resultCount: result.enhanced_nodes },
            },
          }));
          toastSuccess('Knowledge graph enhancement complete');
          break;
        }
        default:
          break;
      }
    } catch (err) {
      setState(prev => ({
        ...prev,
        pipeline: {
          ...prev.pipeline,
          [stage]: { status: 'error', error: err instanceof Error ? err.message : 'Failed to complete analysis' },
        },
      }));
      toastError(`Failed to complete ${stage} analysis`);
    }
  }, [state.workspaceId, state.topic, state.paperIds, toastError, toastSuccess]);

  // Run initial analysis (evidence + gaps)
  const runInitialAnalysis = useCallback(() => {
    void runStage('evidence');
    void runStage('gaps');
  }, [runStage]);

  // Check if stage can be run
  const canRunStage = useCallback((stage: PipelineStage): boolean => {
    // Don't allow running stages if already loading
    if (state.pipeline[stage]?.status === 'loading') {
      return false;
    }
    
    switch (stage) {
      case 'evidence':
      case 'gaps':
        return state.workspaceId !== null && state.paperIds.length > 0;
      case 'opportunities':
        return state.pipeline.gaps.status === 'success';
      case 'questions':
        return state.pipeline.gaps.status === 'success';
      case 'challenge':
        return state.workspaceId !== null;
      case 'citations':
      case 'graph':
        return state.workspaceId !== null && state.paperIds.length > 0;
      default:
        return false;
    }
  }, [state.workspaceId, state.paperIds, state.pipeline]);

  // Evidence trace handlers
  const handleViewEvidence = useCallback((data: EvidenceTraceData) => {
    setState(prev => ({
      ...prev,
      showEvidenceTrace: true,
      evidenceTraceData: data,
    }));
  }, []);

  const handleCloseEvidenceTrace = useCallback(() => {
    setState(prev => ({
      ...prev,
      showEvidenceTrace: false,
      evidenceTraceData: null,
    }));
  }, []);

  // Gap handlers
  const handleRankOpportunity = useCallback(() => {
    void runStage('opportunities');
  }, [runStage]);

  const handleGenerateQuestions = useCallback(() => {
    void runStage('questions');
  }, [runStage]);

  // Question handlers
  const handleAddToWorkspace = useCallback(() => {
    // TODO: Implement add to workspace functionality
    toastSuccess('Question added to workspace (TODO: implement)');
  }, [toastSuccess]);

  const handleChallengeQuestion = useCallback((question: ResearchQuestion) => {
    setState(prev => ({
      ...prev,
      hypothesisInput: question.question,
    }));
  }, []);

  // Hypothesis handler
  const handleChallengeHypothesis = useCallback((hypothesis: string) => {
    if (!state.workspaceId) return;

    setState(prev => ({
      ...prev,
      pipeline: {
        ...prev.pipeline,
        challenge: { status: 'loading' },
      },
    }));

    challengeHypothesis({
      workspace_id: state.workspaceId,
      topic: state.topic,
      paper_ids: state.paperIds.length > 0 ? state.paperIds : undefined,
      hypothesis,
    })
      .then((result) => {
        setState(prev => ({
          ...prev,
          challenge: result,
          pipeline: {
            ...prev.pipeline,
            challenge: { status: 'success', resultCount: result.challenges.length },
          },
        }));
        toastSuccess('Hypothesis challenge complete');
      })
      .catch((err) => {
        setState(prev => ({
          ...prev,
          pipeline: {
            ...prev.pipeline,
            challenge: { status: 'error', error: err.message || 'Failed to challenge hypothesis' },
          },
        }));
        toastError('Failed to challenge hypothesis');
      });
  }, [state.workspaceId, state.topic, state.paperIds, toastSuccess, toastError]);

  // Opportunity handler
  const handleSelectOpportunity = useCallback((opportunityId: string) => {
    setState(prev => ({
      ...prev,
      selectedOpportunityId: opportunityId,
    }));
  }, []);

  if (loading) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center py-20">
          <Loader2 className="h-10 w-10 animate-spin text-indigo-500" />
          <p className="mt-4 text-sm font-medium text-slate-500">Loading Research Intelligence...</p>
        </div>
      </Layout>
    );
  }

  if (error || !workspace) {
    return (
      <Layout>
        <div className="rounded-2xl border border-red-200 bg-red-50 p-8 text-center text-red-800">
          <AlertCircle className="mx-auto mb-3 h-8 w-8 text-red-500" />
          <h3 className="text-lg font-semibold">Failed to Load</h3>
          <p className="mt-1 text-sm text-red-600">{error || 'Workspace not found'}</p>
          <button
            onClick={() => navigate(-1)}
            className="mt-4 inline-flex items-center gap-2 rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100"
          >
            Go Back
          </button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="mx-auto max-w-7xl px-4 py-8">
        {/* Header */}
        <ResearchIntelligenceHeader
          topic={topic}
          workspaceName={workspace.name}
          paperCount={workspace.papers.length}
          scorecard={scorecard}
        />

        {/* Artifact History Section */}
        {artifacts.length > 0 && (
          <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-700">Saved Analyses ({artifacts.length})</h3>
              <button
                onClick={() => setShowHistory(!showHistory)}
                className="text-sm text-indigo-600 hover:text-indigo-700"
              >
                {showHistory ? 'Hide' : 'Show'}
              </button>
            </div>
            {showHistory && (
              <div className="space-y-2">
                {artifacts.map((artifact) => (
                  <div
                    key={artifact.id}
                    className="flex items-center justify-between rounded border border-gray-100 bg-gray-50 p-3 hover:bg-gray-100"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-900">{artifact.topic}</span>
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          artifact.status === 'completed' ? 'bg-green-100 text-green-800' :
                          artifact.status === 'partial' ? 'bg-yellow-100 text-yellow-800' :
                          artifact.status === 'failed' ? 'bg-red-100 text-red-800' :
                          'bg-blue-100 text-blue-800'
                        }`}>
                          {artifact.status}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-4 text-xs text-gray-500">
                        <span>{artifact.paper_count} papers</span>
                        <span>{new Date(artifact.updated_at).toLocaleDateString()}</span>
                        {artifact.overall_score !== undefined && (
                          <span>Score: {artifact.overall_score}/100</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleLoadArtifact(artifact.id)}
                        className="rounded px-3 py-1.5 text-xs font-medium text-indigo-600 hover:bg-indigo-50"
                      >
                        Load
                      </button>
                      <button
                        onClick={() => handleDeleteArtifact(artifact.id)}
                        className="rounded px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Back to Current button when viewing artifact */}
        {viewMode === 'artifact' && currentArtifact && (
          <div className="mb-6 flex items-center justify-between">
            <button
              onClick={handleBackToCurrent}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              ← Back to Current Analysis
            </button>
            {currentArtifact.status === 'completed' && (
              <button
                onClick={handleGenerateReport}
                disabled={currentArtifact.paper_ids.length === 0}
                className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition shadow disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Generate Research Report
              </button>
            )}
            {currentArtifact.status !== 'completed' && (
              <div className="text-sm text-gray-500 italic">
                Artifact status: {currentArtifact.status} - report generation requires completed analysis
              </div>
            )}
          </div>
        )}

        {/* Save Artifact button */}
        {viewMode === 'current' && (
          <div className="mb-6 flex justify-end">
            <button
              onClick={handleSaveArtifact}
              disabled={!state.workspaceId || state.paperIds.length === 0}
              className="inline-flex items-center gap-2 rounded-lg border border-indigo-300 bg-indigo-50 px-4 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-100 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Save Analysis
            </button>
          </div>
        )}

        {/* Run Initial Analysis Button */}
        {viewMode === 'current' && state.pipeline.evidence.status === 'idle' && state.pipeline.gaps.status === 'idle' && (
          <div className="mb-6 flex justify-center">
            <button
              onClick={runInitialAnalysis}
              disabled={state.paperIds.length === 0}
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-6 py-3 text-base font-semibold text-white hover:bg-indigo-700 transition shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Loader2 className="h-5 w-5" />
              {state.paperIds.length === 0 ? 'Add papers to workspace first' : 'Run Intelligence Analysis'}
            </button>
          </div>
        )}

        {/* Pipeline */}
        <div className="mb-8">
          <IntelligencePipeline
            pipeline={state.pipeline}
            onRunStage={runStage}
            canRunStage={canRunStage}
          />
        </div>

        {/* Results */}
        <div className="space-y-8">
          {/* Scorecard */}
          {scorecard && (
            <div>
              <IntelligenceScorecard scorecard={scorecard} />
            </div>
          )}

          {/* Evidence */}
          {state.evidence && (
            <EvidenceLandscape
              evidence={state.evidence}
              onViewEvidence={handleViewEvidence}
            />
          )}

          {/* Gaps */}
          {state.gaps && (
            <GapIntelligence
              gaps={state.gaps}
              onViewEvidence={handleViewEvidence}
              onRankOpportunity={handleRankOpportunity}
              onGenerateQuestions={handleGenerateQuestions}
            />
          )}

          {/* Opportunities */}
          {state.opportunities && (
            <OpportunityRanking
              opportunities={state.opportunities}
              onSelectOpportunity={handleSelectOpportunity}
              onDevelopPlan={handleDevelopPlan}
              artifactId={currentArtifact?.id}
            />
          )}

          {/* Questions */}
          {state.questions && (
            <ResearchQuestionGenerator
              questions={state.questions}
              onAddToWorkspace={handleAddToWorkspace}
              onChallengeQuestion={handleChallengeQuestion}
              onSaveQuestion={handleSaveQuestion}
              savedQuestions={savedQuestions}
              onDeleteSavedQuestion={handleDeleteSavedQuestion}
            />
          )}

          {/* Hypothesis Challenger */}
          <HypothesisChallenger
            challenge={state.challenge}
            onChallengeHypothesis={handleChallengeHypothesis}
            isLoading={state.pipeline.challenge.status === 'loading'}
          />

          {/* Citations */}
          {state.citations && (
            <CitationIntegrity citations={state.citations} />
          )}
        </div>

        {/* Research Plan Builder Modal */}
        {showPlanBuilder && planSuggestions && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
            <div className="max-h-[90vh] w-full max-w-4xl overflow-y-auto p-4">
              <ResearchPlanBuilder
                suggestions={planSuggestions}
                onSavePlan={handleSavePlan}
                onCancel={handleCancelPlan}
                isLoading={isGeneratingPlan}
              />
            </div>
          </div>
        )}

        {/* Evidence Trace Modal */}
        {state.showEvidenceTrace && (
          <EvidenceTrace
            data={state.evidenceTraceData}
            onClose={handleCloseEvidenceTrace}
          />
        )}
      </div>
    </Layout>
  );
};

export default ResearchIntelligencePage;
