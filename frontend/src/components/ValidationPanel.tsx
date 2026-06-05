interface ValidationResult {
  valid?: boolean;
  reason?: string;
  word_count?: number;
  h2_question_ratio?: number;
  h2_questions?: number;
  h2_total?: number;
  schema_types?: string[];
}

interface Props {
  validationResult?: ValidationResult | null;
  validationAttempts?: number;
  targetQuery?: string;
}

const MIN_WORDS = 200;
const MIN_H2_QUESTION_RATIO = 0.6;

const WEAK_OPENERS = [
  "great question",
  "it depends",
  "there are many factors",
  "that's a great",
  "excellent question",
  "well,",
  "in short,",
];

function checkAnswerFirst(reason: string | undefined, valid: boolean | undefined): boolean {
  if (reason?.toLowerCase().includes("weak phrase")) return false;
  if (valid) return true;
  if (reason?.toLowerCase().includes("h2") || reason?.toLowerCase().includes("short")) return true;
  return false;
}

function checkWordCount(wordCount: number | undefined): boolean {
  return (wordCount ?? 0) >= MIN_WORDS;
}

function checkH2Questions(
  ratio: number | undefined,
  total: number | undefined
): boolean | null {
  if (total === undefined || total === 0) return null;
  return (ratio ?? 0) >= MIN_H2_QUESTION_RATIO;
}

export function ValidationPanel({ validationResult, validationAttempts, targetQuery }: Props) {
  if (!validationResult) {
    return (
      <div className="bg-white border border-black/8 rounded px-4 py-3 text-sm text-black/50">
        No validation data for this draft.
      </div>
    );
  }

  const {
    valid,
    reason,
    word_count: wordCount,
    h2_question_ratio: h2Ratio,
    h2_questions: h2Questions,
    h2_total: h2Total,
    schema_types: schemaTypes,
  } = validationResult;

  const answerFirstOk = checkAnswerFirst(reason, valid);
  const wordCountOk = checkWordCount(wordCount);
  const h2Ok = checkH2Questions(h2Ratio, h2Total);

  const checks: {
    label: string;
    rule: string;
    passed: boolean | null;
    detail: string;
  }[] = [
    {
      label: "Answer-first opening",
      rule: `First ~100 words must not use filler openers (${WEAK_OPENERS.slice(0, 3).join(", ")}, …). Content should lead with a direct answer.`,
      passed: answerFirstOk,
      detail: answerFirstOk
        ? "Opening reads as a direct answer."
        : reason?.includes("weak phrase")
          ? reason
          : "Failed answer-first check.",
    },
    {
      label: "Minimum length",
      rule: `At least ${MIN_WORDS} words of body text (HTML stripped).`,
      passed: wordCountOk,
      detail: `${(wordCount ?? 0).toLocaleString()} words`,
    },
    {
      label: "H2 headings as questions",
      rule:
        h2Total && h2Total > 0
          ? `At least ${MIN_H2_QUESTION_RATIO * 100}% of <h2> tags must end with "?" (AEO FAQ structure).`
          : "If the page uses <h2> headings, at least 60% should be phrased as questions.",
      passed: h2Ok,
      detail:
        h2Total && h2Total > 0
          ? `${h2Questions}/${h2Total} H2s are questions (${Math.round((h2Ratio ?? 0) * 100)}%) — need ≥60%`
          : "No H2 tags found — check skipped.",
    },
    {
      label: "JSON-LD schema",
      rule: "FAQPage and/or Article schema is generated from the HTML for WordPress publish.",
      passed: (schemaTypes?.length ?? 0) > 0,
      detail: schemaTypes?.length
        ? `Types: ${schemaTypes.join(", ")}`
        : "No schema types recorded.",
    },
  ];

  return (
    <div className="bg-white border border-black/8 rounded overflow-hidden">
      <div className="px-4 py-3 border-b border-black/8 bg-cream flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-medium text-navy">AEO validation</h3>
          <p className="text-xs text-black/45 mt-0.5">
            Automated checks after Claude generation
            {validationAttempts ? ` · ${validationAttempts} attempt(s)` : ""}
          </p>
        </div>
        <span
          className={`text-xs font-semibold px-2.5 py-1 rounded ${
            valid ? "bg-green-100 text-green-800" : "bg-orange/10 text-orange"
          }`}
        >
          {valid ? "All checks passed" : "Needs review"}
        </span>
      </div>

      {targetQuery && (
        <div className="px-4 py-2 border-b border-black/5 text-xs text-black/50 bg-black/[0.02]">
          <span className="font-medium text-black/60">Target query:</span> {targetQuery}
        </div>
      )}

      <ul className="divide-y divide-black/5">
        {checks.map((check) => (
          <li key={check.label} className="px-4 py-3 text-sm">
            <div className="flex items-start gap-3">
              <StatusIcon passed={check.passed} />
              <div className="min-w-0 flex-1">
                <p className="font-medium text-navy">{check.label}</p>
                <p className="text-xs text-black/45 mt-0.5">{check.rule}</p>
                <p
                  className={`text-xs mt-1.5 ${
                    check.passed === false
                      ? "text-orange"
                      : check.passed === true
                        ? "text-green-700"
                        : "text-black/50"
                  }`}
                >
                  {check.detail}
                </p>
              </div>
            </div>
          </li>
        ))}
      </ul>

      {!valid && reason && (
        <div className="px-4 py-3 border-t border-orange/20 bg-orange/5 text-xs text-orange">
          <span className="font-medium">Failure reason:</span> {reason}
          {validationAttempts && validationAttempts >= 2
            ? " Claude was asked to correct this once; draft was kept for manual review."
            : ""}
        </div>
      )}
    </div>
  );
}

function StatusIcon({ passed }: { passed: boolean | null }) {
  if (passed === true) {
    return (
      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-green-100 text-green-700 text-xs font-bold">
        ✓
      </span>
    );
  }
  if (passed === false) {
    return (
      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-orange/15 text-orange text-xs font-bold">
        !
      </span>
    );
  }
  return (
    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-black/5 text-black/40 text-xs">
      —
    </span>
  );
}
