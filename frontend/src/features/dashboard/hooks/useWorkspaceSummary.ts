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
  fetchWorkspaces: () => Promise<void>;
}

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
          // Keep existing behavior: silent fallback create failure.
        }
      }
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
    fetchWorkspaces,
  };
};
