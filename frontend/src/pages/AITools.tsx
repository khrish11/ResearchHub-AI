import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import { FileText, Lightbulb, BookOpen, Play, Loader2, AlertCircle, Download, CheckSquare } from 'lucide-react';
import api from '../api';

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

const TOOL_CONFIG: Record<ToolType, { label: string; prompt: string; color: string; icon: React.FC<any> }> = {
  summaries: {
    label: 'AI Summaries',
    prompt: 'For each paper below, write a concise 3-sentence summary covering the goal, method, and key finding.\n\n',
    color: 'blue',
    icon: FileText,
  },
  insights: {
    label: 'Key Insights',
    prompt: 'Extract 4-6 cross-paper key insights, trends, and recurring themes from these research papers. Format as bullet points.\n\n',
    color: 'orange',
    icon: Lightbulb,
  },
  review: {
    label: 'Literature Review',
    prompt: 'Write a short structured literature review (Introduction, Themes, Gaps, Conclusion) synthesising the following papers.\n\n',
    color: 'green',
    icon: BookOpen,
  },
};

const colorMap: Record<string, { border: string; bg: string; btn: string; text: string }> = {
  blue: { border: 'border-blue-200', bg: 'bg-blue-100', btn: 'bg-blue-600 hover:bg-blue-700', text: 'text-blue-600' },
  orange: { border: 'border-orange-200', bg: 'bg-orange-100', btn: 'bg-orange-600 hover:bg-orange-700', text: 'text-orange-600' },
  green: { border: 'border-green-200', bg: 'bg-green-100', btn: 'bg-green-600 hover:bg-green-700', text: 'text-green-600' },
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
    api.get('/workspaces/').then((res) => {
      setWorkspaces(res.data);
      if (res.data.length > 0) setSelectedWsId(res.data[0].id);
    }).catch(() => { });
  }, []);

  useEffect(() => {
    if (!selectedWsId) return;
    setLoadingPapers(true);
    setSelectedIds(new Set());
    setResult('');
    api.get(`/workspaces/${selectedWsId}`)
      .then((res) => {
        const p: Paper[] = res.data.papers ?? [];
        setPapers(p);
        // Auto-select all
        setSelectedIds(new Set(p.map((x) => x.id)));
      })
      .catch(() => setError('Failed to load papers.'))
      .finally(() => setLoadingPapers(false));
  }, [selectedWsId]);

  const togglePaper = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const runTool = async (tool: ToolType) => {
    if (selectedIds.size === 0) { setError('Select at least one paper first.'); return; }
    if (!selectedWsId) return;
    setError(null);
    setActiveTool(tool);
    setLoadingTool(true);
    setResult('');

    const chosen = papers.filter((p) => selectedIds.has(p.id));
    // Cap each abstract to 800 chars to stay within token limits
    const context = chosen.map((p, i) =>
      `Paper ${i + 1}: ${p.title}\nAuthors: ${p.authors}\nAbstract: ${p.abstract.slice(0, 800)}`
    ).join('\n\n---\n\n');

    const { prompt } = TOOL_CONFIG[tool];
    const fullPrompt = prompt + context;

    try {
      const res = await api.post('/ai/analyze', { prompt: fullPrompt });
      setResult(res.data.response);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'AI tool failed. Please ensure the Groq key is set.');
    } finally {
      setLoadingTool(false);
    }
  };

  const downloadResult = () => {
    if (!result || !activeTool) return;
    const blob = new Blob([result], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${activeTool}_${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Layout>
      <div>
        <h1 className="text-3xl font-bold text-slate-900 mb-1">AI Tools</h1>
        <p className="text-slate-500 mb-6">Select papers from your workspace and run AI analysis on them.</p>

        {/* Workspace selector */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-5">
          <label className="block text-sm font-medium text-slate-700 mb-2">Workspace</label>
          <select
            value={selectedWsId ?? ''}
            onChange={(e) => setSelectedWsId(Number(e.target.value))}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-600"
          >
            {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </select>
        </div>

        {/* Paper selector */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold text-slate-900">Select Papers for Analysis</h2>
            {papers.length > 0 && (
              <div className="flex gap-3 text-xs">
                <button onClick={() => setSelectedIds(new Set(papers.map((p) => p.id)))} className="text-indigo-600 hover:underline">All</button>
                <button onClick={() => setSelectedIds(new Set())} className="text-slate-500 hover:underline">None</button>
              </div>
            )}
          </div>

          {loadingPapers ? (
            <div className="flex items-center gap-2 text-slate-400 text-sm py-4"><Loader2 className="h-4 w-4 animate-spin" /> Loading papers…</div>
          ) : papers.length === 0 ? (
            <p className="text-sm text-slate-400 py-4">No papers in this workspace. Import papers via Search or Upload PDF.</p>
          ) : (
            <div className="space-y-2 max-h-56 overflow-y-auto">
              {papers.map((p) => (
                <label key={p.id} className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${selectedIds.has(p.id) ? 'border-indigo-200 bg-indigo-50' : 'border-slate-200 hover:bg-slate-50'}`}>
                  <input
                    type="checkbox"
                    checked={selectedIds.has(p.id)}
                    onChange={() => togglePaper(p.id)}
                    className="mt-0.5 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-600"
                  />
                  <div>
                    <p className="text-sm font-medium text-slate-900 line-clamp-1">{p.title}</p>
                    <p className="text-xs text-slate-500">{p.authors}</p>
                  </div>
                </label>
              ))}
            </div>
          )}
          {papers.length > 0 && (
            <p className="mt-3 text-xs text-slate-400">{selectedIds.size} of {papers.length} paper(s) selected</p>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertCircle className="h-4 w-4 flex-shrink-0" /> {error}
          </div>
        )}

        {/* Tool cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-6">
          {(Object.entries(TOOL_CONFIG) as [ToolType, typeof TOOL_CONFIG[ToolType]][]).map(([key, cfg]) => {
            const c = colorMap[cfg.color];
            const Icon = cfg.icon;
            const isActive = activeTool === key && result;
            return (
              <div key={key} className={`bg-white rounded-xl border ${isActive ? `border-2 ${c.border}` : 'border-slate-200'} p-5`}>
                <div className="flex items-center gap-3 mb-4">
                  <div className={`p-2.5 ${c.bg} rounded-lg`}><Icon className={`h-5 w-5 ${c.text}`} /></div>
                  <div>
                    <h3 className="font-semibold text-slate-900 text-sm">{cfg.label}</h3>
                    {isActive && <p className="text-xs text-green-600 font-medium">✓ Complete</p>}
                  </div>
                </div>
                <button
                  onClick={() => runTool(key)}
                  disabled={loadingTool || papers.length === 0}
                  className={`w-full ${c.btn} text-white px-4 py-2.5 rounded-lg text-sm font-semibold transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  {loadingTool && activeTool === key ? (
                    <><Loader2 className="h-4 w-4 animate-spin" /> Running…</>
                  ) : (
                    <><Play className="h-4 w-4" /> Run {cfg.label}</>
                  )}
                </button>
              </div>
            );
          })}
        </div>

        {/* Results */}
        {result && (
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
                <CheckSquare className="h-5 w-5 text-green-600" />
                {activeTool ? TOOL_CONFIG[activeTool].label : 'Results'} — {selectedIds.size} paper(s)
              </h2>
              <button
                onClick={downloadResult}
                className="flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900 font-medium"
              >
                <Download className="h-4 w-4" /> Download
              </button>
            </div>
            <pre className="whitespace-pre-wrap text-sm text-slate-700 font-sans leading-relaxed bg-slate-50 rounded-lg p-4 max-h-96 overflow-y-auto">
              {result}
            </pre>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default AITools;
