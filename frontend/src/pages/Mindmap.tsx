import { useEffect, useMemo, useState } from 'react';
import { Download, FileText, Loader2, Sparkles, Workflow } from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';
import { apiErrorMessage } from '../utils/apiError';

interface Workspace {
  id: number;
  name: string;
  description?: string;
}

interface WorkspaceDetail {
  id: number;
  name: string;
  papers: { id: number }[];
}

const Mindmap = () => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  const [selectedWorkspaceDetail, setSelectedWorkspaceDetail] = useState<WorkspaceDetail | null>(null);
  const [topic, setTopic] = useState('');
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState<'pdf' | 'docx' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

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
          setTopic(`${list[0].name} literature synthesis`);
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
        return;
      }
      try {
        const res = await api.get<WorkspaceDetail>(`/workspaces/${selectedWorkspaceId}`);
        setSelectedWorkspaceDetail(res.data);
      } catch {
        setSelectedWorkspaceDetail(null);
      }
    };
    void fetchWorkspaceDetail();
  }, [selectedWorkspaceId]);

  const selectedWorkspace = useMemo(
    () => workspaces.find((item) => item.id === selectedWorkspaceId) || null,
    [workspaces, selectedWorkspaceId]
  );

  const handleExport = async (format: 'pdf' | 'docx') => {
    if (!selectedWorkspace) {
      setError('Select a workspace first.');
      return;
    }
    const paperCount = selectedWorkspaceDetail?.papers?.length || 0;
    if (paperCount === 0) {
      setError('Mindmap export requires at least one paper in the selected workspace.');
      return;
    }

    setGenerating(format);
    setError(null);
    setSuccess(null);
    try {
      const res = await api.post(
        `/workspaces/${selectedWorkspace.id}/research-report?format=${format}`,
        { topic: topic.trim() || selectedWorkspace.name },
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
          'Failed to generate mindmap report. Ensure workspace has papers and backend is running.'
        )
      );
    } finally {
      setGenerating(null);
    }
  };

  return (
    <Layout>
      <section className="studio-hero mb-6">
        <span className="studio-kicker">
          <Sparkles className="h-3.5 w-3.5" />
          Review Engine
        </span>
        <h2>Mindmap Studio</h2>
        <p>Generate a complete research brief plus hierarchical mindmap from papers in one workspace.</p>
        <div className="studio-chip-row">
          <span className="studio-chip">
            <Workflow className="h-3.5 w-3.5" />
            PDF and Word export
          </span>
          <span className="studio-chip">
            <FileText className="h-3.5 w-3.5" />
            Workspace-based synthesis
          </span>
        </div>
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
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              <div className="lg:col-span-1">
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
                      setTopic(`${nextWs.name} literature synthesis`);
                    }
                  }}
                  className="w-full rounded-xl border border-slate-300 py-2.5 px-3.5 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {workspaces.map((workspace) => (
                    <option key={workspace.id} value={workspace.id}>
                      {workspace.name}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-slate-500 mt-2">
                  Papers: {selectedWorkspaceDetail?.papers?.length ?? 0}
                </p>
              </div>

              <div className="lg:col-span-2">
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                  Focus topic
                </label>
                <input
                  type="text"
                  value={topic}
                  onChange={(event) => setTopic(event.target.value)}
                  placeholder="Example: Graph neural networks for molecular discovery"
                  className="w-full rounded-xl border border-slate-300 py-2.5 px-3.5 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2.5 mt-4">
              <button
                type="button"
                onClick={() => {
                  void handleExport('pdf');
                }}
                disabled={generating !== null}
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
                    Download Mindmap PDF
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={() => {
                  void handleExport('docx');
                }}
                disabled={generating !== null}
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
                    Download Mindmap Word
                  </>
                )}
              </button>
            </div>
          </>
        )}

        {error && <div className="studio-panel px-4 py-3 text-sm text-red-700 border-red-200 bg-red-50 mt-4">{error}</div>}
        {success && <div className="studio-panel px-4 py-3 text-sm text-emerald-700 border-emerald-200 bg-emerald-50 mt-4">{success}</div>}
      </section>
    </Layout>
  );
};

export default Mindmap;

