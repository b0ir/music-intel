import asyncio
import json
import io
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
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
}


# ── Config helpers ───────────────────────────────────────────────────────────

def _detect_provider_from_env() -> dict:
    for provider, conf in PROVIDERS.items():
        key = os.getenv(conf["env_key"], "").strip()
        if key:
            models = conf["models"]
            return {"provider": provider, "model": models[0], "api_key": key}
    return {"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key": ""}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text())
            if not saved.get("api_key", "").strip():
                env_key = os.getenv(
                    PROVIDERS.get(saved["provider"], {}).get("env_key", ""), ""
                ).strip()
                if env_key:
                    saved["api_key"] = env_key
            return saved
        except Exception:
            pass
    return _detect_provider_from_env()


def save_config_action(provider: str, model: str, api_key: str) -> str:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({"provider": provider, "model": model, "api_key": api_key}))
    return "Settings saved."


# ── Source availability ───────────────────────────────────────────────────────

def _source_flags() -> dict[str, bool]:
    def is_configured(key: str, placeholder: str = "") -> bool:
        val = os.getenv(key, "").strip()
        return bool(val and val != placeholder)

    return {
        "spotify":      is_configured("SPOTIFY_CLIENT_ID") and is_configured("SPOTIFY_CLIENT_SECRET"),
        "musicbrainz":  True,
        "lastfm":       is_configured("LASTFM_API_KEY", "your_api_key"),
        "discogs":      is_configured("DISCOGS_USER_TOKEN", "your_user_token"),
    }


def _source_status_md() -> str:
    icons = {True: "✅", False: "❌"}
    hints = {
        "spotify":     "SPOTIFY_CLIENT_ID + SPOTIFY_CLIENT_SECRET",
        "musicbrainz": "no key required",
        "lastfm":      "LASTFM_API_KEY",
        "discogs":     "DISCOGS_USER_TOKEN",
    }
    flags = _source_flags()
    lines = []
    for src, ok in flags.items():
        note = "configured" if ok else f"add `{hints[src]}` to .env"
        lines.append(f"{icons[ok]} **{src.capitalize()}** — {note}")
    return "\n".join(lines)


# ── Action handlers ───────────────────────────────────────────────────────────

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
        return f"✅ Connected. Response: {result[:80]}"
    except Exception as e:
        return f"❌ Connection failed: {e}"


def on_provider_change(provider: str) -> gr.update:
    models = get_models_for_provider(provider)
    return gr.update(choices=models, value=models[0] if models else None)


def analyze_artist(
    artist_name: str,
    use_spotify: bool,
    use_musicbrainz: bool,
    use_lastfm: bool,
    use_discogs: bool,
) -> tuple[str, str]:
    if not artist_name.strip():
        return "Please enter an artist name.", ""

    enabled = []
    flags = _source_flags()
    for src, checked in [
        ("spotify", use_spotify),
        ("musicbrainz", use_musicbrainz),
        ("lastfm", use_lastfm),
        ("discogs", use_discogs),
    ]:
        if checked and flags[src]:
            enabled.append(src)

    if not enabled:
        return "Select at least one configured data source.", ""

    conn = db.connect()
    db.clear_artist_data(conn)

    with ThreadPoolExecutor() as executor:
        future = executor.submit(asyncio.run, fetch_all_sources(artist_name, enabled))
        profiles, releases, errors = future.result()

    db.upsert_artists(conn, profiles)
    db.upsert_releases(conn, releases)

    summary = get_validation_summary(conn)
    _state["artist_name"] = artist_name
    _state["validation_summary"] = summary
    _state["report"] = None

    source_lines = []
    for src in enabled:
        count = summary["source_coverage"].get(src, 0)
        err = errors.get(src)
        if err:
            source_lines.append(f"❌ **{src}:** {err}")
        elif count:
            source_lines.append(f"✅ **{src}:** {count} record(s)")
        else:
            source_lines.append(f"⚠️ **{src}:** no results found")

    release_counts = "\n".join(f"- {src}: {n}" for src, n in summary["release_coverage"].items())
    conflicts_note = f"⚠️ {summary['conflict_count']} conflict(s) detected" if summary["conflict_count"] else "✅ No conflicts"

    data_panel = (
        f"### Sources\n" + "\n".join(source_lines) + "\n\n"
        f"### Releases\n{release_counts or '_None_'}\n\n"
        f"### Data Quality\n{conflicts_note}"
    )

    return "_Data fetched — click **Generate Report** to run AI analysis._", data_panel


def generate_report_action(provider: str, model: str, api_key: str) -> str:
    if not _state.get("artist_name"):
        return "Run Fetch Data first."
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
    history: list[dict],
    provider: str,
    model: str,
    api_key: str,
) -> tuple[str, list[dict]]:
    if not message.strip():
        return "", history
    if not _state.get("report"):
        return "", history + [{"role": "assistant", "content": "Generate a report first."}]
    if not api_key.strip():
        return "", history + [{"role": "assistant", "content": "Enter your API key in Settings."}]
    try:
        formatted_history = [
            {"role": m["role"], "content": m["content"]}
            for m in history
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
        return "", history + [{"role": "assistant", "content": reply}]
    except Exception as e:
        return "", history + [{"role": "assistant", "content": f"Error: {e}"}]


def export_csv_action() -> str | None:
    if not _state.get("validation_summary"):
        return None
    conn = db.connect()
    artists_df = db.get_artists_df(conn)
    releases_df = db.get_releases_df(conn)

    out = io.StringIO()
    out.write("=== Artists ===\n")
    artists_df.to_csv(out, index=False)
    out.write("\n=== Releases ===\n")
    releases_df.to_csv(out, index=False)

    path = Path(tempfile.gettempdir()) / "music_intel_export.csv"
    path.write_text(out.getvalue(), encoding="utf-8")
    return str(path)


def export_json_action() -> str | None:
    if not _state.get("validation_summary"):
        return None
    payload = {
        "artist": _state["artist_name"],
        "report": _state["report"],
        "validation_summary": _state["validation_summary"],
    }
    path = Path(tempfile.gettempdir()) / "music_intel_export.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return str(path)


def discover_action(provider: str, model: str, api_key: str) -> tuple[str, str]:
    if not _state.get("artist_name"):
        return "Run Fetch Data first.", ""
    if not _source_flags()["spotify"]:
        return "Spotify credentials not configured — add them to .env.", ""
    try:
        tracks = spotify_source.get_recommendations(_state["artist_name"], limit=10)
        if not tracks:
            return "No Spotify recommendations found.", ""

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
        return f"Error: {e}", ""


# ── UI ────────────────────────────────────────────────────────────────────────

def build_app() -> gr.Blocks:
    config = load_config()
    flags = _source_flags()

    with gr.Blocks(title="music-intel") as demo:
        gr.Markdown("# music-intel\nMulti-source music intelligence — Spotify · MusicBrainz · Last.fm · Discogs")

        with gr.Tabs():

            # ── Analyze ──────────────────────────────────────────────────
            with gr.Tab("Analyze"):
                gr.Markdown(_source_status_md())

                with gr.Row():
                    artist_input = gr.Textbox(
                        label="Artist Name",
                        placeholder="e.g. Radiohead",
                        scale=4,
                    )
                    analyze_btn = gr.Button("Fetch Data", variant="primary", scale=1)

                with gr.Row():
                    use_spotify = gr.Checkbox(
                        label="Spotify" + ("" if flags["spotify"] else " ⚠"),
                        value=flags["spotify"],
                        interactive=flags["spotify"],
                    )
                    use_mb = gr.Checkbox(label="MusicBrainz", value=True)
                    use_lastfm = gr.Checkbox(
                        label="Last.fm" + ("" if flags["lastfm"] else " ⚠"),
                        value=flags["lastfm"],
                        interactive=flags["lastfm"],
                    )
                    use_discogs = gr.Checkbox(
                        label="Discogs" + ("" if flags["discogs"] else " ⚠"),
                        value=flags["discogs"],
                        interactive=flags["discogs"],
                    )

                with gr.Row():
                    report_output = gr.Markdown(
                        value="_Enter an artist name and click Fetch Data._",
                        label="AI Report",
                    )
                    with gr.Column(scale=1):
                        data_panel = gr.Markdown(label="Source Data")
                        with gr.Row():
                            generate_btn = gr.Button("Generate Report", variant="secondary")
                            generate_spinner = gr.HTML(visible=False)

                with gr.Row():
                    export_csv_btn = gr.Button("Export CSV")
                    export_json_btn = gr.Button("Export JSON")
                csv_file = gr.File(label="Download CSV", visible=False)
                json_file = gr.File(label="Download JSON", visible=False)

                gr.Markdown("### Follow-up Chat")
                chatbot = gr.Chatbot(height=300)
                with gr.Row():
                    chat_input = gr.Textbox(
                        label="Message",
                        show_label=False,
                        placeholder="Ask about the data...",
                        scale=4,
                    )
                    with gr.Column(scale=1):
                        chat_send = gr.Button("Send", scale=1, interactive=False)
                        chat_spinner = gr.HTML(
                            """<span style="font-size:12px">⚡ processing...</span>""",
                            visible=False
                        )

                # Enable/disable send button based on input
                chat_input.change(
                    lambda msg: gr.update(interactive=bool(msg and msg.strip())),
                    inputs=[chat_input],
                    outputs=[chat_send],
                )

            with gr.Tab("Discover"):
                gr.Markdown(
                    "Spotify recommendations based on the last analyzed artist.\n\n"
                    + ("" if flags["spotify"] else "> ⚠️ Spotify not configured — add credentials to .env")
                )
                discover_btn = gr.Button(
                    "Get Recommendations",
                    variant="primary",
                    interactive=flags["spotify"],
                )
                recommendations_output = gr.Markdown()
                ai_explanation = gr.Markdown()

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
                settings_status = gr.Textbox(label="Status", interactive=False)

                gr.Markdown("---\n### Data Sources")
                gr.Markdown(_source_status_md())
                gr.Markdown("_Edit `.env` in the project root and restart the app to add sources._")

        # ── Wiring ────────────────────────────────────────────────────────
        # provider_dropdown, model_dropdown, api_key_input are passed directly —
        # no gr.State needed, avoids the Gradio 5/6 empty-ID bug.

        provider_dropdown.change(on_provider_change, [provider_dropdown], [model_dropdown])

        save_btn.click(
            save_config_action,
            inputs=[provider_dropdown, model_dropdown, api_key_input],
            outputs=[settings_status],
        )

        verify_btn.click(
            verify_connection,
            inputs=[provider_dropdown, model_dropdown, api_key_input],
            outputs=[settings_status],
        )

        analyze_btn.click(
            analyze_artist,
            inputs=[artist_input, use_spotify, use_mb, use_lastfm, use_discogs],
            outputs=[report_output, data_panel],
        )

        generate_btn.click(
            lambda: (gr.update(visible=True), "_Generating report..._"),
            outputs=[generate_spinner, report_output],
        ).then(
            generate_report_action,
            inputs=[provider_dropdown, model_dropdown, api_key_input],
            outputs=[report_output],
        ).then(
            lambda: gr.update(visible=False),
            outputs=[generate_spinner],
        )

        chat_send.click(
            chat_action,
            inputs=[chat_input, chatbot, provider_dropdown, model_dropdown, api_key_input],
            outputs=[chat_input, chatbot],
        )

        chat_input.submit(
            chat_action,
            inputs=[chat_input, chatbot, provider_dropdown, model_dropdown, api_key_input],
            outputs=[chat_input, chatbot],
        )

        export_csv_btn.click(export_csv_action, outputs=[csv_file]).then(
            lambda f: gr.update(visible=f is not None), inputs=[csv_file], outputs=[csv_file]
        )
        export_json_btn.click(export_json_action, outputs=[json_file]).then(
            lambda f: gr.update(visible=f is not None), inputs=[json_file], outputs=[json_file]
        )

        discover_btn.click(
            discover_action,
            inputs=[provider_dropdown, model_dropdown, api_key_input],
            outputs=[recommendations_output, ai_explanation],
        )

    return demo


def main():
    app = build_app()
    app.launch(theme=gr.themes.Soft())


if __name__ == "__main__":
    main()
