/**
 * Hypothesis Challenger
 * 
 * Interactive panel for challenging research hypotheses against literature.
 */

import React, { useState } from 'react';
import { ShieldAlert, AlertTriangle, Play } from 'lucide-react';
import type { HypothesisChallengeResponse } from '../../api/researchIntelligence';

interface HypothesisChallengerProps {
  challenge: HypothesisChallengeResponse | null;
  onChallengeHypothesis: (hypothesis: string) => void;
  isLoading: boolean;
}

export const HypothesisChallenger: React.FC<HypothesisChallengerProps> = ({
  challenge,
  onChallengeHypothesis,
  isLoading,
}) => {
  const [hypothesisInput, setHypothesisInput] = useState('');

  const getVulnerabilityColor = (vulnerability: number): string => {
    if (vulnerability >= 70) return 'text-rose-600 bg-rose-50 border-rose-200';
    if (vulnerability >= 40) return 'text-amber-600 bg-amber-50 border-amber-200';
    return 'text-emerald-600 bg-emerald-50 border-emerald-200';
  };

  const getVulnerabilityLabel = (vulnerability: number): string => {
    if (vulnerability >= 70) return 'High Vulnerability';
    if (vulnerability >= 40) return 'Medium Vulnerability';
    return 'Low Vulnerability';
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (hypothesisInput.trim()) {
      onChallengeHypothesis(hypothesisInput.trim());
    }
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-slate-900">Challenge Your Hypothesis</h2>
        <p className="mt-1 text-sm text-slate-500">
          Before investing months in an idea, stress-test it against the literature
        </p>
      </div>

      {/* Hypothesis Input */}
      <form onSubmit={handleSubmit} className="mb-6">
        <div className="flex gap-3">
          <input
            type="text"
            value={hypothesisInput}
            onChange={(e) => setHypothesisInput(e.target.value)}
            placeholder="Enter your research hypothesis..."
            className="flex-1 rounded-xl border border-slate-300 px-4 py-3 text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !hypothesisInput.trim()}
            className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50 transition"
          >
            {isLoading ? (
              <>
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Analyzing...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Challenge Hypothesis
              </>
            )}
          </button>
        </div>
      </form>

      {/* Results */}
      {challenge && (
        <div className="space-y-6">
          {/* Overall Vulnerability */}
          <div className={`rounded-xl border p-4 ${getVulnerabilityColor(challenge.overall_vulnerability)}`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <ShieldAlert className="h-6 w-6" />
                <div>
                  <p className="text-sm font-medium">Hypothesis Strength</p>
                  <p className="text-2xl font-bold">{challenge.overall_vulnerability}/100</p>
                </div>
              </div>
              <div className={`rounded-full border px-3 py-1 text-sm font-semibold`}>
                {getVulnerabilityLabel(challenge.overall_vulnerability)}
              </div>
            </div>
          </div>

          {/* Challenges List */}
          {challenge.challenges.length > 0 && (
            <div>
              <p className="text-sm font-semibold text-slate-900 mb-3">Identified Challenges</p>
              <div className="space-y-3">
                {challenge.challenges.map((challengeItem, index) => (
                  <div key={index} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm font-medium text-slate-900">{challengeItem.challenge_type}</p>
                      <p className={`text-sm font-bold ${getScoreColor(challengeItem.strength)}`}>
                        {challengeItem.strength}/100
                      </p>
                    </div>
                    <p className="text-sm text-slate-600 mb-2">{challengeItem.challenge_text}</p>
                    {challengeItem.counter_evidence.length > 0 && (
                      <div className="mt-2">
                        <p className="text-xs font-semibold text-slate-700 mb-1">Counter-Evidence:</p>
                        <ul className="space-y-1">
                          {challengeItem.counter_evidence.slice(0, 2).map((evidence: string, i: number) => (
                            <li key={i} className="text-xs text-slate-600">• {evidence}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Strongest Challenge */}
          {challenge.strongest_challenge && (
            <div className="rounded-xl border-2 border-rose-200 bg-rose-50 p-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="h-5 w-5 text-rose-600" />
                <p className="text-sm font-semibold text-rose-900">Strongest Counterargument</p>
              </div>
              <p className="text-base font-medium text-slate-900 mb-2">
                {challenge.strongest_challenge.challenge_text}
              </p>
              <p className="text-sm text-slate-600">{challenge.strongest_challenge.rationale}</p>
            </div>
          )}


          {challenge.summary && (
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-sm font-medium text-slate-900 mb-2">Summary</p>
              <p className="text-sm text-slate-600">{challenge.summary}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const getScoreColor = (value: number): string => {
  if (value >= 70) return 'text-rose-600';
  if (value >= 40) return 'text-amber-600';
  return 'text-emerald-600';
};
