export interface ApiErrorShape {
  response?: {
    status?: number;
    data?: {
      detail?: string;
    };
  };
  message?: string;
}

export function asApiError(err: unknown): ApiErrorShape {
  return (err ?? {}) as ApiErrorShape;
}

export function apiErrorMessage(err: unknown, fallback: string): string {
  const apiErr = asApiError(err);
  return apiErr.response?.data?.detail || apiErr.message || fallback;
}
