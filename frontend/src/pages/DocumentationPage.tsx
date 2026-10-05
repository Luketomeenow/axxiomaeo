import { useEffect, useState } from "react";
import type { MouseEvent, ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";

type SectionGroup = { group: string; items: { id: string; label: string }[] };
type TabId = "platform" | "azure";

const PLATFORM_GROUPS: SectionGroup[] = [
  {
    group: "Platform",
    items: [
      { id: "overview", label: "Overview" },
      { id: "how", label: "How it works" },
      { id: "dashboard", label: "The pages" },
    ],
  },
  {
    group: "Content",
    items: [
      { id: "content", label: "Content engine" },
      { id: "topics", label: "Where topics come from" },
      { id: "guardrails", label: "Content guardrails" },
      { id: "refresh", label: "Content refresh" },
      { id: "schema", label: "Schema (structured data)" },
    ],
  },
  {
    group: "Measurement",
    items: [
      { id: "tracking", label: "Citation tracking" },
      { id: "recommendations", label: "Recommendations" },
      { id: "advisor", label: "Improvement Advisor" },
      { id: "reports", label: "Reports & costs" },
    ],
  },
  {
    group: "Reliability",
    items: [
      { id: "health", label: "System Health & alerts" },
      { id: "optimizer", label: "Optimization agent" },
      { id: "agent", label: "Agent API" },
    ],
  },
  {
    group: "Reference",
    items: [
      { id: "providers", label: "AI providers" },
      { id: "config", label: "Configuration" },
      { id: "operations", label: "Operations" },
    ],
  },
];

const AZURE_GROUPS: SectionGroup[] = [
  {
    group: "Setup",
    items: [
      { id: "azure-overview", label: "What runs where" },
      { id: "azure-resources", label: "Resources" },
    ],
  },
  {
    group: "Access",
    items: [
      { id: "azure-signin", label: "Dashboard sign-in" },
      { id: "azure-secrets", label: "Identity & secrets" },
      { id: "azure-optimizer", label: "Optimization agent" },
    ],
  },
  {
    group: "Operate",
    items: [
      { id: "azure-deploy", label: "Deploying" },
      { id: "azure-settings", label: "App settings" },
      { id: "azure-database", label: "Database & migrations" },
      { id: "azure-scheduler", label: "Scheduler" },
    ],
  },
  {
    group: "Runbooks",
    items: [
      { id: "azure-cloudshell", label: "Cloud Shell" },
      { id: "azure-monitoring", label: "Health & logs" },
      { id: "azure-recovery", label: "Pause & roll back" },
      { id: "azure-troubleshooting", label: "Troubleshooting" },
    ],
  },
  {
    group: "History",
    items: [{ id: "azure-history", label: "Migration record" }],
  },
];

// The tab lives in the URL (?tab=azure) so either tab can be linked directly.
const TABS: { id: TabId; label: string; to: string }[] = [
  { id: "platform", label: "Platform", to: "/docs" },
  { id: "azure", label: "Azure Setup", to: "/docs?tab=azure" },
];

const TAB_GROUPS: Record<TabId, SectionGroup[]> = { platform: PLATFORM_GROUPS, azure: AZURE_GROUPS };

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
    <div className={`max-w-[68ch] rounded-md border border-l-4 p-4 text-sm mb-4 ${box}`}>
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
    <section id={id} className="scroll-mt-16 lg:scroll-mt-4 border-t border-border pt-10 first:border-t-0 first:pt-0">
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

function Td({ tone = "muted", children }: { tone?: "ink" | "muted"; children: ReactNode }) {
  return (
    <td className={`px-3.5 py-2.5 align-top ${tone === "ink" ? "text-ink" : "text-muted"}`}>{children}</td>
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

function Cmd({ children }: { children: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(children);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard unavailable (permissions, insecure origin) — the text is still selectable.
    }
  };
  return (
    <div className="relative max-w-[68ch] mb-4">
      <pre className="overflow-x-auto rounded-md border border-border bg-panel py-3 pl-4 pr-20 font-mono text-[12.5px] leading-6 text-ink/90">
        <code>{children}</code>
      </pre>
      <button
        type="button"
        onClick={copy}
        className="absolute top-2 right-2 rounded border border-border bg-void/80 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted hover:border-cyan/50 hover:text-ink"
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

const STEPS: { title: string; body: ReactNode }[] = [
  {
    title: "Pick topics (8:00 AM)",
    body: (
      <>
        Fills each brand's queue from real demand, best signal first: verbatim customer questions
        (pushed from GHL), rising Google searches (Search Console), AI-visibility gaps (queries where
        a competitor is cited instead), coverage fill — and, only when everything else is exhausted,
        an AI-proposed evergreen topic so the pipeline can never run dry.
      </>
    ),
  },
  {
    title: "Write the drafts (9:00 AM)",
    body: (
      <>
        Claude generates full articles formatted to answer the question directly, with photoreal
        images and a team byline — written under hard truthfulness rules (no invented authors,
        credentials, claims, or statistics; see Content guardrails).
      </>
    ),
  },
  {
    title: "Quality-check",
    body: (
      <>
        Validates that each draft answers the query and is long enough, carries valid structured-data
        markup and image alt text — and verifies every link: external links are probed against the
        live web and internal links are checked against the brand's real published pages.
      </>
    ),
  },
  {
    title: "Publish & announce",
    body: (
      <>
        Publishes to the brand's WordPress site once it passes, then posts the live link to Discord.
        A schema worker separately keeps each brand's structured data complete (10:00 AM).
      </>
    ),
  },
  {
    title: "Verify & watch (10:30 AM + 3:00 PM)",
    body: (
      <>
        A flow-health check diagnoses every pipeline stage mid-morning and alerts Discord if anything
        failed or produced nothing; at 3 PM a posting monitor checks each brand's <em>live</em>{" "}
        website to confirm today's posts actually landed.
      </>
    ),
  },
  {
    title: "Measure (Mondays 5:00 AM)",
    body: (
      <>
        The weekly citation audit asks ChatGPT, Gemini, and Perplexity ~30 real questions per brand
        and records whether each brand is mentioned, cited with a link, or beaten by a named
        competitor — including whether the cited page is one this platform published.
      </>
    ),
  },
  {
    title: "Recommend the next move (Mondays 7:00 AM)",
    body: (
      <>
        Citation gaps become one-click Recommendations, and the Improvement Advisor reads the whole
        platform — KPIs, share by brand, posting cadence, pipeline health, costs — into a prioritized
        "what to improve and why" report. At 7:30 the optimization agent turns it into specific changes
        on System Health; an approved code change becomes a pull request drafted by Claude Code.
      </>
    ),
  },
];

function PlatformDocs() {
  return (
    <>
      {/* Intro / overview */}
      <Section
        id="overview"
        eyebrow="Overview"
        title="The system that keeps Axxiom's brands visible to AI answer engines"
      >
        <p className="text-base text-muted leading-relaxed max-w-[68ch] mb-4">
          Axxiom Elevator runs a network of six brand sites —{" "}
          <Em>
            Axxiom Elevator Florida, AmeriTex, Arizona Elevator Solutions, Liftech, Quality
            Elevator, and Carolina Elevator Service
          </Em>
          . This platform automatically writes and publishes content for those sites, and measures
          whether ChatGPT, Gemini, and Perplexity actually cite the brands when people ask elevator
          questions.
        </p>
        <P>
          It's <Em>Answer Engine Optimization (AEO)</Em> — the same idea as SEO, but for AI
          assistants instead of Google. When someone asks an AI "who does emergency elevator repair
          in Pompano Beach?", the goal is that one of these brands is the answer, not a competitor.
        </P>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3.5 mt-5">
          <Card k="Writes" title="Content, daily">
            AI-written articles per brand per day, sourced from real demand — customer questions,
            search trends, and citation gaps.
          </Card>
          <Card k="Measures" title="AI visibility, weekly">
            Asks the engines ~30 real questions per brand every Monday; records who's cited and who
            loses to a competitor.
          </Card>
          <Card k="Acts" title="Recommendations & Advisor">
            Turns gaps into "publish this next" and a weekly AI report on what to improve and why.
          </Card>
          <Card k="Watches itself" title="System Health">
            Every pipeline stage is diagnosed daily; anything broken or silent alerts Discord the
            same morning.
          </Card>
        </div>
      </Section>

      {/* How it works */}
      <Section id="how" eyebrow="How it works" title="The daily loop, start to finish">
        <P>
          Every day the platform runs this cycle on its own (all times America/Chicago). A human
          monitors it rather than driving each step.
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
          Publishing is automatic (monitor-after), but the human stays in control at the strategy
          layer — approving <em>what</em> to work on in the Recommendations inbox, reviewing flagged
          drafts, and via a kill switch (<Code>AUTO_PUBLISH_ENABLED=false</Code>) that restores
          approve-before-publish for every draft.
        </Callout>
      </Section>

      {/* Dashboard / pages */}
      <Section id="dashboard" eyebrow="The pages" title="What the team sees">
        <P>
          A React dashboard, served by the same Azure App Service as the API, grouped into what to watch,
          what to act on, and what to review.
        </P>
        <div className="grid sm:grid-cols-2 gap-3.5">
          <Card title="Dashboard">
            Headline scorecard — citation share, AI visibility, share of voice vs competitors,
            AI-referred sessions, and AI conversions (GA4 key events from AI visitors).
          </Card>
          <Card title="Recommendations">
            Ranked "what to do next," each explaining why; one <Em>Approve</Em> queues the topic,
            writes the draft, and hands it to Content Review for your sign-off.
          </Card>
          <Card title="Citations">
            The AI-visibility monitor — who's cited on which engine, for which questions, where each
            audited query came from, and an <Em>our post</Em> badge when the AI cited a page this
            platform published. Includes an <Em>AI Recommendations</Em> tab reading the whole audit.
          </Card>
          <Card title="Advisor">
            The weekly Improvement Advisor report — prioritized improvements with the data behind
            each one, quick wins, and a history of past reports. Regenerate on demand.
          </Card>
          <Card title="System Health">
            Live diagnosis of every pipeline stage — integrations (including a real login test
            against each WordPress site), topic discovery, generation, publishing, worker errors —
            plus stranded drafts and interrupted audits, each with what to do about it.
          </Card>
          <Card title="Reports">
            Monthly snapshots with month-over-month trends, AI conversions, an AI executive summary,
            actual API costs, and CSV / print export.
          </Card>
          <Card title="Content Review, Published & Queue">
            Every draft and everything live — searchable and sortable; regenerate, edit, or reject
            before publish, or pull a live post back to review. The queue shows each topic's source.
          </Card>
          <Card title="Schema & Brand Settings">
            Structured data review and health, plus per-brand config: markets, GA4/GSC wiring, target
            queries, topic boost, and a WordPress <Em>Test connection</Em> button.
          </Card>
        </div>
      </Section>

      {/* Content engine */}
      <Section id="content" eyebrow="Content engine" title="From demand signal to published article">
        <P>
          Topic discovery queues <Em>2 topics per brand per day</Em> by default
          (<Code>TOPIC_DISCOVERY_MAX_PER_BRAND</Code>), plus that brand's <Em>topic boost</Em> — a
          per-brand Brand Settings knob (0–10) for visibility sprints, e.g. a new or under-cited
          brand. The daily worker generates a draft per queued topic (hard cap{" "}
          <Code>CONTENT_GENERATION_MAX_PER_BRAND</Code> + boost), validates each, and — under the
          monitor-after model — publishes automatically once a draft passes.
        </P>
        <H3>What makes a good AEO article here</H3>
        <List>
          <li>
            <Em>Answer-first structure</Em> — a direct answer up top, question-shaped H2s, and enough
            depth for the query.
          </li>
          <li>
            <Em>Structured data</Em> — FAQ / LocalBusiness / Article schema so engines understand the
            page.
          </li>
          <li>
            <Em>Honest authorship</Em> — every post is bylined <em>"By the [Brand] Team"</em>; no
            invented individuals or credentials (see Content guardrails).
          </li>
          <li>
            <Em>Verified links</Em> — external links probed live before publish; internal links only
            to pages that actually exist.
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

      {/* Topic sources */}
      <Section id="topics" eyebrow="Where topics come from" title="Five sources, best signal first">
        <P>
          Every queued topic carries its <Em>source</Em> so you always know why an article exists.
          Discovery tries them in trust order and the pipeline can no longer run dry — the floor of
          last resort generates topics instead of silently queueing nothing.
        </P>
        <Table
          head={
            <>
              <Th>Source</Th>
              <Th>What it is</Th>
              <Th>Trust</Th>
            </>
          }
        >
          <tr>
            <Td tone="ink">customer questions</Td>
            <Td>
              Verbatim questions from GHL calls/chats/forms, pushed by the ghl-agent via the Agent
              API — literal human demand
            </Td>
            <Td>highest</Td>
          </tr>
          <tr>
            <Td tone="ink">search demand</Td>
            <Td>Rising or under-served Google queries from each brand's Search Console</Td>
            <Td>high</Td>
          </tr>
          <tr>
            <Td tone="ink">citation gap</Td>
            <Td>Queries where AI engines skip the brand — strongest "will earn a citation" signal</Td>
            <Td>high</Td>
          </tr>
          <tr>
            <Td tone="ink">coverage</Td>
            <Td>Markets and question-bank topics with no content yet (finite)</Td>
            <Td>medium</Td>
          </tr>
          <tr>
            <Td tone="ink">evergreen</Td>
            <Td>
              AI-proposed buyer questions (services × verticals × markets × season) — used only when
              everything above is exhausted
            </Td>
            <Td>floor</Td>
          </tr>
        </Table>
        <Callout tone="info" tag="Why a floor exists">
          In August 2026 every finite pool ran dry at once and four brands silently stopped posting
          for days. Now: a zero-topic morning triggers an immediate Discord alert <em>and</em> the
          evergreen generator keeps the queue fed while you investigate.
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
          <li>
            <Em>Verified state facts only</Em> — each state's elevator regulator, rules, and requirements
            come from a fact sheet where every line carries an official URL and a verbatim quote. A draft
            that names a wrong regulator (e.g. the Texas Department of Insurance instead of TDLR), cites a
            wrong rule, or states a requirement that isn't in force fails and goes back for correction; the
            Sunday refresh is held the same way (<Code>STATE_FACTS_GUARD_ENABLED</Code>).
          </li>
        </List>
        <Callout tone="warn" tag="When scaling further">
          Two practices to keep avoiding: publishing the <em>same</em> draft to multiple brand sites
          (duplicate/doorway-page risk under Google's spam policies), and re-introducing individual
          credentials into bylines or schema without documented attestation from that person. If a
          claim like "our mechanics are IUEC-certified" is genuinely true for a brand, add it as an
          attested brand fact rather than letting the model assert it.
        </Callout>
      </Section>

      {/* Content refresh */}
      <Section id="refresh" eyebrow="Content refresh" title="Old posts get better on their own">
        <P>
          Freshness is a real AI-citation signal, so every Sunday the refresh worker re-optimizes the{" "}
          <Em>least-recently-touched</Em> published posts — up to{" "}
          <Code>CONTENT_REFRESH_MAX_PER_RUN</Code> (default 6) per week, once a post hasn't been
          touched in <Code>CONTENT_REFRESH_DAYS</Code> (default 45).
        </P>
        <List>
          <li>Updates year references and re-verifies statistics against linked sources.</li>
          <li>Adds 2–3 new FAQ questions covering subtopics AI engines fan out to.</li>
          <li>Strengthens the opening direct answer; preserves byline, slug, and brand mentions.</li>
          <li>
            Republishes to WordPress and stamps the piece, so rotation works through the whole
            library instead of revisiting the same posts.
          </li>
        </List>
      </Section>

      {/* Schema */}
      <Section id="schema" eyebrow="Schema (structured data)" title="Structured data, self-healing with a review trail">
        <P>
          Schema is the machine-readable layer — <Em>schema.org JSON-LD</Em> that tells search
          engines and AI crawlers exactly what each page is: the business, its services, its FAQs.
        </P>
        <H3>What gets generated</H3>
        <List>
          <li>
            <Em>Organization</Em> — the brand entity: name, URL, logo, contact, and parent company
            (Axxiom Elevator) for the sub-brands.
          </li>
          <li>
            <Em>LocalBusiness</Em> — address, service area, hours, and phone, for local/near-me search.
          </li>
          <li>
            <Em>Service</Em> — one per service line: maintenance, repair, modernization, new
            installation, and inspection.
          </li>
          <li>
            <Em>FAQPage</Em> &amp; <Em>Article</Em> — carried on published articles, so content pages
            are self-describing too.
          </li>
        </List>
        <H3>Two paths to live</H3>
        <List>
          <li>
            <Em>Self-healing (default on)</Em> — a daily 10 AM worker publishes at most one missing or
            outdated brand-level schema per brand, announcing each on the schema Discord channel.
            Disable with <Code>SCHEMA_AUTO_PUBLISH_ENABLED=false</Code>.
          </li>
          <li>
            <Em>Manual deploys</Em> — generating a brand's full schema set still lands in the{" "}
            <Em>Schema Review</Em> inbox for inspection/edit/approval before it publishes.
          </li>
        </List>
        <P>
          <Em>Schema Health</Em> tracks it per brand: pages tracked, how many validate, errors with
          drill-down. The validator fetches each live URL like a browser and distinguishes{" "}
          <em>missing schema</em> (page loads, no JSON-LD → self-heal queues a fix) from{" "}
          <em>unreachable</em> (blocked/404 — a measurement failure, never a regeneration trigger).
        </P>
        <Callout tone="warn" tag="Needs the WordPress helper">
          Schema Health validates by reading JSON-LD from live page source, so it only lights up once
          the brand's WordPress schema helper plugin is installed (see <Code>wordpress/README</Code>).
          Carrier pages are <Code>noindex</Code>, so the markup reaches crawlers without ranking as
          thin pages themselves.
        </Callout>
      </Section>

      {/* Citation tracking */}
      <Section
        id="tracking"
        eyebrow="Citation tracking"
        title={
          <>
            Measuring AI visibility, weekly <Chip tone="live">live</Chip>
          </>
        }
      >
        <P>
          Every Monday at 5 AM (and on demand via <Em>Run Citation Audit</Em>) the platform asks{" "}
          <Em>ChatGPT, Gemini, and Perplexity</Em> ~30 questions per brand via Bright Data's
          AI-search APIs and records, per query and engine, whether the brand is mentioned, cited
          with a link, or beaten — and whether the cited page is one this platform published
          (the <Em>our post</Em> badge).
        </P>
        <H3>What gets asked — demand-driven, not guesswork</H3>
        <P>
          Each brand's ~30 audit slots fill in trust order, and every record carries its{" "}
          <Em>query source</Em>:
        </P>
        <Table
          head={
            <>
              <Th>Source</Th>
              <Th>Slots</Th>
              <Th>What it proves</Th>
            </>
          }
        >
          <tr>
            <Td tone="ink">custom</Td>
            <Td>all</Td>
            <Td>Queries you set per brand in Brand Settings</Td>
          </tr>
          <tr>
            <Td tone="ink">published</Td>
            <Td>up to 8</Td>
            <Td>Recent posts' target queries — "did we win what we published for?"</Td>
          </tr>
          <tr>
            <Td tone="ink">gsc</Td>
            <Td>up to 8</Td>
            <Td>Real Google demand from Search Console</Td>
          </tr>
          <tr>
            <Td tone="ink">ghl</Td>
            <Td>up to 4</Td>
            <Td>Verbatim customer questions from calls/chats/forms</Td>
          </tr>
          <tr>
            <Td tone="ink">bank</Td>
            <Td>remainder</Td>
            <Td>Curated question bank, round-robin across all its categories</Td>
          </tr>
        </Table>
        <H3>Reading the results</H3>
        <List>
          <li>
            <Em>Local competitors are detected from cited source domains</Em>, not just the national
            OEMs — the gaps reflect who's actually winning each market.
          </li>
          <li>
            The <Em>Audit scope</Em> selector switches between the latest audit, any past audit, all
            history, or a date range; every chart hover shows the math behind its percentage.
          </li>
          <li>Gap analysis stays pinned to the latest audit because it feeds Recommendations.</li>
        </List>
        <Callout tone="warn" tag="Don't deploy mid-audit">
          A full audit takes ~2 hours and runs inside the backend process — a deploy/restart kills it.
          Every audit records its lifecycle, and System Health flags an audit that started but never
          finished, with instructions to re-run. The Monday 5 AM slot exists so audits never overlap
          working-hours deploys.
        </Callout>
      </Section>

      {/* Recommendations */}
      <Section id="recommendations" eyebrow="Recommendations" title="Approve a gap into a published article">
        <P>
          The Recommendations inbox is computed live from un-actioned citation gaps and ranked by
          impact (a cited competitor outranks plain invisibility, amplified by how many engines miss
          the brand and how low visibility is). Each card names the engines missing the brand and the
          competitor winning there. Filter to one brand with{" "}
          <Code>{"/api/recommendations?brand_id=<brand>"}</Code> for a brand-scoped sprint.
        </P>
        <List>
          <li>
            <Em>Approve</Em> → queues the topic, generates the article, and takes you straight to
            Content Review, where the draft waits for your sign-off — unlike daily content,
            recommendation drafts <em>never</em> auto-publish.
          </li>
          <li>
            <Em>Dismiss</Em> → hides it for a 30-day cooldown, then it can resurface if still
            unaddressed.
          </li>
          <li>Anything already queued, drafted, or published falls off automatically.</li>
        </List>
      </Section>

      {/* Advisor */}
      <Section id="advisor" eyebrow="Improvement Advisor" title="Weekly: what to improve, and why">
        <P>
          Every Monday at 7 AM (and on demand from the <Em>Advisor</Em> page), Claude reads the whole
          platform — dashboard KPIs, citation share per brand and engine, gap examples, posting
          cadence for the last 7 days, pipeline flow health, monthly costs, and worker errors — and
          produces a prioritized report.
        </P>
        <List>
          <li>
            <Em>Improvements</Em> — high / medium / low priority, each grounded in the actual numbers
            ("Ameritex is at 0% on ChatGPT while cited on Perplexity — publish X"), tagged with
            category, effort, and brand.
          </li>
          <li>
            <Em>Quick wins</Em> — small concrete actions doable this week.
          </li>
          <li>
            <Em>History</Em> — reports persist, so you can compare week over week; the summary also
            lands in Discord.
          </li>
        </List>
        <Callout tone="info" tag="Two different 'recommendation' features">
          The <Em>Recommendations inbox</Em> turns individual citation gaps into publishable articles.
          The <Em>Advisor</Em> is the level above it — strategy and operations across the whole
          platform, including things content can't fix (broken integrations, a stalled pipeline,
          costs).
        </Callout>
      </Section>

      {/* Reports & costs */}
      <Section id="reports" eyebrow="Reports & costs" title="Monthly performance and spend">
        <P>
          Reports are point-in-time snapshots with a <Em>period selector</Em> to browse any month,{" "}
          <Em>month-over-month deltas</Em>, brand/category charts, an AI executive summary, and
          top-performing / gap-query tables. Export as CSV or print to PDF. GA4 traffic and
          conversions in a monthly report measure that exact calendar month (the live dashboard uses
          a rolling 30 days).
        </P>
        <H3>AI conversions — does AEO convert anyone?</H3>
        <P>
          The dashboard and reports carry an <Em>AI Conversions</Em> KPI: GA4 key events (calls, form
          submits) from sessions referred by ChatGPT, Perplexity, Claude, Gemini, Copilot, and other
          AI assistants — with the conversion rate and month-over-month delta.
        </P>
        <Callout tone="warn" tag="Prerequisite">
          The number reads 0 until each brand's GA4 property has <Em>key events</Em> configured
          (click-to-call and form-submit), and <Code>GOOGLE_SERVICE_ACCOUNT_JSON</Code> must be a
          base64-encoded <em>service-account key</em> granted access to each GA4 property — an OAuth
          client JSON silently zeroes every Google metric. System Health's Integrations stage shows
          whether the credential in production is valid.
        </Callout>
        <H3>Billing-grade API cost tracking</H3>
        <P>
          A ledger records every billable API call with its real usage — content writing, images,
          citation scrapes, the Advisor and evergreen-topic calls — summed on the Reports page.
          Bright Data cost comes from the account balance directly.
        </P>
      </Section>

      {/* System Health & alerts */}
      <Section
        id="health"
        eyebrow="System Health & alerts"
        title={
          <>
            The pipeline watches itself <Chip tone="live">live</Chip>
          </>
        }
      >
        <P>
          The <Em>System Health</Em> page diagnoses every stage of the daily flow in one view, and a
          10:30 AM check posts to Discord whenever anything is failing. Silence in that channel means
          healthy — every failure mode that once passed quietly now has a name.
        </P>
        <Table
          head={
            <>
              <Th>Stage</Th>
              <Th>What it checks</Th>
            </>
          }
        >
          <tr>
            <Td tone="ink">Integrations</Td>
            <Td>
              Google credential validity (in production), citation provider, Discord webhook, and a
              real login test against every brand's WordPress — with per-brand Test buttons
            </Td>
          </tr>
          <tr>
            <Td tone="ink">Topic discovery</Td>
            <Td>Topics queued today by source; distinguishes "ran but queued 0" from "never ran"</Td>
          </tr>
          <tr>
            <Td tone="ink">Generation</Td>
            <Td>
              Drafts created today; items stuck in progress; <em>stranded</em> drafts that generated
              but never published (each linked to Content Review)
            </Td>
          </tr>
          <tr>
            <Td tone="ink">Publishing</Td>
            <Td>Posts published today per brand; silent brands flagged</Td>
          </tr>
          <tr>
            <Td tone="ink">Worker errors</Td>
            <Td>Last 24h grouped by worker, plus interrupted-audit detection</Td>
          </tr>
        </Table>
        <H3>The alert layers</H3>
        <List>
          <li>
            <Em>Immediate</Em> — zero topics at 8 AM or an empty queue at 9 AM alerts Discord the
            moment it happens.
          </li>
          <li>
            <Em>10:30 AM flow check</Em> — full stage-by-stage diagnosis; alerts only when something
            is wrong.
          </li>
          <li>
            <Em>3:00 PM posting monitor</Em> — checks each brand's <em>live website</em> (not our
            database) to confirm today's posts actually landed; catches anything the earlier layers
            can't see.
          </li>
        </List>
      </Section>

      {/* Optimization agent */}
      <Section
        id="optimizer"
        eyebrow="Optimization agent"
        title={
          <>
            Proposes changes; Claude Code drafts the approved ones <Chip tone="gate">human-approved</Chip>
          </>
        }
      >
        <P>
          The Advisor says what to improve. The optimization agent, on the <Em>System Health</Em> page,
          turns that into specific changes you approve or reject, and carries out the approved ones. It
          runs every Monday at 7:30 AM, after the Advisor, and on demand with <Em>Run analysis now</Em>.
        </P>
        <H3>What it reads</H3>
        <P>
          A snapshot the platform computes itself: pipeline stages, posts per brand, citation share per
          brand and engine, phone calls that started on articles (CallRail warehouse), GA4{" "}
          <Code>phone_call_click</Code> and <Code>form_submit</Code> per brand, the topic queue, draft
          validation failures, and the main feature switches. Claude only explains. Each proposal must
          quote numbers from the snapshot, every quoted value is checked against it (✓ found, ⚠ not
          found), and a proposal with nothing found is dropped.
        </P>
        <H3>Two kinds of proposal</H3>
        <Table
          head={
            <>
              <Th>Kind</Th>
              <Th>When you approve it</Th>
            </>
          }
        >
          <tr>
            <Td tone="ink">Code change</Td>
            <Td>
              GitHub Actions starts a Claude Code agent on a new branch. It edits files only (no shell,
              no network). The workflow then runs the backend tests, the type check and the build, gives
              the agent one try at fixing failures, and opens a pull request. The PR is a draft if checks
              still fail. You can edit the agent's task before approving.
            </Td>
          </tr>
          <tr>
            <Td tone="ink">Manual change</Td>
            <Td>
              Work outside this repo, such as WordPress admin, CallRail, GA4, Cloudflare or Brand
              Settings. Accepting it tracks it as yours to do; <Em>Mark done</Em> closes it.
            </Td>
          </tr>
        </Table>
        <H3>Why approval can't ship anything by itself</H3>
        <List>
          <li>
            The platform's GitHub token can start the workflow and read its results. It cannot push code.
          </li>
          <li>
            The agent never holds a push credential. The workflow pushes the branch after the agent has
            exited, and rejects any change under <Code>.github/</Code>, <Code>.claude/</Code>,{" "}
            <Code>scripts/azure/</Code> or an env file.
          </li>
          <li>
            Merging the PR doesn't deploy. Deploys stay manual (<Em>Azure Setup → Deploying</Em>).
          </li>
          <li>
            Rejected proposals aren't proposed again for 60 days, and each approval is recorded with who
            and when.
          </li>
        </List>
        <P>
          Status follows each change from <Em>Starting</Em> to <Em>Claude Code is implementing it</Em>,{" "}
          <Em>Pull request ready</Em> and <Em>Merged</Em>, with links to the run log and the PR. A new
          proposal batch and each ready PR are also posted to Discord. To connect the agent, see{" "}
          <Em>Azure Setup → Optimization agent</Em>.
        </P>
      </Section>

      {/* Agent API */}
      <Section id="agent" eyebrow="Agent API" title="Machine-facing endpoints for external AI agents">
        <P>
          A key-authenticated API (<Code>X-API-Key</Code> = <Code>AGENT_API_KEY</Code>) lets external
          agents — currently the Foundry AEO strategist and the GHL agent — read live performance and
          feed the platform, without ever bypassing the human publishing gate.
        </P>
        <Table
          head={
            <>
              <Th>Endpoint</Th>
              <Th>Purpose</Th>
            </>
          }
        >
          <tr>
            <Td tone="ink">GET /api/agent/overview</Td>
            <Td>Compact snapshot: brands, citation share, queue depth, top recommendations</Td>
          </tr>
          <tr>
            <Td tone="ink">GET /api/agent/gaps</Td>
            <Td>Citation gaps from the latest audit, filterable by brand</Td>
          </tr>
          <tr>
            <Td tone="ink">POST /api/agent/generate</Td>
            <Td>Queue one article draft — deduped, and it always waits for human review</Td>
          </tr>
          <tr>
            <Td tone="ink">POST /api/agent/observed-questions</Td>
            <Td>
              Push verbatim customer questions (calls/chats/forms) — they become the highest-trust
              topic source and join the weekly audit
            </Td>
          </tr>
        </Table>
        <P>
          <Code>/api/agent/openapi.json</Code> serves a scoped spec for importing these as agent
          tools. Without <Code>AGENT_API_KEY</Code> set, the endpoints above answer 503 — see{" "}
          <Em>Azure Setup → Identity &amp; secrets</Em> to turn them on.
        </P>
      </Section>

      {/* AI providers */}
      <Section id="providers" eyebrow="AI providers" title="Swappable model providers">
        <P>
          Each capability sits behind a provider seam, so a model can be swapped by changing
          environment variables — no code change.
        </P>
        <H3>
          Text — Claude <Chip tone="live">live</Chip>
        </H3>
        <P>
          Article writing, refreshes, the Advisor, insights, and evergreen topics use{" "}
          <Code>claude-sonnet-4-6</Code>. It can run against Anthropic directly, or through{" "}
          <Em>Microsoft Foundry</Em> (Azure) by setting <Code>ANTHROPIC_BASE_URL</Code> to the
          Foundry <Code>/anthropic</Code> endpoint and the Azure key — same Messages API.
        </P>
        <H3>
          Images — Azure gpt-image-2 <Chip tone="live">default</Chip> <Chip tone="opt">+ fallbacks</Chip>
        </H3>
        <P>
          Article images default to <Em>Azure OpenAI gpt-image-2</Em> (Foundry); Ideogram, fal.ai,
          and OpenAI remain configured fallbacks. Landscape, photoreal, ~$0.05/image at medium
          quality.
        </P>
        <Callout tone="warn" tag="gotcha">
          The Azure images endpoint is <Code>{"/openai/deployments/<name>/images/generations"}</Code>{" "}
          with a <em>dated</em> <Code>api-version</Code> (e.g. <Code>2025-04-01-preview</Code>) — the
          evergreen <Code>?api-version=preview</Code> 404s, and <Code>/chat/completions</Code> is the
          wrong path. On lower tiers the per-minute rate limit is small, so bursts self-throttle with
          backoff.
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
        <P>
          Set as App Service settings on <Code>app-axxiom-aeo</Code>, with secrets as Key Vault references
          (see the <Em>Azure Setup</Em> tab). Secrets never live in the repo.
        </P>
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
            ["CITATION_PROVIDER", "brightdata (default)"],
            ["BRIGHT_DATA_API_KEY", "AI-search + account-balance cost"],
            ["AUTO_PUBLISH_ENABLED", "true = monitor-after; false = approve-first"],
            ["SCHEDULER_ENABLED", "false = pause every scheduled job (dashboard + API stay up)"],
            ["CONTENT_GENERATION_MAX_PER_BRAND", "Per-brand generation cap (default 4)"],
            ["TOPIC_DISCOVERY_MAX_PER_BRAND", "Topics queued per brand per day (default 2)"],
            ["EVERGREEN_TOPICS_ENABLED", "AI topic floor when all pools are dry (default true)"],
            ["CONTENT_REFRESH_DAYS / _MAX_PER_RUN", "Refresh staleness (45) and weekly cap (6)"],
            ["SCHEMA_AUTO_PUBLISH_ENABLED", "Self-healing brand schema (default true)"],
            ["STATE_FACTS_GUARD_ENABLED", "Fail drafts that contradict the state fact sheet (default true)"],
            ["FLOW_HEALTH_ENABLED", "10:30 AM stage-by-stage check (default true)"],
            ["POSTING_MONITOR_ENABLED", "3 PM live-site posting check (default true)"],
            ["ADVISOR_ENABLED", "Weekly improvement advisor (default true)"],
            ["AGENT_API_KEY", "Enables the machine-facing Agent API"],
            ["GOOGLE_SERVICE_ACCOUNT_JSON", "Base64 service-account key — GA4 + Search Console"],
            ["WP_APP_PASSWORD_<brand>", "WordPress publishing per brand"],
            ["WP_USERNAME_<brand>", "WP login for the app password (default admin)"],
            ["DISCORD_WEBHOOK_URL", "Published posts + all alerts"],
          ].map(([v, purpose]) => (
            <tr key={v}>
              <td className="px-3.5 py-2.5 align-top">
                <Code>{v}</Code>
              </td>
              <td className="px-3.5 py-2.5 align-top text-muted">{purpose}</td>
            </tr>
          ))}
        </Table>
        <Callout tone="info" tag="Per-brand knobs live in the UI">
          Markets, GA4 property, GSC URL, target queries, logo, and <Em>topic boost</Em> are edited
          per brand in <Em>Brand Settings</Em>, not env vars.
        </Callout>
      </Section>

      {/* Operations */}
      <Section id="operations" eyebrow="Operations" title="Stack, schedules & troubleshooting">
        <H3>Stack</H3>
        <div className="max-w-[68ch] mb-4">
          {[
            ["Backend", <>FastAPI + APScheduler + SQLAlchemy on Azure App Service</>],
            ["Frontend", <>React / TypeScript / Tailwind, served by the same App Service</>],
            [
              "Data / auth",
              <>
                Azure Database for PostgreSQL (<Code>aeo</Code> schema) + shared-password sign-in
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
            ["Citation audit", "Mondays, 5:00 AM"],
            ["Improvement advisor", "Mondays, 7:00 AM"],
            ["Optimization agent (proposals)", "Mondays, 7:30 AM"],
            ["Optimizer GitHub follow-up", "every 15 min, only while a change is in flight"],
            ["Topic discovery", "daily, 8:00 AM"],
            ["Daily content + auto-publish", "daily, 9:00 AM"],
            ["Schema auto-publish (self-heal)", "daily, 10:00 AM"],
            ["Flow-health check", "daily, 10:30 AM"],
            ["Posting monitor (live sites)", "daily, 3:00 PM"],
            ["Content refresh", "Sundays, 6:00 AM"],
            ["Schema validation sweep", "1st, 7:00 AM"],
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
            <Em>Anything looks stopped or silent</Em> — start at <Em>System Health</Em>: it names the
            failing stage and what to do, instead of guessing from logs.
          </li>
          <li>
            <Em>Citations page stuck on an old audit</Em> — the audit was likely killed by a deploy
            mid-run (System Health flags this) or a brand failed; the failure notification carries the
            real provider error. Re-run from the Citations page and don't deploy for ~2 hours.
          </li>
          <li>
            <Em>"Regenerate" / generate does nothing</Em> — usually all 3 generation slots are held by
            stale "generating" drafts; clear them on Content Review.
          </li>
          <li>
            <Em>Only some brands publish</Em> — test that brand's WordPress connection in Brand
            Settings; a revoked application password shows up there in seconds.
          </li>
          <li>
            <Em>GA4 / Search Console metrics all zero</Em> — the Google credential is missing, is an
            OAuth client JSON instead of a service-account key, or lacks access; System Health's
            Integrations stage shows the production state, and each brand needs its GSC property URL
            in Brand Settings.
          </li>
          <li>
            <Em>Schema Health shows "bot-blocked" errors</Em> — the site's protection challenged the
            crawler; a blocked fetch is a measurement failure, not missing schema. Re-run validation.
          </li>
          <li>
            <Em>A live post's links or byline look outdated</Em> — run the content-hygiene backfill
            (<Code>scripts/fix_broken_links.py</Code>, dry-run by default), or let the Sunday refresh
            rotation reach it.
          </li>
        </List>

        <p className="font-mono text-[11px] text-muted/60 mt-8 pt-4 border-t border-border">
          AXXIOM AEO · internal platform documentation · v4 (September 2026) · 6 brands · production
        </p>
      </Section>
    </>
  );
}

const AZ = "-g Axxiom-devs-foundry -n app-axxiom-aeo";

const AZURE_RESOURCES: [string, string, string][] = [
  [
    "App Service",
    "app-axxiom-aeo",
    "Linux, Python 3.12, West Central US. HTTPS only, TLS 1.2+, Always On, health check on /health.",
  ],
  [
    "App Service plan",
    "asp-axxiom-mktg-hub",
    "Basic B2, one instance. Shared with app-axxiom-mktg-hub and app-axxiom-agent-service.",
  ],
  [
    "PostgreSQL flexible server",
    "psql-axxiom-marketing",
    "PostgreSQL 18, East US 2. Database axxiom_hub, schema aeo, mirrored to Microsoft Fabric.",
  ],
  ["Key Vault", "kv-axxiom-marketing", "Shared with the hub. Secrets that belong to AEO alone start with aeo-."],
  [
    "Managed identity",
    "umi-marketing-functions",
    "Also runs the hub's functions, which is why it can read and write the aeo tables but not change their structure.",
  ],
  [
    "AI services",
    "Axxiom-AI",
    "Microsoft Foundry: Claude through ANTHROPIC_BASE_URL, and gpt-image-2. On Azure before the move, unchanged by it.",
  ],
];

const AZURE_SECRETS: [string, string, string?][] = [
  ["ANTHROPIC_API_KEY", "aeo-anthropic-api-key"],
  ["WP_APP_PASSWORD_<BRAND>", "aeo-wp-app-password-<brand>", "one per brand site"],
  ["DISCORD_WEBHOOK_URL", "aeo-discord-webhook-url"],
  ["DISCORD_SCHEMA_WEBHOOK_URL", "aeo-discord-schema-webhook-url"],
  ["SECRET_KEY", "aeo-secret-key"],
  ["DASHBOARD_SESSION_SECRET", "aeo-dashboard-session-secret"],
  ["AGENT_API_KEY", "aeo-agent-api-key", "once the Agent API is turned on"],
  ["OPTIMIZER_GITHUB_TOKEN", "aeo-optimizer-github-token", "once the optimization agent is connected"],
  ["DASHBOARD_PASSWORD", "dashboard-password", "shared with the hub"],
  ["BRIGHT_DATA_API_KEY", "bright-data-api-key"],
  ["GOOGLE_SERVICE_ACCOUNT_JSON", "google-service-account-json"],
  ["AZURE_IMAGE_API_KEY", "azure-image-api-key"],
  ["OPENAI_API_KEY", "openai-api-key"],
];

const AZURE_SETTINGS: [string[], string, string][] = [
  [["AZURE_PG_USER", "AZURE_PG_CLIENT_ID"], "umi-marketing-functions and its client ID", "Connect as the managed identity"],
  [["AZURE_PG_HOST", "AZURE_PG_DATABASE", "DB_SCHEMA"], "the psql-axxiom-marketing host, axxiom_hub, aeo", "Where the data lives"],
  [["DB_MIGRATIONS_ON_STARTUP"], "false", "The app never changes the schema"],
  [["SCHEDULER_ENABLED"], "true", "Runs the jobs; false = dashboard and API only"],
  [["AUTH_PROVIDER"], "password", "Shared-password sign-in"],
  [["DASHBOARD_PASSWORD", "DASHBOARD_SESSION_SECRET"], "vault references", "Sign-in and session signing"],
  [["SCM_DO_BUILD_DURING_DEPLOYMENT"], "true", "Installs the Python requirements during deploy"],
  [["WEBSITES_PORT"], "8000", "The port uvicorn listens on"],
  [["FRONTEND_URL", "PUBLIC_API_URL", "CORS_ORIGINS"], "the app's own address", "Dashboard and API share one origin"],
];

const AZURE_TIMELINE: [string, string][] = [
  ["17 Sep 2026", "Migration planned: mirror the marketing hub's Azure footprint rather than provision new resources."],
  ["21 Sep", "Parallel run live on Azure with the scheduler off. Data copied with 0 mismatches across 16 tables."],
  ["25 Sep", "Zach's decision: drop the Supabase RLS policies, keep the app out of DDL, apply migrations by hand."],
  [
    "29 Sep",
    "Cutover. Railway stopped, final copy verified, password sign-in replaced Supabase Auth, and the scheduler switched on in Azure. The verified state fact sheet shipped in the same build.",
  ],
];

function AzureSetupDocs() {
  return (
    <>
      {/* What runs where */}
      <Section id="azure-overview" eyebrow="Azure Setup" title="Everything runs in Axxiom's Azure">
        <p className="text-base text-muted leading-relaxed max-w-[68ch] mb-4">
          Since the cutover on <Em>29 September 2026</Em>, the platform runs entirely in Axxiom's Azure
          subscription, on the marketing hub's footprint. Railway (API), Netlify (dashboard), and Supabase
          (database and sign-in) are retired — nothing in AEO depends on them.
        </p>
        <P>
          One App Service serves the API and this dashboard from the same address and runs the scheduled
          jobs in the same process. API routes (<Code>/api/*</Code>, <Code>/health</Code>) go to FastAPI;
          every other path loads the dashboard. The API's own reference (Swagger) is at{" "}
          <Code>/api/docs</Code>.
        </P>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3.5 mt-5 mb-6">
          <Card k="Runs" title="app-axxiom-aeo">
            The API, the dashboard, and every scheduled job, in one App Service.
          </Card>
          <Card k="Stores" title="psql-axxiom-marketing">
            All AEO data, in the <Code>aeo</Code> schema of the hub's <Code>axxiom_hub</Code> database.
          </Card>
          <Card k="Keeps secrets" title="kv-axxiom-marketing">
            API keys, WordPress passwords, and the dashboard password, as Key Vault references.
          </Card>
          <Card k="Acts as" title="umi-marketing-functions">
            The managed identity the app uses for the vault and the database. There is no database
            password.
          </Card>
        </div>
        <H3>What it connects to</H3>
        <List>
          <li>
            <Em>The six brand WordPress sites</Em> — publishing, with an application password per site.
          </li>
          <li>
            <Em>Microsoft Foundry</Em> — Claude for writing, gpt-image-2 for images.
          </li>
          <li>
            <Em>Bright Data</Em> — the weekly citation audit across ChatGPT, Gemini, and Perplexity.
          </li>
          <li>
            <Em>Google Analytics 4 and Search Console</Em> — traffic, AI conversions, and search demand.
          </li>
          <li>
            <Em>Discord</Em> — published-post announcements and every alert.
          </li>
        </List>
        <Callout tone="info" tag="Address">
          Dashboard and API: <Code>app-axxiom-aeo.azurewebsites.net</Code>. The old Netlify and Railway
          addresses are retired, so update any bookmarks.
        </Callout>
      </Section>

      {/* Resources */}
      <Section id="azure-resources" eyebrow="Resources" title="What lives where">
        <P>
          Everything sits in resource group <Code>Axxiom-devs-foundry</Code> (subscription Axxiom AI Dev),
          next to the marketing hub.
        </P>
        <Table
          head={
            <>
              <Th>Resource</Th>
              <Th>Name</Th>
              <Th>Notes</Th>
            </>
          }
        >
          {AZURE_RESOURCES.map(([kind, name, notes]) => (
            <tr key={name}>
              <Td tone="ink">{kind}</Td>
              <td className="px-3.5 py-2.5 align-top">
                <Code>{name}</Code>
              </td>
              <Td>{notes}</Td>
            </tr>
          ))}
        </Table>
        <Callout tone="warn" tag="Shared plan">
          The plan also runs the marketing hub and the agent service, so resizing it affects all three.
          Never scale it past one instance: every AEO job would run twice (see Scheduler).
        </Callout>
      </Section>

      {/* Dashboard sign-in */}
      <Section id="azure-signin" eyebrow="Dashboard sign-in" title="One team password, 12-hour sessions">
        <P>
          The dashboard uses the same shared password as the marketing hub: Key Vault secret{" "}
          <Code>dashboard-password</Code>. A correct password sets a signed, HttpOnly session cookie that
          lasts 12 hours, and every <Code>/api</Code> call checks it. There are no individual accounts;
          Supabase Auth is gone.
        </P>
        <List>
          <li>
            <Em>Wrong passwords</Em> — 8 misses from one address within 15 minutes lock that address out for
            15 minutes. The count lives in memory, so restarting the app also clears it.
          </li>
          <li>
            <Em>Changing the password</Em> changes it for the hub too: the hub app and{" "}
            <Code>func-axxiom-mktg-node</Code> read the same secret. Add a new version of{" "}
            <Code>dashboard-password</Code>, then refresh each app (see Identity &amp; secrets).
          </li>
          <li>
            <Em>Signing everyone out</Em> — give <Code>aeo-dashboard-session-secret</Code> a new random value
            and refresh the app. Every open session ends; the hub isn't affected.
          </li>
          <li>
            <Em>Session length</Em> — <Code>DASHBOARD_SESSION_HOURS</Code> (default 12).
          </li>
        </List>
        <Callout tone="info" tag="Machines don't use the password">
          The Agent API has its own key (<Code>X-API-Key</Code> = <Code>AGENT_API_KEY</Code>), and{" "}
          <Code>/health</Code> is public. Neither goes through dashboard sign-in.
        </Callout>
      </Section>

      {/* Identity & secrets */}
      <Section id="azure-secrets" eyebrow="Identity & secrets" title="Key Vault references and a managed identity">
        <P>
          Secret settings on <Code>app-axxiom-aeo</Code> hold a pointer to the vault, never the value. App
          Service resolves each one as <Code>umi-marketing-functions</Code>:
        </P>
        <Cmd>
          {"ANTHROPIC_API_KEY=@Microsoft.KeyVault(SecretUri=https://kv-axxiom-marketing.vault.azure.net/secrets/aeo-anthropic-api-key/)"}
        </Cmd>
        <P>
          In the portal (<Em>app-axxiom-aeo → Settings → Environment variables</Em>) a resolved reference
          shows a green check. One that fails to resolve gets the literal reference text as its value, so
          the app still starts but that integration breaks.
        </P>
        <H3>Secret names</H3>
        <P>
          A vault name is the setting name in lowercase, with <Code>_</Code> as <Code>-</Code>. Secrets that
          belong to AEO alone start with <Code>aeo-</Code>, so rotating one system's secret can't silently
          change the other's.
        </P>
        <Table
          head={
            <>
              <Th>Setting</Th>
              <Th>Vault secret</Th>
            </>
          }
        >
          {AZURE_SECRETS.map(([setting, secret, note]) => (
            <tr key={setting}>
              <td className="px-3.5 py-2.5 align-top">
                <Code>{setting}</Code>
              </td>
              <td className="px-3.5 py-2.5 align-top">
                <Code>{secret}</Code>
                {note && <span className="block text-xs text-muted mt-1">{note}</span>}
              </td>
            </tr>
          ))}
        </Table>
        <H3>Rotating a secret</H3>
        <Cmd>{`read -rs NEW_VALUE   # paste the new value, then press Enter
az keyvault secret set --vault-name kv-axxiom-marketing --name <secret-name> --value "$NEW_VALUE" -o none
az rest --method post --url "https://management.azure.com$(az webapp show ${AZ} --query id -o tsv)/config/configreferences/appsettings/refresh?api-version=2022-03-01"
az webapp restart ${AZ}`}</Cmd>
        <P>
          App Service re-reads vault references on its own about every 24 hours, and right away after any
          settings change. The refresh and restart above apply a rotation now. The hub's apps need the same
          for <Code>dashboard-password</Code>, or they pick it up within a day.
        </P>
        <H3>Database: a token, not a password</H3>
        <P>
          The app signs in to Postgres as <Code>umi-marketing-functions</Code> (<Code>AZURE_PG_USER</Code>,{" "}
          <Code>AZURE_PG_CLIENT_ID</Code>) with a Microsoft Entra token as the password, fetched and renewed
          automatically. With <Code>AZURE_PG_USER</Code> set, <Code>DATABASE_URL</Code> and{" "}
          <Code>DB_PASSWORD</Code> are ignored.
        </P>
        <H3>Turning on the Agent API</H3>
        <P>
          Without <Code>AGENT_API_KEY</Code>, the Agent API endpoints answer 503 “Agent API disabled”. To turn
          it on, store a key and point the setting at it, then copy the same value into the Foundry
          connection <Code>aeo-platform-api</Code> (Foundry portal → project Axxiom-Dev → Connected
          resources).
        </P>
        <Cmd>{`az keyvault secret set --vault-name kv-axxiom-marketing --name aeo-agent-api-key --value "$(openssl rand -hex 32)" -o none
az webapp config appsettings set ${AZ} -o none \\
  --settings "AGENT_API_KEY=@Microsoft.KeyVault(SecretUri=https://kv-axxiom-marketing.vault.azure.net/secrets/aeo-agent-api-key/)"`}</Cmd>
      </Section>

      {/* Optimization agent */}
      <Section id="azure-optimizer" eyebrow="Optimization agent" title="Connecting the Claude Code agent">
        <P>
          Proposals work without any of this. Executing approved code changes needs two credentials and
          one GitHub setting. None of them is an Azure resource.
        </P>
        <H3>1. A GitHub token for the platform</H3>
        <P>
          GitHub → Settings → Developer settings → Fine-grained tokens → Generate. Repository access: only{" "}
          <Code>Luketomeenow/axxiomaeo</Code>. Permissions: <Em>Actions: read and write</Em>,{" "}
          <Em>Pull requests: read</Em>. That lets the platform start the workflow and follow it, and
          nothing else. Note the expiry date, because approvals stop working when it lapses.
        </P>
        <Cmd>{`read -rs GH_TOKEN   # paste the token, then press Enter
az keyvault secret set --vault-name kv-axxiom-marketing --name aeo-optimizer-github-token --value "$GH_TOKEN" -o none
az webapp config appsettings set ${AZ} -o none \\
  --settings "OPTIMIZER_GITHUB_TOKEN=@Microsoft.KeyVault(SecretUri=https://kv-axxiom-marketing.vault.azure.net/secrets/aeo-optimizer-github-token/)"`}</Cmd>
        <H3>2. The Foundry key for the agent</H3>
        <P>
          Claude Code runs in GitHub Actions and reaches Claude through the <Code>axxiom-ai</Code> Foundry
          resource. Add the Foundry key (the same key as <Code>aeo-anthropic-api-key</Code>) as a
          repository secret. <Code>gh</Code> prompts for the value, so it never lands in your shell
          history:
        </P>
        <Cmd>{`gh secret set FOUNDRY_API_KEY --repo Luketomeenow/axxiomaeo
# optional: a different deployment for the agent (default claude-opus-5)
gh variable set OPTIMIZER_MODEL --body claude-opus-5 --repo Luketomeenow/axxiomaeo`}</Cmd>
        <H3>3. Let workflows open pull requests</H3>
        <P>
          Repository → Settings → Actions → General → Workflow permissions → tick{" "}
          <Em>Allow GitHub Actions to create and approve pull requests</Em>.
        </P>
        <H3>4. Put the workflow on the default branch</H3>
        <P>
          GitHub only starts a dispatched workflow that is on the default branch, so{" "}
          <Code>.github/workflows/aeo-optimizer.yml</Code> must be merged to <Code>main</Code>. Until{" "}
          <Code>feat/azure-app-service</Code> is merged to <Code>main</Code>, also set{" "}
          <Code>OPTIMIZER_BASE_BRANCH=feat/azure-app-service</Code>, so the agent starts from the code
          that is actually deployed.
        </P>
        <P>
          When everything is in place, System Health → Optimization agent reads{" "}
          <Em>Claude Code agent connected</Em>.
        </P>
        <Callout tone="warn" tag="Foundry quota">
          The <Code>claude-opus-5</Code> deployment allows about 40K tokens a minute. A Claude Code run
          makes dozens of model calls of 20–60K tokens each, so one run can take half an hour or more and
          a second run at the same time will be rate-limited. Approve one code change at a time, or ask
          Zach for a higher-quota deployment for the agent and set <Code>OPTIMIZER_MODEL</Code> to it.
        </Callout>
      </Section>

      {/* Deploying */}
      <Section id="azure-deploy" eyebrow="Deploying" title="Manual zip deploys from a laptop">
        <P>
          Merging to GitHub doesn't deploy anything. To ship, check out what should go live, sign in with{" "}
          <Code>az login</Code>, and run this from the repo root:
        </P>
        <Cmd>./scripts/azure/package-app.sh --deploy</Cmd>
        <List>
          <li>Builds the dashboard for Azure: same-origin API, password sign-in, no Supabase keys.</li>
          <li>
            Zips <Code>backend/</Code> (app, migrations, scripts, requirements, <Code>startup.sh</Code>) with
            the dashboard build, and uploads it with <Code>az webapp deploy</Code>.
          </li>
          <li>
            The server installs the Python requirements (about 3–5 minutes), then restarts the app with{" "}
            <Code>bash startup.sh</Code>: one uvicorn worker.
          </li>
        </List>
        <P>
          Follow the deploy and the app's logs, then check that <Code>/health</Code> reads <Code>ok</Code>:
        </P>
        <Cmd>{`az webapp log deployment show ${AZ}
az webapp log tail ${AZ}`}</Cmd>
        <Callout tone="warn" tag="Before you deploy">
          The script packages your working tree as it is, uncommitted edits included, so deploy from a clean
          checkout. Apply any new migration first (see Database &amp; migrations). And pick a quiet time: a
          deploy restarts the app and kills whatever job is running. Aim for roughly 11 AM–2:30 PM or after
          4 PM Central, and never Monday 5–8 AM, when the two-hour citation audit and the advisor run.
        </Callout>
      </Section>

      {/* App settings */}
      <Section id="azure-settings" eyebrow="App settings" title="Configuration is App Service settings">
        <P>
          Plain settings hold values; secret settings hold vault references. Change one setting at a time
          with <Code>az</Code>. Every change restarts the app.
        </P>
        <Cmd>{`az webapp config appsettings set ${AZ} --settings AUTO_PUBLISH_ENABLED=false`}</Cmd>
        <H3>Settings that exist because of Azure</H3>
        <Table
          head={
            <>
              <Th>Setting</Th>
              <Th>Value</Th>
              <Th>Why</Th>
            </>
          }
        >
          {AZURE_SETTINGS.map(([names, value, why]) => (
            <tr key={names[0]}>
              <td className="px-3.5 py-2.5 align-top">
                <div className="flex flex-col items-start gap-1">
                  {names.map((n) => (
                    <Code key={n}>{n}</Code>
                  ))}
                </div>
              </td>
              <Td tone="ink">{value}</Td>
              <Td>{why}</Td>
            </tr>
          ))}
        </Table>
        <P>
          Feature switches (auto-publish, caps, monitors) work as before; see{" "}
          <Em>Platform → Configuration</Em>.
        </P>
        <H3>Re-syncing everything</H3>
        <P>
          <Code>scripts/azure/sync-app-settings.sh</Code> rebuilds the full set: the Azure settings above, a
          vault reference for every secret, config values, the startup command, Always On, and the health
          check. It's a dry run unless you pass <Code>--apply</Code>. Secrets missing from the vault, and
          every config value, are read from <Code>ENV_FILE</Code> (default <Code>backend/.env</Code>), so
          make sure that file holds production values.
        </P>
        <Cmd>{`./scripts/azure/sync-app-settings.sh                              # dry run
./scripts/azure/sync-app-settings.sh --apply --live               # settings + missing secrets
./scripts/azure/sync-app-settings.sh --apply --no-secrets --live  # settings only, vault untouched`}</Cmd>
        <Callout tone="warn" tag="Always pass --live">
          Without <Code>--live</Code>, the script writes <Code>SCHEDULER_ENABLED=false</Code> (left over from
          the parallel run) and every scheduled job stops.
        </Callout>
      </Section>

      {/* Database & migrations */}
      <Section
        id="azure-database"
        eyebrow="Database & migrations"
        title="The aeo schema, and why the app never changes it"
      >
        <P>
          All AEO tables live in schema <Code>aeo</Code> of <Code>axxiom_hub</Code> on{" "}
          <Code>psql-axxiom-marketing</Code>, and the marketing hub reads and writes the same tables. They're
          owned by the <Code>dataservices</Code> role (the default role for Luke's and Trey's logins), which
          keeps them mirrored to Fabric.
        </P>
        <H3>Migrations are applied by hand</H3>
        <P>
          The app's identity also runs the hub's functions, so it owns nothing and the app runs no DDL
          (<Code>DB_MIGRATIONS_ON_STARTUP=false</Code>). When a release adds a{" "}
          <Code>backend/migrations/alter_aeo_vN.sql</Code> file, apply it from Cloud Shell before you deploy:
        </P>
        <Cmd>{`curl -sO https://raw.githubusercontent.com/Luketomeenow/axxiomaeo/main/scripts/azure/apply-migrations.sh
bash apply-migrations.sh             # migrations on main
bash apply-migrations.sh my-branch   # or the branch you're about to deploy
AZ_USER=you@axxiomelevator.com bash apply-migrations.sh   # anyone other than Luke`}</Cmd>
        <P>
          Every migration file is idempotent, so the script re-applies the whole set in order, gives the
          app's identity read and write access to any table a migration just created, then runs two checks
          that should both print 0: tables with RLS switched on, and tables the app can't read or write. If
          the second one isn't 0, ask Zach.
        </P>
        <H3>Row-Level Security is off, on purpose</H3>
        <P>
          Supabase's RLS policies came across in the copy and made every table read as empty to the app,
          while <Code>/health</Code> still said connected. Zach approved dropping them on 25 September 2026:
          on Azure, grants do the protecting, and nothing in AEO relied on RLS. If tables ever read as empty
          again, <Code>/health</Code> shows <Code>{'"data": "not visible"'}</Code>; re-run{" "}
          <Code>scripts/azure/drop-supabase-rls.sql</Code> in Cloud Shell.
        </P>
      </Section>

      {/* Scheduler */}
      <Section id="azure-scheduler" eyebrow="Scheduler" title="One instance, one worker — or every job runs twice">
        <P>
          The twelve scheduled jobs (<Em>Platform → Operations</Em>) run inside the web process on APScheduler,
          in America/Chicago time. That's why the plan stays at one instance and <Code>startup.sh</Code>{" "}
          starts a single uvicorn worker: a second copy would write, publish, and audit everything twice.
          Always On keeps the process awake so jobs fire on time.
        </P>
        <List>
          <li>
            <Code>SCHEDULER_ENABLED=false</Code> pauses every job. The dashboard and API keep working.
          </li>
          <li>
            <Code>AUTO_PUBLISH_ENABLED=false</Code> keeps the daily drafts coming but holds each one for
            approval.
          </li>
          <li>
            A deploy or restart kills a running job. System Health flags a citation audit that started but
            never finished; re-run it from the Citations page.
          </li>
        </List>
        <Callout tone="warn" tag="Running the backend locally">
          The scheduler defaults to on. If your local <Code>.env</Code> points at the Azure database
          (<Code>AZURE_PG_USER</Code> set to your login), add <Code>SCHEDULER_ENABLED=false</Code> first, or
          your laptop will run production jobs alongside Azure.
        </Callout>
      </Section>

      {/* Cloud Shell */}
      <Section id="azure-cloudshell" eyebrow="Cloud Shell" title="Database work from Azure Cloud Shell">
        <P>
          Anything that talks to Postgres directly (migrations, data fixes, reports) runs in Azure Cloud
          Shell (Bash), signed in as you. Your default database role there is <Code>dataservices</Code>.
        </P>
        <Cmd>{`PGPASSWORD="$(az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv)" \\
psql "host=psql-axxiom-marketing.postgres.database.azure.com dbname=axxiom_hub user=you@axxiomelevator.com sslmode=require"`}</Cmd>
        <List>
          <li>
            The token is the password and lasts about an hour. If new connections start failing, run the
            command again.
          </li>
          <li>
            Cloud Shell here runs Azure Linux with sudo blocked, and <Code>$HOME</Code> doesn't survive
            between sessions, so download scripts again each time.
          </li>
          <li>
            Its stock <Code>pg_dump</Code> can be older than the server (PostgreSQL 18). If it refuses with
            “server version mismatch”, install a current client into your home directory with{" "}
            <Code>scripts/azure/cloudshell-pg-client.sh</Code>, then run <Code>source ~/pgclient/env.sh</Code>.
          </li>
          <li>
            Read-only reports: <Code>scripts/azure/aeo-value-check.sql</Code> covers published articles,
            citations, AEO traffic, phone calls, and cost.
          </li>
        </List>
      </Section>

      {/* Health & logs */}
      <Section id="azure-monitoring" eyebrow="Health & logs" title="Is it up, and is it working?">
        <P>
          <Code>/health</Code> is public and answers both questions. Healthy looks like this:
        </P>
        <Cmd>{`{"status": "ok", "service": "axxiom-aeo-api", "database": "connected", "data": "visible"}`}</Cmd>
        <P>
          <Code>database</Code> means the app reached Postgres. <Code>data</Code> means it could actually read
          a brand row, which catches RLS, grant, or wrong-schema problems that a plain connection test
          misses. If either fails, <Code>status</Code> reads <Code>degraded</Code>. App Service also probes{" "}
          <Code>/health</Code> to confirm the process is answering.
        </P>
        <Table
          head={
            <>
              <Th>Where</Th>
              <Th>What for</Th>
            </>
          }
        >
          <tr>
            <Td tone="ink">System Health page</Td>
            <Td>Stage-by-stage view of today's pipeline (Platform → System Health &amp; alerts)</Td>
          </tr>
          <tr>
            <td className="px-3.5 py-2.5 align-top">
              <Code>az webapp log tail</Code>
            </td>
            <Td>Live application logs</Td>
          </tr>
          <tr>
            <td className="px-3.5 py-2.5 align-top">
              <Code>az webapp log deployment show</Code>
            </td>
            <Td>Status of the last deploy</Td>
          </tr>
          <tr>
            <Td tone="ink">Portal → Diagnose and solve problems</Td>
            <Td>Crashes, restarts, and Key Vault reference diagnostics</Td>
          </tr>
        </Table>
        <P>
          Both <Code>az</Code> commands take <Code>{AZ}</Code>.
        </P>
      </Section>

      {/* Pause & roll back */}
      <Section id="azure-recovery" eyebrow="Pause & roll back" title="Stopping jobs, and going back to a good build">
        <H3>Stop every job (the dashboard stays up)</H3>
        <Cmd>{`az webapp config appsettings set ${AZ} --settings SCHEDULER_ENABLED=false`}</Cmd>
        <P>
          Set it back to <Code>true</Code> to resume. To keep generating but stop auto-publishing, set{" "}
          <Code>AUTO_PUBLISH_ENABLED=false</Code> instead.
        </P>
        <H3>Roll back the code</H3>
        <Cmd>{`git checkout <last-good-commit>
./scripts/azure/package-app.sh --deploy`}</Cmd>
        <P>
          The Basic plan has no deployment slots, so rolling back means redeploying an older commit.
          Migrations so far only add (nothing is dropped or renamed), so an older build runs on the current
          schema.
        </P>
        <H3>Restart the app</H3>
        <Cmd>{`az webapp restart ${AZ}`}</Cmd>
        <Callout tone="warn" tag="Data restores are server-wide">
          Database backups cover the whole <Code>psql-axxiom-marketing</Code> server, which the hub shares.
          Restoring AEO data from one is a job for Zach, not a routine fix.
        </Callout>
      </Section>

      {/* Troubleshooting */}
      <Section id="azure-troubleshooting" eyebrow="Troubleshooting" title="Symptoms and fixes">
        <List>
          <li>
            <Em>Pages load but every table is empty</Em> — <Code>/health</Code> shows{" "}
            <Code>{'"data": "not visible"'}</Code>. A table has RLS back on, or the app lost its grants; the
            checks at the end of <Code>apply-migrations.sh</Code> say which. <Code>drop-supabase-rls.sql</Code>{" "}
            fixes RLS, and Zach fixes grants.
          </li>
          <li>
            <Em>The database shows disconnected</Em> — <Code>/health</Code> shows{" "}
            <Code>{'"database": "disconnected"'}</Code>: the app can't get a token or reach the server. Check
            the <Code>AZURE_PG_*</Code> settings and that <Code>umi-marketing-functions</Code> is still
            attached (app → Identity). The log tail shows the real error.
          </li>
          <li>
            <Em>The right password is rejected</Em> — <Code>DASHBOARD_PASSWORD</Code> isn't resolving (no
            green check under Environment variables), or the hub's password changed. “Dashboard sign-in is not
            configured” means the setting is missing.
          </li>
          <li>
            <Em>“Too many wrong passwords”</Em> — wait 15 minutes, or restart the app.
          </li>
          <li>
            <Em>An integration suddenly fails</Em> (Claude, WordPress, Discord) — its vault reference stopped
            resolving: the secret was deleted or renamed, or the identity lost Key Vault Secrets User. In the
            portal, <Em>Diagnose and solve problems</Em> has a Key Vault Application Settings Diagnostics
            check.
          </li>
          <li>
            <Em>Nothing ran this morning</Em> — check <Code>SCHEDULER_ENABLED</Code>, then System Health. A
            deploy or restart during a job's slot kills that run.
          </li>
          <li>
            <Em>Agent calls get 503 “Agent API disabled”</Em> — <Code>AGENT_API_KEY</Code> isn't set; see
            Identity &amp; secrets.
          </li>
          <li>
            <Em>The app won't start: “Azure schema 'aeo' has no tables”</Em> — it's pointed at the wrong
            database or schema. Check <Code>AZURE_PG_DATABASE</Code> and <Code>DB_SCHEMA</Code>.
          </li>
          <li>
            <Em>pg_dump says “server version mismatch”</Em> in Cloud Shell — install a current client (see
            Cloud Shell).
          </li>
        </List>
      </Section>

      {/* Migration record */}
      <Section id="azure-history" eyebrow="Migration record" title="How AEO moved to Azure">
        <Table
          head={
            <>
              <Th>Date</Th>
              <Th>What happened</Th>
            </>
          }
        >
          {AZURE_TIMELINE.map(([date, what]) => (
            <tr key={date}>
              <td className="px-3.5 py-2.5 align-top text-ink whitespace-nowrap tabular-nums">{date}</td>
              <Td>{what}</Td>
            </tr>
          ))}
        </Table>
        <H3>Why it's built this way</H3>
        <List>
          <li>
            <Em>Same database as the hub</Em> — the hub already reads and writes the <Code>aeo</Code> tables.
          </li>
          <li>
            <Em>The hub's plan, not a new one</Em> — nothing new to provision or approve.
          </li>
          <li>
            <Em>An identity that can use the tables but not restructure them</Em> — it also runs the hub's
            functions, and owner rights would reach all of <Code>axxiom_hub</Code>.
          </li>
          <li>
            <Em>A shared password, like the hub</Em> — it removed the last Supabase dependency without new
            sign-in infrastructure.
          </li>
        </List>
        <P>
          The Supabase copy of the <Code>aeo</Code> schema is frozen at the cutover, and AEO no longer reads
          it.
        </P>
        <p className="font-mono text-[11px] text-muted/60 mt-8 pt-4 border-t border-border">
          AXXIOM AEO · Azure setup · September 2026 · app-axxiom-aeo · production
        </p>
      </Section>
    </>
  );
}

export function DocumentationPage() {
  const [params] = useSearchParams();
  const tab: TabId = params.get("tab") === "azure" ? "azure" : "platform";
  const groups = TAB_GROUPS[tab];
  const [active, setActive] = useState<string>(groups[0].items[0].id);
  const [showTop, setShowTop] = useState(false);
  // Right after a tab switch, `active` can still name a section of the old tab.
  const activeId = groups.some((g) => g.items.some((s) => s.id === active)) ? active : groups[0].items[0].id;

  useEffect(() => {
    // Each tab opens at the top, on its first section, and tracks only its own sections.
    const sections = TAB_GROUPS[tab].flatMap((g) => g.items);
    setActive(sections[0].id);
    const container = document.getElementById("docs-root")?.closest("main");
    (container ?? window).scrollTo({ top: 0 });

    const els = sections.map((s) => document.getElementById(s.id)).filter((el): el is HTMLElement => Boolean(el));
    if (!("IntersectionObserver" in window) || els.length === 0) return;
    const visible = new Set<string>();
    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) visible.add(e.target.id);
          else visible.delete(e.target.id);
        }
        const first = sections.find((s) => visible.has(s.id));
        if (first) setActive(first.id);
      },
      { rootMargin: "-10% 0px -70% 0px", threshold: 0 }
    );
    els.forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, [tab]);

  useEffect(() => {
    // The app shell's <main> is the scroll container, not the window.
    const container = document.getElementById("docs-root")?.closest("main");
    const target: HTMLElement | Window = container ?? window;
    const onScroll = () =>
      setShowTop((container ? container.scrollTop : window.scrollY) > 600);
    target.addEventListener("scroll", onScroll, { passive: true });
    return () => target.removeEventListener("scroll", onScroll);
  }, []);

  const toTop = () => {
    const container = document.getElementById("docs-root")?.closest("main");
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    (container ?? window).scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
  };

  const jump = (e: MouseEvent | null, id: string) => {
    e?.preventDefault();
    const el = document.getElementById(id);
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    setActive(id);
  };

  return (
    <div id="docs-root" className="max-w-6xl">
      {/* Tabs */}
      <nav aria-label="Documentation" className="flex gap-1 border-b border-border mb-8">
        {TABS.map((t) => {
          const isActive = t.id === tab;
          return (
            <Link
              key={t.id}
              to={t.to}
              aria-current={isActive ? "page" : undefined}
              className={`-mb-px border-b-2 px-3.5 py-2.5 text-sm font-medium transition-colors ${
                isActive ? "border-cyan text-cyan" : "border-transparent text-muted hover:text-ink"
              }`}
            >
              {t.label}
            </Link>
          );
        })}
      </nav>

      <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_230px] lg:gap-12">
        {/* Mobile section jump */}
        <div className="lg:hidden sticky top-0 z-10 -mx-1 px-1 py-2 bg-void/95 backdrop-blur border-b border-border mb-4">
          <select
            value={activeId}
            onChange={(e) => jump(null, e.target.value)}
            className="w-full bg-panel border border-border rounded-md px-3 py-2 text-sm text-ink focus:outline-none focus:border-cyan/50"
            aria-label="Jump to section"
          >
            {groups.map((g) => (
              <optgroup key={g.group} label={g.group}>
                {g.items.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>

        <main className="min-w-0 space-y-0">{tab === "azure" ? <AzureSetupDocs /> : <PlatformDocs />}</main>

        {/* Sticky "On this page" rail */}
        <aside className="hidden lg:block">
          <div className="sticky top-0 max-h-screen overflow-y-auto pb-8">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted px-3 pt-1 pb-2.5">
              On this page
            </p>
            {groups.map((g) => (
              <div key={g.group} className="mb-3">
                <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-muted/60 px-3 pb-1">
                  {g.group}
                </p>
                <ol>
                  {g.items.map((s) => {
                    const isActive = activeId === s.id;
                    return (
                      <li key={s.id}>
                        <a
                          href={`#${s.id}`}
                          onClick={(e) => jump(e, s.id)}
                          className={`block px-3 py-1 text-[13px] border-l-2 transition-colors ${
                            isActive
                              ? "border-cyan text-cyan"
                              : "border-transparent text-muted hover:text-ink"
                          }`}
                        >
                          {s.label}
                        </a>
                      </li>
                    );
                  })}
                </ol>
              </div>
            ))}
          </div>
        </aside>
      </div>

      {/* Back to top */}
      {showTop && (
        <button
          type="button"
          onClick={toTop}
          className="fixed bottom-6 right-6 z-20 w-10 h-10 rounded-full bg-panel border border-border text-ink hover:border-cyan hover:text-cyan shadow-lg"
          aria-label="Back to top"
          title="Back to top"
        >
          ↑
        </button>
      )}
    </div>
  );
}
