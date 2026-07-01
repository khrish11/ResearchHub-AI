import { useCallback, useState, type Dispatch, type SetStateAction } from 'react';
import api from '../../../api';
import type { Workspace, WorkspacePaper } from '../types';

interface UseWorkspaceSummaryResult {
  workspaces: Workspace[];
  setWorkspaces: Dispatch<SetStateAction<Workspace[]>>;
  loading: boolean;
  setLoading: Dispatch<SetStateAction<boolean>>;
  totalPapers: number;
  totalChars: number;
  isUserCreatedWorkspace: boolean;
  fetchWorkspaces: () => Promise<void>;
}

const isUserCreatedWorkspace = (workspace: Workspace): boolean => {
  const candidate = workspace as Workspace & { is_user_created?: boolean | null };
  if (typeof candidate.is_user_created === 'boolean') {
    return candidate.is_user_created;
  }
  const name = String(workspace.name || '').trim().toLowerCase();
  if (!name) {
    return false;
  }
  if (['my research workspace', 'default workspace', 'research workspace', 'workspace'].includes(name)) {
    return false;
  }
  if (name.includes('default') || name.includes('auto') || name.includes('system')) {
    return false;
  }
  return true;
};

export const useWorkspaceSummary = (): UseWorkspaceSummaryResult => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalPapers, setTotalPapers] = useState(0);
  const [totalChars, setTotalChars] = useState(0);

  const fetchWorkspaces = useCallback(async () => {
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
            return { ...ws, paperCount: pc, is_user_created: isUserCreatedWorkspace(ws) };
          } catch {
            return { ...ws, paperCount: 0, is_user_created: isUserCreatedWorkspace(ws) };
          }
        })
      );
      setWorkspaces(enriched);
      setTotalPapers(papers);
      setTotalChars(chars);
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    workspaces,
    setWorkspaces,
    loading,
    setLoading,
    totalPapers,
    totalChars,
    isUserCreatedWorkspace: workspaces.some(isUserCreatedWorkspace),
    fetchWorkspaces,
  };
};
