import os
import pylast
from music_intel.models import ArtistProfile

_network: pylast.LastFMNetwork | None = None


def _get_network() -> pylast.LastFMNetwork:
    global _network
    if _network is None:
        _network = pylast.LastFMNetwork(api_key=os.environ["LASTFM_API_KEY"])
    return _network


def fetch_artist(name: str) -> tuple[ArtistProfile | None, list]:
    try:
        network = _get_network()
        artist = network.get_artist(name)

        tags = artist.get_top_tags(limit=5)
        genres = [tag.item.get_name() for tag in tags]

        bio = artist.get_bio_summary()
        listeners = _safe_int(artist.get_listener_count())
        play_count = _safe_int(artist.get_playcount())

        profile = ArtistProfile(
            id=f"lastfm:{name.lower().replace(' ', '_')}",
            name=name,
            source="lastfm",
            genres=genres,
            listeners_lastfm=listeners,
            play_count_lastfm=play_count,
        )
        return profile, []

    except pylast.WSError:
        return None, []


def _safe_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
