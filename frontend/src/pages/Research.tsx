import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Search, ArrowRight, BrainCircuit, Upload, BookOpen, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import Layout from '../components/Layout';
import { classifyQuery, saveResearchQuestion, type QueryClassificationResponse, type SaveResearchQuestionRequest } from '../api/researchIntelligence';
import { saveResearchContext } from '../features/search/searchUtils';
import type { ResearchSearchContext } from '../features/search/types';

type ResearchState = 'idle' | 'classifying' | 'clarifying' | 'ready' | 'starting' | 'saving' | 'save_success' | 'save_error' | 'workspace_required' | 'error';

const Research: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialQuery = searchParams.get('q') || '';
  
  const [researchQuery, setResearchQuery] = useState(initialQuery);
  const [queryError, setQueryError] = useState('');
  
  const [researchState, setResearchState] = useState<ResearchState>('idle');
  const [classificationResult, setClassificationResult] = useState<QueryClassificationResponse | null>(null);
  const [clarificationAnswers, setClarificationAnswers] = useState<Record<string, string>>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  
  // Get workspace ID from session state if available
  const [workspaceId, setWorkspaceId] = useState<number | null>(null);
  
  useEffect(() => {
    // Try to get workspace ID from session state
    const sessionState = sessionStorage.getItem('researchhub_session_state');
    if (sessionState) {
      try {
        const parsed = JSON.parse(sessionState);
        if (parsed.workspace_id) {
          setWorkspaceId(parsed.workspace_id);
        }
      } catch {
        // Ignore parse errors
      }
    }
  }, []);
  
  const handleContinue = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!researchQuery.trim()) {
      setQueryError('Please enter a research topic or question');
      return;
    }
    
    setQueryError('');
    setResearchState('classifying');
    setApiError(null);
    
    try {
      const result = await classifyQuery({ query: researchQuery.trim() });
      setClassificationResult(result);
      
      if (result.classification.requires_clarification && result.clarification_questions.length > 0) {
        setResearchState('clarifying');
      } else {
        setResearchState('ready');
      }
    } catch (error) {
      console.error('Classification failed:', error);
      setApiError('Unable to classify your query. You can continue to search directly.');
      setResearchState('ready'); // Allow user to proceed even if classification fails
    }
  };
  
  const handleClarificationAnswer = (questionId: string, answer: string) => {
    setClarificationAnswers(prev => ({ ...prev, [questionId]: answer }));
  };
  
  const handleSkipClarification = () => {
    setResearchState('ready');
  };
  
  const getEnhancedResearchDirection = () => {
    if (!classificationResult) return null;
    
    const baseDirection = classificationResult.research_direction;
    const focusAnswer = clarificationAnswers['focus'];
    const researchTypeAnswer = clarificationAnswers['research_type'];
    
    return {
      topic: baseDirection?.topic || researchQuery,
      focus: focusAnswer || baseDirection?.focus || null,
      research_intent: researchTypeAnswer || baseDirection?.research_intent || classificationResult.classification.user_friendly_description,
      suggested_scope: baseDirection?.suggested_scope || '2020–2026',
      research_type: researchTypeAnswer || null,
    };
  };
  
  const handleStartResearch = () => {
    setResearchState('starting');
    
    // Save research context to sessionStorage
    const enhancedDirection = getEnhancedResearchDirection();
    const context: ResearchSearchContext = {
      query: researchQuery.trim(),
      intent: classificationResult?.classification.category || null,
      focus: enhancedDirection?.focus || null,
      research_type: enhancedDirection?.research_type || null,
      research_intent: enhancedDirection?.research_intent || null,
      suggested_scope: enhancedDirection?.suggested_scope || null,
      created_at: Date.now(),
    };
    saveResearchContext(context);
    
    // Navigate to search with the query
    navigate(`/search?q=${encodeURIComponent(researchQuery.trim())}`);
  };
  
  const handleDeepResearch = () => {
    setResearchState('starting');
    navigate('/research-agent');
  };
  
  const handleCreateWorkspace = () => {
    setResearchState('starting');
    navigate('/workspaces');
  };
  
  const handleSaveQuestion = async () => {
    if (!workspaceId) {
      setResearchState('workspace_required');
      return;
    }
    
    setResearchState('saving');
    setSaveError(null);
    
    try {
      const enhancedDirection = getEnhancedResearchDirection();
      const confidence = classificationResult?.classification.confidence || 0.7;
      
      // Calculate scores based on classification confidence instead of hardcoded values
      // This provides dynamic scoring based on query quality assessment
      const baseScore = Math.round(confidence * 100);
      
      const saveRequest: SaveResearchQuestionRequest = {
        workspace_id: workspaceId,
        question: researchQuery.trim(),
        category: classificationResult?.classification.category || 'topic_exploration',
        complexity: 'moderate',
        confidence: confidence,
        novelty: baseScore,
        feasibility: baseScore,
        impact: baseScore,
        rationale: enhancedDirection?.research_intent || classificationResult?.classification.user_friendly_description,
      };
      
      await saveResearchQuestion(saveRequest);
      setResearchState('save_success');
    } catch (error) {
      console.error('Save question failed:', error);
      setSaveError('Unable to save your research question. Please try again.');
      setResearchState('save_error');
    }
  };
  
  const handleViewSavedQuestions = () => {
    if (workspaceId) {
      navigate(`/library?tab=questions&workspace=${workspaceId}`);
    } else {
      navigate('/library');
    }
  };
  
  const handleContinueResearch = () => {
    setResearchState('ready');
  };
  
  const handleCreateWorkspaceForSave = () => {
    navigate('/workspaces');
  };
  
  const getLoadingMessage = () => {
    switch (researchState) {
      case 'classifying':
        return 'Understanding your research...';
      case 'clarifying':
        return 'Refining your research question...';
      case 'starting':
        return 'Starting your research...';
      case 'saving':
        return 'Saving your research question...';
      default:
        return 'Loading...';
    }
  };
  
  const getCategoryDescription = (category: string) => {
    const descriptions: Record<string, string> = {
      'topic_exploration': 'You seem to be exploring a research topic.',
      'research_question': 'This looks like a specific research question.',
      'problem_investigation': 'You appear to be investigating a problem.',
      'literature_review': 'This seems to be a literature review.',
      'comparison': 'You appear to be comparing different approaches.',
      'methodology': 'This looks like a methodology investigation.',
      'trend_analysis': 'You seem to be exploring trends or state-of-the-art.',
      'ambiguous': 'Your query could be interpreted in multiple ways.',
    };
    return descriptions[category] || 'Understanding your research intent...';
  };
  
  return (
    <Layout>
      <div className="mx-auto max-w-4xl px-4 py-12">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Research
          </h1>
          <p className="mt-2 text-lg text-slate-600 dark:text-slate-400">
            What exactly do you want to investigate?
          </p>
        </div>
        
        {/* Research Input */}
        {researchState === 'idle' || researchState === 'error' ? (
          <div className="mb-8">
            <form onSubmit={handleContinue}>
              <label htmlFor="research-input" className="sr-only">
                What are you researching?
              </label>
              <div className="relative">
                <input
                  id="research-input"
                  type="text"
                  value={researchQuery}
                  onChange={(e) => setResearchQuery(e.target.value)}
                  placeholder="What are you researching?"
                  className="w-full rounded-xl border border-slate-300 bg-white px-5 py-4 pr-12 text-lg shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:placeholder-slate-400 dark:focus:border-indigo-400 dark:focus:ring-indigo-400"
                  aria-describedby={queryError ? 'query-error' : undefined}
                />
                <div className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400">
                  <Search className="h-5 w-5" />
                </div>
              </div>
              {queryError && (
                <p id="query-error" className="mt-2 text-sm text-red-600 dark:text-red-400" role="alert">
                  {queryError}
                </p>
              )}
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                Enter a topic, research question, or problem you want to investigate.
              </p>
              <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:gap-4">
                <button
                  type="submit"
                  className="inline-flex items-center justify-center rounded-xl bg-indigo-600 px-6 py-3 text-base font-semibold text-white shadow-sm transition-colors hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:bg-indigo-500 dark:hover:bg-indigo-600 dark:focus:ring-indigo-400"
                >
                  Continue
                  <ArrowRight className="ml-2 h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={handleCreateWorkspace}
                  className="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-6 py-3 text-base font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 dark:focus:ring-indigo-400"
                >
                  Create Workspace
                </button>
                <button
                  type="button"
                  onClick={() => navigate('/upload')}
                  className="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-6 py-3 text-base font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 dark:focus:ring-indigo-400"
                >
                  <Upload className="mr-2 h-4 w-4" />
                  Upload Papers
                </button>
              </div>
            </form>
          </div>
        ) : null}
        
        {/* Loading State */}
        {(researchState === 'classifying' || researchState === 'clarifying' || researchState === 'starting') && (
          <div className="mb-8 flex flex-col items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-600 dark:text-indigo-400" />
            <p className="mt-4 text-lg text-slate-600 dark:text-slate-400">{getLoadingMessage()}</p>
          </div>
        )}
        
        {/* Clarification Questions */}
        {researchState === 'clarifying' && classificationResult && (
          <div className="mb-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <h2 className="mb-4 text-xl font-semibold text-slate-900 dark:text-slate-100">
              Let's refine your research
            </h2>
            <p className="mb-6 text-slate-600 dark:text-slate-400">
              To provide better results, please answer a few questions:
            </p>
            
            {classificationResult.clarification_questions.slice(0, 3).map((question) => (
              <div key={question.id} className="mb-6">
                <label htmlFor={`question-${question.id}`} className="mb-3 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  {question.question}
                </label>
                <div className="space-y-2">
                  {question.options.map((option, idx) => (
                    <label
                      key={idx}
                      htmlFor={`question-${question.id}-option-${idx}`}
                      className="flex cursor-pointer items-center rounded-lg border border-slate-200 p-3 transition-colors hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700"
                    >
                      <input
                        id={`question-${question.id}-option-${idx}`}
                        type="radio"
                        name={`question-${question.id}`}
                        value={option}
                        checked={clarificationAnswers[question.id] === option}
                        onChange={(e) => handleClarificationAnswer(question.id, e.target.value)}
                        className="h-4 w-4 border-slate-300 text-indigo-600 focus:ring-indigo-500 dark:border-slate-600 dark:bg-slate-800 dark:text-indigo-400 dark:focus:ring-indigo-400"
                      />
                      <span className="ml-3 text-sm text-slate-700 dark:text-slate-300">{option}</span>
                    </label>
                  ))}
                </div>
              </div>
            ))}
            
            <div className="flex flex-col gap-3 sm:flex-row sm:gap-4">
              <button
                onClick={handleSkipClarification}
                className="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-6 py-3 text-base font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 dark:focus:ring-indigo-400"
              >
                Skip
              </button>
              <button
                onClick={() => setResearchState('ready')}
                className="inline-flex items-center justify-center rounded-xl bg-indigo-600 px-6 py-3 text-base font-semibold text-white shadow-sm transition-colors hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:bg-indigo-500 dark:hover:bg-indigo-600 dark:focus:ring-indigo-400"
              >
                Continue
                <ArrowRight className="ml-2 h-4 w-4" />
              </button>
            </div>
          </div>
        )}
        
        {/* Research Direction */}
        {researchState === 'ready' && classificationResult && (
          <div className="mb-8">
            {/* Classification */}
            <div className="mb-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
              <div className="flex items-start gap-4">
                <div className="mt-1 rounded-full bg-indigo-100 p-2 text-indigo-600 dark:bg-indigo-900 dark:text-indigo-300">
                  <CheckCircle2 className="h-5 w-5" />
                </div>
                <div className="flex-1">
                  <h2 className="mb-2 text-lg font-semibold text-slate-900 dark:text-slate-100">
                    {getCategoryDescription(classificationResult.classification.category)}
                  </h2>
                  <p className="text-sm text-slate-600 dark:text-slate-400">
                    {classificationResult.classification.user_friendly_description}
                  </p>
                </div>
              </div>
            </div>
            
            {/* Research Direction Summary */}
            {(() => {
              const enhancedDirection = getEnhancedResearchDirection();
              if (!enhancedDirection) return null;
              
              return (
                <div className="mb-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
                  <h2 className="mb-4 text-xl font-semibold text-slate-900 dark:text-slate-100">
                    Research Direction
                  </h2>
                  <div className="space-y-3">
                    <div>
                      <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Topic:</span>
                      <p className="text-base text-slate-900 dark:text-slate-100">{enhancedDirection.topic}</p>
                    </div>
                    {enhancedDirection.focus && (
                      <div>
                        <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Focus:</span>
                        <p className="text-base text-slate-900 dark:text-slate-100">{enhancedDirection.focus}</p>
                      </div>
                    )}
                    {enhancedDirection.research_type && (
                      <div>
                        <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Research type:</span>
                        <p className="text-base text-slate-900 dark:text-slate-100">{enhancedDirection.research_type}</p>
                      </div>
                    )}
                    <div>
                      <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Research intent:</span>
                      <p className="text-base text-slate-900 dark:text-slate-100">{enhancedDirection.research_intent}</p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Suggested scope:</span>
                      <p className="text-base text-slate-900 dark:text-slate-100">{enhancedDirection.suggested_scope}</p>
                    </div>
                  </div>
                </div>
              );
            })()}
            
            {/* Search Strategy Preview */}
            <div className="mb-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
              <h2 className="mb-4 text-xl font-semibold text-slate-900 dark:text-slate-100">
                Search Strategy
              </h2>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Sources</span>
                  <ul className="mt-2 space-y-1 text-sm text-slate-700 dark:text-slate-300">
                    <li>• OpenAlex</li>
                    <li>• arXiv</li>
                    <li>• PubMed</li>
                    <li>• Crossref</li>
                  </ul>
                </div>
                <div>
                  <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Focus</span>
                  <ul className="mt-2 space-y-1 text-sm text-slate-700 dark:text-slate-300">
                    <li>• Recent literature</li>
                    <li>• Highly cited work</li>
                    <li>• Methodological approaches</li>
                  </ul>
                </div>
              </div>
            </div>
            
            {/* Primary Actions */}
            <div className="flex flex-col gap-3 sm:flex-row sm:gap-4">
              <button
                onClick={handleStartResearch}
                className="inline-flex items-center justify-center rounded-xl bg-indigo-600 px-6 py-3 text-base font-semibold text-white shadow-sm transition-colors hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:bg-indigo-500 dark:hover:bg-indigo-600 dark:focus:ring-indigo-400"
              >
                <Search className="mr-2 h-4 w-4" />
                Start Research
              </button>
              <button
                onClick={handleDeepResearch}
                className="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-6 py-3 text-base font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 dark:focus:ring-indigo-400"
              >
                <BrainCircuit className="mr-2 h-4 w-4" />
                Deep Research
              </button>
              <button
                onClick={handleSaveQuestion}
                className="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-6 py-3 text-base font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 dark:focus:ring-indigo-400"
              >
                Save Research Question
              </button>
              <button
                onClick={handleCreateWorkspace}
                className="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-6 py-3 text-base font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 dark:focus:ring-indigo-400"
              >
                Create Workspace
              </button>
            </div>
          </div>
        )}
        
        {/* Error State */}
        {apiError && (
          <div className="mb-8 rounded-xl border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
              <div className="flex-1">
                <p className="text-sm text-red-800 dark:text-red-200">{apiError}</p>
              </div>
            </div>
          </div>
        )}
        
        {/* Save Success State */}
        {researchState === 'save_success' && (
          <div className="mb-8 rounded-xl border border-emerald-200 bg-emerald-50 p-6 dark:border-emerald-800 dark:bg-emerald-900/20">
            <div className="flex items-start gap-4">
              <div className="rounded-full bg-emerald-100 p-2 text-emerald-600 dark:bg-emerald-900 dark:text-emerald-300">
                <CheckCircle2 className="h-5 w-5" />
              </div>
              <div className="flex-1">
                <h3 className="mb-2 text-lg font-semibold text-emerald-900 dark:text-emerald-100">
                  Research question saved
                </h3>
                <p className="mb-4 text-sm text-emerald-800 dark:text-emerald-200">
                  Your research question has been saved to your workspace.
                </p>
                <div className="flex flex-col gap-3 sm:flex-row sm:gap-4">
                  <button
                    onClick={handleViewSavedQuestions}
                    className="inline-flex items-center justify-center rounded-xl bg-emerald-600 px-6 py-3 text-base font-semibold text-white shadow-sm transition-colors hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 dark:bg-emerald-500 dark:hover:bg-emerald-600 dark:focus:ring-emerald-400"
                  >
                    View Saved Questions
                  </button>
                  <button
                    onClick={handleContinueResearch}
                    className="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-6 py-3 text-base font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 dark:focus:ring-indigo-400"
                  >
                    Continue Research
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
        
        {/* Save Error State */}
        {researchState === 'save_error' && (
          <div className="mb-8 rounded-xl border border-red-200 bg-red-50 p-6 dark:border-red-800 dark:bg-red-900/20">
            <div className="flex items-start gap-4">
              <div className="rounded-full bg-red-100 p-2 text-red-600 dark:bg-red-900 dark:text-red-300">
                <AlertCircle className="h-5 w-5" />
              </div>
              <div className="flex-1">
                <h3 className="mb-2 text-lg font-semibold text-red-900 dark:text-red-100">
                  Unable to save research question
                </h3>
                <p className="mb-4 text-sm text-red-800 dark:text-red-200">
                  {saveError || 'An error occurred while saving your research question.'}
                </p>
                <div className="flex flex-col gap-3 sm:flex-row sm:gap-4">
                  <button
                    onClick={handleContinueResearch}
                    className="inline-flex items-center justify-center rounded-xl bg-red-600 px-6 py-3 text-base font-semibold text-white shadow-sm transition-colors hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 dark:bg-red-500 dark:hover:bg-red-600 dark:focus:ring-red-400"
                  >
                    Continue Research
                  </button>
                  <button
                    onClick={handleSaveQuestion}
                    className="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-6 py-3 text-base font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 dark:focus:ring-indigo-400"
                  >
                    Try Again
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
        
        {/* Workspace Required State */}
        {researchState === 'workspace_required' && (
          <div className="mb-8 rounded-xl border border-amber-200 bg-amber-50 p-6 dark:border-amber-800 dark:bg-amber-900/20">
            <div className="flex items-start gap-4">
              <div className="rounded-full bg-amber-100 p-2 text-amber-600 dark:bg-amber-900 dark:text-amber-300">
                <AlertCircle className="h-5 w-5" />
              </div>
              <div className="flex-1">
                <h3 className="mb-2 text-lg font-semibold text-amber-900 dark:text-amber-100">
                  Create a workspace to save this research question
                </h3>
                <p className="mb-4 text-sm text-amber-800 dark:text-amber-200">
                  You need a workspace to save research questions. Create one now to continue.
                </p>
                <div className="flex flex-col gap-3 sm:flex-row sm:gap-4">
                  <button
                    onClick={handleCreateWorkspaceForSave}
                    className="inline-flex items-center justify-center rounded-xl bg-amber-600 px-6 py-3 text-base font-semibold text-white shadow-sm transition-colors hover:bg-amber-700 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 dark:bg-amber-500 dark:hover:bg-amber-600 dark:focus:ring-amber-400"
                  >
                    Create Workspace
                  </button>
                  <button
                    onClick={handleContinueResearch}
                    className="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-6 py-3 text-base font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 dark:focus:ring-indigo-400"
                  >
                    Continue Without Saving
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
        
        {/* Quick Actions (always visible at bottom) */}
        <div className="mt-12 border-t border-slate-200 pt-8 dark:border-slate-700">
          <h2 className="mb-4 text-lg font-semibold text-slate-900 dark:text-slate-100">
            Quick Actions
          </h2>
          <div className="grid gap-4 md:grid-cols-3">
            <button
              onClick={() => navigate('/search')}
              className="group flex items-center rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition-all hover:shadow-md hover:border-indigo-300 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-indigo-600"
            >
              <div className="mr-4 rounded-lg bg-indigo-100 p-2 text-indigo-600 dark:bg-indigo-900 dark:text-indigo-300">
                <Search className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-900 dark:text-slate-100">Search Papers</h3>
                <p className="text-sm text-slate-600 dark:text-slate-400">Find papers across 28+ sources</p>
              </div>
            </button>
            <button
              onClick={handleDeepResearch}
              className="group flex items-center rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition-all hover:shadow-md hover:border-fuchsia-300 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-fuchsia-600"
            >
              <div className="mr-4 rounded-lg bg-fuchsia-100 p-2 text-fuchsia-600 dark:bg-fuchsia-900 dark:text-fuchsia-300">
                <BrainCircuit className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-900 dark:text-slate-100">Deep Research</h3>
                <p className="text-sm text-slate-600 dark:text-slate-400">AI-powered literature exploration</p>
              </div>
            </button>
            <button
              onClick={() => navigate('/library')}
              className="group flex items-center rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition-all hover:shadow-md hover:border-emerald-300 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-emerald-600"
            >
              <div className="mr-4 rounded-lg bg-emerald-100 p-2 text-emerald-600 dark:bg-emerald-900 dark:text-emerald-300">
                <BookOpen className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-900 dark:text-slate-100">Open Library</h3>
                <p className="text-sm text-slate-600 dark:text-slate-400">Access your research assets</p>
              </div>
            </button>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default Research;
