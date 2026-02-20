import React, { useCallback, useEffect, useRef, useState } from 'react';
import { UploadCloud, Sparkles, Download, FileText, X, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';

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

  // Load user workspaces
  useEffect(() => {
    api.get('/workspaces/').then((res) => {
      setWorkspaces(res.data);
      if (res.data.length > 0) setSelectedWorkspaceId(res.data[0].id);
    }).catch(() => { });
  }, []);

  const handleFile = (f: File) => {
    if (!f.name.toLowerCase().endsWith('.pdf')) {
      setErrorMsg('Only PDF files are supported.');
      return;
    }
    setFile(f);
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
    if (dropped) handleFile(dropped);
  }, []);

  const handleUpload = async () => {
    if (!file) return;
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
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Upload failed. Please try again.';
      setErrorMsg(detail);
      setUploadState('error');
    }
  };

  const handleDownload = () => {
    if (!extractedText) return;
    const blob = new Blob([extractedText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = (file?.name.replace('.pdf', '') || 'extracted') + '.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  const reset = () => {
    setFile(null);
    setUploadState('idle');
    setErrorMsg('');
    setExtractedText('');
    setAiSummary('');
    setSavedPaperId(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <Layout userEmail="user@example.com" userInitials="U">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 mb-2">Upload Research Paper</h1>
        <p className="text-slate-600 mb-6">Upload a PDF to extract its text and generate an AI summary</p>

        {/* Drop Zone */}
        <div
          className={`bg-white rounded-lg border-2 border-dashed p-8 mb-6 text-center transition-colors ${dragging ? 'border-indigo-500 bg-indigo-50' : 'border-slate-300'
            }`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          {file ? (
            <div className="flex flex-col items-center gap-3">
              <FileText className="h-10 w-10 text-indigo-500" />
              <p className="text-slate-800 font-semibold">{file.name}</p>
              <p className="text-slate-500 text-sm">{(file.size / 1024).toFixed(1)} KB</p>
              <button onClick={reset} className="text-slate-400 hover:text-red-500 flex items-center gap-1 text-sm">
                <X className="h-4 w-4" /> Remove
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <UploadCloud className="h-12 w-12 text-indigo-400" />
              <p className="text-slate-700 font-medium">Drop your PDF here, or</p>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="bg-indigo-600 text-white px-5 py-2 rounded-lg font-semibold hover:bg-indigo-700 transition-colors"
              >
                Browse Files
              </button>
              <p className="text-slate-400 text-xs">PDF files only</p>
            </div>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={(e) => { if (e.target.files?.[0]) handleFile(e.target.files[0]); }}
          />
        </div>

        {/* Options */}
        <div className="bg-white rounded-lg border border-slate-200 p-5 mb-6 flex flex-wrap gap-6 items-center">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Save to Workspace</label>
            <select
              value={selectedWorkspaceId}
              onChange={(e) => setSelectedWorkspaceId(e.target.value ? Number(e.target.value) : '')}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-600"
            >
              <option value="">Don&apos;t save</option>
              {workspaces.map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2 mt-4">
            <input
              id="summarize"
              type="checkbox"
              checked={summarize}
              onChange={(e) => setSummarize(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-600"
            />
            <label htmlFor="summarize" className="text-sm text-slate-700">Generate AI Summary</label>
          </div>
        </div>

        {/* Error */}
        {errorMsg && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {errorMsg}
          </div>
        )}

        {/* Success banner */}
        {uploadState === 'done' && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700">
            <CheckCircle className="h-4 w-4 flex-shrink-0" />
            PDF processed — {charCount.toLocaleString()} characters extracted.
            {savedPaperId && <span className="ml-1">Paper saved to workspace (ID {savedPaperId}).</span>}
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-4 mb-6 flex-wrap">
          <button
            onClick={handleUpload}
            disabled={!file || uploadState === 'uploading'}
            className="flex items-center gap-2 bg-indigo-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {uploadState === 'uploading' ? (
              <><Loader2 className="h-5 w-5 animate-spin" /> Processing…</>
            ) : (
              <><Sparkles className="h-5 w-5" /> Upload & Analyse</>
            )}
          </button>
          <button
            onClick={handleDownload}
            disabled={!extractedText}
            className="flex items-center gap-2 bg-slate-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Download className="h-5 w-5" /> Download Text
          </button>
        </div>

        {/* AI Summary */}
        {aiSummary && (
          <div className="bg-indigo-50 rounded-lg border border-indigo-200 p-6 mb-6">
            <h2 className="text-lg font-semibold text-indigo-900 mb-3 flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-indigo-600" /> AI Summary
            </h2>
            <pre className="whitespace-pre-wrap text-sm text-indigo-800 font-sans leading-relaxed">{aiSummary}</pre>
          </div>
        )}

        {/* Extracted Text */}
        {extractedText && (
          <div className="bg-white rounded-lg border border-slate-200 p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-3 flex items-center gap-2">
              <FileText className="h-5 w-5 text-slate-500" /> Extracted Text
              <span className="ml-auto text-sm text-slate-400 font-normal">{charCount.toLocaleString()} chars</span>
            </h2>
            <textarea
              readOnly
              className="w-full h-64 rounded-lg border border-slate-300 p-4 text-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-600 resize-y"
              value={extractedText}
            />
          </div>
        )}

        {/* Empty state for text area before upload */}
        {!extractedText && uploadState === 'idle' && (
          <div className="bg-white rounded-lg border border-slate-200 p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-3">Extracted Text</h2>
            <textarea
              readOnly
              className="w-full h-64 rounded-lg border border-slate-300 p-4 text-slate-400 text-sm resize-y"
              placeholder="Upload a PDF to see extracted text here…"
            />
          </div>
        )}
      </div>
    </Layout>
  );
};

export default UploadPDF;
