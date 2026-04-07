import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Loader2, Play, BrainCircuit, GitBranch, TrendingUp, FlaskConical, FileText, SearchCheck, Users, Sparkles, Copy, ExternalLink, Rocket, ShieldAlert, MessageSquare } from 'lucide-react';
import Layout from '../../components/Layout';
import api from '../../api';
import { apiErrorMessage } from '../../utils/apiError';
import type {
  AgentPanel,
  AiStatusResponse,
  ChatbotResult,
  ChatMessage,
  FullPipelineResult,
  GraphNode,
  GraphResponse,
  JsonRecord,
  Paper,
  Workspace,
} from './types';
import {
  LAST_WORKSPACE_KEY,
} from './storage';
import { nodeColor, qualityTone, toStringList } from './uiUtils';
import { useAgentPersistence } from './hooks/useAgentPersistence';

const JsonBlock: React.FC<{ value: unknown }> = ({ value }) => (
  <pre className="mt-3 max-h-80 overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700 whitespace-pre-wrap break-words">
    {JSON.stringify(value, null, 2)}
  </pre>
);

const Card: React.FC<{ title: string; subtitle?: string; children: React.ReactNode; icon?: React.ReactNode }> = ({
  title,
  subtitle,
  children,
  icon,
}) => (
  <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="flex items-start justify-between gap-3 mb-3">
      <div>
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
      </div>
      {icon && <div className="text-indigo-600">{icon}</div>}
    </div>
    {children}
  </section>
);

const Pill: React.FC<{ tone?: 'slate' | 'green' | 'amber' | 'rose' | 'indigo'; children: React.ReactNode }> = ({
  tone = 'slate',
  children,
}) => {
  const toneClass =
    tone === 'green'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
      : tone === 'amber'
      ? 'border-amber-200 bg-amber-50 text-amber-700'
      : tone === 'rose'
      ? 'border-rose-200 bg-rose-50 text-rose-700'
      : tone === 'indigo'
      ? 'border-indigo-200 bg-indigo-50 text-indigo-700'
      : 'border-slate-200 bg-slate-50 text-slate-700';
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${toneClass}`}>{children}</span>;
};

const GraphPreview: React.FC<{ graph: GraphResponse }> = ({ graph }) => {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [searchText, setSearchText] = useState('');
  const [minEdgeWeight, setMinEdgeWeight] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const panStartRef = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);
  const [visibleTypes, setVisibleTypes] = useState<Record<string, boolean>>({
    paper: true,
    concept: true,
    author: true,
    year: true,
    other: true,
  });
  const width = 980;
  const height = 460;

  const normalizeType = (node: GraphNode): string => {
    const raw = String(node.type || 'other').toLowerCase();
    if (raw === 'paper' || raw === 'concept' || raw === 'author' || raw === 'year') return raw;
    return 'other';
  };

  const allNodesById = useMemo(() => {
    const map = new Map<string, GraphNode>();
    for (const node of graph.nodes) map.set(node.id, node);
    return map;
  }, [graph.nodes]);

  const maxWeight = useMemo(
    () => Math.max(1, ...graph.edges.map((edge) => Number(edge.weight || 1))),
    [graph.edges]
  );

  const filteredGraph = useMemo(() => {
    const byTypeNodes = graph.nodes.filter((node) => visibleTypes[normalizeType(node)] !== false);
    const allowedNodeIds = new Set(byTypeNodes.map((node) => node.id));

    let edges = graph.edges.filter(
      (edge) =>
        allowedNodeIds.has(edge.source) &&
        allowedNodeIds.has(edge.target) &&
        Number(edge.weight || 1) >= minEdgeWeight
    );
    let nodes = byTypeNodes;

    const q = searchText.trim().toLowerCase();
    if (q) {
      const matchedIds = new Set(
        byTypeNodes
          .filter(
            (node) =>
              String(node.label || '').toLowerCase().includes(q) ||
              String(node.id || '').toLowerCase().includes(q)
          )
          .map((node) => node.id)
      );
      if (matchedIds.size > 0) {
        const includeIds = new Set<string>(matchedIds);
        for (const edge of edges) {
          if (matchedIds.has(edge.source) || matchedIds.has(edge.target)) {
            includeIds.add(edge.source);
            includeIds.add(edge.target);
          }
        }
        nodes = byTypeNodes.filter((node) => includeIds.has(node.id));
        const nextIds = new Set(nodes.map((node) => node.id));
        edges = edges.filter((edge) => nextIds.has(edge.source) && nextIds.has(edge.target));
      } else {
        nodes = [];
        edges = [];
      }
    }

    return { nodes, edges };
  }, [graph.edges, graph.nodes, minEdgeWeight, searchText, visibleTypes]);

  const points = useMemo(() => {
    const grouped = filteredGraph.nodes.reduce<Record<string, GraphNode[]>>((acc, node) => {
      const type = String(node.type || 'other').toLowerCase();
      if (!acc[type]) acc[type] = [];
      acc[type].push(node);
      return acc;
    }, {});
    const centers: Record<string, { x: number; y: number; radius: number }> = {
      paper: { x: 210, y: 210, radius: 110 },
      concept: { x: 490, y: 125, radius: 105 },
      author: { x: 780, y: 210, radius: 108 },
      year: { x: 490, y: 355, radius: 78 },
      other: { x: 800, y: 360, radius: 60 },
    };

    const layout = new Map<string, { x: number; y: number; node: GraphNode }>();
    Object.entries(grouped).forEach(([type, nodes]) => {
      const center = centers[type] || centers.other;
      nodes.forEach((node, index) => {
        const angle = (Math.PI * 2 * index) / Math.max(nodes.length, 1);
        layout.set(node.id, {
          node,
          x: center.x + Math.cos(angle) * center.radius,
          y: center.y + Math.sin(angle) * center.radius,
        });
      });
    });
    return layout;
  }, [filteredGraph.nodes]);

  useEffect(() => {
    if (!selectedNodeId && filteredGraph.nodes.length > 0) {
      setSelectedNodeId(filteredGraph.nodes[0].id);
      return;
    }
    if (selectedNodeId && !filteredGraph.nodes.some((node) => node.id === selectedNodeId)) {
      setSelectedNodeId(filteredGraph.nodes[0]?.id || null);
    }
  }, [filteredGraph.nodes, selectedNodeId]);

  const selectedNode = selectedNodeId ? allNodesById.get(selectedNodeId) || null : null;
  const selectedNodeEdges = useMemo(
    () =>
      selectedNodeId
        ? filteredGraph.edges.filter((edge) => edge.source === selectedNodeId || edge.target === selectedNodeId)
        : [],
    [filteredGraph.edges, selectedNodeId]
  );
  const neighborNodes = useMemo(() => {
    if (!selectedNodeId) return [];
    const seen = new Set<string>();
    const list: GraphNode[] = [];
    for (const edge of selectedNodeEdges) {
      const neighborId = edge.source === selectedNodeId ? edge.target : edge.source;
      if (seen.has(neighborId)) continue;
      seen.add(neighborId);
      const node = allNodesById.get(neighborId);
      if (node) list.push(node);
    }
    return list.slice(0, 10);
  }, [allNodesById, selectedNodeEdges, selectedNodeId]);

  const startPan = (event: React.MouseEvent<SVGSVGElement>) => {
    const target = event.target;
    if (target instanceof Element && target.closest('[data-node-id]')) return;
    panStartRef.current = { x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y };
    setIsPanning(true);
    event.preventDefault();
  };

  const updatePan = (event: React.MouseEvent<SVGSVGElement>) => {
    if (!panStartRef.current) return;
    const dx = event.clientX - panStartRef.current.x;
    const dy = event.clientY - panStartRef.current.y;
    setPan({
      x: panStartRef.current.panX + dx,
      y: panStartRef.current.panY + dy,
    });
  };

  const stopPan = () => {
    panStartRef.current = null;
    setIsPanning(false);
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
        <input
          value={searchText}
          onChange={(event) => setSearchText(event.target.value)}
          placeholder="Filter nodes by keyword"
          className="rounded-lg border border-slate-200 px-2.5 py-2 text-xs md:col-span-2"
        />
        <label className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-2.5 py-2 text-xs text-slate-600">
          Min edge weight
          <input
            type="range"
            min={1}
            max={maxWeight}
            step={1}
            value={minEdgeWeight}
            onChange={(event) => setMinEdgeWeight(Number(event.target.value) || 1)}
          />
          <span className="font-semibold text-slate-800">{minEdgeWeight}</span>
        </label>
        <div className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-2">
          <button
            type="button"
            onClick={() => setZoom((prev) => Math.max(0.7, Number((prev - 0.1).toFixed(2))))}
            className="rounded border border-slate-200 px-2 py-1 text-xs"
          >
            -
          </button>
          <span className="min-w-[56px] text-center text-xs font-semibold text-slate-700">
            {Math.round(zoom * 100)}%
          </span>
          <button
            type="button"
            onClick={() => setZoom((prev) => Math.min(1.7, Number((prev + 0.1).toFixed(2))))}
            className="rounded border border-slate-200 px-2 py-1 text-xs"
          >
            +
          </button>
          <button
            type="button"
            onClick={() => {
              setZoom(1);
              setPan({ x: 0, y: 0 });
            }}
            className="rounded border border-slate-200 px-2 py-1 text-xs text-slate-600"
          >
            Reset
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {(['paper', 'concept', 'author', 'year', 'other'] as const).map((type) => {
          const active = visibleTypes[type] !== false;
          return (
            <button
              key={type}
              type="button"
              onClick={() => setVisibleTypes((prev) => ({ ...prev, [type]: !active }))}
              className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${
                active
                  ? 'border-indigo-200 bg-indigo-50 text-indigo-700'
                  : 'border-slate-200 bg-white text-slate-500'
              }`}
            >
              {type}
            </button>
          );
        })}
        <Pill tone="indigo">Nodes {filteredGraph.nodes.length}</Pill>
        <Pill tone="green">Edges {filteredGraph.edges.length}</Pill>
      </div>

      <div className="overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-2">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className={`h-[360px] min-w-[860px] w-full ${isPanning ? 'cursor-grabbing' : 'cursor-grab'}`}
          onMouseDown={startPan}
          onMouseMove={updatePan}
          onMouseUp={stopPan}
          onMouseLeave={stopPan}
        >
          <rect x={0} y={0} width={width} height={height} fill="#f8fafc" />
          <g
            transform={`translate(${pan.x} ${pan.y}) translate(${width / 2} ${height / 2}) scale(${zoom}) translate(${-width / 2} ${-height / 2})`}
          >
            {filteredGraph.edges.map((edge, index) => {
              const source = points.get(edge.source);
              const target = points.get(edge.target);
              if (!source || !target) return null;
              const edgeWeight = Number(edge.weight || 1);
              return (
                <line
                  key={`${edge.source}-${edge.target}-${index}`}
                  x1={source.x}
                  y1={source.y}
                  x2={target.x}
                  y2={target.y}
                  stroke="#94a3b8"
                  strokeOpacity={0.45}
                  strokeWidth={Math.min(3.6, 0.9 + edgeWeight * 0.45)}
                />
              );
            })}
            {Array.from(points.values()).map(({ node, x, y }) => {
              const active = node.id === selectedNodeId;
              const matched =
                searchText.trim().length > 0 &&
                String(node.label || '').toLowerCase().includes(searchText.trim().toLowerCase());
              return (
                <g
                  key={node.id}
                  data-node-id={node.id}
                  onClick={() => setSelectedNodeId(node.id)}
                  className="cursor-pointer"
                >
                  <circle
                    cx={x}
                    cy={y}
                    r={active ? 9 : matched ? 8 : 6}
                    fill={nodeColor(node.type)}
                    stroke={active ? '#0f172a' : '#fff'}
                    strokeWidth={active ? 2.2 : 1.2}
                  />
                  <text x={x + 9} y={y + 4} fontSize={10.8} fill="#0f172a">
                    {String(node.label || '').slice(0, 34)}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      {selectedNode && (
        <div className="rounded-xl border border-slate-200 p-3 text-sm space-y-2">
          <p className="font-semibold text-slate-900">{selectedNode.label}</p>
          <div className="flex flex-wrap gap-2">
            <Pill tone="indigo">{selectedNode.type}</Pill>
            <Pill tone="slate">Connections {selectedNodeEdges.length}</Pill>
            {typeof selectedNode.metadata?.degree === 'number' && (
              <Pill tone="green">Degree {Number(selectedNode.metadata.degree)}</Pill>
            )}
          </div>
          {neighborNodes.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">Connected Nodes</p>
              <div className="flex flex-wrap gap-1.5">
                {neighborNodes.map((neighbor) => (
                  <button
                    key={neighbor.id}
                    type="button"
                    onClick={() => setSelectedNodeId(neighbor.id)}
                    className="rounded-full border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700"
                  >
                    {String(neighbor.label || '').slice(0, 30)}
                  </button>
                ))}
              </div>
            </div>
          )}
          {Boolean(selectedNode.metadata?.url) && (
            <a
              href={String(selectedNode.metadata?.url || '')}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-700"
            >
              Open paper
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
        </div>
      )}

      {graph.summary && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
          <p className="font-semibold uppercase tracking-wide text-slate-500 mb-2">Graph Highlights</p>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
            <div>
              <p className="font-semibold text-slate-800">Top Concepts</p>
              <p>
                {(graph.summary.top_concepts || []).slice(0, 3).map((item) => item.label).join(', ') || 'N/A'}
              </p>
            </div>
            <div>
              <p className="font-semibold text-slate-800">Top Authors</p>
              <p>
                {(graph.summary.top_authors || []).slice(0, 3).map((item) => item.label).join(', ') || 'N/A'}
              </p>
            </div>
            <div>
              <p className="font-semibold text-slate-800">Most Active Years</p>
              <p>
                {(graph.summary.top_years || []).slice(0, 3).map((item) => String(item.year)).join(', ') || 'N/A'}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const ResearchAgent: React.FC = () => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<number | null>(null);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [selectedPaperIds, setSelectedPaperIds] = useState<number[]>([]);
  const [goal, setGoal] = useState('Explore GNNs in cybersecurity after 2021');
  const [yearFrom, setYearFrom] = useState<number>(2021);
  const [draftText, setDraftText] = useState('Paper 1 shows robust gains in graph anomaly detection under constrained settings.');
  const [rawSmartReadText, setRawSmartReadText] = useState('');
  const [smartPaperId, setSmartPaperId] = useState<number | null>(null);
  const [activePanel, setActivePanel] = useState<AgentPanel>('overview');
  const [loadingKey, setLoadingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [outputs, setOutputs] = useState<Record<string, unknown>>({});
  const [aiStatus, setAiStatus] = useState<AiStatusResponse | null>(null);
  const [chatPrompt, setChatPrompt] = useState('What are the strongest contradictions in selected papers?');
  const [chatStyle, setChatStyle] = useState<'concise' | 'balanced' | 'deep'>('balanced');
  const [chatGroundedOnly, setChatGroundedOnly] = useState(true);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [includeAdvancedPipeline, setIncludeAdvancedPipeline] = useState(false);
  const [pipelineProgress, setPipelineProgress] = useState<{ current: number; total: number; label: string } | null>(null);
  const [resumeSelectedPaperIds, setResumeSelectedPaperIds] = useState<number[] | null>(null);

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
          setSelectedWorkspace(preferred || list[0].id);
        }
        const resumedGoal = String(sessionRes?.data?.last_query || '').trim();
        const resumedDraft = String(sessionRes?.data?.draft_text || '').trim();
        const resumedPanel = String(sessionRes?.data?.extra?.active_panel || '').trim().toLowerCase();
        const resumedYear = Number(sessionRes?.data?.extra?.year_from || 0);
        const resumedPaperIds = Array.isArray(sessionRes?.data?.extra?.selected_paper_ids)
          ? sessionRes.data.extra.selected_paper_ids
              .map((value: unknown) => Number(value))
              .filter((value: number) => Number.isFinite(value) && value > 0)
          : [];
        if (resumedGoal) setGoal(resumedGoal);
        if (resumedDraft) setDraftText(resumedDraft);
        if (resumedPaperIds.length > 0) setResumeSelectedPaperIds(resumedPaperIds);
        if (['overview', 'analysis', 'graph', 'generation', 'advanced'].includes(resumedPanel)) {
          setActivePanel(resumedPanel as AgentPanel);
        }
        if (resumedYear >= 1950 && resumedYear <= 2100) {
          setYearFrom(resumedYear);
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
    api
      .get<AiStatusResponse>('/ai/status')
      .then((res) => setAiStatus(res.data))
      .catch(() => setAiStatus({ enabled: false, model: null, error: 'Unable to fetch AI status.' }));
  }, []);

  useAgentPersistence({
    selectedWorkspace,
    resumeSelectedPaperIds,
    setPapers,
    setSelectedPaperIds,
    setSmartPaperId,
    chatHistory,
    setChatHistory,
    selectedPaperIds,
  });

  useEffect(() => {
    if (!selectedWorkspace) return;
    const timer = window.setTimeout(() => {
      void api
        .put('/workspaces/session-state', {
          page_path: '/research-agent',
          workspace_id: selectedWorkspace,
          last_query: goal.slice(0, 300),
          draft_text: draftText.slice(0, 12000),
          extra: {
            selected_paper_ids: selectedPaperIds,
            active_panel: activePanel,
            year_from: yearFrom,
          },
        })
        .catch(() => undefined);
    }, 800);
    return () => window.clearTimeout(timer);
  }, [activePanel, draftText, goal, selectedPaperIds, selectedWorkspace, yearFrom]);

  const togglePaper = (id: number) => {
    setSelectedPaperIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const runAction = async (key: string, request: () => Promise<{ data: unknown }>, outputKey?: string) => {
    setError(null);
    setLoadingKey(key);
    try {
      const res = await request();
      const bucket = outputKey || key;
      setOutputs((prev) => ({ ...prev, [bucket]: res.data }));
      return res.data;
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Request failed'));
      return null;
    } finally {
      setLoadingKey(null);
    }
  };

  const runFullPipeline = async () => {
    if (!selectedWorkspace || loadingKey) return;
    const estimatedSteps = includeAdvancedPipeline
      ? selectedPaperIds.length >= 2
        ? 13
        : 12
      : 9;
    setPipelineProgress({ current: 0, total: estimatedSteps, label: 'Running full pipeline...' });
    const payload = {
      workspace_id: selectedWorkspace,
      goal,
      year_from: yearFrom,
      paper_ids: selectedPaperIds,
      max_results: 120,
      import_top_n: 14,
      strict_mode: true,
      include_advanced: includeAdvancedPipeline,
    };
    const data = (await runAction(
      'full_pipeline',
      () => api.post('/research/full-pipeline', payload),
      'full_pipeline'
    )) as FullPipelineResult | null;
    if (data && data.results && typeof data.results === 'object') {
      setOutputs((prev) => ({ ...prev, ...(data.results as Record<string, unknown>) }));
      const completed = Array.isArray(data.steps_completed) ? data.steps_completed.length : 0;
      const planned = Array.isArray(data.planned_steps) ? data.planned_steps.length : estimatedSteps;
      setPipelineProgress({ current: completed, total: planned, label: 'Pipeline completed' });
      window.setTimeout(() => setPipelineProgress(null), 4000);
      return;
    }
    setPipelineProgress(null);
  };

  const runChatbot = async (explicitMessage?: string) => {
    if (!selectedWorkspace || loadingKey) return;
    const message = String(explicitMessage ?? chatPrompt).trim();
    if (!message) return;

    const userTurn: ChatMessage = { role: 'user', content: message, createdAt: new Date().toISOString() };
    const conversationSeed = [...chatHistory, userTurn].slice(-12);
    setChatHistory(conversationSeed);
    if (!explicitMessage) {
      setChatPrompt('');
    }

    const data = (await runAction(
      'chatbot',
      () =>
        api.post('/research/chatbot', {
          workspace_id: selectedWorkspace,
          paper_ids: selectedPaperIds,
          topic: goal,
          message,
          context_text: draftText,
          draft_text: draftText,
          response_style: chatStyle,
          grounded_only: chatGroundedOnly,
          max_actions: 8,
          conversation: conversationSeed.map((turn) => ({ role: turn.role, content: turn.content })),
        }),
      'chatbot'
    )) as ChatbotResult | null;

    if (data && typeof data.reply === 'string' && data.reply.trim()) {
      const assistantTurn: ChatMessage = {
        role: 'assistant',
        content: String(data.reply).trim(),
        createdAt: new Date().toISOString(),
      };
      setChatHistory((prev) => [...prev, assistantTurn].slice(-24));
    }
  };

  const canRunWorkspaceActions = useMemo(() => Boolean(selectedWorkspace), [selectedWorkspace]);
  const autonomous = outputs.autonomous as JsonRecord | undefined;
  const graph = outputs.graph as GraphResponse | undefined;
  const fullPipeline = outputs.full_pipeline as JsonRecord | undefined;
  const chatbotOutput = outputs.chatbot as JsonRecord | undefined;
  const smartReadOutput = outputs.smart_read as JsonRecord | undefined;
  const compareOutput = outputs.compare as JsonRecord | undefined;
  const feedOutput = outputs.feed as JsonRecord | undefined;
  const citationsOutput = outputs.citations as JsonRecord | undefined;
  const faultOutput = outputs.fault_detection as JsonRecord | undefined;
  const trendNarrative = String((outputs.trends as Record<string, unknown> | undefined)?.forecast_narrative || '').trim();
  const multiAgent = outputs.multi_agent as JsonRecord | undefined;
  const multiAgentOverall = (multiAgent?.overall_quality as JsonRecord | undefined) || {};
  const multiAgentPlan = (multiAgent?.orchestrated_plan_quality as JsonRecord | undefined) || {};
  const multiAgentAgentQuality = (multiAgent?.agent_quality as JsonRecord | undefined) || {};
  const multiAgentGrade = String(multiAgentOverall.grade || '').trim();
  const faultScore = Number(faultOutput?.quality_score || 0);
  const chatActions = Array.isArray(chatbotOutput?.actions) ? chatbotOutput.actions.map((action: unknown) => String(action)) : [];
  const chatCitations = Array.isArray(chatbotOutput?.citations) ? chatbotOutput.citations as Array<Record<string, unknown>> : [];
  const chatSuggestedQueries = Array.isArray(chatbotOutput?.suggested_queries)
    ? chatbotOutput.suggested_queries.map((query: unknown) => String(query))
    : [];
  const chatEvidenceMap = Array.isArray(chatbotOutput?.evidence_map)
    ? chatbotOutput.evidence_map.map((line: unknown) => String(line))
    : [];
  const chatConfidence = Number.isFinite(Number(chatbotOutput?.confidence))
    ? Number(chatbotOutput?.confidence)
    : null;
  const mergedChatActions = [...chatActions, ...chatSuggestedQueries]
    .filter(Boolean)
    .filter((value, index, source) => source.indexOf(value) === index);
  const compareRows = Array.isArray(compareOutput?.table) ? compareOutput.table as Array<Record<string, unknown>> : [];
  const compareColumns = Array.isArray(compareOutput?.columns) ? compareOutput.columns.map((item: unknown) => String(item)) : [];
  const feedPapers = Array.isArray(feedOutput?.trending_papers)
    ? feedOutput.trending_papers as Array<Record<string, unknown>>
    : [];
  const citationRows = Array.isArray(citationsOutput?.results)
    ? citationsOutput.results as Array<Record<string, unknown>>
    : [];
  const faultRows = Array.isArray(faultOutput?.faults) ? faultOutput.faults as Array<Record<string, unknown>> : [];
  const faultChecklist = Array.isArray(faultOutput?.verification_checklist)
    ? faultOutput.verification_checklist.map((item: unknown) => String(item))
    : [];
  const showOverview = activePanel === 'overview';
  const showAnalysis = activePanel === 'analysis';
  const showGraph = activePanel === 'graph';
  const showGeneration = activePanel === 'generation';
  const showAdvanced = activePanel === 'advanced';

  return (
    <Layout>
      <div className="space-y-4">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500 mb-1 inline-flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
            Agentic Research Stack
          </p>
          <h2 className="text-2xl font-bold text-slate-900">Research Agent Control Plane</h2>
          <p className="text-sm text-slate-500 mt-1">Run autonomous exploration, gap mining, graph intelligence, forecasting, drafting, and citation verification from one page.</p>

          <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
            <input
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="Research goal"
            />
            <input
              type="number"
              value={yearFrom}
              onChange={(e) => setYearFrom(Number(e.target.value) || 2021)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="Year from"
            />
            <select
              value={selectedWorkspace ?? ''}
              onChange={(e) => setSelectedWorkspace(e.target.value ? Number(e.target.value) : null)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            >
              {workspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name}
                </option>
              ))}
            </select>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void runFullPipeline()}
              disabled={!canRunWorkspaceActions || loadingKey !== null}
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {loadingKey === 'full_pipeline' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />}
              Run Full Pipeline
            </button>
            <label className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700">
              <input
                type="checkbox"
                checked={includeAdvancedPipeline}
                onChange={(event) => setIncludeAdvancedPipeline(event.target.checked)}
              />
              Include advanced tools (feed/citation/compare)
            </label>
            <Pill tone="indigo">{selectedPaperIds.length} selected papers</Pill>
            {multiAgentGrade && <Pill tone={qualityTone(multiAgentGrade)}>Agent quality {multiAgentGrade}</Pill>}
            {trendNarrative && <Pill tone="green">Trend forecast ready</Pill>}
            {faultScore > 0 && <Pill tone={faultScore >= 70 ? 'green' : faultScore >= 50 ? 'amber' : 'rose'}>Paper quality {faultScore}</Pill>}
          </div>

          {pipelineProgress && (
            <p className="mt-3 rounded-xl border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm text-indigo-700">
              {pipelineProgress.label} ({pipelineProgress.current}/{pipelineProgress.total})
            </p>
          )}
          {fullPipeline && (
            <div className="mt-3 space-y-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
              <p>
                Pipeline completed {Array.isArray(fullPipeline.steps_completed) ? fullPipeline.steps_completed.length : 0}
                /
                {Array.isArray(fullPipeline.planned_steps) ? fullPipeline.planned_steps.length : 0} steps
                {typeof fullPipeline.completion_ratio === 'number'
                  ? ` (${Math.round(fullPipeline.completion_ratio * 100)}%)`
                  : ''}
                .
              </p>
              {Array.isArray(fullPipeline.errors) && fullPipeline.errors.length > 0 && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-2 text-xs text-amber-800">
                  <p className="font-semibold">Recoverable step errors</p>
                  <ul className="mt-1 list-disc space-y-1 pl-4">
                    {fullPipeline.errors.slice(0, 5).map((err: unknown, index: number) => {
                      const e = (err || {}) as JsonRecord;
                      return (
                      <li key={`${String(e.step || 'step')}-${index}`}>
                        {String(e.step || 'step')}: {String(e.error || 'unknown error')}
                      </li>
                      );
                    })}
                  </ul>
                </div>
              )}
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            {[
              { key: 'overview', label: 'Autonomous' },
              { key: 'analysis', label: 'Analysis' },
              { key: 'graph', label: 'Graph' },
              { key: 'generation', label: 'Generation' },
              { key: 'advanced', label: 'Advanced' },
            ].map((item) => {
              const active = activePanel === (item.key as AgentPanel);
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setActivePanel(item.key as AgentPanel)}
                  className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
                    active
                      ? 'border-indigo-200 bg-indigo-50 text-indigo-700'
                      : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </div>

          {aiStatus && !aiStatus.enabled && (
            <p className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              AI generation is offline{aiStatus.error ? `: ${aiStatus.error}` : '.'} Configure `GROQ_API_KEY` and restart backend.
            </p>
          )}
          {aiStatus?.enabled && aiStatus.model && (
            <p className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
              AI model in use: {aiStatus.model}
            </p>
          )}
          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        </section>

        {showOverview && (
          <Card
            title="Autonomous Research Mode"
            subtitle="Goal -> search all sources -> rank -> import -> review/gaps/trends"
            icon={<BrainCircuit className="h-5 w-5" />}
          >
          <button
            onClick={() =>
              runAction('autonomous', () =>
                api.post('/research/autonomous-research', {
                  goal,
                  workspace_id: selectedWorkspace,
                  year_from: yearFrom,
                  max_results: 100,
                  import_top_n: 12,
                })
              )
            }
            disabled={!canRunWorkspaceActions || loadingKey !== null}
            className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {loadingKey === 'autonomous' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Run Autonomous Mode
          </button>
          {autonomous && (
            <div className="mt-3 space-y-3">
              <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Literature Review</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">
                    {String(autonomous.literature_review || '')}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Open Problems</p>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                    {toStringList(autonomous.open_problems)
                      .slice(0, 8)
                      .map((problem) => (
                        <li key={problem}>{problem}</li>
                      ))}
                  </ul>
                </div>
              </div>

              <details className="rounded-xl border border-slate-200 p-3">
                <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Raw autonomous payload
                </summary>
                <JsonBlock value={autonomous} />
              </details>
            </div>
          )}
          </Card>
        )}

        {(showAnalysis || showGraph || showGeneration) && (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {showAnalysis && (
            <Card title="Gap Detection Engine" subtitle="Contradictions, missing metrics, under-tested datasets" icon={<SearchCheck className="h-5 w-5" />}>
            <button
              onClick={() =>
                runAction('gaps', () =>
                  api.post('/research/gap-detection', {
                    workspace_id: selectedWorkspace,
                    paper_ids: selectedPaperIds,
                    topic: goal,
                  })
                )
              }
              disabled={!canRunWorkspaceActions || loadingKey !== null}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700"
            >
              {loadingKey === 'gaps' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Detect Gaps
            </button>
            {outputs.gaps ? (
              <div className="mt-3 space-y-3">
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Gap Analysis</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">
                    {String((outputs.gaps as Record<string, unknown>)?.analysis || '')}
                  </p>
                </div>
                <details className="rounded-xl border border-slate-200 p-3">
                  <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Raw gap payload
                  </summary>
                  <JsonBlock value={outputs.gaps} />
                </details>
              </div>
            ) : null}
            </Card>
          )}

          {showGraph && (
            <Card title="Interactive Knowledge Graph Data" subtitle="Citation-likely edges, concept graph, author map, timeline" icon={<GitBranch className="h-5 w-5" />}>
            <button
              onClick={() => runAction('graph', () => api.get('/research/knowledge-graph', { params: { workspace_id: selectedWorkspace, paper_limit: 80 } }))}
              disabled={!canRunWorkspaceActions || loadingKey !== null}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700"
            >
              {loadingKey === 'graph' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Build Graph
            </button>
            {graph && (
              <div className="mt-3 space-y-3">
                <div className="flex flex-wrap gap-2">
                  <Pill tone="indigo">Nodes {graph.nodes?.length || 0}</Pill>
                  <Pill tone="green">Edges {graph.edges?.length || 0}</Pill>
                </div>
                <GraphPreview graph={graph} />
              </div>
            )}
            </Card>
          )}

          {showAnalysis && (
            <Card title="Multi-Agent AI" subtitle="Literature/Insight/Gap/Methodology/Writing/Reviewer agents" icon={<Users className="h-5 w-5" />}>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() =>
                  runAction('multi_agent', () =>
                    api.post('/research/multi-agent-analysis', {
                      workspace_id: selectedWorkspace,
                      paper_ids: selectedPaperIds,
                      topic: goal,
                      strict_mode: false,
                    })
                  )
                }
                disabled={!canRunWorkspaceActions || loadingKey !== null}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700"
              >
                {loadingKey === 'multi_agent' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Run Agents
              </button>
              <button
                onClick={() =>
                  runAction('multi_agent_strict', () =>
                    api.post('/research/multi-agent-analysis', {
                      workspace_id: selectedWorkspace,
                      paper_ids: selectedPaperIds,
                      topic: goal,
                      strict_mode: true,
                    }),
                    'multi_agent'
                  )
                }
                disabled={!canRunWorkspaceActions || loadingKey !== null}
                className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {loadingKey === 'multi_agent_strict' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Regenerate Strict
              </button>
            </div>
            {outputs.multi_agent ? (
              <div className="mt-3 space-y-3">
                <div className="flex flex-wrap gap-2">
                  <Pill tone={qualityTone(String(multiAgentOverall.grade || ''))}>
                    Quality {String(multiAgentOverall.grade || 'unknown')}
                  </Pill>
                  <Pill tone="indigo">
                    Avg agent score {Number(multiAgentOverall.avg_agent_score || 0)}
                  </Pill>
                  <Pill tone="slate">
                    Plan score {Number(multiAgentPlan.score || 0)}
                  </Pill>
                  <Pill tone="slate">
                    Mode {multiAgent?.strict_mode ? 'Strict' : 'Standard'}
                  </Pill>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Orchestrated Plan</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">
                    {String((outputs.multi_agent as Record<string, unknown>)?.orchestrated_plan || '')}
                  </p>
                </div>
                {Boolean(multiAgent?.agent_quality) && (
                  <div className="rounded-xl border border-slate-200 p-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Per-agent Quality</p>
                    <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
                      {Object.entries(multiAgentAgentQuality).map(([agent, quality]) => {
                        const qualityRecord = (quality || {}) as JsonRecord;
                        const stats = (qualityRecord.stats as JsonRecord | undefined) || {};
                        return (
                        <div key={agent} className="rounded-lg border border-slate-200 bg-slate-50 p-2">
                          <div className="flex items-center justify-between gap-2">
                            <p className="text-sm font-semibold text-slate-800">{agent.replace(/_/g, ' ')}</p>
                            <Pill tone={qualityTone(String(qualityRecord.label || ''))}>
                              {String(qualityRecord.label || 'unknown')} {Number(qualityRecord.score || 0)}
                            </Pill>
                          </div>
                          <p className="mt-1 text-xs text-slate-500">
                            refs {Number(stats.paper_refs || 0)} | bullets {Number(stats.bullets || 0)} | chars {Number(stats.chars || 0)}
                          </p>
                        </div>
                        );
                      })}
                    </div>
                  </div>
                )}
                <details className="rounded-xl border border-slate-200 p-3">
                  <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Agent outputs
                  </summary>
                  <JsonBlock value={(outputs.multi_agent as Record<string, unknown>)?.agents || {}} />
                </details>
              </div>
            ) : null}
            </Card>
          )}

          {showAnalysis && (
            <Card
              title="Research Chatbot"
              subtitle="Ask broad or paper-grounded questions, like a full research copilot"
              icon={<MessageSquare className="h-5 w-5" />}
            >
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                <select
                  value={chatStyle}
                  onChange={(event) => setChatStyle(event.target.value as 'concise' | 'balanced' | 'deep')}
                  className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
                >
                  <option value="concise">Concise</option>
                  <option value="balanced">Balanced</option>
                  <option value="deep">Deep</option>
                </select>
                <label className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={chatGroundedOnly}
                    onChange={(event) => setChatGroundedOnly(event.target.checked)}
                  />
                  Grounded to selected papers only
                </label>
                <button
                  type="button"
                  onClick={() => setChatHistory([])}
                  className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700"
                >
                  Clear chat
                </button>
              </div>

              <div className="mt-3 max-h-72 space-y-2 overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3">
                {chatHistory.length === 0 ? (
                  <p className="text-sm text-slate-500">Start a conversation to get evidence-grounded answers from your workspace papers.</p>
                ) : (
                  chatHistory.map((turn, index) => (
                    <div
                      key={`${turn.role}-${turn.createdAt}-${index}`}
                      className={`rounded-lg px-3 py-2 text-sm ${
                        turn.role === 'user'
                          ? 'ml-6 border border-indigo-100 bg-indigo-50 text-indigo-900'
                          : 'mr-6 border border-slate-200 bg-white text-slate-800'
                      }`}
                    >
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                        {turn.role === 'user' ? 'You' : 'Research Agent'}
                      </p>
                      <p className="mt-1 whitespace-pre-wrap">{turn.content}</p>
                    </div>
                  ))
                )}
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                {mergedChatActions.slice(0, 6).map((action) => (
                  <button
                    key={action}
                    type="button"
                    onClick={() => void runChatbot(action)}
                    disabled={loadingKey !== null}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700"
                  >
                    {action}
                  </button>
                ))}
              </div>

              {chatConfidence !== null && (
                <div className="mt-3">
                  <Pill tone="green">Confidence {Math.round(chatConfidence * 100)}%</Pill>
                </div>
              )}

              {chatCitations.length > 0 && (
                <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Citations Used</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {chatCitations.slice(0, 8).map((citation, index) => (
                      <Pill key={`${String(citation.label || 'Paper')}-${index}`} tone="slate">
                        {String(citation.label || `Paper ${index + 1}`)}
                      </Pill>
                    ))}
                  </div>
                </div>
              )}

              {chatEvidenceMap.length > 0 && (
                <div className="mt-3 rounded-xl border border-cyan-200 bg-cyan-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-cyan-700">Evidence Map</p>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-cyan-900">
                    {chatEvidenceMap.slice(0, 8).map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="mt-3 flex gap-2">
                <input
                  value={chatPrompt}
                  onChange={(event) => setChatPrompt(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault();
                      void runChatbot();
                    }
                  }}
                  placeholder="Ask any research question..."
                  className="flex-1 rounded-xl border border-slate-200 px-3 py-2 text-sm"
                />
                <button
                  onClick={() => void runChatbot()}
                  disabled={!canRunWorkspaceActions || loadingKey !== null}
                  className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {loadingKey === 'chatbot' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                  Send
                </button>
              </div>
            </Card>
          )}

          {showAnalysis && (
            <Card title="Trend Prediction" subtitle="Publication growth, keyword momentum, 3-year forecast" icon={<TrendingUp className="h-5 w-5" />}>
            <button
              onClick={() =>
                runAction('trends', () =>
                  api.post('/research/trend-prediction', {
                    workspace_id: selectedWorkspace,
                    query: goal,
                    max_results: 100,
                  })
                )
              }
              disabled={loadingKey !== null}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700"
            >
              {loadingKey === 'trends' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Predict Trends
            </button>
            {outputs.trends ? (
              <div className="mt-3 space-y-3">
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Forecast Narrative</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">
                    {String((outputs.trends as Record<string, unknown>)?.forecast_narrative || '')}
                  </p>
                </div>
                <details className="rounded-xl border border-slate-200 p-3">
                  <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Trend data
                  </summary>
                  <JsonBlock value={(outputs.trends as Record<string, unknown>)?.trend_data || {}} />
                </details>
              </div>
            ) : null}
            </Card>
          )}

          {showGeneration && (
            <Card title="Experiment Design Generator" subtitle="Datasets, metrics, baselines, stack, hardware" icon={<FlaskConical className="h-5 w-5" />}>
            <button
              onClick={() =>
                runAction('experiment', () =>
                  api.post('/research/experiment-design', {
                    workspace_id: selectedWorkspace,
                    paper_ids: selectedPaperIds,
                    topic: goal,
                  })
                )
              }
              disabled={!canRunWorkspaceActions || loadingKey !== null}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700"
            >
              {loadingKey === 'experiment' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Design Experiment
            </button>
            {outputs.experiment ? (
              <div className="mt-3 space-y-2">
                <p className="max-h-80 overflow-auto whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                  {String((outputs.experiment as Record<string, unknown>)?.experiment_design || '')}
                </p>
                <details className="rounded-xl border border-slate-200 p-3">
                  <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Raw experiment payload
                  </summary>
                  <JsonBlock value={outputs.experiment} />
                </details>
              </div>
            ) : null}
            </Card>
          )}

          {showGeneration && (
            <Card title="Journal-Aware Paper Writer" subtitle="IEEE/Springer/Elsevier style draft generation" icon={<FileText className="h-5 w-5" />}>
            <button
              onClick={() =>
                runAction('paper_draft', () =>
                  api.post('/research/paper-draft', {
                    workspace_id: selectedWorkspace,
                    paper_ids: selectedPaperIds,
                    topic: goal,
                    target_format: 'IEEE',
                    citation_style: 'IEEE',
                  })
                )
              }
              disabled={!canRunWorkspaceActions || loadingKey !== null}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700"
            >
              {loadingKey === 'paper_draft' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Draft Paper
            </button>
            {outputs.paper_draft ? (
              <div className="mt-3 space-y-2">
                <button
                  type="button"
                  onClick={() => {
                    const draft = String((outputs.paper_draft as Record<string, unknown>)?.draft || '');
                    if (draft) void navigator.clipboard.writeText(draft);
                  }}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700"
                >
                  <Copy className="h-3.5 w-3.5" />
                  Copy Draft
                </button>
                <p className="max-h-80 overflow-auto whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                  {String((outputs.paper_draft as Record<string, unknown>)?.draft || '')}
                </p>
              </div>
            ) : null}
            </Card>
          )}
        </div>
        )}

        {showAdvanced && (
          <Card title="Smart Reading + Comparator + Feed + Citation Verifier" subtitle="Advanced intelligence operations" icon={<BrainCircuit className="h-5 w-5" />}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <select
              value={smartPaperId ?? ''}
              onChange={(e) => setSmartPaperId(e.target.value ? Number(e.target.value) : null)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="">Select paper for Smart Read</option>
              {papers.map((paper) => (
                <option key={paper.id} value={paper.id}>
                  {paper.title}
                </option>
              ))}
            </select>
            <input
              value={rawSmartReadText}
              onChange={(e) => setRawSmartReadText(e.target.value)}
              placeholder="Optional raw text for Smart Read"
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            />
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <button
              onClick={() =>
                runAction('smart_read', () =>
                  api.post('/research/smart-read', {
                    workspace_id: selectedWorkspace,
                    paper_id: smartPaperId,
                    text: rawSmartReadText || undefined,
                  })
                )
              }
              disabled={!canRunWorkspaceActions || loadingKey !== null}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700"
            >
              Smart Read
            </button>

            <button
              onClick={() =>
                runAction('compare', () =>
                  api.post('/research/compare-papers', {
                    workspace_id: selectedWorkspace,
                    paper_ids: selectedPaperIds.slice(0, 5),
                  })
                )
              }
              disabled={!canRunWorkspaceActions || selectedPaperIds.length < 2 || loadingKey !== null}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700"
            >
              Compare Papers
            </button>

            <button
              onClick={() =>
                runAction('feed', () =>
                  api.post('/research/personalized-feed', {
                    workspace_id: selectedWorkspace,
                    max_suggestions: 12,
                    force_live: true,
                    refresh_seed: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                  })
                )
              }
              disabled={!canRunWorkspaceActions || loadingKey !== null}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700"
            >
              Personalized Feed
            </button>

            <button
              onClick={() =>
                runAction('citations', () =>
                  api.post('/research/verify-citations', {
                    workspace_id: selectedWorkspace,
                    paper_ids: selectedPaperIds,
                    draft_text: draftText,
                  })
                )
              }
              disabled={!canRunWorkspaceActions || loadingKey !== null}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700"
            >
              Verify Citations
            </button>

            <button
              onClick={() =>
                runAction('fault_detection', () =>
                  api.post('/research/fault-detection', {
                    workspace_id: selectedWorkspace,
                    paper_id: smartPaperId,
                  })
                )
              }
              disabled={!canRunWorkspaceActions || !smartPaperId || loadingKey !== null}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700"
            >
              Detect Paper Faults
            </button>
          </div>

          <textarea
            value={draftText}
            onChange={(e) => setDraftText(e.target.value)}
            className="mt-3 w-full min-h-[90px] rounded-xl border border-slate-200 px-3 py-2 text-sm"
            placeholder="Paste draft text with claims/citations for authenticity checks"
          />

          <div className="mt-3 space-y-4">
            {smartReadOutput && (
              <div className="space-y-2 rounded-xl border border-slate-200 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Smart Read</p>
                <div className="flex flex-wrap gap-2">
                  <Pill tone="indigo">{String(smartReadOutput.source || 'paper')}</Pill>
                  <Pill tone="slate">{String(smartReadOutput.title || 'Untitled')}</Pill>
                </div>
                {smartReadOutput.extraction ? (
                  <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                    {['contributions', 'claims', 'datasets', 'equations', 'limitations'].map((field) => (
                      <div key={field} className="rounded-lg border border-slate-200 bg-slate-50 p-2">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{field}</p>
                        <p className="mt-1 text-xs text-slate-700">
                          {Array.isArray((smartReadOutput.extraction as Record<string, unknown>)[field])
                            ? ((smartReadOutput.extraction as Record<string, unknown>)[field] as unknown[])
                                .map((item) => String(item))
                                .filter(Boolean)
                                .slice(0, 3)
                                .join(' | ')
                            : String((smartReadOutput.extraction as Record<string, unknown>)[field] || 'Not detected')}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : null}
                <p className="whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                  {String(smartReadOutput.analysis || '')}
                </p>
              </div>
            )}

            {compareOutput && (
              <div className="space-y-2 rounded-xl border border-slate-200 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Paper Comparator</p>
                {compareColumns.length > 0 && (
                  <div className="overflow-auto rounded-xl border border-slate-200">
                    <table className="min-w-full text-left text-xs">
                      <thead className="bg-slate-50">
                        <tr>
                          <th className="px-2 py-2 font-semibold text-slate-600">Feature</th>
                          {compareColumns.map((column) => (
                            <th key={column} className="px-2 py-2 font-semibold text-slate-600">
                              {column}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {compareRows.map((row, index) => {
                          const values = Array.isArray((row as Record<string, unknown>)?.values)
                            ? ((row as Record<string, unknown>).values as unknown[])
                            : [];
                          return (
                            <tr key={`${String((row as Record<string, unknown>)?.feature || 'row')}-${index}`} className="border-t border-slate-100">
                              <td className="px-2 py-2 font-medium text-slate-700">{String((row as Record<string, unknown>)?.feature || '-')}</td>
                              {compareColumns.map((column, columnIndex) => (
                                <td key={`${column}-${columnIndex}`} className="px-2 py-2 text-slate-600">
                                  {String(values[columnIndex] || '-')}
                                </td>
                              ))}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
                <p className="whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                  {String(compareOutput.analysis || '')}
                </p>
              </div>
            )}

            {feedOutput && (
              <div className="space-y-2 rounded-xl border border-slate-200 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Personalized Feed</p>
                <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                  {feedPapers.slice(0, 8).map((paper, index) => {
                    const url = String(paper.url || (paper.doi ? `https://doi.org/${paper.doi}` : '') || '');
                    return (
                      <div key={`${String(paper.title || 'paper')}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 p-2">
                        <p className="text-sm font-semibold text-slate-800">{String(paper.title || 'Untitled')}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {String(paper.source || 'source')} | {String(paper.year || 'n/a')}
                        </p>
                        {url && (
                          <a href={url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-indigo-700">
                            Open paper
                            <ExternalLink className="h-3.5 w-3.5" />
                          </a>
                        )}
                      </div>
                    );
                  })}
                </div>
                <p className="whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                  {String(feedOutput.weekly_digest || '')}
                </p>
              </div>
            )}

            {citationsOutput && (
              <div className="space-y-2 rounded-xl border border-slate-200 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Citation Authenticity</p>
                <div className="flex flex-wrap gap-2">
                  <Pill tone="indigo">Claims {Number(citationsOutput.claims_analyzed || 0)}</Pill>
                  <Pill tone="green">Supported {Number(citationsOutput.supported_claims || 0)}</Pill>
                  <Pill tone="amber">Outdated {Number(citationsOutput.outdated_flags || 0)}</Pill>
                </div>
                <div className="space-y-2">
                  {citationRows.slice(0, 6).map((row, index) => (
                    <div key={`${String(row.claim || 'claim')}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 p-2">
                      <p className="text-sm text-slate-800">{String(row.claim || '')}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {String(row.recommendation || '')}
                        {' | '}
                        score {String(row.support_score || 0)}
                      </p>
                    </div>
                  ))}
                </div>
                <p className="whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                  {String(citationsOutput.summary || '')}
                </p>
              </div>
            )}

            {faultOutput && (
              <div className="space-y-2 rounded-xl border border-slate-200 p-3">
                <p className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <ShieldAlert className="h-3.5 w-3.5 text-rose-500" />
                  Fault Detection
                </p>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  <Pill tone="rose">Risk {Number(faultOutput.risk_score || 0)}</Pill>
                  <Pill tone="green">Quality {Number(faultOutput.quality_score || 0)}</Pill>
                  <Pill tone="slate">Tier {String(faultOutput.quality_tier || 'unknown')}</Pill>
                </div>
                {faultRows.length > 0 && (
                  <div className="space-y-2">
                    {faultRows.slice(0, 5).map((fault, index) => (
                      <div key={`${String(fault.fault_type || 'fault')}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 p-2">
                        <p className="text-sm font-semibold text-slate-800">{String(fault.fault_type || 'issue')}</p>
                        <p className="mt-1 text-xs text-slate-600">{String(fault.evidence || '')}</p>
                        <p className="mt-1 text-xs text-slate-500">Action: {String(fault.recommendation || '')}</p>
                      </div>
                    ))}
                  </div>
                )}
                {faultChecklist.length > 0 && (
                  <ul className="list-disc space-y-1 pl-5 text-xs text-slate-700">
                    {faultChecklist.slice(0, 6).map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                )}
                <p className="whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                  {String(faultOutput.analysis || '')}
                </p>
              </div>
            )}
          </div>
          </Card>
        )}

        <Card title="Paper Selection" subtitle="Used by comparison, gap detection, drafting, and verification">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-56 overflow-auto">
            {papers.map((paper) => (
              <label key={paper.id} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-2 py-1.5 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={selectedPaperIds.includes(paper.id)}
                  onChange={() => togglePaper(paper.id)}
                />
                <span className="truncate">{paper.title}</span>
              </label>
            ))}
          </div>
        </Card>
      </div>
    </Layout>
  );
};

export default ResearchAgent;

