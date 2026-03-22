export interface ApiResponse<T> {
  data: T;
  meta: {
    generated_at: string;
  };
}

export interface GlobalAnalytics {
  total_queries: number;
  successful_queries: number;
  avg_response_time_ms: number;
  cache_hit_rate: number;
  error_rate: number;
  error_count: number;
  cache_hits: number;
  unique_users: number;
  docs_scanned: number;
}

export interface TimeseriesPoint {
  hour: string;
  query_count: number;
  cache_hits: number;
  error_count: number;
}

export interface RouteStat {
  route: string;
  query_count: number;
  cache_hits: number;
  cache_hit_rate: number;
  error_count: number;
  avg_response_time_ms: number;
  p95_latency_ms?: number;
  error_rate?: number;
  slow_query_count?: number;
  slow_query_pct?: number;
  severity?: 'CRITICAL' | 'WARNING' | 'INFO';
  flags?: string[];
}

export interface UserStats {
  user_id: string;
  total_queries: number;
  successful_queries: number;
  error_count: number;
  cache_hits: number;
  cache_hit_rate: number;
  avg_response_time_ms: number;
  total_input_chars: number;
  total_output_chars: number;
  routes_used: Record<string, number>;
}

export interface HeavyUser {
  user_id: string;
  query_count: number;
  fraction_of_total: number;
  error_rate: number;
  cache_hit_rate: number;
  avg_latency_ms: number;
  severity: string;
  recommendation: string;
}

export interface TopIssue {
  category: string;
  route?: string;
  severity: string;
  p95_latency_ms?: number;
  error_rate?: number;
  fraction_of_total?: number;
  recommendation?: string;
  cache_hit_rate?: number;
  query_count?: number;
}

export interface LowCacheRoute {
  route: string;
  cache_hit_rate: number;
  query_count: number;
  recommendations: string[];
}

export interface HighErrorRoute {
  route: string;
  error_rate: number;
  query_count: number;
  severity: string;
  recommendation: string;
}

export interface TrendingRoute {
  route: string;
  recent_queries: number;
  window_hours: number;
  approx_hourly_rate: number;
  baseline_hourly_rate: number;
  spike_factor: number;
  recommendation: string;
}

export interface InsightsSummary {
  overview: {
    total_slow_queries: number;
    slow_query_threshold_ms: number;
    routes_analyzed: number;
    critical_routes: number;
    warning_routes: number;
    info_routes: number;
    critical_errors: number;
    warning_errors: number;
    heavy_users: number;
    critical_heavy_users: number;
    low_cache_routes: number;
    trending_routes: number;
  };
  top_issues: TopIssue[];
  cache_optimization: LowCacheRoute[];
  performance_by_route: RouteStat[];
  error_alerts: HighErrorRoute[];
  high_usage_users: HeavyUser[];
  trending_routes: TrendingRoute[];
  meta?: {
    generated_at: string;
  };
}
