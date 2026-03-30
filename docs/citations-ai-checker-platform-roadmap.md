# Citations, AI Checker, Content Access, and Custom Model Roadmap

## Goal

Add two product features and use them as the base for a stronger research platform:

1. Citations for discovered, uploaded, and workspace papers.
2. AI Checker for uploaded research papers.

At the same time, improve the product around:

1. Higher-trust paper access and metadata coverage.
2. Journal-tier and evidence signals.
3. Migration path from Groq-only inference to a hybrid setup that can include your own trained model.

This plan is designed to fit the current codebase without restructuring core application behavior.

## Current Foundation In This Repo

The codebase already has the right building blocks:

- Upload and extraction pipeline in `backend/routers/upload.py`
- Workspace export flow in `backend/routers/workspaces.py`
- Research-agent and analysis logic in `backend/routers/research_agent.py`
- Search-side citation-related UI behavior in `frontend/src/pages/SearchPapers.tsx`
- Upload flow in `frontend/src/pages/UploadPDF.tsx`
- Workspace review flow in `frontend/src/pages/Workspace.tsx`
- AI routing and model selection in `backend/utils/groq_client.py`
- Central AI orchestration in `backend/services/ai_service.py`
- AI model settings UI in `frontend/src/pages/Settings.tsx`

This means the correct approach is incremental extension, not a rewrite.

## Product Definition

### Feature 1: Citations

Users should be able to:

1. Generate citations for a single paper in APA, MLA, Chicago, IEEE, and BibTeX.
2. Copy a citation immediately from search results, uploaded papers, or workspace papers.
3. Export one or many citations from a workspace.
4. See citation completeness status:
   - complete
   - partial
   - missing metadata

### Feature 2: AI Checker

The AI Checker should review an uploaded paper and return a structured report.

Recommended v1 sections:

1. Paper Snapshot
2. Main Claims
3. Method and Data
4. Evidence Strength
5. Reproducibility Signals
6. Citation Quality
7. Limitations and Risks
8. Potential Red Flags
9. AI-Writing Likelihood Map

Important: this should remain a paper-quality and evidence-review tool first. If you add AI-generated-text detection, it must be presented as probabilistic AI-writing likelihood, not as definitive authorship proof. Hard claims like "this exact section is AI-generated" are technically weak and easy to discredit.

### AI-Writing Detection Requirement

If you want the checker to identify which parts may be AI-generated, the product should do this in a careful way:

1. score text at paragraph or sentence-block level
2. return a heatmap or likelihood label such as:
   - low likelihood
   - medium likelihood
   - high likelihood
3. explain why a block was flagged:
   - repeated phrasing
   - generic transitions
   - shallow specificity
   - template-like structure
   - inconsistent citation grounding
4. always show a disclaimer that this is an advisory signal, not proof

Do not build this as a binary detector.

## Product Experience Plan

### Core UX Principle

Do not create more disconnected pages. Add the new capabilities directly into the flows users already use.

### Where The Features Should Live

1. Search results
   - quick citation actions
   - metadata completeness indicator
   - journal-quality badge when available

2. Upload PDF
   - existing upload behavior stays unchanged
   - after extraction, show:
     - Generate Citation
     - Run AI Checker
     - View AI-writing likelihood map
     - Export Citation

3. Workspace
   - every saved paper should support:
     - copy citation
     - export citation
     - run AI Checker
     - inspect AI-writing likelihood by section
     - compare checker reports over time if the source is reprocessed

4. Research Agent
   - checker output and citations should be reusable in downstream writing tools

### Website Quality Improvements After Adding These Features

To make the site better after rollout:

1. Add trust signals on paper cards:
   - DOI
   - venue
   - year
   - open access flag
   - citation count
   - journal-tier badge when licensed data exists

2. Add consistency in outputs:
   - every AI panel should show source count, model used, timestamp, and export options

3. Improve response clarity:
   - never show raw backend exceptions to end users
   - normalize AI failures into clear UI messages

4. Improve perceived speed:
   - show step-based progress for long paper checks
   - cache extracted text and citation metadata
   - run heavy checker jobs asynchronously

5. Improve credibility:
   - label partial citations clearly
   - mark when a field came from extracted PDF text versus trusted metadata provider
   - label AI-writing flags as probabilistic and advisory

## Technical Plan

## Phase 1: Citations

### Backend

Add a shared citation generation layer that accepts normalized paper metadata and returns:

1. formatted citation by style
2. BibTeX export
3. citation completeness score
4. missing-field warnings

Recommended endpoints:

1. `POST /papers/citation`
   - input: title, authors, year, venue, doi, url, style
   - output: formatted citation, completeness, warnings

2. `GET /papers/{paper_id}/citation`
   - output: same as above, pulling from saved paper data

### Frontend

Add actions in:

1. `SearchPapers.tsx`
2. `UploadPDF.tsx`
3. `Workspace.tsx`

V1 actions:

1. Copy citation
2. Switch style
3. Download BibTeX
4. View missing metadata

### Data Rules

Use trusted metadata priority:

1. Crossref or DOI metadata
2. OpenAlex metadata
3. existing paper record fields
4. extracted PDF title and authors only as fallback

Never fabricate venue, year, DOI, issue, or pages.

## Phase 2: AI Checker

### Backend

Add a dedicated analysis endpoint:

1. `POST /research/paper-check`

Accepted inputs:

1. `paper_id`
2. raw extracted text
3. optional workspace context

Output schema:

1. `snapshot`
2. `claims`
3. `methods`
4. `evidence_strength`
5. `reproducibility`
6. `citation_quality`
7. `limitations`
8. `red_flags`
9. `confidence_notes`
10. `ai_writing_likelihood`
11. `flagged_segments`

### AI-Writing Likeliness Output

For each flagged segment, return:

1. `start_offset`
2. `end_offset`
3. `text_excerpt`
4. `likelihood_score`
5. `likelihood_band`
6. `reasons`
7. `review_note`

This allows the frontend to highlight suspicious passages without claiming certainty.

### Implementation Strategy

Do not create a brand-new analysis stack.

Instead reuse:

1. PDF extraction from `upload.py`
2. evidence and review patterns from `research_agent.py`
3. central AI calling from `ai_service.py`

Add one separate scoring layer for AI-writing likelihood:

1. segment the paper into paragraphs or blocks
2. compute heuristic features first
3. optionally run an LLM review pass over only the suspicious blocks
4. merge the result into a final probability map

This should be separate from citation and evidence review so it can be tuned independently.

### Frontend

Add a result panel in `UploadPDF.tsx`:

1. show checker report after upload
2. allow rerun
3. allow export to markdown or docx later
4. highlight flagged passages in extracted text
5. let users click a passage to see why it was flagged

Then add the same capability to `Workspace.tsx`.

### Recommended Detection Method

Do not rely on one AI detector score.

Use a layered approach:

1. stylometric heuristics
   - repetition
   - burstiness variance
   - sentence-length uniformity
   - transition-template density
   - citation-to-claim mismatch

2. section-aware analysis
   - methods sections naturally look more formulaic
   - abstract and conclusion sections need different thresholds

3. LLM-assisted review
   - ask the model to explain why text seems synthetic or overly templated
   - never let the LLM produce the final decision alone

4. calibration set
   - benchmark on known human-written and AI-assisted text
   - tune threshold bands from your own evaluation set

### Output Messaging

Use language like:

1. "This passage shows a high likelihood of AI-assisted writing."
2. "This flag is advisory and may be incorrect."
3. "Review citation grounding and source support before acting on this signal."

Avoid language like:

1. "This paragraph was generated by AI."
2. "This paper is AI-written."
3. "This result proves misconduct."

## Phase 3: Content Access and Coverage

### Metadata Layer

Use legal, stable metadata providers first:

1. OpenAlex for broad scholarly graph coverage
2. Crossref for DOI-centric metadata
3. optional Semantic Scholar only if rate limits and terms fit your product use

### Full-Text Layer

Use:

1. Europe PMC for open biomedical full text
2. PMC Open Access Subset
3. CORE or institutional repository feeds for OA documents

### Licensed Publisher Layer

If you want stronger Q1 and publisher coverage, use licensed APIs:

1. Elsevier
2. Springer Nature
3. any provider whose text and data mining terms explicitly allow your use case

### Journal Tier Layer

If you want real Q1, Q2, Q3, Q4 labels:

1. treat them as journal metrics, not paper metrics
2. source them from licensed journal-metric providers
3. store them as a metadata enrichment layer, not as hard-coded truth

Do not scrape quartiles from random websites. That will create trust and legal problems.

## Phase 4: Bring Your Own Model

### Current State

Your app is Groq-centered today, but it already has a routing structure. That is an advantage.

### Recommended Target Architecture

Move from:

1. single-provider Groq

To:

1. provider abstraction layer
2. task-based model routing
3. hybrid inference:
   - fast external model for general chat
   - your own model for paper checking, longform review, and domain-specific synthesis

### Best Path

1. Start with RAG first
   - retrieval over your papers
   - prompt and template tuning
   - no training yet

2. Then LoRA fine-tune an open model
   - train for checker-style outputs
   - train for citation-aware writing
   - train for research-agent task formatting

3. Serve the model behind an OpenAI-compatible API
   - easiest for backend compatibility
   - keeps existing frontend model settings usable with small extensions

4. Add provider choices in backend:
   - `groq`
   - `self_hosted`
   - optional future providers

### Model Use Cases

Use your own model for:

1. AI Checker
2. Literature review drafting
3. structured evidence extraction
4. citation-grounded writing assistance

Keep generic fast chat on Groq unless your own infra becomes fast and cheap enough.

## Data And Training Plan For Your Own Model

### Training Data Sources

Use only data you have rights to use:

1. your own prompt-response logs if users consent
2. internal evaluation datasets
3. open-access research papers with allowed licenses
4. licensed text-mining corpora if permitted
5. your own structured annotations

### Do Not Train On

1. subscription full text without explicit TDM rights
2. scraped publisher PDFs from random sites
3. user data without consent and policy coverage

### Dataset Design

Create four task datasets:

1. citation formatting examples
2. paper review and checker outputs
3. evidence extraction and claim mapping
4. research writing with explicit source grounding
5. human-written versus AI-assisted passage classification examples

### Evaluation Set

Build a fixed benchmark with:

1. citation correctness
2. hallucination rate
3. evidence-grounding quality
4. section completeness
5. contradiction detection
6. latency and cost
7. AI-writing likelihood precision and false-positive rate
8. paragraph-level calibration accuracy

## Infra Plan

### Short Term

Keep current deployment split:

1. Vercel for frontend
2. Cloud Run for backend

### Medium Term

For self-hosted model serving:

1. GPU endpoint on a separate service
2. OpenAI-compatible serving layer
3. backend provider switch via environment variables

Do not run heavy model inference on the same general-purpose backend instance.

### Operational Needs

1. request tracing
2. model-level analytics
3. prompt versioning
4. evaluation logging
5. budget limits and rate limits

## Security And Compliance Plan

1. separate public metadata from licensed full text
2. keep license flags on every content source
3. mark whether text is storable, cacheable, exportable, and trainable
4. update privacy policy if user prompts or paper uploads contribute to training
5. add admin-only controls for provider routing and model switching

## Rollout Plan

### Release 1

1. single-paper citations
2. citation export
3. AI Checker on uploaded paper text
4. paragraph-level AI-writing likelihood map with disclaimer
5. no model training yet

### Release 2

1. workspace-wide citation tools
2. checker history
3. better metadata enrichment
4. OA full-text expansion

### Release 3

1. provider abstraction
2. self-hosted model pilot
3. routing selected tasks to your own model

### Release 4

1. journal-tier enrichment
2. advanced citation verification
3. benchmark-driven model improvement loop

## Suggested Timeline

### 0 to 2 weeks

1. finalize scope
2. define output schemas
3. add citation service
4. add AI Checker endpoint
5. define AI-writing likelihood schema and review language

### 3 to 5 weeks

1. wire UI in upload and workspace
2. improve metadata enrichment
3. add export flows
4. add internal evaluation dashboards
5. calibrate paragraph-level AI-writing thresholds

### 6 to 10 weeks

1. build provider abstraction
2. prepare training data
3. run first LoRA experiment
4. stand up self-hosted inference

### 10 weeks and beyond

1. license richer sources
2. add Q-tier metadata
3. move task-specific inference to your own model

## Success Metrics

Track:

1. citation copy/export usage
2. citation completeness rate
3. checker rerun rate
4. checker satisfaction and manual correction rate
5. upload-to-result latency
6. hallucination or unsupported-claim rate
7. source coverage across discovered papers
8. cost per successful analysis
9. AI-writing flag acceptance rate
10. AI-writing false-positive complaints

## Risks

1. weak PDF metadata will reduce citation quality
2. AI checker can become too generic without strong templates
3. Q1/Q2 access expectations can exceed what is legally obtainable
4. self-hosting a model adds GPU cost and MLOps complexity
5. training on the wrong data can create licensing exposure
6. AI-writing detection can create false positives and reputation risk if phrased too strongly

## Final Recommendation

The highest-leverage sequence is:

1. ship citations first
2. ship AI Checker second
3. improve metadata and OA coverage third
4. add provider abstraction fourth
5. train and deploy your own model only after you have real product data, evaluation sets, and clear domain tasks

That path improves the product quickly without destabilizing the current architecture.
