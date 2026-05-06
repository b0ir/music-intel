# CLAUDE.md

This file provides guidance to Claude (or any AI assistant) on how to work with this project.

## Project Overview

music-intel is a multi-source music intelligence tool that aggregates data from Spotify, MusicBrainz, Last.fm, and Discogs into a local DuckDB database with AI-powered analysis via LiteLLM.

## Key Conventions

- Use conventional commit messages for Git Commits.
- Ask before commiting, do not create commits of changes you did without user's approval.
- ALWAYS ask for explicit authorization before pushing to GitHub. Never auto-push.

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
