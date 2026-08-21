/**
 * Research Intelligence Header
 * 
 * Displays the research topic, workspace info, and key status metrics.
 */

import React from 'react';
import { BrainCircuit, FileText, TrendingUp, ShieldCheck } from 'lucide-react';
import type { ScorecardData } from './types';

interface ResearchIntelligenceHeaderProps {
  topic: string;
  workspaceName: string;
  paperCount: number;
  scorecard: ScorecardData | null;
}

export const ResearchIntelligenceHeader: React.FC<ResearchIntelligenceHeaderProps> = ({
  topic,
  workspaceName,
  paperCount,
  scorecard,
}) => {
  const formatScore = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return 'Not available';
    return `${value}/100`;
  };

  const getConfidenceLabel = (confidence: string | null | undefined): string => {
    if (!confidence) return 'Not available';
    return confidence.charAt(0).toUpperCase() + confidence.slice(1);
  };

  return (
    <div className="mb-8 space-y-6">
      {/* Title Section */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">
          Research Intelligence
        </h1>
        <p className="mt-2 text-lg text-slate-600">
          From literature to research opportunity
        </p>
      </div>

      {/* Workspace and Topic Info */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <p className="text-sm font-medium text-slate-500">Workspace</p>
            <p className="text-base font-semibold text-slate-900">{workspaceName}</p>
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium text-slate-500">Research Topic</p>
            <p className="text-base font-semibold text-slate-900">{topic}</p>
          </div>
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-indigo-600" />
            <div className="space-y-1">
              <p className="text-sm font-medium text-slate-500">Papers Analyzed</p>
              <p className="text-base font-semibold text-slate-900">{paperCount}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Status Metrics */}
      {scorecard && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {/* Evidence Strength */}
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-emerald-100 p-2">
                <ShieldCheck className="h-5 w-5 text-emerald-600" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-slate-500">Evidence Strength</p>
                <p className="text-2xl font-bold text-slate-900">
                  {formatScore(scorecard.evidenceStrength)}
                </p>
              </div>
            </div>
          </div>

          {/* Research Opportunity */}
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-indigo-100 p-2">
                <TrendingUp className="h-5 w-5 text-indigo-600" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-slate-500">Research Opportunity</p>
                <p className="text-2xl font-bold text-slate-900">
                  {formatScore(scorecard.overall)}
                </p>
              </div>
            </div>
          </div>

          {/* Research Confidence */}
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-sky-100 p-2">
                <BrainCircuit className="h-5 w-5 text-sky-600" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-slate-500">Research Confidence</p>
                <p className="text-2xl font-bold text-slate-900">
                  {getConfidenceLabel(scorecard.confidence)}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Disclaimer */}
      <p className="text-xs text-slate-500">
        AI-assisted assessment based on analyzed literature. Scores are for research guidance only and do not predict research success.
      </p>
    </div>
  );
};
