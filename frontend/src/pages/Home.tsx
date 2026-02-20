import { Link } from 'react-router-dom';
import { Search, MessageSquare, FileText, BookOpen } from 'lucide-react';
import Layout from '../components/Layout';

const Home = () => {
  return (
    <Layout userEmail="user@example.com" userInitials="U">
      <div>
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-slate-900 mb-2">
            Your AI-Powered <span className="text-indigo-600">Research Assistant</span>
          </h1>
          <p className="text-lg text-slate-600 mb-6">
            Accelerate your research with intelligent paper discovery, AI-powered insights, and collaborative document editing - all in one platform.
          </p>
          <div className="flex gap-4">
            <Link
              to="/search"
              className="bg-indigo-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-indigo-700 transition-colors"
            >
              Start Researching
            </Link>
            <Link
              to="/docs"
              className="border border-slate-300 text-slate-700 px-6 py-3 rounded-lg font-semibold hover:bg-slate-50 transition-colors"
            >
              Try DocSpace
            </Link>
          </div>
        </div>

        <div className="mb-12">
          <h2 className="text-2xl font-bold text-slate-900 mb-6">Powerful Features for Modern Research</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="bg-white rounded-lg border border-slate-200 p-6">
              <Search className="h-10 w-10 text-indigo-600 mb-4" />
              <h3 className="font-semibold text-slate-900 mb-2">Smart Paper Search</h3>
              <p className="text-sm text-slate-600">
                Find research papers across multiple databases with AI-powered search.
              </p>
            </div>
            <div className="bg-white rounded-lg border border-slate-200 p-6">
              <MessageSquare className="h-10 w-10 text-indigo-600 mb-4" />
              <h3 className="font-semibold text-slate-900 mb-2">AI Chat Assistant</h3>
              <p className="text-sm text-slate-600">
                Ask questions about your research papers and get intelligent responses.
              </p>
            </div>
            <div className="bg-white rounded-lg border border-slate-200 p-6">
              <FileText className="h-10 w-10 text-indigo-600 mb-4" />
              <h3 className="font-semibold text-slate-900 mb-2">DocSpace Editor</h3>
              <p className="text-sm text-slate-600">
                Create and edit documents with rich text formatting like Google Docs.
              </p>
            </div>
            <div className="bg-white rounded-lg border border-slate-200 p-6">
              <BookOpen className="h-10 w-10 text-indigo-600 mb-4" />
              <h3 className="font-semibold text-slate-900 mb-2">Literature Review</h3>
              <p className="text-sm text-slate-600">
                Generate comprehensive literature reviews from selected papers.
              </p>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-r from-indigo-600 to-purple-600 rounded-xl p-8 text-white">
          <h2 className="text-2xl font-bold mb-4">Why Choose ResearchHub AI?</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="flex items-center gap-2">
              <span className="text-xl">✓</span>
              <span>Save 80% time on literature review</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xl">✓</span>
              <span>Access millions of research papers</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xl">✓</span>
              <span>AI-powered insights and summaries</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xl">✓</span>
              <span>Collaborative workspace features</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xl">✓</span>
              <span>Export to multiple formats</span>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default Home;
