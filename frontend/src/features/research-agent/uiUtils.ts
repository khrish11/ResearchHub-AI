export const toStringList = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }
  if (typeof value === 'string') {
    return value
      .split('\n')
      .map((line) => line.replace(/^[-*]\s*/, '').trim())
      .filter((line) => line.length > 0);
  }
  if (value && typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>).map(([k, v]) => `${k}: ${String(v)}`);
  }
  return [];
};

export const qualityTone = (label: string): 'green' | 'amber' | 'rose' | 'indigo' | 'slate' => {
  const normalized = (label || '').toLowerCase();
  if (normalized === 'excellent' || normalized === 'strong') return 'green';
  if (normalized === 'fair') return 'amber';
  if (normalized === 'weak') return 'rose';
  if (normalized === 'strict') return 'indigo';
  return 'slate';
};

export const nodeColor = (type: string): string => {
  const normalized = type.toLowerCase();
  if (normalized === 'paper') return '#6366f1';
  if (normalized === 'concept') return '#14b8a6';
  if (normalized === 'author') return '#f59e0b';
  if (normalized === 'year') return '#06b6d4';
  return '#64748b';
};
