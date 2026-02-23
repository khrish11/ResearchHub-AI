import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertCircle,
  CheckCircle,
  Download,
  FileText,
  Loader2,
  Sparkles,
  UploadCloud,
  Wand2,
  X,
} from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';
import { apiErrorMessage } from '../utils/apiError';

interface Workspace {
  id: number;
  name: string;
}

type UploadState = 'idle' | 'uploading' | 'done' | 'error';

const UploadPDF: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploadState, setUploadState] = useState<UploadState>('idle');
  const [errorMsg, setErrorMsg] = useState('');
  const [extractedText, setExtractedText] = useState('');
  const [aiSummary, setAiSummary] = useState('');
  const [charCount, setCharCount] = useState(0);
  const [savedPaperId, setSavedPaperId] = useState<number | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | ''>('');
  const [summarize, setSummarize] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .get('/workspaces/')
      .then(async (res) => {
        const wsList: Workspace[] = res.data;
        setWorkspaces(wsList);
        if (wsList.length > 0) {
          setSelectedWorkspaceId(wsList[0].id);
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
    } catch (err: unknown) {
      setErrorMsg(apiErrorMessage(err, 'Upload failed. Please try again.'));
      setUploadState('error');
    }
  };

  const handleDownload = () => {
    if (!extractedText) {
      return;
    }
    const blob = new Blob([extractedText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${file?.name.replace('.pdf', '') || 'extracted'}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const resetUpload = () => {
    setFile(null);
    setUploadState('idle');
    setErrorMsg('');
    setExtractedText('');
    setAiSummary('');
    setSavedPaperId(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
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
