# Deployment — Vercel, Render and PostgreSQL

Render runs FastAPI and the monitoring jobs it starts. Import the repository root into Vercel with the **Other** framework preset. Vercel serves `vercel/public`, and its rewrite forwards app requests to Render with private, non-cacheable responses. For a different backend, update the destination in `vercel.json`.

1. **GitHub repository.** Push the source code and public demo seed. Keep local `.env` files, databases, virtual environments, and backups out of the repository. The supplied `render.yaml` describes the backend.
2. **Free PostgreSQL:** Provision a persistent PostgreSQL database on a provider with a genuinely free tier. Copy its private connection string (including `sslmode=require` if the provider requires it). This project supports `DATABASE_URL` using `psycopg2`. Do not use Render's ephemeral disk for SQLite in production.
3. **Render web service:** Import the repository as a new blueprint or web service using `render.yaml` and select an available free plan. Set `DATABASE_URL`, `GEMINI_API_KEY` and `TAVILY_API_KEY` as **private dashboard environment variables**; use the `GEMINI_MODEL` that is free and available to your own key. `APP_PASSWORD` should be a strong generated secret. `EXTERNAL_SCHEDULER=1` prevents duplicate local scheduling. `SEED_DEMO_ON_START=1` loads the three existing historical demo datasets exactly once (idempotent).
4. **Start command:** `python seed_demo.py && uvicorn app:app --host 0.0.0.0 --port $PORT`. On startup, visit the assigned HTTPS URL and log in with HTTP Basic username `founder` and the generated `APP_PASSWORD`. Check that MeetUniversity, Ghost and Fairphone appear with historical research and source history. Real API calls still require your keys and provider quotas.
5. **Scheduled worker:** In the same repository's GitHub Actions **Secrets**, add `DATABASE_URL`, `GEMINI_API_KEY`, `TAVILY_API_KEY`. Configure Actions on the default branch. The included `.github/workflows/monitor.yml` calls `python worker.py` twice per hour; the database-backed due logic controls whether each company needs a weekly brief, monthly audit, monitoring or discovery. Test once with **Run workflow** and inspect the dashboard `Activity & audits` view. **Never store credentials directly in workflow YAML.**
6. **Manual smoke checks:** In the hosted UI, try an interview answer, add/approve a safe public source, execute monitoring, confirm a direct link and literal quotation in a source signal, trigger a brief and an audit, and restart the web service to verify records persist. Review date and source-health status; avoid publicising confidential uploaded content.

## Common issues

- **Blank website after deploy:** Look at Render logs; verify `DATABASE_URL` and dependency installation. A free instance can take time to wake from sleep.
- **503 on Render:** `APP_PASSWORD` must be set, as the application explicitly refuses a public Render deployment with no login password.
- **Reports without latest developments:** Expected when only archived sources/old articles are available. Approve current primary-source feeds and wait for genuinely new publications or observed changes; do not backdate events.
- **No automation:** Check company Settings → enable automation, shared database credentials in Actions, workflow permissions and the Actions run history. The scheduler has its own retry logic but cannot operate with disabled workflows.
- **Missing historical samples:** Confirm `samples/demo_snapshot.json.gz` is in the repository and run `python seed_demo.py --seed` against the target database.
- **External API errors:** Check free-tier quotas, permitted model ID and provider terms. API keys from local `.env` do not automatically appear in Render or GitHub.

Do not make the repository public with the **private** ZIP. The private ZIP has the `.env` file intentionally kept byte-for-byte unchanged at the owner's request.
