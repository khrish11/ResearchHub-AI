import React, { useEffect, useState } from 'react';
import api from '../api';
import { Search, ExternalLink, Plus, CheckCircle, AlertCircle, Loader2, Tag, Calendar } from 'lucide-react';
import Layout from '../components/Layout';

interface Paper {
    title: string;
    authors: string[];
    abstract: string;
    url: string;
    published: string;
    categories: string[];
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
    const [error, setError] = useState<string | null>(null);
    const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
    const [activeWorkspaceId, setActiveWorkspaceId] = useState<number | null>(null);
    const [importedSet, setImportedSet] = useState<Set<string>>(new Set());
    const [importingTitle, setImportingTitle] = useState<string | null>(null);

    useEffect(() => {
        // Fetch workspaces (get-or-create default)
        api.post('/workspaces/default')
            .then((res) => {
                setWorkspaces([res.data]);
                setActiveWorkspaceId(res.data.id);
            })
            .catch(() => {
                // If default fails, try listing all
                api.get('/workspaces/').then((r) => {
                    if (r.data.length) {
                        setWorkspaces(r.data);
                        setActiveWorkspaceId(r.data[0].id);
                    }
                }).catch(() => { });
            });
    }, []);

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query.trim()) return;
        setLoading(true);
        setError(null);
        setResults([]);
        setImportedSet(new Set());
        try {
            const res = await api.get(`/papers/search?query=${encodeURIComponent(query)}&max_results=15`);
            setResults(res.data.papers);
        } catch (err: any) {
            setError(err?.response?.data?.detail || 'Search failed. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const handleImport = async (paper: Paper) => {
        if (!activeWorkspaceId) return;
        setImportingTitle(paper.title);
        try {
            await api.post('/papers/import', {
                title: paper.title,
                authors: paper.authors,
                abstract: paper.abstract,
                url: paper.url,
                workspace_id: activeWorkspaceId,
            });
            setImportedSet((prev) => new Set(prev).add(paper.title));
        } catch {
            // silently ignore duplicate import errors
        } finally {
            setImportingTitle(null);
        }
    };

    return (
        <Layout>
            <div>
                <h1 className="text-3xl font-bold text-slate-900 mb-1">Search Research Papers</h1>
                <p className="text-slate-500 mb-6">Live search powered by ArXiv — millions of real papers</p>

                {/* Search bar */}
                <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6 shadow-sm">
                    <form onSubmit={handleSearch} className="flex gap-3 mb-3">
                        <div className="relative flex-grow">
                            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                                <Search className="h-5 w-5 text-slate-400" />
                            </div>
                            <input
                                type="text"
                                className="block w-full rounded-lg border border-slate-300 py-3 pl-10 pr-4 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-600 text-sm"
                                placeholder="e.g. large language models, quantum computing..."
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={loading || !query.trim()}
                            className="rounded-lg bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                            Search
                        </button>
                    </form>

                    <div className="flex items-center gap-3">
                        <label className="text-sm text-slate-600">Import to:</label>
                        <select
                            value={activeWorkspaceId ?? ''}
                            onChange={(e) => setActiveWorkspaceId(e.target.value ? Number(e.target.value) : null)}
                            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-600"
                        >
                            <option value="">— select workspace —</option>
                            {workspaces.map((w) => (
                                <option key={w.id} value={w.id}>{w.name}</option>
                            ))}
                        </select>
                    </div>
                </div>

                {/* Error */}
                {error && (
                    <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
                        <AlertCircle className="h-4 w-4 flex-shrink-0" /> {error}
                    </div>
                )}

                {/* Results count */}
                {!loading && results.length > 0 && (
                    <p className="text-sm text-slate-500 mb-4">{results.length} papers found on ArXiv</p>
                )}

                {/* Loader */}
                {loading && (
                    <div className="flex items-center justify-center py-16 text-slate-400 gap-3">
                        <Loader2 className="h-6 w-6 animate-spin" />
                        <span>Searching ArXiv…</span>
                    </div>
                )}

                {/* Results */}
                <div className="space-y-4">
                    {results.map((paper, idx) => {
                        const imported = importedSet.has(paper.title);
                        const isImporting = importingTitle === paper.title;
                        return (
                            <div key={idx} className="bg-white rounded-xl border border-slate-200 p-6 hover:shadow-md transition-shadow">
                                <div className="flex items-start gap-4">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-start justify-between gap-3">
                                            <h3 className="text-base font-semibold text-slate-900 leading-snug">{paper.title}</h3>
                                            <button
                                                onClick={() => handleImport(paper)}
                                                disabled={imported || isImporting || !activeWorkspaceId}
                                                title={imported ? 'Already imported' : 'Add to workspace'}
                                                className={`flex-shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${imported
                                                        ? 'bg-green-50 text-green-600 cursor-default'
                                                        : 'bg-indigo-50 text-indigo-600 hover:bg-indigo-100'
                                                    } disabled:opacity-50`}
                                            >
                                                {imported ? (
                                                    <><CheckCircle className="h-3.5 w-3.5" /> Saved</>
                                                ) : isImporting ? (
                                                    <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Saving…</>
                                                ) : (
                                                    <><Plus className="h-3.5 w-3.5" /> Import</>
                                                )}
                                            </button>
                                        </div>

                                        {/* Authors */}
                                        <p className="mt-1 text-sm text-slate-500">{paper.authors.slice(0, 4).join(', ')}{paper.authors.length > 4 ? ' et al.' : ''}</p>

                                        {/* Abstract */}
                                        <p className="mt-3 text-sm text-slate-700 line-clamp-3">{paper.abstract}</p>

                                        {/* Metadata row */}
                                        <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-slate-500">
                                            {paper.published && (
                                                <span className="flex items-center gap-1">
                                                    <Calendar className="h-3.5 w-3.5" />
                                                    {paper.published}
                                                </span>
                                            )}
                                            {paper.categories.slice(0, 3).map((cat) => (
                                                <span key={cat} className="flex items-center gap-1 bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">
                                                    <Tag className="h-3 w-3" />{cat}
                                                </span>
                                            ))}
                                            <a
                                                href={paper.url}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="flex items-center gap-1 text-indigo-600 hover:text-indigo-700 font-medium ml-auto"
                                            >
                                                View on ArXiv <ExternalLink className="h-3.5 w-3.5" />
                                            </a>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* Empty state */}
                {!loading && results.length === 0 && query && !error && (
                    <div className="text-center py-16 text-slate-400">No results found. Try a different query.</div>
                )}
                {!loading && !query && (
                    <div className="text-center py-16 text-slate-300 text-lg">
                        Enter a topic above to search millions of ArXiv papers
                    </div>
                )}
            </div>
        </Layout>
    );
};

export default SearchPapers;
