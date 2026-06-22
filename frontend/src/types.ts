export interface DashboardData {
  citation_share: number;
  citation_share_prev: number;
  citation_trend: number;
  avg_visibility_pct?: number;
  share_of_voice?: number;
  topic_coverage_pct?: number;
  platform_consensus_pct?: number;
  ai_referred_sessions: number;
  content_published_mtd: number;
  schema_coverage_pct: number;
  last_updated: string;
  citation_by_brand: { brand_id: string; citation_share: number }[];
  citation_by_category: { category: string; citation_share: number }[];
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
  }[];
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
