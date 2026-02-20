import React from 'react';
import { FileText, NotebookText, Search } from 'lucide-react';
import Layout from '../components/Layout';

const DocSpace: React.FC = () => {
  return (
    <Layout userEmail="user@example.com" userInitials="U">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 mb-2">Doc Space</h1>
        <p className="text-slate-600 mb-6">
          A centralized space for all documents associated with your projects – uploaded PDFs,
          AI‑generated summaries, extracted notes, and analysis reports.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          <div className="bg-white rounded-lg border border-slate-200 p-6">
            <FileText className="h-10 w-10 text-indigo-600 mb-4" />
            <h2 className="text-lg font-semibold text-slate-900 mb-2">Source papers</h2>
            <p className="text-sm text-slate-600">
              View and organize all PDFs you have imported or uploaded into your workspaces.
            </p>
          </div>

          <div className="bg-white rounded-lg border border-slate-200 p-6">
            <NotebookText className="h-10 w-10 text-indigo-600 mb-4" />
            <h2 className="text-lg font-semibold text-slate-900 mb-2">Summaries &amp; notes</h2>
            <p className="text-sm text-slate-600">
              Access AI‑generated summaries, extracted key points, and your own annotations in
              one place.
            </p>
          </div>

          <div className="bg-white rounded-lg border border-slate-200 p-6">
            <Search className="h-10 w-10 text-indigo-600 mb-4" />
            <h2 className="text-lg font-semibold text-slate-900 mb-2">Semantic search</h2>
            <p className="text-sm text-slate-600">
              Quickly retrieve documents and notes using concept‑level semantic search instead of
              brittle keyword matching.
            </p>
          </div>
        </div>

        <div className="bg-white rounded-lg border border-dashed border-slate-300 p-8 text-center">
          <p className="text-slate-500">
            Document listing and filters will appear here once wired to your backend. Use this as
            the entry point for browsing all research artifacts per project.
          </p>
        </div>
      </div>
    </Layout>
  );
};

export default DocSpace;

