import pytest
from music_intel.models import ArtistProfile, Release


@pytest.mark.parametrize("source,expected_source_prefix", [
    ("spotify", "spotify:"),
    ("musicbrainz", "mb:"),
    ("lastfm", "lastfm:"),
    ("discogs", "discogs:"),
])
def test_profile_id_has_source_prefix(source, expected_source_prefix):
    profile = ArtistProfile(id=f"{expected_source_prefix}123", name="Test", source=source)
    assert profile.id.startswith(expected_source_prefix)


def test_profile_genres_defaults_to_empty_list():
    profile = ArtistProfile(id="spotify:1", name="Test", source="spotify")
    assert isinstance(profile.genres, list)
    assert profile.genres == []


def test_profile_optional_fields_default_none():
    profile = ArtistProfile(id="spotify:1", name="Test", source="spotify")
    assert profile.country is None
    assert profile.formed_year is None
    assert profile.popularity is None
    assert profile.listeners_lastfm is None
    assert profile.play_count_lastfm is None


def test_release_links_to_artist():
    release = Release(id="spotify:r1", artist_id="spotify:a1", title="OK Computer", source="spotify")
    assert release.artist_id == "spotify:a1"


def test_release_optional_market_data_defaults_none():
    release = Release(id="discogs:r1", artist_id="discogs:a1", title="Some Album", source="discogs")
    assert release.discogs_price_median is None
    assert release.discogs_have is None
    assert release.discogs_want is None


@pytest.mark.parametrize("name,expected_genres_type", [
    ("Radiohead", list),
    ("Unknown Artist 12345", list),
])
def test_profile_genres_always_list(name, expected_genres_type):
    profile = ArtistProfile(id="x:1", name=name, source="spotify", genres=[])
    assert type(profile.genres) is expected_genres_type
