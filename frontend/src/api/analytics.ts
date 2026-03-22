import { apiRequest } from "../api";
import type { ApiResponse, GlobalAnalytics, TimeseriesPoint, RouteStat, UserStats, HeavyUser } from "../types/api";

export function fetchGlobalAnalytics() {
  return apiRequest<ApiResponse<GlobalAnalytics>>("/analytics/global");
}

export function fetchTimeseries(hours = 24) {
  return apiRequest<ApiResponse<TimeseriesPoint[]>>(`/analytics/timeseries?hours=${hours}`);
}

export function fetchRouteStats() {
  return apiRequest<ApiResponse<Record<string, RouteStat>>>("/analytics/routes");
}

export function fetchTopUsers(limit = 10) {
  return apiRequest<ApiResponse<HeavyUser[]>>(`/analytics/top-users?limit=${limit}`);
}

export function fetchUserAnalytics(userId?: string) {
  const query = userId ? `?user_id=${userId}` : '';
  return apiRequest<ApiResponse<UserStats>>(`/analytics/user${query}`);
}
