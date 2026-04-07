import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, Bot, CheckCircle2, ExternalLink, Loader2, MessageSquare, Mic, MicOff, SendHorizonal, Sparkles, Trash2 } from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';
import { apiErrorMessage } from '../utils/apiError';

interface Workspace {
  id: number;
  name: string;
}

interface Paper {
  id: number;
  title: string;
  authors: string;
  abstract: string;
}

interface ChatCitation {
  label: string;
  paper_id: number;
  title: string;
  doi?: string;
  url?: string;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
  actions?: string[];
  citations?: ChatCitation[];
  confidence?: number;
  evidenceMap?: string[];
}

interface ResearchChatResponse {
  reply?: string;
  actions?: string[];
  citations?: ChatCitation[];
  confidence?: number;
  suggested_queries?: string[];
  evidence_map?: string[];
}

interface SpeechRecognitionAlternativeLike {
  transcript: string;
}

interface SpeechRecognitionResultLike {
  isFinal: boolean;
  length: number;
  [index: number]: SpeechRecognitionAlternativeLike;
}

interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: SpeechRecognitionResultLike[];
}

interface SpeechRecognitionErrorEventLike {
  error?: string;
}

interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

interface SpeechRecognitionCtor {
  new (): SpeechRecognitionLike;
}

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  }
}

const LAST_WORKSPACE_KEY = 'researchhub.last_workspace_id';
const RESEARCH_CHAT_STORE_KEY = 'researchhub.research_chat.v1';

interface StoredChatCitationLike {
  label?: unknown;
  paper_id?: unknown;
  title?: unknown;
  doi?: unknown;
  url?: unknown;
}

interface StoredChatMessageLike {
  role?: unknown;
  content?: unknown;
  createdAt?: unknown;
  actions?: unknown;
  citations?: unknown;
  confidence?: unknown;
  evidenceMap?: unknown;
}

const isStoredChatMessageLike = (value: unknown): value is StoredChatMessageLike => {
  if (!value || typeof value !== 'object') return false;
  const record = value as StoredChatMessageLike;
  return (
    (record.role === 'user' || record.role === 'assistant') &&
    typeof record.content === 'string'
  );
};

const loadStoredThreads = (): Record<string, ChatMessage[]> => {
  try {
    const raw = localStorage.getItem(RESEARCH_CHAT_STORE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return {};
    const out: Record<string, ChatMessage[]> = {};
    Object.entries(parsed).forEach(([key, value]) => {
      if (!Array.isArray(value)) return;
      const messages = value
        .filter(isStoredChatMessageLike)
        .map((item) => ({
          role: item.role as 'user' | 'assistant',
          content: String(item.content || ''),
          createdAt: String(item.createdAt || new Date().toISOString()),
          actions: Array.isArray(item.actions) ? item.actions.map((x: unknown) => String(x)) : [],
          citations: Array.isArray(item.citations)
            ? item.citations
                .filter((ref): ref is StoredChatCitationLike => Boolean(ref) && typeof ref === 'object')
                .map((ref) => ({
                  label: String(ref.label || ''),
                  paper_id: Number(ref.paper_id || 0),
                  title: String(ref.title || ''),
                  doi: String(ref.doi || ''),
                  url: String(ref.url || ''),
                }))
                .filter((ref) => ref.label && ref.title)
            : [],
          confidence: Number.isFinite(Number(item.confidence)) ? Number(item.confidence) : undefined,
          evidenceMap: Array.isArray(item.evidenceMap)
            ? item.evidenceMap.map((x: unknown) => String(x))
            : [],
        }));
      out[key] = messages.slice(-24);
    });
    return out;
  } catch {
    return {};
  }
};

const saveStoredThreads = (value: Record<string, ChatMessage[]>) => {
  localStorage.setItem(RESEARCH_CHAT_STORE_KEY, JSON.stringify(value));
};

const WritingChat: React.FC = () => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWsId, setSelectedWsId] = useState<number | null>(null);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [selectedPaperIds, setSelectedPaperIds] = useState<Set<number>>(new Set());
  const [contextText, setContextText] = useState('');
  const [chatInput, setChatInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadingWorkspace, setLoadingWorkspace] = useState(true);
  const [loadingPapers, setLoadingPapers] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [speechError, setSpeechError] = useState<string | null>(null);
  const [responseStyle, setResponseStyle] = useState<'concise' | 'balanced' | 'deep'>('balanced');
  const [groundedOnly, setGroundedOnly] = useState(true);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const baseInputRef = useRef('');
  const finalTranscriptRef = useRef('');

  const selectedCount = selectedPaperIds.size;
  const selectedWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === selectedWsId) || null,
    [selectedWsId, workspaces]
  );

  useEffect(() => {
    let mounted = true;
    const boot = async () => {
      try {
        const [workspaceRes, sessionRes] = await Promise.all([
          api.get<Workspace[]>('/workspaces/'),
          api.get('/workspaces/session-state').catch(() => ({ data: null })),
        ]);
        if (!mounted) return;
        const list = workspaceRes.data || [];
        setWorkspaces(list);
        if (list.length > 0) {
          const stored = Number(localStorage.getItem(LAST_WORKSPACE_KEY));
          const resumedWs = Number(sessionRes?.data?.workspace_id || 0);
          const preferred = [resumedWs, stored].find(
            (candidate) => Number.isFinite(candidate) && list.some((workspace) => workspace.id === candidate)
          );
          setSelectedWsId(preferred || list[0].id);
        }
        const restoredContext = String(sessionRes?.data?.draft_text || '').trim();
        if (restoredContext) setContextText(restoredContext);
      } catch {
        if (mounted) setError('Failed to load workspaces.');
      } finally {
        if (mounted) setLoadingWorkspace(false);
      }
    };
    void boot();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedWsId) return;
    localStorage.setItem(LAST_WORKSPACE_KEY, String(selectedWsId));
    setLoadingPapers(true);
    setError(null);
    api
      .get(`/workspaces/${selectedWsId}`)
      .then((res) => {
        const wsPapers: Paper[] = res.data?.papers || [];
        setPapers(wsPapers);
        setSelectedPaperIds(new Set(wsPapers.slice(0, 14).map((paper) => paper.id)));
      })
      .catch(() => setError('Failed to load papers for this workspace.'))
      .finally(() => setLoadingPapers(false));

    const store = loadStoredThreads();
    const wsMessages = store[String(selectedWsId)] || [];
    setMessages(wsMessages);
  }, [selectedWsId]);

  useEffect(() => {
    if (!selectedWsId) return;
    const timer = window.setTimeout(() => {
      void api
        .put('/workspaces/session-state', {
          page_path: '/research-chat',
          workspace_id: selectedWsId,
          draft_text: contextText.slice(0, 12000),
          extra: {
            selected_paper_ids: Array.from(selectedPaperIds),
            research_chat_turns: messages.length,
          },
        })
        .catch(() => undefined);
    }, 700);
    return () => window.clearTimeout(timer);
  }, [contextText, messages.length, selectedPaperIds, selectedWsId]);

  useEffect(() => {
    if (!selectedWsId) return;
    const store = loadStoredThreads();
    store[String(selectedWsId)] = messages.slice(-24);
    saveStoredThreads(store);
  }, [messages, selectedWsId]);

  useEffect(() => {
    setSpeechSupported(Boolean(window.SpeechRecognition || window.webkitSpeechRecognition));
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
        recognitionRef.current = null;
      }
    };
  }, []);

  const togglePaper = (paperId: number) => {
    setSelectedPaperIds((prev) => {
      const next = new Set(prev);
      if (next.has(paperId)) next.delete(paperId);
      else next.add(paperId);
      return next;
    });
  };

  const pushUserMessage = (content: string): ChatMessage => ({
    role: 'user',
    content,
    createdAt: new Date().toISOString(),
  });

  const pushAssistantMessage = (payload: ResearchChatResponse): ChatMessage => ({
    role: 'assistant',
    content: String(payload.reply || 'No response generated.'),
    actions: Array.isArray(payload.actions)
      ? [...payload.actions.map((item) => String(item)), ...(payload.suggested_queries || []).map((item) => String(item))]
          .filter(Boolean)
          .slice(0, 8)
      : [],
    citations: Array.isArray(payload.citations) ? payload.citations.slice(0, 8) : [],
    confidence: Number.isFinite(Number(payload.confidence)) ? Number(payload.confidence) : undefined,
    evidenceMap: Array.isArray(payload.evidence_map) ? payload.evidence_map.map((item) => String(item)).slice(0, 8) : [],
    createdAt: new Date().toISOString(),
  });

  const sendMessage = async () => {
    const trimmed = chatInput.trim();
    if (!trimmed || !selectedWsId) return;
    const selectedIds = Array.from(selectedPaperIds);

    const nextUserMessage = pushUserMessage(trimmed);
    const convoPayload = [...messages, nextUserMessage].slice(-12).map((item) => ({
      role: item.role,
      content: item.content,
    }));

    setMessages((prev) => [...prev, nextUserMessage]);
    setChatInput('');
    setSending(true);
    setError(null);

    try {
      const response = await api.post<ResearchChatResponse>('/research/chatbot', {
        workspace_id: selectedWsId,
        paper_ids: selectedIds,
        topic: selectedWorkspace?.name || 'Workspace context',
        context_text: contextText,
        message: trimmed,
        conversation: convoPayload,
        max_actions: 6,
        response_style: responseStyle,
        grounded_only: groundedOnly,
      });
      const assistantMessage = pushAssistantMessage(response.data || {});
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: unknown) {
      const primaryError = apiErrorMessage(err, 'Research chatbot failed.');
      const shouldRetryWithoutSelection =
        selectedIds.length > 0 &&
        /paper selection|selected papers|no papers|workspace selection/i.test(
          primaryError.toLowerCase()
        );

      if (shouldRetryWithoutSelection) {
        try {
          const retry = await api.post<ResearchChatResponse>('/research/chatbot', {
            workspace_id: selectedWsId,
            topic: selectedWorkspace?.name || 'Workspace context',
            context_text: contextText,
            message: trimmed,
            conversation: convoPayload,
            max_actions: 6,
            response_style: responseStyle,
            grounded_only: groundedOnly,
          });
          const assistantMessage = pushAssistantMessage(retry.data || {});
          setMessages((prev) => [...prev, assistantMessage]);
          setError(null);
          return;
        } catch (retryErr: unknown) {
          setError(apiErrorMessage(retryErr, primaryError));
        }
      } else {
        setError(primaryError);
      }
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'I could not process that. Verify paper selection and try again.',
          createdAt: new Date().toISOString(),
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const clearThread = () => {
    setMessages([]);
    if (selectedWsId) {
      const store = loadStoredThreads();
      store[String(selectedWsId)] = [];
      saveStoredThreads(store);
    }
  };

  const stopVoiceInput = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    setListening(false);
  };

  const toggleVoiceInput = () => {
    if (listening) {
      stopVoiceInput();
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setSpeechError('Voice input is not supported in this browser.');
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = 'en-US';
      recognition.continuous = true;
      recognition.interimResults = true;

      baseInputRef.current = chatInput.trim();
      finalTranscriptRef.current = '';
      setSpeechError(null);

      recognition.onresult = (event: SpeechRecognitionEventLike) => {
        let interimTranscript = '';
        for (let idx = event.resultIndex; idx < event.results.length; idx += 1) {
          const result = event.results[idx];
          const transcript = (result?.[0]?.transcript || '').trim();
          if (!transcript) continue;
          if (result.isFinal) {
            finalTranscriptRef.current += `${transcript} `;
          } else {
            interimTranscript += `${transcript} `;
          }
        }
        const merged = `${baseInputRef.current} ${finalTranscriptRef.current}${interimTranscript}`.trim();
        setChatInput(merged);
      };

      recognition.onerror = (event: SpeechRecognitionErrorEventLike) => {
        const reason = String(event?.error || 'unknown_error');
        setSpeechError(`Voice input failed: ${reason}`);
        setListening(false);
        recognitionRef.current = null;
      };

      recognition.onend = () => {
        setListening(false);
        recognitionRef.current = null;
      };

      recognitionRef.current = recognition;
      recognition.start();
      setListening(true);
    } catch {
      setSpeechError('Unable to start voice input.');
      setListening(false);
      recognitionRef.current = null;
    }
  };

  const quickPrompts = [
    'Summarize the key contributions of the selected papers.',
    'What contradictions exist across these papers?',
    'Find research gaps and suggest a strong next experiment.',
  ];

  return (
    <Layout>
      <div className="page-enter">
        <section className="studio-hero mb-5">
          <span className="studio-kicker">
            <Sparkles className="h-3.5 w-3.5" />
            Evidence-first conversation
          </span>
          <h2>Research Chatbot</h2>
          <p>Ask any research question. Answers are grounded in your selected workspace papers.</p>
          <div className="studio-chip-row">
            <span className="studio-chip">{workspaces.length} workspaces</span>
            <span className="studio-chip">{selectedCount} selected papers</span>
            <span className="studio-chip">Style: {responseStyle}</span>
            <span className="studio-chip">{groundedOnly ? 'Grounding: strict' : 'Grounding: hybrid'}</span>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <label className="inline-flex items-center gap-2 text-xs text-slate-600">
              Response style
              <select
                value={responseStyle}
                onChange={(event) => setResponseStyle(event.target.value as 'concise' | 'balanced' | 'deep')}
                className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-700"
              >
                <option value="concise">Concise</option>
                <option value="balanced">Balanced</option>
                <option value="deep">Deep</option>
              </select>
            </label>
            <label className="inline-flex items-center gap-2 text-xs text-slate-600">
              <input
                type="checkbox"
                checked={groundedOnly}
                onChange={(event) => setGroundedOnly(event.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-indigo-600"
              />
              Strict paper grounding
            </label>
          </div>
          <div className="studio-orb" aria-hidden="true" />
        </section>

        {error && (
          <div className="studio-panel px-4 py-3 mb-4 text-sm text-red-700 border-red-200 bg-red-50 flex items-center gap-2">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        )}

        <section className="grid grid-cols-1 xl:grid-cols-[360px_minmax(0,1fr)] gap-4">
          <aside className="studio-surface p-4 space-y-3">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">Workspace</label>
              {loadingWorkspace ? (
                <div className="text-sm text-slate-500 inline-flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" /> Loading...
                </div>
              ) : (
                <select
                  value={selectedWsId ?? ''}
                  onChange={(event) => setSelectedWsId(Number(event.target.value))}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {workspaces.map((workspace) => (
                    <option key={workspace.id} value={workspace.id}>
                      {workspace.name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">Paper context</label>
                <div className="text-xs flex gap-2">
                  <button type="button" onClick={() => setSelectedPaperIds(new Set(papers.map((paper) => paper.id)))} className="text-indigo-600 hover:underline">
                    all
                  </button>
                  <button type="button" onClick={() => setSelectedPaperIds(new Set())} className="text-slate-500 hover:underline">
                    none
                  </button>
                </div>
              </div>
              <div className="max-h-56 overflow-y-auto space-y-2 pr-1">
                {loadingPapers ? (
                  <p className="text-sm text-slate-500 inline-flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading papers...
                  </p>
                ) : papers.length === 0 ? (
                  <p className="text-sm text-slate-500">No papers in this workspace.</p>
                ) : (
                  papers.map((paper) => (
                    <label key={paper.id} className="flex items-start gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selectedPaperIds.has(paper.id)}
                        onChange={() => togglePaper(paper.id)}
                        className="mt-0.5 h-4 w-4 rounded border-slate-300 text-indigo-600"
                      />
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-slate-800 line-clamp-2">{paper.title}</p>
                        <p className="text-xs text-slate-500 truncate">{paper.authors}</p>
                      </div>
                    </label>
                  ))
                )}
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">Optional extra context</label>
              <textarea
                value={contextText}
                onChange={(event) => setContextText(event.target.value)}
                placeholder="Add assumptions, constraints, or custom notes for this chat..."
                className="w-full min-h-[190px] rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <p className="text-xs text-slate-500 mt-1">{contextText.length} characters</p>
            </div>
          </aside>

          <section className="studio-surface p-4 flex flex-col min-h-[680px]">
            <div className="flex items-center justify-between gap-2 mb-3">
              <h3 className="text-base font-semibold text-slate-900 inline-flex items-center gap-2">
                <MessageSquare className="h-4.5 w-4.5 text-indigo-600" />
                Research Chat
              </h3>
              <button
                type="button"
                onClick={clearThread}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Clear
              </button>
            </div>

            <div className="flex-1 rounded-2xl border border-slate-200 bg-slate-50/70 p-3 overflow-y-auto space-y-3">
              {messages.length === 0 && (
                <div className="h-full min-h-[260px] flex flex-col items-center justify-center text-center text-slate-500">
                  <Bot className="h-8 w-8 text-indigo-400 mb-2" />
                  <p className="text-sm font-semibold text-slate-700">Start a research conversation</p>
                  <p className="text-sm max-w-md mt-1">
                    Ask literature, methodology, comparison, gap detection, or experiment design questions.
                  </p>
                </div>
              )}
              {messages.map((message, index) => {
                const isUser = message.role === 'user';
                return (
                  <article
                    key={`${message.createdAt}-${index}`}
                    className={`rounded-2xl px-3 py-2.5 border ${
                      isUser ? 'bg-indigo-600 text-white border-indigo-500 ml-auto max-w-[88%]' : 'bg-white text-slate-800 border-slate-200 max-w-[95%]'
                    }`}
                  >
                    <p className="text-xs uppercase tracking-wide opacity-75 mb-1">{isUser ? 'You' : 'Research Bot'}</p>
                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>

                    {!isUser && Array.isArray(message.actions) && message.actions.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-slate-100">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Next actions</p>
                        <ul className="space-y-1">
                          {message.actions.slice(0, 4).map((action, actionIdx) => (
                            <li key={`${action}-${actionIdx}`} className="text-xs text-slate-700 inline-flex items-start gap-1">
                              <CheckCircle2 className="h-3.5 w-3.5 mt-0.5 text-emerald-600" />
                              <span>{action}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {!isUser && Number.isFinite(Number(message.confidence)) && (
                      <div className="mt-2 inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
                        Confidence {Math.round(Number(message.confidence) * 100)}%
                      </div>
                    )}

                    {!isUser && Array.isArray(message.citations) && message.citations.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-slate-100">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Cited papers</p>
                        <div className="space-y-1.5">
                          {message.citations.slice(0, 4).map((citation) => (
                            <div key={`${citation.paper_id}-${citation.label}`} className="text-xs text-slate-700">
                              <span className="font-semibold">{citation.label}</span>: {citation.title}
                              {citation.url && (
                                <a
                                  href={citation.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-700 ml-2"
                                >
                                  Open <ExternalLink className="h-3 w-3" />
                                </a>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {!isUser && Array.isArray(message.evidenceMap) && message.evidenceMap.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-slate-100">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Evidence map</p>
                        <ul className="list-disc space-y-1 pl-4">
                          {message.evidenceMap.slice(0, 4).map((evidenceItem, evidenceIdx) => (
                            <li key={`${evidenceItem}-${evidenceIdx}`} className="text-xs text-slate-700">
                              {evidenceItem}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>

            <div className="mt-3 space-y-2">
              <div className="flex flex-wrap gap-2">
                {quickPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => setChatInput(prompt)}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
              {speechError && <p className="text-xs text-rose-600">{speechError}</p>}
              <div className="flex items-end gap-2">
                <textarea
                  value={chatInput}
                  onChange={(event) => setChatInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault();
                      void sendMessage();
                    }
                  }}
                  placeholder="Ask any research question about the selected papers..."
                  className="flex-1 min-h-[72px] rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <button
                  type="button"
                  onClick={toggleVoiceInput}
                  disabled={!speechSupported || sending}
                  className={`inline-flex items-center gap-1 rounded-xl border px-3 py-2.5 text-xs font-semibold ${
                    listening
                      ? 'border-rose-300 bg-rose-50 text-rose-700'
                      : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
                  } disabled:opacity-50`}
                  title={speechSupported ? (listening ? 'Stop voice input' : 'Start voice input') : 'Voice not supported'}
                >
                  {listening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                  {listening ? 'Stop' : 'Speak'}
                </button>
                <button
                  type="button"
                  onClick={() => void sendMessage()}
                  disabled={sending || !chatInput.trim() || !selectedWsId}
                  className="hero-btn-primary disabled:opacity-60 h-11"
                >
                  {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <SendHorizonal className="h-4 w-4" />}
                  Send
                </button>
              </div>
            </div>
          </section>
        </section>
      </div>
    </Layout>
  );
};

export default WritingChat;
