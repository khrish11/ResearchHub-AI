import React, { useEffect, useState } from 'react';
import api from '../api';
import { Search } from 'lucide-react';
import Layout from '../components/Layout';

interface Paper {
    title: string;
    authors: string[];
    abstract: string;
    url: string;
    // In real app, we would have ID or we generate fake one
}

interface Workspace {
    id: number;
    name: string;
    description?: string;
}

const SearchPapers = () => {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState<Paper[]>([]);
    const [loading, setLoading] = useState(false);
    const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
    const [activeWorkspaceId, setActiveWorkspaceId] = useState<number | null>(null);
    const [importMessage, setImportMessage] = useState<string | null>(null);

    useEffect(() => {
        const initWorkspace = async () => {
            try {
                // Try to get an existing default workspace or create one
                const res = await api.post('/workspaces/default');
                const ws: Workspace = res.data;
                setWorkspaces([ws]);
                setActiveWorkspaceId(ws.id);
            } catch (err) {
                console.error('Failed to initialize workspace', err);
            }
        };
        initWorkspace();
    }, []);

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setImportMessage(null);
        try {
            const response = await api.get(`/papers/search?query=${encodeURIComponent(query)}`);
            setResults(response.data.papers);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleImport = async (paper: Paper) => {
        if (!activeWorkspaceId) {
            setImportMessage('No workspace available. Please try again after reloading.');
            return;
        }
        try {
            await api.post('/papers/import', {
                title: paper.title,
                authors: paper.authors,
                abstract: paper.abstract,
                url: paper.url,
                workspace_id: activeWorkspaceId,
            });
            setImportMessage(`Imported "${paper.title}" into your workspace.`);
        } catch (err) {
            console.error(err);
            setImportMessage('Failed to import paper. Please try again.');
        }
    };

    return (
        <Layout userEmail="user@example.com" userInitials="U">
            <div>
                <h1 className="text-3xl font-bold text-slate-900 mb-2">Search Research Papers</h1>
                <p className="text-slate-600 mb-6">Search across millions of research papers and import them to your workspace</p>

                <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
                    <form onSubmit={handleSearch} className="flex gap-4 mb-4">
                        <div className="relative flex-grow">
                            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                                <Search className="h-5 w-5 text-slate-400" />
                            </div>
                            <input
                                type="text"
                                className="block w-full rounded-lg border-0 py-3 pl-10 pr-4 text-slate-900 ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-indigo-600 sm:text-sm"
                                placeholder="agentic ai"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                            />
                        </div>
                        <button
                            type="submit"
                            className="rounded-lg bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-700 transition-colors"
                        >
                            Search
                        </button>
                    </form>
                    <div className="flex items-center gap-4">
                        <select
                            value={activeWorkspaceId ?? ''}
                            onChange={(e) => setActiveWorkspaceId(e.target.value ? Number(e.target.value) : null)}
                            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-600"
                        >
                            <option value="">All Sources</option>
                            {workspaces.map((w) => (
                                <option key={w.id} value={w.id}>{w.name}</option>
                            ))}
                        </select>
                    </div>
                </div>

                {importMessage && (
                    <div className="mb-4 rounded-lg bg-indigo-50 px-4 py-3 text-sm text-indigo-800">
                        {importMessage}
                    </div>
                )}

                {loading && <div className="text-center text-slate-500 py-8">Searching...</div>}

                {results.length > 0 && (
                    <div className="mb-4 text-slate-600">Found {results.length} papers</div>
                )}

                <div className="space-y-4">
                    {results.map((paper, index) => (
                        <div key={index} className="bg-white rounded-lg border border-slate-200 p-6 hover:shadow-md transition-shadow">
                            <div className="flex items-start gap-4">
                                <input type="checkbox" className="mt-1 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-600" />
                                <div className="flex-1">
                                    <div className="flex items-start justify-between">
                                        <h3 className="text-lg font-semibold text-slate-900 pr-4">{paper.title}</h3>
                                        <button
                                            onClick={() => handleImport(paper)}
                                            className="text-slate-400 hover:text-indigo-600"
                                            title="Add to workspace"
                                        >
                                            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                                            </svg>
                                        </button>
                                    </div>
                                    <p className="mt-1 text-sm text-slate-600">{paper.authors.join(', ')}</p>
                                    <p className="mt-3 text-sm text-slate-700 line-clamp-3">{paper.abstract}</p>
                                    <div className="mt-4 flex items-center gap-4 text-sm">
                                        <span className="text-slate-500">2025-07-02</span>
                                        <span className="text-slate-500">9 citations</span>
                                        <a href={paper.url} target="_blank" rel="noreferrer" className="text-indigo-600 hover:text-indigo-700 font-medium">
                                            View Paper →
                                        </a>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </Layout>
    );
};

export default SearchPapers;
