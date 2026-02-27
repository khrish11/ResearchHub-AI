import React, { useEffect, useMemo, useState } from 'react';
import { Loader2, Search, ShieldCheck, AlertTriangle, RefreshCw, Database } from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';
import { apiErrorMessage } from '../utils/apiError';

interface DevSummary {
  users: number;
  workspaces: number;
  papers: number;
  chats: number;
}

interface DevUser {
  id: number;
  email: string;
  name?: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at?: string | null;
  workspace_count: number;
  paper_count: number;
  chat_count: number;
}

interface DevOverviewResponse {
  summary: DevSummary;
  recent_users: DevUser[];
  generated_at: string;
}

interface DevUsersResponse {
  total: number;
  offset: number;
  limit: number;
  users: DevUser[];
}

interface DevWorkspace {
  id: number;
  name: string;
  created_at?: string | null;
  paper_count: number;
  chat_count: number;
  papers: Array<{
    id: number;
    title: string;
    doi?: string | null;
    url?: string | null;
    authors?: string | null;
  }>;
}

interface DevUserDetailResponse {
  user: DevUser;
  workspaces: DevWorkspace[];
}

const DEV_KEY_STORAGE = 'researchhub.dev_access_key';

const csvEscape = (value: unknown): string => {
  const raw = String(value ?? '');
  const escaped = raw.replace(/"/g, '""');
  return `"${escaped}"`;
};

const downloadCsv = (filename: string, headers: string[], rows: Array<Array<unknown>>) => {
  const csv = [headers.map(csvEscape).join(','), ...rows.map((row) => row.map(csvEscape).join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
};

const DeveloperConsole: React.FC = () => {
  const [devKey, setDevKey] = useState<string>(() => localStorage.getItem(DEV_KEY_STORAGE) || '');
  const [canAccess, setCanAccess] = useState<boolean>(false);
  const [accessError, setAccessError] = useState<string | null>(null);
  const [checkingAccess, setCheckingAccess] = useState<boolean>(true);

  const [overview, setOverview] = useState<DevOverviewResponse | null>(null);
  const [users, setUsers] = useState<DevUser[]>([]);
  const [usersTotal, setUsersTotal] = useState<number>(0);
  const [query, setQuery] = useState<string>('');
  const [loadingUsers, setLoadingUsers] = useState<boolean>(false);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [selectedUserDetail, setSelectedUserDetail] = useState<DevUserDetailResponse | null>(null);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);

  const headers = useMemo(() => {
    if (!devKey.trim()) return undefined;
    return { 'X-Dev-Key': devKey.trim() };
  }, [devKey]);

  const saveDevKey = (value: string) => {
    setDevKey(value);
    if (value.trim()) {
      localStorage.setItem(DEV_KEY_STORAGE, value.trim());
    } else {
      localStorage.removeItem(DEV_KEY_STORAGE);
    }
  };

  const checkAccess = async () => {
    setCheckingAccess(true);
    setAccessError(null);
    try {
      await api.get('/developer/access', { headers });
      setCanAccess(true);
    } catch (err: unknown) {
      setCanAccess(false);
      setAccessError(apiErrorMessage(err, 'Developer access denied.'));
    } finally {
      setCheckingAccess(false);
    }
  };

  const loadOverview = async () => {
    try {
      const res = await api.get<DevOverviewResponse>('/developer/overview', { headers });
      setOverview(res.data);
    } catch (err: unknown) {
      setAccessError(apiErrorMessage(err, 'Failed to load developer overview.'));
    }
  };

  const loadUsers = async (nextQuery: string) => {
    setLoadingUsers(true);
    try {
      const res = await api.get<DevUsersResponse>('/developer/users', {
        headers,
        params: {
          q: nextQuery.trim() || undefined,
          limit: 80,
          offset: 0,
        },
      });
      setUsers(res.data.users || []);
      setUsersTotal(Number(res.data.total || 0));
      if (!selectedUserId && (res.data.users || []).length > 0) {
        setSelectedUserId(res.data.users[0].id);
      }
    } catch (err: unknown) {
      setAccessError(apiErrorMessage(err, 'Failed to load developer users.'));
      setUsers([]);
      setUsersTotal(0);
    } finally {
      setLoadingUsers(false);
    }
  };

  const loadUserDetail = async (userId: number) => {
    setLoadingDetail(true);
    try {
      const res = await api.get<DevUserDetailResponse>(`/developer/users/${userId}`, { headers });
      setSelectedUserDetail(res.data);
    } catch (err: unknown) {
      setAccessError(apiErrorMessage(err, 'Failed to load user detail.'));
      setSelectedUserDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  };

  const exportUsersCsv = () => {
    if (users.length === 0) return;
    downloadCsv(
      'developer_users.csv',
      ['id', 'email', 'name', 'is_active', 'is_verified', 'workspace_count', 'paper_count', 'chat_count', 'created_at'],
      users.map((user) => [
        user.id,
        user.email,
        user.name || '',
        user.is_active ? 'true' : 'false',
        user.is_verified ? 'true' : 'false',
        user.workspace_count,
        user.paper_count,
        user.chat_count,
        user.created_at || '',
      ])
    );
  };

  const exportWorkspacesCsv = () => {
    const detail = selectedUserDetail;
    if (!detail) return;
    downloadCsv(
      `developer_user_${detail.user.id}_workspaces.csv`,
      ['user_id', 'workspace_id', 'workspace_name', 'created_at', 'paper_count', 'chat_count'],
      detail.workspaces.map((workspace) => [
        detail.user.id,
        workspace.id,
        workspace.name,
        workspace.created_at || '',
        workspace.paper_count,
        workspace.chat_count,
      ])
    );
  };

  const exportPapersCsv = () => {
    const detail = selectedUserDetail;
    if (!detail) return;
    const rows: Array<Array<unknown>> = [];
    for (const workspace of detail.workspaces) {
      for (const paper of workspace.papers) {
        rows.push([
          detail.user.id,
          workspace.id,
          workspace.name,
          paper.id,
          paper.title,
          paper.authors || '',
          paper.doi || '',
          paper.url || '',
        ]);
      }
    }
    if (rows.length === 0) return;
    downloadCsv(
      `developer_user_${detail.user.id}_papers.csv`,
      ['user_id', 'workspace_id', 'workspace_name', 'paper_id', 'title', 'authors', 'doi', 'url'],
      rows
    );
  };

  useEffect(() => {
    void checkAccess();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!canAccess) return;
    void loadOverview();
    void loadUsers(query);
  }, [canAccess]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!canAccess || selectedUserId == null) return;
    void loadUserDetail(selectedUserId);
  }, [canAccess, selectedUserId]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Layout>
      <div className="space-y-4">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500 mb-1 inline-flex items-center gap-1.5">
                <Database className="h-3.5 w-3.5 text-indigo-500" />
                Developer Console
              </p>
              <h2 className="text-2xl font-bold text-slate-900">User Data Access</h2>
              <p className="text-sm text-slate-500 mt-1">
                Browse users, workspaces, and imported papers from one page.
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                void checkAccess();
                if (canAccess) {
                  void loadOverview();
                  void loadUsers(query);
                }
              }}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]">
            <input
              value={devKey}
              onChange={(e) => saveDevKey(e.target.value)}
              placeholder="Optional X-Dev-Key for developer endpoints"
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={() => {
                void checkAccess();
                setOverview(null);
                setUsers([]);
                setSelectedUserDetail(null);
              }}
              className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white"
            >
              Verify Access
            </button>
          </div>

          {checkingAccess ? (
            <p className="mt-3 inline-flex items-center gap-2 text-sm text-slate-600">
              <Loader2 className="h-4 w-4 animate-spin" />
              Checking developer access...
            </p>
          ) : canAccess ? (
            <p className="mt-3 inline-flex items-center gap-2 text-sm text-emerald-700">
              <ShieldCheck className="h-4 w-4" />
              Developer access enabled.
            </p>
          ) : (
            <p className="mt-3 inline-flex items-center gap-2 text-sm text-rose-700">
              <AlertTriangle className="h-4 w-4" />
              {accessError || 'Developer access denied.'}
            </p>
          )}
        </section>

        {canAccess && (
          <>
            {overview && (
              <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
                  <p className="text-xs text-slate-500">Users</p>
                  <p className="text-2xl font-bold text-slate-900">{overview.summary.users}</p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
                  <p className="text-xs text-slate-500">Workspaces</p>
                  <p className="text-2xl font-bold text-slate-900">{overview.summary.workspaces}</p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
                  <p className="text-xs text-slate-500">Papers</p>
                  <p className="text-2xl font-bold text-slate-900">{overview.summary.papers}</p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
                  <p className="text-xs text-slate-500">Chats</p>
                  <p className="text-2xl font-bold text-slate-900">{overview.summary.chats}</p>
                </div>
              </section>
            )}

            <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1.15fr_1fr]">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-900">Users ({usersTotal})</p>
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="relative">
                      <Search className="absolute left-2 top-2.5 h-4 w-4 text-slate-400" />
                      <input
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Search by email or name"
                        className="w-64 rounded-xl border border-slate-200 py-2 pl-8 pr-3 text-sm"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => void loadUsers(query)}
                      className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700"
                    >
                      Search
                    </button>
                    <button
                      type="button"
                      onClick={exportUsersCsv}
                      disabled={users.length === 0}
                      className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50"
                    >
                      Export Users CSV
                    </button>
                  </div>
                </div>

                <div className="mt-3 max-h-[520px] overflow-auto rounded-xl border border-slate-200">
                  <table className="min-w-full text-left text-sm">
                    <thead className="sticky top-0 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                      <tr>
                        <th className="px-3 py-2">Email</th>
                        <th className="px-3 py-2">WS</th>
                        <th className="px-3 py-2">Papers</th>
                        <th className="px-3 py-2">Active</th>
                      </tr>
                    </thead>
                    <tbody>
                      {loadingUsers ? (
                        <tr>
                          <td className="px-3 py-4 text-slate-500" colSpan={4}>
                            Loading users...
                          </td>
                        </tr>
                      ) : users.length === 0 ? (
                        <tr>
                          <td className="px-3 py-4 text-slate-500" colSpan={4}>
                            No users found.
                          </td>
                        </tr>
                      ) : (
                        users.map((user) => {
                          const selected = selectedUserId === user.id;
                          return (
                            <tr
                              key={user.id}
                              onClick={() => setSelectedUserId(user.id)}
                              className={`cursor-pointer border-t border-slate-100 ${selected ? 'bg-indigo-50' : 'hover:bg-slate-50'}`}
                            >
                              <td className="px-3 py-2">
                                <p className="font-medium text-slate-900">{user.email}</p>
                                {user.name ? <p className="text-xs text-slate-500">{user.name}</p> : null}
                              </td>
                              <td className="px-3 py-2 text-slate-700">{user.workspace_count}</td>
                              <td className="px-3 py-2 text-slate-700">{user.paper_count}</td>
                              <td className="px-3 py-2">
                                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${user.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
                                  {user.is_active ? 'Yes' : 'No'}
                                </span>
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-900">Selected User Detail</p>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={exportWorkspacesCsv}
                      disabled={!selectedUserDetail || selectedUserDetail.workspaces.length === 0}
                      className="rounded-xl border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-50"
                    >
                      Export Workspaces CSV
                    </button>
                    <button
                      type="button"
                      onClick={exportPapersCsv}
                      disabled={!selectedUserDetail || selectedUserDetail.workspaces.every((workspace) => workspace.papers.length === 0)}
                      className="rounded-xl border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-50"
                    >
                      Export Papers CSV
                    </button>
                  </div>
                </div>
                {!selectedUserId ? (
                  <p className="mt-3 text-sm text-slate-500">Select a user to inspect workspaces and papers.</p>
                ) : loadingDetail ? (
                  <p className="mt-3 inline-flex items-center gap-2 text-sm text-slate-500">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading detail...
                  </p>
                ) : selectedUserDetail ? (
                  <div className="mt-3 space-y-3">
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <p className="font-semibold text-slate-900">{selectedUserDetail.user.email}</p>
                      <p className="text-xs text-slate-500 mt-0.5">
                        Workspaces: {selectedUserDetail.user.workspace_count} | Papers: {selectedUserDetail.user.paper_count} | Chats: {selectedUserDetail.user.chat_count}
                      </p>
                    </div>

                    <div className="max-h-[460px] space-y-2 overflow-auto pr-1">
                      {selectedUserDetail.workspaces.map((workspace) => (
                        <article key={workspace.id} className="rounded-xl border border-slate-200 p-3">
                          <p className="text-sm font-semibold text-slate-900">{workspace.name}</p>
                          <p className="mt-0.5 text-xs text-slate-500">
                            Papers: {workspace.paper_count} | Chats: {workspace.chat_count}
                          </p>
                          <ul className="mt-2 space-y-1 text-xs text-slate-700">
                            {workspace.papers.slice(0, 6).map((paper) => (
                              <li key={paper.id} className="line-clamp-2">
                                {paper.title}
                              </li>
                            ))}
                          </ul>
                        </article>
                      ))}
                      {selectedUserDetail.workspaces.length === 0 && (
                        <p className="text-sm text-slate-500">No workspace data for this user.</p>
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-slate-500">No detail loaded.</p>
                )}
              </div>
            </section>
          </>
        )}
      </div>
    </Layout>
  );
};

export default DeveloperConsole;
