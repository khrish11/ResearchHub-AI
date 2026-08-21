/**
 * Citation Integrity
 * 
 * Displays citation verification results with quality, accessibility, and consistency scores.
 */

import React from 'react';
import { ShieldCheck, CheckCircle2, FileText } from 'lucide-react';
import type { CitationVerificationResponse } from '../../api/researchIntelligence';

interface CitationIntegrityProps {
  citations: CitationVerificationResponse;
}

export const CitationIntegrity: React.FC<CitationIntegrityProps> = ({ citations }) => {
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

  const getConfidenceLabel = (value: number): string => {
    if (value >= 80) return 'High confidence';
    if (value >= 60) return 'Needs review';
    return 'Potential issue';
  };

  const getSeverityColor = (severity: string): string => {
    switch (severity) {
      case 'high':
        return 'text-rose-600 bg-rose-50 border-rose-200';
      case 'medium':
        return 'text-amber-600 bg-amber-50 border-amber-200';
      case 'low':
        return 'text-slate-600 bg-slate-50 border-slate-200';
      default:
        return 'text-slate-600 bg-slate-50 border-slate-200';
    }
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-slate-900">Citation Integrity</h2>
        <p className="mt-1 text-sm text-slate-500">
          Verification of citation quality, accessibility, and consistency across {citations.total_papers} papers
        </p>
      </div>

      {/* Overall Scores */}
      <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <ShieldCheck className="h-5 w-5 text-indigo-600" />
            <p className="text-sm font-medium text-slate-900">Overall Quality</p>
          </div>
          <p className={`text-3xl font-bold ${getScoreColor(citations.average_quality)}`}>
            {citations.average_quality}/100
          </p>
          <p className={`text-sm ${getScoreColor(citations.average_quality)}`}>
            {getConfidenceLabel(citations.average_quality)}
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            <p className="text-sm font-medium text-slate-900">Accessibility</p>
          </div>
          <p className={`text-3xl font-bold ${getScoreColor(citations.average_accessibility)}`}>
            {citations.average_accessibility}/100
          </p>
          <p className={`text-sm ${getScoreColor(citations.average_accessibility)}`}>
            {getConfidenceLabel(citations.average_accessibility)}
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <FileText className="h-5 w-5 text-sky-600" />
            <p className="text-sm font-medium text-slate-900">Consistency</p>
          </div>
          <p className={`text-3xl font-bold ${getScoreColor(citations.average_consistency)}`}>
            {citations.average_consistency}/100
          </p>
          <p className={`text-sm ${getScoreColor(citations.average_consistency)}`}>
            {getConfidenceLabel(citations.average_consistency)}
          </p>
        </div>
      </div>

      {/* Paper Verifications */}
      <div className="space-y-4">
        {citations.verifications.slice(0, 6).map((verification) => (
          <div key={verification.paper_id} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1">
                <p className="text-sm font-semibold text-slate-900">{verification.paper_title}</p>
                <div className="mt-2 flex flex-wrap gap-3">
                  <div>
                    <p className="text-xs text-slate-500">Quality</p>
                    <p className={`text-sm font-bold ${getScoreColor(verification.quality_score)}`}>
                      {verification.quality_score}/100
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Accessibility</p>
                    <p className={`text-sm font-bold ${getScoreColor(verification.accessibility_score)}`}>
                      {verification.accessibility_score}/100
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Consistency</p>
                    <p className={`text-sm font-bold ${getScoreColor(verification.consistency_score)}`}>
                      {verification.consistency_score}/100
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Overall</p>
                    <p className={`text-sm font-bold ${getScoreColor(verification.overall_confidence)}`}>
                      {verification.overall_confidence}/100
                    </p>
                  </div>
                </div>
              </div>
              <div className={`rounded-full border px-2 py-1 text-xs font-semibold ${getScoreBg(verification.overall_confidence)}`}>
                {getConfidenceLabel(verification.overall_confidence)}
              </div>
            </div>

            {/* Issues */}
            {verification.issues.length > 0 && (
              <div className="mb-3">
                <p className="text-xs font-medium text-slate-700 mb-2">Issues</p>
                <div className="space-y-1">
                  {verification.issues.map((issue, index) => (
                    <div
                      key={index}
                      className={`rounded-lg border px-2 py-1 text-xs ${getSeverityColor(issue.severity)}`}
                    >
                      <span className="font-medium">{issue.type}:</span> {issue.description}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommendations */}
            {verification.recommendations.length > 0 && (
              <div>
                <p className="text-xs font-medium text-slate-700 mb-2">Recommendations</p>
                <ul className="space-y-1">
                  {verification.recommendations.slice(0, 2).map((recommendation, index) => (
                    <li key={index} className="text-xs text-slate-600">
                      • {recommendation}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>

      {citations.summary && (
        <div className="mt-6 rounded-lg bg-slate-50 p-4">
          <p className="text-sm font-medium text-slate-900 mb-2">Summary</p>
          <p className="text-sm text-slate-600">{citations.summary}</p>
        </div>
      )}
    </div>
  );
};
