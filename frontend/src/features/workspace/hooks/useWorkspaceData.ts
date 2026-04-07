import { useCallback, useEffect, useState, type Dispatch, type SetStateAction } from 'react';
import api from '../../../api';
import type { Paper, WorkspaceDetail, WorkspaceTab } from '../types';

export interface WorkspaceRestoreState {
  reportTopic: string;
  chatPaperIds: number[];
  faultPaperId: number | null;
  selectedPaperId: number | null;
  activeTab?: WorkspaceTab;
}

interface UseWorkspaceDataResult {
  workspace: WorkspaceDetail | null;
  setWorkspace: Dispatch<SetStateAction<WorkspaceDetail | null>>;
  loading: boolean;
  error: string | null;
  setError: Dispatch<SetStateAction<string | null>>;
  reload: () => Promise<void>;
}

export const useWorkspaceData = (
  id: string | undefined,
  onRestore?: (state: WorkspaceRestoreState) => void
): UseWorkspaceDataResult => {
  const [workspace, setWorkspace] = useState<WorkspaceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!id) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [workspaceRes, sessionRes] = await Promise.all([
        api.get(`/workspaces/${id}`),
        api.get('/workspaces/session-state').catch(() => ({ data: null })),
      ]);
      const data = workspaceRes.data as WorkspaceDetail;
      setWorkspace(data);
      const paperIds = (data?.papers || []).map((paper: Paper) => paper.id);

      const extra = sessionRes?.data?.extra && typeof sessionRes.data.extra === 'object' ? sessionRes.data.extra : {};
      const restoredIds = Array.isArray(extra.selected_chat_paper_ids)
        ? extra.selected_chat_paper_ids.map((value: unknown) => Number(value)).filter((value: number) => paperIds.includes(value))
        : [];
      const restoredFault = Number(extra.fault_paper_id || 0);
      const restoredSelectedPaper = Number(extra.selected_paper_id || 0);
      const restoredTab = String(extra.active_tab || '');
      const activeTab =
        restoredTab === 'papers' || restoredTab === 'chat' || restoredTab === 'review' || restoredTab === 'ops'
          ? restoredTab
          : undefined;

      onRestore?.({
        reportTopic: data?.name ? `${data.name} literature synthesis` : '',
        chatPaperIds: restoredIds.length > 0 ? restoredIds : paperIds,
        faultPaperId: paperIds.includes(restoredFault) ? restoredFault : paperIds[0] ?? null,
        selectedPaperId: paperIds.includes(restoredSelectedPaper) ? restoredSelectedPaper : paperIds[0] ?? null,
        activeTab,
      });
    } catch {
      setError('Failed to load workspace.');
    } finally {
      setLoading(false);
    }
  }, [id, onRestore]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { workspace, setWorkspace, loading, error, setError, reload };
};
