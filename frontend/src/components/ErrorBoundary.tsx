import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
  errorInfo?: React.ErrorInfo;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ComponentType<{ error: Error; retry: () => void }>;
}

class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
    this.setState({ error, errorInfo });
  }

  retry = () => {
    this.setState({ hasError: false, error: undefined, errorInfo: undefined });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        const FallbackComponent = this.props.fallback;
        return <FallbackComponent error={this.state.error!} retry={this.retry} />;
      }

      return <DefaultErrorFallback error={this.state.error!} retry={this.retry} />;
    }

    return this.props.children;
  }
}

const DefaultErrorFallback: React.FC<{ error: Error; retry: () => void }> = ({ error, retry }) => {
  return (
    <div className="min-h-[400px] flex items-center justify-center p-6">
      <div className="max-w-md w-full bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-8 text-center shadow-lg">
        <AlertTriangle className="h-16 w-16 text-red-500 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100 mb-2">
          Something went wrong
        </h2>
        <p className="text-slate-600 dark:text-slate-400 mb-6">
          We encountered an unexpected error. Please try refreshing the page or contact support if the problem persists.
        </p>
        <div className="space-y-3">
          <button
            onClick={retry}
            className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-3 rounded-lg font-medium transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
            Try Again
          </button>
          <button
            onClick={() => window.location.reload()}
            className="w-full bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 px-4 py-3 rounded-lg font-medium transition-colors"
          >
            Refresh Page
          </button>
        </div>
        {import.meta.env.DEV && (
          <details className="mt-6 text-left">
            <summary className="cursor-pointer text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300">
              Error Details (Development)
            </summary>
            <pre className="mt-2 text-xs bg-slate-100 dark:bg-slate-900 p-3 rounded overflow-auto text-red-600 dark:text-red-400">
              {error.stack}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
};

// Hook version for functional components
export const useErrorHandler = () => {
  return (error: Error, errorInfo?: React.ErrorInfo) => {
    console.error('Error handled:', error, errorInfo);
    // In a real app, you might want to send this to an error reporting service
  };
};

export default ErrorBoundary;
