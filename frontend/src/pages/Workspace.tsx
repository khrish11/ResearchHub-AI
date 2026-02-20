import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, ExternalLink } from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';

interface Paper {
  id: number;
  title: string;
  authors: string;
  abstract: string;
  url?: string;
}

interface ChatItem {
  id: number;
  message: string;
  response: string;
}

interface WorkspaceDetail {
  id: number;
  name: string;
  description?: string;
  papers: Paper[];
  chats: ChatItem[];
}

const Workspace = () => {
  const { id } = useParams();
  const [workspace, setWorkspace] = useState<WorkspaceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [chatInput, setChatInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'papers' | 'chat' | 'review'>('papers');

  useEffect(() => {
    const fetchWorkspace = async () => {
      if (!id) return;
      setLoading(true);
      setError(null);
      try {
        const res = await api.get(`/workspaces/${id}`);
        setWorkspace(res.data);
      } catch (err) {
        console.error(err);
        setError('Failed to load workspace.');
      } finally {
        setLoading(false);
      }
    };
    fetchWorkspace();
  }, [id]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!workspace || !chatInput.trim()) return;
    setSending(true);
    setError(null);
    try {
      const res = await api.post('/chat/', {
        message: chatInput,
        workspace_id: workspace.id,
      });
      const aiResponse: string = res.data.response;
      const newItem: ChatItem = {
        id: Date.now(),
        message: chatInput,
        response: aiResponse,
      };
      setWorkspace({
        ...workspace,
        chats: [...workspace.chats, newItem],
      });
      setChatInput('');
    } catch (err) {
      console.error(err);
      setError('Failed to send message. Check that GROQ_API_KEY is configured.');
    } finally {
      setSending(false);
    }
  };

  return (
    <Layout userEmail="user@example.com" userInitials="U">
      <div>
        {loading && <div className="text-slate-500">Loading workspace...</div>}
        {error && <div className="mb-4 text-sm text-red-600">{error}</div>}
        {workspace && (
          <>
            <div className="flex items-center gap-4 mb-6">
              <Link to="/dashboard" className="text-slate-600 hover:text-slate-900">
                <ArrowLeft className="h-5 w-5" />
              </Link>
              <div>
                <h1 className="text-2xl font-bold text-slate-900">{workspace.name}</h1>
                <p className="text-sm text-slate-600">{workspace.papers.length} papers selected</p>
              </div>
            </div>

            {/* Tabs */}
            <div className="border-b border-slate-200 mb-6">
              <nav className="flex gap-6">
                <button
                  onClick={() => setActiveTab('papers')}
                  className={`pb-3 px-1 border-b-2 font-medium text-sm ${
                    activeTab === 'papers'
                      ? 'border-indigo-600 text-indigo-600'
                      : 'border-transparent text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Papers ({workspace.papers.length})
                </button>
                <button
                  onClick={() => setActiveTab('chat')}
                  className={`pb-3 px-1 border-b-2 font-medium text-sm ${
                    activeTab === 'chat'
                      ? 'border-indigo-600 text-indigo-600'
                      : 'border-transparent text-slate-600 hover:text-slate-900'
                  }`}
                >
                  AI Chat
                </button>
                <button
                  onClick={() => setActiveTab('review')}
                  className={`pb-3 px-1 border-b-2 font-medium text-sm ${
                    activeTab === 'review'
                      ? 'border-indigo-600 text-indigo-600'
                      : 'border-transparent text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Generate Review
                </button>
              </nav>
            </div>

            {/* Tab Content */}
            {activeTab === 'papers' && (
              <div className="space-y-4">
                {workspace.papers.length === 0 ? (
                  <div className="bg-white rounded-lg border border-slate-200 p-8 text-center">
                    <p className="text-slate-600">No papers yet. Use the Search page to import papers into this workspace.</p>
                  </div>
                ) : (
                  workspace.papers.map((paper) => (
                    <div key={paper.id} className="bg-white rounded-lg border border-slate-200 p-6">
                      <h3 className="text-lg font-semibold text-slate-900 mb-2">{paper.title}</h3>
                      <p className="text-sm text-slate-600 mb-3">{paper.authors}</p>
                      <p className="text-sm text-slate-700 mb-4 line-clamp-3">{paper.abstract}</p>
                      {paper.url && (
                        <a
                          href={paper.url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-700 font-medium"
                        >
                          View Paper <ExternalLink className="h-4 w-4" />
                        </a>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === 'chat' && (
              <div className="bg-white rounded-lg border border-slate-200 p-6">
                <div className="mb-4">
                  <h2 className="text-lg font-semibold text-slate-900">AI Research Assistant</h2>
                  <p className="text-sm text-slate-600">{workspace.papers.length} papers selected - Ask anything!</p>
                </div>
                <div className="mb-6 p-4 bg-slate-50 rounded-lg max-h-96 overflow-y-auto">
                  {workspace.chats.length === 0 ? (
                    <p className="text-sm text-slate-600">
                      Start a conversation by asking a question about the papers in this workspace.
                    </p>
                  ) : (
                    <div className="space-y-4">
                      {workspace.chats.map((item) => (
                        <div key={item.id} className="space-y-2">
                          <div className="text-sm font-medium text-slate-900">You</div>
                          <div className="text-sm text-slate-700">{item.message}</div>
                          <div className="text-sm font-medium text-slate-900 mt-3">ResearchHub AI</div>
                          <div className="text-sm text-slate-700 whitespace-pre-wrap">{item.response}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <form onSubmit={handleSendMessage} className="flex gap-2">
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Ask about the selected papers..."
                    className="flex-1 rounded-lg border border-slate-300 py-3 px-4 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-600 sm:text-sm"
                  />
                  <button
                    type="submit"
                    disabled={sending}
                    className="rounded-lg bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60 transition-colors"
                  >
                    {sending ? 'Sending...' : 'Send'}
                  </button>
                </form>
              </div>
            )}

            {activeTab === 'review' && (
              <div className="bg-white rounded-lg border border-slate-200 p-6">
                <h2 className="text-lg font-semibold text-slate-900 mb-4">Generate Literature Review</h2>
                <p className="text-slate-600 mb-6">
                  Generate a comprehensive literature review from the selected papers in this workspace.
                </p>
                <button className="bg-green-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-green-700 transition-colors">
                  Generate Review
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </Layout>
  );
};

export default Workspace;
