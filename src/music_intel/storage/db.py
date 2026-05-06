import duckdb
import pandas as pd
from pathlib import Path
from music_intel.models import ArtistProfile, Release, Conflict

DEFAULT_DB_PATH = Path.home() / ".music_intel" / "data.duckdb"


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> duckdb.DuckDBPyConnection:
    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path))
    init_schema(conn)
    return conn


def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS artists (
            id VARCHAR NOT NULL,
            name VARCHAR,
            source VARCHAR NOT NULL,
            genres VARCHAR[],
            country VARCHAR,
            formed_year INTEGER,
            popularity INTEGER,
            listeners_lastfm INTEGER,
            play_count_lastfm INTEGER,
            image_url VARCHAR,
            fetched_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (id, source)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS releases (
            id VARCHAR NOT NULL,
            artist_id VARCHAR,
            title VARCHAR NOT NULL,
            type VARCHAR,
            year INTEGER,
            source VARCHAR NOT NULL,
            track_count INTEGER,
            discogs_price_median DECIMAL(10, 2),
            discogs_have INTEGER,
            discogs_want INTEGER,
            PRIMARY KEY (id, source)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conflicts (
            entity_type VARCHAR NOT NULL,
            field_name VARCHAR NOT NULL,
            source_a VARCHAR NOT NULL,
            value_a VARCHAR,
            source_b VARCHAR NOT NULL,
            value_b VARCHAR,
            detected_at TIMESTAMP DEFAULT NOW()
        )
    """)


def upsert_artists(conn: duckdb.DuckDBPyConnection, profiles: list[ArtistProfile]) -> None:
    if not profiles:
        return
    rows = [
        (p.id, p.name, p.source, p.genres, p.country, p.formed_year,
         p.popularity, p.listeners_lastfm, p.play_count_lastfm, p.image_url)
        for p in profiles
    ]
    conn.executemany("""
        INSERT OR REPLACE INTO artists
            (id, name, source, genres, country, formed_year, popularity,
             listeners_lastfm, play_count_lastfm, image_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)


def upsert_releases(conn: duckdb.DuckDBPyConnection, releases: list[Release]) -> None:
    if not releases:
        return
    rows = [
        (r.id, r.artist_id, r.title, r.type, r.year, r.source,
         r.track_count, r.discogs_price_median, r.discogs_have, r.discogs_want)
        for r in releases
    ]
    conn.executemany("""
        INSERT OR REPLACE INTO releases
            (id, artist_id, title, type, year, source, track_count,
             discogs_price_median, discogs_have, discogs_want)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)


def insert_conflicts(conn: duckdb.DuckDBPyConnection, conflicts: list[Conflict]) -> None:
    if not conflicts:
        return
    rows = [
        (c.entity_type, c.field_name, c.source_a, c.value_a, c.source_b, c.value_b)
        for c in conflicts
    ]
    conn.executemany("""
        INSERT INTO conflicts (entity_type, field_name, source_a, value_a, source_b, value_b)
        VALUES (?, ?, ?, ?, ?, ?)
    """, rows)


def get_artists_df(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return conn.execute("SELECT * FROM artists").df()


def get_releases_df(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return conn.execute("SELECT * FROM releases ORDER BY year DESC NULLS LAST").df()


def get_conflicts_df(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return conn.execute("SELECT * FROM conflicts ORDER BY detected_at DESC").df()


def clear_artist_data(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("DELETE FROM artists")
    conn.execute("DELETE FROM releases")
    conn.execute("DELETE FROM conflicts")
