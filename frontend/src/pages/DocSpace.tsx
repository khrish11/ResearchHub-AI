import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  BookOpen,
  ExternalLink,
  FileText,
  Loader2,
  NotebookText,
  Search,
  Sparkles,
} from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';

interface Paper {
  id: number;
  title: string;
  authors: string;
  abstract: string;
  url?: string;
}

interface Workspace {
  id: number;
  name: string;
}

const DocSpace: React.FC = () => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWsId, setSelectedWsId] = useState<number | null>(null);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [loadingWs, setLoadingWs] = useState(true);
  const [loadingPapers, setLoadingPapers] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPaper, setSelectedPaper] = useState<Paper | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get('/workspaces/')
      .then((res) => {
        const wsList: Workspace[] = res.data;
        setWorkspaces(wsList);
        if (wsList.length > 0) {
          setSelectedWsId(wsList[0].id);
        }
      })
      .catch(() => setError('Failed to load workspaces.'))
      .finally(() => setLoadingWs(false));
  }, []);

  useEffect(() => {
    if (selectedWsId === null) {
      return;
    }
    setLoadingPapers(true);
    setSelectedPaper(null);
    api
      .get(`/workspaces/${selectedWsId}`)
      .then((res) => {
        const list: Paper[] = res.data.papers ?? [];
        setPapers(list);
      })
      .catch(() => setError('Failed to load papers for this workspace.'))
      .finally(() => setLoadingPapers(false));
  }, [selectedWsId]);

  const filteredPapers = useMemo(
    () =>
      papers.filter(
        (paper) =>
          paper.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          paper.authors.toLowerCase().includes(searchQuery.toLowerCase())
      ),
    [papers, searchQuery]
  );

  const totalChars = useMemo(
    () => papers.reduce((sum, paper) => sum + (paper.abstract?.length ?? 0), 0),
    [papers]
  );

  return (
    <Layout>
      <div className="page-enter">
        <section className="studio-hero mb-5">
          <span className="studio-kicker">
            <Sparkles className="h-3.5 w-3.5" />
            Knowledge vault
          </span>
          <h2>DocSpace</h2>
          <p>
            Central view for workspace papers, searchable metadata, and quick abstract access to speed up
            literature review cycles.
          </p>
          <div className="studio-chip-row">
            <span className="studio-chip">{workspaces.length} workspaces</span>
            <span className="studio-chip">{papers.length} papers in scope</span>
            <span className="studio-chip">{Math.max(0, Math.round(totalChars / 1000))}k chars indexed</span>
          </div>
          <div className="studio-orb" aria-hidden="true" />
        </section>

        <section className="studio-stat-grid mb-4">
          <article className="studio-stat-card">
            <div className="studio-icon-chip bg-indigo-100 text-indigo-600">
              <FileText className="h-4.5 w-4.5" />
            </div>
            <p className="studio-stat-label">Source papers</p>
            <p className="studio-stat-value">{papers.length}</p>
          </article>
          <article className="studio-stat-card">
            <div className="studio-icon-chip bg-purple-100 text-purple-600">
              <NotebookText className="h-4.5 w-4.5" />
            </div>
            <p className="studio-stat-label">Workspaces</p>
            <p className="studio-stat-value">{workspaces.length}</p>
          </article>
          <article className="studio-stat-card">
            <div className="studio-icon-chip bg-emerald-100 text-emerald-600">
              <BookOpen className="h-4.5 w-4.5" />
            </div>
            <p className="studio-stat-label">Indexed chars</p>
            <p className="studio-stat-value">{Math.max(0, Math.round(totalChars / 1000))}k</p>
          </article>
          <article className="studio-stat-card">
            <div className="studio-icon-chip bg-cyan-100 text-cyan-700">
              <Search className="h-4.5 w-4.5" />
            </div>
            <p className="studio-stat-label">Matches</p>
            <p className="studio-stat-value">{filteredPapers.length}</p>
          </article>
        </section>

        {error && (
          <div className="studio-panel px-4 py-3 mb-4 text-sm text-red-700 border-red-200 bg-red-50 flex items-center gap-2">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        )}

        <section className="docspace-shell">
          <aside className="studio-surface p-3">
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
              Workspace
            </label>
            {loadingWs ? (
              <div className="flex items-center gap-2 text-sm text-slate-500 py-3">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading...
              </div>
            ) : (
              <select
                value={selectedWsId ?? ''}
                onChange={(e) => setSelectedWsId(Number(e.target.value))}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {workspaces.map((workspace) => (
                  <option key={workspace.id} value={workspace.id}>
                    {workspace.name}
                  </option>
                ))}
              </select>
            )}

            <div className="relative mt-3">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
              <input
                type="text"
                placeholder="Filter papers..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-xl border border-slate-300 py-2 pl-9 pr-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="mt-3 max-h-[60vh] overflow-y-auto space-y-2 pr-1">
              {loadingPapers ? (
                <div className="text-sm text-slate-500 flex items-center gap-2 py-4">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading papers...
                </div>
              ) : filteredPapers.length === 0 ? (
                <p className="text-sm text-slate-500 py-4 text-center">
                  {papers.length === 0 ? 'No papers in this workspace yet.' : 'No matching papers.'}
                </p>
              ) : (
                filteredPapers.map((paper) => (
                  <button
                    key={paper.id}
                    onClick={() => setSelectedPaper(paper)}
                    className={`paper-list-item ${selectedPaper?.id === paper.id ? 'active' : ''}`}
                  >
                    <p className="text-sm font-semibold text-slate-800 line-clamp-2">{paper.title}</p>
                    <p className="text-xs text-slate-500 truncate mt-0.5">{paper.authors}</p>
                  </button>
                ))
              )}
            </div>
          </aside>

          <div>
            {selectedPaper ? (
              <section className="studio-surface p-4">
                <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                  <h3 className="text-xl font-semibold text-slate-900 leading-tight">
                    {selectedPaper.title}
                  </h3>
                  {selectedPaper.url && (
                    <a
                      href={selectedPaper.url}
                      target="_blank"
                      rel="noreferrer"
                      className="hero-btn-secondary"
                    >
                      Open paper
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  )}
                </div>
                <p className="text-sm text-slate-500 mb-3 inline-flex items-center gap-1.5">
                  <NotebookText className="h-4 w-4" />
                  {selectedPaper.authors}
                </p>
                <div className="studio-panel-quiet p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                    Abstract
                  </p>
                  <p className="text-sm text-slate-700 leading-relaxed">{selectedPaper.abstract}</p>
                </div>
              </section>
            ) : (
              <section className="studio-panel-quiet p-10 text-center">
                <FileText className="h-10 w-10 text-slate-400 mx-auto mb-2" />
                <p className="text-sm font-semibold text-slate-700">Select a paper to preview details</p>
                <p className="text-sm text-slate-500 mt-1">
                  Import papers from Search or Upload PDF to expand this library.
                </p>
              </section>
            )}
          </div>
        </section>
      </div>
    </Layout>
  );
};

export default DocSpace;
