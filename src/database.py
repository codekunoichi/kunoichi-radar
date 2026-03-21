import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, Column, Integer, String, DateTime, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class Repo(Base):
    __tablename__ = "repos"

    repo_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, default="")
    stars = Column(Integer, default=0)
    url = Column(String, nullable=False)
    topics = Column(String, default="")
    category = Column(String, nullable=False)
    created_at = Column(String)
    pushed_at = Column(String)
    last_fetched = Column(String)

    def to_dict(self) -> dict:
        return {
            "repo_id": self.repo_id,
            "name": self.name,
            "description": self.description,
            "stars": self.stars,
            "url": self.url,
            "topics": self.topics.split(",") if self.topics else [],
            "category": self.category,
            "created_at": self.created_at,
            "pushed_at": self.pushed_at,
            "last_fetched": self.last_fetched,
        }


def get_engine(db_path: str = "data/radar.db"):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine) -> Session:
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def upsert_repos(session: Session, repos: list[dict]) -> int:
    """Insert or update repos by repo_id. Returns count of upserted rows."""
    count = 0
    for repo_data in repos:
        existing = session.get(Repo, repo_data["repo_id"])
        if existing:
            for key, value in repo_data.items():
                setattr(existing, key, value)
        else:
            session.add(Repo(**repo_data))
        count += 1

    session.commit()
    logger.info("Upserted %d repos", count)
    return count


def get_repos(
    session: Session,
    category: str | None = None,
    min_stars: int = 0,
    pushed_after: str | None = None,
    pushed_before: str | None = None,
) -> list[dict]:
    query = session.query(Repo)

    if category:
        query = query.filter(Repo.category == category)
    if min_stars:
        query = query.filter(Repo.stars >= min_stars)
    if pushed_after:
        query = query.filter(Repo.pushed_at >= pushed_after)
    if pushed_before:
        query = query.filter(Repo.pushed_at <= pushed_before)

    query = query.order_by(Repo.stars.desc())
    return [repo.to_dict() for repo in query.all()]


def get_categories(session: Session) -> list[str]:
    rows = session.query(Repo.category).distinct().all()
    return [row[0] for row in rows]


def get_last_fetched(session: Session) -> str | None:
    result = session.query(Repo.last_fetched).order_by(Repo.last_fetched.desc()).first()
    return result[0] if result else None
