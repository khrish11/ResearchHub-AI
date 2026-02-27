import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  BookOpen,
  CheckSquare,
  Copy,
  Download,
  Eye,
  FileText,
  Lightbulb,
  Loader2,
  Play,
  Sparkles,
  Wand2,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
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
}

interface Workspace {
  id: number;
  name: string;
}

type ToolType = 'summaries' | 'insights' | 'review';
type DetailLevel = 'quick' | 'balanced' | 'deep';
type FocusMode = 'broad' | 'methods' | 'applications' | 'risks';

interface AnalyzeResponse {
  response: string;
  mode?: string;
  detail_level?: string;
  focus?: string;
}

interface AiStatusResponse {
  enabled: boolean;
  configured?: boolean;
  model?: string | null;
  error?: string | null;
}

interface DraftQuality {
  score?: number;
  label?: string;
  notes?: string[];
  stats?: {
    chars?: number;
    headings?: number;
    bullets?: number;
    paper_refs?: number;
    sentences?: number;
    lexical_diversity?: number;
  };
}

interface SentenceEdit {
  original: string;
  improved: string;
  why?: string;
  evidence?: string;
}

interface WritingSuggestionResponse {
  suggestions?: string[];
  suggestion_groups?: Record<string, string[]>;
  draft_quality?: DraftQuality;
  target_score?: number;
  evidence_map?: string[];
  sentence_edits?: SentenceEdit[];
  revision_checklist?: string[];
  rewrite_excerpt?: string;
  analysis?: string;
}

const TOOL_CONFIG: Record<
  ToolType,
  { label: string; prompt: string; color: string; icon: LucideIcon; details: string }
> = {
  summaries: {
    label: 'AI Summaries',
    prompt:
      'For each paper below, create a detailed analysis with sections: Problem, Method, Data/Benchmarks, Key Results, Limitations, and Practical Takeaways. Use bullet points and cite Paper N for non-trivial claims.\n\n',
    color: '#4f46e5',
    icon: FileText,
    details: 'Detailed per-paper breakdown with method, evidence, and limitations.',
  },
  insights: {
    label: 'Key Insights',
    prompt:
      'Extract 10-14 cross-paper insights, recurring themes, contradictions, and risk areas. Include confidence (High/Medium/Low) for each insight and cite Paper N.\n\n',
    color: '#f97316',
    icon: Lightbulb,
    details: 'Cross-paper synthesis with contradictions, confidence, and next actions.',
  },
  review: {
    label: 'Literature Review',
    prompt:
      'Write a long-form structured literature review with sections: Introduction, Taxonomy of Methods, Comparative Findings, Key Insights, Gaps and Risks, Future Research Directions, and Execution Plan. Cite Paper N throughout.\n\n',
    color: '#059669',
    icon: BookOpen,
    details: 'Long-form review draft with evidence-grounded synthesis and roadmap.',
  },
};

const LAST_WORKSPACE_KEY = 'researchhub.last_workspace_id';
const PAPER_SELECTIONS_KEY = 'researchhub.ai_tool.paper_selection.v1';

const getStoredSelections = (): Record<string, number[]> => {
  try {
    const raw = localStorage.getItem(PAPER_SELECTIONS_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return {};
    return parsed as Record<string, number[]>;
  } catch {
    return {};
  }
};

const saveStoredSelections = (value: Record<string, number[]>) => {
  localStorage.setItem(PAPER_SELECTIONS_KEY, JSON.stringify(value));
};

const AITools: React.FC = () => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWsId, setSelectedWsId] = useState<number | null>(null);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [loadingPapers, setLoadingPapers] = useState(false);
  const [activeTool, setActiveTool] = useState<ToolType | null>(null);
  const [result, setResult] = useState('');
  const [loadingTool, setLoadingTool] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aiStatus, setAiStatus] = useState<AiStatusResponse | null>(null);
  const [detailLevel, setDetailLevel] = useState<DetailLevel>('balanced');
  const [focusMode, setFocusMode] = useState<FocusMode>('broad');
  const [includePaperLinks, setIncludePaperLinks] = useState(true);
  const [copyNotice, setCopyNotice] = useState<string | null>(null);
  const [writingDraft, setWritingDraft] = useState('');
  const [writingSuggestions, setWritingSuggestions] = useState<string[]>([]);
  const [writingSuggestionGroups, setWritingSuggestionGroups] = useState<Record<string, string[]>>({});
  const [writingDraftQuality, setWritingDraftQuality] = useState<DraftQuality | null>(null);
  const [writingTargetScore, setWritingTargetScore] = useState<number | null>(null);
  const [writingEvidenceMap, setWritingEvidenceMap] = useState<string[]>([]);
  const [writingSentenceEdits, setWritingSentenceEdits] = useState<SentenceEdit[]>([]);
  const [writingChecklist, setWritingChecklist] = useState<string[]>([]);
  const [rewriteExcerpt, setRewriteExcerpt] = useState('');
  const [writingSuggestionAnalysis, setWritingSuggestionAnalysis] = useState('');
  const [writingSuggestionLoading, setWritingSuggestionLoading] = useState(false);
  const [writingSuggestionError, setWritingSuggestionError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<AiStatusResponse>('/ai/status')
      .then((res) => setAiStatus(res.data))
      .catch(() => setAiStatus({ enabled: false, configured: false, error: 'Failed to read AI status.' }));
  }, []);

  useEffect(() => {
    let mounted = true;
    const boot = async () => {
      try {
        const [workspaceRes, sessionRes] = await Promise.all([
          api.get('/workspaces/'),
          api.get('/workspaces/session-state').catch(() => ({ data: null })),
        ]);
        if (!mounted) return;
        const list: Workspace[] = workspaceRes.data || [];
        setWorkspaces(list);
        if (list.length > 0) {
          const stored = Number(localStorage.getItem(LAST_WORKSPACE_KEY));
          const resumedWs = Number(sessionRes?.data?.workspace_id || 0);
          const preferred = [resumedWs, stored].find(
            (candidate) => Number.isFinite(candidate) && list.some((workspace) => workspace.id === candidate)
          );
          setSelectedWsId(preferred || list[0].id);
        }
        const restoredDraft = String(sessionRes?.data?.draft_text || '').trim();
        if (restoredDraft) {
          setWritingDraft(restoredDraft);
        }
      } catch {
        if (!mounted) return;
        setWorkspaces([]);
      }
    };
    void boot();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedWsId) {
      return;
    }
    localStorage.setItem(LAST_WORKSPACE_KEY, String(selectedWsId));
    setLoadingPapers(true);
    setSelectedIds(new Set());
    setResult('');
    setError(null);
    api
      .get(`/workspaces/${selectedWsId}`)
      .then((res) => {
        const workspacePapers: Paper[] = res.data.papers ?? [];
        setPapers(workspacePapers);
        const selectionMap = getStoredSelections();
        const stored = Array.isArray(selectionMap[String(selectedWsId)]) ? selectionMap[String(selectedWsId)] : [];
        const validStored = stored.filter((paperId) => workspacePapers.some((paper) => paper.id === paperId));
        const nextSelection = validStored.length > 0 ? validStored : workspacePapers.map((paper) => paper.id);
        setSelectedIds(new Set(nextSelection));
      })
      .catch(() => setError('Failed to load papers.'))
      .finally(() => setLoadingPapers(false));
  }, [selectedWsId]);

  useEffect(() => {
    if (!selectedWsId) return;
    const selectionMap = getStoredSelections();
    selectionMap[String(selectedWsId)] = Array.from(selectedIds);
    saveStoredSelections(selectionMap);
  }, [selectedIds, selectedWsId]);

  useEffect(() => {
    if (!selectedWsId) return;
    const timer = window.setTimeout(() => {
      void api
        .put('/workspaces/session-state', {
          page_path: '/ai-tools',
          workspace_id: selectedWsId,
          draft_text: writingDraft.slice(0, 12000),
          extra: {
            selected_paper_ids: Array.from(selectedIds),
            detail_level: detailLevel,
            focus_mode: focusMode,
          },
        })
        .catch(() => undefined);
    }, 800);
    return () => window.clearTimeout(timer);
  }, [detailLevel, focusMode, selectedIds, selectedWsId, writingDraft]);

  useEffect(() => {
    if (!selectedWsId || writingDraft.trim().length < 30) {
      setWritingSuggestions([]);
      setWritingSuggestionGroups({});
      setWritingDraftQuality(null);
      setWritingTargetScore(null);
      setWritingEvidenceMap([]);
      setWritingSentenceEdits([]);
      setWritingChecklist([]);
      setRewriteExcerpt('');
      setWritingSuggestionAnalysis('');
      setWritingSuggestionError(null);
      return;
    }

    const timer = window.setTimeout(async () => {
      setWritingSuggestionLoading(true);
      setWritingSuggestionError(null);
      try {
        const response = await api.post<WritingSuggestionResponse>('/research/writing-suggestions', {
          workspace_id: selectedWsId,
          paper_ids: Array.from(selectedIds),
          topic: `Workspace manuscript draft: ${workspaces.find((workspace) => workspace.id === selectedWsId)?.name || 'Research topic'}`,
          draft_text: writingDraft,
          max_suggestions: 12,
        });
        setWritingSuggestions(Array.isArray(response.data?.suggestions) ? response.data.suggestions : []);
        setWritingSuggestionGroups(
          response.data?.suggestion_groups && typeof response.data.suggestion_groups === 'object'
            ? response.data.suggestion_groups
            : {}
        );
        setWritingDraftQuality(response.data?.draft_quality || null);
        setWritingTargetScore(
          Number.isFinite(Number(response.data?.target_score)) ? Number(response.data?.target_score) : null
        );
        setWritingEvidenceMap(
          Array.isArray(response.data?.evidence_map) ? response.data.evidence_map.map((item) => String(item)) : []
        );
        setWritingSentenceEdits(
          Array.isArray(response.data?.sentence_edits)
            ? response.data.sentence_edits
                .filter((item) => item && typeof item === 'object')
                .map((item) => ({
                  original: String(item.original || ''),
                  improved: String(item.improved || ''),
                  why: String(item.why || ''),
                  evidence: String(item.evidence || ''),
                }))
                .filter((item) => item.original || item.improved)
            : []
        );
        setWritingChecklist(
          Array.isArray(response.data?.revision_checklist)
            ? response.data.revision_checklist.map((item) => String(item))
            : []
        );
        setRewriteExcerpt(String(response.data?.rewrite_excerpt || ''));
        setWritingSuggestionAnalysis(String(response.data?.analysis || ''));
      } catch (err: unknown) {
        setWritingSuggestionError(apiErrorMessage(err, 'Failed to generate writing suggestions.'));
      } finally {
        setWritingSuggestionLoading(false);
      }
    }, 900);

    return () => {
      window.clearTimeout(timer);
    };
  }, [selectedIds, selectedWsId, workspaces, writingDraft]);

  const togglePaper = (paperId: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(paperId)) {
        next.delete(paperId);
      } else {
        next.add(paperId);
      }
      return next;
    });
  };

  const runTool = async (tool: ToolType) => {
    if (aiStatus && !aiStatus.enabled) {
      setError(
        aiStatus.error
          ? `AI unavailable: ${aiStatus.error}`
          : 'AI service is unavailable. Check backend/.env and restart backend.'
      );
      return;
    }
    if (selectedIds.size === 0) {
      setError('Select at least one paper first.');
      return;
    }
    if (!selectedWsId) {
      return;
    }
    setError(null);
    setActiveTool(tool);
    setLoadingTool(true);
    setResult('');

    const chosenPapers = papers.filter((paper) => selectedIds.has(paper.id));
    const context = chosenPapers
      .map(
        (paper, index) =>
          `Paper ${index + 1} Title: ${paper.title}\nAuthors: ${paper.authors}\nURL: ${paper.url || 'N/A'}\nDOI: ${paper.doi || 'N/A'}\nAbstract: ${(paper.abstract || '').slice(0, 1800) || 'No abstract available.'}`
      )
      .join('\n\n---\n\n');

    const fullPrompt =
      `${TOOL_CONFIG[tool].prompt}` +
      'Use evidence-grounded statements and cite Paper N for non-trivial claims. Avoid [P#] notation.\n\n' +
      context;

    try {
      const res = await api.post<AnalyzeResponse>('/ai/analyze', {
        prompt: fullPrompt,
        mode: tool,
        detail_level: detailLevel,
        focus: focusMode,
        include_paper_links: includePaperLinks,
        reference_style: 'paper',
      });
      setResult(res.data.response);
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'AI tool failed. Please ensure the Groq key is set.'));
    } finally {
      setLoadingTool(false);
    }
  };

  const downloadResult = () => {
    if (!result || !activeTool) {
      return;
    }
    const blob = new Blob([result], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${activeTool}_${Date.now()}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const copyResult = async () => {
    if (!result) {
      return;
    }
    try {
      await navigator.clipboard.writeText(result);
      setCopyNotice('Copied');
      window.setTimeout(() => setCopyNotice(null), 1500);
    } catch {
      setCopyNotice('Copy failed');
      window.setTimeout(() => setCopyNotice(null), 1500);
    }
  };

  const renderInlineLinks = (text: string) => {
    const pattern = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
    const nodes: Array<string | React.ReactNode> = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(text)) !== null) {
      const [full, label, href] = match;
      if (match.index > lastIndex) {
        nodes.push(text.slice(lastIndex, match.index));
      }
      nodes.push(
        <a key={`${href}-${match.index}`} href={href} target="_blank" rel="noreferrer" className="mindmap-inline-link">
          {label}
        </a>
      );
      lastIndex = match.index + full.length;
    }
    if (lastIndex < text.length) {
      nodes.push(text.slice(lastIndex));
    }
    return nodes.length ? nodes : text;
  };

  const totalAbstractChars = useMemo(
    () => papers.reduce((sum, paper) => sum + (paper.abstract?.length ?? 0), 0),
    [papers]
  );
  const draftScore = Number.isFinite(Number(writingDraftQuality?.score))
    ? Number(writingDraftQuality?.score)
    : 0;
  const targetScore = Number.isFinite(Number(writingTargetScore))
    ? Number(writingTargetScore)
    : Math.min(95, draftScore + 15);
  const scoreDelta = Math.max(0, targetScore - draftScore);
  const draftWordCount = useMemo(
    () => writingDraft.trim().split(/\s+/).filter(Boolean).length,
    [writingDraft]
  );
  const applyRewriteToDraft = () => {
    if (!rewriteExcerpt.trim()) return;
    setWritingDraft(rewriteExcerpt.trim());
  };

  return (
    <Layout>
      <div className="page-enter">
        <section className="studio-hero mb-5">
          <span className="studio-kicker">
            <Sparkles className="h-3.5 w-3.5" />
            AI execution
          </span>
          <h2>AI Tools Workspace</h2>
          <p>
            Select paper sets and run synthesis workflows to generate summaries, insights, and review
            drafts with one-click execution.
          </p>
          <div className="studio-chip-row">
            <span className="studio-chip">{workspaces.length} workspaces</span>
            <span className="studio-chip">{papers.length} loaded papers</span>
            <span className="studio-chip">{selectedIds.size} selected</span>
          </div>
          <div className="studio-orb" aria-hidden="true" />
        </section>

        {aiStatus && !aiStatus.enabled && (
          <section className="mb-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 inline-flex items-start gap-2">
            <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-semibold">AI service is currently unavailable.</p>
              <p>
                {aiStatus.error || 'Set GROQ_API_KEY in backend/.env and restart backend.'}
              </p>
            </div>
          </section>
        )}

        <section className="studio-stat-grid mb-4">
          <article className="studio-stat-card">
            <p className="studio-stat-label">Selected papers</p>
            <p className="studio-stat-value">{selectedIds.size}</p>
          </article>
          <article className="studio-stat-card">
            <p className="studio-stat-label">Loaded papers</p>
            <p className="studio-stat-value">{papers.length}</p>
          </article>
          <article className="studio-stat-card">
            <p className="studio-stat-label">Indexed chars</p>
            <p className="studio-stat-value">{Math.max(0, Math.round(totalAbstractChars / 1000))}k</p>
          </article>
          <article className="studio-stat-card">
            <p className="studio-stat-label">AI state</p>
            <p className="studio-stat-value">{loadingTool ? 'Running' : 'Ready'}</p>
          </article>
        </section>

        <section className="studio-surface p-4 mb-4">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <div>
              <h3 className="text-base font-semibold text-slate-900">Workspace and Paper Scope</h3>
              <p className="text-sm text-slate-500">
                Choose a workspace and include the paper subset for the next AI run.
              </p>
            </div>
            {workspaces.length === 0 && (
              <button
                onClick={() => {
                  const name = prompt('Enter workspace name:');
                  if (name) {
                    api
                      .post('/workspaces/', { name, description: '' })
                      .then((res) => {
                        setWorkspaces((prev) => [...prev, res.data]);
                        setSelectedWsId(res.data.id);
                      })
                      .catch((err: unknown) =>
                        setError(
                          `Failed to create workspace: ${apiErrorMessage(err, 'Unknown error')}`
                        )
                      );
                  }
                }}
                className="hero-btn-secondary"
              >
                Create workspace
              </button>
            )}
          </div>

          <div className="mb-3">
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
              Workspace
            </label>
            <select
              value={selectedWsId ?? ''}
              onChange={(e) => setSelectedWsId(Number(e.target.value))}
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {workspaces.length === 0 ? (
                <option value="">No workspaces available</option>
              ) : (
                workspaces.map((workspace) => (
                  <option key={workspace.id} value={workspace.id}>
                    {workspace.name}
                  </option>
                ))
              )}
            </select>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                Detail level
              </label>
              <select
                value={detailLevel}
                onChange={(e) => setDetailLevel(e.target.value as DetailLevel)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="quick">Quick</option>
                <option value="balanced">Balanced</option>
                <option value="deep">Deep</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                Focus mode
              </label>
              <select
                value={focusMode}
                onChange={(e) => setFocusMode(e.target.value as FocusMode)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="broad">Broad</option>
                <option value="methods">Methods</option>
                <option value="applications">Applications</option>
                <option value="risks">Risks</option>
              </select>
            </div>
            <div className="flex items-end">
              <label className="inline-flex items-center gap-2 text-sm text-slate-600 border border-slate-200 rounded-xl px-3 py-2.5 w-full">
                <input
                  type="checkbox"
                  checked={includePaperLinks}
                  onChange={(e) => setIncludePaperLinks(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-indigo-600"
                />
                Include paper links section
              </label>
            </div>
          </div>

          <div className="studio-panel-quiet p-3">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-semibold text-slate-800">Paper Selection</h4>
              {papers.length > 0 && (
                <div className="flex items-center gap-2 text-xs">
                  <button
                    onClick={() => setSelectedIds(new Set(papers.map((paper) => paper.id)))}
                    className="text-indigo-600 font-semibold hover:underline"
                  >
                    Select all
                  </button>
                  <button
                    onClick={() => setSelectedIds(new Set())}
                    className="text-slate-500 font-semibold hover:underline"
                  >
                    Clear
                  </button>
                </div>
              )}
            </div>

            {loadingPapers ? (
              <div className="flex items-center gap-2 text-sm text-slate-500 py-6">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading papers...
              </div>
            ) : papers.length === 0 ? (
              <p className="text-sm text-slate-500 py-4">
                No papers in this workspace. Import papers from Search or Upload PDF first.
              </p>
            ) : (
              <div className="max-h-64 overflow-y-auto space-y-2 pr-1">
                {papers.map((paper) => (
                  <label
                    key={paper.id}
                    className={`flex items-start gap-3 rounded-xl border p-3 cursor-pointer transition-colors ${
                      selectedIds.has(paper.id)
                        ? 'border-indigo-200 bg-indigo-50'
                        : 'border-slate-200 bg-white hover:bg-slate-50'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.has(paper.id)}
                      onChange={() => togglePaper(paper.id)}
                      className="mt-0.5 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-600"
                    />
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-slate-900 line-clamp-1">{paper.title}</p>
                      <p className="text-xs text-slate-500 truncate">{paper.authors}</p>
                    </div>
                  </label>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="studio-surface p-4 mb-4">
          <div className="flex items-center justify-between gap-3 mb-2">
            <h3 className="text-base font-semibold text-slate-900">Real-Time Writing Assistant</h3>
            <div className="text-xs text-slate-500 text-right">
              <p>{writingSuggestionLoading ? 'Analyzing draft...' : `${writingSuggestions.length} suggestions`}</p>
              <p>{draftWordCount} words</p>
            </div>
          </div>

          {writingDraftQuality?.score !== undefined && (
            <div className="mb-3">
              <div className="flex flex-wrap items-center gap-2 text-xs mb-2">
                <span className="rounded-full bg-emerald-50 text-emerald-700 px-2.5 py-1 font-semibold">
                  Target score {targetScore}/100
                </span>
                {scoreDelta > 0 && (
                  <span className="rounded-full bg-amber-50 text-amber-700 px-2.5 py-1 font-semibold">
                    Gap {scoreDelta} points
                  </span>
                )}
              </div>
              <div className="h-2.5 w-full rounded-full bg-slate-200 overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-indigo-500 via-cyan-500 to-emerald-500 transition-all"
                  style={{ width: `${Math.max(4, Math.min(100, draftScore))}%` }}
                />
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded-full bg-indigo-50 text-indigo-700 px-2.5 py-1 font-semibold">
                  Draft score {draftScore}/100
                </span>
                {writingDraftQuality.label && (
                  <span className="rounded-full bg-slate-100 text-slate-700 px-2.5 py-1 font-semibold">
                    Quality {writingDraftQuality.label}
                  </span>
                )}
                <span className="rounded-full bg-slate-100 text-slate-700 px-2.5 py-1 font-semibold">
                  Sentences {Number(writingDraftQuality.stats?.sentences || 0)}
                </span>
                <span className="rounded-full bg-slate-100 text-slate-700 px-2.5 py-1 font-semibold">
                  Paper refs {Number(writingDraftQuality.stats?.paper_refs || 0)}
                </span>
              </div>
            </div>
          )}

          <p className="text-sm text-slate-500 mb-3">
            Write your manuscript draft here and get AI revision suggestions while you type.
            Strong outputs include section headings, quantitative claims, and Paper N references.
          </p>

          <textarea
            value={writingDraft}
            onChange={(event) => setWritingDraft(event.target.value)}
            placeholder="Start writing your abstract, introduction, or methodology draft..."
            className="w-full min-h-[170px] rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <div className="mt-1.5 flex items-center justify-between text-xs text-slate-500">
            <span>{writingDraft.length} characters</span>
            <span>{selectedIds.size} paper contexts selected</span>
          </div>

          {writingSuggestionError && (
            <p className="mt-2 text-xs text-rose-700">{writingSuggestionError}</p>
          )}

          {(writingSuggestions.length > 0 || writingEvidenceMap.length > 0) && (
            <div className="mt-3 grid grid-cols-1 lg:grid-cols-2 gap-3">
              {writingSuggestions.length > 0 && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
                    Priority Suggestions
                  </p>
                  <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700">
                    {writingSuggestions.map((suggestion, idx) => (
                      <li key={`${suggestion}-${idx}`}>{suggestion}</li>
                    ))}
                  </ul>
                </div>
              )}

              {writingEvidenceMap.length > 0 && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700 mb-2">
                    Evidence Mapping
                  </p>
                  <ul className="list-disc pl-5 space-y-1 text-sm text-emerald-900">
                    {writingEvidenceMap.map((row, idx) => (
                      <li key={`${row}-${idx}`}>{row}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {Object.keys(writingSuggestionGroups).length > 0 && (
            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2">
              {Object.entries(writingSuggestionGroups).map(([group, items]) => (
                <div key={group} className="rounded-xl border border-slate-200 bg-white p-2.5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">
                    {group.replace(/_/g, ' ')}
                  </p>
                  <ul className="list-disc pl-4 space-y-1 text-xs text-slate-700">
                    {(items || []).slice(0, 5).map((item, idx) => (
                      <li key={`${item}-${idx}`}>{item}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}

          {writingSentenceEdits.length > 0 && (
            <div className="mt-3 rounded-xl border border-indigo-200 bg-indigo-50 p-3 space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-indigo-700">
                Sentence-Level Edits
              </p>
              <div className="space-y-2">
                {writingSentenceEdits.map((edit, idx) => (
                  <div key={`${edit.original}-${idx}`} className="rounded-lg border border-indigo-100 bg-white p-2.5">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Original</p>
                    <p className="text-sm text-slate-700">{edit.original}</p>
                    <p className="mt-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Improved</p>
                    <p className="text-sm text-slate-900">{edit.improved}</p>
                    {(edit.why || edit.evidence) && (
                      <p className="mt-1.5 text-xs text-slate-600">
                        {edit.why ? `Why: ${edit.why}` : ''}
                        {edit.evidence ? ` ${edit.why ? '| ' : ''}Evidence: ${edit.evidence}` : ''}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {Array.isArray(writingChecklist) && writingChecklist.length > 0 && (
            <div className="mt-3 rounded-xl border border-cyan-200 bg-cyan-50 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-cyan-700 mb-1">Revision checklist</p>
              <ul className="list-disc pl-4 space-y-1 text-xs text-cyan-900">
                {writingChecklist.map((item, idx) => (
                  <li key={`${item}-${idx}`}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {Array.isArray(writingDraftQuality?.notes) && writingDraftQuality?.notes?.length > 0 && (
            <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 mb-1">Quality notes</p>
              <ul className="list-disc pl-4 space-y-1 text-xs text-amber-800">
                {writingDraftQuality.notes.map((item, idx) => (
                  <li key={`${item}-${idx}`}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {rewriteExcerpt && (
            <div className="mt-3 rounded-xl border border-slate-200 bg-white p-3">
              <div className="flex items-center justify-between gap-2 mb-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Rewrite excerpt</p>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={applyRewriteToDraft}
                    className="text-xs font-semibold text-emerald-700 hover:underline"
                  >
                    Apply rewrite
                  </button>
                  <button
                    type="button"
                    onClick={() => void navigator.clipboard.writeText(rewriteExcerpt)}
                    className="text-xs font-semibold text-indigo-700 hover:underline"
                  >
                    Copy rewrite
                  </button>
                </div>
              </div>
              <p className="text-sm text-slate-700 whitespace-pre-wrap">{rewriteExcerpt}</p>
            </div>
          )}

          {writingSuggestionAnalysis && (
            <details className="mt-3 rounded-xl border border-slate-200 p-3">
              <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500">
                Full writing analysis
              </summary>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{writingSuggestionAnalysis}</p>
            </details>
          )}
        </section>

        {error && (
          <div className="studio-panel px-4 py-3 mb-4 text-sm text-red-700 border-red-200 bg-red-50 flex items-center gap-2">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        )}

        <section className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
          {(Object.entries(TOOL_CONFIG) as [ToolType, (typeof TOOL_CONFIG)[ToolType]][]).map(
            ([toolKey, config]) => {
              const Icon = config.icon;
              const isActive = activeTool === toolKey && !!result;
              return (
                <article key={toolKey} className="studio-panel p-4">
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div
                      className="studio-icon-chip"
                      style={{ background: `${config.color}1f`, color: config.color }}
                    >
                      <Icon className="h-4.5 w-4.5" />
                    </div>
                    {isActive && (
                      <span className="text-[11px] font-semibold px-2 py-1 rounded-full bg-emerald-50 text-emerald-700">
                        Complete
                      </span>
                    )}
                  </div>
                  <h4 className="text-sm font-semibold text-slate-900">{config.label}</h4>
                  <p className="text-xs text-slate-500 mt-1 min-h-[2.4rem]">{config.details}</p>
                  <button
                    onClick={() => runTool(toolKey)}
                    disabled={loadingTool || papers.length === 0}
                    className="mt-3 w-full rounded-xl px-3 py-2 text-sm font-semibold text-white inline-flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    style={{ background: `linear-gradient(120deg, ${config.color}, ${config.color}cc)` }}
                  >
                    {loadingTool && activeTool === toolKey ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Running...
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4" />
                        Run
                      </>
                    )}
                  </button>
                </article>
              );
            }
          )}
        </section>

        {result && (
          <section className="studio-surface p-4">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
              <h3 className="text-base font-semibold text-slate-900 inline-flex items-center gap-2">
                <CheckSquare className="h-4.5 w-4.5 text-emerald-600" />
                {activeTool ? TOOL_CONFIG[activeTool].label : 'AI Result'}
              </h3>
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-500 inline-flex items-center gap-1">
                  <Eye className="h-3.5 w-3.5" /> {detailLevel} / {focusMode}
                </span>
                <button onClick={copyResult} className="hero-btn-secondary">
                  <Copy className="h-4 w-4" />
                  Copy
                </button>
                <button onClick={downloadResult} className="hero-btn-secondary">
                  <Download className="h-4 w-4" />
                  Download
                </button>
              </div>
            </div>
            <div className="studio-panel-quiet p-3">
              <div className="whitespace-pre-wrap text-sm text-slate-700 font-sans leading-relaxed max-h-[520px] overflow-y-auto space-y-1">
                {result.split('\n').map((line, idx) => (
                  <p key={`line-${idx}`} className="m-0">
                    {renderInlineLinks(line)}
                  </p>
                ))}
              </div>
            </div>
            {copyNotice && (
              <p className="text-xs text-indigo-700 mt-2 font-semibold">{copyNotice}</p>
            )}
          </section>
        )}

        {!result && !loadingTool && (
          <section className="studio-panel-quiet p-8 text-center">
            <Wand2 className="h-8 w-8 text-indigo-400 mx-auto mb-2" />
            <p className="text-sm font-semibold text-slate-700">Run a tool to generate output</p>
            <p className="text-sm text-slate-500 mt-1">
              Select papers and execute summaries, insights, or a review draft.
            </p>
          </section>
        )}
      </div>
    </Layout>
  );
};

export default AITools;
