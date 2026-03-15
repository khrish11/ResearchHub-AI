import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api';
import { apiErrorMessage } from '../utils/apiError';
import { useUser } from '../hooks/useUser';

type RequestType =
  | 'access'
  | 'delete'
  | 'rectify'
  | 'portability'
  | 'restrict_processing'
  | 'object_processing'
  | 'withdraw_consent';
type Jurisdiction = 'gdpr' | 'ccpa' | 'other';

interface DataRequestItem {
  id: number;
  request_type: string;
  jurisdiction?: string;
  details?: string;
  status: string;
  submitted_at?: string;
}

const DataRights: React.FC = () => {
  const [requestType, setRequestType] = useState<RequestType>('access');
  const [jurisdiction, setJurisdiction] = useState<Jurisdiction>('other');
  const [details, setDetails] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [requests, setRequests] = useState<DataRequestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { user, loading: userLoading } = useUser();
  const isAuthenticated = Boolean(user);

  const loadMine = useCallback(async () => {
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }
    try {
      const response = await api.get<{ items: DataRequestItem[] }>('/compliance/data-rights-request/me');
      setRequests(response.data?.items || []);
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Could not load your data rights requests.'));
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    void loadMine();
  }, [loadMine]);

  const submitRequest = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!isAuthenticated) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.post('/compliance/data-rights-request', {
        request_type: requestType,
        jurisdiction: jurisdiction,
        details: details.trim(),
      });
      setDetails('');
      await loadMine();
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Unable to submit data rights request.'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-10">
      <div className="mx-auto max-w-3xl rounded-3xl border border-slate-200 bg-white p-6 sm:p-8 shadow-sm">
        <h1 className="text-3xl font-bold text-slate-900">Data Rights Portal</h1>
        <p className="mt-2 text-sm text-slate-500">
          Submit GDPR/CCPA requests and export your account data.
        </p>

        {!isAuthenticated ? (
          <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
            Sign in to submit and track requests.
            <Link to="/login" className="ml-2 font-semibold underline">
              Go to Login
            </Link>
          </div>
        ) : (
          <>
            <div className="mt-6 flex flex-wrap gap-2">
              <a
                href="#"
                onClick={async (e) => {
                  e.preventDefault();
                  try {
                    const response = await api.get('/compliance/export-my-data');
                    const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = url;
                    link.download = 'researchhub-my-data-export.json';
                    document.body.appendChild(link);
                    link.click();
                    link.remove();
                    URL.revokeObjectURL(url);
                  } catch (err: unknown) {
                    setError(apiErrorMessage(err, 'Data export failed.'));
                  }
                }}
                className="inline-flex items-center rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Export My Data
              </a>
            </div>

            <form onSubmit={submitRequest} className="mt-6 space-y-4 rounded-2xl border border-slate-200 p-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="text-sm font-medium text-slate-700">
                  Request Type
                  <select
                    value={requestType}
                    onChange={(e) => setRequestType(e.target.value as RequestType)}
                    className="mt-1 h-10 w-full rounded-lg border border-slate-300 px-3 text-sm"
                  >
                    <option value="access">Access</option>
                    <option value="delete">Delete</option>
                    <option value="rectify">Rectify</option>
                    <option value="portability">Portability</option>
                    <option value="restrict_processing">Restrict Processing</option>
                    <option value="object_processing">Object Processing</option>
                    <option value="withdraw_consent">Withdraw Consent</option>
                  </select>
                </label>

                <label className="text-sm font-medium text-slate-700">
                  Jurisdiction
                  <select
                    value={jurisdiction}
                    onChange={(e) => setJurisdiction(e.target.value as Jurisdiction)}
                    className="mt-1 h-10 w-full rounded-lg border border-slate-300 px-3 text-sm"
                  >
                    <option value="gdpr">GDPR</option>
                    <option value="ccpa">CCPA</option>
                    <option value="other">Other</option>
                  </select>
                </label>
              </div>

              <label className="block text-sm font-medium text-slate-700">
                Details
                <textarea
                  value={details}
                  onChange={(e) => setDetails(e.target.value)}
                  className="mt-1 min-h-[110px] w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  placeholder="Describe your request context and any legal timelines."
                />
              </label>

              <button
                type="submit"
                disabled={submitting}
                className="rounded-xl bg-slate-800 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-900 disabled:opacity-60"
              >
                {submitting ? 'Submitting...' : 'Submit Request'}
              </button>
            </form>

            <div className="mt-6">
              <h2 className="text-lg font-semibold text-slate-900">My Requests</h2>
              {(loading || userLoading) && <p className="mt-2 text-sm text-slate-500">Loading requests...</p>}
              {!loading && requests.length === 0 && (
                <p className="mt-2 text-sm text-slate-500">No requests submitted yet.</p>
              )}
              <div className="mt-3 space-y-2">
                {requests.map((item) => (
                  <article key={item.id} className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold text-slate-800">
                        {item.request_type.replace(/_/g, ' ')}
                      </span>
                      <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs text-slate-700">
                        {item.status}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {item.jurisdiction?.toUpperCase() || 'OTHER'} | {item.submitted_at || 'submitted'}
                    </p>
                    {item.details && <p className="mt-2 text-slate-700">{item.details}</p>}
                  </article>
                ))}
              </div>
            </div>
          </>
        )}

        {error && <p className="mt-4 text-sm text-rose-700">{error}</p>}
      </div>
    </div>
  );
};

export default DataRights;
