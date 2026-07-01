import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  CheckCircle,
  Copy,
  Download,
  FileText,
  Loader2,
  Sparkles,
  ShieldCheck,
  UploadCloud,
  Wand2,
  X,
} from 'lucide-react';
import Layout from '../components/Layout';
import PaperCheckReport from '../components/PaperCheckReport';
import api from '../api';
import { apiErrorMessage } from '../utils/apiError';
import { useToast } from '../contexts/ToastContext';
import { downloadTextFile } from '../utils/exportUtils';
import {
  citationMissingFieldLabel,
  extractPaperTitleFromFilename,
  type CitationResponse,
  type CitationStyle,
  type CompletedPaperCheckResult,
  fallbackCitation,
  fetchCitation,
  fetchPaperCitation,
  getLatestPaperCheck,
  runPaperCheck,
} from '../utils/researchArtifacts';

interface Workspace {
  id: number;
  name: string;
}

type UploadState = 'idle' | 'uploading' | 'done' | 'error';

interface UploadPaperSession {
  paperId: number;
  workspaceId?: number;
  charCount?: number;
}

const uploadPaperSessionKey = 'researchhub:last-uploaded-paper';

const readUploadPaperSession = (): UploadPaperSession | null => {
  try {
    const raw = window.localStorage.getItem(uploadPaperSessionKey);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<UploadPaperSession>;
    const paperId = Number(parsed.paperId || 0);
    if (!paperId) {
      return null;
    }
    const workspaceId = Number(parsed.workspaceId || 0);
    return {
      paperId,
      workspaceId: workspaceId || undefined,
      charCount: Number(parsed.charCount || 0) || undefined,
    };
  } catch {
    return null;
  }
};

const writeUploadPaperSession = (session: UploadPaperSession) => {
  try {
    window.localStorage.setItem(uploadPaperSessionKey, JSON.stringify(session));
  } catch {
    // Restoring Paper Check is a convenience; upload must still succeed without local storage.
  }
};

const clearUploadPaperSession = () => {
  try {
    window.localStorage.removeItem(uploadPaperSessionKey);
  } catch {
    // Ignore storage failures.
  }
};

const UploadPDF: React.FC = () => {
  const { success: toastSuccess, error: toastError } = useToast();
  const restoredUploadSession = useRef(readUploadPaperSession());
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploadState, setUploadState] = useState<UploadState>(
    restoredUploadSession.current ? 'done' : 'idle'
  );
  const [errorMsg, setErrorMsg] = useState('');
  const [extractedText, setExtractedText] = useState('');
  const [aiSummary, setAiSummary] = useState('');
  const [charCount, setCharCount] = useState(restoredUploadSession.current?.charCount || 0);
  const [savedPaperId, setSavedPaperId] = useState<number | null>(
    restoredUploadSession.current?.paperId || null
  );
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | ''>(
    restoredUploadSession.current?.workspaceId || ''
  );
  const [summarize, setSummarize] = useState(true);
  const [citationStyle, setCitationStyle] = useState<CitationStyle>('apa');
  const [citationResult, setCitationResult] = useState<CitationResponse | null>(null);
  const [citationLoading, setCitationLoading] = useState(false);
  const [paperCheckResult, setPaperCheckResult] = useState<CompletedPaperCheckResult | null>(null);
  const [paperCheckLoading, setPaperCheckLoading] = useState(false);
  const [paperCheckRestoring, setPaperCheckRestoring] = useState(false);
  const [paperCheckStatus, setPaperCheckStatus] = useState('');
  const [paperCheckRestoreError, setPaperCheckRestoreError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .get('/workspaces/')
      .then(async (res) => {
        const wsList: Workspace[] = res.data;
        setWorkspaces(wsList);
        if (wsList.length > 0) {
          setSelectedWorkspaceId((current) => current || wsList[0].id);
          return;
        }
        try {
          const defaultWs = await api.post('/workspaces/', {
            name: 'My Research Workspace',
            description: 'Default workspace for organizing research papers',
          });
          setWorkspaces([defaultWs.data]);
          setSelectedWorkspaceId(defaultWs.data.id);
        } catch {
          setWorkspaces([]);
        }
      })
      .catch(() => {
        setWorkspaces([]);
      });
  }, []);

  const handleFile = (nextFile: File) => {
    if (!nextFile.name.toLowerCase().endsWith('.pdf')) {
      setErrorMsg('Only PDF files are supported.');
      return;
    }
    setFile(nextFile);
    setErrorMsg('');
    setUploadState('idle');
    setExtractedText('');
    setAiSummary('');
    setSavedPaperId(null);
    setCitationResult(null);
    setPaperCheckResult(null);
    setPaperCheckStatus('');
    setPaperCheckRestoreError('');
    clearUploadPaperSession();
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) {
      handleFile(dropped);
    }
  }, []);

  const handleUpload = async () => {
    if (!file) {
      return;
    }
    setUploadState('uploading');
    setErrorMsg('');
    setExtractedText('');
    setAiSummary('');
    setSavedPaperId(null);
    setCitationResult(null);
    setPaperCheckResult(null);
    setPaperCheckStatus('');
    setPaperCheckRestoreError('');
    clearUploadPaperSession();

    const formData = new FormData();
    formData.append('file', file);
    formData.append('summarize', String(summarize));
    if (selectedWorkspaceId !== '') {
      formData.append('workspace_id', String(selectedWorkspaceId));
    }

    try {
      const res = await api.post('/papers/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setExtractedText(res.data.extracted_text);
      setAiSummary(res.data.ai_summary);
      setCharCount(res.data.char_count);
      setSavedPaperId(res.data.paper_id);
      setUploadState('done');
      if (res.data.paper_id) {
        writeUploadPaperSession({
          paperId: Number(res.data.paper_id),
          workspaceId: selectedWorkspaceId === '' ? undefined : selectedWorkspaceId,
          charCount: Number(res.data.char_count || 0) || undefined,
        });
      }
    } catch (err: unknown) {
      setErrorMsg(apiErrorMessage(err, 'Upload failed. Please try again.'));
      setUploadState('error');
    }
  };

  const handleDownload = () => {
    if (!extractedText) {
      return;
    }
    downloadTextFile(
      `${file?.name.replace('.pdf', '') || 'extracted'}.txt`,
      extractedText,
      'text/plain;charset=utf-8;'
    );
  };

  const resetUpload = () => {
    setFile(null);
    setUploadState('idle');
    setErrorMsg('');
    setExtractedText('');
    setAiSummary('');
    setSavedPaperId(null);
    setCitationResult(null);
    setPaperCheckResult(null);
    setPaperCheckStatus('');
    setPaperCheckRestoreError('');
    clearUploadPaperSession();
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const uploadCitationMetadata = useMemo(
    () => ({
      title: extractPaperTitleFromFilename(file?.name || ''),
      authors: [] as string[],
      url: null,
    }),
    [file?.name],
  );

  const handleGenerateCitation = useCallback(
    async (quiet = false) => {
      if (uploadState !== 'done') {
        return null;
      }
      setCitationLoading(true);
      try {
        const response = savedPaperId
          ? await fetchPaperCitation(savedPaperId, citationStyle)
          : await fetchCitation(uploadCitationMetadata, citationStyle);
        setCitationResult(response);
        if (!quiet) {
          toastSuccess('Citation generated');
        }
        return response;
      } catch (err: unknown) {
        const message = apiErrorMessage(err, 'Failed to generate citation.');
        setErrorMsg(message);
        if (!quiet) {
          toastError(message);
        }
        return null;
      } finally {
        setCitationLoading(false);
      }
    },
    [citationStyle, savedPaperId, toastError, toastSuccess, uploadCitationMetadata, uploadState],
  );

  useEffect(() => {
    if (!citationResult) {
      return;
    }
    if (String(citationResult.style || '').toLowerCase() === citationStyle) {
      return;
    }
    void handleGenerateCitation(true);
  }, [citationResult, citationStyle, handleGenerateCitation]);

  useEffect(() => {
    if (!savedPaperId) {
      setPaperCheckRestoreError('');
      return;
    }
    const workspaceId = selectedWorkspaceId === '' ? undefined : selectedWorkspaceId;
    if (!workspaceId) {
      return;
    }

    let cancelled = false;
    setPaperCheckRestoring(true);
    setPaperCheckRestoreError('');
    void getLatestPaperCheck(savedPaperId, workspaceId)
      .then((response) => {
        if (cancelled) {
          return;
        }
        if (!response) {
          setPaperCheckStatus('');
          return;
        }
        setPaperCheckResult(response);
        setPaperCheckStatus('Previous Paper Check report restored.');
      })
      .catch(() => {
        if (!cancelled) {
          setPaperCheckRestoreError('Unable to load previous Paper Check report.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setPaperCheckRestoring(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [savedPaperId, selectedWorkspaceId]);

  const handleCopyCitation = async () => {
    const resolved = citationResult || (await handleGenerateCitation(true));
    const text = resolved?.citation || fallbackCitation(uploadCitationMetadata, citationStyle);
    try {
      await navigator.clipboard.writeText(text);
      toastSuccess('Citation copied');
    } catch {
      toastError('Failed to copy citation');
    }
  };

  const handleExportBibtex = async () => {
    try {
      const response = savedPaperId
        ? await fetchPaperCitation(savedPaperId, 'bibtex')
        : await fetchCitation(uploadCitationMetadata, 'bibtex');
      downloadTextFile(
        `${extractPaperTitleFromFilename(file?.name || 'uploaded-paper').replace(/\s+/g, '_')}.bib`,
        response.citation,
        'application/x-bibtex'
      );
    } catch (err: unknown) {
      toastError(apiErrorMessage(err, 'Failed to export BibTeX.'));
    }
  };

  const handleRunPaperCheck = async () => {
    if (!savedPaperId && !extractedText.trim()) {
      toastError('Upload a paper first.');
      return;
    }
    setPaperCheckLoading(true);
    setPaperCheckStatus('Running advisory paper analysis...');
    setPaperCheckResult(null);
    setPaperCheckRestoreError('');
    try {
      const response = await runPaperCheck({
        paper_id: savedPaperId || undefined,
        raw_text: savedPaperId ? undefined : extractedText,
        workspace_id: selectedWorkspaceId === '' ? undefined : selectedWorkspaceId,
        prefer_async: extractedText.length > 45000,
      });
      const completedResponse = {
        ...response,
        metadata: {
          ...response.metadata,
          processed_at: response.metadata?.processed_at || new Date().toISOString(),
        },
      };
      setPaperCheckResult(completedResponse);
      if (savedPaperId) {
        writeUploadPaperSession({
          paperId: savedPaperId,
          workspaceId: selectedWorkspaceId === '' ? undefined : selectedWorkspaceId,
          charCount: charCount || undefined,
        });
      }
      setPaperCheckStatus(
        response.job_id
          ? 'Queued analysis completed successfully.'
          : 'Paper analysis completed successfully.'
      );
      toastSuccess('AI checker complete');
    } catch (err: unknown) {
      const message = apiErrorMessage(err, 'AI checker failed.');
      setErrorMsg(message);
      setPaperCheckStatus('');
      toastError(message);
    } finally {
      setPaperCheckLoading(false);
    }
  };

  return (
    <Layout>
      <div className="page-enter">
        <section className="studio-hero mb-5">
          <span className="studio-kicker">
            <Sparkles className="h-3.5 w-3.5" />
            Document ingest
          </span>
          <h2>Upload and Analyze PDF Papers</h2>
          <p>
            Drop a paper, extract full text, generate AI summary, and save the processed record directly
            into your workspace.
          </p>
          <div className="studio-chip-row">
            <span className="studio-chip">{file ? '1 file selected' : 'No file selected'}</span>
            <span className="studio-chip">{workspaces.length} workspaces available</span>
            <span className="studio-chip">{summarize ? 'AI summary enabled' : 'Text extraction only'}</span>
          </div>
          <div className="studio-orb" aria-hidden="true" />
        </section>

        <section className="studio-surface p-4 mb-4">
          <div
            className={`upload-drop ${dragging ? 'dragging' : ''}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
          >
            {file ? (
              <div className="flex flex-col items-center gap-2 text-center">
                <div className="studio-icon-chip bg-indigo-100 text-indigo-600">
                  <FileText className="h-5 w-5" />
                </div>
                <p className="text-sm font-semibold text-slate-900">{file.name}</p>
                <p className="text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB</p>
                <button
                  onClick={resetUpload}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-red-600"
                >
                  <X className="h-3.5 w-3.5" />
                  Remove file
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 text-center">
                <UploadCloud className="h-10 w-10 text-indigo-400" />
                <p className="text-sm font-semibold text-slate-700">
                  Drag and drop a PDF here, or browse from disk
                </p>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="hero-btn-primary"
                >
                  Select file
                </button>
                <p className="text-xs text-slate-500">Only .pdf format is supported.</p>
              </div>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.[0]) {
                  handleFile(e.target.files[0]);
                }
              }}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
            <div className="studio-panel-quiet p-3">
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                Save to workspace
              </label>
              <select
                value={selectedWorkspaceId}
                onChange={(e) => setSelectedWorkspaceId(e.target.value ? Number(e.target.value) : '')}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">Do not save</option>
                {workspaces.map((workspace) => (
                  <option key={workspace.id} value={workspace.id}>
                    {workspace.name}
                  </option>
                ))}
              </select>
            </div>

            <label className="studio-panel-quiet p-3 flex items-center justify-between gap-3 cursor-pointer">
              <div>
                <p className="text-sm font-semibold text-slate-800">AI summary</p>
                <p className="text-xs text-slate-500">Generate concise summary after extraction.</p>
              </div>
              <button
                type="button"
                onClick={() => setSummarize((prev) => !prev)}
                className={`switch ${summarize ? 'active' : ''}`}
                aria-label="Toggle AI summary"
              />
            </label>

            <div className="studio-panel-quiet p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Status</p>
              <p className="text-sm font-semibold text-slate-800 mt-1">
                {uploadState === 'idle' && 'Waiting'}
                {uploadState === 'uploading' && 'Processing'}
                {uploadState === 'done' && 'Complete'}
                {uploadState === 'error' && 'Failed'}
              </p>
            </div>
          </div>
        </section>

        {errorMsg && (
          <div className="studio-panel px-4 py-3 mb-4 text-sm text-red-700 border-red-200 bg-red-50 flex items-center gap-2">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {errorMsg}
          </div>
        )}

        {uploadState === 'done' && (
          <div className="studio-panel px-4 py-3 mb-4 text-sm text-emerald-700 border-emerald-200 bg-emerald-50 flex items-center gap-2">
            <CheckCircle className="h-4 w-4 flex-shrink-0" />
            PDF processed. {charCount.toLocaleString()} characters extracted.
            {savedPaperId && <span> Saved as paper ID {savedPaperId}.</span>}
          </div>
        )}

        <div className="flex flex-wrap gap-2.5 mb-4">
          <button
            onClick={handleUpload}
            disabled={!file || uploadState === 'uploading'}
            className="hero-btn-primary disabled:opacity-55 disabled:cursor-not-allowed"
          >
            {uploadState === 'uploading' ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <Wand2 className="h-4 w-4" />
                Upload and analyze
              </>
            )}
          </button>
          <button
            onClick={handleDownload}
            disabled={!extractedText}
            className="hero-btn-secondary disabled:opacity-55 disabled:cursor-not-allowed"
          >
            <Download className="h-4 w-4" />
            Download text
          </button>
        </div>

        {uploadState === 'done' && (
          <section className="studio-surface p-4 mb-4 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-slate-900">Post-processing actions</h3>
                <p className="mt-1 text-sm text-slate-500">
                  Generate a production citation or run the advisory AI checker on the uploaded paper.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void handleRunPaperCheck()}
                  disabled={paperCheckLoading}
                  className="hero-btn-primary disabled:cursor-not-allowed disabled:opacity-55"
                >
                  {paperCheckLoading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Running checker...
                    </>
                  ) : (
                    <>
                      <ShieldCheck className="h-4 w-4" />
                      Run AI Checker
                    </>
                  )}
                </button>
              </div>
            </div>

            <div className="grid gap-4 xl:grid-cols-[0.9fr,1.1fr]">
              <div className="studio-panel-quiet p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">Citation engine</p>
                    <p className="mt-1 text-xs text-slate-500">
                      Backed by normalized metadata with graceful fallback when fields are sparse.
                    </p>
                  </div>
                  <select
                    value={citationStyle}
                    onChange={(event) => setCitationStyle(event.target.value as CitationStyle)}
                    className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
                  >
                    <option value="apa">APA</option>
                    <option value="mla">MLA</option>
                    <option value="ieee">IEEE</option>
                    <option value="chicago">Chicago</option>
                    <option value="bibtex">BibTeX</option>
                  </select>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => void handleGenerateCitation()}
                    disabled={citationLoading}
                    className="hero-btn-secondary disabled:cursor-not-allowed disabled:opacity-55"
                  >
                    {citationLoading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Generating...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4" />
                        Generate Citation
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleCopyCitation()}
                    disabled={citationLoading && !citationResult}
                    className="hero-btn-secondary disabled:cursor-not-allowed disabled:opacity-55"
                  >
                    <Copy className="h-4 w-4" />
                    Copy
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleExportBibtex()}
                    className="hero-btn-secondary"
                  >
                    <Download className="h-4 w-4" />
                    Export BibTeX
                  </button>
                </div>

                <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    {citationResult ? (
                      <>
                        <span
                          className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                            citationResult.completeness_score >= 80
                              ? 'bg-emerald-50 text-emerald-700'
                              : citationResult.completeness_score >= 55
                              ? 'bg-amber-50 text-amber-700'
                              : 'bg-rose-50 text-rose-700'
                          }`}
                        >
                          Completeness {citationResult.completeness_score}%
                        </span>
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                          {citationResult.style.toUpperCase()}
                        </span>
                      </>
                    ) : (
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                        Citation not generated yet
                      </span>
                    )}
                  </div>

                  <pre className="mt-3 whitespace-pre-wrap break-words rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm leading-6 text-slate-700">
                    {citationResult?.citation || fallbackCitation(uploadCitationMetadata, citationStyle)}
                  </pre>

                  {citationResult && citationResult.missing_fields.length > 0 && (
                    <p className="mt-3 text-xs text-slate-500">
                      Missing fields: {citationResult.missing_fields.map(citationMissingFieldLabel).join(', ')}
                    </p>
                  )}
                  {citationResult && citationResult.warnings.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {citationResult.warnings.map((warning) => (
                        <div key={warning} className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                          {warning}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="studio-panel-quiet p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">AI checker</p>
                    <p className="mt-1 text-xs text-slate-500">
                      Structured paper review with suspicious-segment AI-writing likelihood analysis.
                    </p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                    {savedPaperId ? `paper ${savedPaperId}` : 'raw text mode'}
                  </span>
                </div>

                <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Checker status</p>
                  <p className="mt-2 text-sm text-slate-700">
                    {paperCheckRestoring
                      ? 'Restoring previous Paper Check report...'
                      : paperCheckLoading
                      ? paperCheckStatus || 'Running advisory paper analysis...'
                      : paperCheckStatus || 'Ready to analyze the uploaded paper.'}
                  </p>
                  {paperCheckRestoring && (
                    <div className="mt-3 inline-flex items-center gap-2 text-xs font-semibold text-slate-500">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Loading saved report
                    </div>
                  )}
                  {paperCheckRestoreError && (
                    <p className="mt-3 text-sm text-amber-700">{paperCheckRestoreError}</p>
                  )}
                  <p className="mt-2 text-xs text-slate-500">
                    Suspicious passage review is advisory only and not proof of AI authorship.
                  </p>
                </div>
              </div>
            </div>
          </section>
        )}

        {aiSummary && (
          <section className="studio-surface p-4 mb-4">
            <h3 className="text-base font-semibold text-slate-900 mb-2 inline-flex items-center gap-2">
              <Sparkles className="h-4.5 w-4.5 text-indigo-600" />
              AI Summary
            </h3>
            <div className="studio-panel-quiet p-3">
              <pre className="whitespace-pre-wrap text-sm text-slate-700 font-sans leading-relaxed">
                {aiSummary}
              </pre>
            </div>
          </section>
        )}

        {paperCheckResult && (
          <PaperCheckReport
            result={paperCheckResult}
            title="Upload paper checker report"
            retryPayload={
              savedPaperId || extractedText.trim()
                ? {
                    paper_id: savedPaperId || undefined,
                    raw_text: savedPaperId ? undefined : extractedText,
                    workspace_id: selectedWorkspaceId === '' ? undefined : selectedWorkspaceId,
                    prefer_async: extractedText.length > 45000,
                  }
                : undefined
            }
            onRetryComplete={(response) => {
              const completedResponse = {
                ...response,
                metadata: {
                  ...response.metadata,
                  processed_at: response.metadata?.processed_at || new Date().toISOString(),
                },
              };
              setPaperCheckResult(completedResponse);
              setPaperCheckStatus('Paper analysis completed successfully.');
              toastSuccess('AI checker complete');
            }}
            onRetryError={(message) => {
              setErrorMsg(message);
              toastError(message);
            }}
          />
        )}

        <section className="studio-surface p-4">
          <h3 className="text-base font-semibold text-slate-900 mb-2 inline-flex items-center gap-2">
            <FileText className="h-4.5 w-4.5 text-slate-500" />
            Extracted Text
          </h3>
          <div className="studio-panel-quiet p-3">
            <textarea
              readOnly
              className="w-full h-64 rounded-xl border border-slate-300 p-3 text-sm text-slate-700 resize-y focus:outline-none"
              value={extractedText}
              placeholder="Upload a PDF to view extracted text..."
            />
            <p className="text-xs text-slate-500 mt-2">{charCount.toLocaleString()} characters</p>
          </div>
        </section>
      </div>
    </Layout>
  );
};

export default UploadPDF;
