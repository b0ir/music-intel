import pytest
from unittest.mock import patch, MagicMock
from music_intel.storage.db import upsert_artists, upsert_releases
from music_intel.pipeline.validate import (
    check_row_counts,
    detect_cross_source_conflicts,
    get_source_coverage,
    get_validation_summary,
)
from music_intel.models import ArtistProfile, Release


def test_full_ingest_and_validate_flow(db, sample_profiles, sample_releases):
    upsert_artists(db, sample_profiles)
    upsert_releases(db, sample_releases)

    assert check_row_counts(db, len(sample_profiles))
    coverage = get_source_coverage(db)
    assert set(coverage.keys()) == {"spotify", "musicbrainz", "lastfm"}


def test_upsert_idempotent(db, sample_profiles):
    upsert_artists(db, sample_profiles)
    upsert_artists(db, sample_profiles)  # second insert → upsert, no duplicates
    assert check_row_counts(db, len(sample_profiles))


def test_conflict_detection_after_multi_source_ingest(db, conflicting_profiles):
    upsert_artists(db, conflicting_profiles)
    conflicts = detect_cross_source_conflicts(db)
    assert len(conflicts) >= 1
    assert all(c.source_a != c.source_b for c in conflicts)


def test_validation_summary_after_full_ingest(db, sample_profiles, sample_releases):
    upsert_artists(db, sample_profiles)
    upsert_releases(db, sample_releases)
    summary = get_validation_summary(db)

    assert summary["source_coverage"]["spotify"] == 1
    assert summary["source_coverage"]["musicbrainz"] == 1
    assert summary["null_critical_fields"] == []
    assert summary["conflict_count"] == 0


def test_empty_source_response_handled_gracefully(db):
    upsert_artists(db, [])
    upsert_releases(db, [])
    assert check_row_counts(db, 0)
    summary = get_validation_summary(db)
    assert summary["source_coverage"] == {}


def test_partial_source_failure_still_stores_valid_data(db, sample_profiles):
    # Simulate only 2 of 3 sources returning data
    partial = sample_profiles[:2]
    upsert_artists(db, partial)
    assert check_row_counts(db, 2)
    coverage = get_source_coverage(db)
    assert "discogs" not in coverage


@pytest.mark.parametrize("artist_name", ["Radiohead", "Portishead", "Massive Attack"])
def test_multiple_artists_stored_independently(db, artist_name):
    profile = ArtistProfile(
        id=f"spotify:{artist_name.lower().replace(' ', '_')}",
        name=artist_name,
        source="spotify",
        popularity=70,
    )
    upsert_artists(db, [profile])
    coverage = get_source_coverage(db)
    assert coverage.get("spotify", 0) >= 1
