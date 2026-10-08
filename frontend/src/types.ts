export interface DashboardData {
  citation_share: number;
  citation_share_prev: number;
  citation_trend: number;
  avg_visibility_pct?: number;
  share_of_voice?: number;
  topic_coverage_pct?: number;
  platform_consensus_pct?: number;
  ai_referred_sessions: number;
  ai_referred_conversions?: number;
  ai_conversion_rate?: number;
  content_published_mtd: number;
  schema_coverage_pct: number;
  last_updated: string;
  citation_by_brand: {
    brand_id: string;
    citation_share: number;
    cited_queries?: number;
    total_queries?: number;
  }[];
  citation_by_category: {
    category: string;
    citation_share: number;
    cited_queries?: number;
    total_queries?: number;
  }[];
  citation_by_funnel?: { funnel_stage: string; citation_share: number; avg_visibility_pct: number }[];
  visibility_by_platform?: {
    platform: string;
    citation_share: number;
    avg_visibility_pct: number;
    total_checks: number;
  }[];
  topic_coverage?: {
    total_categories: number;
    cited_categories: number;
    coverage_pct: number;
    categories: string[];
  };
  gap_queries: {
    id?: number;
    query: string;
    brand_id: string;
    category: string;
    competitor_cited: string;
    platform?: string;
    visibility_pct?: number;
    is_mentioned?: boolean;
    is_url_cited?: boolean;
    recommended_content_type?: string;
    invisible?: boolean;
  }[];
  gsc_highlights?: {
    configured: boolean;
    brands: {
      brand_id: string;
      brand_name: string;
      site_url: string;
      queries: {
        query: string;
        clicks: number;
        impressions: number;
        position: number;
        has_featured_snippet: boolean;
      }[];
    }[];
    message?: string;
  };
}

export interface TrafficTrendResponse {
  configured: boolean;
  reason?: "no_ga4" | "no_credentials";
  brands: {
    brand_id: string;
    brand_name: string;
    data: { date: string; sessions: number }[];
    ai_data?: { date: string; sessions: number }[];
    organic_data?: { date: string; sessions: number }[];
  }[];
}

export interface SearchVsGenerative {
  search: {
    configured: boolean;
    visibility: { impressions: number; clicks: number; avg_position: number };
    traffic: {
      organic_search_sessions: number;
      conversions?: number;
      conversion_rate?: number;
    };
  };
  generative: {
    configured: boolean;
    visibility: {
      citation_share: number;
      avg_visibility_pct: number;
      share_of_voice: number;
    };
    traffic: {
      ai_referred_sessions: number;
      conversions?: number;
      conversion_rate?: number;
    };
  };
  last_updated: string;
}

export interface Brand {
  id: string;
  name: string;
  wp_url: string;
  markets: string[];
  is_corporate: boolean;
  phone?: string;
  ga4_property_id?: string;
  gsc_site_url?: string;
  logo_url?: string;
  target_queries?: string[];
  service_page_urls?: Record<string, string>;
  topic_boost?: number;
  wp_publish_configured?: boolean;
}

export interface ContentDraft {
  id: number;
  brand_id: string;
  content_type: string;
  title: string;
  target_query: string;
  status: string;
  priority?: number | null;
  validation_result?: {
    valid: boolean;
    reason: string;
    word_count?: number;
    h2_question_ratio?: number;
    h2_questions?: number;
    h2_total?: number;
    schema_types?: string[];
    images_status?: string;
    image_count?: number;
    images_with_alt?: number;
  };
  validation_attempts?: number;
  created_at: string;
}

export interface ContentDraftImage {
  slot: string;
  wp_media_id?: number;
  url: string;
  alt: string;
  title?: string;
  caption: string;
  prompt?: string;
}

export interface ContentDraftDetail extends ContentDraft {
  html_content: string | null;
  schema_json: string | null;
  slug: string;
  review_notes?: string;
  images_json?: ContentDraftImage[];
  featured_media_id?: number | null;
}

export interface PublishResult {
  brand_id: string;
  post_id: number | null;
  post_url: string | null;
  error: string | null;
}

export interface ApprovePublishResponse {
  status: string;
  published_count: number;
  post_id?: number;
  post_url?: string;
  results: PublishResult[];
  skipped?: PublishResult[];
}

export interface SchemaDeployment {
  id: number;
  brand_id: string;
  schema_type: string;
  title: string;
  status: string;
  created_at: string;
  wp_post_url?: string | null;
}

export interface PublishedSchema {
  id: number;
  source: "brand_schema" | "content";
  brand_id: string;
  title: string | null;
  schema_type: string | null;
  schema_types: string[];
  wp_post_url: string | null;
  published_at: string | null;
  has_schema_json: boolean;
}

export interface PublishedSchemaDetail extends PublishedSchema {
  schema_json: string | null;
  wp_post_id: number | null;
}

export interface Notification {
  id: number;
  type: string;
  title: string;
  body: string;
  entity_type?: string;
  entity_id?: number;
  read_at?: string;
  created_at: string;
}

export interface ContentQueueItem {
  id: number;
  brand_id: string;
  content_type: string;
  title: string;
  target_query: string;
  priority: number;
  status: string;
  scheduled_for?: string;
  source?: string | null;
  source_detail?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface Recommendation {
  key: string;
  brand_id: string;
  brand_name: string;
  query: string;
  title: string;
  content_type: string;
  priority: number;
  score: number;
  competitor_cited: boolean;
  competitors: string[];
  engines_missing: string[];
  visibility_pct: number;
  why: string;
  source_detail?: Record<string, unknown> | null;
  source_citation_id?: number | null;
}

export interface RecommendationsResponse {
  recommendations: Recommendation[];
  count: number;
}

export interface CitationInsights {
  status: "ok" | "no_data";
  message?: string;
  cached?: boolean;
  audit_run_id?: string;
  data_summary?: {
    total_checks: number;
    cited: number;
    citation_share_pct: number;
    avg_visibility_pct: number;
    top_competitors: { name: string; wins: number }[];
  };
  summary?: string;
  strengths?: string[];
  weaknesses?: string[];
  platform_insights?: { platform: string; insight: string }[];
  competitor_threats?: { competitor: string; detail: string }[];
  recommendations?: {
    title: string;
    detail: string;
    priority: string;
    category: string;
  }[];
}

export interface PublishedContent {
  id: number;
  brand_id: string;
  content_type: string | null;
  title: string | null;
  target_query: string | null;
  slug: string | null;
  wp_post_id: number | null;
  wp_post_url: string | null;
  word_count: number | null;
  schema_types: string[];
  published_at: string | null;
  last_refreshed_at: string | null;
}

export interface ReportListItem {
  id: number;
  report_month: string | null;
  overall_citation_share: number;
  ai_referred_sessions: number | null;
  ai_referred_conversions?: number | null;
  aeo_attributed_calls?: number | null;
  content_pieces_published: number | null;
  schema_coverage_pct: number;
  created_at: string | null;
}

export interface ReportsListResponse {
  total: number;
  reports: ReportListItem[];
}

export interface MonthlyReportDetail {
  id?: number;
  message?: string;
  report_month?: string | null;
  overall_citation_share?: number;
  ai_referred_sessions?: number | null;
  ai_referred_conversions?: number | null;
  aeo_attributed_calls?: number | null;
  content_pieces_published?: number | null;
  schema_coverage_pct?: number;
  created_at?: string | null;
  top_performing_queries?: {
    query: string;
    brand_id?: string;
    platform?: string;
    citation_url?: string;
  }[];
  gap_queries?: {
    query: string;
    brand_id?: string;
    competitor_cited?: string;
    platform?: string;
  }[];
  brand_breakdown?: Record<
    string,
    {
      brand_id?: string;
      citation_share?: number;
      cited_queries?: number;
      total_queries?: number;
    }
  >;
  full_report_json?: {
    citation_share?: number;
    avg_visibility_pct?: number;
    share_of_voice?: number;
    topic_coverage_pct?: number;
    content_published_mtd?: number;
    by_category?: {
      category?: string;
      citation_share: number;
      cited_queries?: number;
      total_queries?: number;
    }[];
    by_platform?: { platform?: string; citation_share: number }[];
    by_funnel?: { funnel_stage?: string; citation_share: number }[];
    [key: string]: unknown;
  };
}

export interface ReportSummary {
  status: "ok" | "no_data";
  message?: string;
  cached?: boolean;
  summary?: string;
  highlights?: string[];
  watch_outs?: string[];
  next_steps?: string[];
}

export interface CostSummary {
  period_month: string;
  source?: "ledger" | "estimate";
  estimated: boolean;
  total_usd: number;
  items: {
    key: string;
    label: string;
    cost_usd: number;
    unit?: string;
    units?: number;
    calls?: number;
    input_tokens?: number;
    output_tokens?: number;
    actual?: boolean;
  }[];
}

export interface FlowStage {
  key: string;
  label: string;
  status: "ok" | "warn" | "fail";
  detail: string;
  metrics: {
    gsc_credential?: boolean;
    citation_provider?: boolean;
    discord_webhook?: boolean;
    wordpress?: {
      brand_id: string;
      ok: boolean;
      status_code?: number | null;
      error?: string | null;
      cached?: boolean;
    }[];
    queued_today?: number;
    by_source?: Record<string, number>;
    job_ran?: boolean;
    drafts_today?: number;
    stuck_in_progress?: number;
    stranded?: {
      queue_id: number;
      draft_id: number;
      brand_id: string;
      title?: string | null;
      age_days?: number | null;
    }[];
    published_today?: number;
    by_brand?: Record<string, number>;
    silent_brands?: string[];
    last_24h?: number;
    by_worker?: {
      worker_name: string;
      count: number;
      latest_message?: string;
      latest_at?: string | null;
    }[];
  };
}

export interface FlowHealth {
  checked_at: string;
  overall: "ok" | "warn" | "fail";
  stages: FlowStage[];
}

export interface WorkerErrorItem {
  id: number;
  worker_name: string;
  error_message?: string | null;
  error_details?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface WpTestResult {
  ok: boolean;
  status_code?: number | null;
  error?: string | null;
  checked_at?: string;
}

export interface PhoneCheck {
  checked: boolean;
  reason?: string;
  tracking_number?: boolean;
  website_pool?: boolean;
  trackers?: { tracker: string; company: string; calls: number }[];
}

export interface CtaRefreshResult {
  brand_id: string;
  phone?: string | null;
  contact_url?: string | null;
  published_posts: number;
  posts_to_update: number;
  posts_without_stored_html: number;
  old_numbers: Record<string, number>;
  samples: { title?: string | null; url?: string | null; replaced: string[] }[];
  applied: boolean;
  updated: number;
  remaining: number;
  errors: { title?: string | null; error: string }[];
}

export interface AdvisorImprovement {
  title: string;
  why: string;
  category: string;
  priority: string;
  brand_id?: string | null;
  effort: string;
}

export interface AdvisorReportPayload {
  id: number;
  created_at: string | null;
  trigger: string;
  summary?: string;
  improvements?: AdvisorImprovement[];
  quick_wins?: string[];
  data_summary?: {
    citation_share?: number | null;
    brands_posting_7d?: number;
    flow_overall?: string;
  };
}

export interface AdvisorResponse {
  status: "ok" | "no_data" | "error";
  cached?: boolean;
  message?: string;
  report?: AdvisorReportPayload;
}

export interface OptimizerEvidence {
  label: string;
  value: string;
  source: string;
  verified?: boolean;
}

export interface OptimizerProposal {
  id: number;
  trigger: string;
  title: string;
  category: string;
  priority: string;
  brand_id?: string | null;
  change_type: "code" | "manual" | string;
  problem?: string | null;
  proposed_change?: string | null;
  instructions?: string | null;
  acceptance?: string | null;
  expected_impact?: string | null;
  risk?: string | null;
  evidence: OptimizerEvidence[];
  files_hint: string[];
  status: string;
  decided_at?: string | null;
  decided_by?: string | null;
  decision_note?: string | null;
  dispatched_at?: string | null;
  branch?: string | null;
  run_url?: string | null;
  pr_number?: number | null;
  pr_url?: string | null;
  error?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface OptimizerStatus {
  enabled: boolean;
  github_configured: boolean;
  workflow_registered: boolean | null;
  github_error?: string | null;
  repo: string;
  workflow: string;
  base_branch: string;
  last_proposal_at?: string | null;
  counts: Record<string, number>;
}

export interface OptimizerRunResult {
  status: "ok" | "error";
  message?: string;
  summary?: string;
  created?: OptimizerProposal[];
  skipped_duplicates?: number;
  dropped_ungrounded?: number;
}

export interface CustomerQuestion {
  id: number;
  brand_id: string;
  question: string;
  source?: string | null;
  asked_at?: string | null;
  created_at?: string | null;
  intent?: string | null;
  call_source?: string | null;
  topic?: { queue_id: number; status: string } | null;
}

export interface CallQuestionScanResult {
  status: "ok" | "unavailable";
  message?: string;
  calls_with_summary?: number;
  not_an_aeo_brand?: number;
  already_scanned?: number;
  calls_scanned?: number;
  questions_found?: number;
  out_of_market?: number;
  stored?: number;
  duplicates?: number;
}
