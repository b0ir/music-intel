# music-intel (WIP)

Multi-source music intelligence tool. Search any artist and get aggregated data from Spotify, MusicBrainz, Last.fm and Discogs — stored locally in DuckDB — with an AI-powered report and follow-up chat. Work in progress.

```
Artist search → fetch all sources in parallel → DuckDB → AI report + chat → export CSV/JSON
```

## Features

- Parallel data ingestion from up to 4 sources (Spotify · MusicBrainz · Last.fm · Discogs)
- Local DuckDB storage with cross-source conflict detection
- AI report: discography overview, career arc, market signals, data anomalies
- Follow-up chat grounded in the fetched data
- Music discovery via Spotify related artists
- Multi-provider AI: Anthropic, OpenAI, DeepSeek, Nvidia NIM, xAI, OpenRouter
- Export to CSV or JSON
- Gradio web UI — runs entirely local

## Quick start

```bash
git clone https://github.com/b0ir/music-intel
cd music-intel
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env   # add your API keys
python -m music_intel.app
```

Open `http://localhost:7860`.

## API keys

Copy `.env.example` to `.env` and fill in the keys you have. Only one AI provider key and at least one music source key are required.

| Variable | Source | Required |
|---|---|---|
| `SPOTIFY_CLIENT_ID` + `SPOTIFY_CLIENT_SECRET` | [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) | Recommended |
| `LASTFM_API_KEY` | [Last.fm API](https://www.last.fm/api/account/create) | Optional |
| `DISCOGS_USER_TOKEN` | [Discogs Settings → Developers](https://www.discogs.com/settings/developers) | Optional |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | One AI key required |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) | (or another provider) |
| `NVIDIA_NIM_API_KEY` | [build.nvidia.com](https://build.nvidia.com) | (or another provider) |

MusicBrainz requires no key and is always available.

The app auto-detects which keys are present and shows a status indicator next to each source. Unconfigured sources are disabled automatically.

## Stack

- **DuckDB** — local analytical database
- **Gradio** — web UI
- **LiteLLM** — unified interface for all AI providers
- **Spotipy / musicbrainzngs / pylast / discogs-client** — source APIs
- **pytest + Playwright** — test suite

## Tests

```bash
pip install -e ".[dev]"
pytest tests/unit tests/integration -v
```

E2E (requires a running app):

```bash
playwright install chromium
python -m music_intel.app &
pytest tests/e2e -v
```
