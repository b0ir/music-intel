# CLAUDE.md

## Git rules

- Use conventional commit messages.
- Always ask before committing. Never commit without explicit user approval.
- Never push to GitHub without explicit user authorization.

## Dev environment

- Python 3.14, venv at `.venv/`. Use `.venv/bin/python3`, not `python`.
- Install: `pip install -e ".[dev]"` (editable + dev extras)
- App runs at `http://localhost:7860`

## Verify the app compiles

Always run this after editing `app.py` or any imported module:

```bash
.venv/bin/python3 -c "from music_intel.app import build_app; build_app(); print('OK')"
```

## Architecture

```
sources/        → one fetch_artist(name) per API, returns (ArtistProfile, [Release])
pipeline/
  ingest.py     → runs all sources in parallel via ThreadPoolExecutor + asyncio
  validate.py   → DuckDB queries: row counts, nulls, cross-source conflicts
storage/db.py   → DuckDB schema + CRUD (stored at ~/.music_intel/data.duckdb)
ai/
  providers.py  → PROVIDERS dict: all AI provider configs (models, base_url, env_key)
  analyst.py    → LiteLLM calls: generate_report(), chat(), explain_recommendations()
app.py          → Gradio UI + all action handlers
```

## AI provider pattern

All AI calls go through `analyst._call()` which uses LiteLLM with `model="{provider}/{model}"`. Provider configs (base_url, env_key, model list) live in `ai/providers.py`. Adding a new provider means adding one entry to `PROVIDERS` — nothing else needs changing.

## Tests

```bash
pytest tests/unit tests/integration -v
pytest tests/e2e -v  # requires app running at :7860
```
