import duckdb
import pandas as pd
from music_intel.models import Conflict


def check_row_counts(conn: duckdb.DuckDBPyConnection, expected: int) -> bool:
    actual = conn.execute("SELECT COUNT(*) FROM artists").fetchone()[0]
    return actual == expected


def check_null_critical_fields(conn: duckdb.DuckDBPyConnection) -> list[str]:
    """Return field names that have NULLs in critical columns."""
    fields = ["id", "name", "source"]
    nulls = []
    for field in fields:
        count = conn.execute(
            f"SELECT COUNT(*) FROM artists WHERE {field} IS NULL"
        ).fetchone()[0]
        if count > 0:
            nulls.append(field)
    return nulls


def get_source_coverage(conn: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Return artist count per source."""
    rows = conn.execute(
        "SELECT source, COUNT(*) as count FROM artists GROUP BY source"
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def get_release_coverage(conn: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Return release count per source."""
    rows = conn.execute(
        "SELECT source, COUNT(*) as count FROM releases GROUP BY source"
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def detect_cross_source_conflicts(conn: duckdb.DuckDBPyConnection) -> list[Conflict]:
    """
    Compare artist fields across sources. Returns Conflict records for
    fields where different sources disagree (e.g. country, formed_year).
    """
    conflicts: list[Conflict] = []
    fields_to_check = ["country", "formed_year"]

    for field in fields_to_check:
        # Get all non-null values for this field grouped by artist name
        rows = conn.execute(f"""
            SELECT name, source, {field}::VARCHAR as val
            FROM artists
            WHERE {field} IS NOT NULL
            ORDER BY name, source
        """).fetchall()

        by_artist: dict[str, list[tuple[str, str]]] = {}
        for name, source, val in rows:
            by_artist.setdefault(name, []).append((source, val))

        for name, entries in by_artist.items():
            unique_vals = {v for _, v in entries}
            if len(unique_vals) > 1:
                sources = [s for s, _ in entries]
                vals = [v for _, v in entries]
                conflicts.append(Conflict(
                    entity_type="artist",
                    field_name=field,
                    source_a=sources[0],
                    value_a=vals[0],
                    source_b=sources[1],
                    value_b=vals[1],
                ))

    return conflicts


def check_duplicate_releases(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Return releases with the same title from the same artist appearing more than once per source."""
    return conn.execute("""
        SELECT title, source, COUNT(*) as count
        FROM releases
        GROUP BY title, source
        HAVING COUNT(*) > 1
        ORDER BY count DESC
    """).df()


def get_validation_summary(conn: duckdb.DuckDBPyConnection) -> dict:
    """Full validation report as a dict, suitable for display or AI context."""
    source_coverage = get_source_coverage(conn)
    release_coverage = get_release_coverage(conn)
    null_fields = check_null_critical_fields(conn)
    conflicts = detect_cross_source_conflicts(conn)
    duplicate_releases = check_duplicate_releases(conn)

    releases_df = conn.execute("""
        SELECT title, year, type, source, track_count
        FROM releases
        WHERE year IS NOT NULL
        ORDER BY year DESC
        LIMIT 50
    """).df()

    artists_df = conn.execute("""
        SELECT name, source, country, formed_year, genres, popularity
        FROM artists
        LIMIT 50
    """).df()

    return {
        "source_coverage": source_coverage,
        "release_coverage": release_coverage,
        "null_critical_fields": null_fields,
        "conflict_count": len(conflicts),
        "conflicts": [
            {
                "field": c.field_name,
                "source_a": c.source_a, "value_a": c.value_a,
                "source_b": c.source_b, "value_b": c.value_b,
            }
            for c in conflicts
        ],
        "duplicate_releases": duplicate_releases.to_dict("records"),
        "releases": releases_df.to_dict("records"),
        "artists": artists_df.to_dict("records"),
    }
