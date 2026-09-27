import React from 'react';
import { Link } from 'react-router-dom';
import { FileText, Sparkles, ArrowRight } from 'lucide-react';
import Layout from '../components/Layout';

const Reports: React.FC = () => {
  return (
    <Layout>
      <div className="mx-auto max-w-5xl px-4 py-12">
        <div className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Reports
          </h1>
          <p className="mt-2 text-lg text-slate-600 dark:text-slate-400">
            Generate and view comprehensive research reports from your workspaces.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <Link
            to="/research-report"
            className="group rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition-all hover:shadow-md hover:border-indigo-300 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-indigo-600"
          >
            <div className="mb-4 inline-flex rounded-xl bg-indigo-100 p-3 text-indigo-600 dark:bg-indigo-900 dark:text-indigo-300">
              <Sparkles className="h-6 w-6" />
            </div>
            <h2 className="mb-2 text-xl font-semibold text-slate-900 dark:text-slate-100">
              Generate Report
            </h2>
            <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
              Create a comprehensive research report from your workspace papers or research intelligence artifacts.
            </p>
            <div className="flex items-center text-sm font-medium text-indigo-600 dark:text-indigo-400 group-hover:underline">
              Generate new report
              <ArrowRight className="ml-1 h-4 w-4" />
            </div>
          </Link>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <div className="mb-4 inline-flex rounded-xl bg-slate-100 p-3 text-slate-600 dark:bg-slate-700 dark:text-slate-300">
              <FileText className="h-6 w-6" />
            </div>
            <h2 className="mb-2 text-xl font-semibold text-slate-900 dark:text-slate-100">
              Recent Reports
            </h2>
            <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
              Access your previously generated research reports from workspaces.
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Reports are generated within individual workspaces. Open a workspace to view its reports.
            </p>
          </div>
        </div>

        <div className="mt-8 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
          <p>
            <strong>Tip:</strong> You can also generate reports directly from within a workspace using the "Generate Report" button.
          </p>
        </div>
      </div>
    </Layout>
  );
};

export default Reports;
