# Technical Design — Signal Stack

*EDXSO Assignment 1. Engineering note designed to fit within five printed pages.*

## 1. Product and data lifecycle

The FastAPI/Jinja web interface has seven areas: overview, research/profile and one-at-a-time interview, source and competitor management, evidence-linked feed with editorial review, ten-part Monday briefing, run/audit history and settings. For any user-supplied company URL, initial public research captures the original homepage text and asks Gemini to identify products, segments, positioning, company claims, assumptions and unknowns. Research results are not treated as externally verified truth.

Company records are stored in SQLite locally or PostgreSQL with `DATABASE_URL` in production. The generic records table stores JSON documents keyed by globally unique IDs, company ID, kind and timestamp. Kinds include company, question, revision, source, document, crawl, signal, editorial_review, run, audit, action, upload and brief. Signals carry a literal evidence quote, direct link, observation/discovery dates and source metadata. Historical reports are snapshots, not dynamically changing views. New companies require no per-company code changes.

## 2. Adaptive interviewing

`engine.next_question()` considers the researched company, operator context, previous founder answers, skipped confidential topics and ten uncovered **areas**. The LLM chooses the highest-value uncovered area and generates just one concise question rather than using ten static questions. It refuses near-duplicates, compound questions and unsupported factual premises. The server stores the answer before requesting the next question. Updates remain editable and produce revisions; edits to overall company context trigger a source relevance audit. Private revenue or other confidential information may be skipped. No generated sample answers are passed off as founders' words.

## 3. Source and competitor discovery

Tavily basic search suggests pages using company-, industry- and geography-specific AI-generated queries. Operators must approve sources before monitoring. A separate competitor discovery stage first extracts evidence-backed provider names from search snippets, then searches again for each provider's own primary website and rejects known listicles, forums and social aggregators as competitor URLs. No competitor-name arrays are embedded in code. Candidate ownership remains subject to operator approval, because search snippets alone do not verify site ownership. The source manager lists reasons, evidence, status, version history and duplicates.

Market discovery infers the target country/market from actual research/answers; it calls GOV.UK only when the UK is indicated. Stack Exchange's official API is used for appropriately recent customer questions, respecting licences and attribution. Other public sources go through the restricted crawler. Internal inputs are optional authorised CSV, XLS, XLSX, PDF and TXT uploads. Parsing keeps labelled page/row evidence, splits long materials into bounded chunks, and only shares text with the model upon explicit user consent.

## 4. Safe collection, baselines and dates

`collector.py` restricts outbound HTTP(S) collection: public address validation, robots policy, per-domain pacing, size cap, redirect cap and response timeouts. There is no login or paywall bypass. For Stack Exchange question URLs, the public API is used instead of scraping; the monthly audit uses that same route so it cannot misreport the HTML robots endpoint as a source failure.

`engine.monitor()` saves deduplicated source observations by a SHA-256 content fingerprint. First-seen old/undated content becomes an **historical baseline**; new independently dated material within the last seven days may enter analysis; an undated page observed changing after a prior snapshot is labelled an **observed change** rather than a dated launch. Old publications discovered today do not enter current-week briefings. When exact publication/event dates are unavailable, the report explicitly says so. Monitoring failures and inactive sources stay visible in crawl/audit history.

## 5. Analysis, verification and ranking

Gemini receives company context, source inclusion reason, published timestamps and bounded collected excerpts. AI-proposed signals are **discarded** if their literal quotation cannot be found in the recorded document. The event date must match evidence or document publication metadata; otherwise it is unknown. The model may propose strategic relevance, impact, urgency, novelty and implications, which remain interpretations. The application computes source credibility through deterministic provenance rules: official government 5, academic 4, ordinary corporate/publication 3, forums or known aggregators 2; internal uploads are labelled as operator-provided rather than independently verified. Evidence strength separately accounts for quote match/length, date metadata and verification status.

Ranking is a weighted, explainable score: `3×relevance + 3×impact + 2×urgency + 2×credibility + 2×recency + 1×novelty`, with each component ranging 1–5 and a maximum of 65. Evidence strength is displayed separately; neither AI confidence nor the source score proves truth. Editorial review can approve, flag or reject a signal. Source status and review history are preserved.

## 6. CEO brief and automation

A Monday brief includes the five leading developments, customer/competitor/market/internal sections, evidence-backed opportunities, risks with impacts, owner-linked weekly actions, what to watch and a full dated source appendix. The synthesis pass can reference **only existing signal IDs**; the server validates all returned IDs. The report includes changed signal IDs and category counts relative to the preceding brief. If evidence supports fewer than three opportunities, it explicitly states that shortfall instead of manufacturing recommendations. A synthesis service error produces a saved evidence-level report with a recorded limitation.

Weekly briefs and monthly source audits are independent jobs. The server runs a single 60-second periodic due check locally. In hosting, the GitHub Actions cron dispatches `worker.py` on the shared PostgreSQL database; each company's configured zone, Monday briefing time, source-refresh and audit interval is respected. Jobs are recorded with running/completed/failed/partial-failure status, 30-minute retry backoff and interrupted-run recovery. `EXTERNAL_SCHEDULER=1` disables the local loop to avoid accidental duplicate scheduler processes in hosting.

## 7. Reproducibility, controls and tradeoffs

Local SQLite is easy to run, but hosting requires free-tier PostgreSQL for persistence. Render may sleep, so the GitHub cron scheduler can run separately; GitHub may delay cron delivery. HTTP Basic auth (configured `APP_PASSWORD`) prevents an openly accessible demonstration from exposing operator information. Do not store private information in a public snapshot. The included public `samples/demo_snapshot.json.gz` preserves only original historical public-source records; it is seeded idempotently and does not count as current changes. Free AI/search API quotas may limit runs. The system cannot guarantee publisher truth, license compatibility or full coverage of the internet; operator approval and human review remain necessary.

The offline tests cover baseline dates, quotation verification, ten-question interviewing, credibility, document chunking, scheduling, and source auditing. A context change screens sources for explicit deprioritization and uses a targeted Tavily query to propose sources for the updated focus. Audit results persist if discovery fails. The MeetUniversity demonstration uses labeled public-source responses, and full submission checks are tracked in the submission checklist.
