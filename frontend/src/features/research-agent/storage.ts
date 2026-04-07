import type { ChatMessage } from './types';

export const LAST_WORKSPACE_KEY = 'researchhub.last_workspace_id';
export const AGENT_SELECTIONS_KEY = 'researchhub.research_agent.paper_selection.v1';
export const AGENT_CHAT_KEY = 'researchhub.research_agent.chat_history.v1';

export const getAgentSelections = (): Record<string, number[]> => {
  try {
    const raw = localStorage.getItem(AGENT_SELECTIONS_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return {};
    return parsed as Record<string, number[]>;
  } catch {
    return {};
  }
};

export const saveAgentSelections = (value: Record<string, number[]>) => {
  localStorage.setItem(AGENT_SELECTIONS_KEY, JSON.stringify(value));
};

export const getAgentChatHistory = (): Record<string, ChatMessage[]> => {
  try {
    const raw = localStorage.getItem(AGENT_CHAT_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return {};
    return parsed as Record<string, ChatMessage[]>;
  } catch {
    return {};
  }
};

export const saveAgentChatHistory = (value: Record<string, ChatMessage[]>) => {
  localStorage.setItem(AGENT_CHAT_KEY, JSON.stringify(value));
};
