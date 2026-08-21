/**
 * Gap Intelligence
 * 
 * Displays research gaps with categories, confidence scores, and action buttons.
 */

import React from 'react';
import { AlertTriangle, Target, BarChart3, FileText, TrendingUp } from 'lucide-react';
import type { GapIntelligenceResponse, StructuredGap } from '../../api/researchIntelligence';
import type { EvidenceTraceData } from './types';

interface GapIntelligenceProps {
  gaps: GapIntelligenceResponse;
  onViewEvidence: (data: EvidenceTraceData) => void;
  onRankOpportunity: (gap: StructuredGap) => void;
  onGenerateQuestions: (gap: StructuredGap) => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  methodological: 'Methodological',
  dataset: 'Dataset',
  evaluation: 'Evaluation',
  contradiction: 'Contradiction',
  generalization: 'Generalization',
};

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  methodological: <BarChart3 className="h-4 w-4" />,
  dataset: <FileText className="h-4 w-4" />,
  evaluation: <Target className="h-4 w-4" />,
  contradiction: <AlertTriangle className="h-4 w-4" />,
  generalization: <TrendingUp className="h-4 w-4" />,
};

export const GapIntelligence: React.FC<GapIntelligenceProps> = ({
  gaps,
  onViewEvidence,
  onRankOpportunity,
  onGenerateQuestions,
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

  // Flatten all gaps from all categories
  const allGaps: Array<{ gap: StructuredGap; category: string }> = [];
  Object.entries(gaps.gaps_by_category).forEach(([category, categoryGaps]) => {
    categoryGaps.forEach((gap) => {
      allGaps.push({ gap, category });
    });
  });

  // Sort by confidence (descending)
  allGaps.sort((a, b) => b.gap.confidence - a.gap.confidence);

  const GapCard: React.FC<{ gap: StructuredGap; category: string }> = ({ gap, category }) => (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-md transition">
      <div className="mb-3">
        <div className="flex items-center gap-2 mb-2">
          <div className={`rounded-lg p-1.5 ${getScoreBg(gap.confidence)}`}>
            {CATEGORY_ICONS[category] || <AlertTriangle className="h-4 w-4 text-slate-600" />}
          </div>
          <span className="text-xs font-medium text-slate-500 uppercase">
            {CATEGORY_LABELS[category] || category}
          </span>
        </div>
        <p className="text-base font-semibold text-slate-900">{gap.description}</p>
      </div>

      <div className="mb-3 grid grid-cols-3 gap-2">
        <div>
          <p className="text-xs text-slate-500">Confidence</p>
          <p className={`text-sm font-bold ${getScoreColor(gap.confidence)}`}>{gap.confidence}/100</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Novelty</p>
          <p className={`text-sm font-bold ${getScoreColor(gap.novelty_potential)}`}>{gap.novelty_potential}/100</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Impact</p>
          <p className={`text-sm font-bold ${getScoreColor(gap.research_impact)}`}>{gap.research_impact}/100</p>
        </div>
      </div>

      <div className="mb-3 grid grid-cols-2 gap-2">
        <div>
          <p className="text-xs text-slate-500">Feasibility</p>
          <p className={`text-sm font-bold ${getScoreColor(gap.feasibility)}`}>{gap.feasibility}/100</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Recency</p>
          <p className={`text-sm font-bold ${getScoreColor(gap.recency)}`}>{gap.recency}/100</p>
        </div>
      </div>

      <div className="mb-3">
        <p className="text-xs text-slate-500">Evidence</p>
        <p className="text-sm font-medium text-slate-900">{gap.evidence_count} papers</p>
      </div>

      {gap.explanation && (
        <div className="mb-3 rounded-lg bg-slate-50 p-2">
          <p className="text-xs text-slate-600">{gap.explanation}</p>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => onViewEvidence({
            insight: gap.description,
            insightType: 'gap',
            papers: gap.affected_papers.map(id => ({
              id,
              title: `Paper ${id}`,
              authors: 'Unknown',
            })),
            unavailable: gap.affected_papers.length === 0,
          })}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition"
        >
          <FileText className="h-3.5 w-3.5" />
          View Evidence
        </button>
        <button
          onClick={() => onRankOpportunity(gap)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition"
        >
          <TrendingUp className="h-3.5 w-3.5" />
          Rank Opportunity
        </button>
        <button
          onClick={() => onGenerateQuestions(gap)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition"
        >
          <Target className="h-3.5 w-3.5" />
          Generate Questions
        </button>
      </div>
    </div>
  );

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-slate-900">Research Gaps</h2>
        <p className="mt-1 text-sm text-slate-500">
          Identified research limitations and opportunities across {Object.keys(gaps.gaps_by_category).length} categories
        </p>
      </div>

      {/* Overall Scores */}
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-5">
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs text-slate-500">Overall Confidence</p>
          <p className={`text-lg font-bold ${getScoreColor(gaps.scores.overall_confidence)}`}>
            {gaps.scores.overall_confidence}/100
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs text-slate-500">Novelty Potential</p>
          <p className={`text-lg font-bold ${getScoreColor(gaps.scores.novelty_potential)}`}>
            {gaps.scores.novelty_potential}/100
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs text-slate-500">Research Impact</p>
          <p className={`text-lg font-bold ${getScoreColor(gaps.scores.research_impact)}`}>
            {gaps.scores.research_impact}/100
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs text-slate-500">Feasibility</p>
          <p className={`text-lg font-bold ${getScoreColor(gaps.scores.feasibility)}`}>
            {gaps.scores.feasibility}/100
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs text-slate-500">Recency</p>
          <p className={`text-lg font-bold ${getScoreColor(gaps.scores.recency)}`}>
            {gaps.scores.recency}/100
          </p>
        </div>
      </div>

      {/* Gap Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {allGaps.slice(0, 6).map(({ gap, category }) => (
          <GapCard key={`${category}-${gap.description}`} gap={gap} category={category} />
        ))}
      </div>

      {gaps.summary && (
        <div className="mt-6 rounded-lg bg-slate-50 p-4">
          <p className="text-sm font-medium text-slate-900 mb-2">Summary</p>
          <p className="text-sm text-slate-600">{gaps.summary}</p>
        </div>
      )}
    </div>
  );
};
