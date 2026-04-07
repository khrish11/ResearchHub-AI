import { useEffect, type Dispatch, type SetStateAction } from 'react';
import api from '../../../api';
import {
  LAST_WORKSPACE_KEY,
  getAgentChatHistory,
  getAgentSelections,
  saveAgentChatHistory,
  saveAgentSelections,
} from '../storage';
import type { ChatMessage, JsonRecord, Paper } from '../types';

interface UseAgentPersistenceParams {
  selectedWorkspace: number | null;
  resumeSelectedPaperIds: number[] | null;
  setPapers: Dispatch<SetStateAction<Paper[]>>;
  setSelectedPaperIds: Dispatch<SetStateAction<number[]>>;
  setSmartPaperId: Dispatch<SetStateAction<number | null>>;
  chatHistory: ChatMessage[];
  setChatHistory: Dispatch<SetStateAction<ChatMessage[]>>;
  selectedPaperIds: number[];
}

export const useAgentPersistence = ({
  selectedWorkspace,
  resumeSelectedPaperIds,
  setPapers,
  setSelectedPaperIds,
  setSmartPaperId,
  chatHistory,
  setChatHistory,
  selectedPaperIds,
}: UseAgentPersistenceParams) => {
  useEffect(() => {
    if (!selectedWorkspace) return;
    localStorage.setItem(LAST_WORKSPACE_KEY, String(selectedWorkspace));
    api
      .get(`/workspaces/${selectedWorkspace}`)
      .then((res) => {
        const list: Paper[] = (res.data?.papers || []).map((paper: unknown) => {
          const p = (paper || {}) as JsonRecord;
          return { id: Number(p.id || 0), title: String(p.title || '') };
        });
        setPapers(list);
        const selectionMap = getAgentSelections();
        const stored = Array.isArray(selectionMap[String(selectedWorkspace)]) ? selectionMap[String(selectedWorkspace)] : [];
        const validStored = stored.filter((paperId) => list.some((paper) => paper.id === paperId));
        const validResumed = (resumeSelectedPaperIds || []).filter((paperId) =>
          list.some((paper) => paper.id === paperId)
        );
        const defaults =
          validResumed.length > 0
            ? validResumed
            : validStored.length > 0
            ? validStored
            : list.slice(0, 3).map((paper) => paper.id);
        setSelectedPaperIds(defaults);
        setSmartPaperId(defaults[0] || list[0]?.id || null);
      })
      .catch(() => {
        setPapers([]);
        setSelectedPaperIds([]);
        setSmartPaperId(null);
      });
  }, [resumeSelectedPaperIds, selectedWorkspace, setPapers, setSelectedPaperIds, setSmartPaperId]);

  useEffect(() => {
    if (!selectedWorkspace) {
      setChatHistory([]);
      return;
    }
    const chatMap = getAgentChatHistory();
    const workspaceHistory = Array.isArray(chatMap[String(selectedWorkspace)])
      ? chatMap[String(selectedWorkspace)]
      : [];
    setChatHistory(workspaceHistory.slice(-24));
  }, [selectedWorkspace, setChatHistory]);

  useEffect(() => {
    if (!selectedWorkspace) return;
    const chatMap = getAgentChatHistory();
    chatMap[String(selectedWorkspace)] = [...chatHistory].slice(-24);
    saveAgentChatHistory(chatMap);
  }, [chatHistory, selectedWorkspace]);

  useEffect(() => {
    if (!selectedWorkspace) return;
    const selectionMap = getAgentSelections();
    selectionMap[String(selectedWorkspace)] = [...selectedPaperIds];
    saveAgentSelections(selectionMap);
  }, [selectedPaperIds, selectedWorkspace]);
};
