import { useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent, type ReactNode } from 'react';
import {
  CheckCircle2,
  Crosshair,
  Download,
  FileSearch,
  FileText,
  Loader2,
  RefreshCw,
  Sparkles,
  Wand2,
  Workflow,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';
import { apiErrorMessage } from '../utils/apiError';

interface Workspace {
  id: number;
  name: string;
  description?: string;
}

interface WorkspacePaper {
  id: number;
  title: string;
  authors: string;
  abstract: string;
}

interface WorkspaceDetail {
  id: number;
  name: string;
  papers: WorkspacePaper[];
}

interface ReportPreviewResponse {
  workspace_id: number;
  workspace_name: string;
  topic: string;
  depth: string;
  focus_mode: string;
  paper_count: number;
  selected_paper_ids: number[];
  generated_at: string;
  markdown: string;
  mindmap_nodes?: Array<{ id: string; label: string; depth: number; parent_id?: string | null }>;
  paper_links?: Array<{
    paper: string;
    index: number;
    title: string;
    url?: string | null;
    doi?: string | null;
    link_available: boolean;
  }>;
}

interface MindmapNode {
  id: string;
  label: string;
  depth: number;
  parent_id?: string | null;
}

interface MindmapLayoutNode extends MindmapNode {
  x: number;
  y: number;
  side: 'left' | 'right' | 'center';
}

interface MindmapLayoutEdge {
  from: string;
  to: string;
}

type ReportDepth = 'quick' | 'balanced' | 'deep';
type ReportFocus = 'broad' | 'methods' | 'applications' | 'risks';

const DEPTH_OPTIONS: Array<{ value: ReportDepth; label: string; desc: string }> = [
  { value: 'quick', label: 'Quick Scan', desc: 'Fast overview for orientation.' },
  { value: 'balanced', label: 'Balanced', desc: 'Recommended depth for most reports.' },
  { value: 'deep', label: 'Deep Review', desc: 'Long-form synthesis with richer detail.' },
];

const FOCUS_OPTIONS: Array<{ value: ReportFocus; label: string; desc: string }> = [
  { value: 'broad', label: 'Broad', desc: 'Balanced analysis across all angles.' },
  { value: 'methods', label: 'Methods', desc: 'Methodology and benchmark emphasis.' },
  { value: 'applications', label: 'Applications', desc: 'Real-world usage and deployment focus.' },
  { value: 'risks', label: 'Risks', desc: 'Uncertainty, caveats, and failure modes.' },
];

const TOPIC_TEMPLATES = [
  'State-of-the-art synthesis for {workspace}',
  'Method comparison and gaps in {workspace}',
  'Applied engineering roadmap for {workspace}',
  'Risk and limitation analysis for {workspace}',
];

const MAX_VISIBLE_PAPERS = 18;
const MINDMAP_CANVAS_WIDTH = 1200;
const MINDMAP_CANVAS_HEIGHT = 700;

const wrapLabel = (label: string, maxChars = 18, maxLines = 3): string[] => {
  const words = String(label || '').trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return ['Untitled'];
  const lines: string[] = [];
  let current = '';
  for (const word of words) {
    const next = current ? `${current} ${word}` : word;
    if (next.length <= maxChars) {
      current = next;
      continue;
    }
    if (current) {
      lines.push(current);
      current = word;
    } else {
      lines.push(word.slice(0, maxChars));
      current = word.slice(maxChars);
    }
    if (lines.length >= maxLines) break;
  }
  if (lines.length < maxLines && current) lines.push(current);
  return lines.slice(0, maxLines);
};

const buildMindmapLayout = (nodes: MindmapNode[]) => {
  if (!Array.isArray(nodes) || nodes.length === 0) {
    return { nodes: [] as MindmapLayoutNode[], edges: [] as MindmapLayoutEdge[] };
  }

  const byId = new Map(nodes.map((node) => [node.id, node]));
  const childrenMap = new Map<string, MindmapNode[]>();
  for (const node of nodes) {
    if (node.parent_id && byId.has(node.parent_id)) {
      const arr = childrenMap.get(node.parent_id) || [];
      arr.push(node);
      childrenMap.set(node.parent_id, arr);
    }
  }
  const sortedChildren = (nodeId: string): MindmapNode[] =>
    [...(childrenMap.get(nodeId) || [])].sort((a, b) => String(a.id).localeCompare(String(b.id)));

  const root = nodes.find((node) => !node.parent_id || !byId.has(String(node.parent_id))) || nodes[0];
  const weightMemo = new Map<string, number>();
  const subtreeWeight = (nodeId: string): number => {
    if (weightMemo.has(nodeId)) return weightMemo.get(nodeId) || 1;
    const kids = sortedChildren(nodeId);
    if (kids.length === 0) {
      weightMemo.set(nodeId, 1);
      return 1;
    }
    const total = Math.max(1, kids.reduce((sum, child) => sum + subtreeWeight(child.id), 0));
    weightMemo.set(nodeId, total);
    return total;
  };

  const placed = new Map<string, MindmapLayoutNode>();
  placed.set(root.id, { ...root, x: 50, y: 50, side: 'center' });

  const firstLevel = sortedChildren(root.id);
  const leftRoots: MindmapNode[] = [];
  const rightRoots: MindmapNode[] = [];
  firstLevel.forEach((node, index) => {
    if (index % 2 === 0) rightRoots.push(node);
    else leftRoots.push(node);
  });

  const placeSubtree = (
    node: MindmapNode,
    side: 'left' | 'right',
    level: number,
    yStart: number,
    yEnd: number
  ) => {
    const sign = side === 'right' ? 1 : -1;
    const centerY = (yStart + yEnd) / 2;
    const x = Math.max(7, Math.min(93, 50 + sign * (16 + (level - 1) * 14)));
    const y = Math.max(8, Math.min(92, centerY));
    placed.set(node.id, { ...node, x, y, side });

    const kids = sortedChildren(node.id);
    if (kids.length === 0) return;
    const total = kids.reduce((sum, child) => sum + subtreeWeight(child.id), 0) || 1;
    let cursor = yStart;
    for (const child of kids) {
      const span = ((yEnd - yStart) * subtreeWeight(child.id)) / total;
      placeSubtree(child, side, level + 1, cursor, cursor + span);
      cursor += span;
    }
  };

  const placeSideRoots = (roots: MindmapNode[], side: 'left' | 'right') => {
    if (roots.length === 0) return;
    const total = roots.reduce((sum, node) => sum + subtreeWeight(node.id), 0) || 1;
    let cursor = 10;
    const range = 80;
    for (const node of roots) {
      const span = (range * subtreeWeight(node.id)) / total;
      placeSubtree(node, side, 1, cursor, cursor + span);
      cursor += span;
    }
  };

  placeSideRoots(leftRoots, 'left');
  placeSideRoots(rightRoots, 'right');

  for (const node of nodes) {
    if (!placed.has(node.id)) {
      placed.set(node.id, { ...node, x: 50, y: 90, side: 'center' });
    }
  }

  const edges: MindmapLayoutEdge[] = [];
  for (const node of nodes) {
    if (node.parent_id && placed.has(node.parent_id) && placed.has(node.id)) {
      edges.push({ from: node.parent_id, to: node.id });
    }
  }

  return {
    nodes: Array.from(placed.values()),
    edges,
  };
};

const nodeStyle = (node: MindmapLayoutNode) => {
  if (node.side === 'center') return { fill: '#a78bfa', stroke: '#7c3aed', text: '#ffffff' };
  if (node.depth <= 1) return { fill: '#fecaca', stroke: '#fca5a5', text: '#334155' };
  if (node.depth === 2) return { fill: '#bbf7d0', stroke: '#86efac', text: '#334155' };
  if (node.depth === 3) return { fill: '#bfdbfe', stroke: '#93c5fd', text: '#334155' };
  return { fill: '#e9d5ff', stroke: '#d8b4fe', text: '#334155' };
};

const serializeSvg = (svg: SVGSVGElement): string => {
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  clone.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');
  const serializer = new XMLSerializer();
  return serializer.serializeToString(clone);
};

const Mindmap = () => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  const [selectedWorkspaceDetail, setSelectedWorkspaceDetail] = useState<WorkspaceDetail | null>(null);
  const [topic, setTopic] = useState('');
  const [depth, setDepth] = useState<ReportDepth>('balanced');
  const [focusMode, setFocusMode] = useState<ReportFocus>('broad');
  const [selectedPaperIds, setSelectedPaperIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [generating, setGenerating] = useState<'pdf' | 'docx' | null>(null);
  const [preview, setPreview] = useState<ReportPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [visualQuery, setVisualQuery] = useState('');
  const [visualDepthLimit, setVisualDepthLimit] = useState(2);
  const [visualZoom, setVisualZoom] = useState(1);
  const [visualPan, setVisualPan] = useState({ x: 0, y: 0 });
  const [isVisualPanning, setIsVisualPanning] = useState(false);
  const [activeVisualNodeId, setActiveVisualNodeId] = useState<string | null>(null);
  const visualMapRef = useRef<SVGSVGElement | null>(null);
  const visualPanStartRef = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);

  useEffect(() => {
    const fetchWorkspaces = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.get<Workspace[]>('/workspaces/');
        const list = res.data || [];
        setWorkspaces(list);
        if (list.length > 0) {
          setSelectedWorkspaceId(list[0].id);
          setTopic(`Comprehensive literature synthesis for ${list[0].name}`);
        }
      } catch (err: unknown) {
        setError(apiErrorMessage(err, 'Failed to load workspaces.'));
      } finally {
        setLoading(false);
      }
    };
    void fetchWorkspaces();
  }, []);

  useEffect(() => {
    const fetchWorkspaceDetail = async () => {
      if (!selectedWorkspaceId) {
        setSelectedWorkspaceDetail(null);
        setSelectedPaperIds([]);
        return;
      }
      try {
        const res = await api.get<WorkspaceDetail>(`/workspaces/${selectedWorkspaceId}`);
        setSelectedWorkspaceDetail(res.data);
        const ids = (res.data?.papers || []).map((paper) => paper.id);
        setSelectedPaperIds(ids);
      } catch {
        setSelectedWorkspaceDetail(null);
        setSelectedPaperIds([]);
      } finally {
        setPreview(null);
      }
    };
    void fetchWorkspaceDetail();
  }, [selectedWorkspaceId]);

  const selectedWorkspace = useMemo(
    () => workspaces.find((item) => item.id === selectedWorkspaceId) || null,
    [workspaces, selectedWorkspaceId]
  );

  const paperCount = selectedWorkspaceDetail?.papers?.length ?? 0;
  const selectedCount = selectedPaperIds.length;
  const shownPapers = useMemo(
    () => (selectedWorkspaceDetail?.papers || []).slice(0, MAX_VISIBLE_PAPERS),
    [selectedWorkspaceDetail]
  );
  const previewNodes: MindmapNode[] = preview?.mindmap_nodes || [];
  const previewPaperLinks = preview?.paper_links || [];
  const reportDepthMeta = DEPTH_OPTIONS.find((item) => item.value === depth);
  const reportFocusMeta = FOCUS_OPTIONS.find((item) => item.value === focusMode);
  const visualMindmap = useMemo(() => buildMindmapLayout(previewNodes), [previewNodes]);
  const maxDepthAvailable = useMemo(
    () => previewNodes.reduce((maxValue, node) => Math.max(maxValue, Number(node.depth || 0)), 0),
    [previewNodes]
  );

  useEffect(() => {
    if (maxDepthAvailable > 0) {
      setVisualDepthLimit(maxDepthAvailable);
    } else {
      setVisualDepthLimit(0);
    }
    setVisualQuery('');
    setVisualZoom(1);
    setVisualPan({ x: 0, y: 0 });
    setIsVisualPanning(false);
    setActiveVisualNodeId(null);
  }, [maxDepthAvailable, preview?.generated_at]);

  const filteredVisual = useMemo(() => {
    const cappedDepth = Math.max(0, Math.min(visualDepthLimit, maxDepthAvailable || 0));
    let nodes = visualMindmap.nodes.filter((node) => node.depth <= cappedDepth);
    let edges = visualMindmap.edges.filter(
      (edge) => nodes.some((node) => node.id === edge.from) && nodes.some((node) => node.id === edge.to)
    );

    const query = visualQuery.trim().toLowerCase();
    if (!query) {
      return { nodes, edges };
    }

    const parentById = new Map<string, string>();
    const childrenById = new Map<string, string[]>();
    for (const edge of edges) {
      parentById.set(edge.to, edge.from);
      const children = childrenById.get(edge.from) || [];
      children.push(edge.to);
      childrenById.set(edge.from, children);
    }

    const matched = nodes
      .filter((node) => String(node.label || '').toLowerCase().includes(query))
      .map((node) => node.id);
    if (matched.length === 0) {
      return { nodes: [], edges: [] };
    }

    const includeIds = new Set<string>();
    for (const nodeId of matched) {
      includeIds.add(nodeId);
      let current = nodeId;
      while (parentById.has(current)) {
        const parentId = String(parentById.get(current));
        includeIds.add(parentId);
        current = parentId;
      }
      const directChildren = childrenById.get(nodeId) || [];
      for (const childId of directChildren) includeIds.add(childId);
    }

    nodes = nodes.filter((node) => includeIds.has(node.id));
    const nodeIds = new Set(nodes.map((node) => node.id));
    edges = edges.filter((edge) => nodeIds.has(edge.from) && nodeIds.has(edge.to));
    return { nodes, edges };
  }, [maxDepthAvailable, visualDepthLimit, visualMindmap.edges, visualMindmap.nodes, visualQuery]);

  useEffect(() => {
    if (!activeVisualNodeId && filteredVisual.nodes.length > 0) {
      setActiveVisualNodeId(filteredVisual.nodes[0].id);
      return;
    }
    if (
      activeVisualNodeId &&
      !filteredVisual.nodes.some((node) => node.id === activeVisualNodeId)
    ) {
      setActiveVisualNodeId(filteredVisual.nodes[0]?.id || null);
    }
  }, [activeVisualNodeId, filteredVisual.nodes]);

  const filteredVisualNodeById = useMemo(
    () => new Map(filteredVisual.nodes.map((node) => [node.id, node])),
    [filteredVisual.nodes]
  );
  const activeVisualNode = activeVisualNodeId ? filteredVisualNodeById.get(activeVisualNodeId) || null : null;
  const activeVisualParent = activeVisualNode?.parent_id
    ? filteredVisualNodeById.get(activeVisualNode.parent_id) || null
    : null;
  const activeVisualChildren = activeVisualNode
    ? filteredVisual.nodes.filter((node) => node.parent_id === activeVisualNode.id).slice(0, 8)
    : [];
  const activeVisualPaperLink = useMemo(() => {
    if (!activeVisualNode) return null;
    const match = String(activeVisualNode.label || '').match(/\bpaper\s*(\d+)\b/i);
    if (!match) return null;
    const index = Number(match[1] || 0);
    if (!Number.isFinite(index) || index <= 0) return null;
    return previewPaperLinks.find((item) => item.index === index) || null;
  }, [activeVisualNode, previewPaperLinks]);

  const startVisualPan = (event: ReactMouseEvent<SVGSVGElement>) => {
    const target = event.target;
    if (target instanceof Element && target.closest('[data-node-id]')) return;
    visualPanStartRef.current = {
      x: event.clientX,
      y: event.clientY,
      panX: visualPan.x,
      panY: visualPan.y,
    };
    setIsVisualPanning(true);
    event.preventDefault();
  };

  const updateVisualPan = (event: ReactMouseEvent<SVGSVGElement>) => {
    if (!visualPanStartRef.current) return;
    const dx = event.clientX - visualPanStartRef.current.x;
    const dy = event.clientY - visualPanStartRef.current.y;
    setVisualPan({
      x: visualPanStartRef.current.panX + dx,
      y: visualPanStartRef.current.panY + dy,
    });
  };

  const stopVisualPan = () => {
    visualPanStartRef.current = null;
    setIsVisualPanning(false);
  };

  const buildPayload = () => ({
    topic: topic.trim() || selectedWorkspace?.name || 'Research topic',
    paper_ids: selectedPaperIds,
    depth,
    focus_mode: focusMode,
  });

  const handlePreview = async () => {
    if (!selectedWorkspace) {
      setError('Select a workspace first.');
      return;
    }
    if (selectedCount === 0) {
      setError('Select at least one paper for the mindmap.');
      return;
    }

    setPreviewLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await api.post<ReportPreviewResponse>(
        `/workspaces/${selectedWorkspace.id}/research-report-preview`,
        buildPayload()
      );
      setPreview(res.data);
      setSuccess('Preview updated. Export when ready.');
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Failed to generate preview.'));
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleExport = async (format: 'pdf' | 'docx') => {
    if (!selectedWorkspace) {
      setError('Select a workspace first.');
      return;
    }
    if (selectedCount === 0) {
      setError('Select at least one paper for the export.');
      return;
    }

    setGenerating(format);
    setError(null);
    setSuccess(null);
    try {
      const res = await api.post(
        `/workspaces/${selectedWorkspace.id}/research-report?format=${format}`,
        buildPayload(),
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
      const baseName = (topic || selectedWorkspace.name || 'research-report').replace(/\s+/g, '_');
      anchor.href = url;
      anchor.download = `${baseName}_mindmap.${format}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      setSuccess(`Mindmap ${format.toUpperCase()} downloaded.`);
    } catch (err: unknown) {
      setError(
        apiErrorMessage(
          err,
          'Failed to export mindmap. Confirm backend is running and the workspace has papers.'
        )
      );
    } finally {
      setGenerating(null);
    }
  };

  const downloadVisualSvg = () => {
    const svg = visualMapRef.current;
    if (!svg || filteredVisual.nodes.length === 0) {
      setError('Generate preview first to export the visual mindmap.');
      return;
    }
    const serialized = serializeSvg(svg);
    const blob = new Blob([serialized], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const baseName = (topic || selectedWorkspace?.name || 'mindmap').replace(/\s+/g, '_');
    link.href = url;
    link.download = `${baseName}_visual.svg`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setSuccess('Visual mindmap SVG downloaded.');
  };

  const downloadVisualPng = async () => {
    const svg = visualMapRef.current;
    if (!svg || filteredVisual.nodes.length === 0) {
      setError('Generate preview first to export the visual mindmap.');
      return;
    }
    try {
      const serialized = serializeSvg(svg);
      const svgBlob = new Blob([serialized], { type: 'image/svg+xml;charset=utf-8' });
      const svgUrl = URL.createObjectURL(svgBlob);
      const image = new Image();
      const loaded = new Promise<void>((resolve, reject) => {
        image.onload = () => resolve();
        image.onerror = () => reject(new Error('Failed to render SVG.'));
      });
      image.src = svgUrl;
      await loaded;

      const canvas = document.createElement('canvas');
      canvas.width = MINDMAP_CANVAS_WIDTH;
      canvas.height = MINDMAP_CANVAS_HEIGHT;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        URL.revokeObjectURL(svgUrl);
        throw new Error('Canvas context unavailable.');
      }
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(svgUrl);

      const pngUrl = canvas.toDataURL('image/png');
      const link = document.createElement('a');
      const baseName = (topic || selectedWorkspace?.name || 'mindmap').replace(/\s+/g, '_');
      link.href = pngUrl;
      link.download = `${baseName}_visual.png`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setSuccess('Visual mindmap PNG downloaded.');
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Failed to export visual mindmap PNG.'));
    }
  };

  const applyTemplate = (template: string) => {
    const workspaceName = selectedWorkspace?.name || 'this workspace';
    setTopic(template.replace('{workspace}', workspaceName));
  };

  const togglePaperSelection = (paperId: number) => {
    setSelectedPaperIds((prev) =>
      prev.includes(paperId) ? prev.filter((id) => id !== paperId) : [...prev, paperId]
    );
    setPreview(null);
  };

  const selectAllPapers = () => {
    const allIds = (selectedWorkspaceDetail?.papers || []).map((paper) => paper.id);
    setSelectedPaperIds(allIds);
    setPreview(null);
  };

  const clearPapers = () => {
    setSelectedPaperIds([]);
    setPreview(null);
  };

  const renderInlineLinks = (text: string) => {
    const pattern = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
    const nodes: Array<string | ReactNode> = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = pattern.exec(text)) !== null) {
      const [fullMatch, label, href] = match;
      const start = match.index;
      if (start > lastIndex) {
        nodes.push(text.slice(lastIndex, start));
      }
      nodes.push(
        <a
          key={`lnk-${start}-${href}`}
          href={href}
          target="_blank"
          rel="noreferrer"
          className="mindmap-inline-link"
        >
          {label}
        </a>
      );
      lastIndex = start + fullMatch.length;
    }

    if (lastIndex < text.length) {
      nodes.push(text.slice(lastIndex));
    }

    return nodes.length > 0 ? nodes : text;
  };

  const renderPreviewLine = (line: string, idx: number) => {
    if (!line.trim()) {
      return <div key={`blank-${idx}`} className="h-2" />;
    }
    if (line.startsWith('# ')) {
      return (
        <h3 key={`h1-${idx}`} className="mindmap-preview-h1">
          {line.replace(/^#\s+/, '')}
        </h3>
      );
    }
    if (line.startsWith('## ')) {
      return (
        <h4 key={`h2-${idx}`} className="mindmap-preview-h2">
          {line.replace(/^##\s+/, '')}
        </h4>
      );
    }
    if (line.startsWith('### ')) {
      return (
        <h5 key={`h3-${idx}`} className="mindmap-preview-h3">
          {line.replace(/^###\s+/, '')}
        </h5>
      );
    }

    const bulletMatch = line.match(/^(\s*)-\s+(.*)$/);
    if (bulletMatch) {
      const indent = Math.min(24, Math.max(0, Math.floor(bulletMatch[1].length / 2) * 10));
      return (
        <p key={`bullet-${idx}`} className="mindmap-preview-bullet" style={{ marginLeft: indent }}>
          {renderInlineLinks(bulletMatch[2])}
        </p>
      );
    }

    if (line.includes('|')) {
      return (
        <p key={`table-${idx}`} className="mindmap-preview-tableline">
          {line}
        </p>
      );
    }

    return (
      <p key={`text-${idx}`} className="mindmap-preview-text">
        {renderInlineLinks(line)}
      </p>
    );
  };

  return (
    <Layout>
      <div className="page-enter">
        <section className="studio-hero mb-6">
          <span className="studio-kicker">
            <Sparkles className="h-3.5 w-3.5" />
            Review Engine
          </span>
          <h2>Mindmap Studio</h2>
          <p>Build a structured research brief, inspect a live markdown preview, then export to PDF or Word.</p>
          <div className="studio-chip-row">
            <span className="studio-chip">
              <Workflow className="h-3.5 w-3.5" />
              Preview before export
            </span>
            <span className="studio-chip">
              <Wand2 className="h-3.5 w-3.5" />
              Depth and focus controls
            </span>
            <span className="studio-chip">
              <FileText className="h-3.5 w-3.5" />
              Select specific papers
            </span>
          </div>
          <div className="studio-orb" aria-hidden="true" />
        </section>

        <section className="studio-surface p-5">
          {loading ? (
            <div className="flex items-center gap-2 text-slate-500 py-2">
              <Loader2 className="h-4.5 w-4.5 animate-spin" />
              Loading workspaces...
            </div>
          ) : workspaces.length === 0 ? (
            <div className="studio-panel px-4 py-3 text-sm text-amber-800 border-amber-200 bg-amber-50">
              No workspace found. Create a workspace and import papers first.
            </div>
          ) : (
            <>
              <div className="studio-stat-grid mb-4">
                <div className="studio-stat-card">
                  <p className="studio-stat-label">Workspace</p>
                  <p className="studio-stat-value">{selectedWorkspace?.name || 'N/A'}</p>
                </div>
                <div className="studio-stat-card">
                  <p className="studio-stat-label">Papers In Workspace</p>
                  <p className="studio-stat-value">{paperCount}</p>
                </div>
                <div className="studio-stat-card">
                  <p className="studio-stat-label">Selected For Report</p>
                  <p className="studio-stat-value">{selectedCount}</p>
                </div>
                <div className="studio-stat-card">
                  <p className="studio-stat-label">Current Mode</p>
                  <p className="studio-stat-value">
                    {reportDepthMeta?.label} / {reportFocusMeta?.label}
                  </p>
                </div>
              </div>

              <div className="mindmap-layout-grid">
                <div className="mindmap-config-card">
                  <h3 className="mindmap-card-title">Report Setup</h3>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                        Workspace
                      </label>
                      <select
                        value={selectedWorkspaceId ?? ''}
                        onChange={(event) => {
                          const nextId = Number(event.target.value);
                          setSelectedWorkspaceId(Number.isFinite(nextId) ? nextId : null);
                          const nextWs = workspaces.find((item) => item.id === nextId);
                          if (nextWs) {
                            setTopic(`Comprehensive literature synthesis for ${nextWs.name}`);
                          }
                          setPreview(null);
                        }}
                        className="w-full rounded-xl border border-slate-300 py-2.5 px-3.5 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      >
                        {workspaces.map((workspace) => (
                          <option key={workspace.id} value={workspace.id}>
                            {workspace.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                        Depth
                      </label>
                      <select
                        value={depth}
                        onChange={(event) => {
                          setDepth(event.target.value as ReportDepth);
                          setPreview(null);
                        }}
                        className="w-full rounded-xl border border-slate-300 py-2.5 px-3.5 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      >
                        {DEPTH_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label} - {option.desc}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="md:col-span-2">
                      <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                        Focus topic
                      </label>
                      <input
                        type="text"
                        value={topic}
                        onChange={(event) => {
                          setTopic(event.target.value);
                          setPreview(null);
                        }}
                        placeholder="Example: Graph neural networks for molecular discovery"
                        className="w-full rounded-xl border border-slate-300 py-2.5 px-3.5 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                      <div className="mt-2 flex flex-wrap gap-2">
                        {TOPIC_TEMPLATES.map((template) => (
                          <button
                            key={template}
                            type="button"
                            onClick={() => applyTemplate(template)}
                            className="text-xs px-2.5 py-1.5 rounded-full border border-slate-200 text-slate-600 hover:bg-slate-50"
                          >
                            {template.replace('{workspace}', selectedWorkspace?.name || 'workspace')}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="md:col-span-2">
                      <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                        Focus mode
                      </label>
                      <select
                        value={focusMode}
                        onChange={(event) => {
                          setFocusMode(event.target.value as ReportFocus);
                          setPreview(null);
                        }}
                        className="w-full rounded-xl border border-slate-300 py-2.5 px-3.5 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      >
                        {FOCUS_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label} - {option.desc}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2.5 mt-4">
                    <button
                      type="button"
                      onClick={() => {
                        void handlePreview();
                      }}
                      disabled={previewLoading || generating !== null}
                      className="hero-btn-secondary disabled:opacity-55 disabled:cursor-not-allowed"
                    >
                      {previewLoading ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Generating preview...
                        </>
                      ) : (
                        <>
                          <FileSearch className="h-4 w-4" />
                          Generate Preview
                        </>
                      )}
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        void handleExport('pdf');
                      }}
                      disabled={generating !== null || previewLoading}
                      className="hero-btn-primary disabled:opacity-55 disabled:cursor-not-allowed"
                    >
                      {generating === 'pdf' ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Generating PDF...
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-4 w-4" />
                          Download PDF
                        </>
                      )}
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        void handleExport('docx');
                      }}
                      disabled={generating !== null || previewLoading}
                      className="hero-btn-secondary disabled:opacity-55 disabled:cursor-not-allowed"
                    >
                      {generating === 'docx' ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Generating Word...
                        </>
                      ) : (
                        <>
                          <Download className="h-4 w-4" />
                          Download Word
                        </>
                      )}
                    </button>
                  </div>
                </div>

                <div className="mindmap-preview-card">
                  <div className="mindmap-preview-header">
                    <h3 className="mindmap-card-title">Report Preview</h3>
                    <div className="flex items-center gap-2">
                      {preview && (
                        <span className="mindmap-preview-tag">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          Updated {new Date(preview.generated_at).toLocaleTimeString()}
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={downloadVisualSvg}
                        disabled={filteredVisual.nodes.length === 0}
                        className="text-xs font-semibold text-slate-700 border border-slate-200 rounded-lg px-2.5 py-1.5 hover:bg-slate-50 disabled:opacity-50"
                      >
                        Export SVG
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          void downloadVisualPng();
                        }}
                        disabled={filteredVisual.nodes.length === 0}
                        className="text-xs font-semibold text-slate-700 border border-slate-200 rounded-lg px-2.5 py-1.5 hover:bg-slate-50 disabled:opacity-50"
                      >
                        Export PNG
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-2 md:grid-cols-4 mt-3">
                    <input
                      type="text"
                      value={visualQuery}
                      onChange={(event) => setVisualQuery(event.target.value)}
                      placeholder="Find mindmap nodes"
                      className="rounded-lg border border-slate-200 px-3 py-2 text-xs md:col-span-2"
                    />
                    <label className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-2.5 py-2 text-xs text-slate-700">
                      Depth
                      <input
                        type="range"
                        min={0}
                        max={Math.max(0, maxDepthAvailable)}
                        step={1}
                        value={Math.min(visualDepthLimit, Math.max(0, maxDepthAvailable))}
                        onChange={(event) => setVisualDepthLimit(Number(event.target.value) || 0)}
                      />
                      <span className="font-semibold">{visualDepthLimit}</span>
                    </label>
                    <div className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-2">
                      <button
                        type="button"
                        onClick={() => setVisualZoom((prev) => Math.max(0.65, Number((prev - 0.1).toFixed(2))))}
                        className="rounded border border-slate-200 px-2 py-1 text-xs"
                      >
                        <ZoomOut className="h-3.5 w-3.5" />
                      </button>
                      <span className="min-w-[56px] text-center text-xs font-semibold text-slate-700">
                        {Math.round(visualZoom * 100)}%
                      </span>
                      <button
                        type="button"
                        onClick={() => setVisualZoom((prev) => Math.min(1.8, Number((prev + 0.1).toFixed(2))))}
                        className="rounded border border-slate-200 px-2 py-1 text-xs"
                      >
                        <ZoomIn className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setVisualZoom(1);
                          setVisualPan({ x: 0, y: 0 });
                          setVisualDepthLimit(maxDepthAvailable);
                          setVisualQuery('');
                          setIsVisualPanning(false);
                        }}
                        className="rounded border border-slate-200 px-2 py-1 text-xs text-slate-600"
                      >
                        <Crosshair className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2 mt-2">
                    <span className="mindmap-preview-tag">Visible nodes {filteredVisual.nodes.length}</span>
                    <span className="mindmap-preview-tag">Visible links {filteredVisual.edges.length}</span>
                  </div>

                  <div className="mindmap-visual-card mt-3">
                    {filteredVisual.nodes.length > 0 ? (
                      <div className="mindmap-visual-scroll">
                        <svg
                          ref={visualMapRef}
                          viewBox={`0 0 ${MINDMAP_CANVAS_WIDTH} ${MINDMAP_CANVAS_HEIGHT}`}
                          className={`mindmap-visual-svg ${isVisualPanning ? 'cursor-grabbing' : 'cursor-grab'}`}
                          role="img"
                          aria-label="Visual mindmap graph"
                          onMouseDown={startVisualPan}
                          onMouseMove={updateVisualPan}
                          onMouseUp={stopVisualPan}
                          onMouseLeave={stopVisualPan}
                        >
                          <rect x="0" y="0" width={MINDMAP_CANVAS_WIDTH} height={MINDMAP_CANVAS_HEIGHT} fill="#f8fafc" />
                          <g
                            transform={`translate(${visualPan.x} ${visualPan.y}) translate(${MINDMAP_CANVAS_WIDTH / 2} ${MINDMAP_CANVAS_HEIGHT / 2}) scale(${visualZoom}) translate(${-MINDMAP_CANVAS_WIDTH / 2} ${-MINDMAP_CANVAS_HEIGHT / 2})`}
                          >
                            {filteredVisual.edges.map((edge) => {
                              const source = filteredVisualNodeById.get(edge.from);
                              const target = filteredVisualNodeById.get(edge.to);
                              if (!source || !target) return null;
                              const sx = (source.x / 100) * MINDMAP_CANVAS_WIDTH;
                              const sy = (source.y / 100) * MINDMAP_CANVAS_HEIGHT;
                              const tx = (target.x / 100) * MINDMAP_CANVAS_WIDTH;
                              const ty = (target.y / 100) * MINDMAP_CANVAS_HEIGHT;
                              const cx1 = sx + (tx - sx) * 0.35;
                              const cx2 = sx + (tx - sx) * 0.68;
                              return (
                                <path
                                  key={`${edge.from}-${edge.to}`}
                                  d={`M ${sx} ${sy} C ${cx1} ${sy}, ${cx2} ${ty}, ${tx} ${ty}`}
                                  stroke="#334155"
                                  strokeWidth="2.2"
                                  fill="none"
                                  strokeOpacity="0.68"
                                />
                              );
                            })}
                            {filteredVisual.nodes.map((node) => {
                              const px = (node.x / 100) * MINDMAP_CANVAS_WIDTH;
                              const py = (node.y / 100) * MINDMAP_CANVAS_HEIGHT;
                              const lines = wrapLabel(
                                node.label,
                                node.side === 'center' ? 14 : 18,
                                node.side === 'center' ? 2 : 3
                              );
                              const maxChars = Math.max(8, ...lines.map((line) => line.length));
                              const boxWidth =
                                node.side === 'center'
                                  ? 170
                                  : Math.min(260, Math.max(96, maxChars * 8 + 28));
                              const boxHeight = Math.max(42, lines.length * 17 + 14);
                              const style = nodeStyle(node);
                              const active = node.id === activeVisualNodeId;
                              const matched =
                                visualQuery.trim().length > 0 &&
                                String(node.label || '').toLowerCase().includes(visualQuery.trim().toLowerCase());
                              return (
                                <g
                                  key={node.id}
                                  data-node-id={node.id}
                                  onClick={() => setActiveVisualNodeId(node.id)}
                                  className="cursor-pointer"
                                >
                                  <rect
                                    x={px - boxWidth / 2}
                                    y={py - boxHeight / 2}
                                    width={boxWidth}
                                    height={boxHeight}
                                    rx={14}
                                    fill={style.fill}
                                    stroke={active ? '#1d4ed8' : style.stroke}
                                    strokeWidth={active ? 3 : matched ? 2.2 : node.side === 'center' ? 2.5 : 1.8}
                                  />
                                  <text
                                    x={px}
                                    y={py - ((lines.length - 1) * 8)}
                                    textAnchor="middle"
                                    fontSize={node.side === 'center' ? 27 : 18}
                                    fontWeight={node.side === 'center' ? 700 : 600}
                                    fill={style.text}
                                    fontFamily="'Nunito', 'Poppins', 'Segoe UI', sans-serif"
                                  >
                                    {lines.map((line, idx) => (
                                      <tspan key={`${node.id}-${idx}`} x={px} dy={idx === 0 ? 0 : 18}>
                                        {line}
                                      </tspan>
                                    ))}
                                  </text>
                                </g>
                              );
                            })}
                          </g>
                        </svg>
                      </div>
                    ) : (
                      <div className="mindmap-preview-empty">
                        <p>No visual mindmap yet.</p>
                        <p>Generate preview to build the connected graph.</p>
                      </div>
                    )}
                  </div>

                  {activeVisualNode && (
                    <div className="mindmap-node-inspector mt-3">
                      <div>
                        <p className="mindmap-node-label">{activeVisualNode.label}</p>
                        <p className="mindmap-node-meta">
                          Depth {activeVisualNode.depth} | Side {activeVisualNode.side}
                        </p>
                      </div>
                      {activeVisualParent && (
                        <p className="mindmap-node-meta">Parent: {activeVisualParent.label}</p>
                      )}
                      {activeVisualChildren.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {activeVisualChildren.map((child) => (
                            <button
                              key={child.id}
                              type="button"
                              onClick={() => setActiveVisualNodeId(child.id)}
                              className="mindmap-node-chip"
                            >
                              {child.label}
                            </button>
                          ))}
                        </div>
                      )}
                      {activeVisualPaperLink?.url && (
                        <a
                          href={activeVisualPaperLink.url}
                          target="_blank"
                          rel="noreferrer"
                          className="mindmap-inline-link"
                        >
                          Open linked paper: {activeVisualPaperLink.title}
                        </a>
                      )}
                    </div>
                  )}

                  <div className="mindmap-preview-body">
                    {previewLoading ? (
                      <div className="flex items-center gap-2 text-slate-500 py-2">
                        <Loader2 className="h-4.5 w-4.5 animate-spin" />
                        Generating structured preview...
                      </div>
                    ) : preview?.markdown ? (
                      <div className="mindmap-preview-scroll">
                        {preview.markdown.split('\n').map((line, idx) => renderPreviewLine(line, idx))}
                      </div>
                    ) : (
                      <div className="mindmap-preview-empty">
                        <p>No preview yet.</p>
                        <p>Click "Generate Preview" to inspect structure before exporting.</p>
                      </div>
                    )}
                  </div>

                  {previewPaperLinks.length > 0 && (
                    <div className="mt-3">
                      <h4 className="text-sm font-semibold text-slate-800 mb-2">Referenced Paper Links</h4>
                      <div className="mindmap-links-list">
                        {previewPaperLinks.slice(0, 14).map((item) => (
                          <div key={`ln-${item.index}`} className="mindmap-link-row">
                            <span className="mindmap-link-paper">{item.paper}</span>
                            {item.url ? (
                              <a href={item.url} target="_blank" rel="noreferrer" className="mindmap-inline-link">
                                {item.title}
                              </a>
                            ) : (
                              <span className="text-slate-500">{item.title} (Link unavailable)</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="mindmap-paper-selector mt-4">
                <div className="mindmap-preview-header">
                  <h3 className="mindmap-card-title">Paper Selection</h3>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={selectAllPapers}
                      className="text-xs font-semibold text-slate-700 border border-slate-200 rounded-lg px-2.5 py-1.5 hover:bg-slate-50"
                    >
                      Select all
                    </button>
                    <button
                      type="button"
                      onClick={clearPapers}
                      className="text-xs font-semibold text-slate-700 border border-slate-200 rounded-lg px-2.5 py-1.5 hover:bg-slate-50"
                    >
                      Clear
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        void handlePreview();
                      }}
                      disabled={previewLoading}
                      className="text-xs font-semibold text-slate-700 border border-slate-200 rounded-lg px-2.5 py-1.5 hover:bg-slate-50 disabled:opacity-50"
                    >
                      <span className="inline-flex items-center gap-1">
                        <RefreshCw className="h-3.5 w-3.5" />
                        Refresh preview
                      </span>
                    </button>
                  </div>
                </div>

                {paperCount === 0 ? (
                  <p className="text-sm text-slate-500 mt-2">No papers in this workspace.</p>
                ) : (
                  <>
                    <p className="text-xs text-slate-500 mt-1">
                      Showing {Math.min(MAX_VISIBLE_PAPERS, paperCount)} of {paperCount} papers for fast selection.
                    </p>
                    <div className="mindmap-paper-list mt-2">
                      {shownPapers.map((paper) => {
                        const checked = selectedPaperIds.includes(paper.id);
                        return (
                          <label
                            key={paper.id}
                            className={`mindmap-paper-item ${checked ? 'mindmap-paper-item-active' : ''}`}
                          >
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => togglePaperSelection(paper.id)}
                              className="mt-1"
                            />
                            <div>
                              <p className="mindmap-paper-title">{paper.title}</p>
                              <p className="mindmap-paper-authors">{paper.authors || 'Unknown authors'}</p>
                            </div>
                          </label>
                        );
                      })}
                    </div>
                  </>
                )}
              </div>
            </>
          )}

          {error && (
            <div className="studio-panel px-4 py-3 text-sm text-red-700 border-red-200 bg-red-50 mt-4">{error}</div>
          )}
          {success && (
            <div className="studio-panel px-4 py-3 text-sm text-emerald-700 border-emerald-200 bg-emerald-50 mt-4">
              {success}
            </div>
          )}
        </section>
      </div>
    </Layout>
  );
};

export default Mindmap;
