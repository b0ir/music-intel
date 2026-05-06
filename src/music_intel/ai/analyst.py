import json
import litellm
from music_intel.ai.providers import PROVIDERS

litellm.telemetry = False


def _call(
    messages: list[dict],
    provider: str,
    model: str,
    api_key: str,
) -> str:
    conf = PROVIDERS[provider]
    kwargs = dict(
        model=f"{provider}/{model}",
        messages=messages,
        api_key=api_key,
    )
    if conf["base_url"]:
        kwargs["base_url"] = conf["base_url"]

    response = litellm.completion(**kwargs)
    return response.choices[0].message.content


def generate_report(
    artist_name: str,
    validation_summary: dict,
    provider: str,
    model: str,
    api_key: str,
) -> str:
    data_context = json.dumps(validation_summary, indent=2, default=str)

    system = (
        "You are a music intelligence analyst. You receive aggregated data about an artist "
        "from multiple sources (Spotify, MusicBrainz, Last.fm, Discogs) and produce a "
        "structured, insightful report. Be specific and data-driven. Use markdown formatting."
    )

    prompt = f"""Analyze the following aggregated data for artist: **{artist_name}**

```json
{data_context}
```

Write a comprehensive intelligence report with these sections:

## Career Overview
Brief narrative on who this artist is and what the data reveals about their career.

## Discography Highlights
Key releases, patterns in output volume, type breakdown (albums/singles/EPs).

## Audience & Market Signals
Last.fm listener count, Spotify popularity score, Discogs have/want ratio (demand signal).

## Cross-Source Insights
Any conflicts or interesting discrepancies found between sources. What do they tell us?

## Data Quality Notes
Any missing data, NULL fields, or sources that returned no results.
"""

    return _call(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        provider=provider,
        model=model,
        api_key=api_key,
    )


def chat(
    user_message: str,
    history: list[dict],
    artist_name: str,
    report: str,
    validation_summary: dict,
    provider: str,
    model: str,
    api_key: str,
) -> str:
    system = (
        f"You are a music intelligence analyst. The user is asking follow-up questions about "
        f"**{artist_name}**. You have access to the full analysis report and raw data below.\n\n"
        f"## Report\n{report}\n\n"
        f"## Raw Data\n```json\n{json.dumps(validation_summary, indent=2, default=str)}\n```\n\n"
        "Answer concisely and accurately. Reference specific numbers when available."
    )

    messages = [{"role": "system", "content": system}] + history + [
        {"role": "user", "content": user_message}
    ]

    return _call(messages=messages, provider=provider, model=model, api_key=api_key)


def explain_recommendations(
    artist_name: str,
    recommended_tracks: list[dict],
    validation_summary: dict,
    provider: str,
    model: str,
    api_key: str,
) -> str:
    tracks_str = "\n".join(
        f"- {t['name']} by {t['artist']}" for t in recommended_tracks[:10]
    )
    data_context = json.dumps(validation_summary, indent=2, default=str)

    prompt = (
        f"Based on the intelligence data for **{artist_name}**, explain in 2-3 sentences "
        f"why these Spotify recommendations make sense:\n\n{tracks_str}\n\n"
        f"Data context:\n```json\n{data_context}\n```"
    )

    return _call(
        messages=[{"role": "user", "content": prompt}],
        provider=provider,
        model=model,
        api_key=api_key,
    )
