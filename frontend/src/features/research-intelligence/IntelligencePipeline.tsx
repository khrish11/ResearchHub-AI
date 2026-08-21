/**
 * Intelligence Pipeline
 * 
 * Displays the unified pipeline showing all research intelligence stages.
 */

import React from 'react';
import { CheckCircle2, Circle, Loader2, AlertCircle, Play } from 'lucide-react';
import type { PipelineStage, StageStatus, PipelineState } from './types';

interface IntelligencePipelineProps {
  pipeline: PipelineState;
  onRunStage: (stage: PipelineStage) => void;
  canRunStage: (stage: PipelineStage) => boolean;
}

const STAGE_LABELS: Record<PipelineStage, string> = {
  evidence: 'Evidence',
  gaps: 'Gaps',
  opportunities: 'Opportunities',
  questions: 'Questions',
  challenge: 'Challenge',
  citations: 'Citations',
  graph: 'Knowledge Graph',
};

const STAGE_DESCRIPTIONS: Record<PipelineStage, string> = {
  evidence: 'Analyze evidence strength and contradictions',
  gaps: 'Identify research gaps and limitations',
  opportunities: 'Rank research opportunities',
  questions: 'Generate research questions',
  challenge: 'Challenge your hypothesis',
  citations: 'Verify citation integrity',
  graph: 'Build enhanced knowledge graph',
};

export const IntelligencePipeline: React.FC<IntelligencePipelineProps> = ({
  pipeline,
  onRunStage,
  canRunStage,
}) => {
  const getStatusIcon = (status: StageStatus): React.ReactNode => {
    switch (status) {
      case 'loading':
        return <Loader2 className="h-4 w-4 animate-spin text-indigo-600" />;
      case 'success':
        return <CheckCircle2 className="h-4 w-4 text-emerald-600" />;
      case 'error':
        return <AlertCircle className="h-4 w-4 text-rose-600" />;
      default:
        return <Circle className="h-4 w-4 text-slate-400" />;
    }
  };

  const getStatusText = (status: StageStatus, resultCount?: number): string => {
    switch (status) {
      case 'loading':
        return 'Running...';
      case 'success':
        return resultCount !== undefined ? `Complete (${resultCount})` : 'Complete';
      case 'error':
        return 'Failed';
      default:
        return 'Ready';
    }
  };

  const getStatusColor = (status: StageStatus): string => {
    switch (status) {
      case 'loading':
        return 'text-indigo-600';
      case 'success':
        return 'text-emerald-600';
      case 'error':
        return 'text-rose-600';
      default:
        return 'text-slate-500';
    }
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-bold text-slate-900 mb-4">Research Intelligence Pipeline</h2>
      <div className="space-y-3">
        {(Object.keys(pipeline) as PipelineStage[]).map((stage) => {
          const stageData = pipeline[stage];
          const canRun = canRunStage(stage);
          
          return (
            <div
              key={stage}
              className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 p-4 hover:bg-slate-100 transition"
            >
              <div className="flex items-center gap-4">
                <div className="flex items-center justify-center w-8">
                  {getStatusIcon(stageData.status)}
                </div>
                <div>
                  <p className="font-semibold text-slate-900">{STAGE_LABELS[stage]}</p>
                  <p className="text-sm text-slate-500">{STAGE_DESCRIPTIONS[stage]}</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <p className={`text-sm font-medium ${getStatusColor(stageData.status)}`}>
                  {getStatusText(stageData.status, stageData.resultCount)}
                </p>
                {stageData.status === 'error' && (
                  <button
                    onClick={() => onRunStage(stage)}
                    className="text-sm font-medium text-indigo-600 hover:text-indigo-700"
                  >
                    Retry
                  </button>
                )}
                {stageData.status === 'idle' && canRun && (
                  <button
                    onClick={() => onRunStage(stage)}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 transition"
                  >
                    <Play className="h-3.5 w-3.5" />
                    Run
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
