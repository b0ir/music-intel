import os
import discogs_client
from music_intel.models import ArtistProfile, Release

_client: discogs_client.Client | None = None


def _get_client() -> discogs_client.Client:
    global _client
    if _client is None:
        _client = discogs_client.Client(
            "music-intel/0.1.0",
            user_token=os.environ["DISCOGS_USER_TOKEN"],
        )
    return _client


def fetch_artist(name: str) -> tuple[ArtistProfile | None, list[Release]]:
    try:
        client = _get_client()
        results = client.search(name, type="artist")
        if not results:
            return None, []

        artist = results[0]
        artist_id = str(artist.id)

        releases_raw = list(artist.releases[:25])

        profile = ArtistProfile(
            id=f"discogs:{artist_id}",
            name=getattr(artist, "name", name),
            source="discogs",
        )

        releases = []
        for r in releases_raw:
            try:
                stats = r.marketplace_statistics
                releases.append(Release(
                    id=f"discogs:{r.id}",
                    artist_id=profile.id,
                    title=getattr(r, "title", ""),
                    source="discogs",
                    year=_safe_int(getattr(r, "year", None)),
                    discogs_price_median=_safe_float(
                        getattr(stats, "median", None) if stats else None
                    ),
                    discogs_have=_safe_int(getattr(r, "community", {}).get("have")),
                    discogs_want=_safe_int(getattr(r, "community", {}).get("want")),
                ))
            except Exception:
                continue

        return profile, releases

    except Exception:
        return None, []


def _safe_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
