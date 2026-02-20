import React from 'react';
import { Link } from 'react-router-dom';
import { Search, MessageSquare, Folder, Brain, FileText } from 'lucide-react';

const Landing: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 justify-between items-center">
            <h1 className="text-xl font-bold text-indigo-600">ResearchHub AI</h1>
            <div className="flex gap-4">
              <Link
                to="/login"
                className="rounded-md px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                Sign in
              </Link>
              <Link
                to="/register"
                className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
              >
                Get started
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Hero */}
      <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-16">
        <section className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
            Intelligent Research Paper Management
          </h2>
          <p className="mt-6 text-lg text-slate-600">
            ResearchHub AI is an agentic AI–powered platform that helps researchers discover,
            organize, and analyze academic papers. Use Groq’s Llama 3.3 70B for context-aware
            insights, summaries, and answers from your curated collections.
          </p>
          <div className="mt-10 flex justify-center gap-4">
            <Link
              to="/register"
              className="rounded-md bg-indigo-600 px-6 py-3 text-base font-semibold text-white hover:bg-indigo-500"
            >
              Create free account
            </Link>
            <Link
              to="/login"
              className="rounded-md border border-slate-300 bg-white px-6 py-3 text-base font-semibold text-slate-700 hover:bg-slate-50"
            >
              Sign in
            </Link>
          </div>
        </section>

        {/* Key features - matching PDF */}
        <section className="grid grid-cols-1 gap-8 md:grid-cols-2 lg:grid-cols-3 mt-16">
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <Search className="h-10 w-10 text-indigo-600" />
            <h3 className="mt-4 text-lg font-semibold text-slate-900">Paper search & import</h3>
            <p className="mt-2 text-sm text-slate-600">
              Query multiple academic databases. Get curated results with metadata (title, authors,
              abstract). Import into your workspace with one click.
            </p>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <MessageSquare className="h-10 w-10 text-indigo-600" />
            <h3 className="mt-4 text-lg font-semibold text-slate-900">AI chatbot</h3>
            <p className="mt-2 text-sm text-slate-600">
              Ask research-specific questions. Get summaries, comparisons, and insights across your
              papers with Groq Llama 3.3 70B.
            </p>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <Folder className="h-10 w-10 text-indigo-600" />
            <h3 className="mt-4 text-lg font-semibold text-slate-900">Workspace management</h3>
            <p className="mt-2 text-sm text-slate-600">
              Organize papers in project-specific workspaces. Separate conversation histories per
              project.
            </p>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <Brain className="h-10 w-10 text-indigo-600" />
            <h3 className="mt-4 text-lg font-semibold text-slate-900">Context awareness</h3>
            <p className="mt-2 text-sm text-slate-600">
              The AI maintains context across conversations and synthesizes information from
              multiple documents.
            </p>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <FileText className="h-10 w-10 text-indigo-600" />
            <h3 className="mt-4 text-lg font-semibold text-slate-900">Upload PDF</h3>
            <p className="mt-2 text-sm text-slate-600">
              Add papers from your personal collection. Build a comprehensive research library.
            </p>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <div className="h-10 w-10 rounded-lg bg-indigo-100 flex items-center justify-center">
              <span className="text-indigo-600 font-bold text-sm">Doc</span>
            </div>
            <h3 className="mt-4 text-lg font-semibold text-slate-900">Doc space</h3>
            <p className="mt-2 text-sm text-slate-600">
              Centralized access to PDFs, summaries, notes, and AI-generated analysis reports.
            </p>
          </div>
        </section>

        <section className="mt-20 text-center">
          <p className="text-slate-500 text-sm">
            JWT-secured authentication • FastAPI backend • React & TypeScript frontend
          </p>
        </section>
      </main>
    </div>
  );
};

export default Landing;
