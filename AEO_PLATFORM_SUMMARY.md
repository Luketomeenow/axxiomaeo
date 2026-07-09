# Axxiom AEO Platform — Overall Summary

*A plain-English overview of what this system is, what it does, and where it stands. Written to be handed to someone building a presentation from it — no technical background needed to read this.*

---

## What This Platform Is

Axxiom Elevator runs a network of brand websites — AmeriTex, Arizona Elevator Solutions, Liftech, Quality Elevator, and Axxiom Elevator Florida. This platform is the automated system that keeps those websites full of fresh, useful content and tracks whether AI tools like ChatGPT, Gemini, and Perplexity actually mention these brands when people ask elevator-related questions.

In short, it does four things:
1. **Writes articles** for each brand's website using AI, based on real questions people are searching for and real gaps where the brand is being ignored.
2. **Publishes them automatically** once each draft passes quality checks — with the team monitoring what goes out rather than hand-approving every post (and a switch to put approval back if ever needed).
3. **Watches whether AI engines are citing these brands** — asking the AI tools real customer questions and recording who gets mentioned and who loses to a competitor.
4. **Turns that tracking into action** — surfacing "here's exactly what to publish next to win a query you're losing," which a person approves in one click.

## Why This Matters

Search is changing. People increasingly ask ChatGPT or Perplexity a question instead of typing it into Google. If those AI tools have never heard of "AmeriTex Elevator" or "Quality Elevator," they simply won't recommend them — no matter how good the company is.

This is called **Answer Engine Optimization (AEO)** — the same idea as SEO (getting found on Google), but for AI assistants. The goal is that when someone asks an AI "who does emergency elevator repair in Pompano Beach?" or "how much does elevator modernization cost?", one of these five brands comes up — instead of a competitor.

## How It Works, Start to Finish

1. **The system figures out what to write about.** Every day it looks at two signals: what people are searching for right now (rising demand), and where AI engines currently ignore the brand or cite a competitor instead (a visibility gap). It picks the most valuable topic.
2. **AI writes a draft** — a full article formatted to answer the question directly and clearly, the way AI engines prefer, with relevant AI-generated images and a byline from a real, named team member.
3. **The draft is quality-checked automatically** (does it actually answer the question, is it long enough, is the technical markup valid, do the images have proper descriptions).
4. **It publishes to the brand's website** once it passes — along with the behind-the-scenes markup that helps search engines and AI tools understand exactly what the page is about. A link to every published post is posted to a Discord channel so the team can monitor what went live.
5. **The system checks its own work.** On a schedule, it asks the AI engines real questions and records whether each brand is mentioned, cited with a link, or beaten by a named competitor — building a track record over time.
6. **It recommends the next move.** From that tracking, it produces a ranked list of "you're invisible here and a competitor is winning — publish this to fix it," which a person approves to set in motion.

## What the Team Sees (the Dashboard)

- **Dashboard** — the headline scorecard: citation share, AI-visibility, share of voice vs competitors, and traffic.
- **Recommendations** — the ranked "what to do next" list. Each item explains *why* (which engines ignore the brand, which competitor is winning) and turns into a published article with one **Approve** click.
- **Citations** — the AI-visibility monitor: which brands are cited on which engines, for which questions, and who beats them. Includes an **AI Recommendations** tab where the system reads the whole audit and writes a plain-English "here's what's working, what's at risk, and what to do."
- **Reports** — monthly snapshots with **month-over-month trends**, an AI-written executive summary, and one-click **CSV export / print-to-PDF** for sharing.
- **Content Review & Published** — every draft and everything that's gone live.
- **Schema** — the structured data that makes pages machine-readable; changes here are human-approved before deploying.

## AI Visibility Tracking — Now Live

The platform runs automated checks that literally ask the AI engines (ChatGPT, Gemini, and Perplexity) real customer questions and record whether each brand is mentioned, cited, or beaten by a named competitor. This is the same kind of tool sold commercially by companies like Peec.ai — but self-hosted through **Bright Data**, which is both more capable and meaningfully cheaper to run than a recurring SaaS subscription.

**This is now connected and producing real data across all three engines.** The first audits give us a genuine baseline: the brands *are* being cited on some questions, but are invisible on many others, and specific competitors (for example, **TK Elevator** on Perplexity for a Pompano Beach repair query) are winning answers we want. Critically, the system now detects **local competitors by name**, not just the big national manufacturers — so the gaps it reports reflect who's actually beating us in each market. That baseline is exactly what feeds the Recommendations list.

## What's Been Built and Shipped

Most of the platform described above is **live in production today.** Highlights of the recent wave of work:

- **Automatic daily publishing.** The system moved from a manual, once-a-week process to a self-directing daily one — every brand gets guaranteed daily attention, content publishes automatically once it passes quality checks, and every post is announced to a Discord channel for monitoring. A single setting restores manual "approve-before-publish" if ever wanted.
- **Automated topic selection.** No one has to decide what to write about anymore — the system alternates between trending search demand and AI-visibility gaps, and a person can also trigger it on demand.
- **The Recommendations inbox** — the "hit approve and it acts" surface: live-computed from real citation gaps, one click queues, writes, and publishes the fix.
- **Live AI-visibility tracking** (Bright Data) across ChatGPT, Gemini, and Perplexity, including local-competitor detection.
- **A richer Citations page** — paginated tables, built-in explanations of every metric, and an AI analysis tab.
- **A real Reports hub** — history, month-over-month trend charts, an AI executive summary, and CSV/PDF export (previously it was a single static snapshot).
- **Better article images** — a premium image generator (fal.ai's Flux 2 Pro) plus a rewrite of the image instructions so pictures are varied and on-topic instead of repetitive.
- **Real, named authors per brand** with technician credentials, and a fix so posts are credited to the intended author rather than a developer account.
- **Corrected brand records** (Axxiom Elevator Florida now points at its own Pompano Beach/Sarasota site, not the corporate domain) and a **streamlined five-brand roster** (Motion, Evolution, and IronHawk retired from the system).
- **Reliability & correctness fixes:** a dashboard crash, a login/security gap, inaccurate AI-traffic counting, placeholder text ("[BRAND_PHONE]") leaking onto live pages, and empty auto-generated markup — all found and fixed. Comment/trackback spam is turned off on every auto-published post.

## Where Things Stand Right Now

- **Live in production:** the content engine, automatic daily publishing with Discord monitoring, the Recommendations inbox, live Bright Data visibility tracking, local-competitor detection, and the upgraded Citations page. All five brands' website connections are verified and crediting the right authors.
- **In final review (small, low-risk):** the new Reports hub, and a fix for a reporting quirk where the citation-share number could read 0% even when the tracker clearly had data (it was filtering by calendar month in a way the charts didn't — now corrected).
- **First real visibility baseline captured** — the brands are cited on some queries and invisible on many, which is exactly the starting point AEO work is meant to move.

## What We Still Need From the Business Side

1. **Connect Google Search Console** for each brand — unlocks real "what's trending in search" data (until then, the system uses a reasonable substitute automatically).
2. **Add the premium-image key** (fal.ai) to switch on the best image quality — until then it falls back to the standard generator, which still works.
3. **Decide on posting volume** — currently one article per brand per day; can go to two per brand per day (the original goal) once we're comfortable with quality and cadence.
4. **Keep an eye on the monitoring channel** — since publishing is now automatic, the Discord feed and the Citations dashboard are how the team stays in the loop.

## The Bottom Line

This platform automates the unglamorous, repetitive work of keeping five brand websites visible to both traditional search and the new wave of AI assistants — deciding what to write from real demand and real competitive gaps, writing and publishing it, tagging it for machines to understand, and continuously measuring whether it's working. It has moved from a manual, once-a-week process to a daily, self-directing one that now runs live and produces its own "what to do next." The AI-visibility tracking that most competitors pay a monthly SaaS fee for is running in-house, and it's already showing where these brands win and where competitors are beating them — which is precisely the map this whole effort exists to act on.
