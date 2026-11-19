# Signal Stack — Company Intelligence & Executive Briefing Engine

An evidence-first FastAPI application for the EDXSO AI Engineer Intern assignment. Research an arbitrary company, conduct a ten-question adaptive interview, discover and approve primary/public intelligence sources, monitor source changes, assess business implications and generate a traceable Monday Morning Brief. Three **historical** sample company datasets are provided: MeetUniversity, Ghost and Fairphone.

The MeetUniversity demo includes ten interview responses using labeled demonstration inputs and the confidential skip option. Its competitor profiles link to official sites. Seven were approved after a successful crawler check, and three remain proposed because their sites could not be crawled. Sample reports cover the reporting dates printed in each report.

## Run locally (Python 3.11)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python seed_demo.py --seed
python -m uvicorn app:app --host 127.0.0.1 --port 8076
```

Visit <http://127.0.0.1:8076>. If you use the **private development archive**, it already contains an unchanged `.env` and your existing `data/signals.db` with the three populated companies; seeding is idempotent. For a freshly cloned **GitHub-safe archive**, create a local `.env` using `.env.example`. Set `GEMINI_API_KEY`, `GEMINI_MODEL`, `TAVILY_API_KEY`; optionally `APP_PASSWORD`. Do **not** commit `.env`. AI calls and live discovery require API access; they are not simulated offline.

## Complete one company workflow

1. Open MeetUniversity and review the verified-vs-unverified homepage research in **Profile & interview**. Answer each question individually, or leave it empty to skip. The system uses previous answers and uncovered topics when generating the next question. Editing a previous answer creates a revision record.
2. Record an operator-provided priority or geography change in **Company context**. The audit shows the before/after context, changed scores, and explicit deprioritization matches. It searches for new candidates related to the updated priorities and leaves source approval to the operator.
3. Run **Discover candidate sources**. Inspect competitor profile evidence, official website ownership and terms; approve appropriate competitor pricing/news/product pages. Include customer discussions, geographically appropriate official market/regulatory sources, and authorised internal files.
4. Select **Monitor approved sources**. First crawls establish a baseline. Independently dated recent publications can be assessed on discovery; changes to undated existing pages can be assessed as *observed changes*. Repeated documents are deduplicated by exact content fingerprint; see each source's history.
5. Use **Intelligence feed** for evidence/implications and a per-signal editorial review status. Run **Generate a new brief**, then review the evidence-linked ten sections, comparison with the preceding report, action owners and status tracking. Insufficient evidence is stated, not filled with generated news.
6. Repeat with Ghost and Fairphone; try a fourth previously unseen company. Generate a monthly audit and inspect its health recommendations. For internal CSV/XLS/XLSX/PDF/TXT files, AI analysis requires explicit consent to share extracted contents with Gemini.

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for step-by-step Render + free PostgreSQL + scheduled GitHub Actions setup. The default `render.yaml` is an example and does **not** deploy anything by itself. Hosted scheduled workflows require Actions permissions and shared database secrets. `.env` is for local use only; secrets must be entered into host configuration. Render's free ephemeral disk must not hold the persistent database. A basic-auth app password is mandatory on Render.

## Architecture and requirements

- [ARCHITECTURE.md](ARCHITECTURE.md) — design, confidence/provenance rules, reliability and monitoring (short technical document).
- [DEPLOYMENT.md](DEPLOYMENT.md) — live hosting and scheduling.
- [DEMO_SCRIPT.md](DEMO_SCRIPT.md) — suggested 5–10 minute recording outline and truthful claim checklist.
- [COSTS.md](COSTS.md) — free-tier choices and limitations.
- [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md) — remaining real-world verification and submission items.
- `store_db.py` — SQLite/PostgreSQL JSON record store with durable IDs and history.
- `engine.py`, `collector.py`, `open_sources.py`, `intelligence.py` — discovery, crawling, ranking and analysis.
- `jobs.py`, `worker.py`, `.github/workflows/` — independent scheduled jobs with saved errors/retries.
- `samples/demo_snapshot.json.gz` — three-company **historical public-source** bootstrap; never includes `.env` or internal uploads. Loaded idempotently with `python seed_demo.py --seed` or `SEED_DEMO_ON_START=1`.
- `samples/MeetUniversity.html`, `Ghost.html`, `Fairphone.html` — legacy historical HTML snapshots preserved for provenance. The latest generated briefs use the new validation rules.

## Verification

```bash
python test_pipeline.py
python test_reliability.py
python -m compileall -q .
```

The pipeline suite uses isolated local fixtures, mocked AI/public API calls and makes no claim to validate live external services. See [test-evidence/verification.txt](test-evidence/verification.txt) for the most recent local results. The app can be tested with `uvicorn` plus a browser; the core routes were also exercised through FastAPI TestClient against the preserved demonstration database.

## Limitations before submission

See the [submission checklist](SUBMISSION_CHECKLIST.md) for the remaining hosted scheduling, reporting, and recording checks. The included MeetUniversity responses are demonstration operator inputs. Live runs depend on provider availability, quotas, and crawl permissions.
