import React from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Atom,
  BookOpen,
  BrainCircuit,
  Database,
  FileText,
  Microscope,
  Search,
  ShieldCheck,
  Sparkles,
  Workflow,
} from 'lucide-react';

const featureCards = [
  {
    title: 'Signal Search',
    description: 'Query ArXiv, Semantic Scholar, IEEE, Springer, and NASA ADS from one place.',
    icon: Search,
    bg: 'rgba(79, 70, 229, 0.12)',
    color: '#4f46e5',
  },
  {
    title: 'Workspace Intelligence',
    description: 'Organize papers by project and keep long-running context preserved.',
    icon: Workflow,
    bg: 'rgba(14, 165, 233, 0.12)',
    color: '#0284c7',
  },
  {
    title: 'AI Synthesis',
    description: 'Generate summaries, insights, and review drafts from selected papers.',
    icon: BrainCircuit,
    bg: 'rgba(16, 185, 129, 0.12)',
    color: '#059669',
  },
  {
    title: 'DocSpace',
    description: 'Browse imported papers with metadata, abstract view, and direct links.',
    icon: FileText,
    bg: 'rgba(236, 72, 153, 0.12)',
    color: '#db2777',
  },
  {
    title: 'Security',
    description: 'Use local login or Google sign in with JWT-based sessions.',
    icon: ShieldCheck,
    bg: 'rgba(15, 118, 110, 0.12)',
    color: '#0f766e',
  },
  {
    title: 'Scale',
    description: 'Page through large result sets and import only what matters.',
    icon: Database,
    bg: 'rgba(245, 158, 11, 0.12)',
    color: '#d97706',
  },
];

const Landing: React.FC = () => {
  return (
    <div className="landing-shell">
      <div className="landing-wrap">
        <header className="landing-nav">
          <div className="landing-brand">
            <div className="landing-brand-chip">
              <Microscope className="h-4.5 w-4.5" />
            </div>
            <div>
              <h1>ResearchHub AI</h1>
              <p>Neural Research Interface</p>
            </div>
          </div>
          <div className="landing-actions">
            <Link to="/login" className="landing-btn-ghost">
              Sign in
            </Link>
            <Link to="/register" className="landing-btn-primary">
              Create account
            </Link>
          </div>
        </header>

        <main>
          <section className="landing-hero">
            <span className="landing-kicker">
              <Sparkles className="h-3.5 w-3.5" />
              Research command center
            </span>
            <h2 className="landing-title">
              A clean workspace for paper discovery, synthesis, and execution.
            </h2>
            <p className="landing-sub">
              ResearchHub AI brings search, imports, AI tools, and documentation into one focused flow.
            </p>

            <div className="landing-pill-row">
              <span className="landing-pill">
                <Atom className="h-3.5 w-3.5" />
                Multi-source search
              </span>
              <span className="landing-pill">
                <BookOpen className="h-3.5 w-3.5" />
                AI review workflows
              </span>
            </div>

            <div className="landing-cta-row">
              <Link to="/register" className="hero-btn-primary">
                Launch workspace
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link to="/login" className="hero-btn-secondary">
                Continue session
              </Link>
            </div>

            <div className="landing-hero-orb" aria-hidden="true">
              <div className="orb-core" />
              <div className="orb-ring orb-ring-a" />
              <div className="orb-ring orb-ring-b" />
              <div className="orb-ring orb-ring-c" />
            </div>
          </section>

          <section className="landing-section">
            <h3>Core capabilities</h3>
            <p className="section-sub">Simple, high-signal components for end-to-end research work.</p>
            <div className="landing-feature-grid">
              {featureCards.map((feature) => {
                const Icon = feature.icon;
                return (
                  <article key={feature.title} className="landing-feature-card">
                    <div
                      className="landing-feature-icon"
                      style={{ background: feature.bg, color: feature.color }}
                    >
                      <Icon className="h-4.5 w-4.5" />
                    </div>
                    <h4>{feature.title}</h4>
                    <p>{feature.description}</p>
                  </article>
                );
              })}
            </div>
          </section>

          <p className="landing-footer-note">
            FastAPI backend | React + TypeScript frontend | secure auth with local and Google sign in
          </p>
        </main>
      </div>
    </div>
  );
};

export default Landing;
