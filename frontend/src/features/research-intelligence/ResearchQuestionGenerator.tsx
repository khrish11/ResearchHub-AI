/**
 * Research Question Generator
 * 
 * Displays generated research questions with categories and scores.
 */

import React from 'react';
import { Target, MessageSquare, BarChart3, FileText, Plus, Save, Trash2 } from 'lucide-react';
import type { QuestionGenerationResponse, ResearchQuestion, SavedResearchQuestion } from '../../api/researchIntelligence';

interface ResearchQuestionGeneratorProps {
  questions: QuestionGenerationResponse;
  onAddToWorkspace: (question: ResearchQuestion) => void;
  onChallengeQuestion: (question: ResearchQuestion) => void;
  onSaveQuestion?: (question: ResearchQuestion) => Promise<void>;
  savedQuestions?: SavedResearchQuestion[];
  onDeleteSavedQuestion?: (questionId: string) => Promise<void>;
}

const CATEGORY_LABELS: Record<string, string> = {
  exploratory: 'Exploratory',
  confirmatory: 'Confirmatory',
  comparative: 'Comparative',
  causal: 'Causal',
};

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  exploratory: <Target className="h-4 w-4" />,
  confirmatory: <MessageSquare className="h-4 w-4" />,
  comparative: <BarChart3 className="h-4 w-4" />,
  causal: <FileText className="h-4 w-4" />,
};

export const ResearchQuestionGenerator: React.FC<ResearchQuestionGeneratorProps> = ({
  questions,
  onAddToWorkspace,
  onChallengeQuestion,
  onSaveQuestion,
  savedQuestions = [],
  onDeleteSavedQuestion,
}) => {
  const getScoreColor = (value: number): string => {
    if (value >= 80) return 'text-emerald-600';
    if (value >= 60) return 'text-amber-600';
    return 'text-rose-600';
  };

  const getScoreBg = (value: number): string => {
    if (value >= 80) return 'bg-emerald-100';
    if (value >= 60) return 'bg-amber-100';
    return 'bg-rose-100';
  };

  const QuestionCard: React.FC<{ question: ResearchQuestion; rank: number }> = ({ question, rank }) => (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-md transition">
      <div className="mb-3">
        <div className="flex items-center gap-2 mb-2">
          <div className={`rounded-lg p-1.5 ${getScoreBg(question.novelty)}`}>
            {CATEGORY_ICONS[question.category] || <Target className="h-4 w-4 text-slate-600" />}
          </div>
          <span className="text-xs font-medium text-slate-500 uppercase">
            {CATEGORY_LABELS[question.category] || question.category}
          </span>
          {rank <= 3 && (
            <span className="ml-auto rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-semibold text-indigo-700">
              Top #{rank}
            </span>
          )}
        </div>
        <p className="text-base font-semibold text-slate-900">{question.question}</p>
      </div>

      <div className="mb-3 grid grid-cols-4 gap-2">
        <div>
          <p className="text-xs text-slate-500">Complexity</p>
          <p className={`text-sm font-bold ${getScoreColor(question.complexity)}`}>{question.complexity}/100</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Novelty</p>
          <p className={`text-sm font-bold ${getScoreColor(question.novelty)}`}>{question.novelty}/100</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Impact</p>
          <p className={`text-sm font-bold ${getScoreColor(question.impact)}`}>{question.impact}/100</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Feasibility</p>
          <p className={`text-sm font-bold ${getScoreColor(question.feasibility)}`}>{question.feasibility}/100</p>
        </div>
      </div>

      {question.rationale && (
        <div className="mb-3 rounded-lg bg-slate-50 p-3">
          <p className="text-xs text-slate-600">{question.rationale}</p>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {onSaveQuestion && (
          <button
            onClick={() => void onSaveQuestion(question)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-300 bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100 transition"
          >
            <Save className="h-3.5 w-3.5" />
            Save Question
          </button>
        )}
        <button
          onClick={() => onAddToWorkspace(question)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition"
        >
          <Plus className="h-3.5 w-3.5" />
          Add to Workspace
        </button>
        <button
          onClick={() => onChallengeQuestion(question)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition"
        >
          <MessageSquare className="h-3.5 w-3.5" />
          Challenge Question
        </button>
      </div>
    </div>
  );

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-slate-900">Research Questions</h2>
        <p className="mt-1 text-sm text-slate-500">
          Generated research questions based on identified gaps and opportunities
        </p>
      </div>

      {/* Top Questions */}
      {questions.top_questions.length > 0 && (
        <div className="mb-6">
          <p className="text-sm font-semibold text-slate-900 mb-3">Top Questions</p>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {questions.top_questions.map((question, index) => (
              <QuestionCard key={question.id} question={question} rank={index + 1} />
            ))}
          </div>
        </div>
      )}

      {/* All Questions */}
      <div>
        <p className="text-sm font-semibold text-slate-900 mb-3">All Questions ({questions.total_questions})</p>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {questions.questions.slice(0, 6).map((question, index) => (
            <QuestionCard key={question.id} question={question} rank={index + 1} />
          ))}
        </div>
      </div>

      {questions.summary && (
        <div className="mt-6 rounded-lg bg-slate-50 p-4">
          <p className="text-sm font-medium text-slate-900 mb-2">Summary</p>
          <p className="text-sm text-slate-600">{questions.summary}</p>
        </div>
      )}

      {/* Saved Questions Section */}
      {savedQuestions.length > 0 && (
        <div className="mt-6 rounded-lg border border-indigo-200 bg-indigo-50 p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-semibold text-indigo-900">Saved Questions ({savedQuestions.length})</p>
          </div>
          <div className="space-y-2">
            {savedQuestions.slice(0, 5).map((savedQ) => (
              <div key={savedQ.id} className="flex items-start justify-between rounded bg-white p-3 border border-indigo-100">
                <div className="flex-1">
                  <p className="text-sm font-medium text-slate-900">{savedQ.question}</p>
                  <div className="flex gap-2 mt-1">
                    <span className="text-xs text-slate-500">{savedQ.category}</span>
                    <span className="text-xs text-slate-500">•</span>
                    <span className="text-xs text-slate-500">Impact: {savedQ.impact}</span>
                  </div>
                </div>
                {onDeleteSavedQuestion && (
                  <button
                    onClick={() => void onDeleteSavedQuestion(savedQ.id)}
                    className="ml-2 text-slate-400 hover:text-red-600 transition"
                    title="Delete question"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
