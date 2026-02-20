import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Folder, FileText, Search, Trash2, Plus } from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';

interface Workspace {
  id: number;
  name: string;
  description?: string;
  created_at?: string;
}

const Dashboard = () => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalPapers, setTotalPapers] = useState(0);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await api.get('/workspaces/');
        setWorkspaces(res.data);
        // Calculate total papers across all workspaces
        let total = 0;
        for (const ws of res.data) {
          try {
            const wsDetail = await api.get(`/workspaces/${ws.id}`);
            total += wsDetail.data.papers?.length || 0;
          } catch {
            // Skip if workspace detail fails
          }
        }
        setTotalPapers(total);
      } catch (err) {
        console.error('Failed to fetch workspaces', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'No date';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: 'numeric' });
    } catch {
      return 'No date';
    }
  };

  return (
    <Layout userEmail="user@example.com" userInitials="U">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 mb-2">Dashboard</h1>
        <p className="text-slate-600 mb-6">Manage your research workspaces</p>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-indigo-100 rounded-lg">
                <Folder className="h-5 w-5 text-indigo-600" />
              </div>
              <div>
                <p className="text-sm text-slate-600">Total Workspaces</p>
                <p className="text-2xl font-bold text-slate-900">{workspaces.length}</p>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-indigo-100 rounded-lg">
                <FileText className="h-5 w-5 text-indigo-600" />
              </div>
              <div>
                <p className="text-sm text-slate-600">Papers Imported</p>
                <p className="text-2xl font-bold text-slate-900">{totalPapers}</p>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-indigo-100 rounded-lg">
                <Search className="h-5 w-5 text-indigo-600" />
              </div>
              <div>
                <p className="text-sm text-slate-600">Quick Actions</p>
                <Link to="/search" className="text-sm font-medium text-indigo-600 hover:text-indigo-700">
                  Search Papers →
                </Link>
              </div>
            </div>
          </div>
        </div>

        {/* Create New Workspace Button */}
        <div className="mb-6">
          <button className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors">
            <Plus className="h-5 w-5" />
            Create New Workspace
          </button>
        </div>

        {/* Workspace Grid */}
        {loading ? (
          <div className="text-slate-500">Loading workspaces...</div>
        ) : workspaces.length === 0 ? (
          <div className="bg-white rounded-lg border border-slate-200 p-8 text-center">
            <Folder className="h-12 w-12 text-slate-400 mx-auto mb-4" />
            <p className="text-slate-600">No workspaces yet. Create your first workspace to get started.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {workspaces.map((workspace) => (
              <div key={workspace.id} className="bg-white rounded-lg border border-slate-200 p-4 hover:shadow-md transition-shadow">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-semibold text-slate-900">{workspace.name}</h3>
                  <button className="text-slate-400 hover:text-red-600">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
                <p className="text-sm text-slate-500 mb-2">{workspace.description || 'No description'}</p>
                <p className="text-xs text-slate-400 mb-3">Created {formatDate(workspace.created_at)}</p>
                <Link
                  to={`/workspace/${workspace.id}`}
                  className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
                >
                  Open Workspace →
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Dashboard;
