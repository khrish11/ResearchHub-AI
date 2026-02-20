import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Folder, FileText, Plus, Trash2, X, Check, Loader2, BookOpen, Database } from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';

interface Workspace {
  id: number;
  name: string;
  description?: string;
  created_at?: string;
  paperCount?: number;
}

const Dashboard = () => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalPapers, setTotalPapers] = useState(0);
  const [totalChars, setTotalChars] = useState(0);

  // Create modal
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [creating, setCreating] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);

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
            const cc = (detail.data.papers || []).reduce(
              (acc: number, p: any) => acc + (p.abstract?.length || 0),
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
    } catch (err) {
      console.error('Failed to fetch workspaces', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchWorkspaces(); }, []);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await api.post('/workspaces/', { name: newName.trim(), description: newDesc.trim() });
      setNewName(''); setNewDesc(''); setShowCreate(false);
      await fetchWorkspaces();
    } catch (e) {
      console.error(e);
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/workspaces/${id}`);
      setDeleteId(null);
      await fetchWorkspaces();
    } catch (e) {
      console.error(e);
    }
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '—';
    try {
      return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch { return '—'; }
  };

  const formatNum = (n: number) =>
    n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);

  const stats = [
    { label: 'Workspaces', value: workspaces.length, icon: Folder, color: '#6366f1', bg: 'rgba(99,102,241,0.1)' },
    { label: 'Papers Imported', value: totalPapers, icon: FileText, color: '#8b5cf6', bg: 'rgba(139,92,246,0.1)' },
    { label: 'Chars Indexed', value: formatNum(totalChars), icon: Database, color: '#0ea5e9', bg: 'rgba(14,165,233,0.1)', isStr: true },
    { label: 'Quick Link', value: null, icon: BookOpen, color: '#10b981', bg: 'rgba(16,185,129,0.1)', isLink: true },
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
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <Layout>
      <div className="page-enter">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900 mb-1">Dashboard</h1>
          <p className="text-slate-500">Manage your research workspaces and track progress.</p>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {stats.map((s, i) => {
            const Icon = s.icon;
            return (
              <div key={i} className="bg-white rounded-2xl p-5 border border-slate-100 hover:shadow-lg transition-shadow duration-300" style={{ boxShadow: '0 1px 8px rgba(0,0,0,0.04)' }}>
                <div className="flex items-center justify-between mb-3">
                  <div className="p-2.5 rounded-xl" style={{ background: s.bg }}>
                    <Icon style={{ width: 18, height: 18, color: s.color }} />
                  </div>
                </div>
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">{s.label}</p>
                {s.isLink ? (
                  <Link to="/search" className="text-sm font-semibold" style={{ color: s.color }}>Search ArXiv →</Link>
                ) : (
                  <p className="text-2xl font-bold text-slate-900 count-up">
                    {loading ? '—' : (s.isStr ? s.value : s.value)}
                  </p>
                )}
              </div>
            );
          })}
        </div>

        {/* Workspace header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-900">Your Workspaces</h2>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white transition-all hover:opacity-90"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', boxShadow: '0 4px 12px rgba(99,102,241,0.35)' }}
          >
            <Plus className="h-4 w-4" /> New Workspace
          </button>
        </div>

        {/* Create Workspace Modal */}
        {showCreate && (
          <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.35)', backdropFilter: 'blur(4px)' }}>
            <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl mx-4">
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-lg font-bold text-slate-900">New Workspace</h3>
                <button onClick={() => setShowCreate(false)} className="text-slate-400 hover:text-slate-600"><X className="h-5 w-5" /></button>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Name *</label>
                  <input
                    value={newName} onChange={e => setNewName(e.target.value)}
                    placeholder="e.g. Transformer Research"
                    className="w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
                  <textarea
                    value={newDesc} onChange={e => setNewDesc(e.target.value)}
                    placeholder="Optional description..."
                    rows={3}
                    className="w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm text-slate-900 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>
              <div className="flex gap-3 mt-6">
                <button onClick={() => setShowCreate(false)} className="flex-1 py-2.5 rounded-xl border border-slate-200 text-sm font-medium text-slate-700 hover:bg-slate-50">Cancel</button>
                <button
                  onClick={handleCreate} disabled={creating || !newName.trim()}
                  className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white flex items-center justify-center gap-2 transition-opacity disabled:opacity-50"
                  style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
                >
                  {creating ? <><Loader2 className="h-4 w-4 animate-spin" /> Creating…</> : <><Check className="h-4 w-4" /> Create</>}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Workspaces grid */}
        {loading ? (
          <div className="flex items-center gap-2 text-slate-400 py-8"><Loader2 className="h-5 w-5 animate-spin" /> Loading workspaces…</div>
        ) : workspaces.length === 0 ? (
          <div className="bg-white rounded-2xl border border-dashed border-slate-200 p-12 text-center">
            <div className="w-14 h-14 rounded-2xl bg-indigo-50 flex items-center justify-center mx-auto mb-4">
              <Folder className="h-7 w-7 text-indigo-400" />
            </div>
            <h3 className="text-slate-700 font-semibold mb-1">No workspaces yet</h3>
            <p className="text-slate-400 text-sm mb-4">Create a workspace to start organising your research papers.</p>
            <button onClick={() => setShowCreate(true)} className="px-5 py-2 rounded-xl text-sm font-semibold text-white" style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}>
              Create your first workspace
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {workspaces.map((ws) => (
              <div key={ws.id} className="bg-white rounded-2xl border border-slate-100 p-5 hover:shadow-lg transition-all duration-200 group" style={{ boxShadow: '0 1px 8px rgba(0,0,0,0.04)' }}>
                <div className="flex items-start justify-between mb-3">
                  <div className="p-2 rounded-xl bg-indigo-50">
                    <Folder className="h-5 w-5 text-indigo-500" />
                  </div>
                  {deleteId === ws.id ? (
                    <div className="flex gap-2">
                      <button onClick={() => handleDelete(ws.id)} className="text-xs px-2.5 py-1 rounded-lg bg-red-100 text-red-700 font-medium hover:bg-red-200">Delete</button>
                      <button onClick={() => setDeleteId(null)} className="text-xs px-2.5 py-1 rounded-lg bg-slate-100 text-slate-600 font-medium hover:bg-slate-200">Cancel</button>
                    </div>
                  ) : (
                    <button onClick={() => setDeleteId(ws.id)} className="opacity-0 group-hover:opacity-100 transition-opacity text-slate-300 hover:text-red-400">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
                <h3 className="font-semibold text-slate-900 mb-1 truncate">{ws.name}</h3>
                <p className="text-sm text-slate-400 mb-3 line-clamp-2">{ws.description || 'No description'}</p>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400 bg-slate-50 px-2.5 py-1 rounded-full">
                    {ws.paperCount ?? 0} paper{ws.paperCount !== 1 ? 's' : ''} · {formatDate(ws.created_at)}
                  </span>
                  <div className="flex items-center gap-3">
                    <button onClick={() => handleExportWorkspace(ws.id, ws.name, 'bibtex')} className="text-xs font-semibold text-slate-500 hover:text-slate-700">Export</button>
                    <Link to={`/workspace/${ws.id}`} className="text-xs font-semibold text-indigo-500 hover:text-indigo-700">Open →</Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Dashboard;
