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

        artist = items[0]
        artist_id = artist["id"]
        genres = artist.get("genres", [])

        related_artists = []
        try:
            related = sp.artist_related_artists(artist_id)
            related_artists = related.get("artists", [])[:5]
        except spotipy.exceptions.SpotifyException:
            # Endpoint restricted for this app tier — fall back to genre search
            if genres:
                genre_q = sp.search(q=f"genre:{genres[0]}", type="artist", limit=6)
                related_artists = [
                    a for a in genre_q["artists"]["items"] if a["id"] != artist_id
                ][:5]

        tracks: list[Track] = []
        for ra in related_artists:
            if len(tracks) >= limit:
                break
            try:
                top = sp.artist_top_tracks(ra["id"], country="US")
                for t in top.get("tracks", [])[:2]:
                    if len(tracks) >= limit:
                        break
                    tracks.append(Track(
                        id=t["id"],
                        name=t["name"],
                        artist=", ".join(a["name"] for a in t["artists"]),
                        album=t["album"]["name"] if t.get("album") else None,
                        preview_url=t.get("preview_url"),
                        spotify_url=t["external_urls"].get("spotify"),
                    ))
            except spotipy.exceptions.SpotifyException:
                continue

        return tracks
    except (KeyError, spotipy.exceptions.SpotifyException):
        return []


def _parse_year(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        return int(str(date_str)[:4])
    except (ValueError, TypeError):
        return None
