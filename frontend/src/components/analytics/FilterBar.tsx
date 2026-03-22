import { Clock, Filter, AlertCircle, Activity } from 'lucide-react';
import { RouteStat } from '../../types/api';

export interface FilterState {
  hours: number;
  route: string;
  severity: string;
}

interface FilterBarProps {
  filters: FilterState;
  onFilterChange: (newFilters: Partial<FilterState>) => void;
  availableRoutes: RouteStat[];
}

export default function FilterBar({ filters, onFilterChange, availableRoutes }: FilterBarProps) {
  return (
    <div className="bg-white/5 dark:bg-slate-800/80 backdrop-blur-md border border-white/10 rounded-xl p-4 sticky top-4 z-20 flex flex-wrap items-center gap-4 shadow-xl">
      <div className="flex items-center gap-2 text-slate-300 text-sm font-medium pr-2 border-r border-white/10">
        <Filter size={16} className="text-indigo-400" />
        Filters
      </div>

      {/* Time Range */}
      <div className="flex items-center gap-2">
        <Clock size={14} className="text-slate-500" />
        <select
          value={filters.hours}
          onChange={(e) => onFilterChange({ hours: Number(e.target.value) })}
          className="bg-slate-900/50 border border-white/10 rounded-lg text-sm text-slate-300 px-3 py-1.5 focus:outline-none focus:border-indigo-500/50 transition-colors cursor-pointer"
        >
          <option value={1}>Last 1 Hour</option>
          <option value={24}>Last 24 Hours</option>
          <option value={168}>Last 7 Days</option>
        </select>
      </div>

      {/* Route Filter */}
      <div className="flex items-center gap-2">
        <Activity size={14} className="text-slate-500" />
        <select
          value={filters.route}
          onChange={(e) => onFilterChange({ route: e.target.value })}
          className="bg-slate-900/50 border border-white/10 rounded-lg text-sm text-slate-300 px-3 py-1.5 focus:outline-none focus:border-indigo-500/50 transition-colors cursor-pointer max-w-[150px] truncate"
        >
          <option value="all">All Routes</option>
          {availableRoutes.map(r => (
            <option key={r.route} value={r.route}>{r.route}</option>
          ))}
        </select>
      </div>

      {/* Severity Filter */}
      <div className="flex items-center gap-2">
        <AlertCircle size={14} className="text-slate-500" />
        <select
          value={filters.severity}
          onChange={(e) => onFilterChange({ severity: e.target.value })}
          className="bg-slate-900/50 border border-white/10 rounded-lg text-sm text-slate-300 px-3 py-1.5 focus:outline-none focus:border-indigo-500/50 transition-colors cursor-pointer"
        >
          <option value="all">All Severities</option>
          <option value="CRITICAL">Critical Only</option>
          <option value="WARNING">Warning</option>
          <option value="INFO">Healthy</option>
        </select>
      </div>
    </div>
  );
}
