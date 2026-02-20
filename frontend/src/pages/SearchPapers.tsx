import React, { useEffect, useState } from 'react';
import api from '../api';
import {
    Search, ExternalLink, Plus, CheckCircle, AlertCircle,
    Loader2, Tag, Calendar, SlidersHorizontal,
    Telescope, BookOpen, Cpu, Layers, Rocket
} from 'lucide-react';
import Layout from '../components/Layout';

interface Paper {
    title: string;
    authors: string[];
    abstract: string;
    url: string;
    published: string;
    categories: string[];
    source?: string;
    doi?: string;
    bibcode?: string;
} 

interface Workspace {
    id: number;
    name: string;
}

const CATEGORIES = [
    { value: 'all', label: 'All Categories' },
    { value: 'cs.AI', label: 'cs.AI — Artificial Intelligence' },
    { value: 'cs.LG', label: 'cs.LG — Machine Learning' },
    { value: 'cs.CL', label: 'cs.CL — Computation & Language' },
    { value: 'cs.CV', label: 'cs.CV — Computer Vision' },
    { value: 'cs.RO', label: 'cs.RO — Robotics' },
    { value: 'math.ST', label: 'math.ST — Statistics' },
    { value: 'physics', label: 'Physics' },
    { value: 'q-bio', label: 'Quantitative Biology' },
    { value: 'econ', label: 'Economics' },
];

const SORTS = [
    { value: 'relevance', label: '⭐ Relevance' },
    { value: 'submittedDate', label: '📅 Newest' },
    { value: 'lastUpdatedDate', label: '🔄 Updated' },
];

type Source = 'arxiv' | 'semantic' | 'ieee' | 'springer' | 'nasa';

interface SourceCfg {
    label: string;
    icon: React.ReactNode;
    color: string;
    bg: string;
    desc: string;
    endpoint: string;
}

const SOURCE_CONFIG: Record<Source, SourceCfg> = {
    arxiv: {
        label: 'ArXiv',
        icon: <Telescope style={{ width: 14, height: 14 }} />,
        color: '#6366f1',
        bg: 'rgba(99,102,241,0.12)',
        desc: '2M+ · CS, Math, Physics',
        endpoint: '/papers/search',
    },
    semantic: {
        label: 'Semantic Scholar',
        icon: <BookOpen style={{ width: 14, height: 14 }} />,
        color: '#10b981',
        bg: 'rgba(16,185,129,0.12)',
        desc: '200M+ · All fields',
        endpoint: '/papers/search-semantic',
    },
    ieee: {
        label: 'IEEE Xplore',
        icon: <Cpu style={{ width: 14, height: 14 }} />,
        color: '#f59e0b',
        bg: 'rgba(245,158,11,0.12)',
        desc: '5M+ · Engineering',
        endpoint: '/papers/search-ieee',
    },
    springer: {
        label: 'Springer Nature',
        icon: <Layers style={{ width: 14, height: 14 }} />,
        color: '#ec4899',
        bg: 'rgba(236,72,153,0.12)',
        desc: '12M+ · Science & Tech',
        endpoint: '/papers/search-springer',
    },
    nasa: {
        label: 'NASA ADS',
        icon: <Rocket style={{ width: 14, height: 14 }} />,
        color: '#0ea5e9',
        bg: 'rgba(14,165,233,0.12)',
        desc: '15M+ · Astronomy & Physics',
        endpoint: '/papers/search-nasa',
    },
};

const SearchPapers = () => {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState<Paper[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
    const [activeWorkspaceId, setActiveWorkspaceId] = useState<number | null>(null);
    const [importedSet, setImportedSet] = useState<Set<string>>(new Set());
    const [importingTitle, setImportingTitle] = useState<string | null>(null);
    const [showFilters, setShowFilters] = useState(false);
    const [category, setCategory] = useState('all');
    const [sortBy, setSortBy] = useState('relevance');
    const [source, setSource] = useState<Source>('arxiv');

    useEffect(() => {
        api.get('/workspaces/')
            .then((r) => {
                if (r.data.length) { setWorkspaces(r.data); setActiveWorkspaceId(r.data[0].id); }
            })
            .catch(() => { });
    }, []);

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query.trim()) return;
        setLoading(true);
        setError(null);
        setResults([]);
        setImportedSet(new Set());
        try {
            const cfg = SOURCE_CONFIG[source];
            const params = new URLSearchParams({ query: query.trim(), max_results: '15' });
            if (source === 'arxiv') {
                params.set('category', category);
                params.set('sort_by', sortBy);
            }
            const res = await api.get(`${cfg.endpoint}?${params}`);
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
        } catch { } finally {
            setImportingTitle(null);
        }
    };

    const activeSrc = SOURCE_CONFIG[source];

    return (
        <Layout>
            <div className="page-enter">
                <h1 className="text-3xl font-bold text-slate-900 mb-1">Search Research Papers</h1>
                <p className="text-slate-500 mb-5">5 live databases — pick your source and search instantly</p>

                {/* Source Toggle — scrollable row */}
                <div className="flex gap-2 mb-5 overflow-x-auto pb-1" style={{ scrollbarWidth: 'none' }}>
                    {(Object.entries(SOURCE_CONFIG) as [Source, SourceCfg][]).map(([key, cfg]) => (
                        <button
                            key={key}
                            onClick={() => { setSource(key); setResults([]); setError(null); }}
                            className="flex-shrink-0 flex items-center gap-1.5 px-3.5 py-2 rounded-xl border text-sm font-medium transition-all whitespace-nowrap"
                            style={
                                source === key
                                    ? { background: cfg.bg, color: cfg.color, borderColor: cfg.color, boxShadow: `0 2px 10px ${cfg.bg}` }
                                    : { background: 'white', color: '#64748b', borderColor: '#e2e8f0' }
                            }
                        >
                            {cfg.icon}
                            <span>{cfg.label}</span>
                            {source === key && <span className="text-xs opacity-60 hidden lg:inline">· {cfg.desc}</span>}
                        </button>
                    ))}
                </div>

                {/* Selected source info pill */}
                <div className="mb-4 flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-full max-w-max"
                    style={{ background: activeSrc.bg, color: activeSrc.color }}>
                    {activeSrc.icon}&nbsp;<span>{activeSrc.label}</span>&nbsp;·&nbsp;<span className="opacity-70">{activeSrc.desc}</span>
                </div>

                {/* Search bar */}
                <div className="bg-white rounded-2xl border border-slate-100 p-5 mb-6" style={{ boxShadow: '0 1px 8px rgba(0,0,0,0.04)' }}>
                    <form onSubmit={handleSearch} className="flex gap-3 mb-3">
                        <div className="relative flex-grow">
                            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
                                <Search style={{ width: 17, height: 17 }} className="text-slate-400" />
                            </div>
                            <input
                                type="text"
                                className="block w-full rounded-xl border border-slate-200 py-3 pl-10 pr-4 text-slate-900 placeholder:text-slate-400 focus:outline-none text-sm"
                                style={{ boxShadow: `0 0 0 0px ${activeSrc.color}` }}
                                onFocus={e => (e.target.style.boxShadow = `0 0 0 2px ${activeSrc.color}55`)}
                                onBlur={e => (e.target.style.boxShadow = '')}
                                placeholder="e.g. neural networks, black holes, CRISPR, photovoltaics…"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                            />
                        </div>
                        {source === 'arxiv' && (
                            <button type="button" onClick={() => setShowFilters(!showFilters)}
                                className={`px-3 py-2.5 rounded-xl border text-sm font-medium flex items-center gap-1.5 transition-colors ${showFilters ? 'border-indigo-300 bg-indigo-50 text-indigo-600' : 'border-slate-200 text-slate-600 hover:bg-slate-50'}`}>
                                <SlidersHorizontal style={{ width: 15, height: 15 }} /> Filters
                            </button>
                        )}
                        <button type="submit" disabled={loading || !query.trim()}
                            className="rounded-xl px-6 py-3 text-sm font-semibold text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                            style={{ background: `linear-gradient(135deg, ${activeSrc.color}, ${activeSrc.color}bb)` }}>
                            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                            Search
                        </button>
                    </form>

                    {/* ArXiv filters */}
                    {source === 'arxiv' && showFilters && (
                        <div className="flex flex-wrap items-center gap-4 pt-3 border-t border-slate-100">
                            <div className="flex items-center gap-2">
                                <label className="text-xs font-medium text-slate-500 uppercase tracking-wide">Category</label>
                                <select value={category} onChange={e => setCategory(e.target.value)}
                                    className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 focus:outline-none">
                                    {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                                </select>
                            </div>
                            <div className="flex items-center gap-2">
                                <label className="text-xs font-medium text-slate-500 uppercase tracking-wide">Sort</label>
                                <select value={sortBy} onChange={e => setSortBy(e.target.value)}
                                    className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 focus:outline-none">
                                    {SORTS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                                </select>
                            </div>
                        </div>
                    )}

                    {/* Workspace selector */}
                    <div className={`flex items-center gap-3 ${source === 'arxiv' && showFilters ? 'mt-3 pt-3 border-t border-slate-100' : ''}`}>
                        <label className="text-sm text-slate-500">Import to:</label>
                        <select value={activeWorkspaceId ?? ''} onChange={(e) => setActiveWorkspaceId(e.target.value ? Number(e.target.value) : null)}
                            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 focus:outline-none">
                            <option value="">— select workspace —</option>
                            {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
                        </select>
                    </div>
                </div>

                {/* Error */}
                {error && (
                    <div className="mb-4 flex items-center gap-2 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 border border-red-100">
                        <AlertCircle className="h-4 w-4 flex-shrink-0" /> {error}
                    </div>
                )}

                {/* Count */}
                {!loading && results.length > 0 && (
                    <p className="text-sm text-slate-500 mb-4 font-medium">
                        {results.length} results from <span style={{ color: activeSrc.color }} className="font-semibold">{activeSrc.label}</span>
                    </p>
                )}

                {/* Loader */}
                {loading && (
                    <div className="flex items-center justify-center py-20 text-slate-400 gap-3">
                        <Loader2 className="h-6 w-6 animate-spin" style={{ color: activeSrc.color }} />
                        <span>Searching {activeSrc.label}…</span>
                    </div>
                )}

                {/* Results */}
                <div className="space-y-4">
                    {results.map((paper, idx) => {
                        const imported = importedSet.has(paper.title);
                        const isImporting = importingTitle === paper.title;
                        return (
                            <div key={idx} className="bg-white rounded-2xl border border-slate-100 p-6 hover:shadow-lg transition-all duration-200"
                                style={{ boxShadow: '0 1px 8px rgba(0,0,0,0.04)' }}>
                                <div className="flex items-start justify-between gap-3 mb-2">
                                    <h3 className="text-base font-semibold text-slate-900 leading-snug flex-1">{paper.title}</h3>
                                    <button onClick={() => handleImport(paper)}
                                        disabled={imported || isImporting || !activeWorkspaceId}
                                        className={`flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all border ${imported
                                            ? 'bg-emerald-50 text-emerald-600 border-emerald-100 cursor-default'
                                            : 'bg-indigo-50 text-indigo-600 border-indigo-100 hover:bg-indigo-100'
                                            } disabled:opacity-50`}>
                                        {imported ? <><CheckCircle className="h-3.5 w-3.5" /> Saved</>
                                            : isImporting ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Saving…</>
                                                : <><Plus className="h-3.5 w-3.5" /> Import</>}
                                    </button>
                                </div>
                                <p className="text-sm text-slate-500 mb-2">
                                    {paper.authors.slice(0, 4).join(', ')}{paper.authors.length > 4 ? ' et al.' : ''}
                                </p>
                                <p className="text-sm text-slate-600 line-clamp-3 leading-relaxed">{paper.abstract}</p>

                                <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
                                    {paper.published && (
                                        <span className="flex items-center gap-1 bg-slate-50 text-slate-500 px-2 py-1 rounded-lg">
                                            <Calendar className="h-3.5 w-3.5" />{paper.published}
                                        </span>
                                    )}
                                    <span className="flex items-center gap-1 px-2 py-1 rounded-lg font-medium"
                                        style={{ background: activeSrc.bg, color: activeSrc.color }}>
                                        {activeSrc.icon}&nbsp;{activeSrc.label}
                                    </span>
                                    {paper.categories.slice(0, 2).map((cat) => (
                                        <span key={cat} className="flex items-center gap-1 bg-slate-50 text-slate-500 px-2 py-1 rounded-lg">
                                            <Tag className="h-3 w-3" />{cat}
                                        </span>
                                    ))}

                                    {/* Source-specific metadata */}
                                    {paper.doi && (
                                        <a href={`https://doi.org/${paper.doi}`} target="_blank" rel="noreferrer"
                                            className="text-xs font-medium ml-auto px-2 py-1 rounded-lg bg-emerald-50 text-emerald-700 hover:underline">
                                            DOI: {paper.doi}
                                        </a>
                                    )}
                                    {source === 'nasa' && paper.bibcode && (
                                        <a href={`https://ui.adsabs.harvard.edu/abs/${paper.bibcode}`} target="_blank" rel="noreferrer"
                                            className="text-xs font-medium ml-auto px-2 py-1 rounded-lg bg-emerald-50 text-emerald-700 hover:underline">
                                            Bibcode: {paper.bibcode}
                                        </a>
                                    )}

                                    {paper.url && (
                                        <a href={paper.url} target="_blank" rel="noreferrer"
                                            className="flex items-center gap-1 font-medium ml-auto hover:underline"
                                            style={{ color: activeSrc.color }}>
                                            View Paper <ExternalLink className="h-3.5 w-3.5" />
                                        </a>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* Empty states */}
                {!loading && results.length === 0 && query && !error && (
                    <div className="text-center py-16 text-slate-400">
                        No results for "{query}". Try different keywords or switch to another source.
                    </div>
                )}
                {!loading && !query && (
                    <div className="text-center py-20">
                        <div className="w-16 h-16 mx-auto rounded-2xl flex items-center justify-center mb-4"
                            style={{ background: activeSrc.bg }}>
                            <Search style={{ width: 28, height: 28, color: activeSrc.color }} />
                        </div>
                        <p className="text-slate-400 text-base font-medium">{activeSrc.label}</p>
                        <p className="text-slate-300 text-sm mt-1">{activeSrc.desc}</p>
                    </div>
                )}
            </div>
        </Layout>
    );
};

export default SearchPapers;
