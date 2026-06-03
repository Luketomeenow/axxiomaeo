export interface DashboardData {
  citation_share: number;
  citation_share_prev: number;
  citation_trend: number;
  ai_referred_sessions: number;
  content_published_mtd: number;
  schema_coverage_pct: number;
  last_updated: string;
  citation_by_brand: { brand_id: string; citation_share: number }[];
  citation_by_category: { category: string; citation_share: number }[];
  gap_queries: {
    query: string;
    brand_id: string;
    category: string;
    competitor_cited: string;
  }[];
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
  };
  created_at: string;
}

export interface ContentDraftDetail extends ContentDraft {
  html_content: string;
  schema_json: string;
  slug: string;
  review_notes?: string;
}

export interface SchemaDeployment {
  id: number;
  brand_id: string;
  schema_type: string;
  title: string;
  status: string;
  created_at: string;
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
