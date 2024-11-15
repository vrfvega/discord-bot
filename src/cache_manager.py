from sqlmodel import Field, Session, SQLModel, create_engine, select


class CacheEntry(SQLModel, table=True):
    source_url: str = Field(primary_key=True)
    audio_stream_url: str = Field(nullable=False)
    is_opus: bool | None = None  # Optional field for Opus check


class CacheManager:
    def __init__(self, db_url="sqlite:///cache.db"):
        self.engine = create_engine(db_url)
        SQLModel.metadata.create_all(self.engine)

    def get_entry(self, source_url: str) -> CacheEntry | None:
        """Retrieve a cache entry by source URL."""
        with Session(self.engine) as session:
            return session.exec(
                select(CacheEntry).where(CacheEntry.source_url == source_url)
            ).first()

    def save_entry(self, entry: CacheEntry):
        """Save or update a cache entry."""
        with Session(self.engine) as session:
            existing_entry = session.exec(
                select(CacheEntry).where(CacheEntry.source_url == entry.source_url)
            ).first()
            if existing_entry:
                existing_entry.audio_stream_url = entry.audio_stream_url
                existing_entry.is_opus = entry.is_opus
            else:
                session.add(entry)

            session.commit()

    def get_entry_by_stream_url(self, stream_url: str) -> CacheEntry | None:
        """Retrieve a cache entry by audio stream URL."""
        with Session(self.engine) as session:
            return session.exec(
                select(CacheEntry).where(CacheEntry.audio_stream_url == stream_url)
            ).first()

    def update_is_opus_by_stream_url(self, audio_stream_url: str, is_opus: bool):
        """
        Update the is_opus field for a cache entry based on the audio_stream_url.
        :param audio_stream_url: The audio stream URL to search for.
        :param is_opus: The new value for the is_opus field.
        """
        with Session(self.engine) as session:
            entry = session.exec(
                select(CacheEntry).where(
                    CacheEntry.audio_stream_url == audio_stream_url
                )
            ).first()
            if not entry:
                raise ValueError(
                    f"No entry found with audio_stream_url: {audio_stream_url}"
                )

            # Update the is_opus field
            entry.is_opus = is_opus
            session.commit()
