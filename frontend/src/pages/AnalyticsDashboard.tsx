import { useEffect, useState, useCallback, useMemo } from 'react';
import { toast } from 'react-hot-toast';
import { RefreshCw, Loader2, Download, Sun, Moon } from 'lucide-react';
import Layout from '../components/Layout';
import { fetchGlobalAnalytics, fetchTimeseries } from '../api/analytics';
import { fetchInsightsSummary, fetchPerformanceInsights } from '../api/insights';
import type { 
  GlobalAnalytics as GlobalStats, 
  TimeseriesPoint, 
  RouteStat, 
  InsightsSummary, 
  TopIssue 
} from '../types/api';

// Hooks
import { useLocalStorage } from '../hooks/useLocalStorage';
import { useRealtimeData } from '../hooks/useRealtimeData';
import { exportToCSV, exportToJSON } from '../utils/exportUtils';

// Components
import AlertsBanner from '../components/analytics/AlertsBanner';
import FilterBar, { FilterState } from '../components/analytics/FilterBar';
import OverviewCards from '../components/analytics/OverviewCards';
import TimeseriesChart from '../components/analytics/TimeseriesChart';
import RouteTable from '../components/analytics/RouteTable';
import InsightsPanel from '../components/analytics/InsightsPanel';
import DrilldownModal from '../components/analytics/DrilldownModal';

export default function AnalyticsDashboard() {
  // Data State
  const [global, setGlobal] = useState<GlobalStats | null>(null);
  const [timeseries, setTimeseries] = useState<TimeseriesPoint[]>([]);
  const [performance, setPerformance] = useState<RouteStat[]>([]);
  const [summary, setSummary] = useState<InsightsSummary | null>(null);
  
  // UI State
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters State - Persisted
  const [filters, setFilters] = useLocalStorage<FilterState>('dashboard_filters', {
    hours: 24,
    route: 'all',
    severity: 'all'
  });

  // Theme State - Persisted
  const [theme, setTheme] = useLocalStorage<'dark' | 'light'>('dashboard_theme', 'dark');

  useEffect(() => {
    // Apply theme globally
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

  // Drilldown Modal State
  const [selectedRoute, setSelectedRoute] = useState<RouteStat | null>(null);
  const [selectedIssue, setSelectedIssue] = useState<TopIssue | null>(null);

  const fetchAll = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true);
    setError(null);
    try {
      const [globalRes, timeseriesRes, perfRes, summaryRes] = await Promise.allSettled([
        fetchGlobalAnalytics(),
        fetchTimeseries(filters.hours),
        fetchPerformanceInsights(),
        fetchInsightsSummary(),
      ]);

      if (globalRes.status === 'fulfilled') setGlobal(globalRes.value.data);
      if (timeseriesRes.status === 'fulfilled') setTimeseries(timeseriesRes.value.data);
      if (perfRes.status === 'fulfilled') {
        const perfData = perfRes.value.data as any;
        setPerformance(perfData.routes || perfData || []);
      }
      
      if (summaryRes.status === 'fulfilled') {
        const newSummary = summaryRes.value.data;
        setSummary(newSummary);

        // Real-Time Alert Trigger
        const criticalIssues = (newSummary.top_issues || []).filter(i => i.severity === 'CRITICAL');
        if (criticalIssues.length > 0) {
          toast.error(`${criticalIssues.length} Critical System Issues Detected!`, { id: 'critical-alerts' });
        }
      }
      setLastRefresh(new Date());
    } catch (err: unknown) {
      const msg = (err as Error)?.message || 'Failed to load analytics data';
      setError(msg);
      toast.error(msg);
    } finally {
      if (loading) setLoading(false);
      if (isManual) setRefreshing(false);
    }
  }, [filters.hours, loading]);

  // Initial Fetch
  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // Resilient Real-Time integration (SSE w/ Polling fallback)
  useRealtimeData({
    url: `${import.meta.env.VITE_API_BASE || 'http://localhost:8010'}/analytics/stream`,
    pollingIntervalMs: 30000,
    onPollingTick: () => fetchAll(false),
    onData: (data) => {
       if (data.global) setGlobal(data.global);
       if (data.timeseries) setTimeseries(data.timeseries);
       if (data.performance) setPerformance(data.performance);
       if (data.summary) {
         setSummary(data.summary);
         const criticalIssues = (data.summary.top_issues || []).filter((i: any) => i.severity === 'CRITICAL');
         if (criticalIssues.length > 0) {
           toast.error(`${criticalIssues.length} Critical System Issues Detected!`, { id: 'critical-alerts' });
         }
       }
       setLastRefresh(new Date());
    }
  });

  // Export handlers
  const handleExportJSON = () => {
    exportToJSON({ global, timeseries, performance, summary }, 'analytics_export');
    toast.success('Exported to JSON');
  };

  const handleExportCSV = () => {
    exportToCSV(performance, 'route_performance_export');
    toast.success('Exported Route Performance to CSV');
  };

  // Handle filter changes
  const handleFilterChange = (newFilters: Partial<FilterState>) => {
    setFilters(prev => ({ ...prev, ...newFilters }));
  };

  // Memoized Filtered Data
  const filteredPerformance = useMemo(() => {
    return performance.filter(route => {
      if (filters.route !== 'all' && route.route !== filters.route) return false;
      if (filters.severity !== 'all' && route.severity !== filters.severity) return false;
      return true;
    });
  }, [performance, filters.route, filters.severity]);

  const topIssues = summary?.top_issues || [];

  return (
    <Layout>
      <div className={`max-w-7xl mx-auto space-y-6 transition-colors duration-300 ${theme === 'light' ? 'bg-slate-50 p-6 rounded-2xl' : ''}`}>
        
        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:justify-between md:items-end gap-4 mb-6">
          <div>
            <h1 className={`text-3xl font-bold font-sans tracking-tight flex items-center gap-3 ${theme === 'light' ? 'text-slate-900' : 'text-white'}`}>
              Analytics & Insights
              {refreshing && <Loader2 size={24} className="text-indigo-400 animate-spin" />}
            </h1>
            <p className={`mt-2 ${theme === 'light' ? 'text-slate-600' : 'text-slate-400'}`}>
              System performance, traffic trends, and actionable recommendations.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className={`text-xs font-mono hidden sm:inline ${theme === 'light' ? 'text-slate-500' : 'text-slate-400'}`}>
              Updated: {lastRefresh.toLocaleTimeString()}
            </span>
            
            <button
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              className={`p-2 rounded-lg border transition-colors ${theme === 'light' ? 'bg-white border-slate-200 text-slate-700 hover:bg-slate-100' : 'bg-white/5 border-white/10 text-slate-300 hover:bg-white/10'}`}
              title="Toggle Theme"
            >
              {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            </button>

            <div className="relative group">
              <button
                className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-all font-medium ${theme === 'light' ? 'bg-white border-slate-200 text-slate-700 hover:bg-slate-100' : 'bg-white/5 border-white/10 text-white hover:bg-white/10'}`}
              >
                <Download size={16} />
                <span className="hidden sm:inline">Export</span>
              </button>
              <div className="absolute right-0 top-full mt-2 w-32 bg-slate-800 border border-slate-700/50 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                <button onClick={handleExportCSV} className="w-full text-left px-4 py-2 text-sm text-slate-300 hover:bg-white/5 hover:text-white transition-colors">CSV (Routes)</button>
                <button onClick={handleExportJSON} className="w-full text-left px-4 py-2 text-sm text-slate-300 hover:bg-white/5 hover:text-white transition-colors">JSON (Full)</button>
              </div>
            </div>

            <button
              onClick={() => fetchAll(true)}
              disabled={refreshing}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-all font-medium disabled:opacity-50 ${theme === 'light' ? 'bg-indigo-50 border-indigo-200 text-indigo-700 hover:bg-indigo-100' : 'bg-white/5 border-white/10 text-white hover:bg-white/10'}`}
            >
              <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
              <span className="hidden sm:inline">{refreshing ? 'Refreshing...' : 'Refresh'}</span>
            </button>
          </div>
        </div>

        {error && (
          <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 mb-6">
            Error loading dashboard: {error}
          </div>
        )}

        <AlertsBanner issues={topIssues} />

        <FilterBar 
          filters={filters} 
          onFilterChange={handleFilterChange} 
          availableRoutes={performance} 
        />

        <OverviewCards global={global} loading={loading} />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <TimeseriesChart timeseries={timeseries} loading={loading} />
            <RouteTable 
              data={filteredPerformance} 
              loading={loading} 
              onRouteClick={(route) => setSelectedRoute(route)} 
            />
          </div>
          <div className="lg:col-span-1">
            <InsightsPanel 
              summary={summary} 
              loading={loading} 
              onIssueClick={(issue) => setSelectedIssue(issue)}
            />
          </div>
        </div>

      </div>

      {/* Drilldown Modals */}
      <DrilldownModal
        isOpen={!!selectedRoute}
        onClose={() => setSelectedRoute(null)}
        title={`Route Details: ${selectedRoute?.route}`}
      >
        {selectedRoute && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white/5 p-4 rounded-xl border border-white/10 hover:bg-white/10 transition-colors">
                <p className="text-slate-400 text-xs mb-1">Total Vol</p>
                <p className="text-xl font-mono text-slate-200">{selectedRoute.query_count}</p>
              </div>
              <div className="bg-white/5 p-4 rounded-xl border border-white/10 hover:bg-white/10 transition-colors">
                <p className="text-slate-400 text-xs mb-1">Cache Hit Rate</p>
                <p className="text-xl font-mono text-cyan-400">{((selectedRoute.cache_hit_rate || 0) * 100).toFixed(1)}%</p>
              </div>
              <div className="bg-white/5 p-4 rounded-xl border border-white/10 hover:bg-white/10 transition-colors">
                <p className="text-slate-400 text-xs mb-1">Error Rate</p>
                <p className="text-xl font-mono text-red-400">{((selectedRoute.error_rate || 0) * 100).toFixed(1)}%</p>
              </div>
              <div className="bg-white/5 p-4 rounded-xl border border-white/10 hover:bg-white/10 transition-colors">
                <p className="text-slate-400 text-xs mb-1">p95 Latency</p>
                <p className="text-xl font-mono text-amber-400">{selectedRoute.p95_latency_ms?.toFixed(0) || 0}ms</p>
              </div>
            </div>
            
            {selectedRoute.flags && selectedRoute.flags.length > 0 && (
              <div className="bg-amber-500/10 border border-amber-500/20 p-4 rounded-xl shadow-inner">
                <h4 className="text-amber-400 text-sm font-semibold mb-2">Detected Anomalies</h4>
                <ul className="list-disc list-inside text-amber-200/80 text-sm space-y-1">
                  {selectedRoute.flags.map((flag, idx) => (
                    <li key={idx}>{flag}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </DrilldownModal>

      <DrilldownModal
        isOpen={!!selectedIssue}
        onClose={() => setSelectedIssue(null)}
        title={`Issue Analysis: ${selectedIssue?.category}`}
      >
        {selectedIssue && (
          <div className="space-y-6">
            <div className="bg-slate-800/50 p-5 rounded-xl border border-white/10 shadow-inner">
              <h4 className="text-slate-300 font-semibold mb-2">Root Cause & Context</h4>
              <p className="text-sm text-slate-400 leading-relaxed mb-4">
                We detected a {selectedIssue.category.toLowerCase().replace(/_/g, ' ')} 
                issue affecting system reliability.
              </p>
              {selectedIssue.route && (
                <div className="inline-block bg-white/5 px-3 py-1.5 rounded-lg border border-white/10 font-mono text-xs text-indigo-300">
                  Target Route: {selectedIssue.route}
                </div>
              )}
            </div>

            <div className="bg-emerald-500/10 p-5 rounded-xl border border-emerald-500/20 shadow-inner">
              <h4 className="text-emerald-400 font-semibold mb-2">Recommended Corrective Action</h4>
              <p className="text-sm text-emerald-200/80 leading-relaxed">
                {selectedIssue.recommendation || "Monitor this route closely and consider optimizing backend queries."}
              </p>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
               {selectedIssue.p95_latency_ms !== undefined && (
                 <div className="bg-white/5 p-4 rounded-xl border border-white/10 hover:bg-white/10 transition-colors">
                   <p className="text-slate-400 text-xs mb-1">Detected p95 Latency</p>
                   <p className="text-xl font-mono text-slate-200">{selectedIssue.p95_latency_ms.toFixed(0)} ms</p>
                 </div>
               )}
               {selectedIssue.error_rate !== undefined && (
                 <div className="bg-white/5 p-4 rounded-xl border border-white/10 hover:bg-white/10 transition-colors">
                   <p className="text-slate-400 text-xs mb-1">Detected Error Rate</p>
                   <p className="text-xl font-mono text-slate-200">{((selectedIssue.error_rate || 0) * 100).toFixed(1)}%</p>
                 </div>
               )}
            </div>
          </div>
        )}
      </DrilldownModal>

    </Layout>
  );
}
