import asyncio
import json
import os
import csv
import io
from pathlib import Path
from dotenv import load_dotenv

import gradio as gr

from music_intel.ai.providers import PROVIDERS, get_models_for_provider
from music_intel.ai import analyst
from music_intel.pipeline.ingest import fetch_all_sources
from music_intel.pipeline.validate import get_validation_summary
from music_intel.sources import spotify as spotify_source
from music_intel.storage import db

load_dotenv()

CONFIG_PATH = Path.home() / ".music_intel" / "config.json"

_state: dict = {
    "artist_name": None,
    "report": None,
    "validation_summary": None,
    "chat_history": [],
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key": ""}


def save_config(provider: str, model: str, api_key: str) -> str:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({"provider": provider, "model": model, "api_key": api_key}))
    return "Settings saved."


def verify_connection(provider: str, model: str, api_key: str) -> str:
    if not api_key.strip():
        return "No API key entered."
    try:
        result = analyst._call(
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            provider=provider,
            model=model,
            api_key=api_key,
        )
        return f"Connected. Response: {result[:80]}"
    except Exception as e:
        return f"Connection failed: {e}"


def on_provider_change(provider: str) -> gr.update:
    models = get_models_for_provider(provider)
    return gr.update(choices=models, value=models[0] if models else None)


def analyze_artist(
    artist_name: str,
    use_spotify: bool,
    use_musicbrainz: bool,
    use_lastfm: bool,
    use_discogs: bool,
) -> tuple[str, str, str]:
    if not artist_name.strip():
        return "Please enter an artist name.", "", ""

    enabled = []
    if use_spotify:
        enabled.append("spotify")
    if use_musicbrainz:
        enabled.append("musicbrainz")
    if use_lastfm:
        enabled.append("lastfm")
    if use_discogs:
        enabled.append("discogs")

    if not enabled:
        return "Select at least one data source.", "", ""

    conn = db.connect()
    db.clear_artist_data(conn)

    profiles, releases, errors = asyncio.run(fetch_all_sources(artist_name, enabled))

    db.upsert_artists(conn, profiles)
    db.upsert_releases(conn, releases)

    summary = get_validation_summary(conn)
    _state["artist_name"] = artist_name
    _state["validation_summary"] = summary
    _state["chat_history"] = []

    source_status_lines = []
    for src in enabled:
        count = summary["source_coverage"].get(src, 0)
        err = errors.get(src)
        if err:
            source_status_lines.append(f"**{src}:** error — {err}")
        elif count:
            source_status_lines.append(f"**{src}:** {count} profile(s)")
        else:
            source_status_lines.append(f"**{src}:** no results")

    source_status = "\n".join(source_status_lines)
    release_counts = "\n".join(f"- {src}: {n}" for src, n in summary["release_coverage"].items())
    conflicts_note = f"{summary['conflict_count']} conflict(s) detected" if summary["conflict_count"] else "No conflicts"

    data_panel = (
        f"### Source Coverage\n{source_status}\n\n"
        f"### Releases Found\n{release_counts or '_None_'}\n\n"
        f"### Data Quality\n{conflicts_note}"
    )

    return (
        "_Configure your AI provider in the Settings tab, then click Generate Report._",
        data_panel,
        "",
    )


def generate_report_action(provider: str, model: str, api_key: str) -> str:
    if not _state.get("artist_name"):
        return "Run an analysis first."
    if not api_key.strip():
        return "Enter your API key in the Settings tab."
    try:
        report = analyst.generate_report(
            artist_name=_state["artist_name"],
            validation_summary=_state["validation_summary"],
            provider=provider,
            model=model,
            api_key=api_key,
        )
        _state["report"] = report
        return report
    except Exception as e:
        return f"Error generating report: {e}"


def chat_action(
    message: str,
    history: list,
    provider: str,
    model: str,
    api_key: str,
) -> tuple[str, list]:
    if not _state.get("report"):
        return "", history + [[message, "Generate a report first."]]
    if not api_key.strip():
        return "", history + [[message, "Enter your API key in Settings."]]
    try:
        formatted_history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": msg}
            for pair in history for i, msg in enumerate(pair)
        ]
        reply = analyst.chat(
            user_message=message,
            history=formatted_history,
            artist_name=_state["artist_name"],
            report=_state["report"],
            validation_summary=_state["validation_summary"],
            provider=provider,
            model=model,
            api_key=api_key,
        )
        return "", history + [[message, reply]]
    except Exception as e:
        return "", history + [[message, f"Error: {e}"]]


def export_csv_action() -> str | None:
    if not _state.get("validation_summary"):
        return None
    conn = db.connect()
    artists_df = db.get_artists_df(conn)
    releases_df = db.get_releases_df(conn)

    output = io.StringIO()
    output.write("=== Artists ===\n")
    artists_df.to_csv(output, index=False)
    output.write("\n=== Releases ===\n")
    releases_df.to_csv(output, index=False)

    path = Path("/tmp/music_intel_export.csv")
    path.write_text(output.getvalue())
    return str(path)


def export_json_action() -> str | None:
    if not _state.get("validation_summary"):
        return None
    export = {
        "artist": _state["artist_name"],
        "report": _state["report"],
        "validation_summary": _state["validation_summary"],
    }
    path = Path("/tmp/music_intel_export.json")
    path.write_text(json.dumps(export, indent=2, default=str))
    return str(path)


def discover_action(provider: str, model: str, api_key: str) -> tuple[str, str]:
    if not _state.get("artist_name"):
        return "Run an analysis first.", ""
    try:
        tracks = spotify_source.get_recommendations(_state["artist_name"], limit=10)
        if not tracks:
            return "No Spotify recommendations found (check Spotify credentials).", ""

        track_list = "\n".join(
            f"- [{t.name}]({t.spotify_url}) — {t.artist}" if t.spotify_url
            else f"- {t.name} — {t.artist}"
            for t in tracks
        )

        explanation = ""
        if api_key.strip() and _state.get("validation_summary"):
            try:
                explanation = analyst.explain_recommendations(
                    artist_name=_state["artist_name"],
                    recommended_tracks=[{"name": t.name, "artist": t.artist} for t in tracks],
                    validation_summary=_state["validation_summary"],
                    provider=provider,
                    model=model,
                    api_key=api_key,
                )
            except Exception:
                explanation = "_AI explanation unavailable — check your API key in Settings._"

        return track_list, explanation
    except Exception as e:
        return f"Error fetching recommendations: {e}", ""


def build_app() -> gr.Blocks:
    config = load_config()

    with gr.Blocks(title="music-intel", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# music-intel\nMulti-source music intelligence — Spotify · MusicBrainz · Last.fm · Discogs")

        # Shared AI state (used across tabs)
        provider_state = gr.State(config["provider"])
        model_state = gr.State(config["model"])
        api_key_state = gr.State(config["api_key"])

        with gr.Tabs():

            # ── Analyze Tab ─────────────────────────────────────────────
            with gr.Tab("Analyze"):
                with gr.Row():
                    artist_input = gr.Textbox(
                        label="Artist Name",
                        placeholder="e.g. Radiohead",
                        scale=4,
                    )
                    analyze_btn = gr.Button("Fetch Data", variant="primary", scale=1)

                with gr.Row():
                    use_spotify = gr.Checkbox(label="Spotify", value=True)
                    use_mb = gr.Checkbox(label="MusicBrainz", value=True)
                    use_lastfm = gr.Checkbox(label="Last.fm", value=bool(os.getenv("LASTFM_API_KEY")))
                    use_discogs = gr.Checkbox(label="Discogs", value=bool(os.getenv("DISCOGS_USER_TOKEN")))

                with gr.Row():
                    report_output = gr.Markdown(label="AI Report", value="_Enter an artist and click Fetch Data._")
                    with gr.Column(scale=1):
                        data_panel = gr.Markdown(label="Data Sources")
                        generate_btn = gr.Button("Generate Report", variant="secondary")

                with gr.Row():
                    export_csv_btn = gr.Button("Export CSV")
                    export_json_btn = gr.Button("Export JSON")
                    csv_file = gr.File(label="CSV", visible=False)
                    json_file = gr.File(label="JSON", visible=False)

                gr.Markdown("### Follow-up Chat")
                chatbot = gr.Chatbot(height=300)
                with gr.Row():
                    chat_input = gr.Textbox(placeholder="Ask about the data...", show_label=False, scale=4)
                    chat_send = gr.Button("Send", scale=1)

            # ── Discover Tab ────────────────────────────────────────────
            with gr.Tab("Discover"):
                gr.Markdown("Spotify recommendations based on the last analyzed artist.")
                discover_btn = gr.Button("Get Recommendations", variant="primary")
                recommendations_output = gr.Markdown()
                ai_explanation = gr.Markdown()

            # ── Settings Tab ────────────────────────────────────────────
            with gr.Tab("Settings"):
                gr.Markdown("### AI Provider")
                provider_dropdown = gr.Dropdown(
                    label="AI Provider",
                    choices=list(PROVIDERS.keys()),
                    value=config["provider"],
                )
                model_dropdown = gr.Dropdown(
                    label="Model",
                    choices=get_models_for_provider(config["provider"]),
                    value=config["model"],
                )
                api_key_input = gr.Textbox(
                    label="API Key",
                    type="password",
                    value=config["api_key"],
                    placeholder="Paste your API key here",
                )
                with gr.Row():
                    verify_btn = gr.Button("Verify Connection")
                    save_btn = gr.Button("Save Settings", variant="primary")
                verify_output = gr.Textbox(label="Status", interactive=False)

        # ── Wiring ──────────────────────────────────────────────────────

        provider_dropdown.change(
            on_provider_change,
            inputs=[provider_dropdown],
            outputs=[model_dropdown],
        )

        save_btn.click(
            save_config,
            inputs=[provider_dropdown, model_dropdown, api_key_input],
            outputs=[verify_output],
        ).then(
            lambda p, m, k: (p, m, k),
            inputs=[provider_dropdown, model_dropdown, api_key_input],
            outputs=[provider_state, model_state, api_key_state],
        )

        verify_btn.click(
            verify_connection,
            inputs=[provider_dropdown, model_dropdown, api_key_input],
            outputs=[verify_output],
        )

        analyze_btn.click(
            analyze_artist,
            inputs=[artist_input, use_spotify, use_mb, use_lastfm, use_discogs],
            outputs=[report_output, data_panel, verify_output],
        )

        generate_btn.click(
            generate_report_action,
            inputs=[provider_state, model_state, api_key_state],
            outputs=[report_output],
        )

        chat_send.click(
            chat_action,
            inputs=[chat_input, chatbot, provider_state, model_state, api_key_state],
            outputs=[chat_input, chatbot],
        )

        export_csv_btn.click(
            export_csv_action,
            outputs=[csv_file],
        ).then(lambda f: gr.update(visible=f is not None), inputs=[csv_file], outputs=[csv_file])

        export_json_btn.click(
            export_json_action,
            outputs=[json_file],
        ).then(lambda f: gr.update(visible=f is not None), inputs=[json_file], outputs=[json_file])

        discover_btn.click(
            discover_action,
            inputs=[provider_state, model_state, api_key_state],
            outputs=[recommendations_output, ai_explanation],
        )

    return demo


def main():
    app = build_app()
    app.launch()


if __name__ == "__main__":
    main()
