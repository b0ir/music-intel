import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from music_intel.models import ArtistProfile, Release, Track

_client: spotipy.Spotify | None = None


def _get_client() -> spotipy.Spotify:
    global _client
    if _client is None:
        _client = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=os.environ["SPOTIFY_CLIENT_ID"],
                client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
            )
        )
    return _client


def fetch_artist(name: str) -> tuple[ArtistProfile | None, list[Release]]:
    try:
        sp = _get_client()
        results = sp.search(q=f"artist:{name}", type="artist", limit=1)
        items = results["artists"]["items"]
        if not items:
            return None, []

        artist = items[0]
        artist_id = artist["id"]

        albums_result = sp.artist_albums(
            artist_id,
            album_type="album,single,ep",
            limit=50,
        )
        albums = albums_result.get("items", [])

        images = artist.get("images", [])
        image_url = images[0]["url"] if images else None

        profile = ArtistProfile(
            id=f"spotify:{artist_id}",
            name=artist["name"],
            source="spotify",
            genres=artist.get("genres", [])[:5],
            popularity=artist.get("popularity"),
            image_url=image_url,
        )

        releases = [
            Release(
                id=f"spotify:{a['id']}",
                artist_id=profile.id,
                title=a["name"],
                source="spotify",
                type=a.get("album_type"),
                year=_parse_year(a.get("release_date")),
                track_count=a.get("total_tracks"),
            )
            for a in albums
        ]

        return profile, releases

    except (KeyError, spotipy.exceptions.SpotifyException):
        return None, []


def get_recommendations(artist_name: str, limit: int = 10) -> list[Track]:
    try:
        sp = _get_client()
        results = sp.search(q=f"artist:{artist_name}", type="artist", limit=1)
        items = results["artists"]["items"]
        if not items:
            return []

        artist_id = items[0]["id"]
        recs = sp.recommendations(seed_artists=[artist_id], limit=limit)
        tracks = recs.get("tracks", [])

        return [
            Track(
                id=t["id"],
                name=t["name"],
                artist=", ".join(a["name"] for a in t["artists"]),
                album=t["album"]["name"] if t.get("album") else None,
                preview_url=t.get("preview_url"),
                spotify_url=t["external_urls"].get("spotify"),
            )
            for t in tracks
        ]
    except (KeyError, spotipy.exceptions.SpotifyException):
        return []


def _parse_year(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        return int(str(date_str)[:4])
    except (ValueError, TypeError):
        return None
