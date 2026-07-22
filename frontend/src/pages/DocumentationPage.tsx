import { useEffect, useState } from "react";
import type { MouseEvent, ReactNode } from "react";

const SECTIONS = [
  { id: "overview", label: "Overview" },
  { id: "how", label: "How it works" },
  { id: "dashboard", label: "The dashboard" },
  { id: "content", label: "Content engine" },
  { id: "guardrails", label: "Content guardrails" },
  { id: "schema", label: "Schema (structured data)" },
  { id: "tracking", label: "Citation tracking" },
  { id: "recommendations", label: "Recommendations" },
  { id: "reports", label: "Reports & costs" },
  { id: "providers", label: "AI providers" },
  { id: "config", label: "Configuration" },
  { id: "operations", label: "Operations" },
];

function Code({ children }: { children: ReactNode }) {
  return (
    <code className="font-mono text-[0.85em] text-cyan bg-cyan/10 border border-cyan/20 rounded px-1.5 py-0.5 whitespace-nowrap">
      {children}
    </code>
  );
}

function Em({ children }: { children: ReactNode }) {
  return <strong className="font-semibold text-ink">{children}</strong>;
}

function Chip({ tone = "opt", children }: { tone?: "live" | "opt" | "gate"; children: ReactNode }) {
  const map = {
    live: "text-success border-success/40 bg-success/10",
    opt: "text-muted border-border-strong",
    gate: "text-warning border-warning/40 bg-warning/10",
  } as const;
  return (
    <span
      className={`font-mono text-[10px] font-medium px-2 py-0.5 rounded-full border align-middle ${map[tone]}`}
    >
      {children}
    </span>
  );
}

function Callout({ tone = "info", tag, children }: { tone?: "info" | "warn"; tag: string; children: ReactNode }) {
  const box =
    tone === "warn"
      ? "border-warning/30 border-l-warning bg-warning/[0.06]"
      : "border-cyan/25 border-l-cyan bg-cyan/[0.06]";
  const tagColor = tone === "warn" ? "text-warning" : "text-cyan";
  return (
    <div className={`max-w-[68ch] rounded-md border border-l-4 p-4 text-sm ${box}`}>
      <span className={`block font-mono text-[10px] uppercase tracking-[0.14em] mb-1.5 ${tagColor}`}>{tag}</span>
      <p className="text-ink/90 leading-relaxed m-0">{children}</p>
    </div>
  );
}

function Card({ k, title, children }: { k?: string; title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-panel p-4">
      {k && (
        <span className="block font-mono text-[10px] uppercase tracking-[0.12em] text-muted mb-2">{k}</span>
      )}
      <h3 className="text-[14px] font-semibold text-ink mb-1.5">{title}</h3>
      <p className="text-[13px] text-muted leading-relaxed m-0">{children}</p>
    </div>
  );
}

function Section({ id, eyebrow, title, children }: { id: string; eyebrow: string; title: ReactNode; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-4 border-t border-border pt-10 first:border-t-0 first:pt-0">
      <span className="block font-mono text-[11px] uppercase tracking-[0.18em] text-cyan mb-2.5">{eyebrow}</span>
      <h2 className="text-xl font-semibold text-ink tracking-tight text-balance mb-3">{title}</h2>
      {children}
    </section>
  );
}

function P({ children }: { children: ReactNode }) {
  return <p className="text-sm text-muted leading-7 max-w-[68ch] mb-3.5">{children}</p>;
}

function H3({ children }: { children: ReactNode }) {
  return <h3 className="text-[15px] font-semibold text-ink mt-6 mb-2">{children}</h3>;
}

function List({ children }: { children: ReactNode }) {
  return (
    <ul className="text-sm text-muted leading-7 max-w-[68ch] mb-3.5 list-disc pl-5 marker:text-muted/50 space-y-1">
      {children}
    </ul>
  );
}

function Th({ children }: { children: ReactNode }) {
  return (
    <th className="text-left font-mono text-[10px] font-medium uppercase tracking-wider text-muted px-3.5 py-2.5">
      {children}
    </th>
  );
}

function Table({ head, children }: { head: ReactNode; children: ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border mb-4 max-w-[68ch]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-white/[0.02]">{head}</tr>
        </thead>
        <tbody className="divide-y divide-border">{children}</tbody>
      </table>
    </div>
  );
}

const STEPS: { title: string; body: ReactNode }[] = [
  {
    title: "Pick a topic",
    body: (
      <>
        Mines two signals — rising search demand (Google Search Console) and AI-visibility gaps (queries
        where a brand is ignored or a competitor is cited) — and chooses the most valuable one per brand.
      </>
    ),
  },
  {
    title: "Write the draft",
    body: (
      <>
        Claude generates a full article formatted to answer the question directly, with photorealistic
        images and a team byline — written under hard truthfulness rules (no invented authors,
        credentials, claims, or statistics; see Content guardrails).
      </>
    ),
  },
  {
    title: "Quality-check",
    body: (
      <>
        Validates that it answers the query and is long enough, carries valid structured-data markup and
        image alt text — and verifies every link: external links are probed against the live web (dead
        ones re-pointed to a working authority page or unlinked) and internal links are checked against
        the brand's real published pages.
      </>
    ),
  },
  {
    title: "Publish & announce",
    body: (
      <>
        Publishes to the brand's WordPress site once it passes, then posts the live link to a Discord
        channel so the team can monitor what went out.
      </>
    ),
  },
  {
    title: "Measure",
    body: (
      <>
        On a schedule, asks the AI engines real customer questions and records whether each brand is
        mentioned, cited with a link, or beaten by a named competitor.
      </>
    ),
  },
  {
    title: "Recommend the next move",
    body: (
      <>
        From that tracking, ranks "you're invisible here and a competitor is winning — publish this" for a
        human to approve. Approving generates a draft that waits in Content Review — recommendation
        drafts never publish without sign-off.
      </>
    ),
  },
];

export function DocumentationPage() {
  const [active, setActive] = useState<string>("overview");

  useEffect(() => {
    const els = SECTIONS.map((s) => document.getElementById(s.id)).filter((el): el is HTMLElement => Boolean(el));
    if (!("IntersectionObserver" in window) || els.length === 0) return;
    const visible = new Set<string>();
    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) visible.add(e.target.id);
          else visible.delete(e.target.id);
        }
        const first = SECTIONS.find((s) => visible.has(s.id));
        if (first) setActive(first.id);
      },
      { rootMargin: "-10% 0px -70% 0px", threshold: 0 }
    );
    els.forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, []);

  const jump = (e: MouseEvent, id: string) => {
    e.preventDefault();
    const el = document.getElementById(id);
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    setActive(id);
  };

  return (
    <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_220px] lg:gap-12 max-w-6xl">
      <main className="min-w-0 space-y-0">
        {/* Intro / overview */}
        <Section
          id="overview"
          eyebrow="Overview"
          title="The system that keeps Axxiom's brands visible to AI answer engines"
        >
          <p className="text-base text-muted leading-relaxed max-w-[68ch] mb-4">
            Axxiom Elevator runs a network of brand sites —{" "}
            <Em>Axxiom Elevator Florida, AmeriTex, Arizona Elevator Solutions, Liftech, and Quality Elevator</Em>.
            This platform automatically writes and publishes content for those sites, and measures whether
            ChatGPT, Gemini, and Perplexity actually cite the brands when people ask elevator questions.
          </p>
          <P>
            It's <Em>Answer Engine Optimization (AEO)</Em> — the same idea as SEO, but for AI assistants
            instead of Google. When someone asks an AI "who does emergency elevator repair in Pompano
            Beach?", the goal is that one of these five brands is the answer, not a competitor.
          </P>
          <div className="grid sm:grid-cols-3 gap-3.5 mt-5">
            <Card k="Writes" title="Content, daily">
              AI-written articles — up to 4 per brand per day — from real search demand and citation gaps.
            </Card>
            <Card k="Measures" title="AI visibility">
              Asks the engines real questions; records who's cited and who loses to a competitor.
            </Card>
            <Card k="Acts" title="Recommendations">
              Turns gaps into "publish this next" — approved in one click.
            </Card>
          </div>
        </Section>

        {/* How it works */}
        <Section id="how" eyebrow="How it works" title="The daily loop, start to finish">
          <P>
            Every day the platform runs this cycle on its own. A human monitors it rather than driving each
            step.
          </P>
          <ol className="mt-1 mb-4">
            {STEPS.map((s, i) => (
              <li
                key={s.title}
                className="grid grid-cols-[36px_1fr] gap-4 py-3.5 border-t border-border first:border-t-0"
              >
                <span className="font-mono text-[13px] text-cyan pt-0.5 tabular-nums">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div>
                  <h3 className="text-[15px] font-semibold text-ink mb-1">{s.title}</h3>
                  <p className="text-sm text-muted leading-relaxed m-0">{s.body}</p>
                </div>
              </li>
            ))}
          </ol>
          <Callout tone="info" tag="Human oversight">
            Publishing is automatic (monitor-after), but the human stays in control at the strategy layer —
            approving <em>what</em> to work on in the Recommendations inbox, approving schema changes, and via
            a kill switch (<Code>AUTO_PUBLISH_ENABLED=false</Code>) that restores approve-before-publish for
            every draft.
          </Callout>
        </Section>

        {/* Dashboard */}
        <Section id="dashboard" eyebrow="The dashboard" title="What the team sees">
          <P>A React dashboard (Netlify), grouped into what to watch, what to act on, and what to review.</P>
          <div className="grid sm:grid-cols-2 gap-3.5">
            <Card title="Dashboard">
              Headline scorecard — citation share, AI visibility, share of voice vs competitors,
              AI-referred sessions, and AI conversions (GA4 key events from AI visitors).
            </Card>
            <Card title="Recommendations">
              Ranked "what to do next," each explaining why; one <Em>Approve</Em> queues the topic, writes
              the draft, and hands it to Content Review for your sign-off.
            </Card>
            <Card title="Citations">
              The AI-visibility monitor — who's cited on which engine, for which questions, and who beats
              them. Browse the latest audit, any past audit, all history, or a date range; the platform
              chart breaks citation share down per brand per engine. Includes an{" "}
              <Em>AI Recommendations</Em> tab that reads the whole audit.
            </Card>
            <Card title="Reports">
              Monthly snapshots with month-over-month trends, AI conversions, an AI executive summary,
              estimated/actual API costs, and CSV / print export.
            </Card>
            <Card title="Content Review & Published">
              Every draft and everything that's gone live — searchable and sortable; regenerate, edit, or
              reject before it publishes, or pull a live post back to review.
            </Card>
            <Card title="Schema & Brand Settings">
              The structured data that makes pages machine-readable (human-approved), plus per-brand config
              and authors.
            </Card>
          </div>
        </Section>

        {/* Content engine */}
        <Section id="content" eyebrow="Content engine" title="From demand signal to published article">
          <P>
            Topic discovery mines Search Console demand, citation gaps, and coverage gaps into a per-brand
            queue. The daily worker generates up to <Em>4 drafts per brand per day</Em>{" "}
            (<Code>CONTENT_GENERATION_MAX_PER_BRAND</Code>), validates each, and — under the monitor-after
            model — publishes automatically once a draft passes.
          </P>
          <H3>What makes a good AEO article here</H3>
          <List>
            <li>
              <Em>Answer-first structure</Em> — a direct answer up top, question-shaped H2s, and enough depth
              for the query.
            </li>
            <li>
              <Em>Structured data</Em> — FAQ / LocalBusiness / Article schema so engines understand the page.
            </li>
            <li>
              <Em>Honest authorship</Em> — every post is bylined <em>"By the [Brand] Team"</em>; no invented
              individuals or credentials (see Content guardrails below).
            </li>
            <li>
              <Em>Verified links</Em> — external links are probed live before publish; internal links only to
              pages that actually exist.
            </li>
            <li>
              <Em>On-topic photoreal images</Em> — varied per article, never the same generic stock shot.
            </li>
          </List>
          <Callout tone="warn" tag="Operational note">
            Only 3 drafts generate at once. Drafts stuck in "generating" hold those slots — the Content
            Review page flags stale ones to clear, which also frees regenerate/generate if they start
            returning "too many generating."
          </Callout>
        </Section>

        {/* Content guardrails */}
        <Section id="guardrails" eyebrow="Content guardrails" title="Truthful-claims rules every draft follows">
          <P>
            Because content publishes at scale under the brands' names, the generator runs under hard
            truthfulness rules — added ahead of the volume increase to keep the sites clear of FTC
            deception risk and Google's scaled-content spam policy.
          </P>
          <List>
            <li>
              <Em>Team bylines only</Em> — every post reads <em>"By the [Brand] Team"</em>. No named
              individuals, no certifications or credentials, no years-of-experience claims. The Article
              schema author is the brand organization, not a person.
            </li>
            <li>
              <Em>Third person, no invented experience</Em> — first-person anecdotes ("I have personally
              seen…") are banned; the model writes with expert depth but never a fabricated identity.
            </li>
            <li>
              <Em>No unattested performance claims</Em> — response times, staffing counts, pricing, and
              guarantees may only appear if supplied as brand facts; the model can't invent them.
            </li>
            <li>
              <Em>Statistics need sources</Em> — a number appears only with a linked, verified authority
              source (ASME, ADA, OSHA, official .gov). "Internal service data" attributions are banned.
            </li>
            <li>
              <Em>Every external link is verified live</Em> before publish — hard-404s, dead domains, and
              soft-404 redirects get re-pointed to a working authority page or unlinked.
            </li>
          </List>
          <Callout tone="warn" tag="When scaling further">
            Two practices to keep avoiding: publishing the <em>same</em> draft to multiple brand sites
            (duplicate/doorway-page risk under Google's spam policies), and re-introducing individual
            credentials into bylines or schema without documented attestation from that person. If a claim
            like "our mechanics are IUEC-certified" is genuinely true for a brand, add it as an attested
            brand fact rather than letting the model assert it.
          </Callout>
        </Section>

        {/* Schema */}
        <Section id="schema" eyebrow="Schema (structured data)" title="Structured data, human-approved">
          <P>
            Schema is the machine-readable layer — <Em>schema.org JSON-LD</Em> that tells search engines and
            AI crawlers exactly what each page is: the business, its services, its FAQs. It's generated per
            brand but, unlike content, <Em>never publishes on its own</Em> — every change clears a human
            approval gate first.
          </P>

          <H3>What gets generated</H3>
          <List>
            <li>
              <Em>Organization</Em> — the brand entity: name, URL, logo, contact, and parent company (Axxiom
              Elevator) for the sub-brands.
            </li>
            <li>
              <Em>LocalBusiness</Em> — address, service area, hours, and phone, for local/near-me search.
            </li>
            <li>
              <Em>Service</Em> — one per elevator service line: maintenance, repair, modernization, new
              installation, and inspection.
            </li>
            <li>
              <Em>FAQPage</Em> &amp; <Em>Article</Em> — carried on published articles (FAQ blocks and article
              markup), so content pages are self-describing too.
            </li>
          </List>

          <H3>The approval flow</H3>
          <ol className="text-sm text-muted leading-7 max-w-[68ch] mb-3.5 list-decimal pl-5 marker:text-cyan marker:font-mono space-y-1.5">
            <li>
              <Em>Deploy</Em> — generate a brand's schema set. Items land as <em>pending review</em> and a
              notification announces "N schema deployments ready." Nothing is live yet.
            </li>
            <li>
              <Em>Schema Review</Em> (the <em>Schema Approval Inbox</em>) — inspect the raw JSON-LD, edit it
              if needed, then <Em>Approve</Em> or <Em>Reject</Em> with notes.
            </li>
            <li>
              <Em>Approve → WordPress</Em> — publishes the JSON-LD as a dedicated <Code>noindex</Code>{" "}
              "carrier" page (or updates the existing one) and logs an approval event.
            </li>
            <li>
              <Em>Published Schema</Em> — the running list of everything live, both brand-level and from
              content.
            </li>
            <li>
              <Em>Schema Health</Em> — per brand: pages tracked (published posts + approved carrier pages),
              how many validate, errors, and coverage. The validator fetches each live URL like a browser
              and distinguishes <em>missing schema</em> (page loads, no JSON-LD → self-heal queues a
              regenerated schema for review) from <em>unreachable</em> (blocked/404 — a measurement
              failure, never a regeneration trigger). <Em>Run validation</Em> re-checks a brand on demand;
              a monthly job sweeps everything.
            </li>
          </ol>

          <Callout tone="info" tag="Why a gate here?">
            Content is monitor-after (it auto-publishes), but schema is structural and applies site-wide, so
            it always waits for an explicit human OK. The Schema Approval Inbox is that checkpoint — separate
            from the content kill switch.
          </Callout>
          <Callout tone="warn" tag="Needs the WordPress helper">
            Schema Health validates by reading JSON-LD from live page source, so it only lights up once the
            brand's WordPress schema helper is installed (see <Code>wordpress/README</Code>). Carrier pages
            are <Code>noindex</Code>, so the markup reaches crawlers without ranking as thin pages themselves.
          </Callout>
        </Section>

        {/* Citation tracking */}
        <Section
          id="tracking"
          eyebrow="Citation tracking"
          title={
            <>
              Measuring AI visibility <Chip tone="live">live</Chip>
            </>
          }
        >
          <P>
            The platform asks <Em>ChatGPT, Gemini, and Perplexity</Em> real customer questions (via Bright
            Data's AI-search APIs) and records, per query and engine, whether the brand is mentioned, cited
            with a link, or beaten. This is the same capability sold as SaaS (e.g. Peec.ai) — run in-house.
          </P>
          <H3>How a citation audit runs</H3>
          <List>
            <li>
              Each brand's query set is batched per engine into one Bright Data scrape (trigger → poll
              snapshot → download).
            </li>
            <li>Records are parsed for the brand's name/domain and any cited competitor.</li>
            <li>
              <Em>Local competitors are detected by name</Em> (from cited source domains), not just the big
              national OEMs — so the gaps reflect who's actually winning each market.
            </li>
            <li>Results feed the Citations dashboard, the gap analysis, and the Recommendations inbox.</li>
          </List>
          <P>
            Audits run automatically on the 1st and 15th, or on demand via <Em>Run Citation Audit</Em>.
          </P>
          <H3>Browsing audit history</H3>
          <P>
            The Citations page isn't pinned to the latest run: an <Em>Audit scope</Em> selector switches
            between the latest audit, any past audit (each listed with its date, check count, and cited %),
            all history, or a custom date range. Every chart and the results table follow the selection —
            including the <Em>platform × brand</Em> chart, which shows each brand's citation share on each
            engine so you can see who ChatGPT cites vs who Gemini cites. Gap analysis stays pinned to the
            latest audit because it feeds Recommendations.
          </P>
        </Section>

        {/* Recommendations */}
        <Section id="recommendations" eyebrow="Recommendations" title="Approve a gap into a published article">
          <P>
            The Recommendations inbox is computed live from un-actioned citation gaps and ranked by impact (a
            cited competitor outranks plain invisibility, amplified by how many engines miss the brand and how
            low visibility is). Each card names the engines missing the brand and the competitor winning
            there.
          </P>
          <List>
            <li>
              <Em>Approve</Em> → queues the topic, generates the article, and takes you straight to Content
              Review, where the draft waits for your sign-off — unlike daily content, recommendation drafts{" "}
              <em>never</em> auto-publish.
            </li>
            <li>
              <Em>Dismiss</Em> → hides it for a 30-day cooldown, then it can resurface if still unaddressed.
            </li>
            <li>Anything already queued, drafted, or published falls off automatically.</li>
          </List>
        </Section>

        {/* Reports & costs */}
        <Section id="reports" eyebrow="Reports & costs" title="Monthly performance and spend">
          <P>
            Reports are point-in-time snapshots with a <Em>period selector</Em> to browse any month,{" "}
            <Em>month-over-month deltas</Em>, brand/category charts, an AI executive summary, and
            top-performing / gap-query tables. Export as CSV or print to PDF. GA4 traffic and conversions
            in a monthly report measure that exact calendar month (the live dashboard uses a rolling 30
            days).
          </P>
          <H3>AI conversions — does AEO convert anyone?</H3>
          <P>
            The dashboard and reports carry an <Em>AI Conversions</Em> KPI: GA4 key events (calls, form
            submits) from sessions referred by ChatGPT, Perplexity, Claude, Gemini, Copilot, and other AI
            assistants — with the conversion rate and month-over-month delta. The search-vs-generative
            panel shows conversions for organic search and AI traffic side by side.
          </P>
          <Callout tone="warn" tag="Prerequisite">
            The number reads 0 until each brand's GA4 property has <Em>key events</Em> configured
            (click-to-call and form-submit), and <Code>GOOGLE_SERVICE_ACCOUNT_JSON</Code> must be a
            base64-encoded <em>service-account key</em> granted access to each GA4 property — an OAuth
            client JSON silently zeroes every Google metric (the backend logs exactly what's wrong).
          </Callout>
          <H3>Billing-grade API cost tracking</H3>
          <P>
            A ledger records every billable API call with its real usage, summed on the Reports page into
            three buckets:
          </P>
          <Table
            head={
              <>
                <Th>Bucket</Th>
                <Th>Source</Th>
                <Th>Metered by</Th>
              </>
            }
          >
            <tr>
              <td className="px-3.5 py-2.5 align-top text-ink">Content creation</td>
              <td className="px-3.5 py-2.5 align-top text-muted">Claude</td>
              <td className="px-3.5 py-2.5 align-top text-muted">actual input/output tokens per call</td>
            </tr>
            <tr>
              <td className="px-3.5 py-2.5 align-top text-ink">Image generation</td>
              <td className="px-3.5 py-2.5 align-top text-muted">gpt-image-2 / Ideogram / fal</td>
              <td className="px-3.5 py-2.5 align-top text-muted">per image generated</td>
            </tr>
            <tr>
              <td className="px-3.5 py-2.5 align-top text-ink">AI-visibility tracking</td>
              <td className="px-3.5 py-2.5 align-top text-muted">Bright Data</td>
              <td className="px-3.5 py-2.5 align-top text-muted">real accrued spend (account balance)</td>
            </tr>
          </Table>
          <Callout tone="info" tag="Set your rates">
            Unit counts are exact; the $ figures use configurable rates — set{" "}
            <Code>ANTHROPIC_INPUT/OUTPUT_COST_PER_MTOK</Code> and <Code>COST_PER_IMAGE_USD</Code> to your
            actual prices. Bright Data cost is pulled from the account balance directly.
          </Callout>
        </Section>

        {/* AI providers */}
        <Section id="providers" eyebrow="AI providers" title="Swappable model providers">
          <P>
            Each capability sits behind a provider seam, so a model can be swapped by changing environment
            variables — no code change.
          </P>

          <H3>
            Text — Claude <Chip tone="live">live</Chip>
          </H3>
          <P>
            Article writing, image planning, and the AI summaries use <Code>claude-sonnet-4-6</Code>. It can
            run against Anthropic directly, or through <Em>Microsoft Foundry</Em> (Azure) by setting{" "}
            <Code>ANTHROPIC_BASE_URL</Code> to the Foundry <Code>/anthropic</Code> endpoint and the Azure key
            — same Messages API, so nothing else changes.
          </P>

          <H3>
            Images — Azure gpt-image-2 <Chip tone="live">default</Chip> <Chip tone="opt">+ fallbacks</Chip>
          </H3>
          <P>
            Article images default to <Em>Azure OpenAI gpt-image-2</Em> (Foundry); Ideogram, fal.ai, and
            OpenAI remain configured fallbacks. Landscape, photoreal, ~$0.05/image at medium quality.
          </P>
          <Callout tone="warn" tag="gotcha">
            The Azure images endpoint is <Code>{"/openai/deployments/<name>/images/generations"}</Code> with a{" "}
            <em>dated</em> <Code>api-version</Code> (e.g. <Code>2025-04-01-preview</Code>) — the evergreen{" "}
            <Code>?api-version=preview</Code> 404s, and <Code>/chat/completions</Code> is the wrong path. On
            lower tiers the per-minute rate limit is small, so bursts self-throttle with backoff.
          </Callout>

          <H3>
            Citations — Bright Data <Chip tone="live">live</Chip>
          </H3>
          <P>
            Native AI-search APIs drive ChatGPT, Gemini, and Perplexity. The default provider is{" "}
            <Code>brightdata</Code>.
          </P>
        </Section>

        {/* Configuration */}
        <Section id="config" eyebrow="Configuration" title="Key environment variables">
          <P>Set in Railway (backend). Secrets never live in the repo.</P>
          <Table
            head={
              <>
                <Th>Variable</Th>
                <Th>Purpose</Th>
              </>
            }
          >
            {[
              ["ANTHROPIC_API_KEY", "Claude key (Anthropic direct, or the Azure/Foundry key)"],
              ["ANTHROPIC_BASE_URL", "Optional — route Claude through Microsoft Foundry"],
              ["IMAGE_PROVIDER", "azure · ideogram · fal · openai"],
              ["AZURE_IMAGE_ENDPOINT", "Full images/generations URL (dated api-version)"],
              ["AZURE_IMAGE_API_KEY", "gpt-image-2 deployment key"],
              ["CITATION_PROVIDER", "brightdata (default)"],
              ["BRIGHT_DATA_API_KEY", "AI-search + account-balance cost"],
              ["AUTO_PUBLISH_ENABLED", "true = monitor-after; false = approve-first"],
              ["CONTENT_GENERATION_MAX_PER_BRAND", "Daily posts per brand (default 4)"],
              ["CLAUDE_MODEL", "Writing model (claude-sonnet-4-6)"],
              ["GOOGLE_SERVICE_ACCOUNT_JSON", "Base64 service-account key — GA4 + Search Console"],
              ["WP_APP_PASSWORD_<brand>", "WordPress publishing per brand"],
              ["WP_USERNAME_<brand>", "WP login for the app password (default admin)"],
              ["DISCORD_WEBHOOK_URL", "Published-post notifications"],
            ].map(([v, purpose]) => (
              <tr key={v}>
                <td className="px-3.5 py-2.5 align-top">
                  <Code>{v}</Code>
                </td>
                <td className="px-3.5 py-2.5 align-top text-muted">{purpose}</td>
              </tr>
            ))}
          </Table>
        </Section>

        {/* Operations */}
        <Section id="operations" eyebrow="Operations" title="Stack, schedules & troubleshooting">
          <H3>Stack</H3>
          <div className="max-w-[68ch] mb-4">
            {[
              ["Backend", <>FastAPI + APScheduler + SQLAlchemy on Railway</>],
              ["Frontend", <>React / TypeScript / Tailwind on Netlify</>],
              [
                "Data / auth",
                <>
                  Supabase Postgres (<Code>aeo</Code> schema) + Supabase Auth (JWT)
                </>,
              ],
              ["Models", <>Claude (text) · gpt-image-2 (images) · Bright Data (citations)</>],
            ].map(([label, val], i) => (
              <div
                key={label as string}
                className={`flex gap-4 items-baseline py-2.5 text-sm ${
                  i === 0 ? "" : "border-t border-border"
                }`}
              >
                <span className="font-mono text-xs text-cyan min-w-[112px] shrink-0">{label}</span>
                <span className="text-muted">{val}</span>
              </div>
            ))}
          </div>

          <H3>
            Scheduled jobs <Chip tone="opt">America/Chicago</Chip>
          </H3>
          <Table
            head={
              <>
                <Th>Job</Th>
                <Th>Cadence</Th>
              </>
            }
          >
            {[
              ["Topic discovery", "daily, 8:00 AM"],
              ["Daily content + auto-publish", "daily, 9:00 AM"],
              ["Daily schema auto-posting (if enabled)", "daily, 10:00 AM"],
              ["Citation audit", "1st & 15th, 8:00 AM"],
              ["Schema validation sweep", "1st, 7:00 AM"],
              ["Content refresh", "Sundays, 6:00 AM"],
              ["Monthly report", "last day, 11:00 PM"],
            ].map(([job, cadence]) => (
              <tr key={job}>
                <td className="px-3.5 py-2.5 align-top text-ink">{job}</td>
                <td className="px-3.5 py-2.5 align-top text-muted tabular-nums">{cadence}</td>
              </tr>
            ))}
          </Table>

          <H3>Troubleshooting</H3>
          <List>
            <li>
              <Em>Citations page empty</Em> — an audit hasn't run/persisted; confirm{" "}
              <Code>CITATION_PROVIDER=brightdata</Code> + key, then Run Citation Audit.
            </li>
            <li>
              <Em>"Regenerate" / generate does nothing</Em> — usually all 3 generation slots are held by
              stale "generating" drafts; clear them on Content Review.
            </li>
            <li>
              <Em>Only some brands publish</Em> — those without a working{" "}
              <Code>{"WP_APP_PASSWORD_<brand>"}</Code> fail at publish; the Notifications feed names the
              reason per brand.
            </li>
            <li>
              <Em>Images 404 / 400</Em> — wrong Azure endpoint path or api-version (see the Images gotcha
              above).
            </li>
            <li>
              <Em>GA4 / Search Console metrics all zero</Em> — <Code>GOOGLE_SERVICE_ACCOUNT_JSON</Code> is
              missing, an OAuth client JSON instead of a service-account key, or the account lacks access;
              the backend log names the exact problem. Search-demand also needs each brand's GSC property
              URL in Brand Settings.
            </li>
            <li>
              <Em>Schema Health shows errors with "bot-blocked" details</Em> — the site's protection
              challenged the crawler; a blocked fetch is a measurement failure, not missing schema. Re-run
              validation.
            </li>
            <li>
              <Em>A live post's links or byline look outdated</Em> — run the content-hygiene backfill
              (<Code>scripts/fix_broken_links.py</Code>, dry-run by default) to re-verify links, normalize
              bylines, and refresh schema across all published posts.
            </li>
          </List>

          <p className="font-mono text-[11px] text-muted/60 mt-8 pt-4 border-t border-border">
            AXXIOM AEO · internal platform documentation · v2 (July 2026) · 5 brands · production
          </p>
        </Section>
      </main>

      {/* Sticky "On this page" rail */}
      <aside className="hidden lg:block">
        <div className="sticky top-0">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted px-3 pb-2.5">
            On this page
          </p>
          <ol>
            {SECTIONS.map((s, i) => {
              const isActive = active === s.id;
              return (
                <li key={s.id}>
                  <a
                    href={`#${s.id}`}
                    onClick={(e) => jump(e, s.id)}
                    className={`flex gap-2.5 px-3 py-1.5 text-[13px] border-l-2 transition-colors ${
                      isActive
                        ? "border-cyan text-cyan"
                        : "border-transparent text-muted hover:text-ink"
                    }`}
                  >
                    <span className="font-mono text-[10px] text-muted/60 tabular-nums pt-0.5">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    {s.label}
                  </a>
                </li>
              );
            })}
          </ol>
        </div>
      </aside>
    </div>
  );
}
