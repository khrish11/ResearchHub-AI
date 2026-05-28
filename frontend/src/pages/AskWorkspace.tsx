import React, { useEffect, useMemo, useState } from 'react';
import { Loader2, Search, Database, Sparkles, FileText } from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';
import { apiErrorMessage } from '../utils/apiError';

interface WorkspaceOption {
  id: number;
  name: string;
}

interface RAGSource {
  source_id: string;
  source_type: string;
  title?: string | null;
  mention_count: number;
  relevance_score: number;
}

interface RAGResponse {
  answer: string;
  confidence: number;
  grounding_score: number;
  retrieved_count: number;
  invalid_source_refs: number[];
  sources_used: RAGSource[];
}

const AskWorkspace: React.FC = () => {
  const [workspaces, setWorkspaces] = useState<WorkspaceOption[]>([]);
  const [workspaceId, setWorkspaceId] = useState<number | null>(null);
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState<RAGResponse | null>(null);
  const [indexedVectors, setIndexedVectors] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [indexing, setIndexing] = useState(false);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === workspaceId) || null,
    [workspaces, workspaceId],
  );

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await api.get<WorkspaceOption[]>('/workspaces/');
        if (!active) return;
        const rows = Array.isArray(response.data) ? response.data : [];
        setWorkspaces(rows);
        setWorkspaceId(rows[0]?.id ?? null);
      } catch (err: unknown) {
        if (!active) return;
        setError(apiErrorMessage(err, 'Failed to load workspaces.'));
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const loadStatus = async () => {
      if (!workspaceId) {
        setIndexedVectors(0);
        return;
      }
      try {
        const response = await api.get('/api/rag/status', { params: { workspace_id: workspaceId } });
        setIndexedVectors(Number(response.data?.indexed_vectors || 0));
      } catch {
        setIndexedVectors(0);
      }
    };
    void loadStatus();
  }, [workspaceId]);

  const runIndex = async () => {
    if (!workspaceId) return;
    setIndexing(true);
    setError(null);
    try {
      const response = await api.post('/api/rag/index/workspace', {
        workspace_id: workspaceId,
      });
      setIndexedVectors(Number(response.data?.indexed_vectors || 0));
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Workspace indexing failed.'));
    } finally {
      setIndexing(false);
    }
  };

  const runQuery = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!workspaceId || !query.trim()) return;
    setAsking(true);
    setError(null);
    try {
      const response = await api.post<RAGResponse>('/api/rag/query', {
        workspace_id: workspaceId,
        query: query.trim(),
        top_k: 6,
        strict_grounding: true,
      });
      setAnswer(response.data);
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Workspace query failed.'));
    } finally {
      setAsking(false);
    }
  };

  return (
    <Layout>
      <div className="space-y-5">
        <section className="studio-surface p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Workspace Intelligence</p>
          <h2 className="mt-2 text-2xl font-semibold text-slate-900">Ask Your Workspace</h2>
          <p className="mt-1 text-sm text-slate-600">
            Grounded answers over your indexed papers, summaries, checker outputs, and reports.
          </p>
        </section>

        {loading ? (
          <div className="studio-panel-quiet flex items-center gap-2 p-4 text-sm text-slate-600">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading workspace selector...
          </div>
        ) : (
          <section className="studio-surface p-4">
            <div className="grid gap-3 md:grid-cols-[minmax(220px,300px)_1fr_auto] md:items-end">
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Workspace
                </label>
                <select
                  aria-label="Workspace"
                  title="Workspace"
                  value={workspaceId ?? ''}
                  onChange={(event) => setWorkspaceId(Number(event.target.value))}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {workspaces.map((workspace) => (
                    <option key={workspace.id} value={workspace.id}>
                      {workspace.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-700">
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-indigo-600" />
                  Indexed vectors: <span className="font-semibold">{indexedVectors}</span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => void runIndex()}
                disabled={!workspaceId || indexing}
                className="hero-btn-secondary disabled:cursor-not-allowed disabled:opacity-55"
              >
                {indexing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Indexing...
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    Index Workspace
                  </>
                )}
              </button>
            </div>

            <form onSubmit={runQuery} className="mt-4 flex gap-2">
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Summarize my workspace trends and contradictions..."
                className="flex-1 rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <button
                type="submit"
                disabled={!workspaceId || !query.trim() || asking}
                className="hero-btn-primary disabled:cursor-not-allowed disabled:opacity-55"
              >
                {asking ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Asking...
                  </>
                ) : (
                  <>
                    <Search className="h-4 w-4" />
                    Ask
                  </>
                )}
              </button>
            </form>

            {error && (
              <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            )}
          </section>
        )}

        {answer && (
          <section className="studio-surface p-5">
            <h3 className="text-lg font-semibold text-slate-900">Answer</h3>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{answer.answer}</p>

            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-700">
                Confidence: <span className="font-semibold">{Math.round(answer.confidence * 100)}%</span>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-700">
                Grounding: <span className="font-semibold">{Math.round(answer.grounding_score * 100)}%</span>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-700">
                Retrieved chunks: <span className="font-semibold">{answer.retrieved_count}</span>
              </div>
            </div>

            <div className="mt-5">
              <h4 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Sources Used</h4>
              {answer.sources_used.length === 0 ? (
                <p className="mt-2 text-sm text-slate-600">No explicit source citations were returned.</p>
              ) : (
                <div className="mt-2 space-y-2">
                  {answer.sources_used.map((source) => (
                    <a
                      key={`${source.source_type}-${source.source_id}`}
                      href={selectedWorkspace ? `/workspace/${selectedWorkspace.id}` : '#'}
                      className="block rounded-xl border border-slate-200 bg-white px-3 py-2.5 hover:border-indigo-200"
                    >
                      <div className="flex items-center justify-between gap-3 text-sm">
                        <span className="font-semibold text-slate-800">
                          {source.title || `Source ${source.source_id}`}
                        </span>
                        <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-semibold text-indigo-700">
                          {Math.round(source.relevance_score * 100)}%
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        <FileText className="mr-1 inline h-3.5 w-3.5" />
                        {source.source_type} · id: {source.source_id} · mentions: {source.mention_count}
                      </p>
                    </a>
                  ))}
                </div>
              )}
            </div>
          </section>
        )}
      </div>
    </Layout>
  );
};

export default AskWorkspace;
