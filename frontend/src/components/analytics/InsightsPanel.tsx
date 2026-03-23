import { cn } from '../../utils/cn';
import { AlertCircle, CheckCircle2, Zap, Activity } from 'lucide-react';
import { SEVERITY_COLORS, SeverityBadge } from './RouteTable';
import type { InsightsSummary } from '../../types/api';
;

const SEVERITY_ICON = {
  CRITICAL: AlertCircle,
  WARNING: Activity,
  INFO: Zap
};

export function RouteBadge({ route }: { route: string }) {
  return (
    <span className="font-mono text-[10px] bg-slate-900 text-slate-400 px-1.5 py-0.5 rounded border border-slate-700 truncate max-w-[150px] inline-flex items-center">
      {route}
    </span>
  );
}

interface InsightsPanelProps {
  summary: InsightsSummary | null;
  loading: boolean;
  onIssueClick?: (issue: any) => void;
}

export default function InsightsPanel({ summary, loading, onIssueClick }: InsightsPanelProps) {
  if (loading || !summary) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map(i => (
          <div key={i} className="animate-pulse bg-white/5 border border-white/10 rounded-xl p-4">
            <div className="h-4 w-32 bg-slate-700 rounded mb-3" />
            <div className="h-3 w-full bg-slate-700 rounded mb-2" />
            <div className="h-3 w-3/4 bg-slate-700 rounded" />
          </div>
        ))}
      </div>
    );
  }

  const issues = (summary.top_issues || []).filter(i => i.severity === 'CRITICAL' || i.severity === 'WARNING');

  return (
    <div className="bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border border-white/10 rounded-xl p-5">
      <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2 mb-4">
        <AlertCircle size={15} className="text-indigo-400" />
        Top Issues & Recommendations
      </h3>
      {issues.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-slate-500">
          <CheckCircle2 size={32} className="text-green-400 mb-2" />
          <p className="text-sm">No critical issues detected</p>
        </div>
      ) : (
        <div className="space-y-3">
          {issues.map((issue, i) => {
            const Icon = SEVERITY_ICON[issue.severity as keyof typeof SEVERITY_ICON] || Activity;
            const colors = SEVERITY_COLORS[issue.severity as keyof typeof SEVERITY_COLORS] || SEVERITY_COLORS.INFO;
            return (
              <div 
                key={i} 
                onClick={() => onIssueClick?.(issue)}
                className={cn('rounded-lg border p-4 transition-colors', colors.bg, colors.border, onIssueClick && 'cursor-pointer hover:bg-opacity-20')}
              >
                <div className="flex items-center gap-2 mb-2">
                  <Icon size={14} className={colors.text} />
                  <SeverityBadge severity={issue.severity} />
                  {issue.route && <RouteBadge route={issue.route} />}
                </div>
                {issue.recommendation && (
                  <p className="text-slate-300 text-xs leading-relaxed">{issue.recommendation}</p>
                )}
                {issue.p95_latency_ms !== undefined && (
                  <div className="mt-3 flex gap-4 text-xs font-mono text-slate-400 opacity-80">
                    <span>p95: {issue.p95_latency_ms.toFixed(0)}ms</span>
                    {issue.error_rate !== undefined && <span>err: {(issue.error_rate * 100).toFixed(1)}%</span>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
