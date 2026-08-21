/**
 * Research Plan Builder
 * 
 * Component for building and editing research plans from AI-generated suggestions.
 */

import React, { useState } from 'react';
import { Loader2, Save, X, Check, Edit2 } from 'lucide-react';
import type { PlanSuggestions } from '../../api/researchIntelligence';

interface ResearchPlanBuilderProps {
  suggestions: PlanSuggestions;
  onSavePlan: (planData: PlanSuggestions) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

const PlanField: React.FC<{
  label: string;
  aiSuggestion: string;
  value: string;
  onChange: (value: string) => void;
  onAccept: () => void;
  onReject: () => void;
  decision?: 'ACCEPT' | 'MODIFY' | 'REJECT' | null;
}> = ({ label, aiSuggestion, value, onChange, onAccept, onReject, decision }) => {
  const [isEditing, setIsEditing] = useState(decision === 'MODIFY');

  return (
    <div className="mb-4 rounded-lg border border-slate-200 p-4">
      <div className="mb-2 flex items-center justify-between">
        <label className="text-sm font-semibold text-slate-900">{label}</label>
        <div className="flex gap-2">
          {decision !== 'ACCEPT' && (
            <button
              onClick={() => {
                onChange(aiSuggestion);
                onAccept();
              }}
              className="inline-flex items-center gap-1 rounded bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-200"
            >
              <Check className="h-3 w-3" />
              Accept
            </button>
          )}
          {decision !== 'REJECT' && (
            <button
              onClick={() => {
                setIsEditing(!isEditing);
              }}
              className="inline-flex items-center gap-1 rounded bg-amber-100 px-2 py-1 text-xs font-medium text-amber-700 hover:bg-amber-200"
            >
              <Edit2 className="h-3 w-3" />
              {isEditing ? 'Done' : 'Edit'}
            </button>
          )}
          {decision !== 'REJECT' && (
            <button
              onClick={() => {
                onChange('');
                onReject();
              }}
              className="inline-flex items-center gap-1 rounded bg-rose-100 px-2 py-1 text-xs font-medium text-rose-700 hover:bg-rose-200"
            >
              <X className="h-3 w-3" />
              Reject
            </button>
          )}
        </div>
      </div>
      {decision === 'REJECT' ? (
        <p className="text-sm text-slate-400 italic">Field rejected</p>
      ) : (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={!isEditing && decision === 'ACCEPT'}
          className={`w-full rounded border p-2 text-sm ${
            isEditing || decision === null
              ? 'border-slate-300 focus:border-indigo-500 focus:outline-none'
              : 'border-emerald-200 bg-emerald-50'
          }`}
          rows={3}
        />
      )}
    </div>
  );
};

export const ResearchPlanBuilder: React.FC<ResearchPlanBuilderProps> = ({
  suggestions,
  onSavePlan,
  onCancel,
  isLoading = false,
}) => {
  const [planData, setPlanData] = useState<PlanSuggestions>({
    title: suggestions?.title || '',
    research_problem: suggestions?.research_problem || '',
    research_question: suggestions?.research_question || '',
    hypothesis: suggestions?.hypothesis || '',
    objectives: suggestions?.objectives || '',
    proposed_methodology: suggestions?.proposed_methodology || '',
    alternative_methodology: suggestions?.alternative_methodology || '',
    datasets: suggestions?.datasets || '',
    variables: suggestions?.variables || '',
    baselines: suggestions?.baselines || '',
    evaluation_metrics: suggestions?.evaluation_metrics || '',
    expected_contribution: suggestions?.expected_contribution || '',
    risks: suggestions?.risks || '',
    limitations: suggestions?.limitations || '',
    reproducibility_requirements: suggestions?.reproducibility_requirements || '',
    evidence_references: suggestions?.evidence_references || [],
  });

  const [decisions, setDecisions] = useState<Record<string, 'ACCEPT' | 'MODIFY' | 'REJECT' | null>>({});

  const handleFieldChange = (field: keyof PlanSuggestions, value: string) => {
    setPlanData(prev => ({ ...prev, [field]: value }));
    if (value !== suggestions?.[field]) {
      setDecisions(prev => ({ ...prev, [field]: 'MODIFY' }));
    }
  };

  const handleAcceptField = (field: keyof PlanSuggestions) => {
    setDecisions(prev => ({ ...prev, [field]: 'ACCEPT' }));
  };

  const handleRejectField = (field: keyof PlanSuggestions) => {
    setDecisions(prev => ({ ...prev, [field]: 'REJECT' }));
  };

  const handleSave = () => {
    onSavePlan(planData);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
        <span className="ml-3 text-sm text-slate-600">Generating plan suggestions...</span>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-lg">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Research Plan Builder</h2>
          <p className="text-sm text-slate-500">Review and customize AI-generated plan suggestions</p>
        </div>
        <button
          onClick={onCancel}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          <X className="h-4 w-4" />
          Cancel
        </button>
      </div>

      {suggestions?.evidence_references && suggestions.evidence_references.length > 0 && (
        <div className="mb-6 rounded-lg bg-slate-50 p-4">
          <h3 className="text-sm font-semibold text-slate-900 mb-2">Evidence References</h3>
          <ul className="space-y-1">
            {suggestions.evidence_references.map((ref: string, idx: number) => (
              <li key={idx} className="text-xs text-slate-600">{ref}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="space-y-4">
        <PlanField
          label="Title"
          aiSuggestion={suggestions?.title || ''}
          value={planData.title}
          onChange={(v) => handleFieldChange('title', v)}
          onAccept={() => handleAcceptField('title')}
          onReject={() => handleRejectField('title')}
          decision={decisions.title}
        />
        <PlanField
          label="Research Problem"
          aiSuggestion={suggestions?.research_problem || ''}
          value={planData.research_problem}
          onChange={(v) => handleFieldChange('research_problem', v)}
          onAccept={() => handleAcceptField('research_problem')}
          onReject={() => handleRejectField('research_problem')}
          decision={decisions.research_problem}
        />
        <PlanField
          label="Research Question"
          aiSuggestion={suggestions?.research_question || ''}
          value={planData.research_question}
          onChange={(v) => handleFieldChange('research_question', v)}
          onAccept={() => handleAcceptField('research_question')}
          onReject={() => handleRejectField('research_question')}
          decision={decisions.research_question}
        />
        <PlanField
          label="Hypothesis"
          aiSuggestion={suggestions?.hypothesis || ''}
          value={planData.hypothesis}
          onChange={(v) => handleFieldChange('hypothesis', v)}
          onAccept={() => handleAcceptField('hypothesis')}
          onReject={() => handleRejectField('hypothesis')}
          decision={decisions.hypothesis}
        />
        <PlanField
          label="Objectives"
          aiSuggestion={suggestions?.objectives || ''}
          value={planData.objectives}
          onChange={(v) => handleFieldChange('objectives', v)}
          onAccept={() => handleAcceptField('objectives')}
          onReject={() => handleRejectField('objectives')}
          decision={decisions.objectives}
        />
        <PlanField
          label="Proposed Methodology"
          aiSuggestion={suggestions?.proposed_methodology || ''}
          value={planData.proposed_methodology}
          onChange={(v) => handleFieldChange('proposed_methodology', v)}
          onAccept={() => handleAcceptField('proposed_methodology')}
          onReject={() => handleRejectField('proposed_methodology')}
          decision={decisions.proposed_methodology}
        />
        <PlanField
          label="Alternative Methodology"
          aiSuggestion={suggestions?.alternative_methodology || ''}
          value={planData.alternative_methodology}
          onChange={(v) => handleFieldChange('alternative_methodology', v)}
          onAccept={() => handleAcceptField('alternative_methodology')}
          onReject={() => handleRejectField('alternative_methodology')}
          decision={decisions.alternative_methodology}
        />
        <PlanField
          label="Datasets"
          aiSuggestion={suggestions?.datasets || ''}
          value={planData.datasets}
          onChange={(v) => handleFieldChange('datasets', v)}
          onAccept={() => handleAcceptField('datasets')}
          onReject={() => handleRejectField('datasets')}
          decision={decisions.datasets}
        />
        <PlanField
          label="Variables"
          aiSuggestion={suggestions?.variables || ''}
          value={planData.variables}
          onChange={(v) => handleFieldChange('variables', v)}
          onAccept={() => handleAcceptField('variables')}
          onReject={() => handleRejectField('variables')}
          decision={decisions.variables}
        />
        <PlanField
          label="Baselines"
          aiSuggestion={suggestions?.baselines || ''}
          value={planData.baselines}
          onChange={(v) => handleFieldChange('baselines', v)}
          onAccept={() => handleAcceptField('baselines')}
          onReject={() => handleRejectField('baselines')}
          decision={decisions.baselines}
        />
        <PlanField
          label="Evaluation Metrics"
          aiSuggestion={suggestions?.evaluation_metrics || ''}
          value={planData.evaluation_metrics}
          onChange={(v) => handleFieldChange('evaluation_metrics', v)}
          onAccept={() => handleAcceptField('evaluation_metrics')}
          onReject={() => handleRejectField('evaluation_metrics')}
          decision={decisions.evaluation_metrics}
        />
        <PlanField
          label="Expected Contribution"
          aiSuggestion={suggestions?.expected_contribution || ''}
          value={planData.expected_contribution}
          onChange={(v) => handleFieldChange('expected_contribution', v)}
          onAccept={() => handleAcceptField('expected_contribution')}
          onReject={() => handleRejectField('expected_contribution')}
          decision={decisions.expected_contribution}
        />
        <PlanField
          label="Risks"
          aiSuggestion={suggestions?.risks || ''}
          value={planData.risks}
          onChange={(v) => handleFieldChange('risks', v)}
          onAccept={() => handleAcceptField('risks')}
          onReject={() => handleRejectField('risks')}
          decision={decisions.risks}
        />
        <PlanField
          label="Limitations"
          aiSuggestion={suggestions?.limitations || ''}
          value={planData.limitations}
          onChange={(v) => handleFieldChange('limitations', v)}
          onAccept={() => handleAcceptField('limitations')}
          onReject={() => handleRejectField('limitations')}
          decision={decisions.limitations}
        />
        <PlanField
          label="Reproducibility Requirements"
          aiSuggestion={suggestions?.reproducibility_requirements || ''}
          value={planData.reproducibility_requirements}
          onChange={(v) => handleFieldChange('reproducibility_requirements', v)}
          onAccept={() => handleAcceptField('reproducibility_requirements')}
          onReject={() => handleRejectField('reproducibility_requirements')}
          decision={decisions.reproducibility_requirements}
        />
      </div>

      <div className="mt-6 flex justify-end gap-3">
        <button
          onClick={onCancel}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
        >
          <Save className="h-4 w-4" />
          Save Research Plan
        </button>
      </div>
    </div>
  );
};
