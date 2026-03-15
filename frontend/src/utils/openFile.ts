import api, { API_URL } from '../api';

const PROTECTED_FILE_PATTERNS = [
  /^\/papers\/uploaded\/\d+\/download$/,
  /^\/workspaces\/\d+\/files\/\d+\/download$/,
];

const isProtectedFilePath = (path: string): boolean =>
  PROTECTED_FILE_PATTERNS.some((pattern) => pattern.test(path));

const resolveUrl = (rawUrl: string): URL => {
  try {
    return new URL(rawUrl, window.location.origin);
  } catch {
    return new URL(window.location.origin);
  }
};

const inferFilename = (path: string, fallback: string): string => {
  const last = path.split('/').filter(Boolean).pop();
  return last || fallback;
};

export const openFileUrl = async (rawUrl: string, fallbackFilename = 'file.bin'): Promise<void> => {
  const trimmed = String(rawUrl || '').trim();
  if (!trimmed) {
    throw new Error('File URL is empty.');
  }

  const parsed = resolveUrl(trimmed);
  if (!isProtectedFilePath(parsed.pathname)) {
    window.open(parsed.toString(), '_blank', 'noopener,noreferrer');
    return;
  }

  const relativePath = `${parsed.pathname}${parsed.search || ''}`;
  const response = await api.get(relativePath, { responseType: 'blob' });
  const blob = new Blob([response.data], {
    type: response.headers['content-type'] || 'application/octet-stream',
  });
  const objectUrl = window.URL.createObjectURL(blob);
  const opened = window.open(objectUrl, '_blank', 'noopener,noreferrer');

  if (!opened) {
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = inferFilename(parsed.pathname, fallbackFilename);
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  }

  window.setTimeout(() => {
    window.URL.revokeObjectURL(objectUrl);
  }, 60_000);
};

export const isBackendProtectedFileUrl = (rawUrl: string): boolean => {
  const trimmed = String(rawUrl || '').trim();
  if (!trimmed) {
    return false;
  }
  const parsed = resolveUrl(trimmed);
  if (trimmed.startsWith(API_URL)) {
    return isProtectedFilePath(parsed.pathname);
  }
  return isProtectedFilePath(parsed.pathname);
};
