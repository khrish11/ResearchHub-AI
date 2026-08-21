/**
 * Evidence Landscape
 * 
 * Displays evidence analysis results including claims, supporting/contradicting papers,
 * evidence strength, and confidence metrics.
 */

import React from 'react';
import { CheckCircle2, XCircle, Circle, FileText, ShieldCheck } from 'lucide-react';
import type { EvidenceAnalysisResponse } from '../../api/researchIntelligence';
import type { EvidenceTraceData } from './types';

interface EvidenceLandscapeProps {
  evidence: EvidenceAnalysisResponse;
  onViewEvidence: (data: EvidenceTraceData) => void;
}

export const EvidenceLandscape: React.FC<EvidenceLandscapeProps> = ({ evidence, onViewEvidence }) => {

  const getConfidenceColor = (confidence: string): string => {
    switch (confidence) {
      case 'high':
        return 'text-emerald-600 bg-emerald-50 border-emerald-200';
      case 'medium':
        return 'text-amber-600 bg-amber-50 border-amber-200';
      case 'low':
        return 'text-rose-600 bg-rose-50 border-rose-200';
      default:
        return 'text-slate-600 bg-slate-50 border-slate-200';
    }
  };

  const typeIcon = (type: 'supporting' | 'contradicting' | 'neutral') => {
    if (type === 'supporting') return <CheckCircle2 className="h-4 w-4 text-emerald-600" />;
    if (type === 'contradicting') return <XCircle className="h-4 w-4 text-rose-600" />;
    return <Circle className="h-4 w-4 text-slate-400" />;
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-slate-900">Evidence Landscape</h2>
        <p className="mt-1 text-sm text-slate-500">
          Analysis of claims against literature with supporting and contradicting evidence
        </p>
      </div>

      {/* Claim */}
      <div className="mb-6 rounded-xl border border-indigo-200 bg-indigo-50 p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <p className="text-sm font-medium text-indigo-900 mb-2">Claim Analyzed</p>
            <p className="text-base font-semibold text-slate-900">{evidence.claim}</p>
          </div>
          <button
            onClick={() => onViewEvidence({
              insight: evidence.claim,
              insightType: 'gap',
              papers: [
                ...evidence.classification.supporting_papers.map(p => ({
                  id: p.id,
                  title: p.title,
                  authors: p.authors,
                })),
                ...evidence.classification.contradicting_papers.map(p => ({
                  id: p.id,
                  title: p.title,
                  authors: p.authors,
                })),
              ],
              unavailable: false,
            })}
            className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-300 bg-white px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-100 transition"
          >
            <FileText className="h-3.5 w-3.5" />
            View Evidence
          </button>
        </div>
      </div>

      {/* Classification */}
      <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            <p className="text-sm font-medium text-emerald-900">Supporting</p>
          </div>
          <p className="text-2xl font-bold text-emerald-700">
            {evidence.classification.supporting_count}
          </p>
          <p className="text-xs text-emerald-600">papers</p>
        </div>

        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <XCircle className="h-4 w-4 text-rose-600" />
            <p className="text-sm font-medium text-rose-900">Contradicting</p>
          </div>
          <p className="text-2xl font-bold text-rose-700">
            {evidence.classification.contradicting_count}
          </p>
          <p className="text-xs text-rose-600">papers</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Circle className="h-4 w-4 text-slate-400" />
            <p className="text-sm font-medium text-slate-900">Neutral</p>
          </div>
          <p className="text-2xl font-bold text-slate-700">
            {evidence.classification.neutral_count}
          </p>
          <p className="text-xs text-slate-600">papers</p>
        </div>
      </div>

      {/* Evidence Strength */}
      <div className="mb-6 rounded-xl border border-slate-200 bg-slate-50 p-4">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-indigo-600" />
            <p className="text-sm font-medium text-slate-900">Evidence Strength</p>
          </div>
          <div className={`rounded-full border px-3 py-1 text-sm font-medium ${getConfidenceColor(evidence.strength.confidence)}`}>
            {evidence.strength.confidence.charAt(0).toUpperCase() + evidence.strength.confidence.slice(1)} Confidence
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
          <div>
            <p className="text-xs text-slate-500">Overall</p>
            <p className="text-lg font-bold text-slate-900">{evidence.strength.overall_strength}/100</p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Source Quality</p>
            <p className="text-lg font-bold text-slate-900">{evidence.strength.source_quality_score}/100</p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Recency</p>
            <p className="text-lg font-bold text-slate-900">{evidence.strength.recency_score}/100</p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Replication</p>
            <p className="text-lg font-bold text-slate-900">{evidence.strength.replication_signal}/100</p>
          </div>
          <div className="col-span-2 md:col-span-1">
            <p className="text-xs text-slate-500">Support vs Contradiction</p>
            <p className="text-lg font-bold text-slate-900">
              {evidence.strength.support_count}:{evidence.strength.contradiction_count}
            </p>
          </div>
        </div>

        {evidence.strength.explanation && (
          <div className="mt-4 rounded-lg bg-white p-3">
            <p className="text-sm text-slate-600">{evidence.strength.explanation}</p>
          </div>
        )}
      </div>

      {/* Supporting Papers */}
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-slate-900 mb-2">Supporting Papers</h3>
        <div className="space-y-2">
          {evidence.classification.supporting_papers.map((paper) => (
            <div key={paper.id} className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
              {typeIcon('supporting')}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-900 truncate">{paper.title}</p>
                <p className="text-xs text-slate-500">{paper.authors}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Contradicting Papers */}
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-slate-900 mb-2">Contradicting Papers</h3>
        <div className="space-y-2">
          {evidence.classification.contradicting_papers.map((paper) => (
            <div key={paper.id} className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
              {typeIcon('contradicting')}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-900 truncate">{paper.title}</p>
                <p className="text-xs text-slate-500">{paper.authors}</p>
              </div>
            </div>
          ))}
        </div>
      </div>


      {/* Evidence Type */}
      <div className="mt-6 rounded-lg bg-slate-50 p-3">
        <p className="text-xs text-slate-500">
          Evidence Type: <span className="font-medium text-slate-700">{evidence.evidence_type}</span>
        </p>
      </div>
    </div>
  );
};
