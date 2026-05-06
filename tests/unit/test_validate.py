import pytest
from music_intel.storage.db import upsert_artists, upsert_releases
from music_intel.pipeline.validate import (
    check_row_counts,
    check_null_critical_fields,
    get_source_coverage,
    get_release_coverage,
    detect_cross_source_conflicts,
    check_duplicate_releases,
    get_validation_summary,
)


def test_row_count_matches_ingested(db, sample_profiles):
    upsert_artists(db, sample_profiles)
    assert check_row_counts(db, len(sample_profiles))


def test_row_count_fails_on_mismatch(db, sample_profiles):
    upsert_artists(db, sample_profiles)
    assert not check_row_counts(db, len(sample_profiles) + 1)


def test_null_check_passes_when_clean(db, sample_profiles):
    upsert_artists(db, sample_profiles)
    assert check_null_critical_fields(db) == []


def test_null_check_catches_missing_name(db, profiles_with_nulls):
    upsert_artists(db, profiles_with_nulls)
    nulls = check_null_critical_fields(db)
    assert "name" in nulls


def test_source_coverage_counts_correctly(db, sample_profiles):
    upsert_artists(db, sample_profiles)
    coverage = get_source_coverage(db)
    assert coverage["spotify"] == 1
    assert coverage["musicbrainz"] == 1
    assert coverage["lastfm"] == 1


def test_source_coverage_empty_db(db):
    coverage = get_source_coverage(db)
    assert coverage == {}


def test_release_coverage_counts_by_source(db, sample_releases):
    upsert_releases(db, sample_releases)
    coverage = get_release_coverage(db)
    assert coverage["spotify"] == 2
    assert coverage["musicbrainz"] == 3


def test_conflict_detection_finds_country_mismatch(db, conflicting_profiles):
    upsert_artists(db, conflicting_profiles)
    conflicts = detect_cross_source_conflicts(db)
    field_names = [c.field_name for c in conflicts]
    assert "country" in field_names


def test_conflict_detection_finds_year_mismatch(db, conflicting_profiles):
    upsert_artists(db, conflicting_profiles)
    conflicts = detect_cross_source_conflicts(db)
    field_names = [c.field_name for c in conflicts]
    assert "formed_year" in field_names


def test_no_conflicts_when_data_consistent(db, sample_profiles):
    # sample_profiles don't share country/formed_year across sources → no conflict
    upsert_artists(db, sample_profiles)
    conflicts = detect_cross_source_conflicts(db)
    assert conflicts == []


def test_duplicate_release_detection(db):
    from music_intel.models import Release
    releases = [
        Release(id="s:r1", artist_id="s:a1", title="OK Computer", source="spotify", year=1997),
        Release(id="s:r2", artist_id="s:a1", title="OK Computer", source="spotify", year=1997),
    ]
    upsert_releases(db, releases)
    dupes = check_duplicate_releases(db)
    assert len(dupes) > 0
    assert dupes.iloc[0]["count"] == 2


def test_validation_summary_structure(db, sample_profiles, sample_releases):
    upsert_artists(db, sample_profiles)
    upsert_releases(db, sample_releases)
    summary = get_validation_summary(db)
    assert "source_coverage" in summary
    assert "release_coverage" in summary
    assert "null_critical_fields" in summary
    assert "conflict_count" in summary
    assert "conflicts" in summary
    assert isinstance(summary["conflicts"], list)
