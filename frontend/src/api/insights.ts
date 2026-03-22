import { apiRequest } from "../api";
import type { ApiResponse, InsightsSummary, RouteStat } from "../types/api";

export function fetchInsightsSummary() {
  return apiRequest<ApiResponse<InsightsSummary>>("/insights/summary");
}

export function fetchPerformanceInsights() {
  return apiRequest<ApiResponse<RouteStat[]>>("/insights/performance"); // adjust type if wrapped with ApiResponse
}
