import { XCircle, AlertTriangle, Info } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { TopIssue } from '../../types/api';

interface AlertsBannerProps {
  issues: TopIssue[];
}

export default function AlertsBanner({ issues }: AlertsBannerProps) {
  const criticalIssues = issues.filter(i => i.severity === 'CRITICAL');
  const warningIssues = issues.filter(i => i.severity === 'WARNING');

  if (!criticalIssues.length && !warningIssues.length) return null;

  return (
    <AnimatePresence>
      {(criticalIssues.length > 0 || warningIssues.length > 0) && (
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95 }}
          className={`border rounded-xl p-4 flex items-start gap-3 mb-6 shadow-lg ${
            criticalIssues.length > 0 
              ? 'bg-red-500/15 border-red-500/40' 
              : 'bg-amber-500/15 border-amber-500/40'
          }`}
        >
          {criticalIssues.length > 0 ? (
            <XCircle className="text-red-400 shrink-0 mt-0.5" size={20} />
          ) : (
            <AlertTriangle className="text-amber-400 shrink-0 mt-0.5" size={20} />
          )}
          <div className="flex-1 min-w-0">
            <h3 className={`font-semibold text-sm mb-1 ${
              criticalIssues.length > 0 ? 'text-red-300' : 'text-amber-300'
            }`}>
              {criticalIssues.length > 0 
                ? `${criticalIssues.length} Critical Issue${criticalIssues.length > 1 ? 's' : ''} Detected`
                : `${warningIssues.length} Warning${warningIssues.length > 1 ? 's' : ''} Detected`
              }
            </h3>
            <div className="space-y-1">
              {(criticalIssues.length > 0 ? criticalIssues : warningIssues).slice(0, 3).map((issue, i) => (
                <p key={i} className={`text-xs ${
                  criticalIssues.length > 0 ? 'text-red-200/80' : 'text-amber-200/80'
                }`}>
                  {issue.recommendation || `${issue.route || issue.category}: severity ${issue.severity}`}
                </p>
              ))}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
