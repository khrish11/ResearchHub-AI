import React from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, MessageSquare, Sparkles, FileText, Folder, ArrowRight } from 'lucide-react';
import Layout from '../components/Layout';

const Library: React.FC = () => {
  return (
    <Layout>
      <div className="mx-auto max-w-5xl px-4 py-12">
        <div className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Library
          </h1>
          <p className="mt-2 text-lg text-slate-600 dark:text-slate-400">
            Access all your research assets in one place.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <Link
            to="/search"
            className="group rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition-all hover:shadow-md hover:border-indigo-300 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-indigo-600"
          >
            <div className="mb-4 inline-flex rounded-xl bg-indigo-100 p-3 text-indigo-600 dark:bg-indigo-900 dark:text-indigo-300">
              <BookOpen className="h-6 w-6" />
            </div>
            <h2 className="mb-2 text-xl font-semibold text-slate-900 dark:text-slate-100">
              Papers
            </h2>
            <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
              Search and browse papers across all your workspaces.
            </p>
            <div className="flex items-center text-sm font-medium text-indigo-600 dark:text-indigo-400 group-hover:underline">
              Browse papers
              <ArrowRight className="ml-1 h-4 w-4" />
            </div>
          </Link>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <div className="mb-4 inline-flex rounded-xl bg-fuchsia-100 p-3 text-fuchsia-600 dark:bg-fuchsia-900 dark:text-fuchsia-300">
              <MessageSquare className="h-6 w-6" />
            </div>
            <h2 className="mb-2 text-xl font-semibold text-slate-900 dark:text-slate-100">
              Saved Questions
            </h2>
            <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
              Access your saved research questions from intelligence analysis.
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Questions are saved within individual workspaces.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <div className="mb-4 inline-flex rounded-xl bg-amber-100 p-3 text-amber-600 dark:bg-amber-900 dark:text-amber-300">
              <Sparkles className="h-6 w-6" />
            </div>
            <h2 className="mb-2 text-xl font-semibold text-slate-900 dark:text-slate-100">
              Research Artifacts
            </h2>
            <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
              View saved intelligence analysis artifacts and snapshots.
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Artifacts are managed within individual workspaces.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <div className="mb-4 inline-flex rounded-xl bg-emerald-100 p-3 text-emerald-600 dark:bg-emerald-900 dark:text-emerald-300">
              <FileText className="h-6 w-6" />
            </div>
            <h2 className="mb-2 text-xl font-semibold text-slate-900 dark:text-slate-100">
              Research Plans
            </h2>
            <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
              Access structured research plans generated from opportunities.
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Plans are created within individual workspaces.
            </p>
          </div>

          <Link
            to="/reports"
            className="group rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition-all hover:shadow-md hover:border-indigo-300 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-indigo-600"
          >
            <div className="mb-4 inline-flex rounded-xl bg-sky-100 p-3 text-sky-600 dark:bg-sky-900 dark:text-sky-300">
              <Folder className="h-6 w-6" />
            </div>
            <h2 className="mb-2 text-xl font-semibold text-slate-900 dark:text-slate-100">
              Reports
            </h2>
            <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
              Generate and view comprehensive research reports.
            </p>
            <div className="flex items-center text-sm font-medium text-sky-600 dark:text-sky-400 group-hover:underline">
              View reports
              <ArrowRight className="ml-1 h-4 w-4" />
            </div>
          </Link>
        </div>

        <div className="mt-8 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
          <p>
            <strong>Note:</strong> Questions, artifacts, and plans are currently managed within individual workspaces. Open a workspace to access these assets.
          </p>
        </div>
      </div>
    </Layout>
  );
};

export default Library;
