import React, { useEffect, useMemo, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, Download, Copy, Info, CheckCircle, AlertTriangle, Lightbulb, Save } from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';
import { useToast } from '../contexts/ToastContext';

interface ReportResponse {
  result: {
    title: string;
    abstract: string;
    key_themes: string[];
    literature_overview: string;
    methodology_trends: string;
    consensus_findings: string;
    conflicting_views: string;
    research_gaps: string[];
    future_directions: string[];
    conclusion: string;
    _provenance?: {
      intelligence_artifact_id?: string;
      workspace_id?: number;
      paper_ids?: number[];
      artifact_status?: string;
      overall_score?: number;
      generated_at?: string;
    };
  };
}

const ResearchReport: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { error: toastError, success: toastSuccess } = useToast();

  const idsParam = searchParams.get('ids');
  const topicParam = searchParams.get('topic');
  const workspaceIdParam = searchParams.get('workspace_id');
  const artifactIdParam = searchParams.get('artifact_id');

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<ReportResponse | null>(null);
  const [saving, setSaving] = useState(false);
  const [isIntelligenceBacked, setIsIntelligenceBacked] = useState(false);

  const markdown = useMemo(() => {
    if (!data) return '';
    const { result } = data;
    
    let md = `# ${result.title}\n\n`;
    
    // Add provenance header if intelligence-backed
    if (result._provenance?.intelligence_artifact_id) {
      md += `> **Generated from Research Intelligence Artifact**\n`;
      md += `> Artifact ID: ${result._provenance.intelligence_artifact_id}\n`;
      if (result._provenance.overall_score !== undefined) {
        md += `> Intelligence Score: ${result._provenance.overall_score}/100\n`;
      }
      md += `> Generated: ${result._provenance.generated_at || 'N/A'}\n\n`;
    }
    
    md += `## Abstract\n${result.abstract}\n\n`;
    md += `## Key Themes\n${(result.key_themes || []).map(t => `- ${t}`).join('\n')}\n\n`;
    md += `## Literature Overview\n${result.literature_overview}\n\n`;
    md += `## Methodology Trends\n${result.methodology_trends}\n\n`;
    md += `## Consensus Findings\n${result.consensus_findings}\n\n`;
    md += `## Conflicting Views\n${result.conflicting_views}\n\n`;
    md += `## Research Gaps\n${(result.research_gaps || []).map(g => `- ${g}`).join('\n')}\n\n`;
    md += `## Future Directions\n${(result.future_directions || []).map(d => `- ${d}`).join('\n')}\n\n`;
    md += `## Conclusion\n${result.conclusion}`;
    
    return md.trim();
  }, [data]);

  useEffect(() => {
    // Check for sessionStorage data first (intelligence-backed report)
    const sessionReport = sessionStorage.getItem('generatedReport');
    const sessionArtifactId = sessionStorage.getItem('reportArtifactId');
    
    if (sessionReport && sessionArtifactId) {
      try {
        const reportData = JSON.parse(sessionReport);
        setData({ result: reportData });
        setIsIntelligenceBacked(true);
        setLoading(false);
        // Clear sessionStorage after loading
        sessionStorage.removeItem('generatedReport');
        sessionStorage.removeItem('reportArtifactId');
        sessionStorage.removeItem('reportWorkspaceId');
        return;
      } catch (err) {
        console.error('Failed to parse session report:', err);
      }
    }

    // Fall back to URL parameter-based report generation
    if (!idsParam && !topicParam) {
      navigate('/dashboard');
      return;
    }

    const fetchReport = async () => {
      try {
        const payload: {
          paper_ids: number[];
          topic?: string;
          intelligence_artifact_id?: string;
        } = {
          paper_ids: idsParam ? idsParam.split(',').map(Number) : [],
          topic: topicParam || undefined,
        };
        
        // Include intelligence_artifact_id if present in URL
        if (artifactIdParam) {
          payload.intelligence_artifact_id = artifactIdParam;
        }
        
        const res = await api.post<ReportResponse>('/research/generate-report', payload);
        setData(res.data);
        setIsIntelligenceBacked(!!res.data.result._provenance?.intelligence_artifact_id);
      } catch (err) {
        toastError('Failed to generate or fetch research report.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    void fetchReport();
  }, [idsParam, topicParam, artifactIdParam, navigate, toastError]);

  const handleCopy = () => {
    if (!data) return;
    navigator.clipboard.writeText(markdown).then(() => toastSuccess('Copied to clipboard.'));
  };

  const handleDownloadMarkdown = () => {
    if (!markdown) return;
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${(data?.result?.title || 'research-report').replace(/\s+/g, '_')}.md`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.URL.revokeObjectURL(url);
  };

  const handleExportPdf = () => {
    if (!data) return;
    const html = `
      <html>
        <head>
          <meta charset="utf-8" />
          <title>${data.result.title}</title>
          <style>
            body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; padding: 28px; }
            h1 { margin: 0 0 10px; }
            h2 { margin-top: 18px; }
            ul { padding-left: 18px; }
            .note { margin-top: 18px; font-size: 12px; color: #666; }
            pre { white-space: pre-wrap; }
          </style>
        </head>
        <body>
          <pre>${markdown.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
          <div class="note">AI-generated report may contain inaccuracies.</div>
        </body>
      </html>
    `;
    const w = window.open('', '_blank', 'noopener,noreferrer,width=980,height=720');
    if (!w) {
      toastError('Pop-up blocked. Allow pop-ups to export PDF.');
      return;
    }
    w.document.open();
    w.document.write(html);
    w.document.close();
    w.focus();
    w.print();
  };

  const handleSaveToWorkspace = async () => {
    if (!markdown) return;
    const workspaceId = Number(workspaceIdParam || 0);
    if (!workspaceId) {
      toastError('Open this report from a workspace to enable saving.');
      return;
    }
    setSaving(true);
    try {
      const existing = await api.get(`/workspaces/${workspaceId}/docspace`);
      const currentContent = String(existing.data?.content || '');
      const nextContent = `${currentContent.trim()}\n\n---\n\n${markdown}\n`.trim();
      await api.put(`/workspaces/${workspaceId}/docspace`, {
        title: existing.data?.title || 'Research Notes',
        content: nextContent,
      });
      toastSuccess('Saved to workspace notes.');
    } catch (err) {
      console.error(err);
      toastError('Failed to save to workspace notes.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Layout>
      <div className="mx-auto max-w-5xl px-4 py-8 pb-32">
        <div className="mb-8 flex items-center justify-between">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-900"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>
          <div className="flex items-center gap-3">
            <button
              onClick={handleCopy}
              disabled={!data || loading}
              className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-50"
            >
              <Copy className="h-4 w-4" />
              Copy Markdown
            </button>
            <button
              onClick={handleDownloadMarkdown}
              disabled={!data || loading}
              className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-50"
            >
              <Download className="h-4 w-4" />
              Download .md
            </button>
            <button
              onClick={handleExportPdf}
              disabled={!data || loading}
              className="flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:opacity-50"
            >
              <Download className="h-4 w-4" />
              Export PDF
            </button>
            <button
              onClick={() => void handleSaveToWorkspace()}
              disabled={!data || loading || saving}
              className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-50"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Save to workspace
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <Loader2 className="h-10 w-10 animate-spin text-indigo-500" />
            <p className="mt-4 text-sm font-medium text-slate-500">
              Synthesizing research report... This may take up to a minute.
            </p>
          </div>
        ) : !data ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-8 text-center text-red-800">
            <AlertTriangle className="mx-auto mb-3 h-8 w-8 text-red-500" />
            <h3 className="text-lg font-semibold">Failed to Generate Report</h3>
            <p className="mt-1 text-sm text-red-600">Please try again.</p>
          </div>
        ) : (
          <div className="space-y-8 animate-in fade-in duration-500">
            {/* Intelligence Provenance Banner */}
            {isIntelligenceBacked && data.result._provenance && (
              <div className="rounded-2xl border border-indigo-200 bg-indigo-50 p-4 shadow-sm">
                <div className="flex items-center gap-2 mb-2">
                  <Lightbulb className="h-5 w-5 text-indigo-600" />
                  <h3 className="text-sm font-semibold text-indigo-900">Generated from Research Intelligence</h3>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs text-indigo-700">
                  <div>
                    <span className="font-medium">Artifact ID:</span> {data.result._provenance.intelligence_artifact_id?.slice(0, 8)}...
                  </div>
                  <div>
                    <span className="font-medium">Status:</span> {data.result._provenance.artifact_status}
                  </div>
                  {data.result._provenance.overall_score !== undefined && (
                    <div>
                      <span className="font-medium">Score:</span> {data.result._provenance.overall_score}/100
                    </div>
                  )}
                  <div>
                    <span className="font-medium">Papers:</span> {data.result._provenance.paper_ids?.length || 0}
                  </div>
                </div>
              </div>
            )}

            <div className="text-center">
              <h1 className="text-3xl font-bold tracking-tight text-slate-900">{data.result.title}</h1>
              <p className="mt-4 text-left max-w-3xl mx-auto text-lg text-slate-600 italic">
                {data.result.abstract}
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-slate-800">
                <CheckCircle className="h-5 w-5 text-indigo-500" />
                Key Themes
              </h2>
              <ul className="list-disc pl-5 space-y-1 text-slate-600">
                {data.result.key_themes.map((theme, idx) => (
                  <li key={idx}>{theme}</li>
                ))}
              </ul>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              <ReportSection title="Literature Overview" content={data.result.literature_overview} icon={<FileTextIcon />} />
              <ReportSection title="Methodology Trends" content={data.result.methodology_trends} icon={<Info className="h-5 w-5 text-sky-500" />} />
              <ReportSection title="Consensus Findings" content={data.result.consensus_findings} icon={<CheckCircle className="h-5 w-5 text-emerald-500" />} />
              <ReportSection title="Conflicting Views" content={data.result.conflicting_views} icon={<AlertTriangle className="h-5 w-5 text-rose-500" />} />
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 shadow-sm">
                <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-amber-800">
                  <AlertTriangle className="h-5 w-5 text-amber-600" />
                  Research Gaps
                </h2>
                <ul className="list-disc pl-5 space-y-1 text-amber-900">
                  {data.result.research_gaps.map((gap, idx) => (
                    <li key={idx}>{gap}</li>
                  ))}
                </ul>
              </div>
              <div className="rounded-2xl border border-indigo-200 bg-indigo-50 p-6 shadow-sm">
                <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-indigo-800">
                  <Lightbulb className="h-5 w-5 text-indigo-600" />
                  Future Directions
                </h2>
                <ul className="list-disc pl-5 space-y-1 text-indigo-900">
                  {data.result.future_directions.map((direction, idx) => (
                    <li key={idx}>{direction}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-slate-800">
                <Info className="h-5 w-5 text-purple-500" />
                Conclusion
              </h2>
              <p className="text-slate-600 leading-relaxed font-medium">
                {data.result.conclusion}
              </p>
            </div>

            <div className="mt-8 rounded-xl bg-slate-50 p-4 text-center text-xs text-slate-500">
              Disclaimer: This comprehensive report is generated by AI and may contain inaccuracies. Please refer to the original papers for definitive facts.
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

const FileTextIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
    className="h-5 w-5 text-indigo-500"
  >
    <path
      fillRule="evenodd"
      d="M5.625 1.5H9a3.75 3.75 0 013.75 3.75v1.875c0 1.036.84 1.875 1.875 1.875H16.5a3.75 3.75 0 013.75 3.75v7.875c0 1.035-.84 1.875-1.875 1.875H5.625a1.875 1.875 0 01-1.875-1.875V3.375c0-1.036.84-1.875 1.875-1.875zm5.845 1.7a2.25 2.25 0 00-1.42-.2H5.625a.375.375 0 00-.375.375v16.5c0 .207.168.375.375.375h12.75a.375.375 0 00.375-.375V11.25a2.25 2.25 0 00-2.25-2.25h-1.875a3.375 3.375 0 01-3.375-3.375V3.75m.007-.056v1.931c0 .207.168.375.375.375h1.931a2.25 2.25 0 00-1.426-1.571 2.25 2.25 0 00-.88-.735z"
      clipRule="evenodd"
    />
  </svg>
);

const ReportSection: React.FC<{ title: string; content: string; icon: React.ReactNode }> = ({ title, content, icon }) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:shadow-md">
    <h3 className="mb-4 flex items-center gap-2 text-lg font-bold text-slate-800">
      {icon}
      {title}
    </h3>
    <div className="prose prose-slate prose-sm max-w-none text-slate-600">
      {content.split('\\n').map((para, i) => (
        <p key={i}>{para}</p>
      ))}
    </div>
  </div>
);

export default ResearchReport;
