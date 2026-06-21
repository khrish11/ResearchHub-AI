import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  ExternalLink,
  FileText,
  Loader2,
  NotebookText,
  Search,
  Sparkles,
} from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';
import { useToast } from '../contexts/ToastContext';
import { fetchPaperCitation } from '../utils/researchArtifacts';

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

interface DocspaceDocument {
  workspace_id: number;
  title: string;
  content: string;
  version: number;
  updated_at?: string;
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
  const [docTitle, setDocTitle] = useState('Research Notes');
  const [docContent, setDocContent] = useState('');
  const [docVersion, setDocVersion] = useState(1);
  const [docLoading, setDocLoading] = useState(false);
  const [docSaving, setDocSaving] = useState(false);
  const [docDirty, setDocDirty] = useState(false);
  const [docUpdatedAt, setDocUpdatedAt] = useState<string | null>(null);
  const [docError, setDocError] = useState<string | null>(null);
  const [lastSavedSnapshot, setLastSavedSnapshot] = useState('');
  const [citationInserting, setCitationInserting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { success: toastSuccess, error: toastError } = useToast();

  const buildSnapshot = useCallback((title: string, content: string) => `${title}\n---\n${content}`, []);

  const applyDocumentState = useCallback(
    (doc: DocspaceDocument) => {
      const nextTitle = String(doc.title || 'Research Notes');
      const nextContent = String(doc.content || '');
      const snapshot = buildSnapshot(nextTitle, nextContent);
      setDocTitle(nextTitle);
      setDocContent(nextContent);
      setDocVersion(Number(doc.version || 1));
      setDocUpdatedAt(doc.updated_at || null);
      setLastSavedSnapshot(snapshot);
      setDocDirty(false);
    },
    [buildSnapshot]
  );

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

  const loadDocspaceDocument = useCallback(
    async (workspaceId: number) => {
      setDocLoading(true);
      setDocError(null);
      try {
        const response = await api.get<DocspaceDocument>(`/workspaces/${workspaceId}/docspace`);
        applyDocumentState(response.data);
      } catch {
        setDocError('Failed to load editable doc for this workspace.');
      } finally {
        setDocLoading(false);
      }
    },
    [applyDocumentState]
  );

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
    void loadDocspaceDocument(selectedWsId);
  }, [selectedWsId, loadDocspaceDocument]);

  const saveDocspaceDocument = useCallback(
    async (force = false) => {
      if (selectedWsId === null || docLoading) {
        return;
      }
      const payloadTitle = String(docTitle || '').trim() || 'Research Notes';
      const payloadContent = docContent || '';
      const snapshot = buildSnapshot(payloadTitle, payloadContent);
      if (!force && snapshot === lastSavedSnapshot) {
        return;
      }

      setDocSaving(true);
      setDocError(null);
      try {
        const response = await api.put<DocspaceDocument>(`/workspaces/${selectedWsId}/docspace`, {
          title: payloadTitle,
          content: payloadContent,
        });
        applyDocumentState(response.data);
      } catch {
        setDocError('Auto-save failed. Your local draft is still in the editor.');
      } finally {
        setDocSaving(false);
      }
    },
    [applyDocumentState, buildSnapshot, docContent, docLoading, docTitle, lastSavedSnapshot, selectedWsId]
  );

  useEffect(() => {
    if (selectedWsId === null || docLoading) {
      return;
    }
    const payloadTitle = String(docTitle || '').trim() || 'Research Notes';
    const snapshot = buildSnapshot(payloadTitle, docContent || '');
    if (snapshot === lastSavedSnapshot) {
      setDocDirty(false);
      return;
    }
    setDocDirty(true);
    const timer = window.setTimeout(() => {
      void saveDocspaceDocument(false);
    }, 900);
    return () => window.clearTimeout(timer);
  }, [buildSnapshot, docContent, docLoading, docTitle, lastSavedSnapshot, saveDocspaceDocument, selectedWsId]);

  useEffect(() => {
    if (selectedWsId === null) {
      return;
    }
    const intervalId = window.setInterval(() => {
      if (docDirty || docSaving) {
        return;
      }
      void api
        .get<DocspaceDocument>(`/workspaces/${selectedWsId}/docspace`)
        .then((response) => {
          const remoteVersion = Number(response.data?.version || 1);
          if (remoteVersion > docVersion) {
            applyDocumentState(response.data);
          }
        })
        .catch(() => undefined);
    }, 12000);
    return () => window.clearInterval(intervalId);
  }, [applyDocumentState, docDirty, docSaving, docVersion, selectedWsId]);

  const insertSelectedPaperReference = useCallback(() => {
    if (!selectedPaper) {
      return;
    }
    const link = selectedPaper.url ? ` (${selectedPaper.url})` : '';
    const citationLine = `- ${selectedPaper.title}${link}\n`;
    setDocContent((prev) => `${prev}${prev.endsWith('\n') || prev.length === 0 ? '' : '\n'}${citationLine}`);
  }, [selectedPaper]);

  const insertSelectedAbstract = useCallback(() => {
    if (!selectedPaper) {
      return;
    }
    const abstractBlock =
      `\n## ${selectedPaper.title}\n` +
      `${selectedPaper.authors}\n\n` +
      `${selectedPaper.abstract || 'No abstract available.'}\n`;
    setDocContent((prev) => `${prev}${prev.endsWith('\n') || prev.length === 0 ? '' : '\n'}${abstractBlock}`);
  }, [selectedPaper]);

  const handleInsertCitation = useCallback(async () => {
    if (!selectedPaper) {
      toastError('Select a paper first.');
      return;
    }

    setCitationInserting(true);
    try {
      const response = await fetchPaperCitation(selectedPaper.id, 'apa');
      const citationText = String(response.citation || '').trim();
      if (!citationText) {
        throw new Error('Citation service returned an empty result.');
      }

      setDocContent((prev) => {
        const textarea = textareaRef.current;
        const currentValue = prev;
        const start = textarea?.selectionStart ?? currentValue.length;
        const end = textarea?.selectionEnd ?? currentValue.length;
        const before = currentValue.slice(0, start);
        const after = currentValue.slice(end);
        const prefix = before.length > 0 && !before.endsWith('\n') ? '\n' : '';
        const suffix = after.length > 0 && !after.startsWith('\n') ? '\n' : '';
        return `${before}${prefix}${citationText}${suffix}${after}`;
      });

      window.setTimeout(() => textareaRef.current?.focus(), 0);
      toastSuccess('Citation inserted.');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to insert citation.';
      toastError(message);
    } finally {
      setCitationInserting(false);
    }
  }, [selectedPaper, toastError, toastSuccess]);

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
            <span className="studio-chip">{docSaving ? 'Saving notes...' : docDirty ? 'Draft unsaved' : 'Notes synced'}</span>
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
        {docError && (
          <div className="studio-panel px-4 py-3 mb-4 text-sm text-amber-700 border-amber-200 bg-amber-50 flex items-center gap-2">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {docError}
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
                aria-label="Workspace"
                title="Workspace"
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

          <div className="space-y-4">
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

            <section className="studio-surface p-4">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                <h3 className="text-base font-semibold text-slate-900 inline-flex items-center gap-2">
                  <NotebookText className="h-4.5 w-4.5 text-indigo-600" />
                  Live Workspace Notes
                </h3>
                <div className="flex items-center gap-2 text-xs">
                  {docSaving ? (
                    <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-slate-600">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" /> Saving...
                    </span>
                  ) : docDirty ? (
                    <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-amber-700">
                      Unsaved changes
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-emerald-700">
                      <CheckCircle2 className="h-3.5 w-3.5" /> Synced
                    </span>
                  )}
                  {docUpdatedAt && (
                    <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-slate-500">
                      {new Date(docUpdatedAt).toLocaleTimeString()}
                    </span>
                  )}
                </div>
              </div>

              {docLoading ? (
                <div className="flex items-center gap-2 text-sm text-slate-500 py-4">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading editable document...
                </div>
              ) : (
                <>
                  <input
                    type="text"
                    value={docTitle}
                    onChange={(e) => setDocTitle(e.target.value)}
                    placeholder="Document title"
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  <textarea
                    ref={textareaRef}
                    value={docContent}
                    onChange={(e) => setDocContent(e.target.value)}
                    placeholder="Write notes, draft sections, and references here. Changes auto-save."
                    className="w-full mt-3 min-h-[260px] rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => void saveDocspaceDocument(true)}
                      disabled={docSaving}
                      className="hero-btn-primary disabled:opacity-60"
                    >
                      {docSaving ? 'Saving...' : 'Save now'}
                    </button>
                    <button
                      type="button"
                      onClick={insertSelectedPaperReference}
                      disabled={!selectedPaper}
                      className="hero-btn-secondary disabled:opacity-50"
                    >
                      Insert paper reference
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleInsertCitation()}
                      disabled={!selectedPaper || citationInserting}
                      className="hero-btn-secondary disabled:opacity-50"
                    >
                      {citationInserting ? 'Inserting...' : 'Insert Citation'}
                    </button>
                    <button
                      type="button"
                      onClick={insertSelectedAbstract}
                      disabled={!selectedPaper}
                      className="hero-btn-secondary disabled:opacity-50"
                    >
                      Insert selected abstract
                    </button>
                  </div>
                  <p className="text-xs text-slate-500 mt-2">
                    Version {docVersion}. Auto-save runs every ~1 second while typing.
                  </p>
                </>
              )}
            </section>
          </div>
        </section>
      </div>
    </Layout>
  );
};

export default DocSpace;
