/**
 * Evidence Trace
 * 
 * Modal/dialog for displaying evidence traceability for AI-generated insights.
 */

import React from 'react';
import { X, FileText, AlertCircle } from 'lucide-react';
import type { EvidenceTraceData } from './types';

interface EvidenceTraceProps {
  data: EvidenceTraceData | null;
  onClose: () => void;
}

export const EvidenceTrace: React.FC<EvidenceTraceProps> = ({ data, onClose }) => {
  if (!data) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="max-w-2xl w-full rounded-2xl bg-white shadow-xl max-h-[80vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 p-4">
          <div>
            <h3 className="text-lg font-bold text-slate-900">Evidence Trace</h3>
            <p className="text-sm text-slate-500">Source evidence for this insight</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 hover:bg-slate-100 transition"
            aria-label="Close"
          >
            <X className="h-5 w-5 text-slate-600" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {/* Insight */}
          <div className="mb-6 rounded-xl border border-indigo-200 bg-indigo-50 p-4">
            <p className="text-sm font-medium text-indigo-900 mb-2">Insight</p>
            <p className="text-base font-semibold text-slate-900">{data.insight}</p>
            <p className="text-xs text-slate-500 mt-1">Type: {data.insightType}</p>
          </div>

          {/* Evidence */}
          {data.unavailable ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertCircle className="h-5 w-5 text-amber-600" />
                <p className="text-sm font-medium text-amber-900">Evidence Unavailable</p>
              </div>
              <p className="text-sm text-amber-800">
                Source evidence is not available for this insight. This may be due to limited paper metadata or AI-generated interpretation without direct passage evidence.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm font-medium text-slate-900">Supporting Papers</p>
              {data.papers.map((paper, index) => (
                <div key={index} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-start gap-3">
                    <FileText className="h-5 w-5 text-indigo-600 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-slate-900">{paper.title}</p>
                      <p className="text-xs text-slate-500">{paper.authors}</p>
                      {paper.passage && (
                        <div className="mt-2 rounded bg-white p-2">
                          <p className="text-xs text-slate-600 italic">"{paper.passage}"</p>
                        </div>
                      )}
                      {paper.relevanceScore !== undefined && (
                        <p className="text-xs text-slate-500 mt-1">
                          Relevance: {paper.relevanceScore}/100
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-slate-200 p-4 bg-slate-50">
          <p className="text-xs text-slate-500">
            Evidence traceability ensures AI-generated insights are grounded in source literature.
          </p>
        </div>
      </div>
    </div>
  );
};
