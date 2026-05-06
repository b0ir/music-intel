import asyncio
from concurrent.futures import ThreadPoolExecutor
from music_intel.models import ArtistProfile, Release
from music_intel.sources import musicbrainz, spotify, lastfm, discogs

SOURCES = {
    "musicbrainz": musicbrainz.fetch_artist,
    "spotify": spotify.fetch_artist,
    "lastfm": lastfm.fetch_artist,
    "discogs": discogs.fetch_artist,
}


async def fetch_all_sources(
    artist_name: str,
    enabled_sources: list[str] | None = None,
) -> tuple[list[ArtistProfile], list[Release], dict[str, str]]:
    """
    Fetch from all enabled sources in parallel.
    Returns (profiles, releases, errors) where errors maps source → message.
    """
    sources_to_use = enabled_sources or list(SOURCES.keys())
    profiles: list[ArtistProfile] = []
    releases: list[Release] = []
    errors: dict[str, str] = {}

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=len(sources_to_use)) as pool:
        futures = {
            source: loop.run_in_executor(pool, SOURCES[source], artist_name)
            for source in sources_to_use
            if source in SOURCES
        }

        for source, future in futures.items():
            try:
                profile, source_releases = await future
                if profile:
                    profiles.append(profile)
                    releases.extend(source_releases)
            except Exception as e:
                errors[source] = str(e)

    return profiles, releases, errors
