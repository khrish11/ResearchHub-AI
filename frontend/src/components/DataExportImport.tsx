import React, { useState, useRef } from 'react';
import { Download, Upload, FileText, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import api from '../api';
import { useToast } from '../contexts/ToastContext';

interface DataExportImportProps {
  workspaceId: number;
  workspaceName: string;
  onImportComplete?: () => void;
}

const DataExportImport: React.FC<DataExportImportProps> = ({
  workspaceId,
  workspaceName,
  onImportComplete
}) => {
  const [exporting, setExporting] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResults, setImportResults] = useState<{
    success: number;
    failed: number;
    errors: string[];
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { success: showSuccess, error: showError } = useToast();

  const handleExport = async (format: 'bibtex' | 'csv' | 'json') => {
    setExporting(format);
    try {
      const response = await api.get(`/workspaces/${workspaceId}/export?format=${format}`, {
        responseType: 'blob'
      });

      const blob = new Blob([response.data], {
        type: format === 'csv' ? 'text/csv' :
              format === 'bibtex' ? 'application/x-bibtex' :
              'application/json'
      });

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = format === 'bibtex' ? 'bib' : format;
      a.download = `${workspaceName.replace(/\s+/g, '_')}_papers.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);

      showSuccess(`Papers exported successfully as ${format.toUpperCase()}`);
    } catch (error) {
      showError('Failed to export papers');
    } finally {
      setExporting(null);
    }
  };

  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    const allowedTypes = ['application/json', 'text/csv', 'text/plain'];
    if (!allowedTypes.includes(file.type) && !file.name.endsWith('.bib')) {
      showError('Please select a valid file (.json, .csv, .bib, or .txt)');
      return;
    }

    setImporting(true);
    setImportResults(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('workspace_id', workspaceId.toString());

      const response = await api.post('/papers/import-batch', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      const results = response.data;
      setImportResults(results);

      if (results.success > 0) {
        showSuccess(`Successfully imported ${results.success} papers`);
        onImportComplete?.();
      }

      if (results.failed > 0) {
        showError(`Failed to import ${results.failed} papers`);
      }

    } catch (error: any) {
      const message = error?.response?.data?.detail || 'Failed to import papers';
      showError(message);
    } finally {
      setImporting(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const exportFormats = [
    { key: 'bibtex', label: 'BibTeX', description: 'For LaTeX and reference managers' },
    { key: 'csv', label: 'CSV', description: 'For Excel and data analysis' },
    { key: 'json', label: 'JSON', description: 'For programmatic access' }
  ];

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
      <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-6 flex items-center gap-2">
        <FileText className="h-5 w-5" />
        Data Export & Import
      </h3>

      <div className="space-y-6">
        {/* Export Section */}
        <div>
          <h4 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
            Export Papers
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {exportFormats.map((format) => (
              <button
                key={format.key}
                onClick={() => handleExport(format.key as 'bibtex' | 'csv' | 'json')}
                disabled={exporting === format.key}
                className="p-4 border border-slate-200 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors text-left disabled:opacity-50"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-slate-900 dark:text-slate-100">
                    {format.label}
                  </span>
                  {exporting === format.key ? (
                    <Loader2 className="h-4 w-4 animate-spin text-indigo-600" />
                  ) : (
                    <Download className="h-4 w-4 text-slate-400" />
                  )}
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {format.description}
                </p>
              </button>
            ))}
          </div>
        </div>

        {/* Import Section */}
        <div>
          <h4 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
            Import Papers
          </h4>
          <div className="space-y-3">
            <div className="border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-lg p-6 text-center">
              <Upload className="h-8 w-8 text-slate-400 mx-auto mb-2" />
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
                Upload a file to import papers
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".json,.csv,.bib,.txt"
                onChange={handleImport}
                disabled={importing}
                className="hidden"
                id="file-upload"
              />
              <label
                htmlFor="file-upload"
                className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white text-sm font-medium rounded-lg cursor-pointer transition-colors disabled:cursor-not-allowed"
              >
                {importing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Importing...
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4" />
                    Choose File
                  </>
                )}
              </label>
            </div>

            <div className="text-xs text-slate-500 dark:text-slate-400 space-y-1">
              <p><strong>Supported formats:</strong></p>
              <ul className="list-disc list-inside space-y-0.5 ml-4">
                <li><strong>JSON:</strong> Standard paper data format</li>
                <li><strong>CSV:</strong> Spreadsheet format with columns: title, authors, abstract, url, doi</li>
                <li><strong>BibTeX:</strong> LaTeX bibliography format</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Import Results */}
        {importResults && (
          <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              {importResults.failed === 0 ? (
                <CheckCircle className="h-5 w-5 text-green-600" />
              ) : (
                <AlertCircle className="h-5 w-5 text-yellow-600" />
              )}
              <span className="font-medium text-slate-900 dark:text-slate-100">
                Import Results
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="text-green-600">
                <span className="font-medium">{importResults.success}</span> successful
              </div>
              <div className="text-red-600">
                <span className="font-medium">{importResults.failed}</span> failed
              </div>
            </div>

            {importResults.errors.length > 0 && (
              <div className="mt-3">
                <p className="text-sm font-medium text-red-700 dark:text-red-300 mb-1">
                  Errors:
                </p>
                <ul className="text-xs text-red-600 dark:text-red-400 space-y-0.5">
                  {importResults.errors.slice(0, 5).map((error, index) => (
                    <li key={index}>• {error}</li>
                  ))}
                  {importResults.errors.length > 5 && (
                    <li>• ... and {importResults.errors.length - 5} more</li>
                  )}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default DataExportImport;
