import React, { useEffect, useMemo, useState } from 'react';
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
  Sparkles,
  Workflow,
} from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';
import { apiErrorMessage } from '../utils/apiError';

interface Paper {
  id: number;
  title: string;
  authors: string;
  abstract: string;
  url?: string;
  doi?: string;
  bibcode?: string;
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

type WorkspaceTab = 'papers' | 'chat' | 'review';

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
  const [faultLoading, setFaultLoading] = useState(false);
  const [faultResult, setFaultResult] = useState<FaultResult | null>(null);

  useEffect(() => {
    const fetchWorkspace = async () => {
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

        const restoredTab = String(extra.active_tab || '');
        if (restoredTab === 'papers' || restoredTab === 'chat' || restoredTab === 'review') {
          setActiveTab(restoredTab);
        }
      } catch {
        setError('Failed to load workspace.');
      } finally {
        setLoading(false);
      }
    };
    fetchWorkspace();
  }, [id]);

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
          },
        })
        .catch(() => undefined);
    }, 700);
    return () => window.clearTimeout(timer);
  }, [activeTab, chatInput, chatPaperIds, faultPaperId, workspace]);

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
              </div>
            </div>

            {activeTab === 'papers' && (
              <section className="workspace-grid">
                {workspace.papers.length === 0 ? (
                  <div className="studio-panel-quiet p-8 text-center">
                    <p className="text-sm text-slate-600">
                      No papers in this workspace yet. Import papers from Search to begin.
                    </p>
                  </div>
                ) : (
                  workspace.papers.map((paper) => (
                    <article key={paper.id} className="workspace-paper-card">
                      <h3 className="text-base font-semibold text-slate-900">{paper.title}</h3>
                      <p className="text-sm text-slate-500 mt-1">{paper.authors}</p>
                      <div className="mt-2 flex flex-wrap gap-2 text-xs">
                        {paper.doi && (
                          <a
                            href={`https://doi.org/${paper.doi}`}
                            target="_blank"
                            rel="noreferrer"
                            className="px-2 py-1 rounded-lg bg-emerald-50 text-emerald-700 font-medium"
                          >
                            DOI: {paper.doi}
                          </a>
                        )}
                        {paper.bibcode && (
                          <a
                            href={`https://ui.adsabs.harvard.edu/abs/${paper.bibcode}`}
                            target="_blank"
                            rel="noreferrer"
                            className="px-2 py-1 rounded-lg bg-emerald-50 text-emerald-700 font-medium"
                          >
                            Bibcode: {paper.bibcode}
                          </a>
                        )}
                      </div>
                      <p className="text-sm text-slate-700 mt-3 line-clamp-3">{paper.abstract}</p>
                      {paper.url && (
                        <a
                          href={paper.url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1.5 text-sm text-indigo-600 mt-3 font-semibold"
                        >
                          View paper
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      )}
                    </article>
                  ))
                )}
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
                              ResearchHub AI
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
          </>
        )}
      </div>
    </Layout>
  );
};

export default Workspace;
