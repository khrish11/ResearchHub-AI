import React from 'react';
import { UploadCloud, Sparkles, Save, Download } from 'lucide-react';
import Layout from '../components/Layout';

const UploadPDF: React.FC = () => {
  return (
    <Layout userEmail="user@example.com" userInitials="U">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 mb-2">Upload Research Paper</h1>
        <p className="text-slate-600 mb-6">Upload a PDF to extract text and generate AI insights</p>

        <div className="bg-white rounded-lg border border-slate-200 p-8 mb-6">
          <div className="flex flex-col items-center justify-center border-2 border-dashed border-slate-300 rounded-lg px-6 py-16">
            <UploadCloud className="h-12 w-12 text-indigo-500 mb-4" />
            <h2 className="text-lg font-semibold text-slate-900 mb-2">Upload PDF</h2>
            <p className="text-sm text-slate-600 mb-6">Drop your PDF file here or click to browse</p>
            <button className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-indigo-700 transition-colors">
              Select PDF File
            </button>
          </div>
        </div>

        <div className="flex gap-4 mb-6">
          <button className="flex items-center gap-2 bg-indigo-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-indigo-700 transition-colors">
            <Sparkles className="h-5 w-5" />
            Generate AI Summary
          </button>
          <button className="flex items-center gap-2 bg-green-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-green-700 transition-colors">
            <Save className="h-5 w-5" />
            Save to Workspace
          </button>
          <button className="flex items-center gap-2 bg-slate-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-slate-700 transition-colors">
            <Download className="h-5 w-5" />
            Download Text
          </button>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Extracted Text:</h2>
          <textarea
            className="w-full h-64 rounded-lg border border-slate-300 p-4 text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-600"
            placeholder="Extracted text will appear here..."
          />
        </div>
      </div>
    </Layout>
  );
};

export default UploadPDF;

