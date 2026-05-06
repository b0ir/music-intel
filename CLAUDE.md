# Claude.md

This file provides guidance to Claude (or any AI assistant) on how to work with this project.

## Project Overview

music-intel is a multi-source music intelligence tool that aggregates data from Spotify, MusicBrainz, Last.fm, and Discogs into a local DuckDB database with AI-powered analysis via LiteLLM.

## Key Conventions

### Git Commits

Use conventional commit messages:
- `fix:` - Bug fixes
- `feat:` - New features
- `refactor:` - Code refactoring
- `test:` - Test changes
- `docs:` - Documentation
- `chore:` - Maintenance tasks

Example: `fix: resolve asyncio event loop conflict in e2e tests`

### Branching

- Main branch: `main`
- Feature branches: `feat/<description>`
- Fix branches: `fix/<description>`

### Before Pushing

ALWAYS ask for explicit authorization before pushing to GitHub. Never auto-push.

## Common Tasks

### Running Tests

```bash
# Unit + Integration
pytest tests/unit tests/integration -v

# E2E (requires app running)
python -m music_intel.app &
pytest tests/e2e -v
```

### Running App

```bash
python -m music_intel.app
```

### Environment Variables

See `.env.example` for required keys. Never commit actual API keys.

## Important Notes

1. Do NOT use `asyncio.run()` directly in code that may be called from async test contexts (like pytest-asyncio). Use `ThreadPoolExecutor` to isolate.
2. Source configuration detection checks for placeholder values (`your_api_key`, `your_user_token`) to determine if a source is actually configured.
3. Playwright tests run against all browsers (chromium, firefox, webkit) by default.