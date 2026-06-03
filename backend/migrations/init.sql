-- Axxiom AEO Platform — Initial Schema

CREATE TABLE IF NOT EXISTS brands (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    wp_url VARCHAR(500) NOT NULL,
    wp_username VARCHAR(100) DEFAULT 'admin',
    markets JSONB DEFAULT '[]',
    is_corporate BOOLEAN DEFAULT FALSE,
    ga4_property_id VARCHAR(100),
    gsc_site_url VARCHAR(500),
    phone VARCHAR(50),
    logo_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS content_pieces (
    id SERIAL PRIMARY KEY,
    brand_id VARCHAR(50) REFERENCES brands(id),
    content_type VARCHAR(50),
    title VARCHAR(500),
    target_query TEXT,
    slug VARCHAR(500),
    wp_post_id INTEGER,
    wp_post_url VARCHAR(500),
    word_count INTEGER,
    schema_types JSONB DEFAULT '[]',
    status VARCHAR(50) DEFAULT 'queued',
    published_at TIMESTAMP,
    last_refreshed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS content_drafts (
    id SERIAL PRIMARY KEY,
    brand_id VARCHAR(50) REFERENCES brands(id),
    content_type VARCHAR(50),
    target_query TEXT,
    title VARCHAR(500),
    slug VARCHAR(500),
    html_content TEXT,
    schema_json TEXT,
    validation_result JSONB,
    validation_attempts INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending_review',
    reviewer_id VARCHAR(100),
    review_notes TEXT,
    queue_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS citation_records (
    id SERIAL PRIMARY KEY,
    brand_id VARCHAR(50) REFERENCES brands(id),
    query TEXT NOT NULL,
    query_category VARCHAR(50),
    platform VARCHAR(50),
    is_cited BOOLEAN,
    competitor_cited VARCHAR(200),
    citation_url VARCHAR(500),
    checked_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS schema_jobs (
    id SERIAL PRIMARY KEY,
    brand_id VARCHAR(50) REFERENCES brands(id),
    wp_post_id INTEGER,
    wp_post_url VARCHAR(500),
    schema_types JSONB DEFAULT '[]',
    validation_status VARCHAR(50) DEFAULT 'pending',
    error_details TEXT,
    deployed_at TIMESTAMP,
    validated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS schema_deployments (
    id SERIAL PRIMARY KEY,
    brand_id VARCHAR(50) REFERENCES brands(id),
    wp_post_id INTEGER,
    wp_post_url VARCHAR(500),
    schema_type VARCHAR(50),
    schema_json TEXT,
    title VARCHAR(500),
    status VARCHAR(50) DEFAULT 'pending_review',
    reviewer_id VARCHAR(100),
    review_notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS monthly_reports (
    id SERIAL PRIMARY KEY,
    report_month DATE,
    overall_citation_share DECIMAL(5,2),
    ai_referred_sessions INTEGER,
    content_pieces_published INTEGER,
    schema_coverage_pct DECIMAL(5,2),
    top_performing_queries JSONB DEFAULT '[]',
    gap_queries JSONB DEFAULT '[]',
    brand_breakdown JSONB DEFAULT '{}',
    full_report_json JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS content_queue (
    id SERIAL PRIMARY KEY,
    brand_id VARCHAR(50) REFERENCES brands(id),
    content_type VARCHAR(50),
    target_query TEXT,
    title VARCHAR(500),
    priority INTEGER DEFAULT 5,
    status VARCHAR(50) DEFAULT 'pending',
    scheduled_for DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS approval_events (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id INTEGER NOT NULL,
    action VARCHAR(50) NOT NULL,
    user_id VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    body TEXT,
    entity_type VARCHAR(50),
    entity_id INTEGER,
    read_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS worker_errors (
    id SERIAL PRIMARY KEY,
    worker_name VARCHAR(100) NOT NULL,
    error_message TEXT,
    error_details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_content_drafts_status ON content_drafts(status);
CREATE INDEX IF NOT EXISTS idx_content_queue_status ON content_queue(status);
CREATE INDEX IF NOT EXISTS idx_citation_records_brand ON citation_records(brand_id);
CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read_at);
CREATE INDEX IF NOT EXISTS idx_schema_deployments_status ON schema_deployments(status);
