import React from 'react';
import {
  AlertTriangle,
  BadgeCheck,
  FileSearch,
  FlaskConical,
  Loader2,
  Quote,
  ShieldAlert,
} from 'lucide-react';
import { apiErrorMessage } from '../utils/apiError';
import {
  runPaperCheck,
  type CompletedPaperCheckResult,
  type PaperCheckPayload,
} from '../utils/researchArtifacts';

type PaperCheckReportResult = Partial<Omit<CompletedPaperCheckResult, 'status'>> & {
  status?: string;
  error?: string | { message?: string };
};

interface PaperCheckReportProps {
  result: PaperCheckReportResult;
  title?: string;
  retryPayload?: PaperCheckPayload;
  onRetryComplete?: (result: CompletedPaperCheckResult) => void;
  onRetryError?: (message: string) => void;
}

const scoreTone = (score?: number) => {
  const value = Number(score || 0);
  if (value >= 75) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (value >= 50) return 'bg-amber-50 text-amber-700 border-amber-200';
  return 'bg-rose-50 text-rose-700 border-rose-200';
};

const bandTone: Record<string, string> = {
  low: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  high: 'bg-rose-50 text-rose-700 border-rose-200',
};

const TextList: React.FC<{ items?: string[]; empty: string }> = ({ items, empty }) => {
  if (!Array.isArray(items) || items.length === 0) {
    return <p className="text-sm text-slate-500">{empty}</p>;
  }
  return (
    <div className="space-y-2">
      {items.map((item, index) => (
        <div key={`${item}-${index}`} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
          {item}
        </div>
      ))}
    </div>
  );
};

const ScoreCard: React.FC<{ label: string; score?: number; summary?: string }> = ({ label, score, summary }) => (
  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
    <div className="flex items-center justify-between gap-3">
      <p className="text-sm font-semibold text-slate-900">{label}</p>
      <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${scoreTone(score)}`}>
        {typeof score === 'number' ? `${score}/100` : 'n/a'}
      </span>
    </div>
    <p className="mt-2 text-sm leading-6 text-slate-600">{summary || 'No summary available yet.'}</p>
  </div>
);

const retryableStatuses = new Set(['failed', 'timeout', 'timed_out']);

const PaperCheckReport: React.FC<PaperCheckReportProps> = ({
  result,
  title,
  retryPayload,
  onRetryComplete,
  onRetryError,
}) => {
  const [retrying, setRetrying] = React.useState(false);
  const [retryError, setRetryError] = React.useState('');
  const [retryResult, setRetryResult] = React.useState<CompletedPaperCheckResult | null>(null);
  const displayedResult = retryResult || result;
  const analysis = displayedResult.paper_analysis || {};
  const snapshot = analysis.snapshot || {};
  const methods = analysis.methods || {};
  const segments = Array.isArray(displayedResult.ai_writing_likelihood?.segments)
    ? displayedResult.ai_writing_likelihood.segments
    : [];
  const reportStatus = String(displayedResult.status || '').toLowerCase();
  const showRetry = retryableStatuses.has(reportStatus);

  React.useEffect(() => {
    setRetryResult(null);
    setRetryError('');
  }, [result]);

  const handleRetry = async () => {
    if (!retryPayload || retrying) {
      return;
    }
    setRetrying(true);
    setRetryError('');
    try {
      const response = await runPaperCheck(retryPayload);
      setRetryResult(response);
      onRetryComplete?.(response);
    } catch (err: unknown) {
      const message = apiErrorMessage(err, 'Paper Check retry failed.');
      setRetryError(message);
      onRetryError?.(message);
    } finally {
      setRetrying(false);
    }
  };

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        Paper Check is advisory only and does not prove authorship.
      </div>

      {showRetry && (
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-600">
              This Paper Check did not complete. You can retry the analysis.
            </p>
            <button
              type="button"
              onClick={() => void handleRetry()}
              disabled={retrying || !retryPayload}
              className="hero-btn-secondary disabled:cursor-not-allowed disabled:opacity-55"
            >
              {retrying && <Loader2 className="h-4 w-4 animate-spin" />}
              Retry Paper Check
            </button>
          </div>
          {retryError && (
            <p className="mt-3 text-sm text-amber-700">{retryError}</p>
          )}
        </div>
      )}

      <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              {title || 'Paper check report'}
            </p>
            <h3 className="mt-1 text-xl font-semibold text-slate-950">
              {snapshot.title || 'Structured research-grade review'}
            </h3>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {displayedResult.metadata?.model_used && (
              <span className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 font-semibold text-indigo-700">
                {displayedResult.metadata.model_used}
              </span>
            )}
            <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-slate-600">
              {displayedResult.metadata?.suspicious_segment_count || 0} flagged segments
            </span>
            <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-slate-600">
              {displayedResult.metadata?.cache_hit ? `cache:${displayedResult.metadata.cache_layer || 'memory'}` : 'live analysis'}
            </span>
          </div>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-[1.15fr,0.85fr]">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-center gap-2">
              <FileSearch className="h-4 w-4 text-indigo-600" />
              <p className="text-sm font-semibold text-slate-900">Snapshot</p>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-700">{snapshot.summary || 'No snapshot summary available.'}</p>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Paper type</p>
                <p className="mt-1 text-sm text-slate-700">{snapshot.paper_type || 'Not classified'}</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Core problem</p>
                <p className="mt-1 text-sm text-slate-700">{snapshot.core_problem || 'Not extracted'}</p>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <ScoreCard
              label="Evidence strength"
              score={analysis.evidence_strength?.score}
              summary={analysis.evidence_strength?.summary}
            />
            <ScoreCard
              label="Reproducibility"
              score={analysis.reproducibility?.score}
              summary={analysis.reproducibility?.summary}
            />
            <ScoreCard
              label="Citation quality"
              score={analysis.citation_quality?.score}
              summary={analysis.citation_quality?.summary}
            />
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.08fr,0.92fr]">
        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2">
            <BadgeCheck className="h-4 w-4 text-emerald-600" />
            <p className="text-sm font-semibold text-slate-900">Claims</p>
          </div>
          <div className="mt-4 space-y-3">
            {Array.isArray(analysis.claims) && analysis.claims.length > 0 ? (
              analysis.claims.map((claim, index) => (
                <div key={`${claim.claim || 'claim'}-${index}`} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-900">{claim.claim || 'Unspecified claim'}</p>
                    {claim.support_level && (
                      <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-600">
                        {claim.support_level}
                      </span>
                    )}
                  </div>
                  {claim.evidence && <p className="mt-2 text-sm leading-6 text-slate-600">{claim.evidence}</p>}
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">No structured claim extraction was returned.</p>
            )}
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-sky-600" />
            <p className="text-sm font-semibold text-slate-900">Methods</p>
          </div>
          <div className="mt-4 space-y-3">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Approach</p>
              <p className="mt-2 text-sm leading-6 text-slate-700">{methods.approach || 'No approach summary available.'}</p>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Datasets</p>
                <div className="mt-3">
                  <TextList items={methods.datasets} empty="No datasets extracted." />
                </div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Metrics</p>
                <div className="mt-3">
                  <TextList items={methods.metrics} empty="No metrics extracted." />
                </div>
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Method notes</p>
              <div className="mt-3">
                <TextList items={methods.notes} empty="No additional method notes." />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            <p className="text-sm font-semibold text-slate-900">Limitations</p>
          </div>
          <div className="mt-4">
            <TextList items={analysis.limitations} empty="No limitations called out." />
          </div>
        </div>
        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-rose-600" />
            <p className="text-sm font-semibold text-slate-900">Red flags</p>
          </div>
          <div className="mt-4">
            <TextList items={analysis.red_flags} empty="No major red flags called out." />
          </div>
        </div>
        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2">
            <Quote className="h-4 w-4 text-indigo-600" />
            <p className="text-sm font-semibold text-slate-900">Confidence notes</p>
          </div>
          <div className="mt-4">
            <TextList items={analysis.confidence_notes} empty="No confidence notes provided." />
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-slate-900">AI-writing likelihood review</p>
            <p className="mt-1 text-sm text-slate-500">
              Paragraph-level advisory classification on suspicious segments only.
            </p>
          </div>
          {displayedResult.ai_writing_likelihood?.detection_error && (
            <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
              Partial model output
            </span>
          )}
        </div>

        {segments.length === 0 ? (
          <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            No suspicious segments were escalated for AI-writing review.
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {segments.map((segment) => (
              <div key={segment.segment_id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${bandTone[segment.likelihood_band] || bandTone.low}`}>
                      {segment.likelihood_band} likelihood
                    </span>
                    <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600">
                      {Math.round(Number(segment.likelihood_score || 0) * 100)}%
                    </span>
                    {typeof segment.heuristic_score === 'number' && (
                      <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600">
                        heuristic {Math.round(segment.heuristic_score * 100)}%
                      </span>
                    )}
                  </div>
                </div>
                <p className="mt-3 whitespace-pre-wrap rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm leading-6 text-slate-700">
                  {segment.text_excerpt}
                </p>
                {segment.reasons.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {segment.reasons.map((reason, index) => (
                      <span key={`${reason}-${index}`} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600">
                        {reason}
                      </span>
                    ))}
                  </div>
                )}
                <p className="mt-3 text-sm leading-6 text-slate-600">{segment.explanation}</p>
              </div>
            ))}
          </div>
        )}

        {displayedResult.ai_writing_likelihood?.detection_error && (
          <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {displayedResult.ai_writing_likelihood.detection_error}
          </div>
        )}

        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          {displayedResult.ai_writing_likelihood?.disclaimer || 'This analysis is advisory and may be incorrect. It should not be used as proof of AI authorship.'}
        </div>
      </div>
    </section>
  );
};

export default PaperCheckReport;
