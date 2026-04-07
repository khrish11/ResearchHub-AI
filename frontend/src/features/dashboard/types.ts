export interface Workspace {
  id: number;
  name: string;
  description?: string;
  created_at?: string;
  paperCount?: number;
}

export interface WorkspacePaper {
  abstract?: string;
}

export interface WorkspaceTemplate {
  name: string;
  description: string;
}

export interface WorkspaceInsightItem {
  text: string;
  source_refs: number[];
}

export interface WorkspaceInsightSource {
  source_index: number;
  source_id: string;
  source_type: string;
  title: string;
  similarity_score: number;
  url?: string;
  doi?: string;
}

export interface WorkspaceInsightsPayload {
  key_themes: WorkspaceInsightItem[];
  emerging_trends: WorkspaceInsightItem[];
  contradictions: WorkspaceInsightItem[];
  important_findings: WorkspaceInsightItem[];
  research_gaps: WorkspaceInsightItem[];
  recommended_next_steps: WorkspaceInsightItem[];
}

export interface WorkspaceInsightsResponse {
  status: string;
  workspace_id: number;
  insight_id?: string | null;
  confidence: number;
  disclaimer: string;
  generated_at?: string | null;
  expires_at?: string | null;
  sources: WorkspaceInsightSource[];
  payload: WorkspaceInsightsPayload;
  job_id?: string | null;
  job_status?: string | null;
  error?: string | null;
}

export interface WorkspaceFeedSource {
  source_index: number;
  source_id: string;
  source_type: string;
  title: string;
  url?: string;
  doi?: string;
  paper_id?: number;
  similarity_score?: number;
}

export interface WorkspaceFeedItem {
  feed_item_id: string;
  type: 'trend' | 'contradiction' | 'recommendation' | string;
  title: string;
  description: string;
  related_papers: number[];
  importance_score: number;
  created_at?: string | null;
  updated_at?: string | null;
  read: boolean;
  read_at?: string | null;
  source_refs: number[];
  sources: WorkspaceFeedSource[];
}

export interface WorkspaceFeedResponse {
  status: string;
  workspace_id: number;
  disclaimer: string;
  items: WorkspaceFeedItem[];
  next_cursor?: string | null;
  total_count: number;
  unread_count: number;
  job_id?: string | null;
  job_status?: string | null;
  error?: string | null;
}

export interface OnboardingStep {
  id: string;
  title: string;
  description: string;
  action_label: string;
  action_path: string;
  completed: boolean;
}

export interface OnboardingDemoSamplePaper {
  title: string;
  authors: string;
}

export interface OnboardingDemoFeedPreview {
  type: string;
  title: string;
  description: string;
  importance_score: number;
}

export interface OnboardingDemoState {
  available: boolean;
  seeded: boolean;
  seeded_at?: string | null;
  paper_ids: number[];
  sample_papers: OnboardingDemoSamplePaper[];
  sample_comparison: {
    title: string;
    description: string;
  };
  sample_report: {
    title: string;
    description: string;
  };
  sample_feed_items: OnboardingDemoFeedPreview[];
}

export interface OnboardingStatusResponse {
  workspace_id: number;
  workspace_name: string;
  paper_count: number;
  has_completed_onboarding: boolean;
  dismissed: boolean;
  needs_onboarding: boolean;
  progress: number;
  completed_steps: string[];
  steps: OnboardingStep[];
  copilot_prompts: string[];
  demo: OnboardingDemoState;
}

export interface DemoModeStep {
  id: string;
  index: number;
  title: string;
  what_happening: string;
  why_matters: string;
  action_label: string;
  action_path: string;
  target_key: string;
  tooltip: string;
  completed: boolean;
  active: boolean;
}

export interface DemoModeStateResponse {
  is_demo_mode: boolean;
  workspace_id: number;
  workspace_name: string;
  scenario_title: string;
  story_intro: string;
  progress: number;
  current_step?: string | null;
  completed_steps: string[];
  steps: DemoModeStep[];
  demo_seeded: boolean;
  demo_seeded_at?: string | null;
  paper_count: number;
  comparison_id?: string | null;
  report_id?: string | null;
  insight_id?: string | null;
  started_at?: string | null;
  exited_at?: string | null;
  bootstrap?: Record<string, unknown> | null;
}
