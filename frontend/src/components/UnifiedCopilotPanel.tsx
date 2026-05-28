import { useMemo, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Bot, Loader2, RefreshCcw, Send, ShieldAlert, Sparkles } from 'lucide-react';
import api from '../api';
import { apiErrorMessage } from '../utils/apiError';

type CopilotIntent = 'explain' | 'compare' | 'report' | 'rag_query' | 'insights';

interface CopilotContext {
  workspace_id?: number;
  paper_ids?: number[];
}

interface CopilotSource {
  source_id?: string;
  source_type?: string;
  title?: string;
  url?: string;
  doi?: string;
  relevance_score?: number;
  similarity_score?: number;
}

interface CopilotResponse {
  type: string;
  intent: string;
  content: unknown;
  sources: CopilotSource[];
  confidence: number;
  fallback_used: boolean;
  cached: boolean;
  cache_layer: string | null;
}

interface UnifiedCopilotPanelProps {
  workspaceId?: number | null;
  paperIds?: number[];
  heading?: string;
  subheading?: string;
  initialQuery?: string;
  suggestedPrompts?: string[];
}

interface InsightItem {
  text?: string;
}

interface InsightsPayload {
  key_themes?: InsightItem[];
  emerging_trends?: InsightItem[];
  contradictions?: InsightItem[];
  important_findings?: InsightItem[];
  research_gaps?: InsightItem[];
  recommended_next_steps?: InsightItem[];
}

const stringifyText = (value: unknown): string => (typeof value === 'string' ? value.trim() : '');

const toStringList = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => stringifyText(item))
    .filter(Boolean)
    .slice(0, 10);
};

const toIntList = (value: number[] | undefined): number[] =>
  Array.from(new Set((value || []).map((item) => Number(item)).filter((item) => Number.isInteger(item) && item > 0)));

const intentLabel = (intent: CopilotIntent | string): string => {
  if (intent === 'explain') return 'Explain';
  if (intent === 'compare') return 'Compare';
  if (intent === 'report') return 'Report';
  if (intent === 'insights') return 'Insights';
  return 'RAG Query';
};

const parsePaperId = (source: CopilotSource): number | null => {
  const sourceId = String(source.source_id || '').trim();
  if (!sourceId) {
    return null;
  }
  const match = sourceId.match(/(?:paper[:_])?(\d+)/i);
  if (!match?.[1]) {
    return null;
  }
  const id = Number(match[1]);
  return Number.isInteger(id) && id > 0 ? id : null;
};

const sourceExternalUrl = (source: CopilotSource): string => {
  const url = stringifyText(source.url);
  if (url) {
    return url;
  }
  const doi = stringifyText(source.doi);
  return doi ? `https://doi.org/${doi.replace(/^https?:\/\/doi\.org\//i, '')}` : '';
};

function renderExplainContent(content: Record<string, unknown>) {
  const keyPoints = toStringList(content.key_points);
  const strengths = toStringList(content.strengths);
  const weaknesses = toStringList(content.weaknesses);
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      <article className="rounded-xl border border-slate-200 bg-slate-50 p-3 md:col-span-2">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Simple Explanation</p>
        <p className="mt-1 text-sm leading-relaxed text-slate-700">{stringifyText(content.simple_explanation) || 'Not available.'}</p>
      </article>
      <article className="rounded-xl border border-slate-200 bg-white p-3">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Key Points</p>
        {keyPoints.length > 0 ? (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
            {keyPoints.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-sm text-slate-500">No key points available.</p>
        )}
      </article>
      <article className="rounded-xl border border-slate-200 bg-white p-3">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Method</p>
        <p className="mt-1 text-sm leading-relaxed text-slate-700">{stringifyText(content.methodology) || 'Method summary unavailable.'}</p>
      </article>
      <article className="rounded-xl border border-emerald-200 bg-emerald-50 p-3">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">Strengths</p>
        {strengths.length > 0 ? (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-emerald-900">
            {strengths.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-sm text-emerald-800">No strengths captured.</p>
        )}
      </article>
      <article className="rounded-xl border border-rose-200 bg-rose-50 p-3">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-rose-700">Weaknesses</p>
        {weaknesses.length > 0 ? (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-rose-900">
            {weaknesses.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-sm text-rose-800">No weaknesses captured.</p>
        )}
      </article>
      <article className="rounded-xl border border-slate-200 bg-white p-3">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Evidence Quality</p>
        <p className="mt-1 text-sm text-slate-700">{stringifyText(content.evidence_quality) || 'Unavailable.'}</p>
      </article>
      <article className="rounded-xl border border-slate-200 bg-white p-3">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">AI Writing Likelihood</p>
        <p className="mt-1 text-sm text-slate-700">{stringifyText(content.ai_likelihood) || 'Unavailable.'}</p>
      </article>
      <article className="rounded-xl border border-slate-200 bg-slate-50 p-3 md:col-span-2">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Why It Matters</p>
        <p className="mt-1 text-sm leading-relaxed text-slate-700">{stringifyText(content.significance) || 'Unavailable.'}</p>
      </article>
    </div>
  );
}

const insightTextList = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => {
      if (typeof item === 'string') {
        return item.trim();
      }
      if (item && typeof item === 'object') {
        return stringifyText((item as InsightItem).text);
      }
      return '';
    })
    .filter(Boolean)
    .slice(0, 5);
};

function renderInsightsContent(content: Record<string, unknown>) {
  const payload = (content.payload && typeof content.payload === 'object' ? content.payload : {}) as InsightsPayload;
  const cards: Array<{ key: keyof InsightsPayload; label: string; empty: string }> = [
    { key: 'key_themes', label: 'Key Themes', empty: 'No clear themes detected.' },
    { key: 'emerging_trends', label: 'Emerging Trends', empty: 'No trend signal yet.' },
    { key: 'important_findings', label: 'Important Findings', empty: 'No major finding highlighted yet.' },
    { key: 'contradictions', label: 'Contradictions', empty: 'No major contradiction surfaced.' },
    { key: 'research_gaps', label: 'Research Gaps', empty: 'No explicit gap detected.' },
    { key: 'recommended_next_steps', label: 'Suggestions', empty: 'No next steps available.' },
  ];
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {cards.map((card) => {
        const items = insightTextList(payload[card.key]);
        return (
          <article key={card.key} className="rounded-xl border border-slate-200 bg-white p-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{card.label}</p>
            {items.length > 0 ? (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                {items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-sm text-slate-500">{card.empty}</p>
            )}
          </article>
        );
      })}
    </div>
  );
}

function renderGenericContent(content: unknown) {
  if (typeof content === 'string') {
    return <p className="text-sm leading-relaxed text-slate-700">{content}</p>;
  }
  if (!content || typeof content !== 'object') {
    return <p className="text-sm text-slate-500">No structured response available.</p>;
  }

  const objectContent = content as Record<string, unknown>;
  const answer = stringifyText(objectContent.answer);
  const summary = stringifyText(objectContent.summary);
  const comparisonSummary =
    objectContent.comparison && typeof objectContent.comparison === 'object'
      ? stringifyText((objectContent.comparison as Record<string, unknown>).summary)
      : '';
  const reportSummary =
    objectContent.report && typeof objectContent.report === 'object'
      ? stringifyText((objectContent.report as Record<string, unknown>).summary)
      : '';
  const bestText = answer || summary || comparisonSummary || reportSummary;

  if (bestText) {
    return <p className="text-sm leading-relaxed text-slate-700">{bestText}</p>;
  }

  return (
    <pre className="max-h-72 overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
      {JSON.stringify(objectContent, null, 2)}
    </pre>
  );
}

export default function UnifiedCopilotPanel({
  workspaceId,
  paperIds,
  heading = 'AI Copilot',
  subheading = 'One prompt routes to explain, compare, report, insights, or grounded workspace Q&A.',
  initialQuery = '',
  suggestedPrompts = [],
}: UnifiedCopilotPanelProps) {
  const [query, setQuery] = useState(initialQuery);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CopilotResponse | null>(null);

  const normalizedPaperIds = useMemo(() => toIntList(paperIds), [paperIds]);
  const normalizedWorkspaceId = useMemo(() => {
    const id = Number(workspaceId || 0);
    return Number.isInteger(id) && id > 0 ? id : null;
  }, [workspaceId]);

  const contextPayload = useMemo(() => {
    const payload: CopilotContext = {};
    if (normalizedWorkspaceId) {
      payload.workspace_id = normalizedWorkspaceId;
    }
    if (normalizedPaperIds.length > 0) {
      payload.paper_ids = normalizedPaperIds;
    }
    return payload;
  }, [normalizedPaperIds, normalizedWorkspaceId]);

  const submit = async (refresh = false, overrideQuery?: string) => {
    const activeQuery = typeof overrideQuery === 'string' ? overrideQuery : query;
    const trimmed = activeQuery.trim();
    if (trimmed.length < 2) {
      setError('Enter at least 2 characters.');
      return;
    }
    if (typeof overrideQuery === 'string') {
      setQuery(overrideQuery);
    }
    setLoading(true);
    setError(null);
    try {
      const response = await api.post<Partial<CopilotResponse>>('/ai/copilot', {
        query: trimmed,
        context: contextPayload,
        refresh,
      });
      const data = response.data || {};
      setResult({
        type: String(data.type || 'rag_query'),
        intent: String(data.intent || 'rag_query'),
        content: data.content ?? null,
        sources: Array.isArray(data.sources) ? (data.sources as CopilotSource[]) : [],
        confidence: Number(data.confidence || 0),
        fallback_used: Boolean(data.fallback_used),
        cached: Boolean(data.cached),
        cache_layer: data.cache_layer ? String(data.cache_layer) : null,
      });
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Copilot request failed.'));
    } finally {
      setLoading(false);
    }
  };

  const renderContent = () => {
    if (!result) {
      return (
        <p className="text-sm text-slate-500">
          Ask a question like "Explain this paper", "Compare these papers", or "What are the main trends?"
        </p>
      );
    }
    if (result.type === 'explain' && result.content && typeof result.content === 'object') {
      return renderExplainContent(result.content as Record<string, unknown>);
    }
    if (result.type === 'insights' && result.content && typeof result.content === 'object') {
      return renderInsightsContent(result.content as Record<string, unknown>);
    }
    return renderGenericContent(result.content);
  };

  const confidencePct = Math.round(Math.max(0, Math.min(1, Number(result?.confidence || 0))) * 100);

  return (
    <section className="feature-surface">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Unified AI</p>
          <h3 className="mt-1 text-xl font-bold text-slate-900">{heading}</h3>
          <p className="mt-1 text-sm text-slate-600">{subheading}</p>
        </div>
        <div className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-semibold text-slate-600">
          <Bot className="h-3.5 w-3.5" />
          {normalizedWorkspaceId ? `Workspace ${normalizedWorkspaceId}` : 'No workspace context'}
          {normalizedPaperIds.length > 0 ? ` | ${normalizedPaperIds.length} paper context` : ''}
        </div>
      </div>

      {suggestedPrompts.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {suggestedPrompts.slice(0, 6).map((prompt) => (
            <button
              key={prompt}
              type="button"
              disabled={loading}
              onClick={() => {
                void submit(false, prompt);
              }}
              className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-[11px] font-semibold text-indigo-700 hover:bg-indigo-100 disabled:opacity-60"
            >
              {prompt}
            </button>
          ))}
        </div>
      ) : null}

      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <input
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder='Try: "Explain this paper" or "What are the main trends?"'
          className="w-full flex-1 rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <button
          type="button"
          onClick={() => {
            void submit(false);
          }}
          disabled={loading}
          className="hero-btn-primary disabled:cursor-not-allowed disabled:opacity-55"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          Ask
        </button>
        <button
          type="button"
          onClick={() => {
            void submit(true);
          }}
          disabled={loading || !result}
          className="hero-btn-secondary disabled:cursor-not-allowed disabled:opacity-55"
        >
          <RefreshCcw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      {error && <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}

      <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 font-semibold text-indigo-700">
            Intent: {intentLabel(result?.intent || 'rag_query')}
          </span>
          <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 font-semibold text-slate-700">
            Confidence {confidencePct}%
          </span>
          {result?.cached ? (
            <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 font-semibold text-emerald-700">
              Cached {result.cache_layer ? `(${result.cache_layer})` : ''}
            </span>
          ) : null}
          {result?.fallback_used ? (
            <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 font-semibold text-amber-700">
              Fallback route
            </span>
          ) : null}
        </div>

        <progress
          className="mb-4 h-2 w-full overflow-hidden rounded-full"
          max={100}
          value={confidencePct}
          aria-label="Confidence score"
        />

        <div>{renderContent()}</div>

        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-800">
          <p className="inline-flex items-center gap-1.5 font-semibold uppercase tracking-[0.12em]">
            <ShieldAlert className="h-3.5 w-3.5" />
            Safety
          </p>
          <p className="mt-1">AI output is advisory. Validate important claims using linked sources before decisions.</p>
        </div>

        {result?.sources?.length ? (
          <div className="mt-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Sources</p>
            <div className="mt-2 space-y-2">
              {result.sources.slice(0, 8).map((source, index) => {
                const externalUrl = sourceExternalUrl(source);
                const title = stringifyText(source.title) || `Source ${index + 1}`;
                const similarityRaw = Number(source.similarity_score ?? source.relevance_score ?? 0);
                const similarity = Number.isFinite(similarityRaw) ? Math.max(0, Math.min(1, similarityRaw)) : 0;
                const paperId = parsePaperId(source);
                const workspaceLink = normalizedWorkspaceId && paperId ? `/workspace/${normalizedWorkspaceId}` : '';
                return (
                  <article key={`${source.source_id || index}-${index}`} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-slate-800">{title}</p>
                      <span className="text-[11px] font-semibold text-slate-500">{Math.round(similarity * 100)}% relevance</span>
                    </div>
                    <p className="mt-1 text-xs uppercase tracking-[0.1em] text-slate-500">{stringifyText(source.source_type) || 'source'}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {externalUrl ? (
                        <a
                          href={externalUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 rounded-full border border-cyan-200 bg-cyan-50 px-2.5 py-1 text-[11px] font-semibold text-cyan-700 hover:bg-cyan-100"
                        >
                          <Sparkles className="h-3.5 w-3.5" />
                          Open source
                        </a>
                      ) : workspaceLink ? (
                        <RouterLink
                          to={workspaceLink}
                          className="inline-flex items-center gap-1 rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-[11px] font-semibold text-indigo-700 hover:bg-indigo-100"
                        >
                          Open in workspace
                        </RouterLink>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
