import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Folder, Plus, FileText, MessageSquare, Loader2, ArrowRight } from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';
import { useToast } from '../contexts/ToastContext';

interface Workspace {
  id: number;
  name: string;
  description?: string;
  papers_count?: number;
  chats_count?: number;
  updated_at?: string;
}

const Workspaces: React.FC = () => {
  const { success: toastSuccess, error: toastError } = useToast();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    const fetchWorkspaces = async () => {
      try {
        const response = await api.get('/workspaces/');
        setWorkspaces(response.data || []);
      } catch {
        toastError('Failed to load workspaces');
      } finally {
        setLoading(false);
      }
    };

    void fetchWorkspaces();
  }, [toastError]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) {
      toastError('Workspace name is required');
      return;
    }

    setCreating(true);
    try {
      const response = await api.post('/workspaces/', {
        name: newName.trim(),
        description: newDesc.trim() || undefined,
      });
      setWorkspaces([response.data, ...workspaces]);
      setNewName('');
      setNewDesc('');
      setShowCreate(false);
      toastSuccess('Workspace created successfully');
    } catch {
      toastError('Failed to create workspace');
    } finally {
      setCreating(false);
    }
  };

  return (
    <Layout>
      <div className="mx-auto max-w-5xl px-4 py-12">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              Workspaces
            </h1>
            <p className="mt-2 text-lg text-slate-600 dark:text-slate-400">
              Organize your research into focused workspaces.
            </p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            data-testid="create-workspace"
            className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 transition shadow-sm"
          >
            <Plus className="h-4 w-4" />
            Create Workspace
          </button>
        </div>

        {showCreate && (
          <div className="mb-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <form onSubmit={handleCreate}>
              <div className="mb-4">
                <label htmlFor="workspace-name" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Workspace Name
                </label>
                <input
                  id="workspace-name"
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g., Literature Review on GNNs"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                  autoFocus
                />
              </div>
              <div className="mb-4">
                <label htmlFor="workspace-desc" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Description (optional)
                </label>
                <textarea
                  id="workspace-desc"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="Brief description of your research focus..."
                  rows={3}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                />
              </div>
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={creating}
                  className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 transition disabled:opacity-50"
                >
                  {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                  Create Workspace
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowCreate(false);
                    setNewName('');
                    setNewDesc('');
                  }}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
          </div>
        ) : workspaces.length === 0 ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <Folder className="mx-auto h-12 w-12 text-slate-400" />
            <h3 className="mt-4 text-lg font-semibold text-slate-900 dark:text-slate-100">
              No workspaces yet
            </h3>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
              Create your first workspace to start organizing your research.
            </p>
            <button
              onClick={() => setShowCreate(true)}
              className="mt-4 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 transition"
            >
              <Plus className="h-4 w-4" />
              Create Workspace
            </button>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {workspaces.map((workspace) => (
              <Link
                key={workspace.id}
                to={`/workspace/${workspace.id}`}
                className="group rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition-all hover:shadow-md hover:border-indigo-300 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-indigo-600"
              >
                <div className="mb-4 flex items-start justify-between">
                  <div className="inline-flex rounded-xl bg-indigo-100 p-3 text-indigo-600 dark:bg-indigo-900 dark:text-indigo-300">
                    <Folder className="h-6 w-6" />
                  </div>
                  <div className="flex gap-2 text-xs text-slate-500 dark:text-slate-400">
                    <div className="flex items-center gap-1">
                      <FileText className="h-3 w-3" />
                      {workspace.papers_count || 0}
                    </div>
                    <div className="flex items-center gap-1">
                      <MessageSquare className="h-3 w-3" />
                      {workspace.chats_count || 0}
                    </div>
                  </div>
                </div>
                <h2 className="mb-2 text-lg font-semibold text-slate-900 dark:text-slate-100 line-clamp-1">
                  {workspace.name}
                </h2>
                {workspace.description && (
                  <p className="mb-4 text-sm text-slate-600 dark:text-slate-400 line-clamp-2">
                    {workspace.description}
                  </p>
                )}
                <div className="flex items-center text-sm font-medium text-indigo-600 dark:text-indigo-400 group-hover:underline">
                  Open workspace
                  <ArrowRight className="ml-1 h-4 w-4" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Workspaces;
