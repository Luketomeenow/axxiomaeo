SCHEMA_ENHANCEMENT_PROMPT = """
Given the following HTML content for an elevator service page, suggest additional schema.org properties
that would improve AI citation rates. Return only valid JSON-LD without script tags.

Brand: {brand_name}
Content type: {content_type}
URL: {url}
"""
