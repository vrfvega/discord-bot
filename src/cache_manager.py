from typing import Dict, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, Session, SQLModel, create_engine, select


class CacheEntry(SQLModel, table=True):
    source_url: str = Field(primary_key=True)
    stream_url: str = Field(nullable=False)
    meta: Optional[Dict[str, str]] = Field(sa_column=Column(JSON, nullable=True))


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
                existing_entry.stream_url = entry.stream_url
                existing_entry.meta = entry.meta
            else:
                session.add(entry)

            session.commit()
