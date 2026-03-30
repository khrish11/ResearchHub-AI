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
    title: 'Search Fabric',
    description: 'Scan 28+ connected research rails from one search surface instead of jumping across fragmented portals.',
    icon: Search,
    bg: 'rgba(79, 70, 229, 0.12)',
    color: '#4f46e5',
  },
  {
    title: 'Workspace Memory',
    description: 'Keep papers, AI context, notes, and exports pinned to one real project instead of one-off sessions.',
    icon: Workflow,
    bg: 'rgba(14, 165, 233, 0.12)',
    color: '#0284c7',
  },
  {
    title: 'AI Synthesis',
    description: 'Move from paper discovery to summaries, fault detection, review drafting, and context-aware chat.',
    icon: BrainCircuit,
    bg: 'rgba(16, 185, 129, 0.12)',
    color: '#059669',
  },
  {
    title: 'Reading Layer',
    description: 'Inspect imported papers, resolve access, open full text, and keep evidence review close to the workspace.',
    icon: FileText,
    bg: 'rgba(236, 72, 153, 0.12)',
    color: '#db2777',
  },
  {
    title: 'Control Surface',
    description: 'Use account, workspace, and data-rights flows that fit a real product instead of a demo shell.',
    icon: ShieldCheck,
    bg: 'rgba(15, 118, 110, 0.12)',
    color: '#0f766e',
  },
  {
    title: 'Portable Output',
    description: 'Export citations, workspace data, and report artifacts without losing the structure of your research flow.',
    icon: Database,
    bg: 'rgba(245, 158, 11, 0.12)',
    color: '#d97706',
  },
];

const metaCards = [
  { label: 'Source Rails', value: '28+', note: 'public and keyed discovery providers' },
  { label: 'Core Flow', value: 'Search -> Curate -> Synthesize', note: 'one operating loop instead of separate tools' },
  { label: 'Workspace Model', value: 'Project-based', note: 'context persists across papers, chat, and export' },
  { label: 'Outputs', value: 'BibTeX / CSV / PDF / DOCX', note: 'portable research artifacts' },
];

const flowSteps = [
  {
    title: 'Search with signal',
    copy: 'Start broad across connected paper sources, then narrow with source, access, and year filters.',
  },
  {
    title: 'Curate a workspace',
    copy: 'Import only the evidence that belongs to one research question so the project stays coherent.',
  },
  {
    title: 'Interrogate with AI',
    copy: 'Ask questions, compare evidence, and run synthesis only after the workspace holds enough strong material.',
  },
  {
    title: 'Export and execute',
    copy: 'Turn the workspace into citations, reports, and review-ready output without rebuilding context elsewhere.',
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
              <h1>Soyog AI</h1>
              <p>Research Operating Surface</p>
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
              Soyog AI research shell
            </span>
            <h2 className="landing-title">
              Search the literature, build a clean evidence set, and turn it into review-ready output.
            </h2>
            <p className="landing-sub">
              Soyog AI brings multi-source discovery, workspace curation, AI synthesis, and exportable research deliverables into one deliberate workflow.
            </p>

            <div className="landing-pill-row">
              <span className="landing-pill">
                <Atom className="h-3.5 w-3.5" />
                28+ source rails
              </span>
              <span className="landing-pill">
                <BookOpen className="h-3.5 w-3.5" />
                Workspace memory
              </span>
              <span className="landing-pill">
                <BrainCircuit className="h-3.5 w-3.5" />
                AI review workflows
              </span>
            </div>

            <div className="landing-cta-row">
              <Link to="/register" className="hero-btn-primary">
                Launch Soyog AI
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link to="/login" className="hero-btn-secondary">
                Continue session
              </Link>
              <Link to="/register?demo=1" className="hero-btn-secondary">
                Try Demo
              </Link>
            </div>

            <div className="landing-meta-grid">
              {metaCards.map((item) => (
                <article key={item.label} className="landing-meta-card">
                  <p className="landing-meta-label">{item.label}</p>
                  <p className="landing-meta-value">{item.value}</p>
                  <p className="mt-2 text-xs text-slate-200/85">{item.note}</p>
                </article>
              ))}
            </div>

            <div className="landing-hero-orb" aria-hidden="true">
              <div className="orb-core" />
              <div className="orb-ring orb-ring-a" />
              <div className="orb-ring orb-ring-b" />
              <div className="orb-ring orb-ring-c" />
            </div>
          </section>

          <section className="landing-section">
            <h3>What Soyog AI controls</h3>
            <p className="section-sub">A tighter product surface for real research work, not a collection of disconnected tools.</p>
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

          <section className="landing-section">
            <h3>How the flow works</h3>
            <p className="section-sub">Use one project loop from discovery to execution.</p>
            <div className="landing-flow-grid">
              {flowSteps.map((step, index) => (
                <article key={step.title} className="landing-flow-step">
                  <span className="step-no">{index + 1}</span>
                  <h4>{step.title}</h4>
                  <p>{step.copy}</p>
                </article>
              ))}
            </div>
          </section>

          <p className="landing-footer-note">
            Soyog AI runs on FastAPI + React with secure auth, workspace memory, and research-grade export flows
          </p>
          <div className="mt-3 flex flex-wrap items-center justify-center gap-3 text-xs text-slate-300">
            <Link to="/privacy" className="hover:text-white">
              Privacy
            </Link>
            <Link to="/terms" className="hover:text-white">
              Terms
            </Link>
            <Link to="/cookies" className="hover:text-white">
              Cookies
            </Link>
            <Link to="/data-rights" className="hover:text-white">
              Data Rights
            </Link>
          </div>
        </main>
      </div>
    </div>
  );
};

export default Landing;
