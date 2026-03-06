import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Folder,
  FileText,
  Plus,
  Trash2,
  X,
  Check,
  Loader2,
  Database,
  BrainCircuit,
  Download,
  ArrowUpRight,
  Sparkles,
  Bot,
  Search,
  Upload,
  Workflow,
} from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';

interface Workspace {
  id: number;
  name: string;
  description?: string;
  created_at?: string;
  paperCount?: number;
}

interface WorkspacePaper {
  abstract?: string;
}

interface WorkspaceTemplate {
  name: string;
  description: string;
}

const Dashboard = () => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalPapers, setTotalPapers] = useState(0);
  const [totalChars, setTotalChars] = useState(0);

  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [creating, setCreating] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);

  const workspaceTemplates: WorkspaceTemplate[] = [
    {
      name: 'Literature Review Sprint',
      description: 'Track papers, notes, and synthesis for a structured literature review.',
    },
    {
      name: 'Model Benchmarking',
      description: 'Collect papers, datasets, and evaluation notes for comparing approaches.',
    },
    {
      name: 'Grant Discovery',
      description: 'Capture prior work, evidence gaps, and promising angles for proposal building.',
    },
  ];

  const quickLaunches = [
    {
      title: 'Search papers',
      desc: 'Probe the search fabric and start a fresh evidence trail.',
      to: '/search',
      icon: Search,
      tone: 'from-indigo-500 to-cyan-500',
    },
    {
      title: 'Research agent',
      desc: 'Use AI when you already know the question but need synthesis fast.',
      to: '/research-agent',
      icon: Bot,
      tone: 'from-sky-500 to-blue-600',
    },
    {
      title: 'Upload PDF',
      desc: 'Bring private documents into the same project context.',
      to: '/upload',
      icon: Upload,
      tone: 'from-emerald-500 to-teal-600',
    },
    {
      title: 'Mindmap review',
      desc: 'Convert imported evidence into a navigable review structure.',
      to: '/mindmap',
      icon: Workflow,
      tone: 'from-fuchsia-500 to-violet-600',
    },
  ];

  const fetchWorkspaces = async () => {
    try {
      const res = await api.get('/workspaces/');
      const wsList: Workspace[] = res.data;
      let papers = 0;
      let chars = 0;
      const enriched = await Promise.all(
        wsList.map(async (ws) => {
          try {
            const detail = await api.get(`/workspaces/${ws.id}`);
            const pc = detail.data.papers?.length || 0;
            const cc = ((detail.data.papers as WorkspacePaper[] | undefined) || []).reduce(
              (acc: number, p) => acc + (p.abstract?.length || 0),
              0
            );
            papers += pc;
            chars += cc;
            return { ...ws, paperCount: pc };
          } catch {
            return { ...ws, paperCount: 0 };
          }
        })
      );
      setWorkspaces(enriched);
      setTotalPapers(papers);
      setTotalChars(chars);

      if (enriched.length === 0) {
        try {
          const defaultWs = await api.post('/workspaces/', {
            name: 'My Research Workspace',
            description: 'Default workspace for organizing research papers',
          });
          setWorkspaces([{ ...defaultWs.data, paperCount: 0 }]);
        } catch {
          // keep silent on fallback create failure
        }
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkspaces();
  }, []);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await api.post('/workspaces/', { name: newName.trim(), description: newDesc.trim() });
      setNewName('');
      setNewDesc('');
      setShowCreate(false);
      await fetchWorkspaces();
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/workspaces/${id}`);
      setDeleteId(null);
      await fetchWorkspaces();
    } catch {
      // keep silent on delete failure
    }
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-';
    try {
      return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return '-';
    }
  };

  const formatNum = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));

  const stats = [
    {
      label: 'Workspaces',
      value: workspaces.length,
      icon: Folder,
      color: '#4f46e5',
      bg: 'rgba(79,70,229,0.12)',
    },
    {
      label: 'Papers Imported',
      value: totalPapers,
      icon: FileText,
      color: '#0ea5e9',
      bg: 'rgba(14,165,233,0.12)',
    },
    {
      label: 'Indexed Characters',
      value: formatNum(totalChars),
      icon: Database,
      color: '#9333ea',
      bg: 'rgba(147,51,234,0.12)',
    },
    {
      label: 'AI Context',
      value: 'Ready',
      icon: BrainCircuit,
      color: '#0f766e',
      bg: 'rgba(15,118,110,0.12)',
    },
  ];

  const handleExportWorkspace = async (id: number, name: string, format: 'bibtex' | 'csv') => {
    try {
      const res = await api.get(`/workspaces/${id}/export?format=${format}`, { responseType: 'blob' });
      const blob = new Blob([res.data], { type: format === 'csv' ? 'text/csv' : 'application/x-bibtex' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = format === 'csv' ? 'csv' : 'bib';
      a.download = `${name.replace(/\s+/g, '_')}.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      // keep silent on export failure
    }
  };

  return (
    <Layout>
      <section className="dashboard-hero mb-6">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-cyan-200 mb-2 flex items-center gap-2">
            <Sparkles className="h-3.5 w-3.5" /> Control Plane
          </p>
          <h2 className="text-3xl md:text-4xl font-bold text-white">Workspace Intelligence Dashboard</h2>
          <p className="text-cyan-100/90 mt-2 text-sm md:text-base">
            Create project spaces, orchestrate imports, and monitor research throughput in one place.
          </p>
        </div>
        <button onClick={() => setShowCreate(true)} className="hero-btn-primary mt-4 md:mt-0">
          <Plus className="h-4 w-4" /> New Workspace
        </button>
      </section>

      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 mb-6 md:mb-7">
        {stats.map((s) => {
          const Icon = s.icon;
          return (
            <div key={s.label} className="stat-tile">
              <div className="stat-icon" style={{ background: s.bg, color: s.color }}>
                <Icon className="h-4 w-4 md:h-5 md:w-5" />
              </div>
              <p className="stat-label">{s.label}</p>
              <p className="stat-value">{loading ? '-' : s.value}</p>
            </div>
          );
        })}
      </section>

      <section className="mb-6 grid grid-cols-1 gap-4 xl:grid-cols-[0.95fr,1.05fr]">
        <div className="feature-surface">
          <p className="mb-1 text-xs uppercase tracking-[0.2em] text-slate-500">Workspace operating model</p>
          <h3 className="text-xl font-bold text-slate-900">Keep each project as a contained evidence loop</h3>
          <div className="mt-4 grid gap-3">
            {[
              'Start with one workspace per real research question, not one workspace per paper.',
              'Import only the sources you are willing to cite or synthesize in downstream AI steps.',
              'Use exports and mindmaps after the workspace has enough high-signal material to justify synthesis.',
            ].map((item, index) => (
              <div key={item} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-indigo-600">Rule {index + 1}</p>
                <p className="mt-1 text-sm leading-relaxed text-slate-600">{item}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {quickLaunches.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.title}
                to={item.to}
                className="group rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition-transform duration-150 hover:-translate-y-1 hover:shadow-lg"
              >
                <div className={`inline-flex rounded-2xl bg-gradient-to-br ${item.tone} p-2.5 text-white shadow-md`}>
                  <Icon className="h-5 w-5" />
                </div>
                <h4 className="mt-4 text-base font-semibold text-slate-900">{item.title}</h4>
                <p className="mt-1 text-sm leading-relaxed text-slate-600">{item.desc}</p>
                <span className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-slate-700">
                  Open <ArrowRight className="h-3.5 w-3.5 transition-transform duration-150 group-hover:translate-x-0.5" />
                </span>
              </Link>
            );
          })}
        </div>
      </section>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <h3 className="text-lg md:text-xl font-bold text-slate-900">Your Workspaces</h3>
        <Link
          to="/search"
          className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition-colors"
        >
          <span className="hidden sm:inline">Search Papers</span>
          <span className="sm:hidden">Search</span>
          <ArrowUpRight className="h-3.5 w-3.5" />
        </Link>
      </div>

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-3" style={{ background: 'rgba(2,6,23,0.52)' }}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-lg shadow-2xl border border-slate-100">
            <div className="flex items-center justify-between mb-5">
              <h4 className="text-lg font-bold text-slate-900">Create Workspace</h4>
              <button onClick={() => setShowCreate(false)} className="text-slate-400 hover:text-slate-600">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <p className="mb-2 text-sm font-medium text-slate-700">Start from a template</p>
                <div className="flex flex-wrap gap-2">
                  {workspaceTemplates.map((template) => (
                    <button
                      key={template.name}
                      type="button"
                      onClick={() => {
                        setNewName(template.name);
                        setNewDesc(template.description);
                      }}
                      className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-600 transition-colors hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700"
                    >
                      {template.name}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Name *</label>
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Multi-agent RAG Study"
                  className="w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
                <textarea
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="Project context, target area, key notes..."
                  rows={4}
                  className="w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm text-slate-900 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowCreate(false)}
                className="flex-1 py-2.5 rounded-xl border border-slate-200 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !newName.trim()}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white flex items-center justify-center gap-2 transition-opacity disabled:opacity-50"
                style={{ background: 'linear-gradient(120deg, #4f46e5, #0284c7)' }}
              >
                {creating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" /> Creating...
                  </>
                ) : (
                  <>
                    <Check className="h-4 w-4" /> Create
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-slate-500 py-8">
          <Loader2 className="h-5 w-5 animate-spin" /> Loading workspaces...
        </div>
      ) : workspaces.length === 0 ? (
        <div className="feature-surface text-center py-12">
          <div className="w-14 h-14 rounded-2xl bg-indigo-50 flex items-center justify-center mx-auto mb-4">
            <Folder className="h-7 w-7 text-indigo-500" />
          </div>
          <h4 className="text-slate-800 font-semibold mb-1">No workspaces yet</h4>
          <p className="text-slate-500 text-sm mb-4">Create a workspace to start structuring your research program.</p>
          <button onClick={() => setShowCreate(true)} className="hero-btn-primary">
            <Plus className="h-4 w-4" /> Create first workspace
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {workspaces.map((ws) => (
            <div key={ws.id} className="feature-surface workspace-card">
              <div className="flex items-start justify-between mb-3">
                <div className="p-2 rounded-xl bg-indigo-50">
                  <Folder className="h-5 w-5 text-indigo-500" />
                </div>
                {deleteId === ws.id ? (
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleDelete(ws.id)}
                      className="text-xs px-2.5 py-1 rounded-lg bg-red-100 text-red-700 font-medium hover:bg-red-200"
                    >
                      Delete
                    </button>
                    <button
                      onClick={() => setDeleteId(null)}
                      className="text-xs px-2.5 py-1 rounded-lg bg-slate-100 text-slate-600 font-medium hover:bg-slate-200"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button onClick={() => setDeleteId(ws.id)} className="text-slate-300 hover:text-red-500 transition-colors">
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>

              <h4 className="font-semibold text-slate-900 mb-1 truncate">{ws.name}</h4>
              <p className="text-sm text-slate-500 mb-4 line-clamp-2">{ws.description || 'No description provided.'}</p>

              <div className="mb-4 flex flex-wrap gap-2">
                <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold text-slate-600">
                  {ws.paperCount ?? 0} curated papers
                </span>
                <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
                  AI ready
                </span>
              </div>

              <div className="flex items-center justify-between gap-3">
                <span className="text-xs text-slate-500 bg-slate-100 px-2.5 py-1 rounded-full">
                  {ws.paperCount ?? 0} paper{ws.paperCount !== 1 ? 's' : ''} - {formatDate(ws.created_at)}
                </span>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => handleExportWorkspace(ws.id, ws.name, 'bibtex')}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-slate-600 hover:text-slate-900"
                  >
                    <Download className="h-3.5 w-3.5" /> Export
                  </button>
                  <Link to={`/workspace/${ws.id}`} className="text-xs font-semibold text-indigo-600 hover:text-indigo-800">
                    Open {'->'}
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
};

export default Dashboard;
