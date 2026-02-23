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

  useEffect(() => {
    const fetchWorkspace = async () => {
      if (!id) {
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const res = await api.get(`/workspaces/${id}`);
        setWorkspace(res.data);
        setReportTopic(res.data?.name ? `${res.data.name} literature synthesis` : '');
      } catch {
        setError('Failed to load workspace.');
      } finally {
        setLoading(false);
      }
    };
    fetchWorkspace();
  }, [id]);

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
      });
      const newItem: ChatItem = {
        id: Date.now(),
        message: chatInput,
        response: res.data.response,
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
                    disabled={sending || !chatInput.trim()}
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
