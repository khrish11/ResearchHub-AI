import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  BrainCircuit,
  Download,
  ExternalLink,
  FileText,
  Loader2,
  MessageSquare,
  Rocket,
  Search,
  Sparkles,
  Workflow,
} from 'lucide-react';
import Layout from '../components/Layout';
import DataExportImport from '../components/DataExportImport';
import api from '../api';
import { apiErrorMessage } from '../utils/apiError';
import { openFileUrl } from '../utils/openFile';

interface Paper {
  id: number;
  title: string;
  authors: string;
  abstract: string;
  url?: string;
  doi?: string;
  bibcode?: string;
  source?: string;
  pdf_url?: string;
  institutional_url?: string;
  access_type?: string;
  full_text_available?: boolean;
}

interface ChatItem {
  id: number;
  message: string;
  response: string;
}

interface WorkspaceDetail {
  id: number;
  name: string;
  description?: string;
  papers: Paper[];
  chats: ChatItem[];
}

interface FaultResult {
  fault_count: number;
  risk_score?: number;
  quality_score?: number;
  quality_tier?: string;
  severity_breakdown?: {
    high: number;
    medium: number;
    low: number;
  };
  verification_checklist?: string[];
  faults: Array<{
    severity: string;
    fault_type: string;
    evidence: string;
    recommendation: string;
  }>;
  analysis: string;
}

type WorkspaceTab = 'papers' | 'chat' | 'review' | 'ops';

const Workspace: React.FC = () => {
  const { id } = useParams();
  const [workspace, setWorkspace] = useState<WorkspaceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [chatInput, setChatInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('papers');
  const [reportTopic, setReportTopic] = useState('');
  const [reportGenerating, setReportGenerating] = useState<'pdf' | 'docx' | null>(null);
  const [chatPaperIds, setChatPaperIds] = useState<number[]>([]);
  const [faultPaperId, setFaultPaperId] = useState<number | null>(null);
  const [selectedPaperId, setSelectedPaperId] = useState<number | null>(null);
  const [paperQuery, setPaperQuery] = useState('');
  const [faultLoading, setFaultLoading] = useState(false);
  const [faultResult, setFaultResult] = useState<FaultResult | null>(null);
  const [fullTextOnlyPapers, setFullTextOnlyPapers] = useState(false);
  const [resolvingWorkspaceAccess, setResolvingWorkspaceAccess] = useState(false);
  const [institutionalRaw, setInstitutionalRaw] = useState('');
  const [institutionalImporting, setInstitutionalImporting] = useState(false);

  const loadWorkspace = useCallback(async () => {
    if (!id) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [workspaceRes, sessionRes] = await Promise.all([
        api.get(`/workspaces/${id}`),
        api.get('/workspaces/session-state').catch(() => ({ data: null })),
      ]);
      const data = workspaceRes.data;
      setWorkspace(data);
      setReportTopic(data?.name ? `${data.name} literature synthesis` : '');
      const paperIds = (data?.papers || []).map((paper: Paper) => paper.id);

      const extra = sessionRes?.data?.extra && typeof sessionRes.data.extra === 'object' ? sessionRes.data.extra : {};
      const restoredIds = Array.isArray(extra.selected_chat_paper_ids)
        ? extra.selected_chat_paper_ids.map((value: unknown) => Number(value)).filter((value: number) => paperIds.includes(value))
        : [];
      setChatPaperIds(restoredIds.length > 0 ? restoredIds : paperIds);

      const restoredFault = Number(extra.fault_paper_id || 0);
      setFaultPaperId(paperIds.includes(restoredFault) ? restoredFault : paperIds[0] ?? null);
      const restoredSelectedPaper = Number(extra.selected_paper_id || 0);
      setSelectedPaperId(paperIds.includes(restoredSelectedPaper) ? restoredSelectedPaper : paperIds[0] ?? null);

      const restoredTab = String(extra.active_tab || '');
      if (restoredTab === 'papers' || restoredTab === 'chat' || restoredTab === 'review' || restoredTab === 'ops') {
        setActiveTab(restoredTab);
      }
    } catch {
      setError('Failed to load workspace.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  useEffect(() => {
    if (!workspace) return;
    const timer = window.setTimeout(() => {
      void api
        .put('/workspaces/session-state', {
          page_path: `/workspace/${workspace.id}`,
          workspace_id: workspace.id,
          last_query: chatInput.slice(0, 300),
          extra: {
            active_tab: activeTab,
            selected_chat_paper_ids: chatPaperIds,
            fault_paper_id: faultPaperId,
            selected_paper_id: selectedPaperId,
          },
        })
        .catch(() => undefined);
    }, 700);
    return () => window.clearTimeout(timer);
  }, [activeTab, chatInput, chatPaperIds, faultPaperId, selectedPaperId, workspace]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!workspace || !chatInput.trim()) {
      return;
    }
    setSending(true);
    setError(null);
    try {
      const res = await api.post('/chat/', {
        message: chatInput,
        workspace_id: workspace.id,
        selected_paper_ids: chatPaperIds.length > 0 ? chatPaperIds : undefined,
      });
      const papersUsed = Number(res.data?.papers_used || 0);
      const memoryUsed = Number(res.data?.recent_chat_turns_used || 0);
      const contextMeta =
        papersUsed > 0 ? `\n\n[Context: ${papersUsed} paper${papersUsed === 1 ? '' : 's'}${memoryUsed > 0 ? `, ${memoryUsed} recent chat turn${memoryUsed === 1 ? '' : 's'}` : ''}]` : '';
      const newItem: ChatItem = {
        id: Date.now(),
        message: chatInput,
        response: `${String(res.data.response || '')}${contextMeta}`.trim(),
      };
      setWorkspace({
        ...workspace,
        chats: [...workspace.chats, newItem],
      });
      setChatInput('');
    } catch {
      setError('Failed to send message. Check that GROQ_API_KEY is configured.');
    } finally {
      setSending(false);
    }
  };

  const toggleChatPaper = (paperId: number) => {
    setChatPaperIds((prev) =>
      prev.includes(paperId) ? prev.filter((idValue) => idValue !== paperId) : [...prev, paperId]
    );
  };

  const runFaultDetection = async () => {
    if (!workspace || !faultPaperId) return;
    setFaultLoading(true);
    setFaultResult(null);
    setError(null);
    try {
      const response = await api.post<FaultResult>('/research/fault-detection', {
        workspace_id: workspace.id,
        paper_id: faultPaperId,
      });
      setFaultResult(response.data);
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Failed to analyze paper faults.'));
    } finally {
      setFaultLoading(false);
    }
  };

  const handleExport = async (format: 'bibtex' | 'csv') => {
    if (!workspace) {
      return;
    }
    setError(null);
    try {
      const res = await api.get(`/workspaces/${workspace.id}/export?format=${format}`, {
        responseType: 'blob',
      });
      const blob = new Blob([res.data], {
        type: format === 'csv' ? 'text/csv' : 'application/x-bibtex',
      });
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${workspace.name.replace(/\s+/g, '_')}.${format === 'csv' ? 'csv' : 'bib'}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setError('Failed to export workspace.');
    }
  };

  const handleResearchReportExport = async (format: 'pdf' | 'docx') => {
    if (!workspace) {
      return;
    }
    if (workspace.papers.length === 0) {
      setError('Mindmap export requires at least one paper in this workspace.');
      return;
    }
    setError(null);
    setReportGenerating(format);
    try {
      const res = await api.post(
        `/workspaces/${workspace.id}/research-report?format=${format}`,
        {
          topic: reportTopic.trim() || workspace.name,
        },
        { responseType: 'blob' }
      );

      const blob = new Blob([res.data], {
        type:
          format === 'pdf'
            ? 'application/pdf'
            : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      const baseName = (reportTopic || workspace.name || 'research-report').replace(/\s+/g, '_');
      anchor.href = url;
      anchor.download = `${baseName}_mindmap.${format}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      setError(
        apiErrorMessage(
          err,
          'Failed to generate research report. Ensure papers exist and AI service is configured.'
        )
      );
    } finally {
      setReportGenerating(null);
    }
  };

  const stats = useMemo(() => {
    if (!workspace) {
      return [];
    }
    const abstractChars = workspace.papers.reduce(
      (sum, paper) => sum + (paper.abstract?.length || 0),
      0
    );
    return [
      {
        label: 'Papers',
        value: workspace.papers.length.toString(),
        icon: FileText,
        bg: 'rgba(79, 70, 229, 0.12)',
        color: '#4f46e5',
      },
      {
        label: 'Chat turns',
        value: workspace.chats.length.toString(),
        icon: MessageSquare,
        bg: 'rgba(14, 165, 233, 0.12)',
        color: '#0284c7',
      },
      {
        label: 'Indexed chars',
        value: `${Math.max(1, Math.round(abstractChars / 1000))}k`,
        icon: Workflow,
        bg: 'rgba(16, 185, 129, 0.12)',
        color: '#059669',
      },
      {
        label: 'AI state',
        value: 'Ready',
        icon: BrainCircuit,
        bg: 'rgba(236, 72, 153, 0.12)',
        color: '#db2777',
      },
    ];
  }, [workspace]);

  const papersForDisplay = useMemo(() => {
    if (!workspace) return [];
    let papers = workspace.papers;
    if (paperQuery.trim()) {
      const needle = paperQuery.trim().toLowerCase();
      papers = papers.filter((paper) =>
        [paper.title, paper.authors, paper.abstract, paper.source, paper.doi]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
          .includes(needle)
      );
    }
    if (!fullTextOnlyPapers) return papers;
    return papers.filter((paper) => {
      const fullTextUrl = String(paper.pdf_url || paper.institutional_url || (String(paper.url || '').toLowerCase().endsWith('.pdf') ? paper.url : '') || '').trim();
      return Boolean(paper.full_text_available) || Boolean(fullTextUrl);
    });
  }, [fullTextOnlyPapers, paperQuery, workspace]);

  const selectedPaper = useMemo(
    () => papersForDisplay.find((paper) => paper.id === selectedPaperId) || papersForDisplay[0] || null,
    [papersForDisplay, selectedPaperId],
  );

  const fullTextReadyCount = useMemo(
    () =>
      workspace?.papers.filter((paper) => {
        const fullTextUrl = String(
          paper.pdf_url ||
            paper.institutional_url ||
            (String(paper.url || '').toLowerCase().endsWith('.pdf') ? paper.url : '') ||
            ''
        ).trim();
        return Boolean(paper.full_text_available) || Boolean(fullTextUrl);
      }).length || 0,
    [workspace],
  );

  useEffect(() => {
    if (!papersForDisplay.length) {
      setSelectedPaperId(null);
      return;
    }
    if (!papersForDisplay.some((paper) => paper.id === selectedPaperId)) {
      setSelectedPaperId(papersForDisplay[0].id);
    }
  }, [papersForDisplay, selectedPaperId]);

  const resolveWorkspacePaperAccess = async () => {
    if (!workspace) return;
    setResolvingWorkspaceAccess(true);
    setError(null);
    try {
      await api.post('/papers/resolve-workspace-access', {
        workspace_id: workspace.id,
        refresh_all: false,
        max_unpaywall_lookups: 20,
      });
      await loadWorkspace();
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Failed to resolve workspace full-text access.'));
    } finally {
      setResolvingWorkspaceAccess(false);
    }
  };

  const importInstitutionalPapers = async () => {
    if (!workspace) return;
    if (!institutionalRaw.trim()) {
      setError('Paste institutional entries before importing.');
      return;
    }
    setInstitutionalImporting(true);
    setError(null);
    try {
      await api.post('/papers/import-institutional', {
        workspace_id: workspace.id,
        source_name: 'institutional_portal',
        raw_text: institutionalRaw,
      });
      setInstitutionalRaw('');
      await loadWorkspace();
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Failed to import institutional papers.'));
    } finally {
      setInstitutionalImporting(false);
    }
  };

  const handleOpenFile = async (url: string, fallbackFilename: string) => {
    try {
      await openFileUrl(url, fallbackFilename);
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Failed to open file.'));
    }
  };

  return (
    <Layout>
      <div className="page-enter">
        {loading && (
          <div className="flex items-center gap-2 text-slate-500 py-12">
            <Loader2 className="h-5 w-5 animate-spin" />
            Loading workspace...
          </div>
        )}

        {!loading && error && (
          <div className="studio-panel px-4 py-3 text-sm text-red-700 border-red-200 bg-red-50 mb-4">
            {error}
          </div>
        )}

        {workspace && (
          <>
            <section className="studio-hero mb-5">
              <span className="studio-kicker">
                <Sparkles className="h-3.5 w-3.5" />
                Workspace core
              </span>
              <h2>{workspace.name}</h2>
              <p>
                {workspace.description ||
                  'Focused environment for paper organization, AI chat, and synthesis output.'}
              </p>
              <div className="studio-chip-row">
                <span className="studio-chip">
                  <FileText className="h-3.5 w-3.5" />
                  {workspace.papers.length} papers
                </span>
                <span className="studio-chip">
                  <MessageSquare className="h-3.5 w-3.5" />
                  {workspace.chats.length} chats
                </span>
                <span className="studio-chip">
                  <Rocket className="h-3.5 w-3.5" />
                  Review workflow ready
                </span>
              </div>
              <div className="studio-orb" aria-hidden="true" />
            </section>

            <div className="flex flex-wrap items-center gap-2.5 mb-4">
              <Link to="/dashboard" className="hero-btn-secondary">
                <ArrowLeft className="h-4 w-4" />
                Back to dashboard
              </Link>
              <button onClick={() => handleExport('bibtex')} className="hero-btn-primary">
                <Download className="h-4 w-4" />
                Export .bib
              </button>
              <button onClick={() => handleExport('csv')} className="hero-btn-primary">
                <Download className="h-4 w-4" />
                Export .csv
              </button>
              <button
                type="button"
                onClick={() => {
                  void resolveWorkspacePaperAccess();
                }}
                disabled={resolvingWorkspaceAccess || workspace.papers.length === 0}
                className="hero-btn-secondary disabled:opacity-55 disabled:cursor-not-allowed"
              >
                {resolvingWorkspaceAccess ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Resolving access...
                  </>
                ) : (
                  <>
                    <Workflow className="h-4 w-4" />
                    Resolve Full-Text Access
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={() => {
                  setActiveTab('review');
                }}
                className="hero-btn-secondary"
              >
                <Sparkles className="h-4 w-4" />
                Mindmap tab
              </button>
              <button
                type="button"
                onClick={() => {
                  void handleResearchReportExport('pdf');
                }}
                disabled={reportGenerating !== null || workspace.papers.length === 0}
                className="hero-btn-primary disabled:opacity-55 disabled:cursor-not-allowed"
              >
                {reportGenerating === 'pdf' ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    Mindmap PDF
                  </>
                )}
              </button>
            </div>

            <section className="studio-stat-grid mb-4">
              {stats.map((stat) => {
                const Icon = stat.icon;
                return (
                  <article key={stat.label} className="studio-stat-card">
                    <div className="studio-stat-top">
                      <div
                        className="studio-icon-chip"
                        style={{ background: stat.bg, color: stat.color }}
                      >
                        <Icon className="h-4.5 w-4.5" />
                      </div>
                    </div>
                    <p className="studio-stat-label">{stat.label}</p>
                    <p className="studio-stat-value">{stat.value}</p>
                  </article>
                );
              })}
            </section>

            <section className="mb-4 grid grid-cols-1 gap-4 xl:grid-cols-[1.05fr,0.95fr]">
              <div className="studio-panel p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Workspace flow</p>
                <h3 className="mt-2 text-lg font-semibold text-slate-900">Move from evidence intake to synthesis without leaving this page.</h3>
                <div className="mt-4 grid gap-3">
                  {[
                    'Filter the paper list, inspect one paper in detail, then add it to the chat context only when it is actually relevant.',
                    'Resolve full-text access before asking AI questions so the workspace keeps the strongest evidence possible.',
                    'Use the operations tab for exports and imports instead of mixing those tasks into every reading step.',
                  ].map((item, index) => (
                    <div key={item} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-indigo-600">Step {index + 1}</p>
                      <p className="mt-1 text-sm leading-relaxed text-slate-600">{item}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => setActiveTab('papers')}
                  className="rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-sm transition-transform duration-150 hover:-translate-y-1 hover:shadow-lg"
                >
                  <div className="inline-flex rounded-2xl bg-gradient-to-br from-indigo-500 to-cyan-500 p-2.5 text-white shadow-md">
                    <FileText className="h-5 w-5" />
                  </div>
                  <h4 className="mt-4 text-base font-semibold text-slate-900">Reading lane</h4>
                  <p className="mt-1 text-sm leading-relaxed text-slate-600">
                    {workspace.papers.length} papers loaded, {fullTextReadyCount} ready for full-text review.
                  </p>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('chat')}
                  className="rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-sm transition-transform duration-150 hover:-translate-y-1 hover:shadow-lg"
                >
                  <div className="inline-flex rounded-2xl bg-gradient-to-br from-sky-500 to-blue-600 p-2.5 text-white shadow-md">
                    <MessageSquare className="h-5 w-5" />
                  </div>
                  <h4 className="mt-4 text-base font-semibold text-slate-900">Chat lane</h4>
                  <p className="mt-1 text-sm leading-relaxed text-slate-600">
                    {chatPaperIds.length} paper{chatPaperIds.length === 1 ? '' : 's'} currently in AI context.
                  </p>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('review')}
                  className="rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-sm transition-transform duration-150 hover:-translate-y-1 hover:shadow-lg"
                >
                  <div className="inline-flex rounded-2xl bg-gradient-to-br from-fuchsia-500 to-violet-600 p-2.5 text-white shadow-md">
                    <Sparkles className="h-5 w-5" />
                  </div>
                  <h4 className="mt-4 text-base font-semibold text-slate-900">Review lane</h4>
                  <p className="mt-1 text-sm leading-relaxed text-slate-600">
                    Build a report and fault scan once the workspace evidence is stable.
                  </p>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('ops')}
                  className="rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-sm transition-transform duration-150 hover:-translate-y-1 hover:shadow-lg"
                >
                  <div className="inline-flex rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 p-2.5 text-white shadow-md">
                    <Download className="h-5 w-5" />
                  </div>
                  <h4 className="mt-4 text-base font-semibold text-slate-900">Operations lane</h4>
                  <p className="mt-1 text-sm leading-relaxed text-slate-600">
                    Export, batch import, and keep workspace data portable.
                  </p>
                </button>
              </div>
            </section>

            <div className="mb-4">
              <div className="studio-tabs">
                <button
                  onClick={() => setActiveTab('papers')}
                  className={`studio-tab ${activeTab === 'papers' ? 'studio-tab-active' : ''}`}
                >
                  Papers ({workspace.papers.length})
                </button>
                <button
                  onClick={() => setActiveTab('chat')}
                  className={`studio-tab ${activeTab === 'chat' ? 'studio-tab-active' : ''}`}
                >
                  AI Chat
                </button>
                <button
                  onClick={() => setActiveTab('review')}
                  className={`studio-tab ${activeTab === 'review' ? 'studio-tab-active' : ''}`}
                >
                  Review Draft
                </button>
                <button
                  onClick={() => setActiveTab('ops')}
                  className={`studio-tab ${activeTab === 'ops' ? 'studio-tab-active' : ''}`}
                >
                  Operations
                </button>
              </div>
            </div>

            {activeTab === 'papers' && (
              <section className="space-y-4">
                <div className="grid gap-4 xl:grid-cols-[0.9fr,1.1fr]">
                  <div className="studio-surface p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">Workspace papers</p>
                        <p className="mt-0.5 text-xs text-slate-500">
                          {papersForDisplay.length} of {workspace.papers.length} papers visible
                        </p>
                      </div>
                      <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                        <input
                          type="checkbox"
                          checked={fullTextOnlyPapers}
                          onChange={(event) => setFullTextOnlyPapers(event.target.checked)}
                        />
                        Show full-text only
                      </label>
                    </div>

                    <div className="relative mt-3">
                      <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                      <input
                        type="text"
                        value={paperQuery}
                        onChange={(event) => setPaperQuery(event.target.value)}
                        placeholder="Filter by title, author, DOI, or source"
                        className="w-full rounded-xl border border-slate-300 py-2.5 pl-10 pr-3 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    </div>

                    <div className="mt-4 space-y-3">
                      {workspace.papers.length === 0 ? (
                        <div className="studio-panel-quiet p-8 text-center">
                          <p className="text-sm text-slate-600">
                            No papers in this workspace yet. Import papers from Search to begin.
                          </p>
                          <Link to="/search" className="mt-3 inline-flex items-center gap-1.5 text-sm font-semibold text-indigo-600">
                            Open search
                            <ExternalLink className="h-4 w-4" />
                          </Link>
                        </div>
                      ) : papersForDisplay.length === 0 ? (
                        <div className="studio-panel-quiet p-8 text-center">
                          <p className="text-sm text-slate-600">
                            No papers match the current paper filter. Clear the query or disable full-text only.
                          </p>
                        </div>
                      ) : (
                        papersForDisplay.map((paper) => {
                          const fullTextUrl = String(
                            paper.pdf_url ||
                              paper.institutional_url ||
                              (String(paper.url || '').toLowerCase().endsWith('.pdf') ? paper.url : '') ||
                              ''
                          ).trim();
                          const hasFullText = Boolean(paper.full_text_available) || Boolean(fullTextUrl);
                          const active = selectedPaper?.id === paper.id;

                          return (
                            <button
                              key={paper.id}
                              type="button"
                              onClick={() => setSelectedPaperId(paper.id)}
                              className={`w-full rounded-2xl border p-4 text-left transition ${
                                active
                                  ? 'border-indigo-300 bg-indigo-50/70 shadow-sm'
                                  : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                              }`}
                            >
                              <div className="flex flex-wrap items-center gap-2">
                                <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${hasFullText ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                                  {hasFullText ? 'Full text ready' : 'Metadata / DOI'}
                                </span>
                                {paper.source && (
                                  <span className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] font-semibold text-sky-700">
                                    {paper.source}
                                  </span>
                                )}
                              </div>
                              <h3 className="mt-3 text-base font-semibold text-slate-900 line-clamp-2">{paper.title}</h3>
                              <p className="mt-1 text-sm text-slate-500 line-clamp-1">{paper.authors}</p>
                              <p className="mt-2 line-clamp-2 text-sm text-slate-600">{paper.abstract || 'No abstract available.'}</p>
                            </button>
                          );
                        })
                      )}
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="studio-surface p-5">
                      {selectedPaper ? (() => {
                        const fullTextUrl = String(
                          selectedPaper.pdf_url ||
                            selectedPaper.institutional_url ||
                            (String(selectedPaper.url || '').toLowerCase().endsWith('.pdf') ? selectedPaper.url : '') ||
                            ''
                        ).trim();
                        const hasFullText = Boolean(selectedPaper.full_text_available) || Boolean(fullTextUrl);
                        const accessType = String(selectedPaper.access_type || '').toLowerCase();
                        const accessLabel = hasFullText
                          ? accessType === 'institutional'
                            ? 'Institutional Full Text'
                            : 'Full Text Available'
                          : selectedPaper.doi
                          ? 'DOI Available'
                          : 'Metadata Only';

                        return (
                          <>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${hasFullText ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                                {accessLabel}
                              </span>
                              {selectedPaper.source && (
                                <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-[11px] font-semibold text-indigo-700">
                                  {selectedPaper.source}
                                </span>
                              )}
                            </div>

                            <h3 className="mt-3 text-2xl font-semibold leading-tight text-slate-900">{selectedPaper.title}</h3>
                            <p className="mt-2 text-sm text-slate-500">{selectedPaper.authors}</p>
                            <p className="mt-4 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                              {selectedPaper.abstract || 'No abstract available for this paper yet.'}
                            </p>

                            <div className="mt-4 flex flex-wrap gap-2">
                              {selectedPaper.url && (
                                <a
                                  href={selectedPaper.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1.5 rounded-xl bg-slate-700 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800"
                                >
                                  View paper
                                  <ExternalLink className="h-4 w-4" />
                                </a>
                              )}
                              {fullTextUrl && (
                                <button
                                  type="button"
                                  onClick={() => {
                                    void handleOpenFile(fullTextUrl, `${selectedPaper.title || 'paper'}-full-text.pdf`);
                                  }}
                                  className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-700"
                                >
                                  Open full text
                                  <ExternalLink className="h-4 w-4" />
                                </button>
                              )}
                              {selectedPaper.doi && (
                                <a
                                  href={`https://doi.org/${selectedPaper.doi}`}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700"
                                >
                                  DOI
                                  <ExternalLink className="h-4 w-4" />
                                </a>
                              )}
                            </div>

                            <div className="mt-4 grid gap-3 sm:grid-cols-2">
                              <button
                                type="button"
                                onClick={() => {
                                  if (!chatPaperIds.includes(selectedPaper.id)) {
                                    setChatPaperIds((prev) => [...prev, selectedPaper.id]);
                                  }
                                  setActiveTab('chat');
                                }}
                                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-left transition hover:bg-slate-100"
                              >
                                <p className="text-sm font-semibold text-slate-900">Use in chat context</p>
                                <p className="mt-1 text-xs leading-5 text-slate-500">
                                  Add this paper to the AI context set and switch to the chat lane.
                                </p>
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  setFaultPaperId(selectedPaper.id);
                                  setActiveTab('review');
                                }}
                                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-left transition hover:bg-slate-100"
                              >
                                <p className="text-sm font-semibold text-slate-900">Send to review lane</p>
                                <p className="mt-1 text-xs leading-5 text-slate-500">
                                  Use this paper for fault detection and research brief generation.
                                </p>
                              </button>
                            </div>
                          </>
                        );
                      })() : (
                        <div className="studio-panel-quiet p-8 text-center">
                          <p className="text-sm text-slate-600">Select a paper to inspect details and take the next action.</p>
                        </div>
                      )}
                    </div>

                    <div className="studio-surface p-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-slate-900">Institutional connector</p>
                          <p className="mt-0.5 text-xs text-slate-500">
                            Paste lines in format: <code>Title | URL | DOI | Author1; Author2</code>
                          </p>
                        </div>
                        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600">
                          {institutionalRaw.split('\n').filter((line) => line.trim()).length} lines
                        </span>
                      </div>
                      <textarea
                        value={institutionalRaw}
                        onChange={(event) => setInstitutionalRaw(event.target.value)}
                        placeholder="Example: Explainable IoT Detection | https://publisher.com/paper | 10.1000/example.doi"
                        className="mt-3 min-h-[110px] w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                      <div className="mt-3 flex justify-end">
                        <button
                          type="button"
                          onClick={() => {
                            void importInstitutionalPapers();
                          }}
                          disabled={institutionalImporting || !institutionalRaw.trim()}
                          className="hero-btn-primary disabled:cursor-not-allowed disabled:opacity-55"
                        >
                          {institutionalImporting ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" />
                              Importing...
                            </>
                          ) : (
                            <>
                              <FileText className="h-4 w-4" />
                              Import Institutional Papers
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </section>
            )}

            {activeTab === 'chat' && (
              <section className="studio-surface p-4">
                <div className="mb-3">
                  <h3 className="text-lg font-semibold text-slate-900">AI Research Assistant</h3>
                  <p className="text-sm text-slate-500">
                    Ask deep questions grounded in papers inside this workspace.
                  </p>
                </div>

                <div className="mb-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Context papers ({chatPaperIds.length}/{workspace.papers.length})
                    </p>
                    <div className="flex items-center gap-2 text-xs">
                      <button
                        type="button"
                        onClick={() => setChatPaperIds(workspace.papers.map((paper) => paper.id))}
                        className="text-indigo-600 font-semibold hover:underline"
                      >
                        Select all
                      </button>
                      <button
                        type="button"
                        onClick={() => setChatPaperIds([])}
                        className="text-slate-500 font-semibold hover:underline"
                      >
                        Clear
                      </button>
                    </div>
                  </div>
                  <div className="max-h-36 overflow-auto space-y-1.5 pr-1">
                    {workspace.papers.map((paper) => (
                      <label key={paper.id} className="inline-flex w-full items-start gap-2 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700">
                        <input
                          type="checkbox"
                          checked={chatPaperIds.includes(paper.id)}
                          onChange={() => toggleChatPaper(paper.id)}
                        />
                        <span className="line-clamp-1">{paper.title}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <div className="workspace-chat-window mb-4">
                  {workspace.chats.length === 0 ? (
                    <p className="text-sm text-slate-500">
                      No chat history yet. Ask your first question to start context-aware analysis.
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {workspace.chats.map((chat) => (
                        <div key={chat.id} className="space-y-2">
                          <div className="chat-bubble-user">
                            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">
                              You
                            </p>
                            <p>{chat.message}</p>
                          </div>
                          <div className="chat-bubble-ai">
                            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">
                              Soyog AI
                            </p>
                            <p className="whitespace-pre-wrap">{chat.response}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <form onSubmit={handleSendMessage} className="flex gap-2">
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Ask about methods, gaps, trends, or comparisons..."
                    className="flex-1 rounded-xl border border-slate-300 py-2.5 px-3.5 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  <button
                    type="submit"
                    disabled={sending || !chatInput.trim() || chatPaperIds.length === 0}
                    className="hero-btn-primary disabled:opacity-55 disabled:cursor-not-allowed"
                  >
                    {sending ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Sending...
                      </>
                    ) : (
                      <>
                        <MessageSquare className="h-4 w-4" />
                        Send
                      </>
                    )}
                  </button>
                </form>
                {chatPaperIds.length === 0 && (
                  <p className="mt-2 text-xs text-amber-700">
                    Select at least one paper to run contextual chat.
                  </p>
                )}
              </section>
            )}

            {activeTab === 'review' && (
              <section className="studio-surface p-5">
                <h3 className="text-lg font-semibold text-slate-900 mb-1">Generate Research Brief + Mindmap</h3>
                <p className="text-sm text-slate-600 mb-4">
                  Build a complete research synthesis from workspace papers and export it as PDF or Word.
                </p>
                {workspace.papers.length === 0 && (
                  <div className="studio-panel px-4 py-3 text-sm text-amber-800 border-amber-200 bg-amber-50 mb-4">
                    Add at least one paper to this workspace, then run mindmap export.
                  </div>
                )}
                <div className="studio-panel-quiet p-4 mb-4">
                  <p className="text-sm text-slate-600">
                    The generated document includes executive summary, core concepts, methods landscape,
                    comparative findings, risks, future directions, and a hierarchical mindmap.
                  </p>
                </div>

                <div className="studio-panel-quiet p-4 mb-4">
                  <div className="flex flex-wrap items-end gap-2.5">
                    <div className="min-w-[220px] flex-1">
                      <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                        Fault Detection Paper
                      </label>
                      <select
                        value={faultPaperId ?? ''}
                        onChange={(event) => setFaultPaperId(event.target.value ? Number(event.target.value) : null)}
                        className="w-full rounded-xl border border-slate-300 py-2.5 px-3.5 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      >
                        {workspace.papers.map((paper) => (
                          <option key={paper.id} value={paper.id}>
                            {paper.title}
                          </option>
                        ))}
                      </select>
                    </div>
                    <button
                      type="button"
                      onClick={() => void runFaultDetection()}
                      disabled={!faultPaperId || faultLoading || workspace.papers.length === 0}
                      className="hero-btn-secondary disabled:opacity-55 disabled:cursor-not-allowed"
                    >
                      {faultLoading ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Detecting...
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-4 w-4" />
                          Detect Research Faults
                        </>
                      )}
                    </button>
                  </div>

                  {faultResult && (
                    <div className="mt-3 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-rose-50 text-rose-700 px-2.5 py-1 text-xs font-semibold">
                          Faults: {faultResult.fault_count}
                        </span>
                        {typeof faultResult.risk_score === 'number' && (
                          <span className="rounded-full bg-amber-50 text-amber-700 px-2.5 py-1 text-xs font-semibold">
                            Risk {faultResult.risk_score}/100
                          </span>
                        )}
                        {typeof faultResult.quality_score === 'number' && (
                          <span className="rounded-full bg-emerald-50 text-emerald-700 px-2.5 py-1 text-xs font-semibold">
                            Quality {faultResult.quality_score}/100
                          </span>
                        )}
                        {faultResult.quality_tier && (
                          <span className="rounded-full bg-indigo-50 text-indigo-700 px-2.5 py-1 text-xs font-semibold">
                            Tier {faultResult.quality_tier}
                          </span>
                        )}
                      </div>
                      {faultResult.severity_breakdown && (
                        <p className="text-[11px] text-slate-500">
                          High {faultResult.severity_breakdown.high} | Medium {faultResult.severity_breakdown.medium} | Low {faultResult.severity_breakdown.low}
                        </p>
                      )}
                      <div className="space-y-2">
                        {faultResult.faults.map((fault, index) => (
                          <div key={`${fault.fault_type}-${index}`} className="rounded-lg border border-slate-200 bg-white p-2.5">
                            <p className="text-xs font-semibold text-slate-800">
                              {fault.severity.toUpperCase()} - {fault.fault_type.replace(/_/g, ' ')}
                            </p>
                            <p className="text-xs text-slate-600 mt-1">{fault.evidence}</p>
                            <p className="text-xs text-indigo-700 mt-1">{fault.recommendation}</p>
                          </div>
                        ))}
                      </div>
                      {Array.isArray(faultResult.verification_checklist) && faultResult.verification_checklist.length > 0 && (
                        <div className="rounded-lg border border-slate-200 bg-white p-2.5">
                          <p className="text-xs font-semibold text-slate-800 mb-1">Verification checklist</p>
                          <ul className="list-disc pl-4 space-y-1 text-xs text-slate-600">
                            {faultResult.verification_checklist.map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {faultResult.analysis && (
                        <div className="rounded-lg border border-slate-200 bg-white p-2.5 text-xs text-slate-700 whitespace-pre-wrap max-h-40 overflow-auto">
                          {faultResult.analysis}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="mb-3">
                  <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                    Focus topic
                  </label>
                  <input
                    type="text"
                    value={reportTopic}
                    onChange={(e) => setReportTopic(e.target.value)}
                    placeholder="Example: Graph neural networks for molecular property prediction"
                    className="w-full rounded-xl border border-slate-300 py-2.5 px-3.5 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div className="flex flex-wrap items-center gap-2.5">
                  <button
                    type="button"
                    onClick={() => handleResearchReportExport('pdf')}
                    disabled={reportGenerating !== null || workspace.papers.length === 0}
                    className="hero-btn-primary disabled:opacity-55 disabled:cursor-not-allowed"
                  >
                    {reportGenerating === 'pdf' ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Generating PDF...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4" />
                        Download PDF Mindmap
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleResearchReportExport('docx')}
                    disabled={reportGenerating !== null || workspace.papers.length === 0}
                    className="hero-btn-secondary disabled:opacity-55 disabled:cursor-not-allowed"
                  >
                    {reportGenerating === 'docx' ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Generating Word...
                      </>
                    ) : (
                      <>
                        <Download className="h-4 w-4" />
                        Download Word Mindmap
                      </>
                    )}
                  </button>
                </div>
              </section>
            )}

            {activeTab === 'ops' && (
              <section className="space-y-4">
                <div className="studio-surface p-5">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Operations lane</p>
                  <h3 className="mt-2 text-lg font-semibold text-slate-900">Keep the workspace portable and auditable.</h3>
                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    {[
                      {
                        title: 'Export often',
                        copy: 'Use structured exports before major synthesis changes so you always have a stable checkpoint.',
                      },
                      {
                        title: 'Batch import carefully',
                        copy: 'Bring in external lists through import flows instead of pasting references manually into chat or notes.',
                      },
                      {
                        title: 'Resolve access first',
                        copy: 'Refresh paper access after imports so downstream reading and AI steps work from the strongest version.',
                      },
                    ].map((item) => (
                      <div key={item.title} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                        <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                        <p className="mt-1 text-xs leading-5 text-slate-600">{item.copy}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <DataExportImport
                  workspaceId={workspace.id}
                  workspaceName={workspace.name}
                  onImportComplete={() => {
                    void loadWorkspace();
                  }}
                />
              </section>
            )}
          </>
        )}
      </div>
    </Layout>
  );
};

export default Workspace;
