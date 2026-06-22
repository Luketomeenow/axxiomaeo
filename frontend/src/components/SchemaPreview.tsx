interface Props {
  schemaJson: string | null | undefined;
  editable?: boolean;
  value?: string;
  onChange?: (value: string) => void;
  parseError?: string | null;
}

function formatSchema(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

export function SchemaPreview({
  schemaJson,
  editable = false,
  value,
  onChange,
  parseError,
}: Props) {
  const display = editable
    ? value ?? ""
    : schemaJson
      ? formatSchema(schemaJson)
      : "No schema generated";

  return (
    <div className="aeo-panel overflow-hidden flex flex-col h-full">
      <div className="px-4 py-3 border-b border-border bg-void flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-ink">Schema JSON-LD</h3>
        {editable && (
          <span className="text-xs text-muted">Edit before approve — saved to this deployment only</span>
        )}
      </div>
      {editable ? (
        <textarea
          className={`aeo-code-editor min-h-[400px] max-h-[600px] flex-1 resize-y border-0 rounded-none ${
            parseError ? "focus:ring-warning/40" : ""
          }`}
          value={display}
          onChange={(e) => onChange?.(e.target.value)}
          spellCheck={false}
        />
      ) : (
        <pre className="aeo-code-block max-h-[600px] flex-1">
          {display}
        </pre>
      )}
      {parseError && (
        <p className="px-4 py-2 text-xs text-warning border-t border-border bg-warning/5">{parseError}</p>
      )}
    </div>
  );
}
