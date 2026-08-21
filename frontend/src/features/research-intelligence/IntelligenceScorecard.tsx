/**
 * Intelligence Scorecard
 * 
 * Displays the research opportunity score with breakdown of component scores.
 */

import React from 'react';
import { TrendingUp, BarChart3, Target, Clock, ShieldCheck } from 'lucide-react';
import type { ScorecardData } from './types';

interface IntelligenceScorecardProps {
  scorecard: ScorecardData;
}

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

interface ScoreRowProps {
  icon: React.ReactNode;
  label: string;
  value: number;
  explanation?: string;
}

const ScoreRow: React.FC<ScoreRowProps> = ({ icon, label, value, explanation }) => (
  <div className="flex items-start gap-3">
    <div className={`rounded-lg p-2 ${getScoreBg(value)}`}>
      {icon}
    </div>
    <div className="flex-1">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-700">{label}</p>
        <p className={`text-lg font-bold ${getScoreColor(value)}`}>{value}/100</p>
      </div>
      {explanation && (
        <p className="mt-1 text-xs text-slate-500">{explanation}</p>
      )}
    </div>
  </div>
);

export const IntelligenceScorecard: React.FC<IntelligenceScorecardProps> = ({ scorecard }) => {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Research Opportunity</h2>
          <p className="mt-1 text-sm text-slate-500">
            AI-assisted assessment based on analyzed literature
          </p>
        </div>
        <div className={`rounded-2xl ${getScoreBg(scorecard.overall)} px-6 py-3`}>
          <p className="text-sm font-medium text-slate-600">Overall</p>
          <p className={`text-3xl font-bold ${getScoreColor(scorecard.overall)}`}>
            {scorecard.overall}/100
          </p>
        </div>
      </div>

      <div className="space-y-4">
        <ScoreRow
          icon={<ShieldCheck className="h-4 w-4 text-emerald-600" />}
          label="Evidence Strength"
          value={scorecard.evidenceStrength}
          explanation="Quality and quantity of supporting evidence"
        />
        <ScoreRow
          icon={<Target className="h-4 w-4 text-indigo-600" />}
          label="Novelty"
          value={scorecard.novelty}
          explanation="Uniqueness of the research opportunity"
        />
        <ScoreRow
          icon={<TrendingUp className="h-4 w-4 text-sky-600" />}
          label="Impact"
          value={scorecard.impact}
          explanation="Potential research impact and contribution"
        />
        <ScoreRow
          icon={<BarChart3 className="h-4 w-4 text-amber-600" />}
          label="Feasibility"
          value={scorecard.feasibility}
          explanation="Practical feasibility of execution"
        />
        <ScoreRow
          icon={<Clock className="h-4 w-4 text-rose-600" />}
          label="Recency"
          value={scorecard.recency}
          explanation="Currency of supporting evidence"
        />
      </div>

      {scorecard.explanation && (
        <div className="mt-6 rounded-xl bg-slate-50 p-4">
          <p className="text-sm font-medium text-slate-700">Assessment Summary</p>
          <p className="mt-2 text-sm text-slate-600">{scorecard.explanation}</p>
        </div>
      )}
    </div>
  );
};
