import { Link } from 'react-router-dom';
import { Search, MessageSquare, FileText, BookOpen, Sparkles, Orbit, BrainCircuit, Layers3, ArrowRight } from 'lucide-react';
import Layout from '../components/Layout';

const Home = () => {
  const featureCards = [
    {
      title: 'Signal Search',
      desc: 'Probe multi-source paper indexes with richer relevance and live source diagnostics.',
      icon: Search,
      color: '#4f46e5',
    },
    {
      title: 'Context Chat',
      desc: 'Ask long-horizon research questions and keep context pinned to your workspace.',
      icon: MessageSquare,
      color: '#0284c7',
    },
    {
      title: 'Doc Studio',
      desc: 'Draft, refine, and structure manuscripts with AI-guided editing workflows.',
      icon: FileText,
      color: '#0f766e',
    },
    {
      title: 'Review Engine',
      desc: 'Synthesize connected literature clusters instead of isolated single-paper summaries.',
      icon: BookOpen,
      color: '#9333ea',
    },
  ];

  return (
    <Layout>
      <section className="home-hero mb-6">
        <div className="home-hero-content">
          <p className="text-xs uppercase tracking-[0.2em] text-cyan-200 mb-2 flex items-center gap-2">
            <Sparkles className="h-3.5 w-3.5" /> Research Intelligence Layer
          </p>
          <h2 className="text-4xl md:text-5xl font-bold text-white leading-tight max-w-3xl">
            Design Breakthrough Research Pipelines, Not Just Paper Lists
          </h2>
          <p className="text-cyan-100/90 mt-4 max-w-2xl text-sm md:text-base">
            ResearchHub AI now blends deep search, live source verification, and AI-native writing flow in one command surface.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/search" className="hero-btn-primary">
              Launch Search Matrix <ArrowRight className="h-4 w-4" />
            </Link>
            <Link to="/dashboard" className="hero-btn-secondary">
              Open Dashboard
            </Link>
          </div>
        </div>

        <div className="hero-3d">
          <div className="hero-prism" />
          <div className="hero-ring ring-one" />
          <div className="hero-ring ring-two" />
          <div className="hero-ring ring-three" />
        </div>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-7">
        <div className="stat-tile">
          <div className="stat-icon" style={{ background: 'rgba(79, 70, 229, 0.12)', color: '#4f46e5' }}>
            <Orbit className="h-5 w-5" />
          </div>
          <p className="stat-label">Search Fabric</p>
          <p className="stat-value">5 Unified Sources</p>
        </div>
        <div className="stat-tile">
          <div className="stat-icon" style={{ background: 'rgba(2, 132, 199, 0.12)', color: '#0284c7' }}>
            <BrainCircuit className="h-5 w-5" />
          </div>
          <p className="stat-label">AI Core</p>
          <p className="stat-value">Context Aware</p>
        </div>
        <div className="stat-tile">
          <div className="stat-icon" style={{ background: 'rgba(147, 51, 234, 0.12)', color: '#9333ea' }}>
            <Layers3 className="h-5 w-5" />
          </div>
          <p className="stat-label">Workspace Stack</p>
          <p className="stat-value">Import + Export + Synthesis</p>
        </div>
      </section>

      <section className="mb-4">
        <h3 className="text-2xl font-bold text-slate-900 mb-4">Core Systems</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {featureCards.map((card) => {
            const Icon = card.icon;
            return (
              <div key={card.title} className="feature-surface">
                <div className="feature-icon" style={{ background: `${card.color}1f`, color: card.color }}>
                  <Icon className="h-5 w-5" />
                </div>
                <h4 className="text-base font-semibold text-slate-900 mt-3">{card.title}</h4>
                <p className="text-sm text-slate-600 mt-1 leading-relaxed">{card.desc}</p>
              </div>
            );
          })}
        </div>
      </section>
    </Layout>
  );
};

export default Home;
