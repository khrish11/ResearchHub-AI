import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  BookOpen,
  CheckSquare,
  Download,
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
}

interface Workspace {
  id: number;
  name: string;
}

type ToolType = 'summaries' | 'insights' | 'review';

const TOOL_CONFIG: Record<
  ToolType,
  { label: string; prompt: string; color: string; icon: LucideIcon; details: string }
> = {
  summaries: {
    label: 'AI Summaries',
    prompt:
      'For each paper below, create a detailed analysis with sections: Problem, Method, Data/Benchmarks, Key Results, Limitations, and Practical Takeaways. Use bullet points and cite [P#].\n\n',
    color: '#4f46e5',
    icon: FileText,
    details: 'Detailed per-paper breakdown with method, evidence, and limitations.',
  },
  insights: {
    label: 'Key Insights',
    prompt:
      'Extract 8-12 cross-paper insights, recurring themes, contradictions, and risk areas. Include confidence (High/Medium/Low) for each insight and cite [P#].\n\n',
    color: '#f97316',
    icon: Lightbulb,
    details: 'Cross-paper synthesis with contradictions, confidence, and next actions.',
  },
  review: {
    label: 'Literature Review',
    prompt:
      'Write a long-form structured literature review with sections: Introduction, Taxonomy of Methods, Comparative Findings, Gaps and Risks, Future Research Directions, and Execution Plan. Cite [P#] throughout.\n\n',
    color: '#059669',
    icon: BookOpen,
    details: 'Long-form review draft with evidence-grounded synthesis and roadmap.',
  },
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

  useEffect(() => {
    api
      .get('/workspaces/')
      .then((res) => {
        setWorkspaces(res.data);
        if (res.data.length > 0) {
          setSelectedWsId(res.data[0].id);
        }
      })
      .catch(() => {
        setWorkspaces([]);
      });
  }, []);

  useEffect(() => {
    if (!selectedWsId) {
      return;
    }
    setLoadingPapers(true);
    setSelectedIds(new Set());
    setResult('');
    setError(null);
    api
      .get(`/workspaces/${selectedWsId}`)
      .then((res) => {
        const workspacePapers: Paper[] = res.data.papers ?? [];
        setPapers(workspacePapers);
        setSelectedIds(new Set(workspacePapers.map((paper) => paper.id)));
      })
      .catch(() => setError('Failed to load papers.'))
      .finally(() => setLoadingPapers(false));
  }, [selectedWsId]);

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
          `[P${index + 1}] Title: ${paper.title}\nAuthors: ${paper.authors}\nAbstract: ${(paper.abstract || '').slice(0, 1800) || 'No abstract available.'}`
      )
      .join('\n\n---\n\n');

    const fullPrompt =
      `${TOOL_CONFIG[tool].prompt}` +
      'Use evidence-grounded statements and cite paper ids as [P#] for non-trivial claims.\n\n' +
      context;

    try {
      const res = await api.post('/ai/analyze', { prompt: fullPrompt, mode: tool });
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

  const totalAbstractChars = useMemo(
    () => papers.reduce((sum, paper) => sum + (paper.abstract?.length ?? 0), 0),
    [papers]
  );

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
              <button onClick={downloadResult} className="hero-btn-secondary">
                <Download className="h-4 w-4" />
                Download
              </button>
            </div>
            <div className="studio-panel-quiet p-3">
              <pre className="whitespace-pre-wrap text-sm text-slate-700 font-sans leading-relaxed max-h-[520px] overflow-y-auto">
                {result}
              </pre>
            </div>
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
