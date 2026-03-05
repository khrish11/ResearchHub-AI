import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

// Design tokens (Tailwind-based)
export const tokens = {
  colors: {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white',
    secondary: 'bg-slate-100 hover:bg-slate-200 text-slate-900',
    danger: 'bg-red-600 hover:bg-red-700 text-white',
    ghost: 'bg-transparent hover:bg-slate-100 text-slate-900',
    border: 'border border-slate-300',
  },
  ring: 'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
  disabled: 'disabled:opacity-50 disabled:cursor-not-allowed',
  radius: 'rounded-md',
  input: 'border border-slate-300 bg-white text-slate-900 placeholder-slate-400',
};

// Button
export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
};

export const Button: React.FC<ButtonProps> = ({
  children,
  className = '',
  variant = 'primary',
  size = 'md',
  loading = false,
  ...props
}) => {
  const sizeCls = size === 'sm' ? 'px-2.5 py-1.5 text-sm' : size === 'lg' ? 'px-5 py-3 text-base' : 'px-4 py-2 text-sm';
  const variantCls = tokens.colors[variant] || tokens.colors.primary;
  return (
    <button
      className={`inline-flex items-center justify-center ${tokens.radius} ${tokens.ring} ${tokens.disabled} ${sizeCls} ${variantCls} ${className}`}
      {...props}
      disabled={loading || props.disabled}
    >
      {loading && (
        <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-current" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path>
        </svg>
      )}
      <span>{children}</span>
    </button>
  );
};

// Input
export type InputProps = React.InputHTMLAttributes<HTMLInputElement> & { label?: string; error?: string };
export const Input: React.FC<InputProps> = ({ label, error, className = '', ...props }) => (
  <label className="w-full block">
    {label && <div className="mb-1 text-sm text-slate-700">{label}</div>}
    <input
      className={`w-full ${tokens.radius} ${tokens.ring} ${tokens.input} px-3 py-2 text-sm ${className}`}
      {...props}
    />
    {error && <div className="mt-1 text-xs text-red-600">{error}</div>}
  </label>
);

// TextArea
export type TextAreaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: string; error?: string };
export const TextArea: React.FC<TextAreaProps> = ({ label, error, className = '', ...props }) => (
  <label className="w-full block">
    {label && <div className="mb-1 text-sm text-slate-700">{label}</div>}
    <textarea
      className={`w-full ${tokens.radius} ${tokens.ring} ${tokens.input} px-3 py-2 text-sm min-h-[100px] ${className}`}
      {...props}
    />
    {error && <div className="mt-1 text-xs text-red-600">{error}</div>}
  </label>
);

// Select
export type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement> & { label?: string; error?: string };
export const Select: React.FC<SelectProps> = ({ label, error, className = '', children, ...props }) => (
  <label className="w-full block">
    {label && <div className="mb-1 text-sm text-slate-700">{label}</div>}
    <select className={`w-full ${tokens.radius} ${tokens.ring} ${tokens.input} px-3 py-2 text-sm ${className}`} {...props}>
      {children}
    </select>
    {error && <div className="mt-1 text-xs text-red-600">{error}</div>}
  </label>
);

// Badge
export const Badge: React.FC<{ variant?: 'default' | 'blue' | 'green' | 'red' | 'slate'; className?: string } & React.HTMLAttributes<HTMLSpanElement>> = ({
  variant = 'slate',
  className = '',
  children,
  ...props
}) => {
  const map: Record<string, string> = {
    default: 'bg-slate-200 text-slate-800',
    blue: 'bg-blue-100 text-blue-800',
    green: 'bg-emerald-100 text-emerald-800',
    red: 'bg-red-100 text-red-800',
    slate: 'bg-slate-100 text-slate-800',
  };
  return (
    <span className={`inline-flex items-center ${tokens.radius} px-2 py-0.5 text-xs font-medium ${map[variant]} ${className}`} {...props}>
      {children}
    </span>
  );
};

// Tabs
export const Tabs: React.FC<{
  value: string;
  onChange: (val: string) => void;
  tabs: { value: string; label: string; disabled?: boolean }[];
  className?: string;
}> = ({ value, onChange, tabs, className = '' }) => (
  <div className={`inline-flex items-center gap-1 ${className}`} role="tablist" aria-label="Sources">
    {tabs.map((t) => (
      <button
        key={t.value}
        role="tab"
        aria-selected={value === t.value}
        aria-controls={`panel-${t.value}`}
        disabled={t.disabled}
        className={`px-3 py-1.5 text-sm ${tokens.radius} ${tokens.disabled} ${value === t.value ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-800 hover:bg-slate-200'}`}
        onClick={() => onChange(t.value)}
      >
        {t.label}
      </button>
    ))}
  </div>
);

// Modal / Sheet (simple)
type ModalProps = React.PropsWithChildren<{ open: boolean; onClose: () => void; title?: string; className?: string }>;
export const Modal: React.FC<ModalProps> = ({ open, onClose, title, className = '', children }) => {
  const escHandler = useCallback((e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); }, [onClose]);
  useEffect(() => { if (!open) return; document.addEventListener('keydown', escHandler); return () => document.removeEventListener('keydown', escHandler); }, [open, escHandler]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="absolute inset-0 flex items-center justify-center p-4">
        <div className={`w-full max-w-2xl bg-white ${tokens.radius} shadow-lg ${className}`}>
          <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
            <h3 className="text-sm font-medium text-slate-900">{title}</h3>
            <button aria-label="Close" className={`p-1 ${tokens.ring} ${tokens.radius} hover:bg-slate-100`} onClick={onClose}>✕</button>
          </div>
          <div className="p-4">{children}</div>
        </div>
      </div>
    </div>
  );
};

// Toasts
type Toast = { id: number; title?: string; description?: string; variant?: 'success' | 'error' | 'info' };
const ToastCtx = createContext<{ notify: (t: Omit<Toast, 'id'>) => void } | null>(null);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const ctr = useRef(1);
  const remove = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const notify = useCallback((t: Omit<Toast, 'id'>) => {
    const id = ctr.current++;
    setToasts((arr) => [...arr, { id, ...t }]);
    setTimeout(() => remove(id), 3500);
  }, [remove]);
  const value = useMemo(() => ({ notify }), [notify]);
  return (
    <ToastCtx.Provider value={value}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 space-y-2">
        {toasts.map((t) => {
          const color = t.variant === 'success' ? 'bg-emerald-600' : t.variant === 'error' ? 'bg-red-600' : 'bg-slate-900';
          return (
            <div key={t.id} className={`text-white ${tokens.radius} shadow px-4 py-3 ${color} w-80 max-w-[90vw]`} role="status">
              {t.title && <div className="font-medium text-sm">{t.title}</div>}
              {t.description && <div className="text-sm opacity-90 mt-0.5">{t.description}</div>}
            </div>
          );
        })}
      </div>
    </ToastCtx.Provider>
  );
};

export const useToast = () => {
  const ctx = useContext(ToastCtx);
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>');
  return ctx;
};

// Skeletons
export const Skeleton: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div className={`animate-pulse bg-slate-200 ${tokens.radius} ${className}`} />
);

// Utility: DebouncedInput
export const DebouncedInput: React.FC<{
  value: string;
  onChange: (v: string) => void;
  delay?: number;
  placeholder?: string;
  className?: string;
}> = ({ value, onChange, delay = 400, placeholder, className = '' }) => {
  const [inner, setInner] = useState(value);
  useEffect(() => setInner(value), [value]);
  useEffect(() => {
    const t = setTimeout(() => { if (inner !== value) onChange(inner); }, delay);
    return () => clearTimeout(t);
  }, [delay, inner, onChange, value]);
  return (
    <input
      className={`w-full ${tokens.radius} ${tokens.ring} ${tokens.input} px-3 py-2 text-sm ${className}`}
      placeholder={placeholder}
      value={inner}
      onChange={(e) => setInner(e.target.value)}
    />
  );
};

// Card
type CardProps = React.PropsWithChildren<{ className?: string; title?: string; actions?: React.ReactNode }>;
export const Card: React.FC<CardProps> = ({ className = '', title, actions, children }) => (
  <div className={`bg-white ${tokens.radius} border border-slate-200 shadow-sm ${className}`}>
    {(title || actions) && (
      <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
        <h3 className="text-sm font-medium text-slate-900">{title}</h3>
        {actions}
      </div>
    )}
    <div className="p-4">{children}</div>
  </div>
);

// Helper: SourceStatus
export const SourceStatus: React.FC<{ status: 'ok' | 'pending' | 'error'; label: string }> = ({ status, label }) => {
  const map = {
    ok: { text: 'text-emerald-700', dot: 'bg-emerald-500' },
    pending: { text: 'text-amber-700', dot: 'bg-amber-500' },
    error: { text: 'text-red-700', dot: 'bg-red-500' },
  } as const;
  return (
    <div className={`inline-flex items-center gap-2 text-xs ${map[status].text}`}>
      <span className={`inline-block w-2.5 h-2.5 ${tokens.radius} ${map[status].dot}`} />
      <span>{label}</span>
    </div>
  );
};
