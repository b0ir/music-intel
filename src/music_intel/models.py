from dataclasses import dataclass, field


@dataclass
class ArtistProfile:
    id: str
    name: str
    source: str
    genres: list[str] = field(default_factory=list)
    country: str | None = None
    formed_year: int | None = None
    popularity: int | None = None
    listeners_lastfm: int | None = None
    play_count_lastfm: int | None = None
    image_url: str | None = None


@dataclass
class Release:
    id: str
    artist_id: str
    title: str
    source: str
    type: str | None = None         # 'album' | 'single' | 'ep'
    year: int | None = None
    track_count: int | None = None
    discogs_price_median: float | None = None
    discogs_have: int | None = None
    discogs_want: int | None = None


@dataclass
class Conflict:
    entity_type: str
    field_name: str
    source_a: str
    value_a: str
    source_b: str
    value_b: str


@dataclass
class Track:
    id: str
    name: str
    artist: str
    album: str | None = None
    preview_url: str | None = None
    spotify_url: str | None = None
