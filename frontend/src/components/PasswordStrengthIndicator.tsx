import React, { useMemo } from 'react';

interface PasswordStrengthProps {
  password: string;
  className?: string;
}

interface StrengthResult {
  score: number;
  label: string;
  color: string;
  width: string;
}

const PasswordStrengthIndicator: React.FC<PasswordStrengthProps> = ({ password, className = '' }) => {
  const strength = useMemo((): StrengthResult => {
    if (!password) {
      return { score: 0, label: '', color: 'bg-slate-200', width: 'w-0' };
    }

    let score = 0;

    // Length check
    if (password.length >= 8) score += 1;
    if (password.length >= 12) score += 1;

    // Character variety checks
    if (/[a-z]/.test(password)) score += 1; // lowercase
    if (/[A-Z]/.test(password)) score += 1; // uppercase
    if (/[0-9]/.test(password)) score += 1; // numbers
    if (/[^A-Za-z0-9]/.test(password)) score += 1; // special chars

    // Common patterns (reduce score)
    if (/(.)\1{2,}/.test(password)) score -= 1; // repeated chars
    if (/123|abc|qwe|password|admin/i.test(password)) score -= 1; // common patterns

    // Ensure score is between 0 and 5
    score = Math.max(0, Math.min(5, score));

    const strengthLevels = [
      { score: 0, label: '', color: 'bg-slate-200 dark:bg-slate-700', width: 'w-0' },
      { score: 1, label: 'Very Weak', color: 'bg-red-500', width: 'w-1/5' },
      { score: 2, label: 'Weak', color: 'bg-orange-500', width: 'w-2/5' },
      { score: 3, label: 'Fair', color: 'bg-yellow-500', width: 'w-3/5' },
      { score: 4, label: 'Good', color: 'bg-blue-500', width: 'w-4/5' },
      { score: 5, label: 'Strong', color: 'bg-green-500', width: 'w-full' },
    ];

    return strengthLevels[score];
  }, [password]);

  if (!password) return null;

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="flex items-center gap-2">
        <div className="flex-1 bg-slate-200 dark:bg-slate-700 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all duration-300 ${strength.color} ${strength.width}`}
          />
        </div>
        {strength.label && (
          <span className={`text-xs font-medium ${
            strength.score <= 2 ? 'text-red-600 dark:text-red-400' :
            strength.score <= 3 ? 'text-yellow-600 dark:text-yellow-400' :
            strength.score <= 4 ? 'text-blue-600 dark:text-blue-400' :
            'text-green-600 dark:text-green-400'
          }`}>
            {strength.label}
          </span>
        )}
      </div>
      {password && (
        <div className="text-xs text-slate-500 dark:text-slate-400 space-y-1">
          <p>Password requirements:</p>
          <ul className="list-disc list-inside space-y-0.5 ml-2">
            <li className={password.length >= 8 ? 'text-green-600 dark:text-green-400' : ''}>
              At least 8 characters
            </li>
            <li className={/[a-z]/.test(password) ? 'text-green-600 dark:text-green-400' : ''}>
              One lowercase letter
            </li>
            <li className={/[A-Z]/.test(password) ? 'text-green-600 dark:text-green-400' : ''}>
              One uppercase letter
            </li>
            <li className={/[0-9]/.test(password) ? 'text-green-600 dark:text-green-400' : ''}>
              One number
            </li>
            <li className={/[^A-Za-z0-9]/.test(password) ? 'text-green-600 dark:text-green-400' : ''}>
              One special character
            </li>
          </ul>
        </div>
      )}
    </div>
  );
};

export default PasswordStrengthIndicator;
