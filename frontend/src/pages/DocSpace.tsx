import React, { useEffect, useState } from 'react';
import { FileText, NotebookText, Search, ExternalLink, Trash2, Loader2, AlertCircle, BookOpen } from 'lucide-react';
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
  description?: string;
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

  // Load workspaces
  useEffect(() => {
    api.get('/workspaces/')
      .then((res) => {
        setWorkspaces(res.data);
        if (res.data.length > 0) setSelectedWsId(res.data[0].id);
      })
      .catch(() => setError('Failed to load workspaces.'))
      .finally(() => setLoadingWs(false));
  }, []);

  // Load papers when workspace changes
  useEffect(() => {
    if (selectedWsId === null) return;
    setLoadingPapers(true);
    setSelectedPaper(null);
    api.get(`/workspaces/${selectedWsId}`)
      .then((res) => {
        setPapers(res.data.papers ?? []);
      })
      .catch(() => setError('Failed to load papers for this workspace.'))
      .finally(() => setLoadingPapers(false));
  }, [selectedWsId]);

  const filteredPapers = papers.filter((p) =>
    p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.authors.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const totalChars = papers.reduce((sum, p) => sum + (p.abstract?.length ?? 0), 0);

  return (
    <Layout>
      <div>
        <h1 className="text-3xl font-bold text-slate-900 mb-1">Doc Space</h1>
        <p className="text-slate-500 mb-6">
          All papers saved to your workspaces — view, search, and explore your research library.
        </p>

        {/* Stat cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-slate-200 p-5 flex items-center gap-4">
            <div className="p-3 bg-indigo-100 rounded-lg"><FileText className="h-6 w-6 text-indigo-600" /></div>
            <div>
              <p className="text-2xl font-bold text-slate-900">{papers.length}</p>
              <p className="text-sm text-slate-500">Source Papers</p>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-5 flex items-center gap-4">
            <div className="p-3 bg-purple-100 rounded-lg"><NotebookText className="h-6 w-6 text-purple-600" /></div>
            <div>
              <p className="text-2xl font-bold text-slate-900">{workspaces.length}</p>
              <p className="text-sm text-slate-500">Workspaces</p>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-5 flex items-center gap-4">
            <div className="p-3 bg-green-100 rounded-lg"><BookOpen className="h-6 w-6 text-green-600" /></div>
            <div>
              <p className="text-2xl font-bold text-slate-900">{(totalChars / 1000).toFixed(0)}k</p>
              <p className="text-sm text-slate-500">Characters Indexed</p>
            </div>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertCircle className="h-4 w-4 flex-shrink-0" /> {error}
          </div>
        )}

        <div className="flex gap-6">
          {/* Left: workspace selector + paper list */}
          <div className="w-72 flex-shrink-0">
            <div className="bg-white rounded-xl border border-slate-200 p-4 mb-3">
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Workspace</label>
              {loadingWs ? (
                <div className="flex items-center gap-2 text-slate-400 text-sm"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>
              ) : (
                <select
                  value={selectedWsId ?? ''}
                  onChange={(e) => setSelectedWsId(Number(e.target.value))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-600"
                >
                  {workspaces.map((w) => (
                    <option key={w.id} value={w.id}>{w.name}</option>
                  ))}
                </select>
              )}
            </div>

            {/* Search */}
            <div className="relative mb-3">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
              <input
                type="text"
                placeholder="Filter papers…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-600"
              />
            </div>

            {/* Paper list */}
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden max-h-[60vh] overflow-y-auto">
              {loadingPapers ? (
                <div className="flex items-center justify-center gap-2 py-8 text-slate-400 text-sm">
                  <Loader2 className="h-4 w-4 animate-spin" /> Loading papers…
                </div>
              ) : filteredPapers.length === 0 ? (
                <p className="text-center py-8 text-slate-400 text-sm">
                  {papers.length === 0 ? 'No papers in this workspace yet.' : 'No matches found.'}
                </p>
              ) : (
                filteredPapers.map((paper) => (
                  <button
                    key={paper.id}
                    onClick={() => setSelectedPaper(paper)}
                    className={`w-full text-left px-4 py-3 border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors ${selectedPaper?.id === paper.id ? 'bg-indigo-50' : ''}`}
                  >
                    <p className={`text-sm font-medium line-clamp-2 ${selectedPaper?.id === paper.id ? 'text-indigo-700' : 'text-slate-800'}`}>{paper.title}</p>
                    <p className="text-xs text-slate-400 mt-0.5 truncate">{paper.authors}</p>
                  </button>
                ))
              )}
            </div>
          </div>

          {/* Right: paper detail */}
          <div className="flex-1">
            {selectedPaper ? (
              <div className="bg-white rounded-xl border border-slate-200 p-6">
                <div className="flex items-start justify-between gap-4 mb-4">
                  <h2 className="text-xl font-bold text-slate-900 leading-tight">{selectedPaper.title}</h2>
                  {selectedPaper.url && (
                    <a
                      href={selectedPaper.url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex-shrink-0 flex items-center gap-1 text-indigo-600 hover:text-indigo-700 text-sm font-medium"
                    >
                      Open <ExternalLink className="h-4 w-4" />
                    </a>
                  )}
                </div>
                <p className="text-sm text-slate-500 mb-5 flex items-center gap-1">
                  <NotebookText className="h-4 w-4" /> {selectedPaper.authors}
                </p>
                <div className="bg-slate-50 rounded-lg p-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Abstract</h3>
                  <p className="text-sm text-slate-700 leading-relaxed">{selectedPaper.abstract}</p>
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-xl border-2 border-dashed border-slate-200 flex flex-col items-center justify-center h-80 text-slate-400">
                <FileText className="h-12 w-12 mb-3" />
                <p className="text-base font-medium">Select a paper to read its details</p>
                <p className="text-sm mt-1">Import papers via Search or Upload PDF</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default DocSpace;
