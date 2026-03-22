import { RouteStat } from '../../types/api';
import { cn } from '../../utils/cn';

// Formatters
const formatPct = (num: number | undefined) => `${((num || 0) * 100).toFixed(1)}%`;
const formatMs = (ms: number | undefined) => `${(ms || 0).toFixed(0)} ms`;
const formatNumber = (num: number) => new Intl.NumberFormat('en-US').format(num);

export const SEVERITY_COLORS = {
  CRITICAL: {
    bg: 'bg-red-500/10',
    text: 'text-red-400',
    border: 'border-red-500/20',
    badge: 'bg-red-500/20 text-red-300 border-red-500/30'
  },
  WARNING: {
    bg: 'bg-amber-500/10',
    text: 'text-amber-400',
    border: 'border-amber-500/20',
    badge: 'bg-amber-500/20 text-amber-300 border-amber-500/30'
  },
  INFO: {
    bg: 'bg-indigo-500/10',
    text: 'text-indigo-400',
    border: 'border-indigo-500/20',
    badge: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30'
  }
} as const;

export function SeverityBadge({ severity }: { severity: string }) {
  const colors = SEVERITY_COLORS[severity as keyof typeof SEVERITY_COLORS] || SEVERITY_COLORS.INFO;
  return (
    <span className={cn('px-2 py-0.5 rounded text-[10px] font-bold tracking-wider border uppercase', colors.badge)}>
      {severity}
    </span>
  );
}

interface RouteTableProps {
  data: RouteStat[];
  loading: boolean;
  onRouteClick?: (route: RouteStat) => void;
}

export default function RouteTable({ data, loading, onRouteClick }: RouteTableProps) {
  return (
    <div className="bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border border-white/10 rounded-xl overflow-hidden">
      <div className="p-5 border-b border-white/10 flex justify-between items-center">
        <h3 className="text-sm font-semibold text-slate-200">Route Performance Degradation</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="text-xs text-slate-400 bg-black/20 uppercase">
            <tr>
              <th className="px-5 py-3 font-medium">Route Path</th>
              <th className="px-5 py-3 font-medium">Vol</th>
              <th className="px-5 py-3 font-medium">p95 Latency</th>
              <th className="px-5 py-3 font-medium">Err Rate</th>
              <th className="px-5 py-3 font-medium">Cache</th>
              <th className="px-5 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {loading ? (
              [1, 2, 3].map(i => (
                <tr key={i} className="animate-pulse">
                  <td className="px-5 py-4"><div className="h-4 bg-slate-700 rounded w-48" /></td>
                  <td className="px-5 py-4"><div className="h-4 bg-slate-700 rounded w-12" /></td>
                  <td className="px-5 py-4"><div className="h-4 bg-slate-700 rounded w-16" /></td>
                  <td className="px-5 py-4"><div className="h-4 bg-slate-700 rounded w-16" /></td>
                  <td className="px-5 py-4"><div className="h-4 bg-slate-700 rounded w-24" /></td>
                  <td className="px-5 py-4"><div className="h-5 bg-slate-700 rounded w-16" /></td>
                </tr>
              ))
            ) : data.map((row) => (
              <tr 
                key={row.route} 
                onClick={() => onRouteClick?.(row)}
                className={cn(
                  "hover:bg-white/5 transition-colors", 
                  onRouteClick && "cursor-pointer"
                )}
              >
                <td className="px-5 py-3 font-mono text-slate-300 text-xs truncate max-w-[200px]" title={row.route}>
                  {row.route}
                </td>
                <td className="px-5 py-3 text-slate-400 font-mono text-xs">{formatNumber(row.query_count)}</td>
                <td className="px-5 py-3">
                  <span className={cn(
                    'font-mono font-medium',
                    (row.p95_latency_ms || 0) >= 5000 ? 'text-red-400' : (row.p95_latency_ms || 0) >= 2000 ? 'text-amber-400' : 'text-slate-300'
                  )}>
                    {formatMs(row.p95_latency_ms || 0)}
                  </span>
                </td>
                <td className="px-5 py-3">
                  <span className={cn(
                    'font-mono font-medium',
                    (row.error_rate || 0) >= 0.1 ? 'text-red-400' : (row.error_rate || 0) >= 0.05 ? 'text-amber-400' : 'text-slate-300'
                  )}>
                    {formatPct(row.error_rate || 0)}
                  </span>
                </td>
                <td className="px-5 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div 
                        className={cn("h-full rounded-full", (row.cache_hit_rate || 0) > 0.5 ? 'bg-cyan-500' : 'bg-slate-500')} 
                        style={{ width: `${(row.cache_hit_rate || 0) * 100}%` }}
                      />
                    </div>
                    <span className="text-slate-400 text-xs font-mono w-12">{formatPct(row.cache_hit_rate || 0)}</span>
                  </div>
                </td>
                <td className="px-5 py-3"><SeverityBadge severity={row.severity || 'INFO'} /></td>
              </tr>
            ))}
            {(!loading && data.length === 0) && (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-slate-500">No route performance data available</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
