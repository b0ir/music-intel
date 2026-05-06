import json
import pytest
import duckdb
from pathlib import Path
from music_intel.storage.db import init_schema
from music_intel.models import ArtistProfile, Release

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def db():
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def sample_profiles() -> list[ArtistProfile]:
    return [
        ArtistProfile(
            id="spotify:abc123",
            name="Radiohead",
            source="spotify",
            genres=["alternative rock", "art rock"],
            country=None,
            formed_year=None,
            popularity=72,
        ),
        ArtistProfile(
            id="mb:xyz789",
            name="Radiohead",
            source="musicbrainz",
            genres=["alternative rock", "experimental"],
            country="GB",
            formed_year=1985,
        ),
        ArtistProfile(
            id="lastfm:radiohead",
            name="Radiohead",
            source="lastfm",
            genres=["alternative", "rock"],
            listeners_lastfm=5_200_000,
            play_count_lastfm=850_000_000,
        ),
    ]


@pytest.fixture
def sample_releases() -> list[Release]:
    return [
        Release(id="spotify:r1", artist_id="spotify:abc123", title="OK Computer", source="spotify", type="album", year=1997, track_count=12),
        Release(id="spotify:r2", artist_id="spotify:abc123", title="Kid A", source="spotify", type="album", year=2000, track_count=10),
        Release(id="mb:r1", artist_id="mb:xyz789", title="OK Computer", source="musicbrainz", type="album", year=1997),
        Release(id="mb:r2", artist_id="mb:xyz789", title="Kid A", source="musicbrainz", type="album", year=2000),
        Release(id="mb:r3", artist_id="mb:xyz789", title="Amnesiac", source="musicbrainz", type="album", year=2001),
    ]


@pytest.fixture
def conflicting_profiles() -> list[ArtistProfile]:
    return [
        ArtistProfile(id="spotify:abc", name="Test Artist", source="spotify", country="US", formed_year=2000),
        ArtistProfile(id="mb:abc", name="Test Artist", source="musicbrainz", country="GB", formed_year=1998),
    ]


@pytest.fixture
def profiles_with_nulls() -> list[ArtistProfile]:
    return [
        ArtistProfile(id="spotify:x1", name=None, source="spotify"),
        ArtistProfile(id="mb:x2", name="Valid Artist", source="musicbrainz"),
    ]


def load_fixture(filename: str) -> dict:
    return json.loads((FIXTURES_DIR / filename).read_text())
