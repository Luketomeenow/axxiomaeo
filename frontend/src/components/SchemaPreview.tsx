interface Props {
  schemaJson: string | null | undefined;
}

function formatSchema(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

export function SchemaPreview({ schemaJson }: Props) {
  const formatted = schemaJson ? formatSchema(schemaJson) : "No schema generated";

  return (
    <div className="bg-white rounded border border-black/8 overflow-hidden flex flex-col h-full">
      <div className="px-4 py-3 border-b border-black/8 bg-cream">
        <h3 className="text-sm font-medium text-navy">Schema JSON-LD</h3>
      </div>
      <pre className="p-4 text-xs overflow-auto max-h-[600px] flex-1 bg-gray-50 text-navy font-mono">
        {formatted}
      </pre>
    </div>
  );
}
