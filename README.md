# Signal Stack
Research a company, interview its operator and monitor approved public sources. The dashboard keeps source passages, founder context, collection history, analysis and executive briefs in one workspace.

## Run locally
Use Python 3.11. Create and activate a virtual environment, run `pip install -r requirements.txt`, and copy .env.example to .env. Set GEMINI_API_KEY, GEMINI_MODEL and TAVILY_API_KEY for free-tier projects. Run `python -m uvicorn app:app --port 8076` from this directory and open http://127.0.0.1:8076. SQLite tables and indexes are created automatically by store_db.init. Keep the process running for the local scheduler.

## Reproduce the workflow
Enter a company name and full URL. Refresh Profile after research completes. Answer the current interview question, skip sensitive details with a blank answer, or edit an earlier response. Discover sources under Signal Stack, inspect their evidence and terms, approve or remove them, and check approved sources. Upload authorised CSV, Excel, PDF or text under Internal. Only enable AI analysis of an upload if you have permission to send its content to Google. Run history records failures and duplicate counts. Generate a Monday brief, inspect its sources, track actions, and export HTML. Edit an answer and reassess sources to review changed relevance.

`python demo.py` starts public research for MeetUniversity, Ghost and Fairphone. These names are demonstration inputs only. The normal workflow accepts other companies.

## Technical design
FastAPI serves Jinja HTML forms and a Python job layer. SQLite is the local store. Setting DATABASE_URL selects PostgreSQL. A per-company record index stores company profiles, interview questions and answers, source candidates, documents, monitoring attempts, evidence-backed signals, actions, audit results and historical report snapshots. Schema is in store_db.py.

Tavily basic search finds candidate links using company-specific queries. Flash-Lite evaluates candidates against public research and operator context. HTTP requests, HTML extraction, feed parsing and PDF parsing collect original evidence. Robots checks, per-domain pacing, response sizes and bounded redirects constrain collection. Operators review website terms before approval. Exact content fingerprints identify unchanged content and syndicated copies. Source history records failed checks and duplicate counts. A first observation establishes a baseline.

Gemini receives bounded excerpts. A signal must reference a collected document and contain a literal quote present in the document. Quote matching checks provenance; the operator should review whether the quote supports the complete conclusion. Impact, urgency, relevance, source credibility, novelty and recency each contribute 1–5 to rank. Evidence strength is separate. Missing dates stay unknown. Briefs cover material discovered in the previous seven days and show limitations when evidence is sparse.

Weekly briefs and monthly audits have independent due conditions. Local APScheduler checks the database every minute. Enable automation in company settings. The deployment workflow checks due jobs at minutes 17 and 47 of each hour. GitHub can delay scheduled workflows. Monitor and source-refresh intervals are configurable. Leave EXTERNAL_SCHEDULER unset for local scheduling.

## Deployment and costs
render.yaml defines a free Render web service; supply an external PostgreSQL URL, server-side API keys and an app password (user name founder). Configure the same database and API keys in the GitHub repository Actions secrets. Use only free plans and keep billing disabled. Hosted scheduling requires Actions enabled on the default branch. The local database is ignored by Git and does not automatically transfer to a hosted database.

Python libraries are open source. Gemini free-tier model availability, request and token quotas vary by project. Tavily's free plan includes 1,000 monthly credits; basic searches consume the allowance. Render free web services sleep and use ephemeral disk, so hosted records belong in PostgreSQL. A free Neon database has storage, compute and network limits. A public repository can use standard GitHub-hosted Actions runners free within applicable terms. Avoid confidential uploads on an evaluator instance. Do not commit .env, local databases or internal files.

Provider documentation: [Gemini](https://ai.google.dev/gemini-api/docs/pricing), [Tavily](https://www.tavily.com/pricing), [Render](https://render.com/docs/free), [Neon](https://neon.com/pricing), [Actions](https://docs.github.com/en/actions).

