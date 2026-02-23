const normalizeBase = (value: string): string => {
  const trimmed = (value || '').trim();
  if (!trimmed || trimmed === '/') {
    return '';
  }
  const withLeadingSlash = trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
  return withLeadingSlash.replace(/\/+$/, '');
};

export const getAppBasePath = (): string => {
  const envBase = normalizeBase(import.meta.env.VITE_ROUTER_BASENAME || '');
  if (envBase) {
    return envBase;
  }

  const pathname = window.location.pathname || '';
  if (pathname === '/frontend' || pathname.startsWith('/frontend/')) {
    return '/frontend';
  }
  return '';
};

export const toAppPath = (path: string): string => {
  const safePath = path.startsWith('/') ? path : `/${path}`;
  return `${getAppBasePath()}${safePath}`;
};
