interface ValidationResult {
  valid?: boolean;
  reason?: string;
  word_count?: number;
  h2_question_ratio?: number;
  h2_questions?: number;
  h2_total?: number;
}

interface Props {
  html?: string | null;
  validationResult?: ValidationResult;
}

const PREVIEW_CSS = `
.content-preview-body {
  font-family: Inter, system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.65;
  color: #0f0f0d;
}
.content-preview-body h1 { font-size: 1.75rem; font-weight: 700; color: #1a3a5c; margin-bottom: 1rem; }
.content-preview-body h2 { font-size: 1.25rem; font-weight: 600; color: #1a3a5c; margin: 1.5rem 0 0.5rem; }
.content-preview-body h3 { font-size: 1rem; font-weight: 600; margin: 1rem 0 0.5rem; }
.content-preview-body p { margin-bottom: 0.75rem; }
.content-preview-body table { border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: 13px; }
.content-preview-body th, .content-preview-body td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
.content-preview-body th { background: #f5f3ee; font-weight: 600; }
.content-preview-body ul, .content-preview-body ol { margin: 0.5rem 0 1rem 1.25rem; }
`;

export function ContentPreview({ html, validationResult }: Props) {
  const wordCount = validationResult?.word_count;
  const h2Ratio = validationResult?.h2_question_ratio;
  const h2Questions = validationResult?.h2_questions;
  const h2Total = validationResult?.h2_total;

  const hasHtml = Boolean(html?.trim());
  const bodyHtml = hasHtml
    ? html!
    : "<p>No HTML content yet. If you just clicked Generate, wait 1–2 minutes and refresh this page.</p>";

  return (
    <div className="bg-white rounded border border-black/8 overflow-hidden flex flex-col">
      <div className="px-4 py-3 border-b border-black/8 bg-cream flex items-center justify-between gap-2 flex-wrap">
        <h3 className="text-sm font-medium text-navy">Content Preview</h3>
        <div className="flex gap-2 flex-wrap">
          {wordCount !== undefined && (
            <span className="text-xs bg-navy/10 text-navy px-2 py-0.5 rounded">
              {wordCount.toLocaleString()} words
            </span>
          )}
          {h2Ratio !== undefined && h2Total !== undefined && h2Total > 0 && (
            <span
              className={`text-xs px-2 py-0.5 rounded ${
                h2Ratio >= 0.6 ? "bg-green-100 text-green-800" : "bg-orange/10 text-orange"
              }`}
            >
              H2 questions: {h2Questions}/{h2Total} ({Math.round(h2Ratio * 100)}%)
            </span>
          )}
        </div>
      </div>
      <style>{PREVIEW_CSS}</style>
      <div
        className="content-preview-body p-4 overflow-auto min-h-[400px] max-h-[600px] bg-white"
        dangerouslySetInnerHTML={{ __html: bodyHtml }}
      />
    </div>
  );
}
