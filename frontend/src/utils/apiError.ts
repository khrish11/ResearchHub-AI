export interface ApiErrorShape {
  response?: {
    status?: number;
    data?: unknown;
  };
  message?: string;
}

export function asApiError(err: unknown): ApiErrorShape {
  return (err ?? {}) as ApiErrorShape;
}

function _readText(value: unknown): string {
  if (typeof value === 'string') {
    return value.trim();
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value).trim();
  }
  return '';
}

export function apiErrorMessageFromPayload(payload: unknown, fallback: string): string {
  if (typeof payload === 'string') {
    return _readText(payload) || fallback;
  }
  if (!payload || typeof payload !== 'object') {
    return fallback;
  }
  const data = payload as {
    error_code?: unknown;
    message?: unknown;
    detail?: unknown;
    details?: unknown;
    errors?: unknown;
  };
  const directMessage =
    _readText(data.message) ||
    _readText(data.detail) ||
    _readText((data.details as { message?: unknown } | undefined)?.message);
  if (directMessage) {
    return directMessage;
  }
  if (Array.isArray(data.errors) && data.errors.length > 0) {
    const first = data.errors[0] as { field?: unknown; message?: unknown };
    const field = _readText(first.field);
    const message = _readText(first.message);
    const combined = [field, message].filter(Boolean).join(': ');
    if (combined) {
      return combined;
    }
  }
  const code = _readText(data.error_code);
  if (code) {
    return code;
  }
  return fallback;
}

export function apiErrorMessage(err: unknown, fallback: string): string {
  const apiErr = asApiError(err);
  const payloadMessage = apiErrorMessageFromPayload(apiErr.response?.data, '');
  if (payloadMessage) {
    return payloadMessage;
  }
  const message = _readText(apiErr.message);
  if (!message) {
    return fallback;
  }
  if (message.toLowerCase() === 'network error') {
    return fallback;
  }
  return message;
}
