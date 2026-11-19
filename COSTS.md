# Cost statement and operating constraints

This project is designed for genuinely free/open-source tooling, not paid scraping or paid model APIs.

- **FastAPI, Jinja, Python, Requests, Beautiful Soup, feedparser, openpyxl, pypdf:** open-source runtime dependencies. Check each package licence before redistribution.
- **Gemini API:** use a model and project explicitly eligible for a current free tier. Quotas, free-tier data-use terms, and model availability may change; do not assume an arbitrary model ID is free. The configured model is controlled by `GEMINI_MODEL`.
- **Tavily basic search:** use only included free search credits, and stop/limit discovery when exhausted. Check the account's actual allowance before running bulk discovery.
- **Stack Exchange API and applicable public-government endpoints:** respect each API's published limits, licence and attribution requirements. Public website crawling respects access controls and robots policies.
- **Render free service:** can sleep and has ephemeral filesystem storage. It needs externally persisted PostgreSQL and a separate scheduled worker for reliable monitoring.
- **Free PostgreSQL, e.g. Neon:** limited storage/compute/network resources; the actual plan should be confirmed before use.
- **GitHub Actions:** scheduled workflows can be delayed or disabled; hosted execution is subject to the account's runner policies and quotas.

No monthly paid-cost estimate is asserted because service terms, eligibility and actual usage vary. Configure spend limits; never enable a paid subscription without consent. Internal documents should only be uploaded if the uploader authorises their processing and the model provider's data terms are acceptable.
