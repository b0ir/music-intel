import ssl
import certifi
import urllib.request
import musicbrainzngs
import musicbrainzngs.compat as _mb_compat
from music_intel.models import ArtistProfile, Release

# musicbrainzngs calls compat.build_opener() fresh on every request and never
# touches urllib.request._opener, so install_opener() has no effect.
# Patch compat.build_opener to always inject an HTTPSHandler backed by certifi.
_ssl_ctx = ssl.create_default_context(cafile=certifi.where())
_orig_build_opener = _mb_compat.build_opener

def _build_opener_with_certifi(*handlers, **kw):
    return _orig_build_opener(
        urllib.request.HTTPSHandler(context=_ssl_ctx),
        *handlers,
        **kw,
    )

_mb_compat.build_opener = _build_opener_with_certifi

musicbrainzngs.set_useragent("music-intel", "0.1.0", "https://github.com/b0ir/music-intel")


def fetch_artist(name: str) -> tuple[ArtistProfile | None, list[Release]]:
    result = musicbrainzngs.search_artists(query=name, limit=1)
    artists = result.get("artist-list", [])
    if not artists:
        return None, []

    artist = artists[0]
    artist_id = artist["id"]

    release_result = musicbrainzngs.browse_release_groups(
        artist=artist_id,
        release_type=["album", "single", "ep"],
        limit=25,
    )
    release_groups = release_result.get("release-group-list", [])

    profile = ArtistProfile(
        id=f"mb:{artist_id}",
        name=artist.get("name", name),
        source="musicbrainz",
        genres=_extract_genres(artist),
        country=artist.get("country"),
        formed_year=_parse_year(artist.get("life-span", {}).get("begin")),
    )

    releases = [
        Release(
            id=f"mb:{rg['id']}",
            artist_id=profile.id,
            title=rg.get("title", ""),
            source="musicbrainz",
            type=rg.get("primary-type", "").lower() or None,
            year=_parse_year(rg.get("first-release-date")),
        )
        for rg in release_groups
    ]

    return profile, releases


def _extract_genres(artist: dict) -> list[str]:
    tags = artist.get("tag-list", [])
    return [t["name"] for t in sorted(tags, key=lambda t: int(t.get("count", 0)), reverse=True)[:5]]


def _parse_year(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        return int(str(date_str)[:4])
    except (ValueError, TypeError):
        return None
