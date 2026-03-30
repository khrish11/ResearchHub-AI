import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, Copy, Info, CheckCircle, AlertTriangle, Sparkles } from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';
import { useToast } from '../contexts/ToastContext';

interface CompareResponse {
  comparison: {
    contributions: string;
    methodology_differences: string;
    strengths_and_weaknesses: string;
    evidence_quality: string;
    contradictions: string;
    final_summary: string;
  };
  source_papers: any[];
}

const ComparePapers: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { error: toastError, success: toastSuccess } = useToast();

  const idsParam = searchParams.get('ids');
  const workspaceIdParam = searchParams.get('workspace_id');

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<CompareResponse | null>(null);

  useEffect(() => {
    if (!idsParam) {
      navigate('/workspace');
      return;
    }

    const fetchComparison = async () => {
      try {
        const payload = {
          paper_ids: idsParam.split(',').map(Number),
          workspace_id: workspaceIdParam ? Number(workspaceIdParam) : undefined,
        };
        const res = await api.post<CompareResponse>('/papers/compare', payload);
        setData(res.data);
      } catch (err) {
        toastError('Failed to generate or fetch comparison.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    void fetchComparison();
  }, [idsParam, workspaceIdParam, navigate, toastError]);

  const handleCopy = () => {
    if (!data) return;
    const { comparison } = data;
    const text = `
# Paper Comparison

## Key Contributions
${comparison.contributions}

## Methodology Differences
${comparison.methodology_differences}

## Strengths & Weaknesses
${comparison.strengths_and_weaknesses}

## Evidence Quality
${comparison.evidence_quality}

## Contradictions & Disagreements
${comparison.contradictions}

## Final Summary
${comparison.final_summary}
    `.trim();
    navigator.clipboard.writeText(text).then(() => toastSuccess('Copied to clipboard.'));
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
              onClick={() => {
                if (!idsParam) return;
                const qp = new URLSearchParams();
                qp.set('ids', idsParam);
                if (workspaceIdParam) qp.set('workspace_id', workspaceIdParam);
                navigate(`/research-report?${qp.toString()}`);
              }}
              disabled={!idsParam || loading}
              className="flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:opacity-50"
            >
              <Sparkles className="h-4 w-4" />
              Generate Report
            </button>
            <button
              onClick={handleCopy}
              disabled={!data || loading}
              className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-50"
            >
              <Copy className="h-4 w-4" />
              Copy Text
            </button>
          </div>
        </div>

        <div className="mb-10 text-center">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Compare Papers</h1>
          <p className="mt-2 text-base text-slate-600">
            AI-driven structured analysis across selected research papers.
          </p>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <Loader2 className="h-10 w-10 animate-spin text-indigo-500" />
            <p className="mt-4 text-sm font-medium text-slate-500">
              Generating structured comparison... This may take up to 20 seconds.
            </p>
          </div>
        ) : !data ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-8 text-center text-red-800">
            <AlertTriangle className="mx-auto mb-3 h-8 w-8 text-red-500" />
            <h3 className="text-lg font-semibold">Failed to Compare Papers</h3>
            <p className="mt-1 text-sm text-red-600">Please try again or select fewer papers.</p>
          </div>
        ) : (
          <div className="space-y-8 animate-in fade-in duration-500">
            {/* Header: Source Papers */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-slate-800">
                <Info className="h-5 w-5 text-indigo-500" />
                Papers Analysed
              </h2>
              <ul className="space-y-3">
                {data.source_papers.map((p, idx) => (
                  <li key={p.id || idx} className="flex flex-col gap-0.5 border-l-2 border-indigo-200 pl-4">
                    <span className="font-medium text-slate-900 line-clamp-1">{p.title}</span>
                    <span className="text-sm text-slate-500">
                      {Array.isArray(p.authors) ? p.authors.join(', ') : p.authors}
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Grid for Comparison Sections */}
            <div className="grid gap-6 md:grid-cols-2">
              <ComparisonCard title="Key Contributions" content={data.comparison.contributions} icon={<CheckCircle className="h-5 w-5 text-emerald-500" />} />
              <ComparisonCard title="Methodology Differences" content={data.comparison.methodology_differences} icon={<Info className="h-5 w-5 text-sky-500" />} />
              <ComparisonCard title="Strengths & Weaknesses" content={data.comparison.strengths_and_weaknesses} icon={<AlertTriangle className="h-5 w-5 text-amber-500" />} />
              <ComparisonCard title="Evidence Quality" content={data.comparison.evidence_quality} icon={<CheckCircle className="h-5 w-5 text-indigo-500" />} />
              <ComparisonCard title="Contradictions" content={data.comparison.contradictions} icon={<AlertTriangle className="h-5 w-5 text-rose-500" />} />
              <ComparisonCard title="Final Summary" content={data.comparison.final_summary} icon={<Info className="h-5 w-5 text-purple-500" />} />
            </div>

            <div className="mt-8 rounded-xl bg-slate-50 p-4 text-center text-xs text-slate-500">
              Disclaimer: This comparison is generated by AI and may contain inaccuracies. Please refer to the original papers for definitive facts.
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

const ComparisonCard: React.FC<{ title: string; content: string; icon: React.ReactNode }> = ({ title, content, icon }) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:shadow-md">
    <h3 className="mb-4 flex items-center gap-2 text-lg font-bold text-slate-800">
      {icon}
      {title}
    </h3>
    <div className="prose prose-slate prose-sm max-w-none text-slate-600">
      {content.split('\n').map((para, i) => (
        <p key={i}>{para}</p>
      ))}
    </div>
  </div>
);

export default ComparePapers;
