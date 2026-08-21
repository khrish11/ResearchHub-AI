/**
 * Opportunity Ranking
 * 
 * Displays ranked research opportunities with scores and comparison matrix.
 */

import React from 'react';
import { TrendingUp, ExternalLink, Rocket } from 'lucide-react';
import type { OpportunityRankingResponse, ResearchOpportunity } from '../../api/researchIntelligence';

interface OpportunityRankingProps {
  opportunities: OpportunityRankingResponse;
  onSelectOpportunity: (opportunityId: string) => void;
  onDevelopPlan?: (opportunity: ResearchOpportunity) => void;
  artifactId?: string;
}

const getScoreColor = (value: number): string => {
  if (value >= 80) return 'text-emerald-600';
  if (value >= 60) return 'text-amber-600';
  return 'text-rose-600';
};

const getScoreBg = (value: number): string => {
  if (value >= 90) return 'bg-emerald-100';
  if (value >= 70) return 'bg-amber-100';
  return 'bg-rose-100';
};

interface OpportunityCardProps {
  opportunity: ResearchOpportunity;
  rank: number;
  onSelectOpportunity: (opportunityId: string) => void;
  onDevelopPlan?: (opportunity: ResearchOpportunity) => void;
}

const OpportunityCard: React.FC<OpportunityCardProps> = ({ opportunity, rank, onSelectOpportunity, onDevelopPlan }) => (
  <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-md transition">
    <div className="flex items-start justify-between mb-3">
      <div className="flex items-center gap-3">
        <div className={`rounded-full w-10 h-10 flex items-center justify-center font-bold text-white ${getScoreBg(opportunity.overall_score)}`}>
          {rank}
        </div>
        <div>
          <p className="text-sm font-medium text-slate-500">#{rank} Opportunity</p>
          <p className="text-base font-semibold text-slate-900">{opportunity.gap_description}</p>
        </div>
      </div>
      <div className={`rounded-xl ${getScoreBg(opportunity.overall_score)} px-4 py-2`}>
        <p className={`text-2xl font-bold ${getScoreColor(opportunity.overall_score)}`}>
          {opportunity.overall_score}/100
        </p>
      </div>
    </div>

    <div className="mb-3 grid grid-cols-5 gap-2">
      <div>
        <p className="text-xs text-slate-500">Novelty</p>
        <p className={`text-sm font-bold ${getScoreColor(opportunity.novelty)}`}>{opportunity.novelty}</p>
      </div>
      <div>
        <p className="text-xs text-slate-500">Impact</p>
        <p className={`text-sm font-bold ${getScoreColor(opportunity.impact)}`}>{opportunity.impact}</p>
      </div>
      <div>
        <p className="text-xs text-slate-500">Feasibility</p>
        <p className={`text-sm font-bold ${getScoreColor(opportunity.feasibility)}`}>{opportunity.feasibility}</p>
      </div>
      <div>
        <p className="text-xs text-slate-500">Evidence</p>
        <p className={`text-sm font-bold ${getScoreColor(opportunity.evidence_strength)}`}>{opportunity.evidence_strength}</p>
      </div>
      <div>
        <p className="text-xs text-slate-500">Recency</p>
        <p className={`text-sm font-bold ${getScoreColor(opportunity.recency)}`}>{opportunity.recency}</p>
      </div>
    </div>

    {opportunity.explanation && (
      <div className="mb-3 rounded-lg bg-slate-50 p-3">
        <p className="text-xs font-medium text-slate-700 mb-1">Why this opportunity:</p>
        <p className="text-sm text-slate-500">{opportunity.explanation}</p>
      </div>
    )}

    <div className="flex gap-2">
      <button
        onClick={() => onSelectOpportunity(opportunity.gap_id)}
        className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 transition"
      >
        <ExternalLink className="h-3.5 w-3.5" />
        Explore
      </button>
      {onDevelopPlan && (
        <button
          onClick={() => onDevelopPlan(opportunity)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-emerald-700 transition"
        >
          <Rocket className="h-3.5 w-3.5" />
          Develop Plan
        </button>
      )}
    </div>
  </div>
);

export const OpportunityRanking: React.FC<OpportunityRankingProps> = ({
  opportunities,
  onSelectOpportunity,
  onDevelopPlan,
}) => {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-2">
          <TrendingUp className="h-5 w-5 text-indigo-600" />
          <h3 className="text-lg font-semibold text-slate-900">Research Opportunities</h3>
        </div>
        <p className="text-sm text-slate-500">
          {opportunities.total_opportunities} opportunities identified from {opportunities.paper_count} papers
        </p>
      </div>

      <div className="space-y-4">
        {opportunities.opportunities.map((opportunity, index) => (
          <OpportunityCard
            key={opportunity.gap_id}
            opportunity={opportunity}
            rank={index + 1}
            onSelectOpportunity={onSelectOpportunity}
            onDevelopPlan={onDevelopPlan}
          />
        ))}
      </div>
    </div>
  );
};
